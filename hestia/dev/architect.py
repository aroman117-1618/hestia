from __future__ import annotations
"""ArchitectAgent — planning and review tier for the Hestia Agentic Dev System.

Calls Claude Opus via the cloud client to produce structured JSON plans and
diff reviews. All cloud I/O is async.
"""

import json
import re
from typing import Any, Dict, List, Optional

from hestia.cloud.models import CloudProvider
from hestia.dev.context_builder import DevContextBuilder
from hestia.dev.models import DevSession
from hestia.inference.client import Message
from hestia.logging import get_logger

logger = get_logger()

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

_PLAN_SYSTEM = (
    "You are the Architect for the Hestia Agentic Development System. "
    "Produce a rigorous, actionable implementation plan as a single JSON object "
    "with these exact keys: steps (list of strings), files (list of file paths), "
    "risk (string: low/medium/high/critical), estimated_minutes (integer), "
    "complexity (string: simple/medium/complex/critical), "
    "subtasks (list of objects with keys: title, files). "
    "Return ONLY the JSON — no prose, no markdown fences."
)

_REVIEW_SYSTEM = (
    "You are the Architect reviewing an implementation diff for the Hestia project. "
    "Evaluate correctness, code conventions, and test coverage. "
    "Return a single JSON object with these exact keys: "
    "approved (boolean), feedback (string), issues (list of strings). "
    "Return ONLY the JSON — no prose, no markdown fences."
)


class ArchitectAgent:
    """Planning and review agent backed by Claude Opus."""

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

    async def create_plan(
        self,
        session: DevSession,
        task_description: str,
        researcher_findings: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build architect context, call Opus, parse and return the plan dict.

        Returns a dict with keys: steps, files, risk, estimated_minutes,
        complexity, subtasks.
        """
        # Optionally pull memory context
        memory_context: Optional[str] = None
        if self._memory is not None:
            try:
                memory_context = await self._memory.get_context(session.id)
            except Exception as exc:
                logger.warning(f"Memory bridge unavailable during plan creation: {type(exc).__name__}")

        ctx = self._context_builder.build_architect_context(
            session=session,
            task_description=task_description,
            memory_context=memory_context,
            researcher_findings=researcher_findings,
        )

        api_key = await self._get_api_key()
        messages = [
            Message(role=m["role"], content=m["content"])
            for m in ctx["messages"]
        ]

        try:
            response = await self._cloud.complete(
                provider=self._get_provider(),
                model_id=session.architect_model,
                api_key=api_key,
                messages=messages,
                system=_PLAN_SYSTEM,
                max_tokens=8192,
                temperature=0.0,
            )
        except Exception as exc:
            logger.warning(f"Architect plan call failed: {type(exc).__name__}")
            raise

        plan = self._parse_plan(response.content)
        session.tokens_used += response.tokens_in + response.tokens_out

        logger.info(
            f"Architect plan created for session {session.id!r}: "
            f"complexity={plan.get('complexity')}, steps={len(plan.get('steps', []))}"
        )
        return plan

    async def review_diff(
        self,
        session: DevSession,
        diff: str,
        test_results: str,
    ) -> Dict[str, Any]:
        """Ask the Architect to review a diff and test output.

        Returns a dict with keys: approved (bool), feedback (str), issues (list).
        """
        content = (
            f"## Diff\n\n```diff\n{diff[:15_000]}\n```\n\n"
            f"## Test Results\n\n```\n{test_results[:10_000]}\n```"
        )

        api_key = await self._get_api_key()

        try:
            response = await self._cloud.complete(
                provider=self._get_provider(),
                model_id=session.architect_model,
                api_key=api_key,
                messages=[Message(role="user", content=content)],
                system=_REVIEW_SYSTEM,
                max_tokens=4096,
                temperature=0.0,
            )
        except Exception as exc:
            logger.warning(f"Architect review call failed: {type(exc).__name__}")
            raise

        default: Dict[str, Any] = {"approved": False, "feedback": "", "issues": []}
        result = self._parse_json_response(response.content, default)
        session.tokens_used += response.tokens_in + response.tokens_out

        # Normalise types
        if not isinstance(result.get("approved"), bool):
            result["approved"] = bool(result.get("approved", False))
        if not isinstance(result.get("feedback"), str):
            result["feedback"] = str(result.get("feedback", ""))
        if not isinstance(result.get("issues"), list):
            result["issues"] = []

        logger.info(
            f"Architect review for session {session.id!r}: approved={result['approved']}"
        )
        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_plan(self, content: str) -> Dict[str, Any]:
        """Extract and validate the plan JSON from a raw LLM response."""
        default: Dict[str, Any] = {
            "steps": [],
            "files": [],
            "risk": "unknown",
            "estimated_minutes": 0,
            "complexity": "simple",
            "subtasks": [],
        }
        plan = self._parse_json_response(content, default)

        # Ensure required keys are present with correct types
        if not isinstance(plan.get("steps"), list):
            plan["steps"] = []
        if not isinstance(plan.get("files"), list):
            plan["files"] = []
        if not isinstance(plan.get("risk"), str):
            plan["risk"] = "unknown"
        if not isinstance(plan.get("estimated_minutes"), int):
            try:
                plan["estimated_minutes"] = int(plan.get("estimated_minutes", 0))
            except (TypeError, ValueError):
                plan["estimated_minutes"] = 0
        if not isinstance(plan.get("complexity"), str):
            plan["complexity"] = "simple"
        if not isinstance(plan.get("subtasks"), list):
            plan["subtasks"] = []

        return plan

    def _parse_json_response(self, content: str, default: Dict[str, Any]) -> Dict[str, Any]:
        """Robustly extract JSON from a response that may contain markdown fences."""
        if not content:
            return dict(default)

        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        fence_match = re.search(r"```(?:json)?\s*([\s\S]+?)```", content)
        if fence_match:
            try:
                return json.loads(fence_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Last resort: find the first { ... } block
        brace_match = re.search(r"\{[\s\S]+\}", content)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("ArchitectAgent: could not parse JSON response; using default")
        return dict(default)

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
            logger.warning(f"Could not retrieve Anthropic API key: {type(exc).__name__}")
            return None
