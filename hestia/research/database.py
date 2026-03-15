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

from .models import (
    Community,
    Entity,
    EntityType,
    Fact,
    FactStatus,
    Principle,
    PrincipleStatus,
)

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

            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL DEFAULT 'concept',
                canonical_name TEXT NOT NULL,
                summary TEXT,
                community_id TEXT,
                user_id TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_canonical ON entities(canonical_name, user_id);
            CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
            CREATE INDEX IF NOT EXISTS idx_entities_community ON entities(community_id);

            CREATE TABLE IF NOT EXISTS facts (
                id TEXT PRIMARY KEY,
                source_entity_id TEXT NOT NULL,
                relation TEXT NOT NULL,
                target_entity_id TEXT NOT NULL,
                fact_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                valid_at TEXT,
                invalid_at TEXT,
                expired_at TEXT,
                source_chunk_id TEXT,
                confidence REAL NOT NULL DEFAULT 0.5,
                user_id TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_entity_id) REFERENCES entities(id),
                FOREIGN KEY (target_entity_id) REFERENCES entities(id)
            );
            CREATE INDEX IF NOT EXISTS idx_facts_status ON facts(status);
            CREATE INDEX IF NOT EXISTS idx_facts_entities ON facts(source_entity_id, target_entity_id);
            CREATE INDEX IF NOT EXISTS idx_facts_valid ON facts(valid_at);

            CREATE TABLE IF NOT EXISTS communities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                member_entity_ids TEXT DEFAULT '[]',
                summary TEXT,
                user_id TEXT NOT NULL DEFAULT 'default',
                created_at TEXT NOT NULL
            );
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


    # ── Entities CRUD ──────────────────────────────────────

    async def create_entity(self, entity: Entity) -> Entity:
        """Insert a new entity."""
        if not self._connection:
            raise RuntimeError("Database not initialized")
        await self._connection.execute(
            """INSERT INTO entities
               (id, name, entity_type, canonical_name, summary, community_id,
                user_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                entity.id,
                entity.name,
                entity.entity_type.value,
                entity.canonical_name,
                entity.summary,
                entity.community_id,
                entity.user_id,
                entity.created_at.isoformat() if entity.created_at else datetime.now(timezone.utc).isoformat(),
                entity.updated_at.isoformat() if entity.updated_at else datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._connection.commit()
        return entity

    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get a single entity by ID."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_entity(row) if row else None

    async def find_entity_by_name(self, canonical_name: str) -> Optional[Entity]:
        """Find an entity by its canonical (lowercase) name."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT * FROM entities WHERE canonical_name = ?", (canonical_name,)
        )
        row = await cursor.fetchone()
        return self._row_to_entity(row) if row else None

    async def list_entities(
        self,
        entity_type: Optional[EntityType] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Entity]:
        """List entities with optional type filter."""
        if not self._connection:
            return []

        query = "SELECT * FROM entities"
        params: List[Any] = []

        if entity_type:
            query += " WHERE entity_type = ?"
            params.append(entity_type.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_entity(row) for row in rows]

    async def update_entity_summary(self, entity_id: str, summary: str) -> None:
        """Update an entity's summary."""
        if not self._connection:
            return
        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            "UPDATE entities SET summary = ?, updated_at = ? WHERE id = ?",
            (summary, now, entity_id),
        )
        await self._connection.commit()

    async def update_entity_community(self, entity_id: str, community_id: str) -> None:
        """Update an entity's community assignment."""
        if not self._connection:
            return
        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            "UPDATE entities SET community_id = ?, updated_at = ? WHERE id = ?",
            (community_id, now, entity_id),
        )
        await self._connection.commit()

    async def count_entities(self, entity_type: Optional[EntityType] = None) -> int:
        """Count entities with optional type filter."""
        if not self._connection:
            return 0

        query = "SELECT COUNT(*) FROM entities"
        params: List[Any] = []

        if entity_type:
            query += " WHERE entity_type = ?"
            params.append(entity_type.value)

        cursor = await self._connection.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    def _row_to_entity(self, row: aiosqlite.Row) -> Entity:
        """Convert a database row to an Entity object."""
        # Columns: id, name, entity_type, canonical_name, summary, community_id,
        #          user_id, created_at, updated_at
        created_at = None
        updated_at = None
        try:
            created_at = datetime.fromisoformat(row[7])
        except (ValueError, TypeError, IndexError):
            pass
        try:
            updated_at = datetime.fromisoformat(row[8])
        except (ValueError, TypeError, IndexError):
            pass

        return Entity(
            id=row[0],
            name=row[1],
            entity_type=EntityType(row[2]),
            canonical_name=row[3],
            summary=row[4],
            community_id=row[5],
            user_id=row[6],
            created_at=created_at,
            updated_at=updated_at,
        )

    # ── Facts CRUD ───────────────────────────────────────

    async def create_fact(self, fact: Fact) -> Fact:
        """Insert a new fact."""
        if not self._connection:
            raise RuntimeError("Database not initialized")
        await self._connection.execute(
            """INSERT INTO facts
               (id, source_entity_id, relation, target_entity_id, fact_text,
                status, valid_at, invalid_at, expired_at, source_chunk_id,
                confidence, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fact.id,
                fact.source_entity_id,
                fact.fact_text,  # relation column — use fact_text as the relation label
                fact.target_entity_id,
                fact.fact_text,
                fact.status.value,
                fact.valid_at.isoformat() if fact.valid_at else None,
                fact.invalid_at.isoformat() if fact.invalid_at else None,
                fact.expired_at.isoformat() if fact.expired_at else None,
                None,  # source_chunk_id
                fact.weight,
                fact.user_id,
                fact.created_at.isoformat() if fact.created_at else datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._connection.commit()
        return fact

    async def get_fact(self, fact_id: str) -> Optional[Fact]:
        """Get a single fact by ID."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT * FROM facts WHERE id = ?", (fact_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_fact(row) if row else None

    async def list_facts(
        self,
        status: Optional[FactStatus] = None,
        source_entity_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Fact]:
        """List facts with optional filters."""
        if not self._connection:
            return []

        query = "SELECT * FROM facts"
        params: List[Any] = []
        conditions: List[str] = []

        if status:
            conditions.append("status = ?")
            params.append(status.value)
        if source_entity_id:
            conditions.append("source_entity_id = ?")
            params.append(source_entity_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_fact(row) for row in rows]

    async def invalidate_fact(self, fact_id: str) -> Optional[Fact]:
        """Mark a fact as superseded with timestamps."""
        if not self._connection:
            return None

        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._connection.execute(
            """UPDATE facts SET status = ?, invalid_at = ?, expired_at = ?
               WHERE id = ?""",
            (FactStatus.SUPERSEDED.value, now, now, fact_id),
        )
        await self._connection.commit()
        if cursor.rowcount == 0:
            return None
        return await self.get_fact(fact_id)

    async def find_facts_between(
        self, source_id: str, target_id: str, active_only: bool = True
    ) -> List[Fact]:
        """Find facts between two entities."""
        if not self._connection:
            return []

        query = "SELECT * FROM facts WHERE source_entity_id = ? AND target_entity_id = ?"
        params: List[Any] = [source_id, target_id]

        if active_only:
            query += " AND status = ?"
            params.append(FactStatus.ACTIVE.value)

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_fact(row) for row in rows]

    async def get_facts_valid_at(self, point_in_time: datetime) -> List[Fact]:
        """Bi-temporal query: get facts that were valid at a specific point in time."""
        if not self._connection:
            return []

        ts = point_in_time.isoformat()
        cursor = await self._connection.execute(
            """SELECT * FROM facts
               WHERE valid_at <= ? AND (invalid_at IS NULL OR invalid_at > ?)""",
            (ts, ts),
        )
        rows = await cursor.fetchall()
        return [self._row_to_fact(row) for row in rows]

    async def count_facts(self, status: Optional[FactStatus] = None) -> int:
        """Count facts with optional status filter."""
        if not self._connection:
            return 0

        query = "SELECT COUNT(*) FROM facts"
        params: List[Any] = []

        if status:
            query += " WHERE status = ?"
            params.append(status.value)

        cursor = await self._connection.execute(query, params)
        row = await cursor.fetchone()
        return row[0] if row else 0

    def _row_to_fact(self, row: aiosqlite.Row) -> Fact:
        """Convert a database row to a Fact object."""
        # Columns: id, source_entity_id, relation, target_entity_id, fact_text,
        #          status, valid_at, invalid_at, expired_at, source_chunk_id,
        #          confidence, user_id, created_at
        def _parse_dt(idx: int) -> Optional[datetime]:
            try:
                val = row[idx]
                return datetime.fromisoformat(val) if val else None
            except (ValueError, TypeError, IndexError):
                return None

        return Fact(
            id=row[0],
            source_entity_id=row[1],
            # row[2] is relation — skip, use fact_text from row[4]
            target_entity_id=row[3],
            fact_text=row[4],
            status=FactStatus(row[5]),
            valid_at=_parse_dt(6),
            invalid_at=_parse_dt(7),
            expired_at=_parse_dt(8),
            # row[9] is source_chunk_id — not in Fact dataclass
            weight=row[10] if row[10] is not None else 1.0,
            user_id=row[11],
            created_at=_parse_dt(12),
        )

    # ── Communities CRUD ─────────────────────────────────

    async def create_community(self, community: Community) -> Community:
        """Insert a new community."""
        if not self._connection:
            raise RuntimeError("Database not initialized")
        await self._connection.execute(
            """INSERT INTO communities
               (id, name, member_entity_ids, summary, user_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                community.id,
                community.label,
                json.dumps(community.member_entity_ids),
                community.summary,
                community.user_id,
                community.created_at.isoformat() if community.created_at else datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._connection.commit()
        return community

    async def get_community(self, community_id: str) -> Optional[Community]:
        """Get a single community by ID."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT * FROM communities WHERE id = ?", (community_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_community(row) if row else None

    async def list_communities(
        self, limit: int = 50, offset: int = 0
    ) -> List[Community]:
        """List communities with pagination."""
        if not self._connection:
            return []

        cursor = await self._connection.execute(
            "SELECT * FROM communities ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        rows = await cursor.fetchall()
        return [self._row_to_community(row) for row in rows]

    async def update_community_summary(self, community_id: str, summary: str) -> None:
        """Update a community's summary."""
        if not self._connection:
            return
        await self._connection.execute(
            "UPDATE communities SET summary = ? WHERE id = ?",
            (summary, community_id),
        )
        await self._connection.commit()

    async def delete_all_communities(self) -> None:
        """Delete all communities (used before re-detection)."""
        if not self._connection:
            return
        await self._connection.execute("DELETE FROM communities")
        await self._connection.commit()

    def _row_to_community(self, row: aiosqlite.Row) -> Community:
        """Convert a database row to a Community object."""
        # Columns: id, name, member_entity_ids, summary, user_id, created_at
        created_at = None
        try:
            created_at = datetime.fromisoformat(row[5])
        except (ValueError, TypeError, IndexError):
            pass

        return Community(
            id=row[0],
            label=row[1],
            member_entity_ids=json.loads(row[2]) if row[2] else [],
            summary=row[3],
            user_id=row[4],
            created_at=created_at,
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
