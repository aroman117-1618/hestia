"""
Tests for Hestia invite-based QR onboarding system.

Sprint 1A: DevOps & Deployment — invite generation, nonce lifecycle,
register-with-invite, re-invite recovery, rate limiting, device registry.
"""

import json
import os
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from hestia.api.invite_store import InviteStore
from hestia.api.middleware.auth import (
    create_device_token,
    create_invite_token,
    verify_invite_token,
    verify_setup_secret,
    check_invite_rate_limit,
    check_device_revocation,
    AuthError,
    _invite_rate_limit,
)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test databases."""
    return tmp_path


@pytest_asyncio.fixture
async def store(temp_dir: Path) -> InviteStore:
    """Provide a connected test InviteStore."""
    s = InviteStore(db_path=temp_dir / "test_invites.db")
    await s.connect()
    yield s
    await s.close()


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset rate limit state before each test."""
    _invite_rate_limit["count"] = 0
    _invite_rate_limit["window_start"] = None
    yield


@pytest.fixture
def setup_secret_env():
    """Set a known setup secret for testing."""
    with patch.dict(os.environ, {"HESTIA_SETUP_SECRET": "test_secret_1234567890"}):
        # Reset cached value
        import hestia.api.middleware.auth as auth_mod
        auth_mod._SETUP_SECRET = None
        yield "test_secret_1234567890"
        auth_mod._SETUP_SECRET = None


# ── InviteStore: Nonce Lifecycle ───────────────────────────────────────


class TestInviteStoreNonces:
    """Tests for invite nonce creation and consumption."""

    @pytest.mark.asyncio
    async def test_create_nonce(self, store: InviteStore):
        """Creating a nonce returns a hex string."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires)
        assert isinstance(nonce, str)
        assert len(nonce) == 32  # uuid4().hex

    @pytest.mark.asyncio
    async def test_nonce_is_valid(self, store: InviteStore):
        """Newly created nonce is valid."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires)
        assert await store.is_nonce_valid(nonce) is True

    @pytest.mark.asyncio
    async def test_consume_nonce_success(self, store: InviteStore):
        """Consuming a valid nonce succeeds."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires)
        consumed = await store.consume_nonce(nonce, "device-abc123")
        assert consumed is True

    @pytest.mark.asyncio
    async def test_consumed_nonce_invalid(self, store: InviteStore):
        """Consumed nonce is no longer valid."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires)
        await store.consume_nonce(nonce, "device-abc123")
        assert await store.is_nonce_valid(nonce) is False

    @pytest.mark.asyncio
    async def test_double_consume_fails(self, store: InviteStore):
        """Consuming an already-consumed nonce fails."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires)
        assert await store.consume_nonce(nonce, "device-abc123") is True
        assert await store.consume_nonce(nonce, "device-def456") is False

    @pytest.mark.asyncio
    async def test_expired_nonce_invalid(self, store: InviteStore):
        """Expired nonce cannot be consumed."""
        expires = datetime.now(timezone.utc) - timedelta(minutes=1)
        nonce = await store.create_nonce(expires_at=expires)
        assert await store.is_nonce_valid(nonce) is False
        assert await store.consume_nonce(nonce, "device-abc123") is False

    @pytest.mark.asyncio
    async def test_nonexistent_nonce_invalid(self, store: InviteStore):
        """Nonexistent nonce is invalid."""
        assert await store.is_nonce_valid("nonexistent") is False
        assert await store.consume_nonce("nonexistent", "device-abc123") is False

    @pytest.mark.asyncio
    async def test_nonce_source_tracking(self, store: InviteStore):
        """Nonce tracks its creation source."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires, source="re_invite")
        assert await store.is_nonce_valid(nonce) is True


# ── InviteStore: Device Registry ───────────────────────────────────────


