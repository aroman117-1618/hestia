"""
Data models for the Health module.

Health metrics synced from iOS HealthKit, coaching preferences,
and sync result tracking.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class HealthCategory(Enum):
    """Categories of health metrics."""
    ACTIVITY = "activity"
    HEART = "heart"
    BODY = "body"
    SLEEP = "sleep"
    NUTRITION = "nutrition"
    MINDFULNESS = "mindfulness"


# Map metric types to their categories
METRIC_CATEGORIES: Dict[str, HealthCategory] = {
    # Activity (7)
    "stepCount": HealthCategory.ACTIVITY,
    "distanceWalkingRunning": HealthCategory.ACTIVITY,
    "activeEnergyBurned": HealthCategory.ACTIVITY,
    "appleExerciseTime": HealthCategory.ACTIVITY,
    "appleStandTime": HealthCategory.ACTIVITY,
    "flightsClimbed": HealthCategory.ACTIVITY,
    "vo2Max": HealthCategory.ACTIVITY,
    # Heart (4)
    "heartRate": HealthCategory.HEART,
    "restingHeartRate": HealthCategory.HEART,
    "heartRateVariabilitySDNN": HealthCategory.HEART,
    "walkingHeartRateAverage": HealthCategory.HEART,
    # Body (4)
    "bodyMass": HealthCategory.BODY,
    "bodyMassIndex": HealthCategory.BODY,
    "bodyFatPercentage": HealthCategory.BODY,
    "leanBodyMass": HealthCategory.BODY,
    # Sleep (1 category type)
    "sleepAnalysis": HealthCategory.SLEEP,
    # Nutrition (6)
    "dietaryEnergyConsumed": HealthCategory.NUTRITION,
    "dietaryProtein": HealthCategory.NUTRITION,
    "dietaryCarbohydrates": HealthCategory.NUTRITION,
    "dietaryFatTotal": HealthCategory.NUTRITION,
    "dietaryFiber": HealthCategory.NUTRITION,
    "dietaryWater": HealthCategory.NUTRITION,
    # Vitals (4)
    "respiratoryRate": HealthCategory.HEART,
    "oxygenSaturation": HealthCategory.HEART,
    "bloodPressureSystolic": HealthCategory.HEART,
    "bloodPressureDiastolic": HealthCategory.HEART,
    # Mindfulness (1 category type)
    "mindfulSession": HealthCategory.MINDFULNESS,
}

# Default units per metric type
METRIC_UNITS: Dict[str, str] = {
    "stepCount": "count",
    "distanceWalkingRunning": "mi",
    "activeEnergyBurned": "kcal",
    "appleExerciseTime": "min",
    "appleStandTime": "min",
    "flightsClimbed": "count",
    "vo2Max": "mL/kg/min",
    "heartRate": "bpm",
    "restingHeartRate": "bpm",
    "heartRateVariabilitySDNN": "ms",
    "walkingHeartRateAverage": "bpm",
    "bodyMass": "lb",
    "bodyMassIndex": "count",
    "bodyFatPercentage": "%",
    "leanBodyMass": "lb",
    "sleepAnalysis": "min",
    "dietaryEnergyConsumed": "kcal",
    "dietaryProtein": "g",
    "dietaryCarbohydrates": "g",
    "dietaryFatTotal": "g",
    "dietaryFiber": "g",
    "dietaryWater": "mL",
    "respiratoryRate": "breaths/min",
    "oxygenSaturation": "%",
    "bloodPressureSystolic": "mmHg",
    "bloodPressureDiastolic": "mmHg",
    "mindfulSession": "min",
}


@dataclass
class HealthMetric:
    """
    A single health data point synced from iOS HealthKit.

    Attributes:
        id: Unique metric identifier.
        metric_type: HKQuantityType/HKCategoryType identifier string.
        category: Metric category (activity, heart, body, etc.).
        value: Numeric value.
        unit: Unit string (e.g., "count", "bpm", "kcal").
        start_date: Sample start time.
        end_date: Sample end time.
        source: Source device/app name.
        synced_at: When synced to backend.
        metadata: Extra metadata (e.g., sleep stage).
    """
    id: str
    metric_type: str
    category: HealthCategory
    value: float
    unit: str
    start_date: datetime
    end_date: datetime
    source: str = "unknown"
    synced_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        metric_type: str,
        value: float,
        unit: str,
        start_date: datetime,
        end_date: datetime,
        source: str = "unknown",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "HealthMetric":
        """Factory method to create a new health metric."""
        category = METRIC_CATEGORIES.get(metric_type, HealthCategory.ACTIVITY)
        return cls(
            id=f"hm-{uuid4().hex[:12]}",
            metric_type=metric_type,
            category=category,
            value=value,
            unit=unit,
            start_date=start_date,
            end_date=end_date,
            source=source,
            synced_at=datetime.now(timezone.utc),
            metadata=metadata,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "metric_type": self.metric_type,
            "category": self.category.value,
            "value": self.value,
            "unit": self.unit,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "source": self.source,
            "synced_at": self.synced_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthMetric":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            metric_type=data["metric_type"],
            category=HealthCategory(data["category"]),
            value=data["value"],
            unit=data["unit"],
            start_date=datetime.fromisoformat(data["start_date"]),
            end_date=datetime.fromisoformat(data["end_date"]),
            source=data.get("source", "unknown"),
            synced_at=datetime.fromisoformat(data["synced_at"]),
            metadata=data.get("metadata"),
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.metric_type,
            self.category.value,
            self.value,
            self.unit,
            self.start_date.isoformat(),
            self.end_date.isoformat(),
            self.source,
            self.synced_at.isoformat(),
            json.dumps(self.metadata) if self.metadata else None,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "HealthMetric":
        """Create from SQLite row (dict)."""
        metadata = None
        if row.get("metadata"):
            try:
                metadata = json.loads(row["metadata"])
            except (json.JSONDecodeError, ValueError):
                pass

        return cls(
            id=row["id"],
            metric_type=row["metric_type"],
            category=HealthCategory(row["category"]),
            value=row["value"],
            unit=row["unit"],
            start_date=datetime.fromisoformat(row["start_date"]),
            end_date=datetime.fromisoformat(row["end_date"]),
            source=row.get("source", "unknown"),
            synced_at=datetime.fromisoformat(row["synced_at"]),
            metadata=metadata,
        )


@dataclass
class HealthSyncResult:
    """
    Result of a sync operation from iOS.

    Attributes:
        sync_id: Unique sync identifier.
        device_id: Device that synced.
        timestamp: When sync occurred.
        metrics_received: Total metrics in request.
        metrics_stored: New metrics stored.
        metrics_deduplicated: Duplicate metrics skipped.
        sync_date: Date the metrics cover (YYYY-MM-DD).
        duration_ms: Sync duration in milliseconds.
    """
    sync_id: str
    device_id: str
    timestamp: datetime
    metrics_received: int
    metrics_stored: int
    metrics_deduplicated: int
    sync_date: str
    duration_ms: float = 0.0

    @classmethod
    def create(
        cls,
        device_id: str,
        sync_date: str,
        metrics_received: int = 0,
        metrics_stored: int = 0,
        metrics_deduplicated: int = 0,
        duration_ms: float = 0.0,
    ) -> "HealthSyncResult":
        """Factory method to create a new sync result."""
        return cls(
            sync_id=f"sync-{uuid4().hex[:12]}",
            device_id=device_id,
            timestamp=datetime.now(timezone.utc),
            metrics_received=metrics_received,
            metrics_stored=metrics_stored,
            metrics_deduplicated=metrics_deduplicated,
            sync_date=sync_date,
            duration_ms=duration_ms,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "sync_id": self.sync_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp.isoformat(),
            "metrics_received": self.metrics_received,
            "metrics_stored": self.metrics_stored,
            "metrics_deduplicated": self.metrics_deduplicated,
            "sync_date": self.sync_date,
            "duration_ms": self.duration_ms,
        }

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.sync_id,
            self.device_id,
            self.timestamp.isoformat(),
            self.metrics_received,
            self.metrics_stored,
            self.metrics_deduplicated,
            self.sync_date,
            self.duration_ms,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "HealthSyncResult":
        """Create from SQLite row (dict)."""
        return cls(
            sync_id=row["id"],
            device_id=row["device_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metrics_received=row["metrics_received"],
            metrics_stored=row["metrics_stored"],
            metrics_deduplicated=row["metrics_deduplicated"],
            sync_date=row["sync_date"],
            duration_ms=row.get("duration_ms", 0.0),
        )


@dataclass
class HealthCoachingPreferences:
    """
    User preferences for health coaching.

    Controls what coaching Hestia provides, notification settings,
    personal goals, and coaching tone.
    """
    # Master toggle
    enabled: bool = True

    # Coaching domains
    activity_coaching: bool = True
    sleep_coaching: bool = True
    nutrition_coaching: bool = True
    heart_coaching: bool = True
    mindfulness_coaching: bool = True

    # Notification preferences
    daily_summary: bool = True
    summary_time: time = field(default_factory=lambda: time(20, 0))  # 8 PM
    goal_alerts: bool = True
    anomaly_alerts: bool = True

    # Goals
    daily_step_goal: int = 10000
    daily_active_cal_goal: int = 500
    sleep_hours_goal: float = 8.0
    daily_water_ml_goal: int = 2500

    # Coaching tone: "encouraging", "balanced", "direct"
    coaching_tone: str = "balanced"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "activity_coaching": self.activity_coaching,
            "sleep_coaching": self.sleep_coaching,
            "nutrition_coaching": self.nutrition_coaching,
            "heart_coaching": self.heart_coaching,
            "mindfulness_coaching": self.mindfulness_coaching,
            "daily_summary": self.daily_summary,
            "summary_time": self.summary_time.strftime("%H:%M"),
            "goal_alerts": self.goal_alerts,
            "anomaly_alerts": self.anomaly_alerts,
            "daily_step_goal": self.daily_step_goal,
            "daily_active_cal_goal": self.daily_active_cal_goal,
            "sleep_hours_goal": self.sleep_hours_goal,
            "daily_water_ml_goal": self.daily_water_ml_goal,
            "coaching_tone": self.coaching_tone,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthCoachingPreferences":
        """Create from dictionary."""
        prefs = cls()

        if "enabled" in data:
            prefs.enabled = data["enabled"]
        if "activity_coaching" in data:
            prefs.activity_coaching = data["activity_coaching"]
        if "sleep_coaching" in data:
            prefs.sleep_coaching = data["sleep_coaching"]
        if "nutrition_coaching" in data:
            prefs.nutrition_coaching = data["nutrition_coaching"]
        if "heart_coaching" in data:
            prefs.heart_coaching = data["heart_coaching"]
        if "mindfulness_coaching" in data:
            prefs.mindfulness_coaching = data["mindfulness_coaching"]
        if "daily_summary" in data:
            prefs.daily_summary = data["daily_summary"]
        if "summary_time" in data:
            h, m = map(int, data["summary_time"].split(":"))
            prefs.summary_time = time(h, m)
        if "goal_alerts" in data:
            prefs.goal_alerts = data["goal_alerts"]
        if "anomaly_alerts" in data:
            prefs.anomaly_alerts = data["anomaly_alerts"]
        if "daily_step_goal" in data:
            prefs.daily_step_goal = data["daily_step_goal"]
        if "daily_active_cal_goal" in data:
            prefs.daily_active_cal_goal = data["daily_active_cal_goal"]
        if "sleep_hours_goal" in data:
            prefs.sleep_hours_goal = data["sleep_hours_goal"]
        if "daily_water_ml_goal" in data:
            prefs.daily_water_ml_goal = data["daily_water_ml_goal"]
        if "coaching_tone" in data:
            prefs.coaching_tone = data["coaching_tone"]

        return prefs
