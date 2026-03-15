"""
Tests for SSE streaming chat endpoint (POST /v1/chat/stream).

Tests the SSE framing, auth, event types, and error handling.
Uses direct handler mocking — no real inference.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from hestia.api.routes.chat import router
from hestia.api.middleware.auth import get_device_token


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _create_app(auth_device_id: str = "test-device") -> FastAPI:
    """Create a minimal FastAPI app with chat router and mock auth."""
    app = FastAPI()
    app.include_router(router)

    async def mock_auth():
        return auth_device_id

    app.dependency_overrides[get_device_token] = mock_auth
    return app


async def _mock_streaming_events():
    """Yield a typical sequence of streaming events."""
    yield {"type": "status", "stage": "preparing", "detail": "Loading context"}
    yield {"type": "status", "stage": "inference", "detail": "Generating response"}
    yield {"type": "token", "content": "Hello", "request_id": "req-test123"}
    yield {"type": "token", "content": " world", "request_id": "req-test123"}
    yield {
        "type": "done",
        "request_id": "req-test123",
        "metrics": {"tokens_in": 100, "tokens_out": 2, "duration_ms": 500},
        "mode": "tia",
    }


async def _mock_streaming_with_tool():
    """Yield events including a tool call."""
    yield {"type": "status", "stage": "preparing", "detail": "Loading context"}
    yield {"type": "token", "content": "Let me check", "request_id": "req-test123"}
    yield {"type": "clear_stream"}
    yield {"type": "tool_result", "call_id": "tc-1", "tool_name": "get_today_events", "status": "success", "result": "Meeting at 3pm"}
    yield {"type": "token", "content": "You have a meeting at 3pm.", "request_id": "req-test123"}
    yield {
        "type": "done",
        "request_id": "req-test123",
        "metrics": {"tokens_in": 150, "tokens_out": 10, "duration_ms": 1200},
        "mode": "tia",
    }


async def _mock_streaming_error():
    """Yield events then raise an error mid-stream."""
    yield {"type": "status", "stage": "preparing", "detail": "Loading context"}
    raise RuntimeError("Inference failed")


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSSEEndpoint:
    """Tests for POST /v1/chat/stream SSE endpoint."""

    def _make_request(self, app: FastAPI, message: str = "Hello", **kwargs):
        """Send a streaming request and return the raw response."""
        client = TestClient(app, raise_server_exceptions=False)
        body = {"message": message, **kwargs}
        return client.post("/v1/chat/stream", json=body)

    def _parse_sse_events(self, body: str) -> list:
        """Parse SSE-formatted text into a list of (event_type, data_dict) tuples."""
        events = []
        current_event = ""
        current_data = ""
        for line in body.split("\n"):
            if line.startswith("event: "):
                current_event = line[7:]
            elif line.startswith("data: "):
                current_data = line[6:]
            elif line == "" and current_data:
                events.append((current_event, json.loads(current_data)))
                current_event = ""
                current_data = ""
        return events

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_returns_event_stream_content_type(self, mock_outcome, mock_handler_fn):
        """SSE endpoint returns text/event-stream content type."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_events())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        response = self._make_request(app)

        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_sse_event_framing(self, mock_outcome, mock_handler_fn):
        """Events are properly framed with event: and data: lines."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_events())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        response = self._make_request(app)

        events = self._parse_sse_events(response.text)
        assert len(events) == 5  # 2 status + 2 token + 1 done

        # Check event types match
        event_types = [e[0] for e in events]
        assert event_types == ["status", "status", "token", "token", "done"]

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_token_events_contain_content(self, mock_outcome, mock_handler_fn):
        """Token events contain the streamed content."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_events())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        response = self._make_request(app)

        events = self._parse_sse_events(response.text)
        token_events = [e[1] for e in events if e[0] == "token"]
        combined = "".join(t["content"] for t in token_events)
        assert combined == "Hello world"

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_done_event_contains_metrics(self, mock_outcome, mock_handler_fn):
        """Done event includes metrics dict."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_events())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        response = self._make_request(app)

        events = self._parse_sse_events(response.text)
        done_events = [e[1] for e in events if e[0] == "done"]
        assert len(done_events) == 1
        assert done_events[0]["metrics"]["tokens_out"] == 2
        assert done_events[0]["metrics"]["duration_ms"] == 500
        assert done_events[0]["mode"] == "tia"

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_tool_call_events(self, mock_outcome, mock_handler_fn):
        """Tool call events are streamed with clear_stream signals."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_with_tool())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        response = self._make_request(app, message="What's on my calendar?")

        events = self._parse_sse_events(response.text)
        event_types = [e[0] for e in events]
        assert "clear_stream" in event_types
        assert "tool_result" in event_types

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_error_during_stream(self, mock_outcome, mock_handler_fn):
        """Handler error yields an error SSE event."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_error())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        response = self._make_request(app)

        events = self._parse_sse_events(response.text)
        error_events = [e[1] for e in events if e[0] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["code"] == "internal_error"
        assert "request_id" in error_events[0]

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_no_cache_headers(self, mock_outcome, mock_handler_fn):
        """Response includes no-cache and no-buffering headers."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_events())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        response = self._make_request(app)

        assert response.headers.get("cache-control") == "no-cache"
        assert response.headers.get("x-accel-buffering") == "no"

    def test_auth_required(self):
        """Endpoint requires auth (no dependency override)."""
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post("/v1/chat/stream", json={"message": "Hello"})
        # Without auth override, the dependency raises — results in 401 or 500
        assert response.status_code in (401, 403, 422, 500)

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_session_id_passthrough(self, mock_outcome, mock_handler_fn):
        """Session ID from request is passed to internal request."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_events())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        self._make_request(app, session_id="my-session-123")

        # Verify the internal request was created with our session ID
        call_args = mock_handler.handle_streaming.call_args
        internal_req = call_args[0][0]
        assert internal_req.session_id == "my-session-123"

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_force_local_passthrough(self, mock_outcome, mock_handler_fn):
        """force_local flag is passed to internal request."""
        mock_handler = AsyncMock()
        mock_handler.handle_streaming = MagicMock(return_value=_mock_streaming_events())
        mock_handler_fn.return_value = mock_handler
        mock_outcome.return_value = AsyncMock()

        app = _create_app()
        self._make_request(app, force_local=True)

        call_args = mock_handler.handle_streaming.call_args
        internal_req = call_args[0][0]
        assert internal_req.force_local is True

    @patch("hestia.api.routes.chat.get_request_handler")
    @patch("hestia.api.routes.chat.get_outcome_manager")
    def test_empty_message_rejected(self, mock_outcome, mock_handler_fn):
        """Empty message is rejected by Pydantic validation."""
        app = _create_app()
        client = TestClient(app, raise_server_exceptions=False)

        response = client.post("/v1/chat/stream", json={"message": ""})
        assert response.status_code == 422  # Validation error
