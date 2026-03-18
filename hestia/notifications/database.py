"""
Notification relay database.

Stores bump requests, delivery tracking, and per-user notification settings.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from hestia.database import BaseDatabase
from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent
from hestia.notifications.models import (
    BumpRequest,
    BumpStatus,
    NotificationRoute,
    NotificationSettings,
)

logger = get_logger()


def _utc_iso(dt: datetime) -> str:
    """Format datetime as bare UTC string for SQLite datetime() compatibility.

    SQLite's datetime() function returns 'YYYY-MM-DD HH:MM:SS' (space separator).
    We use the same format so comparisons work correctly.
    """
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class NotificationDatabase(BaseDatabase):
    """SQLite storage for notification relay state."""

    def __init__(self) -> None:
        super().__init__("notifications")

    async def _init_schema(self) -> None:
        """Create tables for bump requests and settings."""
        await self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS bump_requests (
                id TEXT PRIMARY KEY,
                callback_id TEXT UNIQUE NOT NULL,
                session_id TEXT,
                user_id TEXT NOT NULL DEFAULT 'default',
                title TEXT NOT NULL,
                body TEXT,
                priority TEXT NOT NULL DEFAULT 'medium',
                actions TEXT NOT NULL DEFAULT '["approve","deny"]',
                context TEXT NOT NULL DEFAULT '{}',
                status TEXT NOT NULL DEFAULT 'pending',
                route TEXT,
                response_action TEXT,
                created_at TEXT NOT NULL,
                responded_at TEXT,
                expired_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_bump_callback
                ON bump_requests(callback_id);
            CREATE INDEX IF NOT EXISTS idx_bump_status
                ON bump_requests(status);
            CREATE INDEX IF NOT EXISTS idx_bump_session
                ON bump_requests(session_id);
            CREATE INDEX IF NOT EXISTS idx_bump_user_created
                ON bump_requests(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS notification_settings (
                user_id TEXT PRIMARY KEY,
                idle_threshold_seconds INTEGER NOT NULL DEFAULT 120,
                rate_limit_seconds INTEGER NOT NULL DEFAULT 300,
                batch_window_seconds INTEGER NOT NULL DEFAULT 60,
                bump_expiry_seconds INTEGER NOT NULL DEFAULT 900,
                quiet_hours_enabled INTEGER NOT NULL DEFAULT 1,
                quiet_hours_start TEXT NOT NULL DEFAULT '22:00',
                quiet_hours_end TEXT NOT NULL DEFAULT '08:00',
                focus_mode_respect INTEGER NOT NULL DEFAULT 1,
                session_cooldown_seconds INTEGER NOT NULL DEFAULT 600
            );
        """)

    # ── Bump Request CRUD ──────────────────────────────────────

    async def create_bump(self, bump: BumpRequest) -> BumpRequest:
        """Insert a new bump request."""
        await self.connection.execute(
            """INSERT INTO bump_requests
               (id, callback_id, session_id, user_id, title, body,
                priority, actions, context, status, route, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                bump.id,
                bump.callback_id,
                bump.session_id,
                bump.user_id,
                bump.title,
                bump.body,
                bump.priority,
                json.dumps(bump.actions),
                json.dumps(bump.context),
                bump.status.value,
                bump.route.value if bump.route else None,
                _utc_iso(bump.created_at),
            ),
        )
        await self.connection.commit()
        return bump

    async def get_bump_by_callback(self, callback_id: str) -> Optional[BumpRequest]:
        """Look up a bump by its callback ID."""
        cursor = await self.connection.execute(
            "SELECT * FROM bump_requests WHERE callback_id = ?",
            (callback_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_bump(row) if row else None

    async def update_bump_status(
        self,
        callback_id: str,
        status: BumpStatus,
        response_action: Optional[str] = None,
    ) -> bool:
        """Update bump status and optional response action."""
        now = _utc_iso(datetime.now(timezone.utc))
        fields = ["status = ?"]
        params: List[Any] = [status.value]

        if status in (BumpStatus.APPROVED, BumpStatus.DENIED):
            fields.append("responded_at = ?")
            params.append(now)
        if status == BumpStatus.EXPIRED:
            fields.append("expired_at = ?")
            params.append(now)
        if response_action:
            fields.append("response_action = ?")
            params.append(response_action)

        params.append(callback_id)
        cursor = await self.connection.execute(
            f"UPDATE bump_requests SET {', '.join(fields)} WHERE callback_id = ?",
            params,
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def update_bump_route(
        self, callback_id: str, route: NotificationRoute
    ) -> None:
        """Record which route was used for delivery."""
        await self.connection.execute(
            "UPDATE bump_requests SET route = ? WHERE callback_id = ?",
            (route.value, callback_id),
        )
        await self.connection.commit()

    async def list_bumps(
        self,
        user_id: str = "default",
        status: Optional[BumpStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[BumpRequest]:
        """List bump requests with optional filters."""
        query = "SELECT * FROM bump_requests WHERE user_id = ?"
        params: List[Any] = [user_id]

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self.connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_bump(row) for row in rows]

    async def count_bumps(
        self, user_id: str = "default", status: Optional[BumpStatus] = None
    ) -> int:
        """Count bump requests."""
        query = "SELECT COUNT(*) FROM bump_requests WHERE user_id = ?"
        params: List[Any] = [user_id]
        if status:
            query += " AND status = ?"
            params.append(status.value)
        cursor = await self.connection.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_recent_bump_for_session(
        self, session_id: str, seconds: int = 300
    ) -> Optional[BumpRequest]:
        """Check if a session bumped recently (rate limiting)."""
        cursor = await self.connection.execute(
            """SELECT * FROM bump_requests
               WHERE session_id = ?
                 AND status = 'pending'
                 AND created_at > datetime('now', ?)
               ORDER BY created_at DESC LIMIT 1""",
            (session_id, f"-{seconds} seconds"),
        )
        row = await cursor.fetchone()
        return self._row_to_bump(row) if row else None

    async def get_pending_bumps_in_window(
        self, user_id: str, seconds: int = 60
    ) -> List[BumpRequest]:
        """Get pending bumps within a time window (for batching)."""
        cursor = await self.connection.execute(
            """SELECT * FROM bump_requests
               WHERE user_id = ? AND status = 'pending'
                 AND created_at > datetime('now', ?)
               ORDER BY created_at ASC""",
            (user_id, f"-{seconds} seconds"),
        )
        rows = await cursor.fetchall()
        return [self._row_to_bump(row) for row in rows]

    async def expire_old_bumps(self, expiry_seconds: int = 900) -> int:
        """Expire pending bumps older than threshold. Returns count expired."""
        cursor = await self.connection.execute(
            """UPDATE bump_requests
               SET status = 'expired', expired_at = ?
               WHERE status = 'pending'
                 AND created_at < datetime('now', ?)""",
            (
                _utc_iso(datetime.now(timezone.utc)),
                f"-{expiry_seconds} seconds",
            ),
        )
        await self.connection.commit()
        return cursor.rowcount

    async def get_last_response_for_session(
        self, session_id: str
    ) -> Optional[BumpRequest]:
        """Get the most recent responded bump for a session (cooldown check)."""
        cursor = await self.connection.execute(
            """SELECT * FROM bump_requests
               WHERE session_id = ?
                 AND status IN ('approved', 'denied')
               ORDER BY responded_at DESC LIMIT 1""",
            (session_id,),
        )
        row = await cursor.fetchone()
        return self._row_to_bump(row) if row else None

    # ── Settings CRUD ──────────────────────────────────────────

    async def get_settings(self, user_id: str = "default") -> NotificationSettings:
        """Get notification settings, creating defaults if absent."""
        cursor = await self.connection.execute(
            "SELECT * FROM notification_settings WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return NotificationSettings(
                user_id=row["user_id"],
                idle_threshold_seconds=row["idle_threshold_seconds"],
                rate_limit_seconds=row["rate_limit_seconds"],
                batch_window_seconds=row["batch_window_seconds"],
                bump_expiry_seconds=row["bump_expiry_seconds"],
                quiet_hours_enabled=bool(row["quiet_hours_enabled"]),
                quiet_hours_start=row["quiet_hours_start"],
                quiet_hours_end=row["quiet_hours_end"],
                focus_mode_respect=bool(row["focus_mode_respect"]),
                session_cooldown_seconds=row["session_cooldown_seconds"],
            )
        return NotificationSettings(user_id=user_id)

    async def save_settings(self, settings: NotificationSettings) -> None:
        """Upsert notification settings."""
        await self.connection.execute(
            """INSERT INTO notification_settings
               (user_id, idle_threshold_seconds, rate_limit_seconds,
                batch_window_seconds, bump_expiry_seconds,
                quiet_hours_enabled, quiet_hours_start, quiet_hours_end,
                focus_mode_respect, session_cooldown_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                idle_threshold_seconds = excluded.idle_threshold_seconds,
                rate_limit_seconds = excluded.rate_limit_seconds,
                batch_window_seconds = excluded.batch_window_seconds,
                bump_expiry_seconds = excluded.bump_expiry_seconds,
                quiet_hours_enabled = excluded.quiet_hours_enabled,
                quiet_hours_start = excluded.quiet_hours_start,
                quiet_hours_end = excluded.quiet_hours_end,
                focus_mode_respect = excluded.focus_mode_respect,
                session_cooldown_seconds = excluded.session_cooldown_seconds""",
            (
                settings.user_id,
                settings.idle_threshold_seconds,
                settings.rate_limit_seconds,
                settings.batch_window_seconds,
                settings.bump_expiry_seconds,
                int(settings.quiet_hours_enabled),
                settings.quiet_hours_start,
                settings.quiet_hours_end,
                int(settings.focus_mode_respect),
                settings.session_cooldown_seconds,
            ),
        )
        await self.connection.commit()

    # ── Row Mapping ────────────────────────────────────────────

    def _row_to_bump(self, row: aiosqlite.Row) -> BumpRequest:
        """Convert a database row to a BumpRequest."""
        created_at = datetime.fromisoformat(row["created_at"])
        responded_at = (
            datetime.fromisoformat(row["responded_at"])
            if row["responded_at"]
            else None
        )
        expired_at = (
            datetime.fromisoformat(row["expired_at"])
            if row["expired_at"]
            else None
        )

        return BumpRequest(
            id=row["id"],
            callback_id=row["callback_id"],
            session_id=row["session_id"],
            user_id=row["user_id"],
            title=row["title"],
            body=row["body"],
            priority=row["priority"],
            actions=json.loads(row["actions"]),
            context=json.loads(row["context"]),
            status=BumpStatus(row["status"]),
            route=NotificationRoute(row["route"]) if row["route"] else None,
            created_at=created_at,
            responded_at=responded_at,
            expired_at=expired_at,
            response_action=row["response_action"],
        )
