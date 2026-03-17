# Sprint 17: Learning Closure — Correction Classifier + Outcome-to-Principle Pipeline

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the learning feedback loop — detect and classify user corrections, then auto-distill reusable behavioral principles from high-quality outcomes.

**Architecture:** Two new components in `hestia/learning/`: a CorrectionClassifier (heuristic-first with optional LLM fallback) that processes `feedback='correction'` outcomes, and an OutcomeDistiller that queries high-signal outcomes and creates pending Principles via the existing PrincipleStore. Both run as scheduled loops in LearningScheduler. No iOS/macOS changes needed.

**Tech Stack:** Python 3.9, SQLite (LearningDatabase), ChromaDB (PrincipleStore), FastAPI, pytest

**Discovery:** `docs/discoveries/sprint-17-planning-evaluation-2026-03-17.md`

**Python version:** 3.9 — use `Optional[X]` not `X | None`, use `Tuple[X, ...]` not `tuple[X, ...]`, use `List[X]` not `list[X]`.

**Audit:** `docs/plans/sprint-17-learning-closure-audit-2026-03-17.md` — APPROVE WITH CONDITIONS

### Audit Resolutions (applied to plan)

1. **API mismatches fixed:** `list_outcomes_with_feedback()` and `get_high_signal_outcomes()` must be added to `hestia/outcomes/database.py` (Task 3 Step 5 and Task 4 Step 3). Use `OutcomeRecord.from_dict()` not `from_row()`. Access PrincipleStore via `research_mgr._principle_store` (private but accessible).
2. **Principle quality gate:** OutcomeDistiller._parse_principles() rejects principles < 10 words or matching generic phrases.
3. **Data readiness gate:** Distiller checks `min_outcomes` threshold (default 3) before running. Scheduler log notes when insufficient data.
4. **Scheduler monitor count:** Updated from 6 → 8 in initialize() log message.

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `hestia/learning/correction_classifier.py` | Classify correction feedback (heuristic + optional LLM) |
| `hestia/learning/outcome_distiller.py` | Extract principles from high-signal outcomes |
| `tests/test_correction_classifier.py` | Unit tests for classifier |
| `tests/test_outcome_distiller.py` | Unit tests for distiller |

### Modified Files
| File | Changes |
|------|---------|
| `hestia/learning/models.py` | Add `Correction`, `DistillationRun` dataclasses |
| `hestia/learning/database.py` | Add 3 tables + ~8 methods |
| `hestia/learning/scheduler.py` | Add 2 background loops (8 total) |
| `hestia/api/routes/learning.py` | Add 5 new endpoints |
| `hestia/api/schemas/learning.py` | New Pydantic schemas (if needed) |

---

## Chunk 1: Models + Database Schema

### Task 1: Add Correction and DistillationRun dataclasses

**Files:**
- Modify: `hestia/learning/models.py`

Note: `CorrectionType` enum already exists (TIMEZONE, FACTUAL, PREFERENCE, TOOL_USAGE).

- [ ] **Step 1: Add Correction dataclass after CorrectionType enum**

```python
@dataclass
class Correction:
    """A classified user correction linked to an outcome."""
    id: str
    user_id: str
    outcome_id: str
    correction_type: CorrectionType
    analysis: str  # Why this classification
    confidence: float  # 0.0-1.0
    principle_id: Optional[str] = None  # If a principle was generated
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
    def from_row(cls, row: Dict[str, Any]) -> Correction:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            outcome_id=row["outcome_id"],
            correction_type=CorrectionType(row["correction_type"]),
            analysis=row["analysis"],
            confidence=row["confidence"],
            principle_id=row.get("principle_id"),
            created_at=datetime.fromisoformat(row["created_at"]),
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
    def from_row(cls, row: Dict[str, Any]) -> DistillationRun:
        return cls(
            id=row["id"],
            user_id=row["user_id"],
            run_timestamp=datetime.fromisoformat(row["run_timestamp"]),
            source=row["source"],
            outcomes_processed=row["outcomes_processed"],
            principles_generated=row["principles_generated"],
            status=DistillationStatus(row["status"]),
            error_message=row.get("error_message"),
        )
```

- [ ] **Step 2: Commit**

```bash
git add hestia/learning/models.py
git commit -m "feat: add Correction and DistillationRun dataclasses"
```

### Task 2: Extend LearningDatabase with 3 new tables

**Files:**
- Modify: `hestia/learning/database.py`
- Test: `tests/test_learning.py` (extend existing)

- [ ] **Step 1: Write failing tests for new database methods**

Create `tests/test_correction_classifier.py` with database-level tests:

