"""Tests for the hestia.learning module (Sprint 15).

Covers: models, database, MetaMonitor, MemoryHealthMonitor, TriggerMonitor, API routes.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.learning.models import (
    MetaMonitorReport,
    RoutingQualityStats,
    MemoryHealthSnapshot,
    TriggerAlert,
    ReportStatus,
    CorrectionType,
    MIN_SAMPLE_SIZE,
)
from hestia.learning.database import LearningDatabase
from hestia.learning.meta_monitor import MetaMonitorManager
from hestia.learning.memory_health import MemoryHealthMonitor
from hestia.learning.trigger_monitor import TriggerMonitor


# ─── Model Tests ───────────────────────────────────────────────────────────


class TestModels:

    def test_meta_monitor_report_creation(self):
        report = MetaMonitorReport(
            id="r1", user_id="u1",
            timestamp=datetime.now(timezone.utc),
            status=ReportStatus.COMPLETE,
            total_outcomes=50, positive_ratio=0.72,
            routing_stats=None, confusion_sessions=[],
            avg_latency_ms=1200.0, latency_trend="stable",
            sample_size_sufficient=True,
        )
        d = report.to_dict()
        assert d["total_outcomes"] == 50
        assert d["positive_ratio"] == 0.72

    def test_meta_monitor_report_roundtrip(self):
        report = MetaMonitorReport(
            id="r2", user_id="u1",
            timestamp=datetime.now(timezone.utc),
            status=ReportStatus.INSUFFICIENT_DATA,
            total_outcomes=5, positive_ratio=None,
            routing_stats=None, confusion_sessions=[],
            avg_latency_ms=None, latency_trend=None,
            sample_size_sufficient=False,
        )
        d = report.to_dict()
        restored = MetaMonitorReport.from_dict(d)
        assert restored.status == ReportStatus.INSUFFICIENT_DATA
        assert not restored.sample_size_sufficient

    def test_routing_quality_stats(self):
        stats = RoutingQualityStats(
            route="HESTIA_SOLO", total_count=30,
            positive_count=22, negative_count=8,
            positive_ratio=0.733,
        )
        assert stats.positive_ratio == pytest.approx(0.733)

    def test_memory_health_snapshot(self):
        snap = MemoryHealthSnapshot(
            id="s1", user_id="u1",
            timestamp=datetime.now(timezone.utc),
            chunk_count=1200,
            chunk_count_by_source={"conversation": 800, "claude_import": 400},
            redundancy_estimate_pct=12.5,
            entity_count=150, fact_count=300,
            stale_entity_count=10, contradiction_count=3,
            community_count=8,
        )
        d = snap.to_dict()
        assert d["chunk_count"] == 1200
        restored = MemoryHealthSnapshot.from_dict(d)
        assert restored.redundancy_estimate_pct == 12.5

    def test_trigger_alert(self):
        alert = TriggerAlert(
            id="a1", user_id="u1",
            trigger_name="memory_total_chunks",
            current_value=5200.0, threshold_value=5000.0,
            direction="above",
            message="Memory chunk count exceeded 5,000.",
            timestamp=datetime.now(timezone.utc),
        )
        d = alert.to_dict()
        assert d["trigger_name"] == "memory_total_chunks"
        assert not d["acknowledged"]

    def test_correction_type_enum(self):
        assert CorrectionType.TIMEZONE.value == "timezone"
        assert CorrectionType.FACTUAL.value == "factual"
        assert CorrectionType.PREFERENCE.value == "preference"
        assert CorrectionType.TOOL_USAGE.value == "tool_usage"


# ─── Database Tests ────────────────────────────────────────────────────────


class TestLearningDatabase:

    @pytest.fixture
    async def db(self, tmp_path):
        database = LearningDatabase(str(tmp_path / "learning.db"))
        await database.connect()
        yield database
        await database.close()

    @pytest.mark.asyncio
    async def test_store_and_get_report(self, db):
        report = MetaMonitorReport(
            id="r1", user_id="u1",
            timestamp=datetime.now(timezone.utc),
            status=ReportStatus.COMPLETE,
            total_outcomes=50, positive_ratio=0.72,
            routing_stats=None, confusion_sessions=[],
            avg_latency_ms=1200.0, latency_trend="stable",
            sample_size_sufficient=True,
        )
        await db.store_report(report)
        latest = await db.get_latest_report("u1")
        assert latest is not None
        assert latest.id == "r1"
        assert latest.positive_ratio == 0.72

    @pytest.mark.asyncio
    async def test_store_and_get_health_snapshot(self, db):
        snap = MemoryHealthSnapshot(
            id="s1", user_id="u1",
            timestamp=datetime.now(timezone.utc),
            chunk_count=1200,
            chunk_count_by_source={"conversation": 800},
            redundancy_estimate_pct=12.5,
            entity_count=150, fact_count=300,
            stale_entity_count=10, contradiction_count=3,
            community_count=8,
        )
        await db.store_health_snapshot(snap)
        latest = await db.get_latest_health_snapshot("u1")
        assert latest is not None
        assert latest.chunk_count == 1200

    @pytest.mark.asyncio
    async def test_health_snapshot_history(self, db):
        for i in range(5):
            snap = MemoryHealthSnapshot(
                id=f"s{i}", user_id="u1",
                timestamp=datetime.now(timezone.utc) - timedelta(days=i),
                chunk_count=1000 + i * 100,
                chunk_count_by_source={}, redundancy_estimate_pct=10.0,
                entity_count=100, fact_count=200,
                stale_entity_count=5, contradiction_count=1,
                community_count=4,
            )
            await db.store_health_snapshot(snap)
        history = await db.get_health_snapshot_history("u1", days=3)
        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_trigger_alert_lifecycle(self, db):
        alert = TriggerAlert(
            id="a1", user_id="u1",
            trigger_name="memory_total_chunks",
            current_value=5200.0, threshold_value=5000.0,
            direction="above", message="Chunks exceeded 5000.",
            timestamp=datetime.now(timezone.utc),
        )
        await db.store_trigger_alert(alert)

        unacked = await db.get_unacknowledged_alerts("u1")
        assert len(unacked) == 1
        assert unacked[0].trigger_name == "memory_total_chunks"

        await db.acknowledge_alert("a1", "u1")
        unacked = await db.get_unacknowledged_alerts("u1")
        assert len(unacked) == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_reports(self, db):
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        report = MetaMonitorReport(
            id="old-r", user_id="u1", timestamp=old_time,
            status=ReportStatus.COMPLETE, total_outcomes=10,
            positive_ratio=0.5, routing_stats=None,
            confusion_sessions=[], avg_latency_ms=1000.0,
            latency_trend="stable", sample_size_sufficient=True,
        )
        await db.store_report(report)
        deleted = await db.cleanup_old_reports(max_age_days=7)
        assert deleted >= 1
        latest = await db.get_latest_report("u1")
        assert latest is None

    @pytest.mark.asyncio
    async def test_get_last_trigger_fire(self, db):
        alert = TriggerAlert(
            id="a3", user_id="u1", trigger_name="latency",
            current_value=3500.0, threshold_value=3000.0,
            direction="above", message="High latency.",
            timestamp=datetime.now(timezone.utc),
        )
        await db.store_trigger_alert(alert)
        last = await db.get_last_trigger_fire("u1", "latency")
        assert last is not None
        assert await db.get_last_trigger_fire("u1", "nonexistent") is None


# ─── MetaMonitor Tests ─────────────────────────────────────────────────────


def _make_outcome_rows(count, signal="accepted", route="HESTIA_SOLO", duration_ms=1000):
    """Helper to create mock outcome query results."""
    now = datetime.now(timezone.utc)
    return [
        {
            "id": f"o{i}", "user_id": "u1", "session_id": f"s{i % 5}",
            "implicit_signal": signal, "agent_route": route,
            "duration_ms": duration_ms,
            "timestamp": (now - timedelta(hours=i)).isoformat(),
        }
        for i in range(count)
    ]


class TestMetaMonitor:

    @pytest.fixture
    def monitor(self):
        outcome_db = AsyncMock()
        routing_audit_db = AsyncMock()
        learning_db = AsyncMock()
        learning_db.store_report = AsyncMock()
        learning_db.cleanup_old_reports = AsyncMock(return_value=0)
        return MetaMonitorManager(
            outcome_db=outcome_db,
            routing_audit_db=routing_audit_db,
            learning_db=learning_db,
        )

    @pytest.mark.asyncio
    async def test_insufficient_data(self, monitor):
        monitor._outcome_db.get_outcomes = AsyncMock(return_value=_make_outcome_rows(5))
        report = await monitor.analyze(user_id="u1")
        assert report.status == ReportStatus.INSUFFICIENT_DATA
        assert not report.sample_size_sufficient

    @pytest.mark.asyncio
    async def test_routing_quality(self, monitor):
        outcomes = (
            _make_outcome_rows(15, signal="accepted", route="HESTIA_SOLO")
            + _make_outcome_rows(10, signal="accepted", route="ARTEMIS")
            + _make_outcome_rows(5, signal="quick_followup", route="HESTIA_SOLO")
        )
        monitor._outcome_db.get_outcomes = AsyncMock(return_value=outcomes)
        report = await monitor.analyze(user_id="u1")
        assert report.status == ReportStatus.COMPLETE
        assert report.routing_stats is not None
        artemis = next((s for s in report.routing_stats if s.route == "ARTEMIS"), None)
        assert artemis is not None
        assert artemis.positive_ratio == 1.0

    @pytest.mark.asyncio
    async def test_confusion_detection(self, monitor):
        now = datetime.now(timezone.utc)
        outcomes = []
        # Session s0: 8 messages, 6 quick_followup → confusion
        for i in range(8):
            outcomes.append({
                "id": f"o{i}", "user_id": "u1", "session_id": "s0",
                "implicit_signal": "quick_followup" if i < 6 else "accepted",
                "agent_route": "HESTIA_SOLO", "duration_ms": 1000,
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
            })
        # Session s1: 10 normal → no confusion
        for i in range(10):
            outcomes.append({
                "id": f"n{i}", "user_id": "u1", "session_id": "s1",
                "implicit_signal": "accepted",
                "agent_route": "HESTIA_SOLO", "duration_ms": 1000,
                "timestamp": (now - timedelta(minutes=i)).isoformat(),
            })
        # Pad to meet MIN_SAMPLE_SIZE
        outcomes.extend(_make_outcome_rows(10, signal="accepted"))
        monitor._outcome_db.get_outcomes = AsyncMock(return_value=outcomes)
        report = await monitor.analyze(user_id="u1")
        assert "s0" in report.confusion_sessions
        assert "s1" not in report.confusion_sessions

    @pytest.mark.asyncio
    async def test_latency_trend_stable(self, monitor):
        outcomes = _make_outcome_rows(30, duration_ms=1200)
        monitor._outcome_db.get_outcomes = AsyncMock(return_value=outcomes)
        report = await monitor.analyze(user_id="u1")
        assert report.latency_trend == "stable"

    @pytest.mark.asyncio
    async def test_cleanup_called(self, monitor):
        monitor._outcome_db.get_outcomes = AsyncMock(return_value=_make_outcome_rows(5))
        await monitor.analyze(user_id="u1")
        monitor._learning_db.cleanup_old_reports.assert_called_once_with(max_age_days=7)


# ─── Memory Health Tests ───────────────────────────────────────────────────


class TestMemoryHealth:

    @pytest.mark.asyncio
    async def test_collect_snapshot_basic(self):
        mock_memory = AsyncMock()
        mock_memory._vector_store = MagicMock()
        mock_memory._vector_store.count = MagicMock(return_value=1200)
        mock_memory._db = AsyncMock()

        mock_research = AsyncMock()
        mock_research.count_entities = AsyncMock(return_value=150)
        mock_research.count_facts = AsyncMock(return_value=300)
        mock_research.list_communities = AsyncMock(return_value=[
            MagicMock(id="c1"), MagicMock(id="c2"),
        ])

        mock_learning = AsyncMock()

        monitor = MemoryHealthMonitor(
            memory_manager=mock_memory,
            research_db=mock_research,
            learning_db=mock_learning,
        )
        snapshot = await monitor.collect_snapshot(user_id="u1")

        assert isinstance(snapshot, MemoryHealthSnapshot)
        assert snapshot.chunk_count == 1200
        assert snapshot.entity_count == 150
        assert snapshot.community_count == 2
        mock_learning.store_health_snapshot.assert_called_once()

    @pytest.mark.asyncio
    async def test_collect_snapshot_empty(self):
        mock_memory = AsyncMock()
        mock_memory._vector_store = MagicMock()
        mock_memory._vector_store.count = MagicMock(return_value=0)

        mock_research = AsyncMock()
        mock_research.count_entities = AsyncMock(return_value=0)
        mock_research.count_facts = AsyncMock(return_value=0)
        mock_research.list_communities = AsyncMock(return_value=[])

        mock_learning = AsyncMock()

        monitor = MemoryHealthMonitor(
            memory_manager=mock_memory,
            research_db=mock_research,
            learning_db=mock_learning,
        )
        snapshot = await monitor.collect_snapshot(user_id="u1")
        assert snapshot.chunk_count == 0
        assert snapshot.entity_count == 0


# ─── Trigger Monitor Tests ─────────────────────────────────────────────────


class TestTriggerMonitor:

    @pytest.fixture
    def config(self):
        return {
            "triggers": {
                "enabled": True,
                "thresholds": {
                    "memory_total_chunks": {
                        "value": 5000,
                        "direction": "above",
                        "message": "Chunks exceeded {value}.",
                        "cooldown_days": 30,
                    },
                    "inference_avg_latency_ms": {
                        "value": 3000,
                        "direction": "above",
                        "message": "Latency is {value}ms.",
                        "cooldown_days": 7,
                    },
                },
            },
        }

    @pytest.mark.asyncio
    async def test_fires_when_exceeded(self, config):
        db = AsyncMock()
        db.get_last_trigger_fire = AsyncMock(return_value=None)
        monitor = TriggerMonitor(learning_db=db, config=config)
        alerts = await monitor.check_thresholds(
            user_id="u1",
            metrics={"memory_total_chunks": 5200.0, "inference_avg_latency_ms": 1500.0},
        )
        assert len(alerts) == 1
        assert alerts[0].trigger_name == "memory_total_chunks"

    @pytest.mark.asyncio
    async def test_respects_cooldown(self, config):
        recent = TriggerAlert(
            id="old", user_id="u1", trigger_name="memory_total_chunks",
            current_value=5100.0, threshold_value=5000.0,
            direction="above", message="Old alert.",
            timestamp=datetime.now(timezone.utc) - timedelta(days=5),
        )
        db = AsyncMock()
        db.get_last_trigger_fire = AsyncMock(return_value=recent)
        monitor = TriggerMonitor(learning_db=db, config=config)
        alerts = await monitor.check_thresholds(
            user_id="u1", metrics={"memory_total_chunks": 5300.0},
        )
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_disabled(self):
        db = AsyncMock()
        monitor = TriggerMonitor(
            learning_db=db,
            config={"triggers": {"enabled": False, "thresholds": {}}},
        )
        alerts = await monitor.check_thresholds(
            user_id="u1", metrics={"memory_total_chunks": 9999.0},
        )
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_below_direction(self):
        db = AsyncMock()
        db.get_last_trigger_fire = AsyncMock(return_value=None)
        monitor = TriggerMonitor(
            learning_db=db,
            config={
                "triggers": {
                    "enabled": True,
                    "thresholds": {
                        "positive_ratio": {
                            "value": 0.5,
                            "direction": "below",
                            "message": "Ratio dropped to {value}.",
                            "cooldown_days": 7,
                        },
                    },
                },
            },
        )
        alerts = await monitor.check_thresholds(
            user_id="u1", metrics={"positive_ratio": 0.3},
        )
        assert len(alerts) == 1
        assert alerts[0].trigger_name == "positive_ratio"


# ─── Route Tests ───────────────────────────────────────────────────────────


class TestLearningRoutes:

    @pytest.fixture
    def app(self):
        from fastapi import FastAPI
        from hestia.api.routes.learning import router
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    async def client(self, app):
        from httpx import AsyncClient, ASGITransport
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            yield c

    @pytest.mark.asyncio
    async def test_get_report(self, client):
        report = MetaMonitorReport(
            id="r1", user_id="u1",
            timestamp=datetime.now(timezone.utc),
            status=ReportStatus.COMPLETE,
            total_outcomes=50, positive_ratio=0.72,
            routing_stats=[], confusion_sessions=[],
            avg_latency_ms=1200.0, latency_trend="stable",
            sample_size_sufficient=True,
        )
        with patch("hestia.api.routes.learning._get_learning_db") as mock:
            mock.return_value = AsyncMock(get_latest_report=AsyncMock(return_value=report))
            resp = await client.get("/v1/learning/report?user_id=u1")
        assert resp.status_code == 200
        assert resp.json()["data"]["positive_ratio"] == 0.72

    @pytest.mark.asyncio
    async def test_get_report_empty(self, client):
        with patch("hestia.api.routes.learning._get_learning_db") as mock:
            mock.return_value = AsyncMock(get_latest_report=AsyncMock(return_value=None))
            resp = await client.get("/v1/learning/report?user_id=u1")
        assert resp.status_code == 200
        assert resp.json()["data"] is None

    @pytest.mark.asyncio
    async def test_get_memory_health(self, client):
        snap = MemoryHealthSnapshot(
            id="s1", user_id="u1",
            timestamp=datetime.now(timezone.utc),
            chunk_count=1200, chunk_count_by_source={},
            redundancy_estimate_pct=12.5,
            entity_count=150, fact_count=300,
            stale_entity_count=10, contradiction_count=3,
            community_count=8,
        )
        with patch("hestia.api.routes.learning._get_learning_db") as mock:
            mock.return_value = AsyncMock(
                get_latest_health_snapshot=AsyncMock(return_value=snap)
            )
            resp = await client.get("/v1/learning/memory-health?user_id=u1")
        assert resp.status_code == 200
        assert resp.json()["data"]["chunk_count"] == 1200

    @pytest.mark.asyncio
    async def test_get_alerts(self, client):
        alert = TriggerAlert(
            id="a1", user_id="u1", trigger_name="test",
            current_value=100.0, threshold_value=50.0,
            direction="above", message="Test alert.",
            timestamp=datetime.now(timezone.utc),
        )
        with patch("hestia.api.routes.learning._get_learning_db") as mock:
            mock.return_value = AsyncMock(
                get_unacknowledged_alerts=AsyncMock(return_value=[alert])
            )
            resp = await client.get("/v1/learning/alerts?user_id=u1")
        assert resp.status_code == 200
        assert len(resp.json()["data"]) == 1
