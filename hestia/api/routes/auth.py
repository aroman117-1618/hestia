"""
Authentication routes for Hestia API.

Handles device registration, invite-based QR onboarding, and token management.
"""

import json
import os
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from hestia.api.schemas import (
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    InviteGenerateRequest,
    InviteGenerateResponse,
    InviteRegisterRequest,
    InviteRegisterResponse,
    ErrorResponse,
)
from hestia.api.middleware.auth import (
    create_device_token,
    create_invite_token,
    verify_invite_token,
    verify_setup_secret,
    check_invite_rate_limit,
    get_device_token,
    AuthError,
)
from hestia.api.invite_store import get_invite_store
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/auth", tags=["auth"])
logger = get_logger()

# Config: when True, /register returns 403 (only invite-based registration allowed)
_REQUIRE_INVITE = os.environ.get("HESTIA_REQUIRE_INVITE", "false").lower() == "true"


@router.post(
    "/register",
    response_model=DeviceRegisterResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        403: {"model": ErrorResponse, "description": "Invite required"},
    },
    summary="Register a new device",
    description="Register a new device and receive an authentication token. "
                "May be disabled when invite-based onboarding is required.",
)
async def register_device(request: DeviceRegisterRequest) -> DeviceRegisterResponse:
    """
    Register a new device (legacy open registration).

    When HESTIA_REQUIRE_INVITE=true, this endpoint returns 403
    and callers must use /register-with-invite instead.
    """
    if _REQUIRE_INVITE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Open registration is disabled. Use invite-based onboarding.",
        )

    device_id = f"device-{uuid4().hex[:12]}"

    device_info = {
        "device_name": request.device_name or "unknown",
        "device_type": request.device_type or "unknown",
    }

    token, expires_at = create_device_token(device_id, device_info)

    # Track in device registry
    try:
        store = await get_invite_store()
        await store.register_device(
            device_id=device_id,
            device_name=device_info["device_name"],
            device_type=device_info["device_type"],
        )
    except Exception as e:
        logger.warning(
            f"Failed to track device in registry: {sanitize_for_log(e)}",
            component=LogComponent.SECURITY,
        )

    logger.info(
        "Device registered (legacy)",
        component=LogComponent.API,
        data={
            "device_id": device_id,
            "device_name": request.device_name,
            "device_type": request.device_type,
        },
    )

    return DeviceRegisterResponse(
        device_id=device_id,
        token=token,
        expires_at=expires_at,
    )


@router.post(
    "/invite",
    response_model=InviteGenerateResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Invalid setup secret"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Generate invite token",
    description="Generate a one-time invite token for QR code onboarding. "
                "Requires the server setup secret.",
)
async def generate_invite(request: InviteGenerateRequest) -> InviteGenerateResponse:
    """
    Generate an invite token for QR code onboarding.

    Authenticated by setup_secret (Keychain-stored, generated on first boot).
    Rate limited to 5 invites per hour.
    """
    # Verify setup secret
    if not verify_setup_secret(request.setup_secret):
        logger.warning(
            "Invalid setup secret for invite generation",
            component=LogComponent.SECURITY,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid setup secret.",
        )

    # Rate limit check
    if not check_invite_rate_limit():
        logger.warning(
            "Invite rate limit exceeded",
            component=LogComponent.SECURITY,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 5 invites per hour.",
        )

    # Create nonce in database
    store = await get_invite_store()
    invite_token, expires_at = create_invite_token("placeholder")
    nonce = await store.create_nonce(expires_at=expires_at, source="setup_secret")

    # Re-create token with actual nonce
    invite_token, expires_at = create_invite_token(nonce)

    # Build QR payload
    server_url = os.environ.get("HESTIA_SERVER_URL", "https://hestia-3.local:8443")
    cert_fingerprint = os.environ.get("HESTIA_CERT_FINGERPRINT", "")

    qr_data = {
        "t": invite_token,
        "u": server_url,
        "f": cert_fingerprint,
    }

    logger.info(
        "Invite token generated",
        component=LogComponent.SECURITY,
        data={"nonce": nonce[:8] + "...", "expires_at": expires_at.isoformat()},
    )

    return InviteGenerateResponse(
        invite_token=invite_token,
        qr_payload=json.dumps(qr_data, separators=(",", ":")),
        expires_at=expires_at,
    )