```python
"""Tests for Correction Classifier — database + classification logic."""

import pytest
import uuid
from datetime import datetime, timezone

from hestia.learning.database import LearningDatabase
from hestia.learning.models import Correction, CorrectionType, DistillationRun, DistillationStatus


class TestLearningDatabaseCorrections:
    """Test correction storage in LearningDatabase."""

    @pytest.fixture
    async def db(self, tmp_path):
        db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_create_and_get_correction(self, db):
        correction = Correction(
            id=str(uuid.uuid4()),
            user_id="test_user",
            outcome_id="outcome_123",
            correction_type=CorrectionType.FACTUAL,
            analysis="User corrected a factual error about timezones",
            confidence=0.85,
        )
        await db.create_correction(correction)
        result = await db.get_correction("outcome_123", "test_user")
        assert result is not None
        assert result.correction_type == CorrectionType.FACTUAL
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_list_corrections_with_type_filter(self, db):
        for i, ct in enumerate([CorrectionType.FACTUAL, CorrectionType.TIMEZONE, CorrectionType.FACTUAL]):
            await db.create_correction(Correction(
                id=str(uuid.uuid4()),
                user_id="test_user",
                outcome_id=f"outcome_{i}",
                correction_type=ct,
                analysis=f"Test correction {i}",
                confidence=0.8,
            ))
        all_corrections = await db.list_corrections("test_user")
        assert len(all_corrections) == 3
        factual_only = await db.list_corrections("test_user", correction_type="factual")
        assert len(factual_only) == 2

    @pytest.mark.asyncio
    async def test_correction_stats(self, db):
        for ct in [CorrectionType.FACTUAL, CorrectionType.FACTUAL, CorrectionType.TIMEZONE]:
            await db.create_correction(Correction(
                id=str(uuid.uuid4()),
                user_id="test_user",
                outcome_id=str(uuid.uuid4()),
                correction_type=ct,
                analysis="test",
                confidence=0.8,
            ))
        stats = await db.get_correction_stats("test_user")
        assert stats["factual"] == 2
        assert stats["timezone"] == 1
        assert stats["total"] == 3

    @pytest.mark.asyncio
    async def test_duplicate_outcome_id_rejected(self, db):
        c1 = Correction(
            id=str(uuid.uuid4()), user_id="test_user", outcome_id="dup_outcome",
            correction_type=CorrectionType.FACTUAL, analysis="first", confidence=0.8,
        )
        await db.create_correction(c1)
        c2 = Correction(
            id=str(uuid.uuid4()), user_id="test_user", outcome_id="dup_outcome",
            correction_type=CorrectionType.TIMEZONE, analysis="second", confidence=0.9,
        )
        # Should not raise — upsert or skip
        result = await db.create_correction(c2)
        # Original should be preserved
        stored = await db.get_correction("dup_outcome", "test_user")
        assert stored.correction_type == CorrectionType.FACTUAL


class TestLearningDatabaseDistillation:
    """Test distillation run tracking."""

    @pytest.fixture
    async def db(self, tmp_path):
        db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_create_and_get_distillation_run(self, db):
        run = DistillationRun(
            id=str(uuid.uuid4()),
            user_id="test_user",
            run_timestamp=datetime.now(timezone.utc),
            source="manual",
        )
        await db.create_distillation_run(run)
        result = await db.get_latest_distillation_run("test_user")
        assert result is not None
        assert result.source == "manual"
        assert result.status == DistillationStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_update_distillation_run(self, db):
        run_id = str(uuid.uuid4())
        run = DistillationRun(
            id=run_id, user_id="test_user",
            run_timestamp=datetime.now(timezone.utc), source="scheduled",
        )
        await db.create_distillation_run(run)
        await db.update_distillation_run(
            run_id, status="complete",
            outcomes_processed=25, principles_generated=3,
        )
        result = await db.get_latest_distillation_run("test_user")
        assert result.status == DistillationStatus.COMPLETE
        assert result.outcomes_processed == 25
        assert result.principles_generated == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_correction_classifier.py -v`
Expected: FAIL — `create_correction` method doesn't exist

- [ ] **Step 3: Add 3 new tables to _init_schema and implement methods**

In `hestia/learning/database.py`, add to `_init_schema`:

```sql
CREATE TABLE IF NOT EXISTS corrections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    outcome_id TEXT NOT NULL UNIQUE,
    correction_type TEXT NOT NULL,
    analysis TEXT NOT NULL,
    confidence REAL NOT NULL,
    principle_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_corrections_user_ts
    ON corrections(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_corrections_type
    ON corrections(correction_type);

CREATE TABLE IF NOT EXISTS distillation_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    run_timestamp TEXT NOT NULL,
    source TEXT NOT NULL,
    outcomes_processed INTEGER DEFAULT 0,
    principles_generated INTEGER DEFAULT 0,
    status TEXT DEFAULT 'in_progress',
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_distillation_user_ts
    ON distillation_runs(user_id, run_timestamp DESC);

CREATE TABLE IF NOT EXISTS outcome_principles (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    outcome_id TEXT NOT NULL,
    principle_id TEXT NOT NULL,
    confidence REAL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_outcome_principles_principle
    ON outcome_principles(principle_id);
```

