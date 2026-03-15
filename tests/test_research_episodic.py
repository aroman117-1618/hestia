"""Tests for episodic memory nodes and temporal fact queries in the knowledge graph."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hestia.research.models import (
    EpisodicNode,
    Entity,
    EntityType,
    Fact,
    FactStatus,
)
from hestia.research.database import ResearchDatabase


# ── EpisodicNode Model Tests ──────────────────────────────


class TestEpisodicNodeModel:
    """Test EpisodicNode dataclass."""

    def test_create_episodic_node(self):
        node = EpisodicNode(
            id="ep-001",
            session_id="sess-abc",
            summary="Discussed home automation with Matter protocol",
            user_id="andrew",
            entity_ids=["ent-001", "ent-002"],
            fact_ids=["fact-001"],
            created_at=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        assert node.id == "ep-001"
        assert node.session_id == "sess-abc"
        assert node.user_id == "andrew"
        assert len(node.entity_ids) == 2
        assert len(node.fact_ids) == 1

    def test_episodic_node_defaults(self):
        node = EpisodicNode(
            id="ep-002",
            session_id="sess-def",
            summary="Quick chat about weather",
        )
        assert node.user_id == "default"
        assert node.entity_ids == []
        assert node.fact_ids == []
        assert node.created_at is not None

    def test_factory_method(self):
        node = EpisodicNode.create(
            session_id="sess-xyz",
            summary="Discussed model routing architecture",
            entity_ids=["ent-hestia", "ent-qwen"],
            user_id="andrew",
        )
        assert node.id  # Auto-generated UUID
        assert node.session_id == "sess-xyz"
        assert node.user_id == "andrew"
        assert len(node.entity_ids) == 2

    def test_to_dict(self):
        node = EpisodicNode.create(
            session_id="sess-1",
            summary="Test summary",
        )
        d = node.to_dict()
        assert d["sessionId"] == "sess-1"
        assert d["summary"] == "Test summary"
        assert "createdAt" in d

    def test_from_dict(self):
        data = {
            "id": "ep-100",
            "sessionId": "sess-100",
            "summary": "Roundtrip test",
            "userId": "andrew",
            "entityIds": ["e1"],
            "factIds": ["f1", "f2"],
            "createdAt": "2026-03-15T12:00:00+00:00",
        }
        node = EpisodicNode.from_dict(data)
        assert node.id == "ep-100"
        assert node.user_id == "andrew"
        assert node.entity_ids == ["e1"]


# ── Episodic Database Tests ───────────────────────────────


class TestEpisodicDatabase:
    """Test episodic node storage and retrieval."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a test research database."""
        db = ResearchDatabase(tmp_path / "test_research.db")
        asyncio.get_event_loop().run_until_complete(db.initialize())
        yield db
        asyncio.get_event_loop().run_until_complete(db.close())

    def test_store_and_retrieve_episodic_node(self, db):
        node = EpisodicNode.create(
            session_id="sess-abc",
            summary="Discussed Hestia architecture decisions",
            entity_ids=["ent-001"],
            fact_ids=["fact-001", "fact-002"],
            user_id="andrew",
        )
        asyncio.get_event_loop().run_until_complete(
            db.store_episodic_node(node)
        )
        result = asyncio.get_event_loop().run_until_complete(
            db.get_episodic_nodes(user_id="andrew", limit=10)
        )
        assert len(result) == 1
        assert result[0].session_id == "sess-abc"
        assert result[0].entity_ids == ["ent-001"]
        assert result[0].fact_ids == ["fact-001", "fact-002"]

    def test_get_episodic_nodes_for_entity(self, db):
        """Find episodes that mention a specific entity."""
        for i in range(3):
            node = EpisodicNode.create(
                session_id=f"sess-{i}",
                summary=f"Episode {i}",
                entity_ids=["ent-shared"] if i < 2 else ["ent-other"],
            )
            asyncio.get_event_loop().run_until_complete(
                db.store_episodic_node(node)
            )
        results = asyncio.get_event_loop().run_until_complete(
            db.get_episodic_nodes_for_entity("ent-shared")
        )
        assert len(results) == 2

    def test_episodic_nodes_ordered_by_created_at(self, db):
        """Nodes returned newest first."""
        for i in range(3):
            node = EpisodicNode(
                id=f"ep-{i}",
                session_id=f"sess-{i}",
                summary=f"Episode {i}",
                created_at=datetime(2026, 1, i + 1, tzinfo=timezone.utc),
            )
            asyncio.get_event_loop().run_until_complete(
                db.store_episodic_node(node)
            )
        results = asyncio.get_event_loop().run_until_complete(
            db.get_episodic_nodes(limit=10)
        )
        assert len(results) == 3
        # Newest first
        assert results[0].id == "ep-2"
        assert results[2].id == "ep-0"


