"""
Pydantic schemas for Hestia REST API.

Request/response models for all API endpoints.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class ResponseTypeEnum(str, Enum):
    """Type of response generated."""
    TEXT = "text"
    ERROR = "error"
    TOOL_CALL = "tool_call"
    CLARIFICATION = "clarification"


class ModeEnum(str, Enum):
    """Hestia persona modes."""
    TIA = "tia"
    MIRA = "mira"
    OLLY = "olly"


class HealthStatusEnum(str, Enum):
    """System health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ChunkTypeEnum(str, Enum):
    """Type of memory chunk."""
    CONVERSATION = "conversation"
    FACT = "fact"
    PREFERENCE = "preference"
    DECISION = "decision"
    ACTION_ITEM = "action_item"
    RESEARCH = "research"
    SYSTEM = "system"


class MemoryScopeEnum(str, Enum):
    """Memory scope levels."""
    SESSION = "session"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class MemoryStatusEnum(str, Enum):
    """Memory chunk status."""
    ACTIVE = "active"
    STAGED = "staged"
    COMMITTED = "committed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


# ============================================================================
# Common Models
# ============================================================================

class ResponseMetrics(BaseModel):
    """Metrics for a response."""
    tokens_in: int = Field(description="Input tokens used")
    tokens_out: int = Field(description="Output tokens generated")
    duration_ms: float = Field(description="Total processing time in milliseconds")


class ResponseError(BaseModel):
    """Error information in a response."""
    code: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")


# ============================================================================
# Chat Schemas
# ============================================================================

class ChatRequest(BaseModel):
    """Request to send a message to Hestia."""
    message: str = Field(
        ...,
        min_length=1,
        max_length=32000,
        description="The message to send"
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID (creates new if omitted)"
    )
    device_id: Optional[str] = Field(
        None,
        description="Device identifier"
    )
    context_hints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context hints"
    )


class ChatResponse(BaseModel):
    """Response from Hestia."""
    request_id: str = Field(description="Unique request identifier")
    content: str = Field(description="Response content")
    response_type: ResponseTypeEnum = Field(description="Type of response")
    mode: ModeEnum = Field(description="Mode used for response")
    session_id: str = Field(description="Session identifier")
    timestamp: datetime = Field(description="Response timestamp")
    metrics: ResponseMetrics = Field(description="Response metrics")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Tool calls if response_type is tool_call"
    )
    error: Optional[ResponseError] = Field(
        None,
        description="Error details if response_type is error"
    )


# ============================================================================
# Mode Schemas
# ============================================================================

class PersonaInfo(BaseModel):
    """Information about a persona."""
    mode: ModeEnum = Field(description="Mode identifier")
    name: str = Field(description="Short name (Tia, Mira, Olly)")
    full_name: str = Field(description="Full name (Hestia, Artemis, Apollo)")
    description: str = Field(description="Mode description")
    traits: List[str] = Field(description="Personality traits")


class ModeResponse(BaseModel):
    """Current mode information."""
    current: PersonaInfo = Field(description="Current active persona")
    available: List[ModeEnum] = Field(description="Available modes")


class ModeSwitchRequest(BaseModel):
    """Request to switch mode."""
    mode: ModeEnum = Field(description="Mode to switch to")


class ModeSwitchResponse(BaseModel):
    """Response after switching mode."""
    previous_mode: ModeEnum = Field(description="Previous mode")
    current_mode: ModeEnum = Field(description="New current mode")
    persona: PersonaInfo = Field(description="New persona information")


# ============================================================================
# Memory Schemas
# ============================================================================

class ChunkTags(BaseModel):
    """Tag-based metadata for memory chunks."""
    topics: List[str] = Field(default_factory=list, description="Topic tags")
    entities: List[str] = Field(default_factory=list, description="Entity tags")
    people: List[str] = Field(default_factory=list, description="People mentioned")
    mode: Optional[str] = Field(None, description="Mode when created")
    phase: Optional[str] = Field(None, description="Project phase")
    status: List[str] = Field(default_factory=list, description="Status tags")
    custom: Dict[str, str] = Field(default_factory=dict, description="Custom tags")


