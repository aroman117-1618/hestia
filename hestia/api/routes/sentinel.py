"""
Sentinel status routes for Hestia API.

Provides read-only access to sentinel event data and acknowledgement actions.
Queries sentinel_events.db directly via sqlite3 — no sentinel module imports needed.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/v1/sentinel", tags=["sentinel"])

_DB_PATH = Path.home() / "hestia" / "data" / "sentinel_events.db"


def _get_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


@router.get(
    "/status",
    summary="Sentinel status",
    description="Query recent sentinel events and determine overall system status.",
)
async def sentinel_status() -> JSONResponse:
    """
    Read recent sentinel events and return aggregated status.

    Returns not_configured if the sentinel DB does not exist.
    Determines overall status from unacknowledged event severities:
    - critical: any unacknowledged CRITICAL events
    - warning: any unacknowledged HIGH events
    - info: any unacknowledged MEDIUM events
    - healthy: no unacknowledged events
    """
    if not _DB_PATH.exists():
        return JSONResponse(
            status_code=200,
            content={
                "status": "not_configured",
                "events": [],
                "timestamp": _get_timestamp(),
            },
        )

    try:
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                """
                SELECT event_id, severity, title, description, details,
                       acknowledged, created_at
                FROM events
                ORDER BY created_at DESC
                LIMIT 50
                """,
            )
            rows = cursor.fetchall()
        finally:
            conn.close()
    except sqlite3.Error as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": "db_error",
                "message": "Failed to read sentinel database.",
                "timestamp": _get_timestamp(),
            },
        )

    # Count unacknowledged by severity
    unacked_by_severity: dict[str, int] = {}
    for row in rows:
        if not row["acknowledged"]:
            sev = row["severity"]
            unacked_by_severity[sev] = unacked_by_severity.get(sev, 0) + 1

    # Determine overall status
    if unacked_by_severity.get("CRITICAL", 0) > 0:
        overall_status = "critical"
    elif unacked_by_severity.get("HIGH", 0) > 0:
        overall_status = "warning"
    elif unacked_by_severity.get("MEDIUM", 0) > 0:
        overall_status = "info"
    else:
        overall_status = "healthy"

    # Build top-20 event list, parsing details JSON strings back to dicts
    events = []
    for row in rows[:20]:
        details = row["details"]
        if details and isinstance(details, str):
            try:
                details = json.loads(details)
            except (json.JSONDecodeError, ValueError):
                pass  # leave as raw string if unparseable

        events.append(
            {
                "event_id": row["event_id"],
                "severity": row["severity"],
                "title": row["title"],
                "description": row["description"],
                "details": details,
                "acknowledged": bool(row["acknowledged"]),
                "created_at": row["created_at"],
            }
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": overall_status,
            "unacknowledged_counts": unacked_by_severity,
            "events": events,
            "timestamp": _get_timestamp(),
        },
    )


@router.post(
    "/acknowledge/{event_id}",
    summary="Acknowledge a sentinel event",
    description="Mark a sentinel event as acknowledged by event_id.",
)
async def acknowledge_event(event_id: str) -> JSONResponse:
    """
    Acknowledge a sentinel event by its event_id.

    Returns 404 if the sentinel DB does not exist.
    Returns 404 if no matching event is found.
    """
    if not _DB_PATH.exists():
        return JSONResponse(
            status_code=404,
            content={
                "error": "not_found",
                "message": "Sentinel database does not exist.",
                "timestamp": _get_timestamp(),
            },
        )

    try:
        conn = sqlite3.connect(str(_DB_PATH))
        try:
            cursor = conn.execute(
                "UPDATE events SET acknowledged=1 WHERE event_id=?",
                (event_id,),
            )
            conn.commit()
            rows_affected = cursor.rowcount
        finally:
            conn.close()
    except sqlite3.Error:
        return JSONResponse(
            status_code=500,
            content={
                "error": "db_error",
                "message": "Failed to update sentinel database.",
                "timestamp": _get_timestamp(),
            },
        )

    if rows_affected == 0:
        return JSONResponse(
            status_code=404,
            content={
                "error": "not_found",
                "message": f"No event found with event_id '{event_id}'.",
                "timestamp": _get_timestamp(),
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "acknowledged": True,
            "event_id": event_id,
            "timestamp": _get_timestamp(),
        },
    )
