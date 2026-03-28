"""
Newsfeed data models.

Defines the unified newsfeed item type for the Command Center timeline.
Items are materialized from multiple sources (orders, memory, tasks, health,
calendar, system, trading, sentinel) into a single queryable cache.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class NewsfeedItemType(str, Enum):
    """Types of newsfeed items."""
    ORDER_EXECUTION = "order_execution"
    MEMORY_REVIEW = "memory_review"
    TASK_UPDATE = "task_update"
    HEALTH_INSIGHT = "health_insight"
    CALENDAR_EVENT = "calendar_event"
    SYSTEM_ALERT = "system_alert"
    TRADING_ALERT = "trading_alert"
    SECURITY_ALERT = "security_alert"


class NewsfeedItemSource(str, Enum):
    """Where a newsfeed item originates from."""
    ORDERS = "orders"
    MEMORY = "memory"
    TASKS = "tasks"
    HEALTH = "health"
    CALENDAR = "calendar"
    SYSTEM = "system"
    TRADING = "trading"
    SENTINEL = "sentinel"


class NewsfeedItemPriority(str, Enum):
    """Priority levels for newsfeed items."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class NewsfeedItem:
    """
    A single item in the unified newsfeed timeline.

    Items are materialized from source managers (orders, memory, tasks, etc.)
    and cached in SQLite for fast retrieval.
    """
    id: str
    item_type: NewsfeedItemType
    source: NewsfeedItemSource
    title: str
    body: Optional[str] = None
    timestamp: Optional[datetime] = None
    priority: NewsfeedItemPriority = NewsfeedItemPriority.NORMAL
    icon: Optional[str] = None
    color: Optional[str] = None
    action_type: Optional[str] = None
    action_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_read: bool = False
    is_dismissed: bool = False

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
            "icon": self.icon,
            "color": self.color,
            "action_type": self.action_type,
            "action_id": self.action_id,
            "metadata": self.metadata,
            "is_read": self.is_read,
            "is_dismissed": self.is_dismissed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NewsfeedItem":
        """Deserialize from dict."""
        timestamp = None
        if data.get("timestamp"):
            try:
                timestamp = datetime.fromisoformat(data["timestamp"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=data["id"],
            item_type=NewsfeedItemType(data["item_type"]),
            source=NewsfeedItemSource(data["source"]),
            title=data["title"],
            body=data.get("body"),
            timestamp=timestamp,
            priority=NewsfeedItemPriority(data.get("priority", "normal")),
            icon=data.get("icon"),
            color=data.get("color"),
            action_type=data.get("action_type"),
            action_id=data.get("action_id"),
            metadata=data.get("metadata", {}),
            is_read=data.get("is_read", False),
            is_dismissed=data.get("is_dismissed", False),
        )
