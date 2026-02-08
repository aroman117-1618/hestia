"""
Voice journaling module for Hestia.

Provides on-device speech-to-text quality checking and
journal analysis with cross-referencing against calendar,
mail, memory, and reminders.

Architecture:
- iOS handles all speech-to-text via SpeechAnalyzer (on-device)
- Backend receives text transcript only (never audio)
- Quality checker flags uncertain words using LLM + known entities
- Journal analyzer extracts intents, cross-references, and action plans
"""

from .models import (
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
from .quality import TranscriptQualityChecker, get_quality_checker
from .journal import JournalAnalyzer, get_journal_analyzer

__all__ = [
    # Models
    "TranscriptSegment",
    "FlaggedWord",
    "QualityReport",
    "JournalIntent",
    "IntentType",
    "CrossReference",
    "CrossReferenceSource",
    "ActionPlanItem",
    "JournalAnalysis",
    # Quality
    "TranscriptQualityChecker",
    "get_quality_checker",
    # Journal
    "JournalAnalyzer",
    "get_journal_analyzer",
]
