"""Tests for Correction Classifier — heuristic classification + database storage."""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from hestia.learning.database import LearningDatabase
from hestia.learning.models import Correction, CorrectionType, DistillationRun, DistillationStatus
from hestia.learning.correction_classifier import CorrectionClassifier


class TestCorrectionClassifierHeuristics:
    """Test heuristic pre-classification (no LLM)."""

    def test_timezone_keywords(self):
        assert CorrectionClassifier.heuristic_classify(
            "The meeting is in EST, not PST timezone"
        ) == CorrectionType.TIMEZONE

    def test_timezone_utc(self):
        assert CorrectionClassifier.heuristic_classify(
            "It should be UTC+5, not UTC+8"
        ) == CorrectionType.TIMEZONE

    def test_timezone_am_pm(self):
        assert CorrectionClassifier.heuristic_classify(
            "That's 3 AM not PM"
        ) == CorrectionType.TIMEZONE

    def test_tool_usage_keywords(self):
        assert CorrectionClassifier.heuristic_classify(
            "You should have used the calendar tool, not notes"
        ) == CorrectionType.TOOL_USAGE

    def test_tool_usage_didnt(self):
        assert CorrectionClassifier.heuristic_classify(
            "You didn't use the reminder tool"
        ) == CorrectionType.TOOL_USAGE

    def test_preference_keywords(self):
        assert CorrectionClassifier.heuristic_classify(
            "I prefer bullet points rather than paragraphs"
        ) == CorrectionType.PREFERENCE

    def test_preference_style(self):
        assert CorrectionClassifier.heuristic_classify(
            "The tone is too formal, use a casual style"
        ) == CorrectionType.PREFERENCE

    def test_factual_default(self):
        assert CorrectionClassifier.heuristic_classify(
            "That's wrong, the capital of France is Paris"
        ) == CorrectionType.FACTUAL

    def test_empty_note_returns_factual(self):
        assert CorrectionClassifier.heuristic_classify("") == CorrectionType.FACTUAL

    def test_none_like_empty(self):
        assert CorrectionClassifier.heuristic_classify("") == CorrectionType.FACTUAL

    def test_priority_timezone_over_tool(self):
        """Timezone keywords take priority over tool keywords."""
        assert CorrectionClassifier.heuristic_classify(
            "Use the calendar for the correct timezone"
        ) == CorrectionType.TIMEZONE


class TestLearningDatabaseCorrections:
    """Test correction storage in LearningDatabase."""

    @pytest.fixture
    async def db(self, tmp_path):
        db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_create_and_get_correction(self, db):
        correction = Correction(
            id=str(uuid.uuid4()),
            user_id="test_user",
            outcome_id="outcome_123",
            correction_type=CorrectionType.FACTUAL,
            analysis="User corrected a factual error",
            confidence=0.85,
        )
        await db.create_correction(correction)
        result = await db.get_correction("outcome_123", "test_user")
        assert result is not None
        assert result.correction_type == CorrectionType.FACTUAL
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_list_corrections_with_type_filter(self, db):
        for i, ct in enumerate([CorrectionType.FACTUAL, CorrectionType.TIMEZONE, CorrectionType.FACTUAL]):
            await db.create_correction(Correction(
                id=str(uuid.uuid4()), user_id="test_user",
                outcome_id=f"outcome_{i}", correction_type=ct,
                analysis=f"Test {i}", confidence=0.8,
            ))
        all_c = await db.list_corrections("test_user")
        assert len(all_c) == 3
        factual = await db.list_corrections("test_user", correction_type="factual")
        assert len(factual) == 2

    @pytest.mark.asyncio
    async def test_correction_stats(self, db):
        for ct in [CorrectionType.FACTUAL, CorrectionType.FACTUAL, CorrectionType.TIMEZONE]:
            await db.create_correction(Correction(
                id=str(uuid.uuid4()), user_id="test_user",
                outcome_id=str(uuid.uuid4()), correction_type=ct,
                analysis="test", confidence=0.8,
            ))
        stats = await db.get_correction_stats("test_user")
        assert stats["factual"] == 2
        assert stats["timezone"] == 1
        assert stats["total"] == 3

    @pytest.mark.asyncio
    async def test_duplicate_outcome_id_ignored(self, db):
        c1 = Correction(
            id=str(uuid.uuid4()), user_id="test_user", outcome_id="dup",
            correction_type=CorrectionType.FACTUAL, analysis="first", confidence=0.8,
        )
        await db.create_correction(c1)
        c2 = Correction(
            id=str(uuid.uuid4()), user_id="test_user", outcome_id="dup",
            correction_type=CorrectionType.TIMEZONE, analysis="second", confidence=0.9,
        )
        await db.create_correction(c2)
        stored = await db.get_correction("dup", "test_user")
        assert stored.correction_type == CorrectionType.FACTUAL  # First wins


