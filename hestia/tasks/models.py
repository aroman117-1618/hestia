"""
Data models for background task management.

Per ADR-021: Background Task Management
Per ADR-022: Governed Auto-Persistence for Background Tasks

Provides task lifecycle management with autonomy levels for
approval workflows and async execution tracking.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class TaskStatus(Enum):
    """Task lifecycle states."""
    PENDING = "pending"                    # Created, waiting to start
    IN_PROGRESS = "in_progress"            # Currently executing
    COMPLETED = "completed"                # Successfully finished
    FAILED = "failed"                      # Execution failed
    AWAITING_APPROVAL = "awaiting_approval"  # Needs user approval (autonomy level 1-2)
    CANCELLED = "cancelled"                # User cancelled


class TaskSource(Enum):
    """Source of task submission."""
    QUICK_CHAT = "quick_chat"        # From Quick Chat UI
    IOS_SHORTCUT = "ios_shortcut"    # From iOS Shortcuts
    CONVERSATION = "conversation"    # From main chat conversation


class AutonomyLevel(Enum):
    """
    Task autonomy levels per ADR-021.

    Higher levels = more autonomy (less approval needed).
    """
    EXPLICIT = 1      # Always require approval
    CONFIRM = 2       # Await approval for external actions
    NOTIFY = 3        # Execute then notify (default)
    SILENT = 4        # Execute silently (internal lookups)


@dataclass
class BackgroundTask:
    """
    Core task representation for background execution.

    Tracks full lifecycle from creation through completion,
    including approval workflows and retry handling.
    """
    id: str
    status: TaskStatus
    source: TaskSource
    input_summary: str
    created_at: datetime

    # Execution tracking
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Output
    output_summary: Optional[str] = None
    output_details: Optional[Dict[str, Any]] = None

    # Autonomy and approval
    autonomy_level: int = 3  # Default: NOTIFY
    escalated: bool = False
    escalation_reason: Optional[str] = None

    # Error handling
    error_message: Optional[str] = None
    retry_count: int = 0

    # Device tracking
    device_id: Optional[str] = None

    # Progress tracking (0.0 - 1.0)
    progress: float = 0.0

    @classmethod
    def create(
        cls,
        input_summary: str,
        source: TaskSource,
        autonomy_level: int = 3,
        device_id: Optional[str] = None,
    ) -> "BackgroundTask":
        """
        Factory method to create a new task.

        Args:
            input_summary: Description of what the task should do.
            source: Where the task originated from.
            autonomy_level: Approval requirement level (1-4).
            device_id: Device that submitted the task.

        Returns:
            New BackgroundTask in PENDING status.
        """
        # Determine initial status based on autonomy level
        if autonomy_level <= 2:
            initial_status = TaskStatus.AWAITING_APPROVAL
        else:
            initial_status = TaskStatus.PENDING

        return cls(
            id=f"task-{uuid4().hex[:12]}",
            status=initial_status,
            source=source,
            input_summary=input_summary,
            created_at=datetime.now(timezone.utc),
            autonomy_level=autonomy_level,
            device_id=device_id,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "status": self.status.value,
            "source": self.source.value,
            "input_summary": self.input_summary,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "output_summary": self.output_summary,
            "output_details": self.output_details,
            "autonomy_level": self.autonomy_level,
            "escalated": self.escalated,
            "escalation_reason": self.escalation_reason,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "device_id": self.device_id,
            "progress": self.progress,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BackgroundTask":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            status=TaskStatus(data["status"]),
            source=TaskSource(data["source"]),
            input_summary=data["input_summary"],
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            output_summary=data.get("output_summary"),
            output_details=data.get("output_details"),
            autonomy_level=data.get("autonomy_level", 3),
            escalated=data.get("escalated", False),
            escalation_reason=data.get("escalation_reason"),
            error_message=data.get("error_message"),
            retry_count=data.get("retry_count", 0),
            device_id=data.get("device_id"),
            progress=data.get("progress", 0.0),
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.status.value,
            self.source.value,
            self.input_summary,
            self.created_at.isoformat(),
            self.started_at.isoformat() if self.started_at else None,
            self.completed_at.isoformat() if self.completed_at else None,
            self.output_summary,
            json.dumps(self.output_details) if self.output_details else None,
            self.autonomy_level,
            self.escalated,
            self.escalation_reason,
            self.error_message,
            self.retry_count,
            self.device_id,
            self.progress,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "BackgroundTask":
        """Create from SQLite row (dict)."""
        output_details = None
        if row.get("output_details"):
            try:
                output_details = json.loads(row["output_details"])
            except (json.JSONDecodeError, TypeError):
                output_details = None

        return cls(
            id=row["id"],
            status=TaskStatus(row["status"]),
            source=TaskSource(row["source"]),
            input_summary=row["input_summary"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(row["started_at"]) if row.get("started_at") else None,
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
            output_summary=row.get("output_summary"),
            output_details=output_details,
            autonomy_level=row.get("autonomy_level", 3),
            escalated=bool(row.get("escalated", False)),
            escalation_reason=row.get("escalation_reason"),
            error_message=row.get("error_message"),
            retry_count=row.get("retry_count", 0),
            device_id=row.get("device_id"),
            progress=row.get("progress", 0.0),
        )

    def can_transition_to(self, new_status: TaskStatus) -> bool:
        """
        Check if transition to new status is valid.

        Valid transitions:
        - PENDING → IN_PROGRESS, CANCELLED
        - AWAITING_APPROVAL → IN_PROGRESS (after approval), CANCELLED
        - IN_PROGRESS → COMPLETED, FAILED
        - FAILED → PENDING (retry)
        - COMPLETED, CANCELLED → (terminal, no transitions)
        """
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
            TaskStatus.AWAITING_APPROVAL: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
            TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED},
            TaskStatus.FAILED: {TaskStatus.PENDING},  # For retry
            TaskStatus.COMPLETED: set(),  # Terminal
            TaskStatus.CANCELLED: set(),  # Terminal
        }
        return new_status in valid_transitions.get(self.status, set())

    def start(self) -> None:
        """Mark task as started."""
        if not self.can_transition_to(TaskStatus.IN_PROGRESS):
            raise ValueError(f"Cannot start task in {self.status.value} status")
        self.status = TaskStatus.IN_PROGRESS
        self.started_at = datetime.now(timezone.utc)

    def complete(self, output_summary: str, output_details: Optional[Dict[str, Any]] = None) -> None:
        """Mark task as completed."""
        if not self.can_transition_to(TaskStatus.COMPLETED):
            raise ValueError(f"Cannot complete task in {self.status.value} status")
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.output_summary = output_summary
        self.output_details = output_details
        self.progress = 1.0

    def fail(self, error_message: str) -> None:
        """Mark task as failed."""
        if not self.can_transition_to(TaskStatus.FAILED):
            raise ValueError(f"Cannot fail task in {self.status.value} status")
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.error_message = error_message

    def cancel(self) -> None:
        """Cancel the task."""
        if not self.can_transition_to(TaskStatus.CANCELLED):
            raise ValueError(f"Cannot cancel task in {self.status.value} status")
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)

    def prepare_retry(self) -> None:
        """Reset task for retry."""
        if not self.can_transition_to(TaskStatus.PENDING):
            raise ValueError(f"Cannot retry task in {self.status.value} status")
        self.status = TaskStatus.PENDING
        self.started_at = None
        self.completed_at = None
        self.error_message = None
        self.progress = 0.0
        self.retry_count += 1

    def approve(self) -> None:
        """Approve task for execution (from AWAITING_APPROVAL)."""
        if self.status != TaskStatus.AWAITING_APPROVAL:
            raise ValueError(f"Cannot approve task in {self.status.value} status")
        self.status = TaskStatus.PENDING

    def escalate(self, reason: str) -> None:
        """Escalate task to require approval."""
        self.escalated = True
        self.escalation_reason = reason
        if self.status == TaskStatus.PENDING:
            self.status = TaskStatus.AWAITING_APPROVAL

    def update_progress(self, progress: float) -> None:
        """Update task progress (0.0 - 1.0)."""
        self.progress = max(0.0, min(1.0, progress))

    @property
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state."""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.CANCELLED}

    @property
    def can_cancel(self) -> bool:
        """Check if task can be cancelled."""
        return self.can_transition_to(TaskStatus.CANCELLED)

    @property
    def can_retry(self) -> bool:
        """Check if task can be retried."""
        return self.status == TaskStatus.FAILED
