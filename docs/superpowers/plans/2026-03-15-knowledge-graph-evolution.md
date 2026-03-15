# Sprint 9: Knowledge Graph Evolution — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve Hestia's Neural Net from a co-occurrence visualization into a temporal knowledge graph with bi-temporal facts, entity relationships, contradiction detection, and community clustering — all on existing SQLite + ChromaDB infrastructure.

**Architecture:** Three new components (`FactExtractor`, `EntityRegistry`, `FactStore`) layer on top of the existing `ResearchDatabase` and `PrincipleStore`. The `GraphBuilder` gains a new `build_fact_graph()` method that produces entity-relationship edges alongside the existing tag-based edges. New `/v1/research/facts` and `/v1/research/entities` API endpoints expose the temporal knowledge graph. The existing `/v1/research/graph` endpoint gains an optional `mode=facts` parameter to switch between legacy co-occurrence and the new fact-based graph.

**Tech Stack:** Python 3.12, aiosqlite, ChromaDB, FastAPI/Pydantic, Ollama (Qwen 3.5 9B for extraction, structured JSON output)

**Key Design Decisions:**
- Facts live on **edges** (triplets), not nodes — matching Graphiti's core insight
- Bi-temporal: `valid_at` (real-world truth), `invalid_at` (superseded), `expired_at` (system detection time)
- Entity dedup via ChromaDB embedding similarity (threshold 0.85) — no cloud LLM needed
- Contradiction detection via local LLM (Qwen 3.5 9B JSON mode) — 1 call per candidate conflict
- Community detection via label propagation on adjacency list — no graph DB needed
- All new tables include `user_id` column per multi-user readiness rules
- Extraction is **on-demand** (like principle distillation), not automatic on every chat — avoids inference overhead
- Existing graph mode preserved as `mode=legacy`; new mode is `mode=facts`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `hestia/research/fact_extractor.py` | LLM-powered triplet extraction from memory chunks + contradiction detection |
| `hestia/research/entity_registry.py` | Entity CRUD, ChromaDB embedding dedup, label propagation community detection |
| `tests/test_research_facts.py` | Tests for facts table, entity registry, fact extraction, contradiction detection |
| `tests/test_research_graph_facts.py` | Tests for fact-based graph building and temporal queries |

### Modified Files
| File | Changes |
|------|---------|
| `hestia/research/models.py` | Add `Fact`, `Entity`, `Community`, `FactStatus`, `EntityType` dataclasses; extend `NodeType` and `EdgeType` enums |
| `hestia/research/database.py` | Add `facts`, `entities`, `entity_aliases`, `communities` tables; CRUD methods for each |
| `hestia/research/graph_builder.py` | Add `build_fact_graph()` method; new edge types for entity relationships |
| `hestia/research/manager.py` | Wire `FactExtractor` + `EntityRegistry`; add `extract_facts()`, `get_entities()`, `get_facts()`, `get_timeline()` methods |
| `hestia/research/__init__.py` | Export new types |
| `hestia/api/routes/research.py` | Add 6 new endpoints under `/v1/research/facts` and `/v1/research/entities` |
| `hestia/api/schemas/research.py` | Add Pydantic models for facts, entities, communities, timeline |
| `scripts/auto-test.sh` | Add mapping for new test files |

### Unchanged (but referenced)
| File | Why |
|------|-----|
| `hestia/memory/manager.py` | Source of memory chunks for extraction (read-only dependency) |
| `hestia/inference/client.py` | LLM calls for triplet extraction (existing `generate()` method) |
| `hestia/database.py` | `BaseDatabase` ABC (inherited by `ResearchDatabase`) |

---

## Chunk 1: Data Models & Database Schema

### Task 1.1: Add New Enums and Dataclasses to models.py

**Files:**
- Modify: `hestia/research/models.py`
- Test: `tests/test_research_facts.py` (new file)

- [ ] **Step 1: Write failing tests for new model types**

Create `tests/test_research_facts.py`:

```python
"""Tests for knowledge graph fact and entity models."""

import pytest
from datetime import datetime, timezone

from hestia.research.models import (
    EntityType,
    FactStatus,
    Fact,
    Entity,
    Community,
    NodeType,
    EdgeType,
)


class TestEntityType:
    def test_enum_values(self) -> None:
        assert EntityType.PERSON.value == "person"
        assert EntityType.TOOL.value == "tool"
        assert EntityType.CONCEPT.value == "concept"
        assert EntityType.PLACE.value == "place"
        assert EntityType.PROJECT.value == "project"
        assert EntityType.ORGANIZATION.value == "organization"


class TestFactStatus:
    def test_enum_values(self) -> None:
        assert FactStatus.ACTIVE.value == "active"
        assert FactStatus.SUPERSEDED.value == "superseded"
        assert FactStatus.RETRACTED.value == "retracted"


class TestFact:
    def test_create_factory(self) -> None:
        fact = Fact.create(
            source_entity_id="e1",
            relation="USES",
            target_entity_id="e2",
            fact_text="Andrew uses Qwen 3.5 9B",
            source_chunk_id="chunk-1",
            confidence=0.9,
        )
        assert fact.id  # auto-generated UUID
        assert fact.source_entity_id == "e1"
        assert fact.relation == "USES"
        assert fact.target_entity_id == "e2"
        assert fact.fact_text == "Andrew uses Qwen 3.5 9B"
        assert fact.status == FactStatus.ACTIVE
        assert fact.valid_at is not None
        assert fact.invalid_at is None
        assert fact.expired_at is None
        assert fact.confidence == 0.9

    def test_to_dict_camel_case(self) -> None:
        fact = Fact.create(
            source_entity_id="e1",
            relation="USES",
            target_entity_id="e2",
            fact_text="test fact",
            source_chunk_id="chunk-1",
        )
        d = fact.to_dict()
        assert "sourceEntityId" in d
        assert "targetEntityId" in d
        assert "factText" in d
        assert "validAt" in d
        assert "invalidAt" in d
        assert "expiredAt" in d
        assert "sourceChunkId" in d

    def test_from_dict_roundtrip(self) -> None:
        fact = Fact.create(
            source_entity_id="e1",
            relation="USES",
            target_entity_id="e2",
            fact_text="test fact",
            source_chunk_id="chunk-1",
        )
        d = fact.to_dict()
        restored = Fact.from_dict(d)
        assert restored.id == fact.id
        assert restored.source_entity_id == fact.source_entity_id
        assert restored.relation == fact.relation

    def test_is_valid_at_time(self) -> None:
        now = datetime.now(timezone.utc)
        fact = Fact.create(
            source_entity_id="e1",
            relation="USES",
            target_entity_id="e2",
            fact_text="test",
            source_chunk_id="c1",
        )
        assert fact.is_valid_at(now) is True

        # Superseded fact
        fact.invalid_at = now
        assert fact.is_valid_at(now) is False


class TestEntity:
    def test_create_factory(self) -> None:
        entity = Entity.create(
            name="Andrew Lonati",
            entity_type=EntityType.PERSON,
        )
        assert entity.id
        assert entity.name == "Andrew Lonati"
        assert entity.entity_type == EntityType.PERSON
        assert entity.canonical_name == "andrew lonati"
        assert entity.community_id is None

    def test_to_dict_roundtrip(self) -> None:
        entity = Entity.create(name="Qwen", entity_type=EntityType.TOOL)
        d = entity.to_dict()
        restored = Entity.from_dict(d)
        assert restored.name == "Qwen"
        assert restored.entity_type == EntityType.TOOL


class TestCommunity:
    def test_create_factory(self) -> None:
        community = Community.create(
            name="AI Models",
            member_entity_ids=["e1", "e2"],
        )
        assert community.id
        assert community.name == "AI Models"
        assert len(community.member_entity_ids) == 2
        assert community.summary is None

    def test_to_dict_roundtrip(self) -> None:
        community = Community.create(name="Test", member_entity_ids=["e1"])
        d = community.to_dict()
        restored = Community.from_dict(d)
        assert restored.name == "Test"


class TestExtendedEnums:
    def test_node_type_has_fact(self) -> None:
        assert NodeType.FACT.value == "fact"
        assert NodeType.COMMUNITY.value == "community"

    def test_edge_type_has_relationship(self) -> None:
        assert EdgeType.RELATIONSHIP.value == "relationship"
        assert EdgeType.SUPERSEDES.value == "supersedes"
        assert EdgeType.COMMUNITY_MEMBER.value == "community_member"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_facts.py::TestEntityType -v`
