"""
Order (scheduled prompt) schemas.
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class OrderFrequencyTypeEnum(str, Enum):
    """Order frequency types."""
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class OrderStatusEnum(str, Enum):
    """Order status values."""
    ACTIVE = "active"
    INACTIVE = "inactive"


class ExecutionStatusEnum(str, Enum):
    """Order execution status values."""
    SCHEDULED = "scheduled"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class MCPResourceEnum(str, Enum):
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


class OrderFrequency(BaseModel):
    """Order frequency configuration."""
    type: OrderFrequencyTypeEnum = Field(description="Frequency type")
    minutes: Optional[int] = Field(
        None,
        ge=15,
        description="Custom interval in minutes (required for 'custom' type)"
    )


class OrderExecutionSummary(BaseModel):
    """Summary of an order execution."""
    execution_id: str = Field(description="Execution identifier")
    timestamp: datetime = Field(description="Execution timestamp")
    status: ExecutionStatusEnum = Field(description="Execution status")


class OrderCreateRequest(BaseModel):
    """Request to create a new order."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Order name"
    )
    prompt: str = Field(
        ...,
        min_length=10,
        max_length=10000,
        description="Prompt to execute"
    )
    scheduled_time: str = Field(
        ...,
        description="Time of day to execute (HH:MM:SS format)"
    )
    frequency: OrderFrequency = Field(description="Execution frequency")
    resources: List[MCPResourceEnum] = Field(
        ...,
        min_length=1,
        description="MCP resources to use"
    )
    status: OrderStatusEnum = Field(
        default=OrderStatusEnum.ACTIVE,
        description="Initial order status"
    )


class OrderUpdateRequest(BaseModel):
    """Request to update an order (all fields optional)."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    prompt: Optional[str] = Field(None, min_length=10, max_length=10000)
    scheduled_time: Optional[str] = Field(None)
    frequency: Optional[OrderFrequency] = Field(None)
    resources: Optional[List[MCPResourceEnum]] = Field(None, min_length=1)
    status: Optional[OrderStatusEnum] = Field(None)


class OrderResponse(BaseModel):
    """Order information response."""
    order_id: str = Field(description="Order identifier")
    name: str = Field(description="Order name")
    prompt: str = Field(description="Prompt to execute")
    scheduled_time: str = Field(description="Scheduled time (HH:MM:SS)")
    frequency: OrderFrequency = Field(description="Execution frequency")
    resources: List[MCPResourceEnum] = Field(description="MCP resources")
    status: OrderStatusEnum = Field(description="Order status")
    next_execution: Optional[datetime] = Field(None, description="Next scheduled execution")
    last_execution: Optional[OrderExecutionSummary] = Field(None, description="Last execution")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class OrderListResponse(BaseModel):
    """Response listing orders."""
    orders: List[OrderResponse] = Field(description="Order list")
    total: int = Field(description="Total count")
    limit: int = Field(description="Results limit")
    offset: int = Field(description="Results offset")


class OrderDeleteResponse(BaseModel):
    """Response after deleting an order."""
    order_id: str = Field(description="Deleted order identifier")
    deleted: bool = Field(description="Whether deletion succeeded")
    message: str = Field(description="Status message")


class OrderExecutionDetail(BaseModel):
    """Detailed order execution record."""
    execution_id: str = Field(description="Execution identifier")
    timestamp: datetime = Field(description="Execution timestamp")
    status: ExecutionStatusEnum = Field(description="Execution status")
    hestia_read: Optional[str] = Field(None, description="Hestia's analysis/summary")
    full_response: Optional[str] = Field(None, description="Full response text")
    duration_ms: Optional[float] = Field(None, description="Execution duration")
    resources_used: List[MCPResourceEnum] = Field(
        default_factory=list,
        description="Resources used in execution"
    )


class OrderExecutionsResponse(BaseModel):
    """Response listing order executions."""
    order_id: str = Field(description="Order identifier")
    executions: List[OrderExecutionDetail] = Field(description="Execution list")
    total: int = Field(description="Total count")
    limit: int = Field(description="Results limit")
    offset: int = Field(description="Results offset")


class OrderExecuteResponse(BaseModel):
    """Response after manually triggering order execution."""
    order_id: str = Field(description="Order identifier")
    execution_id: str = Field(description="New execution identifier")
    status: ExecutionStatusEnum = Field(description="Execution status")
    message: str = Field(description="Status message")
