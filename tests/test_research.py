"""
Tests for the Research module — models, database, and (later) graph builder + API.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

from hestia.research.models import (
    EdgeType,
    GraphCluster,
    GraphEdge,
    GraphNode,
    GraphResponse,
    NodeType,
    Principle,
    PrincipleStatus,
)
from hestia.research.database import ResearchDatabase


# ── Fixtures ────────────────────────────────────────────


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncGenerator[ResearchDatabase, None]:
    """Create a temporary research database for testing."""
    db_path = tmp_path / "test_research.db"
    database = ResearchDatabase(db_path)
    await database.initialize()
    yield database
    await database.close()


# ── Model Serialization Tests ───────────────────────────


class TestGraphNode:
    def test_to_dict_roundtrip(self) -> None:
        node = GraphNode(
            id="node-1",
            content="Test content",
            node_type=NodeType.MEMORY,
            category="conversation",
            label="Test Node",
            confidence=0.8,
            weight=0.6,
            topics=["python", "testing"],
            entities=["pytest"],
            position={"x": 1.0, "y": 2.0, "z": 3.0},
            last_active=datetime(2026, 3, 3, 12, 0, 0),
            metadata={"source": "chat"},
        )
        d = node.to_dict()
        restored = GraphNode.from_dict(d)

        assert restored.id == node.id
        assert restored.content == node.content
        assert restored.node_type == node.node_type
        assert restored.category == node.category
        assert restored.confidence == node.confidence
        assert restored.weight == node.weight
        assert restored.topics == node.topics
        assert restored.entities == node.entities
        assert restored.position == node.position

    def test_color_from_category(self) -> None:
        node = GraphNode(
            id="n1", content="", node_type=NodeType.MEMORY,
            category="conversation", label="", confidence=0.5, weight=0.5,
        )
        assert node.color == "#5AC8FA"

        node2 = GraphNode(
            id="n2", content="", node_type=NodeType.TOPIC,
            category="topic", label="", confidence=0.5, weight=0.5,
        )
        assert node2.color == "#FFD60A"

    def test_unknown_category_color(self) -> None:
        node = GraphNode(
            id="n1", content="", node_type=NodeType.MEMORY,
            category="unknown_category", label="", confidence=0.5, weight=0.5,
        )
        assert node.color == "#8E8E93"

    def test_radius_calculation(self) -> None:
        low = GraphNode(
            id="n1", content="", node_type=NodeType.MEMORY,
            category="fact", label="", confidence=0.5, weight=0.0,
        )
        assert low.radius == pytest.approx(0.15)

        high = GraphNode(
            id="n2", content="", node_type=NodeType.MEMORY,
            category="fact", label="", confidence=0.5, weight=1.0,
        )
        assert high.radius == pytest.approx(0.30)

    def test_to_dict_keys_camel_case(self) -> None:
        node = GraphNode(
            id="n1", content="c", node_type=NodeType.MEMORY,
            category="fact", label="l", confidence=0.5, weight=0.5,
        )
        d = node.to_dict()
        assert "nodeType" in d
        assert "lastActive" in d
        assert "node_type" not in d


class TestGraphEdge:
    def test_to_dict_roundtrip(self) -> None:
        edge = GraphEdge(
            from_id="a", to_id="b",
            edge_type=EdgeType.SHARED_TOPIC,
            weight=0.75, count=3,
        )
        d = edge.to_dict()
        restored = GraphEdge.from_dict(d)

        assert restored.from_id == "a"
        assert restored.to_id == "b"
        assert restored.weight == 0.75
        assert restored.count == 3

    def test_auto_id(self) -> None:
        edge = GraphEdge(from_id="x", to_id="y", edge_type=EdgeType.SEMANTIC, weight=0.5)
        assert edge.id == "x-y"

    def test_camel_case_keys(self) -> None:
        edge = GraphEdge(from_id="a", to_id="b", edge_type=EdgeType.SEMANTIC, weight=0.5)
        d = edge.to_dict()
        assert "fromId" in d
        assert "toId" in d
        assert "edgeType" in d


class TestGraphCluster:
    def test_to_dict_roundtrip(self) -> None:
        cluster = GraphCluster(id="c1", label="Python", node_ids=["n1", "n2"], color="#FF0000")
        d = cluster.to_dict()
        restored = GraphCluster.from_dict(d)

        assert restored.id == "c1"
        assert restored.label == "Python"
        assert restored.node_ids == ["n1", "n2"]


class TestGraphResponse:
    def test_to_dict_counts(self) -> None:
        node = GraphNode(
            id="n1", content="c", node_type=NodeType.MEMORY,
            category="fact", label="l", confidence=0.5, weight=0.5,
        )
        edge = GraphEdge(from_id="n1", to_id="n2", edge_type=EdgeType.SEMANTIC, weight=0.5)
        cluster = GraphCluster(id="c1", label="test", node_ids=["n1"])

        response = GraphResponse(
            nodes=[node], edges=[edge], clusters=[cluster],
            metadata={"query_time_ms": 42},
        )
        d = response.to_dict()

        assert d["nodeCount"] == 1
        assert d["edgeCount"] == 1
        assert len(d["clusters"]) == 1
        assert d["metadata"]["query_time_ms"] == 42


class TestPrinciple:
    def test_create_factory(self) -> None:
        p = Principle.create(
            content="User prefers concise responses",
            domain="communication",
            confidence=0.7,
            source_chunk_ids=["chunk-1", "chunk-2"],
            topics=["style"],
        )
        assert p.status == PrincipleStatus.PENDING
        assert p.id  # UUID generated
        assert p.created_at is not None
        assert p.content == "User prefers concise responses"
        assert p.domain == "communication"

    def test_to_dict_roundtrip(self) -> None:
        p = Principle.create(content="Test", domain="coding", confidence=0.5)
        d = p.to_dict()
        restored = Principle.from_dict(d)

        assert restored.id == p.id
        assert restored.content == p.content
        assert restored.domain == p.domain
        assert restored.status == PrincipleStatus.PENDING

    def test_default_status_pending(self) -> None:
        p = Principle.from_dict({
            "id": "p1", "content": "test", "domain": "d",
            "confidence": 0.5,
        })
        assert p.status == PrincipleStatus.PENDING


# ── Database Tests ──────────────────────────────────────


class TestResearchDatabaseGraphCache:
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, db: ResearchDatabase) -> None:
        data = {"nodes": [{"id": "n1"}], "edges": []}
        await db.set_cached_graph("test_key", data, ttl_seconds=60)
        result = await db.get_cached_graph("test_key")
        assert result is not None
        assert result["nodes"][0]["id"] == "n1"

    @pytest.mark.asyncio
    async def test_cache_miss(self, db: ResearchDatabase) -> None:
        result = await db.get_cached_graph("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_ttl_expiry(self, db: ResearchDatabase) -> None:
        data = {"nodes": []}
        await db.set_cached_graph("expire_key", data, ttl_seconds=1)

        # Should exist immediately
        result = await db.get_cached_graph("expire_key")
        assert result is not None

        # Wait for expiry
        await asyncio.sleep(1.1)
        result = await db.get_cached_graph("expire_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_overwrite(self, db: ResearchDatabase) -> None:
        await db.set_cached_graph("key", {"v": 1})
        await db.set_cached_graph("key", {"v": 2})
        result = await db.get_cached_graph("key")
        assert result["v"] == 2

    @pytest.mark.asyncio
    async def test_invalidate_specific(self, db: ResearchDatabase) -> None:
        await db.set_cached_graph("a", {"v": 1})
        await db.set_cached_graph("b", {"v": 2})
        await db.invalidate_cache("a")
        assert await db.get_cached_graph("a") is None
        assert await db.get_cached_graph("b") is not None

    @pytest.mark.asyncio
    async def test_invalidate_all(self, db: ResearchDatabase) -> None:
        await db.set_cached_graph("a", {"v": 1})
        await db.set_cached_graph("b", {"v": 2})
        await db.invalidate_cache()
        assert await db.get_cached_graph("a") is None
        assert await db.get_cached_graph("b") is None


class TestResearchDatabasePrinciples:
    @pytest.mark.asyncio
    async def test_create_and_get(self, db: ResearchDatabase) -> None:
        p = Principle.create(content="Test principle", domain="coding", confidence=0.8)
        await db.create_principle(p)
        result = await db.get_principle(p.id)
        assert result is not None
        assert result.content == "Test principle"
        assert result.domain == "coding"
        assert result.status == PrincipleStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, db: ResearchDatabase) -> None:
        result = await db.get_principle("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_principles(self, db: ResearchDatabase) -> None:
        for i in range(5):
            p = Principle.create(content=f"Principle {i}", domain="test")
            await db.create_principle(p)
        results = await db.list_principles()
        assert len(results) == 5

    @pytest.mark.asyncio
    async def test_list_filter_by_status(self, db: ResearchDatabase) -> None:
        p1 = Principle.create(content="Pending one", domain="test")
        p2 = Principle.create(content="Pending two", domain="test")
        await db.create_principle(p1)
        await db.create_principle(p2)
        await db.update_principle_status(p1.id, PrincipleStatus.APPROVED)

        pending = await db.list_principles(status=PrincipleStatus.PENDING)
        approved = await db.list_principles(status=PrincipleStatus.APPROVED)
        assert len(pending) == 1
        assert len(approved) == 1
        assert approved[0].content == "Pending one"

    @pytest.mark.asyncio
    async def test_list_filter_by_domain(self, db: ResearchDatabase) -> None:
        await db.create_principle(Principle.create(content="A", domain="coding"))
        await db.create_principle(Principle.create(content="B", domain="health"))
        results = await db.list_principles(domain="coding")
        assert len(results) == 1
        assert results[0].domain == "coding"

    @pytest.mark.asyncio
    async def test_update_status_approve(self, db: ResearchDatabase) -> None:
        p = Principle.create(content="To approve", domain="test")
        await db.create_principle(p)
        result = await db.update_principle_status(p.id, PrincipleStatus.APPROVED)
        assert result is not None
        assert result.status == PrincipleStatus.APPROVED
        assert result.validation_count == 1

    @pytest.mark.asyncio
    async def test_update_status_reject(self, db: ResearchDatabase) -> None:
        p = Principle.create(content="To reject", domain="test")
        await db.create_principle(p)
        result = await db.update_principle_status(p.id, PrincipleStatus.REJECTED)
        assert result is not None
        assert result.status == PrincipleStatus.REJECTED
        assert result.contradiction_count == 1

    @pytest.mark.asyncio
    async def test_update_content(self, db: ResearchDatabase) -> None:
        p = Principle.create(content="Original", domain="test")
        await db.create_principle(p)
        result = await db.update_principle_content(p.id, "Updated content")
        assert result is not None
        assert result.content == "Updated content"

    @pytest.mark.asyncio
    async def test_delete(self, db: ResearchDatabase) -> None:
        p = Principle.create(content="To delete", domain="test")
        await db.create_principle(p)
        deleted = await db.delete_principle(p.id)
        assert deleted is True
        assert await db.get_principle(p.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db: ResearchDatabase) -> None:
        deleted = await db.delete_principle("no-such-id")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_count_principles(self, db: ResearchDatabase) -> None:
        for i in range(3):
            await db.create_principle(Principle.create(content=f"P{i}", domain="t"))
        total = await db.count_principles()
        assert total == 3

    @pytest.mark.asyncio
    async def test_count_by_status(self, db: ResearchDatabase) -> None:
        p1 = Principle.create(content="A", domain="t")
        p2 = Principle.create(content="B", domain="t")
        await db.create_principle(p1)
        await db.create_principle(p2)
        await db.update_principle_status(p1.id, PrincipleStatus.APPROVED)

        assert await db.count_principles(status=PrincipleStatus.PENDING) == 1
        assert await db.count_principles(status=PrincipleStatus.APPROVED) == 1

    @pytest.mark.asyncio
    async def test_list_pagination(self, db: ResearchDatabase) -> None:
        for i in range(10):
            await db.create_principle(Principle.create(content=f"P{i}", domain="t"))
        page1 = await db.list_principles(limit=5, offset=0)
        page2 = await db.list_principles(limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        # No overlap
        ids1 = {p.id for p in page1}
        ids2 = {p.id for p in page2}
        assert ids1.isdisjoint(ids2)
