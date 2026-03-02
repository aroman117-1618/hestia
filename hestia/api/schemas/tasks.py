"""
Background task schemas (ADR-021/ADR-022).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatusEnum(str, Enum):
    """Background task status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_APPROVAL = "awaiting_approval"
    CANCELLED = "cancelled"


class TaskSourceEnum(str, Enum):
    """Background task source."""
    QUICK_CHAT = "quick_chat"
    IOS_SHORTCUT = "ios_shortcut"
    CONVERSATION = "conversation"


class TaskCreateRequest(BaseModel):
    """Request to create a background task."""
    input: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="Task input/description"
    )
    source: TaskSourceEnum = Field(
        default=TaskSourceEnum.CONVERSATION,
        description="Source of task submission"
    )
    autonomy_level: int = Field(
        default=3,
        ge=1,
        le=4,
        description="Autonomy level (1=explicit approval, 4=silent)"
    )


class TaskResponse(BaseModel):
    """Response with task information."""
    task_id: str = Field(description="Task identifier")
    status: TaskStatusEnum = Field(description="Current task status")
    source: TaskSourceEnum = Field(description="Task source")
    input_summary: str = Field(description="Task input summary")
    created_at: datetime = Field(description="Creation timestamp")
    started_at: Optional[datetime] = Field(None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    output_summary: Optional[str] = Field(None, description="Result summary")
    output_details: Optional[Dict[str, Any]] = Field(None, description="Detailed output")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="Progress 0.0-1.0")
    autonomy_level: int = Field(description="Autonomy level")
    escalated: bool = Field(False, description="Whether task was escalated")
    escalation_reason: Optional[str] = Field(None, description="Reason for escalation")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(0, description="Number of retry attempts")


class TaskListResponse(BaseModel):
    """Response listing background tasks."""
    tasks: List[TaskResponse] = Field(description="Task list")
    count: int = Field(description="Total count matching filters")
    limit: int = Field(description="Results limit")
    offset: int = Field(description="Results offset")


class TaskApprovalResponse(BaseModel):
    """Response after approving/cancelling a task."""
    task_id: str = Field(description="Task identifier")
    status: TaskStatusEnum = Field(description="New task status")
    message: str = Field(description="Status message")


class TaskRetryResponse(BaseModel):
    """Response after retrying a task."""
    task_id: str = Field(description="Task identifier")
    status: TaskStatusEnum = Field(description="New task status")
    retry_count: int = Field(description="Current retry count")
    message: str = Field(description="Status message")
