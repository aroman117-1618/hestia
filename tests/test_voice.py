"""
Tests for Hestia voice journaling module.

WS2 Session 1: Voice module models, quality checker, journal analyzer.
"""

import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

from hestia.voice.models import (
    TranscriptSegment,
    FlaggedWord,
    QualityReport,
    JournalIntent,
    IntentType,
    CrossReference,
    CrossReferenceSource,
    ActionPlanItem,
    JournalAnalysis,
)
from hestia.voice.quality import TranscriptQualityChecker, REVIEW_CONFIDENCE_THRESHOLD
from hestia.voice.journal import JournalAnalyzer


# ── Test: TranscriptSegment ───────────────────────────────────────────


class TestTranscriptSegment:
    """Tests for TranscriptSegment data model."""

    def test_create_segment(self):
        seg = TranscriptSegment(
            text="hello world",
            start_time=0.0,
            end_time=1.5,
            confidence=0.95,
        )
        assert seg.text == "hello world"
        assert seg.start_time == 0.0
        assert seg.end_time == 1.5
        assert seg.confidence == 0.95

    def test_segment_to_dict(self):
        seg = TranscriptSegment(text="test", start_time=1.0, end_time=2.0, confidence=0.9)
        d = seg.to_dict()
        assert d["text"] == "test"
        assert d["start_time"] == 1.0
        assert d["confidence"] == 0.9

    def test_segment_from_dict(self):
        data = {"text": "test", "start_time": 0.5, "end_time": 1.5, "confidence": 0.8}
        seg = TranscriptSegment.from_dict(data)
        assert seg.text == "test"
        assert seg.confidence == 0.8

    def test_segment_roundtrip(self):
        original = TranscriptSegment(text="roundtrip", start_time=0.0, end_time=3.0, confidence=0.99)
        restored = TranscriptSegment.from_dict(original.to_dict())
        assert original.text == restored.text
        assert original.confidence == restored.confidence


# ── Test: FlaggedWord ─────────────────────────────────────────────────


class TestFlaggedWord:
    """Tests for FlaggedWord data model."""

    def test_create_flagged_word(self):
        fw = FlaggedWord(
            word="there",
            position=10,
            confidence=0.7,
            suggestions=["their", "they're"],
            reason="homophone",
        )
        assert fw.word == "there"
        assert fw.position == 10
        assert len(fw.suggestions) == 2
        assert fw.reason == "homophone"

    def test_flagged_word_defaults(self):
        fw = FlaggedWord(word="test", position=0, confidence=0.5)
        assert fw.suggestions == []
        assert fw.reason == ""

    def test_flagged_word_to_dict(self):
        fw = FlaggedWord(word="write", position=5, confidence=0.8, suggestions=["right", "rite"])
        d = fw.to_dict()
        assert d["word"] == "write"
        assert d["suggestions"] == ["right", "rite"]

    def test_flagged_word_from_dict(self):
        data = {
            "word": "brake",
            "position": 20,
            "confidence": 0.6,
            "suggestions": ["break"],
            "reason": "homophone",
        }
        fw = FlaggedWord.from_dict(data)
        assert fw.word == "brake"
        assert fw.suggestions == ["break"]

    def test_flagged_word_from_dict_defaults(self):
        """Missing optional fields should use defaults."""
        data = {"word": "test"}
        fw = FlaggedWord.from_dict(data)
        assert fw.position == 0
        assert fw.confidence == 0.5
        assert fw.suggestions == []


# ── Test: QualityReport ──────────────────────────────────────────────


