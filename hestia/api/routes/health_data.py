"""
Health Data API routes.

Endpoints for receiving HealthKit data synced from iOS,
querying health summaries/trends, and managing coaching preferences.
"""

from datetime import date, time

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_device_token
from hestia.api.schemas import (
    CoachingPreferencesRequest,
    CoachingPreferencesResponse,
    HealthMetricPayload,
    HealthSummaryResponse,
    HealthSyncRequest,
    HealthSyncResponse,
    HealthTrendResponse,
    SyncHistoryItem,
    SyncHistoryResponse,
)
from hestia.health import get_health_manager
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/health_data", tags=["health_data"])
logger = get_logger()


# =============================================================================
# Routes
# =============================================================================

@router.post(
    "/sync",
    response_model=HealthSyncResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sync health metrics",
    description="Receive a batch of health metrics from iOS HealthKit.",
)
async def sync_metrics(
    request: HealthSyncRequest,
    device_id: str = Depends(get_device_token),
):
    """Sync health metrics from iOS."""
    manager = await get_health_manager()

    # Convert Pydantic models to dicts for manager
    metrics_data = [
        {
            "metric_type": m.metric_type,
            "value": m.value,
            "unit": m.unit,
            "start_date": m.start_date,
            "end_date": m.end_date,
            "source": m.source,
            "metadata": m.metadata,
        }
        for m in request.metrics
    ]

    result = await manager.process_sync(
        device_id=device_id,
        metrics_data=metrics_data,
        sync_date=request.sync_date,
    )

    logger.info(
        "Health sync completed via API",
        component=LogComponent.API,
        data={
            "device_id": device_id,
            "sync_date": request.sync_date,
            "received": result.metrics_received,
            "stored": result.metrics_stored,
        },
    )

    return HealthSyncResponse(
        sync_id=result.sync_id,
        metrics_received=result.metrics_received,
        metrics_stored=result.metrics_stored,
        metrics_deduplicated=result.metrics_deduplicated,
        duration_ms=result.duration_ms,
    )


@router.get(
    "/summary",
    response_model=HealthSummaryResponse,
    summary="Get today's health summary",
    description="Get aggregated health data for today.",
)
async def get_summary(
    device_id: str = Depends(get_device_token),
):
    """Get today's health summary."""
    manager = await get_health_manager()
    summary = await manager.get_daily_summary()
    return HealthSummaryResponse(**summary)


@router.get(
    "/summary/{target_date}",
    response_model=HealthSummaryResponse,
    summary="Get health summary for a date",
    description="Get aggregated health data for a specific date.",
)
async def get_summary_for_date(
    target_date: str,
    device_id: str = Depends(get_device_token),
):
    """Get health summary for a specific date."""
    # Validate date format
    try:
        date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Use YYYY-MM-DD.",
        )

    manager = await get_health_manager()
    summary = await manager.get_daily_summary(target_date)
    return HealthSummaryResponse(**summary)


@router.get(
    "/trend/{metric_type}",
    response_model=HealthTrendResponse,
    summary="Get metric trend",
    description="Get trend data for a health metric over time.",
)
async def get_trend(
    metric_type: str,
    days: int = Query(7, ge=1, le=90),
    device_id: str = Depends(get_device_token),
):
    """Get trend data for a metric."""
    manager = await get_health_manager()
    trend = await manager.get_metric_trend(metric_type, days)
    return HealthTrendResponse(**trend)


@router.get(
    "/coaching",
    response_model=CoachingPreferencesResponse,
    summary="Get coaching preferences",
    description="Get health coaching preferences.",
)
async def get_coaching_preferences(
    device_id: str = Depends(get_device_token),
):
    """Get coaching preferences."""
    manager = await get_health_manager()
    prefs = await manager.get_coaching_preferences()

    return CoachingPreferencesResponse(
        preferences=prefs.to_dict(),
        updated_at=date.today().isoformat(),
    )


@router.post(
    "/coaching",
    response_model=CoachingPreferencesResponse,
    summary="Update coaching preferences",
    description="Update health coaching preferences. All fields are optional.",
)
async def update_coaching_preferences(
    request: CoachingPreferencesRequest,
    device_id: str = Depends(get_device_token),
):
    """Update coaching preferences."""
    manager = await get_health_manager()

    # Build kwargs from non-None fields
    kwargs = {}
    for field_name in request.__fields__:
        value = getattr(request, field_name)
        if value is not None:
            # Handle summary_time conversion
            if field_name == "summary_time":
                h, m = map(int, value.split(":"))
                kwargs[field_name] = time(h, m)
            else:
                kwargs[field_name] = value

    prefs = await manager.update_coaching_preferences(**kwargs)

    logger.info(
        "Coaching preferences updated via API",
        component=LogComponent.API,
        data={"device_id": device_id, "fields": list(kwargs.keys())},
    )

    return CoachingPreferencesResponse(
        preferences=prefs.to_dict(),
        updated_at=date.today().isoformat(),
    )


@router.get(
    "/sync/history",
    response_model=SyncHistoryResponse,
    summary="Get sync history",
    description="Get recent sync history.",
)
async def get_sync_history(
    limit: int = Query(20, ge=1, le=100),
    device_id: str = Depends(get_device_token),
):
    """Get sync history."""
    manager = await get_health_manager()
    syncs = await manager.list_syncs(limit=limit)

    return SyncHistoryResponse(
        syncs=[
            SyncHistoryItem(
                sync_id=s.sync_id,
                device_id=s.device_id,
                timestamp=s.timestamp.isoformat(),
                metrics_received=s.metrics_received,
                metrics_stored=s.metrics_stored,
                metrics_deduplicated=s.metrics_deduplicated,
                sync_date=s.sync_date,
                duration_ms=s.duration_ms,
            )
            for s in syncs
        ],
        count=len(syncs),
    )