class TestLearningDatabaseDistillation:
    """Test distillation run tracking."""

    @pytest.fixture
    async def db(self, tmp_path):
        db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_create_and_get_run(self, db):
        run = DistillationRun(
            id=str(uuid.uuid4()), user_id="test_user",
            run_timestamp=datetime.now(timezone.utc), source="manual",
        )
        await db.create_distillation_run(run)
        result = await db.get_latest_distillation_run("test_user")
        assert result is not None
        assert result.source == "manual"
        assert result.status == DistillationStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_update_run(self, db):
        run_id = str(uuid.uuid4())
        run = DistillationRun(
            id=run_id, user_id="test_user",
            run_timestamp=datetime.now(timezone.utc), source="scheduled",
        )
        await db.create_distillation_run(run)
        await db.update_distillation_run(
            run_id, status="complete", outcomes_processed=25, principles_generated=3,
        )
        result = await db.get_latest_distillation_run("test_user")
        assert result.status == DistillationStatus.COMPLETE
        assert result.outcomes_processed == 25

    @pytest.mark.asyncio
    async def test_link_outcome_to_principle(self, db):
        mapping_id = await db.link_outcome_to_principle(
            user_id="test_user", outcome_id="o1", principle_id="p1",
            confidence=0.8, source="batch_distill",
        )
        assert mapping_id is not None


class TestCorrectionClassifierBatch:
    """Test batch classification of pending corrections."""

    @pytest.fixture
    async def classifier(self, tmp_path):
        learning_db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await learning_db.connect()
        outcome_db = AsyncMock()
        classifier = CorrectionClassifier(
            learning_db=learning_db, outcome_db=outcome_db,
        )
        yield classifier
        await learning_db.close()

    @pytest.mark.asyncio
    async def test_no_outcomes(self, classifier):
        classifier._outcome_db.list_outcomes_with_feedback = AsyncMock(return_value=[])
        stats = await classifier.classify_all_pending("test_user")
        assert stats["classified"] == 0

    @pytest.mark.asyncio
    async def test_classify_correction(self, classifier):
        mock_outcome = MagicMock()
        mock_outcome.id = "outcome_1"
        mock_outcome.feedback = "correction"
        mock_outcome.feedback_note = "The timezone was wrong, should be PST"
        mock_outcome.response_content = "The meeting is at 3pm EST"
        classifier._outcome_db.list_outcomes_with_feedback = AsyncMock(
            return_value=[mock_outcome]
        )
        stats = await classifier.classify_all_pending("test_user")
        assert stats["classified"] == 1
        correction = await classifier._learning_db.get_correction("outcome_1", "test_user")
        assert correction is not None
        assert correction.correction_type == CorrectionType.TIMEZONE

    @pytest.mark.asyncio
    async def test_skip_already_classified(self, classifier):
        await classifier._learning_db.create_correction(Correction(
            id="c1", user_id="test_user", outcome_id="outcome_1",
            correction_type=CorrectionType.FACTUAL, analysis="test", confidence=0.8,
        ))
        mock_outcome = MagicMock()
        mock_outcome.id = "outcome_1"
        mock_outcome.feedback = "correction"
        mock_outcome.feedback_note = "wrong"
        mock_outcome.response_content = "..."
        classifier._outcome_db.list_outcomes_with_feedback = AsyncMock(
            return_value=[mock_outcome]
        )
        stats = await classifier.classify_all_pending("test_user")
        assert stats["classified"] == 0
        assert stats["skipped"] == 1

    @pytest.mark.asyncio
    async def test_confidence_boost_for_strong_match(self, classifier):
        mock_outcome = MagicMock()
        mock_outcome.id = "outcome_2"
        mock_outcome.feedback = "correction"
        mock_outcome.feedback_note = "Wrong timezone, it should be PST timezone"
        mock_outcome.response_content = "..."
        classifier._outcome_db.list_outcomes_with_feedback = AsyncMock(
            return_value=[mock_outcome]
        )
        await classifier.classify_all_pending("test_user")
        correction = await classifier._learning_db.get_correction("outcome_2", "test_user")
        assert correction.confidence == 0.90  # Boosted for strong keyword match
