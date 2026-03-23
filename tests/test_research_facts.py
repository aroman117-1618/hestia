"""Tests for research knowledge graph models and database: Fact, Entity, Community."""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from hestia.research.database import ResearchDatabase
from hestia.research.models import (
    Community,
    EdgeType,
    Entity,
    EntityType,
    Fact,
    FactStatus,
    NodeType,
)


# ── Database Fixture ────────────────────────────────────


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncGenerator[ResearchDatabase, None]:
    """Create a temporary research database for testing."""
    database = ResearchDatabase(db_path=tmp_path / "test_research.db")
    await database.initialize()
    try:
        yield database
    finally:
        await database.close()


class TestEntityType:
    """Verify EntityType enum values."""

    def test_person(self) -> None:
        assert EntityType.PERSON.value == "person"

    def test_tool(self) -> None:
        assert EntityType.TOOL.value == "tool"

    def test_concept(self) -> None:
        assert EntityType.CONCEPT.value == "concept"

    def test_place(self) -> None:
        assert EntityType.PLACE.value == "place"

    def test_project(self) -> None:
        assert EntityType.PROJECT.value == "project"

    def test_organization(self) -> None:
        assert EntityType.ORGANIZATION.value == "organization"

    def test_all_values(self) -> None:
        expected = {"person", "tool", "concept", "place", "project", "organization"}
        assert {e.value for e in EntityType} == expected


class TestFactStatus:
    """Verify FactStatus enum values."""

    def test_active(self) -> None:
        assert FactStatus.ACTIVE.value == "active"

    def test_superseded(self) -> None:
        assert FactStatus.SUPERSEDED.value == "superseded"

    def test_retracted(self) -> None:
        assert FactStatus.RETRACTED.value == "retracted"


class TestExtendedEnums:
    """Verify new members added to existing enums."""

    def test_node_type_fact(self) -> None:
        assert NodeType.FACT.value == "fact"

    def test_node_type_community(self) -> None:
        assert NodeType.COMMUNITY.value == "community"

    def test_edge_type_relationship(self) -> None:
        assert EdgeType.RELATIONSHIP.value == "relationship"

    def test_edge_type_supersedes(self) -> None:
        assert EdgeType.SUPERSEDES.value == "supersedes"

    def test_edge_type_community_member(self) -> None:
        assert EdgeType.COMMUNITY_MEMBER.value == "community_member"


