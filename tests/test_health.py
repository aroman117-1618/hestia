"""
Tests for Hestia Health module.

HealthKit data storage, aggregation, and coaching preferences.

Run with: python -m pytest tests/test_health.py -v
"""

import asyncio
import json
import tempfile
from datetime import datetime, date, time, timezone, timedelta
from pathlib import Path
from typing import Generator

import pytest
import pytest_asyncio

from hestia.health.models import (
    HealthMetric,
    HealthCategory,
    HealthSyncResult,
    HealthCoachingPreferences,
    METRIC_CATEGORIES,
    METRIC_UNITS,
)
from hestia.health.database import HealthDatabase
from hestia.health.manager import HealthManager


# ============== Fixtures ==============

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_metric() -> HealthMetric:
    """Create a sample health metric."""
    return HealthMetric.create(
        metric_type="stepCount",
        value=8432.0,
        unit="count",
        start_date=datetime(2026, 2, 15, 0, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 2, 15, 23, 59, tzinfo=timezone.utc),
        source="Apple Watch",
    )


@pytest.fixture
def sample_metrics() -> list:
    """Create a batch of sample metrics for a single day."""
    base_date = datetime(2026, 2, 15, tzinfo=timezone.utc)
    return [
        HealthMetric.create(
            metric_type="stepCount",
            value=8432.0,
            unit="count",
            start_date=base_date,
            end_date=base_date.replace(hour=23, minute=59),
            source="Apple Watch",
        ),
        HealthMetric.create(
            metric_type="activeEnergyBurned",
            value=523.0,
            unit="kcal",
            start_date=base_date,
            end_date=base_date.replace(hour=23, minute=59),
            source="Apple Watch",
        ),
        HealthMetric.create(
            metric_type="heartRate",
            value=72.0,
            unit="bpm",
            start_date=base_date.replace(hour=10),
            end_date=base_date.replace(hour=10, minute=5),
            source="Apple Watch",
        ),
        HealthMetric.create(
            metric_type="heartRate",
            value=85.0,
            unit="bpm",
            start_date=base_date.replace(hour=14),
            end_date=base_date.replace(hour=14, minute=5),
            source="Apple Watch",
        ),
        HealthMetric.create(
            metric_type="sleepAnalysis",
            value=420.0,
            unit="min",
            start_date=base_date.replace(hour=0),
            end_date=base_date.replace(hour=7),
            source="Apple Watch",
            metadata={"stage": "total"},
        ),
        HealthMetric.create(
            metric_type="bodyMass",
            value=175.5,
            unit="lb",
            start_date=base_date.replace(hour=7),
            end_date=base_date.replace(hour=7),
            source="Withings Scale",
        ),
    ]


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> HealthDatabase:
    """Create a test database."""
    db = HealthDatabase(db_path=temp_dir / "test_health.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(temp_dir: Path) -> HealthManager:
    """Create a test health manager."""
    db = HealthDatabase(db_path=temp_dir / "test_health.db")
    await db.connect()

    mgr = HealthManager(database=db)
    await mgr.initialize()

    yield mgr

    await mgr.close()
    await db.close()


# ============== Model Tests ==============

class TestHealthMetric:
    """Tests for HealthMetric model."""

    def test_create(self, sample_metric):
        """Test metric creation."""
        assert sample_metric.id.startswith("hm-")
        assert sample_metric.metric_type == "stepCount"
        assert sample_metric.category == HealthCategory.ACTIVITY
        assert sample_metric.value == 8432.0
        assert sample_metric.unit == "count"
        assert sample_metric.source == "Apple Watch"

    def test_category_mapping(self):
        """Test metric type to category mapping."""
        assert METRIC_CATEGORIES["stepCount"] == HealthCategory.ACTIVITY
        assert METRIC_CATEGORIES["heartRate"] == HealthCategory.HEART
        assert METRIC_CATEGORIES["bodyMass"] == HealthCategory.BODY
        assert METRIC_CATEGORIES["sleepAnalysis"] == HealthCategory.SLEEP
        assert METRIC_CATEGORIES["dietaryProtein"] == HealthCategory.NUTRITION
        assert METRIC_CATEGORIES["mindfulSession"] == HealthCategory.MINDFULNESS

    def test_to_dict(self, sample_metric):
        """Test serialization to dictionary."""
        d = sample_metric.to_dict()
        assert d["metric_type"] == "stepCount"
        assert d["category"] == "activity"
        assert d["value"] == 8432.0
        assert d["unit"] == "count"
        assert d["source"] == "Apple Watch"
        assert "start_date" in d
        assert "end_date" in d
        assert "synced_at" in d

    def test_from_dict(self, sample_metric):
        """Test deserialization from dictionary."""
        d = sample_metric.to_dict()
        restored = HealthMetric.from_dict(d)
        assert restored.metric_type == sample_metric.metric_type
        assert restored.value == sample_metric.value
        assert restored.category == sample_metric.category

    def test_to_sqlite_row(self, sample_metric):
        """Test SQLite row conversion."""
        row = sample_metric.to_sqlite_row()
        assert len(row) == 10
        assert row[0] == sample_metric.id
        assert row[1] == "stepCount"
        assert row[2] == "activity"
        assert row[3] == 8432.0

    def test_from_sqlite_row(self, sample_metric):
        """Test creation from SQLite row."""
        row_dict = {
            "id": sample_metric.id,
            "metric_type": "stepCount",
            "category": "activity",
            "value": 8432.0,
            "unit": "count",
            "start_date": sample_metric.start_date.isoformat(),
            "end_date": sample_metric.end_date.isoformat(),
            "source": "Apple Watch",
            "synced_at": sample_metric.synced_at.isoformat(),
            "metadata": None,
        }
        restored = HealthMetric.from_sqlite_row(row_dict)
        assert restored.metric_type == "stepCount"
        assert restored.value == 8432.0

    def test_metadata_serialization(self):
        """Test metadata JSON serialization."""
        metric = HealthMetric.create(
            metric_type="sleepAnalysis",
            value=120.0,
            unit="min",
            start_date=datetime(2026, 2, 15, 0, 0, tzinfo=timezone.utc),
            end_date=datetime(2026, 2, 15, 2, 0, tzinfo=timezone.utc),
            metadata={"stage": "asleepDeep"},
        )
        row = metric.to_sqlite_row()
        metadata_json = row[9]
        assert json.loads(metadata_json) == {"stage": "asleepDeep"}


class TestHealthCategory:
    """Tests for HealthCategory enum."""

    def test_values(self):
        """Test all category values."""
        assert HealthCategory.ACTIVITY.value == "activity"
        assert HealthCategory.HEART.value == "heart"
        assert HealthCategory.BODY.value == "body"
        assert HealthCategory.SLEEP.value == "sleep"
        assert HealthCategory.NUTRITION.value == "nutrition"
        assert HealthCategory.MINDFULNESS.value == "mindfulness"

    def test_metric_type_coverage(self):
        """Test that all 27 metric types are mapped."""
        assert len(METRIC_CATEGORIES) == 27


class TestHealthSyncResult:
    """Tests for HealthSyncResult model."""

    def test_create(self):
        """Test sync result creation."""
        result = HealthSyncResult.create(
            device_id="test-device",
            sync_date="2026-02-15",
            metrics_received=50,
            metrics_stored=45,
            metrics_deduplicated=5,
            duration_ms=125.3,
        )
        assert result.sync_id.startswith("sync-")
        assert result.device_id == "test-device"
        assert result.metrics_received == 50
        assert result.metrics_stored == 45
        assert result.metrics_deduplicated == 5
        assert result.duration_ms == 125.3

    def test_to_dict(self):
        """Test sync result serialization."""
        result = HealthSyncResult.create(
            device_id="test-device",
            sync_date="2026-02-15",
        )
        d = result.to_dict()
        assert "sync_id" in d
        assert d["device_id"] == "test-device"
        assert d["sync_date"] == "2026-02-15"


class TestHealthCoachingPreferences:
    """Tests for HealthCoachingPreferences model."""

    def test_defaults(self):
        """Test default coaching preferences."""
        prefs = HealthCoachingPreferences()
        assert prefs.enabled is True
        assert prefs.activity_coaching is True
        assert prefs.sleep_coaching is True
        assert prefs.daily_step_goal == 10000
        assert prefs.sleep_hours_goal == 8.0
        assert prefs.coaching_tone == "balanced"
        assert prefs.summary_time == time(20, 0)

    def test_to_dict(self):
        """Test serialization."""
        prefs = HealthCoachingPreferences()
        d = prefs.to_dict()
        assert d["enabled"] is True
        assert d["daily_step_goal"] == 10000
        assert d["coaching_tone"] == "balanced"
        assert d["summary_time"] == "20:00"

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "enabled": False,
            "daily_step_goal": 12000,
            "coaching_tone": "direct",
            "summary_time": "21:30",
        }
        prefs = HealthCoachingPreferences.from_dict(data)
        assert prefs.enabled is False
        assert prefs.daily_step_goal == 12000
        assert prefs.coaching_tone == "direct"
        assert prefs.summary_time == time(21, 30)

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = HealthCoachingPreferences(
            daily_step_goal=15000,
            coaching_tone="encouraging",
            sleep_coaching=False,
        )
        d = original.to_dict()
        restored = HealthCoachingPreferences.from_dict(d)
        assert restored.daily_step_goal == 15000
        assert restored.coaching_tone == "encouraging"
        assert restored.sleep_coaching is False


