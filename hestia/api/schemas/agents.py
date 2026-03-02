"""
Agent profile schemas (v1 slot-based + v2 .md-based).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================================
# V1 Agent Schemas (slot-based)
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
