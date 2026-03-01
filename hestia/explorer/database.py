"""
Explorer database — SQLite storage for drafts and resource cache.

Drafts are user-created Hestia resources. The cache stores aggregated
resources from external sources with TTL-based expiry.
"""

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiosqlite

from .models import (
    ExplorerResource,
    ResourceFlag,
    ResourceSource,
    ResourceType,
)

# TTL per source (seconds)
SOURCE_TTL: Dict[str, int] = {
    ResourceSource.MAIL.value: 300,
    ResourceSource.NOTES.value: 300,
    ResourceSource.REMINDERS.value: 30,
    ResourceSource.FILES.value: 60,
}

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "explorer.db"

_instance: Optional["ExplorerDatabase"] = None


class ExplorerDatabase:
    """SQLite storage for Explorer drafts and resource cache."""

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or _DB_PATH
        self._connection: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Create tables if they don't exist."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(str(self._db_path))
        self._connection.row_factory = aiosqlite.Row

        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                body TEXT,
                color TEXT,
                flags TEXT DEFAULT '[]',
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                modified_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS resource_cache (
                source TEXT NOT NULL,
                data_json TEXT NOT NULL,
                cached_at REAL NOT NULL,
                ttl_seconds INTEGER NOT NULL,
                PRIMARY KEY (source)
            );
        """)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    # ── Drafts ──────────────────────────────────────────────

    async def create_draft(
        self,
        title: str,
        body: Optional[str] = None,
        color: Optional[str] = None,
        flags: Optional[List[ResourceFlag]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> ExplorerResource:
        """Create a new Hestia draft."""
        draft_id = f"drafts:{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        flag_values = [f.value for f in (flags or [])]
        meta = metadata or {}

        assert self._connection is not None
        await self._connection.execute(
            """INSERT INTO drafts (id, title, body, color, flags, metadata, created_at, modified_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                draft_id,
                title,
                body,
                color,
                json.dumps(flag_values),
                json.dumps(meta),
                now.isoformat(),
                now.isoformat(),
            ),
        )
        await self._connection.commit()

        return ExplorerResource(
            id=draft_id,
            type=ResourceType.DRAFT,
            title=title,
            source=ResourceSource.HESTIA,
            created_at=now,
            modified_at=now,
            preview=body[:200] if body else None,
            flags=flags or [],
            color=color,
            metadata=meta,
        )

    async def update_draft(
        self,
        draft_id: str,
        title: Optional[str] = None,
        body: Optional[str] = None,
        color: Optional[str] = None,
        flags: Optional[List[ResourceFlag]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Optional[ExplorerResource]:
        """Update an existing draft. Returns None if not found."""
        assert self._connection is not None
        cursor = await self._connection.execute(
            "SELECT * FROM drafts WHERE id = ?", (draft_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        now = datetime.utcnow()
        new_title = title if title is not None else row["title"]
        new_body = body if body is not None else row["body"]
        new_color = color if color is not None else row["color"]
        new_flags = (
            json.dumps([f.value for f in flags])
            if flags is not None
            else row["flags"]
        )
        new_meta = (
            json.dumps(metadata) if metadata is not None else row["metadata"]
        )

        await self._connection.execute(
            """UPDATE drafts SET title=?, body=?, color=?, flags=?, metadata=?, modified_at=?
               WHERE id=?""",
            (new_title, new_body, new_color, new_flags, new_meta, now.isoformat(), draft_id),
        )
        await self._connection.commit()

        return ExplorerResource(
            id=draft_id,
            type=ResourceType.DRAFT,
            title=new_title,
            source=ResourceSource.HESTIA,
            created_at=datetime.fromisoformat(row["created_at"]),
            modified_at=now,
            preview=new_body[:200] if new_body else None,
            flags=[ResourceFlag(f) for f in json.loads(new_flags)],
            color=new_color,
            metadata=json.loads(new_meta),
        )

    async def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft. Returns True if deleted."""
        assert self._connection is not None
        cursor = await self._connection.execute(
            "DELETE FROM drafts WHERE id = ?", (draft_id,)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    async def get_draft(self, draft_id: str) -> Optional[ExplorerResource]:
        """Get a single draft by ID."""
        assert self._connection is not None
        cursor = await self._connection.execute(
            "SELECT * FROM drafts WHERE id = ?", (draft_id,)
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_resource(row)

    async def list_drafts(self) -> List[ExplorerResource]:
        """List all drafts ordered by modification time."""
        assert self._connection is not None
        cursor = await self._connection.execute(
            "SELECT * FROM drafts ORDER BY modified_at DESC"
        )
        rows = await cursor.fetchall()
        return [self._row_to_resource(r) for r in rows]

    def _row_to_resource(self, row: aiosqlite.Row) -> ExplorerResource:
        """Convert a drafts table row to ExplorerResource."""
        created_at = None
        modified_at = None
        try:
            created_at = datetime.fromisoformat(row["created_at"])
        except (ValueError, TypeError):
            pass
        try:
            modified_at = datetime.fromisoformat(row["modified_at"])
        except (ValueError, TypeError):
            pass

        body = row["body"]
        return ExplorerResource(
            id=row["id"],
            type=ResourceType.DRAFT,
            title=row["title"],
            source=ResourceSource.HESTIA,
            created_at=created_at,
            modified_at=modified_at,
            preview=body[:200] if body else None,
            flags=[ResourceFlag(f) for f in json.loads(row["flags"] or "[]")],
            color=row["color"],
            metadata=json.loads(row["metadata"] or "{}"),
        )

    # ── Resource Cache ──────────────────────────────────────

    async def get_cached_resources(
        self, source: ResourceSource
    ) -> Optional[List[ExplorerResource]]:
        """
        Get cached resources for a source. Returns None if expired or missing.
        """
        assert self._connection is not None
        cursor = await self._connection.execute(
            "SELECT * FROM resource_cache WHERE source = ?", (source.value,)
        )
        row = await cursor.fetchone()
        if not row:
            return None

        elapsed = time.time() - row["cached_at"]
        if elapsed > row["ttl_seconds"]:
            return None

        data_list = json.loads(row["data_json"])
        return [ExplorerResource.from_dict(d) for d in data_list]

    async def set_cached_resources(
        self, source: ResourceSource, resources: List[ExplorerResource]
    ) -> None:
        """Cache resources for a source with appropriate TTL."""
        assert self._connection is not None
        ttl = SOURCE_TTL.get(source.value, 60)
        data_json = json.dumps([r.to_dict() for r in resources])

        await self._connection.execute(
            """INSERT OR REPLACE INTO resource_cache (source, data_json, cached_at, ttl_seconds)
               VALUES (?, ?, ?, ?)""",
            (source.value, data_json, time.time(), ttl),
        )
        await self._connection.commit()

    async def clear_cache(self, source: Optional[ResourceSource] = None) -> None:
        """Clear cache for a specific source or all sources."""
        assert self._connection is not None
        if source:
            await self._connection.execute(
                "DELETE FROM resource_cache WHERE source = ?", (source.value,)
            )
        else:
            await self._connection.execute("DELETE FROM resource_cache")
        await self._connection.commit()


async def get_explorer_database(db_path: Optional[Path] = None) -> ExplorerDatabase:
    """Singleton factory for ExplorerDatabase."""
    global _instance
    if _instance is None:
        _instance = ExplorerDatabase(db_path)
        await _instance.initialize()
    return _instance