class ChunkMetadata(BaseModel):
    """Additional metadata for memory chunks."""
    has_code: bool = Field(False, description="Contains code snippets")
    has_decision: bool = Field(False, description="Contains a decision")
    has_action_item: bool = Field(False, description="Contains action items")
    sentiment: Optional[str] = Field(None, description="Sentiment analysis")
    confidence: float = Field(1.0, description="Confidence score 0.0-1.0")
    token_count: int = Field(0, description="Token count of content")
    source: Optional[str] = Field(None, description="Source of the chunk")


class MemoryChunk(BaseModel):
    """A memory chunk."""
    chunk_id: str = Field(description="Unique chunk identifier")
    session_id: str = Field(description="Session this chunk belongs to")
    timestamp: datetime = Field(description="When the chunk was created")
    content: str = Field(description="The chunk content")
    chunk_type: ChunkTypeEnum = Field(description="Type of chunk")
    scope: MemoryScopeEnum = Field(description="Memory scope")
    status: MemoryStatusEnum = Field(description="Chunk status")
    tags: ChunkTags = Field(description="Tag metadata")
    metadata: ChunkMetadata = Field(description="Additional metadata")


class StagedMemoryItem(BaseModel):
    """A staged memory update awaiting review."""
    chunk_id: str = Field(description="Chunk identifier")
    content: str = Field(description="Chunk content")
    chunk_type: ChunkTypeEnum = Field(description="Type of chunk")
    tags: ChunkTags = Field(description="Tag metadata")
    metadata: ChunkMetadata = Field(description="Additional metadata")
    staged_at: datetime = Field(description="When it was staged")


class StagedMemoryResponse(BaseModel):
    """Response listing staged memory updates."""
    pending: List[StagedMemoryItem] = Field(description="Pending reviews")
    count: int = Field(description="Total count")


class MemoryApprovalRequest(BaseModel):
    """Request to approve a staged memory update."""
    reviewer_notes: Optional[str] = Field(
        None,
        description="Optional notes from reviewer"
    )


class MemoryApprovalResponse(BaseModel):
    """Response after approving/rejecting memory."""
    chunk_id: str = Field(description="Chunk identifier")
    status: str = Field(description="New status (committed/rejected)")
    scope: Optional[str] = Field(None, description="New scope if committed")


class MemorySearchResult(BaseModel):
    """A single search result."""
    chunk_id: str = Field(description="Chunk identifier")
    content: str = Field(description="Chunk content")
    relevance_score: float = Field(description="Relevance score 0.0-1.0")
    match_type: str = Field(description="How it matched (semantic/tag/etc)")
    decay_adjusted: bool = Field(False, description="Whether temporal decay was applied to the score")
    timestamp: datetime = Field(description="When created")
    tags: ChunkTags = Field(description="Tag metadata")


class MemorySearchResponse(BaseModel):
    """Response from memory search."""
    results: List[MemorySearchResult] = Field(description="Search results")
    count: int = Field(description="Number of results")


# ============================================================================
# Session Schemas
# ============================================================================

class SessionMessage(BaseModel):
    """A message in a session."""
    role: str = Field(description="Role (user/assistant)")
    content: str = Field(description="Message content")


class SessionCreateRequest(BaseModel):
    """Request to create a new session."""
    mode: Optional[ModeEnum] = Field(None, description="Initial mode")
    device_id: Optional[str] = Field(None, description="Device identifier")


class SessionCreateResponse(BaseModel):
    """Response after creating a session."""
    session_id: str = Field(description="New session identifier")
    mode: ModeEnum = Field(description="Initial mode")
    created_at: datetime = Field(description="Creation timestamp")