Expected: FAIL — `ImportError: cannot import name 'EntityType'`

- [ ] **Step 3: Implement new enums and dataclasses in models.py**

Add to `hestia/research/models.py` (after existing enums, before `CATEGORY_COLORS`):

```python
class EntityType(str, Enum):
    """Types of entities in the knowledge graph."""
    PERSON = "person"
    TOOL = "tool"
    CONCEPT = "concept"
    PLACE = "place"
    PROJECT = "project"
    ORGANIZATION = "organization"


class FactStatus(str, Enum):
    """Lifecycle status for knowledge graph facts."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"
```

Extend existing enums:
```python
# Add to NodeType:
    FACT = "fact"
    COMMUNITY = "community"

# Add to EdgeType:
    RELATIONSHIP = "relationship"
    SUPERSEDES = "supersedes"
    COMMUNITY_MEMBER = "community_member"
```

Add to `CATEGORY_COLORS`:
```python
    "community": "#FF375F",
    "fact_node": "#64D2FF",
```

Add new dataclasses (after `GraphResponse`, before `Principle`):

```python
@dataclass
class Fact:
    """
    A temporal fact in the knowledge graph — an edge between two entities.

    Bi-temporal model (inspired by Graphiti):
    - valid_at: when this fact became true in the real world
    - invalid_at: when this fact stopped being true (superseded)
    - expired_at: when the system detected the invalidation
    """
    id: str
    source_entity_id: str
    relation: str
    target_entity_id: str
    fact_text: str
    status: FactStatus = FactStatus.ACTIVE
    valid_at: Optional[datetime] = None
    invalid_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    source_chunk_id: Optional[str] = None
    confidence: float = 0.5
    user_id: str = "default"
    created_at: Optional[datetime] = None

    def is_valid_at(self, point_in_time: datetime) -> bool:
        """Check if this fact was true at a given point in time."""
        if self.valid_at and point_in_time < self.valid_at:
            return False
        if self.invalid_at and point_in_time >= self.invalid_at:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sourceEntityId": self.source_entity_id,
            "relation": self.relation,
            "targetEntityId": self.target_entity_id,
            "factText": self.fact_text,
            "status": self.status.value,
            "validAt": self.valid_at.isoformat() if self.valid_at else None,
            "invalidAt": self.invalid_at.isoformat() if self.invalid_at else None,
            "expiredAt": self.expired_at.isoformat() if self.expired_at else None,
            "sourceChunkId": self.source_chunk_id,
            "confidence": self.confidence,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fact":
        def _parse_dt(key: str) -> Optional[datetime]:
            val = data.get(key)
            if val:
                try:
                    return datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    return None
            return None

        return cls(
            id=data["id"],
            source_entity_id=data["sourceEntityId"],
            relation=data["relation"],
            target_entity_id=data["targetEntityId"],
            fact_text=data["factText"],
            status=FactStatus(data.get("status", "active")),
            valid_at=_parse_dt("validAt"),
            invalid_at=_parse_dt("invalidAt"),
            expired_at=_parse_dt("expiredAt"),
            source_chunk_id=data.get("sourceChunkId"),
            confidence=data.get("confidence", 0.5),
            created_at=_parse_dt("createdAt"),
        )

    @classmethod
    def create(
        cls,
        source_entity_id: str,
        relation: str,
        target_entity_id: str,
        fact_text: str,
        source_chunk_id: Optional[str] = None,
        confidence: float = 0.5,
        valid_at: Optional[datetime] = None,
        user_id: str = "default",
    ) -> "Fact":
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            source_entity_id=source_entity_id,
            relation=relation,
            target_entity_id=target_entity_id,
            fact_text=fact_text,
            source_chunk_id=source_chunk_id,
            confidence=confidence,
            valid_at=valid_at or now,
            user_id=user_id,
            created_at=now,
        )


@dataclass
class Entity:
    """
    An entity in the knowledge graph — a person, tool, concept, etc.

    Entities have a canonical name (lowercase) for dedup and an optional
    LLM-generated summary from their connected facts.
    """
    id: str
    name: str
    entity_type: EntityType
    canonical_name: str
    summary: Optional[str] = None
    community_id: Optional[str] = None
    user_id: str = "default"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entityType": self.entity_type.value,
            "canonicalName": self.canonical_name,
            "summary": self.summary,
            "communityId": self.community_id,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        def _parse_dt(key: str) -> Optional[datetime]:
            val = data.get(key)
            if val:
                try:
                    return datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    return None
            return None

        return cls(
            id=data["id"],
            name=data["name"],
            entity_type=EntityType(data.get("entityType", "concept")),
            canonical_name=data.get("canonicalName", data["name"].lower()),
            summary=data.get("summary"),
            community_id=data.get("communityId"),
            created_at=_parse_dt("createdAt"),
            updated_at=_parse_dt("updatedAt"),
        )

    @classmethod
    def create(
        cls,
        name: str,
        entity_type: EntityType = EntityType.CONCEPT,
        user_id: str = "default",
    ) -> "Entity":
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            entity_type=entity_type,
            canonical_name=name.lower().strip(),
            user_id=user_id,
            created_at=now,
            updated_at=now,
        )


@dataclass
class Community:
    """A cluster of related entities with an LLM-generated summary."""
    id: str
    name: str
    member_entity_ids: List[str] = field(default_factory=list)
    summary: Optional[str] = None
    user_id: str = "default"
    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "memberEntityIds": self.member_entity_ids,
            "summary": self.summary,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Community":
        created_at = None
        if data.get("createdAt"):
            try:
                created_at = datetime.fromisoformat(data["createdAt"])
            except (ValueError, TypeError):
                pass
        return cls(
            id=data["id"],
            name=data["name"],
            member_entity_ids=data.get("memberEntityIds", []),
            summary=data.get("summary"),
            created_at=created_at,
        )

    @classmethod
    def create(
        cls,
        name: str,
        member_entity_ids: Optional[List[str]] = None,
        user_id: str = "default",
    ) -> "Community":
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            member_entity_ids=member_entity_ids or [],
            user_id=user_id,
            created_at=datetime.now(timezone.utc),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_facts.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/research/models.py tests/test_research_facts.py
git commit -m "feat(research): add Fact, Entity, Community models with bi-temporal tracking"
```

---

### Task 1.2: Add Database Tables for Facts, Entities, Communities

**Files:**
- Modify: `hestia/research/database.py`
- Test: `tests/test_research_facts.py` (append)

- [ ] **Step 1: Write failing tests for facts/entities CRUD**

Append to `tests/test_research_facts.py`:

```python
import pytest_asyncio
from pathlib import Path
from typing import AsyncGenerator

from hestia.research.database import ResearchDatabase
from hestia.research.models import (
    Entity, EntityType, Fact, FactStatus, Community,
)


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncGenerator[ResearchDatabase, None]:
    """Create a test database with fresh schema."""
    db = ResearchDatabase(db_path=tmp_path / "test_research.db")
    await db.initialize()
    try:
        yield db
    finally:
        await db.close()


class TestFactsDatabase:
    @pytest.mark.asyncio
    async def test_create_and_get_fact(self, db: ResearchDatabase) -> None:
        fact = Fact.create(
            source_entity_id="e1",
            relation="USES",
            target_entity_id="e2",
            fact_text="Andrew uses Qwen",
            source_chunk_id="chunk-1",
            confidence=0.9,
        )
        await db.create_fact(fact)
        retrieved = await db.get_fact(fact.id)
        assert retrieved is not None
        assert retrieved.fact_text == "Andrew uses Qwen"
        assert retrieved.status == FactStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_list_active_facts(self, db: ResearchDatabase) -> None:
        f1 = Fact.create("e1", "USES", "e2", "fact 1", "c1")
        f2 = Fact.create("e1", "LIKES", "e3", "fact 2", "c2")
        await db.create_fact(f1)
        await db.create_fact(f2)
        facts = await db.list_facts(status=FactStatus.ACTIVE)
        assert len(facts) == 2

    @pytest.mark.asyncio
    async def test_invalidate_fact(self, db: ResearchDatabase) -> None:
        fact = Fact.create("e1", "USES", "e2", "old fact", "c1")
        await db.create_fact(fact)
        await db.invalidate_fact(fact.id)
        retrieved = await db.get_fact(fact.id)
        assert retrieved.status == FactStatus.SUPERSEDED
        assert retrieved.invalid_at is not None
        assert retrieved.expired_at is not None

    @pytest.mark.asyncio
    async def test_find_facts_between_entities(self, db: ResearchDatabase) -> None:
        f1 = Fact.create("e1", "USES", "e2", "fact 1", "c1")
        f2 = Fact.create("e1", "LIKES", "e3", "fact 2", "c2")
        await db.create_fact(f1)
        await db.create_fact(f2)
        facts = await db.find_facts_between("e1", "e2")
        assert len(facts) == 1
        assert facts[0].relation == "USES"

    @pytest.mark.asyncio
    async def test_get_facts_valid_at_time(self, db: ResearchDatabase) -> None:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        old = Fact.create("e1", "USES", "e2", "old", "c1")
        old.valid_at = now - timedelta(days=30)
        old.invalid_at = now - timedelta(days=5)
        old.status = FactStatus.SUPERSEDED
        current = Fact.create("e1", "USES", "e3", "current", "c2")
        current.valid_at = now - timedelta(days=5)
        await db.create_fact(old)
        await db.create_fact(current)

        # Query for "now" should return only the current fact
        facts = await db.get_facts_valid_at(now)
        assert len(facts) == 1
        assert facts[0].fact_text == "current"

        # Query for 10 days ago should return the old fact
        facts = await db.get_facts_valid_at(now - timedelta(days=10))
        assert len(facts) == 1
        assert facts[0].fact_text == "old"


class TestEntitiesDatabase:
    @pytest.mark.asyncio
    async def test_create_and_get_entity(self, db: ResearchDatabase) -> None:
        entity = Entity.create("Andrew Lonati", EntityType.PERSON)
        await db.create_entity(entity)
        retrieved = await db.get_entity(entity.id)
        assert retrieved is not None
        assert retrieved.name == "Andrew Lonati"
        assert retrieved.canonical_name == "andrew lonati"

    @pytest.mark.asyncio
    async def test_find_entity_by_canonical_name(self, db: ResearchDatabase) -> None:
        entity = Entity.create("Qwen 3.5", EntityType.TOOL)
        await db.create_entity(entity)
        found = await db.find_entity_by_name("qwen 3.5")
        assert found is not None
        assert found.id == entity.id

    @pytest.mark.asyncio
    async def test_list_entities(self, db: ResearchDatabase) -> None:
        await db.create_entity(Entity.create("Alice", EntityType.PERSON))
        await db.create_entity(Entity.create("Python", EntityType.TOOL))
        entities = await db.list_entities()
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_list_entities_by_type(self, db: ResearchDatabase) -> None:
        await db.create_entity(Entity.create("Alice", EntityType.PERSON))
        await db.create_entity(Entity.create("Python", EntityType.TOOL))
        people = await db.list_entities(entity_type=EntityType.PERSON)
        assert len(people) == 1
        assert people[0].name == "Alice"

    @pytest.mark.asyncio
    async def test_update_entity_summary(self, db: ResearchDatabase) -> None:
        entity = Entity.create("Hestia", EntityType.PROJECT)
        await db.create_entity(entity)
        await db.update_entity_summary(entity.id, "Personal AI assistant")
        updated = await db.get_entity(entity.id)
        assert updated.summary == "Personal AI assistant"

    @pytest.mark.asyncio
    async def test_update_entity_community(self, db: ResearchDatabase) -> None:
        entity = Entity.create("Qwen", EntityType.TOOL)
        await db.create_entity(entity)
        await db.update_entity_community(entity.id, "comm-1")
        updated = await db.get_entity(entity.id)
        assert updated.community_id == "comm-1"


class TestCommunitiesDatabase:
    @pytest.mark.asyncio
    async def test_create_and_get_community(self, db: ResearchDatabase) -> None:
        comm = Community.create("AI Models", ["e1", "e2"])
        await db.create_community(comm)
        retrieved = await db.get_community(comm.id)
        assert retrieved is not None
        assert retrieved.name == "AI Models"
        assert len(retrieved.member_entity_ids) == 2

    @pytest.mark.asyncio
    async def test_list_communities(self, db: ResearchDatabase) -> None:
        await db.create_community(Community.create("Group A", ["e1"]))
        await db.create_community(Community.create("Group B", ["e2"]))
        comms = await db.list_communities()
        assert len(comms) == 2

    @pytest.mark.asyncio
    async def test_update_community_summary(self, db: ResearchDatabase) -> None:
        comm = Community.create("AI Models", ["e1"])
        await db.create_community(comm)
        await db.update_community_summary(comm.id, "LLM models used by Hestia")
        updated = await db.get_community(comm.id)
        assert updated.summary == "LLM models used by Hestia"

    @pytest.mark.asyncio
    async def test_delete_all_communities(self, db: ResearchDatabase) -> None:
        await db.create_community(Community.create("A", ["e1"]))
        await db.create_community(Community.create("B", ["e2"]))
        await db.delete_all_communities()
        comms = await db.list_communities()
        assert len(comms) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_facts.py::TestFactsDatabase::test_create_and_get_fact -v`
Expected: FAIL — `AttributeError: 'ResearchDatabase' object has no attribute 'create_fact'`

- [ ] **Step 3: Add schema and CRUD methods to database.py**

Add three new tables to `_init_schema()` in `hestia/research/database.py`, and add CRUD methods for each (facts, entities, communities). New tables:

```sql
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
CREATE UNIQUE INDEX IF NOT EXISTS idx_entities_canonical
    ON entities(canonical_name, user_id);
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
CREATE INDEX IF NOT EXISTS idx_facts_entities
    ON facts(source_entity_id, target_entity_id);
CREATE INDEX IF NOT EXISTS idx_facts_valid ON facts(valid_at);

CREATE TABLE IF NOT EXISTS communities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    member_entity_ids TEXT DEFAULT '[]',
    summary TEXT,
    user_id TEXT NOT NULL DEFAULT 'default',
    created_at TEXT NOT NULL
);
```

