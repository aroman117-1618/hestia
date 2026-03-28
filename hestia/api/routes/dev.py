"""
Dev session management routes for Hestia API.

Agentic Dev System — REST endpoints for creating and managing autonomous
development sessions, approvals, cancellations, and event streams.
"""

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from hestia.api.middleware.auth import get_device_token
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/dev", tags=["dev"])
logger = get_logger()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    title: str
    description: str
    source: str = "cli"
    source_ref: Optional[str] = None
    priority: int = 3


class SessionResponse(BaseModel):
    id: str
    title: str
    description: str
    state: str
    source: str
    priority: int
    branch_name: Optional[str]
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    total_tokens: int
    retry_count: int
    replan_count: int


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
    count: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _session_to_response(session) -> SessionResponse:
    """Convert a DevSession dataclass to API response."""
    return SessionResponse(
        id=session.id,
        title=session.title,
        description=session.description,
        state=session.state.value,
        source=session.source.value,
        priority=session.priority.value,
        branch_name=session.branch_name,
        created_at=session.created_at,
        started_at=session.started_at,
        completed_at=session.completed_at,
        total_tokens=session.total_tokens,
        retry_count=session.retry_count,
        replan_count=session.replan_count,
    )


# ---------------------------------------------------------------------------
# POST /v1/dev/sessions
# ---------------------------------------------------------------------------

@router.post(
    "/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Create dev session",
    description="Create a new agentic development session in QUEUED state.",
)
async def create_session(
    request: CreateSessionRequest,
    device_id: str = Depends(get_device_token),
) -> SessionResponse:
    """Create a new dev session."""
    try:
        from hestia.dev import get_dev_session_manager
        from hestia.dev.models import DevSessionSource, DevPriority

        manager = await get_dev_session_manager()
        session = await manager.create_session(
            title=request.title,
            description=request.description,
            source=DevSessionSource(request.source),
            source_ref=request.source_ref,
            priority=DevPriority(request.priority),
        )

        logger.info(
            f"Dev session created: {session.id!r}",
            component=LogComponent.DEV,
            data={"device_id": device_id, "session_id": session.id, "title": session.title},
        )

        return _session_to_response(session)

    except (ValueError, KeyError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_request", "message": "Invalid session parameters."},
        )

    except Exception as e:
        logger.error(
            f"Failed to create dev session: {sanitize_for_log(e)}",
            component=LogComponent.DEV,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to create dev session."},
        )


# ---------------------------------------------------------------------------
# GET /v1/dev/sessions
# ---------------------------------------------------------------------------

@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="List dev sessions",
    description="List dev sessions, optionally filtered by state.",
)
async def list_sessions(
    state: Optional[str] = Query(None, description="Filter by session state"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of results"),
    device_id: str = Depends(get_device_token),
) -> SessionListResponse:
    """List dev sessions."""
    try:
        from hestia.dev import get_dev_session_manager
        from hestia.dev.models import DevSessionState

        manager = await get_dev_session_manager()

        state_filter = DevSessionState(state) if state else None
        sessions = await manager.list_sessions(state=state_filter, limit=limit)

        logger.info(
            "Dev sessions listed",
            component=LogComponent.DEV,
            data={"device_id": device_id, "count": len(sessions), "state_filter": state},
        )

        return SessionListResponse(
            sessions=[_session_to_response(s) for s in sessions],
            count=len(sessions),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_state", "message": "Invalid session state filter."},
        )

    except Exception as e:
        logger.error(
            f"Failed to list dev sessions: {sanitize_for_log(e)}",
            component=LogComponent.DEV,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to list dev sessions."},
        )


# ---------------------------------------------------------------------------
# GET /v1/dev/sessions/{session_id}
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses={
        404: {"description": "Session not found"},
    },
    summary="Get dev session",
    description="Get a dev session by ID.",
)
async def get_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
) -> SessionResponse:
    """Get a single dev session by ID."""
    try:
        from hestia.dev import get_dev_session_manager

        manager = await get_dev_session_manager()
        session = await manager.get_session(session_id)

        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "session_not_found", "message": f"Session '{session_id}' not found."},
            )

        return _session_to_response(session)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to get dev session: {sanitize_for_log(e)}",
            component=LogComponent.DEV,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to get dev session."},
        )


