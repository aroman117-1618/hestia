"""Tests for Outcome-to-Principle Distiller."""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from hestia.learning.database import LearningDatabase
from hestia.learning.models import DistillationRun, DistillationStatus
from hestia.learning.outcome_distiller import OutcomeDistiller, MIN_PRINCIPLE_WORDS


class TestOutcomeDistillerSelection:
    """Test distillation pipeline."""

    @pytest.fixture
    async def distiller(self, tmp_path):
        learning_db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await learning_db.connect()
        outcome_db = AsyncMock()
        principle_store = AsyncMock()
        principle_store.store_principle = AsyncMock()
        # find_duplicate must return None so principles are not silently dropped
        principle_store.find_duplicate = AsyncMock(return_value=None)
        distiller = OutcomeDistiller(
            learning_db=learning_db,
            outcome_db=outcome_db,
            principle_store=principle_store,
        )
        yield distiller
        await learning_db.close()

    @pytest.mark.asyncio
    async def test_no_outcomes_returns_empty(self, distiller):
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=[])
        result = await distiller.distill_from_outcomes("test_user")
        assert result["outcomes_analyzed"] == 0
        assert result["principles_generated"] == 0

    @pytest.mark.asyncio
    async def test_insufficient_outcomes_skips(self, distiller):
        mock = MagicMock()
        mock.id = "o1"
        mock.response_content = "Hello"
        mock.feedback = "positive"
        mock.feedback_note = None
        mock.timestamp = datetime.now(timezone.utc).isoformat()
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=[mock])
        result = await distiller.distill_from_outcomes("test_user", min_outcomes=5)
        assert result["outcomes_analyzed"] == 1
        assert result["principles_generated"] == 0

    @pytest.mark.asyncio
    async def test_creates_run_record(self, distiller):
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=[])
        await distiller.distill_from_outcomes("test_user")
        run = await distiller._learning_db.get_latest_distillation_run("test_user")
        assert run is not None
        assert run.status == DistillationStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_no_inference_skips_gracefully(self, distiller):
        mocks = []
        for i in range(5):
            m = MagicMock()
            m.id = f"o{i}"
            m.response_content = f"Great response about topic {i} with enough content"
            m.feedback = "positive"
            m.feedback_note = "Helpful!"
            m.timestamp = datetime.now(timezone.utc).isoformat()
            mocks.append(m)
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=mocks)
        # No inference client set
        result = await distiller.distill_from_outcomes("test_user")
        assert result["outcomes_analyzed"] == 5
        assert result["principles_generated"] == 0

    @pytest.mark.asyncio
    async def test_with_inference_creates_principles(self, distiller):
        mocks = []
        for i in range(5):
            m = MagicMock()
            m.id = f"o{i}"
            m.response_content = f"Detailed response about Python testing with pytest fixtures number {i}"
            m.feedback = "positive"
            m.feedback_note = "Great advice"
            m.timestamp = datetime.now(timezone.utc).isoformat()
            mocks.append(m)
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=mocks)

        mock_inference = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "[testing] User values test-driven development with pytest fixtures and clear assertion messages"
        mock_inference.chat = AsyncMock(return_value=mock_response)
        distiller._inference = mock_inference

        result = await distiller.distill_from_outcomes("test_user")
        assert result["outcomes_analyzed"] == 5
        assert result["principles_generated"] == 1
        distiller._principle_store.store_principle.assert_called_once()

    @pytest.mark.asyncio
    async def test_failure_records_error(self, distiller):
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(
            side_effect=Exception("DB connection failed")
        )
        result = await distiller.distill_from_outcomes("test_user")
        assert result["error"] is not None
        run = await distiller._learning_db.get_latest_distillation_run("test_user")
        assert run.status == DistillationStatus.FAILED
        assert "DB connection failed" in run.error_message

    @pytest.mark.asyncio
    async def test_multiple_principles_from_llm(self, distiller):
        mocks = [MagicMock(id=f"o{i}", response_content=f"Response {i}", feedback="positive",
                           feedback_note=None, timestamp=datetime.now(timezone.utc).isoformat())
                 for i in range(5)]
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=mocks)

        mock_inference = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = """[communication] User prefers concise bullet-point answers over long detailed paragraphs with excess context
[coding] User wants test examples alongside code explanations showing expected inputs and outputs"""
        mock_inference.chat = AsyncMock(return_value=mock_response)
        distiller._inference = mock_inference

        result = await distiller.distill_from_outcomes("test_user")
        assert result["principles_generated"] == 2