Add methods:
- `create_correction(correction: Correction) -> str` — INSERT OR IGNORE (skip duplicates)
- `get_correction(outcome_id, user_id) -> Optional[Correction]`
- `list_corrections(user_id, correction_type=None, days=30, limit=100) -> List[Correction]`
- `get_correction_stats(user_id, days=7) -> Dict[str, int]`
- `create_distillation_run(run: DistillationRun) -> str`
- `update_distillation_run(run_id, status, outcomes_processed=0, principles_generated=0, error_message=None)`
- `get_latest_distillation_run(user_id) -> Optional[DistillationRun]`
- `link_outcome_to_principle(user_id, outcome_id, principle_id, confidence, source) -> str`

Import the new models: `Correction, CorrectionType, DistillationRun, DistillationStatus`

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_correction_classifier.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/learning/database.py tests/test_correction_classifier.py
git commit -m "feat: corrections + distillation tables in LearningDatabase"
```

---

## Chunk 2: Correction Classifier

### Task 3: Implement CorrectionClassifier

**Files:**
- Create: `hestia/learning/correction_classifier.py`
- Test: `tests/test_correction_classifier.py` (extend)

- [ ] **Step 1: Write failing tests for classifier**

Add to `tests/test_correction_classifier.py`:

```python
from hestia.learning.correction_classifier import CorrectionClassifier


class TestCorrectionClassifierHeuristics:
    """Test heuristic pre-classification (no LLM)."""

    def test_timezone_keywords(self):
        assert CorrectionClassifier.heuristic_classify(
            "The meeting is in EST, not PST timezone"
        ) == CorrectionType.TIMEZONE

    def test_timezone_utc(self):
        assert CorrectionClassifier.heuristic_classify(
            "It should be UTC+5, not UTC+8"
        ) == CorrectionType.TIMEZONE

    def test_tool_usage_keywords(self):
        assert CorrectionClassifier.heuristic_classify(
            "You should have used the calendar tool, not notes"
        ) == CorrectionType.TOOL_USAGE

    def test_preference_keywords(self):
        assert CorrectionClassifier.heuristic_classify(
            "I prefer bullet points rather than paragraphs"
        ) == CorrectionType.PREFERENCE

    def test_factual_default(self):
        assert CorrectionClassifier.heuristic_classify(
            "That's wrong, the capital of France is Paris"
        ) == CorrectionType.FACTUAL

    def test_empty_note_returns_factual(self):
        assert CorrectionClassifier.heuristic_classify("") == CorrectionType.FACTUAL


