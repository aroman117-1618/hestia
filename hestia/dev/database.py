"""SQLite persistence for the Hestia Agentic Development System."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from hestia.database import BaseDatabase
from hestia.dev.models import (
    AgentTier,
    DevComplexity,
    DevEvent,
    DevEventType,
    DevPriority,
    DevSession,
    DevSessionSource,
    DevSessionState,
)
from hestia.logging import get_logger

logger = get_logger()

_DB_PATH = Path.home() / "hestia" / "data" / "dev.db"
_instance: Optional["DevDatabase"] = None


class DevDatabase(BaseDatabase):
    """SQLite database for dev sessions and events."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("dev", db_path or _DB_PATH)

    async def _init_schema(self) -> None:
        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS dev_sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                source TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 3,
                complexity TEXT,
                token_budget INTEGER NOT NULL DEFAULT 500000,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                retry_count INTEGER NOT NULL DEFAULT 0,
                replan_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        await self.connection.execute("""
            CREATE TABLE IF NOT EXISTS dev_session_events (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES dev_sessions(id),
                event_type TEXT NOT NULL,
                agent_tier TEXT,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL DEFAULT '{}'
            )
        """)

        await self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_dev_sessions_state ON dev_sessions(state)"
        )
        await self.connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_dev_session_events_session_id "
            "ON dev_session_events(session_id)"
        )

        await self.connection.commit()

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def save_session(self, session: DevSession) -> None:
        """INSERT a new dev session."""
        await self.connection.execute(
            """
            INSERT INTO dev_sessions (
                id, title, description, source, state, priority, complexity,
                token_budget, tokens_used, metadata, retry_count, replan_count,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.title,
                session.description,
                session.source.value,
                session.state.value,
                session.priority.value,
                session.complexity.value if session.complexity else None,
                session.token_budget,
                session.tokens_used,
                json.dumps(session.metadata),
                session.retry_count,
                session.replan_count,
                session.created_at.isoformat(),
                session.updated_at.isoformat(),
            ),
        )
        await self.connection.commit()

    async def update_session(self, session: DevSession) -> None:
        """UPDATE an existing dev session."""
        await self.connection.execute(
            """
            UPDATE dev_sessions SET
                title = ?, description = ?, source = ?, state = ?, priority = ?,
                complexity = ?, token_budget = ?, tokens_used = ?, metadata = ?,
                retry_count = ?, replan_count = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                session.title,
                session.description,
                session.source.value,
                session.state.value,
                session.priority.value,
                session.complexity.value if session.complexity else None,
                session.token_budget,
                session.tokens_used,
                json.dumps(session.metadata),
                session.retry_count,
                session.replan_count,
                session.updated_at.isoformat(),
                session.id,
            ),
        )
        await self.connection.commit()

    async def get_session(self, session_id: str) -> Optional[DevSession]:
        """SELECT a session by ID. Returns None if not found."""
        cursor = await self.connection.execute(
            "SELECT * FROM dev_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_session(row) if row else None

    async def list_sessions(
        self, state: Optional[DevSessionState] = None, limit: int = 50
    ) -> List[DevSession]:
        """SELECT sessions, optionally filtered by state."""
        if state is not None:
            cursor = await self.connection.execute(
                "SELECT * FROM dev_sessions WHERE state = ? ORDER BY created_at DESC LIMIT ?",
                (state.value, limit),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM dev_sessions ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [self._row_to_session(row) for row in rows]

    async def get_pending_proposals(self) -> List[DevSession]:
        """Return all sessions in the PROPOSED state."""
        return await self.list_sessions(state=DevSessionState.PROPOSED)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    async def save_event(self, event: DevEvent) -> str:
        """INSERT a new dev event. Returns the event id."""
        await self.connection.execute(
            """
            INSERT INTO dev_session_events (id, session_id, event_type, agent_tier, timestamp, data)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.id,
                event.session_id,
                event.event_type.value,
                event.agent_tier.value if event.agent_tier else None,
                event.timestamp.isoformat(),
                json.dumps(event.data),
            ),
        )
        await self.connection.commit()
        return event.id

    async def list_events(
        self,
        session_id: str,
        event_type: Optional[DevEventType] = None,
    ) -> List[DevEvent]:
        """SELECT events for a session, optionally filtered by event_type."""
        if event_type is not None:
            cursor = await self.connection.execute(
                "SELECT * FROM dev_session_events WHERE session_id = ? AND event_type = ? "
                "ORDER BY timestamp ASC",
                (session_id, event_type.value),
            )
        else:
            cursor = await self.connection.execute(
                "SELECT * FROM dev_session_events WHERE session_id = ? ORDER BY timestamp ASC",
                (session_id,),
            )
        rows = await cursor.fetchall()
        return [self._row_to_event(row) for row in rows]

    # ------------------------------------------------------------------
    # Row converters
    # ------------------------------------------------------------------

    def _row_to_session(self, row: object) -> DevSession:
        """Convert a sqlite Row to a DevSession dataclass."""
        from datetime import datetime, timezone

        def _parse_dt(val: str) -> datetime:
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        return DevSession(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            state=DevSessionState(row["state"]),
            source=DevSessionSource(row["source"]),
            complexity=DevComplexity(row["complexity"]) if row["complexity"] else DevComplexity.MEDIUM,
            priority=DevPriority(row["priority"]),
            token_budget=row["token_budget"],
            tokens_used=row["tokens_used"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            retry_count=row["retry_count"],
            replan_count=row["replan_count"],
            created_at=_parse_dt(row["created_at"]),
            updated_at=_parse_dt(row["updated_at"]),
        )

    def _row_to_event(self, row: object) -> DevEvent:
        """Convert a sqlite Row to a DevEvent dataclass."""
        from datetime import datetime, timezone

        def _parse_dt(val: str) -> datetime:
            dt = datetime.fromisoformat(val)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt

        return DevEvent(
            id=row["id"],
            session_id=row["session_id"],
            event_type=DevEventType(row["event_type"]),
            agent_tier=AgentTier(row["agent_tier"]) if row["agent_tier"] else None,
            timestamp=_parse_dt(row["timestamp"]),
            data=json.loads(row["data"]) if row["data"] else {},
        )


async def get_dev_database() -> DevDatabase:
    """Singleton factory — returns the shared DevDatabase instance."""
    global _instance
    if _instance is None:
        _instance = DevDatabase()
        await _instance.connect()
    return _instance
