"""Trading event bus — asyncio.Queue-based pub/sub for SSE streaming.

Each SSE client subscribes and gets its own bounded queue.
Critical events (kill_switch, risk_alert) bypass the bounded queue
to ensure delivery even under backpressure.

Single-caller publish pattern — no concurrent access to publish().
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Set

from hestia.logging import get_logger, LogComponent

logger = get_logger()

# Critical event types that bypass bounded queue
CRITICAL_EVENT_TYPES = {"kill_switch", "risk_alert"}


@dataclass
class TradingEvent:
    """A single event published to SSE subscribers."""

    event_type: str
    data: Dict[str, Any] = field(default_factory=dict)
    priority: bool = False
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        """Format as SSE frame (id + event + data)."""
        payload = {
            "type": self.event_type,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            **self.data,
        }
        return f"id: {self.sequence}\nevent: {self.event_type}\ndata: {json.dumps(payload)}\n\n"


class TradingEventBus:
    """Pub/sub event bus for trading SSE streaming.

    - Each subscriber gets an asyncio.Queue
    - Non-critical events respect max_queue_size (drops oldest on overflow)
    - Critical events (kill_switch, risk_alert) always delivered
    """

    def __init__(self, max_queue_size: int = 100) -> None:
        self._subscribers: Set[asyncio.Queue] = set()
        self._max_queue_size = max_queue_size
        self._sequence = 0

    def subscribe(self) -> asyncio.Queue:
        """Create a new subscriber queue."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=0)
        self._subscribers.add(queue)
        logger.debug(
            f"SSE subscriber added (total: {len(self._subscribers)})",
            component=LogComponent.TRADING,
        )
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(queue)
        logger.debug(
            f"SSE subscriber removed (total: {len(self._subscribers)})",
            component=LogComponent.TRADING,
        )

    def publish(self, event: TradingEvent) -> None:
        """Publish an event to all subscribers.

        Single-caller pattern — called from TradeExecutor/RiskManager
        within the same async context. No concurrent access.
        """
        self._sequence += 1
        event.sequence = self._sequence

        is_critical = event.event_type in CRITICAL_EVENT_TYPES or event.priority

        for queue in list(self._subscribers):
            if is_critical:
                # Critical events always delivered — no size limit
                queue.put_nowait(event)
            else:
                # Bounded: drop oldest if full
                if queue.qsize() >= self._max_queue_size:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait(event)

    @property
    def subscriber_count(self) -> int:
        """Number of active SSE subscribers."""
        return len(self._subscribers)

    @property
    def current_sequence(self) -> int:
        """Current event sequence number."""
        return self._sequence
