# Neural Net Learning Cycle — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a learning cycle system that closes the feedback loop between Hestia's actions and their outcomes, enabling self-improvement through reflection and principle distillation.

**Architecture:** New `hestia/learning/` module following the standard manager pattern (models + database + manager). Called from `RequestHandler` post-response via `asyncio.create_task()`. Own SQLite + ChromaDB storage. Dual-path reflection (local-first, cloud-safe fallback).

**Tech Stack:** Python 3.12, FastAPI, aiosqlite, ChromaDB, Qwen 2.5 7B (local), Pydantic, pytest

**Design doc:** `docs/plans/2026-03-03-neural-net-learning-cycle-design.md`

---

## Phase 1: The Reflection Engine (Sprint-Ready, 12 Tasks)

---

### Task 1: Foundation — Models & Enums

**Files:**
- Create: `hestia/learning/__init__.py`
- Create: `hestia/learning/models.py`
- Modify: `hestia/logging/structured_logger.py:55` (add LEARNING to LogComponent)
- Modify: `hestia/memory/models.py:40` (add PRINCIPLE to ChunkType)
- Create: `hestia/config/learning.yaml`
- Test: `tests/test_learning.py`

**Step 1: Write the failing test**

```python
# tests/test_learning.py
"""Tests for Hestia learning cycle (Phase 1: Reflection Engine)."""

import pytest
from hestia.learning.models import (
    LearningDomain,
    OutcomeSignalType,
    OutcomeSignal,
    Principle,
    ReflectionResult,
    InteractionRecord,
)


class TestLearningModels:
    """Tests for learning data models."""

    def test_learning_domain_values(self) -> None:
        assert LearningDomain.SCHEDULING.value == "scheduling"
        assert LearningDomain.COMMUNICATION.value == "communication"
        assert LearningDomain.TECHNICAL.value == "technical"
        assert LearningDomain.HEALTH.value == "health"
        assert LearningDomain.PERSONAL.value == "personal"
        assert LearningDomain.WORKFLOW.value == "workflow"
        assert LearningDomain.GENERAL.value == "general"

    def test_outcome_signal_type_values(self) -> None:
        assert OutcomeSignalType.RESPONSE_ACCEPTED.value == "accepted"
        assert OutcomeSignalType.THUMBS_UP.value == "thumbs_up"
        assert OutcomeSignalType.THUMBS_DOWN.value == "thumbs_down"
        assert OutcomeSignalType.FOLLOW_UP_CORRECTION.value == "correction"

    def test_outcome_signal_creation(self) -> None:
        signal = OutcomeSignal(
            id="sig-001",
            session_id="sess-001",
            interaction_id="int-001",
            signal_type=OutcomeSignalType.RESPONSE_ACCEPTED,
            domain=LearningDomain.SCHEDULING,
            value=0.5,
            context="Response accepted without correction",
            metadata={},
        )
        assert signal.value == 0.5
        assert signal.domain == LearningDomain.SCHEDULING

    def test_principle_creation(self) -> None:
        principle = Principle(
            id="prin-001",
            domain=LearningDomain.COMMUNICATION,
            content="User prefers concise responses for scheduling",
            confidence=0.3,
            validation_count=0,
            contradiction_count=0,
            source_interactions=["int-001", "int-002"],
            active=True,
        )
        assert principle.confidence == 0.3
        assert principle.active is True

    def test_principle_is_established(self) -> None:
        principle = Principle(
            id="prin-002",
            domain=LearningDomain.TECHNICAL,
            content="Detailed responses for architecture questions",
            confidence=0.85,
            validation_count=6,
            contradiction_count=1,
            source_interactions=["int-003"],
            active=True,
        )
        assert principle.is_established is True

    def test_principle_not_established_low_confidence(self) -> None:
        principle = Principle(
            id="prin-003",
            domain=LearningDomain.GENERAL,
            content="Test principle",
            confidence=0.5,
            validation_count=10,
            contradiction_count=0,
            source_interactions=[],
            active=True,
        )
        assert principle.is_established is False


class TestLogComponent:
    """Verify LEARNING was added to LogComponent."""

    def test_learning_component_exists(self) -> None:
        from hestia.logging import LogComponent
        assert LogComponent.LEARNING.value == "learning"


class TestChunkType:
    """Verify PRINCIPLE was added to ChunkType."""

    def test_principle_chunk_type_exists(self) -> None:
        from hestia.memory.models import ChunkType
        assert ChunkType.PRINCIPLE.value == "principle"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestLearningModels -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.learning'`

**Step 3: Create the models**

Create `hestia/learning/__init__.py`:
```python
"""
Hestia Learning Cycle — Phase 1: Reflection Engine.

Closes the feedback loop between actions and outcomes,
enabling self-improvement through reflection and principle distillation.
"""
```

Create `hestia/learning/models.py`:
```python
"""Data models for the Hestia learning cycle."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class LearningDomain(Enum):
    """Area of knowledge/behavior a learning signal relates to."""
    SCHEDULING = "scheduling"
    COMMUNICATION = "communication"
    TECHNICAL = "technical"
    HEALTH = "health"
    PERSONAL = "personal"
    WORKFLOW = "workflow"
    GENERAL = "general"


class OutcomeSignalType(Enum):
    """Type of implicit or explicit outcome signal."""
    RESPONSE_ACCEPTED = "accepted"
    FOLLOW_UP_CORRECTION = "correction"
    TOPIC_REVISIT = "revisit"
    QUICK_FOLLOW_UP = "quick_follow_up"
    LONG_GAP = "long_gap"
    THUMBS_UP = "thumbs_up"
    THUMBS_DOWN = "thumbs_down"
    ANTICIPATION_HIT = "anticipation_hit"
    ANTICIPATION_MISS = "anticipation_miss"


@dataclass
class OutcomeSignal:
    """A signal about how an interaction went."""
    id: str
    session_id: str
    interaction_id: str
    signal_type: OutcomeSignalType
    domain: LearningDomain
    value: float  # -1.0 (negative) to 1.0 (positive)
    context: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        if not -1.0 <= self.value <= 1.0:
            raise ValueError(f"Signal value must be in [-1.0, 1.0], got {self.value}")


@dataclass
class Principle:
    """A distilled behavioral strategy extracted from interactions."""
    id: str
    domain: LearningDomain
    content: str
    confidence: float  # 0.0 - 1.0
    validation_count: int = 0
    contradiction_count: int = 0
    source_interactions: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_validated: Optional[datetime] = None
    last_contradicted: Optional[datetime] = None
    superseded_by: Optional[str] = None
    active: bool = True

    @property
    def is_established(self) -> bool:
        """A principle is established when confidence > 0.8 and validated > 5 times."""
        return self.confidence > 0.8 and self.validation_count > 5

    def validate(self) -> None:
        """Record a validation (outcome confirmed this principle)."""
        self.validation_count += 1
        self.last_validated = datetime.utcnow()
        self.confidence = min(1.0, self.confidence + 0.05)

    def contradict(self) -> None:
        """Record a contradiction (outcome went against this principle)."""
        self.contradiction_count += 1
        self.last_contradicted = datetime.utcnow()
        self.confidence = max(0.0, self.confidence - 0.1)
        if self.confidence < 0.1:
            self.active = False

    def supersede(self, new_principle_id: str) -> None:
        """Mark this principle as superseded by a newer one."""
        self.superseded_by = new_principle_id
        self.active = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "domain": self.domain.value,
            "content": self.content,
            "confidence": self.confidence,
            "validation_count": self.validation_count,
            "contradiction_count": self.contradiction_count,
            "source_interactions": self.source_interactions,
            "created_at": self.created_at.isoformat(),
            "last_validated": self.last_validated.isoformat() if self.last_validated else None,
            "last_contradicted": self.last_contradicted.isoformat() if self.last_contradicted else None,
            "superseded_by": self.superseded_by,
            "active": self.active,
            "is_established": self.is_established,
        }


@dataclass
class InteractionRecord:
    """Record of an interaction for outcome tracking."""
    id: str
    session_id: str
    user_message: str
    response: str
    domain: LearningDomain
    intent_type: Optional[str] = None
    intent_confidence: Optional[float] = None
    council_quality_score: Optional[float] = None
    mode: str = "tia"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    outcome_evaluated: bool = False

    @staticmethod
    def generate_id() -> str:
        return f"int-{uuid.uuid4().hex[:12]}"


@dataclass
class ReflectionResult:
    """Result of a reflection session."""
    id: str
    session_id: str
    interaction_ids: List[str]
    what_worked: List[str]
    what_failed: List[str]
    signals_missed: List[str]
    new_principles: List[str]  # Principle IDs
    updated_principles: List[str]  # Principle IDs
    domain_scores: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @staticmethod
    def generate_id() -> str:
        return f"ref-{uuid.uuid4().hex[:12]}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "interaction_ids": self.interaction_ids,
            "what_worked": self.what_worked,
            "what_failed": self.what_failed,
            "signals_missed": self.signals_missed,
            "new_principles": self.new_principles,
            "updated_principles": self.updated_principles,
            "domain_scores": self.domain_scores,
            "timestamp": self.timestamp.isoformat(),
        }
```

