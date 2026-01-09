"""
Authentication routes for Hestia API.

Handles device registration and token management.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from hestia.api.schemas import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    ErrorResponse,
)
from hestia.api.middleware.auth import create_device_token
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/auth", tags=["auth"])
logger = get_logger()


@router.post(
    "/register",
    response_model=DeviceRegisterResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
    summary="Register a new device",
    description="Register a new device and receive an authentication token."
)
async def register_device(request: DeviceRegisterRequest) -> DeviceRegisterResponse:
    """
    Register a new device.

    This endpoint does not require authentication. A new device token is
    generated and returned. The token should be stored securely on the
    device and included in all subsequent requests.

    In production, additional verification (like Tailscale device cert)
    would be required.
    """
    # Generate device ID
    device_id = f"device-{uuid4().hex[:12]}"

    # Create device info for token payload
    device_info = {
        "device_name": request.device_name or "unknown",
        "device_type": request.device_type or "unknown",
    }

    # Generate token
    token, expires_at = create_device_token(device_id, device_info)

    logger.info(
        "Device registered",
        component=LogComponent.API,
        data={
            "device_id": device_id,
            "device_name": request.device_name,
            "device_type": request.device_type,
        }
    )

    return DeviceRegisterResponse(
        device_id=device_id,
        token=token,
        expires_at=expires_at,
    )


@router.post(
    "/refresh",
    response_model=DeviceRegisterResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
    summary="Refresh device token",
    description="Get a new token for an existing device (requires valid current token)."
)
async def refresh_token(
    # We use a custom dependency here since we need the full token payload
    # In a real implementation, this would validate the current token
) -> DeviceRegisterResponse:
    """
    Refresh an existing device token.

    This is a placeholder for token refresh functionality.
    In production, this would validate the current token and issue a new one.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "error": "not_implemented",
            "message": "Token refresh not yet implemented. Register a new device instead."
        }
    )
