"""Tests for LLM-backed chunk type classification and content quality gates."""

import pytest
from datetime import datetime, timezone
from typing import Optional

from hestia.memory.models import (
    ChunkMetadata,
    ChunkTags,
    ChunkType,
    ConversationChunk,
    MemoryScope,
    MemoryStatus,
)
from hestia.memory.tagger import AutoTagger


def _make_chunk(
    content: str = "Some test content that is long enough to classify properly",
    chunk_type: ChunkType = ChunkType.CONVERSATION,
    source: Optional[str] = None,
    folder: Optional[str] = None,
) -> ConversationChunk:
    """Helper to build a ConversationChunk for testing."""
    custom = {}
    if folder is not None:
        custom["folder"] = folder
    return ConversationChunk(
        id="chunk-test123",
        session_id="session-test",
        timestamp=datetime.now(timezone.utc),
        content=content,
        chunk_type=chunk_type,
        scope=MemoryScope.SESSION,
        status=MemoryStatus.ACTIVE,
        tags=ChunkTags(custom=custom),
        metadata=ChunkMetadata(source=source),
    )


class TestShouldClassify:
    """Tests for AutoTagger._should_classify() content quality gate."""

    def setup_method(self) -> None:
        self.tagger = AutoTagger()

    def test_conversation_chunk_passes(self) -> None:
        chunk = _make_chunk(chunk_type=ChunkType.CONVERSATION)
        assert self.tagger._should_classify(chunk) is True

    def test_observation_chunk_passes(self) -> None:
        chunk = _make_chunk(chunk_type=ChunkType.OBSERVATION)
        assert self.tagger._should_classify(chunk) is True

    def test_source_structured_blocked(self) -> None:
        chunk = _make_chunk(chunk_type=ChunkType.SOURCE_STRUCTURED)
        assert self.tagger._should_classify(chunk) is False

    def test_decision_chunk_blocked(self) -> None:
        """Already-classified DECISION chunks should not be reclassified."""
        chunk = _make_chunk(chunk_type=ChunkType.DECISION)
        assert self.tagger._should_classify(chunk) is False

    def test_fact_chunk_blocked(self) -> None:
        chunk = _make_chunk(chunk_type=ChunkType.FACT)
        assert self.tagger._should_classify(chunk) is False

    def test_short_content_blocked(self) -> None:
        chunk = _make_chunk(content="too short")
        assert self.tagger._should_classify(chunk) is False

    def test_promo_email_blocked(self) -> None:
        chunk = _make_chunk(
            content="Great deals this week! Click here to unsubscribe from our mailing list.",
            source="mail",
        )
        assert self.tagger._should_classify(chunk) is False

    def test_real_email_passes(self) -> None:
        chunk = _make_chunk(
            content="Hey Andrew, the deployment finished successfully. All tests passing on the Mac Mini.",
            source="mail",
        )
        assert self.tagger._should_classify(chunk) is True

    def test_notes_intelligence_folder_passes(self) -> None:
        chunk = _make_chunk(
            content="Research findings on memory graph diversity approaches and tradeoffs.",
            source="notes",
            folder="Intelligence/Research",
        )
        assert self.tagger._should_classify(chunk) is True

    def test_notes_wrong_folder_blocked(self) -> None:
        chunk = _make_chunk(
            content="Some random note content that is long enough to pass length check.",
            source="notes",
            folder="Shopping Lists",
        )
        assert self.tagger._should_classify(chunk) is False

    def test_notes_no_folder_blocked(self) -> None:
        chunk = _make_chunk(
            content="A note with no folder metadata set on the chunk tags at all.",
            source="notes",
        )
        assert self.tagger._should_classify(chunk) is False

    def test_no_source_passes(self) -> None:
        """Chunks without a source (e.g., direct conversation) should pass."""
        chunk = _make_chunk(source=None)
        assert self.tagger._should_classify(chunk) is True

    def test_promo_signal_case_insensitive(self) -> None:
        chunk = _make_chunk(
            content="CLICK HERE TO UNSUBSCRIBE FROM OUR NEWSLETTER AND MANAGE SUBSCRIPTIONS",
            source="mail",
        )
        assert self.tagger._should_classify(chunk) is False