class TestQualityReport:
    """Tests for QualityReport data model."""

    def test_create_clean_report(self):
        report = QualityReport(transcript="all good", overall_confidence=0.95)
        assert report.transcript == "all good"
        assert report.flagged_words == []
        assert not report.needs_review

    def test_create_report_with_flags(self):
        flags = [FlaggedWord(word="there", position=5, confidence=0.7)]
        report = QualityReport(
            transcript="go there now",
            flagged_words=flags,
            overall_confidence=0.75,
            needs_review=True,
        )
        assert len(report.flagged_words) == 1
        assert report.needs_review

    def test_report_roundtrip(self):
        flags = [FlaggedWord(word="write", position=3, confidence=0.8, suggestions=["right"])]
        original = QualityReport(
            transcript="I write code",
            flagged_words=flags,
            overall_confidence=0.8,
            needs_review=True,
        )
        restored = QualityReport.from_dict(original.to_dict())
        assert len(restored.flagged_words) == 1
        assert restored.flagged_words[0].word == "write"
        assert restored.overall_confidence == 0.8


# ── Test: JournalIntent ──────────────────────────────────────────────


class TestJournalIntent:
    """Tests for JournalIntent data model."""

    def test_create_intent(self):
        intent = JournalIntent.create(
            intent_type=IntentType.ACTION_ITEM,
            content="Follow up with contractor",
            confidence=0.9,
            entities=["contractor"],
        )
        assert intent.intent_type == IntentType.ACTION_ITEM
        assert intent.content == "Follow up with contractor"
        assert "contractor" in intent.entities
        assert intent.id.startswith("intent-")

    def test_intent_types(self):
        """All intent types should be valid."""
        for it in IntentType:
            intent = JournalIntent.create(intent_type=it, content="test")
            assert intent.intent_type == it

    def test_intent_roundtrip(self):
        original = JournalIntent.create(
            intent_type=IntentType.REMINDER,
            content="Buy groceries",
            entities=["groceries"],
        )
        restored = JournalIntent.from_dict(original.to_dict())
        assert restored.intent_type == IntentType.REMINDER
        assert restored.content == "Buy groceries"


# ── Test: CrossReference ─────────────────────────────────────────────


class TestCrossReference:
    """Tests for CrossReference data model."""

    def test_create_calendar_ref(self):
        ref = CrossReference(
            source=CrossReferenceSource.CALENDAR,
            match="Board Review - Thursday 2pm",
            relevance=0.8,
            details={"event_id": "123"},
        )
        assert ref.source == CrossReferenceSource.CALENDAR
        assert ref.relevance == 0.8

    def test_all_sources(self):
        """All cross-reference sources should be valid."""
        for source in CrossReferenceSource:
            ref = CrossReference(source=source, match="test", relevance=0.5)
            assert ref.source == source

    def test_cross_reference_roundtrip(self):
        original = CrossReference(
            source=CrossReferenceSource.MAIL,
            match="From boss: Re: Project update",
            relevance=0.6,
            details={"subject": "Re: Project update"},
        )
        restored = CrossReference.from_dict(original.to_dict())
        assert restored.source == CrossReferenceSource.MAIL
        assert restored.match == original.match


# ── Test: ActionPlanItem ─────────────────────────────────────────────


class TestActionPlanItem:
    """Tests for ActionPlanItem data model."""

    def test_create_action_with_tool(self):
        item = ActionPlanItem.create(
            action="Create reminder for contractor follow-up",
            tool_call="create_reminder",
            arguments={"title": "Follow up contractor", "notes": "Kitchen timeline"},
            confidence=0.85,
        )
        assert item.tool_call == "create_reminder"
        assert item.arguments["title"] == "Follow up contractor"
        assert item.id.startswith("action-")

    def test_create_action_without_tool(self):
        item = ActionPlanItem.create(
            action="Reflect on project priorities",
            confidence=0.7,
        )
        assert item.tool_call is None
        assert item.arguments == {}

    def test_action_roundtrip(self):
        original = ActionPlanItem.create(
            action="Create event",
            tool_call="create_event",
            arguments={"title": "Team meeting"},
        )
        restored = ActionPlanItem.from_dict(original.to_dict())
        assert restored.tool_call == "create_event"
        assert restored.arguments["title"] == "Team meeting"


# ── Test: JournalAnalysis ────────────────────────────────────────────


