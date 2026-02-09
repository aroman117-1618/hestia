"""
Health manager for orchestrating health data operations.

Coordinates health metric sync, queries, aggregation,
and coaching preferences.
"""

import time as time_module
from datetime import datetime, date, timezone, timedelta
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import (
    HealthMetric,
    HealthCategory,
    HealthSyncResult,
    HealthCoachingPreferences,
    METRIC_CATEGORIES,
    METRIC_UNITS,
)
from .database import HealthDatabase, get_health_database


class HealthManager:
    """
    Manages health data lifecycle.

    Handles metric sync from iOS, data queries for briefings
    and chat tools, and coaching preference management.
    """

    def __init__(self, database: Optional[HealthDatabase] = None):
        """
        Initialize health manager.

        Args:
            database: HealthDatabase instance. If None, uses singleton.
        """
        self._database = database
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the health manager and its dependencies."""
        if self._database is None:
            self._database = await get_health_database()

        self.logger.info(
            "Health manager initialized",
            component=LogComponent.HEALTH,
        )

    async def close(self) -> None:
        """Close health manager resources."""
        self.logger.debug(
            "Health manager closed",
            component=LogComponent.HEALTH,
        )

    async def __aenter__(self) -> "HealthManager":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def database(self) -> HealthDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("Health manager not initialized. Call initialize() first.")
        return self._database

    # =========================================================================
    # Sync
    # =========================================================================

    async def process_sync(
        self,
        device_id: str,
        metrics_data: List[Dict[str, Any]],
        sync_date: str,
    ) -> HealthSyncResult:
        """
        Process a batch of health metrics from iOS.

        Args:
            device_id: Device that sent the sync.
            metrics_data: List of metric dictionaries from iOS.
            sync_date: Date the metrics cover (YYYY-MM-DD).

        Returns:
            HealthSyncResult with counts.
        """
        start_time = time_module.monotonic()

        # Convert raw data to HealthMetric objects
        metrics = []
        for data in metrics_data:
            try:
                metric = HealthMetric.create(
                    metric_type=data["metric_type"],
                    value=data["value"],
                    unit=data.get("unit", METRIC_UNITS.get(data["metric_type"], "unknown")),
                    start_date=datetime.fromisoformat(data["start_date"]),
                    end_date=datetime.fromisoformat(data["end_date"]),
                    source=data.get("source", "unknown"),
                    metadata=data.get("metadata"),
                )
                metrics.append(metric)
            except (KeyError, ValueError) as e:
                self.logger.warning(
                    f"Skipping invalid metric: {type(e).__name__}",
                    component=LogComponent.HEALTH,
                )

        # Store metrics (deduplication via UNIQUE constraint)
        stored, deduplicated = await self.database.store_metrics(metrics)

        duration_ms = (time_module.monotonic() - start_time) * 1000

        # Record sync
        result = HealthSyncResult.create(
            device_id=device_id,
            sync_date=sync_date,
            metrics_received=len(metrics_data),
            metrics_stored=stored,
            metrics_deduplicated=deduplicated,
            duration_ms=round(duration_ms, 1),
        )
        await self.database.store_sync(result)

        self.logger.info(
            f"Health sync complete: {stored} stored, {deduplicated} deduped",
            component=LogComponent.HEALTH,
            data={
                "device_id": device_id,
                "sync_date": sync_date,
                "received": len(metrics_data),
                "stored": stored,
                "deduplicated": deduplicated,
                "duration_ms": result.duration_ms,
            },
        )

        return result

    # =========================================================================
    # Queries
    # =========================================================================

    async def get_daily_summary(
        self,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated health summary for a day.

        Args:
            target_date: Date in YYYY-MM-DD format. Defaults to today.

        Returns:
            Dictionary with metrics organized by category.
        """
        if target_date is None:
            target_date = date.today().isoformat()

        return await self.database.get_daily_summary(target_date)

    async def get_metric_trend(
        self,
        metric_type: str,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Get trend data for a specific metric over time.

        Args:
            metric_type: HealthKit metric type string.
            days: Number of days to look back.

        Returns:
            Dictionary with data points, trend direction, and statistics.
        """
        metrics = await self.database.get_metrics_range(metric_type, days)

        if not metrics:
            return {
                "metric_type": metric_type,
                "days": days,
                "data_points": [],
                "trend": "no_data",
                "average": None,
                "min_value": None,
                "max_value": None,
            }

        # Group by date and aggregate
        daily_values: Dict[str, List[float]] = {}
        for m in metrics:
            day_key = m.start_date.strftime("%Y-%m-%d")
            if day_key not in daily_values:
                daily_values[day_key] = []
            daily_values[day_key].append(m.value)

        # Determine aggregation: SUM for cumulative, AVG for rates
        sum_types = {
            "stepCount", "distanceWalkingRunning", "activeEnergyBurned",
            "appleExerciseTime", "appleStandTime", "flightsClimbed",
            "dietaryEnergyConsumed", "dietaryProtein", "dietaryCarbohydrates",
            "dietaryFatTotal", "dietaryFiber", "dietaryWater",
            "sleepAnalysis", "mindfulSession",
        }

        data_points = []
        for day_key in sorted(daily_values.keys()):
            values = daily_values[day_key]
            if metric_type in sum_types:
                agg_value = sum(values)
            else:
                agg_value = sum(values) / len(values)
            data_points.append({
                "date": day_key,
                "value": round(agg_value, 1),
                "samples": len(values),
            })

        # Calculate trend
        all_values = [dp["value"] for dp in data_points]
        avg = sum(all_values) / len(all_values)
        min_val = min(all_values)
        max_val = max(all_values)

        # Simple trend: compare first half avg to second half avg
        trend = "stable"
        if len(data_points) >= 2:
            mid = len(data_points) // 2
            first_half = sum(dp["value"] for dp in data_points[:mid]) / mid
            second_half = sum(dp["value"] for dp in data_points[mid:]) / (len(data_points) - mid)
            threshold = avg * 0.05  # 5% change threshold
            if second_half - first_half > threshold:
                trend = "improving"
            elif first_half - second_half > threshold:
                trend = "declining"

        return {
            "metric_type": metric_type,
            "days": days,
            "data_points": data_points,
            "trend": trend,
            "average": round(avg, 1),
            "min_value": round(min_val, 1),
            "max_value": round(max_val, 1),
        }

    async def get_latest_vitals(self) -> Dict[str, Any]:
        """
        Get the most recent vital sign readings.

        Returns:
            Dictionary with latest values for each vital sign metric.
        """
        vital_types = [
            "heartRate", "restingHeartRate", "heartRateVariabilitySDNN",
            "walkingHeartRateAverage", "respiratoryRate", "oxygenSaturation",
            "bloodPressureSystolic", "bloodPressureDiastolic",
        ]

        vitals: Dict[str, Any] = {}
        for metric_type in vital_types:
            metric = await self.database.get_latest_metric(metric_type)
            if metric:
                vitals[metric_type] = {
                    "value": round(metric.value, 1),
                    "unit": metric.unit,
                    "date": metric.start_date.isoformat(),
                }

        return vitals

    async def get_sleep_analysis(self, days: int = 7) -> Dict[str, Any]:
        """
        Get sleep analysis over a period.

        Args:
            days: Number of days to analyze.

        Returns:
            Dictionary with sleep duration, stages, and consistency.
        """
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)

        metrics = await self.database.get_metrics("sleepAnalysis", start, end)

        if not metrics:
            return {
                "days": days,
                "total_nights": 0,
                "avg_hours": None,
                "nightly_data": [],
            }

        # Group by night (use start_date's date)
        nights: Dict[str, float] = {}
        for m in metrics:
            night_key = m.start_date.strftime("%Y-%m-%d")
            if night_key not in nights:
                nights[night_key] = 0.0
            nights[night_key] += m.value  # value is in minutes

        nightly_data = [
            {"date": d, "hours": round(mins / 60, 1)}
            for d, mins in sorted(nights.items())
        ]

        avg_hours = sum(d["hours"] for d in nightly_data) / len(nightly_data) if nightly_data else 0

        return {
            "days": days,
            "total_nights": len(nightly_data),
            "avg_hours": round(avg_hours, 1),
            "nightly_data": nightly_data,
        }

    async def get_activity_summary(self, days: int = 7) -> Dict[str, Any]:
        """
        Get activity summary over a period.

        Args:
            days: Number of days to summarize.

        Returns:
            Dictionary with daily activity metrics.
        """
        activity_types = [
            "stepCount", "distanceWalkingRunning", "activeEnergyBurned",
            "appleExerciseTime", "flightsClimbed",
        ]

        result: Dict[str, Any] = {"days": days, "daily_data": [], "averages": {}}

        for metric_type in activity_types:
            trend = await self.get_metric_trend(metric_type, days)
            if trend["average"] is not None:
                result["averages"][metric_type] = {
                    "avg": trend["average"],
                    "trend": trend["trend"],
                }

        return result

    # =========================================================================
    # Coaching Preferences
    # =========================================================================

    async def get_coaching_preferences(self) -> HealthCoachingPreferences:
        """Get coaching preferences (or defaults)."""
        return await self.database.get_coaching_preferences()

    async def update_coaching_preferences(
        self,
        **kwargs: Any,
    ) -> HealthCoachingPreferences:
        """
        Update coaching preferences.

        Args:
            **kwargs: Fields to update on HealthCoachingPreferences.

        Returns:
            Updated HealthCoachingPreferences.
        """
        prefs = await self.database.get_coaching_preferences()

        for key, value in kwargs.items():
            if hasattr(prefs, key) and value is not None:
                setattr(prefs, key, value)

        await self.database.update_coaching_preferences(prefs)

        self.logger.info(
            "Health coaching preferences updated",
            component=LogComponent.HEALTH,
            data={"fields": list(kwargs.keys())},
        )

        return prefs

    # =========================================================================
    # Sync History
    # =========================================================================

    async def list_syncs(self, limit: int = 20) -> List[HealthSyncResult]:
        """List recent sync results."""
        return await self.database.list_syncs(limit)


# Module-level singleton
_health_manager: Optional[HealthManager] = None


async def get_health_manager() -> HealthManager:
    """Get or create singleton health manager."""
    global _health_manager
    if _health_manager is None:
        _health_manager = HealthManager()
        await _health_manager.initialize()
    return _health_manager


async def close_health_manager() -> None:
    """Close the singleton health manager."""
    global _health_manager
    if _health_manager is not None:
        await _health_manager.close()
        _health_manager = None
