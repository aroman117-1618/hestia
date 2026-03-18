"""API routes for the learning module (Sprint 15 + Sprint 17)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_device_token
from hestia.logging import get_logger, LogComponent


logger = get_logger()
router = APIRouter(prefix="/v1/learning", tags=["learning"])

DEFAULT_USER_ID = "user-default"

_learning_db_instance = None


async def _get_learning_db():
    """Lazy-init singleton for learning database."""
    global _learning_db_instance
    if _learning_db_instance is None:
        from hestia.learning.database import LearningDatabase
        _learning_db_instance = LearningDatabase("data/learning.db")
        await _learning_db_instance.connect()
    return _learning_db_instance


@router.get("/report")
async def get_latest_report(
    device_id: str = Depends(get_device_token),
):
    """Get the latest MetaMonitor report."""
    try:
        db = await _get_learning_db()
        report = await db.get_latest_report(DEFAULT_USER_ID)
        return {"data": report.to_dict() if report else None}
    except Exception as e:
        logger.error(
            "Failed to get learning report",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get report")


@router.get("/memory-health")
async def get_memory_health(
    device_id: str = Depends(get_device_token),
):
    """Get the latest memory health snapshot."""
    try:
        db = await _get_learning_db()
        snapshot = await db.get_latest_health_snapshot(DEFAULT_USER_ID)
        return {"data": snapshot.to_dict() if snapshot else None}
    except Exception as e:
        logger.error(
            "Failed to get memory health",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get memory health")


@router.get("/memory-health/history")
async def get_memory_health_history(
    days: int = Query(default=30, ge=1, le=365),
    device_id: str = Depends(get_device_token),
):
    """Get memory health snapshot history."""
    try:
        db = await _get_learning_db()
        snapshots = await db.get_health_snapshot_history(DEFAULT_USER_ID, days=days)
        return {"data": [s.to_dict() for s in snapshots]}
    except Exception as e:
        logger.error(
            "Failed to get memory health history",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get health history")


@router.get("/alerts")
async def get_alerts(
    device_id: str = Depends(get_device_token),
):
    """Get unacknowledged trigger alerts."""
    try:
        db = await _get_learning_db()
        alerts = await db.get_unacknowledged_alerts(DEFAULT_USER_ID)
        return {"data": [a.to_dict() for a in alerts]}
    except Exception as e:
        logger.error(
            "Failed to get alerts",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get alerts")


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    device_id: str = Depends(get_device_token),
):
    """Acknowledge a trigger alert."""
    try:
        db = await _get_learning_db()
        await db.acknowledge_alert(alert_id, DEFAULT_USER_ID)
        return {"status": "acknowledged"}
    except Exception as e:
        logger.error(
            "Failed to acknowledge alert",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e), "alert_id": alert_id},
        )
        raise HTTPException(status_code=500, detail="Failed to acknowledge alert")


# ── Sprint 17: Correction + Distillation endpoints ────────


@router.get("/corrections")
async def list_corrections(
    correction_type: Optional[str] = Query(None),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    device_id: str = Depends(get_device_token),
):
    """List classified corrections with optional type filter."""
    try:
        db = await _get_learning_db()
        corrections = await db.list_corrections(
            DEFAULT_USER_ID, correction_type=correction_type, days=days, limit=limit,
        )
        return {"data": [c.to_dict() for c in corrections], "count": len(corrections)}
    except Exception as e:
        logger.error(
            "Failed to list corrections",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to list corrections")


@router.get("/corrections/stats")
async def get_correction_stats(
    days: int = Query(default=7, ge=1, le=365),
    device_id: str = Depends(get_device_token),
):
    """Get correction type distribution."""
    try:
        db = await _get_learning_db()
        stats = await db.get_correction_stats(DEFAULT_USER_ID, days=days)
        return {"data": stats}
    except Exception as e:
        logger.error(
            "Failed to get correction stats",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get correction stats")


@router.get("/corrections/{outcome_id}")
async def get_correction_for_outcome(
    outcome_id: str,
    device_id: str = Depends(get_device_token),
):
    """Get correction classification for a specific outcome."""
    try:
        db = await _get_learning_db()
        correction = await db.get_correction(outcome_id, DEFAULT_USER_ID)
        return {"data": correction.to_dict() if correction else None}
    except Exception as e:
        logger.error(
            "Failed to get correction",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e), "outcome_id": outcome_id},
        )
        raise HTTPException(status_code=500, detail="Failed to get correction")


@router.post("/distill")
async def trigger_distillation(
    days: int = Query(default=30, ge=1, le=365),
    device_id: str = Depends(get_device_token),
):
    """Manually trigger outcome-to-principle distillation."""
    try:
        from hestia.learning.outcome_distiller import OutcomeDistiller
        from hestia.outcomes import get_outcome_manager
        from hestia.research.manager import get_research_manager

        db = await _get_learning_db()
        outcome_mgr = await get_outcome_manager()
        research_mgr = await get_research_manager()

        distiller = OutcomeDistiller(
            learning_db=db,
            outcome_db=outcome_mgr._database,
            principle_store=research_mgr._principle_store,
        )
        result = await distiller.distill_from_outcomes(DEFAULT_USER_ID, days=days)
        return {"data": result}
    except Exception as e:
        logger.error(
            "Distillation failed",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Distillation failed")


@router.get("/distillation-runs")
async def get_latest_distillation_run(
    device_id: str = Depends(get_device_token),
):
    """Get most recent distillation run."""
    try:
        db = await _get_learning_db()
        run = await db.get_latest_distillation_run(DEFAULT_USER_ID)
        return {"data": run.to_dict() if run else None}
    except Exception as e:
        logger.error(
            "Failed to get distillation run",
            component=LogComponent.LEARNING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get distillation run")
