"""
Session schemas.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .common import ModeEnum


class SessionMessage(BaseModel):
    """A message in a session."""
    role: str = Field(description="Role (user/assistant)")
    content: str = Field(description="Message content")


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""
    mode: Optional[ModeEnum] = Field(None, description="Initial mode")
    device_id: Optional[str] = Field(None, description="Device identifier")


class SessionCreateResponse(BaseModel):
    """Response after creating a session."""
    session_id: str = Field(description="New session identifier")
    mode: ModeEnum = Field(description="Initial mode")
    created_at: datetime = Field(description="Creation timestamp")


class SessionHistoryResponse(BaseModel):
    """Session history response."""
    session_id: str = Field(description="Session identifier")
    mode: ModeEnum = Field(description="Current session mode")
    started_at: datetime = Field(description="When session started")
    last_activity: datetime = Field(description="Last activity timestamp")
    turn_count: int = Field(description="Number of conversation turns")
    messages: List[SessionMessage] = Field(description="Conversation messages")
