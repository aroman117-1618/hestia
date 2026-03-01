"""
Newsfeed API routes.

Endpoints for the unified Command Center timeline: listing items,
marking read/dismissed, getting unread counts, and force-refreshing.
"""

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from hestia.api.middleware.auth import get_device_token
from hestia.api.errors import sanitize_for_log
from hestia.newsfeed import (
    get_newsfeed_manager,
    NewsfeedItemType,
    NewsfeedItemSource,
)
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/newsfeed", tags=["newsfeed"])
logger = get_logger()

# Default user ID until multi-user ships
DEFAULT_USER_ID = "user-default"

# Rate limit state for /refresh [C1]: 1 per 10s per device
_refresh_timestamps: Dict[str, float] = defaultdict(float)
REFRESH_COOLDOWN_SECONDS = 10


# =============================================================================
# Request/Response Schemas
# =============================================================================

class NewsfeedItemResponse(BaseModel):
    """A single newsfeed item."""
    id: str
    item_type: str
    source: str
    title: str
    body: Optional[str] = None
    timestamp: Optional[str] = None
    priority: str = "normal"
    icon: Optional[str] = None
    color: Optional[str] = None
    action_type: Optional[str] = None
    action_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False
    is_dismissed: bool = False


class NewsfeedTimelineResponse(BaseModel):
    """Timeline response with items and counts."""
    items: List[NewsfeedItemResponse]
    count: int
    unread_count: int


class NewsfeedUnreadResponse(BaseModel):
    """Unread counts by type."""
    total: int
    by_type: Dict[str, int] = Field(default_factory=dict)


class NewsfeedActionResponse(BaseModel):
    """Response for read/dismiss actions."""
    success: bool
    item_id: str


class NewsfeedRefreshResponse(BaseModel):
    """Response for force refresh."""
    items_refreshed: int


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "/timeline",
    response_model=NewsfeedTimelineResponse,
    summary="Get timeline",
    description="Get unified timeline items with optional filters.",
)
async def get_timeline(
    type: Optional[str] = Query(None, description="Filter by item type"),
    source: Optional[str] = Query(None, description="Filter by source"),
    include_dismissed: bool = Query(False, description="Include dismissed items"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_device_token),
):
    """Get unified timeline items."""
    manager = await get_newsfeed_manager()

    item_type = None
    item_source = None

    if type:
        try:
            item_type = NewsfeedItemType(type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid type. Must be one of: {[t.value for t in NewsfeedItemType]}",
            )

    if source:
        try:
            item_source = NewsfeedItemSource(source)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source. Must be one of: {[s.value for s in NewsfeedItemSource]}",
            )

    try:
        items = await manager.get_timeline(
            user_id=DEFAULT_USER_ID,
            item_type=item_type,
            source=item_source,
            include_dismissed=include_dismissed,
            limit=limit,
            offset=offset,
        )
        unread_count = await manager.get_unread_count(user_id=DEFAULT_USER_ID)
    except Exception as e:
        logger.error(
            f"Timeline fetch failed: {sanitize_for_log(e)}",
            component=LogComponent.NEWSFEED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch timeline",
        )

    return NewsfeedTimelineResponse(
        items=[NewsfeedItemResponse(**item.to_dict()) for item in items],
        count=len(items),
        unread_count=unread_count,
    )


@router.get(
    "/unread-count",
    response_model=NewsfeedUnreadResponse,
    summary="Get unread counts",
    description="Get unread item counts, optionally broken down by type.",
)
async def get_unread_count(
    device_id: str = Depends(get_device_token),
):
    """Get unread counts by type."""
    manager = await get_newsfeed_manager()

    try:
        total = await manager.get_unread_count(user_id=DEFAULT_USER_ID)

        by_type = {}
        for item_type in NewsfeedItemType:
            count = await manager.get_unread_count(
                user_id=DEFAULT_USER_ID,
                item_type=item_type,
            )
            if count > 0:
                by_type[item_type.value] = count

    except Exception as e:
        logger.error(
            f"Unread count failed: {sanitize_for_log(e)}",
            component=LogComponent.NEWSFEED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get unread counts",
        )

    return NewsfeedUnreadResponse(total=total, by_type=by_type)


@router.post(
    "/items/{item_id}/read",
    response_model=NewsfeedActionResponse,
    summary="Mark item read",
    description="Mark a newsfeed item as read for the current user.",
)
async def mark_read(
    item_id: str,
    device_id: str = Depends(get_device_token),
):
    """Mark a newsfeed item as read."""
    manager = await get_newsfeed_manager()

    try:
        success = await manager.mark_read(
            item_id=item_id,
            user_id=DEFAULT_USER_ID,
            device_id=device_id,
        )
    except Exception as e:
        logger.error(
            f"Mark read failed for {item_id}: {sanitize_for_log(e)}",
            component=LogComponent.NEWSFEED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark item as read",
        )

    return NewsfeedActionResponse(success=success, item_id=item_id)


@router.post(
    "/items/{item_id}/dismiss",
    response_model=NewsfeedActionResponse,
    summary="Dismiss item",
    description="Dismiss a newsfeed item (hides from timeline).",
)
async def dismiss_item(
    item_id: str,
    device_id: str = Depends(get_device_token),
):
    """Dismiss a newsfeed item."""
    manager = await get_newsfeed_manager()

    try:
        success = await manager.mark_dismissed(
            item_id=item_id,
            user_id=DEFAULT_USER_ID,
            device_id=device_id,
        )
    except Exception as e:
        logger.error(
            f"Dismiss failed for {item_id}: {sanitize_for_log(e)}",
            component=LogComponent.NEWSFEED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to dismiss item",
        )

    return NewsfeedActionResponse(success=success, item_id=item_id)


@router.post(
    "/refresh",
    response_model=NewsfeedRefreshResponse,
    summary="Force refresh",
    description="Force re-aggregate from all sources. Rate limited to 1 per 10s per device.",
)
async def refresh_timeline(
    device_id: str = Depends(get_device_token),
):
    """Force re-aggregate timeline from sources. [C1] Rate limited."""
    # Check rate limit
    last_refresh = _refresh_timestamps.get(device_id, 0)
    elapsed = time.time() - last_refresh
    if elapsed < REFRESH_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Refresh rate limited. Try again in {int(REFRESH_COOLDOWN_SECONDS - elapsed)}s.",
        )

    _refresh_timestamps[device_id] = time.time()

    manager = await get_newsfeed_manager()

    try:
        count = await manager.refresh()
    except Exception as e:
        logger.error(
            f"Timeline refresh failed: {sanitize_for_log(e)}",
            component=LogComponent.NEWSFEED,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh timeline",
        )

    logger.info(
        "Timeline refreshed via API",
        component=LogComponent.NEWSFEED,
        data={"items_refreshed": count, "device_id": device_id},
    )

    return NewsfeedRefreshResponse(items_refreshed=count)
