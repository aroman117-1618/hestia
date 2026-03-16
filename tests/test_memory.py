"""
Tests for Hestia memory layer.

Tests cover:
- Models and data structures
- SQLite database operations
- ChromaDB vector store operations
- Auto-tagger (quick tagging)
- Memory manager integration
"""

import asyncio
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Generator

import pytest

from hestia.memory.models import (
    ConversationChunk,
    ChunkTags,
    ChunkMetadata,
    ChunkType,
    MemoryScope,
    MemorySource,
    MemoryStatus,
    MemoryQuery,
    MemorySearchResult,
)
from hestia.memory.database import MemoryDatabase
from hestia.memory.vector_store import VectorStore
from hestia.memory.tagger import AutoTagger
from hestia.memory.manager import MemoryManager


# ============== Fixtures ==============

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_chunk() -> ConversationChunk:
    """Create a sample conversation chunk."""
    return ConversationChunk.create(
        content="User: How do I implement secure credential storage?",
        session_id="test-session-001",
        chunk_type=ChunkType.CONVERSATION,
        tags=ChunkTags(
            topics=["security", "credentials"],
            entities=["Keychain", "Secure Enclave"],
            people=["andrew"],
            mode="Tia",
        ),
        metadata=ChunkMetadata(
            has_code=False,
            has_decision=False,
            has_action_item=False,
            sentiment="neutral",
        ),
    )


@pytest.fixture
async def database(temp_dir: Path) -> MemoryDatabase:
    """Create a test database."""
    db = MemoryDatabase(db_path=temp_dir / "test_memory.db")
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
def vector_store(temp_dir: Path) -> VectorStore:
    """Create a test vector store."""
    store = VectorStore(persist_directory=temp_dir / "chromadb")
    store.connect()
    yield store
    store.close()


@pytest.fixture
def tagger() -> AutoTagger:
    """Create an auto-tagger instance."""
    return AutoTagger()


@pytest.fixture
async def memory_manager(temp_dir: Path) -> MemoryManager:
    """Create a test memory manager."""
    db = MemoryDatabase(db_path=temp_dir / "test_memory.db")
    await db.connect()

    store = VectorStore(persist_directory=temp_dir / "chromadb")
    store.connect()

    tagger = AutoTagger()

    manager = MemoryManager(
        database=db,
        vector_store=store,
        tagger=tagger,
    )
    await manager.initialize()

    yield manager

    await manager.close()


# ============== Model Tests ==============

class TestModels:
    """Tests for memory data models."""

    def test_chunk_create(self):
        """Test creating a conversation chunk."""
        chunk = ConversationChunk.create(
            content="Test content",
            session_id="test-session",
        )

        assert chunk.id.startswith("chunk-")
        assert chunk.content == "Test content"
        assert chunk.session_id == "test-session"
        assert chunk.chunk_type == ChunkType.CONVERSATION
        assert chunk.scope == MemoryScope.SESSION
        assert chunk.status == MemoryStatus.ACTIVE

    def test_chunk_tags(self):
        """Test ChunkTags serialization."""
        tags = ChunkTags(
            topics=["security", "auth"],
            entities=["Face ID"],
            people=["andrew"],
            mode="Tia",
            custom={"project": "hestia"},
        )

        # Round-trip through dict
        data = tags.to_dict()
        restored = ChunkTags.from_dict(data)

        assert restored.topics == tags.topics
        assert restored.entities == tags.entities
        assert restored.mode == tags.mode
        assert restored.custom == tags.custom

    def test_chunk_metadata(self):
        """Test ChunkMetadata serialization."""
        metadata = ChunkMetadata(
            has_code=True,
            has_decision=True,
            sentiment="positive",
            confidence=0.95,
        )

        data = metadata.to_dict()
        restored = ChunkMetadata.from_dict(data)

        assert restored.has_code == metadata.has_code
        assert restored.has_decision == metadata.has_decision
        assert restored.sentiment == metadata.sentiment
        assert restored.confidence == metadata.confidence

    def test_chunk_to_sqlite_row(self, sample_chunk: ConversationChunk):
        """Test converting chunk to SQLite row."""
        row = sample_chunk.to_sqlite_row()

        assert row["id"] == sample_chunk.id
        assert row["session_id"] == sample_chunk.session_id
        assert row["content"] == sample_chunk.content
        assert row["chunk_type"] == "conversation"
        assert "security" in row["tags"]

    def test_memory_query_defaults(self):
        """Test MemoryQuery default values."""
        query = MemoryQuery()

        assert query.limit == 10
        assert query.offset == 0
        assert query.semantic_threshold == 0.7
        assert query.topics is None