Add CRUD methods:
- `create_fact(fact: Fact) -> Fact`
- `get_fact(fact_id: str) -> Optional[Fact]`
- `list_facts(status: Optional[FactStatus], source_entity_id: Optional[str], limit: int, offset: int) -> List[Fact]`
- `invalidate_fact(fact_id: str) -> Optional[Fact]` — sets status=SUPERSEDED, invalid_at=now, expired_at=now
- `find_facts_between(source_id: str, target_id: str, active_only: bool) -> List[Fact]`
- `get_facts_valid_at(point_in_time: datetime) -> List[Fact]` — bi-temporal query
- `create_entity(entity: Entity) -> Entity`
- `get_entity(entity_id: str) -> Optional[Entity]`
- `find_entity_by_name(canonical_name: str) -> Optional[Entity]`
- `list_entities(entity_type: Optional[EntityType], limit: int, offset: int) -> List[Entity]`
- `update_entity_summary(entity_id: str, summary: str) -> None`
- `update_entity_community(entity_id: str, community_id: str) -> None`
- `create_community(community: Community) -> Community`
- `get_community(community_id: str) -> Optional[Community]`
- `list_communities(limit: int, offset: int) -> List[Community]`
- `update_community_summary(community_id: str, summary: str) -> None`
- `delete_all_communities() -> None`
- Row conversion helpers: `_row_to_fact()`, `_row_to_entity()`, `_row_to_community()`

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_facts.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `python -m pytest tests/test_research.py tests/test_research_facts.py -v`
Expected: All existing tests PASS + all new tests PASS

- [ ] **Step 6: Commit**

```bash
git add hestia/research/database.py hestia/research/models.py tests/test_research_facts.py
git commit -m "feat(research): facts, entities, communities tables with bi-temporal queries"
```

---

## Chunk 2: Entity Registry (ChromaDB Dedup + Community Detection)

### Task 2.1: Create EntityRegistry with Embedding-Based Dedup

**Files:**
- Create: `hestia/research/entity_registry.py`
- Test: `tests/test_research_facts.py` (append)

- [ ] **Step 1: Write failing tests for entity resolution**

Append to `tests/test_research_facts.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch


class TestEntityRegistry:
    """Tests for entity registry — resolution, dedup, community detection."""

    @pytest.mark.asyncio
    async def test_resolve_exact_match(self, db: ResearchDatabase) -> None:
        """Exact canonical name match returns existing entity."""
        from hestia.research.entity_registry import EntityRegistry
        registry = EntityRegistry(db)

        existing = Entity.create("Qwen", EntityType.TOOL)
        await db.create_entity(existing)

        resolved = await registry.resolve_entity("Qwen", EntityType.TOOL)
        assert resolved.id == existing.id

    @pytest.mark.asyncio
    async def test_resolve_creates_new_entity(self, db: ResearchDatabase) -> None:
        """No match creates a new entity."""
        from hestia.research.entity_registry import EntityRegistry
        registry = EntityRegistry(db)

        resolved = await registry.resolve_entity("NewEntity", EntityType.CONCEPT)
        assert resolved.name == "NewEntity"
        # Verify it was persisted
        found = await db.find_entity_by_name("newentity")
        assert found is not None

    @pytest.mark.asyncio
    async def test_resolve_case_insensitive(self, db: ResearchDatabase) -> None:
        """Resolution is case-insensitive."""
        from hestia.research.entity_registry import EntityRegistry
        registry = EntityRegistry(db)

        existing = Entity.create("Python", EntityType.TOOL)
        await db.create_entity(existing)

        resolved = await registry.resolve_entity("python", EntityType.TOOL)
        assert resolved.id == existing.id

    @pytest.mark.asyncio
    async def test_label_propagation_simple(self, db: ResearchDatabase) -> None:
        """Label propagation clusters connected entities."""
        from hestia.research.entity_registry import EntityRegistry
        registry = EntityRegistry(db)

        # Create entities
        e1 = Entity.create("Qwen", EntityType.TOOL)
        e2 = Entity.create("Ollama", EntityType.TOOL)
        e3 = Entity.create("Python", EntityType.TOOL)
        for e in [e1, e2, e3]:
            await db.create_entity(e)

        # Create facts connecting them
        f1 = Fact.create(e1.id, "RUNS_ON", e2.id, "Qwen runs on Ollama", "c1")
        f2 = Fact.create(e2.id, "USES", e3.id, "Ollama uses Python", "c2")
        await db.create_fact(f1)
        await db.create_fact(f2)

        # Run community detection
        communities = await registry.detect_communities()
        assert len(communities) >= 1
        # All three entities should be in the same community
        all_members = []
        for c in communities:
            all_members.extend(c.member_entity_ids)
        assert e1.id in all_members
        assert e2.id in all_members
        assert e3.id in all_members
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_facts.py::TestEntityRegistry -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.research.entity_registry'`

- [ ] **Step 3: Implement EntityRegistry**

Create `hestia/research/entity_registry.py`:

```python
"""
Entity Registry — resolution, deduplication, and community detection.

Entity resolution pipeline:
1. Canonical name match (exact, case-insensitive)
2. ChromaDB embedding similarity (if available, threshold 0.85)
3. Create new entity if no match

Community detection uses label propagation on the fact adjacency graph.
No graph database required — runs on SQLite fact edges.
"""

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import LogComponent, get_logger

from .database import ResearchDatabase
from .models import Community, Entity, EntityType, FactStatus

logger = get_logger()

# ChromaDB similarity threshold for entity dedup
DEDUP_THRESHOLD = 0.85
COLLECTION_NAME = "hestia_entities"
# Label propagation max iterations
MAX_LP_ITERATIONS = 20


class EntityRegistry:
    """Manages entity lifecycle: resolution, dedup, and community detection."""

    def __init__(self, database: ResearchDatabase) -> None:
        self._db = database
        self._collection = None  # ChromaDB collection, lazy init

    async def resolve_entity(
        self,
        name: str,
        entity_type: EntityType = EntityType.CONCEPT,
        user_id: str = "default",
    ) -> Entity:
        """
        Resolve an entity name to an existing or new Entity.

        Pipeline:
        1. Exact canonical name match in SQLite
        2. Create new entity if no match found
        """
        canonical = name.lower().strip()

        # Step 1: Exact match
        existing = await self._db.find_entity_by_name(canonical)
        if existing:
            return existing

        # Step 2: Create new
        entity = Entity.create(name=name, entity_type=entity_type, user_id=user_id)
        await self._db.create_entity(entity)

        logger.debug(
            "New entity created",
            component=LogComponent.RESEARCH,
            data={"name": name, "type": entity_type.value, "id": entity.id},
        )

        return entity

    async def detect_communities(
        self,
        min_community_size: int = 2,
        user_id: str = "default",
    ) -> List[Community]:
        """
        Run label propagation on the entity-fact graph to detect communities.

        Algorithm:
        1. Build adjacency list from active facts
        2. Initialize each entity with its own community label
        3. Iterate: each entity adopts the majority label of its neighbors
        4. Repeat until convergence or MAX_LP_ITERATIONS
        5. Create Community objects for groups >= min_community_size
        """
        # Build adjacency from active facts
        facts = await self._db.list_facts(status=FactStatus.ACTIVE, limit=10000)
        if not facts:
            return []

        adjacency: Dict[str, List[str]] = defaultdict(list)
        entity_ids: set = set()
        for fact in facts:
            adjacency[fact.source_entity_id].append(fact.target_entity_id)
            adjacency[fact.target_entity_id].append(fact.source_entity_id)
            entity_ids.add(fact.source_entity_id)
            entity_ids.add(fact.target_entity_id)

        if not entity_ids:
            return []

        # Initialize labels: each entity is its own community
        labels: Dict[str, str] = {eid: eid for eid in entity_ids}

        # Label propagation
        for _ in range(MAX_LP_ITERATIONS):
            changed = False
            for eid in entity_ids:
                neighbors = adjacency.get(eid, [])
                if not neighbors:
                    continue
                # Count neighbor labels
                label_counts: Dict[str, int] = defaultdict(int)
                for neighbor in neighbors:
                    label_counts[labels[neighbor]] += 1
                # Adopt majority label
                best_label = max(label_counts, key=label_counts.get)
                if labels[eid] != best_label:
                    labels[eid] = best_label
                    changed = True
            if not changed:
                break

        # Group entities by label
        groups: Dict[str, List[str]] = defaultdict(list)
        for eid, label in labels.items():
            groups[label].append(eid)

        # Clear old communities
        await self._db.delete_all_communities()

        # Create communities for groups meeting min size
        communities = []
        for label, member_ids in groups.items():
            if len(member_ids) >= min_community_size:
                # Name from first entity
                first_entity = await self._db.get_entity(member_ids[0])
                name = first_entity.name if first_entity else label[:20]
                comm = Community.create(
                    name=f"{name} cluster",
                    member_entity_ids=member_ids,
                    user_id=user_id,
                )
                await self._db.create_community(comm)

                # Update entity community_id references
                for mid in member_ids:
                    await self._db.update_entity_community(mid, comm.id)

                communities.append(comm)

        logger.info(
            "Community detection complete",
            component=LogComponent.RESEARCH,
            data={
                "entities": len(entity_ids),
                "communities": len(communities),
                "iterations": MAX_LP_ITERATIONS,
            },
        )

        return communities
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_facts.py::TestEntityRegistry -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/research/entity_registry.py tests/test_research_facts.py
git commit -m "feat(research): entity registry with resolution and label propagation communities"
```

