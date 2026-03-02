"""
Common schemas: enums, error models, and shared response types.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class ResponseTypeEnum(str, Enum):
    """Type of response generated."""
    TEXT = "text"
    ERROR = "error"
    TOOL_CALL = "tool_call"
    CLARIFICATION = "clarification"


class ModeEnum(str, Enum):
    """Hestia persona modes."""
    TIA = "tia"
    MIRA = "mira"
    OLLY = "olly"


class HealthStatusEnum(str, Enum):
    """System health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ChunkTypeEnum(str, Enum):
    """Type of memory chunk."""
    CONVERSATION = "conversation"
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    RESEARCH = "research"
    SYSTEM = "system"


class MemoryScopeEnum(str, Enum):
    """Memory scope levels."""
    SESSION = "session"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class MemoryStatusEnum(str, Enum):
    """Memory chunk status."""
    ACTIVE = "active"
    STAGED = "staged"
    COMMITTED = "committed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


# ============================================================================
# Common Models
# ============================================================================

class ResponseMetrics(BaseModel):
    """Metrics for a response."""
    tokens_in: int = Field(description="Input tokens used")
    tokens_out: int = Field(description="Output tokens generated")
    duration_ms: float = Field(description="Total processing time in milliseconds")


class ResponseError(BaseModel):
    """Error information in a response."""
    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    request_id: Optional[str] = Field(None, description="Request ID if available")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Error timestamp"
    )