class TestFact:
    """Tests for the Fact dataclass."""

    def test_create_factory(self) -> None:
        fact = Fact.create(
            source_entity_id="ent-1",
            relation="USES",
            target_entity_id="ent-2",
            fact_text="Andrew uses Hestia",
        )
        assert fact.id  # auto-generated UUID
        assert fact.source_entity_id == "ent-1"
        assert fact.relation == "USES"
        assert fact.target_entity_id == "ent-2"
        assert fact.fact_text == "Andrew uses Hestia"
        assert fact.status == FactStatus.ACTIVE
        assert fact.confidence == 0.5
        assert fact.source_chunk_id is None
        assert fact.created_at is not None
        assert fact.valid_at is not None
        assert fact.invalid_at is None
        assert fact.expired_at is None
        assert fact.user_id == "default"

    def test_create_with_user_id(self) -> None:
        fact = Fact.create(
            source_entity_id="e1",
            relation="RELATED_TO",
            target_entity_id="e2",
            fact_text="test",
            user_id="user-42",
        )
        assert fact.user_id == "user-42"

    def test_to_dict_camel_case(self) -> None:
        now = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
        fact = Fact(
            id="fact-1",
            source_entity_id="ent-a",
            relation="RELATES_TO",
            target_entity_id="ent-b",
            fact_text="A relates to B",
            confidence=0.9,
            status=FactStatus.ACTIVE,
            valid_at=now,
            invalid_at=None,
            expired_at=None,
            source_chunk_id="chunk-99",
            created_at=now,
            user_id="user-1",
        )
        d = fact.to_dict()
        assert d["id"] == "fact-1"
        assert d["sourceEntityId"] == "ent-a"
        assert d["relation"] == "RELATES_TO"
        assert d["targetEntityId"] == "ent-b"
        assert d["factText"] == "A relates to B"
        assert d["confidence"] == 0.9
        assert d["sourceChunkId"] == "chunk-99"
        assert d["status"] == "active"
        assert d["validAt"] == now.isoformat()
        assert d["invalidAt"] is None
        assert d["expiredAt"] is None
        assert d["createdAt"] == now.isoformat()

    def test_from_dict_roundtrip(self) -> None:
        original = Fact.create(
            source_entity_id="ent-x",
            relation="KNOWS",
            target_entity_id="ent-y",
            fact_text="X knows Y",
            confidence=0.75,
        )
        d = original.to_dict()
        restored = Fact.from_dict(d)
        assert restored.id == original.id
        assert restored.source_entity_id == original.source_entity_id
        assert restored.relation == original.relation
        assert restored.target_entity_id == original.target_entity_id
        assert restored.fact_text == original.fact_text
        assert restored.confidence == original.confidence
        assert restored.status == original.status

    def test_is_valid_at_active(self) -> None:
        fact = Fact.create(
            source_entity_id="a",
            relation="RELATED_TO",
            target_entity_id="b",
            fact_text="active fact",
        )
        # Check at a time after valid_at (no invalid_at set)
        check_time = fact.valid_at + timedelta(seconds=1)
        assert fact.is_valid_at(check_time) is True

    def test_is_valid_at_before_valid(self) -> None:
        valid_time = datetime(2026, 6, 1, tzinfo=timezone.utc)
        fact = Fact.create(
            source_entity_id="a",
            relation="RELATED_TO",
            target_entity_id="b",
            fact_text="future fact",
        )
        # Override valid_at to a future date
        fact.valid_at = valid_time
        check_time = datetime(2026, 5, 1, tzinfo=timezone.utc)
        assert fact.is_valid_at(check_time) is False

    def test_is_valid_at_after_invalid(self) -> None:
        valid_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        invalid_time = datetime(2026, 3, 1, tzinfo=timezone.utc)
        fact = Fact.create(
            source_entity_id="a",
            relation="RELATED_TO",
            target_entity_id="b",
            fact_text="expired fact",
        )
        fact.valid_at = valid_time
        fact.invalid_at = invalid_time
        # Check a time after invalid_at
        check_time = datetime(2026, 4, 1, tzinfo=timezone.utc)
        assert fact.is_valid_at(check_time) is False
        # Check a time between valid and invalid
        check_time_between = datetime(2026, 2, 1, tzinfo=timezone.utc)
        assert fact.is_valid_at(check_time_between) is True


class TestEntity:
    """Tests for the Entity dataclass."""

    def test_create_factory(self) -> None:
        entity = Entity.create(
            name="Andrew Lonati",
            entity_type=EntityType.PERSON,
        )
        assert entity.id  # auto-generated UUID
        assert entity.name == "Andrew Lonati"
        assert entity.canonical_name == "andrew lonati"
        assert entity.entity_type == EntityType.PERSON
        assert entity.summary is None
        assert entity.community_id is None
        assert entity.created_at is not None
        assert entity.user_id == "default"

    def test_create_with_user_id(self) -> None:
        entity = Entity.create(
            name="Hestia",
            entity_type=EntityType.PROJECT,
            user_id="user-99",
        )
        assert entity.user_id == "user-99"

    def test_canonical_name_lowercase(self) -> None:
        entity = Entity.create(
            name="Claude Code",
            entity_type=EntityType.TOOL,
        )
        assert entity.canonical_name == "claude code"

    def test_to_dict_camel_case(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=timezone.utc)
        entity = Entity(
            id="ent-1",
            name="FastAPI",
            canonical_name="fastapi",
            entity_type=EntityType.TOOL,
            summary="Web framework",
            community_id="comm-1",
            created_at=now,
            updated_at=now,
            user_id="user-1",
        )
        d = entity.to_dict()
        assert d["id"] == "ent-1"
        assert d["name"] == "FastAPI"
        assert d["canonicalName"] == "fastapi"
        assert d["entityType"] == "tool"
        assert d["summary"] == "Web framework"
        assert d["communityId"] == "comm-1"
        assert d["createdAt"] == now.isoformat()
        assert d["updatedAt"] == now.isoformat()
        assert d["userId"] == "user-1"

    def test_from_dict_roundtrip(self) -> None:
        original = Entity.create(
            name="Python",
            entity_type=EntityType.TOOL,
            summary="Programming language",
        )
        d = original.to_dict()
        restored = Entity.from_dict(d)
        assert restored.id == original.id
        assert restored.name == original.name
        assert restored.canonical_name == original.canonical_name
        assert restored.entity_type == original.entity_type
        assert restored.summary == original.summary
        assert restored.user_id == original.user_id


