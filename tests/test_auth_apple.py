"""Tests for Apple Sign In authentication."""

import pytest
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from hestia.api.invite_store import get_invite_store


@pytest.mark.asyncio
async def test_apple_user_id_migration():
    """Verify apple_user_id column is added to registered_devices."""
    store = await get_invite_store()
    cursor = await store._connection.execute(
        "PRAGMA table_info(registered_devices)"
    )
    columns = await cursor.fetchall()
    column_names = [col["name"] for col in columns]
    assert "apple_user_id" in column_names


@pytest.mark.asyncio
async def test_register_device_with_apple_id():
    """Verify device registration stores apple_user_id."""
    store = await get_invite_store()
    device_id = "test-apple-device-001"
    await store.register_device(
        device_id=device_id,
        device_name="Test iPhone",
        device_type="ios",
        apple_user_id="000123.abc456.789",
    )
    found = await store.find_device_by_apple_id("000123.abc456.789")
    assert found is not None
    assert found["device_id"] == device_id
    # Cleanup
    await store._connection.execute(
        "DELETE FROM registered_devices WHERE device_id = ?", (device_id,)
    )
    await store._connection.commit()


@pytest.mark.asyncio
async def test_find_device_by_apple_id_not_found():
    """Verify None returned for unknown apple_user_id."""
    store = await get_invite_store()
    found = await store.find_device_by_apple_id("nonexistent.id")
    assert found is None


@pytest.mark.asyncio
async def test_find_device_by_apple_id_revoked():
    """Verify revoked device not returned by apple_user_id lookup."""
    store = await get_invite_store()
    device_id = "test-apple-revoked-001"
    apple_id = "000999.revoked.test"
    await store.register_device(
        device_id=device_id,
        device_name="Revoked iPhone",
        device_type="ios",
        apple_user_id=apple_id,
    )
    await store._connection.execute(
        "UPDATE registered_devices SET revoked_at = ? WHERE device_id = ?",
        (datetime.now(timezone.utc).isoformat(), device_id),
    )
    await store._connection.commit()
    found = await store.find_device_by_apple_id(apple_id)
    assert found is None
    # Cleanup
    await store._connection.execute(
        "DELETE FROM registered_devices WHERE device_id = ?", (device_id,)
    )
    await store._connection.commit()


@pytest.fixture
def mock_apple_jwt_payload():
    """Mock decoded Apple identity token payload."""
    return {
        "iss": "https://appleid.apple.com",
        "aud": "com.andrewlonati.hestia",
        "exp": 9999999999,
        "sub": "000123.testuser.apple",
        "email": "andrew@example.com",
    }


def _make_auth_app():
    """Create a minimal FastAPI app with just the auth router (no ReadinessMiddleware)."""
    from fastapi import FastAPI
    from hestia.api.routes.auth import router as auth_router

    test_app = FastAPI()
    test_app.include_router(auth_router)
    return test_app


@pytest.mark.asyncio
async def test_register_with_apple_success(mock_apple_jwt_payload):
    """Test successful Apple Sign In registration."""
    app = _make_auth_app()

    with patch("hestia.api.routes.auth.verify_apple_identity_token") as mock_verify:
        mock_verify.return_value = mock_apple_jwt_payload

        # First, seed a device with this apple_user_id so the lookup succeeds
        store = await get_invite_store()
        await store.register_device(
            device_id="seed-device",
            device_name="Seed",
            device_type="ios",
            apple_user_id="000123.testuser.apple",
        )

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://test") as client:
            response = await client.post(
                "/v1/auth/register-with-apple",
                json={
                    "identity_token": "fake.jwt.token",
                    "device_name": "Test iPhone",
                    "device_type": "ios",
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "device_id" in data
        assert "server_url" in data

        # Cleanup
        await store._connection.execute(
            "DELETE FROM registered_devices WHERE apple_user_id = ?",
            ("000123.testuser.apple",)
        )
        await store._connection.commit()


@pytest.mark.asyncio
async def test_register_with_apple_invalid_token():
    """Test rejection of invalid Apple token."""
    app = _make_auth_app()

    with patch("hestia.api.routes.auth.verify_apple_identity_token") as mock_verify:
        mock_verify.side_effect = ValueError("Invalid token")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://test") as client:
            response = await client.post(
                "/v1/auth/register-with-apple",
                json={
                    "identity_token": "invalid.jwt.token",
                    "device_name": "Test iPhone",
                    "device_type": "ios",
                },
            )

        assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_with_apple_unknown_user():
    """Test rejection when Apple ID is not registered."""
    app = _make_auth_app()

    with patch("hestia.api.routes.auth.verify_apple_identity_token") as mock_verify:
        mock_verify.return_value = {
            "iss": "https://appleid.apple.com",
            "aud": "com.andrewlonati.hestia",
            "exp": 9999999999,
            "sub": "unknown.user.apple",
            "email": "stranger@example.com",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="https://test") as client:
            response = await client.post(
                "/v1/auth/register-with-apple",
                json={
                    "identity_token": "fake.jwt.token",
                    "device_name": "Stranger iPhone",
                    "device_type": "ios",
                },
            )

        assert response.status_code == 403