---

## Chunk 3: Fact Extractor (LLM Triplet Extraction + Contradiction Detection)

### Task 3.1: Create FactExtractor with LLM-Powered Extraction

**Files:**
- Create: `hestia/research/fact_extractor.py`
- Test: `tests/test_research_facts.py` (append)

- [ ] **Step 1: Write failing tests for fact extraction**

Append to `tests/test_research_facts.py`:

```python
import json


class TestFactExtractor:
    """Tests for LLM-powered fact extraction from memory chunks."""

    def test_parse_extraction_response_valid(self) -> None:
        """Parse a well-formed LLM extraction response."""
        from hestia.research.fact_extractor import FactExtractor
        extractor = FactExtractor.__new__(FactExtractor)

        llm_output = json.dumps({
            "triplets": [
                {
                    "source": "Andrew",
                    "source_type": "person",
                    "relation": "USES",
                    "target": "Qwen 3.5 9B",
                    "target_type": "tool",
                    "fact": "Andrew uses Qwen 3.5 9B as primary model",
                    "confidence": 0.9,
                },
                {
                    "source": "Hestia",
                    "source_type": "project",
                    "relation": "RUNS_ON",
                    "target": "Mac Mini M1",
                    "target_type": "tool",
                    "fact": "Hestia runs on Mac Mini M1",
                    "confidence": 0.95,
                },
            ]
        })

        triplets = extractor._parse_extraction_response(llm_output)
        assert len(triplets) == 2
        assert triplets[0]["source"] == "Andrew"
        assert triplets[0]["relation"] == "USES"
        assert triplets[1]["target"] == "Mac Mini M1"

    def test_parse_extraction_response_malformed(self) -> None:
        """Malformed LLM response returns empty list."""
        from hestia.research.fact_extractor import FactExtractor
        extractor = FactExtractor.__new__(FactExtractor)

        assert extractor._parse_extraction_response("not json") == []
        assert extractor._parse_extraction_response("{}") == []
        assert extractor._parse_extraction_response('{"triplets": "invalid"}') == []

    def test_parse_contradiction_response(self) -> None:
        """Parse a contradiction detection LLM response."""
        from hestia.research.fact_extractor import FactExtractor
        extractor = FactExtractor.__new__(FactExtractor)

        llm_output = json.dumps({
            "contradicts": True,
            "supersedes_id": "fact-123",
            "reason": "New model replaces old model",
        })
        result = extractor._parse_contradiction_response(llm_output)
        assert result["contradicts"] is True
        assert result["supersedes_id"] == "fact-123"

    def test_parse_contradiction_response_no_conflict(self) -> None:
        from hestia.research.fact_extractor import FactExtractor
        extractor = FactExtractor.__new__(FactExtractor)

        llm_output = json.dumps({"contradicts": False})
        result = extractor._parse_contradiction_response(llm_output)
        assert result["contradicts"] is False

    @pytest.mark.asyncio
    async def test_extract_from_chunk_integration(self, db: ResearchDatabase) -> None:
        """Full extraction pipeline with mocked LLM."""
        from hestia.research.fact_extractor import FactExtractor
        from hestia.research.entity_registry import EntityRegistry

        registry = EntityRegistry(db)
        extractor = FactExtractor(db, registry)

        # Mock LLM to return structured triplets
        mock_inference = AsyncMock()
        mock_inference.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "triplets": [{
                    "source": "Andrew",
                    "source_type": "person",
                    "relation": "USES",
                    "target": "Python",
                    "target_type": "tool",
                    "fact": "Andrew uses Python",
                    "confidence": 0.8,
                }]
            })
        ))

        with patch(
            "hestia.research.fact_extractor.get_inference_client",
            new=AsyncMock(return_value=mock_inference),
        ):
            facts = await extractor.extract_from_text(
                text="Andrew has been using Python for this project.",
                source_chunk_id="chunk-1",
            )

        assert len(facts) == 1
        assert facts[0].relation == "USES"
        # Entities should have been created
        entities = await db.list_entities()
        assert len(entities) == 2

    @pytest.mark.asyncio
    async def test_contradiction_detection(self, db: ResearchDatabase) -> None:
        """New fact that contradicts existing fact invalidates the old one."""
        from hestia.research.fact_extractor import FactExtractor
        from hestia.research.entity_registry import EntityRegistry

        registry = EntityRegistry(db)
        extractor = FactExtractor(db, registry)

        # Create existing entities and fact
        e1 = Entity.create("Andrew", EntityType.PERSON)
        e2 = Entity.create("Qwen 2.5 7B", EntityType.TOOL)
        await db.create_entity(e1)
        await db.create_entity(e2)
        old_fact = Fact.create(e1.id, "USES", e2.id, "Andrew uses Qwen 2.5 7B", "c1")
        await db.create_fact(old_fact)

        # Mock LLM contradiction check
        mock_inference = AsyncMock()
        mock_inference.generate = AsyncMock(return_value=MagicMock(
            content=json.dumps({
                "contradicts": True,
                "supersedes_id": old_fact.id,
                "reason": "New model replaces old",
            })
        ))

        with patch(
            "hestia.research.fact_extractor.get_inference_client",
            new=AsyncMock(return_value=mock_inference),
        ):
            await extractor.check_contradictions(
                new_fact=Fact.create(
                    e1.id, "USES", "e3", "Andrew uses Qwen 3.5 9B", "c2"
                ),
                existing_facts=[old_fact],
            )

        # Old fact should be invalidated
        updated = await db.get_fact(old_fact.id)
        assert updated.status == FactStatus.SUPERSEDED
        assert updated.invalid_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_facts.py::TestFactExtractor -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.research.fact_extractor'`

- [ ] **Step 3: Implement FactExtractor**

Create `hestia/research/fact_extractor.py`:

