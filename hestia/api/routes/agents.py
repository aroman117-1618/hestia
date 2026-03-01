"""
Agent Profiles API routes.

CRUD operations for agent profiles with snapshot/restore and sync support.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from hestia.api.middleware.auth import get_device_token
from hestia.api.schemas import (
    AgentProfileResponse,
    AgentListResponse,
    AgentUpdateRequest,
    AgentDeleteResponse,
    AgentPhotoResponse,
    AgentSnapshotsResponse,
    AgentSnapshotDetail,
    AgentSnapshotSummary,
    AgentRestoreRequest,
    AgentRestoreResponse,
    AgentSyncRequest,
    AgentSyncResponse,
    AgentSyncConflict,
    AgentSyncItem,
    SnapshotReasonEnum,
)
from hestia.agents import get_agent_manager, AgentProfile, AgentSnapshot
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/agents", tags=["agents"])
logger = get_logger()


# =============================================================================
# Helper Functions
# =============================================================================

def _agent_to_response(
    agent: AgentProfile,
    snapshots: Optional[List[AgentSnapshot]] = None,
) -> AgentProfileResponse:
    """Convert domain AgentProfile to API response."""
    photo_url = f"/v1/agents/{agent.slot_index}/photo" if agent.photo_path else None

    snapshot_summaries = None
    if snapshots:
        snapshot_summaries = [
            AgentSnapshotSummary(
                snapshot_id=s.id,
                snapshot_date=s.snapshot_date,
                reason=SnapshotReasonEnum(s.reason.value),
            )
            for s in snapshots
        ]

    return AgentProfileResponse(
        agent_id=agent.id,
        slot_index=agent.slot_index,
        name=agent.name,
        instructions=agent.instructions,
        gradient_color_1=agent.gradient_color_1,
        gradient_color_2=agent.gradient_color_2,
        is_default=agent.is_default,
        can_be_deleted=agent.can_be_deleted,
        photo_url=photo_url,
        snapshots=snapshot_summaries,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "",
    response_model=AgentListResponse,
    summary="List agent profiles",
    description="List all 3 agent profiles.",
)
async def list_agents(
    device_id: str = Depends(get_device_token),
):
    """List all agents."""
    manager = await get_agent_manager()

    agents = await manager.list_agents()

    return AgentListResponse(
        agents=[_agent_to_response(a) for a in agents],
        count=len(agents),
    )


@router.get(
    "/{slot_index}",
    response_model=AgentProfileResponse,
    summary="Get agent profile",
    description="Get detailed information about an agent, including recent snapshots.",
)
async def get_agent(
    slot_index: int,
    device_id: str = Depends(get_device_token),
):
    """Get agent by slot index."""
    if slot_index not in (0, 1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_index must be 0, 1, or 2",
        )

    manager = await get_agent_manager()

    agent = await manager.get_agent(slot_index)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent not found at slot {slot_index}",
        )

    # Include recent snapshots
    snapshots = await manager.list_snapshots(slot_index, limit=5)

    return _agent_to_response(agent, snapshots)


@router.put(
    "/{slot_index}",
    response_model=AgentProfileResponse,
    summary="Update agent profile",
    description="Update or create an agent profile at a slot index.",
)
async def update_agent(
    slot_index: int,
    request: AgentUpdateRequest,
    device_id: str = Depends(get_device_token),
):
    """Update an agent."""
    if slot_index not in (0, 1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_index must be 0, 1, or 2",
        )

    manager = await get_agent_manager()

    try:
        agent = await manager.update_agent(
            slot_index=slot_index,
            name=request.name,
            instructions=request.instructions,
            gradient_color_1=request.gradient_color_1,
            gradient_color_2=request.gradient_color_2,
        )

        logger.info(
            f"Agent updated via API: slot {slot_index}",
            component=LogComponent.API,
            data={"slot": slot_index, "device_id": device_id},
        )

        return _agent_to_response(agent)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": "Invalid agent parameters."},
        )


@router.delete(
    "/{slot_index}",
    response_model=AgentDeleteResponse,
    summary="Delete agent profile",
    description="Reset an agent profile to default. Slot 0 cannot be deleted.",
)
async def delete_agent(
    slot_index: int,
    device_id: str = Depends(get_device_token),
):
    """Delete (reset) an agent."""
    if slot_index not in (0, 1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_index must be 0, 1, or 2",
        )

    if slot_index == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Primary agent cannot be deleted",
        )

    manager = await get_agent_manager()

    try:
        agent = await manager.delete_agent(slot_index)

        logger.info(
            f"Agent reset via API: slot {slot_index}",
            component=LogComponent.API,
            data={"slot": slot_index, "device_id": device_id},
        )

        return AgentDeleteResponse(
            slot_index=slot_index,
            reset_to_default=True,
            default_name=agent.name,
            snapshot_created=True,
            message="Agent profile reset to default",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": "Invalid agent parameters."},
        )


# =============================================================================
# Photo Management
# =============================================================================

@router.post(
    "/{slot_index}/photo",
    response_model=AgentPhotoResponse,
    summary="Upload agent photo",
    description="Upload a custom photo for an agent.",
)
async def upload_photo(
    slot_index: int,
    photo: UploadFile = File(...),
    device_id: str = Depends(get_device_token),
):
    """Upload an agent photo."""
    if slot_index not in (0, 1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_index must be 0, 1, or 2",
        )

    # Validate content type
    if photo.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photo must be JPEG, PNG, or WebP",
        )

    # Limit size (5MB)
    contents = await photo.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Photo must be less than 5MB",
        )

    manager = await get_agent_manager()

    try:
        filename = await manager.save_photo(
            slot_index=slot_index,
            photo_data=contents,
            content_type=photo.content_type,
        )

        logger.info(
            f"Agent photo uploaded: slot {slot_index}",
            component=LogComponent.API,
            data={"slot": slot_index, "device_id": device_id},
        )

        return AgentPhotoResponse(
            slot_index=slot_index,
            photo_url=f"/v1/agents/{slot_index}/photo",
            message="Photo uploaded successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": "Invalid agent parameters."},
        )


@router.get(
    "/{slot_index}/photo",
    summary="Get agent photo",
    description="Get the custom photo for an agent.",
)
async def get_photo(
    slot_index: int,
    device_id: str = Depends(get_device_token),
):
    """Get an agent's photo."""
    if slot_index not in (0, 1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_index must be 0, 1, or 2",
        )

    manager = await get_agent_manager()

    agent = await manager.get_agent(slot_index)
    if agent is None or not agent.photo_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    photo_path = manager.get_photo_path(slot_index, agent.photo_path)
    if photo_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo file not found",
        )

    # Determine media type
    ext = photo_path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(ext, "image/jpeg")

    return FileResponse(photo_path, media_type=media_type)