class SessionHistoryResponse(BaseModel):
    """Session history response."""
    session_id: str = Field(description="Session identifier")
    mode: ModeEnum = Field(description="Current session mode")
    started_at: datetime = Field(description="When session started")
    last_activity: datetime = Field(description="Last activity timestamp")
    turn_count: int = Field(description="Number of conversation turns")
    messages: List[SessionMessage] = Field(description="Conversation messages")


# ============================================================================
# Health Schemas
# ============================================================================

class InferenceHealth(BaseModel):
    """Inference component health."""
    status: HealthStatusEnum = Field(description="Component status")
    ollama_available: Optional[bool] = Field(None, description="Ollama availability")
    primary_model_available: Optional[bool] = Field(None, description="Primary model available")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class MemoryHealth(BaseModel):
    """Memory component health."""
    status: HealthStatusEnum = Field(description="Component status")
    vector_count: Optional[int] = Field(None, description="Number of vectors stored")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class StateMachineHealth(BaseModel):
    """State machine component health."""
    status: HealthStatusEnum = Field(description="Component status")
    active_tasks: int = Field(0, description="Number of active tasks")
    state_summary: Optional[Dict[str, int]] = Field(None, description="State counts")


class ToolsHealth(BaseModel):
    """Tools component health."""
    status: HealthStatusEnum = Field(description="Component status")
    registered_tools: int = Field(0, description="Number of registered tools")
    tool_names: Optional[List[str]] = Field(None, description="List of tool names")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class HealthComponents(BaseModel):
    """Health status of all components."""
    inference: InferenceHealth = Field(description="Inference status")
    memory: MemoryHealth = Field(description="Memory status")
    state_machine: StateMachineHealth = Field(description="State machine status")
    tools: ToolsHealth = Field(description="Tools status")


class HealthResponse(BaseModel):
    """System health response."""
    status: HealthStatusEnum = Field(description="Overall system status")
    timestamp: datetime = Field(description="Health check timestamp")
    components: HealthComponents = Field(description="Component health details")


# ============================================================================
# Tool Schemas
# ============================================================================

class ToolParameter(BaseModel):
    """A tool parameter definition."""
    type: str = Field(description="Parameter type")
    description: str = Field(description="Parameter description")
    required: bool = Field(description="Whether parameter is required")
    default: Optional[Any] = Field(None, description="Default value")
    enum_values: Optional[List[str]] = Field(None, description="Allowed values")


class ToolDefinition(BaseModel):
    """A tool definition."""
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    category: str = Field(description="Tool category")
    requires_approval: bool = Field(description="Whether tool requires approval")
    parameters: Dict[str, ToolParameter] = Field(
        default_factory=dict,
        description="Tool parameters"
    )


class ToolsResponse(BaseModel):
    """Response listing available tools."""
    tools: List[ToolDefinition] = Field(description="Available tools")
    count: int = Field(description="Total tool count")


# ============================================================================
# Auth Schemas
# ============================================================================

class DeviceRegisterRequest(BaseModel):
    """Request to register a device."""
    device_name: Optional[str] = Field(None, description="Device name")
    device_type: Optional[str] = Field(None, description="Device type (ios/macos)")
    device_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional device information"
    )


class DeviceRegisterResponse(BaseModel):
    """Response after device registration."""
    device_id: str = Field(description="Assigned device identifier")
    token: str = Field(description="JWT token for authentication")
    expires_at: datetime = Field(description="Token expiration time")


# ============================================================================
# Error Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str = Field(description="Error type")
    message: str = Field(description="Error message")
    request_id: Optional[str] = Field(None, description="Request ID if available")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Error timestamp"
    )


# ============================================================================
# Task Schemas (Phase 4.5 - ADR-021/ADR-022)
# ============================================================================

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


# ============================================================================
# Order Schemas (Phase 6b - Orders API)
# ============================================================================

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


# ============================================================================
# Agent Profile Schemas (Phase 6b - Agent Profiles API)
# ============================================================================

