"""Tests for the conversation history import pipeline."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from hestia.memory.importers.pipeline import ImportPipeline, ImportResult
from hestia.memory.models import ChunkType, MemoryScope, MemorySource


SAMPLE_CONVERSATIONS = [
    {
        "uuid": "conv-001",
        "name": "Test conversation",
        "summary": "",
        "created_at": "2026-01-15T10:30:00Z",
        "chat_messages": [
            {
                "uuid": "msg-001",
                "text": "Hello, what is the meaning of life?",
                "sender": "human",
                "created_at": "2026-01-15T10:30:05Z",
                "content": [{"type": "text", "text": "Hello, what is the meaning of life?"}],
                "files": [],
                "attachments": [],
            },
            {
                "uuid": "msg-002",
                "text": "The meaning of life is a deeply personal question.",
                "sender": "assistant",
                "created_at": "2026-01-15T10:30:45Z",
                "content": [{"type": "text", "text": "The meaning of life is a deeply personal question."}],
                "files": [],
                "attachments": [],
            },
        ],
    },
]


def _make_mock_manager():
    """Create a mock memory manager that returns stored chunks."""
    manager = AsyncMock()

    async def mock_store(**kwargs):
        from hestia.memory.models import ConversationChunk
        return ConversationChunk.create(
            content=kwargs.get("content", ""),
            session_id=kwargs.get("session_id", "test"),
            chunk_type=kwargs.get("chunk_type", ChunkType.CONVERSATION),
        )

    manager.store = mock_store
    return manager


def _make_mock_database():
    """Create a mock memory database with dedup support."""
    db = AsyncMock()
    seen: set = set()

    async def mock_check_dup(source: str, source_id: str) -> bool:
        return f"{source}:{source_id}" in seen

    async def mock_record_dup(source: str, source_id: str, chunk_id: str, batch_id=None):
        seen.add(f"{source}:{source_id}")

    db.check_duplicate = mock_check_dup
    db.record_dedup = mock_record_dup
    db._seen = seen
    return db


class TestImportPipeline:
    def test_import_stores_chunks(self, tmp_path):
        """Import stores parsed chunks through memory manager."""
        conv_path = tmp_path / "conversations.json"
        conv_path.write_text(json.dumps(SAMPLE_CONVERSATIONS))

        manager = _make_mock_manager()
        database = _make_mock_database()
        pipeline = ImportPipeline(manager, database)

        result = asyncio.get_event_loop().run_until_complete(
            pipeline.import_claude_history(str(conv_path))
        )

        assert result.conversations_processed == 1
        assert result.chunks_stored > 0
        assert result.chunks_failed == 0

    def test_import_deduplicates(self, tmp_path):
        """Importing the same data twice skips already-imported chunks."""
        conv_path = tmp_path / "conversations.json"
        conv_path.write_text(json.dumps(SAMPLE_CONVERSATIONS))

        manager = _make_mock_manager()
        database = _make_mock_database()
        pipeline = ImportPipeline(manager, database)

        # First import
        r1 = asyncio.get_event_loop().run_until_complete(
            pipeline.import_claude_history(str(conv_path))
        )
        first_stored = r1.chunks_stored

        # Second import — should skip all
        r2 = asyncio.get_event_loop().run_until_complete(
            pipeline.import_claude_history(str(conv_path))
        )
        assert r2.chunks_stored == 0
        assert r2.chunks_skipped == first_stored

    def test_import_handles_missing_file(self):
        """Missing file returns error in result."""
        manager = _make_mock_manager()
        database = _make_mock_database()
        pipeline = ImportPipeline(manager, database)

        result = asyncio.get_event_loop().run_until_complete(
            pipeline.import_claude_history("/nonexistent/path.json")
        )
        assert len(result.errors) > 0
        assert result.chunks_stored == 0

    def test_import_with_memories(self, tmp_path):
        """Import includes memories.json content."""
        conv_path = tmp_path / "conversations.json"
        conv_path.write_text(json.dumps([]))

        mem_path = tmp_path / "memories.json"
        mem_path.write_text(json.dumps([{
            "conversations_memory": "Andrew is a software engineer who values learning-while-building and uses Claude Code extensively.",
            "project_memories": {},
            "account_uuid": "user-001",
        }]))

        manager = _make_mock_manager()
        database = _make_mock_database()
        pipeline = ImportPipeline(manager, database)

        result = asyncio.get_event_loop().run_until_complete(
            pipeline.import_claude_history(str(conv_path), memories_path=str(mem_path))
        )
        assert result.chunks_stored == 1  # Memory summary chunk

    def test_import_result_serializable(self, tmp_path):
        """ImportResult.to_dict() returns JSON-serializable data."""
        conv_path = tmp_path / "conversations.json"
        conv_path.write_text(json.dumps(SAMPLE_CONVERSATIONS))

        manager = _make_mock_manager()
        database = _make_mock_database()
        pipeline = ImportPipeline(manager, database)

        result = asyncio.get_event_loop().run_until_complete(
            pipeline.import_claude_history(str(conv_path))
        )
        d = result.to_dict()
        json.dumps(d)  # Should not raise
        assert "batch_id" in d
        assert "chunks_stored" in d

    def test_import_batch_id_format(self, tmp_path):
        """Batch ID follows expected format."""
        conv_path = tmp_path / "conversations.json"
        conv_path.write_text(json.dumps([]))

        manager = _make_mock_manager()
        database = _make_mock_database()
        pipeline = ImportPipeline(manager, database)

        result = asyncio.get_event_loop().run_until_complete(
            pipeline.import_claude_history(str(conv_path))
        )
        assert result.batch_id.startswith("claude-import-")
