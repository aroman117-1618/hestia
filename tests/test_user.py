"""
Tests for Hestia User Settings module.

Phase 6b: User Settings API - profile, push tokens, and preferences.

Run with: python -m pytest tests/test_user.py -v
"""

import asyncio
import tempfile
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Generator

import pytest
import pytest_asyncio

from hestia.user.models import (
    UserProfile,
    UserSettings,
    PushNotificationSettings,
    QuietHours,
    PushToken,
    PushEnvironment,
)
from hestia.user.database import UserDatabase
from hestia.user.manager import UserManager


# ============== Fixtures ==============

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_profile() -> UserProfile:
    """Create a sample user profile."""
    return UserProfile.create(name="Andrew")


@pytest.fixture
def sample_settings() -> UserSettings:
    """Create sample user settings."""
    return UserSettings(
        push_notifications=PushNotificationSettings(
            enabled=True,
            order_executions=True,
            order_failures=True,
            proactive_briefings=True,
            quiet_hours=QuietHours(
                enabled=True,
                start=time(22, 0),
                end=time(7, 0),
            ),
        ),
        default_mode="tia",
        auto_lock_timeout_minutes=5,
    )


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> UserDatabase:
    """Create a test database."""
    db = UserDatabase(db_path=temp_dir / "test_user.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(temp_dir: Path) -> UserManager:
    """Create a test user manager."""
    photos_dir = temp_dir / "photos"
    photos_dir.mkdir()

    db = UserDatabase(db_path=temp_dir / "test_user.db")
    await db.connect()

    mgr = UserManager(database=db, photos_dir=photos_dir)
    await mgr.initialize()

    yield mgr

    await mgr.close()
    await db.close()


# ============== Model Tests ==============

class TestUserProfile:
    """Tests for UserProfile dataclass."""

    def test_profile_create(self):
        """Test profile creation with factory method."""
        profile = UserProfile.create(name="Test User")

        # Note: UserProfile.create() generates user-{uuid} IDs
        # The database overrides this to user-default for single-user system
        assert profile.id.startswith("user-")
        assert profile.name == "Test User"
        assert profile.description is None
        assert profile.photo_path is None
        assert profile.settings is not None
        assert profile.created_at is not None
        assert profile.updated_at is not None

    def test_profile_with_description(self):
        """Test profile creation with description."""
        # UserProfile.create() only takes name parameter
        profile = UserProfile.create(name="Test User")
        profile.description = "A test user for unit tests."

        assert profile.description == "A test user for unit tests."

    def test_profile_default_settings(self):
        """Test profile has sensible default settings."""
        profile = UserProfile.create(name="Test")

        assert profile.settings.default_mode == "tia"
        assert profile.settings.auto_lock_timeout_minutes == 5
        assert profile.settings.push_notifications.enabled is True


class TestUserSettings:
    """Tests for UserSettings dataclass."""

    def test_settings_defaults(self):
        """Test default settings."""
        settings = UserSettings()

        assert settings.default_mode == "tia"
        assert settings.auto_lock_timeout_minutes == 5
        assert settings.push_notifications.enabled is True

    def test_settings_custom(self, sample_settings: UserSettings):
        """Test custom settings."""
        assert sample_settings.push_notifications.quiet_hours.enabled is True
        assert sample_settings.push_notifications.quiet_hours.start == time(22, 0)


class TestPushNotificationSettings:
    """Tests for PushNotificationSettings dataclass."""

    def test_push_defaults(self):
        """Test default push settings."""
        push = PushNotificationSettings()

        assert push.enabled is True
        assert push.order_executions is True
        assert push.order_failures is True
        assert push.proactive_briefings is True
        assert push.quiet_hours.enabled is False

    def test_push_custom(self):
        """Test custom push settings."""
        push = PushNotificationSettings(
            enabled=True,
            order_executions=False,
            order_failures=True,
            proactive_briefings=False,
            quiet_hours=QuietHours(
                enabled=True,
                start=time(23, 0),
                end=time(6, 0),
            ),
        )

        assert push.order_executions is False
        assert push.proactive_briefings is False
        assert push.quiet_hours.start == time(23, 0)


class TestQuietHours:
    """Tests for QuietHours dataclass."""

    def test_quiet_hours_defaults(self):
        """Test default quiet hours."""
        quiet = QuietHours()

        assert quiet.enabled is False
        assert quiet.start == time(22, 0)
        assert quiet.end == time(7, 0)

    def test_quiet_hours_custom(self):
        """Test custom quiet hours."""
        quiet = QuietHours(
            enabled=True,
            start=time(21, 30),
            end=time(8, 30),
        )

        assert quiet.enabled is True
        assert quiet.start == time(21, 30)
        assert quiet.end == time(8, 30)


class TestPushToken:
    """Tests for PushToken dataclass."""

    def test_token_create(self):
        """Test push token creation."""
        token = PushToken.create(
            device_id="device-123",
            push_token="apns-token-abc123",
            environment=PushEnvironment.SANDBOX,
        )

        assert token.id.startswith("pt-")  # Push token IDs start with pt-
        assert token.device_id == "device-123"
        assert token.push_token == "apns-token-abc123"
        assert token.environment == PushEnvironment.SANDBOX

    def test_token_production_default(self):
        """Test push token defaults to production."""
        token = PushToken.create(
            device_id="device-456",
            push_token="apns-token-xyz789",
        )

        assert token.environment == PushEnvironment.PRODUCTION


class TestPushEnvironment:
    """Tests for PushEnvironment enum."""

    def test_environments(self):
        """Test all environments exist."""
        assert PushEnvironment.PRODUCTION.value == "production"
        assert PushEnvironment.SANDBOX.value == "sandbox"


# ============== Database Tests ==============

class TestUserDatabase:
    """Tests for UserDatabase persistence."""

    @pytest.mark.asyncio
    async def test_store_and_get_user(self, database: UserDatabase):
        """Test storing and retrieving a user."""
        # Database auto-creates default user on connect
        # So we update the existing user
        profile = await database.get_user()
        profile.name = "Test User"
        await database.update_user(profile)

        retrieved = await database.get_user()
        assert retrieved is not None
        assert retrieved.name == "Test User"

    @pytest.mark.asyncio
    async def test_get_user_returns_default(self, database: UserDatabase):
        """Test getting user returns default user."""
        # Database auto-creates a default user on connect
        user = await database.get_user()
        assert user is not None
        assert user.id == "user-default"

    @pytest.mark.asyncio
    async def test_update_user(self, database: UserDatabase):
        """Test updating a user."""
        # Database auto-creates default user on connect
        profile = await database.get_user()
        original_name = profile.name

        profile.name = "Updated"
        profile.description = "A description"
        await database.update_user(profile)

        retrieved = await database.get_user()
        assert retrieved.name == "Updated"
        assert retrieved.description == "A description"

    @pytest.mark.asyncio
    async def test_update_photo_path(self, database: UserDatabase):
        """Test updating photo path."""
        profile = UserProfile.create(name="Test")
        await database.store_user(profile)

        await database.update_photo_path("photo.jpg")

        retrieved = await database.get_user()
        assert retrieved.photo_path == "photo.jpg"

    @pytest.mark.asyncio
    async def test_clear_photo_path(self, database: UserDatabase):
        """Test clearing photo path."""
        profile = UserProfile.create(name="Test")
        profile.photo_path = "existing.jpg"
        await database.store_user(profile)

        await database.update_photo_path(None)

        retrieved = await database.get_user()
        assert retrieved.photo_path is None

    @pytest.mark.asyncio
    async def test_store_and_get_push_token(self, database: UserDatabase):
        """Test storing and retrieving push token."""
        token = PushToken.create(
            device_id="device-123",
            push_token="apns-token-abc",
        )

        await database.store_push_token(token)

        retrieved = await database.get_push_token("device-123")
        assert retrieved is not None
        assert retrieved.push_token == "apns-token-abc"

    @pytest.mark.asyncio
    async def test_push_token_upsert(self, database: UserDatabase):
        """Test that storing a token for existing device updates it."""
        token1 = PushToken.create(
            device_id="device-123",
            push_token="token-1",
        )
        await database.store_push_token(token1)

        token2 = PushToken.create(
            device_id="device-123",
            push_token="token-2",
        )
        await database.store_push_token(token2)

        retrieved = await database.get_push_token("device-123")
        assert retrieved.push_token == "token-2"

    @pytest.mark.asyncio
    async def test_delete_push_token(self, database: UserDatabase):
        """Test deleting push token."""
        token = PushToken.create(
            device_id="device-456",
            push_token="apns-token-xyz",
        )
        await database.store_push_token(token)

        deleted = await database.delete_push_token("device-456")
        assert deleted is True

        retrieved = await database.get_push_token("device-456")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_token(self, database: UserDatabase):
        """Test deleting non-existent token."""
        deleted = await database.delete_push_token("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_push_tokens(self, database: UserDatabase):
        """Test listing all push tokens."""
        for i in range(3):
            token = PushToken.create(
                device_id=f"device-{i}",
                push_token=f"token-{i}",
            )
            await database.store_push_token(token)

        tokens = await database.list_push_tokens()
        assert len(tokens) == 3


# ============== Manager Tests ==============

class TestUserManager:
    """Tests for UserManager lifecycle."""

    @pytest.mark.asyncio
    async def test_get_profile_creates_default(self, manager: UserManager):
        """Test getting profile creates default if none exists."""
        profile = await manager.get_profile()

        assert profile is not None
        assert profile.id == "user-default"
        # Default name is "Andrew" (set in database._ensure_default_user)
        assert profile.name == "Andrew"

    @pytest.mark.asyncio
    async def test_update_profile(self, manager: UserManager):
        """Test updating profile."""
        # Get default profile
        await manager.get_profile()

        # Update it
        updated = await manager.update_profile(
            name="Andrew",
            description="The user of Hestia.",
        )

        assert updated.name == "Andrew"
        assert updated.description == "The user of Hestia."

    @pytest.mark.asyncio
    async def test_update_profile_partial(self, manager: UserManager):
        """Test partial profile update."""
        # Set initial values
        await manager.update_profile(
            name="Andrew",
            description="Original description",
        )

        # Update only name
        updated = await manager.update_profile(name="Andy")

        assert updated.name == "Andy"
        assert updated.description == "Original description"

    @pytest.mark.asyncio
    async def test_save_photo(self, manager: UserManager):
        """Test saving user photo."""
        photo_data = b"fake jpeg data for testing"
        filename = await manager.save_photo(
            photo_data=photo_data,
            content_type="image/jpeg",
        )

        assert filename == "user_profile.jpg"

        profile = await manager.get_profile()
        assert profile.photo_path == filename

    @pytest.mark.asyncio
    async def test_save_photo_replaces_existing(self, manager: UserManager):
        """Test that saving photo replaces existing."""
        # Save first photo
        await manager.save_photo(
            photo_data=b"first photo",
            content_type="image/jpeg",
        )

        # Save second photo (should replace)
        await manager.save_photo(
            photo_data=b"second photo",
            content_type="image/png",
        )

        profile = await manager.get_profile()
        assert profile.photo_path == "user_profile.png"

    @pytest.mark.asyncio
    async def test_delete_photo(self, manager: UserManager):
        """Test deleting user photo."""
        # Save photo first
        await manager.save_photo(
            photo_data=b"photo to delete",
            content_type="image/jpeg",
        )

        # Delete it
        deleted = await manager.delete_photo()
        assert deleted is True

        profile = await manager.get_profile()
        assert profile.photo_path is None

    @pytest.mark.asyncio
    async def test_delete_photo_when_none(self, manager: UserManager):
        """Test deleting photo when none exists."""
        # Ensure profile exists but no photo
        await manager.get_profile()

        deleted = await manager.delete_photo()
        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_photo_path(self, manager: UserManager):
        """Test getting photo path."""
        # Save photo
        await manager.save_photo(
            photo_data=b"photo data",
            content_type="image/webp",
        )

        path = manager.get_photo_path("user_profile.webp")
        assert path is not None
        assert path.exists()

    @pytest.mark.asyncio
    async def test_get_photo_path_nonexistent(self, manager: UserManager):
        """Test getting non-existent photo path."""
        path = manager.get_photo_path("nonexistent.jpg")
        assert path is None

    @pytest.mark.asyncio
    async def test_get_settings(self, manager: UserManager):
        """Test getting user settings."""
        settings = await manager.get_settings()

        assert settings.default_mode == "tia"
        assert settings.push_notifications.enabled is True

    @pytest.mark.asyncio
    async def test_update_settings(self, manager: UserManager):
        """Test updating user settings."""
        new_push = PushNotificationSettings(
            enabled=False,
            order_executions=False,
            order_failures=True,
            proactive_briefings=False,
        )

        updated = await manager.update_settings(
            push_notifications=new_push,
            default_mode="mira",
            auto_lock_timeout_minutes=10,
        )

        assert updated.push_notifications.enabled is False
        assert updated.default_mode == "mira"
        assert updated.auto_lock_timeout_minutes == 10

    @pytest.mark.asyncio
    async def test_update_settings_partial(self, manager: UserManager):
        """Test partial settings update."""
        # Set initial values
        await manager.update_settings(
            default_mode="olly",
            auto_lock_timeout_minutes=15,
        )

        # Update only one field
        updated = await manager.update_settings(auto_lock_timeout_minutes=20)

        assert updated.default_mode == "olly"  # Unchanged
        assert updated.auto_lock_timeout_minutes == 20

    @pytest.mark.asyncio
    async def test_register_push_token(self, manager: UserManager):
        """Test registering push token."""
        token = await manager.register_push_token(
            device_id="device-123",
            push_token="apns-token-abc",
            environment=PushEnvironment.SANDBOX,
        )

        assert token.device_id == "device-123"
        assert token.push_token == "apns-token-abc"
        assert token.environment == PushEnvironment.SANDBOX

    @pytest.mark.asyncio
    async def test_unregister_push_token(self, manager: UserManager):
        """Test unregistering push token."""
        # Register first
        await manager.register_push_token(
            device_id="device-456",
            push_token="apns-token-xyz",
        )

        # Unregister
        deleted = await manager.unregister_push_token("device-456")
        assert deleted is True

        # Verify it's gone
        token = await manager.get_push_token("device-456")
        assert token is None

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_token(self, manager: UserManager):
        """Test unregistering non-existent token."""
        deleted = await manager.unregister_push_token("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_push_token(self, manager: UserManager):
        """Test getting push token."""
        await manager.register_push_token(
            device_id="device-789",
            push_token="apns-token-qrs",
        )

        token = await manager.get_push_token("device-789")
        assert token is not None
        assert token.push_token == "apns-token-qrs"


# ============== Settings Serialization Tests ==============

class TestSettingsSerialization:
    """Tests for settings serialization."""

    @pytest.mark.asyncio
    async def test_settings_persist_through_database(self, database: UserDatabase):
        """Test settings are properly serialized and deserialized."""
        # Get the default user created on connect
        profile = await database.get_user()
        profile.settings = UserSettings(
            push_notifications=PushNotificationSettings(
                enabled=True,
                order_executions=False,
                order_failures=True,
                proactive_briefings=False,
                quiet_hours=QuietHours(
                    enabled=True,
                    start=time(21, 0),
                    end=time(8, 0),
                ),
            ),
            default_mode="mira",
            auto_lock_timeout_minutes=10,
        )

        await database.update_user(profile)
        retrieved = await database.get_user()

        assert retrieved.settings.push_notifications.order_executions is False
        assert retrieved.settings.push_notifications.proactive_briefings is False
        assert retrieved.settings.push_notifications.quiet_hours.enabled is True
        assert retrieved.settings.push_notifications.quiet_hours.start == time(21, 0)
        assert retrieved.settings.default_mode == "mira"
        assert retrieved.settings.auto_lock_timeout_minutes == 10


# ============== Edge Cases ==============

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_multiple_devices_same_user(self, manager: UserManager):
        """Test multiple devices can register tokens for same user."""
        await manager.register_push_token(
            device_id="iphone",
            push_token="token-iphone",
        )
        await manager.register_push_token(
            device_id="ipad",
            push_token="token-ipad",
        )
        await manager.register_push_token(
            device_id="mac",
            push_token="token-mac",
        )

        # All should be retrievable
        iphone = await manager.get_push_token("iphone")
        ipad = await manager.get_push_token("ipad")
        mac = await manager.get_push_token("mac")

        assert iphone.push_token == "token-iphone"
        assert ipad.push_token == "token-ipad"
        assert mac.push_token == "token-mac"

    @pytest.mark.asyncio
    async def test_photo_content_types(self, manager: UserManager):
        """Test different photo content types."""
        types = [
            ("image/jpeg", ".jpg"),
            ("image/png", ".png"),
            ("image/webp", ".webp"),
        ]

        for content_type, expected_ext in types:
            filename = await manager.save_photo(
                photo_data=b"fake data",
                content_type=content_type,
            )
            assert filename.endswith(expected_ext)