class SnapshotReasonEnum(str, Enum):
    """Reason for creating a snapshot."""
    EDITED = "edited"
    DELETED = "deleted"


class AgentSnapshotSummary(BaseModel):
    """Summary of an agent profile snapshot."""
    snapshot_id: str = Field(description="Snapshot identifier")
    snapshot_date: datetime = Field(description="When snapshot was created")
    reason: SnapshotReasonEnum = Field(description="Reason for snapshot")


class AgentProfileResponse(BaseModel):
    """Agent profile information."""
    agent_id: str = Field(description="Agent identifier")
    slot_index: int = Field(ge=0, le=2, description="Slot index (0-2)")
    name: str = Field(description="Agent name")
    instructions: str = Field(description="Agent instructions/persona")
    gradient_color_1: str = Field(description="Primary gradient color (hex)")
    gradient_color_2: str = Field(description="Secondary gradient color (hex)")
    is_default: bool = Field(description="Whether using default config")
    can_be_deleted: bool = Field(description="Whether can be deleted")
    photo_url: Optional[str] = Field(None, description="Photo URL if set")
    snapshots: Optional[List[AgentSnapshotSummary]] = Field(
        None,
        description="Available snapshots (only in detail view)"
    )
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class AgentListResponse(BaseModel):
    """Response listing agent profiles."""
    agents: List[AgentProfileResponse] = Field(description="Agent list")
    count: int = Field(description="Total count")