# ---------------------------------------------------------------------------
# POST /v1/dev/sessions/{session_id}/approve
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/approve",
    response_model=SessionResponse,
    responses={
        404: {"description": "Session not found"},
        400: {"description": "Session not in approvable state"},
    },
    summary="Approve dev session",
    description="Approve a PROPOSED session, moving it to EXECUTING.",
)
async def approve_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
) -> SessionResponse:
    """Approve a dev session."""
    try:
        from hestia.dev import get_dev_session_manager

        manager = await get_dev_session_manager()
        session = await manager.approve_session(session_id, approved_by=device_id)

        logger.info(
            f"Dev session approved: {session_id!r}",
            component=LogComponent.DEV,
            data={"device_id": device_id, "session_id": session_id},
        )

        return _session_to_response(session)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_transition", "message": "Session cannot be approved in its current state."},
        )

    except Exception as e:
        logger.error(
            f"Failed to approve dev session: {sanitize_for_log(e)}",
            component=LogComponent.DEV,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to approve dev session."},
        )


# ---------------------------------------------------------------------------
# POST /v1/dev/sessions/{session_id}/cancel
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/cancel",
    response_model=SessionResponse,
    responses={
        404: {"description": "Session not found"},
        400: {"description": "Session cannot be cancelled"},
    },
    summary="Cancel dev session",
    description="Cancel a dev session.",
)
async def cancel_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
) -> SessionResponse:
    """Cancel a dev session."""
    try:
        from hestia.dev import get_dev_session_manager

        manager = await get_dev_session_manager()
        session = await manager.cancel_session(session_id)

        logger.info(
            f"Dev session cancelled: {session_id!r}",
            component=LogComponent.DEV,
            data={"device_id": device_id, "session_id": session_id},
        )

        return _session_to_response(session)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_transition", "message": "Session cannot be cancelled in its current state."},
        )

    except Exception as e:
        logger.error(
            f"Failed to cancel dev session: {sanitize_for_log(e)}",
            component=LogComponent.DEV,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to cancel dev session."},
        )


# ---------------------------------------------------------------------------
# GET /v1/dev/proposals
# ---------------------------------------------------------------------------

@router.get(
    "/proposals",
    summary="List pending proposals",
    description="List all sessions in PROPOSED state awaiting approval.",
)
async def list_pending_proposals(
    device_id: str = Depends(get_device_token),
) -> dict:
    """List all pending proposals."""
    try:
        from hestia.dev import get_dev_session_manager

        manager = await get_dev_session_manager()
        proposals = await manager.list_pending_proposals()

        return {"proposals": [_session_to_response(p).model_dump() for p in proposals]}

    except Exception as e:
        logger.error(
            f"Failed to list proposals: {sanitize_for_log(e)}",
            component=LogComponent.DEV,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to list proposals."},
        )


# ---------------------------------------------------------------------------
# GET /v1/dev/sessions/{session_id}/events
# ---------------------------------------------------------------------------

@router.get(
    "/sessions/{session_id}/events",
    responses={
        404: {"description": "Session not found"},
    },
    summary="Get session events",
    description="Get all events for a dev session.",
)
async def get_events(
    session_id: str,
    device_id: str = Depends(get_device_token),
) -> dict:
    """Get events for a dev session."""
    try:
        from hestia.dev import get_dev_session_manager

        manager = await get_dev_session_manager()

        # Verify session exists
        session = await manager.get_session(session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "session_not_found", "message": f"Session '{session_id}' not found."},
            )

        events = await manager.get_events(session_id)

        return {
            "events": [
                {
                    "id": e.id,
                    "session_id": e.session_id,
                    "event_type": e.event_type.value,
                    "agent_tier": e.agent_tier.value if e.agent_tier else None,
                    "timestamp": e.timestamp,
                    "data": e.data,
                }
                for e in events
            ]
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to get dev session events: {sanitize_for_log(e)}",
            component=LogComponent.DEV,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to get session events."},
        )


