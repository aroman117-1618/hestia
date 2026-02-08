"""
Tests for Hestia voice journaling API routes.

WS2: Voice Journaling — Session 2
Tests both voice endpoints and Pydantic schema validation.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.api.schemas import (
    VoiceFlaggedWord,
    VoiceQualityCheckRequest,
    VoiceQualityCheckResponse,
    VoiceIntentType,
    VoiceJournalIntent,
    VoiceCrossReferenceSource,
    VoiceCrossReference,
    VoiceActionPlanItem,
    VoiceJournalAnalyzeRequest,
    VoiceJournalAnalyzeResponse,
)
from hestia.voice.models import (
    FlaggedWord,
    QualityReport,
    JournalAnalysis,
    JournalIntent,
    IntentType,
    CrossReference,
    CrossReferenceSource,
    ActionPlanItem,
)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def clean_report() -> QualityReport:
    """A transcript that passed quality check cleanly."""
    return QualityReport(
        transcript="I need to follow up with the contractor about the kitchen",
        flagged_words=[],
        overall_confidence=0.95,
        needs_review=False,
    )


@pytest.fixture
def flagged_report() -> QualityReport:
    """A transcript with flagged words."""
    return QualityReport(
        transcript="I need to follow up with the contactor about the kichen",
        flagged_words=[
            FlaggedWord(
                word="contactor",
                position=35,
                confidence=0.8,
                suggestions=["contractor", "contactor"],
                reason="proper noun",
            ),
            FlaggedWord(
                word="kichen",
                position=55,
                confidence=0.9,
                suggestions=["kitchen"],
                reason="common misspelling",
            ),
        ],
        overall_confidence=0.6,
        needs_review=True,
    )


@pytest.fixture
def full_analysis() -> JournalAnalysis:
    """A complete journal analysis with all stages populated."""
    analysis = JournalAnalysis.create("I need to call the contractor about the kitchen timeline")
    analysis.intents = [
        JournalIntent(
            id="intent-abc123",
            intent_type=IntentType.ACTION_ITEM,
            content="Follow up with contractor about kitchen timeline",
            confidence=0.9,
            entities=["contractor", "kitchen"],
        ),
    ]
    analysis.cross_references = [
        CrossReference(
            source=CrossReferenceSource.CALENDAR,
            match="Kitchen meeting (Feb 10 14:00)",
            relevance=0.7,
            details={"event_id": "evt-1", "title": "Kitchen meeting"},
        ),
    ]
    analysis.action_plan = [
        ActionPlanItem(
            id="action-xyz789",
            action="Create a reminder to follow up with contractor",
            tool_call="create_reminder",
            arguments={"title": "Follow up with contractor - kitchen timeline"},
            confidence=0.85,
            intent_id="intent-abc123",
        ),
    ]
    analysis.summary = "Journal entry about following up with contractor on kitchen project."
    return analysis


@pytest.fixture
def empty_analysis() -> JournalAnalysis:
    """A journal analysis with no intents found."""
    analysis = JournalAnalysis.create("Just thinking out loud today")
    analysis.summary = "No actionable intents found in journal entry."
    return analysis


# ── Test: Pydantic Schemas ──────────────────────────────────────────


class TestVoiceSchemas:
    """Test voice Pydantic schema validation."""

    def test_quality_check_request_valid(self):
        """Valid quality check request should pass validation."""
        req = VoiceQualityCheckRequest(
            transcript="Hello world",
            known_entities=["Alice", "Bob"],
        )
        assert req.transcript == "Hello world"
        assert req.known_entities == ["Alice", "Bob"]

    def test_quality_check_request_no_entities(self):
        """Quality check request without entities should be valid."""
        req = VoiceQualityCheckRequest(transcript="Hello world")
        assert req.known_entities is None

    def test_quality_check_request_empty_transcript(self):
        """Empty transcript should fail validation."""
        with pytest.raises(Exception):
            VoiceQualityCheckRequest(transcript="")

    def test_quality_check_request_too_long(self):
        """Transcript over 10000 chars should fail validation."""
        with pytest.raises(Exception):
            VoiceQualityCheckRequest(transcript="x" * 10001)

    def test_quality_check_response_clean(self):
        """Clean quality check response should serialize correctly."""
        resp = VoiceQualityCheckResponse(
            transcript="Hello world",
            flagged_words=[],
            overall_confidence=0.95,
            needs_review=False,
        )
        data = resp.model_dump()
        assert data["overall_confidence"] == 0.95
        assert data["needs_review"] is False
        assert data["flagged_words"] == []

    def test_quality_check_response_with_flags(self):
        """Quality check response with flags should serialize correctly."""
        resp = VoiceQualityCheckResponse(
            transcript="contactor issue",
            flagged_words=[
                VoiceFlaggedWord(
                    word="contactor",
                    position=0,
                    confidence=0.8,
                    suggestions=["contractor"],
                    reason="proper noun",
                ),
            ],
            overall_confidence=0.6,
            needs_review=True,
        )
        data = resp.model_dump()
        assert len(data["flagged_words"]) == 1
        assert data["flagged_words"][0]["word"] == "contactor"
        assert data["flagged_words"][0]["suggestions"] == ["contractor"]

    def test_journal_analyze_request_valid(self):
        """Valid journal analyze request should pass validation."""
        req = VoiceJournalAnalyzeRequest(
            transcript="I need to call the contractor",
            mode="tia",
        )
        assert req.transcript == "I need to call the contractor"
        assert req.mode == "tia"

    def test_journal_analyze_request_default_mode(self):
        """Journal analyze request should default to tia mode."""
        req = VoiceJournalAnalyzeRequest(transcript="Hello")
        assert req.mode == "tia"

    def test_journal_analyze_request_empty_transcript(self):
        """Empty transcript should fail validation."""
        with pytest.raises(Exception):
            VoiceJournalAnalyzeRequest(transcript="")

    def test_journal_analyze_response_full(self):
        """Full journal analyze response should serialize correctly."""
        resp = VoiceJournalAnalyzeResponse(
            id="journal-abc123",
            transcript="Follow up with contractor",
            intents=[
                VoiceJournalIntent(
                    id="intent-1",
                    intent_type=VoiceIntentType.ACTION_ITEM,
                    content="Follow up with contractor",
                    confidence=0.9,
                    entities=["contractor"],
                ),
            ],
            cross_references=[
                VoiceCrossReference(
                    source=VoiceCrossReferenceSource.CALENDAR,
                    match="Kitchen meeting",
                    relevance=0.7,
                    details={"event_id": "evt-1"},
                ),
            ],
            action_plan=[
                VoiceActionPlanItem(
                    id="action-1",
                    action="Create reminder",
                    tool_call="create_reminder",
                    arguments={"title": "Follow up"},
                    confidence=0.85,
                    intent_id="intent-1",
                ),
            ],
            summary="Journal about contractor follow-up.",
            timestamp="2026-02-08T12:00:00+00:00",
        )
        data = resp.model_dump()
        assert data["id"] == "journal-abc123"
        assert len(data["intents"]) == 1
        assert len(data["cross_references"]) == 1
        assert len(data["action_plan"]) == 1
        assert data["action_plan"][0]["tool_call"] == "create_reminder"

    def test_journal_analyze_response_empty(self):
        """Empty journal analyze response should serialize correctly."""
        resp = VoiceJournalAnalyzeResponse(
            id="journal-empty",
            transcript="Nothing much",
            summary="No actionable intents found.",
            timestamp="2026-02-08T12:00:00+00:00",
        )
        data = resp.model_dump()
        assert data["intents"] == []
        assert data["cross_references"] == []
        assert data["action_plan"] == []

    def test_intent_type_enum_values(self):
        """All intent types should be valid enum values."""
        for vtype in VoiceIntentType:
            assert vtype.value in {
                "action_item", "reminder", "note",
                "decision", "reflection", "follow_up",
            }

    def test_cross_reference_source_enum_values(self):
        """All cross-reference sources should be valid enum values."""
        for source in VoiceCrossReferenceSource:
            assert source.value in {"calendar", "mail", "memory", "reminders"}


# ── Test: Quality Check Route ───────────────────────────────────────


class TestQualityCheckRoute:
    """Test POST /v1/voice/quality-check route logic."""

    @pytest.mark.asyncio
    async def test_quality_check_clean(self, clean_report):
        """Clean transcript should return high confidence, no review needed."""
        from hestia.api.routes.voice import quality_check

        req = VoiceQualityCheckRequest(
            transcript="I need to follow up with the contractor about the kitchen",
        )

        with patch("hestia.api.routes.voice.get_quality_checker") as mock_get:
            mock_checker = MagicMock()
            mock_get.return_value = mock_checker
            mock_checker.check = AsyncMock(return_value=clean_report)

            resp = await quality_check(request=req, device_id="test-device")

        assert isinstance(resp, VoiceQualityCheckResponse)
        assert resp.overall_confidence == 0.95
        assert resp.needs_review is False
        assert len(resp.flagged_words) == 0

    @pytest.mark.asyncio
    async def test_quality_check_flagged(self, flagged_report):
        """Transcript with issues should return flagged words."""
        from hestia.api.routes.voice import quality_check

        req = VoiceQualityCheckRequest(
            transcript="I need to follow up with the contactor about the kichen",
        )

        with patch("hestia.api.routes.voice.get_quality_checker") as mock_get:
            mock_checker = MagicMock()
            mock_get.return_value = mock_checker
            mock_checker.check = AsyncMock(return_value=flagged_report)

            resp = await quality_check(request=req, device_id="test-device")

        assert resp.needs_review is True
        assert resp.overall_confidence == 0.6
        assert len(resp.flagged_words) == 2
        assert resp.flagged_words[0].word == "contactor"
        assert resp.flagged_words[1].word == "kichen"
        assert "contractor" in resp.flagged_words[0].suggestions

    @pytest.mark.asyncio
    async def test_quality_check_with_entities(self, clean_report):
        """Known entities should be passed through to the checker."""
        from hestia.api.routes.voice import quality_check

        req = VoiceQualityCheckRequest(
            transcript="Meeting with Alice about Project Zeus",
            known_entities=["Alice", "Project Zeus"],
        )

        with patch("hestia.api.routes.voice.get_quality_checker") as mock_get:
            mock_checker = MagicMock()
            mock_get.return_value = mock_checker
            mock_checker.check = AsyncMock(return_value=clean_report)

            await quality_check(request=req, device_id="test-device")

            # Verify entities were passed through
            mock_checker.check.assert_called_once_with(
                transcript="Meeting with Alice about Project Zeus",
                known_entities=["Alice", "Project Zeus"],
            )

    @pytest.mark.asyncio
    async def test_quality_check_error_returns_500(self):
        """Checker failure should return 500."""
        from fastapi import HTTPException
        from hestia.api.routes.voice import quality_check

        req = VoiceQualityCheckRequest(transcript="Test transcript")

        with patch("hestia.api.routes.voice.get_quality_checker") as mock_get:
            mock_checker = MagicMock()
            mock_get.return_value = mock_checker
            mock_checker.check = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

            with pytest.raises(HTTPException) as exc_info:
                await quality_check(request=req, device_id="test-device")

            assert exc_info.value.status_code == 500
            assert "quality_check_failed" in str(exc_info.value.detail)


# ── Test: Journal Analyze Route ─────────────────────────────────────


class TestJournalAnalyzeRoute:
    """Test POST /v1/voice/journal-analyze route logic."""

    @pytest.mark.asyncio
    async def test_journal_analyze_full(self, full_analysis):
        """Full analysis should return intents, cross-refs, and action plan."""
        from hestia.api.routes.voice import journal_analyze

        req = VoiceJournalAnalyzeRequest(
            transcript="I need to call the contractor about the kitchen timeline",
            mode="tia",
        )

        with patch("hestia.api.routes.voice.get_journal_analyzer") as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            mock_analyzer.analyze = AsyncMock(return_value=full_analysis)

            resp = await journal_analyze(request=req, device_id="test-device")

        assert isinstance(resp, VoiceJournalAnalyzeResponse)
        assert resp.id == full_analysis.id
        assert len(resp.intents) == 1
        assert resp.intents[0].intent_type == VoiceIntentType.ACTION_ITEM
        assert resp.intents[0].content == "Follow up with contractor about kitchen timeline"
        assert len(resp.cross_references) == 1
        assert resp.cross_references[0].source == VoiceCrossReferenceSource.CALENDAR
        assert len(resp.action_plan) == 1
        assert resp.action_plan[0].tool_call == "create_reminder"
        assert resp.summary == "Journal entry about following up with contractor on kitchen project."

    @pytest.mark.asyncio
    async def test_journal_analyze_empty(self, empty_analysis):
        """Transcript with no intents should return empty lists."""
        from hestia.api.routes.voice import journal_analyze

        req = VoiceJournalAnalyzeRequest(transcript="Just thinking out loud today")

        with patch("hestia.api.routes.voice.get_journal_analyzer") as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            mock_analyzer.analyze = AsyncMock(return_value=empty_analysis)

            resp = await journal_analyze(request=req, device_id="test-device")

        assert resp.intents == []
        assert resp.cross_references == []
        assert resp.action_plan == []
        assert "No actionable intents" in resp.summary

    @pytest.mark.asyncio
    async def test_journal_analyze_mode_passed(self, full_analysis):
        """Mode should be passed through to the analyzer."""
        from hestia.api.routes.voice import journal_analyze

        req = VoiceJournalAnalyzeRequest(
            transcript="Research quantum computing",
            mode="mira",
        )

        with patch("hestia.api.routes.voice.get_journal_analyzer") as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            mock_analyzer.analyze = AsyncMock(return_value=full_analysis)

            await journal_analyze(request=req, device_id="test-device")

            mock_analyzer.analyze.assert_called_once_with(
                transcript="Research quantum computing",
                mode="mira",
            )

    @pytest.mark.asyncio
    async def test_journal_analyze_default_mode(self, full_analysis):
        """Default mode should be tia."""
        from hestia.api.routes.voice import journal_analyze

        req = VoiceJournalAnalyzeRequest(transcript="Something to analyze")

        with patch("hestia.api.routes.voice.get_journal_analyzer") as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            mock_analyzer.analyze = AsyncMock(return_value=full_analysis)

            await journal_analyze(request=req, device_id="test-device")

            mock_analyzer.analyze.assert_called_once_with(
                transcript="Something to analyze",
                mode="tia",
            )

    @pytest.mark.asyncio
    async def test_journal_analyze_error_returns_500(self):
        """Analyzer failure should return 500."""
        from fastapi import HTTPException
        from hestia.api.routes.voice import journal_analyze

        req = VoiceJournalAnalyzeRequest(transcript="Test transcript")

        with patch("hestia.api.routes.voice.get_journal_analyzer") as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            mock_analyzer.analyze = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

            with pytest.raises(HTTPException) as exc_info:
                await journal_analyze(request=req, device_id="test-device")

            assert exc_info.value.status_code == 500
            assert "journal_analysis_failed" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_journal_analyze_timestamp_format(self, full_analysis):
        """Response timestamp should be ISO 8601 format."""
        from hestia.api.routes.voice import journal_analyze

        req = VoiceJournalAnalyzeRequest(transcript="Test entry")

        with patch("hestia.api.routes.voice.get_journal_analyzer") as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            mock_analyzer.analyze = AsyncMock(return_value=full_analysis)

            resp = await journal_analyze(request=req, device_id="test-device")

        # Should be parseable as ISO 8601
        parsed = datetime.fromisoformat(resp.timestamp)
        assert parsed.tzinfo is not None or "+" in resp.timestamp or "Z" in resp.timestamp

    @pytest.mark.asyncio
    async def test_journal_analyze_cross_ref_details_preserved(self, full_analysis):
        """Cross-reference details dict should be preserved in response."""
        from hestia.api.routes.voice import journal_analyze

        req = VoiceJournalAnalyzeRequest(transcript="Kitchen contractor")

        with patch("hestia.api.routes.voice.get_journal_analyzer") as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            mock_analyzer.analyze = AsyncMock(return_value=full_analysis)

            resp = await journal_analyze(request=req, device_id="test-device")

        assert resp.cross_references[0].details["event_id"] == "evt-1"

    @pytest.mark.asyncio
    async def test_journal_analyze_action_plan_arguments(self, full_analysis):
        """Action plan arguments should be preserved in response."""
        from hestia.api.routes.voice import journal_analyze

        req = VoiceJournalAnalyzeRequest(transcript="Kitchen contractor")

        with patch("hestia.api.routes.voice.get_journal_analyzer") as mock_get:
            mock_analyzer = MagicMock()
            mock_get.return_value = mock_analyzer
            mock_analyzer.analyze = AsyncMock(return_value=full_analysis)

            resp = await journal_analyze(request=req, device_id="test-device")

        assert resp.action_plan[0].arguments["title"] == "Follow up with contractor - kitchen timeline"
        assert resp.action_plan[0].intent_id == "intent-abc123"
