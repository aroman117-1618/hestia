# Sprint 15: MetaMonitor + Memory Health + Trigger Metrics — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Hestia's first self-awareness infrastructure — hourly behavioral analysis, daily memory health diagnostics, and configurable threshold monitoring with briefing injection.

**Architecture:** Three loosely-coupled workstreams in a new `hestia/learning/` module, sharing a single `learning.db` SQLite database. MetaMonitor runs hourly (pure SQL aggregation, no inference). Memory Health runs daily (ChromaDB + research DB read-only diagnostics). Trigger Metrics runs daily (YAML thresholds → briefing alerts). A prerequisite Chunk 0 decomposes handler.py to reduce risk.

**Tech Stack:** Python 3.9+, FastAPI, SQLite (aiosqlite), ChromaDB client, APScheduler, YAML config, pytest + asyncio.

**Discovery:** `docs/discoveries/metamonitor-memory-health-triggers-2026-03-16.md`
**Audit:** `docs/plans/sprint-15-metamonitor-audit-2026-03-16.md`

**Audit Conditions Applied:**
- API namespace: `/v1/learning/` (route module: `hestia/api/routes/learning.py`)
- All `learning.db` tables include `user_id` column
- `LEARNING` added to `LogComponent` enum
- Correction classifier stores type labels only, not raw content
- `auto-test.sh` mapping for `hestia/learning/`
- Report self-cleanup in MetaMonitor hourly run
- Minimum sample size gates (n ≥ 20) on all analyses

---

## File Structure

### New Files
```
hestia/learning/
├── __init__.py                    # Module init, exports
├── models.py                      # MetaMonitorReport, MemoryHealthSnapshot, TriggerAlert, CorrectionType
├── database.py                    # LearningDatabase (BaseDatabase) — monitor_reports, health_snapshots, trigger_log
├── meta_monitor.py                # MetaMonitorManager — hourly analysis
├── memory_health.py               # MemoryHealthMonitor — daily diagnostics
├── trigger_monitor.py             # TriggerMonitor — threshold checking

hestia/api/routes/learning.py     # 5 API endpoints under /v1/learning/
config/triggers.yaml               # Threshold configuration

tests/test_learning_models.py      # Model unit tests
tests/test_learning_database.py    # Database CRUD tests
tests/test_learning_meta_monitor.py # MetaMonitor analysis tests
tests/test_learning_memory_health.py # Memory health tests
tests/test_learning_triggers.py    # Trigger monitor tests
tests/test_learning_routes.py      # API route tests
```

### Modified Files
```
hestia/orchestration/handler.py        # Chunk 0: extract agentic handler; Chunk 1: add retrieved_chunk_ids to Response
hestia/orchestration/agentic_handler.py # NEW — extracted from handler.py
hestia/orchestration/models.py         # Add retrieved_chunk_ids to Response
hestia/memory/manager.py               # Add build_context_with_ids() method
hestia/logging/structured_logger.py    # Add LEARNING to LogComponent enum
hestia/api/routes/chat.py              # Thread chunk_ids into outcome metadata
hestia/api/server.py                   # Register learning routes + manager init
hestia/proactive/briefing.py           # Add _add_system_alerts_section()
scripts/auto-test.sh                   # Add learning module mapping
```

---

## Chunk 0: handler.py Decomposition (Prerequisite)

### Task 0.1: Extract agentic handler

**Files:**
- Create: `hestia/orchestration/agentic_handler.py`
- Modify: `hestia/orchestration/handler.py:1622-1766`

- [ ] **Step 1: Create agentic_handler.py with the handle_agentic method**

Extract `handle_agentic()` (handler.py lines 1622-1766) and all its private helpers into a new class `AgenticHandler`. It needs access to `_memory_manager`, `_inference_client`, `_prompt_builder`, `state_machine`, and `logger`.

```python
"""Agentic tool-loop handler — extracted from handler.py for maintainability."""

from __future__ import annotations

import json
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.orchestration.models import Request, Response, ResponseType, Mode


logger = get_logger()


class AgenticHandler:
    """Handles iterative tool-calling loop for agentic chat."""

    MAX_ITERATIONS = 25

    def __init__(
        self,
        memory_manager: Any,
        inference_client: Any,
        prompt_builder: Any,
        state_machine: Any,
    ) -> None:
        self._memory_manager = memory_manager
        self._inference_client = inference_client
        self._prompt_builder = prompt_builder
        self.state_machine = state_machine
        self.logger = logger

    async def handle_agentic(
        self, request: Request
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # ... paste full body from handler.py lines 1622-1766
        # Replace all self.inference_client with self._inference_client
        # All other self.* references remain unchanged
        ...
```

- [ ] **Step 2: Update handler.py to delegate to AgenticHandler**

In `RequestHandler.__init__()`, add:
```python
from hestia.orchestration.agentic_handler import AgenticHandler
self._agentic_handler = AgenticHandler(
    memory_manager=self._memory_manager,
    inference_client=self._inference_client,
    prompt_builder=self._prompt_builder,
    state_machine=self.state_machine,
)
```