class TestJournalAnalysis:
    """Tests for JournalAnalysis data model."""

    def test_create_analysis(self):
        analysis = JournalAnalysis.create("I need to call the dentist")
        assert analysis.transcript == "I need to call the dentist"
        assert analysis.intents == []
        assert analysis.cross_references == []
        assert analysis.action_plan == []
        assert analysis.id.startswith("journal-")

    def test_analysis_with_full_data(self):
        analysis = JournalAnalysis.create("test transcript")
        analysis.intents = [
            JournalIntent.create(IntentType.ACTION_ITEM, "Call dentist"),
        ]
        analysis.cross_references = [
            CrossReference(source=CrossReferenceSource.REMINDERS, match="Dentist appt", relevance=0.8),
        ]
        analysis.action_plan = [
            ActionPlanItem.create(action="Create reminder to call dentist"),
        ]
        analysis.summary = "User needs to call the dentist."

        d = analysis.to_dict()
        assert len(d["intents"]) == 1
        assert len(d["cross_references"]) == 1
        assert len(d["action_plan"]) == 1
        assert d["summary"] == "User needs to call the dentist."

    def test_analysis_roundtrip(self):
        original = JournalAnalysis.create("test")
        original.intents = [JournalIntent.create(IntentType.NOTE, "Remember this")]
        original.summary = "A simple note."

        restored = JournalAnalysis.from_dict(original.to_dict())
        assert restored.transcript == "test"
        assert len(restored.intents) == 1
        assert restored.summary == "A simple note."


# ── Test: TranscriptQualityChecker ───────────────────────────────────