# ============== Database Tests ==============

class TestDatabase:
    """Tests for SQLite database operations."""

    @pytest.mark.asyncio
    async def test_store_and_get_chunk(
        self,
        database: MemoryDatabase,
        sample_chunk: ConversationChunk
    ):
        """Test storing and retrieving a chunk."""
        chunk_id = await database.store_chunk(sample_chunk)

        retrieved = await database.get_chunk(chunk_id)

        assert retrieved is not None
        assert retrieved.id == sample_chunk.id
        assert retrieved.content == sample_chunk.content
        assert retrieved.tags.topics == sample_chunk.tags.topics

    @pytest.mark.asyncio
    async def test_update_chunk(
        self,
        database: MemoryDatabase,
        sample_chunk: ConversationChunk
    ):
        """Test updating a chunk."""
        await database.store_chunk(sample_chunk)

        # Modify and update
        sample_chunk.tags.topics.append("updated")
        sample_chunk.metadata.has_decision = True
        await database.update_chunk(sample_chunk)

        retrieved = await database.get_chunk(sample_chunk.id)

        assert "updated" in retrieved.tags.topics
        assert retrieved.metadata.has_decision is True

    @pytest.mark.asyncio
    async def test_delete_chunk(
        self,
        database: MemoryDatabase,
        sample_chunk: ConversationChunk
    ):
        """Test deleting a chunk."""
        await database.store_chunk(sample_chunk)

        deleted = await database.delete_chunk(sample_chunk.id)
        assert deleted is True

        retrieved = await database.get_chunk(sample_chunk.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_query_by_session(self, database: MemoryDatabase):
        """Test querying chunks by session ID."""
        session_id = "query-test-session"

        # Store multiple chunks
        for i in range(5):
            chunk = ConversationChunk.create(
                content=f"Message {i}",
                session_id=session_id,
            )
            await database.store_chunk(chunk)

        # Also store one in different session
        other_chunk = ConversationChunk.create(
            content="Other session",
            session_id="other-session",
        )
        await database.store_chunk(other_chunk)

        # Query by session
        query = MemoryQuery(session_id=session_id, limit=10)
        results = await database.query_chunks(query)

        assert len(results) == 5
        assert all(c.session_id == session_id for c in results)

    @pytest.mark.asyncio
    async def test_query_by_chunk_type(self, database: MemoryDatabase):
        """Test querying chunks by type."""
        # Store different types
        conv_chunk = ConversationChunk.create(
            content="Conversation",
            session_id="test",
            chunk_type=ChunkType.CONVERSATION,
        )
        decision_chunk = ConversationChunk.create(
            content="Decision made",
            session_id="test",
            chunk_type=ChunkType.DECISION,
        )

        await database.store_chunk(conv_chunk)
        await database.store_chunk(decision_chunk)

        # Query decisions only
        query = MemoryQuery(chunk_types=[ChunkType.DECISION])
        results = await database.query_chunks(query)

        assert len(results) == 1
        assert results[0].chunk_type == ChunkType.DECISION

    @pytest.mark.asyncio
    async def test_query_with_metadata_filter(self, database: MemoryDatabase):
        """Test querying with metadata filters."""
        # Chunk with code
        code_chunk = ConversationChunk.create(
            content="```python\nprint('hello')\n```",
            session_id="test",
        )
        code_chunk.metadata.has_code = True

        # Chunk without code
        text_chunk = ConversationChunk.create(
            content="Just some text",
            session_id="test",
        )

        await database.store_chunk(code_chunk)
        await database.store_chunk(text_chunk)

        # Query for code chunks
        query = MemoryQuery(has_code=True)
        results = await database.query_chunks(query)

        assert len(results) == 1
        assert results[0].metadata.has_code is True

    @pytest.mark.asyncio
    async def test_stage_and_commit(self, database: MemoryDatabase, sample_chunk: ConversationChunk):
        """Test staging and committing chunks for review."""
        await database.store_chunk(sample_chunk)

        # Stage for review
        await database.stage_for_review(sample_chunk.id)

        # Check it's pending
        pending = await database.get_pending_reviews()
        assert len(pending) == 1
        assert pending[0].id == sample_chunk.id

        # Commit
        await database.commit_chunk(sample_chunk.id, "Looks good")

        # Verify committed
        retrieved = await database.get_chunk(sample_chunk.id)
        assert retrieved.status == MemoryStatus.COMMITTED
        assert retrieved.scope == MemoryScope.LONG_TERM

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, database: MemoryDatabase):
        """Test session creation and ending."""
        session_id = "lifecycle-test"

        await database.create_session(session_id, mode="Tia", device_id="test-device")

        # Add some chunks
        for i in range(3):
            chunk = ConversationChunk.create(
                content=f"Message {i}",
                session_id=session_id,
            )
            await database.store_chunk(chunk)

        # End session
        await database.end_session(session_id, "Test session completed")

        # Verify chunk count was updated (would need to query sessions table)


