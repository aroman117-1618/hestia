"""
Apple cache database -- FTS5-backed SQLite storage for entity metadata.

Two tables:
- apple_cache: standard table with entity metadata
- apple_cache_fts: FTS5 virtual table for fast title search

Sync timestamp tracking per source for TTL-based refresh.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from hestia.database import BaseDatabase

from .models import CachedEntity, EntitySource

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "apple_cache.db"

_instance: Optional["AppleCacheDatabase"] = None


class AppleCacheDatabase(BaseDatabase):
    """SQLite + FTS5 storage for Apple ecosystem entity metadata."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("apple_cache", db_path or _DB_PATH)

    async def initialize(self) -> None:
        """Alias for connect() -- backward compat with manager pattern."""
        await self.connect()

    async def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS apple_cache (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                native_id TEXT NOT NULL,
                title TEXT NOT NULL,
                container TEXT,
                modified_at TEXT,
                created_at TEXT,
                metadata TEXT DEFAULT '{}',
                cached_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_ac_source
                ON apple_cache(source);
            CREATE INDEX IF NOT EXISTS idx_ac_container
                ON apple_cache(source, container);
            CREATE INDEX IF NOT EXISTS idx_ac_modified
                ON apple_cache(modified_at DESC);

            CREATE TABLE IF NOT EXISTS apple_cache_sync (
                source TEXT PRIMARY KEY,
                last_sync TEXT NOT NULL,
                item_count INTEGER DEFAULT 0
            );
        """)

        # FTS5 virtual table -- separate CREATE because executescript
        # doesn't handle IF NOT EXISTS well for virtual tables in all versions
        try:
            await self._connection.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS apple_cache_fts
                USING fts5(
                    title,
                    container,
                    content='apple_cache',
                    content_rowid='rowid'
                )
            """)
        except Exception:
            # Table already exists
            pass

        await self._connection.commit()

    # -- Upsert / Bulk Sync ------------------------------------------------

    async def upsert_entities(
        self, entities: List[CachedEntity], source: EntitySource
    ) -> int:
        """
        Replace all entities for a source (full sync).

        Deletes existing entries for the source, inserts new ones,
        and rebuilds the FTS5 index for that source.

        Returns the number of entities inserted.
        """
        if not entities and source:
            # Empty sync -- clear this source
            await self._delete_source(source)
            await self._update_sync_timestamp(source, 0)
            return 0

        assert self._connection is not None
        now = datetime.now(timezone.utc).isoformat()

        # Delete old entries for this source
        await self._delete_source(source)

        # Insert new entries
        for entity in entities:
            await self._connection.execute(
                """INSERT INTO apple_cache
                   (id, source, native_id, title, container,
                    modified_at, created_at, metadata, cached_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    entity.id,
                    entity.source.value,
                    entity.native_id,
                    entity.title,
                    entity.container,
                    entity.modified_at.isoformat() if entity.modified_at else None,
                    entity.created_at.isoformat() if entity.created_at else None,
                    json.dumps(entity.metadata),
                    now,
                ),
            )

        # Rebuild FTS index
        await self._rebuild_fts()

        await self._connection.commit()
        await self._update_sync_timestamp(source, len(entities))

        return len(entities)

    async def upsert_single(self, entity: CachedEntity) -> None:
        """Write-through: upsert a single entity (e.g., after create/update)."""
        assert self._connection is not None
        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """INSERT OR REPLACE INTO apple_cache
               (id, source, native_id, title, container,
                modified_at, created_at, metadata, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity.id,
                entity.source.value,
                entity.native_id,
                entity.title,
                entity.container,
                entity.modified_at.isoformat() if entity.modified_at else None,
                entity.created_at.isoformat() if entity.created_at else None,
                json.dumps(entity.metadata),
                now,
            ),
        )

        # Update FTS
        await self._rebuild_fts()
        await self._connection.commit()

    async def delete_entity(self, entity_id: str) -> bool:
        """Remove a single entity (e.g., after delete operation)."""
        assert self._connection is not None

        cursor = await self._connection.execute(
            "DELETE FROM apple_cache WHERE id = ?", (entity_id,)
        )
        deleted = cursor.rowcount > 0

        if deleted:
            await self._rebuild_fts()
            await self._connection.commit()

        return deleted

    # -- Query -------------------------------------------------------------

    async def search_fts(
        self,
        query: str,
        source: Optional[EntitySource] = None,
        limit: int = 20,
    ) -> List[CachedEntity]:
        """
        Search entities using FTS5 full-text search.

        Returns candidates ranked by FTS5 relevance score.
        """
        assert self._connection is not None

        # Sanitize query for FTS5 -- escape special chars, add prefix matching
        fts_query = self._sanitize_fts_query(query)
        if not fts_query:
            return []

        if source:
            sql = """
                SELECT c.* FROM apple_cache c
                JOIN apple_cache_fts f ON c.rowid = f.rowid
                WHERE apple_cache_fts MATCH ?
                  AND c.source = ?
                ORDER BY rank
                LIMIT ?
            """
            params: list = [fts_query, source.value, limit]
        else:
            sql = """
                SELECT c.* FROM apple_cache c
                JOIN apple_cache_fts f ON c.rowid = f.rowid
                WHERE apple_cache_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """
            params = [fts_query, limit]

        entities = []
        async with self._connection.execute(sql, params) as cursor:
            async for row in cursor:
                entities.append(self._row_to_entity(row))

        return entities

    async def get_all(
        self,
        source: Optional[EntitySource] = None,
        container: Optional[str] = None,
        limit: int = 500,
    ) -> List[CachedEntity]:
        """Get all cached entities, optionally filtered by source/container."""
        assert self._connection is not None

        sql = "SELECT * FROM apple_cache WHERE 1=1"
        params: List[Any] = []

        if source:
            sql += " AND source = ?"
            params.append(source.value)
        if container:
            sql += " AND container = ?"
            params.append(container)

        sql += " ORDER BY modified_at DESC LIMIT ?"
        params.append(limit)

        entities = []
        async with self._connection.execute(sql, params) as cursor:
            async for row in cursor:
                entities.append(self._row_to_entity(row))

        return entities

    async def get_by_id(self, entity_id: str) -> Optional[CachedEntity]:
        """Get a single entity by its composite ID."""
        assert self._connection is not None

        async with self._connection.execute(
            "SELECT * FROM apple_cache WHERE id = ?", (entity_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_entity(row)

    async def get_containers(
        self, source: EntitySource
    ) -> List[str]:
        """Get distinct container names for a source (folders, calendars, lists)."""
        assert self._connection is not None

        containers = []
        async with self._connection.execute(
            """SELECT DISTINCT container FROM apple_cache
               WHERE source = ? AND container IS NOT NULL
               ORDER BY container""",
            (source.value,),
        ) as cursor:
            async for row in cursor:
                containers.append(row["container"])

        return containers

    async def get_entity_count(
        self, source: Optional[EntitySource] = None
    ) -> int:
        """Get count of cached entities."""
        assert self._connection is not None

        if source:
            sql = "SELECT COUNT(*) FROM apple_cache WHERE source = ?"
            params: list = [source.value]
        else:
            sql = "SELECT COUNT(*) FROM apple_cache"
            params = []

        async with self._connection.execute(sql, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # -- Sync Tracking -----------------------------------------------------

    async def get_last_sync(self, source: EntitySource) -> Optional[datetime]:
        """Get the last sync timestamp for a source."""
        assert self._connection is not None

        async with self._connection.execute(
            "SELECT last_sync FROM apple_cache_sync WHERE source = ?",
            (source.value,),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None or row["last_sync"] is None:
                return None
            try:
                return datetime.fromisoformat(row["last_sync"])
            except (ValueError, TypeError):
                return None

    async def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status for all sources."""
        assert self._connection is not None

        status: Dict[str, Any] = {}
        async with self._connection.execute(
            "SELECT * FROM apple_cache_sync"
        ) as cursor:
            async for row in cursor:
                status[row["source"]] = {
                    "last_sync": row["last_sync"],
                    "item_count": row["item_count"],
                }

        return status

    # -- Internal ----------------------------------------------------------

    async def _delete_source(self, source: EntitySource) -> None:
        """Delete all entries for a source."""
        await self._connection.execute(
            "DELETE FROM apple_cache WHERE source = ?",
            (source.value,),
        )

    async def _rebuild_fts(self) -> None:
        """Rebuild the FTS5 index from the content table."""
        await self._connection.execute(
            "INSERT INTO apple_cache_fts(apple_cache_fts) VALUES('rebuild')"
        )

    async def _update_sync_timestamp(
        self, source: EntitySource, count: int
    ) -> None:
        """Update the sync tracking table."""
        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            """INSERT INTO apple_cache_sync (source, last_sync, item_count)
               VALUES (?, ?, ?)
               ON CONFLICT(source) DO UPDATE SET
                   last_sync = ?,
                   item_count = ?""",
            (source.value, now, count, now, count),
        )
        await self._connection.commit()

    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """
        Sanitize a user query for FTS5 syntax.

        Wraps each token in quotes for literal matching and adds * for prefix.
        """
        # Remove FTS5 special characters
        cleaned = query.replace('"', "").replace("'", "")
        tokens = cleaned.split()
        if not tokens:
            return ""

        # Each token as a quoted prefix search
        parts = []
        for token in tokens:
            token = token.strip()
            if token:
                parts.append(f'"{token}"*')

        return " ".join(parts)

    @staticmethod
    def _row_to_entity(row: aiosqlite.Row) -> CachedEntity:
        """Convert a database row to CachedEntity."""
        modified_at = None
        if row["modified_at"]:
            try:
                modified_at = datetime.fromisoformat(row["modified_at"])
            except (ValueError, TypeError):
                pass

        created_at = None
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                pass

        metadata = {}
        if row["metadata"]:
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                pass

        return CachedEntity(
            id=row["id"],
            source=EntitySource(row["source"]),
            native_id=row["native_id"],
            title=row["title"],
            container=row["container"],
            modified_at=modified_at,
            created_at=created_at,
            metadata=metadata,
        )


async def get_apple_cache_database(
    db_path: Optional[Path] = None,
) -> "AppleCacheDatabase":
    """Singleton factory for AppleCacheDatabase."""
    global _instance
    if _instance is None:
        _instance = AppleCacheDatabase(db_path)
        await _instance.initialize()
    return _instance


async def close_apple_cache_database() -> None:
    """Close the singleton apple cache database."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