class TestTranscriptQualityChecker:
    """Tests for the LLM-powered quality checker."""

    @pytest.fixture
    def checker(self):
        return TranscriptQualityChecker()

    @pytest.mark.asyncio
    async def test_empty_transcript(self, checker):
        """Empty transcript should return clean report."""
        report = await checker.check("")
        assert report.overall_confidence == 1.0
        assert not report.needs_review
        assert report.flagged_words == []

    @pytest.mark.asyncio
    async def test_whitespace_transcript(self, checker):
        """Whitespace-only transcript should return clean report."""
        report = await checker.check("   ")
        assert report.overall_confidence == 1.0
        assert not report.needs_review

    @pytest.mark.asyncio
    async def test_clean_transcript(self, checker):
        """Clean transcript should be returned with high confidence."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "flagged_words": [],
            "overall_confidence": 0.95,
        })

        with patch("hestia.voice.quality.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(return_value=mock_response)
            report = await checker.check("I need to call the dentist tomorrow")

        assert report.overall_confidence == 0.95
        assert len(report.flagged_words) == 0
        assert not report.needs_review

    @pytest.mark.asyncio
    async def test_flagged_words_detected(self, checker):
        """Quality checker should return flagged words from LLM."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "flagged_words": [
                {
                    "word": "there",
                    "position": 10,
                    "confidence": 0.7,
                    "suggestions": ["their", "they're"],
                    "reason": "homophone",
                }
            ],
            "overall_confidence": 0.75,
        })

        with patch("hestia.voice.quality.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(return_value=mock_response)
            report = await checker.check("I went to there house yesterday")

        assert len(report.flagged_words) == 1
        assert report.flagged_words[0].word == "there"
        assert report.flagged_words[0].suggestions == ["their", "they're"]
        assert report.needs_review

    @pytest.mark.asyncio
    async def test_known_entities_in_prompt(self, checker):
        """Known entities should be included in the quality check prompt."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"flagged_words": [], "overall_confidence": 0.95})

        with patch("hestia.voice.quality.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(return_value=mock_response)
            await checker.check(
                "Meeting with Gavin tomorrow",
                known_entities=["Gavin", "Board Review", "Project Hestia"],
            )

            # Verify the prompt contains the entities
            call_args = mock_client.return_value.complete.call_args
            prompt = call_args.kwargs.get("prompt", call_args.args[0] if call_args.args else "")
            assert "Gavin" in prompt
            assert "Board Review" in prompt

    @pytest.mark.asyncio
    async def test_inference_failure_graceful(self, checker):
        """Quality checker should handle inference failures gracefully."""
        with patch("hestia.voice.quality.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(side_effect=Exception("Ollama down"))
            report = await checker.check("Some transcript text")

        assert report.transcript == "Some transcript text"
        assert report.overall_confidence == 0.7
        assert report.needs_review

    @pytest.mark.asyncio
    async def test_malformed_json_response(self, checker):
        """Quality checker should handle malformed LLM responses."""
        mock_response = MagicMock()
        mock_response.content = "This is not JSON at all"

        with patch("hestia.voice.quality.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(return_value=mock_response)
            report = await checker.check("Some transcript")

        assert report.overall_confidence == 0.7
        assert report.needs_review

    @pytest.mark.asyncio
    async def test_json_in_code_block(self, checker):
        """Quality checker should extract JSON from markdown code blocks."""
        mock_response = MagicMock()
        mock_response.content = '```json\n{"flagged_words": [], "overall_confidence": 0.92}\n```'

        with patch("hestia.voice.quality.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(return_value=mock_response)
            report = await checker.check("Hello world")

        assert report.overall_confidence == 0.92
        assert not report.needs_review

    @pytest.mark.asyncio
    async def test_out_of_bounds_positions_filtered(self, checker):
        """Flagged words with invalid positions should be filtered out."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "flagged_words": [
                {"word": "test", "position": 0, "confidence": 0.5},
                {"word": "bad", "position": 999, "confidence": 0.5},  # Out of bounds
            ],
            "overall_confidence": 0.8,
        })

        with patch("hestia.voice.quality.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(return_value=mock_response)
            report = await checker.check("test input")

        assert len(report.flagged_words) == 1
        assert report.flagged_words[0].word == "test"

    def test_build_context_section_empty(self, checker):
        """No entities should return empty context section."""
        assert checker._build_context_section(None) == ""
        assert checker._build_context_section([]) == ""

    def test_build_context_section_with_entities(self, checker):
        """Entities should be formatted into context section."""
        result = checker._build_context_section(["Alice", "Project X"])
        assert "Alice" in result
        assert "Project X" in result

    def test_review_threshold(self):
        """Reports below threshold should need review."""
        assert REVIEW_CONFIDENCE_THRESHOLD == 0.8


# ── Test: JournalAnalyzer ────────────────────────────────────────────


class TestJournalAnalyzer:
    """Tests for the multi-stage journal analyzer."""

    @pytest.fixture
    def analyzer(self):
        return JournalAnalyzer()

    @pytest.mark.asyncio
    async def test_full_pipeline_with_intents(self, analyzer):
        """Full pipeline should extract intents, cross-ref, and plan."""
        intent_response = MagicMock()
        intent_response.content = json.dumps({
            "intents": [
                {
                    "intent_type": "action_item",
                    "content": "Follow up with contractor",
                    "confidence": 0.9,
                    "entities": ["contractor"],
                }
            ]
        })

        plan_response = MagicMock()
        plan_response.content = json.dumps({
            "action_plan": [
                {
                    "action": "Create reminder to follow up with contractor",
                    "tool_call": "create_reminder",
                    "arguments": {"title": "Follow up contractor"},
                    "confidence": 0.85,
                }
            ],
            "summary": "User needs to follow up with contractor.",
        })

        with patch("hestia.voice.journal.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(
                side_effect=[intent_response, plan_response]
            )
            # Mock all cross-reference sources to avoid real calls
            with patch.object(analyzer, "_xref_calendar", return_value=[]), \
                 patch.object(analyzer, "_xref_reminders", return_value=[]), \
                 patch.object(analyzer, "_xref_mail", return_value=[]), \
                 patch.object(analyzer, "_xref_memory", return_value=[]):

                analysis = await analyzer.analyze("I need to follow up with the contractor about the kitchen")

        assert len(analysis.intents) == 1
        assert analysis.intents[0].intent_type == IntentType.ACTION_ITEM
        assert len(analysis.action_plan) == 1
        assert analysis.action_plan[0].tool_call == "create_reminder"
        assert analysis.summary == "User needs to follow up with contractor."

    @pytest.mark.asyncio
    async def test_no_intents_extracted(self, analyzer):
        """Empty transcript intents should short-circuit the pipeline."""
        mock_response = MagicMock()
        mock_response.content = json.dumps({"intents": []})

        with patch("hestia.voice.journal.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(return_value=mock_response)
            analysis = await analyzer.analyze("Just rambling about nothing specific")

        assert analysis.intents == []
        assert analysis.action_plan == []
        assert "No actionable intents" in analysis.summary

    @pytest.mark.asyncio
    async def test_intent_extraction_failure(self, analyzer):
        """Intent extraction failure should produce empty analysis."""
        with patch("hestia.voice.journal.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(
                side_effect=Exception("LLM timeout")
            )
            analysis = await analyzer.analyze("Some text")

        assert analysis.intents == []
        assert "error" in analysis.summary.lower()

    @pytest.mark.asyncio
    async def test_cross_reference_failures_graceful(self, analyzer):
        """Cross-reference failures should not crash the pipeline."""
        intent_response = MagicMock()
        intent_response.content = json.dumps({
            "intents": [
                {"intent_type": "action_item", "content": "Do something", "confidence": 0.8, "entities": []}
            ]
        })

        plan_response = MagicMock()
        plan_response.content = json.dumps({
            "action_plan": [{"action": "Do it", "confidence": 0.7}],
            "summary": "Action needed.",
        })

        with patch("hestia.voice.journal.get_inference_client") as mock_client:
            mock_client.return_value.complete = AsyncMock(
                side_effect=[intent_response, plan_response]
            )
            # All cross-ref sources raise exceptions
            with patch.object(analyzer, "_xref_calendar", side_effect=Exception("No CLI")), \
                 patch.object(analyzer, "_xref_reminders", side_effect=Exception("No CLI")), \
                 patch.object(analyzer, "_xref_mail", side_effect=Exception("No access")), \
                 patch.object(analyzer, "_xref_memory", side_effect=Exception("No DB")):

                analysis = await analyzer.analyze("Do something important")

        assert len(analysis.intents) == 1
        assert analysis.cross_references == []  # All failed gracefully
        assert len(analysis.action_plan) == 1

    @pytest.mark.asyncio
    async def test_cross_reference_calendar(self, analyzer):
        """Calendar cross-reference should return events."""
        mock_event = MagicMock()
        mock_event.id = "evt-1"
        mock_event.title = "Board Review"
        mock_event.start = datetime(2026, 2, 10, 14, 0, tzinfo=timezone.utc)
        mock_event.location = "Conference Room A"

        with patch("hestia.apple.calendar.CalendarClient") as MockCal:
            mock_cal = MockCal.return_value
            mock_cal.get_today_events = AsyncMock(return_value=[mock_event])
            mock_cal.get_upcoming_events = AsyncMock(return_value=[])

            refs = await analyzer._xref_calendar()

        assert len(refs) == 1
        assert refs[0].source == CrossReferenceSource.CALENDAR
        assert "Board Review" in refs[0].match

    @pytest.mark.asyncio
    async def test_cross_reference_reminders(self, analyzer):
        """Reminders cross-reference should return incomplete items."""
        mock_reminder = MagicMock()
        mock_reminder.id = "rem-1"
        mock_reminder.title = "Buy groceries"
        mock_reminder.due_date = None

        with patch("hestia.apple.reminders.RemindersClient") as MockRem:
            mock_rem = MockRem.return_value
            mock_rem.get_incomplete = AsyncMock(return_value=[mock_reminder])
            mock_rem.get_overdue = AsyncMock(return_value=[])

            refs = await analyzer._xref_reminders()

        assert len(refs) == 1
        assert refs[0].source == CrossReferenceSource.REMINDERS
        assert refs[0].match == "Buy groceries"

    @pytest.mark.asyncio
    async def test_cross_reference_mail(self, analyzer):
        """Mail cross-reference should match search terms in subjects."""
        mock_email = MagicMock()
        mock_email.message_id = "msg-1"
        mock_email.subject = "Re: Kitchen renovation quote"
        mock_email.sender = "contractor@example.com"
        mock_email.date = datetime(2026, 2, 7, 10, 0, tzinfo=timezone.utc)

        with patch("hestia.apple.mail.MailClient") as MockMail:
            mock_mail = MockMail.return_value
            mock_mail.__aenter__ = AsyncMock(return_value=mock_mail)
            mock_mail.__aexit__ = AsyncMock(return_value=False)
            mock_mail.get_recent_emails = AsyncMock(return_value=[mock_email])

            refs = await analyzer._xref_mail(["kitchen", "contractor"])

        assert len(refs) == 1
        assert refs[0].source == CrossReferenceSource.MAIL
        assert "Kitchen renovation" in refs[0].match

    @pytest.mark.asyncio
    async def test_cross_reference_memory(self, analyzer):
        """Memory cross-reference should search for terms."""
        mock_result = MagicMock()
        mock_result.chunk = MagicMock()
        mock_result.chunk.id = "chunk-1"
        mock_result.chunk.content = "Contractor mentioned kitchen will be done by March"
        mock_result.chunk.chunk_type = MagicMock(value="conversation")
        mock_result.relevance_score = 0.75

        with patch("hestia.memory.manager.get_memory_manager", new_callable=AsyncMock) as mock_get_mgr:
            mock_mgr = MagicMock()
            mock_get_mgr.return_value = mock_mgr
            mock_mgr.search = AsyncMock(return_value=[mock_result])

            refs = await analyzer._xref_memory(["kitchen", "contractor"])

        assert len(refs) >= 1
        assert refs[0].source == CrossReferenceSource.MEMORY

    def test_parse_intents_valid_json(self, analyzer):
        """Valid intent JSON should parse correctly."""
        response = json.dumps({
            "intents": [
                {"intent_type": "action_item", "content": "Do X", "confidence": 0.9, "entities": ["X"]},
                {"intent_type": "reminder", "content": "Remember Y", "confidence": 0.8, "entities": []},
            ]
        })
        intents = analyzer._parse_intents_response(response)
        assert len(intents) == 2
        assert intents[0].intent_type == IntentType.ACTION_ITEM
        assert intents[1].intent_type == IntentType.REMINDER

    def test_parse_intents_malformed_json(self, analyzer):
        """Malformed JSON should return empty list."""
        intents = analyzer._parse_intents_response("not json at all")
        assert intents == []

    def test_parse_intents_skips_invalid(self, analyzer):
        """Invalid intent entries should be skipped."""
        response = json.dumps({
            "intents": [
                {"intent_type": "action_item", "content": "Valid"},
                {"intent_type": "INVALID_TYPE", "content": "Bad"},  # Invalid enum
            ]
        })
        intents = analyzer._parse_intents_response(response)
        assert len(intents) == 1

    def test_parse_action_plan_valid(self, analyzer):
        """Valid action plan JSON should parse correctly."""
        response = json.dumps({
            "action_plan": [
                {"action": "Do X", "tool_call": "create_reminder", "arguments": {"title": "X"}, "confidence": 0.85},
            ],
            "summary": "One action needed.",
        })
        items, summary = analyzer._parse_action_plan_response(response, [])
        assert len(items) == 1
        assert items[0].tool_call == "create_reminder"
        assert summary == "One action needed."

    def test_parse_action_plan_malformed(self, analyzer):
        """Malformed action plan should return empty."""
        items, summary = analyzer._parse_action_plan_response("broken", [])
        assert items == []
        assert summary == ""

    def test_extract_json_raw(self, analyzer):
        """Raw JSON should be extracted as-is."""
        result = analyzer._extract_json('{"key": "value"}')
        assert result == '{"key": "value"}'

    def test_extract_json_code_block(self, analyzer):
        """JSON in code blocks should be extracted."""
        result = analyzer._extract_json('```json\n{"key": "value"}\n```')
        assert result == '{"key": "value"}'

    def test_extract_json_with_text(self, analyzer):
        """JSON embedded in text should be extracted."""
        result = analyzer._extract_json('Here is the result: {"key": "value"} end')
        assert '"key": "value"' in result
