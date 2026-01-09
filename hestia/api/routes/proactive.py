"""
Proactive Intelligence API endpoints.

Provides endpoints for:
- GET /v1/proactive/briefing - Get today's briefing
- GET /v1/proactive/policy - Get interruption policy
- POST /v1/proactive/policy - Update interruption policy
- GET /v1/proactive/patterns - List detected patterns
- GET /v1/proactive/notifications - Get notification history

Implements ADR-017: Proactive Intelligence Framework.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from hestia.api.middleware.auth import verify_device_token
from hestia.logging import get_logger, LogComponent
from hestia.proactive import (
    BriefingGenerator,
    get_briefing_generator,
    PatternDetector,
    get_pattern_detector,
    InterruptionManager,
    get_interruption_manager,
    InterruptionPolicy,
    ProactiveConfig,
)

logger = get_logger()
router = APIRouter(prefix="/v1/proactive", tags=["proactive"])


# Request/Response Models

class PolicyUpdateRequest(BaseModel):
    """Request to update proactive policy."""
    interruption_policy: Optional[str] = Field(
        None,
        description="Interruption policy: 'never', 'daily', or 'proactive'"
    )
    briefing_enabled: Optional[bool] = Field(
        None,
        description="Enable/disable daily briefings"
    )
    briefing_time: Optional[str] = Field(
        None,
        description="Briefing time in HH:MM format"
    )
    briefing_days: Optional[List[int]] = Field(
        None,
        description="Days for briefing (0=Mon, 6=Sun)"
    )
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = Field(
        None,
        description="Quiet hours start in HH:MM format"
    )
    quiet_hours_end: Optional[str] = Field(
        None,
        description="Quiet hours end in HH:MM format"
    )
    pattern_detection_enabled: Optional[bool] = None
    weather_enabled: Optional[bool] = None
    weather_location: Optional[str] = Field(
        None,
        description="Weather location (city name or coordinates)"
    )


class BriefingResponse(BaseModel):
    """Response containing daily briefing."""
    greeting: str
    timestamp: str
    text: str
    calendar: Dict[str, Any]
    reminders: Dict[str, Any]
    tasks: Dict[str, Any]
    weather: Dict[str, Any]
    suggestions: List[str]
    sections: List[Dict[str, Any]]


class PolicyResponse(BaseModel):
    """Response containing current policy."""
    interruption_policy: str
    briefing: Dict[str, Any]
    quiet_hours: Dict[str, Any]
    patterns: Dict[str, Any]
    weather: Dict[str, Any]
    next_briefing: Optional[str] = None
    can_interrupt_now: bool


class PatternResponse(BaseModel):
    """Response containing detected patterns."""
    patterns: List[Dict[str, Any]]
    total_count: int
    valid_count: int
    last_analysis: Optional[str] = None


class ContextResponse(BaseModel):
    """Response containing current context."""
    current_time: str
    day_of_week: int
    is_focus_mode: bool
    is_busy_calendar: bool
    is_quiet_hours: bool


# Singleton instances (initialized lazily)
_config: Optional[ProactiveConfig] = None


def get_config() -> ProactiveConfig:
    """Get or create proactive configuration."""
    global _config
    if _config is None:
        _config = ProactiveConfig()
    return _config


def set_config(config: ProactiveConfig) -> None:
    """Update proactive configuration."""
    global _config
    _config = config


# Endpoints

@router.get(
    "/briefing",
    response_model=BriefingResponse,
    summary="Get today's briefing",
    description="Generate and return today's daily briefing including calendar, reminders, weather, and suggestions.",
)
async def get_briefing(device_id: str = Depends(verify_device_token)):
    """Get today's daily briefing."""
    logger.info(
        "Generating briefing",
        component=LogComponent.API,
        data={"device_id": device_id[:8]},
    )

    try:
        config = get_config()
        generator = get_briefing_generator(config)
        detector = get_pattern_detector(config)

        # Get patterns for suggestions
        patterns = await detector.analyze()

        # Generate briefing
        briefing = await generator.generate(patterns=patterns)

        return BriefingResponse(**briefing.to_dict())

    except Exception as e:
        logger.error(
            f"Briefing generation failed: {e}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate briefing: {str(e)}",
        )


@router.get(
    "/policy",
    response_model=PolicyResponse,
    summary="Get proactive policy",
    description="Get current proactive intelligence settings and status.",
)
async def get_policy(device_id: str = Depends(verify_device_token)):
    """Get current proactive policy settings."""
    config = get_config()
    manager = get_interruption_manager(config)

    context = manager.get_context()
    next_briefing = manager.get_next_briefing_time()

    return PolicyResponse(
        **config.to_dict(),
        next_briefing=next_briefing.isoformat() if next_briefing else None,
        can_interrupt_now=manager.can_interrupt(context=context),
    )