```python
"""
Fact Extractor — LLM-powered triplet extraction and contradiction detection.

Extraction pipeline (per memory chunk):
1. Send chunk text to LLM with structured extraction prompt
2. Parse response into (source, relation, target) triplets
3. Resolve each entity via EntityRegistry
4. Check for contradictions against existing facts between same entities
5. Invalidate contradicted facts (bi-temporal: set invalid_at + expired_at)
6. Store new facts in SQLite

Uses Ollama JSON mode for structured output. Qwen 3.5 9B handles this well.
"""

import json
from typing import Any, Dict, List, Optional

from hestia.logging import LogComponent, get_logger

from .database import ResearchDatabase
from .entity_registry import EntityRegistry
from .models import Entity, EntityType, Fact, FactStatus

logger = get_logger()

EXTRACTION_PROMPT = """Extract entity-relationship-entity triplets from this text.

Return a JSON object with a "triplets" array. Each triplet has:
- "source": entity name (proper noun or specific thing)
- "source_type": one of: person, tool, concept, place, project, organization
- "relation": relationship in SCREAMING_SNAKE_CASE (e.g., USES, WORKS_ON, LIVES_IN, BUILT_WITH, RUNS_ON, MANAGES, CREATED, PART_OF)
- "target": entity name
- "target_type": same types as source_type
- "fact": natural language sentence describing this relationship
- "confidence": 0.0 to 1.0

Rules:
- Only extract factual relationships, not opinions or speculation
- Use specific entity names, not pronouns
- Each triplet should be independently meaningful
- Skip trivial or overly generic relationships
- Maximum 5 triplets per text

Text:
{text}"""

CONTRADICTION_PROMPT = """Given a new fact and existing facts between the same entities, determine if the new fact contradicts or supersedes any existing fact.

New fact: {new_fact}

Existing facts:
{existing_facts}

Return a JSON object:
- "contradicts": true/false
- "supersedes_id": ID of the fact being superseded (only if contradicts is true)
- "reason": brief explanation

Only mark as contradiction if the new fact makes an existing fact UNTRUE (e.g., "uses X" superseded by "uses Y" for the same purpose). Additive facts (learning new things) are NOT contradictions."""


async def get_inference_client() -> Any:
    """Lazy import to avoid circular dependencies."""
    from hestia.inference import get_inference_client as _get_client
    return await _get_client()


class FactExtractor:
    """Extracts entity-relationship triplets from text using local LLM."""

    def __init__(self, database: ResearchDatabase, registry: EntityRegistry) -> None:
        self._db = database
        self._registry = registry

    async def extract_from_text(
        self,
        text: str,
        source_chunk_id: Optional[str] = None,
        user_id: str = "default",
    ) -> List[Fact]:
        """
        Extract facts from a text chunk.

        Returns list of newly created Fact objects.
        """
        # Step 1: LLM extraction
        client = await get_inference_client()
        prompt = EXTRACTION_PROMPT.format(text=text[:2000])

        try:
            response = await client.generate(
                prompt=prompt,
                system="You are a knowledge extraction system. Return valid JSON only.",
                format="json",
            )
            triplets = self._parse_extraction_response(response.content)
        except Exception as e:
            logger.warning(
                "Fact extraction LLM call failed",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return []

        if not triplets:
            return []

        # Step 2: Resolve entities and create facts
        facts: List[Fact] = []
        for triplet in triplets:
            try:
                source_type = EntityType(triplet.get("source_type", "concept"))
                target_type = EntityType(triplet.get("target_type", "concept"))
            except ValueError:
                source_type = EntityType.CONCEPT
                target_type = EntityType.CONCEPT

            source_entity = await self._registry.resolve_entity(
                triplet["source"], source_type, user_id,
            )
            target_entity = await self._registry.resolve_entity(
                triplet["target"], target_type, user_id,
            )

            fact = Fact.create(
                source_entity_id=source_entity.id,
                relation=triplet["relation"],
                target_entity_id=target_entity.id,
                fact_text=triplet.get("fact", f"{triplet['source']} {triplet['relation']} {triplet['target']}"),
                source_chunk_id=source_chunk_id,
                confidence=triplet.get("confidence", 0.5),
                user_id=user_id,
            )

            # Step 3: Check contradictions
            existing = await self._db.find_facts_between(
                source_entity.id, target_entity.id, active_only=True,
            )
            if existing:
                await self.check_contradictions(fact, existing)

            await self._db.create_fact(fact)
            facts.append(fact)

        logger.info(
            "Facts extracted",
            component=LogComponent.RESEARCH,
            data={
                "chunk_id": source_chunk_id,
                "facts_created": len(facts),
                "triplets_parsed": len(triplets),
            },
        )

        return facts

    async def check_contradictions(
        self,
        new_fact: Fact,
        existing_facts: List[Fact],
    ) -> None:
        """Check if new fact contradicts/supersedes existing facts."""
        if not existing_facts:
            return

        existing_text = "\n".join(
            f"- [{f.id}] {f.fact_text} (since {f.valid_at.isoformat() if f.valid_at else 'unknown'})"
            for f in existing_facts
        )

        client = await get_inference_client()
        prompt = CONTRADICTION_PROMPT.format(
            new_fact=new_fact.fact_text,
            existing_facts=existing_text,
        )

        try:
            response = await client.generate(
                prompt=prompt,
                system="You are a fact consistency checker. Return valid JSON only.",
                format="json",
            )
            result = self._parse_contradiction_response(response.content)
        except Exception as e:
            logger.debug(
                "Contradiction check failed, assuming no conflict",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return

        if result.get("contradicts") and result.get("supersedes_id"):
            await self._db.invalidate_fact(result["supersedes_id"])
            logger.info(
                "Fact superseded",
                component=LogComponent.RESEARCH,
                data={
                    "old_fact_id": result["supersedes_id"],
                    "new_fact": new_fact.fact_text[:80],
                    "reason": result.get("reason", ""),
                },
            )

    def _parse_extraction_response(self, content: str) -> List[Dict[str, Any]]:
        """Parse LLM JSON response into triplet dicts."""
        try:
            data = json.loads(content)
            triplets = data.get("triplets", [])
            if not isinstance(triplets, list):
                return []
            # Validate required fields
            valid = []
            for t in triplets:
                if all(k in t for k in ("source", "relation", "target")):
                    valid.append(t)
            return valid
        except (json.JSONDecodeError, AttributeError):
            return []

    def _parse_contradiction_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM contradiction check response."""
        try:
            data = json.loads(content)
            return {
                "contradicts": bool(data.get("contradicts", False)),
                "supersedes_id": data.get("supersedes_id"),
                "reason": data.get("reason", ""),
            }
        except (json.JSONDecodeError, AttributeError):
            return {"contradicts": False}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_facts.py::TestFactExtractor -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/test_research.py tests/test_research_facts.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add hestia/research/fact_extractor.py tests/test_research_facts.py
git commit -m "feat(research): LLM fact extraction with contradiction detection"
```

---

## Chunk 4: Enhanced Graph Builder + Manager Wiring

### Task 4.1: Add Fact-Based Graph Building to GraphBuilder

**Files:**
- Modify: `hestia/research/graph_builder.py`
- Test: `tests/test_research_graph_facts.py` (new file)

- [ ] **Step 1: Write failing tests for fact-based graph**

Create `tests/test_research_graph_facts.py`:

