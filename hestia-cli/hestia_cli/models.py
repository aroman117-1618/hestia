"""
WebSocket protocol models for the CLI client.

Mirrors the server-side schemas in hestia/api/schemas/ws_chat.py
but as lightweight Pydantic models for client-side use.
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class ServerEventType(str, Enum):
    """Server-to-client event types."""
    AUTH_RESULT = "auth_result"
    STATUS = "status"
    TOKEN = "token"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    DONE = "done"
    ERROR = "error"
    PONG = "pong"


class PipelineStage(str, Enum):
    """Pipeline stages for status display."""
    VALIDATING = "validating"
    MEMORY = "memory"
    BUILDING_PROMPT = "building_prompt"
    COUNCIL = "council"
    INFERENCE = "inference"
    TOOLS = "tools"
    CACHE_HIT = "cache_hit"


STAGE_LABELS: Dict[str, str] = {
    "validating": "Validating",
    "memory": "Searching memory",
    "building_prompt": "Building prompt",
    "council": "Classifying intent",
    "inference": "Generating",
    "tools": "Executing tools",
    "cache_hit": "Cache hit",
}


class AuthResult(BaseModel):
    """Parsed auth result from server."""
    success: bool
    device_id: Optional[str] = None
    error: Optional[str] = None
    trust_tiers: Optional[Dict[str, str]] = None


class ToolRequest(BaseModel):
    """Tool approval request from server."""
    call_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    tier: str = "execute"


class DoneMetrics(BaseModel):
    """Metrics from a completed response."""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: float = 0.0
    model: Optional[str] = None
    cached: bool = False
    cancelled: bool = False