class TestCommunity:
    """Tests for the Community dataclass."""

    def test_create_factory(self) -> None:
        community = Community.create(
            label="Development Tools",
            member_entity_ids=["ent-1", "ent-2"],
        )
        assert community.id  # auto-generated UUID
        assert community.label == "Development Tools"
        assert community.member_entity_ids == ["ent-1", "ent-2"]
        assert community.summary is None
        assert community.created_at is not None
        assert community.user_id == "default"

    def test_create_with_user_id(self) -> None:
        community = Community.create(
            label="Test",
            user_id="user-7",
        )
        assert community.user_id == "user-7"

    def test_to_dict_camel_case(self) -> None:
        now = datetime(2026, 3, 15, tzinfo=timezone.utc)
        community = Community(
            id="comm-1",
            label="AI Tools",
            summary="Tools for AI development",
            member_entity_ids=["e1", "e2", "e3"],
            created_at=now,
            updated_at=now,
            user_id="user-1",
        )
        d = community.to_dict()
        assert d["id"] == "comm-1"
        assert d["label"] == "AI Tools"
        assert d["summary"] == "Tools for AI development"
        assert d["memberEntityIds"] == ["e1", "e2", "e3"]
        assert d["createdAt"] == now.isoformat()
        assert d["updatedAt"] == now.isoformat()
        assert d["userId"] == "user-1"

    def test_from_dict_roundtrip(self) -> None:
        original = Community.create(
            label="Backend Stack",
            member_entity_ids=["ent-a", "ent-b"],
            summary="Core backend technologies",
        )
        d = original.to_dict()
        restored = Community.from_dict(d)
        assert restored.id == original.id
        assert restored.label == original.label
        assert restored.summary == original.summary
        assert restored.member_entity_ids == original.member_entity_ids
        assert restored.user_id == original.user_id


# ── Database Tests ──────────────────────────────────────


@pytest.mark.asyncio
class TestEntitiesDatabase:
    """Database CRUD tests for entities table."""

    async def test_create_and_get(self, db: ResearchDatabase) -> None:
        entity = Entity.create(
            name="FastAPI",
            entity_type=EntityType.TOOL,
            summary="Web framework",
        )
        created = await db.create_entity(entity)
        assert created.id == entity.id

        fetched = await db.get_entity(entity.id)
        assert fetched is not None
        assert fetched.name == "FastAPI"
        assert fetched.entity_type == EntityType.TOOL
        assert fetched.summary == "Web framework"
        assert fetched.canonical_name == "fastapi"
        assert fetched.user_id == "default"

    async def test_get_nonexistent(self, db: ResearchDatabase) -> None:
        result = await db.get_entity("no-such-id")
        assert result is None

    async def test_find_by_canonical_name(self, db: ResearchDatabase) -> None:
        entity = Entity.create(name="Claude Code", entity_type=EntityType.TOOL)
        await db.create_entity(entity)

        found = await db.find_entity_by_name("claude code")
        assert found is not None
        assert found.id == entity.id

    async def test_find_by_canonical_name_not_found(self, db: ResearchDatabase) -> None:
        result = await db.find_entity_by_name("nonexistent")
        assert result is None

    async def test_list_all(self, db: ResearchDatabase) -> None:
        e1 = Entity.create(name="Python", entity_type=EntityType.TOOL)
        e2 = Entity.create(name="Andrew", entity_type=EntityType.PERSON)
        await db.create_entity(e1)
        await db.create_entity(e2)

        entities = await db.list_entities()
        assert len(entities) == 2

    async def test_list_by_type(self, db: ResearchDatabase) -> None:
        e1 = Entity.create(name="Python", entity_type=EntityType.TOOL)
        e2 = Entity.create(name="Andrew", entity_type=EntityType.PERSON)
        e3 = Entity.create(name="Vim", entity_type=EntityType.TOOL)
        await db.create_entity(e1)
        await db.create_entity(e2)
        await db.create_entity(e3)

        tools = await db.list_entities(entity_type=EntityType.TOOL)
        assert len(tools) == 2
        assert all(e.entity_type == EntityType.TOOL for e in tools)

    async def test_update_summary(self, db: ResearchDatabase) -> None:
        entity = Entity.create(name="Hestia", entity_type=EntityType.PROJECT)
        await db.create_entity(entity)

        await db.update_entity_summary(entity.id, "Personal AI assistant")
        updated = await db.get_entity(entity.id)
        assert updated is not None
        assert updated.summary == "Personal AI assistant"

    async def test_update_community(self, db: ResearchDatabase) -> None:
        entity = Entity.create(name="SQLite", entity_type=EntityType.TOOL)
        await db.create_entity(entity)

        await db.update_entity_community(entity.id, "comm-1")
        updated = await db.get_entity(entity.id)
        assert updated is not None
        assert updated.community_id == "comm-1"

    async def test_count_all(self, db: ResearchDatabase) -> None:
        assert await db.count_entities() == 0
        await db.create_entity(Entity.create(name="A", entity_type=EntityType.CONCEPT))
        await db.create_entity(Entity.create(name="B", entity_type=EntityType.TOOL))
        assert await db.count_entities() == 2

    async def test_count_by_type(self, db: ResearchDatabase) -> None:
        await db.create_entity(Entity.create(name="A", entity_type=EntityType.CONCEPT))
        await db.create_entity(Entity.create(name="B", entity_type=EntityType.TOOL))
        await db.create_entity(Entity.create(name="C", entity_type=EntityType.CONCEPT))
        assert await db.count_entities(entity_type=EntityType.CONCEPT) == 2
        assert await db.count_entities(entity_type=EntityType.TOOL) == 1