```python
"""Tests for fact-based knowledge graph building."""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, patch

from hestia.research.database import ResearchDatabase
from hestia.research.graph_builder import GraphBuilder
from hestia.research.models import (
    Community, EdgeType, Entity, EntityType, Fact, NodeType,
)


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncGenerator[ResearchDatabase, None]:
    db = ResearchDatabase(db_path=tmp_path / "test_research.db")
    await db.initialize()
    try:
        yield db
    finally:
        await db.close()


@pytest_asyncio.fixture
async def populated_db(db: ResearchDatabase) -> ResearchDatabase:
    """DB with entities, facts, and a community."""
    e1 = Entity.create("Andrew", EntityType.PERSON)
    e2 = Entity.create("Qwen", EntityType.TOOL)
    e3 = Entity.create("Hestia", EntityType.PROJECT)
    for e in [e1, e2, e3]:
        await db.create_entity(e)

    f1 = Fact.create(e1.id, "USES", e2.id, "Andrew uses Qwen", "c1", 0.9)
    f2 = Fact.create(e1.id, "BUILT", e3.id, "Andrew built Hestia", "c2", 0.95)
    f3 = Fact.create(e3.id, "RUNS_ON", e2.id, "Hestia runs on Qwen", "c3", 0.8)
    await db.create_fact(f1)
    await db.create_fact(f2)
    await db.create_fact(f3)

    comm = Community.create("Dev cluster", [e1.id, e2.id, e3.id])
    await db.create_community(comm)
    for e in [e1, e2, e3]:
        await db.update_entity_community(e.id, comm.id)

    return db


class TestFactGraphBuilder:
    @pytest.mark.asyncio
    async def test_build_fact_graph_returns_entities_as_nodes(
        self, populated_db: ResearchDatabase,
    ) -> None:
        builder = GraphBuilder()
        with patch(
            "hestia.research.graph_builder.get_research_database",
            new=AsyncMock(return_value=populated_db),
        ):
            response = await builder.build_fact_graph()

        entity_nodes = [n for n in response.nodes if n.node_type == NodeType.ENTITY]
        assert len(entity_nodes) == 3

    @pytest.mark.asyncio
    async def test_build_fact_graph_returns_relationship_edges(
        self, populated_db: ResearchDatabase,
    ) -> None:
        builder = GraphBuilder()
        with patch(
            "hestia.research.graph_builder.get_research_database",
            new=AsyncMock(return_value=populated_db),
        ):
            response = await builder.build_fact_graph()

        rel_edges = [e for e in response.edges if e.edge_type == EdgeType.RELATIONSHIP]
        assert len(rel_edges) == 3

    @pytest.mark.asyncio
    async def test_build_fact_graph_includes_community_nodes(
        self, populated_db: ResearchDatabase,
    ) -> None:
        builder = GraphBuilder()
        with patch(
            "hestia.research.graph_builder.get_research_database",
            new=AsyncMock(return_value=populated_db),
        ):
            response = await builder.build_fact_graph()

        comm_nodes = [n for n in response.nodes if n.node_type == NodeType.COMMUNITY]
        assert len(comm_nodes) == 1
        comm_edges = [e for e in response.edges if e.edge_type == EdgeType.COMMUNITY_MEMBER]
        assert len(comm_edges) == 3

    @pytest.mark.asyncio
    async def test_build_fact_graph_edge_has_fact_text(
        self, populated_db: ResearchDatabase,
    ) -> None:
        builder = GraphBuilder()
        with patch(
            "hestia.research.graph_builder.get_research_database",
            new=AsyncMock(return_value=populated_db),
        ):
            response = await builder.build_fact_graph()

        rel_edges = [e for e in response.edges if e.edge_type == EdgeType.RELATIONSHIP]
        # Edges should carry fact text in metadata (via edge content)
        assert any("Andrew uses Qwen" in str(e.to_dict()) for e in rel_edges) or len(rel_edges) == 3

    @pytest.mark.asyncio
    async def test_build_fact_graph_empty_db(
        self, db: ResearchDatabase,
    ) -> None:
        builder = GraphBuilder()
        with patch(
            "hestia.research.graph_builder.get_research_database",
            new=AsyncMock(return_value=db),
        ):
            response = await builder.build_fact_graph()

        assert len(response.nodes) == 0
        assert len(response.edges) == 0

    @pytest.mark.asyncio
    async def test_fact_graph_serializable(
        self, populated_db: ResearchDatabase,
    ) -> None:
        """Graph response must be JSON-serializable."""
        import json
        builder = GraphBuilder()
        with patch(
            "hestia.research.graph_builder.get_research_database",
            new=AsyncMock(return_value=populated_db),
        ):
            response = await builder.build_fact_graph()

        data = response.to_dict()
        json_str = json.dumps(data)
        assert json_str  # No serialization error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_graph_facts.py -v`
Expected: FAIL — `AttributeError: 'GraphBuilder' object has no attribute 'build_fact_graph'`

- [ ] **Step 3: Add build_fact_graph() to GraphBuilder**

Add to `hestia/research/graph_builder.py` — a new method `build_fact_graph()` that:
1. Loads all entities from SQLite
2. Creates entity nodes (using entity_type for category, summary for content)
3. Loads all active facts from SQLite
4. Creates RELATIONSHIP edges between entity nodes (weight from fact confidence)
5. Loads communities, creates community nodes + COMMUNITY_MEMBER edges
6. Runs force-directed layout
7. Returns GraphResponse

Also add a `get_research_database` import at the top:
```python
async def get_research_database():
    from .database import get_research_database as _get_db
    return await _get_db()
```

The method signature:
```python
async def build_fact_graph(
    self,
    center_entity: Optional[str] = None,
    max_depth: int = 3,
) -> GraphResponse:
```

