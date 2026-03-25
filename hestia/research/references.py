"""Entity reference models for cross-linking Research entities to other modules."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from hestia.logging import get_logger

logger = get_logger()


class ReferenceModule(str, Enum):
    """Hestia modules that can reference a Research entity."""

    WORKFLOW = "workflow"
    CHAT = "chat"
    COMMAND = "command"
    RESEARCH_CANVAS = "research_canvas"
    MEMORY = "memory"


@dataclass
class EntityReference:
    """A cross-module reference linking a Research entity to an item in another module."""

    entity_id: str
    module: ReferenceModule
    item_id: str
    context: str
    user_id: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entityId": self.entity_id,
            "module": self.module.value,
            "itemId": self.item_id,
            "context": self.context,
            "userId": self.user_id,
            "createdAt": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> EntityReference:
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            entity_id=data.get("entity_id", data.get("entityId", "")),
            module=ReferenceModule(data.get("module", "memory")),
            item_id=data.get("item_id", data.get("itemId", "")),
            context=data.get("context", ""),
            user_id=data.get("user_id", data.get("userId", "")),
            created_at=data.get(
                "created_at",
                data.get("createdAt", datetime.now(timezone.utc).isoformat()),
            ),
        )
