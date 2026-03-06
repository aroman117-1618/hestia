"""
SQLite database for Hestia memory storage.

Stores structured metadata, tags, and relationships.
Vector embeddings stored separately in ChromaDB.
"""

from pathlib import Path
from typing import List, Optional

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent
from hestia.memory.models import (
    ConversationChunk,
    MemoryQuery,
    MemoryScope,
    MemoryStatus,
)


# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
-- Memory chunks table (core storage)
CREATE TABLE IF NOT EXISTS memory_chunks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    content TEXT NOT NULL,
    chunk_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    tags TEXT NOT NULL,          -- JSON blob
    metadata TEXT NOT NULL,      -- JSON blob
    chunk_refs TEXT NOT NULL,    -- JSON array of chunk IDs (renamed from 'references')
    supersedes TEXT,             -- ID of chunk this supersedes
    parent_id TEXT,              -- For threaded conversations
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_chunks_session ON memory_chunks(session_id);
CREATE INDEX IF NOT EXISTS idx_chunks_timestamp ON memory_chunks(timestamp);
CREATE INDEX IF NOT EXISTS idx_chunks_type ON memory_chunks(chunk_type);
CREATE INDEX IF NOT EXISTS idx_chunks_scope ON memory_chunks(scope);
CREATE INDEX IF NOT EXISTS idx_chunks_status ON memory_chunks(status);

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    last_activity TEXT,          -- Set when session ends; in-memory Conversation.last_activity used for TTL
    mode TEXT,                   -- Tia, Mira, Olly
    device_id TEXT,
    summary TEXT,
    chunk_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_sessions_started ON sessions(started_at);

