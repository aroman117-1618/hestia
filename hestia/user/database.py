"""
SQLite persistence for user settings.

Provides async database operations for user profile, settings,
and push token management using aiosqlite.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent

from .models import UserProfile, PushToken, PushEnvironment


class UserDatabase(BaseDatabase):
    """
    SQLite database for user settings persistence.

    Uses async aiosqlite for non-blocking I/O.
    """

    # Default user ID (single-user system)
    DEFAULT_USER_ID = "user-default"

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("user", db_path)
        self.logger = get_logger()

    async def connect(self) -> None:
        """Open database connection, initialize schema, seed defaults."""
        await super().connect()
        await self._ensure_default_user()
        self.logger.info(
            f"User database connected: {self.db_path}",
            component=LogComponent.API,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS user_profiles (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                photo_path TEXT,
                settings TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS push_tokens (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL UNIQUE,
                push_token TEXT NOT NULL,
                environment TEXT NOT NULL DEFAULT 'production',
                registered_at TEXT NOT NULL,
                last_used_at TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_push_tokens_device
                ON push_tokens(device_id);
        """)
        await self._connection.commit()

    async def _ensure_default_user(self) -> None:
        """Ensure default user profile exists."""
        async with self.connection.execute(
            "SELECT id FROM user_profiles WHERE id = ?",
            (self.DEFAULT_USER_ID,),
        ) as cursor:
            row = await cursor.fetchone()

            if not row:
                user = UserProfile.create("Andrew")
                user.id = self.DEFAULT_USER_ID
                await self.store_user(user)

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self.logger.debug(
                "User database closed",
                component=LogComponent.API,
            )
        await super().close()

    # =========================================================================
    # User Profile CRUD
    # =========================================================================

    async def store_user(self, user: UserProfile) -> str:
        """Store a user profile."""
        row = user.to_sqlite_row()

        await self.connection.execute(
            """
            INSERT OR REPLACE INTO user_profiles (
                id, name, description, photo_path, settings,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        await self.connection.commit()

        return user.id

    async def get_user(self) -> Optional[UserProfile]:
        """Get the user profile (single-user system)."""
        async with self.connection.execute(
            "SELECT * FROM user_profiles WHERE id = ?",
            (self.DEFAULT_USER_ID,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                return UserProfile.from_sqlite_row(dict(row))

        return None

    async def update_user(self, user: UserProfile) -> bool:
        """Update user profile."""
        user.updated_at = datetime.now(timezone.utc)
        row = user.to_sqlite_row()

        cursor = await self.connection.execute(
            """
            UPDATE user_profiles SET
                name = ?,
                description = ?,
                photo_path = ?,
                settings = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (row[1], row[2], row[3], row[4], row[6], row[0]),
        )
        await self.connection.commit()

        return cursor.rowcount > 0

    async def update_photo_path(self, photo_path: Optional[str]) -> bool:
        """Update only the photo path."""
        cursor = await self.connection.execute(
            """
            UPDATE user_profiles SET
                photo_path = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (photo_path, datetime.now(timezone.utc).isoformat(), self.DEFAULT_USER_ID),
        )
        await self.connection.commit()

        return cursor.rowcount > 0

    # =========================================================================
    # Push Token CRUD
    # =========================================================================

    async def store_push_token(self, token: PushToken) -> str:
        """Store or update a push token."""
        # Delete existing token for this device
        await self.connection.execute(
            "DELETE FROM push_tokens WHERE device_id = ?",
            (token.device_id,),
        )

        row = token.to_sqlite_row()

        await self.connection.execute(
            """
            INSERT INTO push_tokens (
                id, device_id, push_token, environment,
                registered_at, last_used_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        await self.connection.commit()

        self.logger.debug(
            f"Stored push token for device: {token.device_id}",
            component=LogComponent.API,
        )

        return token.id

    async def get_push_token(self, device_id: str) -> Optional[PushToken]:
        """Get push token for a device."""
        async with self.connection.execute(
            "SELECT * FROM push_tokens WHERE device_id = ?",
            (device_id,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                return PushToken.from_sqlite_row(dict(row))

        return None

    async def delete_push_token(self, device_id: str) -> bool:
        """Delete push token for a device."""
        cursor = await self.connection.execute(
            "DELETE FROM push_tokens WHERE device_id = ?",
            (device_id,),
        )
        await self.connection.commit()

        deleted = cursor.rowcount > 0

        if deleted:
            self.logger.debug(
                f"Deleted push token for device: {device_id}",
                component=LogComponent.API,
            )

        return deleted

    async def list_push_tokens(self) -> List[PushToken]:
        """List all push tokens."""
        tokens = []
        async with self.connection.execute(
            "SELECT * FROM push_tokens ORDER BY registered_at DESC",
        ) as cursor:
            async for row in cursor:
                tokens.append(PushToken.from_sqlite_row(dict(row)))

        return tokens

    async def update_token_last_used(self, device_id: str) -> bool:
        """Update last_used_at for a token."""
        cursor = await self.connection.execute(
            """
            UPDATE push_tokens SET
                last_used_at = ?
            WHERE device_id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), device_id),
        )
        await self.connection.commit()

        return cursor.rowcount > 0


# Module-level singleton
_user_database: Optional[UserDatabase] = None


async def get_user_database() -> UserDatabase:
    """Get or create singleton user database."""
    global _user_database
    if _user_database is None:
        _user_database = UserDatabase()
        await _user_database.connect()
    return _user_database


async def close_user_database() -> None:
    """Close the singleton user database."""
    global _user_database
    if _user_database is not None:
        await _user_database.close()
        _user_database = None