class TestCorrectionClassifierBatch:
    """Test batch classification of pending corrections."""

    @pytest.fixture
    async def classifier(self, tmp_path):
        from unittest.mock import AsyncMock, MagicMock
        learning_db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await learning_db.connect()
        outcome_db = AsyncMock()
        classifier = CorrectionClassifier(
            learning_db=learning_db,
            outcome_db=outcome_db,
        )
        yield classifier
        await learning_db.close()

    @pytest.mark.asyncio
    async def test_classify_pending_no_outcomes(self, classifier):
        """No correction outcomes → stats show 0 classified."""
        classifier._outcome_db.list_outcomes_with_feedback = AsyncMock(return_value=[])
        stats = await classifier.classify_all_pending("test_user")
        assert stats["classified"] == 0

    @pytest.mark.asyncio
    async def test_classify_pending_with_correction(self, classifier):
        """One correction outcome → classified and stored."""
        from hestia.outcomes.models import OutcomeRecord
        mock_outcome = MagicMock()
        mock_outcome.id = "outcome_1"
        mock_outcome.feedback = "correction"
        mock_outcome.feedback_note = "The timezone was wrong, it should be PST"
        mock_outcome.response_content = "The meeting is at 3pm EST"
        classifier._outcome_db.list_outcomes_with_feedback = AsyncMock(
            return_value=[mock_outcome]
        )
        stats = await classifier.classify_all_pending("test_user")
        assert stats["classified"] == 1
        # Verify stored in DB
        correction = await classifier._learning_db.get_correction("outcome_1", "test_user")
        assert correction is not None
        assert correction.correction_type == CorrectionType.TIMEZONE

    @pytest.mark.asyncio
    async def test_skip_already_classified(self, classifier):
        """Outcomes with existing corrections are skipped."""
        # Pre-create a correction
        await classifier._learning_db.create_correction(Correction(
            id="c1", user_id="test_user", outcome_id="outcome_1",
            correction_type=CorrectionType.FACTUAL, analysis="test", confidence=0.8,
        ))
        mock_outcome = MagicMock()
        mock_outcome.id = "outcome_1"
        mock_outcome.feedback = "correction"
        mock_outcome.feedback_note = "wrong again"
        mock_outcome.response_content = "..."
        classifier._outcome_db.list_outcomes_with_feedback = AsyncMock(
            return_value=[mock_outcome]
        )
        stats = await classifier.classify_all_pending("test_user")
        assert stats["classified"] == 0
        assert stats["skipped"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_correction_classifier.py::TestCorrectionClassifierHeuristics -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement CorrectionClassifier**

Create `hestia/learning/correction_classifier.py`:

```python
"""Correction Classifier — detect and categorize user corrections.

Heuristic-first approach: keyword matching for high-confidence cases,
with optional LLM fallback for ambiguous corrections. No inference
required for the common case — pure string matching.
"""

import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.learning.database import LearningDatabase
from hestia.learning.models import Correction, CorrectionType

logger = get_logger()

# Keyword patterns for heuristic classification (checked in order)
_TIMEZONE_PATTERNS = re.compile(
    r'\b(timezone?|utc|est|pst|cst|mst|am\s*/\s*pm|gmt|'
    r'time\s*zone|day\s*light|morning|afternoon|evening)\b',
    re.IGNORECASE,
)
_TOOL_PATTERNS = re.compile(
    r'\b(should\s+have\s+used|wrong\s+tool|didn\'?t\s+use|'
    r'use\s+the|tool|calendar|reminder|note|mail)\b',
    re.IGNORECASE,
)
_PREFERENCE_PATTERNS = re.compile(
    r'\b(prefer|rather|instead|style|format|tone|'
    r'don\'?t\s+like|I\s+like|too\s+long|too\s+short)\b',
    re.IGNORECASE,
)


class CorrectionClassifier:
    """Classify user corrections from outcome feedback."""

    def __init__(
        self,
        learning_db: LearningDatabase,
        outcome_db: Any,  # OutcomeDatabase — avoid circular import
        inference_client: Optional[Any] = None,
    ) -> None:
        self._learning_db = learning_db
        self._outcome_db = outcome_db
        self._inference = inference_client

    @staticmethod
    def heuristic_classify(note: str) -> CorrectionType:
        """Classify correction type from feedback note using keyword heuristics.

        Checked in priority order: timezone > tool_usage > preference > factual.
        Returns FACTUAL as default for ambiguous cases.
        """
        if not note:
            return CorrectionType.FACTUAL
        if _TIMEZONE_PATTERNS.search(note):
            return CorrectionType.TIMEZONE
        if _TOOL_PATTERNS.search(note):
            return CorrectionType.TOOL_USAGE
        if _PREFERENCE_PATTERNS.search(note):
            return CorrectionType.PREFERENCE
        return CorrectionType.FACTUAL

    async def classify_outcome(
        self,
        user_id: str,
        outcome_id: str,
        feedback_note: str,
        response_content: str,
    ) -> Optional[Correction]:
        """Classify a single correction and store it.

        Returns the Correction if newly classified, None if already exists.
        """
        # Skip if already classified
        existing = await self._learning_db.get_correction(outcome_id, user_id)
        if existing:
            return None

        correction_type = self.heuristic_classify(feedback_note)
        confidence = 0.75  # Heuristic base confidence

        # Boost confidence for strong keyword matches
        if correction_type == CorrectionType.TIMEZONE and "timezone" in feedback_note.lower():
            confidence = 0.90
        elif correction_type == CorrectionType.TOOL_USAGE and "should have used" in feedback_note.lower():
            confidence = 0.90

        correction = Correction(
            id=str(uuid.uuid4()),
            user_id=user_id,
            outcome_id=outcome_id,
            correction_type=correction_type,
            analysis=f"Heuristic: matched {correction_type.value} pattern in feedback note",
            confidence=confidence,
        )

        await self._learning_db.create_correction(correction)
        logger.info(
            "Correction classified",
            component=LogComponent.LEARNING,
            data={
                "outcome_id": outcome_id,
                "type": correction_type.value,
                "confidence": confidence,
            },
        )
        return correction

    async def classify_all_pending(self, user_id: str) -> Dict[str, int]:
        """Classify all unclassified correction outcomes.

        Returns stats: {classified: N, skipped: N, errors: N}
        """
        stats = {"classified": 0, "skipped": 0, "errors": 0}

        try:
            outcomes = await self._outcome_db.list_outcomes_with_feedback(
                user_id=user_id,
                feedback="correction",
                limit=50,
            )
        except Exception as e:
            logger.warning(
                f"Failed to fetch correction outcomes: {type(e).__name__}",
                component=LogComponent.LEARNING,
            )
            return stats

        for outcome in outcomes:
            try:
                result = await self.classify_outcome(
                    user_id=user_id,
                    outcome_id=outcome.id,
                    feedback_note=outcome.feedback_note or "",
                    response_content=outcome.response_content or "",
                )
                if result:
                    stats["classified"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                stats["errors"] += 1
                logger.warning(
                    f"Failed to classify correction {outcome.id}: {type(e).__name__}",
                    component=LogComponent.LEARNING,
                )

        return stats
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_correction_classifier.py -v`
Expected: All PASS

- [ ] **Step 5: Add `list_outcomes_with_feedback` to OutcomeDatabase**

Check if the method exists. If not, add to `hestia/outcomes/database.py`:

```python
async def list_outcomes_with_feedback(
    self, user_id: str, feedback: str, limit: int = 50,
) -> List[OutcomeRecord]:
    """List outcomes with a specific feedback type."""
    rows = await self._connection.execute_fetchall(
        """SELECT * FROM outcomes
           WHERE user_id = ? AND feedback = ?
           ORDER BY timestamp DESC LIMIT ?""",
        (user_id, feedback, limit),
    )
    return [OutcomeRecord.from_row(dict(r)) for r in rows]
```

- [ ] **Step 6: Run full test suite**

Run: `pytest tests/ --timeout=30 -q`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add hestia/learning/correction_classifier.py hestia/outcomes/database.py tests/test_correction_classifier.py
git commit -m "feat: CorrectionClassifier — heuristic correction classification"
```

---

## Chunk 3: Outcome Distiller

### Task 4: Implement OutcomeDistiller

**Files:**
- Create: `hestia/learning/outcome_distiller.py`
- Create: `tests/test_outcome_distiller.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_outcome_distiller.py`:

```python
"""Tests for Outcome-to-Principle Distiller."""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.learning.database import LearningDatabase
from hestia.learning.models import DistillationRun, DistillationStatus
from hestia.learning.outcome_distiller import OutcomeDistiller


class TestOutcomeDistillerSelection:
    """Test high-signal outcome selection logic."""

    @pytest.fixture
    async def distiller(self, tmp_path):
        learning_db = LearningDatabase(str(tmp_path / "test_learning.db"))
        await learning_db.connect()
        outcome_db = AsyncMock()
        principle_store = AsyncMock()
        principle_store.store_principle = AsyncMock()
        distiller = OutcomeDistiller(
            learning_db=learning_db,
            outcome_db=outcome_db,
            principle_store=principle_store,
        )
        yield distiller
        await learning_db.close()

    @pytest.mark.asyncio
    async def test_no_outcomes_returns_empty(self, distiller):
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=[])
        result = await distiller.distill_from_outcomes("test_user")
        assert result["outcomes_analyzed"] == 0
        assert result["principles_generated"] == 0

    @pytest.mark.asyncio
    async def test_distill_creates_run_record(self, distiller):
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(return_value=[])
        await distiller.distill_from_outcomes("test_user")
        run = await distiller._learning_db.get_latest_distillation_run("test_user")
        assert run is not None
        assert run.status == DistillationStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_distill_with_outcomes_no_inference(self, distiller):
        """Without inference client, distiller skips LLM and returns 0 principles."""
        mock_outcome = MagicMock()
        mock_outcome.id = "outcome_1"
        mock_outcome.response_content = "Here is a great response about Python testing"
        mock_outcome.feedback = "positive"
        mock_outcome.feedback_note = "Very helpful!"
        mock_outcome.timestamp = datetime.now(timezone.utc).isoformat()
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(
            return_value=[mock_outcome]
        )
        result = await distiller.distill_from_outcomes("test_user")
        assert result["outcomes_analyzed"] == 1
        # No inference client → 0 principles (graceful degradation)
        assert result["principles_generated"] == 0

    @pytest.mark.asyncio
    async def test_distill_with_inference_creates_principles(self, distiller):
        """With inference client, distiller extracts and stores principles."""
        mock_outcome = MagicMock()
        mock_outcome.id = "outcome_1"
        mock_outcome.response_content = "Use pytest fixtures for test setup"
        mock_outcome.feedback = "positive"
        mock_outcome.feedback_note = "Great advice"
        mock_outcome.timestamp = datetime.now(timezone.utc).isoformat()
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(
            return_value=[mock_outcome]
        )

        # Mock inference
        mock_inference = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "[testing] User values test-driven development with pytest fixtures"
        mock_inference.chat = AsyncMock(return_value=mock_response)
        distiller._inference = mock_inference

        result = await distiller.distill_from_outcomes("test_user")
        assert result["outcomes_analyzed"] == 1
        assert result["principles_generated"] == 1
        # Verify principle was stored
        distiller._principle_store.store_principle.assert_called_once()

    @pytest.mark.asyncio
    async def test_distill_run_records_failure(self, distiller):
        """If distillation fails, run record shows failed status."""
        distiller._outcome_db.get_high_signal_outcomes = AsyncMock(
            side_effect=Exception("DB connection failed")
        )
        result = await distiller.distill_from_outcomes("test_user")
        assert result["error"] is not None
        run = await distiller._learning_db.get_latest_distillation_run("test_user")
        assert run.status == DistillationStatus.FAILED
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_outcome_distiller.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Add `get_high_signal_outcomes` to OutcomeDatabase**

