"""
Outcome database -- SQLite storage for chat response outcomes.

Stores outcome records for every chat response, including explicit
user feedback (thumbs-up/down/correction) and implicit behavioral
signals (quick follow-up, long gap, accepted).

90-day retention cleanup keeps the database from growing indefinitely.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from hestia.database import BaseDatabase

from .models import OutcomeRecord

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "outcomes.db"

_instance: Optional["OutcomeDatabase"] = None


class OutcomeDatabase(BaseDatabase):
    """SQLite storage for outcome tracking records."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("outcomes", db_path or _DB_PATH)

    async def initialize(self) -> None:
        """Alias for connect() -- backward compat."""
        await self.connect()

    async def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS outcomes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                device_id TEXT,
                session_id TEXT,
                message_id TEXT,
                response_content TEXT,
                response_type TEXT,
                duration_ms INTEGER,
                feedback TEXT,
                feedback_note TEXT,
                implicit_signal TEXT,
                elapsed_to_next_ms INTEGER,
                timestamp TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_outcomes_user_ts
                ON outcomes(user_id, timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_outcomes_session
                ON outcomes(session_id, timestamp DESC);
        """)
        # Migration: add agent routing columns (ADR-042)
        for col in ("agent_route TEXT", "route_confidence REAL"):
            try:
                await self._connection.execute(
                    f"ALTER TABLE outcomes ADD COLUMN {col}"
                )
            except Exception:
                pass  # Column already exists
        await self._connection.commit()

    # -- Store / Query --------------------------------------------------------

    async def store_outcome(self, record: OutcomeRecord) -> str:
        """
        Insert a new outcome record.

        Returns the record ID.
        """
        assert self._connection is not None

        metadata_json = json.dumps(record.metadata) if record.metadata else "{}"

        await self._connection.execute(
            """INSERT INTO outcomes
               (id, user_id, device_id, session_id, message_id,
                response_content, response_type, duration_ms,
                feedback, feedback_note, implicit_signal,
                elapsed_to_next_ms, timestamp, metadata,
                agent_route, route_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.id,
                record.user_id,
                record.device_id,
                record.session_id,
                record.message_id,
                record.response_content,
                record.response_type,
                record.duration_ms,
                record.feedback,
                record.feedback_note,
                record.implicit_signal,
                record.elapsed_to_next_ms,
                record.timestamp.isoformat(),
                metadata_json,
                record.agent_route,
                record.route_confidence,
            ),
        )
        await self._connection.commit()
        return record.id

    async def get_outcomes(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        days: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get outcome records with optional filters.

        Returns newest first. Scoped by user_id.
        """
        assert self._connection is not None

        query = "SELECT * FROM outcomes WHERE user_id = ?"
        params: List[Any] = [user_id]

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        if days is not None:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query += " AND timestamp >= ?"
            params.append(cutoff)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        results = []
        async with self._connection.execute(query, params) as cursor:
            async for row in cursor:
                results.append(self._row_to_dict(row))

        return results

    async def get_outcome(
        self, outcome_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get a single outcome record by ID, scoped by user_id."""
        assert self._connection is not None

        async with self._connection.execute(
            "SELECT * FROM outcomes WHERE id = ? AND user_id = ?",
            (outcome_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    async def update_feedback(
        self,
        outcome_id: str,
        user_id: str,
        feedback: str,
        note: Optional[str] = None,
    ) -> bool:
        """
        Update explicit feedback on an outcome.

        Returns True if the record was found and updated.
        """
        assert self._connection is not None

        cursor = await self._connection.execute(
            """UPDATE outcomes SET feedback = ?, feedback_note = ?
               WHERE id = ? AND user_id = ?""",
            (feedback, note, outcome_id, user_id),
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def update_implicit_signal(
        self,
        outcome_id: str,
        signal: str,
        elapsed_ms: int,
    ) -> bool:
        """
        Update implicit signal fields on an outcome.

        Returns True if the record was found and updated.
        """
        assert self._connection is not None

        cursor = await self._connection.execute(
            """UPDATE outcomes SET implicit_signal = ?, elapsed_to_next_ms = ?
               WHERE id = ?""",
            (signal, elapsed_ms, outcome_id),
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def get_stats(
        self, user_id: str, days: int = 7
    ) -> Dict[str, Any]:
        """
        Get aggregated outcome statistics for a user.

        Returns: {total, positive_count, negative_count, correction_count, avg_duration_ms}
        """
        assert self._connection is not None

        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        async with self._connection.execute(
            """SELECT
                   COUNT(*) as total,
                   SUM(CASE WHEN feedback = 'positive' THEN 1 ELSE 0 END) as positive_count,
                   SUM(CASE WHEN feedback = 'negative' THEN 1 ELSE 0 END) as negative_count,
                   SUM(CASE WHEN feedback = 'correction' THEN 1 ELSE 0 END) as correction_count,
                   AVG(duration_ms) as avg_duration_ms
               FROM outcomes
               WHERE user_id = ? AND timestamp >= ?""",
            (user_id, cutoff),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None or row["total"] == 0:
            return {
                "total": 0,
                "positive_count": 0,
                "negative_count": 0,
                "correction_count": 0,
                "avg_duration_ms": 0,
            }

        return {
            "total": row["total"],
            "positive_count": row["positive_count"] or 0,
            "negative_count": row["negative_count"] or 0,
            "correction_count": row["correction_count"] or 0,
            "avg_duration_ms": round(row["avg_duration_ms"] or 0),
        }

    async def get_latest_for_session(
        self, session_id: str, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent outcome in a session.

        Used for implicit signal detection — finds the last response
        that hasn't been signaled yet.
        """
        assert self._connection is not None

        async with self._connection.execute(
            """SELECT * FROM outcomes
               WHERE session_id = ? AND user_id = ?
                 AND implicit_signal IS NULL
               ORDER BY timestamp DESC LIMIT 1""",
            (session_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    async def cleanup_old(self, retention_days: int = 90) -> int:
        """
        Remove outcomes older than retention period.

        Returns number of records deleted.
        """
        assert self._connection is not None

        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

        cursor = await self._connection.execute(
            "DELETE FROM outcomes WHERE timestamp < ?",
            (cutoff,),
        )
        await self._connection.commit()
        return cursor.rowcount

    # -- Internal -------------------------------------------------------------

    def _row_to_dict(self, row: aiosqlite.Row) -> Dict[str, Any]:
        """Convert a database row to dict."""
        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass

        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "device_id": row["device_id"],
            "session_id": row["session_id"],
            "message_id": row["message_id"],
            "response_content": row["response_content"],
            "response_type": row["response_type"],
            "duration_ms": row["duration_ms"],
            "feedback": row["feedback"],
            "feedback_note": row["feedback_note"],
            "implicit_signal": row["implicit_signal"],
            "elapsed_to_next_ms": row["elapsed_to_next_ms"],
            "timestamp": row["timestamp"],
            "metadata": metadata,
            "agent_route": row["agent_route"] if "agent_route" in row.keys() else None,
            "route_confidence": row["route_confidence"] if "route_confidence" in row.keys() else None,
        }


async def get_outcome_database(db_path: Optional[Path] = None) -> "OutcomeDatabase":
    """Singleton factory for OutcomeDatabase."""
    global _instance
    if _instance is None:
        _instance = OutcomeDatabase(db_path)
        await _instance.initialize()
    return _instance


async def close_outcome_database() -> None:
    """Close the singleton outcome database."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