@router.post(
    "/register-with-invite",
    response_model=InviteRegisterResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid invite token"},
        409: {"model": ErrorResponse, "description": "Invite already consumed"},
    },
    summary="Register device with invite",
    description="Register a new device using an invite token from QR code scanning.",
)
async def register_with_invite(request: InviteRegisterRequest) -> InviteRegisterResponse:
    """
    Register a device using an invite token (QR code onboarding).

    Validates the invite JWT, consumes the one-time nonce, and issues a device token.
    """
    # Verify invite token
    try:
        payload = verify_invite_token(request.invite_token)
    except AuthError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token.",
        )

    nonce = payload["nonce"]

    # Generate device
    device_id = f"device-{uuid4().hex[:12]}"
    device_name = request.device_name or "unknown"
    device_type = request.device_type or "unknown"

    # Consume nonce (atomic — prevents race conditions)
    store = await get_invite_store()
    consumed = await store.consume_nonce(nonce, device_id)

    if not consumed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invite has already been used or has expired.",
        )

    # Create device token
    device_info = {
        "device_name": device_name,
        "device_type": device_type,
    }
    token, expires_at = create_device_token(device_id, device_info)

    # Track in device registry
    await store.register_device(
        device_id=device_id,
        device_name=device_name,
        device_type=device_type,
        invite_nonce=nonce,
    )

    server_url = os.environ.get("HESTIA_SERVER_URL", "https://hestia-3.local:8443")

    logger.info(
        "Device registered via invite",
        component=LogComponent.SECURITY,
        data={
            "device_id": device_id,
            "device_name": device_name,
            "device_type": device_type,
            "nonce": nonce[:8] + "...",
        },
    )

    return InviteRegisterResponse(
        device_id=device_id,
        token=token,
        expires_at=expires_at,
        server_url=server_url,
    )


@router.post(
    "/re-invite",
    response_model=InviteGenerateResponse,
    responses={
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    },
    summary="Generate invite from authenticated device",
    description="Generate a new invite token from an already-authenticated device. "
                "Recovery path when setup secret is lost.",
)
async def re_invite(
    _device: str = Depends(get_device_token),
) -> InviteGenerateResponse:
    """
    Generate an invite from an authenticated device (recovery path).

    Requires a valid device JWT. No setup secret needed.
    """
    if not check_invite_rate_limit():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Maximum 5 invites per hour.",
        )

    store = await get_invite_store()
    invite_token, expires_at = create_invite_token("placeholder")
    nonce = await store.create_nonce(expires_at=expires_at, source="re_invite")
    invite_token, expires_at = create_invite_token(nonce)

    server_url = os.environ.get("HESTIA_SERVER_URL", "https://hestia-3.local:8443")
    cert_fingerprint = os.environ.get("HESTIA_CERT_FINGERPRINT", "")

    qr_data = {
        "t": invite_token,
        "u": server_url,
        "f": cert_fingerprint,
    }

    logger.info(
        "Re-invite token generated by authenticated device",
        component=LogComponent.SECURITY,
        data={"device_id": _device, "nonce": nonce[:8] + "..."},
    )

    return InviteGenerateResponse(
        invite_token=invite_token,
        qr_payload=json.dumps(qr_data, separators=(",", ":")),
        expires_at=expires_at,
    )


@router.post(
    "/refresh",
    response_model=DeviceRegisterResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
    summary="Refresh device token",
    description="Get a new token for an existing device (requires valid current token).",
)
async def refresh_token() -> DeviceRegisterResponse:
    """Placeholder for token refresh functionality."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Token refresh not yet implemented. Register a new device instead.",
    )
