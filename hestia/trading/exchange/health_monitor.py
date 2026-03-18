"""
Exchange connection health monitor.

Tracks heartbeat, latency, and uptime. Feeds data into the
Layer 6 latency circuit breaker.
"""

import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from hestia.logging import get_logger, LogComponent

logger = get_logger()


class HealthMonitor:
    """
    Monitors exchange connection health.

    Tracks:
    - Last heartbeat time
    - API response latency (moving average)
    - Connection uptime
    - Disconnect count
    """

    def __init__(self, heartbeat_interval_s: float = 30.0) -> None:
        self._heartbeat_interval = heartbeat_interval_s
        self._last_heartbeat: Optional[float] = None
        self._connect_time: Optional[float] = None
        self._disconnect_count = 0

        # Latency tracking (circular buffer)
        self._latencies: list = []
        self._max_latency_samples = 100

    def record_heartbeat(self) -> None:
        """Record a heartbeat (connection is alive)."""
        self._last_heartbeat = time.monotonic()

    def record_connect(self) -> None:
        """Record a successful connection."""
        self._connect_time = time.monotonic()
        self._last_heartbeat = time.monotonic()

    def record_disconnect(self) -> None:
        """Record a disconnection event."""
        self._disconnect_count += 1
        self._connect_time = None

    def record_latency(self, latency_ms: float) -> None:
        """Record an API response latency measurement."""
        self._latencies.append(latency_ms)
        if len(self._latencies) > self._max_latency_samples:
            self._latencies.pop(0)

    @property
    def is_healthy(self) -> bool:
        """Whether the connection is considered healthy."""
        if self._last_heartbeat is None:
            return False
        age = time.monotonic() - self._last_heartbeat
        return age < self._heartbeat_interval * 2

    @property
    def avg_latency_ms(self) -> float:
        """Average API latency over recent samples."""
        if not self._latencies:
            return 0.0
        return sum(self._latencies) / len(self._latencies)

    @property
    def p95_latency_ms(self) -> float:
        """95th percentile latency."""
        if not self._latencies:
            return 0.0
        sorted_lat = sorted(self._latencies)
        idx = int(len(sorted_lat) * 0.95)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]

    @property
    def uptime_seconds(self) -> float:
        """How long the current connection has been up."""
        if self._connect_time is None:
            return 0.0
        return time.monotonic() - self._connect_time

    @property
    def heartbeat_age_seconds(self) -> Optional[float]:
        """Seconds since last heartbeat."""
        if self._last_heartbeat is None:
            return None
        return time.monotonic() - self._last_heartbeat

    def get_status(self) -> Dict[str, Any]:
        return {
            "healthy": self.is_healthy,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "heartbeat_age_s": (
                round(self.heartbeat_age_seconds, 1)
                if self.heartbeat_age_seconds is not None else None
            ),
            "avg_latency_ms": round(self.avg_latency_ms, 1),
            "p95_latency_ms": round(self.p95_latency_ms, 1),
            "disconnect_count": self._disconnect_count,
            "latency_samples": len(self._latencies),
        }