-- Tag index table (for efficient tag queries)
CREATE TABLE IF NOT EXISTS chunk_tags (
    chunk_id TEXT NOT NULL,
    tag_type TEXT NOT NULL,      -- topics, entities, people, status, custom
    tag_value TEXT NOT NULL,
    FOREIGN KEY (chunk_id) REFERENCES memory_chunks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tags_type_value ON chunk_tags(tag_type, tag_value);
CREATE INDEX IF NOT EXISTS idx_tags_chunk ON chunk_tags(chunk_id);

-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Staged memory for human review (ADR-002)
CREATE TABLE IF NOT EXISTS staged_memory (
    id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL,
    staged_at TEXT NOT NULL,
    reviewed_at TEXT,
    review_status TEXT,          -- pending, approved, rejected
    reviewer_notes TEXT,
    FOREIGN KEY (chunk_id) REFERENCES memory_chunks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_staged_status ON staged_memory(review_status);

-- Source deduplication (Sprint 11.5 — prevents duplicate ingestion)
CREATE TABLE IF NOT EXISTS source_dedup (
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    chunk_id TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    batch_id TEXT,
    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_dedup_batch ON source_dedup(batch_id);

-- Ingestion log (Sprint 11.5 — batch tracking for rollback)
CREATE TABLE IF NOT EXISTS source_ingestion_log (
    batch_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    items_processed INTEGER DEFAULT 0,
    items_stored INTEGER DEFAULT 0,
    items_skipped INTEGER DEFAULT 0,
    status TEXT DEFAULT 'running'
);
"""


class MemoryDatabase(BaseDatabase):
    """
    Async SQLite database for memory storage.

    Handles structured metadata while ChromaDB handles embeddings.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("memory", db_path)
        self.logger = get_logger()

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        await super().connect()
        self.logger.info(
            f"Memory database connected: {self.db_path}",
            component=LogComponent.MEMORY,
            data={"db_path": str(self.db_path)}
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript(SCHEMA_SQL)
        await self._connection.commit()

        # Check/update schema version
        async with self._connection.execute(
            "SELECT MAX(version) FROM schema_version"
        ) as cursor:
            row = await cursor.fetchone()
            current_version = row[0] if row and row[0] else 0

        if current_version < SCHEMA_VERSION:
            await self._connection.execute(
                "INSERT INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,)
            )
            await self._connection.commit()

    async def store_chunk(self, chunk: ConversationChunk) -> str:
        """
        Store a memory chunk.

        Args:
            chunk: The chunk to store.

        Returns:
            The chunk ID.
        """
        row = chunk.to_sqlite_row()

        await self._connection.execute(
            """
            INSERT INTO memory_chunks
            (id, session_id, timestamp, content, chunk_type, scope, status,
             tags, metadata, chunk_refs, supersedes, parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"], row["session_id"], row["timestamp"], row["content"],
                row["chunk_type"], row["scope"], row["status"],
                row["tags"], row["metadata"], row["chunk_refs"],
                row["supersedes"], row["parent_id"]
            )
        )

        # Store tags in index table
        await self._index_chunk_tags(chunk)

        await self._connection.commit()

        self.logger.log_memory_access(
            operation="store",
            scope=chunk.scope.value,
            data={"chunk_id": chunk.id, "chunk_type": chunk.chunk_type.value}
        )

        return chunk.id

    async def _index_chunk_tags(self, chunk: ConversationChunk) -> None:
        """Index chunk tags for efficient querying."""
        tag_rows = []

        for topic in chunk.tags.topics:
            tag_rows.append((chunk.id, "topics", topic))
        for entity in chunk.tags.entities:
            tag_rows.append((chunk.id, "entities", entity))
        for person in chunk.tags.people:
            tag_rows.append((chunk.id, "people", person))
        for status in chunk.tags.status:
            tag_rows.append((chunk.id, "status", status))
        if chunk.tags.mode:
            tag_rows.append((chunk.id, "mode", chunk.tags.mode))
        for key, value in chunk.tags.custom.items():
            tag_rows.append((chunk.id, f"custom:{key}", value))

        if tag_rows:
            await self._connection.executemany(
                "INSERT INTO chunk_tags (chunk_id, tag_type, tag_value) VALUES (?, ?, ?)",
                tag_rows
            )

    async def get_chunk(self, chunk_id: str) -> Optional[ConversationChunk]:
        """Get a chunk by ID."""
        async with self._connection.execute(
            "SELECT * FROM memory_chunks WHERE id = ?",
            (chunk_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return ConversationChunk.from_sqlite_row(dict(row))
        return None

    async def update_chunk(self, chunk: ConversationChunk) -> None:
        """Update an existing chunk."""
        row = chunk.to_sqlite_row()

        await self._connection.execute(
            """
            UPDATE memory_chunks SET
                content = ?, chunk_type = ?, scope = ?, status = ?,
                tags = ?, metadata = ?, chunk_refs = ?, supersedes = ?,
                parent_id = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                row["content"], row["chunk_type"], row["scope"], row["status"],
                row["tags"], row["metadata"], row["chunk_refs"], row["supersedes"],
                row["parent_id"], row["id"]
            )
        )

        # Re-index tags
        await self._connection.execute(
            "DELETE FROM chunk_tags WHERE chunk_id = ?",
            (chunk.id,)
        )
        await self._index_chunk_tags(chunk)

        await self._connection.commit()

    async def delete_chunk(self, chunk_id: str) -> bool:
        """Delete a chunk by ID."""
        async with self._connection.execute(
            "DELETE FROM memory_chunks WHERE id = ?",
            (chunk_id,)
        ) as cursor:
            await self._connection.commit()
            return cursor.rowcount > 0

    async def query_chunks(
        self,
        query: MemoryQuery,
        chunk_ids: Optional[List[str]] = None,
    ) -> List[ConversationChunk]:
        """
        Query chunks with filters.

        Args:
            query: Query parameters.
            chunk_ids: Optional list of chunk IDs to filter by (from vector search).

        Returns:
            List of matching chunks.
        """
        conditions = []
        params = []

        # Filter by chunk IDs (from vector search)
        if chunk_ids is not None:
            if not chunk_ids:
                return []  # No results if empty list provided
            placeholders = ",".join("?" * len(chunk_ids))
            conditions.append(f"id IN ({placeholders})")
            params.extend(chunk_ids)

        # Temporal filters
        if query.start_date:
            conditions.append("timestamp >= ?")
            params.append(query.start_date.isoformat())
        if query.end_date:
            conditions.append("timestamp <= ?")
            params.append(query.end_date.isoformat())
        if query.session_id:
            conditions.append("session_id = ?")
            params.append(query.session_id)

        # Type filters
        if query.chunk_types:
            placeholders = ",".join("?" * len(query.chunk_types))
            conditions.append(f"chunk_type IN ({placeholders})")
            params.extend([ct.value for ct in query.chunk_types])

        # Scope filters
        if query.scopes:
            placeholders = ",".join("?" * len(query.scopes))
            conditions.append(f"scope IN ({placeholders})")
            params.extend([s.value for s in query.scopes])

        # Status filter (exclude superseded/archived by default)
        conditions.append("status NOT IN ('superseded', 'archived')")

        # Metadata filters (JSON queries)
        if query.has_code is not None:
            conditions.append("json_extract(metadata, '$.has_code') = ?")
            params.append(1 if query.has_code else 0)
        if query.has_decision is not None:
            conditions.append("json_extract(metadata, '$.has_decision') = ?")
            params.append(1 if query.has_decision else 0)
        if query.has_action_item is not None:
            conditions.append("json_extract(metadata, '$.has_action_item') = ?")
            params.append(1 if query.has_action_item else 0)
        if query.source is not None:
            conditions.append("json_extract(metadata, '$.source') = ?")
            params.append(query.source.value)

        # Build WHERE clause
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Build query
        sql = f"""
            SELECT * FROM memory_chunks
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
        """
        params.extend([query.limit, query.offset])

        chunks = []
        async with self._connection.execute(sql, params) as cursor:
            async for row in cursor:
                chunks.append(ConversationChunk.from_sqlite_row(dict(row)))

        # Apply tag filters (post-query for flexibility)
        if any([query.topics, query.entities, query.people, query.mode, query.status]):
            chunks = self._filter_by_tags(chunks, query)

        return chunks

    def _filter_by_tags(
        self,
        chunks: List[ConversationChunk],
        query: MemoryQuery
    ) -> List[ConversationChunk]:
        """Filter chunks by tag criteria."""
        filtered = []

        for chunk in chunks:
            match = True

            if query.topics:
                if not any(t in chunk.tags.topics for t in query.topics):
                    match = False
            if query.entities and match:
                if not any(e in chunk.tags.entities for e in query.entities):
                    match = False
            if query.people and match:
                if not any(p in chunk.tags.people for p in query.people):
                    match = False
            if query.mode and match:
                if chunk.tags.mode != query.mode:
                    match = False
            if query.status and match:
                if not any(s in chunk.tags.status for s in query.status):
                    match = False

            if match:
                filtered.append(chunk)

        return filtered

    async def get_session_chunks(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[ConversationChunk]:
        """Get all chunks for a session."""
        query = MemoryQuery(session_id=session_id, limit=limit)
        return await self.query_chunks(query)

    async def stage_for_review(self, chunk_id: str) -> None:
        """Stage a chunk for human review (ADR-002)."""
        await self._connection.execute(
            """
            INSERT INTO staged_memory (id, chunk_id, staged_at, review_status)
            VALUES (?, ?, datetime('now'), 'pending')
            """,
            (f"staged-{chunk_id}", chunk_id)
        )

        # Update chunk status
        await self._connection.execute(
            "UPDATE memory_chunks SET status = ? WHERE id = ?",
            (MemoryStatus.STAGED.value, chunk_id)
        )
        await self._connection.commit()

    async def commit_chunk(self, chunk_id: str, reviewer_notes: Optional[str] = None) -> None:
        """Commit a staged chunk to long-term memory."""
        await self._connection.execute(
            """
            UPDATE staged_memory SET
                reviewed_at = datetime('now'),
                review_status = 'approved',
                reviewer_notes = ?
            WHERE chunk_id = ?
            """,
            (reviewer_notes, chunk_id)
        )

        await self._connection.execute(
            """
            UPDATE memory_chunks SET
                status = ?,
                scope = ?
            WHERE id = ?
            """,
            (MemoryStatus.COMMITTED.value, MemoryScope.LONG_TERM.value, chunk_id)
        )
        await self._connection.commit()

    async def get_pending_reviews(self) -> List[ConversationChunk]:
        """Get chunks pending human review."""
        chunks = []
        async with self._connection.execute(
            """
            SELECT mc.* FROM memory_chunks mc
            JOIN staged_memory sm ON mc.id = sm.chunk_id
            WHERE sm.review_status = 'pending'
            ORDER BY sm.staged_at DESC
            """
        ) as cursor:
            async for row in cursor:
                chunks.append(ConversationChunk.from_sqlite_row(dict(row)))
        return chunks

    async def create_session(
        self,
        session_id: str,
        mode: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> None:
        """Create a new session record."""
        await self._connection.execute(
            """
            INSERT INTO sessions (id, started_at, mode, device_id)
            VALUES (?, datetime('now'), ?, ?)
            """,
            (session_id, mode, device_id)
        )
        await self._connection.commit()

    async def end_session(self, session_id: str, summary: Optional[str] = None) -> None:
        """End a session and update summary."""
        # Count chunks
        async with self._connection.execute(
            "SELECT COUNT(*) FROM memory_chunks WHERE session_id = ?",
            (session_id,)
        ) as cursor:
            row = await cursor.fetchone()
            chunk_count = row[0] if row else 0

        await self._connection.execute(
            """
            UPDATE sessions SET
                ended_at = datetime('now'),
                last_activity = datetime('now'),
                summary = ?,
                chunk_count = ?
            WHERE id = ?
            """,
            (summary, chunk_count, session_id)
        )
        await self._connection.commit()

    # -- Source Deduplication (Sprint 11.5) --------------------------------

    async def check_duplicate(self, source: str, source_id: str) -> bool:
        """Check if a source item has already been ingested."""
        async with self._connection.execute(
            "SELECT 1 FROM source_dedup WHERE source = ? AND source_id = ?",
            (source, source_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def record_dedup(
        self, source: str, source_id: str, chunk_id: str, batch_id: Optional[str] = None
    ) -> None:
        """Record that a source item has been ingested."""
        await self._connection.execute(
            """INSERT OR IGNORE INTO source_dedup (source, source_id, chunk_id, batch_id)
               VALUES (?, ?, ?, ?)""",
            (source, source_id, chunk_id, batch_id),
        )
        await self._connection.commit()

    async def rollback_batch(self, batch_id: str) -> int:
        """Delete all chunks from a specific ingestion batch. Returns count deleted."""
        # Get chunk IDs for this batch
        chunk_ids = []
        async with self._connection.execute(
            "SELECT chunk_id FROM source_dedup WHERE batch_id = ?", (batch_id,)
        ) as cursor:
            async for row in cursor:
                chunk_ids.append(row[0])

        if not chunk_ids:
            return 0

        # Delete chunks
        placeholders = ",".join("?" * len(chunk_ids))
        await self._connection.execute(
            f"DELETE FROM memory_chunks WHERE id IN ({placeholders})", chunk_ids
        )
        # Delete dedup entries
        await self._connection.execute(
            "DELETE FROM source_dedup WHERE batch_id = ?", (batch_id,)
        )
        # Update ingestion log
        await self._connection.execute(
            "UPDATE source_ingestion_log SET status = 'rolled_back' WHERE batch_id = ?",
            (batch_id,),
        )
        await self._connection.commit()
        return len(chunk_ids)

    # -- Ingestion Log (Sprint 11.5) --------------------------------------

    async def start_ingestion_batch(self, batch_id: str, source: str) -> None:
        """Record the start of an ingestion batch."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            """INSERT INTO source_ingestion_log
               (batch_id, source, started_at, status)
               VALUES (?, ?, ?, 'running')""",
            (batch_id, source, now),
        )
        await self._connection.commit()

    async def complete_ingestion_batch(
        self, batch_id: str, items_processed: int, items_stored: int, items_skipped: int
    ) -> None:
        """Record completion of an ingestion batch."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            """UPDATE source_ingestion_log SET
                completed_at = ?, items_processed = ?, items_stored = ?,
                items_skipped = ?, status = 'completed'
               WHERE batch_id = ?""",
            (now, items_processed, items_stored, items_skipped, batch_id),
        )
        await self._connection.commit()

    async def fail_ingestion_batch(self, batch_id: str, items_processed: int) -> None:
        """Record failure of an ingestion batch."""
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        await self._connection.execute(
            """UPDATE source_ingestion_log SET
                completed_at = ?, items_processed = ?, status = 'failed'
               WHERE batch_id = ?""",
            (now, items_processed, batch_id),
        )
        await self._connection.commit()

    async def get_ingestion_log(
        self, source: Optional[str] = None, limit: int = 20
    ) -> list:
        """Get recent ingestion log entries."""
        if source:
            sql = "SELECT * FROM source_ingestion_log WHERE source = ? ORDER BY started_at DESC LIMIT ?"
            params: list = [source, limit]
        else:
            sql = "SELECT * FROM source_ingestion_log ORDER BY started_at DESC LIMIT ?"
            params = [limit]

        rows = []
        async with self._connection.execute(sql, params) as cursor:
            async for row in cursor:
                rows.append(dict(row))
        return rows


# Module-level singleton
_database: Optional[MemoryDatabase] = None


async def get_database() -> MemoryDatabase:
    """Get or create the singleton database instance."""
    global _database
    if _database is None:
        _database = MemoryDatabase()
        await _database.connect()
    return _database
