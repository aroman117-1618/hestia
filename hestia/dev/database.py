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
                source_ref TEXT,
                state TEXT NOT NULL DEFAULT 'queued',
                priority INTEGER NOT NULL DEFAULT 3,
                complexity TEXT,
                branch_name TEXT,
                plan TEXT,
                subtasks TEXT,
                current_subtask INTEGER NOT NULL DEFAULT 0,
                architect_model TEXT NOT NULL DEFAULT 'claude-opus-4-20250514',
                engineer_model TEXT NOT NULL DEFAULT 'claude-sonnet-4-20250514',
                researcher_model TEXT NOT NULL DEFAULT 'gemini-2.0-pro',
                validator_model TEXT NOT NULL DEFAULT 'claude-haiku-4-5-20251001',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                approved_at TEXT,
                approved_by TEXT,
                token_budget INTEGER NOT NULL DEFAULT 500000,
                tokens_used INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                total_cost_usd REAL NOT NULL DEFAULT 0.0,
                error_log TEXT,
                retry_count INTEGER NOT NULL DEFAULT 0,
                replan_count INTEGER NOT NULL DEFAULT 0,
                metadata TEXT DEFAULT '{}'
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
                id, title, description, source, source_ref, state, priority, complexity,
                branch_name, plan, subtasks, current_subtask,
                architect_model, engineer_model, researcher_model, validator_model,
                created_at, updated_at, started_at, completed_at, approved_at, approved_by,
                token_budget, tokens_used, total_tokens, total_cost_usd,
                error_log, retry_count, replan_count, metadata
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                session.id,
                session.title,
                session.description,
                session.source.value,
                session.source_ref,
                session.state.value,
                session.priority.value,
                session.complexity.value if session.complexity else None,
                session.branch_name,
                json.dumps(session.plan) if session.plan is not None else None,
                json.dumps(session.subtasks) if session.subtasks is not None else None,
                session.current_subtask,
                session.architect_model,
                session.engineer_model,
                session.researcher_model,
                session.validator_model,
                session.created_at,
                session.updated_at,
                session.started_at,
                session.completed_at,
                session.approved_at,
                session.approved_by,
                session.token_budget,
                session.tokens_used,
                session.total_tokens,
                session.total_cost_usd,
                session.error_log,
                session.retry_count,
                session.replan_count,
                json.dumps(session.metadata),
            ),
        )
        await self.connection.commit()

    async def update_session(self, session: DevSession) -> None:
        """UPDATE an existing dev session."""
        await self.connection.execute(
            """
            UPDATE dev_sessions SET
                title = ?, description = ?, source = ?, source_ref = ?,
                state = ?, priority = ?, complexity = ?,
                branch_name = ?, plan = ?, subtasks = ?, current_subtask = ?,
                architect_model = ?, engineer_model = ?, researcher_model = ?, validator_model = ?,
                updated_at = ?, started_at = ?, completed_at = ?, approved_at = ?, approved_by = ?,
                token_budget = ?, tokens_used = ?, total_tokens = ?, total_cost_usd = ?,
                error_log = ?, retry_count = ?, replan_count = ?, metadata = ?
            WHERE id = ?
            """,
            (
                session.title,
                session.description,
                session.source.value,
                session.source_ref,
                session.state.value,
                session.priority.value,
                session.complexity.value if session.complexity else None,
                session.branch_name,
                json.dumps(session.plan) if session.plan is not None else None,
                json.dumps(session.subtasks) if session.subtasks is not None else None,
                session.current_subtask,
                session.architect_model,
                session.engineer_model,
                session.researcher_model,
                session.validator_model,
                session.updated_at,
                session.started_at,
                session.completed_at,
                session.approved_at,
                session.approved_by,
                session.token_budget,
                session.tokens_used,
                session.total_tokens,
                session.total_cost_usd,
                session.error_log,
                session.retry_count,
                session.replan_count,
                json.dumps(session.metadata),
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
                event.timestamp,
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
        return DevSession(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            source=DevSessionSource(row["source"]),
            source_ref=row["source_ref"],
            state=DevSessionState(row["state"]),
            priority=DevPriority(row["priority"]),
            complexity=DevComplexity(row["complexity"]) if row["complexity"] else None,
            branch_name=row["branch_name"],
            plan=json.loads(row["plan"]) if row["plan"] else None,
            subtasks=json.loads(row["subtasks"]) if row["subtasks"] else None,
            current_subtask=row["current_subtask"],
            architect_model=row["architect_model"],
            engineer_model=row["engineer_model"],
            researcher_model=row["researcher_model"],
            validator_model=row["validator_model"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            approved_at=row["approved_at"],
            approved_by=row["approved_by"],
            token_budget=row["token_budget"],
            tokens_used=row["tokens_used"],
            total_tokens=row["total_tokens"],
            total_cost_usd=row["total_cost_usd"],
            error_log=row["error_log"],
            retry_count=row["retry_count"],
            replan_count=row["replan_count"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def _row_to_event(self, row: object) -> DevEvent:
        """Convert a sqlite Row to a DevEvent dataclass."""
        return DevEvent(
            id=row["id"],
            session_id=row["session_id"],
            event_type=DevEventType(row["event_type"]),
            agent_tier=AgentTier(row["agent_tier"]) if row["agent_tier"] else None,
            timestamp=row["timestamp"],
            data=json.loads(row["data"]) if row["data"] else {},
        )


async def get_dev_database() -> DevDatabase:
    """Singleton factory — returns the shared DevDatabase instance."""
    global _instance
    if _instance is None:
        _instance = DevDatabase()
        await _instance.connect()
    return _instance