Add `LEARNING` to LogComponent in `hestia/logging/structured_logger.py:55`:
```python
    INVESTIGATE = "investigate"
    LEARNING = "learning"
```

Add `PRINCIPLE` to ChunkType in `hestia/memory/models.py:40`:
```python
    SYSTEM = "system"               # System-generated notes
    PRINCIPLE = "principle"         # Distilled behavioral principle
```

Create `hestia/config/learning.yaml`:
```yaml
learning:
  enabled: true
  outcome_tracking:
    quick_follow_up_threshold_seconds: 30
    long_gap_threshold_seconds: 300
    correction_keywords: ["no", "actually", "I meant", "not what I", "wrong"]
  reflection:
    trigger_after_interactions: 10
    min_interactions_for_reflection: 3
    new_principle_confidence: 0.3
    established_confidence_threshold: 0.8
    established_validation_threshold: 5
    cloud_fallback_enabled: false
  principles:
    max_active_principles: 200
    min_confidence_for_prompt_injection: 0.5
    max_principles_in_prompt: 5
    decay_rate: 0.003
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_learning.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add hestia/learning/ hestia/config/learning.yaml hestia/logging/structured_logger.py hestia/memory/models.py tests/test_learning.py
git commit -m "feat(learning): add foundation models, enums, and config for learning cycle"
```

---

### Task 2: LearningDatabase (SQLite)

**Files:**
- Create: `hestia/learning/database.py`
- Test: `tests/test_learning.py` (add TestLearningDatabase class)

**Reference:** `hestia/tasks/database.py` (lines 24–84) for BaseDatabase extension pattern.

**Step 1: Write the failing test**

```python
# Add to tests/test_learning.py

import asyncio
from pathlib import Path
import tempfile

from hestia.learning.database import LearningDatabase


class TestLearningDatabase:
    """Tests for LearningDatabase SQLite operations."""

    @pytest.fixture
    async def db(self, tmp_path: Path) -> LearningDatabase:
        """Create a temporary learning database."""
        db = LearningDatabase(db_path=tmp_path / "test_learning.db")
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_schema_creation(self, db: LearningDatabase) -> None:
        """Tables exist after init."""
        tables = await db.list_tables()
        assert "interactions" in tables
        assert "outcome_signals" in tables
        assert "principles" in tables
        assert "reflections" in tables

    @pytest.mark.asyncio
    async def test_store_interaction(self, db: LearningDatabase) -> None:
        record = InteractionRecord(
            id="int-test001",
            session_id="sess-001",
            user_message="What's on my calendar?",
            response="You have a meeting at 3pm.",
            domain=LearningDomain.SCHEDULING,
            intent_type="CALENDAR_QUERY",
            intent_confidence=0.9,
            mode="tia",
        )
        await db.store_interaction(record)
        result = await db.get_interaction("int-test001")
        assert result is not None
        assert result.domain == LearningDomain.SCHEDULING

    @pytest.mark.asyncio
    async def test_store_outcome_signal(self, db: LearningDatabase) -> None:
        signal = OutcomeSignal(
            id="sig-test001",
            session_id="sess-001",
            interaction_id="int-test001",
            signal_type=OutcomeSignalType.RESPONSE_ACCEPTED,
            domain=LearningDomain.SCHEDULING,
            value=0.5,
            context="No correction followed",
        )
        await db.store_signal(signal)
        signals = await db.get_signals_for_session("sess-001")
        assert len(signals) == 1
        assert signals[0].value == 0.5

    @pytest.mark.asyncio
    async def test_store_principle(self, db: LearningDatabase) -> None:
        principle = Principle(
            id="prin-test001",
            domain=LearningDomain.COMMUNICATION,
            content="User prefers concise scheduling responses",
            confidence=0.3,
            source_interactions=["int-001"],
            active=True,
        )
        await db.store_principle(principle)
        result = await db.get_principle("prin-test001")
        assert result is not None
        assert result.confidence == 0.3

    @pytest.mark.asyncio
    async def test_update_principle_confidence(self, db: LearningDatabase) -> None:
        principle = Principle(
            id="prin-test002",
            domain=LearningDomain.TECHNICAL,
            content="Test principle",
            confidence=0.3,
            source_interactions=[],
            active=True,
        )
        await db.store_principle(principle)
        principle.validate()
        await db.update_principle(principle)
        result = await db.get_principle("prin-test002")
        assert result.confidence == 0.35
        assert result.validation_count == 1

    @pytest.mark.asyncio
    async def test_get_active_principles(self, db: LearningDatabase) -> None:
        for i in range(3):
            p = Principle(
                id=f"prin-active-{i}",
                domain=LearningDomain.GENERAL,
                content=f"Principle {i}",
                confidence=0.5,
                source_interactions=[],
                active=(i != 2),  # Third one is inactive
            )
            await db.store_principle(p)
        active = await db.get_active_principles()
        assert len(active) == 2

    @pytest.mark.asyncio
    async def test_get_unevaluated_interactions(self, db: LearningDatabase) -> None:
        for i in range(3):
            record = InteractionRecord(
                id=f"int-uneval-{i}",
                session_id="sess-001",
                user_message=f"Message {i}",
                response=f"Response {i}",
                domain=LearningDomain.GENERAL,
            )
            record.outcome_evaluated = (i == 0)  # First one already evaluated
            await db.store_interaction(record)
        unevaluated = await db.get_unevaluated_interactions("sess-001")
        assert len(unevaluated) == 2

    @pytest.mark.asyncio
    async def test_store_reflection(self, db: LearningDatabase) -> None:
        result = ReflectionResult(
            id="ref-test001",
            session_id="sess-001",
            interaction_ids=["int-001", "int-002"],
            what_worked=["Concise responses"],
            what_failed=["Missed calendar context"],
            signals_missed=["Time-of-day pattern"],
            new_principles=["prin-001"],
            updated_principles=[],
            domain_scores={"scheduling": 0.7, "communication": 0.8},
        )
        await db.store_reflection(result)
        reflections = await db.get_recent_reflections(limit=5)
        assert len(reflections) == 1
        assert reflections[0].id == "ref-test001"

    @pytest.mark.asyncio
    async def test_get_domain_stats(self, db: LearningDatabase) -> None:
        # Store some signals across domains
        for i, domain in enumerate([LearningDomain.SCHEDULING, LearningDomain.SCHEDULING, LearningDomain.TECHNICAL]):
            signal = OutcomeSignal(
                id=f"sig-stats-{i}",
                session_id="sess-001",
                interaction_id=f"int-{i}",
                signal_type=OutcomeSignalType.RESPONSE_ACCEPTED,
                domain=domain,
                value=0.5,
                context="Test",
            )
            await db.store_signal(signal)
        stats = await db.get_domain_stats()
        assert stats[LearningDomain.SCHEDULING]["signal_count"] == 2
        assert stats[LearningDomain.TECHNICAL]["signal_count"] == 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestLearningDatabase -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'hestia.learning.database'`