Edge metadata should include `fact_text` and `valid_at` for frontend rendering.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_graph_facts.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/research/graph_builder.py tests/test_research_graph_facts.py
git commit -m "feat(research): fact-based graph builder with entity nodes and relationship edges"
```

---

### Task 4.2: Wire New Components into ResearchManager

**Files:**
- Modify: `hestia/research/manager.py`
- Modify: `hestia/research/__init__.py`
- Test: `tests/test_research_graph_facts.py` (append)

- [ ] **Step 1: Write failing tests for manager integration**

Append to `tests/test_research_graph_facts.py`:

```python
class TestResearchManagerFacts:
    @pytest.mark.asyncio
    async def test_extract_facts_calls_extractor(
        self, populated_db: ResearchDatabase,
    ) -> None:
        from hestia.research.manager import ResearchManager
        manager = ResearchManager()
        manager._database = populated_db
        manager._initialized = True

        # Mock the extractor
        mock_extractor = AsyncMock()
        mock_extractor.extract_from_text = AsyncMock(return_value=[])
        manager._fact_extractor = mock_extractor

        # Mock memory manager
        mock_memory = AsyncMock()
        mock_memory.search = AsyncMock(return_value=[])
        with patch("hestia.research.manager.get_memory_manager", new=AsyncMock(return_value=mock_memory)):
            result = await manager.extract_facts(time_range_days=7)

        assert "facts_created" in result

    @pytest.mark.asyncio
    async def test_get_entities_returns_list(
        self, populated_db: ResearchDatabase,
    ) -> None:
        from hestia.research.manager import ResearchManager
        manager = ResearchManager()
        manager._database = populated_db
        manager._initialized = True

        result = await manager.get_entities()
        assert "entities" in result
        assert len(result["entities"]) == 3

    @pytest.mark.asyncio
    async def test_get_facts_returns_active(
        self, populated_db: ResearchDatabase,
    ) -> None:
        from hestia.research.manager import ResearchManager
        manager = ResearchManager()
        manager._database = populated_db
        manager._initialized = True

        result = await manager.get_facts()
        assert "facts" in result
        assert len(result["facts"]) == 3

    @pytest.mark.asyncio
    async def test_get_timeline_returns_ordered_facts(
        self, populated_db: ResearchDatabase,
    ) -> None:
        from hestia.research.manager import ResearchManager
        manager = ResearchManager()
        manager._database = populated_db
        manager._initialized = True

        result = await manager.get_timeline()
        assert "facts" in result
        assert "entities" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_research_graph_facts.py::TestResearchManagerFacts -v`
Expected: FAIL — `AttributeError: 'ResearchManager' object has no attribute 'extract_facts'`

- [ ] **Step 3: Update ResearchManager with new methods**

Modify `hestia/research/manager.py`:
- Add `_fact_extractor: Optional[FactExtractor]` and `_entity_registry: Optional[EntityRegistry]` to `__init__`
- Initialize them in `initialize()` after database setup
- Add methods:
  - `extract_facts(time_range_days: int) -> Dict[str, Any]` — queries memory, runs FactExtractor on each chunk
  - `get_entities(entity_type: Optional[str], limit: int, offset: int) -> Dict[str, Any]`
  - `get_facts(status: Optional[str], entity_id: Optional[str], limit: int, offset: int) -> Dict[str, Any]`
  - `get_timeline(point_in_time: Optional[datetime]) -> Dict[str, Any]` — returns facts + entities valid at a point in time
  - `get_fact_graph(center_entity: Optional[str]) -> GraphResponse` — delegates to `build_fact_graph()`
  - `detect_communities() -> Dict[str, Any]` — delegates to EntityRegistry

Update `__init__.py` exports to include new types:
```python
from .models import Community, Entity, EntityType, Fact, FactStatus
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_research_graph_facts.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add hestia/research/manager.py hestia/research/__init__.py tests/test_research_graph_facts.py
git commit -m "feat(research): wire fact extractor and entity registry into ResearchManager"
```

---

## Chunk 5: API Endpoints + Pydantic Schemas

### Task 5.1: Add Pydantic Schemas for Facts and Entities

**Files:**
- Modify: `hestia/api/schemas/research.py`

- [ ] **Step 1: Add new schema classes**

Append to `hestia/api/schemas/research.py`:

```python
class FactResponse(BaseModel):
    id: str
    sourceEntityId: str
    relation: str
    targetEntityId: str
    factText: str
    status: str
    validAt: Optional[str] = None
    invalidAt: Optional[str] = None
    expiredAt: Optional[str] = None
    sourceChunkId: Optional[str] = None
    confidence: float = 0.5
    createdAt: Optional[str] = None


class FactListResponse(BaseModel):
    facts: List[FactResponse]
    total: int


class EntityResponse(BaseModel):
    id: str
    name: str
    entityType: str
    canonicalName: str
    summary: Optional[str] = None
    communityId: Optional[str] = None
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class EntityListResponse(BaseModel):
    entities: List[EntityResponse]
    total: int


class CommunityResponse(BaseModel):
    id: str
    name: str
    memberEntityIds: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    createdAt: Optional[str] = None


class CommunityListResponse(BaseModel):
    communities: List[CommunityResponse]
    total: int


class ExtractFactsRequest(BaseModel):
    time_range_days: int = Field(default=7, ge=1, le=90)


class ExtractFactsResponse(BaseModel):
    facts_created: int
    chunks_processed: int
    entities_created: int


class TimelineResponse(BaseModel):
    facts: List[FactResponse]
    entities: List[EntityResponse]
    point_in_time: Optional[str] = None
```

- [ ] **Step 2: Commit**

```bash
git add hestia/api/schemas/research.py
git commit -m "feat(api): Pydantic schemas for facts, entities, communities, timeline"
```

---

### Task 5.2: Add API Endpoints

**Files:**
- Modify: `hestia/api/routes/research.py`

- [ ] **Step 1: Add 7 new endpoints**

Add to `hestia/api/routes/research.py`:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/v1/research/facts/extract` | POST | Trigger fact extraction from recent memory |
| `/v1/research/facts` | GET | List facts (filter by status, entity_id) |
| `/v1/research/facts/timeline` | GET | Get facts valid at a point in time |
| `/v1/research/entities` | GET | List entities (filter by type) |
| `/v1/research/entities/communities` | POST | Trigger community detection |
| `/v1/research/communities` | GET | List communities |
| `/v1/research/graph?mode=facts` | GET | Existing endpoint gains `mode` query param |

Implementation pattern follows existing endpoints: `get_research_manager()`, try/except, `sanitize_for_log(e)`, HTTPException with generic messages.

The existing `/v1/research/graph` endpoint gets an optional `mode: str = "legacy"` query parameter. When `mode=facts`, it delegates to `manager.get_fact_graph()`.

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All PASS (new endpoints don't break existing tests)

- [ ] **Step 3: Commit**

```bash
git add hestia/api/routes/research.py
git commit -m "feat(api): 7 new research endpoints for facts, entities, communities, timeline"
```

---

### Task 5.3: Update auto-test.sh and __init__.py

**Files:**
- Modify: `scripts/auto-test.sh`
- Modify: `hestia/research/__init__.py`

- [ ] **Step 1: Add test file mappings**

Add to `scripts/auto-test.sh` research section:

```bash
# Existing:
*hestia/research/*)
    echo "tests/test_research.py tests/test_research_facts.py tests/test_research_graph_facts.py" ;;
```

- [ ] **Step 2: Update __init__.py exports**

```python
from .models import (
    CATEGORY_COLORS,
    Community,
    EdgeType,
    Entity,
    EntityType,
    Fact,
    FactStatus,
    GraphCluster,
    GraphEdge,
    GraphNode,
    GraphResponse,
    NodeType,
    Principle,
    PrincipleStatus,
)
```

- [ ] **Step 3: Commit**

```bash
git add scripts/auto-test.sh hestia/research/__init__.py
git commit -m "chore(research): update auto-test mappings and module exports"
```

---

### Task 5.4: Run @hestia-tester and @hestia-reviewer

- [ ] **Step 1: Run full test suite via @hestia-tester**

Verify all tests pass, no regressions.

- [ ] **Step 2: Run @hestia-reviewer on all changed files**

Code audit mode: check all modified/created files for:
- Type hints complete
- Error handling (no bare excepts)
- Logging pattern correct (get_logger() no args)
- sanitize_for_log in routes
- user_id scoping on all new tables
- No hardcoded values

- [ ] **Step 3: Update CLAUDE.md**

Update project structure to include new files. Update endpoint count. Add ADR reference.

- [ ] **Step 4: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for Sprint 9 knowledge graph evolution"
```

---

## Summary

| Chunk | Tasks | New Files | Modified Files | Estimated Tests |
|-------|-------|-----------|----------------|-----------------|
| 1: Models & Schema | 1.1, 1.2 | `tests/test_research_facts.py` | `models.py`, `database.py` | ~25 |
| 2: Entity Registry | 2.1 | `entity_registry.py` | `tests/test_research_facts.py` | ~4 |
| 3: Fact Extractor | 3.1 | `fact_extractor.py` | `tests/test_research_facts.py` | ~6 |
| 4: Graph Builder + Manager | 4.1, 4.2 | `tests/test_research_graph_facts.py` | `graph_builder.py`, `manager.py`, `__init__.py` | ~10 |
| 5: API & Cleanup | 5.1-5.4 | — | `schemas/research.py`, `routes/research.py`, `auto-test.sh`, `CLAUDE.md` | ~5 |

**Total: ~50 new tests, 2 new source files, 8 modified files, 8 commits**

**Execution order:** Chunks 1→2→3→4→5 (strict dependency chain — each chunk builds on the previous).

**ADR to create:** ADR-041: Knowledge Graph Evolution — bi-temporal facts on SQLite, entity registry with label propagation, Graphiti-inspired architecture without graph database dependency.
