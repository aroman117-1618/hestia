"""
Newsfeed database — SQLite storage for materialized timeline items.

Two tables:
- newsfeed_items: cached items from source managers
- newsfeed_state: per-user read/dismiss state (multi-device ready)

30-day retention cleanup keeps the database from growing indefinitely.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from .models import (
    NewsfeedItem,
    NewsfeedItemPriority,
    NewsfeedItemSource,
    NewsfeedItemType,
)

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "newsfeed.db"

_instance: Optional["NewsfeedDatabase"] = None


class NewsfeedDatabase:
    """SQLite storage for newsfeed items and read/dismiss state."""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or _DB_PATH
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self._db_path))
        self._connection.row_factory = aiosqlite.Row

        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS newsfeed_items (
                id TEXT PRIMARY KEY,
                item_type TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                timestamp TEXT,
                priority TEXT NOT NULL DEFAULT 'normal',
                icon TEXT,
                color TEXT,
                action_type TEXT,
                action_id TEXT,
                metadata TEXT DEFAULT '{}',
                cached_at REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_newsfeed_timestamp
                ON newsfeed_items(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_newsfeed_item_type
                ON newsfeed_items(item_type);

            CREATE TABLE IF NOT EXISTS newsfeed_state (
                item_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                read_at TEXT,
                dismissed_at TEXT,
                acted_on_device_id TEXT,
                PRIMARY KEY (item_id, user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_newsfeed_state_user
                ON newsfeed_state(user_id);
        """)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    # ── Upsert / Query ──────────────────────────────────────

    async def upsert_items(self, items: List[NewsfeedItem]) -> int:
        """
        Insert or replace items in the cache.

        Returns the number of items upserted.
        """
        if not items:
            return 0

        assert self._connection is not None
        now = time.time()

        for item in items:
            await self._connection.execute(
                """INSERT OR REPLACE INTO newsfeed_items
                   (id, item_type, source, title, body, timestamp,
                    priority, icon, color, action_type, action_id,
                    metadata, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.id,
                    item.item_type.value,
                    item.source.value,
                    item.title,
                    item.body,
                    item.timestamp.isoformat() if item.timestamp else None,
                    item.priority.value,
                    item.icon,
                    item.color,
                    item.action_type,
                    item.action_id,
                    json.dumps(item.metadata),
                    now,
                ),
            )

        await self._connection.commit()
        return len(items)

    async def get_items(
        self,
        user_id: str,
        item_type: Optional[NewsfeedItemType] = None,
        source: Optional[NewsfeedItemSource] = None,
        include_dismissed: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[NewsfeedItem]:
        """
        Get timeline items with user-specific read/dismiss state.

        Uses LEFT JOIN on newsfeed_state for per-user state overlay.
        """
        assert self._connection is not None

        query = """
            SELECT i.*, s.read_at, s.dismissed_at
            FROM newsfeed_items i
            LEFT JOIN newsfeed_state s
                ON i.id = s.item_id AND s.user_id = ?
            WHERE 1=1
        """
        params: List[Any] = [user_id]

        if item_type:
            query += " AND i.item_type = ?"
            params.append(item_type.value)

        if source:
            query += " AND i.source = ?"
            params.append(source.value)

        if not include_dismissed:
            query += " AND (s.dismissed_at IS NULL)"

        query += " ORDER BY i.timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        items = []
        async with self._connection.execute(query, params) as cursor:
            async for row in cursor:
                item = self._row_to_item(row)
                items.append(item)

        return items

    async def mark_read(
        self, item_id: str, user_id: str, device_id: Optional[str] = None
    ) -> bool:
        """Mark an item as read for a user."""
        assert self._connection is not None
        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """INSERT INTO newsfeed_state (item_id, user_id, read_at, acted_on_device_id)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(item_id, user_id) DO UPDATE SET
                   read_at = COALESCE(newsfeed_state.read_at, ?),
                   acted_on_device_id = ?""",
            (item_id, user_id, now, device_id, now, device_id),
        )
        await self._connection.commit()
        return True

    async def mark_dismissed(
        self, item_id: str, user_id: str, device_id: Optional[str] = None
    ) -> bool:
        """Mark an item as dismissed for a user."""
        assert self._connection is not None
        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """INSERT INTO newsfeed_state (item_id, user_id, dismissed_at, acted_on_device_id)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(item_id, user_id) DO UPDATE SET
                   dismissed_at = ?,
                   acted_on_device_id = ?""",
            (item_id, user_id, now, device_id, now, device_id),
        )
        await self._connection.commit()
        return True

    async def get_unread_count(
        self,
        user_id: str,
        item_type: Optional[NewsfeedItemType] = None,
    ) -> int:
        """Get count of unread, non-dismissed items for a user."""
        assert self._connection is not None

        query = """
            SELECT COUNT(*) FROM newsfeed_items i
            LEFT JOIN newsfeed_state s
                ON i.id = s.item_id AND s.user_id = ?
            WHERE s.read_at IS NULL AND s.dismissed_at IS NULL
        """
        params: List[Any] = [user_id]

        if item_type:
            query += " AND i.item_type = ?"
            params.append(item_type.value)

        async with self._connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def cleanup_old_items(self, days: int = 30) -> int:
        """
        Remove items older than `days` days. [T4]

        Also cleans up orphaned state rows.
        Returns number of items deleted.
        """
        assert self._connection is not None
        cutoff = time.time() - (days * 86400)

        cursor = await self._connection.execute(
            "DELETE FROM newsfeed_items WHERE cached_at < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount

        # Clean orphaned state rows
        await self._connection.execute(
            """DELETE FROM newsfeed_state
               WHERE item_id NOT IN (SELECT id FROM newsfeed_items)"""
        )

        await self._connection.commit()
        return deleted

    # ── Internal ────────────────────────────────────────────

    def _row_to_item(self, row: aiosqlite.Row) -> NewsfeedItem:
        """Convert a database row to NewsfeedItem."""
        timestamp = None
        if row["timestamp"]:
            try:
                timestamp = datetime.fromisoformat(row["timestamp"])
            except (ValueError, TypeError):
                pass

        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass

        return NewsfeedItem(
            id=row["id"],
            item_type=NewsfeedItemType(row["item_type"]),
            source=NewsfeedItemSource(row["source"]),
            title=row["title"],
            body=row["body"],
            timestamp=timestamp,
            priority=NewsfeedItemPriority(row["priority"]),
            icon=row["icon"],
            color=row["color"],
            action_type=row["action_type"],
            action_id=row["action_id"],
            metadata=metadata,
            is_read=row["read_at"] is not None,
            is_dismissed=row["dismissed_at"] is not None,
        )


async def get_newsfeed_database(db_path: Optional[Path] = None) -> NewsfeedDatabase:
    """Singleton factory for NewsfeedDatabase."""
    global _instance
    if _instance is None:
        _instance = NewsfeedDatabase(db_path)
        await _instance.initialize()
    return _instance
