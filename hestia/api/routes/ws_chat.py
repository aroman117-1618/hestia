"""
WebSocket chat route for Hestia CLI streaming.

Provides bidirectional streaming chat over WebSocket with:
- JWT auth via first message (not query params)
- Token-by-token response streaming
- Interactive tool approval mid-stream
- Keepalive ping/pong
- Rate limiting and idle timeout
"""

import asyncio
import time
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from hestia.api.middleware.auth import verify_device_token, check_device_revocation, AuthError
from hestia.api.errors import sanitize_for_log
from hestia.orchestration.handler import get_request_handler
from hestia.orchestration.models import Request, RequestSource, Mode
from hestia.logging import get_logger, LogComponent

router = APIRouter(tags=["websocket"])
logger = get_logger()

# Security limits
AUTH_TIMEOUT_SECONDS = 10
IDLE_TIMEOUT_SECONDS = 1800  # 30 minutes (matches session TTL)
MAX_MESSAGE_SIZE = 65536  # 64KB
MAX_MESSAGES_PER_MINUTE = 60


class WSConnection:
    """
    Manages state for a single WebSocket connection.

    Tracks authentication, rate limiting, and tool approval coordination.
    """

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.device_id: Optional[str] = None
        self.authenticated = False
        self.session_id: Optional[str] = None
        self._message_timestamps: list[float] = []
        self._cancel_event = asyncio.Event()
        self._tool_approval_queue: asyncio.Queue = asyncio.Queue()
        self._last_activity = time.time()

    def check_rate_limit(self) -> bool:
        """Check if client is within rate limit. Returns True if OK."""
        now = time.time()
        # Remove timestamps older than 60 seconds
        self._message_timestamps = [t for t in self._message_timestamps if now - t < 60]
        if len(self._message_timestamps) >= MAX_MESSAGES_PER_MINUTE:
            return False
        self._message_timestamps.append(now)
        return True

    def touch(self) -> None:
        """Update last activity timestamp."""
        self._last_activity = time.time()

    @property
    def idle_seconds(self) -> float:
        """Seconds since last activity."""
        return time.time() - self._last_activity


@router.websocket("/v1/ws/chat")
async def ws_chat(websocket: WebSocket):
    """
    WebSocket endpoint for streaming chat with Hestia.

    Protocol:
    1. Client connects, server accepts
    2. Client sends {"type": "auth", "token": "<JWT>"} within 10 seconds
    3. Server responds with {"type": "auth_result", ...}
    4. Client sends chat messages, server streams responses
    5. Tool approval is handled bidirectionally mid-stream
    """
    await websocket.accept()
    conn = WSConnection(websocket)

    try:
        # Phase 1: Authentication
        device_id = await _authenticate(conn)
        if device_id is None:
            return  # Auth failed, connection closed

        conn.device_id = device_id
        conn.authenticated = True

        logger.info(
            f"WebSocket client authenticated",
            component=LogComponent.API,
            data={"device_id": device_id},
        )

        # Phase 2: Message loop
        await _message_loop(conn)

    except WebSocketDisconnect:
        logger.info(
            f"WebSocket client disconnected",
            component=LogComponent.API,
            data={"device_id": conn.device_id},
        )
    except Exception as e:
        logger.error(
            f"WebSocket error: {type(e).__name__}",
            component=LogComponent.API,
            data={"device_id": conn.device_id, "error_type": type(e).__name__},
        )
        try:
            await conn.websocket.send_json({
                "type": "error",
                "code": "internal_error",
                "message": "An unexpected error occurred.",
            })
        except Exception:
            pass
    finally:
        if conn.websocket.client_state == WebSocketState.CONNECTED:
            try:
                await conn.websocket.close()
            except Exception:
                pass


async def _authenticate(conn: WSConnection) -> Optional[str]:
    """
    Authenticate the WebSocket connection via first message.

    Returns device_id on success, None on failure (connection closed).
    """
    try:
        # Wait for auth message with timeout
        raw = await asyncio.wait_for(
            conn.websocket.receive_json(),
            timeout=AUTH_TIMEOUT_SECONDS,
        )

        if not isinstance(raw, dict) or raw.get("type") != "auth":
            await conn.websocket.send_json({
                "type": "auth_result",
                "success": False,
                "error": "First message must be {\"type\": \"auth\", \"token\": \"...\"}",
            })
            await conn.websocket.close(code=4001, reason="Auth required")
            return None

        token = raw.get("token", "")
        if not token:
            await conn.websocket.send_json({
                "type": "auth_result",
                "success": False,
                "error": "Missing token",
            })
            await conn.websocket.close(code=4001, reason="Missing token")
            return None

        # Verify JWT
        payload = verify_device_token(token)
        device_id = payload["device_id"]

        # Check revocation
        await check_device_revocation(device_id)

        # Load trust tiers for the auth response
        trust_tiers_dict = {}
        try:
            from hestia.user import get_user_manager
            user_mgr = await get_user_manager()
            user_settings = await user_mgr.get_settings()
            trust_tiers_dict = user_settings.get_tool_trust_tiers().to_dict()
        except Exception:
            pass  # Defaults will be used

        # Auth success
        await conn.websocket.send_json({
            "type": "auth_result",
            "success": True,
            "device_id": device_id,
            "trust_tiers": trust_tiers_dict,
        })

        conn.touch()
        return device_id

    except asyncio.TimeoutError:
        logger.warning(
            "WebSocket auth timeout",
            component=LogComponent.API,
        )
        try:
            await conn.websocket.send_json({
                "type": "auth_result",
                "success": False,
                "error": "Authentication timeout (10s)",
            })
            await conn.websocket.close(code=4001, reason="Auth timeout")
        except Exception:
            pass
        return None

    except AuthError as e:
        try:
            await conn.websocket.send_json({
                "type": "auth_result",
                "success": False,
                "error": e.message,
            })
            await conn.websocket.close(code=4003, reason="Auth failed")
        except Exception:
            pass
        return None

    except Exception as e:
        logger.error(
            f"WebSocket auth error: {type(e).__name__}",
            component=LogComponent.API,
        )
        try:
            await conn.websocket.close(code=4000, reason="Auth error")
        except Exception:
            pass
        return None


