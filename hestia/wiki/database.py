"""
SQLite persistence for wiki articles.

Provides async database operations for wiki article
storage, retrieval, and staleness tracking.
"""

import aiosqlite
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import WikiArticle, ArticleType, GenerationStatus


class WikiDatabase:
    """
    SQLite database for wiki article persistence.

    Uses async aiosqlite for non-blocking I/O.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize wiki database.

        Args:
            db_path: Path to SQLite database file.
                     Defaults to ~/hestia/data/wiki.db
        """
        if db_path is None:
            db_path = Path.home() / "hestia" / "data" / "wiki.db"

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
            f"Wiki database connected: {self.db_path}",
            component=LogComponent.WIKI,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS wiki_articles (
                id TEXT PRIMARY KEY,
                article_type TEXT NOT NULL,
                title TEXT NOT NULL,
                subtitle TEXT DEFAULT '',
                content TEXT DEFAULT '',
                module_name TEXT,
                source_hash TEXT,
                generation_status TEXT NOT NULL DEFAULT 'pending',
                generated_at TEXT,
                generation_model TEXT,
                word_count INTEGER DEFAULT 0,
                estimated_read_time INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_articles_type
                ON wiki_articles(article_type);

            CREATE INDEX IF NOT EXISTS idx_articles_module
                ON wiki_articles(module_name);
        """)

        # Auto-migrate: add audit columns if missing
        cursor = await self._connection.execute("PRAGMA table_info(wiki_articles)")
        columns = {row[1] for row in await cursor.fetchall()}

        if "last_trigger_source" not in columns:
            await self._connection.execute(
                "ALTER TABLE wiki_articles ADD COLUMN last_trigger_source TEXT DEFAULT 'manual'"
            )
        if "regeneration_count" not in columns:
            await self._connection.execute(
                "ALTER TABLE wiki_articles ADD COLUMN regeneration_count INTEGER DEFAULT 0"
            )

        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self.logger.debug(
                "Wiki database closed",
                component=LogComponent.WIKI,
            )

    async def __aenter__(self) -> "WikiDatabase":
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
    # Article CRUD
    # =========================================================================

    async def upsert_article(self, article: WikiArticle) -> str:
        """
        Insert or update a wiki article.

        Args:
            article: WikiArticle to store.

        Returns:
            Article ID.
        """
        row = article.to_sqlite_row()
        await self.connection.execute(
            """
            INSERT INTO wiki_articles (
                id, article_type, title, subtitle, content,
                module_name, source_hash, generation_status,
                generated_at, generation_model, word_count,
                estimated_read_time, last_trigger_source,
                regeneration_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                subtitle = excluded.subtitle,
                content = excluded.content,
                source_hash = excluded.source_hash,
                generation_status = excluded.generation_status,
                generated_at = excluded.generated_at,
                generation_model = excluded.generation_model,
                word_count = excluded.word_count,
                estimated_read_time = excluded.estimated_read_time,
                last_trigger_source = excluded.last_trigger_source,
                regeneration_count = excluded.regeneration_count
            """,
            row,
        )
        await self.connection.commit()
        return article.id

    async def get_article(self, article_id: str) -> Optional[WikiArticle]:
        """Get a single article by ID."""
        async with self.connection.execute(
            "SELECT * FROM wiki_articles WHERE id = ?",
            (article_id,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return WikiArticle.from_sqlite_row(dict(row))
        return None

    async def list_articles(
        self,
        article_type: Optional[ArticleType] = None,
    ) -> List[WikiArticle]:
        """
        List articles, optionally filtered by type.

        Args:
            article_type: Filter by article type, or None for all.

        Returns:
            List of WikiArticle objects.
        """
        articles = []
        if article_type:
            query = "SELECT * FROM wiki_articles WHERE article_type = ? ORDER BY title"
            params = (article_type.value,)
        else:
            query = "SELECT * FROM wiki_articles ORDER BY article_type, title"
            params = ()

        async with self.connection.execute(query, params) as cursor:
            async for row in cursor:
                articles.append(WikiArticle.from_sqlite_row(dict(row)))
        return articles

    async def delete_article(self, article_id: str) -> bool:
        """Delete an article by ID. Returns True if deleted."""
        cursor = await self.connection.execute(
            "DELETE FROM wiki_articles WHERE id = ?",
            (article_id,),
        )
        await self.connection.commit()
        return cursor.rowcount > 0

    async def get_article_count(self) -> int:
        """Get total number of articles."""
        async with self.connection.execute(
            "SELECT COUNT(*) FROM wiki_articles"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_stale_articles(self) -> List[WikiArticle]:
        """
        Get articles that have source_hash but may be outdated.

        Returns articles with generation_status='complete' that
        have a source_hash (i.e., AI-generated, checkable).
        """
        articles = []
        async with self.connection.execute(
            """
            SELECT * FROM wiki_articles
            WHERE generation_status = 'complete'
            AND source_hash IS NOT NULL
            ORDER BY title
            """
        ) as cursor:
            async for row in cursor:
                articles.append(WikiArticle.from_sqlite_row(dict(row)))
        return articles


# Module-level singleton
_wiki_database: Optional[WikiDatabase] = None


async def get_wiki_database() -> WikiDatabase:
    """Get or create singleton wiki database."""
    global _wiki_database
    if _wiki_database is None:
        _wiki_database = WikiDatabase()
        await _wiki_database.connect()
    return _wiki_database


async def close_wiki_database() -> None:
    """Close the singleton wiki database."""
    global _wiki_database
    if _wiki_database is not None:
        await _wiki_database.close()
        _wiki_database = None
