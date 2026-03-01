"""
Investigate module — URL content analysis for Hestia.

Extracts and analyzes content from web articles, YouTube videos,
and other URL-based sources using a 3-tier extraction pipeline
and LLM-powered analysis.
"""

from .manager import get_investigate_manager, close_investigate_manager
from .models import (
    AnalysisDepth,
    ContentType,
    ExtractionResult,
    Investigation,
    InvestigationStatus,
)

__all__ = [
    "get_investigate_manager",
    "close_investigate_manager",
    "AnalysisDepth",
    "ContentType",
    "ExtractionResult",
    "Investigation",
    "InvestigationStatus",
]
