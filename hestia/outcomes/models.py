"""
Outcome tracking data models.

Captures response outcomes for the Learning Cycle — both explicit
user feedback and implicit behavioral signals.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class OutcomeFeedback(str, Enum):
    """Explicit user feedback on a response."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    CORRECTION = "correction"


class ImplicitSignal(str, Enum):
    """Auto-detected behavioral signals."""
    ACCEPTED = "accepted"           # User moved to different topic (positive)
    QUICK_FOLLOWUP = "quick_followup"  # Same topic, fast reply (likely negative)
    LONG_GAP = "long_gap"           # Long pause after response (positive)
    SESSION_END = "session_end"     # User ended session after response


@dataclass
class OutcomeRecord:
    """
    A single outcome record for a chat response.

    Created automatically after every chat response. Updated when
    the user provides explicit feedback or when implicit signals
    are detected from follow-up behavior.
    """
    id: str
    user_id: str
    device_id: Optional[str] = None
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    response_content: Optional[str] = None  # Truncated for storage
    response_type: Optional[str] = None     # text/tool_call/clarification
    duration_ms: Optional[int] = None
    feedback: Optional[str] = None          # OutcomeFeedback value
    feedback_note: Optional[str] = None
    implicit_signal: Optional[str] = None   # ImplicitSignal value
    elapsed_to_next_ms: Optional[int] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "session_id": self.session_id,
            "message_id": self.message_id,
            "response_content": self.response_content,
            "response_type": self.response_type,
            "duration_ms": self.duration_ms,
            "feedback": self.feedback,
            "feedback_note": self.feedback_note,
            "implicit_signal": self.implicit_signal,
            "elapsed_to_next_ms": self.elapsed_to_next_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutcomeRecord":
        """Deserialize from dict."""
        timestamp = datetime.now(timezone.utc)
        if data.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=data["id"],
            user_id=data["user_id"],
            device_id=data.get("device_id"),
            session_id=data.get("session_id"),
            message_id=data.get("message_id"),
            response_content=data.get("response_content"),
            response_type=data.get("response_type"),
            duration_ms=data.get("duration_ms"),
            feedback=data.get("feedback"),
            feedback_note=data.get("feedback_note"),
            implicit_signal=data.get("implicit_signal"),
            elapsed_to_next_ms=data.get("elapsed_to_next_ms"),
            timestamp=timestamp,
            metadata=data.get("metadata", {}),
        )
