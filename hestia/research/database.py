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
from hestia.logging import get_logger, LogComponent

logger = get_logger()

from .models import (
    Community,
    Entity,
    EntityType,
    EpisodicNode,
    Fact,
    FactStatus,
    ImportSource,
    Principle,
    PrincipleStatus,
    SourceCategory,
    TemporalType,
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

            CREATE TABLE IF NOT EXISTS principle_edits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                principle_id TEXT NOT NULL,
                original_content TEXT NOT NULL,
                edited_content TEXT NOT NULL,
                removed_fragment TEXT,
                edited_at TEXT NOT NULL,
                FOREIGN KEY (principle_id) REFERENCES principles(id)
            );
            CREATE INDEX IF NOT EXISTS idx_principle_edits_principle ON principle_edits(principle_id);

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

            CREATE TABLE IF NOT EXISTS episodic_nodes (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'default',
                summary TEXT NOT NULL,
                entity_ids TEXT NOT NULL DEFAULT '[]',
                fact_ids TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_episodic_session ON episodic_nodes(session_id);
            CREATE INDEX IF NOT EXISTS idx_episodic_user ON episodic_nodes(user_id);
            CREATE INDEX IF NOT EXISTS idx_episodic_created ON episodic_nodes(created_at);

            CREATE TABLE IF NOT EXISTS import_sources (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL DEFAULT 'default',
                provider TEXT NOT NULL,
                import_type TEXT NOT NULL,
                filename TEXT,
                description TEXT,
                chunk_count INTEGER NOT NULL DEFAULT 0,
                fact_count INTEGER NOT NULL DEFAULT 0,
                entity_count INTEGER NOT NULL DEFAULT 0,
                source_category TEXT NOT NULL DEFAULT 'imported',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_import_sources_user ON import_sources(user_id);
            CREATE INDEX IF NOT EXISTS idx_import_sources_provider ON import_sources(provider);
        """)

        # Sprint 20A: Add durability/temporal/source columns to facts table
        # Sprint 20B: Add import_source_id FK on facts
        for col_sql in [
            "ALTER TABLE facts ADD COLUMN durability_score INTEGER DEFAULT 1",
            "ALTER TABLE facts ADD COLUMN temporal_type TEXT DEFAULT 'dynamic'",
            "ALTER TABLE facts ADD COLUMN source_category TEXT DEFAULT 'conversation'",
            "ALTER TABLE facts ADD COLUMN import_source_id TEXT",
        ]:
            try:
                await self._connection.execute(col_sql)
            except Exception as e:
                if "duplicate column name" not in str(e):
                    logger.warning(
                        "Schema migration issue",
                        component=LogComponent.RESEARCH,
                        data={"sql": col_sql, "error": type(e).__name__},
                    )

        # Sprint 20A: Add first_seen_source to entities table
        try:
            await self._connection.execute(
                "ALTER TABLE entities ADD COLUMN first_seen_source TEXT DEFAULT 'conversation'"
            )
        except Exception as e:
            if "duplicate column name" not in str(e):
                logger.warning(
                    "Schema migration issue",
                    component=LogComponent.RESEARCH,
                    data={"error": type(e).__name__},
                )

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
        """Update a principle's content and log the edit diff."""
        if not self._connection:
            return None

        # Fetch original content for diff logging
        original = await self.get_principle(principle_id)
        if not original:
            return None

        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            "UPDATE principles SET content = ?, updated_at = ? WHERE id = ?",
            (content, now, principle_id),
        )

        # Log the edit with before/after and auto-extracted removed fragment
        removed = self._extract_removed_fragment(original.content, content)
        await self._connection.execute(
            """INSERT INTO principle_edits
               (principle_id, original_content, edited_content, removed_fragment, edited_at)
               VALUES (?, ?, ?, ?, ?)""",
            (principle_id, original.content, content, removed, now),
        )

        await self._connection.commit()
        return await self.get_principle(principle_id)

    @staticmethod
    def _extract_removed_fragment(original: str, edited: str) -> Optional[str]:
        """Extract the text that was removed during an edit.

        Simple approach: find the longest substring of original that's
        not present in edited. Good enough for single-edit trimming.
        """
        if edited in original:
            # Simple case: edited is a substring of original
            removed = original.replace(edited, "").strip()
            # Clean up conjunctions left behind
            for prefix in [" and ", " but ", ", and ", ", but "]:
                removed = removed.removeprefix(prefix).removesuffix(prefix)
            return removed if removed else None

        # Fallback: just note what changed
        return None

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
                user_id, created_at, updated_at, first_seen_source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                entity.first_seen_source.value,
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

    async def search_entities_by_name(self, pattern: str, limit: int = 20) -> List[Entity]:
        """Search entities by canonical_name LIKE pattern."""
        if not self._connection:
            return []
        cursor = await self._connection.execute(
            "SELECT * FROM entities WHERE canonical_name LIKE ? ORDER BY updated_at DESC LIMIT ?",
            (f"%{pattern.lower()}%", limit),
        )
        rows = await cursor.fetchall()
        return [self._row_to_entity(row) for row in rows]

    async def find_entity_by_name_like(self, pattern: str) -> Optional[Entity]:
        """Find the first entity whose canonical_name matches a LIKE pattern."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT * FROM entities WHERE LOWER(canonical_name) LIKE ? LIMIT 1",
            (f"%{pattern.lower()}%",),
        )
        row = await cursor.fetchone()
        return self._row_to_entity(row) if row else None

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
        #          user_id, created_at, updated_at, first_seen_source (Sprint 20B)
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

        # first_seen_source added via ALTER TABLE — may not exist on old DBs
        first_seen_source = SourceCategory.CONVERSATION
        try:
            if len(row) > 9 and row[9]:
                first_seen_source = SourceCategory(row[9])
        except (ValueError, IndexError):
            pass

        return Entity(
            id=row[0],
            name=row[1],
            entity_type=EntityType(row[2]),
            canonical_name=row[3],
            summary=row[4],
            community_id=row[5],
            first_seen_source=first_seen_source,
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
                confidence, user_id, created_at,
                durability_score, temporal_type, source_category, import_source_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                fact.id,
                fact.source_entity_id,
                fact.relation,
                fact.target_entity_id,
                fact.fact_text,
                fact.status.value,
                fact.valid_at.isoformat() if fact.valid_at else None,
                fact.invalid_at.isoformat() if fact.invalid_at else None,
                fact.expired_at.isoformat() if fact.expired_at else None,
                fact.source_chunk_id,
                fact.confidence,
                fact.user_id,
                fact.created_at.isoformat() if fact.created_at else datetime.now(timezone.utc).isoformat(),
                fact.durability_score,
                fact.temporal_type.value,
                fact.source_category.value,
                fact.import_source_id,
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
        #          confidence, user_id, created_at,
        #          durability_score, temporal_type, source_category  (Sprint 20A)
        #          import_source_id  (Sprint 20B)
        def _parse_dt(idx: int) -> Optional[datetime]:
            try:
                val = row[idx]
                return datetime.fromisoformat(val) if val else None
            except (ValueError, TypeError, IndexError):
                return None

        # New columns may not exist on old DBs — safe access
        durability = 1
        temporal_type = TemporalType.DYNAMIC
        source_category = SourceCategory.CONVERSATION
        import_source_id = None
        try:
            if len(row) > 13 and row[13] is not None:
                durability = int(row[13])
            if len(row) > 14 and row[14]:
                temporal_type = TemporalType(row[14])
            if len(row) > 15 and row[15]:
                source_category = SourceCategory(row[15])
            if len(row) > 16 and row[16]:
                import_source_id = row[16]
        except (ValueError, IndexError):
            pass

        return Fact(
            id=row[0],
            source_entity_id=row[1],
            relation=row[2] or "RELATED_TO",
            target_entity_id=row[3],
            fact_text=row[4],
            status=FactStatus(row[5]),
            valid_at=_parse_dt(6),
            invalid_at=_parse_dt(7),
            expired_at=_parse_dt(8),
            source_chunk_id=row[9],
            confidence=row[10] if row[10] is not None else 0.5,
            durability_score=durability,
            temporal_type=temporal_type,
            source_category=source_category,
            import_source_id=import_source_id,
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


    # ── Episodic Nodes ─────────────────────────────────────

    async def store_episodic_node(self, node: EpisodicNode) -> None:
        """Insert an episodic node (conversation summary linked to entities/facts)."""
        if not self._connection:
            raise RuntimeError("Database not initialized")
        await self._connection.execute(
            """INSERT OR REPLACE INTO episodic_nodes
               (id, session_id, user_id, summary, entity_ids, fact_ids, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                node.id,
                node.session_id,
                node.user_id,
                node.summary,
                json.dumps(node.entity_ids),
                json.dumps(node.fact_ids),
                node.created_at.isoformat() if node.created_at else datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._connection.commit()

    async def get_episodic_nodes(
        self,
        user_id: str = "default",
        limit: int = 50,
        offset: int = 0,
    ) -> List[EpisodicNode]:
        """List episodic nodes, newest first."""
        if not self._connection:
            return []
        cursor = await self._connection.execute(
            "SELECT * FROM episodic_nodes WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        rows = await cursor.fetchall()
        return [self._row_to_episodic_node(row) for row in rows]

    async def get_episodic_nodes_for_entity(
        self, entity_id: str, user_id: str = "default",
    ) -> List[EpisodicNode]:
        """Find episodes that mention a specific entity via JSON array search."""
        if not self._connection:
            return []
        # Use json_each to search within the JSON array
        cursor = await self._connection.execute(
            """SELECT DISTINCT e.* FROM episodic_nodes e, json_each(e.entity_ids) j
               WHERE j.value = ? AND e.user_id = ?
               ORDER BY e.created_at DESC""",
            (entity_id, user_id),
        )
        rows = await cursor.fetchall()
        return [self._row_to_episodic_node(row) for row in rows]

    def _row_to_episodic_node(self, row: aiosqlite.Row) -> EpisodicNode:
        """Convert a database row to an EpisodicNode."""
        # Columns: id, session_id, user_id, summary, entity_ids, fact_ids, created_at
        created_at = datetime.now(timezone.utc)
        try:
            created_at = datetime.fromisoformat(row[6])
        except (ValueError, TypeError, IndexError):
            pass

        return EpisodicNode(
            id=row[0],
            session_id=row[1],
            user_id=row[2],
            summary=row[3],
            entity_ids=json.loads(row[4]) if row[4] else [],
            fact_ids=json.loads(row[5]) if row[5] else [],
            created_at=created_at,
        )

    # ── Import Sources CRUD ─────────────────────────────────

    async def create_import_source(self, source: ImportSource) -> ImportSource:
        """Insert a new import source record."""
        if not self._connection:
            raise RuntimeError("Database not initialized")
        await self._connection.execute(
            """INSERT INTO import_sources
               (id, user_id, provider, import_type, filename, description,
                chunk_count, fact_count, entity_count, source_category, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                source.id,
                source.user_id,
                source.provider,
                source.import_type,
                source.filename,
                source.description,
                source.chunk_count,
                source.fact_count,
                source.entity_count,
                source.source_category.value,
                source.created_at.isoformat() if source.created_at else datetime.now(timezone.utc).isoformat(),
            ),
        )
        await self._connection.commit()
        return source

    async def get_import_source(self, source_id: str) -> Optional[ImportSource]:
        """Get a single import source by ID."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT * FROM import_sources WHERE id = ?", (source_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_import_source(row) if row else None

    async def list_import_sources(
        self,
        user_id: str = "default",
        provider: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[ImportSource]:
        """List import sources for a user, newest first."""
        if not self._connection:
            return []

        query = "SELECT * FROM import_sources WHERE user_id = ?"
        params: List[Any] = [user_id]

        if provider:
            query += " AND provider = ?"
            params.append(provider)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_import_source(row) for row in rows]

    async def update_import_source_counts(
        self, source_id: str, chunk_count: int, fact_count: int, entity_count: int
    ) -> None:
        """Update counts after an import completes."""
        if not self._connection:
            return
        await self._connection.execute(
            "UPDATE import_sources SET chunk_count = ?, fact_count = ?, entity_count = ? WHERE id = ?",
            (chunk_count, fact_count, entity_count, source_id),
        )
        await self._connection.commit()

    async def delete_import_source(self, source_id: str) -> bool:
        """Delete an import source by ID."""
        if not self._connection:
            return False
        cursor = await self._connection.execute(
            "DELETE FROM import_sources WHERE id = ?", (source_id,)
        )
        await self._connection.commit()
        return cursor.rowcount > 0

    def _row_to_import_source(self, row: aiosqlite.Row) -> ImportSource:
        """Convert a database row to an ImportSource object."""
        # Columns: id, user_id, provider, import_type, filename, description,
        #          chunk_count, fact_count, entity_count, source_category, created_at
        created_at = None
        try:
            created_at = datetime.fromisoformat(row[10])
        except (ValueError, TypeError, IndexError):
            pass

        return ImportSource(
            id=row[0],
            user_id=row[1],
            provider=row[2],
            import_type=row[3],
            filename=row[4],
            description=row[5],
            chunk_count=row[6] or 0,
            fact_count=row[7] or 0,
            entity_count=row[8] or 0,
            source_category=SourceCategory(row[9]) if row[9] else SourceCategory.IMPORTED,
            created_at=created_at,
        )

    # ── Earliest Fact Date ─────────────────────────────────

    async def get_earliest_fact_date(self) -> Optional[datetime]:
        """Get the earliest valid_at date across all active facts."""
        if not self._connection:
            return None
        cursor = await self._connection.execute(
            "SELECT MIN(valid_at) FROM facts WHERE status = 'active'"
        )
        row = await cursor.fetchone()
        if row and row[0]:
            return datetime.fromisoformat(row[0])
        return None

    # ── Temporal Fact Queries ─────────────────────────────

    async def get_facts_at_time(
        self,
        point_in_time: datetime,
        subject: Optional[str] = None,
        user_id: str = "default",
        limit: int = 100,
    ) -> List[Fact]:
        """Get facts that were valid at a specific point in time.

        A fact is valid at point_in_time if:
        - valid_at <= point_in_time
        - invalid_at IS NULL OR invalid_at > point_in_time
        - expired_at IS NULL (not retracted)
        """
        if not self._connection:
            return []

        pit_str = point_in_time.isoformat()
        query = """
            SELECT f.* FROM facts f
            JOIN entities e ON f.source_entity_id = e.id
            WHERE f.valid_at <= ?
              AND (f.invalid_at IS NULL OR f.invalid_at > ?)
              AND f.expired_at IS NULL
              AND f.user_id = ?
        """
        params: List[Any] = [pit_str, pit_str, user_id]

        if subject:
            query += " AND e.name LIKE ?"
            params.append(f"%{subject}%")

        query += " ORDER BY f.valid_at DESC LIMIT ?"
        params.append(limit)

        cursor = await self._connection.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_fact(row) for row in rows]


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
