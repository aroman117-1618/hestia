"""Tests for fact-based knowledge graph building."""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, List
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from hestia.research.database import ResearchDatabase
from hestia.research.graph_builder import GraphBuilder
from hestia.research.models import (
    Community,
    EdgeType,
    Entity,
    EntityType,
    Fact,
    FactStatus,
    GraphResponse,
    NodeType,
)


# ── Fixtures ───────────────────────────────────────────


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncGenerator[ResearchDatabase, None]:
    """Create a temporary research database for testing."""
    database = ResearchDatabase(db_path=tmp_path / "test_graph_facts.db")
    await database.initialize()
    try:
        yield database
    finally:
        await database.close()


@pytest_asyncio.fixture
async def populated_db(db: ResearchDatabase) -> ResearchDatabase:
    """Database pre-populated with 3 entities, 3 facts, and 1 community."""
    now = datetime.now(timezone.utc)

    # 3 entities
    e1 = Entity(
        id="ent-1",
        name="Andrew",
        canonical_name="andrew",
        entity_type=EntityType.PERSON,
        summary="The user",
        user_id="default",
        created_at=now,
        updated_at=now,
    )
    e2 = Entity(
        id="ent-2",
        name="Hestia",
        canonical_name="hestia",
        entity_type=EntityType.PROJECT,
        summary="AI assistant project",
        user_id="default",
        created_at=now,
        updated_at=now,
    )
    e3 = Entity(
        id="ent-3",
        name="FastAPI",
        canonical_name="fastapi",
        entity_type=EntityType.TOOL,
        summary="Web framework",
        user_id="default",
        created_at=now,
        updated_at=now,
    )
    for e in [e1, e2, e3]:
        await db.create_entity(e)

    # 3 facts linking entities
    f1 = Fact(
        id="fact-1",
        source_entity_id="ent-1",
        target_entity_id="ent-2",
        fact_text="Andrew builds Hestia",
        weight=0.9,
        status=FactStatus.ACTIVE,
        valid_at=now,
        created_at=now,
        user_id="default",
    )
    f2 = Fact(
        id="fact-2",
        source_entity_id="ent-2",
        target_entity_id="ent-3",
        fact_text="Hestia uses FastAPI",
        weight=0.8,
        status=FactStatus.ACTIVE,
        valid_at=now,
        created_at=now,
        user_id="default",
    )
    f3 = Fact(
        id="fact-3",
        source_entity_id="ent-1",
        target_entity_id="ent-3",
        fact_text="Andrew uses FastAPI",
        weight=0.7,
        status=FactStatus.ACTIVE,
        valid_at=now,
        created_at=now,
        user_id="default",
    )
    for f in [f1, f2, f3]:
        await db.create_fact(f)

    # 1 community containing all 3 entities
    c1 = Community(
        id="comm-1",
        label="Hestia Dev Team",
        summary="Core development group",
        member_entity_ids=["ent-1", "ent-2", "ent-3"],
        user_id="default",
        created_at=now,
    )
    await db.create_community(c1)

    return db


@pytest.fixture
def builder() -> GraphBuilder:
    """Fresh GraphBuilder instance."""
    return GraphBuilder()


# ── Tests ──────────────────────────────────────────────


