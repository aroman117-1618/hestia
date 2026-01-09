"""
Data models for the Orders system.

Orders are scheduled, recurring prompts that Hestia executes autonomously.
Like standing orders - they run on schedule without user intervention.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4


class FrequencyType(Enum):
    """Order frequency types."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class OrderStatus(Enum):
    """Order status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class ExecutionStatus(Enum):
    """Order execution status values."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class MCPResource(Enum):
    """Available MCP resources for orders."""
    FIRECRAWL = "firecrawl"
    GITHUB = "github"
    APPLE_NEWS = "apple_news"
    FIDELITY = "fidelity"
    CALENDAR = "calendar"
    EMAIL = "email"
    REMINDER = "reminder"
    NOTE = "note"
    SHORTCUT = "shortcut"


@dataclass
class OrderFrequency:
    """
    Order frequency configuration.

    Attributes:
        type: Frequency type (once, daily, weekly, monthly, custom).
        minutes: Custom interval in minutes (only for custom type, min 15).
    """
    type: FrequencyType
    minutes: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "minutes": self.minutes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderFrequency":
        """Create from dictionary."""
        return cls(
            type=FrequencyType(data["type"]),
            minutes=data.get("minutes"),
        )

    def validate(self) -> List[str]:
        """Validate frequency configuration."""
        errors = []
        if self.type == FrequencyType.CUSTOM:
            if self.minutes is None:
                errors.append("Custom frequency requires minutes value")
            elif self.minutes < 15:
                errors.append("Custom frequency must be at least 15 minutes")
        return errors