class AgentUpdateRequest(BaseModel):
    """Request to update an agent profile."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Agent name"
    )
    instructions: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Agent instructions/persona"
    )
    gradient_color_1: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Primary gradient color (hex without #)"
    )
    gradient_color_2: str = Field(
        ...,
        min_length=6,
        max_length=6,
        description="Secondary gradient color (hex without #)"
    )


class AgentDeleteResponse(BaseModel):
    """Response after deleting/resetting an agent profile."""
    slot_index: int = Field(description="Slot index")
    reset_to_default: bool = Field(description="Whether reset to default")
    default_name: str = Field(description="Default agent name")
    snapshot_created: bool = Field(description="Whether snapshot was created")
    message: str = Field(description="Status message")


class AgentPhotoResponse(BaseModel):
    """Response after photo upload/delete."""
    slot_index: int = Field(description="Slot index")
    photo_url: Optional[str] = Field(None, description="Photo URL or null")
    message: str = Field(description="Status message")


class AgentSnapshotDetail(BaseModel):
    """Detailed snapshot information."""
    snapshot_id: str = Field(description="Snapshot identifier")
    snapshot_date: datetime = Field(description="When snapshot was created")
    reason: SnapshotReasonEnum = Field(description="Reason for snapshot")
    name: str = Field(description="Agent name at snapshot time")
    instructions_preview: str = Field(description="First 100 chars of instructions")


class AgentSnapshotsResponse(BaseModel):
    """Response listing agent snapshots."""
    slot_index: int = Field(description="Slot index")
    snapshots: List[AgentSnapshotDetail] = Field(description="Snapshot list")
    count: int = Field(description="Total count")
    retention_days: int = Field(default=90, description="Snapshot retention period")


class AgentRestoreRequest(BaseModel):
    """Request to restore from snapshot."""
    snapshot_id: str = Field(description="Snapshot to restore from")


class AgentRestoreResponse(BaseModel):
    """Response after restoring from snapshot."""
    slot_index: int = Field(description="Slot index")
    restored_from: str = Field(description="Snapshot ID restored from")
    name: str = Field(description="Restored agent name")
    message: str = Field(description="Status message")


class SyncStrategyEnum(str, Enum):
    """Multi-device sync strategy."""
    LATEST_WINS = "latest_wins"
    SERVER_WINS = "server_wins"
    DEVICE_WINS = "device_wins"


class AgentSyncItem(BaseModel):
    """Agent data for sync."""
    slot_index: int = Field(ge=0, le=2, description="Slot index")
    name: str = Field(description="Agent name")
    instructions: str = Field(description="Agent instructions")
    gradient_color_1: str = Field(description="Primary gradient color")
    gradient_color_2: str = Field(description="Secondary gradient color")
    updated_at: datetime = Field(description="Last update timestamp")


class AgentSyncRequest(BaseModel):
    """Request to sync agent profiles."""
    agents: List[AgentSyncItem] = Field(description="Agents to sync")
    device_id: str = Field(description="Device identifier")
    sync_strategy: SyncStrategyEnum = Field(
        default=SyncStrategyEnum.LATEST_WINS,
        description="Conflict resolution strategy"
    )


class AgentSyncConflict(BaseModel):
    """Sync conflict information."""
    slot_index: int = Field(description="Conflicting slot")
    device_updated_at: datetime = Field(description="Device version timestamp")
    server_updated_at: datetime = Field(description="Server version timestamp")
    resolution: str = Field(description="How conflict was resolved")


class AgentSyncResponse(BaseModel):
    """Response after syncing agents."""
    synced_count: int = Field(description="Number of agents synced")
    conflicts: List[AgentSyncConflict] = Field(description="Any conflicts encountered")
    server_agents: List[AgentSyncItem] = Field(description="Current server state")


# ============================================================================
# V2 Agent Config Schemas (.md-based system)
# ============================================================================


class AgentIdentityResponse(BaseModel):
    """Agent identity from IDENTITY.md."""
    name: str = Field(description="Agent display name")
    full_name: str = Field(default="", description="Full name")
    emoji: str = Field(default="", description="Agent emoji")
    vibe: str = Field(default="", description="Short personality descriptor")
    avatar_path: Optional[str] = Field(None, description="Path to avatar image")
    gradient_color_1: str = Field(description="Primary gradient color (hex)")
    gradient_color_2: str = Field(description="Secondary gradient color (hex)")
    invoke_pattern: str = Field(default="", description="Regex for @-mention detection")
    temperature: float = Field(default=0.0, description="Default inference temperature")


class AgentConfigResponse(BaseModel):
    """V2 agent configuration response."""
    directory_name: str = Field(description="Agent directory name (slug)")
    name: str = Field(description="Agent display name")
    identity: AgentIdentityResponse = Field(description="Agent identity")
    is_default: bool = Field(description="Whether this is a built-in default agent")
    is_archived: bool = Field(default=False, description="Whether archived")
    has_bootstrap: bool = Field(default=False, description="Whether onboarding is pending")
    config_version: str = Field(default="1.0", description="Config schema version")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    files: Dict[str, bool] = Field(description="Map of config files to whether they have content")


class AgentConfigListResponse(BaseModel):
    """V2 agent list response."""
    agents: List[AgentConfigResponse] = Field(description="Agent list")
    count: int = Field(description="Total count")
    default_agent: str = Field(description="Default agent name")


class AgentCreateRequest(BaseModel):
    """Request to create a new agent."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Agent display name"
    )
    slug: Optional[str] = Field(
        None,
        max_length=50,
        description="Directory name (auto-generated from name if not provided)"
    )


class AgentConfigFileResponse(BaseModel):
    """Response containing a single config file's content."""
    agent_name: str = Field(description="Agent directory name")
    file_name: str = Field(description="Config file name (e.g., ANIMA.md)")
    content: str = Field(description="File content")
    writable_by_agent: bool = Field(description="Whether agent can modify this file")
    requires_confirmation: bool = Field(description="Whether agent modification needs user confirmation")


class AgentConfigFileUpdateRequest(BaseModel):
    """Request to update a config file."""
    content: str = Field(
        ...,
        description="New file content"
    )
    source: str = Field(
        default="user",
        description="Who is making the change: 'user', 'agent', or 'system'"
    )
    confirmed: bool = Field(
        default=False,
        description="Whether user confirmed this change (required for agent-initiated edits to sensitive files)"
    )


