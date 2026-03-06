"""
Apple cache data models.

Lightweight metadata entries cached from Apple ecosystem clients.
No body/content stored -- only enough metadata for fuzzy title resolution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class EntitySource(str, Enum):
    """Apple ecosystem data source."""
    NOTES = "notes"
    CALENDAR = "calendar"
    REMINDERS = "reminders"


@dataclass
class CachedEntity:
    """
    Cached metadata for an Apple ecosystem entity.

    Stores just enough data to resolve fuzzy title queries to native IDs
    without calling AppleScript/EventKit.

    ID format: "{source}:{native_id}" for global uniqueness.
    """
    id: str
    source: EntitySource
    native_id: str
    title: str
    container: Optional[str] = None  # folder (notes), calendar, list (reminders)
    modified_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API/debug output."""
        return {
            "id": self.id,
            "source": self.source.value,
            "native_id": self.native_id,
            "title": self.title,
            "container": self.container,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "metadata": self.metadata,
        }


@dataclass
class ResolvedMatch:
    """Result of a fuzzy resolution with confidence score."""
    entity: CachedEntity
    score: float  # 0.0 - 100.0 (rapidfuzz scale)
    match_method: str  # "fts5", "fuzzy", "exact"
