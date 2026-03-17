"""
Chat request/response schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import ModeEnum, ResponseMetrics, ResponseError, ResponseTypeEnum


class ChatRequest(BaseModel):
    """Request to send a message to Hestia."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description="The message to send"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID (creates new if omitted)"
    )
    device_id: Optional[str] = Field(
        None,
        description="Device identifier"
    )
    force_local: bool = Field(
        False,
        description="Force local inference, bypass cloud routing"
    )
    mode: Optional[str] = Field(
        None,
        description="Persona mode (tia, mira, olly). Defaults to mode detection from message."
    )
    context_hints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context hints"
    )


class AgentBylineSchema(BaseModel):
    """Attribution for a specialist agent's contribution."""
    agent: str = Field(description="Agent identifier (artemis, apollo)")
    contribution: str = Field(description="Type of contribution (analysis, implementation)")
    summary: str = Field(description="One-line description of contribution")


class ChatResponse(BaseModel):
    """Response from Hestia."""
    request_id: str = Field(description="Unique request identifier")
    content: str = Field(description="Response content")
    response_type: ResponseTypeEnum = Field(description="Type of response")
    mode: ModeEnum = Field(description="Mode used for response")
    session_id: str = Field(description="Session identifier")
    timestamp: datetime = Field(description="Response timestamp")
    metrics: ResponseMetrics = Field(description="Response metrics")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Tool calls if response_type is tool_call"
    )
    error: Optional[ResponseError] = Field(
        None,
        description="Error details if response_type is error"
    )
    bylines: Optional[List[AgentBylineSchema]] = Field(
        None,
        description="Agent attribution bylines (present when specialists contributed)"
    )