class TestPrincipleQualityGate:
    """Test the quality filtering in _parse_principles."""

    def _make_distiller(self):
        return OutcomeDistiller(
            learning_db=MagicMock(),
            outcome_db=MagicMock(),
        )

    def test_rejects_short_principles(self):
        distiller = self._make_distiller()
        result = distiller._parse_principles("[test] Too short", "user1")
        assert len(result) == 0

    def test_rejects_generic_principles(self):
        distiller = self._make_distiller()
        result = distiller._parse_principles(
            "[quality] User likes good responses and wants everything to be accurate and helpful always",
            "user1",
        )
        assert len(result) == 0  # Contains "user likes good"

    def test_accepts_specific_principles(self):
        distiller = self._make_distiller()
        result = distiller._parse_principles(
            "[coding] User prefers pytest fixtures over setUp/tearDown methods and wants assertion messages in every test",
            "user1",
        )
        assert len(result) == 1
        assert result[0].domain == "coding"
        assert result[0].status.value == "pending"

    def test_skips_non_bracket_lines(self):
        distiller = self._make_distiller()
        result = distiller._parse_principles(
            "This is just a comment\n[valid] This is a real principle with enough words to pass the quality gate easily",
            "user1",
        )
        assert len(result) == 1

    def test_empty_content_after_bracket(self):
        distiller = self._make_distiller()
        result = distiller._parse_principles("[empty]", "user1")
        assert len(result) == 0

    def test_min_word_count(self):
        """Principle must have at least MIN_PRINCIPLE_WORDS words."""
        distiller = self._make_distiller()
        # Exactly at threshold
        words = " ".join(["word"] * MIN_PRINCIPLE_WORDS)
        result = distiller._parse_principles(f"[test] {words}", "user1")
        assert len(result) == 1

    def test_format_outcomes(self):
        distiller = self._make_distiller()
        mock = MagicMock()
        mock.response_content = "Hello world"
        mock.feedback = "positive"
        mock.feedback_note = "Great!"
        formatted = distiller._format_outcomes([mock])
        assert "Hello world" in formatted
        assert "[feedback: positive]" in formatted
        assert "Note: Great!" in formatted


# ─────────────────────────────────────────────────────────────────────────────
# Sprint 19: distill_from_corrections + semantic dedup (Gap 2 + Gap 3)
# ─────────────────────────────────────────────────────────────────────────────

