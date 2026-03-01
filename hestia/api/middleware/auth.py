"""
Authentication middleware for Hestia API.

Implements device-based JWT authentication and invite-based onboarding.
"""

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Header, HTTPException, status
from jose import jwt, JWTError


# Configuration - in production, load from secure config
# Generate a secure key on first run and store it
_SECRET_KEY: Optional[str] = None
_SETUP_SECRET: Optional[str] = None
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 90  # 3 months - balanced security vs convenience
INVITE_EXPIRE_MINUTES = 10  # Short-lived invite tokens


def get_secret_key() -> str:
    """
    Get or generate the JWT secret key.

    Priority:
    1. Environment variable (HESTIA_JWT_SECRET)
    2. macOS Keychain via CredentialManager
    3. Generate new and store in Keychain
    """
    global _SECRET_KEY

    if _SECRET_KEY is None:
        # Try environment variable first (useful for deployment/testing)
        _SECRET_KEY = os.environ.get("HESTIA_JWT_SECRET")

        if not _SECRET_KEY:
            # Try Keychain via CredentialManager
            try:
                from hestia.security import get_credential_manager
                cred_manager = get_credential_manager()
                _SECRET_KEY = cred_manager.retrieve_sensitive(
                    "jwt_secret",
                    reason="API authentication initialization"
                )
            except Exception:
                pass  # Keychain not available, will generate new key

        if not _SECRET_KEY:
            # Generate new key and persist to Keychain
            _SECRET_KEY = secrets.token_urlsafe(32)
            try:
                from hestia.security import get_credential_manager
                cred_manager = get_credential_manager()
                cred_manager.store_sensitive(
                    "jwt_secret",
                    _SECRET_KEY,
                    reason="Initial JWT secret generation for API authentication"
                )
            except Exception:
                pass  # Fall back to in-memory only

    return _SECRET_KEY


def get_setup_secret() -> str:
    """
    Get or generate the setup secret for invite-based onboarding.

    The setup secret is generated on first boot and stored in Keychain.
    It's used to authenticate invite generation requests from the server owner.

    Priority:
    1. Environment variable (HESTIA_SETUP_SECRET) — for testing
    2. macOS Keychain via CredentialManager
    3. Generate new and store in Keychain
    """
    global _SETUP_SECRET

    if _SETUP_SECRET is None:
        _SETUP_SECRET = os.environ.get("HESTIA_SETUP_SECRET")

        if not _SETUP_SECRET:
            try:
                from hestia.security import get_credential_manager
                cred_manager = get_credential_manager()
                _SETUP_SECRET = cred_manager.retrieve_sensitive(
                    "setup_secret",
                    reason="Invite system initialization"
                )
            except Exception:
                pass

        if not _SETUP_SECRET:
            _SETUP_SECRET = secrets.token_urlsafe(32)
            try:
                from hestia.security import get_credential_manager
                cred_manager = get_credential_manager()
                cred_manager.store_sensitive(
                    "setup_secret",
                    _SETUP_SECRET,
                    reason="Initial setup secret generation for invite onboarding"
                )
            except Exception:
                pass

    return _SETUP_SECRET


def verify_setup_secret(provided_secret: str) -> bool:
    """Constant-time comparison of setup secret."""
    return secrets.compare_digest(provided_secret, get_setup_secret())


# Rate limiting for invite generation (in-memory, single-server)
_invite_rate_limit: dict = {"count": 0, "window_start": None}
INVITE_RATE_LIMIT = 5  # max invites per hour


def check_invite_rate_limit() -> bool:
    """Check if invite generation is within rate limits. Returns True if allowed."""
    now = datetime.now(timezone.utc)
    window = _invite_rate_limit

    if window["window_start"] is None or (now - window["window_start"]).total_seconds() > 3600:
        window["count"] = 0
        window["window_start"] = now

    if window["count"] >= INVITE_RATE_LIMIT:
        return False

    window["count"] += 1
    return True