class AgentArchiveResponse(BaseModel):
    """Response after archiving an agent."""
    agent_name: str = Field(description="Archived agent name")
    message: str = Field(description="Status message")


class ChatContextModel(BaseModel):
    """Workspace context for v2 chat API."""
    active_tab: Optional[str] = Field(None, description="Currently active tab (calendar, notes, files, etc.)")
    selected_text: Optional[str] = Field(None, description="User-selected text in canvas")
    attached_files: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Files attached via @ mention or drag-and-drop. Each has 'path' and optional 'content_preview'."
    )
    referenced_items: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Referenced items (calendar events, notes, etc.). Each has 'type', 'id', and 'summary' or 'title'."
    )
    panel_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Soft context from visible panels. Has 'visible_panels' list and optional metadata."
    )


class DailyNoteResponse(BaseModel):
    """A daily note entry."""
    date: str = Field(description="Note date (YYYY-MM-DD)")
    content: str = Field(description="Note content")
    agent_name: str = Field(description="Agent directory name")


class DailyNoteAppendRequest(BaseModel):
    """Request to append to a daily note."""
    content: str = Field(
        ...,
        min_length=1,
        description="Content to append"
    )


# ============================================================================
# User Settings Schemas (Phase 6b - User Settings API)
# ============================================================================

class QuietHours(BaseModel):
    """Quiet hours configuration."""
    enabled: bool = Field(default=False, description="Whether quiet hours are enabled")
    start: str = Field(default="22:00", description="Start time (HH:MM)")
    end: str = Field(default="07:00", description="End time (HH:MM)")


class PushNotificationSettings(BaseModel):
    """Push notification preferences."""
    enabled: bool = Field(default=True, description="Master enable/disable")
    order_executions: bool = Field(default=True, description="Notify on order completion")
    order_failures: bool = Field(default=True, description="Notify on order failure")
    proactive_briefings: bool = Field(default=True, description="Proactive intelligence alerts")
    quiet_hours: QuietHours = Field(
        default_factory=QuietHours,
        description="Quiet hours configuration"
    )


