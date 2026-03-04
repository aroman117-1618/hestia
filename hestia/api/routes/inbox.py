"""
Inbox API routes.

Endpoints for the unified inbox: listing items, marking read/archived,
getting unread counts, and force-refreshing from Apple sources.
"""

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from hestia.api.middleware.auth import get_device_token
from hestia.api.errors import sanitize_for_log
from hestia.inbox import (
    get_inbox_manager,
    InboxItemSource,
    InboxItemType,
)
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/inbox", tags=["inbox"])
logger = get_logger()

# Default user ID until multi-user ships
DEFAULT_USER_ID = "user-default"

# Rate limit state for /refresh: 1 per 10s per device
_refresh_timestamps: Dict[str, float] = defaultdict(float)
REFRESH_COOLDOWN_SECONDS = 10


# =============================================================================
# Request/Response Schemas
# =============================================================================

class InboxItemResponse(BaseModel):
    """A single inbox item."""
    id: str
    item_type: str
    source: str
    title: str
    body: Optional[str] = None
    timestamp: Optional[str] = None
    priority: str = "normal"
    sender: Optional[str] = None
    sender_detail: Optional[str] = None
    has_attachments: bool = False
    icon: Optional[str] = None
    color: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False
    is_archived: bool = False


class InboxListResponse(BaseModel):
    """Inbox listing response."""
    items: List[InboxItemResponse]
    count: int
    unread_count: int


class InboxUnreadResponse(BaseModel):
    """Unread counts with per-source breakdown."""
    total: int
    by_source: Dict[str, int] = Field(default_factory=dict)


class InboxActionResponse(BaseModel):
    """Response for read/archive actions."""
    success: bool
    item_id: str


class InboxMarkAllReadResponse(BaseModel):
    """Response for mark-all-read."""
    success: bool
    count: int


class InboxRefreshResponse(BaseModel):
    """Response for force refresh."""
    items_refreshed: int


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "",
    response_model=InboxListResponse,
    summary="List inbox items",
    description="Get unified inbox items with optional filters.",
)
async def list_inbox(
    source: Optional[str] = Query(None, description="Filter by source"),
    type: Optional[str] = Query(None, description="Filter by item type"),
    include_archived: bool = Query(False, description="Include archived items"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_device_token),
):
    """Get unified inbox items."""
    manager = await get_inbox_manager()

    item_source = None
    item_type = None

    if source:
        try:
            item_source = InboxItemSource(source)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source. Must be one of: {[s.value for s in InboxItemSource]}",
            )

    if type:
        try:
            item_type = InboxItemType(type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid type. Must be one of: {[t.value for t in InboxItemType]}",
            )

    try:
        items = await manager.get_inbox(
            user_id=DEFAULT_USER_ID,
            source=item_source,
            item_type=item_type,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )
        unread_count = await manager.get_unread_count(user_id=DEFAULT_USER_ID)
    except Exception as e:
        logger.error(
            f"Inbox fetch failed: {sanitize_for_log(e)}",
            component=LogComponent.INBOX,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch inbox",
        )

    return InboxListResponse(
        items=[InboxItemResponse(**item.to_dict()) for item in items],
        count=len(items),
        unread_count=unread_count,
    )


@router.get(
    "/unread-count",
    response_model=InboxUnreadResponse,
    summary="Get unread counts",
    description="Get total unread count and per-source breakdown.",
)
async def get_unread_count(
    device_id: str = Depends(get_device_token),
):
    """Get unread counts with per-source breakdown."""
    manager = await get_inbox_manager()

    try:
        total = await manager.get_unread_count(user_id=DEFAULT_USER_ID)
        by_source = await manager.get_unread_by_source(user_id=DEFAULT_USER_ID)
    except Exception as e:
        logger.error(
            f"Unread count failed: {sanitize_for_log(e)}",
            component=LogComponent.INBOX,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread counts",
        )

    return InboxUnreadResponse(total=total, by_source=by_source)


