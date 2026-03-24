"""Tests for enhanced tool categories endpoint."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from hestia.api.routes.tools import router
from hestia.api.middleware.auth import get_device_token


@pytest.fixture
def mock_registry():
    """Create a mock ToolRegistry with categorized tools."""
    from hestia.execution.models import Tool, ToolParam, ToolParamType

    dummy_handler = AsyncMock()

    tools = [
        Tool(
            name="list_events",
            description="List calendar events",
            parameters={"start_date": ToolParam(type=ToolParamType.STRING, description="Start date", required=True)},
            handler=dummy_handler,
            category="calendar",
        ),
        Tool(
            name="create_event",
            description="Create a calendar event",
            parameters={"title": ToolParam(type=ToolParamType.STRING, description="Event title", required=True)},
            handler=dummy_handler,
            category="calendar",
        ),
        Tool(
            name="read_file",
            description="Read a file",
            parameters={"path": ToolParam(type=ToolParamType.STRING, description="File path", required=True)},
            handler=dummy_handler,
            category="file",
        ),
    ]

    registry = MagicMock()
    registry.list_tools.return_value = tools
    registry.__len__ = lambda self: 3
    return registry


@pytest.fixture
def test_app():
    """Minimal FastAPI app with just the tools router and auth bypassed."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_device_token] = lambda: "test-token"
    return app


class TestToolCategoriesEnhanced:
    """Tests for enhanced GET /v1/tools/categories."""

    @pytest.mark.asyncio
    async def test_returns_grouped_tools_with_metadata(self, mock_registry, test_app):
        """Should return tools grouped by category with labels and icons."""
        with patch("hestia.api.routes.tools.get_tool_registry", return_value=mock_registry):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.get(
                    "/v1/tools/categories",
                    headers={"Authorization": "Bearer test-token"},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert "categories" in data

        cats = {c["id"]: c for c in data["categories"]}
        assert "calendar" in cats
        assert "file" in cats
        assert len(cats["calendar"]["tools"]) == 2
        assert len(cats["file"]["tools"]) == 1

    @pytest.mark.asyncio
    async def test_categories_have_labels_and_icons(self, mock_registry, test_app):
        """Each category should have a human-readable label and SF Symbol icon."""
        with patch("hestia.api.routes.tools.get_tool_registry", return_value=mock_registry):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.get(
                    "/v1/tools/categories",
                    headers={"Authorization": "Bearer test-token"},
                )

        data = resp.json()
        for cat in data["categories"]:
            assert "id" in cat
            assert "label" in cat
            assert "icon" in cat
            assert "tools" in cat

        cal = next(c for c in data["categories"] if c["id"] == "calendar")
        assert cal["label"] == "Calendar"
        assert cal["icon"] == "calendar"

    @pytest.mark.asyncio
    async def test_tool_entries_have_schema(self, mock_registry, test_app):
        """Each tool entry should include name, description, and parameter schema."""
        with patch("hestia.api.routes.tools.get_tool_registry", return_value=mock_registry):
            transport = ASGITransport(app=test_app)
            async with AsyncClient(transport=transport, base_url="https://test") as client:
                resp = await client.get(
                    "/v1/tools/categories",
                    headers={"Authorization": "Bearer test-token"},
                )

        data = resp.json()
        cal_cat = next(c for c in data["categories"] if c["id"] == "calendar")
        tool = cal_cat["tools"][0]
        assert "name" in tool
        assert "description" in tool
        assert "parameters" in tool
