"""WorkflowHandlerAdapter — bridge between workflow engine and RequestHandler.

This adapter constructs synthetic Request objects for background execution,
handling session management, memory scope, and agent routing configuration.
The handler has no internal auth check (auth is at the FastAPI route level),
so the adapter can call handler.handle() directly.
"""
import uuid
from typing import Optional

from hestia.logging import get_logger
from hestia.orchestration.models import Mode, Request, RequestSource, Response
from hestia.workflows.models import SessionStrategy, WorkflowExecutionConfig

logger = get_logger()

# Maps agent_mode strings to Mode enum values.
# artemis/mira -> Mode.MIRA (analysis persona)
# apollo/olly  -> Mode.OLLY (execution persona)
# tia/hestia   -> Mode.TIA  (default persona)
_MODE_MAP = {
    "tia": Mode.TIA,
    "hestia": Mode.TIA,
    "artemis": Mode.MIRA,
    "mira": Mode.MIRA,
    "apollo": Mode.OLLY,
    "olly": Mode.OLLY,
}


class WorkflowHandlerAdapter:
    """Adapts workflow execution requests into handler-compatible Requests."""

    def __init__(self, handler) -> None:
        self._handler = handler

    async def execute(
        self,
        prompt: str,
        config: Optional[WorkflowExecutionConfig] = None,
    ) -> Response:
        if config is None:
            config = WorkflowExecutionConfig()

        request = self._build_request(prompt, config)

        logger.info(
            "Workflow adapter executing prompt",
            component="workflow",
            data={
                "request_id": request.id,
                "session_strategy": config.session_strategy.value,
                "session_id": request.session_id,
                "workflow_id": config.workflow_id,
                "node_id": config.node_id,
                "memory_write": config.memory_write,
            },
        )

        try:
            response = await self._handler.handle(request)
            logger.info(
                "Workflow adapter execution complete",
                component="workflow",
                data={
                    "request_id": request.id,
                    "tokens_in": response.tokens_in,
                    "tokens_out": response.tokens_out,
                    "duration_ms": response.duration_ms,
                },
            )
            return response
        except Exception as e:
            logger.error(
                f"Workflow adapter execution failed: {type(e).__name__}",
                component="workflow",
                data={
                    "request_id": request.id,
                    "workflow_id": config.workflow_id,
                    "node_id": config.node_id,
                },
            )
            return Response(
                request_id=request.id,
                content="",
                error_code="workflow_execution_error",
                error_message=f"Workflow execution failed: {type(e).__name__}: {e}",
            )

    # Prepended to every workflow prompt so the LLM acts autonomously
    # instead of asking the user for confirmation.
    _AUTONOMOUS_DIRECTIVE = (
        "You are executing an automated workflow on behalf of the user. "
        "Act immediately — do NOT ask for confirmation, clarification, or "
        "permission. Complete all steps autonomously using the tools available "
        "to you. If a step fails, note the failure and continue.\n\n"
    )

    def _build_request(self, prompt: str, config: WorkflowExecutionConfig) -> Request:
        session_id = self._resolve_session_id(config)
        mode = self._resolve_mode(config)

        # Prepend autonomous execution directive to all workflow prompts
        prompt = self._AUTONOMOUS_DIRECTIVE + prompt

        context_hints = {
            "source_type": "workflow",
            "memory_write": config.memory_write,
            "memory_read": config.memory_read,
        }
        if config.workflow_id:
            context_hints["workflow_id"] = config.workflow_id
        if config.workflow_name:
            context_hints["workflow_name"] = config.workflow_name
        if config.node_id:
            context_hints["node_id"] = config.node_id
        if config.run_id:
            context_hints["run_id"] = config.run_id
        if config.allowed_tools is not None:
            context_hints["allowed_tools"] = config.allowed_tools

        return Request.create(
            content=prompt,
            mode=mode,
            source=RequestSource.WORKFLOW,
            session_id=session_id,
            force_local=config.force_local,
            context_hints=context_hints,
        )

    def _resolve_session_id(self, config: WorkflowExecutionConfig) -> str:
        if config.session_strategy == SessionStrategy.EPHEMERAL:
            return f"wf-eph-{uuid.uuid4().hex[:12]}"
        elif config.session_strategy == SessionStrategy.PER_RUN:
            run_id = config.run_id or uuid.uuid4().hex[:12]
            return f"wf-run-{run_id}"
        elif config.session_strategy == SessionStrategy.PERSISTENT:
            if config.session_id:
                return config.session_id
            wf_id = config.workflow_id or uuid.uuid4().hex[:12]
            return f"wf-persist-{wf_id}"
        return f"wf-{uuid.uuid4().hex[:12]}"

    def _resolve_mode(self, config: WorkflowExecutionConfig) -> Mode:
        if config.agent_mode:
            return _MODE_MAP.get(config.agent_mode.lower(), Mode.TIA)
        return Mode.TIA