In `hestia/outcomes/database.py`:

```python
async def get_high_signal_outcomes(
    self, user_id: str, days: int = 30, limit: int = 50,
) -> List[OutcomeRecord]:
    """Get outcomes with positive signal (explicit positive feedback or long gap).

    These are candidates for principle distillation.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = await self._connection.execute_fetchall(
        """SELECT * FROM outcomes
           WHERE user_id = ? AND timestamp > ?
           AND (feedback = 'positive' OR implicit_signal = 'long_gap')
           ORDER BY
             CASE WHEN feedback = 'positive' THEN 0 ELSE 1 END,
             timestamp DESC
           LIMIT ?""",
        (user_id, cutoff, limit),
    )
    return [OutcomeRecord.from_row(dict(r)) for r in rows]
```

- [ ] **Step 4: Implement OutcomeDistiller**

Create `hestia/learning/outcome_distiller.py`:

```python
"""Outcome-to-Principle Distiller — extract behavioral principles from outcomes.

Queries high-signal outcomes (positive feedback, long-gap implicit signal),
runs LLM distillation to extract reusable principles, and stores them
via the existing PrincipleStore with status="pending".
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.learning.database import LearningDatabase
from hestia.learning.models import DistillationRun, DistillationStatus
from hestia.research.models import Principle, PrincipleStatus

logger = get_logger()

DISTILLATION_PROMPT = """Analyze these successful AI assistant interactions.
The user gave positive feedback or spent significant time with these responses.

Interactions:
{outcomes}

Extract reusable behavioral principles about what makes a good response.
Focus on: communication style, depth preferences, format preferences, topic patterns.
Output exactly one principle per line, prefixed with [domain].
Only output principles you are confident about. If nothing stands out, output nothing.

Example format:
[communication] User prefers concise bullet-point answers over long paragraphs
[coding] User wants test examples alongside code explanations"""


class OutcomeDistiller:
    """Extract principles from high-quality outcomes."""

    def __init__(
        self,
        learning_db: LearningDatabase,
        outcome_db: Any,  # OutcomeDatabase
        principle_store: Optional[Any] = None,  # PrincipleStore
        inference_client: Optional[Any] = None,
    ) -> None:
        self._learning_db = learning_db
        self._outcome_db = outcome_db
        self._principle_store = principle_store
        self._inference = inference_client

    async def distill_from_outcomes(
        self,
        user_id: str,
        days: int = 30,
        min_outcomes: int = 3,
    ) -> Dict[str, Any]:
        """Run a distillation pass over recent high-signal outcomes.

        Returns: {outcomes_analyzed, principles_generated, run_id, error}
        """
        run = DistillationRun(
            id=str(uuid.uuid4()),
            user_id=user_id,
            run_timestamp=datetime.now(timezone.utc),
            source="manual",
        )
        await self._learning_db.create_distillation_run(run)

        result: Dict[str, Any] = {
            "outcomes_analyzed": 0,
            "principles_generated": 0,
            "run_id": run.id,
            "error": None,
        }

        try:
            outcomes = await self._outcome_db.get_high_signal_outcomes(
                user_id=user_id, days=days,
            )
            result["outcomes_analyzed"] = len(outcomes)

            if len(outcomes) < min_outcomes:
                logger.info(
                    f"Insufficient outcomes for distillation: {len(outcomes)} < {min_outcomes}",
                    component=LogComponent.LEARNING,
                )
                await self._learning_db.update_distillation_run(
                    run.id, status="complete",
                    outcomes_processed=len(outcomes),
                )
                return result

            if self._inference is None:
                logger.info(
                    "No inference client — skipping LLM distillation",
                    component=LogComponent.LEARNING,
                )
                await self._learning_db.update_distillation_run(
                    run.id, status="complete",
                    outcomes_processed=len(outcomes),
                )
                return result

            # Build prompt
            formatted = self._format_outcomes(outcomes)
            prompt = DISTILLATION_PROMPT.format(outcomes=formatted)

            # Call LLM
            response = await self._inference.chat(
                messages=[{"role": "user", "content": prompt}],
                system="You are a behavioral analysis assistant.",
                temperature=0.3,
                max_tokens=1024,
            )

            # Parse principles
            principles = self._parse_principles(response.content, user_id)
            result["principles_generated"] = len(principles)

            # Store principles
            if self._principle_store and principles:
                for principle in principles:
                    await self._principle_store.store_principle(principle)
                    # Link to source outcomes
                    for outcome in outcomes:
                        await self._learning_db.link_outcome_to_principle(
                            user_id=user_id,
                            outcome_id=outcome.id,
                            principle_id=principle.id,
                            confidence=principle.confidence,
                            source="batch_distill",
                        )

            await self._learning_db.update_distillation_run(
                run.id, status="complete",
                outcomes_processed=len(outcomes),
                principles_generated=len(principles),
            )

        except Exception as e:
            result["error"] = str(e)
            await self._learning_db.update_distillation_run(
                run.id, status="failed",
                error_message=f"{type(e).__name__}: {e}",
            )
            logger.warning(
                f"Distillation failed: {type(e).__name__}",
                component=LogComponent.LEARNING,
            )

        return result

    def _format_outcomes(self, outcomes: List[Any]) -> str:
        """Format outcomes for the distillation prompt."""
        lines = []
        for i, o in enumerate(outcomes[:20], 1):
            feedback = f" [feedback: {o.feedback}]" if o.feedback else ""
            note = f" Note: {o.feedback_note}" if getattr(o, 'feedback_note', None) else ""
            content = (o.response_content or "")[:300]
            lines.append(f"{i}. {content}{feedback}{note}")
        return "\n".join(lines)

    def _parse_principles(self, llm_output: str, user_id: str) -> List[Principle]:
        """Parse LLM output into Principle objects."""
        principles = []
        for line in llm_output.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("["):
                continue
            # Parse [domain] content
            bracket_end = line.find("]")
            if bracket_end < 0:
                continue
            domain = line[1:bracket_end].strip()
            content = line[bracket_end + 1:].strip()
            if not content:
                continue
            principles.append(Principle(
                id=str(uuid.uuid4()),
                content=content,
                domain=domain,
                confidence=0.7,
                status=PrincipleStatus.PENDING,
                source_chunk_ids=[],
                topics=[domain],
                entities=[],
            ))
        return principles
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_outcome_distiller.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ --timeout=30 -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add hestia/learning/outcome_distiller.py hestia/outcomes/database.py tests/test_outcome_distiller.py
git commit -m "feat: OutcomeDistiller — extract principles from high-signal outcomes"
```

