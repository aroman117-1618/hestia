"""
Explorer data models.

Defines the unified resource type that aggregates across mail, notes,
reminders, files, and Hestia drafts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class ResourceType(str, Enum):
    """Types of resources the Explorer can display."""
    DRAFT = "draft"
    MAIL = "mail"
    TASK = "task"
    NOTE = "note"
    FILE = "file"


class ResourceSource(str, Enum):
    """Where a resource originates from."""
    HESTIA = "hestia"
    MAIL = "mail"
    NOTES = "notes"
    REMINDERS = "reminders"
    FILES = "files"


class ResourceFlag(str, Enum):
    """Flags that can be applied to resources."""
    FLAGGED = "flagged"
    URGENT = "urgent"
    RECENT = "recent"
    PLAN = "plan"
    UNREAD = "unread"


@dataclass
class ExplorerResource:
    """
    Unified resource for the Explorer view.

    ID format is "{source}:{native_id}" for deduplication.
    """
    id: str
    type: ResourceType
    title: str
    source: ResourceSource
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    preview: Optional[str] = None
    flags: List[ResourceFlag] = field(default_factory=list)
    color: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Serialize for API response."""
        return {
            "id": self.id,
            "type": self.type.value,
            "title": self.title,
            "source": self.source.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "preview": self.preview,
            "flags": [f.value for f in self.flags],
            "color": self.color,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ExplorerResource":
        """Deserialize from dict (e.g. from database cache)."""
        created_at = None
        modified_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass
        if data.get("modified_at"):
            try:
                modified_at = datetime.fromisoformat(data["modified_at"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=data["id"],
            type=ResourceType(data["type"]),
            title=data["title"],
            source=ResourceSource(data["source"]),
            created_at=created_at,
            modified_at=modified_at,
            preview=data.get("preview"),
            flags=[ResourceFlag(f) for f in data.get("flags", [])],
            color=data.get("color"),
            metadata=data.get("metadata", {}),
        )
