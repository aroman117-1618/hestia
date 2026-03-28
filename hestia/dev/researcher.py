"""ResearcherAgent — knowledge-gathering tier for the Hestia Agentic Dev System.

Calls Gemini 2.0 Pro via the cloud client for deep codebase analysis.
Supports targeted Q&A driven by Architect questions and cross-model code review.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.cloud.models import CloudProvider
from hestia.dev.context_builder import DevContextBuilder
from hestia.dev.models import DevSession
from hestia.inference.client import Message
from hestia.logging import get_logger

logger = get_logger()


class ResearcherAgent:
    """Knowledge-gathering agent backed by Gemini 2.0 Pro.

    Answers Architect questions about the codebase and performs cross-model
    code review as a second opinion (different model than the code author).
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

    async def analyze(
        self,
        session: DevSession,
        questions: str,
        module_paths: List[str],
    ) -> Dict[str, Any]:
        """Deep codebase analysis driven by Architect questions.

        Args:
            session: The active dev session.
            questions: A string of questions from the Architect (newline-separated
                       or free-form). Converted to a list for the context builder.
            module_paths: List of module directories or file paths to load as
                          source context.

        Returns:
            {"findings": str, "tokens_used": int}
        """
        # Retrieve memory context for delta research (skip failures silently)
        memory_ctx: Optional[str] = None
        if self._memory is not None:
            try:
                memory_ctx = await self._memory.retrieve_for_researcher(questions)
            except Exception as exc:
                logger.warning(
                    f"ResearcherAgent: memory_bridge.retrieve_for_researcher failed: {type(exc).__name__}"
                )

        # Convert flat question string to list expected by context builder
        question_list: List[str] = [
            q.strip() for q in questions.splitlines() if q.strip()
        ] or [questions]

        ctx = self._context_builder.build_researcher_context(
            session=session,
            architect_questions=question_list,
            module_paths=module_paths,
            memory_context=memory_ctx,
        )

        messages = [
            Message(role=m["role"], content=m["content"])
            for m in ctx["messages"]
        ]

        api_key = await self._get_api_key()

        try:
            response = await self._cloud.complete(
                provider=CloudProvider.GOOGLE,
                model_id=session.researcher_model,
                api_key=api_key,
                messages=messages,
                system=ctx["system_prompt"],
                max_tokens=8192,
                temperature=0.0,
            )
        except Exception as exc:
            logger.warning(f"ResearcherAgent.analyze call failed: {type(exc).__name__}")
            raise

        session.tokens_used += response.tokens_in + response.tokens_out

        logger.info(
            f"Researcher analysis complete for session {session.id!r}: "
            f"questions={len(question_list)}, modules={len(module_paths)}"
        )

        return {
            "findings": response.content,
            "tokens_used": response.tokens_in + response.tokens_out,
        }

    async def review_code(
        self,
        session: DevSession,
        diff: str,
        context: str = "",
    ) -> Dict[str, Any]:
        """Cross-model code review — Gemini reviews code written by Claude.

        Using a different model than the code author surfaces blind spots.

        Args:
            session: The active dev session.
            diff: The unified diff to review (capped at 50K chars internally).
            context: Optional additional context (task description, test results, etc.).

        Returns:
            {"approved": bool, "issues": list[str], "feedback": str, "tokens_used": int}
        """
        system = (
            "You are a code reviewer for Hestia. You are a DIFFERENT model than the code author. "
            "Find issues the author might miss. Return JSON with these exact keys: "
            '{"approved": bool, "issues": [...], "feedback": str}. '
            "Return ONLY the JSON — no prose, no markdown fences."
        )

        user_content = f"## Diff to Review\n\n```diff\n{diff[:50_000]}\n```"
        if context:
            user_content += f"\n\n{context}"

        messages = [Message(role="user", content=user_content)]
        api_key = await self._get_api_key()

        try:
            response = await self._cloud.complete(
                provider=CloudProvider.GOOGLE,
                model_id=session.researcher_model,
                api_key=api_key,
                messages=messages,
                system=system,
                max_tokens=4096,
                temperature=0.0,
            )
        except Exception as exc:
            logger.warning(f"ResearcherAgent.review_code call failed: {type(exc).__name__}")
            raise

        tokens_used = response.tokens_in + response.tokens_out
        session.tokens_used += tokens_used

        default: Dict[str, Any] = {
            "approved": False,
            "issues": [],
            "feedback": response.content,
        }
        result = self._parse_json(response.content, default)
        result["tokens_used"] = tokens_used

        # Normalise types
        if not isinstance(result.get("approved"), bool):
            result["approved"] = bool(result.get("approved", False))
        if not isinstance(result.get("issues"), list):
            result["issues"] = []
        if not isinstance(result.get("feedback"), str):
            result["feedback"] = str(result.get("feedback", ""))

        logger.info(
            f"Researcher code review for session {session.id!r}: approved={result['approved']}, "
            f"issues={len(result['issues'])}"
        )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_json(self, content: str, default: Dict[str, Any]) -> Dict[str, Any]:
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

        logger.warning("ResearcherAgent: could not parse JSON response; using default")
        return dict(default)

    async def _get_api_key(self) -> Optional[str]:
        """Retrieve the Google API key from CloudManager."""
        try:
            from hestia.cloud.manager import get_cloud_manager
            manager = await get_cloud_manager()
            return await manager.get_api_key(CloudProvider.GOOGLE)
        except Exception as exc:
            logger.warning(f"ResearcherAgent: could not retrieve Google API key: {type(exc).__name__}")
            return None