class UserProfileResponse(BaseModel):
    """User profile information."""
    user_id: str = Field(description="User identifier")
    name: str = Field(description="User display name")
    description: Optional[str] = Field(None, description="User description")
    photo_url: Optional[str] = Field(None, description="Profile photo URL")
    created_at: datetime = Field(description="Account creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class UserProfileUpdateRequest(BaseModel):
    """Request to update user profile."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)


class UserSettingsResponse(BaseModel):
    """User settings response."""
    push_notifications: PushNotificationSettings = Field(description="Push notification settings")
    default_mode: ModeEnum = Field(description="Default Hestia mode")
    auto_lock_timeout_minutes: int = Field(description="Auto-lock timeout")


class UserSettingsUpdateRequest(BaseModel):
    """Request to update user settings."""
    push_notifications: Optional[PushNotificationSettings] = Field(None)
    default_mode: Optional[ModeEnum] = Field(None)
    auto_lock_timeout_minutes: Optional[int] = Field(None, ge=1, le=60)


class UserSettingsUpdateResponse(BaseModel):
    """Response after updating settings."""
    updated: bool = Field(description="Whether update succeeded")
    settings: UserSettingsResponse = Field(description="Current settings")


class PushEnvironmentEnum(str, Enum):
    """APNS environment."""
    PRODUCTION = "production"
    SANDBOX = "sandbox"


class PushTokenRequest(BaseModel):
    """Request to register push token."""
    push_token: str = Field(
        ...,
        min_length=1,
        description="APNS device token"
    )
    device_id: str = Field(description="Device identifier")
    environment: PushEnvironmentEnum = Field(
        default=PushEnvironmentEnum.PRODUCTION,
        description="APNS environment"
    )


class PushTokenResponse(BaseModel):
    """Response after registering/unregistering push token."""
    registered: Optional[bool] = Field(None, description="For register")
    unregistered: Optional[bool] = Field(None, description="For unregister")
    device_id: Optional[str] = Field(None, description="Device identifier")
    message: str = Field(description="Status message")


# ============================================================================
# Cloud Provider Schemas (WS1 - Cloud LLM Support)
# ============================================================================

class CloudProviderEnum(str, Enum):
    """Supported cloud LLM providers."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"


class CloudProviderStateEnum(str, Enum):
    """Cloud provider operational state."""
    DISABLED = "disabled"
    ENABLED_FULL = "enabled_full"
    ENABLED_SMART = "enabled_smart"


class CloudProviderAddRequest(BaseModel):
    """Request to add a cloud provider."""
    provider: CloudProviderEnum = Field(
        ...,
        description="Cloud provider type (anthropic, openai, google)"
    )
    api_key: str = Field(
        ...,
        min_length=1,
        description="API key for the provider (stored in Keychain)"
    )
    state: CloudProviderStateEnum = Field(
        default=CloudProviderStateEnum.ENABLED_SMART,
        description="Initial provider state"
    )
    model_id: Optional[str] = Field(
        None,
        description="Preferred model ID (uses provider default if omitted)"
    )


class CloudProviderStateUpdateRequest(BaseModel):
    """Request to update a provider's routing state."""
    state: CloudProviderStateEnum = Field(
        ...,
        description="New provider state"
    )


class CloudProviderModelUpdateRequest(BaseModel):
    """Request to select a provider's active model."""
    model_id: str = Field(
        ...,
        min_length=1,
        description="Model ID to use for this provider"
    )


class CloudProviderResponse(BaseModel):
    """Cloud provider configuration (never exposes raw API key)."""
    id: str = Field(description="Provider config identifier")
    provider: CloudProviderEnum = Field(description="Provider type")
    state: CloudProviderStateEnum = Field(description="Operational state")
    active_model_id: Optional[str] = Field(None, description="Currently selected model")
    available_models: List[str] = Field(default_factory=list, description="Available model IDs")
    has_api_key: bool = Field(description="Whether an API key is configured")
    health_status: str = Field(default="unknown", description="Last health check result")
    last_health_check: Optional[datetime] = Field(None, description="Last health check timestamp")
    created_at: datetime = Field(description="When provider was added")
    updated_at: datetime = Field(description="Last update timestamp")


class CloudProviderListResponse(BaseModel):
    """Response listing cloud providers."""
    providers: List[CloudProviderResponse] = Field(description="Configured providers")
    count: int = Field(description="Number of providers")
    cloud_state: str = Field(description="Effective cloud routing state")


class CloudProviderDeleteResponse(BaseModel):
    """Response after removing a cloud provider."""
    provider: CloudProviderEnum = Field(description="Removed provider")
    deleted: bool = Field(description="Whether deletion succeeded")
    message: str = Field(description="Status message")


class CloudUsageSummaryResponse(BaseModel):
    """Cloud usage and cost summary."""
    period_days: int = Field(description="Summary period in days")
    total_requests: int = Field(default=0, description="Total cloud API requests")
    total_tokens_in: int = Field(default=0, description="Total input tokens")
    total_tokens_out: int = Field(default=0, description="Total output tokens")
    total_cost_usd: float = Field(default=0.0, description="Total cost in USD")
    by_provider: Dict[str, Any] = Field(default_factory=dict, description="Breakdown by provider")
    by_model: Dict[str, Any] = Field(default_factory=dict, description="Breakdown by model")


class CloudHealthCheckResponse(BaseModel):
    """Response from a provider health check."""
    provider: CloudProviderEnum = Field(description="Provider checked")
    healthy: bool = Field(description="Whether the provider is reachable")
    health_status: str = Field(description="Health status string")
    message: str = Field(description="Status message")


# ============================================================================
# Voice Journaling (WS2)
# ============================================================================

class VoiceFlaggedWord(BaseModel):
    """A word flagged by the quality checker as potentially incorrect."""
    word: str = Field(description="The flagged word as it appears in the transcript")
    position: int = Field(description="Character offset in the transcript (0-indexed)")
    confidence: float = Field(description="Confidence this word is incorrect (0.0-1.0)")
    suggestions: List[str] = Field(default_factory=list, description="Suggested corrections")
    reason: str = Field(default="", description="Reason for flagging (e.g. homophone, proper noun)")


class VoiceQualityCheckRequest(BaseModel):
    """Request to quality-check a voice transcript."""
    transcript: str = Field(description="The transcript text to check", min_length=1, max_length=10000)
    known_entities: Optional[List[str]] = Field(
        default=None,
        description="Known entity names (people, events, projects) to help catch misheard proper nouns",
    )


class VoiceQualityCheckResponse(BaseModel):
    """Response from quality checking a transcript."""
    transcript: str = Field(description="The original transcript")
    flagged_words: List[VoiceFlaggedWord] = Field(default_factory=list, description="Words flagged as potentially incorrect")
    overall_confidence: float = Field(description="Overall confidence in transcript accuracy (0.0-1.0)")
    needs_review: bool = Field(description="Whether the transcript should be reviewed by the user")


class VoiceIntentType(str, Enum):
    """Types of intents extracted from journal entries."""
    ACTION_ITEM = "action_item"
    REMINDER = "reminder"
    NOTE = "note"
    DECISION = "decision"
    REFLECTION = "reflection"
    FOLLOW_UP = "follow_up"


class VoiceJournalIntent(BaseModel):
    """A structured intent extracted from a journal transcript."""
    id: str = Field(description="Unique intent identifier")
    intent_type: VoiceIntentType = Field(description="Type of intent")
    content: str = Field(description="Concise description of the intent")
    confidence: float = Field(description="Confidence in intent extraction (0.0-1.0)")
    entities: List[str] = Field(default_factory=list, description="Named entities referenced")


class VoiceCrossReferenceSource(str, Enum):
    """Sources for cross-referencing journal intents."""
    CALENDAR = "calendar"
    MAIL = "mail"
    MEMORY = "memory"
    REMINDERS = "reminders"


class VoiceCrossReference(BaseModel):
    """A cross-reference match from an external source."""
    source: VoiceCrossReferenceSource = Field(description="Data source")
    match: str = Field(description="Description of the matched item")
    relevance: float = Field(description="Relevance score (0.0-1.0)")
    details: Dict[str, Any] = Field(default_factory=dict, description="Source-specific details")


class VoiceActionPlanItem(BaseModel):
    """A single action item in the journal analysis action plan."""
    id: str = Field(description="Unique action identifier")
    action: str = Field(description="Human-readable action description")
    tool_call: Optional[str] = Field(default=None, description="Tool name if executable")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments")
    confidence: float = Field(description="Confidence in action plan item (0.0-1.0)")
    intent_id: Optional[str] = Field(default=None, description="Links back to JournalIntent")


class VoiceJournalAnalyzeRequest(BaseModel):
    """Request to analyze a confirmed journal transcript."""
    transcript: str = Field(description="The confirmed transcript text", min_length=1, max_length=10000)
    mode: Optional[str] = Field(default="tia", description="Current Hestia mode (tia/mira/olly)")


class VoiceJournalAnalyzeResponse(BaseModel):
    """Response from journal analysis."""
    id: str = Field(description="Unique analysis identifier")
    transcript: str = Field(description="The analyzed transcript")
    intents: List[VoiceJournalIntent] = Field(default_factory=list, description="Extracted intents")
    cross_references: List[VoiceCrossReference] = Field(default_factory=list, description="Cross-reference matches")
    action_plan: List[VoiceActionPlanItem] = Field(default_factory=list, description="Generated action plan")
    summary: str = Field(default="", description="Brief summary of the analysis")
    timestamp: str = Field(description="ISO 8601 timestamp of the analysis")