@pytest.mark.asyncio
class TestFactsDatabase:
    """Database CRUD tests for facts table."""

    async def _make_entities(self, db: ResearchDatabase) -> tuple:
        """Helper to create source and target entities."""
        src = Entity.create(name="Andrew", entity_type=EntityType.PERSON)
        tgt = Entity.create(name="Hestia", entity_type=EntityType.PROJECT)
        await db.create_entity(src)
        await db.create_entity(tgt)
        return src, tgt

    async def test_create_and_get(self, db: ResearchDatabase) -> None:
        src, tgt = await self._make_entities(db)
        fact = Fact.create(
            source_entity_id=src.id,
            relation="BUILDS",
            target_entity_id=tgt.id,
            fact_text="Andrew builds Hestia",
        )
        created = await db.create_fact(fact)
        assert created.id == fact.id

        fetched = await db.get_fact(fact.id)
        assert fetched is not None
        assert fetched.fact_text == "Andrew builds Hestia"
        assert fetched.status == FactStatus.ACTIVE
        assert fetched.source_entity_id == src.id
        assert fetched.target_entity_id == tgt.id
        assert fetched.user_id == "default"

    async def test_get_nonexistent(self, db: ResearchDatabase) -> None:
        result = await db.get_fact("no-such-id")
        assert result is None

    async def test_list_by_status(self, db: ResearchDatabase) -> None:
        src, tgt = await self._make_entities(db)
        f1 = Fact.create(source_entity_id=src.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="fact 1")
        f2 = Fact.create(source_entity_id=src.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="fact 2")
        await db.create_fact(f1)
        await db.create_fact(f2)

        # Both active
        active = await db.list_facts(status=FactStatus.ACTIVE)
        assert len(active) == 2

        # Invalidate one
        await db.invalidate_fact(f1.id)
        active_after = await db.list_facts(status=FactStatus.ACTIVE)
        assert len(active_after) == 1
        superseded = await db.list_facts(status=FactStatus.SUPERSEDED)
        assert len(superseded) == 1

    async def test_list_by_source_entity(self, db: ResearchDatabase) -> None:
        src, tgt = await self._make_entities(db)
        other = Entity.create(name="Other", entity_type=EntityType.CONCEPT)
        await db.create_entity(other)

        f1 = Fact.create(source_entity_id=src.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="fact A")
        f2 = Fact.create(source_entity_id=other.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="fact B")
        await db.create_fact(f1)
        await db.create_fact(f2)

        results = await db.list_facts(source_entity_id=src.id)
        assert len(results) == 1
        assert results[0].fact_text == "fact A"

    async def test_invalidate_fact(self, db: ResearchDatabase) -> None:
        src, tgt = await self._make_entities(db)
        fact = Fact.create(source_entity_id=src.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="old info")
        await db.create_fact(fact)

        result = await db.invalidate_fact(fact.id)
        assert result is not None
        assert result.status == FactStatus.SUPERSEDED
        assert result.invalid_at is not None
        assert result.expired_at is not None

    async def test_invalidate_nonexistent(self, db: ResearchDatabase) -> None:
        result = await db.invalidate_fact("no-such-id")
        assert result is None

    async def test_find_facts_between(self, db: ResearchDatabase) -> None:
        src, tgt = await self._make_entities(db)
        f1 = Fact.create(source_entity_id=src.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="rel 1")
        f2 = Fact.create(source_entity_id=src.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="rel 2")
        await db.create_fact(f1)
        await db.create_fact(f2)

        # Invalidate one
        await db.invalidate_fact(f1.id)

        # active_only=True (default)
        active = await db.find_facts_between(src.id, tgt.id)
        assert len(active) == 1

        # active_only=False
        all_facts = await db.find_facts_between(src.id, tgt.id, active_only=False)
        assert len(all_facts) == 2

    async def test_get_facts_valid_at_bitemporal(self, db: ResearchDatabase) -> None:
        """Bi-temporal query: old superseded fact + current active fact."""
        src, tgt = await self._make_entities(db)

        # Old fact valid from Jan 1 to Feb 1
        old_fact = Fact.create(
            source_entity_id=src.id,
            relation="LEARNING",
            target_entity_id=tgt.id,
            fact_text="Andrew learning Hestia",
        )
        old_fact.valid_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        old_fact.invalid_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        old_fact.status = FactStatus.SUPERSEDED
        await db.create_fact(old_fact)

        # Current fact valid from Feb 1, no end
        new_fact = Fact.create(
            source_entity_id=src.id,
            relation="BUILDS",
            target_entity_id=tgt.id,
            fact_text="Andrew builds Hestia",
        )
        new_fact.valid_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
        await db.create_fact(new_fact)

        # Query at Jan 15 — should get old fact only
        jan_facts = await db.get_facts_valid_at(datetime(2026, 1, 15, tzinfo=timezone.utc))
        assert len(jan_facts) == 1
        assert jan_facts[0].fact_text == "Andrew learning Hestia"

        # Query at Mar 1 — should get new fact only
        mar_facts = await db.get_facts_valid_at(datetime(2026, 3, 1, tzinfo=timezone.utc))
        assert len(mar_facts) == 1
        assert mar_facts[0].fact_text == "Andrew builds Hestia"

        # Query before any facts
        early = await db.get_facts_valid_at(datetime(2025, 12, 1, tzinfo=timezone.utc))
        assert len(early) == 0

    async def test_count_facts(self, db: ResearchDatabase) -> None:
        src, tgt = await self._make_entities(db)
        assert await db.count_facts() == 0

        f1 = Fact.create(source_entity_id=src.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="f1")
        f2 = Fact.create(source_entity_id=src.id, relation="RELATED_TO", target_entity_id=tgt.id, fact_text="f2")
        await db.create_fact(f1)
        await db.create_fact(f2)
        assert await db.count_facts() == 2

        await db.invalidate_fact(f1.id)
        assert await db.count_facts(status=FactStatus.ACTIVE) == 1
        assert await db.count_facts(status=FactStatus.SUPERSEDED) == 1


