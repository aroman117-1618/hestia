"""
SQLite persistence for invite nonces and device registry.

Tracks one-time-use invite tokens for QR code onboarding
and maintains a registry of all registered devices.
"""

import aiosqlite
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from hestia.logging import get_logger, LogComponent


_instance: Optional["InviteStore"] = None


class InviteStore:
    """
    SQLite store for invite nonces and device registry.

    Uses async aiosqlite for non-blocking I/O.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path.home() / "hestia" / "data" / "invites.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None
        self.logger = get_logger()

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()

        self.logger.info(
            f"Invite store connected: {self.db_path}",
            component=LogComponent.SECURITY,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS invite_nonces (
                nonce TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                claimed_by_device_id TEXT,
                claimed_at TEXT,
                source TEXT NOT NULL DEFAULT 'setup_secret'
            );
            CREATE INDEX IF NOT EXISTS idx_nonces_expires
                ON invite_nonces(expires_at);

            CREATE TABLE IF NOT EXISTS registered_devices (
                device_id TEXT PRIMARY KEY,
                device_name TEXT NOT NULL DEFAULT 'unknown',
                device_type TEXT NOT NULL DEFAULT 'unknown',
                registered_at TEXT NOT NULL,
                last_seen_at TEXT,
                invite_nonce TEXT,
                FOREIGN KEY (invite_nonce) REFERENCES invite_nonces(nonce)
            );
            CREATE INDEX IF NOT EXISTS idx_devices_registered
                ON registered_devices(registered_at);
        """)
        await self._connection.commit()

        # Migration: add revoked_at column if missing
        await self._migrate_revoked_at()

    async def _migrate_revoked_at(self) -> None:
        """Add revoked_at column to registered_devices if it doesn't exist."""
        cursor = await self._connection.execute(
            "PRAGMA table_info(registered_devices)"
        )
        columns = await cursor.fetchall()
        column_names = [col["name"] for col in columns]

        if "revoked_at" not in column_names:
            await self._connection.execute(
                "ALTER TABLE registered_devices ADD COLUMN revoked_at TEXT"
            )
            await self._connection.commit()
            self.logger.info(
                "Migrated registered_devices: added revoked_at column",
                component=LogComponent.SECURITY,
            )

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    # =========================================================================
    # Nonce Operations
    # =========================================================================

    async def create_nonce(self, expires_at: datetime, source: str = "setup_secret") -> str:
        """
        Create a new one-time-use invite nonce.

        Args:
            expires_at: When this nonce expires.
            source: How the nonce was generated ('setup_secret' or 're_invite').

        Returns:
            The generated nonce string.
        """
        nonce = uuid4().hex
        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """INSERT INTO invite_nonces (nonce, created_at, expires_at, source)
               VALUES (?, ?, ?, ?)""",
            (nonce, now, expires_at.isoformat(), source),
        )
        await self._connection.commit()
        return nonce

    async def consume_nonce(self, nonce: str, device_id: str) -> bool:
        """
        Consume a nonce (mark as claimed by a device).

        Args:
            nonce: The nonce to consume.
            device_id: The device claiming this nonce.

        Returns:
            True if nonce was valid and consumed, False if invalid/expired/already claimed.
        """
        now = datetime.now(timezone.utc)

        # Check nonce exists, is not expired, and is not already claimed
        cursor = await self._connection.execute(
            """SELECT nonce, expires_at, claimed_by_device_id
               FROM invite_nonces WHERE nonce = ?""",
            (nonce,),
        )
        row = await cursor.fetchone()

        if row is None:
            return False

        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if now > expires_at:
            return False

        if row["claimed_by_device_id"] is not None:
            return False

        # Mark as consumed
        await self._connection.execute(
            """UPDATE invite_nonces
               SET claimed_by_device_id = ?, claimed_at = ?
               WHERE nonce = ?""",
            (device_id, now.isoformat(), nonce),
        )
        await self._connection.commit()
        return True

    async def is_nonce_valid(self, nonce: str) -> bool:
        """Check if a nonce is valid (exists, not expired, not claimed)."""
        now = datetime.now(timezone.utc)

        cursor = await self._connection.execute(
            """SELECT expires_at, claimed_by_device_id
               FROM invite_nonces WHERE nonce = ?""",
            (nonce,),
        )
        row = await cursor.fetchone()

        if row is None:
            return False

        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return now <= expires_at and row["claimed_by_device_id"] is None

    # =========================================================================
    # Device Registry Operations
    # =========================================================================

    async def register_device(
        self,
        device_id: str,
        device_name: str,
        device_type: str,
        invite_nonce: Optional[str] = None,
    ) -> None:
        """Register a device in the registry."""
        now = datetime.now(timezone.utc).isoformat()

        await self._connection.execute(
            """INSERT OR REPLACE INTO registered_devices
               (device_id, device_name, device_type, registered_at, invite_nonce)
               VALUES (?, ?, ?, ?, ?)""",
            (device_id, device_name, device_type, now, invite_nonce),
        )
        await self._connection.commit()

    async def update_last_seen(self, device_id: str) -> None:
        """Update last_seen_at for a device."""
        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            "UPDATE registered_devices SET last_seen_at = ? WHERE device_id = ?",
            (now, device_id),
        )
        await self._connection.commit()

    async def list_devices(self) -> List[Dict]:
        """List all registered devices with revocation status."""
        cursor = await self._connection.execute(
            """SELECT device_id, device_name, device_type,
                      registered_at, last_seen_at, revoked_at
               FROM registered_devices ORDER BY registered_at DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_device_count(self) -> int:
        """Get number of registered devices."""
        cursor = await self._connection.execute(
            "SELECT COUNT(*) FROM registered_devices"
        )
        row = await cursor.fetchone()
        return row[0]

    # =========================================================================
    # Device Revocation
    # =========================================================================

    async def revoke_device(self, device_id: str) -> bool:
        """
        Revoke a device's access.

        Args:
            device_id: Device to revoke.

        Returns:
            True if device was found and revoked, False if not found.
        """
        cursor = await self._connection.execute(
            "SELECT device_id, revoked_at FROM registered_devices WHERE device_id = ?",
            (device_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return False

        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            "UPDATE registered_devices SET revoked_at = ? WHERE device_id = ?",
            (now, device_id),
        )
        await self._connection.commit()

        self.logger.info(
            f"Device revoked: {device_id}",
            component=LogComponent.SECURITY,
        )
        return True

    async def unrevoke_device(self, device_id: str) -> bool:
        """
        Restore a revoked device's access.

        Args:
            device_id: Device to unrevoke.

        Returns:
            True if device was found and unrevoked, False if not found.
        """
        cursor = await self._connection.execute(
            "SELECT device_id, revoked_at FROM registered_devices WHERE device_id = ?",
            (device_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return False

        await self._connection.execute(
            "UPDATE registered_devices SET revoked_at = NULL WHERE device_id = ?",
            (device_id,),
        )
        await self._connection.commit()

        self.logger.info(
            f"Device unrevoked: {device_id}",
            component=LogComponent.SECURITY,
        )
        return True

    async def is_device_revoked(self, device_id: str) -> bool:
        """
        Check if a device has been revoked.

        Args:
            device_id: Device to check.

        Returns:
            True if device is revoked, False if active or not found.
        """
        cursor = await self._connection.execute(
            "SELECT revoked_at FROM registered_devices WHERE device_id = ?",
            (device_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return False
        return row["revoked_at"] is not None


async def get_invite_store() -> InviteStore:
    """Get or create the singleton InviteStore instance."""
    global _instance
    if _instance is None:
        _instance = InviteStore()
        await _instance.connect()
    return _instance