# ---------------------------------------------------------------------------
# POST /v1/dev/sessions/{session_id}/plan
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/plan",
    response_model=SessionResponse,
    responses={
        404: {"description": "Session not found"},
        400: {"description": "Session cannot be planned in current state"},
    },
    summary="Run planning phase",
    description="Run the planning phase for a session (QUEUED → PROPOSED).",
)
async def plan_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
) -> SessionResponse:
    """Run the planning phase for a dev session."""
    try:
        from hestia.dev import get_dev_session_manager

        manager = await get_dev_session_manager()

        # Verify session exists
        session = await manager.get_session(session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "session_not_found", "message": f"Session '{session_id}' not found."},
            )

        orchestrator = await _create_orchestrator(manager)
        session = await orchestrator.run_planning_phase(session_id)

        logger.info(
            f"Dev session planning complete: {session_id!r}",
            component=LogComponent.DEV,
            data={"device_id": device_id, "session_id": session_id},
        )

        return _session_to_response(session)

    except HTTPException:
        raise

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "invalid_transition", "message": "Session cannot be planned in its current state."},
        )

    except Exception as e:
        logger.error(
            f"Failed to plan dev session: {sanitize_for_log(e)}",
            component=LogComponent.DEV,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to plan dev session."},
        )


# ---------------------------------------------------------------------------
# POST /v1/dev/sessions/{session_id}/execute  (SSE)
# ---------------------------------------------------------------------------

@router.post(
    "/sessions/{session_id}/execute",
    responses={
        404: {"description": "Session not found"},
        400: {"description": "Session not in EXECUTING state"},
    },
    summary="Stream execution progress",
    description="Stream execution progress of an approved dev session via SSE.",
)
async def execute_session(
    session_id: str,
    device_id: str = Depends(get_device_token),
) -> StreamingResponse:
    """Stream execution progress of an approved dev session via SSE."""
    from hestia.dev import get_dev_session_manager

    manager = await get_dev_session_manager()

    # Verify session exists before streaming
    session = await manager.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "session_not_found", "message": f"Session '{session_id}' not found."},
        )

    async def event_generator():
        try:
            orchestrator = await _create_orchestrator(manager)
            async for event in orchestrator.run_execution_phase(session_id):
                event_type = event.get("type", "status")
                yield f"event: {event_type}\ndata: {json.dumps(event)}\n\n"
        except ValueError as e:
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'invalid_state', 'message': 'Session is not in an executable state.'})}\n\n"
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error(
                f"Dev session execution stream error: {sanitize_for_log(e)}",
                component=LogComponent.DEV,
                data={"session_id": session_id, "traceback": tb},
            )
            yield f"event: error\ndata: {json.dumps({'type': 'error', 'code': 'execution_error', 'message': 'Dev session execution failed.'})}\n\n"

    logger.info(
        f"Dev session execution started: {session_id!r}",
        component=LogComponent.DEV,
        data={"device_id": device_id, "session_id": session_id},
    )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# Helpers — orchestrator factory
# ---------------------------------------------------------------------------

async def _create_orchestrator(manager):
    """Create a DevOrchestrator with all agent tiers."""
    from hestia.cloud.client import CloudInferenceClient
    from hestia.dev.architect import ArchitectAgent
    from hestia.dev.engineer import EngineerAgent
    from hestia.dev.validator import ValidatorAgent
    from hestia.dev.researcher import ResearcherAgent
    from hestia.dev.proposal import ProposalDelivery
    from hestia.dev.orchestrator import DevOrchestrator

    cloud_client = CloudInferenceClient()

    return DevOrchestrator(
        manager=manager,
        architect=ArchitectAgent(cloud_client=cloud_client),
        engineer=EngineerAgent(cloud_client=cloud_client),
        validator=ValidatorAgent(cloud_client=cloud_client),
        researcher=ResearcherAgent(cloud_client=cloud_client),
        proposal_delivery=ProposalDelivery(),
    )