class TestMetricUnits:
    """Tests for METRIC_UNITS mapping."""

    def test_coverage(self):
        """All metric types have units defined."""
        for metric_type in METRIC_CATEGORIES:
            assert metric_type in METRIC_UNITS, f"Missing unit for {metric_type}"

    def test_known_units(self):
        """Check some known units."""
        assert METRIC_UNITS["stepCount"] == "count"
        assert METRIC_UNITS["heartRate"] == "bpm"
        assert METRIC_UNITS["bodyMass"] == "lb"
        assert METRIC_UNITS["sleepAnalysis"] == "min"


# ============== Database Tests ==============

class TestHealthDatabase:
    """Tests for HealthDatabase."""

    @pytest.mark.asyncio
    async def test_connect(self, database):
        """Test database connection."""
        assert database._connection is not None

    @pytest.mark.asyncio
    async def test_store_metrics(self, database, sample_metrics):
        """Test storing metrics."""
        stored, deduped = await database.store_metrics(sample_metrics)
        assert stored == len(sample_metrics)
        assert deduped == 0

    @pytest.mark.asyncio
    async def test_deduplication(self, database, sample_metrics):
        """Test that duplicate metrics are skipped."""
        # Store once
        stored1, deduped1 = await database.store_metrics(sample_metrics)
        assert stored1 == len(sample_metrics)
        assert deduped1 == 0

        # Store again — all should be deduplicated
        stored2, deduped2 = await database.store_metrics(sample_metrics)
        assert stored2 == 0
        assert deduped2 == len(sample_metrics)

    @pytest.mark.asyncio
    async def test_get_metrics(self, database, sample_metrics):
        """Test retrieving metrics by type and date range."""
        await database.store_metrics(sample_metrics)

        start = datetime(2026, 2, 14, tzinfo=timezone.utc)
        end = datetime(2026, 2, 16, tzinfo=timezone.utc)
        metrics = await database.get_metrics("stepCount", start, end)
        assert len(metrics) == 1
        assert metrics[0].value == 8432.0

    @pytest.mark.asyncio
    async def test_get_latest_metric(self, database, sample_metrics):
        """Test getting the most recent metric."""
        await database.store_metrics(sample_metrics)

        latest_hr = await database.get_latest_metric("heartRate")
        assert latest_hr is not None
        assert latest_hr.value == 85.0  # The 2PM reading

    @pytest.mark.asyncio
    async def test_get_daily_summary(self, database, sample_metrics):
        """Test daily summary aggregation."""
        await database.store_metrics(sample_metrics)

        summary = await database.get_daily_summary("2026-02-15")
        assert summary["date"] == "2026-02-15"

        # Activity: stepCount should be summed
        assert "stepCount" in summary["activity"]
        assert summary["activity"]["stepCount"]["value"] == 8432.0

        # Heart: heartRate should be averaged
        assert "heartRate" in summary["heart"]
        assert summary["heart"]["heartRate"]["avg"] == 78.5  # (72+85)/2

        # Body: bodyMass should be latest
        assert "bodyMass" in summary["body"]
        assert summary["body"]["bodyMass"]["value"] == 175.5

        # Sleep: should have total
        assert summary["sleep"]["total_minutes"] == 420.0
        assert summary["sleep"]["total_hours"] == 7.0

    @pytest.mark.asyncio
    async def test_get_metric_count(self, database, sample_metrics):
        """Test total metric count."""
        assert await database.get_metric_count() == 0
        await database.store_metrics(sample_metrics)
        assert await database.get_metric_count() == len(sample_metrics)

    @pytest.mark.asyncio
    async def test_store_sync(self, database):
        """Test storing sync results."""
        result = HealthSyncResult.create(
            device_id="test-device",
            sync_date="2026-02-15",
            metrics_received=50,
            metrics_stored=45,
        )
        sync_id = await database.store_sync(result)
        assert sync_id == result.sync_id

    @pytest.mark.asyncio
    async def test_list_syncs(self, database):
        """Test listing sync history."""
        for i in range(3):
            result = HealthSyncResult.create(
                device_id="test-device",
                sync_date=f"2026-02-{15+i}",
            )
            await database.store_sync(result)

        syncs = await database.list_syncs()
        assert len(syncs) == 3

    @pytest.mark.asyncio
    async def test_get_last_sync(self, database):
        """Test getting most recent sync."""
        result = HealthSyncResult.create(
            device_id="test-device",
            sync_date="2026-02-15",
        )
        await database.store_sync(result)

        last = await database.get_last_sync()
        assert last is not None
        assert last.sync_id == result.sync_id

    @pytest.mark.asyncio
    async def test_coaching_preferences_default(self, database):
        """Test that default preferences are returned when none set."""
        prefs = await database.get_coaching_preferences()
        assert prefs.enabled is True
        assert prefs.daily_step_goal == 10000

    @pytest.mark.asyncio
    async def test_coaching_preferences_roundtrip(self, database):
        """Test storing and retrieving coaching preferences."""
        prefs = HealthCoachingPreferences(
            daily_step_goal=15000,
            coaching_tone="encouraging",
            sleep_coaching=False,
        )
        await database.update_coaching_preferences(prefs)

        loaded = await database.get_coaching_preferences()
        assert loaded.daily_step_goal == 15000
        assert loaded.coaching_tone == "encouraging"
        assert loaded.sleep_coaching is False

    @pytest.mark.asyncio
    async def test_coaching_preferences_update(self, database):
        """Test updating existing coaching preferences."""
        prefs1 = HealthCoachingPreferences(daily_step_goal=8000)
        await database.update_coaching_preferences(prefs1)

        prefs2 = HealthCoachingPreferences(daily_step_goal=12000)
        await database.update_coaching_preferences(prefs2)

        loaded = await database.get_coaching_preferences()
        assert loaded.daily_step_goal == 12000