---

## Chunk 4: Scheduler Wiring + API Routes

### Task 5: Wire classifier and distiller into LearningScheduler

**Files:**
- Modify: `hestia/learning/scheduler.py`

- [ ] **Step 1: Add imports and fields to LearningScheduler**

Add to imports:
```python
from hestia.learning.correction_classifier import CorrectionClassifier
from hestia.learning.outcome_distiller import OutcomeDistiller
```

Add to `__init__`:
```python
self._correction_classifier: Optional[CorrectionClassifier] = None
self._outcome_distiller: Optional[OutcomeDistiller] = None
```

- [ ] **Step 2: Initialize in `initialize()` method, after existing components**

```python
# Sprint 17: Learning closure components
self._correction_classifier = CorrectionClassifier(
    learning_db=self._db,
    outcome_db=outcome_mgr._database,
)
self._outcome_distiller = OutcomeDistiller(
    learning_db=self._db,
    outcome_db=outcome_mgr._database,
    principle_store=research_mgr.principle_store,
)
```

- [ ] **Step 3: Add two background loops**

```python
self._tasks.append(asyncio.create_task(self._correction_loop()))
self._tasks.append(asyncio.create_task(self._distillation_loop()))
```

Update monitor count in log: `"monitors": 8`

Add the loop methods:
```python
# ── Learning Closure Loops (Sprint 17) ─────────────────────

async def _correction_loop(self) -> None:
    """Classify pending corrections every 6 hours."""
    await asyncio.sleep(360)  # 6 min after startup
    while self._running:
        try:
            stats = await self._correction_classifier.classify_all_pending(DEFAULT_USER_ID)
            if stats.get("classified", 0) > 0:
                logger.info(
                    "Correction classification complete",
                    component=LogComponent.LEARNING,
                    data=stats,
                )
        except Exception as e:
            logger.warning(
                f"Correction classification failed: {type(e).__name__}",
                component=LogComponent.LEARNING,
            )
        await asyncio.sleep(21600)  # 6 hours

async def _distillation_loop(self) -> None:
    """Distill principles from outcomes weekly."""
    await asyncio.sleep(420)  # 7 min after startup
    while self._running:
        try:
            result = await self._outcome_distiller.distill_from_outcomes(DEFAULT_USER_ID)
            logger.info(
                "Outcome distillation complete",
                component=LogComponent.LEARNING,
                data=result,
            )
        except Exception as e:
            logger.warning(
                f"Outcome distillation failed: {type(e).__name__}",
                component=LogComponent.LEARNING,
            )
        await asyncio.sleep(604800)  # 7 days
```

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ --timeout=30 -q`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add hestia/learning/scheduler.py
git commit -m "feat: wire correction classifier + outcome distiller into LearningScheduler"
```

