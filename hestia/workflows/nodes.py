"""
Node executor registry — per-type execution functions for workflow nodes.

Each executor takes (node_config, input_data) and returns a result dict.
The DAGExecutor calls these through the NODE_EXECUTORS registry.
"""

import asyncio
import operator
from typing import Any, Callable, Coroutine, Dict, Optional

from hestia.logging import get_logger, LogComponent
from hestia.workflows.models import NodeType

logger = get_logger()

# Type alias for executor functions
NodeExecutorFn = Callable[
    [Dict[str, Any], Dict[str, Any]],
    Coroutine[Any, Any, Dict[str, Any]],
]


# ── Safe condition evaluator ─────────────────────────────────────────

# Allowed operators for if_else conditions — never arbitrary code execution
_OPERATORS: Dict[str, Callable] = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "ge": operator.ge,
    "lt": operator.lt,
    "le": operator.le,
    "contains": operator.contains,
    "not_contains": lambda a, b: not operator.contains(a, b),
    "is_empty": lambda a, _: not a,
    "is_not_empty": lambda a, _: bool(a),
    "is_true": lambda a, _: bool(a),
    "is_false": lambda a, _: not bool(a),
}


def evaluate_condition(condition: Dict[str, Any], input_data: Dict[str, Any]) -> bool:
    """
    Evaluate a condition safely against input data.

    Condition format:
        {"field": "response", "operator": "contains", "value": "urgent"}
    or:
        {"field": "confidence", "operator": "gt", "value": 0.8}

    The field is looked up in input_data using dot-path traversal.
    """
    field_path = condition.get("field", "")
    op_name = condition.get("operator", "is_true")
    expected = condition.get("value")

    # Traverse dot-path to get actual value
    actual = _resolve_path(input_data, field_path)

    op_fn = _OPERATORS.get(op_name)
    if op_fn is None:
        logger.warning(
            f"Unknown condition operator '{op_name}', defaulting to false",
            component=LogComponent.WORKFLOW,
        )
        return False

    try:
        return bool(op_fn(actual, expected))
    except (TypeError, ValueError):
        return False


def _resolve_path(data: Dict[str, Any], path: str) -> Any:
    """Resolve a dot-path like 'response.content' against a nested dict."""
    if not path:
        return data

    current: Any = data
    for key in path.split("."):
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current


# ── Node Executors ───────────────────────────────────────────────────