# ============== Vector Store Tests ==============

class TestVectorStore:
    """Tests for ChromaDB vector store operations."""

    def test_add_and_search(self, vector_store: VectorStore, sample_chunk: ConversationChunk):
        """Test adding a chunk and searching."""
        vector_store.add_chunk(sample_chunk)

        # Search for similar content
        results = vector_store.search("credential storage security", n_results=5)

        assert len(results) > 0
        assert results[0][0] == sample_chunk.id
        assert results[0][1] > 0.5  # Should have decent similarity

    def test_search_with_threshold(self, vector_store: VectorStore):
        """Test search with minimum score threshold."""
        # Add chunks
        chunk1 = ConversationChunk.create(
            content="Python programming tutorial",
            session_id="test",
        )
        chunk2 = ConversationChunk.create(
            content="Security and encryption methods",
            session_id="test",
        )

        vector_store.add_chunk(chunk1)
        vector_store.add_chunk(chunk2)

        # Search with high threshold
        results = vector_store.search(
            "Python code examples",
            n_results=5,
            min_score=0.3
        )

        # Should find Python chunk with reasonable score
        assert any(r[0] == chunk1.id for r in results)

    def test_delete_chunk(self, vector_store: VectorStore, sample_chunk: ConversationChunk):
        """Test deleting a chunk from vector store."""
        vector_store.add_chunk(sample_chunk)

        # Verify it's there
        results = vector_store.search(sample_chunk.content, n_results=1)
        assert len(results) > 0

        # Delete
        vector_store.delete_chunk(sample_chunk.id)

        # Search should not find it
        results = vector_store.search(sample_chunk.content, n_results=1, min_score=0.9)
        assert not any(r[0] == sample_chunk.id for r in results)

    def test_add_multiple_chunks(self, vector_store: VectorStore):
        """Test batch adding chunks."""
        chunks = [
            ConversationChunk.create(content=f"Content {i}", session_id="test")
            for i in range(10)
        ]

        vector_store.add_chunks(chunks)

        assert vector_store.count() >= 10

    def test_update_chunk(self, vector_store: VectorStore, sample_chunk: ConversationChunk):
        """Test updating a chunk."""
        vector_store.add_chunk(sample_chunk)

        # Update content
        sample_chunk.content = "Updated content about databases and storage"
        vector_store.update_chunk(sample_chunk)

        # Search for new content
        results = vector_store.search("databases storage", n_results=1)
        assert results[0][0] == sample_chunk.id


