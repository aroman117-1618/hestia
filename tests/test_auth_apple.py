"""Tests for Apple Sign In authentication."""

import pytest
from datetime import datetime, timezone
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
