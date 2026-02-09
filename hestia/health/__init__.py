"""
Health module — HealthKit data storage and analysis.

Receives health metrics synced from iOS HealthKit via REST API,
stores raw data in SQLite, and provides analysis/query capabilities
for briefings and chat tools.
"""

from .manager import HealthManager, get_health_manager, close_health_manager
from .models import (
    HealthMetric,
    HealthCategory,
    HealthSyncResult,
    HealthCoachingPreferences,
)
from .database import HealthDatabase, get_health_database, close_health_database

__all__ = [
    "HealthManager",
    "get_health_manager",
    "close_health_manager",
    "HealthMetric",
    "HealthCategory",
    "HealthSyncResult",
    "HealthCoachingPreferences",
    "HealthDatabase",
    "get_health_database",
    "close_health_database",
]
