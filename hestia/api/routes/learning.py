"""API routes for the learning module (Sprint 15 + Sprint 17)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from hestia.logging import get_logger, LogComponent


logger = get_logger()
router = APIRouter(prefix="/v1/learning", tags=["learning"])

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
async def get_latest_report(user_id: str = Query(...)):
    """Get the latest MetaMonitor report."""
    db = await _get_learning_db()
    report = await db.get_latest_report(user_id)
    return {"data": report.to_dict() if report else None}


@router.get("/memory-health")
async def get_memory_health(user_id: str = Query(...)):
    """Get the latest memory health snapshot."""
    db = await _get_learning_db()
    snapshot = await db.get_latest_health_snapshot(user_id)
    return {"data": snapshot.to_dict() if snapshot else None}


@router.get("/memory-health/history")
async def get_memory_health_history(
    user_id: str = Query(...),
    days: int = Query(default=30, ge=1, le=365),
):
    """Get memory health snapshot history."""
    db = await _get_learning_db()
    snapshots = await db.get_health_snapshot_history(user_id, days=days)
    return {"data": [s.to_dict() for s in snapshots]}


@router.get("/alerts")
async def get_alerts(user_id: str = Query(...)):
    """Get unacknowledged trigger alerts."""
    db = await _get_learning_db()
    alerts = await db.get_unacknowledged_alerts(user_id)
    return {"data": [a.to_dict() for a in alerts]}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user_id: str = Query(...)):
    """Acknowledge a trigger alert."""
    db = await _get_learning_db()
    await db.acknowledge_alert(alert_id, user_id)
    return {"status": "acknowledged"}


# ── Sprint 17: Correction + Distillation endpoints ────────


@router.get("/corrections")
async def list_corrections(
    user_id: str = Query(...),
    correction_type: Optional[str] = Query(None),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
):
    """List classified corrections with optional type filter."""
    db = await _get_learning_db()
    corrections = await db.list_corrections(
        user_id, correction_type=correction_type, days=days, limit=limit,
    )
    return {"data": [c.to_dict() for c in corrections], "count": len(corrections)}


@router.get("/corrections/stats")
async def get_correction_stats(
    user_id: str = Query(...),
    days: int = Query(default=7, ge=1, le=365),
):
    """Get correction type distribution."""
    db = await _get_learning_db()
    stats = await db.get_correction_stats(user_id, days=days)
    return {"data": stats}


@router.get("/corrections/{outcome_id}")
async def get_correction_for_outcome(
    outcome_id: str,
    user_id: str = Query(...),
):
    """Get correction classification for a specific outcome."""
    db = await _get_learning_db()
    correction = await db.get_correction(outcome_id, user_id)
    return {"data": correction.to_dict() if correction else None}


@router.post("/distill")
async def trigger_distillation(
    user_id: str = Query(...),
    days: int = Query(default=30, ge=1, le=365),
):
    """Manually trigger outcome-to-principle distillation."""
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
    result = await distiller.distill_from_outcomes(user_id, days=days)
    return {"data": result}


@router.get("/distillation-runs")
async def get_latest_distillation_run(
    user_id: str = Query(...),
):
    """Get most recent distillation run."""
    db = await _get_learning_db()
    run = await db.get_latest_distillation_run(user_id)
    return {"data": run.to_dict() if run else None}
