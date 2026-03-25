"""
Authentication and device registration schemas.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DeviceRegisterRequest(BaseModel):
    """Request to register a device."""
    device_name: Optional[str] = Field(None, description="Device name")
    device_type: Optional[str] = Field(None, description="Device type (ios/macos)")
    device_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional device information"
    )


class DeviceRegisterResponse(BaseModel):
    """Response after device registration."""
    device_id: str = Field(description="Assigned device identifier")
    token: str = Field(description="JWT token for authentication")
    expires_at: datetime = Field(description="Token expiration time")


class InviteGenerateRequest(BaseModel):
    """Request to generate an invite token for QR code onboarding."""
    setup_secret: str = Field(
        ...,
        min_length=10,
        description="Setup secret from Keychain (generated on first boot)"
    )


class InviteGenerateResponse(BaseModel):
    """Response with invite token and QR data."""
    invite_token: str = Field(description="JWT invite token (10min expiry)")
    qr_payload: str = Field(description="JSON string for QR code encoding")
    expires_at: datetime = Field(description="Invite token expiration time")


class InviteRegisterRequest(BaseModel):
    """Request to register a device using an invite token."""
    invite_token: str = Field(..., description="Invite token from QR code")
    device_name: Optional[str] = Field(None, description="Device name")
    device_type: Optional[str] = Field(None, description="Device type (ios/macos)")


class InviteRegisterResponse(BaseModel):
    """Response after invite-based registration."""
    device_id: str = Field(description="Assigned device identifier")
    token: str = Field(description="JWT device token for authentication")
    expires_at: datetime = Field(description="Token expiration time")
    server_url: str = Field(description="Server base URL")


class DeviceListItem(BaseModel):
    """A registered device."""
    device_id: str = Field(description="Device identifier")
    device_name: str = Field(description="Device name")
    device_type: str = Field(description="Device type")
    registered_at: datetime = Field(description="Registration timestamp")
    last_seen_at: Optional[datetime] = Field(None, description="Last API call timestamp")
    revoked_at: Optional[datetime] = Field(None, description="Revocation timestamp (None if active)")
    is_active: bool = Field(True, description="Whether the device is currently active")


class DeviceListResponse(BaseModel):
    """Response listing registered devices."""
    devices: List[DeviceListItem] = Field(description="Registered devices")
    count: int = Field(description="Total device count")


class DeviceRevokeResponse(BaseModel):
    """Response for device revocation/unrevocation."""
    device_id: str = Field(description="Device identifier")
    revoked: bool = Field(description="Whether the device is now revoked")
    message: str = Field(description="Status message")


class AppleRegisterRequest(BaseModel):
    """Request to register a device using Sign in with Apple."""
    identity_token: str = Field(..., description="Apple identity JWT token")
    device_name: Optional[str] = Field(None, description="Device name")
    device_type: Optional[str] = Field(None, description="Device type (ios/macos)")


class AppleRegisterResponse(BaseModel):
    """Response after Apple-based registration."""
    device_id: str = Field(description="Assigned device identifier")
    token: str = Field(description="JWT device token for authentication")
    expires_at: str = Field(description="Token expiration time (ISO8601 string)")
    server_url: str = Field(description="Server base URL")
