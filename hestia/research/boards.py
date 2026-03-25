"""Research Canvas board persistence."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import uuid

from hestia.logging import get_logger

logger = get_logger()


@dataclass
class ResearchBoard:
    """A saved Research Canvas board with layout state."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Untitled Board"
    layout_json: str = "{}"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """Serialize to camelCase API dict."""
        return {
            "id": self.id,
            "name": self.name,
            "layoutJson": self.layout_json,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }

    @classmethod
    def from_row(cls, row: dict) -> ResearchBoard:
        """Create from a database row dict."""
        return cls(
            id=row["id"],
            name=row["name"],
            layout_json=row["layout_json"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
