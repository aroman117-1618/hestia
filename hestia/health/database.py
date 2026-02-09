"""
SQLite persistence for health data.

Provides async database operations for health metric storage,
aggregation queries, sync tracking, and coaching preferences.
"""

import json
import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hestia.logging import get_logger, LogComponent

from .models import (
    HealthMetric,
    HealthCategory,
    HealthSyncResult,
    HealthCoachingPreferences,
)


class HealthDatabase:
    """
    SQLite database for health data persistence.

    Uses async aiosqlite for non-blocking I/O.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize health database.

        Args:
            db_path: Path to SQLite database file.
                     Defaults to ~/hestia/data/health.db
        """
        if db_path is None:
            db_path = Path.home() / "hestia" / "data" / "health.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection: Optional[aiosqlite.Connection] = None
        self.logger = get_logger()

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()

        self.logger.info(
            f"Health database connected: {self.db_path}",
            component=LogComponent.HEALTH,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS health_metrics (
                id TEXT PRIMARY KEY,
                metric_type TEXT NOT NULL,
                category TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'unknown',
                synced_at TEXT NOT NULL,
                metadata TEXT,
                UNIQUE(metric_type, start_date, end_date, source)
            );

            CREATE INDEX IF NOT EXISTS idx_metrics_type_date
                ON health_metrics(metric_type, start_date);

            CREATE INDEX IF NOT EXISTS idx_metrics_category
                ON health_metrics(category);

            CREATE INDEX IF NOT EXISTS idx_metrics_start_date
                ON health_metrics(start_date);

            CREATE TABLE IF NOT EXISTS health_syncs (
                id TEXT PRIMARY KEY,
                device_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metrics_received INTEGER NOT NULL DEFAULT 0,
                metrics_stored INTEGER NOT NULL DEFAULT 0,
                metrics_deduplicated INTEGER NOT NULL DEFAULT 0,
                sync_date TEXT NOT NULL,
                duration_ms REAL
            );

            CREATE INDEX IF NOT EXISTS idx_syncs_timestamp
                ON health_syncs(timestamp DESC);

            CREATE TABLE IF NOT EXISTS health_coaching_preferences (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                preferences_json TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
        """)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self.logger.debug(
                "Health database closed",
                component=LogComponent.HEALTH,
            )

    async def __aenter__(self) -> "HealthDatabase":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get active connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # =========================================================================
    # Metric Storage
    # =========================================================================

    async def store_metrics(self, metrics: List[HealthMetric]) -> Tuple[int, int]:
        """
        Store a batch of health metrics.

        Uses INSERT OR IGNORE for deduplication based on the
        UNIQUE(metric_type, start_date, end_date, source) constraint.

        Args:
            metrics: List of HealthMetric objects to store.

        Returns:
            Tuple of (stored_count, deduplicated_count).
        """
        stored = 0
        for metric in metrics:
            row = metric.to_sqlite_row()
            try:
                cursor = await self.connection.execute(
                    """
                    INSERT OR IGNORE INTO health_metrics (
                        id, metric_type, category, value, unit,
                        start_date, end_date, source, synced_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    row,
                )
                if cursor.rowcount > 0:
                    stored += 1
            except Exception as e:
                self.logger.warning(
                    f"Failed to store metric: {metric.metric_type}",
                    component=LogComponent.HEALTH,
                )

        await self.connection.commit()
        deduplicated = len(metrics) - stored
        return stored, deduplicated

    async def get_metrics(
        self,
        metric_type: str,
        start: datetime,
        end: datetime,
        limit: int = 1000,
    ) -> List[HealthMetric]:
        """Get metrics of a type within a date range."""
        metrics = []
        async with self.connection.execute(
            """
            SELECT * FROM health_metrics
            WHERE metric_type = ? AND start_date >= ? AND start_date <= ?
            ORDER BY start_date ASC
            LIMIT ?
            """,
            (metric_type, start.isoformat(), end.isoformat(), limit),
        ) as cursor:
            async for row in cursor:
                metrics.append(HealthMetric.from_sqlite_row(dict(row)))
        return metrics

    async def get_metrics_by_category(
        self,
        category: HealthCategory,
        start: datetime,
        end: datetime,
        limit: int = 1000,
    ) -> List[HealthMetric]:
        """Get all metrics in a category within a date range."""
        metrics = []
        async with self.connection.execute(
            """
            SELECT * FROM health_metrics
            WHERE category = ? AND start_date >= ? AND start_date <= ?
            ORDER BY start_date ASC
            LIMIT ?
            """,
            (category.value, start.isoformat(), end.isoformat(), limit),
        ) as cursor:
            async for row in cursor:
                metrics.append(HealthMetric.from_sqlite_row(dict(row)))
        return metrics

    async def get_latest_metric(self, metric_type: str) -> Optional[HealthMetric]:
        """Get the most recent metric of a given type."""
        async with self.connection.execute(
            """
            SELECT * FROM health_metrics
            WHERE metric_type = ?
            ORDER BY start_date DESC LIMIT 1
            """,
            (metric_type,),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return HealthMetric.from_sqlite_row(dict(row))
        return None

    async def get_metrics_range(
        self,
        metric_type: str,
        days: int = 7,
    ) -> List[HealthMetric]:
        """Get metrics for a type over the last N days."""
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        return await self.get_metrics(metric_type, start, end)

    async def get_daily_summary(self, date: str) -> Dict[str, Any]:
        """
        Get aggregated health data for a single day.

        Args:
            date: Date string in YYYY-MM-DD format.

        Returns:
            Dictionary with aggregated metrics per category.
        """
        start = f"{date}T00:00:00"
        end = f"{date}T23:59:59"

        summary: Dict[str, Any] = {
            "date": date,
            "activity": {},
            "heart": {},
            "body": {},
            "sleep": {},
            "nutrition": {},
            "mindfulness": {},
        }

        # Aggregate activity metrics (SUM for cumulative, AVG for rates)
        sum_types = [
            "stepCount", "distanceWalkingRunning", "activeEnergyBurned",
            "appleExerciseTime", "appleStandTime", "flightsClimbed",
        ]
        for metric_type in sum_types:
            async with self.connection.execute(
                """
                SELECT SUM(value) as total, COUNT(*) as samples
                FROM health_metrics
                WHERE metric_type = ? AND start_date >= ? AND start_date <= ?
                """,
                (metric_type, start, end),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row["total"] is not None:
                    summary["activity"][metric_type] = {
                        "value": round(row["total"], 1),
                        "samples": row["samples"],
                    }

        # Heart metrics (AVG, MIN, MAX)
        heart_types = [
            "heartRate", "restingHeartRate", "heartRateVariabilitySDNN",
            "walkingHeartRateAverage", "respiratoryRate", "oxygenSaturation",
            "bloodPressureSystolic", "bloodPressureDiastolic",
        ]
        for metric_type in heart_types:
            async with self.connection.execute(
                """
                SELECT AVG(value) as avg, MIN(value) as min_val,
                       MAX(value) as max_val, COUNT(*) as samples
                FROM health_metrics
                WHERE metric_type = ? AND start_date >= ? AND start_date <= ?
                """,
                (metric_type, start, end),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row["avg"] is not None:
                    summary["heart"][metric_type] = {
                        "avg": round(row["avg"], 1),
                        "min": round(row["min_val"], 1),
                        "max": round(row["max_val"], 1),
                        "samples": row["samples"],
                    }

        # Body metrics (latest value)
        body_types = ["bodyMass", "bodyMassIndex", "bodyFatPercentage", "leanBodyMass"]
        for metric_type in body_types:
            async with self.connection.execute(
                """
                SELECT value, start_date
                FROM health_metrics
                WHERE metric_type = ? AND start_date >= ? AND start_date <= ?
                ORDER BY start_date DESC LIMIT 1
                """,
                (metric_type, start, end),
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    summary["body"][metric_type] = {
                        "value": round(row["value"], 1),
                    }

        # Sleep (SUM by metadata stage or total)
        async with self.connection.execute(
            """
            SELECT SUM(value) as total_minutes, COUNT(*) as samples, metadata
            FROM health_metrics
            WHERE metric_type = 'sleepAnalysis' AND start_date >= ? AND start_date <= ?
            GROUP BY metadata
            """,
            (start, end),
        ) as cursor:
            sleep_stages: Dict[str, float] = {}
            total_sleep = 0.0
            async for row in cursor:
                minutes = row["total_minutes"] or 0
                total_sleep += minutes
                metadata = row["metadata"]
                if metadata:
                    try:
                        meta = json.loads(metadata)
                        stage = meta.get("stage", "unknown")
                    except (json.JSONDecodeError, ValueError):
                        stage = "unknown"
                else:
                    stage = "total"
                sleep_stages[stage] = round(minutes, 1)
            if total_sleep > 0:
                summary["sleep"] = {
                    "total_minutes": round(total_sleep, 1),
                    "total_hours": round(total_sleep / 60, 1),
                    "stages": sleep_stages,
                }

        # Nutrition (SUM)
        nutrition_types = [
            "dietaryEnergyConsumed", "dietaryProtein", "dietaryCarbohydrates",
            "dietaryFatTotal", "dietaryFiber", "dietaryWater",
        ]
        for metric_type in nutrition_types:
            async with self.connection.execute(
                """
                SELECT SUM(value) as total, COUNT(*) as samples
                FROM health_metrics
                WHERE metric_type = ? AND start_date >= ? AND start_date <= ?
                """,
                (metric_type, start, end),
            ) as cursor:
                row = await cursor.fetchone()
                if row and row["total"] is not None:
                    summary["nutrition"][metric_type] = {
                        "value": round(row["total"], 1),
                        "samples": row["samples"],
                    }

        # Mindfulness (SUM)
        async with self.connection.execute(
            """
            SELECT SUM(value) as total, COUNT(*) as sessions
            FROM health_metrics
            WHERE metric_type = 'mindfulSession' AND start_date >= ? AND start_date <= ?
            """,
            (start, end),
        ) as cursor:
            row = await cursor.fetchone()
            if row and row["total"] is not None:
                summary["mindfulness"] = {
                    "total_minutes": round(row["total"], 1),
                    "sessions": row["sessions"],
                }

        return summary

    async def get_metric_count(self) -> int:
        """Get total number of stored metrics."""
        async with self.connection.execute(
            "SELECT COUNT(*) FROM health_metrics"
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    # =========================================================================
    # Sync Tracking
    # =========================================================================

    async def store_sync(self, sync_result: HealthSyncResult) -> str:
        """Store a sync result record."""
        row = sync_result.to_sqlite_row()
        await self.connection.execute(
            """
            INSERT INTO health_syncs (
                id, device_id, timestamp, metrics_received,
                metrics_stored, metrics_deduplicated, sync_date, duration_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        await self.connection.commit()
        return sync_result.sync_id

    async def list_syncs(self, limit: int = 20) -> List[HealthSyncResult]:
        """List recent sync results."""
        syncs = []
        async with self.connection.execute(
            "SELECT * FROM health_syncs ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            async for row in cursor:
                syncs.append(HealthSyncResult.from_sqlite_row(dict(row)))
        return syncs

    async def get_last_sync(self) -> Optional[HealthSyncResult]:
        """Get the most recent sync result."""
        async with self.connection.execute(
            "SELECT * FROM health_syncs ORDER BY timestamp DESC LIMIT 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return HealthSyncResult.from_sqlite_row(dict(row))
        return None

    # =========================================================================
    # Coaching Preferences
    # =========================================================================

    async def get_coaching_preferences(self) -> HealthCoachingPreferences:
        """Get coaching preferences (or defaults if not set)."""
        async with self.connection.execute(
            "SELECT preferences_json FROM health_coaching_preferences WHERE id = 1"
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                try:
                    data = json.loads(row["preferences_json"])
                    return HealthCoachingPreferences.from_dict(data)
                except (json.JSONDecodeError, ValueError):
                    pass
        return HealthCoachingPreferences()

    async def update_coaching_preferences(
        self,
        prefs: HealthCoachingPreferences,
    ) -> None:
        """Store or update coaching preferences."""
        now = datetime.now(timezone.utc).isoformat()
        prefs_json = json.dumps(prefs.to_dict())

        await self.connection.execute(
            """
            INSERT INTO health_coaching_preferences (id, preferences_json, updated_at)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                preferences_json = excluded.preferences_json,
                updated_at = excluded.updated_at
            """,
            (prefs_json, now),
        )
        await self.connection.commit()


# Module-level singleton
_health_database: Optional[HealthDatabase] = None


async def get_health_database() -> HealthDatabase:
    """Get or create singleton health database."""
    global _health_database
    if _health_database is None:
        _health_database = HealthDatabase()
        await _health_database.connect()
    return _health_database


async def close_health_database() -> None:
    """Close the singleton health database."""
    global _health_database
    if _health_database is not None:
        await _health_database.close()
        _health_database = None
