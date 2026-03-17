"""Data models for the learning module."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ReportStatus(Enum):
    """Status of a MetaMonitor report."""
    COMPLETE = "complete"
    INSUFFICIENT_DATA = "insufficient_data"
    ERROR = "error"


class CorrectionType(Enum):
    """Classification of user corrections."""
    TIMEZONE = "timezone"
    FACTUAL = "factual"
    PREFERENCE = "preference"
    TOOL_USAGE = "tool_usage"


@dataclass
class Correction:
    """A classified user correction linked to an outcome."""
    id: str
    user_id: str
    outcome_id: str
    correction_type: CorrectionType
    analysis: str
    confidence: float
    principle_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "outcome_id": self.outcome_id,
            "correction_type": self.correction_type.value,
            "analysis": self.analysis,
            "confidence": self.confidence,
            "principle_id": self.principle_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Correction:
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            outcome_id=data["outcome_id"],
            correction_type=CorrectionType(data["correction_type"]),
            analysis=data["analysis"],
            confidence=data["confidence"],
            principle_id=data.get("principle_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class DistillationStatus(Enum):
    """Status of a distillation run."""
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class DistillationRun:
    """Record of an outcome-to-principle distillation batch."""
    id: str
    user_id: str
    run_timestamp: datetime
    source: str  # "scheduled" | "manual"
    outcomes_processed: int = 0
    principles_generated: int = 0
    status: DistillationStatus = DistillationStatus.IN_PROGRESS
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "run_timestamp": self.run_timestamp.isoformat(),
            "source": self.source,
            "outcomes_processed": self.outcomes_processed,
            "principles_generated": self.principles_generated,
            "status": self.status.value,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DistillationRun:
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            run_timestamp=datetime.fromisoformat(data["run_timestamp"]),
            source=data["source"],
            outcomes_processed=data.get("outcomes_processed", 0),
            principles_generated=data.get("principles_generated", 0),
            status=DistillationStatus(data["status"]),
            error_message=data.get("error_message"),
        )


MIN_SAMPLE_SIZE = 20


@dataclass
class RoutingQualityStats:
    """Outcome quality stats for a specific agent route."""
    route: str
    total_count: int
    positive_count: int
    negative_count: int
    positive_ratio: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route,
            "total_count": self.total_count,
            "positive_count": self.positive_count,
            "negative_count": self.negative_count,
            "positive_ratio": self.positive_ratio,
        }


@dataclass
class MetaMonitorReport:
    """Hourly MetaMonitor analysis report."""
    id: str
    user_id: str
    timestamp: datetime
    status: ReportStatus
    total_outcomes: int
    positive_ratio: Optional[float]
    routing_stats: Optional[List[RoutingQualityStats]]
    confusion_sessions: List[str]
    avg_latency_ms: Optional[float]
    latency_trend: Optional[str]  # "improving", "stable", "degrading"
    sample_size_sufficient: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "total_outcomes": self.total_outcomes,
            "positive_ratio": self.positive_ratio,
            "routing_stats": [s.to_dict() for s in self.routing_stats] if self.routing_stats else None,
            "confusion_sessions": self.confusion_sessions,
            "avg_latency_ms": self.avg_latency_ms,
            "latency_trend": self.latency_trend,
            "sample_size_sufficient": self.sample_size_sufficient,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MetaMonitorReport:
        routing_stats = None
        if data.get("routing_stats"):
            routing_stats = [RoutingQualityStats(**s) for s in data["routing_stats"]]
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            status=ReportStatus(data["status"]),
            total_outcomes=data["total_outcomes"],
            positive_ratio=data.get("positive_ratio"),
            routing_stats=routing_stats,
            confusion_sessions=data.get("confusion_sessions", []),
            avg_latency_ms=data.get("avg_latency_ms"),
            latency_trend=data.get("latency_trend"),
            sample_size_sufficient=data.get("sample_size_sufficient", False),
        )


@dataclass
class MemoryHealthSnapshot:
    """Daily memory system health snapshot."""
    id: str
    user_id: str
    timestamp: datetime
    chunk_count: int
    chunk_count_by_source: Dict[str, int]
    redundancy_estimate_pct: float
    entity_count: int
    fact_count: int
    stale_entity_count: int
    contradiction_count: int
    community_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "timestamp": self.timestamp.isoformat(),
            "chunk_count": self.chunk_count,
            "chunk_count_by_source": self.chunk_count_by_source,
            "redundancy_estimate_pct": self.redundancy_estimate_pct,
            "entity_count": self.entity_count,
            "fact_count": self.fact_count,
            "stale_entity_count": self.stale_entity_count,
            "contradiction_count": self.contradiction_count,
            "community_count": self.community_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryHealthSnapshot:
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            chunk_count=data["chunk_count"],
            chunk_count_by_source=data.get("chunk_count_by_source", {}),
            redundancy_estimate_pct=data.get("redundancy_estimate_pct", 0.0),
            entity_count=data.get("entity_count", 0),
            fact_count=data.get("fact_count", 0),
            stale_entity_count=data.get("stale_entity_count", 0),
            contradiction_count=data.get("contradiction_count", 0),
            community_count=data.get("community_count", 0),
        )


@dataclass
class TriggerAlert:
    """Alert generated when a metric crosses a threshold."""
    id: str
    user_id: str
    trigger_name: str
    current_value: float
    threshold_value: float
    direction: str  # "above" or "below"
    message: str
    timestamp: datetime
    acknowledged: bool = False
    cooldown_until: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "trigger_name": self.trigger_name,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "direction": self.direction,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TriggerAlert:
        return cls(
            id=data["id"],
            user_id=data["user_id"],
            trigger_name=data["trigger_name"],
            current_value=data["current_value"],
            threshold_value=data["threshold_value"],
            direction=data["direction"],
            message=data["message"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            acknowledged=data.get("acknowledged", False),
            cooldown_until=datetime.fromisoformat(data["cooldown_until"]) if data.get("cooldown_until") else None,
        )