@router.delete(
    "/{slot_index}/photo",
    response_model=AgentPhotoResponse,
    summary="Delete agent photo",
    description="Remove the custom photo for an agent.",
)
async def delete_photo(
    slot_index: int,
    device_id: str = Depends(get_device_token),
):
    """Delete an agent's photo."""
    if slot_index not in (0, 1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_index must be 0, 1, or 2",
        )

    manager = await get_agent_manager()

    try:
        deleted = await manager.delete_photo(slot_index)

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No photo to delete",
            )

        logger.info(
            f"Agent photo deleted: slot {slot_index}",
            component=LogComponent.API,
            data={"slot": slot_index, "device_id": device_id},
        )

        return AgentPhotoResponse(
            slot_index=slot_index,
            photo_url=None,
            message="Photo removed",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": "Invalid agent parameters."},
        )


# =============================================================================
# Snapshot Management
# =============================================================================

@router.get(
    "/{slot_index}/snapshots",
    response_model=AgentSnapshotsResponse,
    summary="List agent snapshots",
    description="List available snapshots for recovery.",
)
async def list_snapshots(
    slot_index: int,
    device_id: str = Depends(get_device_token),
):
    """List snapshots for an agent."""
    if slot_index not in (0, 1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_index must be 0, 1, or 2",
        )

    manager = await get_agent_manager()

    snapshots = await manager.list_snapshots(slot_index, limit=50)
    count = await manager.count_snapshots(slot_index)

    snapshot_details = [
        AgentSnapshotDetail(
            snapshot_id=s.id,
            snapshot_date=s.snapshot_date,
            reason=SnapshotReasonEnum(s.reason.value),
            name=s.name,
            instructions_preview=s.instructions_preview,
        )
        for s in snapshots
    ]

    return AgentSnapshotsResponse(
        slot_index=slot_index,
        snapshots=snapshot_details,
        count=count,
        retention_days=90,
    )


