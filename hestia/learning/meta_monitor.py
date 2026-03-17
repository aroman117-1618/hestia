"""MetaMonitor — hourly behavioral analysis via SQL aggregation."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.learning.models import (
    MetaMonitorReport,
    RoutingQualityStats,
    ReportStatus,
    MIN_SAMPLE_SIZE,
)


logger = get_logger()

POSITIVE_SIGNALS = {"accepted", "long_gap", "session_end"}
NEGATIVE_SIGNALS = {"quick_followup"}
CONFUSION_MIN_MESSAGES = 5
CONFUSION_NEGATIVE_RATIO = 0.5


class MetaMonitorManager:
    """Hourly analysis of outcomes + routing data. Pure SQL aggregation, no inference."""

    def __init__(
        self,
        outcome_db: Any,
        routing_audit_db: Any,
        learning_db: Any,
    ) -> None:
        self._outcome_db = outcome_db
        self._routing_audit_db = routing_audit_db
        self._learning_db = learning_db

    async def analyze(self, user_id: str) -> MetaMonitorReport:
        """Run full analysis cycle. Called hourly by scheduler."""
        logger.info(
            "MetaMonitor analysis starting",
            component=LogComponent.LEARNING,
            data={"user_id": user_id},
        )

        # Self-cleanup: remove reports older than 7 days
        await self._learning_db.cleanup_old_reports(max_age_days=7)

        # Fetch 7-day rolling window of outcomes
        outcomes = await self._outcome_db.get_outcomes(user_id=user_id, days=7)

        total = len(outcomes)
        sufficient = total >= MIN_SAMPLE_SIZE

        if not sufficient:
            report = MetaMonitorReport(
                id=str(uuid.uuid4()),
                user_id=user_id,
                timestamp=datetime.now(timezone.utc),
                status=ReportStatus.INSUFFICIENT_DATA,
                total_outcomes=total,
                positive_ratio=None,
                routing_stats=None,
                confusion_sessions=[],
                avg_latency_ms=None,
                latency_trend=None,
                sample_size_sufficient=False,
            )
            await self._learning_db.store_report(report)
            return report

        # Compute metrics
        positive_ratio = self._compute_positive_ratio(outcomes)
        routing_stats = self._compute_routing_quality(outcomes)
        confusion_sessions = self._detect_confusion_loops(outcomes)
        avg_latency, latency_trend = self._compute_latency_trend(outcomes)

        report = MetaMonitorReport(
            id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            status=ReportStatus.COMPLETE,
            total_outcomes=total,
            positive_ratio=positive_ratio,
            routing_stats=routing_stats,
            confusion_sessions=confusion_sessions,
            avg_latency_ms=avg_latency,
            latency_trend=latency_trend,
            sample_size_sufficient=True,
        )

        await self._learning_db.store_report(report)

        logger.info(
            "MetaMonitor analysis complete",
            component=LogComponent.LEARNING,
            data={
                "user_id": user_id,
                "total_outcomes": total,
                "positive_ratio": positive_ratio,
                "confusion_sessions": len(confusion_sessions),
            },
        )

        return report

    def _compute_positive_ratio(self, outcomes: List[Dict]) -> float:
        """Compute ratio of positive implicit signals."""
        with_signal = [o for o in outcomes if o.get("implicit_signal")]
        if not with_signal:
            return 0.0
        positive = sum(1 for o in with_signal if o["implicit_signal"] in POSITIVE_SIGNALS)
        return round(positive / len(with_signal), 3)

    def _compute_routing_quality(self, outcomes: List[Dict]) -> List[RoutingQualityStats]:
        """Compare outcome quality across agent routes."""
        by_route: Dict[str, List[Dict]] = defaultdict(list)
        for o in outcomes:
            route = o.get("agent_route") or "HESTIA_SOLO"
            by_route[route].append(o)

        stats = []
        for route, route_outcomes in by_route.items():
            with_signal = [o for o in route_outcomes if o.get("implicit_signal")]
            total = len(with_signal)
            if total == 0:
                continue
            positive = sum(1 for o in with_signal if o["implicit_signal"] in POSITIVE_SIGNALS)
            negative = total - positive
            stats.append(RoutingQualityStats(
                route=route,
                total_count=total,
                positive_count=positive,
                negative_count=negative,
                positive_ratio=round(positive / total, 3),
            ))

        return sorted(stats, key=lambda s: s.total_count, reverse=True)

    def _detect_confusion_loops(self, outcomes: List[Dict]) -> List[str]:
        """Detect sessions with high negative signal ratio.

        Confusion = >CONFUSION_MIN_MESSAGES messages AND
                    >CONFUSION_NEGATIVE_RATIO quick_followup signals.
        """
        by_session: Dict[str, List[Dict]] = defaultdict(list)
        for o in outcomes:
            sid = o.get("session_id")
            if sid:
                by_session[sid].append(o)

        confused = []
        for sid, session_outcomes in by_session.items():
            if len(session_outcomes) < CONFUSION_MIN_MESSAGES:
                continue
            with_signal = [o for o in session_outcomes if o.get("implicit_signal")]
            if not with_signal:
                continue
            negative = sum(1 for o in with_signal if o["implicit_signal"] in NEGATIVE_SIGNALS)
            if negative / len(with_signal) > CONFUSION_NEGATIVE_RATIO:
                confused.append(sid)

        return confused

    def _compute_latency_trend(
        self, outcomes: List[Dict]
    ) -> tuple:
        """Compute average latency and detect trend."""
        durations = [o["duration_ms"] for o in outcomes if o.get("duration_ms")]
        if not durations:
            return None, None

        avg = sum(durations) / len(durations)

        # Simple trend: compare first half vs second half
        mid = len(durations) // 2
        if mid < 5:
            return round(avg, 1), "stable"

        first_half_avg = sum(durations[:mid]) / mid
        second_half_avg = sum(durations[mid:]) / (len(durations) - mid)

        # >20% increase = degrading, >20% decrease = improving
        if second_half_avg > first_half_avg * 1.2:
            trend = "degrading"
        elif second_half_avg < first_half_avg * 0.8:
            trend = "improving"
        else:
            trend = "stable"

        return round(avg, 1), trend
