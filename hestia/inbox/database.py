"""
Inbox database -- SQLite storage for unified inbox items.

Two tables:
- inbox_items: cached items from Apple clients (mail, reminders, calendar)
- inbox_state: per-user read/archive state (multi-device ready)

30-day retention cleanup keeps the database from growing indefinitely.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from hestia.database import BaseDatabase

from .models import (
    InboxItem,
    InboxItemPriority,
    InboxItemSource,
    InboxItemType,
)

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "inbox.db"

_instance: Optional["InboxDatabase"] = None


class InboxDatabase(BaseDatabase):
    """SQLite storage for inbox items and per-user read/archive state."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("inbox", db_path or _DB_PATH)

    async def initialize(self) -> None:
        """Alias for connect() -- backward compat."""
        await self.connect()

    async def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS inbox_items (
                id TEXT PRIMARY KEY,
                item_type TEXT NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                timestamp TEXT,
                priority TEXT DEFAULT 'normal',
                sender TEXT,
                sender_detail TEXT,
                has_attachments INTEGER DEFAULT 0,
                icon TEXT,
                color TEXT,
                metadata TEXT DEFAULT '{}',
                cached_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_inbox_timestamp
                ON inbox_items(timestamp DESC);
            CREATE INDEX IF NOT EXISTS idx_inbox_source
                ON inbox_items(source);
            CREATE INDEX IF NOT EXISTS idx_inbox_item_type
                ON inbox_items(item_type);

            CREATE TABLE IF NOT EXISTS inbox_state (
                item_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                is_read INTEGER DEFAULT 0,
                is_archived INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (item_id, user_id)
            );

            CREATE INDEX IF NOT EXISTS idx_inbox_state_user
                ON inbox_state(user_id);
        """)
        await self._connection.commit()

    # -- Upsert / Query ---------------------------------------------------

    async def upsert_items(self, items: List[InboxItem]) -> int:
        """
        Insert or replace items in the cache.

        Returns the number of items upserted.
        """
        if not items:
            return 0

        assert self._connection is not None
        now = datetime.now(timezone.utc).isoformat()

        for item in items:
            await self._connection.execute(
                """INSERT OR REPLACE INTO inbox_items
                   (id, item_type, source, title, body, timestamp,
                    priority, sender, sender_detail, has_attachments,
                    icon, color, metadata, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item.id,
                    item.item_type.value,
                    item.source.value,
                    item.title,
                    item.body,
                    item.timestamp.isoformat() if item.timestamp else None,
                    item.priority.value,
                    item.sender,
                    item.sender_detail,
                    1 if item.has_attachments else 0,
                    item.icon,
                    item.color,
                    json.dumps(item.metadata),
                    now,
                ),
            )

        await self._connection.commit()
        return len(items)

    async def get_items(
        self,
        user_id: str,
        source: Optional[InboxItemSource] = None,
        item_type: Optional[InboxItemType] = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InboxItem]:
        """
        Get inbox items with user-specific read/archive state.

        Uses LEFT JOIN on inbox_state for per-user state overlay.
        """
        assert self._connection is not None

        query = """
            SELECT i.*, s.is_read, s.is_archived
            FROM inbox_items i
            LEFT JOIN inbox_state s
                ON i.id = s.item_id AND s.user_id = ?
            WHERE 1=1
        """
        params: List[Any] = [user_id]

        if source:
            query += " AND i.source = ?"
            params.append(source.value)

        if item_type:
            query += " AND i.item_type = ?"
            params.append(item_type.value)

        if not include_archived:
            query += " AND (s.is_archived IS NULL OR s.is_archived = 0)"

        query += " ORDER BY i.timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        items = []
        async with self._connection.execute(query, params) as cursor:
            async for row in cursor:
                item = self._row_to_item(row)
                items.append(item)

        return items

    async def get_item(
        self, item_id: str, user_id: str
    ) -> Optional[InboxItem]:
        """Get a single inbox item with user state."""
        assert self._connection is not None

        query = """
            SELECT i.*, s.is_read, s.is_archived
            FROM inbox_items i
            LEFT JOIN inbox_state s
                ON i.id = s.item_id AND s.user_id = ?
            WHERE i.id = ?
        """

        async with self._connection.execute(query, [user_id, item_id]) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_item(row)

    async def mark_read(self, item_id: str, user_id: str) -> bool:
        """Mark an item as read for a user."""
        assert self._connection is not None
        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """INSERT INTO inbox_state (item_id, user_id, is_read, is_archived, updated_at)
               VALUES (?, ?, 1, 0, ?)
               ON CONFLICT(item_id, user_id) DO UPDATE SET
                   is_read = 1,
                   updated_at = ?""",
            (item_id, user_id, now, now),
        )
        await self._connection.commit()
        return True

    async def mark_all_read(
        self, user_id: str, source: Optional[InboxItemSource] = None
    ) -> int:
        """
        Mark all items as read for a user.

        Optionally filter by source. Returns number of items marked.
        """
        assert self._connection is not None
        now = datetime.now(timezone.utc).isoformat()

        # Find unread items (those with no state row or is_read=0)
        query = """
            SELECT i.id FROM inbox_items i
            LEFT JOIN inbox_state s
                ON i.id = s.item_id AND s.user_id = ?
            WHERE (s.is_read IS NULL OR s.is_read = 0)
        """
        params: List[Any] = [user_id]

        if source:
            query += " AND i.source = ?"
            params.append(source.value)

        async with self._connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()

        count = 0
        for row in rows:
            await self._connection.execute(
                """INSERT INTO inbox_state (item_id, user_id, is_read, is_archived, updated_at)
                   VALUES (?, ?, 1, 0, ?)
                   ON CONFLICT(item_id, user_id) DO UPDATE SET
                       is_read = 1,
                       updated_at = ?""",
                (row["id"], user_id, now, now),
            )
            count += 1

        await self._connection.commit()
        return count

    async def archive(self, item_id: str, user_id: str) -> bool:
        """Archive an item for a user (also marks read)."""
        assert self._connection is not None
        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """INSERT INTO inbox_state (item_id, user_id, is_read, is_archived, updated_at)
               VALUES (?, ?, 1, 1, ?)
               ON CONFLICT(item_id, user_id) DO UPDATE SET
                   is_read = 1,
                   is_archived = 1,
                   updated_at = ?""",
            (item_id, user_id, now, now),
        )
        await self._connection.commit()
        return True

    async def get_unread_count(
        self, user_id: str, source: Optional[InboxItemSource] = None
    ) -> int:
        """Get count of unread, non-archived items for a user."""
        assert self._connection is not None

        query = """
            SELECT COUNT(*) FROM inbox_items i
            LEFT JOIN inbox_state s
                ON i.id = s.item_id AND s.user_id = ?
            WHERE (s.is_read IS NULL OR s.is_read = 0)
              AND (s.is_archived IS NULL OR s.is_archived = 0)
        """
        params: List[Any] = [user_id]

        if source:
            query += " AND i.source = ?"
            params.append(source.value)

        async with self._connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_unread_by_source(self, user_id: str) -> Dict[str, int]:
        """Get unread counts broken down by source."""
        result: Dict[str, int] = {}
        for src in InboxItemSource:
            count = await self.get_unread_count(user_id, source=src)
            if count > 0:
                result[src.value] = count
        return result

    async def cleanup_old_items(self, retention_days: int = 30) -> int:
        """
        Remove items cached more than `retention_days` ago.

        Also cleans up orphaned state rows.
        Returns number of items deleted.
        """
        assert self._connection is not None
        cutoff = datetime.now(timezone.utc).isoformat()
        # Calculate cutoff date
        from datetime import timedelta
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff = cutoff_dt.isoformat()

        cursor = await self._connection.execute(
            "DELETE FROM inbox_items WHERE cached_at < ?",
            (cutoff,),
        )
        deleted = cursor.rowcount

        # Clean orphaned state rows
        await self._connection.execute(
            """DELETE FROM inbox_state
               WHERE item_id NOT IN (SELECT id FROM inbox_items)"""
        )

        await self._connection.commit()
        return deleted

    # -- Internal ----------------------------------------------------------

    def _row_to_item(self, row: aiosqlite.Row) -> InboxItem:
        """Convert a database row to InboxItem."""
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

        # State columns come from LEFT JOIN -- may be None
        is_read = bool(row["is_read"]) if row["is_read"] is not None else False
        is_archived = bool(row["is_archived"]) if row["is_archived"] is not None else False

        return InboxItem(
            id=row["id"],
            item_type=InboxItemType(row["item_type"]),
            source=InboxItemSource(row["source"]),
            title=row["title"],
            body=row["body"],
            timestamp=timestamp,
            priority=InboxItemPriority(row["priority"]),
            sender=row["sender"],
            sender_detail=row["sender_detail"],
            has_attachments=bool(row["has_attachments"]),
            icon=row["icon"],
            color=row["color"],
            metadata=metadata,
            is_read=is_read,
            is_archived=is_archived,
        )


async def get_inbox_database(db_path: Optional[Path] = None) -> "InboxDatabase":
    """Singleton factory for InboxDatabase."""
    global _instance
    if _instance is None:
        _instance = InboxDatabase(db_path)
        await _instance.initialize()
    return _instance


async def close_inbox_database() -> None:
    """Close the singleton inbox database."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
