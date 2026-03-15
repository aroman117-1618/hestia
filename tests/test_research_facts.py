"""Tests for research knowledge graph models: Fact, Entity, Community."""

from datetime import datetime, timezone, timedelta

import pytest

from hestia.research.models import (
    Community,
    EdgeType,
    Entity,
    EntityType,
    Fact,
    FactStatus,
    NodeType,
)


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
            target_entity_id="ent-2",
            fact_text="Andrew uses Hestia",
        )
        assert fact.id  # auto-generated UUID
        assert fact.source_entity_id == "ent-1"
        assert fact.target_entity_id == "ent-2"
        assert fact.fact_text == "Andrew uses Hestia"
        assert fact.status == FactStatus.ACTIVE
        assert fact.created_at is not None
        assert fact.valid_at is not None
        assert fact.invalid_at is None
        assert fact.expired_at is None
        assert fact.user_id == "default"

    def test_create_with_user_id(self) -> None:
        fact = Fact.create(
            source_entity_id="e1",
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
            target_entity_id="ent-b",
            fact_text="A relates to B",
            weight=0.9,
            status=FactStatus.ACTIVE,
            valid_at=now,
            invalid_at=None,
            expired_at=None,
            created_at=now,
            user_id="user-1",
        )
        d = fact.to_dict()
        assert d["id"] == "fact-1"
        assert d["sourceEntityId"] == "ent-a"
        assert d["targetEntityId"] == "ent-b"
        assert d["factText"] == "A relates to B"
        assert d["weight"] == 0.9
        assert d["status"] == "active"
        assert d["validAt"] == now.isoformat()
        assert d["invalidAt"] is None
        assert d["expiredAt"] is None
        assert d["createdAt"] == now.isoformat()
        assert d["userId"] == "user-1"

    def test_from_dict_roundtrip(self) -> None:
        original = Fact.create(
            source_entity_id="ent-x",
            target_entity_id="ent-y",
            fact_text="X knows Y",
            weight=0.75,
        )
        d = original.to_dict()
        restored = Fact.from_dict(d)
        assert restored.id == original.id
        assert restored.source_entity_id == original.source_entity_id
        assert restored.target_entity_id == original.target_entity_id
        assert restored.fact_text == original.fact_text
        assert restored.weight == original.weight
        assert restored.status == original.status
        assert restored.user_id == original.user_id

    def test_is_valid_at_active(self) -> None:
        fact = Fact.create(
            source_entity_id="a",
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