class AuthError(Exception):
    """Authentication error."""

    def __init__(self, message: str, code: str = "auth_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def create_device_token(device_id: str, device_info: dict = None) -> tuple[str, datetime]:
    """
    Create a JWT token for a device.

    Args:
        device_id: Unique device identifier.
        device_info: Optional device metadata.

    Returns:
        Tuple of (token, expiration_datetime).
    """
    expires = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)

    payload = {
        "device_id": device_id,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
        "type": "device",
    }

    if device_info:
        payload["device_name"] = device_info.get("device_name", "")
        payload["device_type"] = device_info.get("device_type", "")

    token = jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)
    return token, expires


def create_invite_token(nonce: str) -> tuple[str, datetime]:
    """
    Create a short-lived JWT invite token for device onboarding.

    Args:
        nonce: One-time-use nonce to prevent replay attacks.

    Returns:
        Tuple of (token, expiration_datetime).
    """
    expires = datetime.now(timezone.utc) + timedelta(minutes=INVITE_EXPIRE_MINUTES)

    payload = {
        "nonce": nonce,
        "exp": expires,
        "iat": datetime.now(timezone.utc),
        "type": "invite",
    }

    token = jwt.encode(payload, get_secret_key(), algorithm=ALGORITHM)
    return token, expires


def verify_invite_token(token: str) -> dict:
    """
    Verify an invite JWT token.

    Args:
        token: The JWT invite token to verify.

    Returns:
        Decoded payload if valid (contains 'nonce' field).

    Raises:
        AuthError: If token is invalid, expired, or wrong type.
    """
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])

        if payload.get("type") != "invite":
            raise AuthError("Invalid token type — expected invite token", "invalid_token_type")

        if "nonce" not in payload:
            raise AuthError("Invite token missing nonce", "invalid_token")

        return payload

    except jwt.ExpiredSignatureError:
        raise AuthError("Invite token has expired", "token_expired")
    except JWTError as e:
        raise AuthError(f"Invalid invite token", "invalid_token")


def verify_device_token(token: str) -> dict:
    """
    Verify a device JWT token.

    Args:
        token: The JWT token to verify.

    Returns:
        Decoded payload if valid.

    Raises:
        AuthError: If token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, get_secret_key(), algorithms=[ALGORITHM])

        # Check token type
        if payload.get("type") != "device":
            raise AuthError("Invalid token type", "invalid_token_type")

        return payload

    except jwt.ExpiredSignatureError:
        raise AuthError("Token has expired", "token_expired")
    except JWTError as e:
        raise AuthError(f"Invalid token: {str(e)}", "invalid_token")


async def check_device_revocation(device_id: str) -> None:
    """
    Check if a device has been revoked in the invite store.

    Args:
        device_id: The device ID to check.

    Raises:
        HTTPException: 401 if the device is revoked.
    """
    try:
        from hestia.api.invite_store import get_invite_store
        store = await get_invite_store()
        if await store.is_device_revoked(device_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "device_revoked",
                    "message": "Device access revoked"
                }
            )
    except HTTPException:
        raise
    except Exception:
        # If invite store is unavailable, allow the request through
        # (fail-open for availability; revocation is defense-in-depth)
        pass


async def get_device_token(
    x_hestia_device_token: Optional[str] = Header(None, alias="X-Hestia-Device-Token")
) -> str:
    """
    FastAPI dependency to extract and validate device token.

    Args:
        x_hestia_device_token: Token from request header.

    Returns:
        Device ID from the validated token.

    Raises:
        HTTPException: If token is missing, invalid, or device is revoked.
    """
    if not x_hestia_device_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "unauthorized",
                "message": "Missing device token. Include X-Hestia-Device-Token header."
            }
        )

    try:
        payload = verify_device_token(x_hestia_device_token)
        device_id = payload["device_id"]
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": e.code,
                "message": e.message
            }
        )

    # Check revocation status
    await check_device_revocation(device_id)

    return device_id


async def get_optional_device_token(
    x_hestia_device_token: Optional[str] = Header(None, alias="X-Hestia-Device-Token")
) -> Optional[str]:
    """
    FastAPI dependency to optionally extract device token.

    Returns None if no token provided, otherwise validates and returns device ID.
    """
    if not x_hestia_device_token:
        return None

    try:
        payload = verify_device_token(x_hestia_device_token)
        return payload["device_id"]
    except AuthError:
        return None


# Alias for backward compatibility
get_current_device = get_device_token
