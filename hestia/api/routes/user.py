"""
User Settings API routes.

User profile, notification preferences, and push token management.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from hestia.api.middleware.auth import get_current_device
from hestia.api.schemas import (
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
    UserSettingsUpdateResponse,
    PushTokenRequest,
    PushTokenResponse,
    PushNotificationSettings as PushNotificationSettingsSchema,
    QuietHours as QuietHoursSchema,
    PushEnvironmentEnum,
    ModeEnum,
    DeviceListResponse,
    DeviceListItem,
    DeviceRevokeResponse,
)
from hestia.user import (
    get_user_manager,
    PushNotificationSettings,
    QuietHours,
    PushEnvironment,
)
from hestia.api.invite_store import get_invite_store
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent
from datetime import datetime, time


router = APIRouter(prefix="/v1/user", tags=["user"])
logger = get_logger()


# =============================================================================
# Helper Functions
# =============================================================================

def _parse_time(time_str: str) -> time:
    """Parse HH:MM time string."""
    h, m = map(int, time_str.split(":"))
    return time(h, m)


def _schema_to_push_settings(schema: PushNotificationSettingsSchema) -> PushNotificationSettings:
    """Convert schema to domain model."""
    quiet_hours = QuietHours(
        enabled=schema.quiet_hours.enabled,
        start=_parse_time(schema.quiet_hours.start),
        end=_parse_time(schema.quiet_hours.end),
    )

    return PushNotificationSettings(
        enabled=schema.enabled,
        order_executions=schema.order_executions,
        order_failures=schema.order_failures,
        proactive_briefings=schema.proactive_briefings,
        quiet_hours=quiet_hours,
    )


def _push_settings_to_schema(settings: PushNotificationSettings) -> PushNotificationSettingsSchema:
    """Convert domain model to schema."""
    return PushNotificationSettingsSchema(
        enabled=settings.enabled,
        order_executions=settings.order_executions,
        order_failures=settings.order_failures,
        proactive_briefings=settings.proactive_briefings,
        quiet_hours=QuietHoursSchema(
            enabled=settings.quiet_hours.enabled,
            start=settings.quiet_hours.start.strftime("%H:%M"),
            end=settings.quiet_hours.end.strftime("%H:%M"),
        ),
    )


# =============================================================================
# Profile Routes
# =============================================================================

@router.get(
    "/profile",
    response_model=UserProfileResponse,
    summary="Get user profile",
    description="Get current user profile information.",
)
async def get_profile(
    device_id: str = Depends(get_current_device),
):
    """Get user profile."""
    manager = await get_user_manager()

    profile = await manager.get_profile()

    photo_url = f"/v1/user/photo" if profile.photo_path else None

    return UserProfileResponse(
        user_id=profile.id,
        name=profile.name,
        description=profile.description,
        photo_url=photo_url,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.patch(
    "/profile",
    response_model=UserProfileResponse,
    summary="Update user profile",
    description="Update user profile information.",
)
async def update_profile(
    request: UserProfileUpdateRequest,
    device_id: str = Depends(get_current_device),
):
    """Update user profile."""
    manager = await get_user_manager()

    profile = await manager.update_profile(
        name=request.name,
        description=request.description,
    )

    logger.info(
        "User profile updated via API",
        component=LogComponent.API,
        data={"device_id": device_id},
    )

    photo_url = f"/v1/user/photo" if profile.photo_path else None

    return UserProfileResponse(
        user_id=profile.id,
        name=profile.name,
        description=profile.description,
        photo_url=photo_url,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


@router.post(
    "/photo",
    summary="Upload profile photo",
    description="Upload a user profile photo.",
)
async def upload_photo(
    photo: UploadFile = File(...),
    device_id: str = Depends(get_current_device),
):
    """Upload user profile photo."""
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

    manager = await get_user_manager()

    filename = await manager.save_photo(
        photo_data=contents,
        content_type=photo.content_type,
    )

    logger.info(
        "User photo uploaded via API",
        component=LogComponent.API,
        data={"device_id": device_id},
    )

    return {
        "photo_url": "/v1/user/photo",
        "message": "Photo uploaded successfully",
    }


@router.get(
    "/photo",
    summary="Get profile photo",
    description="Get the user profile photo.",
)
async def get_photo(
    device_id: str = Depends(get_current_device),
):
    """Get user profile photo."""
    manager = await get_user_manager()

    profile = await manager.get_profile()
    if not profile.photo_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Photo not found",
        )

    photo_path = manager.get_photo_path(profile.photo_path)
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
    "/photo",
    summary="Delete profile photo",
    description="Delete the user profile photo.",
)
async def delete_photo(
    device_id: str = Depends(get_current_device),
):
    """Delete user profile photo."""
    manager = await get_user_manager()

    deleted = await manager.delete_photo()

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No photo to delete",
        )

    logger.info(
        "User photo deleted via API",
        component=LogComponent.API,
        data={"device_id": device_id},
    )

    return {
        "photo_url": None,
        "message": "Photo removed",
    }


# =============================================================================
# Settings Routes
# =============================================================================

@router.get(
    "/settings",
    response_model=UserSettingsResponse,
    summary="Get user settings",
    description="Get user notification and preference settings.",
)
async def get_settings(
    device_id: str = Depends(get_current_device),
):
    """Get user settings."""
    manager = await get_user_manager()

    settings = await manager.get_settings()

    return UserSettingsResponse(
        push_notifications=_push_settings_to_schema(settings.push_notifications),
        default_mode=ModeEnum(settings.default_mode),
        auto_lock_timeout_minutes=settings.auto_lock_timeout_minutes,
    )


@router.patch(
    "/settings",
    response_model=UserSettingsUpdateResponse,
    summary="Update user settings",
    description="Update user settings. All fields are optional.",
)
async def update_settings(
    request: UserSettingsUpdateRequest,
    device_id: str = Depends(get_current_device),
):
    """Update user settings."""
    manager = await get_user_manager()

    # Build update kwargs
    kwargs = {}
    if request.push_notifications is not None:
        kwargs["push_notifications"] = _schema_to_push_settings(request.push_notifications)
    if request.default_mode is not None:
        kwargs["default_mode"] = request.default_mode.value
    if request.auto_lock_timeout_minutes is not None:
        kwargs["auto_lock_timeout_minutes"] = request.auto_lock_timeout_minutes

    settings = await manager.update_settings(**kwargs)

    logger.info(
        "User settings updated via API",
        component=LogComponent.API,
        data={"device_id": device_id},
    )

    return UserSettingsUpdateResponse(
        updated=True,
        settings=UserSettingsResponse(
            push_notifications=_push_settings_to_schema(settings.push_notifications),
            default_mode=ModeEnum(settings.default_mode),
            auto_lock_timeout_minutes=settings.auto_lock_timeout_minutes,
        ),
    )


# =============================================================================
# Push Token Routes
# =============================================================================

@router.post(
    "/push-token",
    response_model=PushTokenResponse,
    summary="Register push token",
    description="Register APNS push token for notifications.",
)
async def register_push_token(
    request: PushTokenRequest,
    device_id: str = Depends(get_current_device),
):
    """Register a push token."""
    manager = await get_user_manager()

    env = PushEnvironment(request.environment.value)

    token = await manager.register_push_token(
        device_id=request.device_id,
        push_token=request.push_token,
        environment=env,
    )

    logger.info(
        f"Push token registered via API: {request.device_id}",
        component=LogComponent.API,
    )

    return PushTokenResponse(
        registered=True,
        device_id=token.device_id,
        message="Push token registered",
    )


@router.delete(
    "/push-token",
    response_model=PushTokenResponse,
    summary="Unregister push token",
    description="Unregister push token for this device.",
)
async def unregister_push_token(
    device_id: str = Depends(get_current_device),
):
    """Unregister push token for current device."""
    manager = await get_user_manager()

    deleted = await manager.unregister_push_token(device_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No push token found for this device",
        )

    logger.info(
        f"Push token unregistered via API: {device_id}",
        component=LogComponent.API,
    )

    return PushTokenResponse(
        unregistered=True,
        message="Push token removed",
    )


# =============================================================================
# Device Registry Routes
# =============================================================================

@router.get(
    "/devices",
    response_model=DeviceListResponse,
    summary="List registered devices",
    description="List all devices that have registered with this Hestia instance.",
)
async def list_devices(
    device_id: str = Depends(get_current_device),
):
    """List all registered devices with revocation status."""
    try:
        store = await get_invite_store()
        devices = await store.list_devices()

        return DeviceListResponse(
            devices=[
                DeviceListItem(
                    device_id=d["device_id"],
                    device_name=d["device_name"],
                    device_type=d["device_type"],
                    registered_at=datetime.fromisoformat(d["registered_at"]),
                    last_seen_at=datetime.fromisoformat(d["last_seen_at"]) if d.get("last_seen_at") else None,
                    revoked_at=datetime.fromisoformat(d["revoked_at"]) if d.get("revoked_at") else None,
                    is_active=d.get("revoked_at") is None,
                )
                for d in devices
            ],
            count=len(devices),
        )
    except Exception as e:
        logger.error(
            f"Failed to list devices: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list devices",
        )


@router.post(
    "/devices/{target_device_id}/revoke",
    response_model=DeviceRevokeResponse,
    summary="Revoke device access",
    description="Revoke a device's access. The device will receive 401 on subsequent requests.",
)
async def revoke_device(
    target_device_id: str,
    device_id: str = Depends(get_current_device),
):
    """Revoke a registered device's access."""
    try:
        store = await get_invite_store()
        revoked = await store.revoke_device(target_device_id)

        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found",
            )

        logger.info(
            f"Device revoked via API: {target_device_id}",
            component=LogComponent.API,
            data={"device_id": device_id, "target_device_id": target_device_id},
        )

        return DeviceRevokeResponse(
            device_id=target_device_id,
            revoked=True,
            message="Device access revoked",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to revoke device: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke device",
        )


@router.post(
    "/devices/{target_device_id}/unrevoke",
    response_model=DeviceRevokeResponse,
    summary="Restore device access",
    description="Restore a revoked device's access.",
)
async def unrevoke_device(
    target_device_id: str,
    device_id: str = Depends(get_current_device),
):
    """Restore a revoked device's access."""
    try:
        store = await get_invite_store()
        unrevoked = await store.unrevoke_device(target_device_id)

        if not unrevoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Device not found",
            )

        logger.info(
            f"Device unrevoked via API: {target_device_id}",
            component=LogComponent.API,
            data={"device_id": device_id, "target_device_id": target_device_id},
        )

        return DeviceRevokeResponse(
            device_id=target_device_id,
            revoked=False,
            message="Device access restored",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to unrevoke device: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to restore device access",
        )