@pytest.mark.asyncio
class TestCommunitiesDatabase:
    """Database CRUD tests for communities table."""

    async def test_create_and_get(self, db: ResearchDatabase) -> None:
        community = Community.create(
            label="Dev Tools",
            member_entity_ids=["e1", "e2"],
            summary="Development tools cluster",
        )
        created = await db.create_community(community)
        assert created.id == community.id

        fetched = await db.get_community(community.id)
        assert fetched is not None
        assert fetched.label == "Dev Tools"
        assert fetched.member_entity_ids == ["e1", "e2"]
        assert fetched.summary == "Development tools cluster"
        assert fetched.user_id == "default"

    async def test_get_nonexistent(self, db: ResearchDatabase) -> None:
        result = await db.get_community("no-such-id")
        assert result is None

    async def test_list(self, db: ResearchDatabase) -> None:
        c1 = Community.create(label="Group A")
        c2 = Community.create(label="Group B")
        await db.create_community(c1)
        await db.create_community(c2)

        communities = await db.list_communities()
        assert len(communities) == 2

    async def test_update_summary(self, db: ResearchDatabase) -> None:
        community = Community.create(label="AI Stack")
        await db.create_community(community)

        await db.update_community_summary(community.id, "AI and ML tools")
        updated = await db.get_community(community.id)
        assert updated is not None
        assert updated.summary == "AI and ML tools"

    async def test_delete_all(self, db: ResearchDatabase) -> None:
        c1 = Community.create(label="Group A")
        c2 = Community.create(label="Group B")
        await db.create_community(c1)
        await db.create_community(c2)

        assert len(await db.list_communities()) == 2
        await db.delete_all_communities()
        assert len(await db.list_communities()) == 0


