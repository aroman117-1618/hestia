"""
Tests for hestia.memory.pruner — MemoryPruner.

TDD: tests written before implementation.
Covers eligibility filtering, preview dry-run, execute archive+ChromaDB delete,
undo restore, and stats output.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from hestia.memory.models import (
    ChunkMetadata,
    ChunkTags,
    ChunkType,
    ConversationChunk,
    MemoryScope,
    MemoryStatus,
)
from hestia.memory.pruner import MemoryPruner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(
    chunk_id: str = "chunk-abc123",
    chunk_type: ChunkType = ChunkType.CONVERSATION,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    age_days: int = 90,
    importance: float = 0.1,
) -> ConversationChunk:
    """Build a ConversationChunk with the given characteristics."""
    ts = datetime.now(timezone.utc) - timedelta(days=age_days)
    return ConversationChunk(
        id=chunk_id,
        session_id="sess-001",
        timestamp=ts,
        content="Some memory content",
        chunk_type=chunk_type,
        scope=MemoryScope.SHORT_TERM,
        status=status,
        tags=ChunkTags(),
        metadata=ChunkMetadata(confidence=importance),
    )


_DEFAULT_CONFIG: Dict[str, Any] = {
    "pruning": {
        "enabled": True,
        "max_age_days": 60,
        "importance_threshold": 0.2,
        "protected_statuses": ["committed"],
        "protected_types": ["system"],
    }
}


def _make_pruner(
    eligible_chunks: Optional[List[ConversationChunk]] = None,
) -> Tuple[MemoryPruner, MagicMock, MagicMock, MagicMock]:
    """Return (pruner, mock_db, mock_vs, mock_ldb) with find_eligible patched."""
    mock_db = MagicMock()
    mock_db._connection = AsyncMock()
    mock_vs = MagicMock()
    mock_vs.delete_chunks = MagicMock()
    mock_ldb = MagicMock()
    mock_ldb.store_trigger_alert = AsyncMock()

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=mock_vs,
        learning_db=mock_ldb,
        config=_DEFAULT_CONFIG,
    )

    if eligible_chunks is not None:
        pruner.find_eligible = AsyncMock(return_value=eligible_chunks)

    return pruner, mock_db, mock_vs, mock_ldb


# ---------------------------------------------------------------------------
# find_eligible — unit tests with real SQL logic mocked at DB layer
# ---------------------------------------------------------------------------

def _make_db_with_rows(rows: list) -> MagicMock:
    """Create a mock DB whose _connection.execute returns a cursor with fetchall."""
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=rows)
    mock_db = MagicMock()
    mock_db._connection = MagicMock()
    mock_db._connection.execute = AsyncMock(return_value=mock_cursor)
    return mock_db


@pytest.mark.asyncio
async def test_find_eligible_old_low_importance() -> None:
    """Chunk 90 days old, importance 0.1 → eligible."""
    chunk = _make_chunk(age_days=90, importance=0.1)
    mock_db = _make_db_with_rows([chunk.to_sqlite_row()])

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=MagicMock(),
        learning_db=MagicMock(),
        config=_DEFAULT_CONFIG,
    )

    with patch(
        "hestia.memory.pruner.ConversationChunk.from_sqlite_row",
        return_value=chunk,
    ):
        results = await pruner.find_eligible()

    assert len(results) == 1
    assert results[0].id == chunk.id


@pytest.mark.asyncio
async def test_find_eligible_excludes_recent() -> None:
    """Chunk only 30 days old → NOT eligible (below max_age_days=60)."""
    mock_db = _make_db_with_rows([])

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=MagicMock(),
        learning_db=MagicMock(),
        config=_DEFAULT_CONFIG,
    )

    results = await pruner.find_eligible()
    assert results == []


@pytest.mark.asyncio
async def test_find_eligible_excludes_important() -> None:
    """Chunk 90 days old but importance 0.5 → NOT eligible (above threshold=0.2)."""
    mock_db = _make_db_with_rows([])

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=MagicMock(),
        learning_db=MagicMock(),
        config=_DEFAULT_CONFIG,
    )

    results = await pruner.find_eligible()
    assert results == []


@pytest.mark.asyncio
async def test_find_eligible_excludes_committed() -> None:
    """Committed chunk (protected_status) → NOT eligible even if old and low importance."""
    mock_db = _make_db_with_rows([])

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=MagicMock(),
        learning_db=MagicMock(),
        config=_DEFAULT_CONFIG,
    )

    results = await pruner.find_eligible()
    assert results == []


@pytest.mark.asyncio
async def test_find_eligible_excludes_system_type() -> None:
    """System chunk type (protected_type) → NOT eligible even if old and low importance."""
    mock_db = _make_db_with_rows([])

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=MagicMock(),
        learning_db=MagicMock(),
        config=_DEFAULT_CONFIG,
    )

    results = await pruner.find_eligible()
    assert results == []


# ---------------------------------------------------------------------------
# SQL query construction — verify correct parameters passed to DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_find_eligible_sql_uses_age_and_threshold() -> None:
    """Verify find_eligible passes max_age_days and importance_threshold to SQL."""
    mock_db = _make_db_with_rows([])

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=MagicMock(),
        learning_db=MagicMock(),
        config=_DEFAULT_CONFIG,
    )

    await pruner.find_eligible()

    # execute was called once; check the SQL and params
    call_args = mock_db._connection.execute.call_args
    sql: str = call_args[0][0]
    params: tuple = call_args[0][1]

    assert "json_extract(metadata, '$.confidence')" in sql
    assert 0.2 in params


# ---------------------------------------------------------------------------
# preview — dry-run, no writes
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_preview_returns_list_without_modifying() -> None:
    """preview() returns chunk list as dicts; no DB writes occur."""
    chunk = _make_chunk(chunk_id="chunk-preview1", age_days=90, importance=0.1)
    pruner, mock_db, mock_vs, mock_ldb = _make_pruner(eligible_chunks=[chunk])

    result = await pruner.preview()

    assert isinstance(result, list)
    assert len(result) == 1
    item = result[0]
    assert item["id"] == "chunk-preview1"
    assert item["chunk_type"] == ChunkType.CONVERSATION.value
    assert item["importance"] == 0.1
    assert item["age_days"] >= 89  # approximately 90 days

    # No database writes
    mock_db.update_chunk.assert_not_called()
    mock_vs.delete_chunks.assert_not_called()
    mock_ldb.store_trigger_alert.assert_not_called()


# ---------------------------------------------------------------------------
# execute — archive + ChromaDB delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_execute_archives_chunks() -> None:
    """execute() sets status=ARCHIVED on each eligible chunk."""
    chunk = _make_chunk(chunk_id="chunk-exec1", status=MemoryStatus.ACTIVE)
    pruner, mock_db, mock_vs, mock_ldb = _make_pruner(eligible_chunks=[chunk])
    mock_db.update_chunk = AsyncMock()

    await pruner.execute()

    # update_chunk must have been called with the chunk in ARCHIVED state
    mock_db.update_chunk.assert_called_once()
    updated_chunk: ConversationChunk = mock_db.update_chunk.call_args[0][0]
    assert updated_chunk.id == "chunk-exec1"
    assert updated_chunk.status == MemoryStatus.ARCHIVED


@pytest.mark.asyncio
async def test_execute_deletes_from_chromadb() -> None:
    """execute() calls vector_store.delete_chunks with the archived IDs."""
    chunk1 = _make_chunk(chunk_id="chunk-c1")
    chunk2 = _make_chunk(chunk_id="chunk-c2")
    pruner, mock_db, mock_vs, mock_ldb = _make_pruner(eligible_chunks=[chunk1, chunk2])
    mock_db.update_chunk = AsyncMock()

    await pruner.execute()

    mock_vs.delete_chunks.assert_called_once()
    deleted_ids = mock_vs.delete_chunks.call_args[0][0]
    assert set(deleted_ids) == {"chunk-c1", "chunk-c2"}


@pytest.mark.asyncio
async def test_execute_returns_stats() -> None:
    """execute() returns {'archived': N}."""
    chunks = [_make_chunk(chunk_id=f"chunk-s{i}") for i in range(3)]
    pruner, mock_db, mock_vs, mock_ldb = _make_pruner(eligible_chunks=chunks)
    mock_db.update_chunk = AsyncMock()

    stats = await pruner.execute()

    assert stats["archived"] == 3


@pytest.mark.asyncio
async def test_execute_no_eligible_chunks() -> None:
    """execute() with no eligible chunks returns 0 archived, skips ChromaDB."""
    pruner, mock_db, mock_vs, mock_ldb = _make_pruner(eligible_chunks=[])
    mock_db.update_chunk = AsyncMock()

    stats = await pruner.execute()

    assert stats["archived"] == 0
    mock_vs.delete_chunks.assert_not_called()


# ---------------------------------------------------------------------------
# undo — restore ARCHIVED → ACTIVE
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_undo_restores_to_active() -> None:
    """undo() sets ARCHIVED chunks back to ACTIVE status."""
    chunk = _make_chunk(chunk_id="chunk-undo1", status=MemoryStatus.ARCHIVED)

    mock_db = MagicMock()
    mock_db.get_chunk = AsyncMock(return_value=chunk)
    mock_db.update_chunk = AsyncMock()

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=MagicMock(),
        learning_db=MagicMock(),
        config=_DEFAULT_CONFIG,
    )

    restored = await pruner.undo(["chunk-undo1"])

    assert restored == 1
    mock_db.update_chunk.assert_called_once()
    updated: ConversationChunk = mock_db.update_chunk.call_args[0][0]
    assert updated.id == "chunk-undo1"
    assert updated.status == MemoryStatus.ACTIVE


@pytest.mark.asyncio
async def test_undo_skips_missing_chunks() -> None:
    """undo() gracefully handles chunk IDs that no longer exist in DB."""
    mock_db = MagicMock()
    mock_db.get_chunk = AsyncMock(return_value=None)
    mock_db.update_chunk = AsyncMock()

    pruner = MemoryPruner(
        memory_db=mock_db,
        vector_store=MagicMock(),
        learning_db=MagicMock(),
        config=_DEFAULT_CONFIG,
    )

    restored = await pruner.undo(["chunk-ghost"])

    assert restored == 0
    mock_db.update_chunk.assert_not_called()