class TestClassifyChunkType:
    """Tests for AutoTagger.classify_chunk_type()."""

    def setup_method(self) -> None:
        self.tagger = AutoTagger()
        self.metadata = ChunkMetadata()

    def test_todo_prefix_returns_action_item(self) -> None:
        result = self.tagger.classify_chunk_type(
            "TODO: update the deployment script", self.metadata
        )
        assert result == ChunkType.ACTION_ITEM

    def test_todo_dash_prefix(self) -> None:
        result = self.tagger.classify_chunk_type(
            "todo - fix the memory leak in consolidator", self.metadata
        )
        assert result == ChunkType.ACTION_ITEM

    def test_action_item_prefix(self) -> None:
        result = self.tagger.classify_chunk_type(
            "action item: schedule the security review", self.metadata
        )
        assert result == ChunkType.ACTION_ITEM

    def test_task_prefix(self) -> None:
        result = self.tagger.classify_chunk_type(
            "task: run the backfill script on prod", self.metadata
        )
        assert result == ChunkType.ACTION_ITEM

    def test_checkbox_prefix(self) -> None:
        result = self.tagger.classify_chunk_type(
            "- [ ] Wire up the new endpoint", self.metadata
        )
        assert result == ChunkType.ACTION_ITEM

    def test_llm_decision_high_confidence(self) -> None:
        result = self.tagger.classify_chunk_type(
            "We decided to go with SQLite over Postgres for the trading module.",
            self.metadata,
            llm_suggested_type="decision",
            llm_type_confidence=0.9,
        )
        assert result == ChunkType.DECISION

    def test_llm_decision_low_confidence_stays_conversation(self) -> None:
        result = self.tagger.classify_chunk_type(
            "Maybe we should consider using Postgres instead.",
            self.metadata,
            llm_suggested_type="decision",
            llm_type_confidence=0.5,
        )
        assert result == ChunkType.CONVERSATION

    def test_llm_preference_high_confidence(self) -> None:
        result = self.tagger.classify_chunk_type(
            "I always prefer dark mode in all my development tools.",
            self.metadata,
            llm_suggested_type="preference",
            llm_type_confidence=0.85,
        )
        assert result == ChunkType.PREFERENCE

    def test_llm_research_high_confidence(self) -> None:
        result = self.tagger.classify_chunk_type(
            "After comparing VectorBT and Backtrader, VectorBT is 10x faster.",
            self.metadata,
            llm_suggested_type="research",
            llm_type_confidence=0.8,
        )
        assert result == ChunkType.RESEARCH

    def test_confidence_threshold_boundary_passes(self) -> None:
        """Exactly 0.7 should pass the threshold."""
        result = self.tagger.classify_chunk_type(
            "I decided to use Quarter-Kelly for position sizing.",
            self.metadata,
            llm_suggested_type="decision",
            llm_type_confidence=0.7,
        )
        assert result == ChunkType.DECISION

    def test_confidence_threshold_boundary_fails(self) -> None:
        """Just below 0.7 should not pass."""
        result = self.tagger.classify_chunk_type(
            "I think maybe we should use Quarter-Kelly.",
            self.metadata,
            llm_suggested_type="decision",
            llm_type_confidence=0.69,
        )
        assert result == ChunkType.CONVERSATION

    def test_non_promotable_type_ignored(self) -> None:
        """conversation is not in PROMOTABLE_TYPES, so it stays CONVERSATION."""
        result = self.tagger.classify_chunk_type(
            "Just chatting about the weather today.",
            self.metadata,
            llm_suggested_type="conversation",
            llm_type_confidence=0.95,
        )
        assert result == ChunkType.CONVERSATION

    def test_invalid_llm_type_falls_through(self) -> None:
        """Invalid type string should fall through to CONVERSATION."""
        result = self.tagger.classify_chunk_type(
            "Some content here.",
            self.metadata,
            llm_suggested_type="nonexistent_type",
            llm_type_confidence=0.9,
        )
        assert result == ChunkType.CONVERSATION

    def test_heuristic_beats_llm(self) -> None:
        """Action item prefix should win over LLM suggesting something else."""
        result = self.tagger.classify_chunk_type(
            "TODO: this is actually a research task according to the LLM",
            self.metadata,
            llm_suggested_type="research",
            llm_type_confidence=0.95,
        )
        assert result == ChunkType.ACTION_ITEM

    def test_no_llm_signals_returns_conversation(self) -> None:
        result = self.tagger.classify_chunk_type(
            "Just a regular message without any special markers.",
            self.metadata,
        )
        assert result == ChunkType.CONVERSATION

    def test_llm_action_item_high_confidence(self) -> None:
        result = self.tagger.classify_chunk_type(
            "Need to update the deployment script before Friday.",
            self.metadata,
            llm_suggested_type="action_item",
            llm_type_confidence=0.88,
        )
        assert result == ChunkType.ACTION_ITEM


class TestChunkMetadataClassificationFields:
    """Tests for the new suggested_type and type_confidence fields on ChunkMetadata."""

    def test_defaults(self) -> None:
        meta = ChunkMetadata()
        assert meta.suggested_type is None
        assert meta.type_confidence == 0.0

    def test_to_dict_includes_fields(self) -> None:
        meta = ChunkMetadata(suggested_type="decision", type_confidence=0.85)
        d = meta.to_dict()
        assert d["suggested_type"] == "decision"
        assert d["type_confidence"] == 0.85

    def test_from_dict_reads_fields(self) -> None:
        data = {
            "suggested_type": "preference",
            "type_confidence": 0.72,
        }
        meta = ChunkMetadata.from_dict(data)
        assert meta.suggested_type == "preference"
        assert meta.type_confidence == 0.72

    def test_from_dict_defaults_when_missing(self) -> None:
        meta = ChunkMetadata.from_dict({})
        assert meta.suggested_type is None
        assert meta.type_confidence == 0.0

    def test_round_trip(self) -> None:
        original = ChunkMetadata(
            has_code=True,
            suggested_type="research",
            type_confidence=0.91,
            source="notes",
        )
        restored = ChunkMetadata.from_dict(original.to_dict())
        assert restored.suggested_type == original.suggested_type
        assert restored.type_confidence == original.type_confidence
        assert restored.has_code == original.has_code
        assert restored.source == original.source


class TestParseTagResponseClassification:
    """Tests that _parse_tag_response extracts suggested_type and type_confidence."""

    def setup_method(self) -> None:
        self.tagger = AutoTagger()

    def test_parses_suggested_type(self) -> None:
        response = '{"topics": [], "entities": [], "people": [], "has_code": false, "has_decision": true, "has_action_item": false, "sentiment": "neutral", "status": ["active"], "suggested_type": "decision", "type_confidence": 0.9}'
        _, metadata = self.tagger._parse_tag_response(response)
        assert metadata.suggested_type == "decision"
        assert metadata.type_confidence == 0.9

    def test_missing_classification_fields_default(self) -> None:
        response = '{"topics": ["testing"], "entities": [], "people": [], "has_code": false, "has_decision": false, "has_action_item": false, "sentiment": "neutral", "status": ["active"]}'
        _, metadata = self.tagger._parse_tag_response(response)
        assert metadata.suggested_type is None
        assert metadata.type_confidence == 0.0
