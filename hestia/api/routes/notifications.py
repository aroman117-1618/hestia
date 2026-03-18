"""
Notification relay API routes.

Provides endpoints for creating bump requests, polling status,
responding to bumps, viewing history, and managing settings.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_device_token
from hestia.api.schemas.notifications import (
    BumpCreateRequest,
    BumpCreateResponse,
    BumpListResponse,
    BumpRespondRequest,
    BumpRespondResponse,
    BumpStatusResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
)
from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent
from hestia.notifications.manager import get_notification_manager

logger = get_logger()

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.post("/bump", response_model=BumpCreateResponse)
async def create_bump(
    request: BumpCreateRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Create a bump notification request.

    Routes intelligently: macOS notification if active, APNs push if idle.
    Respects rate limits, quiet hours, and Focus mode.
    """
    try:
        manager = await get_notification_manager()
        result = await manager.create_bump(
            title=request.title,
            body=request.body,
            priority=request.priority,
            actions=request.actions,
            context=request.context,
            session_id=request.session_id,
        )

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Notification service not available",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Bump creation error",
            component=LogComponent.NOTIFICATION,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create bump notification",
        )


@router.get("/bump/{callback_id}/status", response_model=BumpStatusResponse)
async def get_bump_status(
    callback_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Poll the status of a bump request.

    Used by Claude Code to wait for user response.
    Returns: pending, approved, denied, or expired.
    """
    try:
        manager = await get_notification_manager()
        result = await manager.get_bump_status(callback_id)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bump request not found",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Bump status error",
            component=LogComponent.NOTIFICATION,
            data={"error": sanitize_for_log(e), "callback_id": callback_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get bump status",
        )


@router.post("/bump/{callback_id}/respond", response_model=BumpRespondResponse)
async def respond_to_bump(
    callback_id: str,
    request: BumpRespondRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Submit a response to a bump request (approve/deny).

    Called by the iOS app after the user taps an action button,
    or by the macOS app / CLI.
    """
    try:
        manager = await get_notification_manager()
        result = await manager.respond_to_bump(callback_id, request.action)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bump request not found",
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Bump respond error",
            component=LogComponent.NOTIFICATION,
            data={"error": sanitize_for_log(e), "callback_id": callback_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to respond to bump",
        )


@router.get("/history", response_model=BumpListResponse)
async def list_bump_history(
    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
        description="Filter by status: pending, approved, denied, expired",
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List bump request history with optional status filter."""
    try:
        manager = await get_notification_manager()
        return await manager.list_bumps(
            status=status_filter, limit=limit, offset=offset
        )

    except Exception as e:
        logger.error(
            "Bump history error",
            component=LogComponent.NOTIFICATION,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list bump history",
        )


@router.get("/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get current notification relay settings."""
    try:
        manager = await get_notification_manager()
        return await manager.get_settings()

    except Exception as e:
        logger.error(
            "Get settings error",
            component=LogComponent.NOTIFICATION,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get notification settings",
        )


@router.put("/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    request: NotificationSettingsUpdateRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Update notification relay settings."""
    try:
        manager = await get_notification_manager()
        updates = request.model_dump(exclude_none=True)
        return await manager.update_settings("default", updates)

    except Exception as e:
        logger.error(
            "Update settings error",
            component=LogComponent.NOTIFICATION,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification settings",
        )