# ── Entity Registry Tests ──────────────────────────────


from hestia.research.entity_registry import EntityRegistry


@pytest.mark.asyncio
class TestEntityRegistry:
    """Tests for EntityRegistry resolution and community detection."""

    async def test_resolve_exact_match(self, db: ResearchDatabase) -> None:
        """Resolve an existing entity by exact canonical name."""
        registry = EntityRegistry(db)
        entity = Entity.create(name="Python", entity_type=EntityType.TOOL)
        await db.create_entity(entity)

        resolved = await registry.resolve_entity("Python", EntityType.TOOL)
        assert resolved.id == entity.id
        assert resolved.name == "Python"

    async def test_resolve_creates_new(self, db: ResearchDatabase) -> None:
        """Resolve an unknown name creates a new entity."""
        registry = EntityRegistry(db)

        resolved = await registry.resolve_entity("FastAPI", EntityType.TOOL)
        assert resolved.name == "FastAPI"
        assert resolved.canonical_name == "fastapi"
        assert resolved.entity_type == EntityType.TOOL

        # Verify it's in the database
        fetched = await db.get_entity(resolved.id)
        assert fetched is not None
        assert fetched.name == "FastAPI"

    async def test_resolve_case_insensitive(self, db: ResearchDatabase) -> None:
        """Resolve with different casing returns the same entity."""
        registry = EntityRegistry(db)
        entity = Entity.create(name="Python", entity_type=EntityType.TOOL)
        await db.create_entity(entity)

        resolved = await registry.resolve_entity("python", EntityType.TOOL)
        assert resolved.id == entity.id

    async def test_label_propagation_simple(self, db: ResearchDatabase) -> None:
        """Three entities connected by facts end up in the same community."""
        registry = EntityRegistry(db)

        e1 = Entity.create(name="A", entity_type=EntityType.CONCEPT)
        e2 = Entity.create(name="B", entity_type=EntityType.CONCEPT)
        e3 = Entity.create(name="C", entity_type=EntityType.CONCEPT)
        await db.create_entity(e1)
        await db.create_entity(e2)
        await db.create_entity(e3)

        f1 = Fact.create(source_entity_id=e1.id, relation="RELATED_TO", target_entity_id=e2.id, fact_text="A-B")
        f2 = Fact.create(source_entity_id=e2.id, relation="RELATED_TO", target_entity_id=e3.id, fact_text="B-C")
        await db.create_fact(f1)
        await db.create_fact(f2)

        communities = await registry.detect_communities(min_community_size=2)
        assert len(communities) == 1
        assert len(communities[0].member_entity_ids) == 3

    async def test_label_propagation_disconnected(self, db: ResearchDatabase) -> None:
        """Two separate pairs of entities produce two communities."""
        registry = EntityRegistry(db)

        e1 = Entity.create(name="A", entity_type=EntityType.CONCEPT)
        e2 = Entity.create(name="B", entity_type=EntityType.CONCEPT)
        e3 = Entity.create(name="C", entity_type=EntityType.CONCEPT)
        e4 = Entity.create(name="D", entity_type=EntityType.CONCEPT)
        await db.create_entity(e1)
        await db.create_entity(e2)
        await db.create_entity(e3)
        await db.create_entity(e4)

        f1 = Fact.create(source_entity_id=e1.id, relation="RELATED_TO", target_entity_id=e2.id, fact_text="A-B")
        f2 = Fact.create(source_entity_id=e3.id, relation="RELATED_TO", target_entity_id=e4.id, fact_text="C-D")
        await db.create_fact(f1)
        await db.create_fact(f2)

        communities = await registry.detect_communities(min_community_size=2)
        assert len(communities) == 2
        sizes = sorted([len(c.member_entity_ids) for c in communities])
        assert sizes == [2, 2]

    async def test_label_propagation_empty(self, db: ResearchDatabase) -> None:
        """No facts yields no communities."""
        registry = EntityRegistry(db)

        communities = await registry.detect_communities(min_community_size=2)
        assert communities == []


