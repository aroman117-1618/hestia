"""
User manager for orchestrating user profile and settings operations.

Coordinates user profile updates, settings changes, and push token registration.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from hestia.logging import get_logger, LogComponent

from .models import (
    UserProfile,
    UserSettings,
    PushNotificationSettings,
    QuietHours,
    PushToken,
    PushEnvironment,
)
from .database import UserDatabase, get_user_database


class UserManager:
    """
    Manages user profile and settings lifecycle.

    Handles profile updates, settings changes, and push token registration.
    """

    def __init__(
        self,
        database: Optional[UserDatabase] = None,
        photos_dir: Optional[Path] = None,
    ):
        """
        Initialize user manager.

        Args:
            database: UserDatabase instance. If None, uses singleton.
            photos_dir: Directory for user photos.
                       Defaults to ~/hestia/data/user_photos/
        """
        self._database = database
        self.photos_dir = photos_dir or Path.home() / "hestia" / "data" / "user_photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the user manager and its dependencies."""
        if self._database is None:
            self._database = await get_user_database()

        self.logger.info(
            "User manager initialized",
            component=LogComponent.API,
        )

    async def close(self) -> None:
        """Close user manager resources."""
        self.logger.debug(
            "User manager closed",
            component=LogComponent.API,
        )

    async def __aenter__(self) -> "UserManager":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def database(self) -> UserDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("User manager not initialized. Call initialize() first.")
        return self._database

    # =========================================================================
    # Profile Operations
    # =========================================================================

    async def get_profile(self) -> UserProfile:
        """Get the user profile."""
        profile = await self.database.get_user()
        if profile is None:
            # Create default profile if not exists
            profile = UserProfile.create("User")
            await self.database.store_user(profile)
        return profile

    async def update_profile(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> UserProfile:
        """
        Update user profile.

        Args:
            name: New name (optional).
            description: New description (optional).

        Returns:
            Updated UserProfile.
        """
        profile = await self.get_profile()

        if name is not None:
            profile.name = name
        if description is not None:
            profile.description = description

        profile.updated_at = datetime.now(timezone.utc)

        await self.database.update_user(profile)

        self.logger.info(
            "User profile updated",
            component=LogComponent.API,
        )

        return profile

    async def save_photo(
        self,
        photo_data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """
        Save user profile photo.

        Args:
            photo_data: Photo bytes.
            content_type: MIME type.

        Returns:
            Relative path to saved photo.
        """
        profile = await self.get_profile()

        # Determine extension
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }
        ext = ext_map.get(content_type, ".jpg")

        # Delete existing photo if any
        if profile.photo_path:
            old_path = self.photos_dir / profile.photo_path
            if old_path.exists():
                old_path.unlink()

        # Save new photo
        filename = f"user_profile{ext}"
        photo_path = self.photos_dir / filename

        with open(photo_path, "wb") as f:
            f.write(photo_data)

        await self.database.update_photo_path(filename)

        self.logger.info(
            "User photo saved",
            component=LogComponent.API,
        )

        return filename

    async def delete_photo(self) -> bool:
        """Delete user profile photo."""
        profile = await self.get_profile()

        if not profile.photo_path:
            return False

        # Delete file
        photo_path = self.photos_dir / profile.photo_path
        if photo_path.exists():
            photo_path.unlink()

        await self.database.update_photo_path(None)

        self.logger.info(
            "User photo deleted",
            component=LogComponent.API,
        )

        return True

    def get_photo_path(self, filename: str) -> Optional[Path]:
        """Get full path to a photo file."""
        photo_path = self.photos_dir / filename
        if photo_path.exists():
            return photo_path
        return None

    # =========================================================================
    # Settings Operations
    # =========================================================================

    async def get_settings(self) -> UserSettings:
        """Get user settings."""
        profile = await self.get_profile()
        return profile.settings

    async def update_settings(
        self,
        push_notifications: Optional[PushNotificationSettings] = None,
        default_mode: Optional[str] = None,
        auto_lock_timeout_minutes: Optional[int] = None,
    ) -> UserSettings:
        """
        Update user settings.

        Args:
            push_notifications: New push settings (optional).
            default_mode: New default mode (optional).
            auto_lock_timeout_minutes: New auto-lock timeout (optional).

        Returns:
            Updated UserSettings.
        """
        profile = await self.get_profile()
        settings = profile.settings

        if push_notifications is not None:
            settings.push_notifications = push_notifications
        if default_mode is not None:
            settings.default_mode = default_mode
        if auto_lock_timeout_minutes is not None:
            settings.auto_lock_timeout_minutes = auto_lock_timeout_minutes

        profile.updated_at = datetime.now(timezone.utc)

        await self.database.update_user(profile)

        self.logger.info(
            "User settings updated",
            component=LogComponent.API,
        )

        return settings

    # =========================================================================
    # Push Token Operations
    # =========================================================================

    async def register_push_token(
        self,
        device_id: str,
        push_token: str,
        environment: PushEnvironment = PushEnvironment.PRODUCTION,
    ) -> PushToken:
        """
        Register a push notification token for a device.

        Args:
            device_id: Device identifier.
            push_token: APNS token.
            environment: APNS environment.

        Returns:
            Created PushToken.
        """
        token = PushToken.create(
            device_id=device_id,
            push_token=push_token,
            environment=environment,
        )

        await self.database.store_push_token(token)

        self.logger.info(
            f"Push token registered: {device_id}",
            component=LogComponent.API,
        )

        return token

    async def unregister_push_token(self, device_id: str) -> bool:
        """
        Unregister push token for a device.

        Args:
            device_id: Device identifier.

        Returns:
            True if token was deleted, False if not found.
        """
        deleted = await self.database.delete_push_token(device_id)

        if deleted:
            self.logger.info(
                f"Push token unregistered: {device_id}",
                component=LogComponent.API,
            )

        return deleted

    async def get_push_token(self, device_id: str) -> Optional[PushToken]:
        """Get push token for a device."""
        return await self.database.get_push_token(device_id)


# Module-level singleton
_user_manager: Optional[UserManager] = None


async def get_user_manager() -> UserManager:
    """Get or create singleton user manager."""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
        await _user_manager.initialize()
    return _user_manager


async def close_user_manager() -> None:
    """Close the singleton user manager."""
    global _user_manager
    if _user_manager is not None:
        await _user_manager.close()
        _user_manager = None
