"""
Tests for Dev session API routes.

Agentic Dev System — Task 11.
Covers: create, list, get, approve, cancel, proposals, and events endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch

from hestia.dev.models import DevSession, DevSessionSource


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_manager():
    """Mock DevSessionManager with a pre-built test session."""
    session = DevSession.create(
        title="Test Session",
        description="A test dev session",
        source=DevSessionSource.CLI,
    )

    manager = AsyncMock()
    manager.create_session = AsyncMock(return_value=session)
    manager.get_session = AsyncMock(return_value=session)
    manager.list_sessions = AsyncMock(return_value=[session])
    manager.list_pending_proposals = AsyncMock(return_value=[])
    manager.approve_session = AsyncMock(return_value=session)
    manager.cancel_session = AsyncMock(return_value=session)
    manager.get_events = AsyncMock(return_value=[])
    return manager


def _make_app(mock_manager):
    """Create a minimal FastAPI test app with the dev router and auth override."""
    from fastapi import FastAPI
    from hestia.api.routes.dev import router
    from hestia.api.middleware.auth import get_device_token

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_device_token] = lambda: "test-device-123"
    return app


# ---------------------------------------------------------------------------
# POST /v1/dev/sessions
# ---------------------------------------------------------------------------


class TestCreateSession:
    """Tests for POST /v1/dev/sessions."""

    @pytest.mark.asyncio
    async def test_create_returns_200_with_id(self, mock_manager):
        """Creating a session returns 200 with the session id."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/dev/sessions",
                json={"title": "Test Session", "description": "A test dev session"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["id"].startswith("dev-")
        assert data["title"] == "Test Session"
        assert data["state"] == "queued"
        assert data["source"] == "cli"

    @pytest.mark.asyncio
    async def test_create_with_custom_priority(self, mock_manager):
        """Session creation accepts a custom priority."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/dev/sessions",
                json={"title": "Urgent task", "description": "Do it now", "priority": 1},
            )

        assert response.status_code == 200
        mock_manager.create_session.assert_called_once()
        call_kwargs = mock_manager.create_session.call_args.kwargs
        # Priority 1 = CRITICAL
        assert call_kwargs["priority"].value == 1

    @pytest.mark.asyncio
    async def test_create_with_source_ref(self, mock_manager):
        """Session creation accepts a source_ref."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post(
                "/v1/dev/sessions",
                json={"title": "Issue fix", "description": "Fix #123", "source_ref": "#123"},
            )

        assert response.status_code == 200
        call_kwargs = mock_manager.create_session.call_args.kwargs
        assert call_kwargs["source_ref"] == "#123"


# ---------------------------------------------------------------------------
# GET /v1/dev/sessions
# ---------------------------------------------------------------------------


