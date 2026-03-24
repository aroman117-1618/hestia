"""Tests for workflow API routes — endpoint coverage, auth, validation."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from hestia.workflows.database import WorkflowDatabase
from hestia.workflows.event_bus import WorkflowEventBus
from hestia.workflows.executor import DAGExecutor
from hestia.workflows.manager import WorkflowManager
from hestia.workflows.models import (
    RunStatus,
    Workflow,
    WorkflowNode,
    WorkflowRun,
    WorkflowStatus,
    NodeType,
)


@pytest_asyncio.fixture
async def manager(tmp_path: Path):
    """Create a real workflow manager for route testing."""
    db = WorkflowDatabase(tmp_path / "test_routes.db")
    await db.connect()
    event_bus = WorkflowEventBus()
    executor = DAGExecutor(event_bus=event_bus, node_timeout=5)
    mgr = WorkflowManager(database=db, executor=executor, event_bus=event_bus)
    yield mgr
    await db.close()


@pytest_asyncio.fixture
async def client(manager: WorkflowManager):
    """Create a test HTTP client with mocked auth and manager."""
    from hestia.api.routes.workflows import router
    from hestia.api.middleware.auth import get_device_token
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    # Override auth dependency to always succeed
    app.dependency_overrides[get_device_token] = lambda: "test-token"

    # Patch manager and scheduler singletons
    with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=manager):
        with patch("hestia.api.routes.workflows.get_workflow_scheduler") as mock_sched:
            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_workflow = lambda wf: None
            mock_scheduler.unschedule_workflow = lambda wf_id: None
            mock_sched.return_value = mock_scheduler
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c


class TestWorkflowCRUDRoutes:
    @pytest.mark.asyncio
    async def test_create_workflow(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/workflows",
            json={"name": "Morning Brief", "description": "Daily summary"},
        )
        assert response.status_code == 201
        data = response.json()
        assert "workflow" in data
        assert data["workflow"]["name"] == "Morning Brief"

    @pytest.mark.asyncio
    async def test_list_workflows(self, client: AsyncClient) -> None:
        await client.post("/v1/workflows", json={"name": "WF 1"})
        await client.post("/v1/workflows", json={"name": "WF 2"})
        response = await client.get("/v1/workflows")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    @pytest.mark.asyncio
    async def test_get_workflow_detail(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Detail Test"})
        wf_id = create.json()["workflow"]["id"]
        response = await client.get(f"/v1/workflows/{wf_id}")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data["workflow"]
        assert "edges" in data["workflow"]

    @pytest.mark.asyncio
    async def test_update_workflow(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Original"})
        wf_id = create.json()["workflow"]["id"]
        response = await client.patch(
            f"/v1/workflows/{wf_id}",
            json={"name": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["workflow"]["name"] == "Updated"

    @pytest.mark.asyncio
    async def test_delete_workflow(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "To Delete"})
        wf_id = create.json()["workflow"]["id"]
        response = await client.delete(f"/v1/workflows/{wf_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] is True


class TestNodeRoutes:
    @pytest.mark.asyncio
    async def test_add_node(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Node Test"})
        wf_id = create.json()["workflow"]["id"]
        response = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "Step 1", "config": {"message": "hi"}},
        )
        assert response.status_code == 201
        assert response.json()["node"]["label"] == "Step 1"

    @pytest.mark.asyncio
    async def test_update_node(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Node Test"})
        wf_id = create.json()["workflow"]["id"]
        node_resp = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "Original", "config": {"message": "hi"}},
        )
        node_id = node_resp.json()["node"]["id"]
        response = await client.patch(
            f"/v1/workflows/{wf_id}/nodes/{node_id}",
            json={"label": "Updated"},
        )
        assert response.status_code == 200
        assert response.json()["node"]["label"] == "Updated"

    @pytest.mark.asyncio
    async def test_delete_node(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Node Test"})
        wf_id = create.json()["workflow"]["id"]
        node_resp = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "To Delete", "config": {"message": "bye"}},
        )
        node_id = node_resp.json()["node"]["id"]
        response = await client.delete(f"/v1/workflows/{wf_id}/nodes/{node_id}")
        assert response.status_code == 200
        assert response.json()["deleted"] is True


class TestEdgeRoutes:
    @pytest.mark.asyncio
    async def test_add_edge(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Edge Test"})
        wf_id = create.json()["workflow"]["id"]
        n1 = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "manual", "label": "Trigger"},
        )
        n2 = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "Step", "config": {"message": "hi"}},
        )
        response = await client.post(
            f"/v1/workflows/{wf_id}/edges",
            json={
                "source_node_id": n1.json()["node"]["id"],
                "target_node_id": n2.json()["node"]["id"],
            },
        )
        assert response.status_code == 201
        assert "edge" in response.json()

    @pytest.mark.asyncio
    async def test_add_edge_cycle_rejected(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Cycle Test"})
        wf_id = create.json()["workflow"]["id"]
        n1 = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "A", "config": {"message": "a"}},
        )
        n2 = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "B", "config": {"message": "b"}},
        )
        n1_id = n1.json()["node"]["id"]
        n2_id = n2.json()["node"]["id"]
        # Add A -> B
        await client.post(
            f"/v1/workflows/{wf_id}/edges",
            json={"source_node_id": n1_id, "target_node_id": n2_id},
        )
        # Try B -> A (cycle)
        response = await client.post(
            f"/v1/workflows/{wf_id}/edges",
            json={"source_node_id": n2_id, "target_node_id": n1_id},
        )
        assert response.status_code == 400
        assert "cycle" in response.json().get("error", "").lower()


class TestLifecycleRoutes:
    @pytest.mark.asyncio
    async def test_activate_and_deactivate(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Lifecycle Test"})
        wf_id = create.json()["workflow"]["id"]
        await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "Step", "config": {"message": "hi"}},
        )
        # Activate
        response = await client.post(f"/v1/workflows/{wf_id}/activate")
        assert response.status_code == 200
        assert response.json()["workflow"]["status"] == "active"

        # Deactivate
        response = await client.post(f"/v1/workflows/{wf_id}/deactivate")
        assert response.status_code == 200
        assert response.json()["workflow"]["status"] == "inactive"


class TestExecutionRoutes:
    @pytest.mark.asyncio
    async def test_trigger_workflow(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Trigger Test"})
        wf_id = create.json()["workflow"]["id"]
        await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "Step", "config": {"message": "hello"}},
        )
        response = await client.post(f"/v1/workflows/{wf_id}/trigger")
        assert response.status_code == 200
        assert response.json()["run"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_list_runs(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "History Test"})
        wf_id = create.json()["workflow"]["id"]
        await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "Step", "config": {"message": "hi"}},
        )
        await client.post(f"/v1/workflows/{wf_id}/trigger")
        response = await client.get(f"/v1/workflows/{wf_id}/runs")
        assert response.status_code == 200
        assert response.json()["total"] == 1


class TestLayoutRoute:
    @pytest.mark.asyncio
    async def test_batch_update_layout(self, client: AsyncClient) -> None:
        create = await client.post("/v1/workflows", json={"name": "Layout Test"})
        wf_id = create.json()["workflow"]["id"]
        # Add 3 nodes
        n1 = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "A", "config": {"message": "a"}},
        )
        n2 = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "B", "config": {"message": "b"}},
        )
        n3 = await client.post(
            f"/v1/workflows/{wf_id}/nodes",
            json={"node_type": "log", "label": "C", "config": {"message": "c"}},
        )
        n1_id = n1.json()["node"]["id"]
        n2_id = n2.json()["node"]["id"]
        n3_id = n3.json()["node"]["id"]
        # Batch update positions for all 3 nodes
        response = await client.patch(
            f"/v1/workflows/{wf_id}/layout",
            json={
                "positions": [
                    {"node_id": n1_id, "position_x": 100.0, "position_y": 200.0},
                    {"node_id": n2_id, "position_x": 300.0, "position_y": 400.0},
                    {"node_id": n3_id, "position_x": 500.0, "position_y": 600.0},
                ]
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data == {"updated": 3, "workflow_id": wf_id}

    @pytest.mark.asyncio
    async def test_batch_update_layout_not_found(self, client: AsyncClient) -> None:
        response = await client.patch(
            "/v1/workflows/wf-123/layout",
            json={
                "positions": [
                    {"node_id": "node-x", "position_x": 0.0, "position_y": 0.0},
                ]
            },
        )
        assert response.status_code == 404
        assert "not found" in response.json()["error"].lower()
