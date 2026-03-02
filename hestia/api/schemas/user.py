"""
User profile, settings, push token, and daily note schemas.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .common import ModeEnum


class ChatContextModel(BaseModel):
    """Workspace context for v2 chat API."""
    active_tab: Optional[str] = Field(None, description="Currently active tab (calendar, notes, files, etc.)")
    selected_text: Optional[str] = Field(None, description="User-selected text in canvas")
    attached_files: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Files attached via @ mention or drag-and-drop. Each has 'path' and optional 'content_preview'."
    )
    referenced_items: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Referenced items (calendar events, notes, etc.). Each has 'type', 'id', and 'summary' or 'title'."
    )
    panel_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Soft context from visible panels. Has 'visible_panels' list and optional metadata."
    )


class DailyNoteResponse(BaseModel):
    """A daily note entry."""
    date: str = Field(description="Note date (YYYY-MM-DD)")
    content: str = Field(description="Note content")
    agent_name: str = Field(description="Agent directory name")


class DailyNoteAppendRequest(BaseModel):
    """Request to append to a daily note."""
    content: str = Field(
        ...,
        min_length=1,
        description="Content to append"
    )


class QuietHours(BaseModel):
    """Quiet hours configuration."""
    enabled: bool = Field(default=False, description="Whether quiet hours are enabled")
    start: str = Field(default="22:00", description="Start time (HH:MM)")
    end: str = Field(default="07:00", description="End time (HH:MM)")


class PushNotificationSettings(BaseModel):
    """Push notification preferences."""
    enabled: bool = Field(default=True, description="Master enable/disable")
    order_executions: bool = Field(default=True, description="Notify on order completion")
    order_failures: bool = Field(default=True, description="Notify on order failure")
    proactive_briefings: bool = Field(default=True, description="Proactive intelligence alerts")
    quiet_hours: QuietHours = Field(
        default_factory=QuietHours,
        description="Quiet hours configuration"
    )


class UserProfileResponse(BaseModel):
    """User profile information."""
    user_id: str = Field(description="User identifier")
    name: str = Field(description="User display name")
    description: Optional[str] = Field(None, description="User description")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
    created_at: datetime = Field(description="Account creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class UserProfileUpdateRequest(BaseModel):
    """Request to update user profile."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class UserSettingsResponse(BaseModel):
    """User settings response."""
    push_notifications: PushNotificationSettings = Field(description="Push notification settings")
    default_mode: ModeEnum = Field(description="Default Hestia mode")
    auto_lock_timeout_minutes: int = Field(description="Auto-lock timeout")


class UserSettingsUpdateRequest(BaseModel):
    """Request to update user settings."""
    push_notifications: Optional[PushNotificationSettings] = Field(None)
    default_mode: Optional[ModeEnum] = Field(None)
    auto_lock_timeout_minutes: Optional[int] = Field(None, ge=1, le=60)


class UserSettingsUpdateResponse(BaseModel):
    """Response after updating settings."""
    updated: bool = Field(description="Whether update succeeded")
    settings: UserSettingsResponse = Field(description="Current settings")


class PushEnvironmentEnum(str, Enum):
    """APNS environment."""
    PRODUCTION = "production"
    SANDBOX = "sandbox"


class PushTokenRequest(BaseModel):
    """Request to register push token."""
    push_token: str = Field(
        ...,
        min_length=1,
        description="APNS device token"
    )
    device_id: str = Field(description="Device identifier")
    environment: PushEnvironmentEnum = Field(
        default=PushEnvironmentEnum.PRODUCTION,
        description="APNS environment"
    )


class PushTokenResponse(BaseModel):
    """Response after registering/unregistering push token."""
    registered: Optional[bool] = Field(None, description="For register")
    unregistered: Optional[bool] = Field(None, description="For unregister")
    device_id: Optional[str] = Field(None, description="Device identifier")
    message: str = Field(description="Status message")
