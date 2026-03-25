"""
Chat routes for Hestia API.

Main conversation endpoint for interacting with Hestia.
Includes REST (POST /v1/chat) and SSE streaming (POST /v1/chat/stream).
"""

import json
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from hestia.api.schemas import (
    ChatRequest,
    ChatResponse,
    ResponseTypeEnum,
    ModeEnum,
    ResponseMetrics,
    ResponseError,
    ErrorResponse,
)
from hestia.api.schemas.chat import AgentBylineSchema
from hestia.api.middleware.auth import get_device_token
from hestia.orchestration.handler import get_request_handler
from hestia.orchestration.models import Request, RequestSource, Mode, ResponseType
from hestia.api.errors import sanitize_for_log
from hestia.outcomes import get_outcome_manager
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


async def _get_last_chunk_ids() -> list:
    """Get chunk IDs from the last memory retrieval (Sprint 15 feedback loop)."""
    try:
        from hestia.memory import get_memory_manager
        memory = await get_memory_manager()
        return getattr(memory, '_last_retrieved_chunk_ids', [])
    except Exception:
        return []


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

        # Wire privacy control
        internal_request.force_local = request.force_local

        # Add context hints if provided
        if request.context_hints:
            internal_request.context_hints = request.context_hints

        # Forward client metadata (voice journal source, agent hint, etc.)
        if request.metadata:
            internal_request.context_hints.update({
                k: v for k, v in request.metadata.items()
                if k in ("source", "input_mode", "agent_hint", "duration")
            })

        # Detect implicit signal from previous response (Learning Cycle)
        try:
            outcome_mgr = await get_outcome_manager()
            await outcome_mgr.detect_implicit_signal(
                session_id=session_id,
                user_id=device_id,
                new_message_content=request.message,
            )
        except Exception:
            pass  # Outcome tracking must never break chat

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
            bylines=[
                AgentBylineSchema(
                    agent=b.agent.value,
                    contribution=b.contribution_type,
                    summary=b.summary,
                )
                for b in response.bylines
            ] if response.bylines else None,
            hallucination_risk=response.hallucination_risk,
        )

        # Track outcome for Learning Cycle
        try:
            outcome_mgr = await get_outcome_manager()
            await outcome_mgr.track_response(
                user_id=device_id,
                device_id=device_id,
                session_id=session_id,
                message_id=request_id,
                response_content=response.content[:500] if response.content else None,
                response_type=api_response.response_type.value,
                duration_ms=response.duration_ms or 0,
                metadata={
                    "mode": api_response.mode.value,
                    "tool_calls": len(response.tool_calls) if response.tool_calls else 0,
                    "tokens_out": response.tokens_out or 0,
                    "retrieved_chunk_ids": await _get_last_chunk_ids(),
                },
            )
        except Exception:
            pass  # Outcome tracking must never break chat

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


