"""
WebSocket chat message schemas.

Defines the bidirectional protocol for streaming chat over WebSocket.
Client sends messages (auth, chat, tool approval, cancel, ping).
Server sends events (auth result, status, tokens, tool requests, done, error, pong).
"""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


# --- Enums ---

class WSClientMessageType(str, Enum):
    """Client-to-server message types."""
    AUTH = "auth"
    MESSAGE = "message"
    TOOL_APPROVAL = "tool_approval"
    CANCEL = "cancel"
    PING = "ping"


class WSServerMessageType(str, Enum):
    """Server-to-client message types."""
    AUTH_RESULT = "auth_result"
    STATUS = "status"
    TOKEN = "token"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    DONE = "done"
    ERROR = "error"
    PONG = "pong"


class WSPipelineStage(str, Enum):
    """Pipeline stages reported in status events."""
    VALIDATING = "validating"
    MEMORY = "memory"
    BUILDING_PROMPT = "building_prompt"
    COUNCIL = "council"
    INFERENCE = "inference"
    TOOLS = "tools"
    CACHE_HIT = "cache_hit"


class WSToolTier(str, Enum):
    """Tool trust tiers for approval."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    EXTERNAL = "external"


# --- Client Messages ---

class WSAuthMessage(BaseModel):
    """Client authentication message (must be first message after connect)."""
    type: WSClientMessageType = WSClientMessageType.AUTH
    token: str = Field(..., description="JWT device token")


class WSChatMessage(BaseModel):
    """Client chat message."""
    type: WSClientMessageType = WSClientMessageType.MESSAGE
    content: str = Field(..., min_length=1, max_length=32000, description="Message content")
    session_id: Optional[str] = Field(None, description="Session ID (auto-generated if omitted)")
    mode: Optional[str] = Field(None, description="Persona mode: tia, mira, olly")
    force_local: bool = Field(False, description="Force local inference")
    context_hints: Dict[str, Any] = Field(default_factory=dict, description="Additional context (git, CWD)")


class WSToolApprovalMessage(BaseModel):
    """Client response to a tool approval request."""
    type: WSClientMessageType = WSClientMessageType.TOOL_APPROVAL
    call_id: str = Field(..., description="Tool call ID from the tool_request event")
    approved: bool = Field(..., description="Whether to approve the tool execution")


class WSCancelMessage(BaseModel):
    """Client cancellation of current generation."""
    type: WSClientMessageType = WSClientMessageType.CANCEL


class WSPingMessage(BaseModel):
    """Client keepalive ping."""
    type: WSClientMessageType = WSClientMessageType.PING


# --- Server Messages ---

class WSAuthResultMessage(BaseModel):
    """Server authentication result."""
    type: WSServerMessageType = WSServerMessageType.AUTH_RESULT
    success: bool
    device_id: Optional[str] = None
    error: Optional[str] = None


class WSStatusMessage(BaseModel):
    """Server pipeline status update."""
    type: WSServerMessageType = WSServerMessageType.STATUS
    stage: str
    detail: Optional[str] = None


class WSTokenMessage(BaseModel):
    """Server streaming token."""
    type: WSServerMessageType = WSServerMessageType.TOKEN
    content: str
    request_id: str


class WSToolRequestMessage(BaseModel):
    """Server tool approval request (pauses stream until client responds)."""
    type: WSServerMessageType = WSServerMessageType.TOOL_REQUEST
    call_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    tier: str = Field(default="execute", description="Tool trust tier")


class WSToolResultMessage(BaseModel):
    """Server tool execution result."""
    type: WSServerMessageType = WSServerMessageType.TOOL_RESULT
    call_id: str
    status: str  # "success" | "error" | "denied"
    output: Optional[str] = None


class WSDoneMessage(BaseModel):
    """Server response completion."""
    type: WSServerMessageType = WSServerMessageType.DONE
    request_id: str
    metrics: Dict[str, Any] = Field(default_factory=dict)
    mode: str = "tia"


class WSErrorMessage(BaseModel):
    """Server error message."""
    type: WSServerMessageType = WSServerMessageType.ERROR
    code: str
    message: str


class WSPongMessage(BaseModel):
    """Server keepalive pong."""
    type: WSServerMessageType = WSServerMessageType.PONG
