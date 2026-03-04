"""
Tests for the Research module — models, database, graph builder, and API.
"""

import asyncio
import json
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

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


# ── Mock Memory Types ───────────────────────────────────
# Lightweight mocks matching the MemoryManager.search() return contract.


class MockChunkType(Enum):
    CONVERSATION = "conversation"
    FACT = "fact"
    PREFERENCE = "preference"
    RESEARCH = "research"


class MockMemoryScope(Enum):
    SESSION = "session"


@dataclass
class MockChunkTags:
    topics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    people: List[str] = field(default_factory=list)
    mode: Optional[str] = None
    phase: Optional[str] = None
    status: List[str] = field(default_factory=list)
    custom: Dict[str, str] = field(default_factory=dict)


@dataclass
class MockChunkMetadata:
    confidence: float = 0.7


@dataclass
class MockConversationChunk:
    id: str
    session_id: str = "session-1"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    content: str = "Test content"
    chunk_type: MockChunkType = MockChunkType.CONVERSATION
    scope: MockMemoryScope = MockMemoryScope.SESSION
    tags: MockChunkTags = field(default_factory=MockChunkTags)
    metadata: MockChunkMetadata = field(default_factory=MockChunkMetadata)


@dataclass
class MockSearchResult:
    chunk: MockConversationChunk
    relevance_score: float = 0.8
    match_type: str = "semantic"


def _make_results(count: int, topics_per: int = 2, entities_per: int = 1) -> List[MockSearchResult]:
    """Generate mock search results with overlapping topics."""
    topic_pool = ["python", "testing", "security", "api", "database", "memory", "health"]
    entity_pool = ["FastAPI", "ChromaDB", "Ollama", "SQLite", "Keychain"]

    results = []
    for i in range(count):
        topics = [topic_pool[j % len(topic_pool)] for j in range(i, i + topics_per)]
        entities = [entity_pool[j % len(entity_pool)] for j in range(i, i + entities_per)]
        chunk = MockConversationChunk(
            id=f"chunk-{i}",
            content=f"Memory chunk {i} about {', '.join(topics)}",
            chunk_type=MockChunkType(["conversation", "fact", "preference", "research"][i % 4]),
            tags=MockChunkTags(topics=topics, entities=entities),
            metadata=MockChunkMetadata(confidence=0.5 + (i % 5) * 0.1),
        )
        results.append(MockSearchResult(chunk=chunk, relevance_score=0.9 - i * 0.05))
    return results


# ── Graph Builder Tests ─────────────────────────────────


from hestia.research.graph_builder import GraphBuilder


class TestGraphBuilderNodes:
    def test_build_memory_nodes(self) -> None:
        builder = GraphBuilder()
        results = _make_results(5)
        nodes = builder._build_memory_nodes(results)

        assert len(nodes) == 5
        assert all(n.node_type == NodeType.MEMORY for n in nodes)
        assert nodes[0].category == "conversation"
        assert nodes[1].category == "fact"

    def test_build_topic_nodes(self) -> None:
        builder = GraphBuilder()
        results = _make_results(10)
        nodes = builder._build_topic_nodes(results)

        assert len(nodes) > 0
        assert all(n.node_type == NodeType.TOPIC for n in nodes)
        assert all(n.id.startswith("topic:") for n in nodes)

        # Topics should be deduplicated
        labels = [n.label.lower() for n in nodes]
        assert len(labels) == len(set(labels))

    def test_build_entity_nodes(self) -> None:
        builder = GraphBuilder()
        results = _make_results(10)
        nodes = builder._build_entity_nodes(results)

        assert len(nodes) > 0
        assert all(n.node_type == NodeType.ENTITY for n in nodes)
        assert all(n.id.startswith("entity:") for n in nodes)

    def test_empty_results(self) -> None:
        builder = GraphBuilder()
        assert builder._build_memory_nodes([]) == []
        assert builder._build_topic_nodes([]) == []
        assert builder._build_entity_nodes([]) == []


class TestGraphBuilderEdges:
    def test_shared_topic_edges(self) -> None:
        builder = GraphBuilder()
        results = _make_results(5, topics_per=2)
        memory_nodes = builder._build_memory_nodes(results)
        valid_ids = {n.id for n in memory_nodes}
        edges = builder._build_edges(memory_nodes, results, valid_ids)

        # Chunks with overlapping topics should be connected
        shared_edges = [e for e in edges if e.edge_type in (EdgeType.SHARED_TOPIC, EdgeType.SHARED_ENTITY)]
        assert len(shared_edges) > 0

    def test_edge_weight_bounded(self) -> None:
        builder = GraphBuilder()
        results = _make_results(10, topics_per=3)
        memory_nodes = builder._build_memory_nodes(results)
        valid_ids = {n.id for n in memory_nodes}
        edges = builder._build_edges(memory_nodes, results, valid_ids)

        for edge in edges:
            assert 0.0 <= edge.weight <= 1.0

    def test_membership_edges(self) -> None:
        builder = GraphBuilder()
        results = _make_results(5, topics_per=2)
        memory_nodes = builder._build_memory_nodes(results)
        topic_nodes = builder._build_topic_nodes(results)
        all_nodes = memory_nodes + topic_nodes
        valid_ids = {n.id for n in all_nodes}
        edges = builder._build_edges(all_nodes, results, valid_ids)

        membership_edges = [e for e in edges if e.edge_type == EdgeType.TOPIC_MEMBERSHIP]
        assert len(membership_edges) > 0

    def test_no_duplicate_edges(self) -> None:
        builder = GraphBuilder()
        results = _make_results(10, topics_per=3)
        memory_nodes = builder._build_memory_nodes(results)
        valid_ids = {n.id for n in memory_nodes}
        edges = builder._build_edges(memory_nodes, results, valid_ids)

        edge_pairs = [(e.from_id, e.to_id) for e in edges]
        normalized = [(min(a, b), max(a, b)) for a, b in edge_pairs]
        assert len(normalized) == len(set(normalized))

    def test_empty_nodes_no_edges(self) -> None:
        builder = GraphBuilder()
        edges = builder._build_edges([], [], set())
        assert edges == []