async def execute_run_prompt(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    adapter: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Execute a RunPrompt node — sends prompt through WorkflowHandlerAdapter.

    Config keys:
        prompt (str): The prompt to send (required)
        agent_mode (str): Optional agent override (artemis/apollo)
        memory_write (bool): Whether to persist to memory
        force_local (bool): Force local inference
        allowed_tools (list): Tool allowlist
    """
    from hestia.workflows.models import WorkflowExecutionConfig, SessionStrategy

    if adapter is None:
        from hestia.workflows.adapter import WorkflowHandlerAdapter
        from hestia.orchestration.handler import get_request_handler
        handler = await get_request_handler()
        adapter = WorkflowHandlerAdapter(handler)

    prompt = config.get("prompt", "")
    if not prompt:
        return {"error": "No prompt configured", "response": ""}

    exec_config = WorkflowExecutionConfig(
        session_strategy=SessionStrategy(config.get("session_strategy", "ephemeral")),
        memory_write=config.get("memory_write", False),
        memory_read=config.get("memory_read", True),
        force_local=config.get("force_local", False),
        agent_mode=config.get("agent_mode"),
        allowed_tools=config.get("allowed_tools"),
    )

    response = await adapter.execute(prompt, exec_config)

    return {
        "response": response.content or "",
        "tokens_in": response.tokens_in,
        "tokens_out": response.tokens_out,
        "duration_ms": response.duration_ms,
        "error": response.error_code,
    }


async def execute_call_tool(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute a CallTool node — calls ToolExecutor directly (no LLM).

    Config keys:
        tool_name (str): Tool to execute (required)
        arguments (dict): Arguments to pass to the tool
    """
    from hestia.execution.models import ToolCall
    from hestia.execution.executor import ToolExecutor

    tool_name = config.get("tool_name", "")
    arguments = config.get("arguments", {})

    if not tool_name:
        return {"error": "No tool_name configured", "result": ""}

    call = ToolCall(
        id=f"wf-{tool_name}",
        tool_name=tool_name,
        arguments=arguments,
    )
    executor = ToolExecutor()
    result = await executor.execute(call)

    return {
        "result": result.output if hasattr(result, "output") else str(result),
        "tool_name": tool_name,
        "success": not (hasattr(result, "error") and result.error),
    }


async def execute_notify(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute a Notify node — sends notification via NotificationManager.

    Config keys:
        title (str): Notification title
        body (str): Notification body
        priority (str): "normal" or "high"
    """
    title = config.get("title", "Workflow Notification")
    body = config.get("body") or config.get("message", "")
    priority = config.get("priority", "normal")

    try:
        from hestia.notifications import get_notification_manager
        manager = await get_notification_manager()
        bump = await manager.create_bump(
            title=title,
            body=body,
            priority=priority,
            context={"source": "workflow"},
        )
        return {"delivered": True, "bump_id": bump.get("id", ""), "title": title}
    except Exception as e:
        # Notifications are best-effort — don't fail the workflow
        logger.warning(
            f"Notification delivery failed: {type(e).__name__}",
            component=LogComponent.WORKFLOW,
        )
        return {"delivered": False, "error": type(e).__name__, "title": title}


async def execute_log(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute a Log node — writes to Hestia logger.

    Config keys:
        message (str): Log message
        level (str): "info" or "warning"
    """
    message = config.get("message", "Workflow log")
    level = config.get("level", "info")

    if level == "warning":
        logger.warning(message, component=LogComponent.WORKFLOW)
    else:
        logger.info(message, component=LogComponent.WORKFLOW)

    return {"logged": True, "message": message, "level": level}


async def execute_if_else(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute an IfElse condition node — evaluates condition, returns branch.

    Config keys:
        condition (dict): {"field": "...", "operator": "...", "value": ...}

    Returns:
        {"branch": "true"} or {"branch": "false"}
    """
    condition = config.get("condition", {})
    if not condition:
        return {"branch": "false", "reason": "No condition configured"}

    result = evaluate_condition(condition, input_data)
    return {"branch": "true" if result else "false", "evaluated": True}


async def execute_switch(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute a Switch node — N-ary condition branching.

    Config keys:
        field (str): dot-path to evaluate in input_data
        cases (list): [{"value": ..., "label": "case_X"}, ...]
        default_label (str): label for no-match fallback

    Returns:
        {"branch": "case_X"} — the label of the matched case
    """
    field_path = config.get("field", "")
    cases = config.get("cases", [])
    default_label = config.get("default_label", "default")

    actual = _resolve_path(input_data, field_path)

    for case in cases:
        if actual == case.get("value"):
            return {"branch": case["label"], "matched_value": actual}

    return {"branch": default_label, "matched_value": actual}


async def execute_trigger_noop(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """Trigger nodes are no-ops at execution time — they initiate the DAG."""
    return {"triggered": True}


async def execute_delay(
    config: Dict[str, Any],
    input_data: Dict[str, Any],
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Execute a Delay node — pauses execution for configured seconds.

    Config keys:
        delay_seconds (float): How long to wait (max 180 days, default 0)

    Returns input_data passthrough plus delay metadata.
    """
    import time

    max_delay = 180 * 86400  # 180 days in seconds
    delay = float(config.get("delay_seconds", 0))
    delay = max(0, min(delay, max_delay))

    start = time.monotonic()
    if delay > 0:
        await asyncio.sleep(delay)
    elapsed_ms = int((time.monotonic() - start) * 1000)

    return {
        "delayed": True,
        "delay_seconds": delay,
        "elapsed_ms": elapsed_ms,
        "input_data": input_data,
    }


# ── Registry ─────────────────────────────────────────────────────────

NODE_EXECUTORS: Dict[NodeType, NodeExecutorFn] = {
    NodeType.RUN_PROMPT: execute_run_prompt,
    NodeType.CALL_TOOL: execute_call_tool,
    NodeType.NOTIFY: execute_notify,
    NodeType.LOG: execute_log,
    NodeType.IF_ELSE: execute_if_else,
    NodeType.SWITCH: execute_switch,
    NodeType.SCHEDULE: execute_trigger_noop,
    NodeType.MANUAL: execute_trigger_noop,
    NodeType.DELAY: execute_delay,
}
