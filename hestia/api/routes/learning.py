"""API routes for the learning module (Sprint 15)."""

from __future__ import annotations

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