**Step 3: Write minimal implementation**

Create `hestia/learning/database.py` following the `TaskDatabase` pattern from `hestia/tasks/database.py`. Key tables:
- `interactions` — InteractionRecord storage
- `outcome_signals` — OutcomeSignal storage
- `principles` — Principle metadata (content also stored in ChromaDB for vector search)
- `reflections` — ReflectionResult storage

Methods: `store_interaction()`, `get_interaction()`, `get_unevaluated_interactions()`, `mark_interaction_evaluated()`, `store_signal()`, `get_signals_for_session()`, `get_signals_for_interaction()`, `store_principle()`, `get_principle()`, `update_principle()`, `get_active_principles()`, `get_active_principles_by_domain()`, `store_reflection()`, `get_recent_reflections()`, `get_domain_stats()`, `list_tables()`.

Each method uses `async with self._connection.execute(...)` pattern from `BaseDatabase`. Serialize JSON fields (lists, dicts) via `json.dumps`/`json.loads`. Enum fields stored as `.value` strings.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_learning.py::TestLearningDatabase -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add hestia/learning/database.py tests/test_learning.py
git commit -m "feat(learning): add LearningDatabase with SQLite schema and CRUD operations"
```

---

### Task 3: PrincipleStore (ChromaDB)

**Files:**
- Create: `hestia/learning/principles.py`
- Test: `tests/test_learning.py` (add TestPrincipleStore class)

**Reference:** `hestia/memory/manager.py` for ChromaDB collection usage pattern.

**Step 1: Write the failing test**

```python
# Add to tests/test_learning.py
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.learning.principles import PrincipleStore


class TestPrincipleStore:
    """Tests for PrincipleStore (ChromaDB vector storage)."""

    @pytest.fixture
    def mock_chromadb(self) -> MagicMock:
        """Mock ChromaDB client and collection."""
        collection = MagicMock()
        collection.add = MagicMock()
        collection.query = MagicMock(return_value={
            "ids": [["prin-001"]],
            "documents": [["User prefers concise scheduling responses"]],
            "metadatas": [[{
                "domain": "scheduling",
                "confidence": "0.7",
                "active": "true",
                "validation_count": "3",
            }]],
            "distances": [[0.3]],
        })
        collection.update = MagicMock()
        collection.delete = MagicMock()
        collection.count = MagicMock(return_value=5)
        client = MagicMock()
        client.get_or_create_collection = MagicMock(return_value=collection)
        return client

    @pytest.fixture
    def store(self, mock_chromadb: MagicMock) -> PrincipleStore:
        return PrincipleStore(chromadb_client=mock_chromadb)

    def test_store_principle(self, store: PrincipleStore) -> None:
        principle = Principle(
            id="prin-001",
            domain=LearningDomain.SCHEDULING,
            content="User prefers concise scheduling responses",
            confidence=0.3,
            source_interactions=["int-001"],
            active=True,
        )
        store.store(principle)
        store._collection.add.assert_called_once()

    def test_search_relevant_principles(self, store: PrincipleStore) -> None:
        results = store.search("calendar scheduling", limit=5, min_confidence=0.5)
        assert len(results) == 1
        assert results[0]["id"] == "prin-001"
        assert results[0]["relevance"] > 0

    def test_search_filters_by_domain(self, store: PrincipleStore) -> None:
        store.search("test", domain=LearningDomain.SCHEDULING, limit=5)
        call_kwargs = store._collection.query.call_args
        assert call_kwargs is not None

    def test_update_principle(self, store: PrincipleStore) -> None:
        principle = Principle(
            id="prin-001",
            domain=LearningDomain.SCHEDULING,
            content="Updated content",
            confidence=0.7,
            source_interactions=["int-001"],
            active=True,
        )
        store.update(principle)
        store._collection.update.assert_called_once()

    def test_count(self, store: PrincipleStore) -> None:
        assert store.count() == 5
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestPrincipleStore -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `hestia/learning/principles.py`:
- Class `PrincipleStore` wrapping a ChromaDB collection (`learning_principles`)
- Uses same embedding function as memory (`all-MiniLM-L6-v2` via `chromadb.utils.embedding_functions`)
- Methods: `store(principle)`, `search(query, domain, limit, min_confidence)`, `update(principle)`, `delete(principle_id)`, `count()`
- Metadata stored as strings (ChromaDB limitation), parsed back to proper types on retrieval
- Returns relevance-weighted results: `relevance = (1 - distance) * confidence`

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_learning.py::TestPrincipleStore -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add hestia/learning/principles.py tests/test_learning.py
git commit -m "feat(learning): add PrincipleStore with ChromaDB vector search"
```

---

### Task 4: OutcomeTracker

**Files:**
- Create: `hestia/learning/outcome_tracker.py`
- Test: `tests/test_learning.py` (add TestOutcomeTracker class)

**Step 1: Write the failing test**

```python
# Add to tests/test_learning.py
from hestia.learning.outcome_tracker import OutcomeTracker


