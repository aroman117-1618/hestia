"""
Outcomes API routes.

Endpoints for viewing chat response outcomes, submitting explicit
feedback, and manually tracking responses. Outcome data feeds the
Learning Cycle for continuous improvement.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from hestia.api.middleware.auth import get_device_token
from hestia.api.errors import sanitize_for_log
from hestia.outcomes.manager import get_outcome_manager
from hestia.outcomes.models import OutcomeFeedback
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/outcomes", tags=["outcomes"])
logger = get_logger()

# Default user ID until multi-user ships
DEFAULT_USER_ID = "user-default"


# =============================================================================
# Request/Response Schemas
# =============================================================================

class OutcomeResponse(BaseModel):
    """A single outcome record."""
    id: str
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    response_type: Optional[str] = None
    duration_ms: Optional[int] = None
    feedback: Optional[str] = None
    feedback_note: Optional[str] = None
    implicit_signal: Optional[str] = None
    elapsed_to_next_ms: Optional[int] = None
    timestamp: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OutcomeListResponse(BaseModel):
    """Outcome listing response."""
    outcomes: List[OutcomeResponse]
    count: int


class OutcomeStatsResponse(BaseModel):
    """Aggregated outcome statistics."""
    total: int
    positive_count: int
    negative_count: int
    correction_count: int
    avg_duration_ms: int


class FeedbackRequest(BaseModel):
    """Request to submit feedback on an outcome."""
    feedback: str = Field(
        ...,
        description=f"Feedback type. Must be one of: {[f.value for f in OutcomeFeedback]}",
    )
    note: Optional[str] = Field(None, description="Optional feedback note")


class TrackRequest(BaseModel):
    """Request to manually track a response outcome."""
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    response_content: Optional[str] = None
    response_type: Optional[str] = None
    duration_ms: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "",
    response_model=OutcomeListResponse,
    summary="List outcomes",
    description="Get outcome records with optional filters.",
)
async def list_outcomes(
    session_id: Optional[str] = Query(None, description="Filter by session"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Filter by days"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_device_token),
):
    """Get outcome records with optional filters."""
    manager = await get_outcome_manager()

    try:
        outcomes = await manager.get_outcomes(
            user_id=DEFAULT_USER_ID,
            session_id=session_id,
            days=days,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(
            f"Outcome list failed: {sanitize_for_log(e)}",
            component=LogComponent.OUTCOMES,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch outcomes",
        )

    return OutcomeListResponse(
        outcomes=[OutcomeResponse(**_outcome_to_response(o)) for o in outcomes],
        count=len(outcomes),
    )


@router.get(
    "/stats",
    response_model=OutcomeStatsResponse,
    summary="Get outcome stats",
    description="Get aggregated outcome statistics for a time period.",
)
async def get_stats(
    days: int = Query(7, ge=1, le=365, description="Number of days to aggregate"),
    device_id: str = Depends(get_device_token),
):
    """Get aggregated outcome statistics."""
    manager = await get_outcome_manager()

    try:
        stats = await manager.get_stats(user_id=DEFAULT_USER_ID, days=days)
    except Exception as e:
        logger.error(
            f"Outcome stats failed: {sanitize_for_log(e)}",
            component=LogComponent.OUTCOMES,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch outcome stats",
        )

    return OutcomeStatsResponse(**stats)


@router.get(
    "/{outcome_id}",
    response_model=OutcomeResponse,
    summary="Get outcome detail",
    description="Get a single outcome record by ID.",
)
async def get_outcome(
    outcome_id: str,
    device_id: str = Depends(get_device_token),
):
    """Get a single outcome record."""
    manager = await get_outcome_manager()

    try:
        outcome = await manager.get_outcome(
            outcome_id=outcome_id,
            user_id=DEFAULT_USER_ID,
        )
    except Exception as e:
        logger.error(
            f"Outcome fetch failed for {outcome_id}: {sanitize_for_log(e)}",
            component=LogComponent.OUTCOMES,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch outcome",
        )

    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outcome not found",
        )

    return OutcomeResponse(**_outcome_to_response(outcome))


@router.post(
    "/{outcome_id}/feedback",
    response_model=OutcomeResponse,
    summary="Submit feedback",
    description="Submit explicit feedback on an outcome (positive/negative/correction).",
)
async def submit_feedback(
    outcome_id: str,
    request: FeedbackRequest,
    device_id: str = Depends(get_device_token),
):
    """Submit explicit feedback on an outcome."""
    manager = await get_outcome_manager()

    # Validate feedback value
    valid_values = [f.value for f in OutcomeFeedback]
    if request.feedback not in valid_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid feedback. Must be one of: {valid_values}",
        )

    try:
        success = await manager.record_feedback(
            outcome_id=outcome_id,
            user_id=DEFAULT_USER_ID,
            feedback=request.feedback,
            note=request.note,
        )
    except Exception as e:
        logger.error(
            f"Feedback update failed for {outcome_id}: {sanitize_for_log(e)}",
            component=LogComponent.OUTCOMES,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update feedback",
        )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outcome not found",
        )

    # Return updated outcome
    outcome = await manager.get_outcome(outcome_id, DEFAULT_USER_ID)
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Outcome not found",
        )

    return OutcomeResponse(**_outcome_to_response(outcome))


@router.post(
    "/track",
    response_model=OutcomeResponse,
    summary="Track response",
    description="Manually track a chat response outcome.",
)
async def track_response(
    request: TrackRequest,
    device_id: str = Depends(get_device_token),
):
    """Manually track a chat response outcome."""
    manager = await get_outcome_manager()

    try:
        outcome_id = await manager.track_response(
            user_id=DEFAULT_USER_ID,
            device_id=device_id,
            session_id=request.session_id,
            message_id=request.message_id,
            response_content=request.response_content,
            response_type=request.response_type,
            duration_ms=request.duration_ms,
            metadata=request.metadata,
        )
    except Exception as e:
        logger.error(
            f"Outcome tracking failed: {sanitize_for_log(e)}",
            component=LogComponent.OUTCOMES,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to track outcome",
        )

    # Return the created outcome
    outcome = await manager.get_outcome(outcome_id, DEFAULT_USER_ID)
    if outcome is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tracked outcome",
        )

    return OutcomeResponse(**_outcome_to_response(outcome))


# =============================================================================
# Helpers
# =============================================================================

def _outcome_to_response(outcome: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a raw outcome dict to response fields."""
    return {
        "id": outcome["id"],
        "session_id": outcome.get("session_id"),
        "message_id": outcome.get("message_id"),
        "response_type": outcome.get("response_type"),
        "duration_ms": outcome.get("duration_ms"),
        "feedback": outcome.get("feedback"),
        "feedback_note": outcome.get("feedback_note"),
        "implicit_signal": outcome.get("implicit_signal"),
        "elapsed_to_next_ms": outcome.get("elapsed_to_next_ms"),
        "timestamp": outcome.get("timestamp"),
        "metadata": outcome.get("metadata", {}),
    }
