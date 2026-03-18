"""
Tests for the notification relay module.

Covers models, database CRUD, router decisions, and manager lifecycle.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hestia.notifications.models import (
    BumpRequest,
    BumpStatus,
    NotificationRoute,
    NotificationSettings,
)
from hestia.notifications.database import NotificationDatabase
from hestia.notifications.router import NotificationRouter
from hestia.notifications.manager import NotificationManager


# =============================================================================
# Model Tests
# =============================================================================


class TestBumpRequest:
    """Tests for BumpRequest dataclass."""

    def test_create_defaults(self) -> None:
        bump = BumpRequest.create(title="Deploy?")
        assert bump.title == "Deploy?"
        assert bump.status == BumpStatus.PENDING
        assert bump.actions == ["approve", "deny"]
        assert bump.priority == "medium"
        assert bump.user_id == "default"
        assert bump.callback_id  # UUID generated
        assert bump.id != bump.callback_id

    def test_create_with_params(self) -> None:
        bump = BumpRequest.create(
            title="Restart server?",
            body="The server needs a restart after deploy.",
            priority="high",
            actions=["approve", "deny", "defer"],
            context={"command": "deploy"},
            session_id="session-123",
            user_id="andrew",
        )
        assert bump.title == "Restart server?"
        assert bump.body == "The server needs a restart after deploy."
        assert bump.priority == "high"
        assert len(bump.actions) == 3
        assert bump.context["command"] == "deploy"
        assert bump.session_id == "session-123"

    def test_to_dict(self) -> None:
        bump = BumpRequest.create(title="Test")
        d = bump.to_dict()
        assert d["title"] == "Test"
        assert d["status"] == "pending"
        assert d["callbackId"] == bump.callback_id
        assert d["route"] is None

    def test_from_dict_roundtrip(self) -> None:
        bump = BumpRequest.create(title="Roundtrip", body="test body")
        d = bump.to_dict()
        restored = BumpRequest.from_dict(d)
        assert restored.title == bump.title
        assert restored.body == bump.body
        assert restored.callback_id == bump.callback_id
        assert restored.status == bump.status


class TestNotificationSettings:
    """Tests for NotificationSettings dataclass."""

    def test_defaults(self) -> None:
        s = NotificationSettings()
        assert s.idle_threshold_seconds == 120
        assert s.rate_limit_seconds == 300
        assert s.bump_expiry_seconds == 900
        assert s.quiet_hours_start == "22:00"
        assert s.quiet_hours_end == "08:00"

    def test_to_dict_roundtrip(self) -> None:
        s = NotificationSettings(idle_threshold_seconds=60, quiet_hours_enabled=False)
        d = s.to_dict()
        restored = NotificationSettings.from_dict(d)
        assert restored.idle_threshold_seconds == 60
        assert restored.quiet_hours_enabled is False


# =============================================================================
# Database Tests
# =============================================================================


@pytest.fixture
async def db(tmp_path):
    """Create an in-memory notification database."""
    database = NotificationDatabase()
    database.db_path = tmp_path / "test_notifications.db"
    await database.connect()
    yield database
    await database.close()


class TestNotificationDatabase:
    """Tests for NotificationDatabase CRUD."""

    @pytest.mark.asyncio
    async def test_create_and_get_bump(self, db: NotificationDatabase) -> None:
        bump = BumpRequest.create(title="Test bump")
        await db.create_bump(bump)

        found = await db.get_bump_by_callback(bump.callback_id)
        assert found is not None
        assert found.title == "Test bump"
        assert found.status == BumpStatus.PENDING

    @pytest.mark.asyncio
    async def test_update_bump_status_approved(self, db: NotificationDatabase) -> None:
        bump = BumpRequest.create(title="Approve me")
        await db.create_bump(bump)

        updated = await db.update_bump_status(
            bump.callback_id, BumpStatus.APPROVED, response_action="approve"
        )
        assert updated is True

        found = await db.get_bump_by_callback(bump.callback_id)
        assert found.status == BumpStatus.APPROVED
        assert found.response_action == "approve"
        assert found.responded_at is not None

    @pytest.mark.asyncio
    async def test_update_bump_status_expired(self, db: NotificationDatabase) -> None:
        bump = BumpRequest.create(title="Expire me")
        await db.create_bump(bump)

        await db.update_bump_status(bump.callback_id, BumpStatus.EXPIRED)

        found = await db.get_bump_by_callback(bump.callback_id)
        assert found.status == BumpStatus.EXPIRED
        assert found.expired_at is not None

    @pytest.mark.asyncio
    async def test_list_bumps(self, db: NotificationDatabase) -> None:
        for i in range(5):
            bump = BumpRequest.create(title=f"Bump {i}")
            await db.create_bump(bump)

        bumps = await db.list_bumps()
        assert len(bumps) == 5

    @pytest.mark.asyncio
    async def test_list_bumps_with_status_filter(self, db: NotificationDatabase) -> None:
        b1 = BumpRequest.create(title="Pending")
        b2 = BumpRequest.create(title="Approved")
        await db.create_bump(b1)
        await db.create_bump(b2)
        await db.update_bump_status(b2.callback_id, BumpStatus.APPROVED)

        pending = await db.list_bumps(status=BumpStatus.PENDING)
        assert len(pending) == 1
        assert pending[0].title == "Pending"

    @pytest.mark.asyncio
    async def test_count_bumps(self, db: NotificationDatabase) -> None:
        for _ in range(3):
            await db.create_bump(BumpRequest.create(title="Count"))
        assert await db.count_bumps() == 3

    @pytest.mark.asyncio
    async def test_update_bump_route(self, db: NotificationDatabase) -> None:
        bump = BumpRequest.create(title="Route me")
        await db.create_bump(bump)

        await db.update_bump_route(bump.callback_id, NotificationRoute.MACOS)
        found = await db.get_bump_by_callback(bump.callback_id)
        assert found.route == NotificationRoute.MACOS

    @pytest.mark.asyncio
    async def test_get_bump_not_found(self, db: NotificationDatabase) -> None:
        found = await db.get_bump_by_callback("nonexistent")
        assert found is None

    @pytest.mark.asyncio
    async def test_settings_defaults(self, db: NotificationDatabase) -> None:
        settings = await db.get_settings()
        assert settings.idle_threshold_seconds == 120
        assert settings.user_id == "default"

    @pytest.mark.asyncio
    async def test_settings_save_and_load(self, db: NotificationDatabase) -> None:
        settings = NotificationSettings(
            idle_threshold_seconds=60,
            rate_limit_seconds=120,
            quiet_hours_enabled=False,
        )
        await db.save_settings(settings)

        loaded = await db.get_settings()
        assert loaded.idle_threshold_seconds == 60
        assert loaded.rate_limit_seconds == 120
        assert loaded.quiet_hours_enabled is False

    @pytest.mark.asyncio
    async def test_settings_upsert(self, db: NotificationDatabase) -> None:
        s1 = NotificationSettings(idle_threshold_seconds=60)
        await db.save_settings(s1)

        s2 = NotificationSettings(idle_threshold_seconds=180)
        await db.save_settings(s2)

        loaded = await db.get_settings()
        assert loaded.idle_threshold_seconds == 180

    @pytest.mark.asyncio
    async def test_rate_limit_recent_bump(self, db: NotificationDatabase) -> None:
        bump = BumpRequest.create(title="Rate limit", session_id="sess-1")
        await db.create_bump(bump)

        recent = await db.get_recent_bump_for_session("sess-1", seconds=300)
        assert recent is not None
        assert recent.callback_id == bump.callback_id

        # Different session should return None
        recent_other = await db.get_recent_bump_for_session("sess-2", seconds=300)
        assert recent_other is None

    @pytest.mark.asyncio
    async def test_expire_old_bumps(self, db: NotificationDatabase) -> None:
        # Create a bump, then expire with 0-second threshold (expire all)
        bump = BumpRequest.create(title="Old bump")
        await db.create_bump(bump)

        # Artificially set created_at to the past
        past = (datetime.now(timezone.utc) - timedelta(hours=1))
        bare_utc = past.strftime("%Y-%m-%d %H:%M:%S")
        await db.connection.execute(
            "UPDATE bump_requests SET created_at = ? WHERE id = ?",
            (bare_utc, bump.id),
        )
        await db.connection.commit()

        expired = await db.expire_old_bumps(expiry_seconds=60)
        assert expired == 1

        found = await db.get_bump_by_callback(bump.callback_id)
        assert found.status == BumpStatus.EXPIRED


# =============================================================================
# Router Tests
# =============================================================================


class TestNotificationRouter:
    """Tests for notification routing decisions."""

    @pytest.fixture
    def settings(self) -> NotificationSettings:
        return NotificationSettings(
            quiet_hours_enabled=False,  # Disable for most tests
            focus_mode_respect=False,   # Disable for most tests
        )

    @pytest.fixture
    async def router_with_db(self, db: NotificationDatabase):
        return NotificationRouter(db)

    @pytest.mark.asyncio
    async def test_routes_to_macos_when_active(
        self, router_with_db: NotificationRouter, settings: NotificationSettings
    ) -> None:
        bump = BumpRequest.create(title="Active test")

        with patch("hestia.notifications.router.get_idle_seconds", return_value=10.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                route, reason = await router_with_db.route(bump, settings)

        assert route == NotificationRoute.MACOS
        assert reason == "active"

    @pytest.mark.asyncio
    async def test_routes_to_apns_when_idle(
        self, router_with_db: NotificationRouter, settings: NotificationSettings
    ) -> None:
        bump = BumpRequest.create(title="Idle test")

        with patch("hestia.notifications.router.get_idle_seconds", return_value=300.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                route, reason = await router_with_db.route(bump, settings)

        assert route == NotificationRoute.APNS
        assert reason == "idle"

    @pytest.mark.asyncio
    async def test_rate_limiting(
        self, router_with_db: NotificationRouter, db: NotificationDatabase,
        settings: NotificationSettings,
    ) -> None:
        # Create a recent bump for the session
        existing = BumpRequest.create(title="First", session_id="sess-1")
        await db.create_bump(existing)

        # Second bump in same session should be suppressed
        new_bump = BumpRequest.create(title="Second", session_id="sess-1")

        with patch("hestia.notifications.router.get_idle_seconds", return_value=10.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                route, reason = await router_with_db.route(new_bump, settings)

        assert route == NotificationRoute.SUPPRESSED
        assert reason == "rate_limited"

    @pytest.mark.asyncio
    async def test_quiet_hours_suppresses(
        self, router_with_db: NotificationRouter,
    ) -> None:
        settings = NotificationSettings(
            quiet_hours_enabled=True,
            focus_mode_respect=False,
        )
        bump = BumpRequest.create(title="Late night")

        # Patch the time check to be in quiet hours
        with patch.object(router_with_db, "_is_quiet_hours", return_value=True):
            route, reason = await router_with_db.route(bump, settings)

        assert route == NotificationRoute.SUPPRESSED
        assert reason == "quiet_hours"

    @pytest.mark.asyncio
    async def test_urgent_overrides_quiet_hours(
        self, router_with_db: NotificationRouter,
    ) -> None:
        settings = NotificationSettings(
            quiet_hours_enabled=True,
            focus_mode_respect=False,
        )
        bump = BumpRequest.create(title="Urgent!", priority="urgent")

        with patch.object(router_with_db, "_is_quiet_hours", return_value=True):
            with patch("hestia.notifications.router.get_idle_seconds", return_value=10.0):
                with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                    route, reason = await router_with_db.route(bump, settings)

        assert route == NotificationRoute.MACOS
        assert reason == "active"

    @pytest.mark.asyncio
    async def test_focus_mode_suppresses(
        self, router_with_db: NotificationRouter,
    ) -> None:
        settings = NotificationSettings(
            quiet_hours_enabled=False,
            focus_mode_respect=True,
        )
        bump = BumpRequest.create(title="Focus test")

        with patch("hestia.notifications.router.is_focus_mode_active", return_value=True):
            route, reason = await router_with_db.route(bump, settings)

        assert route == NotificationRoute.SUPPRESSED
        assert reason == "focus_mode"

    @pytest.mark.asyncio
    async def test_session_cooldown(
        self, router_with_db: NotificationRouter, db: NotificationDatabase,
        settings: NotificationSettings,
    ) -> None:
        # Create an already-responded bump
        responded = BumpRequest.create(title="Done", session_id="sess-cool")
        responded.status = BumpStatus.APPROVED
        responded.responded_at = datetime.now(timezone.utc)
        await db.create_bump(responded)
        await db.update_bump_status(
            responded.callback_id, BumpStatus.APPROVED, response_action="approve"
        )

        # New bump should be suppressed by cooldown
        new_bump = BumpRequest.create(title="New", session_id="sess-cool")

        with patch("hestia.notifications.router.get_idle_seconds", return_value=10.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                route, reason = await router_with_db.route(new_bump, settings)

        assert route == NotificationRoute.SUPPRESSED
        assert reason == "session_cooldown"


# =============================================================================
# Manager Tests
# =============================================================================


class TestNotificationManager:
    """Tests for NotificationManager orchestration."""

    @pytest.fixture
    async def manager(self, tmp_path):
        mgr = NotificationManager()
        mgr._database = NotificationDatabase()
        mgr._database.db_path = tmp_path / "test_mgr_notifications.db"
        await mgr._database.connect()
        mgr._router = NotificationRouter(mgr._database)
        mgr._apns_client = None
        mgr._initialized = True
        yield mgr
        await mgr.close()

    @pytest.mark.asyncio
    async def test_create_bump_routes_to_macos(self, manager: NotificationManager) -> None:
        with patch("hestia.notifications.router.get_idle_seconds", return_value=5.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                with patch("hestia.notifications.manager.send_macos_notification", return_value=True) as mock_notify:
                    result = await manager.create_bump(
                        title="Test macOS delivery",
                        body="Should go to macOS",
                    )

        assert result["route"] == "macos"
        assert result["delivered"] is True
        mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_bump_suppressed(self, manager: NotificationManager) -> None:
        # Create a bump with rate limiting
        with patch("hestia.notifications.router.get_idle_seconds", return_value=5.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                with patch("hestia.notifications.manager.send_macos_notification", return_value=True):
                    await manager.create_bump(title="First", session_id="sess-rl")

        # Second should be suppressed
        result = await manager.create_bump(title="Second", session_id="sess-rl")
        assert result["route"] == "suppressed"

    @pytest.mark.asyncio
    async def test_get_bump_status(self, manager: NotificationManager) -> None:
        with patch("hestia.notifications.router.get_idle_seconds", return_value=5.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                with patch("hestia.notifications.manager.send_macos_notification", return_value=True):
                    result = await manager.create_bump(title="Status check")

        status = await manager.get_bump_status(result["callbackId"])
        assert status is not None
        assert status["status"] == "pending"

    @pytest.mark.asyncio
    async def test_respond_to_bump(self, manager: NotificationManager) -> None:
        with patch("hestia.notifications.router.get_idle_seconds", return_value=5.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                with patch("hestia.notifications.manager.send_macos_notification", return_value=True):
                    result = await manager.create_bump(title="Respond test")

        response = await manager.respond_to_bump(result["callbackId"], "approve")
        assert response["status"] == "approved"
        assert response["responseAction"] == "approve"

    @pytest.mark.asyncio
    async def test_respond_already_responded(self, manager: NotificationManager) -> None:
        with patch("hestia.notifications.router.get_idle_seconds", return_value=5.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                with patch("hestia.notifications.manager.send_macos_notification", return_value=True):
                    result = await manager.create_bump(title="Double respond")

        await manager.respond_to_bump(result["callbackId"], "approve")
        response2 = await manager.respond_to_bump(result["callbackId"], "deny")
        assert response2["error"] == "already_responded"

    @pytest.mark.asyncio
    async def test_respond_invalid_action(self, manager: NotificationManager) -> None:
        with patch("hestia.notifications.router.get_idle_seconds", return_value=5.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                with patch("hestia.notifications.manager.send_macos_notification", return_value=True):
                    result = await manager.create_bump(title="Invalid action test")

        response = await manager.respond_to_bump(result["callbackId"], "snooze")
        assert response["error"] == "invalid_action"

        # Bump should still be pending
        status = await manager.get_bump_status(result["callbackId"])
        assert status["status"] == "pending"

    @pytest.mark.asyncio
    async def test_list_bumps(self, manager: NotificationManager) -> None:
        with patch("hestia.notifications.router.get_idle_seconds", return_value=5.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                with patch("hestia.notifications.manager.send_macos_notification", return_value=True):
                    for i in range(3):
                        await manager.create_bump(title=f"List {i}", session_id=f"sess-{i}")

        result = await manager.list_bumps()
        assert result["total"] == 3
        assert len(result["bumps"]) == 3

    @pytest.mark.asyncio
    async def test_get_and_update_settings(self, manager: NotificationManager) -> None:
        settings = await manager.get_settings()
        assert settings["idleThresholdSeconds"] == 120

        updated = await manager.update_settings("default", {"idleThresholdSeconds": 60})
        assert updated["idleThresholdSeconds"] == 60

    @pytest.mark.asyncio
    async def test_bump_not_found(self, manager: NotificationManager) -> None:
        status = await manager.get_bump_status("nonexistent")
        assert status is None

        response = await manager.respond_to_bump("nonexistent", "approve")
        assert response is None

    @pytest.mark.asyncio
    async def test_apns_fallback_to_macos(self, manager: NotificationManager) -> None:
        """When APNs is unavailable, idle bumps should fall back to macOS."""
        with patch("hestia.notifications.router.get_idle_seconds", return_value=300.0):
            with patch("hestia.notifications.router.is_focus_mode_active", return_value=False):
                with patch("hestia.notifications.manager.send_macos_notification", return_value=True) as mock_notify:
                    result = await manager.create_bump(title="Fallback test")

        # Route should initially be APNS, but fallback to MACOS
        assert result["delivered"] is True
        mock_notify.assert_called_once()


# =============================================================================
# Idle Detector Tests
# =============================================================================


class TestIdleDetector:
    """Tests for macOS idle time detection."""

    @pytest.mark.asyncio
    async def test_get_idle_seconds_parses_output(self) -> None:
        mock_stdout = b'"HIDIdleTime" = 5000000000'  # 5 seconds
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(mock_stdout, b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            from hestia.notifications.idle_detector import get_idle_seconds
            result = await get_idle_seconds()

        assert abs(result - 5.0) < 0.01

    @pytest.mark.asyncio
    async def test_get_idle_seconds_returns_zero_on_error(self) -> None:
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("failed")):
            from hestia.notifications.idle_detector import get_idle_seconds
            result = await get_idle_seconds()

        assert result == 0.0


# =============================================================================
# macOS Notifier Tests
# =============================================================================


class TestMacOSNotifier:
    """Tests for macOS notification delivery."""

    @pytest.mark.asyncio
    async def test_send_notification_success(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            from hestia.notifications.macos_notifier import send_macos_notification
            result = await send_macos_notification(
                title="Test", body="Hello", subtitle="Sub"
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_notification_failure(self) -> None:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            from hestia.notifications.macos_notifier import send_macos_notification
            result = await send_macos_notification(title="Fail")

        assert result is False

    def test_escape_applescript(self) -> None:
        from hestia.notifications.macos_notifier import _escape_applescript
        assert _escape_applescript('Hello "world"') == 'Hello \\"world\\"'
        assert _escape_applescript("back\\slash") == "back\\\\slash"


# =============================================================================
# APNs Client Tests
# =============================================================================


class TestAPNsClient:
    """Tests for APNs client."""

    def test_jwt_token_generation(self, tmp_path) -> None:
        # Create a fake ES256 key for testing
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization

        private_key = ec.generate_private_key(ec.SECP256R1())
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        key_file = tmp_path / "AuthKey_TEST.p8"
        key_file.write_bytes(pem)

        from hestia.notifications.apns_client import APNsClient
        client = APNsClient(
            key_id="TESTKEY123",
            team_id="TEAMID456",
            key_path=str(key_file),
        )

        token = client._get_jwt_token()
        assert token is not None
        assert len(token) > 50

        # Second call should return cached token
        token2 = client._get_jwt_token()
        assert token2 == token

    def test_key_file_not_found(self) -> None:
        from hestia.notifications.apns_client import APNsClient
        client = APNsClient(
            key_id="TEST",
            team_id="TEAM",
            key_path="/nonexistent/key.p8",
        )

        with pytest.raises(FileNotFoundError):
            client._load_key()