@router.post(
    "/policy",
    response_model=PolicyResponse,
    summary="Update proactive policy",
    description="Update proactive intelligence settings.",
)
async def update_policy(
    request: PolicyUpdateRequest,
    device_id: str = Depends(verify_device_token),
):
    """Update proactive policy settings."""
    config = get_config()

    # Update fields that were provided
    if request.interruption_policy is not None:
        try:
            config.interruption_policy = InterruptionPolicy(request.interruption_policy)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid interruption_policy: {request.interruption_policy}. Must be 'never', 'daily', or 'proactive'.",
            )

    if request.briefing_enabled is not None:
        config.briefing_enabled = request.briefing_enabled

    if request.briefing_time is not None:
        from datetime import time
        try:
            config.briefing_time = time.fromisoformat(request.briefing_time)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid briefing_time format: {request.briefing_time}. Use HH:MM format.",
            )

    if request.briefing_days is not None:
        if not all(0 <= d <= 6 for d in request.briefing_days):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="briefing_days must contain values 0-6 (Monday-Sunday).",
            )
        config.briefing_days = request.briefing_days

    if request.quiet_hours_enabled is not None:
        config.quiet_hours_enabled = request.quiet_hours_enabled

    if request.quiet_hours_start is not None:
        from datetime import time
        try:
            config.quiet_hours_start = time.fromisoformat(request.quiet_hours_start)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid quiet_hours_start format. Use HH:MM format.",
            )

    if request.quiet_hours_end is not None:
        from datetime import time
        try:
            config.quiet_hours_end = time.fromisoformat(request.quiet_hours_end)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid quiet_hours_end format. Use HH:MM format.",
            )

    if request.pattern_detection_enabled is not None:
        config.pattern_detection_enabled = request.pattern_detection_enabled

    if request.weather_enabled is not None:
        config.weather_enabled = request.weather_enabled

    if request.weather_location is not None:
        config.weather_location = request.weather_location

    # Save updated config
    set_config(config)

    logger.info(
        "Proactive policy updated",
        component=LogComponent.API,
        data={"device_id": device_id[:8], "policy": config.interruption_policy.value},
    )

    # Return updated policy
    manager = get_interruption_manager(config)
    context = manager.get_context()
    next_briefing = manager.get_next_briefing_time()

    return PolicyResponse(
        **config.to_dict(),
        next_briefing=next_briefing.isoformat() if next_briefing else None,
        can_interrupt_now=manager.can_interrupt(context=context),
    )


@router.get(
    "/patterns",
    response_model=PatternResponse,
    summary="List detected patterns",
    description="Get behavioral patterns detected from conversation history.",
)
async def get_patterns(
    valid_only: bool = True,
    refresh: bool = False,
    device_id: str = Depends(verify_device_token),
):
    """Get detected behavioral patterns."""
    config = get_config()
    detector = get_pattern_detector(config)

    if refresh:
        await detector.analyze(force_refresh=True)

    all_patterns = detector.get_patterns(valid_only=False)
    valid_patterns = [p for p in all_patterns if p.is_valid()]

    patterns_to_return = valid_patterns if valid_only else all_patterns

    return PatternResponse(
        patterns=[p.to_dict() for p in patterns_to_return],
        total_count=len(all_patterns),
        valid_count=len(valid_patterns),
        last_analysis=detector._last_analysis.isoformat() if detector._last_analysis else None,
    )


@router.get(
    "/context",
    response_model=ContextResponse,
    summary="Get current context",
    description="Get current interruption context (Focus mode, calendar, quiet hours).",
)
async def get_context(device_id: str = Depends(verify_device_token)):
    """Get current interruption context."""
    config = get_config()
    manager = get_interruption_manager(config)
    context = manager.get_context()

    return ContextResponse(
        current_time=context.current_time.isoformat(),
        day_of_week=context.day_of_week,
        is_focus_mode=context.is_focus_mode,
        is_busy_calendar=context.is_busy_calendar,
        is_quiet_hours=context.is_quiet_hours,
    )


@router.post(
    "/analyze",
    response_model=PatternResponse,
    summary="Trigger pattern analysis",
    description="Force re-analysis of conversation history for patterns.",
)
async def analyze_patterns(device_id: str = Depends(verify_device_token)):
    """Trigger pattern analysis."""
    logger.info(
        "Pattern analysis requested",
        component=LogComponent.API,
        data={"device_id": device_id[:8]},
    )

    config = get_config()
    detector = get_pattern_detector(config)

    await detector.analyze(force_refresh=True)

    all_patterns = detector.get_patterns(valid_only=False)
    valid_patterns = [p for p in all_patterns if p.is_valid()]

    return PatternResponse(
        patterns=[p.to_dict() for p in valid_patterns],
        total_count=len(all_patterns),
        valid_count=len(valid_patterns),
        last_analysis=detector._last_analysis.isoformat() if detector._last_analysis else None,
    )
