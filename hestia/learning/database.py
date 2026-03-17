"""SQLite database for the learning module."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent
from hestia.learning.models import (
    MetaMonitorReport,
    MemoryHealthSnapshot,
    TriggerAlert,
    Correction,
    CorrectionType,
    DistillationRun,
    DistillationStatus,
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

            CREATE TABLE IF NOT EXISTS corrections (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                outcome_id TEXT NOT NULL UNIQUE,
                correction_type TEXT NOT NULL,
                analysis TEXT NOT NULL,
                confidence REAL NOT NULL,
                principle_id TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_corrections_user_ts
                ON corrections(user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_corrections_type
                ON corrections(correction_type);

            CREATE TABLE IF NOT EXISTS distillation_runs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                run_timestamp TEXT NOT NULL,
                source TEXT NOT NULL,
                outcomes_processed INTEGER DEFAULT 0,
                principles_generated INTEGER DEFAULT 0,
                status TEXT DEFAULT 'in_progress',
                error_message TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_distillation_user_ts
                ON distillation_runs(user_id, run_timestamp DESC);

            CREATE TABLE IF NOT EXISTS outcome_principles (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                outcome_id TEXT NOT NULL,
                principle_id TEXT NOT NULL,
                confidence REAL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_outcome_principles_principle
                ON outcome_principles(principle_id);
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

    async def create_correction(self, correction: Correction) -> str:
        """Store a classified correction. Skips if outcome_id already classified."""
        await self.connection.execute(
            """INSERT OR IGNORE INTO corrections
               (id, user_id, outcome_id, correction_type, analysis, confidence, principle_id, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (correction.id, correction.user_id, correction.outcome_id,
             correction.correction_type.value, correction.analysis,
             correction.confidence, correction.principle_id,
             correction.created_at.isoformat()),
        )
        await self.connection.commit()
        return correction.id

    async def get_correction(self, outcome_id: str, user_id: str) -> Optional[Correction]:
        """Get correction for a specific outcome."""
        cursor = await self.connection.execute(
            "SELECT * FROM corrections WHERE outcome_id = ? AND user_id = ?",
            (outcome_id, user_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        return Correction.from_dict(data)

    async def list_corrections(
        self, user_id: str, correction_type: Optional[str] = None,
        days: int = 30, limit: int = 100,
    ) -> List[Correction]:
        """List corrections with optional type filter."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        if correction_type:
            cursor = await self.connection.execute(
                """SELECT * FROM corrections
                   WHERE user_id = ? AND correction_type = ? AND created_at > ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, correction_type, cutoff, limit),
            )
        else:
            cursor = await self.connection.execute(
                """SELECT * FROM corrections
                   WHERE user_id = ? AND created_at > ?
                   ORDER BY created_at DESC LIMIT ?""",
                (user_id, cutoff, limit),
            )
        rows = await cursor.fetchall()
        return [Correction.from_dict(dict(r)) for r in rows]

    async def get_correction_stats(self, user_id: str, days: int = 7) -> Dict[str, int]:
        """Get correction type distribution."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self.connection.execute(
            """SELECT correction_type, COUNT(*) as count FROM corrections
               WHERE user_id = ? AND created_at > ?
               GROUP BY correction_type""",
            (user_id, cutoff),
        )
        rows = await cursor.fetchall()
        stats = {ct.value: 0 for ct in CorrectionType}
        total = 0
        for row in rows:
            d = dict(row)
            stats[d["correction_type"]] = d["count"]
            total += d["count"]
        stats["total"] = total
        return stats

    async def create_distillation_run(self, run: DistillationRun) -> str:
        """Create a new distillation run record."""
        await self.connection.execute(
            """INSERT INTO distillation_runs
               (id, user_id, run_timestamp, source, outcomes_processed,
                principles_generated, status, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (run.id, run.user_id, run.run_timestamp.isoformat(),
             run.source, run.outcomes_processed, run.principles_generated,
             run.status.value, run.error_message),
        )
        await self.connection.commit()
        return run.id

    async def update_distillation_run(
        self, run_id: str, status: str,
        outcomes_processed: int = 0, principles_generated: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Update a distillation run's status and counts."""
        await self.connection.execute(
            """UPDATE distillation_runs
               SET status = ?, outcomes_processed = ?,
                   principles_generated = ?, error_message = ?
               WHERE id = ?""",
            (status, outcomes_processed, principles_generated, error_message, run_id),
        )
        await self.connection.commit()

    async def get_latest_distillation_run(self, user_id: str) -> Optional[DistillationRun]:
        """Get the most recent distillation run."""
        cursor = await self.connection.execute(
            """SELECT * FROM distillation_runs
               WHERE user_id = ? ORDER BY run_timestamp DESC LIMIT 1""",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return DistillationRun.from_dict(dict(row))

    async def link_outcome_to_principle(
        self, user_id: str, outcome_id: str, principle_id: str,
        confidence: float, source: str,
    ) -> str:
        """Create an outcome-to-principle mapping."""
        import uuid
        mapping_id = str(uuid.uuid4())
        await self.connection.execute(
            """INSERT INTO outcome_principles
               (id, user_id, outcome_id, principle_id, confidence, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mapping_id, user_id, outcome_id, principle_id,
             confidence, source, datetime.now(timezone.utc).isoformat()),
        )
        await self.connection.commit()
        return mapping_id

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
