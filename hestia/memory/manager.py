"""
Memory Manager for Hestia.

Coordinates SQLite (structured data) and ChromaDB (embeddings)
to provide unified memory storage and retrieval.

Based on ADR-013: Tag-based memory schema.
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from hestia.logging import get_logger, LogComponent
from hestia.memory.database import MemoryDatabase, get_database
from hestia.memory.vector_store import VectorStore, get_vector_store
from hestia.memory.tagger import AutoTagger, get_tagger
from hestia.memory.models import (
    ConversationChunk,
    ChunkTags,
    ChunkMetadata,
    ChunkType,
    MemoryScope,
    MemoryStatus,
    MemoryQuery,
    MemorySearchResult,
)


class MemoryManager:
    """
    Unified memory management for Hestia.

    Coordinates:
    - SQLite for structured metadata and tags
    - ChromaDB for vector embeddings and semantic search
    - Auto-tagger for extracting tags from content

    Implements ADR-002 (Governed Memory) and ADR-013 (Tag-Based Schema).
    """

    def __init__(
        self,
        database: Optional[MemoryDatabase] = None,
        vector_store: Optional[VectorStore] = None,
        tagger: Optional[AutoTagger] = None,
    ):
        """
        Initialize memory manager.

        Args:
            database: SQLite database instance.
            vector_store: ChromaDB vector store instance.
            tagger: Auto-tagger instance.
        """
        self._database = database
        self._vector_store = vector_store
        self._tagger = tagger
        self.logger = get_logger()

        # Current session tracking
        self._current_session_id: Optional[str] = None

    async def initialize(self, timeout: float = 30.0) -> None:
        """
        Initialize all storage backends.

        Args:
            timeout: Maximum seconds to wait for database initialization.

        Raises:
            RuntimeError: If initialization times out.
        """
        try:
            if self._database is None:
                self._database = await asyncio.wait_for(
                    get_database(),
                    timeout=timeout
                )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Database initialization timed out after {timeout}s")

        if self._vector_store is None:
            self._vector_store = get_vector_store()
        if self._tagger is None:
            self._tagger = get_tagger()

        self.logger.info(
            "Memory manager initialized",
            component=LogComponent.MEMORY,
            data={
                "vector_count": self._vector_store.count(),
            }
        )

    async def close(self) -> None:
        """Close all storage backends."""
        if self._database:
            await self._database.close()
        if self._vector_store:
            self._vector_store.close()

    async def __aenter__(self) -> "MemoryManager":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def database(self) -> MemoryDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("Memory manager not initialized")
        return self._database

    @property
    def vector_store(self) -> VectorStore:
        """Get vector store instance."""
        if self._vector_store is None:
            raise RuntimeError("Memory manager not initialized")
        return self._vector_store

    @property
    def tagger(self) -> AutoTagger:
        """Get tagger instance."""
        if self._tagger is None:
            raise RuntimeError("Memory manager not initialized")
        return self._tagger

    # Session Management

    async def start_session(
        self,
        mode: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> str:
        """
        Start a new conversation session.

        Args:
            mode: Initial persona mode (Tia, Mira, Olly).
            device_id: Device identifier.

        Returns:
            Session ID.
        """
        session_id = f"session-{uuid4().hex[:12]}"

        # Await session creation to ensure database consistency
        await self.database.create_session(
            session_id,
            mode=mode,
            device_id=device_id
        )

        self._current_session_id = session_id

        self.logger.info(
            f"Started session: {session_id}",
            component=LogComponent.MEMORY,
            data={"session_id": session_id, "mode": mode}
        )

        return session_id

    async def end_session(self, summary: Optional[str] = None) -> None:
        """
        End the current session.

        Args:
            summary: Optional session summary.
        """
        if self._current_session_id:
            await self.database.end_session(self._current_session_id, summary)
            self.logger.info(
                f"Ended session: {self._current_session_id}",
                component=LogComponent.MEMORY
            )
            self._current_session_id = None

    @property
    def current_session_id(self) -> Optional[str]:
        """Get current session ID if one exists."""
        return self._current_session_id

    async def get_or_create_session_id(
        self,
        mode: Optional[str] = None,
        device_id: Optional[str] = None
    ) -> str:
        """Get current session ID, creating one if needed."""
        if self._current_session_id is None:
            self._current_session_id = await self.start_session(mode=mode, device_id=device_id)
        return self._current_session_id

    # Memory Storage

    async def store(
        self,
        content: str,
        chunk_type: ChunkType = ChunkType.CONVERSATION,
        tags: Optional[ChunkTags] = None,
        metadata: Optional[ChunkMetadata] = None,
        session_id: Optional[str] = None,
        auto_tag: bool = True,
        scope: MemoryScope = MemoryScope.SESSION,
    ) -> ConversationChunk:
        """
        Store content in memory.

        Args:
            content: The content to store.
            chunk_type: Type of content.
            tags: Optional pre-defined tags.
            metadata: Optional pre-defined metadata.
            session_id: Session to associate with.
            auto_tag: Whether to run auto-tagging.
            scope: Memory scope.

        Returns:
            The created ConversationChunk.
        """
        # Get or create session if needed
        if session_id is None:
            session_id = await self.get_or_create_session_id()

        # Quick tag for immediate use
        if tags is None or metadata is None:
            quick_tags, quick_metadata = self.tagger.quick_tag(content)
            tags = tags or quick_tags
            metadata = metadata or quick_metadata

        # Create chunk
        chunk = ConversationChunk.create(
            content=content,
            session_id=session_id,
            chunk_type=chunk_type,
            tags=tags,
            metadata=metadata,
            scope=scope,
        )

        # Store in both backends
        await self.database.store_chunk(chunk)
        self.vector_store.add_chunk(chunk)

        self.logger.log_memory_access(
            operation="store",
            scope=scope.value,
            data={
                "chunk_id": chunk.id,
                "chunk_type": chunk_type.value,
                "content_length": len(content),
            }
        )

        # Run async auto-tagging if enabled (non-blocking)
        if auto_tag:
            asyncio.create_task(self._async_tag_chunk(chunk))

        return chunk

    async def _async_tag_chunk(self, chunk: ConversationChunk) -> None:
        """Run auto-tagging asynchronously and update chunk."""
        try:
            new_tags, new_metadata = await self.tagger.extract_tags(
                chunk.content,
                existing_tags=chunk.tags
            )

            # Update chunk with extracted tags
            chunk.tags = new_tags
            chunk.metadata = new_metadata

            await self.database.update_chunk(chunk)
            self.vector_store.update_chunk(chunk)

            self.logger.debug(
                f"Async tagged chunk: {chunk.id}",
                component=LogComponent.MEMORY,
                data={"topics": chunk.tags.topics}
            )

        except Exception as e:
            self.logger.warning(
                f"Async tagging failed for chunk {chunk.id}: {e}",
                component=LogComponent.MEMORY
            )

    async def store_exchange(
        self,
        user_message: str,
        assistant_response: str,
        mode: Optional[str] = None,
    ) -> tuple[ConversationChunk, ConversationChunk]:
        """
        Store a user-assistant exchange.

        Convenience method for storing conversation turns.

        Args:
            user_message: The user's message.
            assistant_response: The assistant's response.
            mode: Current persona mode.

        Returns:
            Tuple of (user_chunk, assistant_chunk).
        """
        tags = ChunkTags(mode=mode) if mode else ChunkTags()

        user_chunk = await self.store(
            content=f"User: {user_message}",
            chunk_type=ChunkType.CONVERSATION,
            tags=tags,
        )

        assistant_chunk = await self.store(
            content=f"Assistant: {assistant_response}",
            chunk_type=ChunkType.CONVERSATION,
            tags=tags,
            auto_tag=True,  # Tag the response
        )

        # Link chunks
        assistant_chunk.parent_id = user_chunk.id
        await self.database.update_chunk(assistant_chunk)

        return user_chunk, assistant_chunk

    # Memory Retrieval

    async def search(
        self,
        query: str,
        limit: int = 10,
        semantic_threshold: float = 0.7,
        **filters
    ) -> List[MemorySearchResult]:
        """
        Search memory with semantic and filter queries.

        Args:
            query: The search query.
            limit: Maximum results.
            semantic_threshold: Minimum semantic similarity.
            **filters: Additional filters (topics, entities, etc.).

        Returns:
            List of MemorySearchResult.
        """
        # First, do semantic search in vector store
        vector_results = self.vector_store.search(
            query=query,
            n_results=limit * 2,  # Get more for filtering
            min_score=semantic_threshold,
        )

        if not vector_results:
            return []

        chunk_ids = [r[0] for r in vector_results]
        scores = {r[0]: r[1] for r in vector_results}

        # Build query with filters
        memory_query = MemoryQuery(
            semantic_query=query,
            semantic_threshold=semantic_threshold,
            limit=limit,
            **filters
        )

        # Get chunks from database with filters
        chunks = await self.database.query_chunks(memory_query, chunk_ids=chunk_ids)

        # Build results with scores
        results = []
        for chunk in chunks:
            score = scores.get(chunk.id, 0.0)
            results.append(MemorySearchResult(
                chunk=chunk,
                relevance_score=score,
                match_type="semantic"
            ))

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        self.logger.log_memory_access(
            operation="search",
            scope="all",
            data={
                "query_preview": query[:50],
                "result_count": len(results),
                "filters": list(filters.keys()),
            }
        )

        return results[:limit]

    async def get_recent(
        self,
        limit: int = 20,
        session_id: Optional[str] = None,
    ) -> List[ConversationChunk]:
        """
        Get recent memory chunks.

        Args:
            limit: Maximum results.
            session_id: Optional session filter.

        Returns:
            List of recent chunks.
        """
        query = MemoryQuery(
            session_id=session_id or self._current_session_id,
            limit=limit,
        )
        return await self.database.query_chunks(query)

    async def get_by_tags(
        self,
        topics: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        status: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[ConversationChunk]:
        """
        Get chunks by tag filters.

        Args:
            topics: Filter by topics.
            entities: Filter by entities.
            status: Filter by status.
            limit: Maximum results.

        Returns:
            List of matching chunks.
        """
        query = MemoryQuery(
            topics=topics,
            entities=entities,
            status=status,
            limit=limit,
        )
        return await self.database.query_chunks(query)

    async def get_action_items(self, resolved: bool = False) -> List[ConversationChunk]:
        """Get unresolved action items."""
        query = MemoryQuery(
            has_action_item=True,
            status=["active"] if not resolved else None,
            limit=50,
        )
        return await self.database.query_chunks(query)

    async def get_decisions(self, limit: int = 20) -> List[ConversationChunk]:
        """Get recorded decisions."""
        query = MemoryQuery(
            has_decision=True,
            limit=limit,
        )
        return await self.database.query_chunks(query)

    # Memory Management (ADR-002)

    async def stage_for_review(self, chunk_id: str) -> None:
        """
        Stage a chunk for human review before long-term storage.

        Implements ADR-002: Governed Memory Persistence.
        """
        await self.database.stage_for_review(chunk_id)

        self.logger.info(
            f"Staged chunk for review: {chunk_id}",
            component=LogComponent.MEMORY
        )

    async def commit_to_long_term(
        self,
        chunk_id: str,
        reviewer_notes: Optional[str] = None
    ) -> None:
        """
        Commit a reviewed chunk to long-term memory.

        Args:
            chunk_id: The chunk to commit.
            reviewer_notes: Optional notes from reviewer.
        """
        await self.database.commit_chunk(chunk_id, reviewer_notes)

        self.logger.info(
            f"Committed chunk to long-term: {chunk_id}",
            component=LogComponent.MEMORY
        )

    async def get_pending_reviews(self) -> List[ConversationChunk]:
        """Get chunks pending human review."""
        return await self.database.get_pending_reviews()

    async def supersede_chunk(
        self,
        old_chunk_id: str,
        new_content: str,
        reason: str = ""
    ) -> ConversationChunk:
        """
        Create new chunk that supersedes an old one.

        Useful for correcting or updating information.

        Args:
            old_chunk_id: ID of chunk being superseded.
            new_content: Updated content.
            reason: Reason for superseding.

        Returns:
            The new chunk.
        """
        # Get old chunk
        old_chunk = await self.database.get_chunk(old_chunk_id)
        if not old_chunk:
            raise ValueError(f"Chunk not found: {old_chunk_id}")

        # Create new chunk that supersedes
        new_chunk = await self.store(
            content=new_content,
            chunk_type=old_chunk.chunk_type,
            tags=old_chunk.tags,
        )
        new_chunk.supersedes = old_chunk_id

        # Mark old chunk as superseded
        old_chunk.status = MemoryStatus.SUPERSEDED
        await self.database.update_chunk(old_chunk)
        await self.database.update_chunk(new_chunk)

        self.logger.info(
            f"Superseded chunk {old_chunk_id} with {new_chunk.id}",
            component=LogComponent.MEMORY,
            data={"reason": reason}
        )

        return new_chunk

    # Context Building for Inference

    async def build_context(
        self,
        query: str,
        max_tokens: int = 4000,
        include_recent: bool = True,
    ) -> str:
        """
        Build context string for inference from relevant memories.

        Args:
            query: Current user query for relevance filtering.
            max_tokens: Maximum tokens to include.
            include_recent: Whether to include recent conversation.

        Returns:
            Formatted context string.
        """
        context_parts = []
        estimated_tokens = 0

        # Include relevant memories from search
        results = await self.search(query, limit=5, semantic_threshold=0.6)
        if results:
            context_parts.append("## Relevant Memory\n")
            for result in results:
                if estimated_tokens > max_tokens * 0.6:
                    break
                chunk_text = f"- [{result.chunk.timestamp.strftime('%Y-%m-%d')}] {result.chunk.content[:500]}\n"
                context_parts.append(chunk_text)
                estimated_tokens += len(chunk_text.split()) * 1.3  # Rough token estimate

        # Include recent conversation if space allows
        if include_recent and estimated_tokens < max_tokens * 0.8:
            recent = await self.get_recent(limit=10)
            if recent:
                context_parts.append("\n## Recent Conversation\n")
                for chunk in reversed(recent):  # Oldest first
                    if estimated_tokens > max_tokens:
                        break
                    chunk_text = f"{chunk.content[:300]}\n"
                    context_parts.append(chunk_text)
                    estimated_tokens += len(chunk_text.split()) * 1.3

        return "".join(context_parts)


# Module-level singleton
_manager: Optional[MemoryManager] = None


async def get_memory_manager() -> MemoryManager:
    """Get or create the singleton memory manager instance."""
    global _manager
    if _manager is None:
        _manager = MemoryManager()
        await _manager.initialize()
    return _manager