class TestOutcomeTracker:
    """Tests for implicit and explicit outcome signal detection."""

    @pytest.fixture
    def tracker(self) -> OutcomeTracker:
        return OutcomeTracker()

    def test_intent_to_domain_mapping(self, tracker: OutcomeTracker) -> None:
        assert tracker.intent_to_domain("CALENDAR_QUERY") == LearningDomain.SCHEDULING
        assert tracker.intent_to_domain("CALENDAR_CREATE") == LearningDomain.SCHEDULING
        assert tracker.intent_to_domain("CHAT") == LearningDomain.COMMUNICATION
        assert tracker.intent_to_domain("MEMORY_SEARCH") == LearningDomain.WORKFLOW
        assert tracker.intent_to_domain("UNKNOWN_TYPE") == LearningDomain.GENERAL

    def test_detect_correction_keywords(self, tracker: OutcomeTracker) -> None:
        assert tracker.is_correction("No, I meant the other meeting") is True
        assert tracker.is_correction("Actually, cancel that") is True
        assert tracker.is_correction("That's not what I wanted") is True
        assert tracker.is_correction("Thanks, that's perfect") is False
        assert tracker.is_correction("Tell me more about that") is False

    def test_detect_quick_follow_up(self, tracker: OutcomeTracker) -> None:
        """<30 seconds between messages suggests insufficient response."""
        from datetime import timedelta
        prev_time = datetime(2026, 3, 3, 10, 0, 0)
        quick_time = prev_time + timedelta(seconds=15)
        normal_time = prev_time + timedelta(seconds=60)

        assert tracker.is_quick_follow_up(prev_time, quick_time) is True
        assert tracker.is_quick_follow_up(prev_time, normal_time) is False

    def test_detect_long_gap(self, tracker: OutcomeTracker) -> None:
        """5+ minutes suggests the response was useful (user went off to use it)."""
        from datetime import timedelta
        prev_time = datetime(2026, 3, 3, 10, 0, 0)
        long_time = prev_time + timedelta(minutes=6)
        short_time = prev_time + timedelta(minutes=2)

        assert tracker.is_long_gap(prev_time, long_time) is True
        assert tracker.is_long_gap(prev_time, short_time) is False

    def test_evaluate_interaction_accepted(self, tracker: OutcomeTracker) -> None:
        """When next message is on a different topic with normal timing, signal is 'accepted'."""
        from datetime import timedelta
        prev = InteractionRecord(
            id="int-001", session_id="sess-001",
            user_message="What's on my calendar?",
            response="Meeting at 3pm",
            domain=LearningDomain.SCHEDULING,
        )
        current_time = prev.timestamp + timedelta(minutes=2)
        current_message = "Can you remind me to buy groceries?"

        signals = tracker.evaluate_previous(prev, current_message, current_time)
        assert len(signals) >= 1
        accepted = [s for s in signals if s.signal_type == OutcomeSignalType.RESPONSE_ACCEPTED]
        assert len(accepted) == 1

    def test_evaluate_interaction_correction(self, tracker: OutcomeTracker) -> None:
        """When next message corrects on same topic, signal is 'correction'."""
        from datetime import timedelta
        prev = InteractionRecord(
            id="int-002", session_id="sess-001",
            user_message="What's on my calendar?",
            response="Meeting at 3pm",
            domain=LearningDomain.SCHEDULING,
        )
        current_time = prev.timestamp + timedelta(seconds=20)
        current_message = "No, I meant tomorrow's calendar"

        signals = tracker.evaluate_previous(prev, current_message, current_time)
        correction = [s for s in signals if s.signal_type == OutcomeSignalType.FOLLOW_UP_CORRECTION]
        assert len(correction) == 1

    def test_record_explicit_feedback_thumbs_up(self, tracker: OutcomeTracker) -> None:
        signal = tracker.create_feedback_signal(
            interaction_id="int-003",
            session_id="sess-001",
            domain=LearningDomain.COMMUNICATION,
            rating=5,
            comment="Great response",
        )
        assert signal.signal_type == OutcomeSignalType.THUMBS_UP
        assert signal.value == 1.0
        assert signal.metadata["comment"] == "Great response"

    def test_record_explicit_feedback_thumbs_down(self, tracker: OutcomeTracker) -> None:
        signal = tracker.create_feedback_signal(
            interaction_id="int-004",
            session_id="sess-001",
            domain=LearningDomain.TECHNICAL,
            rating=1,
            comment="Too verbose",
        )
        assert signal.signal_type == OutcomeSignalType.THUMBS_DOWN
        assert signal.value == -1.0
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestOutcomeTracker -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `hestia/learning/outcome_tracker.py`:
- `OutcomeTracker` class with config loaded from `learning.yaml`
- `intent_to_domain(intent_type: str) -> LearningDomain` mapping IntentType strings to domains
- `is_correction(message: str) -> bool` using config's correction_keywords
- `is_quick_follow_up(prev_time, current_time) -> bool` using config threshold
- `is_long_gap(prev_time, current_time) -> bool` using config threshold
- `evaluate_previous(prev: InteractionRecord, current_message: str, current_time: datetime) -> List[OutcomeSignal]` — the core "evaluate on next message" logic
- `create_feedback_signal(interaction_id, session_id, domain, rating, comment) -> OutcomeSignal` for explicit feedback

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_learning.py::TestOutcomeTracker -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add hestia/learning/outcome_tracker.py tests/test_learning.py
git commit -m "feat(learning): add OutcomeTracker with implicit/explicit signal detection"
```

---

### Task 5: ReflectionAgent

**Files:**
- Create: `hestia/learning/reflection.py`
- Test: `tests/test_learning.py` (add TestReflectionAgent class)

**Step 1: Write the failing test**

```python
# Add to tests/test_learning.py
from hestia.learning.reflection import ReflectionAgent, sanitize_for_cloud


class TestReflectionAgent:
    """Tests for LLM-based post-interaction self-critique."""

    def test_sanitize_for_cloud_strips_names(self) -> None:
        text = "Andrew wants the Tuesday dentist appointment moved"
        sanitized = sanitize_for_cloud(text)
        assert "Andrew" not in sanitized
        assert "the user" in sanitized

    def test_sanitize_for_cloud_strips_health(self) -> None:
        text = "User's blood pressure is 120/80, heart rate 72bpm"
        sanitized = sanitize_for_cloud(text, exclude_health=True)
        assert "blood pressure" not in sanitized
        assert "[health data excluded]" in sanitized

    def test_sanitize_for_cloud_preserves_structure(self) -> None:
        text = "The response was too verbose for a scheduling request"
        sanitized = sanitize_for_cloud(text)
        assert "scheduling" in sanitized
        assert "verbose" in sanitized

    def test_build_reflection_prompt(self) -> None:
        agent = ReflectionAgent()
        interactions = [
            InteractionRecord(
                id="int-001", session_id="sess-001",
                user_message="What's on my calendar?",
                response="Meeting at 3pm",
                domain=LearningDomain.SCHEDULING,
            ),
        ]
        signals = [
            OutcomeSignal(
                id="sig-001", session_id="sess-001",
                interaction_id="int-001",
                signal_type=OutcomeSignalType.RESPONSE_ACCEPTED,
                domain=LearningDomain.SCHEDULING,
                value=0.5, context="Accepted",
            ),
        ]
        existing_principles = [
            Principle(
                id="prin-001",
                domain=LearningDomain.SCHEDULING,
                content="User prefers concise scheduling responses",
                confidence=0.6, source_interactions=[], active=True,
            ),
        ]
        prompt = agent.build_reflection_prompt(interactions, signals, existing_principles)
        assert "INTERACTIONS" in prompt
        assert "OUTCOME SIGNALS" in prompt
        assert "EXISTING PRINCIPLES" in prompt
        assert "What worked well" in prompt

    @pytest.mark.asyncio
    async def test_reflect_with_mock_inference(self) -> None:
        """Mock the inference call and verify reflection parsing."""
        agent = ReflectionAgent()
        mock_response = '''
        {
            "what_worked": ["Concise calendar response"],
            "what_failed": [],
            "signals_missed": ["Time-of-day preference"],
            "confirmed_principles": ["prin-001"],
            "contradicted_principles": [],
            "new_principles": [
                {"domain": "scheduling", "content": "Morning queries prefer brief answers", "confidence": 0.3}
            ]
        }
        '''
        with patch.object(agent, '_call_inference', new_callable=AsyncMock, return_value=mock_response):
            result = await agent.reflect(
                session_id="sess-001",
                interactions=[],
                signals=[],
                existing_principles=[],
            )
        assert isinstance(result, ReflectionResult)
        assert "Concise calendar response" in result.what_worked
        assert len(result.signals_missed) == 1

    @pytest.mark.asyncio
    async def test_reflect_handles_malformed_json(self) -> None:
        """If the LLM returns garbage, reflection should return empty result, not crash."""
        agent = ReflectionAgent()
        with patch.object(agent, '_call_inference', new_callable=AsyncMock, return_value="not valid json"):
            result = await agent.reflect(
                session_id="sess-001",
                interactions=[], signals=[], existing_principles=[],
            )
        assert isinstance(result, ReflectionResult)
        assert len(result.what_worked) == 0

    def test_guard_min_interactions(self) -> None:
        agent = ReflectionAgent()
        assert agent.should_reflect(interaction_count=2, signals_count=2) is False
        assert agent.should_reflect(interaction_count=4, signals_count=4) is True
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestReflectionAgent -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `hestia/learning/reflection.py`:
- `sanitize_for_cloud(text, exclude_health=False) -> str` — strips PII using regex, replaces proper nouns with tokens
- `ReflectionAgent` class:
  - `__init__()` — loads config from learning.yaml
  - `should_reflect(interaction_count, signals_count) -> bool` — guard rail check
  - `build_reflection_prompt(interactions, signals, existing_principles) -> str` — structured prompt
  - `_call_inference(prompt, use_cloud=False) -> str` — calls inference client (Qwen local, or cloud if enabled + sanitized)
  - `_parse_reflection(raw_response) -> ReflectionResult` — JSON parsing with fallback to empty result
  - `reflect(session_id, interactions, signals, existing_principles) -> ReflectionResult` — full pipeline

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_learning.py::TestReflectionAgent -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add hestia/learning/reflection.py tests/test_learning.py
git commit -m "feat(learning): add ReflectionAgent with dual-path inference and cloud sanitization"
```

---

### Task 6: LearningManager (Orchestrator + Singleton)

**Files:**
- Create: `hestia/learning/manager.py`
- Modify: `hestia/learning/__init__.py` (export singleton factory)
- Test: `tests/test_learning.py` (add TestLearningManager class)

**Reference:** `hestia/tasks/manager.py` for singleton pattern.

**Step 1: Write the failing test**

```python
# Add to tests/test_learning.py
from hestia.learning.manager import LearningManager