@router.get(
    "/{item_id}",
    response_model=InboxItemResponse,
    summary="Get inbox item",
    description="Get a single inbox item with full body (lazy-loaded for emails).",
)
async def get_item(
    item_id: str,
    device_id: str = Depends(get_device_token),
):
    """Get a single inbox item."""
    manager = await get_inbox_manager()

    try:
        item = await manager.get_item(item_id=item_id, user_id=DEFAULT_USER_ID)
    except Exception as e:
        logger.error(
            f"Inbox item fetch failed for {item_id}: {sanitize_for_log(e)}",
            component=LogComponent.INBOX,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch inbox item",
        )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    return InboxItemResponse(**item.to_dict())


@router.post(
    "/{item_id}/read",
    response_model=InboxActionResponse,
    summary="Mark item read",
    description="Mark an inbox item as read for the current user.",
)
async def mark_read(
    item_id: str,
    device_id: str = Depends(get_device_token),
):
    """Mark an inbox item as read."""
    manager = await get_inbox_manager()

    try:
        success = await manager.mark_read(
            item_id=item_id,
            user_id=DEFAULT_USER_ID,
            device_id=device_id,
        )
    except Exception as e:
        logger.error(
            f"Mark read failed for {item_id}: {sanitize_for_log(e)}",
            component=LogComponent.INBOX,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark item as read",
        )

    return InboxActionResponse(success=success, item_id=item_id)


@router.post(
    "/mark-all-read",
    response_model=InboxMarkAllReadResponse,
    summary="Mark all read",
    description="Mark all inbox items as read, optionally filtered by source.",
)
async def mark_all_read(
    source: Optional[str] = Query(None, description="Filter by source"),
    device_id: str = Depends(get_device_token),
):
    """Mark all inbox items as read."""
    manager = await get_inbox_manager()

    source_enum = None
    if source:
        try:
            source_enum = InboxItemSource(source)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source. Must be one of: {[s.value for s in InboxItemSource]}",
            )

    try:
        count = await manager.mark_all_read(
            user_id=DEFAULT_USER_ID,
            source=source_enum,
            device_id=device_id,
        )
    except Exception as e:
        logger.error(
            f"Mark all read failed: {sanitize_for_log(e)}",
            component=LogComponent.INBOX,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark all as read",
        )

    return InboxMarkAllReadResponse(success=True, count=count)


@router.post(
    "/{item_id}/archive",
    response_model=InboxActionResponse,
    summary="Archive item",
    description="Archive an inbox item (hides from default listing).",
)
async def archive_item(
    item_id: str,
    device_id: str = Depends(get_device_token),
):
    """Archive an inbox item."""
    manager = await get_inbox_manager()

    try:
        success = await manager.archive(
            item_id=item_id,
            user_id=DEFAULT_USER_ID,
            device_id=device_id,
        )
    except Exception as e:
        logger.error(
            f"Archive failed for {item_id}: {sanitize_for_log(e)}",
            component=LogComponent.INBOX,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to archive item",
        )

    return InboxActionResponse(success=success, item_id=item_id)


@router.post(
    "/refresh",
    response_model=InboxRefreshResponse,
    summary="Force refresh",
    description="Force re-aggregate from all Apple sources. Rate limited to 1 per 10s per device.",
)
async def refresh_inbox(
    device_id: str = Depends(get_device_token),
):
    """Force re-aggregate inbox from Apple sources. Rate limited."""
    # Check rate limit
    last_refresh = _refresh_timestamps.get(device_id, 0)
    elapsed = time.time() - last_refresh
    if elapsed < REFRESH_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Refresh rate limited. Try again in {int(REFRESH_COOLDOWN_SECONDS - elapsed)}s.",
        )

    _refresh_timestamps[device_id] = time.time()

    manager = await get_inbox_manager()

    try:
        count = await manager.refresh()
    except Exception as e:
        logger.error(
            f"Inbox refresh failed: {sanitize_for_log(e)}",
            component=LogComponent.INBOX,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh inbox",
        )

    logger.info(
        "Inbox refreshed via API",
        component=LogComponent.INBOX,
        data={"items_refreshed": count, "device_id": device_id},
    )

    return InboxRefreshResponse(items_refreshed=count)
