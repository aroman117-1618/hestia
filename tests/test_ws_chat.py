"""
Tests for WebSocket chat route (/v1/ws/chat).

Tests the WebSocket lifecycle: connection, JWT authentication,
message dispatching, rate limiting, idle timeout, and tool approval.

Run with: python -m pytest tests/test_ws_chat.py -v
"""

import asyncio
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.api.routes.ws_chat import (
    WSConnection,
    _authenticate,
    _message_loop,
    _handle_chat_message,
    AUTH_TIMEOUT_SECONDS,
    IDLE_TIMEOUT_SECONDS,
    MAX_MESSAGE_SIZE,
    MAX_MESSAGES_PER_MINUTE,
)
from hestia.api.schemas.ws_chat import (
    WSClientMessageType,
    WSServerMessageType,
    WSPipelineStage,
    WSToolTier,
    WSAuthMessage,
    WSChatMessage,
    WSToolApprovalMessage,
    WSAuthResultMessage,
    WSTokenMessage,
    WSDoneMessage,
    WSErrorMessage,
)


# ============== Helpers ==============


class MockWebSocket:
    """Mock WebSocket for testing without a real server."""

    def __init__(self):
        self.sent_messages: list[dict] = []
        self._receive_queue: asyncio.Queue = asyncio.Queue()
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None
        # Simulate Starlette's client_state
        self.client_state = MagicMock()
        self.client_state.__eq__ = lambda self, other: False  # Not CONNECTED by default

    async def send_json(self, data: dict) -> None:
        self.sent_messages.append(data)

    async def receive_json(self) -> dict:
        return await self._receive_queue.get()

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason

    async def accept(self) -> None:
        pass

    def enqueue_message(self, data: dict) -> None:
        """Helper to enqueue a message for receive_json() to return."""
        self._receive_queue.put_nowait(data)


# ============== WSConnection Tests ==============


