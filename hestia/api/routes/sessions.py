"""
Session management routes for Hestia API.

Handles conversation session creation and history.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from hestia.api.schemas import (
    SessionCreateRequest,
    SessionCreateResponse,
    SessionHistoryResponse,
    SessionMessage,
    ModeEnum,
    ErrorResponse,
)
from hestia.api.middleware.auth import get_device_token
from hestia.orchestration.handler import get_request_handler
from hestia.orchestration.mode import get_mode_manager, Mode
from hestia.memory import get_memory_manager
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])
logger = get_logger()


def _mode_to_enum(mode: Mode) -> ModeEnum:
    """Convert internal Mode to API ModeEnum."""
    return ModeEnum(mode.value)


@router.post(
    "",
    response_model=SessionCreateResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
    summary="Create a new session",
    description="Create a new conversation session."
)
async def create_session(
    request: SessionCreateRequest = None,
    device_id: str = Depends(get_device_token),
) -> SessionCreateResponse:
    """
    Create a new conversation session.

    Sessions track conversation history and mode state.

    Args:
        request: Optional session configuration.
        device_id: Device ID from authentication token.

    Returns:
        SessionCreateResponse with new session ID.
    """
    try:
        memory = await get_memory_manager()
        mode_manager = get_mode_manager()

        # Determine initial mode
        initial_mode = mode_manager.current_mode
        if request and request.mode:
            initial_mode = Mode(request.mode.value)
            mode_manager.switch_mode(initial_mode)

        # Start session in memory manager
        session_id = memory.start_session(
            mode=initial_mode.value,
            device_id=request.device_id if request else device_id,
        )

        created_at = datetime.now(timezone.utc)

        logger.info(
            "Session created",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "session_id": session_id,
                "mode": initial_mode.value,
            }
        )

        return SessionCreateResponse(
            session_id=session_id,
            mode=_mode_to_enum(initial_mode),
            created_at=created_at,
        )

    except Exception as e:
        logger.error(
            f"Failed to create session: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to create session.",
            }
        )


@router.get(
    "/{session_id}/history",
    response_model=SessionHistoryResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
    summary="Get session history",
    description="Get the conversation history for a session."
)
async def get_session_history(
    session_id: str,
    device_id: str = Depends(get_device_token),
) -> SessionHistoryResponse:
    """
    Get conversation history for a session.

    Returns all messages exchanged in the session.

    Args:
        session_id: The session ID to retrieve.
        device_id: Device ID from authentication token.

    Returns:
        SessionHistoryResponse with conversation messages.
    """
    try:
        handler = await get_request_handler()

        # Check if session exists in handler's conversation cache
        if session_id in handler._conversations:
            conversation = handler._conversations[session_id]

            messages = [
                SessionMessage(role=msg["role"], content=msg["content"])
                for msg in conversation.messages
            ]

            return SessionHistoryResponse(
                session_id=session_id,
                mode=_mode_to_enum(conversation.mode),
                started_at=conversation.started_at,
                last_activity=conversation.last_activity,
                turn_count=conversation.turn_count,
                messages=messages,
            )

        # Try to reconstruct from memory
        memory = await get_memory_manager()
        chunks = await memory.get_recent(limit=100, session_id=session_id)

        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "session_not_found",
                    "message": f"Session '{session_id}' not found.",
                }
            )

        # Reconstruct messages from chunks
        messages = []
        for chunk in sorted(chunks, key=lambda c: c.timestamp):
            # Parse role from content prefix
            content = chunk.content
            if content.startswith("User: "):
                messages.append(SessionMessage(
                    role="user",
                    content=content[6:],  # Remove "User: " prefix
                ))
            elif content.startswith("Assistant: "):
                messages.append(SessionMessage(
                    role="assistant",
                    content=content[11:],  # Remove "Assistant: " prefix
                ))

        # Get timestamps
        started_at = chunks[0].timestamp if chunks else datetime.now(timezone.utc)
        last_activity = chunks[-1].timestamp if chunks else started_at

        # Get mode from chunks
        mode = ModeEnum.TIA
        if chunks and chunks[0].tags.mode:
            try:
                mode = ModeEnum(chunks[0].tags.mode)
            except ValueError:
                pass

        logger.info(
            "Session history retrieved",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "session_id": session_id,
                "message_count": len(messages),
            }
        )

        return SessionHistoryResponse(
            session_id=session_id,
            mode=mode,
            started_at=started_at,
            last_activity=last_activity,
            turn_count=len(messages) // 2,
            messages=messages,
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to get session history: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"session_id": session_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to retrieve session history.",
            }
        )


@router.delete(
    "/{session_id}",
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
    summary="End a session",
    description="End and clean up a conversation session."
)
async def end_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
) -> dict:
    """
    End a conversation session.

    This cleans up the session from the in-memory cache but preserves
    the conversation history in the memory layer.

    Args:
        session_id: The session ID to end.
        device_id: Device ID from authentication token.

    Returns:
        Success message.
    """
    try:
        handler = await get_request_handler()

        # Remove from conversation cache if present
        if session_id in handler._conversations:
            del handler._conversations[session_id]

        logger.info(
            "Session ended",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "session_id": session_id,
            }
        )

        return {
            "status": "ok",
            "message": f"Session '{session_id}' ended.",
        }

    except Exception as e:
        logger.error(
            f"Failed to end session: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"session_id": session_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to end session.",
            }
        )