# ─────────────────────────────────────────────────────────────────────────────
# SSE Streaming Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/stream",
    summary="Send a message with streaming response",
    description=(
        "Send a message to Hestia and receive a Server-Sent Events stream. "
        "Events include status updates, response tokens, tool results, and "
        "a final done event with metrics."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
async def send_message_stream(
    request: ChatRequest,
    device_id: str = Depends(get_device_token),
) -> StreamingResponse:
    """
    SSE streaming chat endpoint for iOS/macOS clients.

    Reuses the same handler.handle_streaming() pipeline as the CLI WebSocket,
    formatting each event as an SSE frame (event: type, data: JSON).

    Event types:
        status  — Pipeline stage progress (preparing, inference, tools)
        token   — Streaming response token
        tool_result — Tool execution result
        insight — Metadata (cloud routing, synthesis)
        clear_stream — Signal to discard buffered tokens (tool re-synthesis)
        done    — Final event with metrics, mode, session_id
        error   — Error during processing
    """
    request_id = f"req-{uuid4().hex[:12]}"
    session_id = request.session_id or f"sess-{uuid4().hex[:12]}"

    logger.info(
        "Chat stream request received",
        component=LogComponent.API,
        data={
            "request_id": request_id,
            "session_id": session_id,
            "device_id": device_id,
            "message_length": len(request.message),
        },
    )

    async def event_generator():
        try:
            handler = await get_request_handler()

            # Build internal request (same as REST endpoint)
            internal_request = Request.create(
                content=request.message,
                source=RequestSource.API,
                session_id=session_id,
                device_id=request.device_id or device_id,
            )
            internal_request.id = request_id
            internal_request.force_local = request.force_local
            if request.context_hints:
                internal_request.context_hints = request.context_hints

            # Forward client metadata (voice journal source, agent hint, etc.)
            if request.metadata:
                internal_request.context_hints.update({
                    k: v for k, v in request.metadata.items()
                    if k in ("source", "input_mode", "agent_hint", "duration")
                })

            # Detect implicit signal from previous response (Learning Cycle)
            try:
                outcome_mgr = await get_outcome_manager()
                await outcome_mgr.detect_implicit_signal(
                    session_id=session_id,
                    user_id=device_id,
                    new_message_content=request.message,
                )
            except Exception:
                pass

            # Stream events from handler
            async for event in handler.handle_streaming(internal_request):
                event_type = event.get("type", "status")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"

                # Track outcome on done event (Learning Cycle)
                if event_type == "done":
                    try:
                        outcome_mgr = await get_outcome_manager()
                        await outcome_mgr.track_response(
                            user_id=device_id,
                            device_id=device_id,
                            session_id=session_id,
                            message_id=request_id,
                            response_content=None,  # Content already streamed
                            response_type="text",
                            duration_ms=event.get("metrics", {}).get("duration_ms", 0),
                            metadata={
                                "mode": event.get("mode", "tia"),
                                "streaming": True,
                                "tokens_out": event.get("metrics", {}).get("tokens_out", 0),
                                "retrieved_chunk_ids": await _get_last_chunk_ids(),
                            },
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.error(
                f"SSE stream error: {sanitize_for_log(e)}",
                component=LogComponent.API,
                data={"request_id": request_id},
            )
            error_event = {
                "type": "error",
                "code": "internal_error",
                "message": "An error occurred processing your request.",
                "request_id": request_id,
            }
            yield f"event: error\ndata: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
            "X-Accel-Buffering": "no",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Agentic Coding Endpoint (Sprint 13 WS4)
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/agentic",
    summary="Agentic coding session with iterative tool loop",
    description=(
        "Send a coding task to Hestia. Unlike /chat and /stream, this endpoint "
        "runs an iterative tool loop: the model calls tools, sees results, and "
        "calls more tools until the task is complete or a safety limit is reached."
    ),
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
    },
)
async def send_agentic_request(
    request: ChatRequest,
    device_id: str = Depends(get_device_token),
) -> StreamingResponse:
    """
    Agentic coding SSE endpoint.

    Streams events: status, token, tool_start, tool_result, agentic_done, error.
    """
    from hestia.orchestration import get_request_handler
    from hestia.orchestration.models import Request, RequestSource, Mode

    request_id = f"agentic-{uuid4().hex[:12]}"
    session_id = request.session_id or f"sess-{uuid4().hex[:12]}"

    handler = await get_request_handler()

    # Use Request.create() like other chat endpoints for consistent mode detection
    hestia_request = Request.create(
        content=request.message,
        source=RequestSource.API,
        session_id=session_id,
        device_id=request.device_id or device_id,
    )
    hestia_request.id = request_id
    hestia_request.force_local = False  # Agentic always uses cloud

    # Override mode if explicitly provided by the client
    if request.mode:
        hestia_request.mode = Mode(request.mode)

    async def event_generator():
        try:
            async for event in handler.handle_agentic(hestia_request):
                event_type = event.get("type", "status")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
        except Exception as e:
            logger.error(
                f"Agentic stream error: {sanitize_for_log(e)}",
                component=LogComponent.API,
                data={"request_id": request_id},
            )
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'agentic_error', 'message': 'Agentic session failed.'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Request-ID": request_id,
            "X-Accel-Buffering": "no",
        },
    )