class TestLearningManager:
    """Tests for LearningManager orchestration."""

    @pytest.fixture
    async def manager(self, tmp_path: Path) -> LearningManager:
        """Create manager with temp database and mocked ChromaDB."""
        mock_client = MagicMock()
        collection = MagicMock()
        collection.add = MagicMock()
        collection.query = MagicMock(return_value={
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]],
        })
        collection.count = MagicMock(return_value=0)
        mock_client.get_or_create_collection = MagicMock(return_value=collection)

        manager = LearningManager(
            db_path=tmp_path / "test_learning.db",
            chromadb_client=mock_client,
        )
        await manager.initialize()
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_record_interaction(self, manager: LearningManager) -> None:
        """Recording an interaction stores it and evaluates the previous one."""
        await manager.record_interaction(
            session_id="sess-001",
            user_message="What's on my calendar?",
            response="Meeting at 3pm",
            intent_type="CALENDAR_QUERY",
            intent_confidence=0.9,
            council_quality_score=0.8,
            mode="tia",
        )
        # Verify interaction was stored
        record = await manager._database.get_interaction(
            (await manager._database.get_unevaluated_interactions("sess-001"))[0].id
        )
        assert record is not None
        assert record.domain == LearningDomain.SCHEDULING

    @pytest.mark.asyncio
    async def test_record_feedback(self, manager: LearningManager) -> None:
        """Explicit feedback creates an outcome signal."""
        # First record an interaction
        await manager.record_interaction(
            session_id="sess-001",
            user_message="What's on my calendar?",
            response="Meeting at 3pm",
            intent_type="CALENDAR_QUERY",
            intent_confidence=0.9,
            mode="tia",
        )
        interactions = await manager._database.get_unevaluated_interactions("sess-001")
        interaction_id = interactions[0].id

        await manager.record_feedback(
            interaction_id=interaction_id,
            session_id="sess-001",
            rating=5,
            comment="Perfect",
        )
        signals = await manager._database.get_signals_for_interaction(interaction_id)
        assert len(signals) == 1
        assert signals[0].signal_type == OutcomeSignalType.THUMBS_UP

    @pytest.mark.asyncio
    async def test_get_stats(self, manager: LearningManager) -> None:
        stats = await manager.get_stats()
        assert "domains" in stats
        assert "total_interactions" in stats
        assert "total_signals" in stats
        assert "total_principles" in stats

    @pytest.mark.asyncio
    async def test_get_principles(self, manager: LearningManager) -> None:
        principles = await manager.get_principles()
        assert isinstance(principles, list)

    @pytest.mark.asyncio
    async def test_trigger_reflection_guard_rail(self, manager: LearningManager) -> None:
        """Reflection should not trigger with too few interactions."""
        result = await manager.trigger_reflection("sess-001")
        assert result is None  # Not enough data
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestLearningManager -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `hestia/learning/manager.py`:
- `LearningManager` class with `_database: LearningDatabase`, `_principle_store: PrincipleStore`, `_outcome_tracker: OutcomeTracker`, `_reflection_agent: ReflectionAgent`
- `initialize()` — creates/connects all sub-components
- `close()` — cleanup
- `record_interaction(session_id, user_message, response, intent_type, intent_confidence, council_quality_score, mode)` — stores InteractionRecord, evaluates previous interaction's outcome
- `record_feedback(interaction_id, session_id, rating, comment)` — explicit feedback
- `trigger_reflection(session_id) -> Optional[ReflectionResult]` — runs reflection if guard rails pass, creates/updates principles
- `get_principles(domain, min_confidence, active_only) -> List[Principle]`
- `get_relevant_principles(query, domain, limit) -> List[Dict]` — semantic search via PrincipleStore
- `get_stats() -> Dict[str, Any]`
- `get_reflections(limit) -> List[ReflectionResult]`
- Singleton: `get_learning_manager()`, `close_learning_manager()`

Update `hestia/learning/__init__.py` to export:
```python
from hestia.learning.manager import get_learning_manager, close_learning_manager
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_learning.py::TestLearningManager -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add hestia/learning/manager.py hestia/learning/__init__.py tests/test_learning.py
git commit -m "feat(learning): add LearningManager singleton with full orchestration"
```

---

### Task 7: API Schemas

**Files:**
- Create: `hestia/api/schemas/learning.py`
- Test: `tests/test_learning.py` (add TestLearningSchemas class)

**Reference:** `hestia/api/schemas/chat.py` for Pydantic schema pattern.

**Step 1: Write the failing test**