class TestDistillFromCorrections:
    """Test the correction-to-principle distillation path (Gap 2)."""

    @pytest.fixture
    async def distiller(self, tmp_path):
        learning_db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await learning_db.connect()
        outcome_db = AsyncMock()
        principle_store = AsyncMock()
        principle_store.store_principle = AsyncMock()
        principle_store.find_duplicate = AsyncMock(return_value=None)
        inst = OutcomeDistiller(
            learning_db=learning_db,
            outcome_db=outcome_db,
            principle_store=principle_store,
        )
        yield inst
        await learning_db.close()

    @pytest.mark.asyncio
    async def test_no_corrections_returns_empty(self, distiller):
        distiller._learning_db.list_corrections = AsyncMock(return_value=[])
        result = await distiller.distill_from_corrections("user1")
        assert result["corrections_processed"] == 0
        assert result["principles_generated"] == 0

    @pytest.mark.asyncio
    async def test_insufficient_corrections_skips_llm(self, distiller):
        from hestia.learning.models import Correction, CorrectionType
        correction = Correction(
            id="c1", user_id="user1", outcome_id="o1",
            correction_type=CorrectionType.PREFERENCE,
            analysis="test", confidence=0.75,
        )
        distiller._learning_db.list_corrections = AsyncMock(return_value=[correction])
        result = await distiller.distill_from_corrections("user1", min_corrections=2)
        assert result["corrections_processed"] == 0
        assert result["principles_generated"] == 0

    @pytest.mark.asyncio
    async def test_no_inference_skips_gracefully(self, distiller):
        from hestia.learning.models import Correction, CorrectionType
        corrections = [
            Correction(
                id=f"c{i}", user_id="user1", outcome_id=f"o{i}",
                correction_type=CorrectionType.PREFERENCE,
                analysis="test", confidence=0.75,
            )
            for i in range(3)
        ]
        distiller._learning_db.list_corrections = AsyncMock(return_value=corrections)
        # No inference client
        result = await distiller.distill_from_corrections("user1")
        assert result["corrections_processed"] == 0
        assert result["principles_generated"] == 0

    @pytest.mark.asyncio
    async def test_with_corrections_creates_principle(self, distiller):
        from hestia.learning.models import Correction, CorrectionType
        corrections = [
            Correction(
                id=f"c{i}", user_id="user1", outcome_id=f"o{i}",
                correction_type=CorrectionType.PREFERENCE,
                analysis="test", confidence=0.75,
            )
            for i in range(3)
        ]
        distiller._learning_db.list_corrections = AsyncMock(return_value=corrections)
        distiller._outcome_db.get_outcome = AsyncMock(
            return_value={"feedback_note": "Please be more concise in your answers"}
        )

        mock_inference = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            "[communication] Provide concise answers without unnecessary preamble "
            "and keep responses focused on what the user explicitly asked"
        )
        mock_inference.chat = AsyncMock(return_value=mock_response)
        distiller._inference = mock_inference

        result = await distiller.distill_from_corrections("user1")
        assert result["principles_generated"] == 1
        distiller._principle_store.store_principle.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_feedback_note_skips_group(self, distiller):
        """If outcome has no feedback_note, the correction group produces nothing."""
        from hestia.learning.models import Correction, CorrectionType
        corrections = [
            Correction(
                id=f"c{i}", user_id="user1", outcome_id=f"o{i}",
                correction_type=CorrectionType.FACTUAL,
                analysis="test", confidence=0.75,
            )
            for i in range(3)
        ]
        distiller._learning_db.list_corrections = AsyncMock(return_value=corrections)
        # outcome has no feedback_note
        distiller._outcome_db.get_outcome = AsyncMock(
            return_value={"feedback_note": None}
        )

        mock_inference = AsyncMock()
        distiller._inference = mock_inference

        result = await distiller.distill_from_corrections("user1")
        assert result["principles_generated"] == 0
        mock_inference.chat.assert_not_called()


class TestSemanticDedup:
    """Test that find_duplicate prevents duplicate principles (Gap 3)."""

    @pytest.mark.asyncio
    async def test_dedup_blocks_similar_principle(self, tmp_path):
        """A principle similar to an existing one is not stored."""
        learning_db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await learning_db.connect()
        outcome_db = AsyncMock()
        principle_store = AsyncMock()
        principle_store.store_principle = AsyncMock()
        # Simulate duplicate found
        duplicate_principle = MagicMock()
        duplicate_principle.id = "existing-123"
        principle_store.find_duplicate = AsyncMock(return_value=duplicate_principle)

        distiller = OutcomeDistiller(
            learning_db=learning_db,
            outcome_db=outcome_db,
            principle_store=principle_store,
        )

        mocks = [
            MagicMock(id=f"o{i}", response_content=f"Response {i}", feedback="positive",
                      feedback_note=None, timestamp="2026-01-01T00:00:00Z")
            for i in range(5)
        ]
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=mocks)

        mock_inference = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = (
            "[communication] User prefers concise responses without lengthy preamble "
            "or repeated context that they already know from the conversation"
        )
        mock_inference.chat = AsyncMock(return_value=mock_response)
        distiller._inference = mock_inference

        result = await distiller.distill_from_outcomes("user1")
        # Duplicate detected — principle NOT stored
        assert result["principles_generated"] == 0
        principle_store.store_principle.assert_not_called()
        await learning_db.close()