class TestListSessions:
    """Tests for GET /v1/dev/sessions."""

    @pytest.mark.asyncio
    async def test_list_returns_sessions_array(self, mock_manager):
        """List endpoint returns a sessions array with count."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/dev/sessions")

        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert "count" in data
        assert data["count"] == 1
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["id"].startswith("dev-")

    @pytest.mark.asyncio
    async def test_list_passes_limit_param(self, mock_manager):
        """List endpoint passes the limit parameter to manager."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/dev/sessions?limit=10")

        assert response.status_code == 200
        mock_manager.list_sessions.assert_called_once_with(state=None, limit=10)

    @pytest.mark.asyncio
    async def test_list_with_invalid_state_returns_400(self, mock_manager):
        """List endpoint returns 400 for an invalid state filter."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/dev/sessions?state=invalid_state")

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /v1/dev/sessions/{session_id}
# ---------------------------------------------------------------------------


class TestGetSession:
    """Tests for GET /v1/dev/sessions/{session_id}."""

    @pytest.mark.asyncio
    async def test_get_existing_session(self, mock_manager):
        """Get returns the session when it exists."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            session_id = mock_manager.get_session.return_value.id
            response = client.get(f"/v1/dev/sessions/{session_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id

    @pytest.mark.asyncio
    async def test_get_missing_session_returns_404(self, mock_manager):
        """Get returns 404 for a non-existent session ID."""
        from fastapi.testclient import TestClient

        mock_manager.get_session = AsyncMock(return_value=None)
        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/dev/sessions/dev-nonexistent")

        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["error"] == "session_not_found"


# ---------------------------------------------------------------------------
# POST /v1/dev/sessions/{session_id}/approve
# ---------------------------------------------------------------------------


class TestApproveSession:
    """Tests for POST /v1/dev/sessions/{session_id}/approve."""

    @pytest.mark.asyncio
    async def test_approve_returns_200(self, mock_manager):
        """Approving a session returns 200 with updated session."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post("/v1/dev/sessions/dev-abc123/approve")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data

    @pytest.mark.asyncio
    async def test_approve_invalid_state_returns_400(self, mock_manager):
        """Approving a session in a non-PROPOSED state returns 400."""
        from fastapi.testclient import TestClient

        mock_manager.approve_session = AsyncMock(
            side_effect=ValueError("Can only approve sessions in PROPOSED state")
        )
        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post("/v1/dev/sessions/dev-abc123/approve")

        assert response.status_code == 400
        data = response.json()
        assert data["detail"]["error"] == "invalid_transition"


# ---------------------------------------------------------------------------
# POST /v1/dev/sessions/{session_id}/cancel
# ---------------------------------------------------------------------------


class TestCancelSession:
    """Tests for POST /v1/dev/sessions/{session_id}/cancel."""

    @pytest.mark.asyncio
    async def test_cancel_returns_200(self, mock_manager):
        """Cancelling a session returns 200."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post("/v1/dev/sessions/dev-abc123/cancel")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_cancel_invalid_transition_returns_400(self, mock_manager):
        """Cancelling a session in a terminal state returns 400."""
        from fastapi.testclient import TestClient

        mock_manager.cancel_session = AsyncMock(
            side_effect=ValueError("Invalid transition: complete -> cancelled")
        )
        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.post("/v1/dev/sessions/dev-abc123/cancel")

        assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /v1/dev/proposals
# ---------------------------------------------------------------------------


class TestListPendingProposals:
    """Tests for GET /v1/dev/proposals."""

    @pytest.mark.asyncio
    async def test_proposals_returns_array(self, mock_manager):
        """Proposals endpoint returns a proposals array."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/dev/proposals")

        assert response.status_code == 200
        data = response.json()
        assert "proposals" in data
        assert isinstance(data["proposals"], list)
        assert len(data["proposals"]) == 0  # mock returns []

    @pytest.mark.asyncio
    async def test_proposals_with_pending_sessions(self, mock_manager):
        """Proposals endpoint includes PROPOSED sessions."""
        from fastapi.testclient import TestClient

        proposed_session = DevSession.create(
            title="Pending proposal",
            description="Waiting for approval",
            source=DevSessionSource.CLI,
        )
        mock_manager.list_pending_proposals = AsyncMock(return_value=[proposed_session])

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/dev/proposals")

        assert response.status_code == 200
        data = response.json()
        assert len(data["proposals"]) == 1
        assert data["proposals"][0]["title"] == "Pending proposal"


# ---------------------------------------------------------------------------
# GET /v1/dev/sessions/{session_id}/events
# ---------------------------------------------------------------------------


class TestGetEvents:
    """Tests for GET /v1/dev/sessions/{session_id}/events."""

    @pytest.mark.asyncio
    async def test_events_returns_array(self, mock_manager):
        """Events endpoint returns an events array."""
        from fastapi.testclient import TestClient

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            session_id = mock_manager.get_session.return_value.id
            response = client.get(f"/v1/dev/sessions/{session_id}/events")

        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert isinstance(data["events"], list)

    @pytest.mark.asyncio
    async def test_events_missing_session_returns_404(self, mock_manager):
        """Events returns 404 if the session doesn't exist."""
        from fastapi.testclient import TestClient

        mock_manager.get_session = AsyncMock(return_value=None)
        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/dev/sessions/dev-nonexistent/events")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_events_with_data(self, mock_manager):
        """Events endpoint serializes event fields correctly."""
        from fastapi.testclient import TestClient
        from hestia.dev.models import DevEvent, DevEventType

        event = DevEvent.create(
            session_id="dev-abc123",
            event_type=DevEventType.STATE_CHANGE,
            data={"from": "queued", "to": "planning"},
        )
        mock_manager.get_events = AsyncMock(return_value=[event])

        app = _make_app(mock_manager)
        with patch("hestia.dev.get_dev_session_manager", new_callable=AsyncMock, return_value=mock_manager):
            client = TestClient(app)
            session_id = mock_manager.get_session.return_value.id
            response = client.get(f"/v1/dev/sessions/{session_id}/events")

        assert response.status_code == 200
        data = response.json()
        assert len(data["events"]) == 1
        ev = data["events"][0]
        assert ev["event_type"] == "state_change"
        assert ev["data"] == {"from": "queued", "to": "planning"}
        assert ev["agent_tier"] is None
