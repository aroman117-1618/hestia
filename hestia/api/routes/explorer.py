"""
Explorer API routes.

Endpoints for browsing aggregated resources (mail, notes, reminders,
files, drafts), managing Hestia drafts, and fetching resource content.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from hestia.api.middleware.auth import get_current_device
from hestia.api.errors import sanitize_for_log
from hestia.explorer import get_explorer_manager, ResourceType, ResourceSource, ResourceFlag
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/explorer", tags=["explorer"])
logger = get_logger()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class ExplorerResourceResponse(BaseModel):
    """A single explorer resource."""
    id: str
    type: str
    title: str
    source: str
    created_at: Optional[str] = None
    modified_at: Optional[str] = None
    preview: Optional[str] = None
    flags: List[str] = Field(default_factory=list)
    color: Optional[str] = None
    metadata: Dict[str, str] = Field(default_factory=dict)


class ExplorerResourceListResponse(BaseModel):
    """List of explorer resources."""
    resources: List[ExplorerResourceResponse]
    count: int


class ExplorerContentResponse(BaseModel):
    """Full content for a resource."""
    id: str
    content: Optional[str] = None


class DraftCreateRequest(BaseModel):
    """Request to create a new draft."""
    title: str = Field(..., min_length=1, max_length=500)
    body: Optional[str] = Field(None, max_length=50000)
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    flags: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)


class DraftUpdateRequest(BaseModel):
    """Request to update an existing draft."""
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    body: Optional[str] = Field(None, max_length=50000)
    color: Optional[str] = Field(None, max_length=7, pattern=r"^#[0-9a-fA-F]{6}$")
    flags: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None


class DraftDeleteResponse(BaseModel):
    """Response after deleting a draft."""
    deleted: bool


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "/resources",
    response_model=ExplorerResourceListResponse,
    summary="List resources",
    description="List aggregated resources, filterable by type, source, and search query.",
)
async def list_resources(
    type: Optional[str] = Query(None, description="Filter by resource type (draft, mail, task, note, file)"),
    source: Optional[str] = Query(None, description="Filter by source (hestia, mail, notes, reminders, files)"),
    search: Optional[str] = Query(None, description="Search by title or preview text"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_current_device),
):
    """List aggregated resources from all sources."""
    manager = await get_explorer_manager()

    resource_type = None
    resource_source = None

    if type:
        try:
            resource_type = ResourceType(type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid type. Must be one of: {[t.value for t in ResourceType]}",
            )

    if source:
        try:
            resource_source = ResourceSource(source)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source. Must be one of: {[s.value for s in ResourceSource]}",
            )

    try:
        resources = await manager.get_resources(
            resource_type=resource_type,
            source=resource_source,
            search=search,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(
            f"Explorer resource fetch failed: {sanitize_for_log(e)}",
            component=LogComponent.EXPLORER,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch resources",
        )

    return ExplorerResourceListResponse(
        resources=[
            ExplorerResourceResponse(**r.to_dict())
            for r in resources
        ],
        count=len(resources),
    )


@router.get(
    "/resources/{resource_id:path}",
    response_model=ExplorerResourceResponse,
    summary="Get resource",
    description="Get a single resource by its ID.",
)
async def get_resource(
    resource_id: str,
    device_id: str = Depends(get_current_device),
):
    """Get a single resource by ID."""
    manager = await get_explorer_manager()
    resource = await manager.get_resource(resource_id)

    if resource is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Resource not found",
        )

    return ExplorerResourceResponse(**resource.to_dict())


@router.get(
    "/resources/{resource_id:path}/content",
    response_model=ExplorerContentResponse,
    summary="Get resource content",
    description="Get full content for a resource (not just preview).",
)
async def get_resource_content(
    resource_id: str,
    device_id: str = Depends(get_current_device),
):
    """Get full content for a resource."""
    manager = await get_explorer_manager()

    try:
        content = await manager.get_resource_content(resource_id)
    except Exception as e:
        logger.error(
            f"Content fetch failed for {resource_id}: {sanitize_for_log(e)}",
            component=LogComponent.EXPLORER,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch resource content",
        )

    return ExplorerContentResponse(id=resource_id, content=content)


@router.post(
    "/drafts",
    response_model=ExplorerResourceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create draft",
    description="Create a new Hestia draft resource.",
)
async def create_draft(
    request: DraftCreateRequest,
    device_id: str = Depends(get_current_device),
):
    """Create a new Hestia draft."""
    manager = await get_explorer_manager()

    flags = []
    for f in request.flags:
        try:
            flags.append(ResourceFlag(f))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid flag '{f}'. Must be one of: {[fl.value for fl in ResourceFlag]}",
            )

    try:
        draft = await manager.create_draft(
            title=request.title,
            body=request.body,
            color=request.color,
            flags=flags,
            metadata=request.metadata,
        )
    except Exception as e:
        logger.error(
            f"Draft creation failed: {sanitize_for_log(e)}",
            component=LogComponent.EXPLORER,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create draft",
        )

    logger.info(
        "Draft created via API",
        component=LogComponent.EXPLORER,
        data={"draft_id": draft.id},
    )

    return ExplorerResourceResponse(**draft.to_dict())


@router.patch(
    "/drafts/{draft_id:path}",
    response_model=ExplorerResourceResponse,
    summary="Update draft",
    description="Update an existing Hestia draft.",
)
async def update_draft(
    draft_id: str,
    request: DraftUpdateRequest,
    device_id: str = Depends(get_current_device),
):
    """Update an existing draft."""
    manager = await get_explorer_manager()

    flags = None
    if request.flags is not None:
        flags = []
        for f in request.flags:
            try:
                flags.append(ResourceFlag(f))
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid flag '{f}'.",
                )

    try:
        draft = await manager.update_draft(
            draft_id=draft_id,
            title=request.title,
            body=request.body,
            color=request.color,
            flags=flags,
            metadata=request.metadata,
        )
    except Exception as e:
        logger.error(
            f"Draft update failed: {sanitize_for_log(e)}",
            component=LogComponent.EXPLORER,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update draft",
        )

    if draft is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )

    return ExplorerResourceResponse(**draft.to_dict())


@router.delete(
    "/drafts/{draft_id:path}",
    response_model=DraftDeleteResponse,
    summary="Delete draft",
    description="Delete a Hestia draft.",
)
async def delete_draft(
    draft_id: str,
    device_id: str = Depends(get_current_device),
):
    """Delete a draft."""
    manager = await get_explorer_manager()

    try:
        deleted = await manager.delete_draft(draft_id)
    except Exception as e:
        logger.error(
            f"Draft deletion failed: {sanitize_for_log(e)}",
            component=LogComponent.EXPLORER,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete draft",
        )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Draft not found",
        )

    logger.info(
        "Draft deleted via API",
        component=LogComponent.EXPLORER,
        data={"draft_id": draft_id},
    )

    return DraftDeleteResponse(deleted=True)