# ── Fact Extractor Tests ─────────────────────────────────

import json
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.research.fact_extractor import FactExtractor


class TestFactExtractorParsing:
    """Unit tests for FactExtractor response parsing (sync, no DB)."""

    def _make_extractor(self) -> FactExtractor:
        """Create an extractor with dummy deps for parsing tests."""
        return FactExtractor(
            database=MagicMock(),
            registry=MagicMock(),
        )

    def test_parse_extraction_response_valid(self) -> None:
        """Valid JSON with 2 triplets returns 2 dicts."""
        extractor = self._make_extractor()
        content = json.dumps({
            "triplets": [
                {
                    "source": "Andrew",
                    "source_type": "person",
                    "relation": "USES",
                    "target": "Hestia",
                    "target_type": "project",
                    "fact": "Andrew uses Hestia",
                    "confidence": 0.9,
                },
                {
                    "source": "Hestia",
                    "source_type": "project",
                    "relation": "BUILT_WITH",
                    "target": "FastAPI",
                    "target_type": "tool",
                    "fact": "Hestia is built with FastAPI",
                    "confidence": 0.85,
                },
            ]
        })
        result = extractor._parse_extraction_response(content)
        assert len(result) == 2
        assert result[0]["source"] == "Andrew"
        assert result[1]["relation"] == "BUILT_WITH"

    def test_parse_extraction_response_malformed_not_json(self) -> None:
        """Non-JSON string returns empty list."""
        extractor = self._make_extractor()
        assert extractor._parse_extraction_response("not json") == []

    def test_parse_extraction_response_malformed_no_triplets(self) -> None:
        """JSON without 'triplets' key returns empty list."""
        extractor = self._make_extractor()
        assert extractor._parse_extraction_response("{}") == []

    def test_parse_extraction_response_malformed_invalid_triplets(self) -> None:
        """'triplets' not a list returns empty list."""
        extractor = self._make_extractor()
        assert extractor._parse_extraction_response('{"triplets": "invalid"}') == []

    def test_parse_extraction_response_filters_incomplete(self) -> None:
        """Triplets missing required fields are filtered out."""
        extractor = self._make_extractor()
        content = json.dumps({
            "triplets": [
                {"source": "A", "relation": "USES", "target": "B", "fact": "A uses B", "confidence": 0.9},
                {"source": "C"},  # missing relation and target
            ]
        })
        result = extractor._parse_extraction_response(content)
        assert len(result) == 1

    def test_parse_contradiction_response_true(self) -> None:
        """Contradicts=true with supersedes_id parsed correctly."""
        extractor = self._make_extractor()
        content = json.dumps({
            "contradicts": True,
            "supersedes_id": "fact-old-123",
            "reason": "New role replaces old role",
        })
        result = extractor._parse_contradiction_response(content)
        assert result["contradicts"] is True
        assert result["supersedes_id"] == "fact-old-123"
        assert result["reason"] == "New role replaces old role"

    def test_parse_contradiction_response_no_conflict(self) -> None:
        """Contradicts=false parsed correctly."""
        extractor = self._make_extractor()
        content = json.dumps({
            "contradicts": False,
            "reason": "Facts are additive",
        })
        result = extractor._parse_contradiction_response(content)
        assert result["contradicts"] is False

    def test_parse_contradiction_response_malformed(self) -> None:
        """Malformed response returns no-contradiction default."""
        extractor = self._make_extractor()
        result = extractor._parse_contradiction_response("not json")
        assert result["contradicts"] is False


