"""
Health Data (HealthKit) schemas.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthMetricPayload(BaseModel):
    """A single health metric from iOS HealthKit."""
    metric_type: str = Field(..., description="HKQuantityType identifier (e.g., 'stepCount')")
    value: float = Field(..., description="Numeric value")
    unit: str = Field("unknown", description="Unit string (e.g., 'count', 'bpm')")
    start_date: str = Field(..., description="ISO 8601 start time")
    end_date: str = Field(..., description="ISO 8601 end time")
    source: str = Field("unknown", description="Source device/app name")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Extra metadata")


class HealthSyncRequest(BaseModel):
    """Batch sync request from iOS."""
    metrics: List[HealthMetricPayload] = Field(..., description="Health metrics to sync")
    sync_date: str = Field(..., description="Date covered (YYYY-MM-DD)")


class HealthSyncResponse(BaseModel):
    """Sync result."""
    sync_id: str
    metrics_received: int
    metrics_stored: int
    metrics_deduplicated: int
    duration_ms: float


class HealthSummaryResponse(BaseModel):
    """Daily health summary."""
    date: str
    activity: Dict[str, Any] = Field(default_factory=dict)
    heart: Dict[str, Any] = Field(default_factory=dict)
    sleep: Dict[str, Any] = Field(default_factory=dict)
    body: Dict[str, Any] = Field(default_factory=dict)
    nutrition: Dict[str, Any] = Field(default_factory=dict)
    mindfulness: Dict[str, Any] = Field(default_factory=dict)


class HealthTrendResponse(BaseModel):
    """Metric trend data."""
    metric_type: str
    days: int
    data_points: List[Dict[str, Any]]
    trend: str
    average: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class CoachingPreferencesRequest(BaseModel):
    """Update coaching preferences (all fields optional)."""
    enabled: Optional[bool] = None
    activity_coaching: Optional[bool] = None
    sleep_coaching: Optional[bool] = None
    nutrition_coaching: Optional[bool] = None
    heart_coaching: Optional[bool] = None
    mindfulness_coaching: Optional[bool] = None
    daily_summary: Optional[bool] = None
    summary_time: Optional[str] = None
    goal_alerts: Optional[bool] = None
    anomaly_alerts: Optional[bool] = None
    daily_step_goal: Optional[int] = None
    daily_active_cal_goal: Optional[int] = None
    sleep_hours_goal: Optional[float] = None
    daily_water_ml_goal: Optional[int] = None
    coaching_tone: Optional[str] = None


class CoachingPreferencesResponse(BaseModel):
    """Coaching preferences."""
    preferences: Dict[str, Any]
    updated_at: str


class SyncHistoryItem(BaseModel):
    """A sync history entry."""
    sync_id: str
    device_id: str
    timestamp: str
    metrics_received: int
    metrics_stored: int
    metrics_deduplicated: int
    sync_date: str
    duration_ms: float


class SyncHistoryResponse(BaseModel):
    """Sync history list."""
    syncs: List[SyncHistoryItem]
    count: int