# ============== Tagger Tests ==============

class TestTagger:
    """Tests for auto-tagger."""

    def test_quick_tag_code_detection(self, tagger: AutoTagger):
        """Test quick tagging detects code."""
        content = """Here's how to implement it:
        ```python
        def secure_store(key, value):
            return encrypt(value)
        ```
        """

        tags, metadata = tagger.quick_tag(content)

        assert metadata.has_code is True

    def test_quick_tag_decision_detection(self, tagger: AutoTagger):
        """Test quick tagging detects decisions."""
        content = "We've decided to use ChromaDB for vector storage."

        tags, metadata = tagger.quick_tag(content)

        assert metadata.has_decision is True

    def test_quick_tag_action_item_detection(self, tagger: AutoTagger):
        """Test quick tagging detects action items."""
        content = "TODO: implement the memory manager next."

        tags, metadata = tagger.quick_tag(content)

        assert metadata.has_action_item is True

    def test_quick_tag_question_detection(self, tagger: AutoTagger):
        """Test quick tagging detects unresolved questions."""
        content = "How should we handle the edge case when the database is empty?"

        tags, metadata = tagger.quick_tag(content)

        assert "unresolved" in tags.status

    def test_quick_tag_entity_extraction(self, tagger: AutoTagger):
        """Test quick tagging extracts common entities."""
        content = "We'll use ChromaDB and SQLite with Face ID for authentication."

        tags, metadata = tagger.quick_tag(content)

        assert "ChromaDB" in tags.entities
        assert "SQLite" in tags.entities
        assert "Face ID" in tags.entities


# ============== Memory Manager Tests ==============