### Task 6: Add API routes

**Files:**
- Modify: `hestia/api/routes/learning.py`

- [ ] **Step 1: Add correction and distillation endpoints**

```python
@router.get("/corrections")
async def list_corrections(
    user_id: str = Query(...),
    correction_type: Optional[str] = Query(None),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
):
    """List classified corrections."""
    db = await _get_learning_db()
    corrections = await db.list_corrections(
        user_id, correction_type=correction_type, days=days, limit=limit,
    )
    return {"data": [c.to_dict() for c in corrections], "count": len(corrections)}


@router.get("/corrections/stats")
async def get_correction_stats(
    user_id: str = Query(...),
    days: int = Query(default=7, ge=1, le=365),
):
    """Get correction type distribution."""
    db = await _get_learning_db()
    stats = await db.get_correction_stats(user_id, days=days)
    return {"data": stats}


@router.post("/distill")
async def trigger_distillation(
    user_id: str = Query(...),
    days: int = Query(default=30, ge=1, le=365),
):
    """Manually trigger outcome-to-principle distillation."""
    from hestia.learning.outcome_distiller import OutcomeDistiller
    from hestia.outcomes import get_outcome_manager
    from hestia.research.manager import get_research_manager

    db = await _get_learning_db()
    outcome_mgr = await get_outcome_manager()
    research_mgr = await get_research_manager()

    distiller = OutcomeDistiller(
        learning_db=db,
        outcome_db=outcome_mgr._database,
        principle_store=research_mgr.principle_store,
    )
    result = await distiller.distill_from_outcomes(user_id, days=days)
    return {"data": result}


@router.get("/distillation-runs")
async def list_distillation_runs(
    user_id: str = Query(...),
    limit: int = Query(default=20, ge=1, le=100),
):
    """Get distillation run history."""
    db = await _get_learning_db()
    run = await db.get_latest_distillation_run(user_id)
    return {"data": run.to_dict() if run else None}


@router.get("/corrections/{outcome_id}")
async def get_correction_for_outcome(
    outcome_id: str,
    user_id: str = Query(...),
):
    """Get correction classification for a specific outcome."""
    db = await _get_learning_db()
    correction = await db.get_correction(outcome_id, user_id)
    return {"data": correction.to_dict() if correction else None}
```