async def _message_loop(conn: WSConnection) -> None:
    """
    Main message processing loop for an authenticated connection.
    """
    while True:
        # Check idle timeout
        if conn.idle_seconds > IDLE_TIMEOUT_SECONDS:
            await conn.websocket.send_json({
                "type": "error",
                "code": "idle_timeout",
                "message": f"Connection idle for {IDLE_TIMEOUT_SECONDS}s. Disconnecting.",
            })
            await conn.websocket.close(code=4008, reason="Idle timeout")
            return

        # Receive next message
        try:
            raw = await asyncio.wait_for(
                conn.websocket.receive_json(),
                timeout=IDLE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            # Idle timeout during receive
            await conn.websocket.send_json({
                "type": "error",
                "code": "idle_timeout",
                "message": "Connection idle. Disconnecting.",
            })
            await conn.websocket.close(code=4008, reason="Idle timeout")
            return

        conn.touch()

        if not isinstance(raw, dict):
            await conn.websocket.send_json({
                "type": "error",
                "code": "invalid_message",
                "message": "Messages must be JSON objects.",
            })
            continue

        msg_type = raw.get("type")

        # Rate limiting
        if not conn.check_rate_limit():
            await conn.websocket.send_json({
                "type": "error",
                "code": "rate_limited",
                "message": f"Rate limit exceeded ({MAX_MESSAGES_PER_MINUTE}/minute).",
            })
            continue

        # Dispatch by message type
        if msg_type == "ping":
            await conn.websocket.send_json({"type": "pong"})

        elif msg_type == "message":
            await _handle_chat_message(conn, raw)

        elif msg_type == "tool_approval":
            # Route to the approval queue for the streaming handler
            await conn._tool_approval_queue.put(raw)

        elif msg_type == "cancel":
            conn._cancel_event.set()

        else:
            await conn.websocket.send_json({
                "type": "error",
                "code": "unknown_message_type",
                "message": f"Unknown message type: {msg_type}",
            })


async def _handle_chat_message(conn: WSConnection, raw: dict) -> None:
    """
    Process a chat message through the streaming handler.
    """
    content = raw.get("content", "").strip()
    if not content:
        await conn.websocket.send_json({
            "type": "error",
            "code": "empty_message",
            "message": "Message content cannot be empty.",
        })
        return

    if len(content) > MAX_MESSAGE_SIZE:
        await conn.websocket.send_json({
            "type": "error",
            "code": "message_too_large",
            "message": f"Message exceeds {MAX_MESSAGE_SIZE} bytes.",
        })
        return

    # Build internal Request
    session_id = raw.get("session_id") or conn.session_id
    mode_str = raw.get("mode", "tia")
    try:
        mode = Mode(mode_str)
    except ValueError:
        mode = Mode.TIA

    request = Request.create(
        content=content,
        mode=mode,
        source=RequestSource.CLI,
        session_id=session_id,
        device_id=conn.device_id,
        force_local=raw.get("force_local", False),
        context_hints=raw.get("context_hints", {}),
    )

    # Reset cancel event for this generation
    conn._cancel_event.clear()

    # Clear any stale tool approvals
    while not conn._tool_approval_queue.empty():
        try:
            conn._tool_approval_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    # Tool approval callback for the streaming handler
    async def tool_approval_callback(
        call_id: str, tool_name: str, arguments: dict, tier: str
    ) -> bool:
        """Send tool approval request to client, wait for response."""
        # Send approval request
        await conn.websocket.send_json({
            "type": "tool_request",
            "call_id": call_id,
            "tool_name": tool_name,
            "arguments": arguments,
            "tier": tier,
        })

        # Wait for approval (with 30s timeout)
        try:
            response = await asyncio.wait_for(
                conn._tool_approval_queue.get(),
                timeout=30.0,
            )
            return response.get("approved", False)
        except asyncio.TimeoutError:
            logger.warning(
                f"Tool approval timeout for {tool_name}",
                component=LogComponent.API,
                data={"device_id": conn.device_id, "call_id": call_id},
            )
            return False

    # Stream the response
    try:
        handler = await get_request_handler()

        async for event in handler.handle_streaming(
            request,
            tool_approval_callback=tool_approval_callback,
        ):
            # Check for cancellation
            if conn._cancel_event.is_set():
                await conn.websocket.send_json({
                    "type": "done",
                    "request_id": request.id,
                    "metrics": {"cancelled": True},
                    "mode": mode_str,
                })
                break

            # Forward event to client
            await conn.websocket.send_json(event)

            # Track session ID from done event
            if event.get("type") == "done":
                conn.session_id = session_id or request.session_id

    except Exception as e:
        logger.error(
            f"Streaming chat error: {type(e).__name__}",
            component=LogComponent.API,
            data={"device_id": conn.device_id, "error_type": type(e).__name__},
        )
        await conn.websocket.send_json({
            "type": "error",
            "code": "streaming_error",
            "message": "An error occurred during message processing.",
        })