# ============== Manager Tests ==============

class TestHealthManager:
    """Tests for HealthManager."""

    @pytest.mark.asyncio
    async def test_process_sync(self, manager):
        """Test processing a sync from iOS."""
        metrics_data = [
            {
                "metric_type": "stepCount",
                "value": 8432.0,
                "unit": "count",
                "start_date": "2026-02-15T00:00:00+00:00",
                "end_date": "2026-02-15T23:59:00+00:00",
                "source": "Apple Watch",
            },
            {
                "metric_type": "heartRate",
                "value": 72.0,
                "unit": "bpm",
                "start_date": "2026-02-15T10:00:00+00:00",
                "end_date": "2026-02-15T10:05:00+00:00",
                "source": "Apple Watch",
            },
        ]

        result = await manager.process_sync(
            device_id="test-device",
            metrics_data=metrics_data,
            sync_date="2026-02-15",
        )

        assert result.metrics_received == 2
        assert result.metrics_stored == 2
        assert result.metrics_deduplicated == 0
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_process_sync_dedup(self, manager):
        """Test that re-syncing deduplicates."""
        metrics_data = [
            {
                "metric_type": "stepCount",
                "value": 8432.0,
                "unit": "count",
                "start_date": "2026-02-15T00:00:00+00:00",
                "end_date": "2026-02-15T23:59:00+00:00",
                "source": "Apple Watch",
            },
        ]

        result1 = await manager.process_sync("test-device", metrics_data, "2026-02-15")
        assert result1.metrics_stored == 1

        result2 = await manager.process_sync("test-device", metrics_data, "2026-02-15")
        assert result2.metrics_stored == 0
        assert result2.metrics_deduplicated == 1

    @pytest.mark.asyncio
    async def test_process_sync_invalid_metric(self, manager):
        """Test that invalid metrics are skipped."""
        metrics_data = [
            {"metric_type": "stepCount", "value": 100},  # Missing required fields
            {
                "metric_type": "heartRate",
                "value": 72.0,
                "start_date": "2026-02-15T10:00:00+00:00",
                "end_date": "2026-02-15T10:05:00+00:00",
            },
        ]

        result = await manager.process_sync("test-device", metrics_data, "2026-02-15")
        # First metric fails (missing start_date), second succeeds
        assert result.metrics_received == 2
        assert result.metrics_stored == 1

    @pytest.mark.asyncio
    async def test_get_daily_summary(self, manager):
        """Test daily summary after sync."""
        metrics_data = [
            {
                "metric_type": "stepCount",
                "value": 10000.0,
                "unit": "count",
                "start_date": "2026-02-15T00:00:00+00:00",
                "end_date": "2026-02-15T23:59:00+00:00",
            },
        ]
        await manager.process_sync("test-device", metrics_data, "2026-02-15")

        summary = await manager.get_daily_summary("2026-02-15")
        assert summary["date"] == "2026-02-15"
        assert "stepCount" in summary["activity"]
        assert summary["activity"]["stepCount"]["value"] == 10000.0

    @pytest.mark.asyncio
    async def test_get_metric_trend(self, manager):
        """Test metric trend calculation."""
        # Store 7 days of step data
        for i in range(7):
            dt = datetime(2026, 2, 9 + i, tzinfo=timezone.utc)
            metrics_data = [
                {
                    "metric_type": "stepCount",
                    "value": 8000.0 + (i * 500),  # Increasing trend
                    "unit": "count",
                    "start_date": dt.isoformat(),
                    "end_date": dt.replace(hour=23, minute=59).isoformat(),
                },
            ]
            await manager.process_sync("test-device", metrics_data, dt.strftime("%Y-%m-%d"))

        trend = await manager.get_metric_trend("stepCount", days=7)
        assert trend["metric_type"] == "stepCount"
        assert trend["days"] == 7
        assert len(trend["data_points"]) == 7
        assert trend["trend"] == "improving"
        assert trend["average"] is not None
        assert trend["min_value"] is not None
        assert trend["max_value"] is not None

    @pytest.mark.asyncio
    async def test_get_metric_trend_no_data(self, manager):
        """Test trend with no data."""
        trend = await manager.get_metric_trend("stepCount", days=7)
        assert trend["trend"] == "no_data"
        assert trend["data_points"] == []

    @pytest.mark.asyncio
    async def test_get_latest_vitals(self, manager):
        """Test getting latest vital signs."""
        metrics_data = [
            {
                "metric_type": "heartRate",
                "value": 72.0,
                "unit": "bpm",
                "start_date": "2026-02-15T10:00:00+00:00",
                "end_date": "2026-02-15T10:05:00+00:00",
            },
            {
                "metric_type": "restingHeartRate",
                "value": 58.0,
                "unit": "bpm",
                "start_date": "2026-02-15T06:00:00+00:00",
                "end_date": "2026-02-15T06:00:00+00:00",
            },
        ]
        await manager.process_sync("test-device", metrics_data, "2026-02-15")

        vitals = await manager.get_latest_vitals()
        assert "heartRate" in vitals
        assert vitals["heartRate"]["value"] == 72.0
        assert "restingHeartRate" in vitals
        assert vitals["restingHeartRate"]["value"] == 58.0

    @pytest.mark.asyncio
    async def test_get_sleep_analysis(self, manager):
        """Test sleep analysis."""
        metrics_data = [
            {
                "metric_type": "sleepAnalysis",
                "value": 420.0,
                "unit": "min",
                "start_date": "2026-02-15T00:00:00+00:00",
                "end_date": "2026-02-15T07:00:00+00:00",
                "metadata": {"stage": "total"},
            },
        ]
        await manager.process_sync("test-device", metrics_data, "2026-02-15")

        analysis = await manager.get_sleep_analysis(days=7)
        assert analysis["total_nights"] == 1
        assert analysis["avg_hours"] == 7.0

    @pytest.mark.asyncio
    async def test_get_activity_summary(self, manager):
        """Test activity summary."""
        metrics_data = [
            {
                "metric_type": "stepCount",
                "value": 10000.0,
                "start_date": "2026-02-15T00:00:00+00:00",
                "end_date": "2026-02-15T23:59:00+00:00",
            },
        ]
        await manager.process_sync("test-device", metrics_data, "2026-02-15")

        summary = await manager.get_activity_summary(days=7)
        assert summary["days"] == 7
        assert "stepCount" in summary["averages"]

    @pytest.mark.asyncio
    async def test_coaching_preferences(self, manager):
        """Test coaching preference management."""
        # Get defaults
        prefs = await manager.get_coaching_preferences()
        assert prefs.daily_step_goal == 10000

        # Update
        updated = await manager.update_coaching_preferences(
            daily_step_goal=15000,
            coaching_tone="direct",
        )
        assert updated.daily_step_goal == 15000
        assert updated.coaching_tone == "direct"

        # Verify persistence
        loaded = await manager.get_coaching_preferences()
        assert loaded.daily_step_goal == 15000

    @pytest.mark.asyncio
    async def test_list_syncs(self, manager):
        """Test sync history listing."""
        await manager.process_sync("device-1", [], "2026-02-15")
        await manager.process_sync("device-1", [], "2026-02-16")

        syncs = await manager.list_syncs()
        assert len(syncs) == 2