@pytest.mark.asyncio
class TestFactExtractorIntegration:
    """Integration tests for FactExtractor with real DB and mocked LLM."""

    async def test_extract_from_chunk_integration(self, db: ResearchDatabase) -> None:
        """Mock LLM returns structured triplets; verify facts created and entities resolved."""
        registry = EntityRegistry(db)
        extractor = FactExtractor(database=db, registry=registry)

        llm_response = json.dumps({
            "triplets": [
                {
                    "source": "Andrew",
                    "source_type": "person",
                    "relation": "BUILDS",
                    "target": "Hestia",
                    "target_type": "project",
                    "fact": "Andrew builds Hestia",
                    "confidence": 0.95,
                },
                {
                    "source": "Hestia",
                    "source_type": "project",
                    "relation": "USES",
                    "target": "FastAPI",
                    "target_type": "tool",
                    "fact": "Hestia uses FastAPI",
                    "confidence": 0.88,
                },
            ]
        })

        mock_inference = AsyncMock()
        mock_inference.complete = AsyncMock(
            return_value=MagicMock(content=llm_response)
        )

        with patch(
            "hestia.research.fact_extractor._get_inference_client",
            return_value=mock_inference,
        ):
            facts = await extractor.extract_from_text(
                "Andrew builds Hestia using FastAPI for the backend.",
                source_chunk_id="chunk-1",
            )

        assert len(facts) == 2
        assert facts[0].fact_text == "Andrew builds Hestia"
        assert facts[1].fact_text == "Hestia uses FastAPI"

        # Verify entities were created in the DB
        andrew = await db.find_entity_by_name("andrew")
        assert andrew is not None
        assert andrew.entity_type == EntityType.PERSON

        hestia = await db.find_entity_by_name("hestia")
        assert hestia is not None
        assert hestia.entity_type == EntityType.PROJECT

        fastapi = await db.find_entity_by_name("fastapi")
        assert fastapi is not None
        assert fastapi.entity_type == EntityType.TOOL

        # Verify facts stored in DB
        db_facts = await db.list_facts(status=FactStatus.ACTIVE)
        assert len(db_facts) == 2

    async def test_contradiction_detection(self, db: ResearchDatabase) -> None:
        """Existing fact gets invalidated when LLM detects contradiction."""
        registry = EntityRegistry(db)
        extractor = FactExtractor(database=db, registry=registry)

        # Create existing entities and fact
        src = Entity.create(name="Andrew", entity_type=EntityType.PERSON)
        tgt = Entity.create(name="Acme Corp", entity_type=EntityType.ORGANIZATION)
        await db.create_entity(src)
        await db.create_entity(tgt)

        old_fact = Fact.create(
            source_entity_id=src.id,
            relation="WORKS_AT",
            target_entity_id=tgt.id,
            fact_text="Andrew works at Acme Corp",
        )
        await db.create_fact(old_fact)

        # Phase 1: Entity identification
        phase1_response = json.dumps({
            "entities": [
                {"name": "Andrew", "type": "person"},
                {"name": "Acme Corp", "type": "organization"},
            ]
        })

        # Phase 2: Significance filter
        phase2_response = json.dumps({
            "core": ["Andrew", "Acme Corp"],
            "background": [],
        })

        # Phase 3: PRISM triple extraction
        phase3_response = json.dumps({
            "triples": [
                {
                    "source": "Andrew",
                    "source_type": "person",
                    "relation": "LEFT",
                    "target": "Acme Corp",
                    "target_type": "organization",
                    "fact": "Andrew left Acme Corp",
                    "confidence": 0.9,
                    "durability": 2,
                    "temporal_type": "dynamic",
                },
            ]
        })

        contradiction_response = json.dumps({
            "contradicts": True,
            "supersedes_id": old_fact.id,
            "reason": "Leaving contradicts working at",
        })

        mock_inference = AsyncMock()
        # 4 calls: Phase 1 entities, Phase 2 significance, Phase 3 PRISM, contradiction check
        mock_inference.complete = AsyncMock(
            side_effect=[
                MagicMock(content=phase1_response),
                MagicMock(content=phase2_response),
                MagicMock(content=phase3_response),
                MagicMock(content=contradiction_response),
            ]
        )

        with patch(
            "hestia.research.fact_extractor._get_inference_client",
            return_value=mock_inference,
        ):
            facts = await extractor.extract_from_text(
                "Andrew left Acme Corp last month."
            )

        assert len(facts) == 1
        assert facts[0].fact_text == "Andrew left Acme Corp"

        # Verify old fact was invalidated
        old = await db.get_fact(old_fact.id)
        assert old is not None
        assert old.status == FactStatus.SUPERSEDED
        assert old.invalid_at is not None

    async def test_extract_returns_empty_on_llm_failure(self, db: ResearchDatabase) -> None:
        """LLM failure returns empty list, no crash."""
        registry = EntityRegistry(db)
        extractor = FactExtractor(database=db, registry=registry)

        mock_inference = AsyncMock()
        mock_inference.complete = AsyncMock(side_effect=RuntimeError("LLM down"))

        with patch(
            "hestia.research.fact_extractor._get_inference_client",
            return_value=mock_inference,
        ):
            facts = await extractor.extract_from_text("Some text here")

        assert facts == []
