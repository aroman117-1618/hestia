"""
Apple Push Notification service (APNs) client.

Uses JWT-based authentication with .p8 auth keys.
Sends push notifications to iOS devices via APNs HTTP/2 API.

Credentials read from macOS Keychain:
  - apns-key-id: 10-char key identifier
  - apns-team-id: Apple Developer Team ID
  - apns-key-path: Path to .p8 auth key file
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import jwt

from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent

logger = get_logger()

# APNs endpoints
APNS_PRODUCTION = "https://api.push.apple.com"
APNS_SANDBOX = "https://api.sandbox.push.apple.com"

# Bundle ID for push topic
BUNDLE_ID = "com.andrewlonati.hestia"

# JWT tokens are cached for 50 minutes (APNs allows up to 60)
JWT_TOKEN_TTL = 50 * 60


class APNsClient:
    """HTTP/2 client for Apple Push Notification service."""

    def __init__(
        self,
        key_id: str,
        team_id: str,
        key_path: str,
        sandbox: bool = False,
    ) -> None:
        self._key_id = key_id
        self._team_id = team_id
        self._key_path = Path(key_path)
        self._sandbox = sandbox
        self._base_url = APNS_SANDBOX if sandbox else APNS_PRODUCTION
        self._jwt_token: Optional[str] = None
        self._jwt_issued_at: float = 0
        self._key_data: Optional[str] = None

    def _load_key(self) -> str:
        """Load the .p8 auth key from disk (cached after first read)."""
        if self._key_data is None:
            if not self._key_path.exists():
                raise FileNotFoundError(
                    f"APNs auth key not found: {self._key_path}"
                )
            self._key_data = self._key_path.read_text().strip()
        return self._key_data

    def _get_jwt_token(self) -> str:
        """Get a valid JWT token, refreshing if expired."""
        now = time.time()
        if self._jwt_token and (now - self._jwt_issued_at) < JWT_TOKEN_TTL:
            return self._jwt_token

        key_data = self._load_key()
        self._jwt_issued_at = now
        self._jwt_token = jwt.encode(
            {"iss": self._team_id, "iat": int(now)},
            key_data,
            algorithm="ES256",
            headers={"kid": self._key_id},
        )
        return self._jwt_token

    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str = "",
        category: str = "BUMP_REQUEST",
        data: Optional[Dict[str, Any]] = None,
        sound: str = "default",
        badge: Optional[int] = None,
        priority: int = 10,
        collapse_id: Optional[str] = None,
    ) -> bool:
        """Send a push notification to an iOS device.

        Args:
            device_token: The APNs device token (hex string).
            title: Alert title.
            body: Alert body.
            category: Notification category for actionable notifications.
            data: Custom payload data.
            sound: Sound name or "default".
            badge: App badge number (None = don't change).
            priority: 10 (immediate) or 5 (power-considerate).
            collapse_id: Collapse identifier for replacing notifications.

        Returns:
            True if APNs accepted the notification.
        """
        token = self._get_jwt_token()

        # Build APNs payload
        alert: Dict[str, str] = {"title": title}
        if body:
            alert["body"] = body

        aps: Dict[str, Any] = {
            "alert": alert,
            "category": category,
        }
        if sound:
            aps["sound"] = sound
        if badge is not None:
            aps["badge"] = badge

        payload: Dict[str, Any] = {"aps": aps}
        if data:
            payload["hestia"] = data

        # Build headers
        headers: Dict[str, str] = {
            "authorization": f"bearer {token}",
            "apns-topic": BUNDLE_ID,
            "apns-priority": str(priority),
            "apns-push-type": "alert",
        }
        if collapse_id:
            headers["apns-collapse-id"] = collapse_id

        url = f"{self._base_url}/3/device/{device_token}"

        try:
            async with httpx.AsyncClient(http2=True) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=10.0,
                )

            if response.status_code == 200:
                logger.info(
                    "APNs notification sent",
                    component=LogComponent.NOTIFICATION,
                    data={"title": title, "token_prefix": device_token[:8]},
                )
                return True

            # Parse APNs error
            error_body = response.json() if response.content else {}
            reason = error_body.get("reason", "unknown")
            logger.warning(
                "APNs notification rejected",
                component=LogComponent.NOTIFICATION,
                data={
                    "status": response.status_code,
                    "reason": reason,
                    "token_prefix": device_token[:8],
                },
            )
            return False

        except Exception as e:
            logger.warning(
                "APNs request failed",
                component=LogComponent.NOTIFICATION,
                data={"error": type(e).__name__},
            )
            return False

    async def send_actionable_bump(
        self,
        device_token: str,
        callback_id: str,
        title: str,
        body: str = "",
        actions: Optional[List[str]] = None,
    ) -> bool:
        """Send an actionable bump notification with approve/deny actions.

        The iOS app registers a BUMP_REQUEST category with action buttons.
        When the user taps an action, the app posts back to the server.
        """
        return await self.send_notification(
            device_token=device_token,
            title=title,
            body=body,
            category="BUMP_REQUEST",
            data={
                "callbackId": callback_id,
                "actions": actions or ["approve", "deny"],
            },
            collapse_id=f"bump-{callback_id}",
            priority=10,
        )


async def create_apns_client_from_keychain() -> Optional[APNsClient]:
    """Create an APNs client using credentials from macOS Keychain.

    Reads apns-key-id, apns-team-id, apns-key-path from Keychain.
    Returns None if any credential is missing.
    """

    async def read_keychain(service: str) -> Optional[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "security", "find-generic-password",
                "-s", service, "-w",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                return stdout.decode().strip()
            return None
        except (asyncio.TimeoutError, OSError):
            return None

    key_id = await read_keychain("apns-key-id")
    team_id = await read_keychain("apns-team-id")
    key_path = await read_keychain("apns-key-path")

    if not all([key_id, team_id, key_path]):
        logger.warning(
            "APNs credentials incomplete in Keychain",
            component=LogComponent.NOTIFICATION,
            data={
                "has_key_id": key_id is not None,
                "has_team_id": team_id is not None,
                "has_key_path": key_path is not None,
            },
        )
        return None

    # Verify the key file exists
    if not Path(key_path).exists():
        logger.warning(
            "APNs key file not found",
            component=LogComponent.NOTIFICATION,
            data={"path": key_path},
        )
        return None

    logger.info(
        "APNs client initialized from Keychain",
        component=LogComponent.NOTIFICATION,
    )
    return APNsClient(
        key_id=key_id,
        team_id=team_id,
        key_path=key_path,
        sandbox=False,
    )