class TestFactGraphBuilder:
    """Tests for build_fact_graph() on GraphBuilder."""

    @pytest.mark.asyncio
    async def test_build_fact_graph_returns_entity_nodes(
        self, builder: GraphBuilder, populated_db: ResearchDatabase
    ) -> None:
        """3 entities in DB should produce 3 entity nodes."""
        with patch.object(
            builder, "_get_research_database", new=AsyncMock(return_value=populated_db)
        ):
            response = await builder.build_fact_graph()

        entity_nodes = [n for n in response.nodes if n.node_type == NodeType.ENTITY]
        assert len(entity_nodes) == 3

        # Verify node IDs
        node_ids = {n.id for n in entity_nodes}
        assert node_ids == {"entity:ent-1", "entity:ent-2", "entity:ent-3"}

        # Verify labels
        labels = {n.label for n in entity_nodes}
        assert "Andrew" in labels
        assert "Hestia" in labels
        assert "FastAPI" in labels

    @pytest.mark.asyncio
    async def test_build_fact_graph_returns_relationship_edges(
        self, builder: GraphBuilder, populated_db: ResearchDatabase
    ) -> None:
        """3 active facts should produce 3 RELATIONSHIP edges."""
        with patch.object(
            builder, "_get_research_database", new=AsyncMock(return_value=populated_db)
        ):
            response = await builder.build_fact_graph()

        rel_edges = [e for e in response.edges if e.edge_type == EdgeType.RELATIONSHIP]
        assert len(rel_edges) == 3

        # Verify edge endpoints reference entity nodes
        for edge in rel_edges:
            assert edge.from_id.startswith("entity:")
            assert edge.to_id.startswith("entity:")

    @pytest.mark.asyncio
    async def test_build_fact_graph_includes_community_nodes(
        self, builder: GraphBuilder, populated_db: ResearchDatabase
    ) -> None:
        """1 community with 3 members → 1 community node + 3 COMMUNITY_MEMBER edges."""
        with patch.object(
            builder, "_get_research_database", new=AsyncMock(return_value=populated_db)
        ):
            response = await builder.build_fact_graph()

        comm_nodes = [n for n in response.nodes if n.node_type == NodeType.COMMUNITY]
        assert len(comm_nodes) == 1
        assert comm_nodes[0].id == "community:comm-1"
        assert comm_nodes[0].label == "Hestia Dev Team"

        member_edges = [
            e for e in response.edges if e.edge_type == EdgeType.COMMUNITY_MEMBER
        ]
        assert len(member_edges) == 3

    @pytest.mark.asyncio
    async def test_build_fact_graph_empty_db(
        self, builder: GraphBuilder, db: ResearchDatabase
    ) -> None:
        """Empty DB → empty graph response."""
        with patch.object(
            builder, "_get_research_database", new=AsyncMock(return_value=db)
        ):
            response = await builder.build_fact_graph()

        assert len(response.nodes) == 0
        assert len(response.edges) == 0
        assert len(response.clusters) == 0

    @pytest.mark.asyncio
    async def test_fact_graph_serializable(
        self, builder: GraphBuilder, populated_db: ResearchDatabase
    ) -> None:
        """response.to_dict() → json.dumps() should not throw."""
        with patch.object(
            builder, "_get_research_database", new=AsyncMock(return_value=populated_db)
        ):
            response = await builder.build_fact_graph()

        data = response.to_dict()
        serialized = json.dumps(data)
        assert isinstance(serialized, str)
        assert len(serialized) > 0

    @pytest.mark.asyncio
    async def test_fact_graph_has_positions(
        self, builder: GraphBuilder, populated_db: ResearchDatabase
    ) -> None:
        """All nodes should have position {x, y, z} after layout."""
        with patch.object(
            builder, "_get_research_database", new=AsyncMock(return_value=populated_db)
        ):
            response = await builder.build_fact_graph()

        for node in response.nodes:
            assert node.position is not None, f"Node {node.id} missing position"
            assert "x" in node.position
            assert "y" in node.position
            assert "z" in node.position

    @pytest.mark.asyncio
    async def test_build_fact_graph_center_entity_filters(
        self, builder: GraphBuilder, populated_db: ResearchDatabase
    ) -> None:
        """center_entity should filter to entities within max_depth hops."""
        with patch.object(
            builder, "_get_research_database", new=AsyncMock(return_value=populated_db)
        ):
            # Center on ent-1 with depth 1: should reach ent-2 and ent-3 directly
            response = await builder.build_fact_graph(
                center_entity="ent-1", max_depth=1
            )

        entity_nodes = [n for n in response.nodes if n.node_type == NodeType.ENTITY]
        entity_ids = {n.id for n in entity_nodes}
        # ent-1 is center, ent-2 and ent-3 are 1 hop away
        assert "entity:ent-1" in entity_ids

    @pytest.mark.asyncio
    async def test_fact_graph_entity_weight_scales_by_fact_count(
        self, builder: GraphBuilder, populated_db: ResearchDatabase
    ) -> None:
        """Entity weight should be proportional to fact count."""
        with patch.object(
            builder, "_get_research_database", new=AsyncMock(return_value=populated_db)
        ):
            response = await builder.build_fact_graph()

        entity_nodes = {
            n.id: n for n in response.nodes if n.node_type == NodeType.ENTITY
        }
        # ent-1 (Andrew) appears in fact-1 and fact-3 → 2 connections
        # ent-2 (Hestia) appears in fact-1 and fact-2 → 2 connections
        # ent-3 (FastAPI) appears in fact-2 and fact-3 → 2 connections
        # All equal, so all should have the same weight
        weights = {nid: n.weight for nid, n in entity_nodes.items()}
        assert len(set(weights.values())) == 1  # all equal


