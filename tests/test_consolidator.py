"""
Tests for MemoryConsolidator — embedding-similarity dedup.

Covers: candidate detection, similarity threshold, type gating,
preview dry-run, execution with merge cap, strategy protocol,
dry_run flag, and supersedes linkage.
"""

import contextlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hestia.memory.consolidator import (
    ImportanceBasedMerge,
    MemoryConsolidator,
    MergeStrategy,
)
from hestia.memory.models import (
    ChunkMetadata,
    ChunkType,
    ConversationChunk,
    MemoryScope,
    MemoryStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: str,
    chunk_type: ChunkType = ChunkType.FACT,
    confidence: float = 0.8,
    status: MemoryStatus = MemoryStatus.ACTIVE,
) -> ConversationChunk:
    return ConversationChunk(
        id=chunk_id,
        session_id="sess-test",
        timestamp=datetime.now(timezone.utc),
        content=f"Content for {chunk_id}",
        chunk_type=chunk_type,
        scope=MemoryScope.LONG_TERM,
        status=status,
        metadata=ChunkMetadata(confidence=confidence),
    )


def _make_config(
    threshold: float = 0.90,
    sample_size: int = 50,
    max_merges: int = 100,
    require_same_type: bool = True,
) -> Dict[str, Any]:
    return {
        "consolidation": {
            "enabled": True,
            "similarity_threshold": threshold,
            "sample_size": sample_size,
            "max_merges_per_run": max_merges,
            "require_same_type": require_same_type,
        }
    }


def _make_db_mock(sample_rows: List[Tuple[str, ...]]) -> MagicMock:
    """Build a MemoryDatabase mock that yields sample_rows from _connection.execute."""

    @contextlib.asynccontextmanager
    async def _async_cm(*args, **kwargs):
        cursor = AsyncMock()
        cursor.fetchall = AsyncMock(return_value=sample_rows)
        yield cursor

    db = MagicMock()
    db._connection = MagicMock()
    db._connection.execute = _async_cm
    return db


def _make_vs_mock(
    fake_embedding: List[float],
    search_results: List[Tuple[str, float]],
) -> MagicMock:
    """Build a VectorStore mock."""
    mock_collection = MagicMock()
    mock_collection.get = MagicMock(return_value={"embeddings": [fake_embedding]})
    vs = MagicMock()
    vs.collection = mock_collection
    vs.search_by_embedding = MagicMock(return_value=search_results)
    return vs


