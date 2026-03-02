"""
Voice journaling schemas (WS2).
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VoiceFlaggedWord(BaseModel):
    """A word flagged by the quality checker as potentially incorrect."""
    word: str = Field(description="The flagged word as it appears in the transcript")
    position: int = Field(description="Character offset in the transcript (0-indexed)")
    confidence: float = Field(description="Confidence this word is incorrect (0.0-1.0)")
    suggestions: List[str] = Field(default_factory=list, description="Suggested corrections")
    reason: str = Field(default="", description="Reason for flagging (e.g. homophone, proper noun)")


class VoiceQualityCheckRequest(BaseModel):
    """Request to quality-check a voice transcript."""
    transcript: str = Field(description="The transcript text to check", min_length=1, max_length=10000)
    known_entities: Optional[List[str]] = Field(
        default=None,
        description="Known entity names (people, events, projects) to help catch misheard proper nouns",
    )


class VoiceQualityCheckResponse(BaseModel):
    """Response from quality checking a transcript."""
    transcript: str = Field(description="The original transcript")
    flagged_words: List[VoiceFlaggedWord] = Field(default_factory=list, description="Words flagged as potentially incorrect")
    overall_confidence: float = Field(description="Overall confidence in transcript accuracy (0.0-1.0)")
    needs_review: bool = Field(description="Whether the transcript should be reviewed by the user")


class VoiceIntentType(str, Enum):
    """Types of intents extracted from journal entries."""
    ACTION_ITEM = "action_item"
    REMINDER = "reminder"
    NOTE = "note"
    DECISION = "decision"
    REFLECTION = "reflection"
    FOLLOW_UP = "follow_up"


class VoiceJournalIntent(BaseModel):
    """A structured intent extracted from a journal transcript."""
    id: str = Field(description="Unique intent identifier")
    intent_type: VoiceIntentType = Field(description="Type of intent")
    content: str = Field(description="Concise description of the intent")
    confidence: float = Field(description="Confidence in intent extraction (0.0-1.0)")
    entities: List[str] = Field(default_factory=list, description="Named entities referenced")


class VoiceCrossReferenceSource(str, Enum):
    """Sources for cross-referencing journal intents."""
    CALENDAR = "calendar"
    MAIL = "mail"
    MEMORY = "memory"
    REMINDERS = "reminders"


class VoiceCrossReference(BaseModel):
    """A cross-reference match from an external source."""
    source: VoiceCrossReferenceSource = Field(description="Data source")
    match: str = Field(description="Description of the matched item")
    relevance: float = Field(description="Relevance score (0.0-1.0)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Source-specific details")


class VoiceActionPlanItem(BaseModel):
    """A single action item in the journal analysis action plan."""
    id: str = Field(description="Unique action identifier")
    action: str = Field(description="Human-readable action description")
    tool_call: Optional[str] = Field(default=None, description="Tool name if executable")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    confidence: float = Field(description="Confidence in action plan item (0.0-1.0)")
    intent_id: Optional[str] = Field(default=None, description="Links back to JournalIntent")


class VoiceJournalAnalyzeRequest(BaseModel):
    """Request to analyze a confirmed journal transcript."""
    transcript: str = Field(description="The confirmed transcript text", min_length=1, max_length=10000)
    mode: Optional[str] = Field(default="tia", description="Current Hestia mode (tia/mira/olly)")


class VoiceJournalAnalyzeResponse(BaseModel):
    """Response from journal analysis."""
    id: str = Field(description="Unique analysis identifier")
    transcript: str = Field(description="The analyzed transcript")
    intents: List[VoiceJournalIntent] = Field(default_factory=list, description="Extracted intents")
    cross_references: List[VoiceCrossReference] = Field(default_factory=list, description="Cross-reference matches")
    action_plan: List[VoiceActionPlanItem] = Field(default_factory=list, description="Generated action plan")
    summary: str = Field(default="", description="Brief summary of the analysis")
    timestamp: str = Field(description="ISO 8601 timestamp of the analysis")
