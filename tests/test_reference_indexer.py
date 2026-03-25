"""Tests for the batch entity reference indexer (hestia/research/indexer.py).

Covers:
- index_research_canvas_references: boards with entity nodes create references
- index_workflow_references: workflow nodes containing entity names create references
- run_batch_index: aggregates counts from all indexers
- POST /v1/research/references/reindex endpoint
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from hestia.research.boards import ResearchBoard
from hestia.research.database import ResearchDatabase
from hestia.research.models import Entity, EntityType
from hestia.research.references import EntityReference, ReferenceModule


# =============================================================================
# Fixtures
# =============================================================================


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncGenerator[ResearchDatabase, None]:
    """Temporary research database."""
    database = ResearchDatabase(db_path=tmp_path / "test_indexer.db")
    await database.initialize()
    try:
        yield database
    finally:
        await database.close()


@pytest_asyncio.fixture
async def entity(db: ResearchDatabase) -> Entity:
    """A single entity pre-inserted into the database."""
    now = datetime.now(timezone.utc)
    e = Entity(
        id="entity-pytest-001",
        name="FastAPI",
        entity_type=EntityType.TOOL,
        canonical_name="fastapi",
        user_id="user-test",
        created_at=now,
        updated_at=now,
    )
    await db.create_entity(e)
    return e


@pytest_asyncio.fixture
async def client(tmp_path: Path):
    """Test HTTP client with mocked auth and a real research database."""
    from fastapi import FastAPI
    from hestia.api.routes.research import router
    from hestia.api.middleware.auth import get_device_token

    database = ResearchDatabase(db_path=tmp_path / "test_indexer_api.db")
    await database.initialize()

    manager = MagicMock()
    manager._database = database
    manager._principle_store = None

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_device_token] = lambda: "test-token"

    with patch("hestia.api.routes.research.get_research_manager", return_value=manager):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    await database.close()


# =============================================================================
# Canvas Reference Indexer
# =============================================================================


class TestIndexResearchCanvasReferences:
    @pytest.mark.asyncio
    async def test_board_with_entity_node_creates_reference(
        self, db: ResearchDatabase, entity: Entity
    ) -> None:
        """A board whose layout_json contains an entity node generates a reference."""
        from hestia.research.indexer import index_research_canvas_references

        layout = json.dumps({
            "nodes": [
                {
                    "id": "node-1",
                    "type": "entity",
                    "data": {"entityId": entity.id, "label": entity.name},
                }
            ],
            "edges": [],
        })
        board = ResearchBoard(name="Test Board", layout_json=layout)
        await db.create_board(board)

        count = await index_research_canvas_references(db)
        assert count == 1

        refs = await db.get_entity_references(entity.id)
        assert len(refs) == 1
        assert refs[0].module == ReferenceModule.RESEARCH_CANVAS
        assert refs[0].item_id == board.id
        assert refs[0].context == board.name

    @pytest.mark.asyncio
    async def test_board_with_no_entity_nodes_creates_no_references(
        self, db: ResearchDatabase
    ) -> None:
        """A board with only annotation nodes should not create any references."""
        from hestia.research.indexer import index_research_canvas_references

        layout = json.dumps({
            "nodes": [
                {"id": "ann-1", "type": "annotation", "data": {"text": "hello"}}
            ],
            "edges": [],
        })
        board = ResearchBoard(name="Empty Board", layout_json=layout)
        await db.create_board(board)

        count = await index_research_canvas_references(db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_idempotent_rerun_does_not_double_count(
        self, db: ResearchDatabase, entity: Entity
    ) -> None:
        """Running the indexer twice must not create duplicate references."""
        from hestia.research.indexer import index_research_canvas_references

        layout = json.dumps({
            "nodes": [{"id": "n1", "data": {"entityId": entity.id}}],
            "edges": [],
        })
        board = ResearchBoard(name="Board", layout_json=layout)
        await db.create_board(board)

        await index_research_canvas_references(db)
        await index_research_canvas_references(db)

        refs = await db.get_entity_references(entity.id, module=ReferenceModule.RESEARCH_CANVAS)
        assert len(refs) == 1

    @pytest.mark.asyncio
    async def test_unknown_entity_id_skipped(self, db: ResearchDatabase) -> None:
        """Entity IDs not in the registry are silently ignored."""
        from hestia.research.indexer import index_research_canvas_references

        layout = json.dumps({
            "nodes": [{"id": "n1", "data": {"entityId": "does-not-exist"}}],
            "edges": [],
        })
        board = ResearchBoard(name="Ghost Board", layout_json=layout)
        await db.create_board(board)

        count = await index_research_canvas_references(db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_empty_database_returns_zero(self, db: ResearchDatabase) -> None:
        """No boards → zero references."""
        from hestia.research.indexer import index_research_canvas_references

        count = await index_research_canvas_references(db)
        assert count == 0


# =============================================================================
# Workflow Reference Indexer
# =============================================================================


class TestIndexWorkflowReferences:
    @pytest.mark.asyncio
    async def test_node_mentioning_entity_creates_reference(
        self, db: ResearchDatabase, entity: Entity
    ) -> None:
        """A workflow node whose config contains the entity's canonical_name
        should generate a reference."""
        from hestia.research.indexer import index_workflow_references

        # Build a minimal workflow DB stub
        mock_workflow_db = MagicMock()
        mock_workflow_db.connection = MagicMock()  # truthy

        from hestia.workflows.models import Workflow, WorkflowNode, WorkflowStatus

        wf = Workflow(
            id="wf-001",
            name="My Workflow",
            status=WorkflowStatus.ACTIVE,
        )
        node = WorkflowNode(
            id="node-001",
            workflow_id=wf.id,
            label="Run FastAPI setup",
            config={"prompt": "Bootstrap a fastapi project"},
        )

        mock_workflow_db.list_workflows = AsyncMock(return_value=([wf], 1))
        mock_workflow_db.get_nodes_for_workflow = AsyncMock(return_value=[node])

        count = await index_workflow_references(db, mock_workflow_db)
        assert count == 1

        refs = await db.get_entity_references(entity.id, module=ReferenceModule.WORKFLOW)
        assert len(refs) == 1
        assert refs[0].item_id == wf.id

    @pytest.mark.asyncio
    async def test_node_without_entity_mention_creates_no_reference(
        self, db: ResearchDatabase, entity: Entity
    ) -> None:
        """A node whose config does not mention any entity name creates nothing."""
        from hestia.research.indexer import index_workflow_references
        from hestia.workflows.models import Workflow, WorkflowNode

        wf = Workflow(id="wf-002", name="Unrelated Workflow")
        node = WorkflowNode(
            id="node-002",
            workflow_id=wf.id,
            label="Send email",
            config={"subject": "Hello World"},
        )

        mock_workflow_db = MagicMock()
        mock_workflow_db.connection = MagicMock()
        mock_workflow_db.list_workflows = AsyncMock(return_value=([wf], 1))
        mock_workflow_db.get_nodes_for_workflow = AsyncMock(return_value=[node])

        count = await index_workflow_references(db, mock_workflow_db)
        assert count == 0

    @pytest.mark.asyncio
    async def test_no_entities_returns_zero(self, db: ResearchDatabase) -> None:
        """Empty entity registry → no references regardless of workflow content."""
        from hestia.research.indexer import index_workflow_references
        from hestia.workflows.models import Workflow, WorkflowNode

        wf = Workflow(id="wf-003", name="Some Workflow")
        node = WorkflowNode(
            id="node-003",
            workflow_id=wf.id,
            label="Action",
            config={"prompt": "do something with fastapi"},
        )

        mock_workflow_db = MagicMock()
        mock_workflow_db.connection = MagicMock()
        mock_workflow_db.list_workflows = AsyncMock(return_value=([wf], 1))
        mock_workflow_db.get_nodes_for_workflow = AsyncMock(return_value=[node])

        # Database has no entities — list_entities returns []
        count = await index_workflow_references(db, mock_workflow_db)
        assert count == 0


# =============================================================================
# run_batch_index
# =============================================================================


class TestRunBatchIndex:
    @pytest.mark.asyncio
    async def test_returns_count_dict_with_canvas_key(
        self, db: ResearchDatabase
    ) -> None:
        """run_batch_index without workflow_db returns counts with research_canvas key."""
        from hestia.research.indexer import run_batch_index

        counts = await run_batch_index(db)
        assert "research_canvas" in counts
        assert isinstance(counts["research_canvas"], int)

    @pytest.mark.asyncio
    async def test_returns_workflow_key_when_db_provided(
        self, db: ResearchDatabase
    ) -> None:
        """run_batch_index with workflow_db includes 'workflow' key."""
        from hestia.research.indexer import run_batch_index

        mock_workflow_db = MagicMock()
        mock_workflow_db.connection = MagicMock()
        mock_workflow_db.list_workflows = AsyncMock(return_value=([], 0))
        mock_workflow_db.get_nodes_for_workflow = AsyncMock(return_value=[])

        counts = await run_batch_index(db, workflow_db=mock_workflow_db)
        assert "workflow" in counts
        assert "research_canvas" in counts


# =============================================================================
# Reindex Endpoint
# =============================================================================


class TestReindexEndpoint:
    @pytest.mark.asyncio
    async def test_reindex_returns_200_with_counts(self, client: AsyncClient) -> None:
        """POST /v1/research/references/reindex returns 200 with counts dict."""
        with patch("hestia.research.indexer.run_batch_index", new_callable=AsyncMock) as mock_index:
            mock_index.return_value = {"research_canvas": 0}
            with patch("hestia.workflows.database.get_workflow_database", new_callable=AsyncMock) as mock_wf_db:
                mock_wf_db.return_value = MagicMock()
                response = await client.post("/v1/research/references/reindex")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "counts" in data

    @pytest.mark.asyncio
    async def test_reindex_handles_workflow_db_failure_gracefully(
        self, client: AsyncClient
    ) -> None:
        """If the workflow database is unavailable the endpoint still returns 200."""
        with patch("hestia.research.indexer.run_batch_index", new_callable=AsyncMock) as mock_index:
            mock_index.return_value = {"research_canvas": 0}
            with patch(
                "hestia.workflows.database.get_workflow_database",
                side_effect=RuntimeError("db offline"),
            ):
                response = await client.post("/v1/research/references/reindex")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