class TestMemoryManager:
    """Tests for memory manager integration."""

    @pytest.mark.asyncio
    async def test_store_and_search(self, memory_manager: MemoryManager):
        """Test storing and searching memory."""
        # Store content
        chunk = await memory_manager.store(
            content="The security architecture uses Face ID for biometric authentication.",
            chunk_type=ChunkType.CONVERSATION,
            auto_tag=False,  # Skip async tagging for test
        )

        assert chunk.id is not None

        # Search for it
        results = await memory_manager.search(
            "biometric authentication Face ID",
            limit=5,
            semantic_threshold=0.3,
        )

        assert len(results) > 0
        assert any(r.chunk.id == chunk.id for r in results)

    @pytest.mark.asyncio
    async def test_import_relevance_penalty(self, memory_manager: MemoryManager):
        """Imported chunks get a 0.9x relevance penalty vs native conversation."""
        # Store identical content — one native, one imported
        native = await memory_manager.store(
            content="The capital of France is Paris, a beautiful city of lights.",
            chunk_type=ChunkType.CONVERSATION,
            auto_tag=False,
        )
        imported = await memory_manager.store(
            content="The capital of France is Paris, a beautiful city of lights.",
            chunk_type=ChunkType.CONVERSATION,
            auto_tag=False,
            metadata=ChunkMetadata(source=MemorySource.CLAUDE_HISTORY.value),
        )

        results = await memory_manager.search(
            "capital of France Paris",
            limit=10,
            semantic_threshold=0.1,
        )

        native_result = next((r for r in results if r.chunk.id == native.id), None)
        imported_result = next((r for r in results if r.chunk.id == imported.id), None)

        assert native_result is not None
        assert imported_result is not None
        assert native_result.relevance_score > imported_result.relevance_score

    @pytest.mark.asyncio
    async def test_store_exchange(self, memory_manager: MemoryManager):
        """Test storing a conversation exchange."""
        user_chunk, assistant_chunk = await memory_manager.store_exchange(
            user_message="How do I secure API keys?",
            assistant_response="Use the CredentialManager with the operational tier.",
            mode="Tia",
        )

        assert user_chunk.id is not None
        assert assistant_chunk.id is not None
        assert assistant_chunk.parent_id == user_chunk.id

    @pytest.mark.asyncio
    async def test_get_recent(self, memory_manager: MemoryManager):
        """Test getting recent chunks."""
        # Store several chunks
        for i in range(5):
            await memory_manager.store(
                content=f"Test message {i}",
                auto_tag=False,
            )

        recent = await memory_manager.get_recent(limit=3)

        assert len(recent) == 3
        # Should be in reverse chronological order
        assert "message 4" in recent[0].content

    @pytest.mark.asyncio
    async def test_get_by_tags(self, memory_manager: MemoryManager):
        """Test filtering by tags."""
        # Store with specific tags
        chunk = await memory_manager.store(
            content="Security implementation details",
            tags=ChunkTags(topics=["security", "implementation"]),
            auto_tag=False,
        )

        # Store without tags
        await memory_manager.store(
            content="General conversation",
            auto_tag=False,
        )

        # Filter by topic
        results = await memory_manager.get_by_tags(topics=["security"])

        assert len(results) >= 1
        assert any(r.id == chunk.id for r in results)

    @pytest.mark.asyncio
    async def test_session_management(self, memory_manager: MemoryManager):
        """Test session start and end."""
        session_id = await memory_manager.start_session(mode="Mira")

        assert session_id is not None
        assert session_id.startswith("session-")

        # Store in session
        chunk = await memory_manager.store(
            content="Session test content",
            auto_tag=False,
        )
        assert chunk.session_id == session_id

        await memory_manager.end_session("Test completed")

    @pytest.mark.asyncio
    async def test_stage_and_commit(self, memory_manager: MemoryManager):
        """Test staging and committing chunks."""
        chunk = await memory_manager.store(
            content="Important fact to remember",
            auto_tag=False,
        )

        # Stage for review
        await memory_manager.stage_for_review(chunk.id)

        # Get pending reviews
        pending = await memory_manager.get_pending_reviews()
        assert any(c.id == chunk.id for c in pending)

        # Commit
        await memory_manager.commit_to_long_term(chunk.id, "Verified")

    @pytest.mark.asyncio
    async def test_supersede_chunk(self, memory_manager: MemoryManager):
        """Test superseding an old chunk."""
        old_chunk = await memory_manager.store(
            content="The API uses v1 endpoints",
            auto_tag=False,
        )

        new_chunk = await memory_manager.supersede_chunk(
            old_chunk_id=old_chunk.id,
            new_content="The API uses v2 endpoints (updated)",
            reason="API version upgrade",
        )

        assert new_chunk.supersedes == old_chunk.id

        # Old chunk should be superseded
        old_retrieved = await memory_manager.database.get_chunk(old_chunk.id)
        assert old_retrieved.status == MemoryStatus.SUPERSEDED

    @pytest.mark.asyncio
    async def test_build_context(self, memory_manager: MemoryManager):
        """Test building context for inference."""
        # Store some content
        await memory_manager.store(
            content="The project uses ChromaDB for vector storage.",
            auto_tag=False,
        )
        await memory_manager.store(
            content="SQLite handles structured metadata.",
            auto_tag=False,
        )

        context = await memory_manager.build_context(
            query="How does Hestia store data?",
            max_tokens=1000,
        )

        assert len(context) > 0
        assert "ChromaDB" in context or "SQLite" in context

    @pytest.mark.asyncio
    async def test_get_action_items(self, memory_manager: MemoryManager):
        """Test getting action items."""
        # Store action item
        chunk = await memory_manager.store(
            content="TODO: implement the notification system",
            metadata=ChunkMetadata(has_action_item=True),
            auto_tag=False,
        )

        # Store non-action item
        await memory_manager.store(
            content="Regular conversation",
            auto_tag=False,
        )

        action_items = await memory_manager.get_action_items()

        assert len(action_items) >= 1
        assert any(a.id == chunk.id for a in action_items)

    @pytest.mark.asyncio
    async def test_get_decisions(self, memory_manager: MemoryManager):
        """Test getting decisions."""
        # Store decision
        chunk = await memory_manager.store(
            content="We decided to use async/await throughout",
            metadata=ChunkMetadata(has_decision=True),
            auto_tag=False,
        )

        decisions = await memory_manager.get_decisions()

        assert len(decisions) >= 1
        assert any(d.id == chunk.id for d in decisions)


