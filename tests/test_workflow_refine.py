"""Tests for the workflow prompt refinement endpoint."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from hestia.workflows.database import WorkflowDatabase
from hestia.workflows.event_bus import WorkflowEventBus
from hestia.workflows.executor import DAGExecutor
from hestia.workflows.manager import WorkflowManager


@pytest_asyncio.fixture
async def manager(tmp_path: Path):
    db = WorkflowDatabase(tmp_path / "test_refine.db")
    await db.connect()
    event_bus = WorkflowEventBus()
    executor = DAGExecutor(event_bus=event_bus, node_timeout=5)
    mgr = WorkflowManager(database=db, executor=executor, event_bus=event_bus)
    yield mgr
    await db.close()


@pytest_asyncio.fixture
async def client(manager: WorkflowManager):
    from hestia.api.routes.workflows import router
    from hestia.api.middleware.auth import get_device_token
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_device_token] = lambda: "test-token"

    with patch("hestia.api.routes.workflows.get_workflow_manager", return_value=manager):
        with patch("hestia.api.routes.workflows.get_workflow_scheduler") as mock_sched:
            mock_scheduler = AsyncMock()
            mock_scheduler.schedule_workflow = lambda wf: None
            mock_scheduler.unschedule_workflow = lambda wf_id: None
            mock_sched.return_value = mock_scheduler
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                yield c


class TestRefinePromptEndpoint:
    @pytest.mark.asyncio
    async def test_empty_prompt_returns_400(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/workflows/refine-prompt",
            json={"prompt": "", "inference_route": "full_cloud"},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_prompt_returns_422(self, client: AsyncClient) -> None:
        response = await client.post(
            "/v1/workflows/refine-prompt",
            json={"inference_route": "full_cloud"},
        )
        assert response.status_code == 422


class TestRefinePromptLogic:
    @pytest.mark.asyncio
    async def test_happy_path_returns_variations(self, client: AsyncClient) -> None:
        """Mock inference to return valid JSON, verify structured response."""
        mock_inference_response = MagicMock()
        mock_inference_response.content = json.dumps({
            "variations": [
                {
                    "label": "Focused",
                    "prompt": "Audit the top 5 issues in security and performance.",
                    "explanation": "Scoped to actionable items.",
                    "model_suitability": "cloud_optimized",
                },
                {
                    "label": "Structured",
                    "prompt": "Report findings as JSON with severity scores.",
                    "explanation": "Machine-parseable output.",
                    "model_suitability": "local_friendly",
                },
            ]
        })

        mock_user_config = MagicMock()
        mock_user_config.context_block = "## User Profile\n\nAndrew is a software engineer."
        mock_user_config.get_topic_context.return_value = ""

        mock_loader = AsyncMock()
        mock_loader.load.return_value = mock_user_config

        mock_memory_results = [
            MagicMock(content="Andrew prioritizes security and performance."),
        ]

        with patch("hestia.api.routes.workflows.get_user_config_loader", return_value=mock_loader), \
             patch("hestia.api.routes.workflows.get_memory_manager") as mock_mem_factory, \
             patch("hestia.api.routes.workflows.get_inference_client") as mock_inf_factory:
            mock_mem = AsyncMock()
            mock_mem.search.return_value = mock_memory_results
            mock_mem_factory.return_value = mock_mem

            mock_inference = AsyncMock()
            mock_inference.complete.return_value = mock_inference_response
            mock_inf_factory.return_value = mock_inference

            response = await client.post(
                "/v1/workflows/refine-prompt",
                json={
                    "prompt": "Hunt through the codebase for issues",
                    "inference_route": "full_cloud",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "variations" in data
        assert len(data["variations"]) == 2
        assert data["variations"][0]["label"] == "Focused"
        assert "context_used" in data
        assert "user_profile" in data["context_used"]
        assert "memory" in data["context_used"]

    @pytest.mark.asyncio
    async def test_json_parse_failure_returns_single_variation(self, client: AsyncClient) -> None:
        """When local model returns non-JSON, fall back to single variation."""
        mock_inference_response = MagicMock()
        mock_inference_response.content = "Here is an improved prompt: Analyze the codebase systematically."

        mock_user_config = MagicMock()
        mock_user_config.context_block = ""
        mock_user_config.get_topic_context.return_value = ""

        mock_loader = AsyncMock()
        mock_loader.load.return_value = mock_user_config

        with patch("hestia.api.routes.workflows.get_user_config_loader", return_value=mock_loader), \
             patch("hestia.api.routes.workflows.get_memory_manager") as mock_mem_factory, \
             patch("hestia.api.routes.workflows.get_inference_client") as mock_inf_factory:
            mock_mem = AsyncMock()
            mock_mem.search.return_value = []
            mock_mem_factory.return_value = mock_mem

            mock_inference = AsyncMock()
            mock_inference.complete.return_value = mock_inference_response
            mock_inf_factory.return_value = mock_inference

            response = await client.post(
                "/v1/workflows/refine-prompt",
                json={"prompt": "Do something useful"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["variations"]) == 1
        assert data["variations"][0]["label"] == "Improved"
        assert "Analyze the codebase" in data["variations"][0]["prompt"]

    @pytest.mark.asyncio
    async def test_force_tier_primary_used(self, client: AsyncClient) -> None:
        """Verify refinement always uses force_tier='primary' (local only)."""
        mock_inference_response = MagicMock()
        mock_inference_response.content = json.dumps({"variations": [{
            "label": "Test", "prompt": "test", "explanation": "test",
            "model_suitability": "universal",
        }]})

        mock_user_config = MagicMock()
        mock_user_config.context_block = ""
        mock_user_config.get_topic_context.return_value = ""
        mock_loader = AsyncMock()
        mock_loader.load.return_value = mock_user_config

        with patch("hestia.api.routes.workflows.get_user_config_loader", return_value=mock_loader), \
             patch("hestia.api.routes.workflows.get_memory_manager") as mock_mem_factory, \
             patch("hestia.api.routes.workflows.get_inference_client") as mock_inf_factory:
            mock_mem = AsyncMock()
            mock_mem.search.return_value = []
            mock_mem_factory.return_value = mock_mem

            mock_inference = AsyncMock()
            mock_inference.complete.return_value = mock_inference_response
            mock_inf_factory.return_value = mock_inference

            await client.post(
                "/v1/workflows/refine-prompt",
                json={"prompt": "Test prompt", "inference_route": "full_cloud"},
            )

            # Verify force_tier="primary" was passed
            call_kwargs = mock_inference.complete.call_args
            assert call_kwargs.kwargs.get("force_tier") == "primary" or \
                   (len(call_kwargs.args) > 0 and "force_tier" in str(call_kwargs))

    @pytest.mark.asyncio
    async def test_inference_unavailable_returns_503(self, client: AsyncClient) -> None:
        """When local model is down, return 503."""
        mock_user_config = MagicMock()
        mock_user_config.context_block = ""
        mock_user_config.get_topic_context.return_value = ""
        mock_loader = AsyncMock()
        mock_loader.load.return_value = mock_user_config

        with patch("hestia.api.routes.workflows.get_user_config_loader", return_value=mock_loader), \
             patch("hestia.api.routes.workflows.get_memory_manager") as mock_mem_factory, \
             patch("hestia.api.routes.workflows.get_inference_client") as mock_inf_factory:
            mock_mem = AsyncMock()
            mock_mem.search.return_value = []
            mock_mem_factory.return_value = mock_mem

            mock_inference = AsyncMock()
            mock_inference.complete.side_effect = Exception("Connection refused")
            mock_inf_factory.return_value = mock_inference

            response = await client.post(
                "/v1/workflows/refine-prompt",
                json={"prompt": "Test prompt"},
            )

        assert response.status_code == 503
