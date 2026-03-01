"""
SQLite persistence for investigation data.

Provides async database operations for investigation storage,
retrieval, history listing, and cleanup.
"""

import json

import aiosqlite
from pathlib import Path
from typing import Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import Investigation, InvestigationStatus


class InvestigateDatabase:
    """
    SQLite database for investigation persistence.

    Uses async aiosqlite for non-blocking I/O.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize investigation database.

        Args:
            db_path: Path to SQLite database file.
                     Defaults to ~/hestia/data/investigate.db
        """
        if db_path is None:
            db_path = Path.home() / "hestia" / "data" / "investigate.db"

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
            f"Investigation database connected: {self.db_path}",
            component=LogComponent.INVESTIGATE,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS investigations (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'default',
                content_type TEXT NOT NULL,
                depth TEXT NOT NULL DEFAULT 'standard',
                status TEXT NOT NULL DEFAULT 'pending',
                title TEXT,
                source_author TEXT,
                source_date TEXT,
                extracted_text TEXT DEFAULT '',
                analysis TEXT DEFAULT '',
                key_points TEXT DEFAULT '[]',
                model_used TEXT,
                tokens_used INTEGER DEFAULT 0,
                extraction_metadata TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                error TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_investigations_user
                ON investigations(user_id, created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_investigations_url
                ON investigations(url);

            CREATE INDEX IF NOT EXISTS idx_investigations_status
                ON investigations(status);

            CREATE INDEX IF NOT EXISTS idx_investigations_content_type
                ON investigations(content_type);
        """)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def __aenter__(self) -> "InvestigateDatabase":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get active connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # =========================================================================
    # CRUD
    # =========================================================================

    async def store(self, investigation: Investigation) -> None:
        """Store a new or updated investigation (upsert)."""
        row = investigation.to_sqlite_row()
        await self.connection.execute(
            """
            INSERT INTO investigations (
                id, url, user_id, content_type, depth, status,
                title, source_author, source_date,
                extracted_text, analysis, key_points,
                model_used, tokens_used, extraction_metadata,
                created_at, completed_at, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status=excluded.status,
                title=excluded.title,
                source_author=excluded.source_author,
                source_date=excluded.source_date,
                extracted_text=excluded.extracted_text,
                analysis=excluded.analysis,
                key_points=excluded.key_points,
                model_used=excluded.model_used,
                tokens_used=excluded.tokens_used,
                extraction_metadata=excluded.extraction_metadata,
                completed_at=excluded.completed_at,
                error=excluded.error
            """,
            row,
        )
        await self.connection.commit()

    async def get(self, investigation_id: str, user_id: str = "default") -> Optional[Investigation]:
        """Get an investigation by ID, scoped to user."""
        async with self.connection.execute(
            "SELECT * FROM investigations WHERE id = ? AND user_id = ?",
            (investigation_id, user_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Investigation.from_sqlite_row(dict(row))
            return None

    async def update(self, investigation: Investigation) -> None:
        """Update an existing investigation."""
        await self.connection.execute(
            """
            UPDATE investigations SET
                status = ?, title = ?, source_author = ?, source_date = ?,
                extracted_text = ?, analysis = ?, key_points = ?,
                model_used = ?, tokens_used = ?, extraction_metadata = ?,
                completed_at = ?, error = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                investigation.status.value,
                investigation.title,
                investigation.source_author,
                investigation.source_date,
                investigation.extracted_text,
                investigation.analysis,
                json.dumps(investigation.key_points),
                investigation.model_used,
                investigation.tokens_used,
                json.dumps(investigation.extraction_metadata) if investigation.extraction_metadata else None,
                investigation.completed_at.isoformat() if investigation.completed_at else None,
                investigation.error,
                investigation.id,
                investigation.user_id,
            ),
        )
        await self.connection.commit()

    async def delete(self, investigation_id: str, user_id: str = "default") -> bool:
        """Delete an investigation. Returns True if deleted."""
        cursor = await self.connection.execute(
            "DELETE FROM investigations WHERE id = ? AND user_id = ?",
            (investigation_id, user_id),
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def list_history(
        self,
        user_id: str = "default",
        content_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Investigation]:
        """List investigations with optional filtering."""
        query = "SELECT * FROM investigations WHERE user_id = ?"
        params: list = [user_id]

        if content_type:
            query += " AND content_type = ?"
            params.append(content_type)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        investigations = []
        async with self.connection.execute(query, params) as cursor:
            async for row in cursor:
                investigations.append(Investigation.from_sqlite_row(dict(row)))

        return investigations

    async def count(self, user_id: str = "default") -> int:
        """Count investigations for a user."""
        async with self.connection.execute(
            "SELECT COUNT(*) FROM investigations WHERE user_id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def find_by_url(self, url: str, user_id: str = "default") -> Optional[Investigation]:
        """Find the most recent investigation for a URL."""
        async with self.connection.execute(
            """
            SELECT * FROM investigations
            WHERE url = ? AND user_id = ? AND status = ?
            ORDER BY created_at DESC LIMIT 1
            """,
            (url, user_id, InvestigationStatus.COMPLETE.value),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return Investigation.from_sqlite_row(dict(row))
            return None


# Module-level singleton
_investigate_database: Optional[InvestigateDatabase] = None


async def get_investigate_database() -> InvestigateDatabase:
    """Get or create singleton investigation database."""
    global _investigate_database
    if _investigate_database is None:
        _investigate_database = InvestigateDatabase()
        await _investigate_database.connect()
    return _investigate_database


async def close_investigate_database() -> None:
    """Close the singleton investigation database."""
    global _investigate_database
    if _investigate_database is not None:
        await _investigate_database.close()
        _investigate_database = None