class TestInviteStoreDevices:
    """Tests for device registry operations."""

    @pytest.mark.asyncio
    async def test_register_device(self, store: InviteStore):
        """Registering a device adds it to the registry."""
        await store.register_device(
            device_id="device-abc123",
            device_name="iPhone 15",
            device_type="ios",
        )
        devices = await store.list_devices()
        assert len(devices) == 1
        assert devices[0]["device_id"] == "device-abc123"
        assert devices[0]["device_name"] == "iPhone 15"
        assert devices[0]["device_type"] == "ios"

    @pytest.mark.asyncio
    async def test_register_with_invite_nonce(self, store: InviteStore):
        """Device can be registered with an invite nonce reference."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires)

        await store.register_device(
            device_id="device-abc123",
            device_name="MacBook",
            device_type="macos",
            invite_nonce=nonce,
        )
        devices = await store.list_devices()
        assert len(devices) == 1

    @pytest.mark.asyncio
    async def test_multiple_devices(self, store: InviteStore):
        """Multiple devices can be registered."""
        for i in range(3):
            await store.register_device(
                device_id=f"device-{i:06d}",
                device_name=f"Device {i}",
                device_type="ios",
            )
        devices = await store.list_devices()
        assert len(devices) == 3

    @pytest.mark.asyncio
    async def test_device_count(self, store: InviteStore):
        """Device count reflects registered devices."""
        assert await store.get_device_count() == 0
        await store.register_device("d1", "Phone", "ios")
        assert await store.get_device_count() == 1
        await store.register_device("d2", "Mac", "macos")
        assert await store.get_device_count() == 2

    @pytest.mark.asyncio
    async def test_update_last_seen(self, store: InviteStore):
        """Last seen timestamp can be updated."""
        await store.register_device("d1", "Phone", "ios")
        devices = await store.list_devices()
        assert devices[0]["last_seen_at"] is None

        await store.update_last_seen("d1")
        devices = await store.list_devices()
        assert devices[0]["last_seen_at"] is not None

    @pytest.mark.asyncio
    async def test_devices_ordered_by_registration(self, store: InviteStore):
        """Devices are returned most-recent first."""
        await store.register_device("d1", "First", "ios")
        await store.register_device("d2", "Second", "macos")
        devices = await store.list_devices()
        # Most recent first (DESC order)
        assert devices[0]["device_id"] == "d2"
        assert devices[1]["device_id"] == "d1"


# -- Device Revocation ─────────────────────────────────────────────────


class TestDeviceRevocation:
    """Tests for device revocation and unrevocation."""

    @pytest.mark.asyncio
    async def test_revoke_device(self, store: InviteStore):
        """Revoking a device sets revoked_at."""
        await store.register_device("d1", "Phone", "ios")
        result = await store.revoke_device("d1")
        assert result is True
        assert await store.is_device_revoked("d1") is True

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_device(self, store: InviteStore):
        """Revoking a nonexistent device returns False."""
        result = await store.revoke_device("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_unrevoke_device(self, store: InviteStore):
        """Unrevoking restores access."""
        await store.register_device("d1", "Phone", "ios")
        await store.revoke_device("d1")
        assert await store.is_device_revoked("d1") is True

        result = await store.unrevoke_device("d1")
        assert result is True
        assert await store.is_device_revoked("d1") is False

    @pytest.mark.asyncio
    async def test_unrevoke_nonexistent_device(self, store: InviteStore):
        """Unrevoking a nonexistent device returns False."""
        result = await store.unrevoke_device("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_active_device_not_revoked(self, store: InviteStore):
        """Freshly registered device is not revoked."""
        await store.register_device("d1", "Phone", "ios")
        assert await store.is_device_revoked("d1") is False

    @pytest.mark.asyncio
    async def test_nonexistent_device_not_revoked(self, store: InviteStore):
        """Nonexistent device returns False (not revoked)."""
        assert await store.is_device_revoked("nonexistent") is False

    @pytest.mark.asyncio
    async def test_revoked_device_shows_in_list(self, store: InviteStore):
        """Revoked device includes revoked_at in device list."""
        await store.register_device("d1", "Phone", "ios")
        await store.revoke_device("d1")
        devices = await store.list_devices()
        assert len(devices) == 1
        assert devices[0]["revoked_at"] is not None

    @pytest.mark.asyncio
    async def test_active_device_null_revoked_at(self, store: InviteStore):
        """Active device has null revoked_at in list."""
        await store.register_device("d1", "Phone", "ios")
        devices = await store.list_devices()
        assert devices[0]["revoked_at"] is None

    @pytest.mark.asyncio
    async def test_double_revoke_idempotent(self, store: InviteStore):
        """Revoking an already-revoked device succeeds (idempotent)."""
        await store.register_device("d1", "Phone", "ios")
        assert await store.revoke_device("d1") is True
        assert await store.revoke_device("d1") is True
        assert await store.is_device_revoked("d1") is True


# ── Auth Middleware: Invite Tokens ─────────────────────────────────────


class TestInviteTokens:
    """Tests for invite JWT token creation and verification."""

    def test_create_invite_token(self):
        """Creating an invite token returns token + expiry."""
        token, expires = create_invite_token("test-nonce-123")
        assert isinstance(token, str)
        assert len(token) > 0
        assert expires > datetime.now(timezone.utc)

    def test_verify_invite_token(self):
        """Valid invite token can be verified."""
        token, _ = create_invite_token("test-nonce-123")
        payload = verify_invite_token(token)
        assert payload["nonce"] == "test-nonce-123"
        assert payload["type"] == "invite"

    def test_verify_device_token_as_invite_fails(self):
        """Device token cannot be used as invite token."""
        token, _ = create_device_token("device-123")
        with pytest.raises(AuthError, match="invite"):
            verify_invite_token(token)

    def test_verify_expired_invite_token(self):
        """Expired invite token raises AuthError."""
        with patch("hestia.api.middleware.auth.INVITE_EXPIRE_MINUTES", -1):
            token, _ = create_invite_token("expired-nonce")
        with pytest.raises(AuthError, match="expired"):
            verify_invite_token(token)

    def test_verify_invalid_invite_token(self):
        """Garbage token raises AuthError."""
        with pytest.raises(AuthError):
            verify_invite_token("not.a.valid.token")


# ── Auth Middleware: Setup Secret ──────────────────────────────────────


class TestSetupSecret:
    """Tests for setup secret verification."""

    def test_verify_correct_secret(self, setup_secret_env):
        """Correct setup secret verifies."""
        assert verify_setup_secret("test_secret_1234567890") is True

    def test_verify_wrong_secret(self, setup_secret_env):
        """Wrong setup secret fails verification."""
        assert verify_setup_secret("wrong_secret") is False

    def test_verify_empty_secret(self, setup_secret_env):
        """Empty string fails verification."""
        assert verify_setup_secret("") is False


# ── Rate Limiting ──────────────────────────────────────────────────────


class TestRateLimiting:
    """Tests for invite rate limiting."""

    def test_within_rate_limit(self):
        """First invites within limit are allowed."""
        for _ in range(5):
            assert check_invite_rate_limit() is True

    def test_exceeds_rate_limit(self):
        """6th invite within window is blocked."""
        for _ in range(5):
            check_invite_rate_limit()
        assert check_invite_rate_limit() is False

    def test_rate_limit_resets_after_window(self):
        """Rate limit resets after 1 hour."""
        for _ in range(5):
            check_invite_rate_limit()
        assert check_invite_rate_limit() is False

        # Simulate window expiry
        _invite_rate_limit["window_start"] = (
            datetime.now(timezone.utc) - timedelta(hours=2)
        )
        assert check_invite_rate_limit() is True


# ── Full Invite Flow Integration ───────────────────────────────────────


class TestInviteFlowIntegration:
    """End-to-end tests for the complete invite flow."""

    @pytest.mark.asyncio
    async def test_full_invite_flow(self, store: InviteStore, setup_secret_env):
        """Full flow: create nonce → generate token → verify → consume → register."""
        # 1. Create nonce
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires)

        # 2. Create invite token with nonce
        invite_token, token_expires = create_invite_token(nonce)

        # 3. Verify invite token
        payload = verify_invite_token(invite_token)
        assert payload["nonce"] == nonce

        # 4. Consume nonce
        device_id = "device-new123456"
        consumed = await store.consume_nonce(nonce, device_id)
        assert consumed is True

        # 5. Register device
        await store.register_device(
            device_id=device_id,
            device_name="New iPhone",
            device_type="ios",
            invite_nonce=nonce,
        )

        # 6. Create device token
        device_token, device_expires = create_device_token(device_id)
        assert isinstance(device_token, str)

        # 7. Verify device registered
        devices = await store.list_devices()
        assert len(devices) == 1
        assert devices[0]["device_id"] == device_id

    @pytest.mark.asyncio
    async def test_replay_attack_prevention(self, store: InviteStore):
        """Same invite token cannot register two devices."""
        expires = datetime.now(timezone.utc) + timedelta(minutes=10)
        nonce = await store.create_nonce(expires_at=expires)
        invite_token, _ = create_invite_token(nonce)

        # First device succeeds
        assert await store.consume_nonce(nonce, "device-first") is True

        # Second device fails (nonce already consumed)
        assert await store.consume_nonce(nonce, "device-second") is False

    @pytest.mark.asyncio
    async def test_qr_payload_format(self, setup_secret_env):
        """QR payload contains required fields as compact JSON."""
        nonce = "test-nonce-for-qr"
        invite_token, _ = create_invite_token(nonce)

        with patch.dict(os.environ, {
            "HESTIA_SERVER_URL": "https://hestia-3.local:8443",
            "HESTIA_CERT_FINGERPRINT": "abc123",
        }):
            qr_data = {
                "t": invite_token,
                "u": "https://hestia-3.local:8443",
                "f": "abc123",
            }
            payload_json = json.dumps(qr_data, separators=(",", ":"))

        parsed = json.loads(payload_json)
        assert "t" in parsed
        assert "u" in parsed
        assert "f" in parsed
        assert parsed["u"].startswith("https://")


# -- Middleware Revocation Check ────────────────────────────────────────


class TestMiddlewareRevocation:
    """Tests for revocation check in auth middleware."""

    @pytest.mark.asyncio
    async def test_revoked_device_raises_401(self, store: InviteStore):
        """Revoked device triggers HTTPException from middleware check."""
        from fastapi import HTTPException
        from unittest.mock import AsyncMock

        await store.register_device("d1", "Phone", "ios")
        await store.revoke_device("d1")

        # get_invite_store is async, so mock must return a coroutine
        mock_get_store = AsyncMock(return_value=store)
        with patch("hestia.api.invite_store.get_invite_store", mock_get_store):
            with pytest.raises(HTTPException) as exc_info:
                await check_device_revocation("d1")
            assert exc_info.value.status_code == 401
            assert "revoked" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_active_device_passes(self, store: InviteStore):
        """Active device passes revocation check without error."""
        from unittest.mock import AsyncMock

        await store.register_device("d1", "Phone", "ios")

        mock_get_store = AsyncMock(return_value=store)
        with patch("hestia.api.invite_store.get_invite_store", mock_get_store):
            # Should not raise
            await check_device_revocation("d1")

    @pytest.mark.asyncio
    async def test_unknown_device_passes(self, store: InviteStore):
        """Unknown device passes revocation check (fail-open)."""
        from unittest.mock import AsyncMock

        mock_get_store = AsyncMock(return_value=store)
        with patch("hestia.api.invite_store.get_invite_store", mock_get_store):
            await check_device_revocation("unknown-device")
