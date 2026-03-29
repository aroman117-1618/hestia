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