# -----------------------------------------------------------------------
# MemorySource Tests (Sprint 11.5 — Task A1)
# -----------------------------------------------------------------------


class TestMemorySource:
    """Tests for MemorySource enum and source filtering."""

    def test_memory_source_enum_values(self):
        """All expected source values exist."""
        assert MemorySource.CONVERSATION.value == "conversation"
        assert MemorySource.MAIL.value == "mail"
        assert MemorySource.CALENDAR.value == "calendar"
        assert MemorySource.REMINDERS.value == "reminders"
        assert MemorySource.NOTES.value == "notes"
        assert MemorySource.HEALTH.value == "health"

    def test_memory_source_is_str_enum(self):
        """MemorySource is a string enum for JSON serialization."""
        assert isinstance(MemorySource.CONVERSATION, str)
        assert MemorySource.MAIL == "mail"

    def test_invalid_source_raises(self):
        """Invalid source value raises ValueError."""
        with pytest.raises(ValueError):
            MemorySource("invalid_source")

    def test_chunk_metadata_source_serialization(self):
        """Source field round-trips through to_dict/from_dict."""
        meta = ChunkMetadata(source=MemorySource.MAIL.value)
        d = meta.to_dict()
        assert d["source"] == "mail"

        restored = ChunkMetadata.from_dict(d)
        assert restored.source == "mail"

    def test_chunk_metadata_source_default_none(self):
        """Source defaults to None when not specified."""
        meta = ChunkMetadata()
        assert meta.source is None

    @pytest.mark.asyncio
    async def test_store_with_source(self, memory_manager: MemoryManager):
        """Store chunk with explicit source persists correctly."""
        chunk = await memory_manager.store(
            content="Email from John about meeting",
            chunk_type=ChunkType.FACT,
            metadata=ChunkMetadata(source=MemorySource.MAIL.value),
        )
        assert chunk.metadata.source == MemorySource.MAIL.value

    @pytest.mark.asyncio
    async def test_store_default_source_conversation(self, memory_manager: MemoryManager):
        """Store without explicit source defaults to 'conversation'."""
        chunk = await memory_manager.store(
            content="What is the weather today?",
        )
        assert chunk.metadata.source == MemorySource.CONVERSATION.value

    @pytest.mark.asyncio
    async def test_query_filter_by_source(self, memory_manager: MemoryManager):
        """Query with source filter returns only matching chunks."""
        # Store chunks with different sources
        await memory_manager.store(
            content="Calendar event: team standup",
            chunk_type=ChunkType.FACT,
            metadata=ChunkMetadata(source=MemorySource.CALENDAR.value),
        )
        await memory_manager.store(
            content="Email: project update",
            chunk_type=ChunkType.FACT,
            metadata=ChunkMetadata(source=MemorySource.MAIL.value),
        )
        await memory_manager.store(
            content="Regular conversation",
            metadata=ChunkMetadata(source=MemorySource.CONVERSATION.value),
        )

        # Query for mail only
        query = MemoryQuery(source=MemorySource.MAIL)
        results = await memory_manager.database.query_chunks(query)
        assert len(results) >= 1
        assert all(r.metadata.source == "mail" for r in results)

    @pytest.mark.asyncio
    async def test_query_no_source_filter_returns_all(self, memory_manager: MemoryManager):
        """Query without source filter returns all sources (backward compat)."""
        await memory_manager.store(
            content="Source test: mail item",
            metadata=ChunkMetadata(source=MemorySource.MAIL.value),
        )
        await memory_manager.store(
            content="Source test: conversation",
            metadata=ChunkMetadata(source=MemorySource.CONVERSATION.value),
        )

        query = MemoryQuery()  # No source filter
        results = await memory_manager.database.query_chunks(query)
        sources = {r.metadata.source for r in results}
        assert len(sources) >= 2  # Multiple source types returned


