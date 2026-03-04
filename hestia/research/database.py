"""
Research database — SQLite storage for graph cache and principles.

Graph cache stores pre-computed graph JSON with TTL-based expiry.
Principles table stores distilled interaction principles with status lifecycle.
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiosqlite

from hestia.database import BaseDatabase

from .models import Principle, PrincipleStatus

_DB_DIR = Path("data")
_DB_PATH = _DB_DIR / "research.db"

_instance: Optional["ResearchDatabase"] = None


class ResearchDatabase(BaseDatabase):
    """SQLite storage for Research graph cache and principles."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("research", db_path or _DB_PATH)

    async def initialize(self) -> None:
        """Alias for connect() — backward compat."""
        await self.connect()

    async def _init_schema(self) -> None:
        """Create tables if they don't exist."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS graph_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                created_at REAL NOT NULL,
                ttl_seconds INTEGER NOT NULL DEFAULT 300
            );

            CREATE TABLE IF NOT EXISTS principles (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                domain TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                status TEXT NOT NULL DEFAULT 'pending',
                source_chunk_ids TEXT DEFAULT '[]',
                topics TEXT DEFAULT '[]',
                entities TEXT DEFAULT '[]',
                validation_count INTEGER NOT NULL DEFAULT 0,
                contradiction_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_principles_status ON principles(status);
            CREATE INDEX IF NOT EXISTS idx_principles_domain ON principles(domain);
        """)

    # ── Graph Cache ─────────────────────────────────────────

    async def get_cached_graph(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached graph data if not expired."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT data, created_at, ttl_seconds FROM graph_cache WHERE cache_key = ?",
            (cache_key,),
        )
        row = await cursor.fetchone()
        if not row:
            return None

        data_json, created_at, ttl = row
        if time.time() - created_at > ttl:
            await self._connection.execute(
                "DELETE FROM graph_cache WHERE cache_key = ?", (cache_key,)
            )
            await self._connection.commit()
            return None

        return json.loads(data_json)

    async def set_cached_graph(
        self, cache_key: str, data: Dict[str, Any], ttl_seconds: int = 300
    ) -> None:
        """Store graph data in cache."""
        if not self._connection:
            return
        await self._connection.execute(
            """INSERT OR REPLACE INTO graph_cache (cache_key, data, created_at, ttl_seconds)
               VALUES (?, ?, ?, ?)""",
            (cache_key, json.dumps(data), time.time(), ttl_seconds),
        )
        await self._connection.commit()

    async def invalidate_cache(self, cache_key: Optional[str] = None) -> None:
        """Invalidate one or all cached graphs."""
        if not self._connection:
            return
        if cache_key:
            await self._connection.execute(
                "DELETE FROM graph_cache WHERE cache_key = ?", (cache_key,)
            )
        else:
            await self._connection.execute("DELETE FROM graph_cache")
        await self._connection.commit()

    # ── Principles CRUD ─────────────────────────────────────

    async def create_principle(self, principle: Principle) -> Principle:
        """Insert a new principle."""
        if not self._connection:
            raise RuntimeError("Database not initialized")
        await self._connection.execute(
            """INSERT INTO principles
               (id, content, domain, confidence, status, source_chunk_ids,
                topics, entities, validation_count, contradiction_count,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                principle.id,
                principle.content,
                principle.domain,
                principle.confidence,
                principle.status.value,
                json.dumps(principle.source_chunk_ids),
                json.dumps(principle.topics),
                json.dumps(principle.entities),
                principle.validation_count,
                principle.contradiction_count,
                principle.created_at.isoformat() if principle.created_at else datetime.now(timezone.utc).isoformat(),
                principle.updated_at.isoformat() if principle.updated_at else datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._connection.commit()
        return principle

    async def get_principle(self, principle_id: str) -> Optional[Principle]:
        """Get a single principle by ID."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT * FROM principles WHERE id = ?", (principle_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_principle(row) if row else None

    async def list_principles(
        self,
        status: Optional[PrincipleStatus] = None,
        domain: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Principle]:
        """List principles with optional filters."""
        if not self._connection:
            return []

        query = "SELECT * FROM principles"
        params: List[Any] = []
        conditions: List[str] = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if domain:
            conditions.append("domain = ?")
            params.append(domain)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_principle(row) for row in rows]

    async def count_principles(
        self,
        status: Optional[PrincipleStatus] = None,
    ) -> int:
        """Count principles with optional status filter."""
        if not self._connection:
            return 0

        query = "SELECT COUNT(*) FROM principles"
        params: List[Any] = []

        if status:
            query += " WHERE status = ?"
            params.append(status.value)

        cursor = await self._connection.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def update_principle_status(
        self, principle_id: str, status: PrincipleStatus
    ) -> Optional[Principle]:
        """Update a principle's status (approve/reject)."""
        if not self._connection:
            return None

        now = datetime.now(timezone.utc).isoformat()
        update_fields = "status = ?, updated_at = ?"
        params: List[Any] = [status.value, now]

        if status == PrincipleStatus.APPROVED:
            update_fields += ", validation_count = validation_count + 1"
        elif status == PrincipleStatus.REJECTED:
            update_fields += ", contradiction_count = contradiction_count + 1"

        await self._connection.execute(
            f"UPDATE principles SET {update_fields} WHERE id = ?",
            params + [principle_id],
        )
        await self._connection.commit()
        return await self.get_principle(principle_id)

    async def update_principle_content(
        self, principle_id: str, content: str
    ) -> Optional[Principle]:
        """Update a principle's content."""
        if not self._connection:
            return None

        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            "UPDATE principles SET content = ?, updated_at = ? WHERE id = ?",
            (content, now, principle_id),
        )
        await self._connection.commit()
        return await self.get_principle(principle_id)

    async def delete_principle(self, principle_id: str) -> bool:
        """Delete a principle by ID."""
        if not self._connection:
            return False
        cursor = await self._connection.execute(
            "DELETE FROM principles WHERE id = ?", (principle_id,)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    def _row_to_principle(self, row: aiosqlite.Row) -> Principle:
        """Convert a database row to a Principle object."""
        created_at = None
        updated_at = None
        try:
            created_at = datetime.fromisoformat(row[10])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            updated_at = datetime.fromisoformat(row[11])
        except (ValueError, TypeError, IndexError):
            pass

        return Principle(
            id=row[0],
            content=row[1],
            domain=row[2],
            confidence=row[3],
            status=PrincipleStatus(row[4]),
            source_chunk_ids=json.loads(row[5]) if row[5] else [],
            topics=json.loads(row[6]) if row[6] else [],
            entities=json.loads(row[7]) if row[7] else [],
            validation_count=row[8],
            contradiction_count=row[9],
            created_at=created_at,
            updated_at=updated_at,
        )


async def get_research_database(db_path: Optional[Path] = None) -> "ResearchDatabase":
    """Get or create the singleton ResearchDatabase instance."""
    global _instance
    if _instance is None:
        _instance = ResearchDatabase(db_path)
        await _instance.initialize()
    return _instance


async def close_research_database() -> None:
    """Close the singleton database connection."""
    global _instance
    if _instance:
        await _instance.close()
        _instance = None