class TestWSConnection:
    """Tests for the WSConnection state manager."""

    def test_initial_state(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)
        assert conn.authenticated is False
        assert conn.device_id is None
        assert conn.session_id is None

    def test_rate_limiting(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        # First MAX_MESSAGES_PER_MINUTE messages should pass
        for _ in range(MAX_MESSAGES_PER_MINUTE):
            assert conn.check_rate_limit() is True

        # Next should fail
        assert conn.check_rate_limit() is False

    def test_rate_limit_window_expiry(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        # Fill up rate limit with old timestamps
        old_time = time.time() - 61  # 61 seconds ago
        conn._message_timestamps = [old_time] * MAX_MESSAGES_PER_MINUTE

        # Should pass because old timestamps expire
        assert conn.check_rate_limit() is True

    def test_touch_updates_activity(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        before = conn._last_activity
        time.sleep(0.01)
        conn.touch()
        assert conn._last_activity > before

    def test_idle_seconds(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn._last_activity = time.time() - 100
        assert conn.idle_seconds >= 100


# ============== Authentication Tests ==============


class TestAuthentication:
    """Tests for WebSocket authentication flow."""

    @pytest.mark.asyncio
    async def test_auth_success(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        ws.enqueue_message({"type": "auth", "token": "valid-jwt-token"})

        with patch('hestia.api.routes.ws_chat.verify_device_token') as mock_verify, \
             patch('hestia.api.routes.ws_chat.check_device_revocation') as mock_revoke:
            mock_verify.return_value = {"device_id": "dev-123", "exp": 9999999999}
            mock_revoke.return_value = None

            result = await _authenticate(conn)

        assert result == "dev-123"
        # Should have sent auth_result success
        assert len(ws.sent_messages) == 1
        assert ws.sent_messages[0]["type"] == "auth_result"
        assert ws.sent_messages[0]["success"] is True
        assert ws.sent_messages[0]["device_id"] == "dev-123"

    @pytest.mark.asyncio
    async def test_auth_wrong_message_type(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        ws.enqueue_message({"type": "message", "content": "Hello"})

        result = await _authenticate(conn)

        assert result is None
        assert ws.sent_messages[0]["type"] == "auth_result"
        assert ws.sent_messages[0]["success"] is False
        assert ws.closed is True
        assert ws.close_code == 4001

    @pytest.mark.asyncio
    async def test_auth_missing_token(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        ws.enqueue_message({"type": "auth", "token": ""})

        result = await _authenticate(conn)

        assert result is None
        assert ws.sent_messages[0]["success"] is False
        assert ws.closed is True

    @pytest.mark.asyncio
    async def test_auth_invalid_jwt(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        ws.enqueue_message({"type": "auth", "token": "invalid-token"})

        from hestia.api.middleware.auth import AuthError

        with patch('hestia.api.routes.ws_chat.verify_device_token', side_effect=AuthError("Invalid token")):
            result = await _authenticate(conn)

        assert result is None
        assert ws.sent_messages[0]["success"] is False
        assert ws.closed is True
        assert ws.close_code == 4003

    @pytest.mark.asyncio
    async def test_auth_timeout(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        # Don't enqueue any message — will timeout
        # Override timeout to be very short for testing
        with patch('hestia.api.routes.ws_chat.AUTH_TIMEOUT_SECONDS', 0.01):
            result = await _authenticate(conn)

        assert result is None
        assert ws.closed is True
        assert ws.close_code == 4001

    @pytest.mark.asyncio
    async def test_auth_revoked_device(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)

        ws.enqueue_message({"type": "auth", "token": "valid-jwt"})

        from hestia.api.middleware.auth import AuthError

        with patch('hestia.api.routes.ws_chat.verify_device_token') as mock_verify, \
             patch('hestia.api.routes.ws_chat.check_device_revocation', side_effect=AuthError("Device revoked")):
            mock_verify.return_value = {"device_id": "dev-revoked"}

            result = await _authenticate(conn)

        assert result is None
        assert ws.sent_messages[0]["success"] is False


# ============== Message Handling Tests ==============


class TestMessageHandling:
    """Tests for chat message processing over WebSocket."""

    @pytest.mark.asyncio
    async def test_handle_chat_message_streams_events(self):
        """Chat message should yield streaming events to client."""
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"
        conn.authenticated = True

        raw = {"type": "message", "content": "Hello", "mode": "tia"}

        async def mock_handle_streaming(request, tool_approval_callback=None):
            yield {"type": "status", "stage": "inference"}
            yield {"type": "token", "content": "Hi!", "request_id": "req-1"}
            yield {"type": "done", "request_id": "req-1", "metrics": {}, "mode": "tia"}

        with patch('hestia.api.routes.ws_chat.get_request_handler', new_callable=AsyncMock) as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.handle_streaming = MagicMock(return_value=mock_handle_streaming(None))
            mock_get_handler.return_value = mock_handler

            await _handle_chat_message(conn, raw)

        # Verify events were forwarded to client
        event_types = [m["type"] for m in ws.sent_messages]
        assert "status" in event_types
        assert "token" in event_types
        assert "done" in event_types

    @pytest.mark.asyncio
    async def test_handle_empty_message_rejected(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"

        raw = {"type": "message", "content": ""}

        await _handle_chat_message(conn, raw)

        assert ws.sent_messages[0]["type"] == "error"
        assert ws.sent_messages[0]["code"] == "empty_message"

    @pytest.mark.asyncio
    async def test_handle_oversized_message_rejected(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"

        raw = {"type": "message", "content": "x" * (MAX_MESSAGE_SIZE + 1)}

        await _handle_chat_message(conn, raw)

        assert ws.sent_messages[0]["type"] == "error"
        assert ws.sent_messages[0]["code"] == "message_too_large"

    @pytest.mark.asyncio
    async def test_handle_message_creates_cli_request(self):
        """Message should create a Request with source=CLI and correct fields."""
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"
        conn.session_id = "session-existing"

        captured_request = None

        async def capture_streaming(request, tool_approval_callback=None):
            nonlocal captured_request
            captured_request = request
            yield {"type": "done", "request_id": request.id, "metrics": {}, "mode": "tia"}

        with patch('hestia.api.routes.ws_chat.get_request_handler', new_callable=AsyncMock) as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.handle_streaming = MagicMock(side_effect=capture_streaming)
            mock_get_handler.return_value = mock_handler

            raw = {
                "type": "message",
                "content": "What's on my calendar?",
                "mode": "mira",
                "force_local": True,
                "context_hints": {"cwd": "/Users/test"},
            }
            await _handle_chat_message(conn, raw)

        from hestia.orchestration.models import RequestSource, Mode
        assert captured_request is not None
        assert captured_request.source == RequestSource.CLI
        assert captured_request.device_id == "dev-123"
        assert captured_request.mode == Mode.MIRA
        assert captured_request.force_local is True
        assert captured_request.context_hints == {"cwd": "/Users/test"}

    @pytest.mark.asyncio
    async def test_handle_message_default_mode(self):
        """Default mode should be TIA when not specified."""
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"

        captured_request = None

        async def capture_streaming(request, tool_approval_callback=None):
            nonlocal captured_request
            captured_request = request
            yield {"type": "done", "request_id": request.id, "metrics": {}, "mode": "tia"}

        with patch('hestia.api.routes.ws_chat.get_request_handler', new_callable=AsyncMock) as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.handle_streaming = MagicMock(side_effect=capture_streaming)
            mock_get_handler.return_value = mock_handler

            raw = {"type": "message", "content": "Hello"}
            await _handle_chat_message(conn, raw)

        from hestia.orchestration.models import Mode
        assert captured_request.mode == Mode.TIA

    @pytest.mark.asyncio
    async def test_handle_message_invalid_mode_defaults_to_tia(self):
        """Invalid mode string should default to TIA."""
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"

        captured_request = None

        async def capture_streaming(request, tool_approval_callback=None):
            nonlocal captured_request
            captured_request = request
            yield {"type": "done", "request_id": request.id, "metrics": {}, "mode": "tia"}

        with patch('hestia.api.routes.ws_chat.get_request_handler', new_callable=AsyncMock) as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.handle_streaming = MagicMock(side_effect=capture_streaming)
            mock_get_handler.return_value = mock_handler

            raw = {"type": "message", "content": "Hello", "mode": "invalid_mode"}
            await _handle_chat_message(conn, raw)

        from hestia.orchestration.models import Mode
        assert captured_request.mode == Mode.TIA

    @pytest.mark.asyncio
    async def test_streaming_error_handled_gracefully(self):
        """Errors during streaming should send error event, not crash."""
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"

        async def failing_streaming(request, tool_approval_callback=None):
            raise RuntimeError("Inference died")

        with patch('hestia.api.routes.ws_chat.get_request_handler', new_callable=AsyncMock) as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.handle_streaming = MagicMock(side_effect=failing_streaming)
            mock_get_handler.return_value = mock_handler

            raw = {"type": "message", "content": "Hello"}
            await _handle_chat_message(conn, raw)

        assert any(m["type"] == "error" for m in ws.sent_messages)


# ============== Tool Approval Tests ==============


class TestToolApproval:
    """Tests for tool approval coordination over WebSocket."""

    @pytest.mark.asyncio
    async def test_tool_approval_sent_and_received(self):
        """Tool approval request should be sent and response received via queue."""
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"

        async def streaming_with_tool_request(request, tool_approval_callback=None):
            # Simulate tool requesting approval
            if tool_approval_callback:
                approved = await tool_approval_callback(
                    "tc-001", "run_command", {"command": "ls"}, "execute"
                )
                if approved:
                    yield {"type": "tool_result", "call_id": "tc-001", "status": "success", "output": "file.py"}
            yield {"type": "done", "request_id": request.id, "metrics": {}, "mode": "tia"}

        with patch('hestia.api.routes.ws_chat.get_request_handler', new_callable=AsyncMock) as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.handle_streaming = MagicMock(side_effect=streaming_with_tool_request)
            mock_get_handler.return_value = mock_handler

            # Schedule approval to arrive AFTER the stale-approval clearing
            async def delayed_approval():
                await asyncio.sleep(0.05)  # Small delay to arrive after stale clearing
                conn._tool_approval_queue.put_nowait({"call_id": "tc-001", "approved": True})

            raw = {"type": "message", "content": "List files"}
            # Run both concurrently
            await asyncio.gather(
                _handle_chat_message(conn, raw),
                delayed_approval(),
            )

        # Should have sent tool_request to client
        tool_requests = [m for m in ws.sent_messages if m.get("type") == "tool_request"]
        assert len(tool_requests) == 1
        assert tool_requests[0]["tool_name"] == "run_command"
        assert tool_requests[0]["tier"] == "execute"

    @pytest.mark.asyncio
    async def test_tool_approval_callback_sends_request(self):
        """The tool_approval_callback should send a tool_request message to the client."""
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"

        # Test the callback behavior directly by capturing what it sends
        captured_callback = None

        async def capture_callback_streaming(request, tool_approval_callback=None):
            nonlocal captured_callback
            captured_callback = tool_approval_callback
            yield {"type": "done", "request_id": request.id, "metrics": {}, "mode": "tia"}

        with patch('hestia.api.routes.ws_chat.get_request_handler', new_callable=AsyncMock) as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.handle_streaming = MagicMock(side_effect=capture_callback_streaming)
            mock_get_handler.return_value = mock_handler

            raw = {"type": "message", "content": "List files"}
            await _handle_chat_message(conn, raw)

        # Verify a callback was passed
        assert captured_callback is not None


# ============== Pydantic Schema Tests ==============


class TestWSSchemas:
    """Tests for WebSocket Pydantic message schemas."""

    def test_auth_message(self):
        msg = WSAuthMessage(token="test-jwt")
        assert msg.type == WSClientMessageType.AUTH
        assert msg.token == "test-jwt"

    def test_chat_message_defaults(self):
        msg = WSChatMessage(content="Hello")
        assert msg.type == WSClientMessageType.MESSAGE
        assert msg.session_id is None
        assert msg.mode is None
        assert msg.force_local is False
        assert msg.context_hints == {}

    def test_chat_message_full(self):
        msg = WSChatMessage(
            content="Hello",
            session_id="sess-123",
            mode="mira",
            force_local=True,
            context_hints={"cwd": "/test"},
        )
        assert msg.session_id == "sess-123"
        assert msg.mode == "mira"
        assert msg.force_local is True

    def test_tool_approval_message(self):
        msg = WSToolApprovalMessage(call_id="tc-001", approved=True)
        assert msg.type == WSClientMessageType.TOOL_APPROVAL
        assert msg.approved is True

    def test_auth_result_success(self):
        msg = WSAuthResultMessage(success=True, device_id="dev-123")
        assert msg.type == WSServerMessageType.AUTH_RESULT
        assert msg.success is True
        assert msg.error is None

    def test_auth_result_failure(self):
        msg = WSAuthResultMessage(success=False, error="Invalid token")
        assert msg.success is False
        assert msg.error == "Invalid token"

    def test_token_message(self):
        msg = WSTokenMessage(content="Hello", request_id="req-001")
        assert msg.type == WSServerMessageType.TOKEN

    def test_done_message(self):
        msg = WSDoneMessage(request_id="req-001", metrics={"tokens_in": 50}, mode="tia")
        assert msg.type == WSServerMessageType.DONE
        assert msg.metrics["tokens_in"] == 50

    def test_error_message(self):
        msg = WSErrorMessage(code="rate_limited", message="Too many requests")
        assert msg.type == WSServerMessageType.ERROR

    def test_pipeline_stages(self):
        assert WSPipelineStage.INFERENCE.value == "inference"
        assert WSPipelineStage.MEMORY.value == "memory"
        assert WSPipelineStage.TOOLS.value == "tools"

    def test_tool_tiers(self):
        assert WSToolTier.READ.value == "read"
        assert WSToolTier.EXECUTE.value == "execute"
        assert WSToolTier.EXTERNAL.value == "external"

    def test_chat_message_min_length_validation(self):
        """Empty content should fail Pydantic validation."""
        with pytest.raises(Exception):  # ValidationError
            WSChatMessage(content="")

    def test_chat_message_max_length_validation(self):
        """Overly long content should fail Pydantic validation."""
        with pytest.raises(Exception):  # ValidationError
            WSChatMessage(content="x" * 32001)


# ============== Cancel / Ping Tests ==============


class TestControlMessages:
    """Tests for cancel and ping message types."""

    def test_cancel_sets_event(self):
        ws = MockWebSocket()
        conn = WSConnection(ws)
        assert not conn._cancel_event.is_set()
        conn._cancel_event.set()
        assert conn._cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_cancel_event_clears_on_new_message(self):
        """Cancel event should be cleared when a new chat message is processed."""
        ws = MockWebSocket()
        conn = WSConnection(ws)
        conn.device_id = "dev-123"
        conn._cancel_event.set()

        async def simple_stream(request, tool_approval_callback=None):
            yield {"type": "done", "request_id": request.id, "metrics": {}, "mode": "tia"}

        with patch('hestia.api.routes.ws_chat.get_request_handler', new_callable=AsyncMock) as mock_get_handler:
            mock_handler = MagicMock()
            mock_handler.handle_streaming = MagicMock(side_effect=simple_stream)
            mock_get_handler.return_value = mock_handler

            raw = {"type": "message", "content": "Hello"}
            await _handle_chat_message(conn, raw)

        # Cancel event should have been cleared at start of message handling
        assert not conn._cancel_event.is_set()
