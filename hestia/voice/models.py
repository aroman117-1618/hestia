"""
Voice journaling models for Hestia.

Defines transcript segments, quality reports, journal intents,
cross-references, and action plan structures.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


@dataclass
class TranscriptSegment:
    """A segment of transcribed speech with timing and confidence."""
    text: str
    start_time: float  # seconds from start of recording
    end_time: float
    confidence: float  # 0.0 - 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptSegment":
        """Create from dictionary."""
        return cls(
            text=data["text"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            confidence=data["confidence"],
        )


@dataclass
class FlaggedWord:
    """A word flagged by the quality checker as potentially incorrect."""
    word: str
    position: int  # character offset in transcript
    confidence: float  # how confident the checker is this word is wrong (0.0 - 1.0)
    suggestions: List[str] = field(default_factory=list)
    reason: str = ""  # e.g. "homophone", "proper noun", "uncommon word"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "word": self.word,
            "position": self.position,
            "confidence": self.confidence,
            "suggestions": self.suggestions,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FlaggedWord":
        """Create from dictionary."""
        return cls(
            word=data["word"],
            position=data.get("position", 0),
            confidence=data.get("confidence", 0.5),
            suggestions=data.get("suggestions", []),
            reason=data.get("reason", ""),
        )


@dataclass
class QualityReport:
    """Result of quality checking a transcript."""
    transcript: str
    flagged_words: List[FlaggedWord] = field(default_factory=list)
    overall_confidence: float = 1.0  # 0.0 - 1.0
    needs_review: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "transcript": self.transcript,
            "flagged_words": [fw.to_dict() for fw in self.flagged_words],
            "overall_confidence": self.overall_confidence,
            "needs_review": self.needs_review,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QualityReport":
        """Create from dictionary."""
        return cls(
            transcript=data["transcript"],
            flagged_words=[FlaggedWord.from_dict(fw) for fw in data.get("flagged_words", [])],
            overall_confidence=data.get("overall_confidence", 1.0),
            needs_review=data.get("needs_review", False),
        )


class IntentType(Enum):
    """Types of intents extracted from journal entries."""
    ACTION_ITEM = "action_item"
    REMINDER = "reminder"
    NOTE = "note"
    DECISION = "decision"
    REFLECTION = "reflection"
    FOLLOW_UP = "follow_up"


@dataclass
class JournalIntent:
    """A structured intent extracted from a journal transcript."""
    id: str
    intent_type: IntentType
    content: str
    confidence: float  # 0.0 - 1.0
    entities: List[str] = field(default_factory=list)  # named entities referenced

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "intent_type": self.intent_type.value,
            "content": self.content,
            "confidence": self.confidence,
            "entities": self.entities,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JournalIntent":
        """Create from dictionary."""
        return cls(
            id=data.get("id", f"intent-{uuid4().hex[:8]}"),
            intent_type=IntentType(data["intent_type"]),
            content=data["content"],
            confidence=data.get("confidence", 0.5),
            entities=data.get("entities", []),
        )

    @classmethod
    def create(
        cls,
        intent_type: IntentType,
        content: str,
        confidence: float = 0.8,
        entities: Optional[List[str]] = None,
    ) -> "JournalIntent":
        """Factory method."""
        return cls(
            id=f"intent-{uuid4().hex[:8]}",
            intent_type=intent_type,
            content=content,
            confidence=confidence,
            entities=entities or [],
        )


class CrossReferenceSource(Enum):
    """Sources for cross-referencing journal intents."""
    CALENDAR = "calendar"
    MAIL = "mail"
    MEMORY = "memory"
    REMINDERS = "reminders"


@dataclass
class CrossReference:
    """A cross-reference match from an external source."""
    source: CrossReferenceSource
    match: str  # description of the matched item
    relevance: float  # 0.0 - 1.0
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "source": self.source.value,
            "match": self.match,
            "relevance": self.relevance,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrossReference":
        """Create from dictionary."""
        return cls(
            source=CrossReferenceSource(data["source"]),
            match=data["match"],
            relevance=data.get("relevance", 0.5),
            details=data.get("details", {}),
        )


@dataclass
class ActionPlanItem:
    """A single action item in the journal analysis action plan."""
    id: str
    action: str  # human-readable description
    tool_call: Optional[str] = None  # tool name if executable
    arguments: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.8
    intent_id: Optional[str] = None  # links back to JournalIntent

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "tool_call": self.tool_call,
            "arguments": self.arguments,
            "confidence": self.confidence,
            "intent_id": self.intent_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActionPlanItem":
        """Create from dictionary."""
        return cls(
            id=data.get("id", f"action-{uuid4().hex[:8]}"),
            action=data["action"],
            tool_call=data.get("tool_call"),
            arguments=data.get("arguments", {}),
            confidence=data.get("confidence", 0.8),
            intent_id=data.get("intent_id"),
        )

    @classmethod
    def create(
        cls,
        action: str,
        tool_call: Optional[str] = None,
        arguments: Optional[Dict[str, Any]] = None,
        confidence: float = 0.8,
        intent_id: Optional[str] = None,
    ) -> "ActionPlanItem":
        """Factory method."""
        return cls(
            id=f"action-{uuid4().hex[:8]}",
            action=action,
            tool_call=tool_call,
            arguments=arguments or {},
            confidence=confidence,
            intent_id=intent_id,
        )


@dataclass
class JournalAnalysis:
    """Complete analysis of a journal transcript."""
    id: str
    transcript: str
    intents: List[JournalIntent] = field(default_factory=list)
    cross_references: List[CrossReference] = field(default_factory=list)
    action_plan: List[ActionPlanItem] = field(default_factory=list)
    summary: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "transcript": self.transcript,
            "intents": [i.to_dict() for i in self.intents],
            "cross_references": [cr.to_dict() for cr in self.cross_references],
            "action_plan": [ap.to_dict() for ap in self.action_plan],
            "summary": self.summary,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JournalAnalysis":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            transcript=data["transcript"],
            intents=[JournalIntent.from_dict(i) for i in data.get("intents", [])],
            cross_references=[CrossReference.from_dict(cr) for cr in data.get("cross_references", [])],
            action_plan=[ActionPlanItem.from_dict(ap) for ap in data.get("action_plan", [])],
            summary=data.get("summary", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
        )

    @classmethod
    def create(cls, transcript: str) -> "JournalAnalysis":
        """Factory method for a new analysis."""
        return cls(
            id=f"journal-{uuid4().hex[:12]}",
            transcript=transcript,
        )
