"""Tests for Step-to-DAG node translation endpoint."""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from hestia.api.routes.workflows import router
from hestia.api.middleware.auth import get_device_token


@pytest_asyncio.fixture
async def mock_manager():
    """Mock WorkflowManager that returns predictable node IDs."""
    manager = AsyncMock()

    call_count = 0

    async def mock_add_node(
        workflow_id,
        node_type,
        label="Untitled",
        config=None,
        position_x=0.0,
        position_y=0.0,
    ):
        nonlocal call_count
        call_count += 1
        node = MagicMock()
        node.id = f"node-test-{call_count:03d}"
        node.to_dict.return_value = {
            "id": node.id,
            "node_type": node_type,
            "label": label,
            "config": config or {},
            "position_x": position_x,
            "position_y": position_y,
        }
        return node

    manager.add_node = mock_add_node

    edge_count = 0

    async def mock_add_edge(workflow_id, source_node_id, target_node_id, edge_label=""):
        nonlocal edge_count
        edge_count += 1
        edge = MagicMock()
        edge.id = f"edge-test-{edge_count:03d}"
        edge.to_dict.return_value = {
            "id": edge.id,
            "source_node_id": source_node_id,
            "target_node_id": target_node_id,
            "edge_label": edge_label,
        }
        return edge

    manager.add_edge = mock_add_edge
    return manager


@pytest_asyncio.fixture
async def client(mock_manager):
    """Test HTTP client with mocked auth and manager."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_device_token] = lambda: "test-token"

    with patch(
        "hestia.api.routes.workflows.get_workflow_manager",
        return_value=mock_manager,
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


class TestStepTranslation:
    """Tests for POST /v1/workflows/{id}/nodes/from-step."""

    @pytest.mark.asyncio
    async def test_prompt_step_creates_run_prompt_node(self, client: AsyncClient):
        """A Step with a prompt and no delay → single run_prompt node."""
        resp = await client.post(
            "/v1/workflows/wf-test/nodes/from-step",
            json={
                "title": "Summarize Email",
                "prompt": "Summarize the latest unread emails",
                "trigger": "immediate",
                "resources": ["calendar", "mail"],
                "position_x": 300,
                "position_y": 200,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 1
        node = data["nodes"][0]
        assert node["node_type"] == "run_prompt"
        assert node["label"] == "Summarize Email"

    @pytest.mark.asyncio
    async def test_delayed_step_creates_delay_plus_prompt(self, client: AsyncClient):
        """A Step with delay trigger → DELAY node + run_prompt node + connecting edge."""
        resp = await client.post(
            "/v1/workflows/wf-test/nodes/from-step",
            json={
                "title": "Wait then Notify",
                "prompt": "Generate a summary",
                "trigger": "delay",
                "delay_seconds": 300,
                "position_x": 300,
                "position_y": 200,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["nodes"]) == 2
        assert data["nodes"][0]["node_type"] == "delay"
        assert data["nodes"][1]["node_type"] == "run_prompt"
        assert len(data["edges"]) >= 1

    @pytest.mark.asyncio
    async def test_step_with_after_node_creates_edge(self, client: AsyncClient):
        """When after_node_id is provided, edge from existing node to new node."""
        resp = await client.post(
            "/v1/workflows/wf-test/nodes/from-step",
            json={
                "title": "Next Step",
                "prompt": "Do something",
                "trigger": "immediate",
                "after_node_id": "node-existing-001",
                "position_x": 300,
                "position_y": 400,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        edges = data["edges"]
        assert any(e["source_node_id"] == "node-existing-001" for e in edges)

    @pytest.mark.asyncio
    async def test_resources_mapped_to_allowed_tools(self, mock_manager):
        """Resource categories expanded to tool names in allowed_tools config."""
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_device_token] = lambda: "test-token"

        with patch(
            "hestia.api.routes.workflows.get_workflow_manager",
            return_value=mock_manager,
        ), patch(
            "hestia.api.routes.workflows._expand_resource_categories",
            return_value=["list_calendar_events", "search_calendar"],
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                resp = await c.post(
                    "/v1/workflows/wf-test/nodes/from-step",
                    json={
                        "title": "Check Calendar",
                        "prompt": "What's on my calendar today?",
                        "trigger": "immediate",
                        "resources": ["calendar"],
                        "position_x": 300,
                        "position_y": 200,
                    },
                )

        assert resp.status_code == 200
        node = resp.json()["nodes"][0]
        config = node["config"]
        assert "allowed_tools" in config
        assert isinstance(config["allowed_tools"], list)
        assert len(config["allowed_tools"]) > 0

    @pytest.mark.asyncio
    async def test_step_without_prompt_rejected(self, client: AsyncClient):
        """A Step must have a prompt."""
        resp = await client.post(
            "/v1/workflows/wf-test/nodes/from-step",
            json={
                "title": "No Prompt",
                "trigger": "immediate",
                "position_x": 300,
                "position_y": 200,
            },
        )

        assert resp.status_code == 400