Replace `handle_agentic()` method body with delegation:
```python
async def handle_agentic(self, request: Request) -> AsyncGenerator[Dict[str, Any], None]:
    async for event in self._agentic_handler.handle_agentic(request):
        yield event
```

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ --timeout=30 -q`
Expected: All existing tests pass (2009+). The extraction is purely mechanical — no behavior change.

- [ ] **Step 4: Commit**

```bash
git add hestia/orchestration/agentic_handler.py hestia/orchestration/handler.py
git commit -m "refactor: extract AgenticHandler from handler.py (Sprint 15 prereq)"
```

### Task 0.2: Add LEARNING LogComponent

**Files:**
- Modify: `hestia/logging/structured_logger.py:42-62`

- [ ] **Step 1: Add LEARNING to LogComponent enum**

After `APPLE_CACHE = "apple_cache"` (line ~61), add:
```python
LEARNING = "learning"
```

- [ ] **Step 2: Update auto-test.sh**

In `scripts/auto-test.sh`, in the `get_test_file()` case statement (around line 149), add:
```bash
*hestia/learning/*)
    echo "tests/test_learning_meta_monitor.py tests/test_learning_database.py" ;;
*hestia/api/routes/learning*)
    echo "tests/test_learning_routes.py" ;;
```

- [ ] **Step 3: Commit**

```bash
git add hestia/logging/structured_logger.py scripts/auto-test.sh
git commit -m "chore: add LEARNING LogComponent + auto-test mapping (Sprint 15 prereq)"
```

---

## Chunk 1: Retrieval Feedback Loop (Chunk Attribution)

The single highest-ROI change in Sprint 15. When `build_context()` assembles memory chunks, capture the chunk IDs and thread them into outcome metadata.

### Task 1.1: Add build_context_with_ids() to MemoryManager

**Files:**
- Modify: `hestia/memory/manager.py:596-640`
- Test: `tests/test_memory.py` (add test)

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_build_context_with_ids_returns_chunk_ids(memory_manager):
    """build_context_with_ids returns both context string and chunk IDs."""
    # Store a test chunk first
    chunk = ConversationChunk(
        id="test-chunk-1",
        session_id="session-1",
        timestamp=datetime.now(timezone.utc),
        content="Test memory about Python programming",
        chunk_type="message",
        scope=MemoryScope.LONG_TERM,
        metadata=ChunkMetadata(tags=["python"]),
    )
    await memory_manager.store(chunk)

    context, chunk_ids = await memory_manager.build_context_with_ids(
        query="Python programming",
        max_tokens=4000,
    )
    assert isinstance(context, str)
    assert isinstance(chunk_ids, list)
    assert "test-chunk-1" in chunk_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory.py -k test_build_context_with_ids -v`
Expected: FAIL — method doesn't exist yet.

- [ ] **Step 3: Implement build_context_with_ids()**

Add to `MemoryManager` after `build_context()` (after line 640):

```python
async def build_context_with_ids(
    self,
    query: str,
    max_tokens: int = 4000,
    include_recent: bool = True,
    cloud_safe: bool = False,
) -> tuple[str, list[str]]:
    """Build context string AND return chunk IDs used.

    Returns:
        Tuple of (context_string, list_of_chunk_ids).
        chunk_ids includes ALL retrieved chunks, even those filtered out.
    """
    context_parts: list[str] = []
    all_chunk_ids: list[str] = []
    estimated_tokens = 0

    # Include relevant memories from search
    results = await self.search(query, limit=5, semantic_threshold=0.6)
    # Log ALL retrieved chunk IDs (even filtered ones)
    all_chunk_ids = [r.chunk.id for r in results]

    if results:
        context_parts.append("## Relevant Memory\n")
        for result in results:
            if cloud_safe and result.chunk.metadata.is_sensitive:
                continue
            if estimated_tokens > max_tokens * 0.6:
                break
            chunk_text = f"- [{result.chunk.timestamp.strftime('%Y-%m-%d')}] {result.chunk.content[:500]}\n"
            context_parts.append(chunk_text)
            estimated_tokens += len(chunk_text.split()) * 1.3

    # Include recent conversation if space allows
    if include_recent and estimated_tokens < max_tokens * 0.8:
        recent = await self.get_recent(limit=10)
        if recent:
            context_parts.append("\n## Recent Conversation\n")
            for chunk in reversed(recent):
                if cloud_safe and chunk.metadata.is_sensitive:
                    continue
                if estimated_tokens > max_tokens:
                    break
                chunk_text = f"{chunk.content[:300]}\n"
                context_parts.append(chunk_text)
                estimated_tokens += len(chunk_text.split()) * 1.3

    return "".join(context_parts), all_chunk_ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_memory.py -k test_build_context_with_ids -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/memory/manager.py tests/test_memory.py
git commit -m "feat: build_context_with_ids() for retrieval feedback loop"
```

### Task 1.2: Add retrieved_chunk_ids to Response model

**Files:**
- Modify: `hestia/orchestration/models.py:106-133`

- [ ] **Step 1: Add field to Response dataclass**

After `bylines` field (line 132), add:
```python
# Retrieval feedback loop — chunk IDs used in context
retrieved_chunk_ids: List[str] = field(default_factory=list)
```

- [ ] **Step 2: Commit**

```bash
git add hestia/orchestration/models.py
git commit -m "feat: add retrieved_chunk_ids to Response model"
```

### Task 1.3: Wire chunk IDs through handler pipeline

**Files:**
- Modify: `hestia/orchestration/handler.py:511-538`

- [ ] **Step 1: Switch handle() to use build_context_with_ids()**

In `handle()`, replace the `build_context()` call in the gather (lines 511-517):

```python
# Before:
results = await asyncio.gather(
    memory.build_context(
        query=request.content,
        max_tokens=4000,
        include_recent=True,
        cloud_safe=will_use_cloud,
    ),
    ...
)
# After:
results = await asyncio.gather(
    memory.build_context_with_ids(
        query=request.content,
        max_tokens=4000,
        include_recent=True,
        cloud_safe=will_use_cloud,
    ),
    ...
)
```

Then update the unpack block (lines 529-538):
```python
# Before:
if isinstance(results[0], Exception):
    ...
    memory_context = ""
else:
    memory_context = results[0]

# After:
retrieved_chunk_ids: list[str] = []
if isinstance(results[0], Exception):
    ...
    memory_context = ""
else:
    memory_context, retrieved_chunk_ids = results[0]
```

And set on the response object (wherever Response is constructed, after inference):
```python
response.retrieved_chunk_ids = retrieved_chunk_ids
```

- [ ] **Step 2: Same change in handle_streaming()**

Apply the identical pattern to `handle_streaming()` gather call (~lines 787-800). The `retrieved_chunk_ids` should be included in the SSE `done` event data:
```python
# In the done event dict:
"retrieved_chunk_ids": retrieved_chunk_ids,
```

- [ ] **Step 3: Thread chunk IDs into outcome tracking in chat.py**

In `hestia/api/routes/chat.py`, update the `track_response()` metadata dict.

For POST `/v1/chat` (line 175):
```python
metadata={
    "mode": api_response.mode.value,
    "tool_calls": len(response.tool_calls) if response.tool_calls else 0,
    "tokens_out": response.tokens_out or 0,
    "retrieved_chunk_ids": response.retrieved_chunk_ids,
},
```

For SSE `/v1/chat/stream` (line 321):
```python
metadata={
    "mode": event.get("mode", "tia"),
    "streaming": True,
    "tokens_out": event.get("metrics", {}).get("tokens_out", 0),
    "retrieved_chunk_ids": event.get("retrieved_chunk_ids", []),
},
```

- [ ] **Step 4: Run full test suite**

Run: `python -m pytest tests/ --timeout=30 -q`
Expected: All tests pass. The change is additive — existing metadata fields unchanged.

- [ ] **Step 5: Commit**

```bash
git add hestia/orchestration/handler.py hestia/api/routes/chat.py
git commit -m "feat: thread retrieved_chunk_ids through pipeline into outcome metadata"
```

---

## Chunk 2: Learning Module Foundation + Memory Health Monitor

### Task 2.1: Learning models

**Files:**
- Create: `hestia/learning/__init__.py`
- Create: `hestia/learning/models.py`
- Test: `tests/test_learning_models.py`

- [ ] **Step 1: Write model tests**

```python
"""Tests for hestia.learning.models."""

import pytest
from datetime import datetime, timezone
from hestia.learning.models import (
    MetaMonitorReport,
    RoutingQualityStats,
    MemoryHealthSnapshot,
    TriggerAlert,
    ReportStatus,
    CorrectionType,
)


def test_meta_monitor_report_creation():
    report = MetaMonitorReport(
        id="report-1",
        user_id="user-1",
        timestamp=datetime.now(timezone.utc),
        status=ReportStatus.COMPLETE,
        total_outcomes=50,
        positive_ratio=0.72,
        routing_stats=None,
        confusion_sessions=[],
        avg_latency_ms=1200.0,
        latency_trend="stable",
        sample_size_sufficient=True,
    )
    assert report.status == ReportStatus.COMPLETE
    d = report.to_dict()
    assert d["total_outcomes"] == 50
    assert d["positive_ratio"] == 0.72


def test_meta_monitor_report_insufficient_data():
    report = MetaMonitorReport(
        id="report-2",
        user_id="user-1",
        timestamp=datetime.now(timezone.utc),
        status=ReportStatus.INSUFFICIENT_DATA,
        total_outcomes=5,
        positive_ratio=None,
        routing_stats=None,
        confusion_sessions=[],
        avg_latency_ms=None,
        latency_trend=None,
        sample_size_sufficient=False,
    )
    assert report.status == ReportStatus.INSUFFICIENT_DATA
    assert not report.sample_size_sufficient


def test_routing_quality_stats():
    stats = RoutingQualityStats(
        route="HESTIA_SOLO",
        total_count=30,
        positive_count=22,
        negative_count=8,
        positive_ratio=0.733,
    )
    assert stats.positive_ratio == pytest.approx(0.733)


def test_memory_health_snapshot():
    snap = MemoryHealthSnapshot(
        id="snap-1",
        user_id="user-1",
        timestamp=datetime.now(timezone.utc),
        chunk_count=1200,
        chunk_count_by_source={"conversation": 800, "claude_import": 400},
        redundancy_estimate_pct=12.5,
        entity_count=150,
        fact_count=300,
        stale_entity_count=10,
        contradiction_count=3,
        community_count=8,
    )
    d = snap.to_dict()
    assert d["chunk_count"] == 1200
    assert d["redundancy_estimate_pct"] == 12.5


def test_trigger_alert():
    alert = TriggerAlert(
        id="alert-1",
        user_id="user-1",
        trigger_name="memory_total_chunks",
        current_value=5200.0,
        threshold_value=5000.0,
        direction="above",
        message="Memory chunk count exceeded 5,000.",
        timestamp=datetime.now(timezone.utc),
        acknowledged=False,
    )
    d = alert.to_dict()
    assert d["trigger_name"] == "memory_total_chunks"
    assert not d["acknowledged"]


def test_correction_type_enum():
    assert CorrectionType.TIMEZONE.value == "timezone"
    assert CorrectionType.FACTUAL.value == "factual"
    assert CorrectionType.PREFERENCE.value == "preference"
    assert CorrectionType.TOOL_USAGE.value == "tool_usage"
```

- [ ] **Step 2: Run to verify tests fail**

Run: `python -m pytest tests/test_learning_models.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement models**

Create `hestia/learning/__init__.py`:
```python
"""Hestia learning module — self-awareness infrastructure."""
```

Create `hestia/learning/models.py`:
```python
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
    confusion_sessions: List[str]  # session IDs flagged
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
            routing_stats = [
                RoutingQualityStats(**s) for s in data["routing_stats"]
            ]
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_learning_models.py -v`
Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add hestia/learning/ tests/test_learning_models.py
git commit -m "feat: learning module models — MetaMonitorReport, MemoryHealthSnapshot, TriggerAlert"
```

### Task 2.2: Learning database

**Files:**
- Create: `hestia/learning/database.py`
- Test: `tests/test_learning_database.py`

- [ ] **Step 1: Write database tests**

```python
"""Tests for hestia.learning.database."""

import pytest
import json
from datetime import datetime, timezone, timedelta
from hestia.learning.database import LearningDatabase
from hestia.learning.models import (
    MetaMonitorReport, MemoryHealthSnapshot, TriggerAlert, ReportStatus,
)


@pytest.fixture
async def learning_db(tmp_path):
    db = LearningDatabase(str(tmp_path / "learning.db"))
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_store_and_get_report(learning_db):
    report = MetaMonitorReport(
        id="r1", user_id="u1",
        timestamp=datetime.now(timezone.utc),
        status=ReportStatus.COMPLETE,
        total_outcomes=50, positive_ratio=0.72,
        routing_stats=None, confusion_sessions=[],
        avg_latency_ms=1200.0, latency_trend="stable",
        sample_size_sufficient=True,
    )
    await learning_db.store_report(report)
    latest = await learning_db.get_latest_report("u1")
    assert latest is not None
    assert latest.id == "r1"
    assert latest.positive_ratio == 0.72


@pytest.mark.asyncio
async def test_store_and_get_health_snapshot(learning_db):
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
    await learning_db.store_health_snapshot(snap)
    latest = await learning_db.get_latest_health_snapshot("u1")
    assert latest is not None
    assert latest.chunk_count == 1200


@pytest.mark.asyncio
async def test_health_snapshot_history(learning_db):
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
        await learning_db.store_health_snapshot(snap)
    history = await learning_db.get_health_snapshot_history("u1", days=3)
    assert len(history) == 3


@pytest.mark.asyncio
async def test_store_and_get_trigger_alert(learning_db):
    alert = TriggerAlert(
        id="a1", user_id="u1", trigger_name="memory_total_chunks",
        current_value=5200.0, threshold_value=5000.0,
        direction="above", message="Chunks exceeded 5000.",
        timestamp=datetime.now(timezone.utc),
    )
    await learning_db.store_trigger_alert(alert)
    unacked = await learning_db.get_unacknowledged_alerts("u1")
    assert len(unacked) == 1
    assert unacked[0].trigger_name == "memory_total_chunks"


@pytest.mark.asyncio
async def test_acknowledge_alert(learning_db):
    alert = TriggerAlert(
        id="a2", user_id="u1", trigger_name="test",
        current_value=100.0, threshold_value=50.0,
        direction="above", message="Test alert.",
        timestamp=datetime.now(timezone.utc),
    )
    await learning_db.store_trigger_alert(alert)
    await learning_db.acknowledge_alert("a2", "u1")
    unacked = await learning_db.get_unacknowledged_alerts("u1")
    assert len(unacked) == 0


@pytest.mark.asyncio
async def test_cleanup_old_reports(learning_db):
    old_time = datetime.now(timezone.utc) - timedelta(days=10)
    report = MetaMonitorReport(
        id="old-r", user_id="u1", timestamp=old_time,
        status=ReportStatus.COMPLETE, total_outcomes=10,
        positive_ratio=0.5, routing_stats=None,
        confusion_sessions=[], avg_latency_ms=1000.0,
        latency_trend="stable", sample_size_sufficient=True,
    )
    await learning_db.store_report(report)
    deleted = await learning_db.cleanup_old_reports(max_age_days=7)
    assert deleted >= 1
    latest = await learning_db.get_latest_report("u1")
    assert latest is None


@pytest.mark.asyncio
async def test_get_last_trigger_fire(learning_db):
    alert = TriggerAlert(
        id="a3", user_id="u1", trigger_name="latency",
        current_value=3500.0, threshold_value=3000.0,
        direction="above", message="High latency.",
        timestamp=datetime.now(timezone.utc),
    )
    await learning_db.store_trigger_alert(alert)
    last = await learning_db.get_last_trigger_fire("u1", "latency")
    assert last is not None
    none_result = await learning_db.get_last_trigger_fire("u1", "nonexistent")
    assert none_result is None
```

- [ ] **Step 2: Run to verify tests fail**

Run: `python -m pytest tests/test_learning_database.py -v`
Expected: FAIL — database module doesn't exist.

- [ ] **Step 3: Implement LearningDatabase**

Create `hestia/learning/database.py`:
```python
"""SQLite database for the learning module."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent
from hestia.learning.models import (
    MetaMonitorReport,
    MemoryHealthSnapshot,
    TriggerAlert,
)


logger = get_logger()


class LearningDatabase(BaseDatabase):
    """Stores MetaMonitor reports, health snapshots, and trigger alerts."""

    async def _create_tables(self) -> None:
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS monitor_reports (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reports_user_ts
                ON monitor_reports(user_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS health_snapshots (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                data TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_snapshots_user_ts
                ON health_snapshots(user_id, timestamp DESC);

            CREATE TABLE IF NOT EXISTS trigger_log (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                trigger_name TEXT NOT NULL,
                current_value REAL NOT NULL,
                threshold_value REAL NOT NULL,
                direction TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0,
                cooldown_until TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_triggers_user_ack
                ON trigger_log(user_id, acknowledged);
            CREATE INDEX IF NOT EXISTS idx_triggers_name
                ON trigger_log(user_id, trigger_name, timestamp DESC);
        """)
        await self.db.commit()

    async def store_report(self, report: MetaMonitorReport) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO monitor_reports (id, user_id, timestamp, data) VALUES (?, ?, ?, ?)",
            (report.id, report.user_id, report.timestamp.isoformat(), json.dumps(report.to_dict())),
        )
        await self.db.commit()

    async def get_latest_report(self, user_id: str) -> Optional[MetaMonitorReport]:
        cursor = await self.db.execute(
            "SELECT data FROM monitor_reports WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return MetaMonitorReport.from_dict(json.loads(row[0]))

    async def store_health_snapshot(self, snapshot: MemoryHealthSnapshot) -> None:
        await self.db.execute(
            "INSERT OR REPLACE INTO health_snapshots (id, user_id, timestamp, data) VALUES (?, ?, ?, ?)",
            (snapshot.id, snapshot.user_id, snapshot.timestamp.isoformat(), json.dumps(snapshot.to_dict())),
        )
        await self.db.commit()

    async def get_latest_health_snapshot(self, user_id: str) -> Optional[MemoryHealthSnapshot]:
        cursor = await self.db.execute(
            "SELECT data FROM health_snapshots WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return MemoryHealthSnapshot.from_dict(json.loads(row[0]))

    async def get_health_snapshot_history(
        self, user_id: str, days: int = 30
    ) -> List[MemoryHealthSnapshot]:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        cursor = await self.db.execute(
            "SELECT data FROM health_snapshots WHERE user_id = ? AND timestamp >= ? ORDER BY timestamp DESC",
            (user_id, cutoff),
        )
        rows = await cursor.fetchall()
        return [MemoryHealthSnapshot.from_dict(json.loads(r[0])) for r in rows]

    async def store_trigger_alert(self, alert: TriggerAlert) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO trigger_log
               (id, user_id, trigger_name, current_value, threshold_value, direction, message, timestamp, acknowledged, cooldown_until)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alert.id, alert.user_id, alert.trigger_name, alert.current_value,
             alert.threshold_value, alert.direction, alert.message,
             alert.timestamp.isoformat(), 1 if alert.acknowledged else 0,
             alert.cooldown_until.isoformat() if alert.cooldown_until else None),
        )
        await self.db.commit()

    async def get_unacknowledged_alerts(self, user_id: str) -> List[TriggerAlert]:
        cursor = await self.db.execute(
            "SELECT * FROM trigger_log WHERE user_id = ? AND acknowledged = 0 ORDER BY timestamp DESC",
            (user_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_alert(r) for r in rows]

    async def acknowledge_alert(self, alert_id: str, user_id: str) -> None:
        await self.db.execute(
            "UPDATE trigger_log SET acknowledged = 1 WHERE id = ? AND user_id = ?",
            (alert_id, user_id),
        )
        await self.db.commit()

    async def get_last_trigger_fire(
        self, user_id: str, trigger_name: str
    ) -> Optional[TriggerAlert]:
        cursor = await self.db.execute(
            "SELECT * FROM trigger_log WHERE user_id = ? AND trigger_name = ? ORDER BY timestamp DESC LIMIT 1",
            (user_id, trigger_name),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_alert(row)

    async def cleanup_old_reports(self, max_age_days: int = 7) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
        cursor = await self.db.execute(
            "DELETE FROM monitor_reports WHERE timestamp < ?", (cutoff,)
        )
        await self.db.commit()
        return cursor.rowcount

    def _row_to_alert(self, row: tuple) -> TriggerAlert:
        return TriggerAlert(
            id=row[0], user_id=row[1], trigger_name=row[2],
            current_value=row[3], threshold_value=row[4],
            direction=row[5], message=row[6],
            timestamp=datetime.fromisoformat(row[7]),
            acknowledged=bool(row[8]),
            cooldown_until=datetime.fromisoformat(row[9]) if row[9] else None,
        )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_learning_database.py -v`
Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add hestia/learning/database.py tests/test_learning_database.py
git commit -m "feat: LearningDatabase — reports, snapshots, trigger alerts"
```

### Task 2.3: Memory Health Monitor

**Files:**
- Create: `hestia/learning/memory_health.py`
- Test: `tests/test_learning_memory_health.py`

- [ ] **Step 1: Write memory health tests**

```python
"""Tests for hestia.learning.memory_health."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from hestia.learning.memory_health import MemoryHealthMonitor
from hestia.learning.models import MemoryHealthSnapshot


@pytest.fixture
def mock_memory_manager():
    mgr = AsyncMock()
    mgr._db = AsyncMock()
    mgr._vector_store = MagicMock()
    return mgr


@pytest.fixture
def mock_research_db():
    db = AsyncMock()
    db.count_entities = AsyncMock(return_value=150)
    db.count_facts = AsyncMock(return_value=300)
    db.list_communities = AsyncMock(return_value=[
        MagicMock(id="c1", member_entity_ids=["e1", "e2", "e3"]),
        MagicMock(id="c2", member_entity_ids=["e4", "e5"]),
    ])
    return db


@pytest.fixture
def mock_learning_db():
    db = AsyncMock()
    db.store_health_snapshot = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_collect_snapshot_basic(mock_memory_manager, mock_research_db, mock_learning_db):
    """Test basic health snapshot collection."""
    # Mock memory DB chunk count
    mock_memory_manager._db.execute = AsyncMock()
    cursor_mock = AsyncMock()
    cursor_mock.fetchone = AsyncMock(return_value=(1200,))
    mock_memory_manager._db.execute.return_value = cursor_mock

    # Mock vector store
    mock_memory_manager._vector_store.count = MagicMock(return_value=1200)

    # Mock stale entities
    mock_research_db.count_entities.side_effect = [150, 10]  # total, then stale
    # Mock contradictions
    mock_research_db.count_facts.side_effect = [300, 3]  # total, then contradicted

    monitor = MemoryHealthMonitor(
        memory_manager=mock_memory_manager,
        research_db=mock_research_db,
        learning_db=mock_learning_db,
    )
    snapshot = await monitor.collect_snapshot(user_id="user-1")

    assert isinstance(snapshot, MemoryHealthSnapshot)
    assert snapshot.user_id == "user-1"
    assert snapshot.chunk_count == 1200
    assert snapshot.entity_count == 150
    mock_learning_db.store_health_snapshot.assert_called_once()


@pytest.mark.asyncio
async def test_collect_snapshot_empty_db(mock_memory_manager, mock_research_db, mock_learning_db):
    """Test health snapshot with empty databases."""
    mock_memory_manager._vector_store.count = MagicMock(return_value=0)
    mock_research_db.count_entities.return_value = 0
    mock_research_db.count_facts.return_value = 0
    mock_research_db.list_communities.return_value = []

    monitor = MemoryHealthMonitor(
        memory_manager=mock_memory_manager,
        research_db=mock_research_db,
        learning_db=mock_learning_db,
    )
    snapshot = await monitor.collect_snapshot(user_id="user-1")

    assert snapshot.chunk_count == 0
    assert snapshot.entity_count == 0
    assert snapshot.redundancy_estimate_pct == 0.0
```

- [ ] **Step 2: Run to verify tests fail**

Run: `python -m pytest tests/test_learning_memory_health.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement MemoryHealthMonitor**

Create `hestia/learning/memory_health.py`:
```python
"""Memory health monitoring — daily cross-system diagnostics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from hestia.logging import get_logger, LogComponent
from hestia.learning.models import MemoryHealthSnapshot


logger = get_logger()


class MemoryHealthMonitor:
    """Collects daily health snapshots across ChromaDB + knowledge graph."""

    def __init__(
        self,
        memory_manager: Any,
        research_db: Any,
        learning_db: Any,
    ) -> None:
        self._memory_manager = memory_manager
        self._research_db = research_db
        self._learning_db = learning_db

    async def collect_snapshot(self, user_id: str) -> MemoryHealthSnapshot:
        """Collect and store a memory health snapshot."""
        logger.info(
            "Collecting memory health snapshot",
            component=LogComponent.LEARNING,
            data={"user_id": user_id},
        )

        # ChromaDB chunk count
        try:
            chunk_count = self._memory_manager._vector_store.count()
        except Exception:
            chunk_count = 0

        # Chunk count by source (if available via memory DB)
        chunk_count_by_source: Dict[str, int] = {}
        try:
            chunk_count_by_source = await self._get_chunk_counts_by_source()
        except Exception:
            pass

        # Redundancy estimate (sampling-based)
        redundancy_pct = 0.0
        try:
            redundancy_pct = await self._estimate_redundancy()
        except Exception:
            pass

        # Knowledge graph stats
        entity_count = 0
        fact_count = 0
        stale_entity_count = 0
        contradiction_count = 0
        community_count = 0

        try:
            entity_count = await self._research_db.count_entities()
            fact_count = await self._research_db.count_facts()
            communities = await self._research_db.list_communities(limit=1000, offset=0)
            community_count = len(communities)
        except Exception:
            pass

        # Stale entities (no new facts in 30 days) — approximation
        try:
            stale_entity_count = await self._count_stale_entities()
        except Exception:
            pass

        # Contradictions
        try:
            from hestia.research.models import FactStatus
            contradiction_count = await self._research_db.count_facts(status=FactStatus.CONTRADICTED)
        except Exception:
            pass

        snapshot = MemoryHealthSnapshot(
            id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            chunk_count=chunk_count,
            chunk_count_by_source=chunk_count_by_source,
            redundancy_estimate_pct=redundancy_pct,
            entity_count=entity_count,
            fact_count=fact_count,
            stale_entity_count=stale_entity_count,
            contradiction_count=contradiction_count,
            community_count=community_count,
        )

        await self._learning_db.store_health_snapshot(snapshot)

        logger.info(
            "Memory health snapshot stored",
            component=LogComponent.LEARNING,
            data={
                "user_id": user_id,
                "chunk_count": chunk_count,
                "entity_count": entity_count,
                "redundancy_pct": redundancy_pct,
            },
        )

        return snapshot

    async def _get_chunk_counts_by_source(self) -> Dict[str, int]:
        """Count chunks grouped by source metadata."""
        # Query memory DB for source distribution
        try:
            db = self._memory_manager._db
            cursor = await db.execute(
                "SELECT json_extract(metadata, '$.source') as source, COUNT(*) "
                "FROM memory_chunks GROUP BY source"
            )
            rows = await cursor.fetchall()
            return {(row[0] or "unknown"): row[1] for row in rows}
        except Exception:
            return {}

    async def _estimate_redundancy(self) -> float:
        """Estimate chunk redundancy via pairwise similarity sampling.

        Samples up to 100 random chunks and computes pairwise cosine similarity.
        Reports % of pairs with similarity > 0.92.
        """
        # This is a placeholder — actual implementation needs
        # ChromaDB's get() with random sampling + pairwise comparison.
        # For now, return 0.0 (baseline).
        return 0.0

    async def _count_stale_entities(self) -> int:
        """Count entities with no facts updated in 30 days."""
        # Approximation: entities whose most recent fact is >30 days old
        # Requires a join across entities and facts tables
        try:
            cursor = await self._research_db.db.execute(
                """SELECT COUNT(DISTINCT e.id) FROM entities e
                   LEFT JOIN facts f ON (
                       json_extract(f.subject_entity_id, '$') = e.id
                       OR json_extract(f.object_entity_id, '$') = e.id
                   )
                   WHERE f.id IS NULL
                      OR f.created_at < datetime('now', '-30 days')"""
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
        except Exception:
            return 0
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_learning_memory_health.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add hestia/learning/memory_health.py tests/test_learning_memory_health.py
git commit -m "feat: MemoryHealthMonitor — daily cross-system diagnostics"
```

---

## Chunk 3: MetaMonitor Core

### Task 3.1: MetaMonitor manager

**Files:**
- Create: `hestia/learning/meta_monitor.py`
- Test: `tests/test_learning_meta_monitor.py`

- [ ] **Step 1: Write MetaMonitor tests**

Test file covers: routing quality analysis, acceptance trend, confusion detection, insufficient data handling, report self-cleanup.

```python
"""Tests for hestia.learning.meta_monitor."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from hestia.learning.meta_monitor import MetaMonitorManager
from hestia.learning.models import ReportStatus, MIN_SAMPLE_SIZE


@pytest.fixture
def mock_outcome_db():
    db = AsyncMock()
    return db


@pytest.fixture
def mock_routing_audit_db():
    db = AsyncMock()
    return db


@pytest.fixture
def mock_learning_db():
    db = AsyncMock()
    db.store_report = AsyncMock()
    db.cleanup_old_reports = AsyncMock(return_value=0)
    return db


def _make_outcome_rows(count, signal="accepted", route="HESTIA_SOLO", duration_ms=1000):
    """Helper to create mock outcome query results."""
    now = datetime.now(timezone.utc)
    return [
        {
            "id": f"o{i}",
            "user_id": "u1",
            "session_id": f"s{i % 5}",
            "implicit_signal": signal,
            "agent_route": route,
            "duration_ms": duration_ms,
            "timestamp": (now - timedelta(hours=i)).isoformat(),
        }
        for i in range(count)
    ]


@pytest.mark.asyncio
async def test_analyze_insufficient_data(mock_outcome_db, mock_routing_audit_db, mock_learning_db):
    """MetaMonitor reports insufficient_data when < MIN_SAMPLE_SIZE outcomes."""
    mock_outcome_db.get_outcomes = AsyncMock(return_value=_make_outcome_rows(5))

    monitor = MetaMonitorManager(
        outcome_db=mock_outcome_db,
        routing_audit_db=mock_routing_audit_db,
        learning_db=mock_learning_db,
    )
    report = await monitor.analyze(user_id="u1")
    assert report.status == ReportStatus.INSUFFICIENT_DATA
    assert not report.sample_size_sufficient
    mock_learning_db.store_report.assert_called_once()


@pytest.mark.asyncio
async def test_analyze_routing_quality(mock_outcome_db, mock_routing_audit_db, mock_learning_db):
    """MetaMonitor produces routing quality stats when data is sufficient."""
    outcomes = (
        _make_outcome_rows(15, signal="accepted", route="HESTIA_SOLO")
        + _make_outcome_rows(10, signal="accepted", route="ARTEMIS")
        + _make_outcome_rows(5, signal="quick_followup", route="HESTIA_SOLO")
    )
    mock_outcome_db.get_outcomes = AsyncMock(return_value=outcomes)

    monitor = MetaMonitorManager(
        outcome_db=mock_outcome_db,
        routing_audit_db=mock_routing_audit_db,
        learning_db=mock_learning_db,
    )
    report = await monitor.analyze(user_id="u1")
    assert report.status == ReportStatus.COMPLETE
    assert report.sample_size_sufficient
    assert report.routing_stats is not None
    assert len(report.routing_stats) >= 1

    # ARTEMIS should have 100% positive (10/10)
    artemis_stat = next((s for s in report.routing_stats if s.route == "ARTEMIS"), None)
    assert artemis_stat is not None
    assert artemis_stat.positive_ratio == 1.0


@pytest.mark.asyncio
async def test_confusion_detection(mock_outcome_db, mock_routing_audit_db, mock_learning_db):
    """Sessions with >5 messages AND >50% quick_followup are flagged."""
    # Session s0 with 8 messages, 6 quick_followup
    outcomes = []
    now = datetime.now(timezone.utc)
    for i in range(8):
        outcomes.append({
            "id": f"o{i}", "user_id": "u1", "session_id": "s0",
            "implicit_signal": "quick_followup" if i < 6 else "accepted",
            "agent_route": "HESTIA_SOLO", "duration_ms": 1000,
            "timestamp": (now - timedelta(minutes=i)).isoformat(),
        })
    # Session s1 with 10 normal messages (no confusion)
    for i in range(10):
        outcomes.append({
            "id": f"o{i+8}", "user_id": "u1", "session_id": "s1",
            "implicit_signal": "accepted",
            "agent_route": "HESTIA_SOLO", "duration_ms": 1000,
            "timestamp": (now - timedelta(minutes=i)).isoformat(),
        })
    # Add more to pass min sample size
    outcomes.extend(_make_outcome_rows(10, signal="accepted"))

    mock_outcome_db.get_outcomes = AsyncMock(return_value=outcomes)

    monitor = MetaMonitorManager(
        outcome_db=mock_outcome_db,
        routing_audit_db=mock_routing_audit_db,
        learning_db=mock_learning_db,
    )
    report = await monitor.analyze(user_id="u1")
    assert "s0" in report.confusion_sessions
    assert "s1" not in report.confusion_sessions


@pytest.mark.asyncio
async def test_latency_trend_stable(mock_outcome_db, mock_routing_audit_db, mock_learning_db):
    """Latency trend is 'stable' when no significant change."""
    outcomes = _make_outcome_rows(30, duration_ms=1200)
    mock_outcome_db.get_outcomes = AsyncMock(return_value=outcomes)

    monitor = MetaMonitorManager(
        outcome_db=mock_outcome_db,
        routing_audit_db=mock_routing_audit_db,
        learning_db=mock_learning_db,
    )
    report = await monitor.analyze(user_id="u1")
    assert report.latency_trend == "stable"


@pytest.mark.asyncio
async def test_cleanup_called_during_analyze(mock_outcome_db, mock_routing_audit_db, mock_learning_db):
    """MetaMonitor cleans up old reports during each analysis run."""
    mock_outcome_db.get_outcomes = AsyncMock(return_value=_make_outcome_rows(5))

    monitor = MetaMonitorManager(
        outcome_db=mock_outcome_db,
        routing_audit_db=mock_routing_audit_db,
        learning_db=mock_learning_db,
    )
    await monitor.analyze(user_id="u1")
    mock_learning_db.cleanup_old_reports.assert_called_once_with(max_age_days=7)
```

- [ ] **Step 2: Run to verify tests fail**

Run: `python -m pytest tests/test_learning_meta_monitor.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement MetaMonitorManager**

Create `hestia/learning/meta_monitor.py`:
```python
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

    def _compute_latency_trend(self, outcomes: List[Dict]) -> tuple[Optional[float], Optional[str]]:
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
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_learning_meta_monitor.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add hestia/learning/meta_monitor.py tests/test_learning_meta_monitor.py
git commit -m "feat: MetaMonitorManager — routing quality, confusion detection, latency trends"
```

---

## Chunk 4: Trigger Metrics + Briefing Integration

### Task 4.1: Trigger config and monitor

**Files:**
- Create: `config/triggers.yaml`
- Create: `hestia/learning/trigger_monitor.py`
- Test: `tests/test_learning_triggers.py`

- [ ] **Step 1: Create triggers.yaml**

```yaml
triggers:
  enabled: true
  check_interval_hours: 24

  thresholds:
    memory_total_chunks:
      value: 5000
      direction: above
      message: "Memory chunk count exceeded {value}. Consider Sprint 16 consolidation."
      cooldown_days: 30

    memory_redundancy_pct:
      value: 30
      direction: above
      message: "Memory redundancy rate is {value}%. Consolidation would reduce noise."
      cooldown_days: 30

    knowledge_entity_count:
      value: 500
      direction: above
      message: "Knowledge graph has {value} entities. Graph RAG Lite (Sprint 17) may be actionable."
      cooldown_days: 30

    inference_avg_latency_ms:
      value: 3000
      direction: above
      message: "Average inference latency is {value}ms. Consider model optimization."
      cooldown_days: 7
```

- [ ] **Step 2: Write trigger tests**

```python
"""Tests for hestia.learning.trigger_monitor."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock
from hestia.learning.trigger_monitor import TriggerMonitor
from hestia.learning.models import TriggerAlert


@pytest.fixture
def mock_learning_db():
    db = AsyncMock()
    db.store_trigger_alert = AsyncMock()
    db.get_last_trigger_fire = AsyncMock(return_value=None)
    return db


@pytest.fixture
def trigger_config():
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
async def test_trigger_fires_when_threshold_exceeded(mock_learning_db, trigger_config):
    monitor = TriggerMonitor(learning_db=mock_learning_db, config=trigger_config)
    current_metrics = {"memory_total_chunks": 5200.0, "inference_avg_latency_ms": 1500.0}

    alerts = await monitor.check_thresholds(user_id="u1", metrics=current_metrics)
    assert len(alerts) == 1
    assert alerts[0].trigger_name == "memory_total_chunks"
    mock_learning_db.store_trigger_alert.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_does_not_fire_within_cooldown(mock_learning_db, trigger_config):
    """Trigger suppressed if last fire was within cooldown period."""
    recent_alert = TriggerAlert(
        id="old", user_id="u1", trigger_name="memory_total_chunks",
        current_value=5100.0, threshold_value=5000.0,
        direction="above", message="Old alert.",
        timestamp=datetime.now(timezone.utc) - timedelta(days=5),  # 5 days ago, cooldown is 30
    )
    mock_learning_db.get_last_trigger_fire = AsyncMock(return_value=recent_alert)

    monitor = TriggerMonitor(learning_db=mock_learning_db, config=trigger_config)
    current_metrics = {"memory_total_chunks": 5300.0, "inference_avg_latency_ms": 1500.0}

    alerts = await monitor.check_thresholds(user_id="u1", metrics=current_metrics)
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_trigger_disabled(mock_learning_db):
    config = {"triggers": {"enabled": False, "thresholds": {}}}
    monitor = TriggerMonitor(learning_db=mock_learning_db, config=config)

    alerts = await monitor.check_thresholds(user_id="u1", metrics={"memory_total_chunks": 9999.0})
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_trigger_below_direction(mock_learning_db):
    config = {
        "triggers": {
            "enabled": True,
            "thresholds": {
                "positive_ratio": {
                    "value": 0.5,
                    "direction": "below",
                    "message": "Positive ratio dropped to {value}.",
                    "cooldown_days": 7,
                },
            },
        },
    }
    monitor = TriggerMonitor(learning_db=mock_learning_db, config=config)

    alerts = await monitor.check_thresholds(user_id="u1", metrics={"positive_ratio": 0.3})
    assert len(alerts) == 1
    assert alerts[0].trigger_name == "positive_ratio"
```

- [ ] **Step 3: Implement TriggerMonitor**

Create `hestia/learning/trigger_monitor.py`:
```python
"""Trigger metrics monitor — configurable threshold checking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List

from hestia.logging import get_logger, LogComponent
from hestia.learning.models import TriggerAlert


logger = get_logger()


class TriggerMonitor:
    """Checks system metrics against configurable thresholds."""

    def __init__(self, learning_db: Any, config: Dict[str, Any]) -> None:
        self._learning_db = learning_db
        self._config = config

    async def check_thresholds(
        self, user_id: str, metrics: Dict[str, float]
    ) -> List[TriggerAlert]:
        """Check all configured thresholds against current metrics.

        Returns list of newly fired alerts (respects cooldown).
        """
        triggers_cfg = self._config.get("triggers", {})
        if not triggers_cfg.get("enabled", False):
            return []

        thresholds = triggers_cfg.get("thresholds", {})
        fired: List[TriggerAlert] = []

        for name, threshold_cfg in thresholds.items():
            current = metrics.get(name)
            if current is None:
                continue

            threshold_value = threshold_cfg["value"]
            direction = threshold_cfg["direction"]
            cooldown_days = threshold_cfg.get("cooldown_days", 30)

            # Check direction
            exceeded = False
            if direction == "above" and current > threshold_value:
                exceeded = True
            elif direction == "below" and current < threshold_value:
                exceeded = True

            if not exceeded:
                continue

            # Check cooldown
            last_fire = await self._learning_db.get_last_trigger_fire(user_id, name)
            if last_fire:
                cooldown_until = last_fire.timestamp + timedelta(days=cooldown_days)
                if datetime.now(timezone.utc) < cooldown_until:
                    continue

            # Fire alert
            message = threshold_cfg["message"].replace("{value}", str(current))
            alert = TriggerAlert(
                id=str(uuid.uuid4()),
                user_id=user_id,
                trigger_name=name,
                current_value=current,
                threshold_value=threshold_value,
                direction=direction,
                message=message,
                timestamp=datetime.now(timezone.utc),
            )
            await self._learning_db.store_trigger_alert(alert)
            fired.append(alert)

            logger.info(
                f"Trigger fired: {name}",
                component=LogComponent.LEARNING,
                data={
                    "trigger": name,
                    "current": current,
                    "threshold": threshold_value,
                    "direction": direction,
                },
            )

        return fired
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_learning_triggers.py -v`
Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add config/triggers.yaml hestia/learning/trigger_monitor.py tests/test_learning_triggers.py
git commit -m "feat: TriggerMonitor — configurable threshold checking with cooldown"
```

### Task 4.2: Briefing integration

**Files:**
- Modify: `hestia/proactive/briefing.py:535-589`

- [ ] **Step 1: Add _add_system_alerts_section() to BriefingGenerator**

After `_add_health_section()` (line ~589), add:
```python
async def _add_system_alerts_section(self, briefing: Briefing) -> None:
    """Add unacknowledged system alerts to briefing."""
    try:
        from hestia.learning.database import LearningDatabase
        learning_db = LearningDatabase("data/learning.db")
        await learning_db.initialize()
        # Use a default user_id — single-user system
        alerts = await learning_db.get_unacknowledged_alerts("default")
        await learning_db.close()

        if alerts:
            lines = [f"- {a.message}" for a in alerts[:5]]  # Max 5 alerts
            briefing.sections.append(BriefingSection(
                title="System Alerts",
                content="\n".join(lines),
                priority=95,
                icon="bell.badge",
            ))
    except Exception:
        pass  # System alerts are best-effort
```

Call it in `generate()` after `_add_health_section()`:
```python
await self._add_system_alerts_section(briefing)
```

- [ ] **Step 2: Run existing proactive tests to verify no regression**

Run: `python -m pytest tests/test_proactive*.py -v --timeout=30`
Expected: All existing proactive tests PASS.

- [ ] **Step 3: Commit**

```bash
git add hestia/proactive/briefing.py
git commit -m "feat: inject system alerts section into proactive briefing"
```

---

## Chunk 5: API Routes + Server Wiring

### Task 5.1: Learning API routes

**Files:**
- Create: `hestia/api/routes/learning.py`
- Test: `tests/test_learning_routes.py`

- [ ] **Step 1: Write route tests**

```python
"""Tests for learning API routes."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from hestia.api.routes.learning import router as learning_router
from hestia.learning.models import (
    MetaMonitorReport, MemoryHealthSnapshot, TriggerAlert, ReportStatus,
)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(learning_router)
    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _mock_report():
    return MetaMonitorReport(
        id="r1", user_id="u1",
        timestamp=datetime.now(timezone.utc),
        status=ReportStatus.COMPLETE,
        total_outcomes=50, positive_ratio=0.72,
        routing_stats=[], confusion_sessions=[],
        avg_latency_ms=1200.0, latency_trend="stable",
        sample_size_sufficient=True,
    )


def _mock_snapshot():
    return MemoryHealthSnapshot(
        id="s1", user_id="u1",
        timestamp=datetime.now(timezone.utc),
        chunk_count=1200,
        chunk_count_by_source={"conversation": 800},
        redundancy_estimate_pct=12.5,
        entity_count=150, fact_count=300,
        stale_entity_count=10, contradiction_count=3,
        community_count=8,
    )


@pytest.mark.asyncio
async def test_get_latest_report(client):
    with patch("hestia.api.routes.learning._get_learning_db") as mock_db:
        mock_db.return_value = AsyncMock(
            get_latest_report=AsyncMock(return_value=_mock_report())
        )
        resp = await client.get("/v1/learning/report?user_id=u1")
    assert resp.status_code == 200
    assert resp.json()["data"]["positive_ratio"] == 0.72


@pytest.mark.asyncio
async def test_get_latest_report_not_found(client):
    with patch("hestia.api.routes.learning._get_learning_db") as mock_db:
        mock_db.return_value = AsyncMock(
            get_latest_report=AsyncMock(return_value=None)
        )
        resp = await client.get("/v1/learning/report?user_id=u1")
    assert resp.status_code == 200
    assert resp.json()["data"] is None


@pytest.mark.asyncio
async def test_get_memory_health(client):
    with patch("hestia.api.routes.learning._get_learning_db") as mock_db:
        mock_db.return_value = AsyncMock(
            get_latest_health_snapshot=AsyncMock(return_value=_mock_snapshot())
        )
        resp = await client.get("/v1/learning/memory-health?user_id=u1")
    assert resp.status_code == 200
    assert resp.json()["data"]["chunk_count"] == 1200


@pytest.mark.asyncio
async def test_get_memory_health_history(client):
    with patch("hestia.api.routes.learning._get_learning_db") as mock_db:
        mock_db.return_value = AsyncMock(
            get_health_snapshot_history=AsyncMock(return_value=[_mock_snapshot()])
        )
        resp = await client.get("/v1/learning/memory-health/history?user_id=u1&days=30")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1


@pytest.mark.asyncio
async def test_get_unacknowledged_alerts(client):
    alert = TriggerAlert(
        id="a1", user_id="u1", trigger_name="test",
        current_value=100.0, threshold_value=50.0,
        direction="above", message="Test alert.",
        timestamp=datetime.now(timezone.utc),
    )
    with patch("hestia.api.routes.learning._get_learning_db") as mock_db:
        mock_db.return_value = AsyncMock(
            get_unacknowledged_alerts=AsyncMock(return_value=[alert])
        )
        resp = await client.get("/v1/learning/alerts?user_id=u1")
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1
```

- [ ] **Step 2: Implement routes**

Create `hestia/api/routes/learning.py`:
```python
"""API routes for the learning module."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from hestia.logging import get_logger, LogComponent


logger = get_logger()
router = APIRouter(prefix="/v1/learning", tags=["learning"])

_learning_db_instance = None


async def _get_learning_db():
    global _learning_db_instance
    if _learning_db_instance is None:
        from hestia.learning.database import LearningDatabase
        _learning_db_instance = LearningDatabase("data/learning.db")
        await _learning_db_instance.initialize()
    return _learning_db_instance


@router.get("/report")
async def get_latest_report(user_id: str = Query(...)):
    """Get the latest MetaMonitor report."""
    db = await _get_learning_db()
    report = await db.get_latest_report(user_id)
    return {"data": report.to_dict() if report else None}


@router.get("/memory-health")
async def get_memory_health(user_id: str = Query(...)):
    """Get the latest memory health snapshot."""
    db = await _get_learning_db()
    snapshot = await db.get_latest_health_snapshot(user_id)
    return {"data": snapshot.to_dict() if snapshot else None}


@router.get("/memory-health/history")
async def get_memory_health_history(
    user_id: str = Query(...),
    days: int = Query(default=30, ge=1, le=365),
):
    """Get memory health snapshot history."""
    db = await _get_learning_db()
    snapshots = await db.get_health_snapshot_history(user_id, days=days)
    return {"data": [s.to_dict() for s in snapshots]}


@router.get("/alerts")
async def get_alerts(user_id: str = Query(...)):
    """Get unacknowledged trigger alerts."""
    db = await _get_learning_db()
    alerts = await db.get_unacknowledged_alerts(user_id)
    return {"data": [a.to_dict() for a in alerts]}


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user_id: str = Query(...)):
    """Acknowledge a trigger alert."""
    db = await _get_learning_db()
    await db.acknowledge_alert(alert_id, user_id)
    return {"status": "acknowledged"}
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_learning_routes.py -v`
Expected: All 5 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add hestia/api/routes/learning.py tests/test_learning_routes.py
git commit -m "feat: /v1/learning/ API routes — report, memory-health, alerts"
```

### Task 5.2: Server wiring

**Files:**
- Modify: `hestia/api/server.py`

- [ ] **Step 1: Register learning router in server.py**

In the router import section, add:
```python
from hestia.api.routes.learning import router as learning_router
```

In the `include_router` block (after the last router), add:
```python
app.include_router(learning_router)
```

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest tests/ --timeout=30 -q`
Expected: All tests pass. No behavior change — just registration.

- [ ] **Step 3: Commit**

```bash
git add hestia/api/server.py
git commit -m "feat: register learning routes in server"
```

---

## Chunk 6: Integration + Full Suite Verification

### Task 6.1: Validate-security-edit.sh compatibility

- [ ] **Step 1: Check that security hook doesn't false-positive on learning module**

The learning module handles no credentials and stores no sensitive data. Verify:
```bash
echo "hestia/learning/meta_monitor.py" | bash scripts/validate-security-edit.sh
```
Expected: No security warnings.

### Task 6.2: Full test suite verification

- [ ] **Step 1: Run complete backend test suite**

Run: `python -m pytest tests/ --timeout=30 -v`
Expected: All existing tests pass + ~25 new learning tests pass.

- [ ] **Step 2: Run CLI tests**

Run: `cd hestia-cli && python -m pytest tests/ -v --timeout=30`
Expected: All 135 CLI tests pass (no changes to CLI).

- [ ] **Step 3: Verify count-check.sh**

Run: `bash scripts/count-check.sh`
Note: Script may show drift for test file count — known issue (doesn't scan hestia-cli/tests/).

### Task 6.3: Documentation updates

- [ ] **Step 1: Update CLAUDE.md project structure**

Add `learning/` to the project structure under `hestia/`:
```
├── learning/                    # MetaMonitor, Memory Health, Trigger Metrics
│   ├── models.py               # MetaMonitorReport, MemoryHealthSnapshot, TriggerAlert
│   ├── database.py             # LearningDatabase (SQLite: reports, snapshots, alerts)
│   ├── meta_monitor.py         # MetaMonitorManager (hourly analysis)
│   ├── memory_health.py        # MemoryHealthMonitor (daily diagnostics)
│   └── trigger_monitor.py      # TriggerMonitor (threshold checking)
```

Update endpoint count: `~175 endpoints across 27 route modules`

Add `LEARNING` to LogComponent list.

Update test count after final run.

- [ ] **Step 2: Update api-contract.md**

Add Learning section:
```markdown
| Learning | 5 | `/v1/learning/report`, `memory-health`, `memory-health/history`, `alerts`, `alerts/{id}/acknowledge` |
```

- [ ] **Step 3: Update SPRINT.md**

Mark Sprint 15 WS1 (MetaMonitor), WS2 (Memory Health), WS3 (Triggers) as complete with commit hashes.

- [ ] **Step 4: Final commit**

```bash
git add CLAUDE.md docs/api-contract.md SPRINT.md
git commit -m "docs: Sprint 15 — learning module, 5 endpoints, ~25 tests"
```

---

## Summary

| Chunk | Tasks | Tests | Commits |
|-------|-------|-------|---------|
| 0: handler.py decomposition | 2 | 0 (existing pass) | 2 |
| 1: Retrieval feedback loop | 3 | 1 | 3 |
| 2: Learning foundation + Memory Health | 3 | 15 | 3 |
| 3: MetaMonitor core | 1 | 5 | 1 |
| 4: Trigger metrics + briefing | 2 | 4 | 2 |
| 5: API routes + server | 2 | 5 | 2 |
| 6: Integration + docs | 3 | 0 (verification) | 1 |
| **Total** | **16** | **~30** | **14** |

**Note:** This plan covers the core Sprint 15 workstreams. The "additional items" (outcome pipeline, correction classifier, settings tools) are deferred per the audit's half-time cut list — they can be added in a follow-up sprint or as individual tasks if velocity allows.
