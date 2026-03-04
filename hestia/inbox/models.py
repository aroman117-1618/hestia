"""
Inbox data models.

Unified inbox item that can represent an email, reminder, calendar event,
or system notification from any aggregated source.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional


class InboxItemType(str, Enum):
    """Types of inbox items."""
    EMAIL = "email"
    REMINDER = "reminder"
    CALENDAR = "calendar"
    NOTIFICATION = "notification"


class InboxItemSource(str, Enum):
    """Where inbox items originate."""
    MAIL = "mail"
    REMINDERS = "reminders"
    CALENDAR = "calendar"
    PROACTIVE = "proactive"


class InboxItemPriority(str, Enum):
    """Priority levels for inbox items."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class InboxItem:
    """
    Unified inbox item from mail, reminders, calendar, or notifications.

    ID format: "{source}:{native_id}" for deduplication.
    """
    id: str
    item_type: InboxItemType
    source: InboxItemSource
    title: str
    body: Optional[str] = None
    timestamp: Optional[datetime] = None
    priority: InboxItemPriority = InboxItemPriority.NORMAL
    sender: Optional[str] = None
    sender_detail: Optional[str] = None
    has_attachments: bool = False
    icon: Optional[str] = None
    color: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_read: bool = False
    is_archived: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response."""
        return {
            "id": self.id,
            "item_type": self.item_type.value,
            "source": self.source.value,
            "title": self.title,
            "body": self.body,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "priority": self.priority.value,
            "sender": self.sender,
            "sender_detail": self.sender_detail,
            "has_attachments": self.has_attachments,
            "icon": self.icon,
            "color": self.color,
            "metadata": self.metadata,
            "is_read": self.is_read,
            "is_archived": self.is_archived,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InboxItem":
        """Deserialize from dict."""
        timestamp = None
        if data.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=data["id"],
            item_type=InboxItemType(data["item_type"]),
            source=InboxItemSource(data["source"]),
            title=data["title"],
            body=data.get("body"),
            timestamp=timestamp,
            priority=InboxItemPriority(data.get("priority", "normal")),
            sender=data.get("sender"),
            sender_detail=data.get("sender_detail"),
            has_attachments=data.get("has_attachments", False),
            icon=data.get("icon"),
            color=data.get("color"),
            metadata=data.get("metadata", {}),
            is_read=data.get("is_read", False),
            is_archived=data.get("is_archived", False),
        )
