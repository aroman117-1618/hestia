"""EngineerAgent — implementation tier for the Hestia Agentic Dev System.

Calls Claude Sonnet via the cloud client to execute a single well-scoped
subtask. Runs a tool loop (max 25 iterations) and returns a structured
result dict.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from hestia.cloud.models import CloudProvider
from hestia.dev.context_builder import DevContextBuilder
from hestia.dev.models import AgentTier, DevSession
from hestia.dev.safety import AuthorityMatrix
from hestia.execution import get_tool_executor, get_tool_registry
from hestia.inference.client import Message
from hestia.logging import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_TOOL_ITERATIONS: int = 25
MAX_TOKENS_PER_SUBTASK: int = 150_000


class EngineerAgent:
    """Implementation agent backed by Claude Sonnet.

    Receives a single subtask from the Architect, builds context, then drives
    a cloud LLM through a tool loop until the task is complete or the iteration
    / token budget is exhausted.
    """

    def __init__(
        self,
        cloud_client: Any,
        memory_bridge: Optional[Any] = None,
    ) -> None:
        self._cloud = cloud_client
        self._memory = memory_bridge
        self._context_builder = DevContextBuilder()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_subtask(
        self,
        session: DevSession,
        subtask: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single subtask and return a result dict.

        Returns:
            {
                "content": str,           # final model response text
                "tokens_used": int,        # total tokens consumed
                "iterations": int,         # number of tool-call iterations
                "files_affected": list[str],
            }
        """
        # Retrieve optional memory context — failures are silenced
        memory_learnings: Optional[str] = None
        codebase_invariants: Optional[str] = None
        if self._memory is not None:
            try:
                memory_learnings = await self._memory.retrieve_for_engineer(session.id)
            except Exception as exc:
                logger.warning(
                    f"EngineerAgent: memory_bridge.retrieve_for_engineer failed: {type(exc).__name__}"
                )
            try:
                codebase_invariants = await self._memory.retrieve_invariants(session.id)
            except Exception as exc:
                logger.warning(
                    f"EngineerAgent: memory_bridge.retrieve_invariants failed: {type(exc).__name__}"
                )

        ctx = self._context_builder.build_engineer_context(
            session=session,
            subtask=subtask,
            memory_learnings=memory_learnings,
            codebase_invariants=codebase_invariants,
        )

        # Build tool list filtered by Engineer authority
        allowed_tools = self._build_allowed_tools()

        api_key = await self._get_api_key()

        # Assemble messages
        messages: List[Message] = [
            Message(role=m["role"], content=m["content"])
            for m in ctx["messages"]
        ]

        tokens_used: int = 0
        iterations: int = 0
        final_content: str = ""

        # Initial call
        try:
            response = await self._cloud.complete(
                provider=self._get_provider(),
                model_id=session.engineer_model,
                api_key=api_key,
                messages=messages,
                system=ctx["system_prompt"],
                max_tokens=8192,
                temperature=0.0,
                tools=allowed_tools if allowed_tools else None,
            )
        except Exception as exc:
            logger.warning(f"EngineerAgent initial call failed: {type(exc).__name__}")
            raise

        tokens_used += response.tokens_in + response.tokens_out
        final_content = response.content

        # Tool loop
        executor = await get_tool_executor()
        while (
            response.tool_calls
            and iterations < MAX_TOOL_ITERATIONS
            and tokens_used < MAX_TOKENS_PER_SUBTASK
        ):
            iterations += 1

            # Append assistant message with tool calls
            messages.append(Message(
                role="assistant",
                content=response.content or "",
                tool_calls=response.tool_calls,
            ))

            # Execute each tool call
            tool_results: List[str] = []
            for tc in response.tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                tool_args = fn.get("arguments", {})

                if not AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, tool_name):
                    tool_results.append(
                        f"[DENIED] Tool '{tool_name}' is not permitted for the Engineer tier."
                    )
                    continue

                try:
                    from hestia.execution import ToolCall
                    call = ToolCall.create(tool_name, tool_args if isinstance(tool_args, dict) else {})
                    result = await executor.execute(call)
                    tool_results.append(result.output if result.success else f"[ERROR] {result.error}")
                except Exception as exc:
                    logger.warning(f"EngineerAgent tool execution error ({tool_name}): {type(exc).__name__}")
                    tool_results.append(f"[ERROR] Tool execution failed: {type(exc).__name__}")

            # Append tool results as a user message
            messages.append(Message(
                role="user",
                content="\n\n".join(tool_results),
            ))

            # Follow-up call
            try:
                response = await self._cloud.complete(
                    provider=self._get_provider(),
                    model_id=session.engineer_model,
                    api_key=api_key,
                    messages=messages,
                    system=ctx["system_prompt"],
                    max_tokens=8192,
                    temperature=0.0,
                    tools=allowed_tools if allowed_tools else None,
                )
            except Exception as exc:
                logger.warning(f"EngineerAgent tool-loop call failed: {type(exc).__name__}")
                break

            tokens_used += response.tokens_in + response.tokens_out
            final_content = response.content

        # Accumulate on session
        session.tokens_used += tokens_used

        files_affected: List[str] = subtask.get("target_files", subtask.get("files", []))

        logger.info(
            f"Engineer subtask complete for session {session.id!r}: "
            f"iterations={iterations}, tokens={tokens_used}"
        )

        return {
            "content": final_content,
            "tokens_used": tokens_used,
            "iterations": iterations,
            "files_affected": files_affected,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_allowed_tools(self) -> List[Dict[str, Any]]:
        """Return tool definitions filtered to the Engineer's authority."""
        registry = get_tool_registry()
        all_tools: List[Dict[str, Any]] = registry.get_definitions_as_list()
        return [
            t for t in all_tools
            if AuthorityMatrix.can_use_tool(
                AgentTier.ENGINEER,
                t.get("function", {}).get("name", ""),
            )
        ]

    def _get_provider(self) -> CloudProvider:
        """Return the cloud provider for this agent."""
        return CloudProvider.ANTHROPIC

    async def _get_api_key(self) -> Optional[str]:
        """Retrieve the Anthropic API key from CloudManager."""
        try:
            from hestia.cloud.manager import get_cloud_manager
            manager = await get_cloud_manager()
            return await manager.get_api_key(CloudProvider.ANTHROPIC)
        except Exception as exc:
            logger.warning(f"EngineerAgent: Could not retrieve Anthropic API key: {type(exc).__name__}")
            return None
