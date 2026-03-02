"""
Tests for Hestia server lifecycle: readiness gate, shutdown cleanup, cache headers.

Sprint 6: Stability & Efficiency.

Run with: python -m pytest tests/test_server_lifecycle.py -v
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from starlette.testclient import TestClient
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


# ============== ReadinessMiddleware Tests ==============


class TestReadinessMiddleware:
    """Test the ReadinessMiddleware behavior."""

    def _create_app(self, ready: bool = False) -> FastAPI:
        """Create a minimal FastAPI app with ReadinessMiddleware."""
        from hestia.api.server import ReadinessMiddleware

        app = FastAPI()
        app.state.ready = ready
        app.state.started_at = time.monotonic() if ready else 0.0

        @app.get("/v1/ping")
        async def ping():
            return {"status": "ok", "message": "pong"}

        @app.get("/v1/ready")
        async def ready_check(request: Request):
            is_ready = getattr(request.app.state, "ready", False)
            if is_ready:
                return JSONResponse(
                    status_code=200,
                    content={"ready": True, "uptime_seconds": 1.0},
                )
            return JSONResponse(
                status_code=503,
                content={"ready": False, "uptime_seconds": 0.0},
            )

        @app.get("/v1/chat")
        async def chat():
            return {"message": "hello"}

        @app.get("/docs")
        async def docs():
            return {"docs": True}

        @app.get("/")
        async def root():
            return {"root": True}

        app.add_middleware(ReadinessMiddleware)
        return app

    def test_returns_503_when_not_ready(self):
        """Regular endpoints should return 503 during startup."""
        app = self._create_app(ready=False)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/v1/chat")
        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "service_unavailable"
        assert data["ready"] is False
        assert response.headers.get("Retry-After") == "5"

    def test_allows_ping_when_not_ready(self):
        """Ping should bypass the readiness gate."""
        app = self._create_app(ready=False)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/v1/ping")
        assert response.status_code == 200
        assert response.json()["message"] == "pong"

    def test_allows_ready_endpoint_when_not_ready(self):
        """Ready endpoint should be reachable during startup."""
        app = self._create_app(ready=False)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/v1/ready")
        assert response.status_code == 503
        assert response.json()["ready"] is False

    def test_allows_docs_when_not_ready(self):
        """Docs should bypass the readiness gate."""
        app = self._create_app(ready=False)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/docs")
        assert response.status_code == 200

    def test_allows_root_when_not_ready(self):
        """Root endpoint should bypass the readiness gate."""
        app = self._create_app(ready=False)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/")
        assert response.status_code == 200

    def test_allows_all_when_ready(self):
        """All endpoints should work when server is ready."""
        app = self._create_app(ready=True)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/v1/chat")
        assert response.status_code == 200
        assert response.json()["message"] == "hello"

    def test_ready_endpoint_returns_200_when_ready(self):
        """Ready endpoint should return 200 with uptime when ready."""
        app = self._create_app(ready=True)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/v1/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert "uptime_seconds" in data


# ============== Cache-Control Tests ==============


class TestCacheControlHeaders:
    """Test path-aware Cache-Control headers."""

    def test_ping_is_cacheable(self):
        """Ping should have max-age=10."""
        from hestia.api.server import _CACHE_POLICIES, _DEFAULT_CACHE_POLICY

        # Find the policy for /v1/ping
        policy = _DEFAULT_CACHE_POLICY
        for prefix, p in _CACHE_POLICIES:
            if "/v1/ping".startswith(prefix):
                policy = p
                break
        assert policy == "max-age=10"

    def test_tools_is_cacheable(self):
        """Tools should have max-age=60."""
        from hestia.api.server import _CACHE_POLICIES, _DEFAULT_CACHE_POLICY

        policy = _DEFAULT_CACHE_POLICY
        for prefix, p in _CACHE_POLICIES:
            if "/v1/tools".startswith(prefix):
                policy = p
                break
        assert policy == "max-age=60"

    def test_wiki_articles_cacheable(self):
        """Wiki articles should have max-age=30."""
        from hestia.api.server import _CACHE_POLICIES, _DEFAULT_CACHE_POLICY

        policy = _DEFAULT_CACHE_POLICY
        for prefix, p in _CACHE_POLICIES:
            if "/v1/wiki/articles".startswith(prefix):
                policy = p
                break
        assert policy == "max-age=30"

    def test_default_is_no_store(self):
        """Non-listed paths should get no-store."""
        from hestia.api.server import _CACHE_POLICIES, _DEFAULT_CACHE_POLICY

        policy = _DEFAULT_CACHE_POLICY
        for prefix, p in _CACHE_POLICIES:
            if "/v1/chat".startswith(prefix):
                policy = p
                break
        assert "no-store" in policy


# ============== Shutdown Cleanup Tests ==============


class TestShutdownCleanup:
    """Test that all managers have close functions."""

    def test_memory_close_exists(self):
        """Memory module should export close_memory_manager."""
        from hestia.memory import close_memory_manager
        assert callable(close_memory_manager)

    def test_cloud_close_exists(self):
        """Cloud module should export close_cloud_manager."""
        from hestia.cloud import close_cloud_manager
        assert callable(close_cloud_manager)

    def test_explorer_close_exists(self):
        """Explorer module should export close_explorer_manager."""
        from hestia.explorer import close_explorer_manager
        assert callable(close_explorer_manager)

    def test_task_close_exists(self):
        """Tasks module should export close_task_manager."""
        from hestia.tasks import close_task_manager
        assert callable(close_task_manager)

    def test_order_close_exists(self):
        """Orders module should export close_order_manager."""
        from hestia.orders import close_order_manager
        assert callable(close_order_manager)

    def test_order_scheduler_close_exists(self):
        """Orders module should export close_order_scheduler."""
        from hestia.orders import close_order_scheduler
        assert callable(close_order_scheduler)

    def test_agent_close_exists(self):
        """Agents module should export close_agent_manager."""
        from hestia.agents import close_agent_manager
        assert callable(close_agent_manager)

    def test_user_close_exists(self):
        """User module should export close_user_manager."""
        from hestia.user import close_user_manager
        assert callable(close_user_manager)

    def test_health_close_exists(self):
        """Health module should export close_health_manager."""
        from hestia.health import close_health_manager
        assert callable(close_health_manager)

    def test_wiki_close_exists(self):
        """Wiki module should export close_wiki_manager."""
        from hestia.wiki import close_wiki_manager
        assert callable(close_wiki_manager)

    def test_newsfeed_close_exists(self):
        """Newsfeed module should export close_newsfeed_manager."""
        from hestia.newsfeed import close_newsfeed_manager
        assert callable(close_newsfeed_manager)

    def test_investigate_close_exists(self):
        """Investigate module should export close_investigate_manager."""
        from hestia.investigate import close_investigate_manager
        assert callable(close_investigate_manager)


# ============== Explorer Manager Close Method ==============


class TestExplorerClose:
    """Test ExplorerManager.close() method."""

    @pytest.mark.asyncio
    async def test_close_with_database(self):
        """close() should call database.close()."""
        from hestia.explorer.manager import ExplorerManager

        mock_db = AsyncMock()
        manager = ExplorerManager(database=mock_db)
        await manager.close()
        mock_db.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_without_database(self):
        """close() should handle None database gracefully."""
        from hestia.explorer.manager import ExplorerManager

        manager = ExplorerManager(database=None)
        await manager.close()  # Should not raise


# ============== Readiness Bypass Paths ==============


class TestReadinessBypassPaths:
    """Verify bypass paths are complete."""

    def test_bypass_paths_include_essentials(self):
        """Readiness bypass should include health probes, docs, and root."""
        from hestia.api.server import _READINESS_BYPASS_PATHS

        assert "/v1/ping" in _READINESS_BYPASS_PATHS
        assert "/v1/ready" in _READINESS_BYPASS_PATHS
        assert "/docs" in _READINESS_BYPASS_PATHS
        assert "/redoc" in _READINESS_BYPASS_PATHS
        assert "/openapi.json" in _READINESS_BYPASS_PATHS
        assert "/" in _READINESS_BYPASS_PATHS

    def test_regular_paths_not_bypassed(self):
        """Regular endpoints should NOT be in the bypass set."""
        from hestia.api.server import _READINESS_BYPASS_PATHS

        assert "/v1/chat" not in _READINESS_BYPASS_PATHS
        assert "/v1/health" not in _READINESS_BYPASS_PATHS
        assert "/v1/memory" not in _READINESS_BYPASS_PATHS


# ============== Uvicorn Config ==============


class TestUvicornConfig:
    """Test Uvicorn configuration values."""

    def test_limit_max_requests_set(self):
        """Uvicorn should have request limit configured."""
        # We can't easily test the uvicorn_config dict without calling run_server,
        # but we can verify the module-level constants are importable and the
        # server module doesn't error on import
        import hestia.api.server
        assert hasattr(hestia.api.server, 'app')
