"""SQLite database for the learning module."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent
from hestia.learning.models import (
    MetaMonitorReport,
    MemoryHealthSnapshot,
    TriggerAlert,
)


logger = get_logger()


class LearningDatabase(BaseDatabase):
    """Stores MetaMonitor reports, health snapshots, and trigger alerts.

    All tables include user_id for multi-user readiness.
    """

    def __init__(self, db_path: str = "learning") -> None:
        from pathlib import Path
        super().__init__("learning", db_path=Path(db_path) if "/" in db_path else None)

    async def _init_schema(self) -> None:
        await self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS monitor_reports (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reports_user_ts
                ON monitor_reports(user_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS health_snapshots (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_user_ts
                ON health_snapshots(user_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS trigger_log (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                trigger_name TEXT NOT NULL,
                current_value REAL NOT NULL,
                threshold_value REAL NOT NULL,
                direction TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0,
                cooldown_until TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_triggers_user_ack
                ON trigger_log(user_id, acknowledged);
            CREATE INDEX IF NOT EXISTS idx_triggers_name
                ON trigger_log(user_id, trigger_name, timestamp DESC);
        """)
        await self.connection.commit()

    async def store_report(self, report: MetaMonitorReport) -> None:
        """Store a MetaMonitor report."""
        await self.connection.execute(
            "INSERT OR REPLACE INTO monitor_reports (id, user_id, timestamp, data) VALUES (?, ?, ?, ?)",
            (report.id, report.user_id, report.timestamp.isoformat(), json.dumps(report.to_dict())),
        )
        await self.connection.commit()

    async def get_latest_report(self, user_id: str) -> Optional[MetaMonitorReport]:
        """Get most recent MetaMonitor report for a user."""
        cursor = await self.connection.execute(
            "SELECT data FROM monitor_reports WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return MetaMonitorReport.from_dict(json.loads(row[0]))

    async def store_health_snapshot(self, snapshot: MemoryHealthSnapshot) -> None:
        """Store a memory health snapshot."""
        await self.connection.execute(
            "INSERT OR REPLACE INTO health_snapshots (id, user_id, timestamp, data) VALUES (?, ?, ?, ?)",
            (snapshot.id, snapshot.user_id, snapshot.timestamp.isoformat(), json.dumps(snapshot.to_dict())),
        )
        await self.connection.commit()

    async def get_latest_health_snapshot(self, user_id: str) -> Optional[MemoryHealthSnapshot]:
        """Get most recent health snapshot for a user."""
        cursor = await self.connection.execute(
            "SELECT data FROM health_snapshots WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return MemoryHealthSnapshot.from_dict(json.loads(row[0]))

    async def get_health_snapshot_history(
        self, user_id: str, days: int = 30
    ) -> List[MemoryHealthSnapshot]:
        """Get health snapshot history for a user within a time window."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self.connection.execute(
            "SELECT data FROM health_snapshots WHERE user_id = ? AND timestamp >= ? ORDER BY timestamp DESC",
            (user_id, cutoff),
        )
        rows = await cursor.fetchall()
        return [MemoryHealthSnapshot.from_dict(json.loads(r[0])) for r in rows]

    async def store_trigger_alert(self, alert: TriggerAlert) -> None:
        """Store a trigger alert."""
        await self.connection.execute(
            """INSERT OR REPLACE INTO trigger_log
               (id, user_id, trigger_name, current_value, threshold_value,
                direction, message, timestamp, acknowledged, cooldown_until)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alert.id, alert.user_id, alert.trigger_name, alert.current_value,
             alert.threshold_value, alert.direction, alert.message,
             alert.timestamp.isoformat(), 1 if alert.acknowledged else 0,
             alert.cooldown_until.isoformat() if alert.cooldown_until else None),
        )
        await self.connection.commit()

    async def get_unacknowledged_alerts(self, user_id: str) -> List[TriggerAlert]:
        """Get all unacknowledged alerts for a user."""
        cursor = await self.connection.execute(
            "SELECT * FROM trigger_log WHERE user_id = ? AND acknowledged = 0 ORDER BY timestamp DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_alert(r) for r in rows]

    async def acknowledge_alert(self, alert_id: str, user_id: str) -> None:
        """Mark an alert as acknowledged."""
        await self.connection.execute(
            "UPDATE trigger_log SET acknowledged = 1 WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        )
        await self.connection.commit()

    async def get_last_trigger_fire(
        self, user_id: str, trigger_name: str
    ) -> Optional[TriggerAlert]:
        """Get the most recent alert for a specific trigger."""
        cursor = await self.connection.execute(
            "SELECT * FROM trigger_log WHERE user_id = ? AND trigger_name = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id, trigger_name),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_alert(row)

    async def cleanup_old_reports(self, max_age_days: int = 7) -> int:
        """Delete reports older than max_age_days. Called during each analysis run."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        cursor = await self.connection.execute(
            "DELETE FROM monitor_reports WHERE timestamp < ?", (cutoff,)
        )
        await self.connection.commit()
        return cursor.rowcount

    def _row_to_alert(self, row: tuple) -> TriggerAlert:
        """Convert a database row to a TriggerAlert."""
        return TriggerAlert(
            id=row[0], user_id=row[1], trigger_name=row[2],
            current_value=row[3], threshold_value=row[4],
            direction=row[5], message=row[6],
            timestamp=datetime.fromisoformat(row[7]),
            acknowledged=bool(row[8]),
            cooldown_until=datetime.fromisoformat(row[9]) if row[9] else None,
        )
