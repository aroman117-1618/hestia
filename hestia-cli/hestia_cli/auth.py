"""
Authentication for Hestia CLI.

Handles device registration via the invite flow and stores
JWT tokens in macOS Keychain via the keyring library.
"""

import platform
import socket
from typing import Optional, Tuple

import httpx
import keyring

SERVICE_NAME = "hestia-cli"
TOKEN_KEY = "device-token"
DEVICE_ID_KEY = "device-id"


def get_stored_token() -> Optional[str]:
    """Retrieve stored JWT from Keychain."""
    return keyring.get_password(SERVICE_NAME, TOKEN_KEY)


def get_stored_device_id() -> Optional[str]:
    """Retrieve stored device ID from Keychain."""
    return keyring.get_password(SERVICE_NAME, DEVICE_ID_KEY)


def store_credentials(token: str, device_id: str) -> None:
    """Store JWT and device ID in Keychain."""
    keyring.set_password(SERVICE_NAME, TOKEN_KEY, token)
    keyring.set_password(SERVICE_NAME, DEVICE_ID_KEY, device_id)


def clear_credentials() -> None:
    """Remove stored credentials from Keychain."""
    try:
        keyring.delete_password(SERVICE_NAME, TOKEN_KEY)
    except keyring.errors.PasswordDeleteError:
        pass
    try:
        keyring.delete_password(SERVICE_NAME, DEVICE_ID_KEY)
    except keyring.errors.PasswordDeleteError:
        pass


async def register_with_invite(
    server_url: str,
    invite_token: str,
    verify_ssl: bool = False,
) -> Tuple[str, str]:
    """
    Register this CLI device using an invite token.

    Args:
        server_url: Hestia server URL (e.g., https://localhost:8443)
        invite_token: One-time invite token from server
        verify_ssl: Whether to verify SSL certificates

    Returns:
        Tuple of (jwt_token, device_id)

    Raises:
        httpx.HTTPStatusError: If registration fails
        httpx.ConnectError: If server is unreachable
    """
    device_name = f"cli-{socket.gethostname()}"

    async with httpx.AsyncClient(verify=verify_ssl, timeout=15.0) as client:
        response = await client.post(
            f"{server_url}/v1/auth/register-with-invite",
            json={
                "invite_token": invite_token,
                "device_type": "cli",
                "device_name": device_name,
            },
        )
        response.raise_for_status()
        data = response.json()

    token = data["token"]
    device_id = data["device_id"]

    store_credentials(token, device_id)
    return token, device_id


async def check_connection(server_url: str, verify_ssl: bool = False) -> bool:
    """Test connectivity to the Hestia server."""
    try:
        async with httpx.AsyncClient(verify=verify_ssl, timeout=5.0) as client:
            response = await client.get(f"{server_url}/v1/ping")
            return response.status_code == 200
    except Exception:
        return False


async def refresh_token(
    server_url: str,
    current_token: str,
    verify_ssl: bool = False,
) -> Optional[str]:
    """
    Attempt to refresh an expired JWT token.

    Returns new token on success, None on failure.
    """
    try:
        async with httpx.AsyncClient(verify=verify_ssl, timeout=10.0) as client:
            response = await client.post(
                f"{server_url}/v1/auth/refresh",
                headers={"X-Hestia-Device-Token": current_token},
            )
            if response.status_code == 200:
                data = response.json()
                new_token = data.get("token")
                if new_token:
                    device_id = get_stored_device_id() or ""
                    store_credentials(new_token, device_id)
                    return new_token
    except Exception:
        pass
    return None