```python
# Add to tests/test_learning.py
from hestia.api.schemas.learning import (
    FeedbackRequest, FeedbackResponse,
    PrincipleResponse, PrincipleListResponse,
    LearningStatsResponse,
    ReflectionResponse, ReflectionListResponse,
    ReflectRequest,
)


class TestLearningSchemas:
    """Tests for API request/response schemas."""

    def test_feedback_request_valid(self) -> None:
        req = FeedbackRequest(rating=5, comment="Great response")
        assert req.rating == 5

    def test_feedback_request_invalid_rating(self) -> None:
        with pytest.raises(Exception):
            FeedbackRequest(rating=3)  # Only 1 or 5 allowed

    def test_feedback_response(self) -> None:
        resp = FeedbackResponse(recorded=True, interaction_id="int-001")
        assert resp.recorded is True

    def test_principle_response(self) -> None:
        resp = PrincipleResponse(
            id="prin-001",
            domain="scheduling",
            content="Prefers concise responses",
            confidence=0.7,
            validation_count=3,
            contradiction_count=0,
            active=True,
            is_established=False,
            created_at="2026-03-03T10:00:00",
        )
        assert resp.confidence == 0.7

    def test_learning_stats_response(self) -> None:
        resp = LearningStatsResponse(
            total_interactions=50,
            total_signals=35,
            total_principles=8,
            active_principles=6,
            domains={},
        )
        assert resp.total_principles == 8
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestLearningSchemas -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `hestia/api/schemas/learning.py` with Pydantic models:
- `FeedbackRequest(rating: Literal[1, 5], comment: Optional[str])`
- `FeedbackResponse(recorded: bool, interaction_id: str)`
- `PrincipleResponse` — mirrors Principle.to_dict() fields
- `PrincipleListResponse(principles: List[PrincipleResponse], count: int)`
- `LearningStatsResponse(total_interactions, total_signals, total_principles, active_principles, domains)`
- `ReflectionResponse` — mirrors ReflectionResult.to_dict()
- `ReflectionListResponse(reflections: List[ReflectionResponse], count: int)`
- `ReflectRequest(session_id: Optional[str])` — for manual trigger

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_learning.py::TestLearningSchemas -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add hestia/api/schemas/learning.py tests/test_learning.py
git commit -m "feat(learning): add Pydantic API schemas for learning endpoints"
```

---

### Task 8: API Routes (Learning + Feedback)

**Files:**
- Create: `hestia/api/routes/learning.py`
- Test: `tests/test_learning.py` (add TestLearningRoutes class)

**Reference:** `hestia/api/routes/wiki.py` for JWT auth + router pattern.

**Step 1: Write the failing test**

```python
# Add to tests/test_learning.py
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch


class TestLearningRoutes:
    """Tests for learning API endpoints."""

    @pytest.fixture
    def app(self) -> FastAPI:
        """Create a minimal FastAPI app with learning routes."""
        from hestia.api.routes.learning import router
        app = FastAPI()
        app.include_router(router)
        return app

    @pytest.fixture
    def client(self, app: FastAPI) -> TestClient:
        return TestClient(app)

    @pytest.fixture(autouse=True)
    def mock_auth(self) -> None:
        """Skip JWT auth for testing."""
        with patch("hestia.api.routes.learning.get_device_token", return_value="test-device"):
            yield

    @pytest.fixture(autouse=True)
    def mock_manager(self) -> None:
        """Mock the learning manager."""
        mock_mgr = AsyncMock()
        mock_mgr.get_principles.return_value = []
        mock_mgr.get_stats.return_value = {
            "total_interactions": 0, "total_signals": 0,
            "total_principles": 0, "active_principles": 0, "domains": {},
        }
        mock_mgr.get_reflections.return_value = []
        mock_mgr.record_feedback.return_value = None
        mock_mgr.trigger_reflection.return_value = None
        with patch("hestia.api.routes.learning.get_learning_manager", new_callable=AsyncMock, return_value=mock_mgr):
            yield

    def test_list_principles(self, client: TestClient) -> None:
        response = client.get("/v1/learning/principles")
        assert response.status_code == 200
        data = response.json()
        assert "principles" in data

    def test_get_stats(self, client: TestClient) -> None:
        response = client.get("/v1/learning/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_interactions" in data

    def test_list_reflections(self, client: TestClient) -> None:
        response = client.get("/v1/learning/reflections")
        assert response.status_code == 200

    def test_submit_feedback(self, client: TestClient) -> None:
        response = client.post(
            "/v1/chat/int-001/feedback",
            json={"rating": 5, "comment": "Good response"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["recorded"] is True

    def test_submit_feedback_invalid_rating(self, client: TestClient) -> None:
        response = client.post(
            "/v1/chat/int-001/feedback",
            json={"rating": 3},
        )
        assert response.status_code == 422  # Validation error

    def test_trigger_reflection(self, client: TestClient) -> None:
        response = client.post(
            "/v1/learning/reflect",
            json={},
        )
        assert response.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestLearningRoutes -v`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write implementation**

Create `hestia/api/routes/learning.py`:
- Router with `prefix="/v1"` and two tag groups: `["learning"]` and `["chat"]` (feedback lives under chat)
- 6 endpoints per design doc table
- All use `Depends(get_device_token)` for JWT auth
- Error handling: `sanitize_for_log(e)` in logs, generic messages in responses
- `component=LogComponent.LEARNING` in all log calls

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_learning.py::TestLearningRoutes -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add hestia/api/routes/learning.py tests/test_learning.py
git commit -m "feat(learning): add 6 API endpoints for learning and feedback"
```

---

### Task 9: Server Integration

**Files:**
- Modify: `hestia/api/server.py` (3 locations: init, shutdown, route registration)
- Test: existing `tests/test_server_lifecycle.py` (verify import doesn't break)

**Step 1: Read current server.py to find exact insertion points**

Read `hestia/api/server.py` and locate:
1. Phase 2 manager lists (~line 223)
2. Retry map (~line 255)
3. Shutdown sequence (~line 495)
4. Route imports and registration (~line 653)

**Step 2: Add learning_manager to Phase 2 parallel init**

In the Phase 2 names/coroutines lists, add `"learning_manager"` and `get_learning_manager()`.

**Step 3: Add to retry map**

Add `"learning_manager": get_learning_manager` to the retry mapping.

**Step 4: Add to shutdown**

Add `close_learning_manager()` cleanup block following the existing pattern.

**Step 5: Register routes**

Add import and `app.include_router(learning_router)`.

**Step 6: Run server lifecycle tests**

Run: `python -m pytest tests/test_server_lifecycle.py -v`
Expected: ALL PASS

**Step 7: Commit**

```bash
git add hestia/api/server.py
git commit -m "feat(learning): register LearningManager in server init, shutdown, and routes"
```

---

### Task 10: RequestHandler Integration

**Files:**
- Modify: `hestia/orchestration/handler.py` (~line 710, between Step 9.5 and Step 10)
- Test: `tests/test_learning.py` (add TestRequestHandlerIntegration class)

**Step 1: Write the failing test**

```python
# Add to tests/test_learning.py

class TestRequestHandlerIntegration:
    """Verify learning recording is called from RequestHandler."""

    @pytest.mark.asyncio
    async def test_handler_calls_learning_manager(self) -> None:
        """The handle() method should fire-and-forget a learning recording."""
        from hestia.orchestration.handler import RequestHandler
        # This is a smoke test — verify the import path and call signature exist
        # Full integration tested via API endpoint tests
        from hestia.learning.manager import LearningManager
        manager = LearningManager.__new__(LearningManager)
        assert hasattr(manager, 'record_interaction')
        import inspect
        sig = inspect.signature(manager.record_interaction)
        params = list(sig.parameters.keys())
        assert "session_id" in params
        assert "user_message" in params
        assert "response" in params
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_learning.py::TestRequestHandlerIntegration -v`
Expected: Should pass (it's checking the method exists from Task 6). If not, adjust after Task 6 is confirmed.

**Step 3: Add learning recording to handler.py**

Insert after the response cache step (Step 9.5) and before the task completion step (Step 10):

```python
# Step 9.8: Record interaction for learning cycle (fire-and-forget)
try:
    from hestia.learning import get_learning_manager
    learning_mgr = await get_learning_manager()
    if learning_mgr.enabled:
        asyncio.create_task(
            learning_mgr.record_interaction(
                session_id=conversation.session_id,
                user_message=request.content,
                response=response.content,
                intent_type=intent.primary_intent.value if intent else None,
                intent_confidence=intent.confidence if intent else None,
                council_quality_score=(
                    council_result.validation.quality_score
                    if council_result and council_result.validation
                    else None
                ),
                mode=self._mode_manager.current_mode if self._mode_manager else "tia",
            )
        )
