"""
Chat routes for Hestia API.

Main conversation endpoint for interacting with Hestia.
"""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status

from hestia.api.schemas import (
    ChatRequest,
    ChatResponse,
    ResponseTypeEnum,
    ModeEnum,
    ResponseMetrics,
    ResponseError,
    ErrorResponse,
)
from hestia.api.middleware.auth import get_device_token
from hestia.orchestration.handler import get_request_handler
from hestia.orchestration.models import Request, RequestSource, Mode, ResponseType
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/chat", tags=["chat"])
logger = get_logger()


def _mode_to_enum(mode: Mode) -> ModeEnum:
    """Convert internal Mode to API ModeEnum."""
    return ModeEnum(mode.value)


def _response_type_to_enum(rt: ResponseType) -> ResponseTypeEnum:
    """Convert internal ResponseType to API ResponseTypeEnum."""
    mapping = {
        ResponseType.TEXT: ResponseTypeEnum.TEXT,
        ResponseType.ERROR: ResponseTypeEnum.ERROR,
        ResponseType.TOOL_CALL: ResponseTypeEnum.TOOL_CALL,
        ResponseType.CLARIFICATION: ResponseTypeEnum.CLARIFICATION,
        ResponseType.STRUCTURED: ResponseTypeEnum.TEXT,  # Map structured to text
    }
    return mapping.get(rt, ResponseTypeEnum.TEXT)


@router.post(
    "",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Send a message",
    description="Send a message to Hestia and receive a response."
)
async def send_message(
    request: ChatRequest,
    device_id: str = Depends(get_device_token),
) -> ChatResponse:
    """
    Send a message to Hestia.

    This is the main chat endpoint. The message is processed through:
    1. Validation
    2. Mode detection (from @tia, @mira, @olly invocations)
    3. Memory retrieval for context
    4. Inference via Ollama
    5. Response validation
    6. Memory storage

    Args:
        request: The chat request with message and optional context.
        device_id: Device ID from authentication token.

    Returns:
        ChatResponse with Hestia's response.
    """
    # Generate IDs
    request_id = f"req-{uuid4().hex[:12]}"
    session_id = request.session_id or f"sess-{uuid4().hex[:12]}"

    logger.info(
        "Chat request received",
        component=LogComponent.API,
        data={
            "request_id": request_id,
            "session_id": session_id,
            "device_id": device_id,
            "message_length": len(request.message),
        }
    )

    try:
        # Get request handler
        handler = await get_request_handler()

        # Build internal request
        internal_request = Request.create(
            content=request.message,
            source=RequestSource.API,
            session_id=session_id,
            device_id=request.device_id or device_id,
        )
        # Override the auto-generated ID with ours
        internal_request.id = request_id

        # Add context hints if provided
        if request.context_hints:
            internal_request.context_hints = request.context_hints

        # Process request
        response = await handler.handle(internal_request)

        # Build API response
        api_response = ChatResponse(
            request_id=response.request_id,
            content=response.content,
            response_type=_response_type_to_enum(response.response_type),
            mode=_mode_to_enum(response.mode),
            session_id=session_id,
            timestamp=response.timestamp,
            metrics=ResponseMetrics(
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
                duration_ms=response.duration_ms,
            ),
            tool_calls=response.tool_calls,
            error=ResponseError(
                code=response.error_code,
                message=response.error_message,
            ) if response.error_code else None,
        )

        logger.info(
            "Chat response sent",
            component=LogComponent.API,
            data={
                "request_id": request_id,
                "response_type": api_response.response_type.value,
                "tokens_out": response.tokens_out,
                "duration_ms": response.duration_ms,
            }
        )

        return api_response

    except ValueError as e:
        logger.warning(
            f"Chat request validation error: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"request_id": request_id},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_error",
                "message": "Invalid chat request.",
                "request_id": request_id,
            }
        )

    except Exception as e:
        logger.error(
            f"Chat request failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"request_id": request_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "An error occurred processing your request.",
                "request_id": request_id,
            }
        )
