"""DevOrchestrator — drives sessions through the full Architect → Engineer → Validator lifecycle."""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent
from hestia.dev.models import (
    DevSession, DevSessionState, DevComplexity, AgentTier, DevEventType,
)

logger = get_logger()
PROJECT_ROOT = Path.home() / "hestia"


class DevOrchestrator:
    """Orchestrates the full dev session lifecycle.

    Flow: PLANNING → [RESEARCHING] → PROPOSED → [approval gate] → EXECUTING → VALIDATING → REVIEWING → COMPLETE
    """

    def __init__(
        self,
        manager: Any,
        architect: Any,
        engineer: Any,
        validator: Optional[Any] = None,
        researcher: Optional[Any] = None,
        proposal_delivery: Optional[Any] = None,
        memory_bridge: Optional[Any] = None,
    ) -> None:
        self._manager = manager
        self._architect = architect
        self._engineer = engineer
        self._validator = validator
        self._researcher = researcher
        self._delivery = proposal_delivery
        self._memory = memory_bridge

    async def run_planning_phase(self, session_id: str) -> DevSession:
        """QUEUED → PLANNING → [RESEARCHING →] PROPOSED.

        Architect analyzes the task, optionally invokes Researcher for complex tasks,
        produces a plan, and transitions to PROPOSED (awaiting approval).
        """
        session = await self._manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Transition to PLANNING
        session = await self._manager.transition(session_id, DevSessionState.PLANNING)

        # Create git branch
        branch_name = f"hestia/dev-{session_id[-8:]}"
        self._create_branch(branch_name)
        session.branch_name = branch_name
        await self._manager._db.update_session(session)

        # Architect creates plan
        plan = await self._architect.create_plan(session, session.description)

        await self._manager.record_event(
            session_id=session_id,
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.PLAN_CREATED,
            detail=plan,
        )

        # If complex, invoke Researcher
        complexity = plan.get("complexity", "medium")
        if complexity in ("complex", "critical") and self._researcher:
            session = await self._manager.transition(session_id, DevSessionState.RESEARCHING)
            research = await self._researcher.analyze(
                session, f"Deep analysis for: {session.title}", plan.get("files", []),
            )
            await self._manager.record_event(
                session_id=session_id,
                agent=AgentTier.RESEARCHER,
                event_type=DevEventType.RESEARCH,
                detail={"findings": research.get("findings", "")[:2000]},
                tokens_used=research.get("tokens_used", 0),
            )
            # Re-plan with researcher findings
            plan = await self._architect.create_plan(
                session, session.description, researcher_findings=research.get("findings"),
            )

        # Store plan on session
        session.plan = plan
        session.subtasks = plan.get("subtasks", [])
        session.complexity = DevComplexity(complexity) if complexity in [c.value for c in DevComplexity] else DevComplexity.MEDIUM
        await self._manager._db.update_session(session)

        # Transition to PROPOSED
        session = await self._manager.transition(session_id, DevSessionState.PROPOSED)

        # Deliver proposal
        if self._delivery:
            await self._delivery.deliver_proposal(session)

        return session

    async def run_execution_phase(self, session_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """EXECUTING → VALIDATING → [REVIEWING →] COMPLETE.

        Yields progress events for CLI streaming.
        Assumes session is already in EXECUTING state (post-approval).
        """
        session = await self._manager.get_session(session_id)
        if not session or session.state != DevSessionState.EXECUTING:
            raise ValueError(f"Session {session_id} not in EXECUTING state")

        subtasks = session.subtasks or []
        if not subtasks:
            subtasks = [{"title": session.title, "description": session.description, "files": session.plan.get("files", []) if session.plan else []}]

        total_tokens = 0

        # Checkout session branch
        self._checkout_branch(session.branch_name or "main")

        for i, subtask in enumerate(subtasks):
            session.current_subtask = i
            await self._manager._db.update_session(session)

            yield {"type": "subtask_start", "index": i, "title": subtask.get("title", f"Subtask {i+1}"), "total": len(subtasks)}

            await self._manager.record_event(
                session_id=session_id,
                agent=AgentTier.ENGINEER,
                event_type=DevEventType.SUBTASK_STARTED,
                detail={"index": i, "title": subtask.get("title", "")},
            )

            # Engineer executes
            try:
                result = await self._engineer.execute_subtask(session, subtask)
            except Exception as exc:
                logger.error(f"Engineer subtask {i} failed: {type(exc).__name__}", component=LogComponent.DEV)
                result = {"content": f"Subtask failed: {type(exc).__name__}", "tokens_used": 0, "iterations": 0, "files_affected": []}
            total_tokens += result.get("tokens_used", 0)

            yield {"type": "subtask_result", "index": i, "content": (result.get("content") or "")[:500], "files": result.get("files_affected", [])}

            await self._manager.record_event(
                session_id=session_id,
                agent=AgentTier.ENGINEER,
                event_type=DevEventType.SUBTASK_COMPLETED,
                detail={"iterations": result.get("iterations", 0), "files": result.get("files_affected", [])},
                tokens_used=result.get("tokens_used", 0),
                files_affected=result.get("files_affected", []),
            )

        # Transition to VALIDATING
        session = await self._manager.transition(session_id, DevSessionState.VALIDATING)
        yield {"type": "state_change", "state": "validating"}

        # Run validation
        validation_passed = True
        if self._validator:
            diff = self._get_diff(session.branch_name)
            val_result = await self._validator.validate_session(session, diff=diff)
            validation_passed = val_result.get("passed", False)

            await self._manager.record_event(
                session_id=session_id,
                agent=AgentTier.VALIDATOR,
                event_type=DevEventType.TEST_RUN,
                detail=val_result.get("test_result", {}),
            )

            yield {"type": "validation", "passed": validation_passed, "detail": val_result}

        if not validation_passed:
            session = await self._manager.transition(session_id, DevSessionState.FAILED)
            yield {"type": "state_change", "state": "failed"}
            # Store failure pattern
            if self._memory:
                await self._memory.store_failure_pattern(
                    session_id=session_id,
                    approach=session.title,
                    failure_reason="Validation failed",
                    resolution="Pending retry or replan",
                )
            return

        # Transition to REVIEWING
        session = await self._manager.transition(session_id, DevSessionState.REVIEWING)
        yield {"type": "state_change", "state": "reviewing"}

        # Architect reviews
        diff = self._get_diff(session.branch_name)
        test_output = "Tests passed" if validation_passed else "Tests failed"
        review = await self._architect.review_diff(session, diff=diff, test_results=test_output)

        await self._manager.record_event(
            session_id=session_id,
            agent=AgentTier.ARCHITECT,
            event_type=DevEventType.REVIEW,
            detail=review,
        )

        yield {"type": "review", "approved": review.get("approved", False), "feedback": review.get("feedback", "")}

        if not review.get("approved", False):
            session = await self._manager.transition(session_id, DevSessionState.FAILED)
            yield {"type": "state_change", "state": "failed"}
            return

        # Cross-model review for critical tasks
        if self._researcher and session.complexity in (DevComplexity.COMPLEX, DevComplexity.CRITICAL):
            research_review = await self._researcher.review_code(session, diff=diff)
            yield {"type": "cross_model_review", "approved": research_review.get("approved", True)}

        # Complete
        session.total_tokens = total_tokens
        await self._manager._db.update_session(session)
        session = await self._manager.transition(session_id, DevSessionState.COMPLETE)

        # Store session summary in memory
        if self._memory:
            await self._memory.store_session_summary(
                session_id=session_id,
                title=session.title,
                description=session.description,
                files_changed=[],  # Could extract from events
                key_decisions=[review.get("feedback", "Approved")],
            )

        # Send completion notification
        if self._delivery:
            await self._delivery.send_completion_notification(session)

        yield {"type": "state_change", "state": "complete", "total_tokens": total_tokens}

    async def cancel_session(self, session_id: str) -> DevSession:
        """Cancel a session and run compensating actions."""
        session = await self._manager.cancel_session(session_id)

        # Compensating actions
        if session.branch_name:
            self._delete_remote_branch(session.branch_name)

        if self._delivery:
            await self._delivery.send_cancellation_notification(session)

        return session

    def _create_branch(self, name: str) -> None:
        try:
            subprocess.run(
                ["git", "checkout", "-b", name],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
            )
        except Exception as e:
            logger.warning(f"Branch creation failed: {type(e).__name__}", component=LogComponent.DEV)

    def _checkout_branch(self, name: str) -> None:
        try:
            subprocess.run(
                ["git", "checkout", name],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=10,
            )
        except Exception:
            pass

    def _get_diff(self, branch: Optional[str]) -> str:
        try:
            result = subprocess.run(
                ["git", "diff", "main..HEAD"],
                cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=10,
            )
            return result.stdout[:30000]
        except Exception:
            return ""

    def _delete_remote_branch(self, name: str) -> None:
        try:
            subprocess.run(
                ["git", "push", "origin", "--delete", name],
                cwd=str(PROJECT_ROOT), capture_output=True, timeout=15,
            )
        except Exception:
            pass
