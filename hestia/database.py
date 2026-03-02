"""
Base database class for Hestia SQLite modules.

Provides the common connect/close/schema lifecycle that all 11
database modules share. Subclasses override ``_init_schema()`` to
define their own tables and migrations.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import aiosqlite

from hestia.logging import get_logger


logger = get_logger()


class BaseDatabase(ABC):
    """
    Async SQLite database base class.

    Encapsulates the connect → row_factory → PRAGMA → schema lifecycle
    shared by all Hestia database modules.

    Subclasses MUST implement ``_init_schema()``.
    """

    def __init__(self, db_name: str, db_path: Optional[Path] = None) -> None:
        """
        Initialize database.

        Args:
            db_name: Logical name (used for default path and logging).
            db_path: Explicit path to the .db file.
                     Defaults to ``~/hestia/data/{db_name}.db``.
        """
        if db_path is None:
            db_path = Path.home() / "hestia" / "data" / f"{db_name}.db"

        self.db_name = db_name
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()

    @abstractmethod
    async def _init_schema(self) -> None:
        """Initialize database schema (tables, indexes, migrations)."""
        ...

    async def close(self) -> None:
        """Close database connection safely."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get active connection. Raises if not connected."""
        if self._connection is None:
            raise RuntimeError(
                f"{self.db_name} database not connected. Call connect() first."
            )
        return self._connection

    async def __aenter__(self) -> "BaseDatabase":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