# ── Temporal Fact Query Tests ─────────────────────────────


class TestTemporalFactQueries:
    """Test point-in-time fact retrieval."""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a test research database with entities and facts."""
        db = ResearchDatabase(tmp_path / "test_temporal.db")
        asyncio.get_event_loop().run_until_complete(db.initialize())

        # Create entities
        hestia = Entity.create(name="Hestia", entity_type=EntityType.PROJECT)
        andrew = Entity.create(name="Andrew", entity_type=EntityType.PERSON)
        asyncio.get_event_loop().run_until_complete(db.create_entity(hestia))
        asyncio.get_event_loop().run_until_complete(db.create_entity(andrew))

        # Create facts with temporal bounds
        f1 = Fact.create(
            source_entity_id=hestia.id,
            relation="uses",
            target_entity_id=hestia.id,  # self-ref for simplicity
            fact_text="Hestia uses Mixtral 8x7B",
            confidence=0.9,
            valid_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        f1.invalid_at = datetime(2026, 3, 5, tzinfo=timezone.utc)

        f2 = Fact.create(
            source_entity_id=hestia.id,
            relation="uses",
            target_entity_id=hestia.id,
            fact_text="Hestia uses Qwen 3.5 9B",
            confidence=0.95,
            valid_at=datetime(2026, 3, 5, tzinfo=timezone.utc),
        )

        f3 = Fact.create(
            source_entity_id=andrew.id,
            relation="works_at",
            target_entity_id=andrew.id,
            fact_text="Andrew works at Postman",
            confidence=0.9,
            valid_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )

        for f in [f1, f2, f3]:
            asyncio.get_event_loop().run_until_complete(db.create_fact(f))

        yield db
        asyncio.get_event_loop().run_until_complete(db.close())

    def test_facts_at_january_2026(self, db):
        """In Jan 2026, Hestia used Mixtral, not Qwen."""
        results = asyncio.get_event_loop().run_until_complete(
            db.get_facts_at_time(
                point_in_time=datetime(2026, 1, 15, tzinfo=timezone.utc),
                subject="Hestia",
            )
        )
        texts = [f.fact_text for f in results]
        assert any("Mixtral" in t for t in texts)
        assert not any("Qwen" in t for t in texts)

    def test_facts_at_march_2026(self, db):
        """In Mar 2026, Hestia uses Qwen, Mixtral is expired."""
        results = asyncio.get_event_loop().run_until_complete(
            db.get_facts_at_time(
                point_in_time=datetime(2026, 3, 10, tzinfo=timezone.utc),
                subject="Hestia",
            )
        )
        texts = [f.fact_text for f in results]
        assert any("Qwen" in t for t in texts)
        assert not any("Mixtral" in t for t in texts)

    def test_all_facts_at_time(self, db):
        """Without subject filter, returns all valid facts."""
        results = asyncio.get_event_loop().run_until_complete(
            db.get_facts_at_time(
                point_in_time=datetime(2026, 3, 10, tzinfo=timezone.utc),
            )
        )
        # Should have Qwen fact + Andrew works_at
        assert len(results) >= 2
