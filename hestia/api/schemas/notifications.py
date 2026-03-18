"""
Notification relay schemas: bump requests and settings.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Bump Request Schemas ───────────────────────────────────────


class BumpCreateRequest(BaseModel):
    """Request to create a new bump notification."""
    title: str = Field(..., min_length=1, max_length=200)
    body: Optional[str] = Field(default=None, max_length=1000)
    priority: str = Field(default="medium", pattern="^(low|medium|high|urgent)$")
    actions: List[str] = Field(default=["approve", "deny"], max_length=5)
    context: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = Field(default=None, max_length=100)


class BumpCreateResponse(BaseModel):
    """Response after creating a bump."""
    callbackId: str
    status: str
    route: str
    reason: str
    delivered: bool


class BumpStatusResponse(BaseModel):
    """Current status of a bump request."""
    callbackId: str
    status: str
    route: Optional[str] = None
    responseAction: Optional[str] = None
    createdAt: str
    respondedAt: Optional[str] = None


class BumpRespondRequest(BaseModel):
    """Request to respond to a bump."""
    action: str = Field(..., min_length=1, max_length=50)


class BumpRespondResponse(BaseModel):
    """Response after responding to a bump."""
    callbackId: str
    status: str
    responseAction: Optional[str] = None
    error: Optional[str] = None


class BumpListItem(BaseModel):
    """A bump request in a list response."""
    id: str
    callbackId: str
    sessionId: Optional[str] = None
    title: str
    body: Optional[str] = None
    priority: str
    status: str
    route: Optional[str] = None
    responseAction: Optional[str] = None
    createdAt: str
    respondedAt: Optional[str] = None


class BumpListResponse(BaseModel):
    """List of bump requests."""
    bumps: List[BumpListItem]
    total: int


# ── Settings Schemas ───────────────────────────────────────────


class NotificationSettingsResponse(BaseModel):
    """Current notification settings."""
    userId: str
    idleThresholdSeconds: int
    rateLimitSeconds: int
    batchWindowSeconds: int
    bumpExpirySeconds: int
    quietHoursEnabled: bool
    quietHoursStart: str
    quietHoursEnd: str
    focusModeRespect: bool
    sessionCooldownSeconds: int


class NotificationSettingsUpdateRequest(BaseModel):
    """Request to update notification settings."""
    idleThresholdSeconds: Optional[int] = Field(default=None, ge=30, le=3600)
    rateLimitSeconds: Optional[int] = Field(default=None, ge=60, le=3600)
    batchWindowSeconds: Optional[int] = Field(default=None, ge=10, le=300)
    bumpExpirySeconds: Optional[int] = Field(default=None, ge=60, le=7200)
    quietHoursEnabled: Optional[bool] = None
    quietHoursStart: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    quietHoursEnd: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    focusModeRespect: Optional[bool] = None
    sessionCooldownSeconds: Optional[int] = Field(default=None, ge=0, le=3600)