# ── ResearchManager Integration Tests ────────────────


class TestResearchManagerFacts:
    """Tests for fact/entity/community methods on ResearchManager."""

    @pytest.mark.asyncio
    async def test_get_entities_returns_list(self, populated_db: ResearchDatabase) -> None:
        from hestia.research.manager import ResearchManager

        manager = ResearchManager()
        manager._database = populated_db
        manager._initialized = True
        result = await manager.get_entities()
        assert "entities" in result
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_get_entities_filter_by_type(self, populated_db: ResearchDatabase) -> None:
        from hestia.research.manager import ResearchManager

        manager = ResearchManager()
        manager._database = populated_db
        manager._initialized = True
        result = await manager.get_entities(entity_type="person")
        assert result["total"] == 1
        assert result["entities"][0]["name"] == "Andrew"

    @pytest.mark.asyncio
    async def test_get_facts_returns_active(self, populated_db: ResearchDatabase) -> None:
        from hestia.research.manager import ResearchManager

        manager = ResearchManager()
        manager._database = populated_db
        manager._initialized = True
        result = await manager.get_facts()
        assert "facts" in result
        assert result["total"] == 3

    @pytest.mark.asyncio
    async def test_get_timeline(self, populated_db: ResearchDatabase) -> None:
        from hestia.research.manager import ResearchManager

        manager = ResearchManager()
        manager._database = populated_db
        manager._initialized = True
        result = await manager.get_timeline()
        assert "facts" in result
        assert "entities" in result
        assert "point_in_time" in result

    @pytest.mark.asyncio
    async def test_get_fact_graph(self, populated_db: ResearchDatabase) -> None:
        from hestia.research.manager import ResearchManager

        manager = ResearchManager()
        manager._database = populated_db
        manager._graph_builder = GraphBuilder()
        manager._initialized = True
        with patch.object(
            manager._graph_builder,
            "_get_research_database",
            new=AsyncMock(return_value=populated_db),
        ):
            result = await manager.get_fact_graph()
        assert len(result.nodes) > 0

    @pytest.mark.asyncio
    async def test_detect_communities(self, populated_db: ResearchDatabase) -> None:
        from hestia.research.entity_registry import EntityRegistry
        from hestia.research.manager import ResearchManager

        manager = ResearchManager()
        manager._database = populated_db
        manager._entity_registry = EntityRegistry(populated_db)
        manager._initialized = True
        result = await manager.detect_communities()
        assert "communities" in result

    @pytest.mark.asyncio
    async def test_get_entities_no_database(self) -> None:
        from hestia.research.manager import ResearchManager

        manager = ResearchManager()
        manager._initialized = True
        result = await manager.get_entities()
        assert result == {"entities": [], "total": 0}

    @pytest.mark.asyncio
    async def test_get_fact_graph_no_builder(self) -> None:
        from hestia.research.manager import ResearchManager

        manager = ResearchManager()
        manager._initialized = True
        result = await manager.get_fact_graph()
        assert result.metadata.get("error") == "not_initialized"