# -----------------------------------------------------------------------
# Source Dedup + Ingestion Tracking Tests (Sprint 11.5 — Task A2)
# -----------------------------------------------------------------------


class TestSourceDedup:
    """Tests for source deduplication and ingestion batch tracking."""

    @pytest.mark.asyncio
    async def test_check_duplicate_not_found(self, memory_manager: MemoryManager):
        """Non-ingested item returns False."""
        db = memory_manager.database
        assert await db.check_duplicate("mail", "msg-123") is False

    @pytest.mark.asyncio
    async def test_record_and_check_duplicate(self, memory_manager: MemoryManager):
        """Ingested item is detected as duplicate."""
        db = memory_manager.database
        await db.record_dedup("mail", "msg-123", "chunk-abc")
        assert await db.check_duplicate("mail", "msg-123") is True

    @pytest.mark.asyncio
    async def test_duplicate_different_source_ok(self, memory_manager: MemoryManager):
        """Same source_id from different source is not a duplicate."""
        db = memory_manager.database
        await db.record_dedup("mail", "item-1", "chunk-1")
        assert await db.check_duplicate("calendar", "item-1") is False

    @pytest.mark.asyncio
    async def test_record_dedup_idempotent(self, memory_manager: MemoryManager):
        """Recording same dedup entry twice doesn't raise."""
        db = memory_manager.database
        await db.record_dedup("mail", "msg-123", "chunk-abc")
        await db.record_dedup("mail", "msg-123", "chunk-abc")  # Should not raise

    @pytest.mark.asyncio
    async def test_ingestion_batch_lifecycle(self, memory_manager: MemoryManager):
        """Full batch lifecycle: start → complete."""
        db = memory_manager.database
        await db.start_ingestion_batch("batch-001", "mail")
        await db.complete_ingestion_batch("batch-001", 100, 80, 20)

        log = await db.get_ingestion_log("mail")
        assert len(log) == 1
        assert log[0]["batch_id"] == "batch-001"
        assert log[0]["status"] == "completed"
        assert log[0]["items_stored"] == 80
        assert log[0]["items_skipped"] == 20

    @pytest.mark.asyncio
    async def test_ingestion_batch_failure(self, memory_manager: MemoryManager):
        """Failed batch records status correctly."""
        db = memory_manager.database
        await db.start_ingestion_batch("batch-fail", "calendar")
        await db.fail_ingestion_batch("batch-fail", 50)

        log = await db.get_ingestion_log("calendar")
        assert log[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_rollback_batch(self, memory_manager: MemoryManager):
        """Rollback deletes all chunks from a batch."""
        db = memory_manager.database
        batch_id = "batch-rollback"

        # Store chunks via the normal path, then record dedup
        chunk1 = await memory_manager.store(
            content="Email 1 content",
            metadata=ChunkMetadata(source=MemorySource.MAIL.value),
        )
        chunk2 = await memory_manager.store(
            content="Email 2 content",
            metadata=ChunkMetadata(source=MemorySource.MAIL.value),
        )

        await db.record_dedup("mail", "email-1", chunk1.id, batch_id)
        await db.record_dedup("mail", "email-2", chunk2.id, batch_id)
        await db.start_ingestion_batch(batch_id, "mail")

        # Rollback
        deleted = await db.rollback_batch(batch_id)
        assert deleted == 2

        # Chunks should be gone
        assert await db.get_chunk(chunk1.id) is None
        assert await db.get_chunk(chunk2.id) is None

        # Dedup entries should be gone (can re-ingest)
        assert await db.check_duplicate("mail", "email-1") is False

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_batch(self, memory_manager: MemoryManager):
        """Rollback of unknown batch returns 0."""
        db = memory_manager.database
        deleted = await db.rollback_batch("nonexistent")
        assert deleted == 0