- [ ] **Step 2: Add import for Optional at top of file**

```python
from typing import Optional
```

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/ --timeout=30 -q`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add hestia/api/routes/learning.py
git commit -m "feat: 5 new learning API endpoints — corrections + distillation"
```

---

## Chunk 5: Integration + Documentation

### Task 7: Export new components from learning module

**Files:**
- Modify: `hestia/learning/__init__.py`

- [ ] **Step 1: Add exports**

```python
from hestia.learning.correction_classifier import CorrectionClassifier
from hestia.learning.outcome_distiller import OutcomeDistiller
```

- [ ] **Step 2: Commit**

```bash
git add hestia/learning/__init__.py
git commit -m "feat: export CorrectionClassifier, OutcomeDistiller from learning module"
```

### Task 8: Update documentation

**Files:**
- Modify: `CLAUDE.md`
- Modify: `SPRINT.md`

- [ ] **Step 1: Update CLAUDE.md**

Updates needed:
- Current workstreams: Sprint 17 (Learning Closure)
- Test counts: update after final count
- Endpoint counts: +5 (was 180, now 185)
- Learning module in project structure: add `correction_classifier.py`, `outcome_distiller.py`
- API Summary: update Learning row from 5 to 10 endpoints
- Key Architecture Notes: add Learning Closure section

- [ ] **Step 2: Update SPRINT.md**

Add Sprint 17 section at top with summary of what was built.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md SPRINT.md
git commit -m "docs: Sprint 17 status, endpoint counts, project structure updates"
```

### Task 9: Run full verification

- [ ] **Step 1: Run full backend test suite**

Run: `pytest tests/ --timeout=30 -v`
Expected: All PASS, ~2110+ tests

- [ ] **Step 2: Start server and verify new endpoints**

```bash
lsof -i :8443 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null
python -m hestia.api.server &
sleep 5
# Test new endpoints
curl -sk https://localhost:8443/v1/learning/corrections?user_id=default
curl -sk https://localhost:8443/v1/learning/corrections/stats?user_id=default
curl -sk https://localhost:8443/v1/learning/distillation-runs?user_id=default
```

- [ ] **Step 3: Kill test server**

```bash
lsof -i :8443 | grep LISTEN | awk '{print $2}' | xargs kill -9
```
