"""
WebSocket client for Hestia backend.

Manages the WebSocket connection lifecycle: connect, authenticate,
send messages, receive streaming events, and handle reconnection.
"""

import asyncio
import json
import ssl
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
import websockets
import websockets.exceptions

from hestia_cli.auth import get_stored_token, get_stored_device_id
from hestia_cli.config import get_server_url, get_verify_ssl, load_config
from hestia_cli.models import AgentTheme, AuthResult, ServerEventType


class ConnectionError(Exception):
    """Raised when WebSocket connection fails."""
    pass


class AuthenticationError(Exception):
    """Raised when WebSocket authentication fails."""
    pass


class HestiaWSClient:
    """
    WebSocket client for streaming chat with Hestia backend.

    Handles connection, JWT authentication, message streaming,
    tool approval, and automatic reconnection.
    """

    def __init__(
        self,
        server_url: Optional[str] = None,
        verify_ssl: Optional[bool] = None,
    ):
        config = load_config()
        self.server_url = server_url or get_server_url(config)
        self.verify_ssl = verify_ssl if verify_ssl is not None else get_verify_ssl(config)
        self.device_id: Optional[str] = None
        self.mode: str = config.get("preferences", {}).get("default_mode", "tia")
        self.trust_tiers: Dict[str, str] = {}
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._connected = False
        self._session_id: Optional[str] = None

    @property
    def connected(self) -> bool:
        return self._connected and self._ws is not None

    @property
    def ws_url(self) -> str:
        """Convert HTTP URL to WebSocket URL."""
        url = self.server_url
        if url.startswith("https://"):
            return url.replace("https://", "wss://", 1) + "/v1/ws/chat"
        elif url.startswith("http://"):
            return url.replace("http://", "ws://", 1) + "/v1/ws/chat"
        return f"wss://{url}/v1/ws/chat"

    def _get_ssl_context(self) -> Optional[ssl.SSLContext]:
        """Build SSL context for WebSocket connection."""
        if self.ws_url.startswith("wss://"):
            ctx = ssl.create_default_context()
            if not self.verify_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            return ctx
        return None

    async def connect(self) -> AuthResult:
        """
        Connect to the Hestia WebSocket and authenticate.

        Returns AuthResult on success.
        Raises ConnectionError or AuthenticationError on failure.
        """
        token = get_stored_token()
        if not token:
            raise AuthenticationError(
                "No stored token. Run 'hestia auth login' first."
            )

        try:
            self._ws = await websockets.connect(
                self.ws_url,
                ssl=self._get_ssl_context(),
                max_size=2**20,  # 1MB max message
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
            )
        except Exception as e:
            raise ConnectionError(
                f"Cannot connect to Hestia at {self.server_url}. "
                f"Is the server running? ({type(e).__name__})"
            ) from e

        # Authenticate with first message
        try:
            await self._ws.send(json.dumps({"type": "auth", "token": token}))
            raw = await asyncio.wait_for(self._ws.recv(), timeout=10.0)
            data = json.loads(raw)
        except asyncio.TimeoutError:
            await self._close_ws()
            raise AuthenticationError("Authentication timed out (10s)")
        except Exception as e:
            await self._close_ws()
            raise ConnectionError(f"Auth handshake failed: {type(e).__name__}") from e

        result = AuthResult(**data) if data.get("type") == "auth_result" else AuthResult(success=False, error="Unexpected response")

        if not result.success:
            await self._close_ws()
            raise AuthenticationError(result.error or "Authentication failed")

        self._connected = True
        self.device_id = result.device_id or get_stored_device_id()
        self.trust_tiers = result.trust_tiers or {}
        return result

    async def send_message(
        self,
        content: str,
        mode: Optional[str] = None,
        session_id: Optional[str] = None,
        force_local: bool = False,
        context_hints: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send a chat message and yield streaming events.

        Yields dicts with "type" key matching ServerEventType values.
        """
        if not self.connected:
            raise ConnectionError("Not connected. Call connect() first.")

        msg = {
            "type": "message",
            "content": content,
            "mode": mode or self.mode,
            "session_id": session_id or self._session_id,
            "force_local": force_local,
            "context_hints": context_hints or {},
        }

        await self._ws.send(json.dumps(msg))

        # Receive streaming events until done or error
        while True:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=120.0)
                event = json.loads(raw)
            except asyncio.TimeoutError:
                yield {"type": "error", "code": "timeout", "message": "Response timed out"}
                return
            except websockets.exceptions.ConnectionClosed:
                self._connected = False
                yield {"type": "error", "code": "disconnected", "message": "Connection lost"}
                return

            event_type = event.get("type")
            yield event

            # Track session from done events
            if event_type == ServerEventType.DONE:
                self._session_id = session_id or self._session_id
                return
            elif event_type == ServerEventType.ERROR:
                return

    async def send_tool_approval(self, call_id: str, approved: bool) -> None:
        """Send tool approval response to server."""
        if not self.connected:
            return
        await self._ws.send(json.dumps({
            "type": "tool_approval",
            "call_id": call_id,
            "approved": approved,
        }))

    async def send_cancel(self) -> None:
        """Cancel current generation."""
        if not self.connected:
            return
        await self._ws.send(json.dumps({"type": "cancel"}))

    async def send_ping(self) -> bool:
        """Send keepalive ping, return True if pong received."""
        if not self.connected:
            return False
        try:
            await self._ws.send(json.dumps({"type": "ping"}))
            raw = await asyncio.wait_for(self._ws.recv(), timeout=5.0)
            data = json.loads(raw)
            return data.get("type") == "pong"
        except Exception:
            return False

    async def fetch_agent_theme(self) -> AgentTheme:
        """Fetch the active agent's theme from the V2 API. Falls back to defaults."""
        try:
            token = get_stored_token()
            async with httpx.AsyncClient(verify=self.verify_ssl) as http:
                resp = await http.get(
                    f"{self.server_url}/v2/agents/{self.mode}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    identity = data.get("identity", {})
                    return AgentTheme(
                        name=identity.get("name", self.mode),
                        color_hex=identity.get("gradientColor1", "#FF9500"),
                        gradient_secondary=identity.get("gradientColor2"),
                    )
        except Exception:
            pass
        return AgentTheme.for_agent(self.mode)

    async def disconnect(self) -> None:
        """Cleanly close the WebSocket connection."""
        self._connected = False
        await self._close_ws()

    async def reconnect(self, max_attempts: int = 3) -> bool:
        """
        Attempt to reconnect with exponential backoff.

        Returns True if reconnection succeeded.
        """
        await self._close_ws()
        self._connected = False

        for attempt in range(max_attempts):
            delay = 2 ** attempt  # 1s, 2s, 4s
            await asyncio.sleep(delay)
            try:
                await self.connect()
                return True
            except (ConnectionError, AuthenticationError):
                continue
        return False

    async def _close_ws(self) -> None:
        """Close WebSocket if open."""
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