def _make_consolidator(
    db: Any,
    vector_store: Any,
    config: Optional[Dict[str, Any]] = None,
    strategy: Any = None,
) -> MemoryConsolidator:
    return MemoryConsolidator(
        memory_db=db,
        vector_store=vector_store,
        config=config or _make_config(),
        strategy=strategy,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_candidates_detects_similar() -> None:
    """Two chunks at 0.95 similarity with same type produce a candidate pair."""
    chunk_a = _make_chunk("chunk-a", ChunkType.FACT)
    chunk_b = _make_chunk("chunk-b", ChunkType.FACT)

    db = _make_db_mock([("chunk-a",)])
    db.get_chunk = AsyncMock(side_effect=lambda cid: chunk_a if cid == "chunk-a" else chunk_b)

    vs = _make_vs_mock([0.1] * 384, [("chunk-b", 0.95)])

    consolidator = _make_consolidator(db, vs)
    candidates = await consolidator.find_candidates()

    assert len(candidates) == 1
    ids = {candidates[0][0], candidates[0][1]}
    assert ids == {"chunk-a", "chunk-b"}
    assert abs(candidates[0][2] - 0.95) < 1e-9


@pytest.mark.asyncio
async def test_find_candidates_skips_low_similarity() -> None:
    """Chunks at 0.85 similarity are below the 0.90 threshold — no candidates."""
    chunk_a = _make_chunk("chunk-a", ChunkType.FACT)
    chunk_b = _make_chunk("chunk-b", ChunkType.FACT)

    db = _make_db_mock([("chunk-a",)])
    db.get_chunk = AsyncMock(side_effect=lambda cid: chunk_a if cid == "chunk-a" else chunk_b)

    # 0.85 is below the 0.90 threshold — search_by_embedding filters internally
    # but consolidator also checks the returned score against threshold.
    # We return it from the mock so the threshold check in find_candidates fires.
    vs = _make_vs_mock([0.1] * 384, [("chunk-b", 0.85)])

    consolidator = _make_consolidator(db, vs)
    candidates = await consolidator.find_candidates()

    assert candidates == []


@pytest.mark.asyncio
async def test_find_candidates_skips_different_types() -> None:
    """Chunks at 0.95 similarity with different types are skipped when require_same_type=True."""
    chunk_a = _make_chunk("chunk-a", ChunkType.FACT)
    chunk_b = _make_chunk("chunk-b", ChunkType.PREFERENCE)  # different type

    db = _make_db_mock([("chunk-a",)])
    db.get_chunk = AsyncMock(side_effect=lambda cid: chunk_a if cid == "chunk-a" else chunk_b)

    vs = _make_vs_mock([0.1] * 384, [("chunk-b", 0.95)])

    consolidator = _make_consolidator(db, vs, config=_make_config(require_same_type=True))
    candidates = await consolidator.find_candidates()

    assert candidates == []


@pytest.mark.asyncio
async def test_preview_returns_without_modifying() -> None:
    """preview() returns candidate info and never calls db.update_chunk."""
    chunk_a = _make_chunk("chunk-a", ChunkType.FACT)
    chunk_b = _make_chunk("chunk-b", ChunkType.FACT)

    db = _make_db_mock([("chunk-a",)])
    db.get_chunk = AsyncMock(side_effect=lambda cid: chunk_a if cid == "chunk-a" else chunk_b)
    db.update_chunk = AsyncMock()

    vs = _make_vs_mock([0.1] * 384, [("chunk-b", 0.95)])

    consolidator = _make_consolidator(db, vs)
    result = await consolidator.preview()

    # Must return structured result
    assert "candidates" in result
    assert result["candidates"] == 1

    # Must NOT write to the database
    db.update_chunk.assert_not_called()


@pytest.mark.asyncio
async def test_execute_marks_lower_importance_superseded() -> None:
    """execute() marks the low-confidence chunk (0.3) SUPERSEDED, keeps high (0.8)."""
    chunk_low = _make_chunk("chunk-low", ChunkType.FACT, confidence=0.3)
    chunk_high = _make_chunk("chunk-high", ChunkType.FACT, confidence=0.8)

    db = _make_db_mock([("chunk-low",)])
    db.get_chunk = AsyncMock(
        side_effect=lambda cid: chunk_low if cid == "chunk-low" else chunk_high
    )
    db.update_chunk = AsyncMock()

    vs = _make_vs_mock([0.1] * 384, [("chunk-high", 0.95)])

    consolidator = _make_consolidator(db, vs)
    result = await consolidator.execute(dry_run=False)

    assert result["merged"] == 1
    db.update_chunk.assert_called_once()

    updated_chunk = db.update_chunk.call_args[0][0]
    assert updated_chunk.id == "chunk-low"
    assert updated_chunk.status == MemoryStatus.SUPERSEDED


@pytest.mark.asyncio
async def test_execute_respects_merge_cap() -> None:
    """With 200 candidate pairs, only max_merges_per_run (100) are processed."""
    # Build 400 chunks — even-indexed are "a", odd-indexed are "b" partners
    chunks: Dict[str, ConversationChunk] = {}
    for i in range(400):
        cid = f"chunk-{i}"
        chunks[cid] = _make_chunk(cid, ChunkType.FACT, confidence=float(i % 10) / 10)

    # Sample 200 "a" chunks (even indices)
    sample_rows = [(f"chunk-{i}",) for i in range(0, 400, 2)]

    db = _make_db_mock(sample_rows)
    db.get_chunk = AsyncMock(side_effect=lambda cid: chunks.get(cid))
    db.update_chunk = AsyncMock()

    call_count = [0]

    def _search(embedding: List[float], n_results: int, min_score: float) -> List[Tuple[str, float]]:
        i = call_count[0]
        call_count[0] += 1
        partner_id = f"chunk-{i * 2 + 1}"
        if partner_id in chunks:
            return [(partner_id, 0.95)]
        return []

    mock_collection = MagicMock()
    mock_collection.get = MagicMock(return_value={"embeddings": [[0.1] * 384]})
    vs = MagicMock()
    vs.collection = mock_collection
    vs.search_by_embedding = MagicMock(side_effect=_search)

    consolidator = _make_consolidator(db, vs, config=_make_config(max_merges=100))
    result = await consolidator.execute(dry_run=False)

    assert result["merged"] <= 100


@pytest.mark.asyncio
async def test_merge_strategy_protocol() -> None:
    """ImportanceBasedMerge satisfies MergeStrategy: picks higher-confidence chunk."""
    strategy = ImportanceBasedMerge()

    chunk_low = _make_chunk("low", confidence=0.3)
    chunk_high = _make_chunk("high", confidence=0.9)

    assert strategy.select_survivor(chunk_low, chunk_high) == "high"
    assert strategy.select_survivor(chunk_high, chunk_low) == "high"

    # Equal confidence — chunk_a wins (stable determinism: >= favours a)
    chunk_equal_a = _make_chunk("eq-a", confidence=0.5)
    chunk_equal_b = _make_chunk("eq-b", confidence=0.5)
    assert strategy.select_survivor(chunk_equal_a, chunk_equal_b) == "eq-a"


@pytest.mark.asyncio
async def test_execute_dry_run() -> None:
    """execute(dry_run=True) returns stats but does not write to the database."""
    chunk_a = _make_chunk("chunk-a", ChunkType.FACT, confidence=0.3)
    chunk_b = _make_chunk("chunk-b", ChunkType.FACT, confidence=0.8)

    db = _make_db_mock([("chunk-a",)])
    db.get_chunk = AsyncMock(side_effect=lambda cid: chunk_a if cid == "chunk-a" else chunk_b)
    db.update_chunk = AsyncMock()

    vs = _make_vs_mock([0.1] * 384, [("chunk-b", 0.95)])

    consolidator = _make_consolidator(db, vs)
    result = await consolidator.execute(dry_run=True)

    assert result["mode"] == "dry_run"
    assert result["candidates"] == 1
    # No writes
    db.update_chunk.assert_not_called()


@pytest.mark.asyncio
async def test_superseded_chunk_points_to_survivor() -> None:
    """After merge, the loser chunk has supersedes == survivor.id."""
    chunk_low = _make_chunk("chunk-low", ChunkType.FACT, confidence=0.2)
    chunk_high = _make_chunk("chunk-high", ChunkType.FACT, confidence=0.9)

    db = _make_db_mock([("chunk-low",)])
    db.get_chunk = AsyncMock(
        side_effect=lambda cid: chunk_low if cid == "chunk-low" else chunk_high
    )
    db.update_chunk = AsyncMock()

    vs = _make_vs_mock([0.1] * 384, [("chunk-high", 0.95)])

    consolidator = _make_consolidator(db, vs)
    await consolidator.execute(dry_run=False)

    updated_chunk = db.update_chunk.call_args[0][0]
    assert updated_chunk.supersedes == "chunk-high"