class TestGraphBuilderLayout:
    def test_layout_produces_positions(self) -> None:
        builder = GraphBuilder()
        results = _make_results(10)
        nodes = builder._build_memory_nodes(results)
        edges = builder._build_edges(nodes, results, {n.id for n in nodes})
        builder._compute_layout(nodes, edges)

        for node in nodes:
            assert node.position is not None
            assert "x" in node.position
            assert "y" in node.position
            assert "z" in node.position
            # Positions should be finite numbers
            assert math.isfinite(node.position["x"])
            assert math.isfinite(node.position["y"])
            assert math.isfinite(node.position["z"])

    def test_layout_single_node(self) -> None:
        builder = GraphBuilder()
        nodes = [GraphNode(
            id="only", content="alone", node_type=NodeType.MEMORY,
            category="fact", label="alone", confidence=0.5, weight=0.5,
        )]
        builder._compute_layout(nodes, [])
        assert nodes[0].position is not None

    def test_layout_empty(self) -> None:
        builder = GraphBuilder()
        builder._compute_layout([], [])  # Should not raise


class TestGraphBuilderClusters:
    def test_clusters_created(self) -> None:
        builder = GraphBuilder()
        results = _make_results(10, topics_per=2)
        nodes = builder._build_memory_nodes(results)
        clusters = builder._build_clusters(nodes)

        assert len(clusters) > 0
        for cluster in clusters:
            assert len(cluster.node_ids) >= 2

    def test_cluster_labels(self) -> None:
        builder = GraphBuilder()
        results = _make_results(10, topics_per=1)
        nodes = builder._build_memory_nodes(results)
        clusters = builder._build_clusters(nodes)

        for cluster in clusters:
            assert cluster.label
            assert cluster.id.startswith("cluster:")


class TestGraphBuilderIntegration:
    @pytest.mark.asyncio
    async def test_build_graph_with_mock(self) -> None:
        builder = GraphBuilder()
        mock_results = _make_results(20, topics_per=2, entities_per=1)

        mock_mgr = AsyncMock()
        mock_mgr.search = AsyncMock(return_value=mock_results)
        builder._memory_manager = mock_mgr

        response = await builder.build_graph(limit=20)

        assert len(response.nodes) > 0
        assert len(response.edges) > 0
        assert response.metadata["total_chunks"] == 20
        assert response.metadata["query_time_ms"] >= 0

        # All nodes have positions
        for node in response.nodes:
            assert node.position is not None

    @pytest.mark.asyncio
    async def test_build_graph_empty_memory(self) -> None:
        builder = GraphBuilder()
        mock_mgr = AsyncMock()
        mock_mgr.search = AsyncMock(return_value=[])
        builder._memory_manager = mock_mgr

        response = await builder.build_graph()

        assert response.nodes == []
        assert response.edges == []
        assert response.metadata["total_chunks"] == 0

    @pytest.mark.asyncio
    async def test_build_graph_memory_error(self) -> None:
        builder = GraphBuilder()
        mock_mgr = AsyncMock()
        mock_mgr.search = AsyncMock(side_effect=RuntimeError("DB unavailable"))
        builder._memory_manager = mock_mgr

        response = await builder.build_graph()

        assert response.nodes == []
        assert "error" in response.metadata

    @pytest.mark.asyncio
    async def test_build_graph_filter_by_topic(self) -> None:
        builder = GraphBuilder()
        mock_results = _make_results(20, topics_per=2)

        mock_mgr = AsyncMock()
        mock_mgr.search = AsyncMock(return_value=mock_results)
        builder._memory_manager = mock_mgr

        response = await builder.build_graph(center_topic="python")

        # Should have fewer nodes than unfiltered
        assert len(response.nodes) > 0
        # All memory nodes should relate to "python"
        for node in response.nodes:
            if node.node_type == NodeType.MEMORY:
                assert "python" in [t.lower() for t in node.topics] or "python" in node.content.lower()

    @pytest.mark.asyncio
    async def test_build_graph_serializable(self) -> None:
        builder = GraphBuilder()
        mock_results = _make_results(10)

        mock_mgr = AsyncMock()
        mock_mgr.search = AsyncMock(return_value=mock_results)
        builder._memory_manager = mock_mgr

        response = await builder.build_graph()
        d = response.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(d)
        assert json_str
        parsed = json.loads(json_str)
        assert parsed["nodeCount"] == len(response.nodes)
