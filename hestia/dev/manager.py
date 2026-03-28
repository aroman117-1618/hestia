"""DevSessionManager — session lifecycle orchestrator for the Hestia Agentic Dev System."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from hestia.dev.database import DevDatabase
from hestia.dev.models import (
    AgentTier,
    DevEvent,
    DevEventType,
    DevPriority,
    DevSession,
    DevSessionSource,
    DevSessionState,
    VALID_TRANSITIONS,
)
from hestia.logging import get_logger

logger = get_logger()

_instance: Optional["DevSessionManager"] = None


class DevSessionManager:
    """Orchestrates the lifecycle of agentic dev sessions."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db = DevDatabase(db_path=db_path) if db_path else DevDatabase()
        self._initialized = False

    async def initialize(self) -> None:
        if not self._initialized:
            await self._db.connect()
            self._initialized = True
            logger.info("DevSessionManager initialized")

    async def shutdown(self) -> None:
        if self._initialized:
            await self._db.close()
            self._initialized = False
            logger.info("DevSessionManager shut down")

    # ------------------------------------------------------------------
    # Session CRUD
    # ------------------------------------------------------------------

    async def create_session(
        self,
        title: str,
        description: str,
        source: DevSessionSource,
        source_ref: Optional[str] = None,
        priority: DevPriority = DevPriority.NORMAL,
    ) -> DevSession:
        """Create a new QUEUED session and persist it."""
        session = DevSession.create(
            title=title,
            description=description,
            source=source,
            source_ref=source_ref,
            priority=priority,
        )
        await self._db.save_session(session)
        logger.info(f"Created dev session {session.id!r} ({title!r})")
        return session

    async def get_session(self, session_id: str) -> Optional[DevSession]:
        """Return a session by ID, or None if not found."""
        return await self._db.get_session(session_id)

    async def list_sessions(
        self,
        state: Optional[DevSessionState] = None,
        limit: int = 50,
    ) -> List[DevSession]:
        """List sessions, optionally filtered by state."""
        return await self._db.list_sessions(state=state, limit=limit)

    async def list_pending_proposals(self) -> List[DevSession]:
        """Return all sessions awaiting approval (state == PROPOSED)."""
        return await self._db.get_pending_proposals()

    # ------------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------------

    async def transition(
        self, session_id: str, target_state: DevSessionState
    ) -> DevSession:
        """Validate and apply a state transition, updating timestamps as needed.

        Raises ValueError if the session is not found or the transition is invalid.
        """
        session = await self._db.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id!r}")

        previous_state = session.state

        # This raises ValueError on invalid transitions
        session.transition(target_state)

        now = datetime.now(timezone.utc).isoformat()

        if target_state == DevSessionState.EXECUTING and session.started_at is None:
            session.started_at = now

        if target_state in (DevSessionState.COMPLETE, DevSessionState.CANCELLED):
            session.completed_at = now

        await self._db.update_session(session)

        logger.info(
            f"Session {session_id!r} transitioned {previous_state.value} -> {target_state.value}"
        )

        await self._log_state_change_event(
            session_id=session_id,
            previous_state=previous_state,
            new_state=target_state,
        )

        return session

    async def approve_session(
        self, session_id: str, approved_by: str = "andrew"
    ) -> DevSession:
        """Approve a PROPOSED session and move it to EXECUTING.

        Raises ValueError if the session is not in PROPOSED state.
        """
        session = await self._db.get_session(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id!r}")

        if session.state != DevSessionState.PROPOSED:
            raise ValueError(
                f"Can only approve sessions in PROPOSED state; "
                f"session {session_id!r} is in {session.state.value!r}"
            )

        now = datetime.now(timezone.utc).isoformat()
        session.approved_at = now
        session.approved_by = approved_by

        # Apply the PROPOSED -> EXECUTING transition
        previous_state = session.state
        session.transition(DevSessionState.EXECUTING)

        if session.started_at is None:
            session.started_at = now

        await self._db.update_session(session)

        logger.info(
            f"Session {session_id!r} approved by {approved_by!r}, transitioning to EXECUTING"
        )

        await self._log_state_change_event(
            session_id=session_id,
            previous_state=previous_state,
            new_state=DevSessionState.EXECUTING,
            extra={"approved_by": approved_by},
        )

        # Record the approval-granted event
        approval_event = DevEvent.create(
            session_id=session_id,
            event_type=DevEventType.APPROVAL_GRANTED,
            data={"approved_by": approved_by, "approved_at": now},
        )
        await self._db.save_event(approval_event)

        return session

    async def cancel_session(self, session_id: str) -> DevSession:
        """Cancel a session from any cancellable state.

        Raises ValueError if the session is not found or CANCELLED is not reachable.
        """
        return await self.transition(session_id, DevSessionState.CANCELLED)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def record_event(
        self,
        session_id: str,
        agent: AgentTier,
        event_type: DevEventType,
        detail: Optional[str] = None,
        tokens_used: int = 0,
        model: Optional[str] = None,
        files_affected: Optional[List[str]] = None,
    ) -> None:
        """Persist a dev event for the given session."""
        data: dict = {}
        if detail is not None:
            data["detail"] = detail
        if tokens_used:
            data["tokens_used"] = tokens_used
        if model is not None:
            data["model"] = model
        if files_affected is not None:
            data["files_affected"] = files_affected

        event = DevEvent.create(
            session_id=session_id,
            event_type=event_type,
            agent_tier=agent,
            data=data,
        )
        await self._db.save_event(event)

    async def get_events(
        self,
        session_id: str,
        event_type: Optional[DevEventType] = None,
    ) -> List[DevEvent]:
        """Return events for the given session, optionally filtered by type."""
        return await self._db.list_events(session_id=session_id, event_type=event_type)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _log_state_change_event(
        self,
        session_id: str,
        previous_state: DevSessionState,
        new_state: DevSessionState,
        extra: Optional[dict] = None,
    ) -> None:
        data: dict = {
            "from": previous_state.value,
            "to": new_state.value,
        }
        if extra:
            data.update(extra)
        event = DevEvent.create(
            session_id=session_id,
            event_type=DevEventType.STATE_CHANGE,
            data=data,
        )
        await self._db.save_event(event)


async def get_dev_session_manager() -> DevSessionManager:
    """Singleton factory — returns the shared DevSessionManager instance."""
    global _instance
    if _instance is None:
        _instance = DevSessionManager()
        await _instance.initialize()
    return _instance