@dataclass
class OrderExecution:
    """
    Record of an order execution.

    Attributes:
        id: Unique execution identifier.
        order_id: Parent order ID.
        timestamp: When execution started.
        status: Execution status.
        completed_at: When execution completed.
        duration_ms: Execution duration in milliseconds.
        hestia_read: Hestia's analysis/summary (shown to user).
        full_response: Full response text.
        resources_used: Which resources were actually used.
        error_message: Error details if failed.
    """
    id: str
    order_id: str
    timestamp: datetime
    status: ExecutionStatus
    completed_at: Optional[datetime] = None
    duration_ms: Optional[float] = None
    hestia_read: Optional[str] = None
    full_response: Optional[str] = None
    resources_used: List[MCPResource] = field(default_factory=list)
    error_message: Optional[str] = None

    @classmethod
    def create(cls, order_id: str) -> "OrderExecution":
        """Factory method to create a new execution."""
        return cls(
            id=f"exec-{uuid4().hex[:12]}",
            order_id=order_id,
            timestamp=datetime.now(timezone.utc),
            status=ExecutionStatus.RUNNING,
        )

    def complete(
        self,
        hestia_read: Optional[str] = None,
        full_response: Optional[str] = None,
        resources_used: Optional[List[MCPResource]] = None,
    ) -> None:
        """Mark execution as completed successfully."""
        self.status = ExecutionStatus.SUCCESS
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = (self.completed_at - self.timestamp).total_seconds() * 1000
        self.hestia_read = hestia_read
        self.full_response = full_response
        if resources_used:
            self.resources_used = resources_used

    def fail(self, error_message: str) -> None:
        """Mark execution as failed."""
        self.status = ExecutionStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.duration_ms = (self.completed_at - self.timestamp).total_seconds() * 1000
        self.error_message = error_message

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_ms": self.duration_ms,
            "hestia_read": self.hestia_read,
            "full_response": self.full_response,
            "resources_used": [r.value for r in self.resources_used],
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderExecution":
        """Create from dictionary."""
        resources_used = [
            MCPResource(r) for r in data.get("resources_used", [])
        ]
        return cls(
            id=data["id"],
            order_id=data["order_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=ExecutionStatus(data["status"]),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            duration_ms=data.get("duration_ms"),
            hestia_read=data.get("hestia_read"),
            full_response=data.get("full_response"),
            resources_used=resources_used,
            error_message=data.get("error_message"),
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.order_id,
            self.timestamp.isoformat(),
            self.status.value,
            self.completed_at.isoformat() if self.completed_at else None,
            self.duration_ms,
            self.hestia_read,
            self.full_response,
            json.dumps([r.value for r in self.resources_used]),
            self.error_message,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "OrderExecution":
        """Create from SQLite row (dict)."""
        resources_used = []
        if row.get("resources_used"):
            try:
                resources_used = [MCPResource(r) for r in json.loads(row["resources_used"])]
            except (json.JSONDecodeError, ValueError):
                pass

        return cls(
            id=row["id"],
            order_id=row["order_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            status=ExecutionStatus(row["status"]),
            completed_at=datetime.fromisoformat(row["completed_at"]) if row.get("completed_at") else None,
            duration_ms=row.get("duration_ms"),
            hestia_read=row.get("hestia_read"),
            full_response=row.get("full_response"),
            resources_used=resources_used,
            error_message=row.get("error_message"),
        )


@dataclass
class Order:
    """
    A scheduled recurring prompt (standing order).

    Attributes:
        id: Unique order identifier.
        name: Human-readable name.
        prompt: The prompt to execute.
        scheduled_time: Time of day to execute (HH:MM:SS).
        frequency: Execution frequency configuration.
        resources: MCP resources to use.
        status: Order status (active/inactive).
        created_at: Creation timestamp.
        updated_at: Last update timestamp.
        last_execution: Most recent execution summary.
        execution_count: Total executions.
        success_count: Successful executions.
    """
    id: str
    name: str
    prompt: str
    scheduled_time: time
    frequency: OrderFrequency
    resources: Set[MCPResource]
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    last_execution: Optional[OrderExecution] = None
    execution_count: int = 0
    success_count: int = 0

    @classmethod
    def create(
        cls,
        name: str,
        prompt: str,
        scheduled_time: time,
        frequency: OrderFrequency,
        resources: Set[MCPResource],
        status: OrderStatus = OrderStatus.ACTIVE,
    ) -> "Order":
        """Factory method to create a new order."""
        now = datetime.now(timezone.utc)
        return cls(
            id=f"order-{uuid4().hex[:12]}",
            name=name,
            prompt=prompt,
            scheduled_time=scheduled_time,
            frequency=frequency,
            resources=resources,
            status=status,
            created_at=now,
            updated_at=now,
        )

    @property
    def success_rate(self) -> float:
        """Calculate success rate (0.0 - 1.0)."""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count

    def validate(self) -> List[str]:
        """Validate order configuration."""
        errors = []
        if not self.name or len(self.name) > 100:
            errors.append("Name must be 1-100 characters")
        if not self.prompt or len(self.prompt) < 10:
            errors.append("Prompt must be at least 10 characters")
        if len(self.prompt) > 10000:
            errors.append("Prompt must be at most 10000 characters")
        if not self.resources:
            errors.append("At least one resource is required")
        errors.extend(self.frequency.validate())
        return errors

    @property
    def is_valid(self) -> bool:
        """Check if order is valid."""
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "scheduled_time": self.scheduled_time.isoformat(),
            "frequency": self.frequency.to_dict(),
            "resources": [r.value for r in self.resources],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_execution": self.last_execution.to_dict() if self.last_execution else None,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Order":
        """Create from dictionary."""
        resources = {MCPResource(r) for r in data.get("resources", [])}
        last_execution = None
        if data.get("last_execution"):
            last_execution = OrderExecution.from_dict(data["last_execution"])

        return cls(
            id=data["id"],
            name=data["name"],
            prompt=data["prompt"],
            scheduled_time=time.fromisoformat(data["scheduled_time"]),
            frequency=OrderFrequency.from_dict(data["frequency"]),
            resources=resources,
            status=OrderStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            last_execution=last_execution,
            execution_count=data.get("execution_count", 0),
            success_count=data.get("success_count", 0),
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.name,
            self.prompt,
            self.scheduled_time.isoformat(),
            self.frequency.type.value,
            self.frequency.minutes,
            json.dumps([r.value for r in self.resources]),
            self.status.value,
            self.created_at.isoformat(),
            self.updated_at.isoformat(),
            self.execution_count,
            self.success_count,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "Order":
        """Create from SQLite row (dict)."""
        resources = set()
        if row.get("resources"):
            try:
                resources = {MCPResource(r) for r in json.loads(row["resources"])}
            except (json.JSONDecodeError, ValueError):
                pass

        return cls(
            id=row["id"],
            name=row["name"],
            prompt=row["prompt"],
            scheduled_time=time.fromisoformat(row["scheduled_time"]),
            frequency=OrderFrequency(
                type=FrequencyType(row["frequency_type"]),
                minutes=row.get("frequency_minutes"),
            ),
            resources=resources,
            status=OrderStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_execution=None,  # Loaded separately
            execution_count=row.get("execution_count", 0),
            success_count=row.get("success_count", 0),
        )
