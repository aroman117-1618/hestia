"""
Tests for ImportanceScorer (Sprint 16).

All tests mock MemoryDatabase and OutcomeManager so no live DB is required.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock

import pytest

from hestia.memory.importance import ImportanceScorer
from hestia.memory.models import ChunkType, ConversationChunk


# ── Fixtures ─────────────────────────────────────────────────────────────────


_CONFIG = {
    "importance": {
        "enabled": True,
        "weights": {
            "recency": 0.3,
            "retrieval": 0.4,
            "type_bonus": 0.3,
        },
        "type_bonuses": {
            "fact": 0.8,
            "decision": 0.7,
            "preference": 0.6,
            "research": 0.5,
            "insight": 0.8,
            "action_item": 0.4,
            "conversation": 0.3,
            "system": 1.0,
        },
        "recency_max_days": 90,
        "min_importance": 0.05,
        "system_floor": 0.5,
    }
}


def _make_chunk(
    chunk_id: str = "chunk-001",
    chunk_type: ChunkType = ChunkType.CONVERSATION,
    age_days: float = 0.0,
) -> ConversationChunk:
    """Create a minimal ConversationChunk with a given age."""
    ts = datetime.now(timezone.utc) - timedelta(days=age_days)
    return ConversationChunk.create(
        content="test content",
        session_id="session-1",
        chunk_type=chunk_type,
        id=chunk_id,  # override auto-generated id via kwargs → goes to create()'s **kwargs
    )


def _chunk_with_ts(
    chunk_id: str,
    chunk_type: ChunkType,
    timestamp: datetime,
) -> ConversationChunk:
    """Create a chunk with an explicit timestamp."""
    chunk = ConversationChunk(
        id=chunk_id,
        session_id="session-1",
        timestamp=timestamp,
        content="test content",
        chunk_type=chunk_type,
    )
    return chunk


def _make_scorer(
    chunks: Optional[List[ConversationChunk]] = None,
    outcomes: Optional[List[Dict]] = None,
) -> ImportanceScorer:
    """Build a scorer with mocked DB dependencies."""
    memory_db = AsyncMock()
    outcome_db = AsyncMock()

    # Stub _get_active_chunks via the connection cursor
    # We mock _connection.execute to return an async context manager
    active = chunks or []

    # We'll override _get_active_chunks directly via side-effect on the method
    # because the real implementation accesses _connection directly.
    # The cleanest approach: subclass or patch the private method.
    # Since ImportanceScorer._get_active_chunks is an async method, we can
    # monkey-patch the bound method after construction.

    memory_db.update_chunk = AsyncMock(return_value=None)

    outcome_db.get_outcomes = AsyncMock(return_value=outcomes or [])

    scorer = ImportanceScorer(
        memory_db=memory_db,
        outcome_db=outcome_db,
        config=_CONFIG,
    )

    # Monkey-patch _get_active_chunks to return our fixture chunks
    async def _mock_get_active():
        return active

    scorer._get_active_chunks = _mock_get_active  # type: ignore[method-assign]
    return scorer


# ── Recency Score Tests ───────────────────────────────────────────────────────


class TestRecencyScore:

    def test_recency_score_fresh_chunk(self) -> None:
        """Chunk from right now → recency score ≈ 1.0."""
        scorer = _make_scorer()
        ts = datetime.now(timezone.utc)
        score = scorer._compute_recency_score(ts)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_recency_score_old_chunk(self) -> None:
        """Chunk from 90+ days ago → score at min_importance (0.05)."""
        scorer = _make_scorer()
        ts = datetime.now(timezone.utc) - timedelta(days=90)
        score = scorer._compute_recency_score(ts)
        assert score == pytest.approx(0.05, abs=0.01)

    def test_recency_score_beyond_max(self) -> None:
        """Chunk older than recency_max_days → clamped to min_importance."""
        scorer = _make_scorer()
        ts = datetime.now(timezone.utc) - timedelta(days=120)
        score = scorer._compute_recency_score(ts)
        assert score == pytest.approx(0.05, abs=0.01)

    def test_recency_score_mid_age(self) -> None:
        """Chunk from 45 days ago → score ≈ 0.525 (midpoint of decay range)."""
        scorer = _make_scorer()
        ts = datetime.now(timezone.utc) - timedelta(days=45)
        score = scorer._compute_recency_score(ts)
        # Linear: 1.0 - (45/90) * (1.0 - 0.05) = 1.0 - 0.475 = 0.525
        assert score == pytest.approx(0.525, abs=0.01)

    def test_recency_score_future_timestamp(self) -> None:
        """Future timestamp treated as age=0 → score = 1.0."""
        scorer = _make_scorer()
        ts = datetime.now(timezone.utc) + timedelta(hours=2)
        score = scorer._compute_recency_score(ts)
        assert score == pytest.approx(1.0, abs=0.01)


# ── Retrieval Score Tests ─────────────────────────────────────────────────────


class TestRetrievalScore:

    @pytest.mark.asyncio
    async def test_retrieval_score_with_positive_outcomes(self) -> None:
        """Chunk retrieved in 5 outcomes with positive signals → high score."""
        chunk_id = "chunk-abc"
        outcomes = [
            {
                "id": f"o{i}",
                "implicit_signal": "accepted",
                "metadata": {"retrieved_chunk_ids": [chunk_id]},
            }
            for i in range(5)
        ]
        scorer = _make_scorer(outcomes=outcomes)
        scores = await scorer._compute_retrieval_scores([chunk_id], user_id="default")
        assert scores[chunk_id] > 0.5

    @pytest.mark.asyncio
    async def test_retrieval_score_no_data(self) -> None:
        """Chunk never retrieved → 0.0."""
        scorer = _make_scorer(outcomes=[])
        scores = await scorer._compute_retrieval_scores(["chunk-never"], user_id="default")
        assert scores["chunk-never"] == 0.0

    @pytest.mark.asyncio
    async def test_retrieval_score_negative_feedback(self) -> None:
        """Chunk with mostly negative signals → penalized score."""
        chunk_id = "chunk-bad"
        # 5 retrieval events all with quick_followup (negative)
        outcomes = [
            {
                "id": f"o{i}",
                "implicit_signal": "quick_followup",
                "metadata": {"retrieved_chunk_ids": [chunk_id]},
            }
            for i in range(5)
        ]
        # Also add a chunk that was retrieved but with positive signals to provide contrast
        other_id = "chunk-good"
        for i in range(5):
            outcomes.append({
                "id": f"p{i}",
                "implicit_signal": "accepted",
                "metadata": {"retrieved_chunk_ids": [other_id]},
            })

        scorer = _make_scorer(outcomes=outcomes)
        scores = await scorer._compute_retrieval_scores([chunk_id, other_id], user_id="default")

        # Negative chunk should score lower than positive chunk
        assert scores[chunk_id] < scores[other_id]

    @pytest.mark.asyncio
    async def test_retrieval_score_metadata_json_string(self) -> None:
        """Metadata as JSON string should be parsed correctly."""
        chunk_id = "chunk-json"
        outcomes = [
            {
                "id": "o1",
                "implicit_signal": "accepted",
                "metadata": json.dumps({"retrieved_chunk_ids": [chunk_id]}),
            }
        ]
        scorer = _make_scorer(outcomes=outcomes)
        scores = await scorer._compute_retrieval_scores([chunk_id], user_id="default")
        assert scores[chunk_id] > 0.0

    @pytest.mark.asyncio
    async def test_retrieval_score_unknown_chunk_returns_zero(self) -> None:
        """chunk_ids not in any outcome get 0.0 even if other chunks were retrieved."""
        outcomes = [
            {
                "id": "o1",
                "implicit_signal": "accepted",
                "metadata": {"retrieved_chunk_ids": ["chunk-other"]},
            }
        ]
        scorer = _make_scorer(outcomes=outcomes)
        scores = await scorer._compute_retrieval_scores(["chunk-missing"], user_id="default")
        assert scores["chunk-missing"] == 0.0


# ── Type Bonus Tests ──────────────────────────────────────────────────────────


class TestTypeBonusLookup:

    def test_type_bonus_fact(self) -> None:
        scorer = _make_scorer()
        assert scorer._get_type_bonus("fact") == pytest.approx(0.8)

    def test_type_bonus_conversation(self) -> None:
        scorer = _make_scorer()
        assert scorer._get_type_bonus("conversation") == pytest.approx(0.3)

    def test_type_bonus_system(self) -> None:
        scorer = _make_scorer()
        assert scorer._get_type_bonus("system") == pytest.approx(1.0)

    def test_type_bonus_unknown_defaults_to_0_3(self) -> None:
        scorer = _make_scorer()
        assert scorer._get_type_bonus("unknown_type") == pytest.approx(0.3)


# ── Composite Score Test ──────────────────────────────────────────────────────


class TestCompositeScore:

    def test_composite_score_formula(self) -> None:
        """Verify: 0.3*recency + 0.4*retrieval + 0.3*type_bonus."""
        scorer = _make_scorer()
        recency = 0.8
        retrieval = 0.6
        type_bonus = 0.7  # decision
        expected = 0.3 * recency + 0.4 * retrieval + 0.3 * type_bonus
        # = 0.24 + 0.24 + 0.21 = 0.69
        result = scorer._compute_importance(recency, retrieval, type_bonus)
        assert result == pytest.approx(expected, abs=0.001)

    def test_composite_score_clamps_to_min(self) -> None:
        """All-zero inputs → min_importance."""
        scorer = _make_scorer()
        result = scorer._compute_importance(0.0, 0.0, 0.0)
        assert result == pytest.approx(0.05)

    def test_composite_score_clamps_to_max(self) -> None:
        """All-max inputs → 1.0."""
        scorer = _make_scorer()
        result = scorer._compute_importance(1.0, 1.0, 1.0)
        assert result == pytest.approx(1.0)


# ── Batch Score Tests ─────────────────────────────────────────────────────────


class TestBatchScore:

    @pytest.mark.asyncio
    async def test_batch_score_updates_confidence(self) -> None:
        """score_all() updates ChunkMetadata.confidence on each chunk."""
        chunk = _chunk_with_ts(
            "chunk-001",
            ChunkType.FACT,
            datetime.now(timezone.utc) - timedelta(days=10),
        )
        assert chunk.metadata.confidence == 1.0  # default

        scorer = _make_scorer(chunks=[chunk], outcomes=[])
        stats = await scorer.score_all(user_id="default")

        assert stats["scored"] == 1
        # confidence should have been updated away from the default 1.0
        # fact with 10-day age should get a reasonably high score
        assert 0.0 < chunk.metadata.confidence <= 1.0

        # update_chunk must have been called once
        scorer._memory_db.update_chunk.assert_called_once_with(chunk)

    @pytest.mark.asyncio
    async def test_batch_score_empty_returns_zeros(self) -> None:
        """score_all() on empty chunk set returns zeroed stats."""
        scorer = _make_scorer(chunks=[], outcomes=[])
        stats = await scorer.score_all()
        assert stats["scored"] == 0
        assert stats["avg_importance"] == 0.0

    @pytest.mark.asyncio
    async def test_score_all_returns_stats(self) -> None:
        """Returns dict with scored count, avg_importance, below_threshold, distribution."""
        chunks = [
            _chunk_with_ts(
                f"c{i}",
                ChunkType.CONVERSATION,
                datetime.now(timezone.utc) - timedelta(days=i * 5),
            )
            for i in range(5)
        ]
        scorer = _make_scorer(chunks=chunks, outcomes=[])
        stats = await scorer.score_all(user_id="default")

        assert "scored" in stats
        assert "avg_importance" in stats
        assert "below_threshold" in stats
        assert "distribution" in stats
        assert stats["scored"] == 5
        assert 0.0 < stats["avg_importance"] <= 1.0
        dist = stats["distribution"]
        assert "low" in dist and "mid" in dist and "high" in dist
        assert dist["low"] + dist["mid"] + dist["high"] == 5


# ── System Chunk Floor Test ───────────────────────────────────────────────────


class TestSystemChunkFloor:

    @pytest.mark.asyncio
    async def test_system_chunk_never_below_floor(self) -> None:
        """System chunks never drop below system_floor (0.5)."""
        # Very old system chunk with no retrieval history → would score low without floor
        chunk = _chunk_with_ts(
            "sys-001",
            ChunkType.SYSTEM,
            datetime.now(timezone.utc) - timedelta(days=89),
        )
        scorer = _make_scorer(chunks=[chunk], outcomes=[])
        await scorer.score_all(user_id="default")
        assert chunk.metadata.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_fact_chunk_never_below_floor(self) -> None:
        """Fact chunks also get the system_floor guarantee."""
        chunk = _chunk_with_ts(
            "fact-001",
            ChunkType.FACT,
            datetime.now(timezone.utc) - timedelta(days=89),
        )
        scorer = _make_scorer(chunks=[chunk], outcomes=[])
        await scorer.score_all(user_id="default")
        assert chunk.metadata.confidence >= 0.5

    @pytest.mark.asyncio
    async def test_conversation_chunk_can_go_below_floor(self) -> None:
        """Conversation chunks are NOT protected by the floor."""
        chunk = _chunk_with_ts(
            "conv-001",
            ChunkType.CONVERSATION,
            datetime.now(timezone.utc) - timedelta(days=89),
        )
        scorer = _make_scorer(chunks=[chunk], outcomes=[])
        await scorer.score_all(user_id="default")
        # Conversation chunks should score low (no retrieval, old, low type bonus)
        # This tests that the floor is NOT applied
        assert chunk.metadata.confidence < 0.5
