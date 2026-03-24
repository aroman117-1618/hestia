"""Workflow event bus — asyncio.Queue-based pub/sub for SSE streaming.

Each SSE client subscribes and gets its own bounded queue.
Mirrors the TradingEventBus pattern.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Set

from hestia.logging import get_logger, LogComponent

logger = get_logger()


@dataclass
class WorkflowEvent:
    """A single workflow execution event published to SSE subscribers."""

    event_type: str  # run_started, node_started, node_completed, node_failed, run_completed
    workflow_id: str = ""
    run_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    sequence: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        """Format as SSE frame (id + event + data)."""
        payload = {
            "type": self.event_type,
            "workflow_id": self.workflow_id,
            "run_id": self.run_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            **self.data,
        }
        return f"id: {self.sequence}\nevent: {self.event_type}\ndata: {json.dumps(payload)}\n\n"


class WorkflowEventBus:
    """Pub/sub event bus for workflow SSE streaming.

    Each subscriber gets an asyncio.Queue. Non-critical events
    respect max_queue_size (drops oldest on overflow).
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
            f"Workflow SSE subscriber added (total: {len(self._subscribers)})",
            component=LogComponent.WORKFLOW,
        )
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue."""
        self._subscribers.discard(queue)
        logger.debug(
            f"Workflow SSE subscriber removed (total: {len(self._subscribers)})",
            component=LogComponent.WORKFLOW,
        )

    def publish(self, event: WorkflowEvent) -> None:
        """Publish an event to all subscribers."""
        self._sequence += 1
        event.sequence = self._sequence

        for queue in list(self._subscribers):
            if queue.qsize() >= self._max_queue_size:
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def current_sequence(self) -> int:
        return self._sequence
