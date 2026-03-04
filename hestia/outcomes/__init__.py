"""
Outcomes module — tracks chat response outcomes for learning cycle.

Captures both explicit user feedback (thumbs-up/down) and implicit
signals (response timing, follow-up patterns) to enable Hestia to
learn from interactions over time.
"""

from .models import OutcomeRecord, OutcomeFeedback, ImplicitSignal
from .manager import get_outcome_manager, close_outcome_manager

__all__ = [
    "OutcomeRecord",
    "OutcomeFeedback",
    "ImplicitSignal",
    "get_outcome_manager",
    "close_outcome_manager",
]
