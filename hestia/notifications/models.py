"""
Notification relay data models.

Defines bump requests, routing decisions, and notification settings
for the intelligent notification relay system.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class BumpStatus(Enum):
    """Status of a bump request lifecycle."""
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class NotificationRoute(Enum):
    """Where a notification was routed."""
    MACOS = "macos"          # macOS notification center
    APNS = "apns"            # iPhone push via APNs
    QUEUED = "queued"        # Queued for later delivery
    SUPPRESSED = "suppressed"  # Blocked by rate limit / quiet hours / focus


@dataclass
class BumpRequest:
    """A request for user attention from a Claude Code session."""
    id: str
    callback_id: str
    session_id: Optional[str]
    user_id: str
    title: str
    body: Optional[str]
    priority: str  # low, medium, high, urgent
    actions: List[str]
    context: Dict[str, Any]
    status: BumpStatus
    route: Optional[NotificationRoute]
    created_at: datetime
    responded_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    response_action: Optional[str] = None  # Which action was chosen

    @classmethod
    def create(
        cls,
        title: str,
        body: Optional[str] = None,
        priority: str = "medium",
        actions: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: str = "default",
    ) -> "BumpRequest":
        """Factory method for new bump requests."""
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            callback_id=str(uuid.uuid4()),
            session_id=session_id,
            user_id=user_id,
            title=title,
            body=body,
            priority=priority,
            actions=actions or ["approve", "deny"],
            context=context or {},
            status=BumpStatus.PENDING,
            route=None,
            created_at=now,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to API-friendly dict."""
        return {
            "id": self.id,
            "callbackId": self.callback_id,
            "sessionId": self.session_id,
            "userId": self.user_id,
            "title": self.title,
            "body": self.body,
            "priority": self.priority,
            "actions": self.actions,
            "context": self.context,
            "status": self.status.value,
            "route": self.route.value if self.route else None,
            "createdAt": self.created_at.isoformat(),
            "respondedAt": self.responded_at.isoformat() if self.responded_at else None,
            "expiredAt": self.expired_at.isoformat() if self.expired_at else None,
            "responseAction": self.response_action,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BumpRequest":
        """Deserialize from dict."""
        created_at = datetime.fromisoformat(data["createdAt"]) if data.get("createdAt") else datetime.now(timezone.utc)
        responded_at = datetime.fromisoformat(data["respondedAt"]) if data.get("respondedAt") else None
        expired_at = datetime.fromisoformat(data["expiredAt"]) if data.get("expiredAt") else None

        return cls(
            id=data["id"],
            callback_id=data["callbackId"],
            session_id=data.get("sessionId"),
            user_id=data.get("userId", "default"),
            title=data["title"],
            body=data.get("body"),
            priority=data.get("priority", "medium"),
            actions=data.get("actions", ["approve", "deny"]),
            context=data.get("context", {}),
            status=BumpStatus(data.get("status", "pending")),
            route=NotificationRoute(data["route"]) if data.get("route") else None,
            created_at=created_at,
            responded_at=responded_at,
            expired_at=expired_at,
            response_action=data.get("responseAction"),
        )


@dataclass
class NotificationSettings:
    """Per-user notification relay settings."""
    user_id: str = "default"
    idle_threshold_seconds: int = 120        # 2 min → escalate to iPhone
    rate_limit_seconds: int = 300            # 1 bump per 5 min per session
    batch_window_seconds: int = 60           # Consolidate rapid bumps
    bump_expiry_seconds: int = 900           # 15 min TTL on pending bumps
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = "22:00"         # 10 PM
    quiet_hours_end: str = "08:00"           # 8 AM
    focus_mode_respect: bool = True
    session_cooldown_seconds: int = 600      # After response, suppress 10 min

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to API-friendly dict."""
        return {
            "userId": self.user_id,
            "idleThresholdSeconds": self.idle_threshold_seconds,
            "rateLimitSeconds": self.rate_limit_seconds,
            "batchWindowSeconds": self.batch_window_seconds,
            "bumpExpirySeconds": self.bump_expiry_seconds,
            "quietHoursEnabled": self.quiet_hours_enabled,
            "quietHoursStart": self.quiet_hours_start,
            "quietHoursEnd": self.quiet_hours_end,
            "focusModeRespect": self.focus_mode_respect,
            "sessionCooldownSeconds": self.session_cooldown_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NotificationSettings":
        """Deserialize from dict."""
        return cls(
            user_id=data.get("userId", "default"),
            idle_threshold_seconds=data.get("idleThresholdSeconds", 120),
            rate_limit_seconds=data.get("rateLimitSeconds", 300),
            batch_window_seconds=data.get("batchWindowSeconds", 60),
            bump_expiry_seconds=data.get("bumpExpirySeconds", 900),
            quiet_hours_enabled=data.get("quietHoursEnabled", True),
            quiet_hours_start=data.get("quietHoursStart", "22:00"),
            quiet_hours_end=data.get("quietHoursEnd", "08:00"),
            focus_mode_respect=data.get("focusModeRespect", True),
            session_cooldown_seconds=data.get("sessionCooldownSeconds", 600),
        )
