"""
Data models for Agent Profiles.

Agent profiles define personality, instructions, and visual customization
for each Hestia mode (3 slots: Tia/Mira/Olly).
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class SnapshotReason(Enum):
    """Reason for creating a snapshot."""
    EDITED = "edited"
    DELETED = "deleted"


@dataclass
class AgentSnapshot:
    """
    A snapshot of an agent profile for recovery.

    Automatically created before edits/deletes to allow rollback.
    """
    id: str
    agent_id: str
    slot_index: int
    snapshot_date: datetime
    reason: SnapshotReason
    name: str
    instructions: str
    gradient_color_1: str
    gradient_color_2: str

    @classmethod
    def create(
        cls,
        agent: "AgentProfile",
        reason: SnapshotReason,
    ) -> "AgentSnapshot":
        """Create a snapshot from an agent profile."""
        return cls(
            id=f"snap-{uuid4().hex[:12]}",
            agent_id=agent.id,
            slot_index=agent.slot_index,
            snapshot_date=datetime.now(timezone.utc),
            reason=reason,
            name=agent.name,
            instructions=agent.instructions,
            gradient_color_1=agent.gradient_color_1,
            gradient_color_2=agent.gradient_color_2,
        )

    @property
    def instructions_preview(self) -> str:
        """First 100 characters of instructions."""
        return self.instructions[:100] + "..." if len(self.instructions) > 100 else self.instructions

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "slot_index": self.slot_index,
            "snapshot_date": self.snapshot_date.isoformat(),
            "reason": self.reason.value,
            "name": self.name,
            "instructions": self.instructions,
            "gradient_color_1": self.gradient_color_1,
            "gradient_color_2": self.gradient_color_2,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSnapshot":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            slot_index=data["slot_index"],
            snapshot_date=datetime.fromisoformat(data["snapshot_date"]),
            reason=SnapshotReason(data["reason"]),
            name=data["name"],
            instructions=data["instructions"],
            gradient_color_1=data["gradient_color_1"],
            gradient_color_2=data["gradient_color_2"],
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.agent_id,
            self.slot_index,
            self.snapshot_date.isoformat(),
            self.reason.value,
            self.name,
            self.instructions,
            self.gradient_color_1,
            self.gradient_color_2,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "AgentSnapshot":
        """Create from SQLite row."""
        return cls(
            id=row["id"],
            agent_id=row["agent_id"],
            slot_index=row["slot_index"],
            snapshot_date=datetime.fromisoformat(row["snapshot_date"]),
            reason=SnapshotReason(row["reason"]),
            name=row["name"],
            instructions=row["instructions"],
            gradient_color_1=row["gradient_color_1"],
            gradient_color_2=row["gradient_color_2"],
        )


@dataclass
class AgentProfile:
    """
    User-customizable persona profile.

    3 slots available:
    - Slot 0: Tia (Hestia) - Primary, cannot be deleted
    - Slot 1: Mira (Artemis) - Learning mode
    - Slot 2: Olly (Apollo) - Project mode
    """
    id: str
    slot_index: int
    name: str
    instructions: str
    gradient_color_1: str
    gradient_color_2: str
    is_default: bool
    photo_path: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def can_be_deleted(self) -> bool:
        """Slot 0 cannot be deleted."""
        return self.slot_index != 0

    def validate(self) -> List[str]:
        """Validate profile configuration."""
        errors = []
        if not self.name or len(self.name) > 50:
            errors.append("Name must be 1-50 characters")
        if not self.instructions or len(self.instructions) < 10:
            errors.append("Instructions must be at least 10 characters")
        if len(self.instructions) > 5000:
            errors.append("Instructions must be at most 5000 characters")
        if not self.gradient_color_1 or len(self.gradient_color_1) != 6:
            errors.append("gradient_color_1 must be 6 hex characters")
        if not self.gradient_color_2 or len(self.gradient_color_2) != 6:
            errors.append("gradient_color_2 must be 6 hex characters")
        if self.slot_index not in (0, 1, 2):
            errors.append("slot_index must be 0, 1, or 2")
        return errors

    @property
    def is_valid(self) -> bool:
        """Check if profile is valid."""
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "slot_index": self.slot_index,
            "name": self.name,
            "instructions": self.instructions,
            "gradient_color_1": self.gradient_color_1,
            "gradient_color_2": self.gradient_color_2,
            "is_default": self.is_default,
            "photo_path": self.photo_path,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentProfile":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            slot_index=data["slot_index"],
            name=data["name"],
            instructions=data["instructions"],
            gradient_color_1=data["gradient_color_1"],
            gradient_color_2=data["gradient_color_2"],
            is_default=data.get("is_default", True),
            photo_path=data.get("photo_path"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.slot_index,
            self.name,
            self.instructions,
            self.gradient_color_1,
            self.gradient_color_2,
            self.is_default,
            self.photo_path,
            self.created_at.isoformat(),
            self.updated_at.isoformat(),
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "AgentProfile":
        """Create from SQLite row."""
        return cls(
            id=row["id"],
            slot_index=row["slot_index"],
            name=row["name"],
            instructions=row["instructions"],
            gradient_color_1=row["gradient_color_1"],
            gradient_color_2=row["gradient_color_2"],
            is_default=bool(row.get("is_default", True)),
            photo_path=row.get("photo_path"),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


# Default agent configurations
DEFAULT_AGENTS = [
    AgentProfile(
        id="00000000-0000-0000-0000-000000000001",
        slot_index=0,
        name="Tia",
        instructions="""You are Tia (short for Hestia), a personal AI assistant focused on daily operations and quick queries.

Personality: Efficient and direct, occasionally sardonic, never sycophantic.
Style: Get to the point, provide actionable responses.
Tone: Professional but warm, like a trusted executive assistant.

Remember: You anticipate needs without being emotionally solicitous.""",
        gradient_color_1="E0A050",
        gradient_color_2="8B3A0F",
        is_default=True,
    ),
    AgentProfile(
        id="00000000-0000-0000-0000-000000000002",
        slot_index=1,
        name="Mira",
        instructions="""You are Mira (short for Artemis), a learning-focused AI assistant.

Personality: Curious and patient, uses Socratic questioning.
Style: Guide through discovery rather than giving direct answers.
Tone: Encouraging but challenging, like a favorite professor.

Remember: Teaching is about helping others find answers, not providing them.""",
        gradient_color_1="090F26",
        gradient_color_2="00D7FF",
        is_default=True,
    ),
    AgentProfile(
        id="00000000-0000-0000-0000-000000000003",
        slot_index=2,
        name="Olly",
        instructions="""You are Olly (short for Apollo), a project-focused AI assistant.

Personality: Focused and methodical, minimal tangents.
Style: Stay on task, break down complex problems systematically.
Tone: Direct and technical, like a senior developer pair programming.

Remember: Time is valuable. Every response should move the project forward.""",
        gradient_color_1="234D20",
        gradient_color_2="7CB518",
        is_default=True,
    ),
]