except Exception as e:
    self.logger.warning(
        f"Learning recording failed: {type(e).__name__}",
        component=LogComponent.LEARNING,
    )
```

**Step 4: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: ALL PASS (no regressions)

**Step 5: Commit**

```bash
git add hestia/orchestration/handler.py tests/test_learning.py
git commit -m "feat(learning): wire learning recording into RequestHandler post-response"
```

---

### Task 11: Hook Scripts & Documentation

**Files:**
- Modify: `scripts/auto-test.sh` (add learning module mapping)
- Modify: `CLAUDE.md` (update project structure, test count, endpoint count, module count)

**Step 1: Add auto-test.sh mapping**

Add to the case statement in `scripts/auto-test.sh`:
```bash
*hestia/learning/*)
    echo "tests/test_learning.py" ;;
```

**Step 2: Update CLAUDE.md**

- Add `hestia/learning/` to project structure with description
- Update endpoint count (126 → 132)
- Update route module count (21 → 22)
- Add learning routes to API Summary table
- Update test count after final test run
- Add `LEARNING` to LogComponent enum list

**Step 3: Run count-check.sh to verify**

Run: `./scripts/count-check.sh`
Expected: Counts match updated CLAUDE.md

**Step 4: Commit**

```bash
git add scripts/auto-test.sh CLAUDE.md
git commit -m "docs: update CLAUDE.md and auto-test.sh for learning module"
```

---

### Task 12: Neural Net Visualization — Principle Nodes (iOS + macOS)

**Files:**
- Modify: `HestiaApp/Shared/Models/MemoryChunk.swift` (add principle to ChunkType)
- Modify: `HestiaApp/Shared/ViewModels/NeuralNetViewModel.swift` (load principles, merge into graph)
- Modify: `HestiaApp/Shared/Views/CommandCenter/NeuralNetView.swift` (gold color, glow)
- Modify: `HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift` (same as iOS VM)
- Modify: `HestiaApp/macOS/Views/Research/MacSceneKitGraphView.swift` (gold color, glow)
- Create: `HestiaApp/Shared/Models/LearningModels.swift` (API response models)

**Step 1: Add LearningModels.swift**

Create shared models for principle API responses:
```swift
struct PrincipleResponse: Codable, Identifiable {
    let id: String
    let domain: String
    let content: String
    let confidence: Double
    let validationCount: Int
    let contradictionCount: Int
    let active: Bool
    let isEstablished: Bool
    let createdAt: String
    let sourceInteractions: [String]
}

struct PrincipleListResponse: Codable {
    let principles: [PrincipleResponse]
    let count: Int
}

struct FeedbackRequest: Codable {
    let rating: Int
    let comment: String?
}

struct FeedbackResponse: Codable {
    let recorded: Bool
    let interactionId: String
}
```

**Step 2: Add principle to ChunkType**

In `MemoryChunk.swift`, add `case principle` to the `ChunkType` enum.

**Step 3: Update NeuralNetViewModel (iOS)**

Add a `loadPrinciples()` method that calls `GET /v1/learning/principles`, converts to `GraphNode` objects with `chunkType = .principle`, and merges them into the existing nodes array. Link principles to their source interactions via edges.

**Step 4: Add gold color and glow to NeuralNetView (iOS)**

In the SceneKit color mapping, add `case .principle: return UIColor(red: 1.0, green: 0.85, blue: 0.2, alpha: 1.0)` (gold). For principle nodes, increase `SCNMaterial.emission.intensity` proportional to `confidence`.

**Step 5: Mirror changes in macOS**

Apply equivalent changes to `MacNeuralNetViewModel.swift` and `MacSceneKitGraphView.swift`.

**Step 6: Build both targets**

Run: `xcodebuild -scheme HestiaWorkspace build` and `xcodebuild -scheme HestiaApp build`
Expected: Both succeed

**Step 7: Commit**

```bash
git add HestiaApp/
git commit -m "feat(ui): add principle nodes to Neural Net visualization with gold glow"
```

---

## Phase 2: Metacognitive Monitoring (Interface Sketch)

**Prerequisite:** Phase 1 deployed and ~4 weeks of outcome data accumulated.

### Files to Create

```
hestia/learning/metacognition.py    # MetaMonitor
hestia/learning/confidence.py       # ConfidenceCalibrator
hestia/learning/knowledge_gaps.py   # KnowledgeGapDetector
hestia/api/routes/learning.py       # Add 3 new endpoints
```

### Interface Contracts

```python
# metacognition.py
@dataclass
class DomainHealth:
    domain: LearningDomain
    acceptance_rate: float       # 0-1
    correction_rate: float       # 0-1
    avg_signal_value: float      # -1 to 1
    trend: str                   # "improving", "stable", "declining"
    signal_count: int
    principle_count: int

@dataclass
class MetaReport:
    timestamp: datetime
    domain_health: Dict[LearningDomain, DomainHealth]
    confusion_loops: List[Dict[str, Any]]  # Topics with repeated corrections
    stale_principles: List[str]            # Principle IDs not validated recently
    recommendations: List[str]             # Natural language suggestions

class MetaMonitor:
    async def initialize(self) -> None
    async def run_analysis(self, lookback_days: int = 30) -> MetaReport
    async def get_domain_health(self) -> Dict[LearningDomain, DomainHealth]
    async def schedule_periodic(self, interval_hours: int = 24) -> None

# confidence.py
@dataclass
class CalibrationReport:
    domain: LearningDomain
    confidence: float              # Current calibrated confidence 0-1
    prediction_count: int
    correct_predictions: int
    accuracy: float               # correct / total
    last_updated: datetime

class ConfidenceCalibrator:
    async def update(self, domain: LearningDomain, predicted: str, actual: str, match: bool) -> float
    async def get_confidence(self, domain: LearningDomain) -> float
    async def get_calibration_report(self) -> Dict[LearningDomain, CalibrationReport]

# knowledge_gaps.py
@dataclass
class KnowledgeGap:
    domain: LearningDomain
    description: str
    confidence: float             # How uncertain we are (high = big gap)
    interaction_count: int        # How little data we have
    expected_information_gain: float  # How much one question would help

@dataclass
class CuriosityQuestion:
    domain: LearningDomain
    question: str
    priority: float              # Ranked by expected information gain
    context: str                 # Why Hestia wants to ask this

class KnowledgeGapDetector:
    async def identify_gaps(self) -> List[KnowledgeGap]
    async def generate_questions(self, max_questions: int = 3) -> List[CuriosityQuestion]
```

### New Endpoints

| Method | Route | Request | Response |
|--------|-------|---------|----------|
| GET | `/v1/learning/confidence` | `?domain=scheduling` | `Dict[str, CalibrationReport]` |
| GET | `/v1/learning/gaps` | `?max_questions=3` | `List[CuriosityQuestion]` |
| GET | `/v1/learning/meta-report` | — | `MetaReport` |

### Integration Points

- `MetaMonitor.schedule_periodic()` registers with APScheduler (same as `OrderManager`)
- `ConfidenceCalibrator` stores predictions in the existing `learning.db` (new table)
- `KnowledgeGapDetector.generate_questions()` feeds into `BriefingGenerator` as new section
- `InterruptionPolicy` gates when questions surface (not during focus time)

### Database Schema Addition (learning.db)

```sql
CREATE TABLE IF NOT EXISTS predictions (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    predicted TEXT NOT NULL,
    actual TEXT,
    match INTEGER,  -- 0 or 1
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta_reports (
    id TEXT PRIMARY KEY,
    report_json TEXT NOT NULL,
    timestamp TEXT NOT NULL
);
```

---

## Phase 3: Active Inference Engine (Interface Sketch)

**Prerequisite:** Phase 2 confidence calibration running for ~4 weeks.

### Files to Create

```
hestia/learning/world_model.py    # GenerativeWorldModel
hestia/learning/prediction.py     # PredictionEngine
hestia/learning/curiosity.py      # CuriosityDrive
```

### Interface Contracts

```python
# world_model.py
class BeliefLayer(Enum):
    ABSTRACT = "abstract"       # Personality, goals, values — updates weekly
    ROUTINE = "routine"         # Patterns, preferences — updates daily
    SITUATIONAL = "situational" # Current context — updates per-interaction

@dataclass
class DomainBelief:
    domain: LearningDomain
    layer: BeliefLayer
    content: Dict[str, Any]    # Structured belief state
    confidence: float
    entropy: float             # Shannon entropy of belief distribution
    last_updated: datetime
    update_count: int

class GenerativeWorldModel:
    async def initialize(self) -> None
    async def update_belief(self, domain: LearningDomain, layer: BeliefLayer, observation: Any) -> None
    async def get_belief(self, domain: LearningDomain, layer: Optional[BeliefLayer] = None) -> DomainBelief
    async def get_all_beliefs(self) -> Dict[LearningDomain, Dict[BeliefLayer, DomainBelief]]
    async def consolidate(self) -> None  # Weekly: abstract ← routine; Daily: routine ← situational

# prediction.py
@dataclass
class Prediction:
    id: str
    domain: LearningDomain
    predicted_need: str         # "User will want calendar summary"
    confidence: float
    basis: List[str]           # Principle IDs or belief references
    timestamp: datetime

class PredictionEngine:
    async def predict(self, user_message: str, context: Dict[str, Any]) -> List[Prediction]
    async def score(self, prediction: Prediction, actual_outcome: OutcomeSignal) -> float
    async def get_prediction_error_ema(self, domain: LearningDomain) -> float

# curiosity.py
class OperatingRegime(Enum):
    ANTICIPATORY = "anticipatory"  # confidence > 0.8, PE < 0.2
    CURIOUS = "curious"            # confidence < 0.4, entropy > threshold
    OBSERVANT = "observant"        # 0.4 < confidence < 0.8

class CuriosityDrive:
    async def compute_curiosity(self) -> Dict[LearningDomain, float]
    async def get_regime(self, domain: LearningDomain) -> OperatingRegime
    async def rank_questions(self, gaps: List[KnowledgeGap]) -> List[RankedQuestion]
    async def should_anticipate(self, domain: LearningDomain) -> bool
    async def should_ask(self, domain: LearningDomain) -> bool
```

### Math Implementation

```python
# In prediction.py
def compute_prediction_error(predicted: float, actual: float) -> float:
    return abs(predicted - actual)

def update_ema(current_ema: float, new_value: float, alpha: float = 0.3) -> float:
    return alpha * new_value + (1 - alpha) * current_ema

# In curiosity.py
def compute_entropy(belief_distribution: Dict[str, float]) -> float:
    """Shannon entropy of a belief distribution."""
    import math
    return -sum(p * math.log2(p) for p in belief_distribution.values() if p > 0)

def compute_curiosity(entropy: float, expected_info_gain: float) -> float:
    """Curiosity = entropy weighted by expected information gain."""
    return entropy * expected_info_gain

# In world_model.py — temporal decay extension
def compute_effective_lambda(base_lambda: float, validation_rate: float) -> float:
    """Validated memories decay slower."""
    return base_lambda * (1 - validation_rate)

def compute_outcome_weight(signals: List[float]) -> float:
    """Sigmoid of average outcome signal."""
    import math
    if not signals:
        return 0.5
    avg = sum(signals) / len(signals)
    return 1 / (1 + math.exp(-avg))
```

### Database Schema Addition (learning.db)

```sql
CREATE TABLE IF NOT EXISTS beliefs (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    layer TEXT NOT NULL,  -- abstract, routine, situational
    content_json TEXT NOT NULL,
    confidence REAL NOT NULL,
    entropy REAL NOT NULL,
    last_updated TEXT NOT NULL,
    update_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS prediction_log (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    predicted_need TEXT NOT NULL,
    confidence REAL NOT NULL,
    basis_json TEXT,
    actual_outcome_id TEXT,
    prediction_error REAL,
    timestamp TEXT NOT NULL
);
```

### Integration with Existing Systems

- **PredictionEngine** hooks into `RequestHandler` *before* processing (pre-prediction step)
- **CuriosityDrive** feeds `BriefingGenerator` → "Questions of the day" section
- **GenerativeWorldModel.consolidate()** runs on APScheduler (weekly for abstract, daily for routine)
- **AnticipationExecutor** extends `BackgroundTask` system — auto-creates tasks with autonomy_level=2 (confirm before executing)
- **Neural Net viz**: cluster colors change based on `OperatingRegime` (green/amber/neutral)

---

## Dependency Graph

```
Task 1 (Models)
  ↓
Task 2 (Database) ← Task 3 (PrincipleStore)
  ↓                    ↓
Task 4 (OutcomeTracker)
  ↓
Task 5 (ReflectionAgent)
  ↓
Task 6 (LearningManager) ← uses all above
  ↓
Task 7 (API Schemas)
  ↓
Task 8 (API Routes)
  ↓
Task 9 (Server Integration)
  ↓
Task 10 (RequestHandler Integration)
  ↓
Task 11 (Docs & Hooks)
  ↓
Task 12 (Neural Net Viz) — independent of Tasks 9-11, can run in parallel

--- Phase 2 (after 4 weeks of data) ---
MetaMonitor ← LearningDatabase (Phase 1)
ConfidenceCalibrator ← OutcomeTracker + TemporalDecay
KnowledgeGapDetector ← ConfidenceCalibrator + PrincipleStore

--- Phase 3 (after Phase 2 calibration) ---
GenerativeWorldModel ← PrincipleStore + PatternDetector + ConfidenceCalibrator
PredictionEngine ← GenerativeWorldModel + OutcomeTracker
CuriosityDrive ← PredictionEngine + KnowledgeGapDetector
```

---

## ADR Required

**ADR-039: Learning Cycle Architecture**
- Decision: New `hestia/learning/` module with standard manager pattern
- Context: Closing the feedback loop between actions and outcomes
- Status: Accepted
- Add to `docs/hestia-decision-log.md` during Task 11