@router.post(
    "/{slot_index}/restore",
    response_model=AgentRestoreResponse,
    summary="Restore from snapshot",
    description="Restore an agent profile from a snapshot.",
)
async def restore_from_snapshot(
    slot_index: int,
    request: AgentRestoreRequest,
    device_id: str = Depends(get_device_token),
):
    """Restore an agent from a snapshot."""
    if slot_index not in (0, 1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot_index must be 0, 1, or 2",
        )

    manager = await get_agent_manager()

    try:
        agent = await manager.restore_from_snapshot(
            slot_index=slot_index,
            snapshot_id=request.snapshot_id,
        )

        logger.info(
            f"Agent restored from snapshot: slot {slot_index}",
            component=LogComponent.API,
            data={
                "slot": slot_index,
                "snapshot_id": request.snapshot_id,
                "device_id": device_id,
            },
        )

        return AgentRestoreResponse(
            slot_index=slot_index,
            restored_from=request.snapshot_id,
            name=agent.name,
            message="Agent profile restored successfully",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": "Invalid agent parameters."},
        )


# =============================================================================
# Multi-Device Sync
# =============================================================================

@router.post(
    "/sync",
    response_model=AgentSyncResponse,
    summary="Sync agent profiles",
    description="Sync all agent profiles from device to server.",
)
async def sync_agents(
    request: AgentSyncRequest,
    device_id: str = Depends(get_device_token),
):
    """Sync agents from a device."""
    manager = await get_agent_manager()

    # Convert request to internal format
    device_agents = [
        {
            "slot_index": a.slot_index,
            "name": a.name,
            "instructions": a.instructions,
            "gradient_color_1": a.gradient_color_1,
            "gradient_color_2": a.gradient_color_2,
            "updated_at": a.updated_at.isoformat(),
        }
        for a in request.agents
    ]

    result = await manager.sync_agents(
        device_agents=device_agents,
        device_id=request.device_id,
        sync_strategy=request.sync_strategy.value,
    )

    logger.info(
        f"Agent sync completed: {result['synced_count']} synced",
        component=LogComponent.API,
        data={"device_id": request.device_id},
    )

    return AgentSyncResponse(
        synced_count=result["synced_count"],
        conflicts=[
            AgentSyncConflict(
                slot_index=c["slot_index"],
                device_updated_at=datetime.fromisoformat(c["device_updated_at"]),
                server_updated_at=datetime.fromisoformat(c["server_updated_at"]),
                resolution=c["resolution"],
            )
            for c in result["conflicts"]
        ],
        server_agents=[
            AgentSyncItem(
                slot_index=a["slot_index"],
                name=a["name"],
                instructions=a["instructions"],
                gradient_color_1=a["gradient_color_1"],
                gradient_color_2=a["gradient_color_2"],
                updated_at=datetime.fromisoformat(a["updated_at"]),
            )
            for a in result["server_agents"]
        ],
    )
