"""
Tests for session auto-lock (TTL enforcement).

Validates that RequestHandler expires idle conversations and
cleans up stale sessions from the in-memory cache.
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from hestia.orchestration.handler import RequestHandler
from hestia.orchestration.models import Conversation, Mode


# -- Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def handler() -> RequestHandler:
    """Create a RequestHandler with mocked dependencies."""
    h = RequestHandler(
        inference_client=MagicMock(),
        memory_manager=AsyncMock(),
        tool_executor=AsyncMock(),
    )
    return h


def _make_conversation(
    session_id: str = "test-session",
    last_activity_minutes_ago: int = 0,
) -> Conversation:
    """Create a conversation with a controlled last_activity timestamp."""
    conv = Conversation(session_id=session_id)
    conv.last_activity = datetime.now(timezone.utc) - timedelta(
        minutes=last_activity_minutes_ago
    )
    return conv


# -- Session Expiry Detection ──────────────────────────────────────────


class TestSessionExpiry:
    """Tests for _is_session_expired."""

    def test_fresh_session_not_expired(self, handler: RequestHandler):
        """Session with recent activity is not expired."""
        conv = _make_conversation(last_activity_minutes_ago=1)
        assert handler._is_session_expired(conv, timeout_minutes=30) is False

    def test_stale_session_expired(self, handler: RequestHandler):
        """Session idle beyond timeout is expired."""
        conv = _make_conversation(last_activity_minutes_ago=45)
        assert handler._is_session_expired(conv, timeout_minutes=30) is True

    def test_just_under_boundary_not_expired(self, handler: RequestHandler):
        """Session just under the timeout is not expired."""
        conv = _make_conversation(last_activity_minutes_ago=29)
        assert handler._is_session_expired(conv, timeout_minutes=30) is False

    def test_custom_timeout(self, handler: RequestHandler):
        """Custom timeout is respected."""
        conv = _make_conversation(last_activity_minutes_ago=10)
        assert handler._is_session_expired(conv, timeout_minutes=5) is True
        assert handler._is_session_expired(conv, timeout_minutes=15) is False


# -- TTL-Aware Conversation Retrieval ──────────────────────────────────


class TestConversationWithTTL:
    """Tests for _get_or_create_conversation_with_ttl."""

    @pytest.mark.asyncio
    async def test_creates_new_session(self, handler: RequestHandler):
        """Creates a conversation when none exists."""
        with patch.object(handler, "_get_session_timeout", return_value=30):
            conv = await handler._get_or_create_conversation_with_ttl("new-session")
        assert conv.session_id == "new-session"
        assert "new-session" in handler._conversations

    @pytest.mark.asyncio
    async def test_returns_existing_active_session(self, handler: RequestHandler):
        """Returns existing conversation if still active."""
        existing = _make_conversation("active-session", last_activity_minutes_ago=5)
        handler._conversations["active-session"] = existing

        with patch.object(handler, "_get_session_timeout", return_value=30):
            conv = await handler._get_or_create_conversation_with_ttl("active-session")
        assert conv is existing

    @pytest.mark.asyncio
    async def test_expires_stale_session(self, handler: RequestHandler):
        """Expired session is replaced with a fresh one."""
        stale = _make_conversation("stale-session", last_activity_minutes_ago=45)
        stale.turn_count = 10
        handler._conversations["stale-session"] = stale

        with patch.object(handler, "_get_session_timeout", return_value=30):
            conv = await handler._get_or_create_conversation_with_ttl("stale-session")
        assert conv is not stale
        assert conv.turn_count == 0
        assert conv.session_id == "stale-session"


# -- Session Cleanup ───────────────────────────────────────────────────


class TestSessionCleanup:
    """Tests for _cleanup_expired_sessions."""

    def test_cleanup_removes_expired(self, handler: RequestHandler):
        """Expired sessions are evicted."""
        handler._conversations["old"] = _make_conversation(
            "old", last_activity_minutes_ago=60
        )
        handler._conversations["fresh"] = _make_conversation(
            "fresh", last_activity_minutes_ago=5
        )

        evicted = handler._cleanup_expired_sessions(timeout_minutes=30)
        assert evicted == 1
        assert "old" not in handler._conversations
        assert "fresh" in handler._conversations

    def test_cleanup_no_expired(self, handler: RequestHandler):
        """No sessions evicted when all are active."""
        handler._conversations["a"] = _make_conversation("a", last_activity_minutes_ago=1)
        handler._conversations["b"] = _make_conversation("b", last_activity_minutes_ago=10)

        evicted = handler._cleanup_expired_sessions(timeout_minutes=30)
        assert evicted == 0
        assert len(handler._conversations) == 2

    def test_cleanup_empty_cache(self, handler: RequestHandler):
        """Cleanup on empty cache does nothing."""
        evicted = handler._cleanup_expired_sessions(timeout_minutes=30)
        assert evicted == 0

    def test_cleanup_all_expired(self, handler: RequestHandler):
        """All sessions evicted when all are stale."""
        for i in range(5):
            handler._conversations[f"s{i}"] = _make_conversation(
                f"s{i}", last_activity_minutes_ago=120
            )

        evicted = handler._cleanup_expired_sessions(timeout_minutes=30)
        assert evicted == 5
        assert len(handler._conversations) == 0


# -- Timeout Fallback ──────────────────────────────────────────────────


class TestTimeoutFallback:
    """Tests for _get_session_timeout."""

    @pytest.mark.asyncio
    async def test_default_timeout_on_error(self, handler: RequestHandler):
        """Falls back to default when user manager unavailable."""
        with patch(
            "hestia.user.get_user_manager",
            side_effect=Exception("not available"),
        ):
            timeout = await handler._get_session_timeout()
        assert timeout == handler._DEFAULT_SESSION_TIMEOUT

    @pytest.mark.asyncio
    async def test_custom_timeout_from_settings(self, handler: RequestHandler):
        """Uses auto_lock_timeout_minutes from user settings."""
        mock_settings = MagicMock()
        mock_settings.auto_lock_timeout_minutes = 15

        mock_manager = AsyncMock()
        mock_manager.get_settings = AsyncMock(return_value=mock_settings)

        with patch(
            "hestia.user.get_user_manager",
            return_value=mock_manager,
        ):
            timeout = await handler._get_session_timeout()
        assert timeout == 15
