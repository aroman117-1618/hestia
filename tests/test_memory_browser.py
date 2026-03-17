"""Tests for the Memory Browser endpoint and database method."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from hestia.memory.models import (
    ConversationChunk,
    ChunkType,
    MemoryScope,
    MemoryStatus,
    ChunkTags,
    ChunkMetadata,
)


def _make_chunk(
    chunk_id: str = "chunk-test1",
    content: str = "Test memory content",
    chunk_type: ChunkType = ChunkType.FACT,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    confidence: float = 0.85,
    source: str = "conversation",
) -> ConversationChunk:
    """Create a test chunk."""
    return ConversationChunk(
        id=chunk_id,
        session_id="session-test",
        timestamp=datetime.now(timezone.utc),
        content=content,
        chunk_type=chunk_type,
        scope=MemoryScope.LONG_TERM,
        status=status,
        tags=ChunkTags(topics=["python", "hestia"], entities=["andrew"]),
        metadata=ChunkMetadata(confidence=confidence, source=source),
    )


class TestListMemoryChunksEndpoint:
    """Tests for GET /v1/memory/chunks."""

    @pytest.fixture
    def mock_memory_manager(self):
        manager = AsyncMock()
        manager.database = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_list_chunks_default_sort(self, mock_memory_manager):
        """Default sort by importance descending."""
        chunks = [_make_chunk("c1", confidence=0.9), _make_chunk("c2", confidence=0.5)]
        mock_memory_manager.database.list_chunks = AsyncMock(return_value=(chunks, 2))

        with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory_manager):
            from hestia.api.routes.memory import list_memory_chunks
            result = await list_memory_chunks(
                limit=50, offset=0, sort_by="importance", sort_order="desc",
                chunk_type=None, chunk_status=None, source=None, device_id="test-device",
            )

        assert result["total"] == 2
        assert len(result["chunks"]) == 2
        assert result["chunks"][0]["id"] == "c1"
        assert result["chunks"][0]["importance"] == 0.9

    @pytest.mark.asyncio
    async def test_list_chunks_with_type_filter(self, mock_memory_manager):
        """Filter by chunk type."""
        chunks = [_make_chunk("c1", chunk_type=ChunkType.PREFERENCE)]
        mock_memory_manager.database.list_chunks = AsyncMock(return_value=(chunks, 1))

        with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory_manager):
            from hestia.api.routes.memory import list_memory_chunks
            result = await list_memory_chunks(
                limit=50, offset=0, sort_by="importance", sort_order="desc",
                chunk_type="preference", chunk_status=None, source=None, device_id="test-device",
            )

        mock_memory_manager.database.list_chunks.assert_called_once_with(
            limit=50, offset=0, sort_by="importance", sort_order="desc",
            chunk_type="preference", status=None, source=None,
        )
        assert result["total"] == 1

    @pytest.mark.asyncio
    async def test_list_chunks_pagination(self, mock_memory_manager):
        """Pagination with offset."""
        chunks = [_make_chunk("c3")]
        mock_memory_manager.database.list_chunks = AsyncMock(return_value=(chunks, 100))

        with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory_manager):
            from hestia.api.routes.memory import list_memory_chunks
            result = await list_memory_chunks(
                limit=50, offset=50, sort_by="created", sort_order="desc",
                chunk_type=None, chunk_status=None, source=None, device_id="test-device",
            )

        assert result["total"] == 100
        assert result["offset"] == 50
        assert result["limit"] == 50

    @pytest.mark.asyncio
    async def test_list_chunks_empty(self, mock_memory_manager):
        """Empty result set."""
        mock_memory_manager.database.list_chunks = AsyncMock(return_value=([], 0))

        with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory_manager):
            from hestia.api.routes.memory import list_memory_chunks
            result = await list_memory_chunks(
                limit=50, offset=0, sort_by="importance", sort_order="desc",
                chunk_type=None, chunk_status=None, source=None, device_id="test-device",
            )

        assert result["total"] == 0
        assert result["chunks"] == []

    @pytest.mark.asyncio
    async def test_list_chunks_content_truncated(self, mock_memory_manager):
        """Content is truncated to 200 chars."""
        long_content = "x" * 500
        chunks = [_make_chunk("c1", content=long_content)]
        mock_memory_manager.database.list_chunks = AsyncMock(return_value=(chunks, 1))

        with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory_manager):
            from hestia.api.routes.memory import list_memory_chunks
            result = await list_memory_chunks(
                limit=50, offset=0, sort_by="importance", sort_order="desc",
                chunk_type=None, chunk_status=None, source=None, device_id="test-device",
            )

        assert len(result["chunks"][0]["content"]) == 200

    @pytest.mark.asyncio
    async def test_list_chunks_status_filter(self, mock_memory_manager):
        """Filter by status."""
        chunks = [_make_chunk("c1", status=MemoryStatus.ARCHIVED)]
        mock_memory_manager.database.list_chunks = AsyncMock(return_value=(chunks, 1))

        with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory_manager):
            from hestia.api.routes.memory import list_memory_chunks
            result = await list_memory_chunks(
                limit=50, offset=0, sort_by="importance", sort_order="desc",
                chunk_type=None, chunk_status="archived", source=None, device_id="test-device",
            )

        mock_memory_manager.database.list_chunks.assert_called_once_with(
            limit=50, offset=0, sort_by="importance", sort_order="desc",
            chunk_type=None, status="archived", source=None,
        )


@pytest.mark.asyncio
async def test_update_chunk_content_success():
    """PUT /v1/memory/chunks/{id} returns updated chunk on success."""
    from hestia.api.routes.memory import update_memory_chunk
    from hestia.api.schemas.memory import MemoryChunkUpdateRequest
    from hestia.memory.models import ConversationChunk, ChunkType
    from unittest.mock import AsyncMock, patch, MagicMock

    fake_chunk = MagicMock(spec=ConversationChunk)
    fake_chunk.id = "chunk-123"
    fake_chunk.content = "Updated content."
    fake_chunk.chunk_type = ChunkType.FACT
    fake_chunk.tags = None

    mock_memory = AsyncMock()
    mock_memory.update_chunk_content.return_value = fake_chunk

    with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory):
        result = await update_memory_chunk(
            chunk_id="chunk-123",
            request=MemoryChunkUpdateRequest(content="Updated content."),
            device_id="test-device",
        )

    assert result.chunk_id == "chunk-123"
    assert result.content == "Updated content."
    mock_memory.update_chunk_content.assert_awaited_once_with(
        chunk_id="chunk-123", content="Updated content.", chunk_type=None, tags=None
    )


@pytest.mark.asyncio
async def test_update_chunk_not_found():
    """PUT returns 404 HTTPException when manager returns None."""
    from hestia.api.routes.memory import update_memory_chunk
    from hestia.api.schemas.memory import MemoryChunkUpdateRequest
    from fastapi import HTTPException
    from unittest.mock import AsyncMock, patch

    mock_memory = AsyncMock()
    mock_memory.update_chunk_content.return_value = None

    with patch("hestia.api.routes.memory.get_memory_manager", return_value=mock_memory):
        with pytest.raises(HTTPException) as exc_info:
            await update_memory_chunk(
                chunk_id="missing-id",
                request=MemoryChunkUpdateRequest(content="anything"),
                device_id="test-device",
            )
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_update_chunk_empty_body_rejected():
    """MemoryChunkUpdateRequest raises ValidationError when no fields provided."""
    from hestia.api.schemas.memory import MemoryChunkUpdateRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MemoryChunkUpdateRequest()  # no content, chunk_type, or tags


class TestMemoryDatabaseListChunks:
    """Tests for MemoryDatabase.list_chunks() method."""

    @pytest.mark.asyncio
    async def test_list_chunks_builds_query(self):
        """Verify list_chunks constructs correct SQL."""
        from hestia.memory.database import MemoryDatabase

        db = MemoryDatabase.__new__(MemoryDatabase)

        # Mock the connection
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(5,))
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)
        db._connection = mock_conn

        chunks, total = await db.list_chunks(limit=10, offset=0, sort_by="importance")
        assert total == 5
        assert chunks == []
        assert mock_conn.execute.call_count == 2
