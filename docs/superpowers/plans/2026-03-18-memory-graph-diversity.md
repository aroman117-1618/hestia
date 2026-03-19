# Memory Graph Diversity Implementation Plan (Revised)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the monochrome memory graph into a diverse, high-quality knowledge visualization with Decision, Action Item, Preference, Research, and Fact nodes — by adding LLM-backed classification to the existing async tagger pipeline, with content quality gates for mail and notes.

**Architecture:** Two-tier classification: (1) Lightweight heuristic at store time for only the most unambiguous ACTION_ITEMs, (2) LLM-backed classification in the existing async tagger for Decision/Preference/Research. Content quality gates filter out promotional emails and restrict notes to the "Intelligence" folder. Retroactive script reclassifies existing data. Fact extraction pipeline debugged separately.

**Tech Stack:** Python/FastAPI backend, SQLite, ChromaDB, Ollama LLM inference, existing AutoTagger and FactExtractor modules.

**Second Opinion:** `docs/plans/memory-graph-diversity-second-opinion-2026-03-18.md` — both Claude and Gemini approved with conditions (incorporated below).

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `hestia/memory/tagger.py` | Modify | Add `suggested_type` to TAG_EXTRACTION_PROMPT, add `classify_chunk_type()`, add `_should_classify()` gate |
| `hestia/memory/manager.py` | Modify | Wire classification into `_async_tag_chunk()` and minimal sync gate in `store()` |
| `hestia/orchestration/handler.py` | Modify | Add logging to `_maybe_extract_facts()` |
| `hestia/research/fact_extractor.py` | Modify | Add diagnostic logging to each phase |
| `scripts/reclassify-conversations.py` | Create | Retroactive reclassification of CONVERSATION + OBSERVATION chunks |
| `tests/test_memory_classification.py` | Create | Tests for chunk type promotion pipeline |
| `tests/test_fact_extraction_debug.py` | Create | Tests to verify fact extraction succeeds end-to-end |

---

## Task 1: Add LLM Classification to TAG_EXTRACTION_PROMPT + Quality Gates

**Files:**
- Modify: `hestia/memory/tagger.py` (prompt, new methods, new constants)
- Test: `tests/test_memory_classification.py` (new file)

This task extends the existing LLM tagger prompt to return a `suggested_type`, adds content quality gates (mail promo filter, notes folder filter), and adds a `classify_chunk_type()` method that uses both heuristic and LLM signals.

- [ ] **Step 1: Write failing tests for content quality gates**

```python
# tests/test_memory_classification.py
"""Tests for memory chunk type classification pipeline."""
import pytest
from hestia.memory.tagger import AutoTagger, PROMO_SIGNALS
from hestia.memory.models import ChunkType, ChunkTags, ChunkMetadata, ConversationChunk, MemoryScope


class TestContentQualityGates:
    """Test _should_classify() pre-filters."""

    def setup_method(self) -> None:
        self.tagger = AutoTagger()

    def _make_chunk(
        self,
        content: str,
        chunk_type: ChunkType = ChunkType.CONVERSATION,
        source: str = "conversation",
        folder: str = "",
    ) -> ConversationChunk:
        metadata = ChunkMetadata(source=source)
        tags = ChunkTags()
        if folder:
            tags.custom = {"folder": folder}
        return ConversationChunk(
            id="test-1",
            session_id="s1",
            content=content,
            chunk_type=chunk_type,
            tags=tags,
            metadata=metadata,
            scope=MemoryScope.SESSION,
        )

    def test_conversation_passes_gate(self) -> None:
        chunk = self._make_chunk("After careful analysis, I've decided to use PostgreSQL for the database.")
        assert self.tagger._should_classify(chunk) is True

    def test_observation_passes_gate(self) -> None:
        chunk = self._make_chunk(
            "[INGESTED NOTES -- 2026-03-01]: Research findings on transformer architectures",
            chunk_type=ChunkType.OBSERVATION,
            source="notes",
            folder="Intelligence",
        )
        assert self.tagger._should_classify(chunk) is True

    def test_source_structured_blocked(self) -> None:
        chunk = self._make_chunk("Meeting at 3pm", chunk_type=ChunkType.SOURCE_STRUCTURED)
        assert self.tagger._should_classify(chunk) is False

    def test_short_content_blocked(self) -> None:
        chunk = self._make_chunk("hello")
        assert self.tagger._should_classify(chunk) is False

    def test_promo_email_blocked(self) -> None:
        chunk = self._make_chunk(
            "[INGESTED MAIL -- noreply@store.com -- 2026-03-01]: 50% off! Click to unsubscribe from these emails.",
            chunk_type=ChunkType.OBSERVATION,
            source="mail",
        )
        assert self.tagger._should_classify(chunk) is False

    def test_real_email_passes(self) -> None:
        chunk = self._make_chunk(
            "[INGESTED MAIL -- john@company.com -- 2026-03-01]: Hey Andrew, here's the quarterly report with the API metrics we discussed.",
            chunk_type=ChunkType.OBSERVATION,
            source="mail",
        )
        assert self.tagger._should_classify(chunk) is True

    def test_notes_intelligence_folder_passes(self) -> None:
        chunk = self._make_chunk(
            "[INGESTED NOTES -- 2026-03-01]: Analysis of market trends for crypto trading strategy",
            chunk_type=ChunkType.OBSERVATION,
            source="notes",
            folder="Intelligence",
        )
        assert self.tagger._should_classify(chunk) is True

    def test_notes_other_folder_blocked(self) -> None:
        chunk = self._make_chunk(
            "[INGESTED NOTES -- 2026-03-01]: Grocery list for the week",
            chunk_type=ChunkType.OBSERVATION,
            source="notes",
            folder="Personal",
        )
        assert self.tagger._should_classify(chunk) is False

    def test_notes_no_folder_blocked(self) -> None:
        """Notes without folder metadata are blocked (can't confirm Intelligence folder)."""
        chunk = self._make_chunk(
            "[INGESTED NOTES -- 2026-03-01]: Some random note",
            chunk_type=ChunkType.OBSERVATION,
            source="notes",
        )
        assert self.tagger._should_classify(chunk) is False

    def test_already_classified_blocked(self) -> None:
        chunk = self._make_chunk("I decided to use Postgres", chunk_type=ChunkType.DECISION)
        assert self.tagger._should_classify(chunk) is False


class TestClassifyChunkType:
    """Test classify_chunk_type() with heuristic + LLM signals."""

    def setup_method(self) -> None:
        self.tagger = AutoTagger()

    def test_explicit_todo_becomes_action_item(self) -> None:
        """Sync heuristic: explicit TODO prefix."""
        result = self.tagger.classify_chunk_type(
            content="TODO: Update the deployment script to handle new env vars before Friday release.",
            metadata=ChunkMetadata(has_action_item=True),
            llm_suggested_type=None,
            llm_type_confidence=0.0,
        )
        assert result == ChunkType.ACTION_ITEM

    def test_llm_decision_with_high_confidence(self) -> None:
        result = self.tagger.classify_chunk_type(
            content="After comparing options, I've decided to go with PostgreSQL.",
            metadata=ChunkMetadata(has_decision=True),
            llm_suggested_type="decision",
            llm_type_confidence=0.85,
        )
        assert result == ChunkType.DECISION

    def test_llm_decision_with_low_confidence_stays_conversation(self) -> None:
        result = self.tagger.classify_chunk_type(
            content="Maybe we should consider PostgreSQL?",
            metadata=ChunkMetadata(),
            llm_suggested_type="decision",
            llm_type_confidence=0.4,
        )
        assert result == ChunkType.CONVERSATION

    def test_llm_preference_detected(self) -> None:
        result = self.tagger.classify_chunk_type(
            content="I always prefer dark mode for development. Tabs over spaces, every time.",
            metadata=ChunkMetadata(),
            llm_suggested_type="preference",
            llm_type_confidence=0.9,
        )
        assert result == ChunkType.PREFERENCE

    def test_llm_research_detected(self) -> None:
        result = self.tagger.classify_chunk_type(
            content="Analysis shows transformer architectures outperform RNNs. Key finding: attention scales better with context length.",
            metadata=ChunkMetadata(),
            llm_suggested_type="research",
            llm_type_confidence=0.8,
        )
        assert result == ChunkType.RESEARCH

    def test_no_llm_signal_stays_conversation(self) -> None:
        result = self.tagger.classify_chunk_type(
            content="Can you help me debug this issue?",
            metadata=ChunkMetadata(),
            llm_suggested_type=None,
            llm_type_confidence=0.0,
        )
        assert result == ChunkType.CONVERSATION

    def test_llm_conversation_stays_conversation(self) -> None:
        result = self.tagger.classify_chunk_type(
            content="Hey, what's the status of the project?",
            metadata=ChunkMetadata(),
            llm_suggested_type="conversation",
            llm_type_confidence=0.95,
        )
        assert result == ChunkType.CONVERSATION

    def test_confidence_threshold_at_boundary(self) -> None:
        """Exactly 0.7 should pass (>=0.7 threshold)."""
        result = self.tagger.classify_chunk_type(
            content="I've decided to switch to GraphQL for the new API.",
            metadata=ChunkMetadata(has_decision=True),
            llm_suggested_type="decision",
            llm_type_confidence=0.7,
        )
        assert result == ChunkType.DECISION
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_memory_classification.py -v`
Expected: FAIL — methods don't exist yet

- [ ] **Step 3: Implement quality gates and classification in tagger.py**

Add constants near the top of `hestia/memory/tagger.py`, after `SENSITIVE_PATTERNS`:

```python
# Promotional email signals — skip these from classification
PROMO_SIGNALS = [
    "unsubscribe", "view in browser", "email preferences",
    "no longer wish to receive", "opt out", "manage subscriptions",
    "privacy policy", "terms of service", "do not reply",
    "noreply@", "no-reply@", "marketing@", "updates@",
    "newsletter", "weekly digest", "daily summary",
    "powered by mailchimp", "powered by sendgrid",
]

# Minimum content length for classification (chars)
MIN_CLASSIFICATION_LENGTH = 40

# Minimum LLM confidence to promote chunk type
CLASSIFICATION_CONFIDENCE_THRESHOLD = 0.7

# Explicit action item prefixes (high-confidence heuristic, sync-safe)
ACTION_ITEM_PREFIXES = [
    "todo:", "todo -", "action item:", "action item -",
    "task:", "[ ]", "[x]", "- [ ]", "- [x]",
]

# Valid LLM-suggested types for promotion
PROMOTABLE_TYPES = {"decision", "action_item", "preference", "research"}
```

Update `TAG_EXTRACTION_PROMPT` — add classification fields to the JSON schema and guidelines:

```python
TAG_EXTRACTION_PROMPT = """Analyze the following conversation content and extract structured tags.

Content:
{content}

Extract the following information as JSON:
{{
    "topics": ["list", "of", "main", "topics"],
    "entities": ["specific", "named", "things", "mentioned"],
    "people": ["names", "of", "people", "mentioned"],
    "has_code": true/false,
    "has_decision": true/false,
    "has_action_item": true/false,
    "sentiment": "positive" | "neutral" | "negative",
    "status": ["active"] or ["unresolved"] if there's an open question,
    "suggested_type": "conversation" | "decision" | "action_item" | "preference" | "research",
    "type_confidence": 0.0 to 1.0
}}

Guidelines:
- Topics should be general categories (e.g., "security", "authentication", "database")
- Entities should be specific things (e.g., "ChromaDB", "Face ID", "ADR-009")
- Only include people if explicitly mentioned by name
- has_code is true if there's actual code, not just technical discussion
- has_decision is true if a decision was made or confirmed
- has_action_item is true if there's a task to be done
- sentiment reflects the overall tone
- status is ["unresolved"] if there's an open question or issue

Chunk Type Classification (for suggested_type):
- "decision": Author made a clear, finalized choice between alternatives.
  MUST contain explicit commitment ("I decided", "we're going with", "I chose").
  Do NOT classify tentative statements ("maybe we should", "thinking about").
- "action_item": A concrete task with implied or stated deadline.
  MUST describe a specific action ("TODO:", "need to update X", "schedule Y").
  Do NOT classify vague intentions ("should probably", "would be nice to").
- "preference": A personal taste, habit, or recurring style choice.
  MUST express a consistent preference ("I prefer", "I always", "I never").
  Do NOT classify one-time situational choices.
- "research": Analysis results, investigation findings, or comparative evaluation.
  MUST contain synthesized findings, not just raw data or questions.
- "conversation": Default. Casual chat, questions, greetings, troubleshooting.
  When in doubt, choose "conversation" — false negatives are better than false positives.
- type_confidence: How confident you are in the classification (0.0-1.0).
  Use 0.9+ only for unambiguous cases. Use <0.5 for borderline.

Respond with ONLY the JSON object, no other text."""
```

Add methods to `AutoTagger` class:

```python
def _should_classify(self, chunk: ConversationChunk) -> bool:
    """Content quality gate: only classify chunks worth promoting."""
    # Only classify CONVERSATION and OBSERVATION chunks
    if chunk.chunk_type not in (ChunkType.CONVERSATION, ChunkType.OBSERVATION):
        return False

    # Too short to classify meaningfully
    if len(chunk.content.strip()) < MIN_CLASSIFICATION_LENGTH:
        return False

    source = chunk.metadata.source if chunk.metadata else None

    # Mail filter: skip promotional/marketing emails
    if source == "mail":
        content_lower = chunk.content.lower()
        if any(signal in content_lower for signal in PROMO_SIGNALS):
            return False

    # Notes filter: only classify from "Intelligence" folder
    if source == "notes":
        folder = ""
        if chunk.tags and chunk.tags.custom:
            folder = chunk.tags.custom.get("folder", "")
        if not folder or "intelligence" not in folder.lower():
            return False

    return True

def classify_chunk_type(
    self,
    content: str,
    metadata: ChunkMetadata,
    llm_suggested_type: Optional[str] = None,
    llm_type_confidence: float = 0.0,
) -> ChunkType:
    """Classify chunk type using heuristic + LLM signals.

    Priority:
    1. Explicit ACTION_ITEM prefixes (heuristic, high confidence)
    2. LLM suggested_type with confidence >= threshold
    3. Default: CONVERSATION
    """
    # Tier 1: Heuristic — explicit action item prefixes only
    content_stripped = content.strip().lower()
    if any(content_stripped.startswith(prefix) for prefix in ACTION_ITEM_PREFIXES):
        return ChunkType.ACTION_ITEM

    # Tier 2: LLM classification with confidence gate
    if (
        llm_suggested_type
        and llm_suggested_type in PROMOTABLE_TYPES
        and llm_type_confidence >= CLASSIFICATION_CONFIDENCE_THRESHOLD
    ):
        try:
            return ChunkType(llm_suggested_type)
        except ValueError:
            pass  # Invalid type string, fall through

    return ChunkType.CONVERSATION
```

Also update `_parse_tag_response()` to extract the new fields. Find the method and add parsing for `suggested_type` and `type_confidence`:

```python
# In _parse_tag_response(), after existing field extraction:
suggested_type = data.get("suggested_type")
type_confidence = float(data.get("type_confidence", 0.0))
# Store in metadata for use by classify_chunk_type
metadata.suggested_type = suggested_type
metadata.type_confidence = type_confidence
```

Note: `ChunkMetadata` needs two new optional fields: `suggested_type: Optional[str] = None` and `type_confidence: float = 0.0`. Add these to the dataclass in `hestia/memory/models.py`.

- [ ] **Step 4: Add suggested_type and type_confidence to ChunkMetadata**

In `hestia/memory/models.py`, add to the `ChunkMetadata` dataclass (after existing fields):

```python
suggested_type: Optional[str] = None       # LLM-suggested chunk type
type_confidence: float = 0.0               # LLM confidence in suggested type
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_memory_classification.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite for regressions**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All existing tests still pass. The new fields on ChunkMetadata have defaults so existing code is unaffected.

- [ ] **Step 7: Commit**

```bash
git add hestia/memory/tagger.py hestia/memory/models.py tests/test_memory_classification.py
git commit -m "feat: LLM-backed chunk type classification with content quality gates"
```

---

## Task 2: Wire Classification into Memory Manager Pipeline

**Files:**
- Modify: `hestia/memory/manager.py:211-305` (store and _async_tag_chunk methods)
- Test: `tests/test_memory_classification.py` (extend)

Wire the classifier into the async tagger (primary path) and add a minimal sync-path check for explicit ACTION_ITEMs only.

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_memory_classification.py`:

```python
@pytest.mark.asyncio
class TestAsyncClassificationPipeline:
    """Test that _async_tag_chunk promotes chunk types via LLM."""

    async def test_async_tagger_promotes_decision(self) -> None:
        """When LLM returns suggested_type=decision with high confidence, chunk is promoted."""
        from unittest.mock import AsyncMock, patch, MagicMock
        from hestia.memory.manager import MemoryManager

        manager = MemoryManager.__new__(MemoryManager)
        manager.tagger = AutoTagger()
        manager.database = AsyncMock()
        manager.vector_store = MagicMock()
        manager.logger = MagicMock()

        chunk = ConversationChunk(
            id="test-async-1",
            session_id="s1",
            content="After reviewing all options, I've decided to go with PostgreSQL for the primary database.",
            chunk_type=ChunkType.CONVERSATION,
            tags=ChunkTags(),
            metadata=ChunkMetadata(source="conversation"),
            scope=MemoryScope.SESSION,
        )

        # Mock extract_tags to return LLM classification
        mock_metadata = ChunkMetadata(
            has_decision=True,
            suggested_type="decision",
            type_confidence=0.9,
            source="conversation",
        )
        with patch.object(manager.tagger, 'extract_tags', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = (ChunkTags(topics=["database"]), mock_metadata)
            await manager._async_tag_chunk(chunk)

        assert chunk.chunk_type == ChunkType.DECISION
        manager.database.update_chunk.assert_called_once()

    async def test_async_tagger_skips_low_confidence(self) -> None:
        """Low LLM confidence should not promote."""
        from unittest.mock import AsyncMock, patch, MagicMock
        from hestia.memory.manager import MemoryManager

        manager = MemoryManager.__new__(MemoryManager)
        manager.tagger = AutoTagger()
        manager.database = AsyncMock()
        manager.vector_store = MagicMock()
        manager.logger = MagicMock()

        chunk = ConversationChunk(
            id="test-async-2",
            session_id="s1",
            content="Maybe we should think about using PostgreSQL sometime.",
            chunk_type=ChunkType.CONVERSATION,
            tags=ChunkTags(),
            metadata=ChunkMetadata(source="conversation"),
            scope=MemoryScope.SESSION,
        )

        mock_metadata = ChunkMetadata(
            suggested_type="decision",
            type_confidence=0.3,
            source="conversation",
        )
        with patch.object(manager.tagger, 'extract_tags', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = (ChunkTags(), mock_metadata)
            await manager._async_tag_chunk(chunk)

        assert chunk.chunk_type == ChunkType.CONVERSATION

    async def test_async_tagger_skips_promo_email(self) -> None:
        """Promotional emails should not be classified."""
        from unittest.mock import AsyncMock, patch, MagicMock
        from hestia.memory.manager import MemoryManager

        manager = MemoryManager.__new__(MemoryManager)
        manager.tagger = AutoTagger()
        manager.database = AsyncMock()
        manager.vector_store = MagicMock()
        manager.logger = MagicMock()

        chunk = ConversationChunk(
            id="test-async-3",
            session_id="s1",
            content="[INGESTED MAIL -- store@example.com -- 2026-03-01]: Big sale! Click to unsubscribe from our newsletter.",
            chunk_type=ChunkType.OBSERVATION,
            tags=ChunkTags(),
            metadata=ChunkMetadata(source="mail"),
            scope=MemoryScope.SESSION,
        )

        with patch.object(manager.tagger, 'extract_tags', new_callable=AsyncMock) as mock_extract:
            mock_extract.return_value = (ChunkTags(), ChunkMetadata(source="mail"))
            await manager._async_tag_chunk(chunk)

        # Should remain OBSERVATION — promo filter blocks classification
        assert chunk.chunk_type == ChunkType.OBSERVATION
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_memory_classification.py::TestAsyncClassificationPipeline -v`
Expected: FAIL — _async_tag_chunk doesn't do classification yet

- [ ] **Step 3: Modify _async_tag_chunk() to classify after LLM tagging**

In `hestia/memory/manager.py`, inside `_async_tag_chunk()`, after `extract_tags` returns and before `update_chunk`:

```python
async def _async_tag_chunk(self, chunk: ConversationChunk) -> None:
    """Asynchronously tag and classify a chunk using LLM."""
    try:
        new_tags, new_metadata = await self.tagger.extract_tags(
            chunk.content, existing_tags=chunk.tags
        )

        chunk.tags = new_tags
        chunk.metadata = new_metadata

        # Classify chunk type if content passes quality gates
        if self.tagger._should_classify(chunk):
            new_type = self.tagger.classify_chunk_type(
                content=chunk.content,
                metadata=new_metadata,
                llm_suggested_type=new_metadata.suggested_type,
                llm_type_confidence=new_metadata.type_confidence,
            )
            if new_type != chunk.chunk_type:
                old_type = chunk.chunk_type.value
                chunk.chunk_type = new_type
                logger.info(
                    "Promoted chunk type",
                    component=LogComponent.MEMORY,
                    data={
                        "chunk_id": chunk.id,
                        "old_type": old_type,
                        "new_type": new_type.value,
                        "confidence": new_metadata.type_confidence,
                        "llm_suggested": new_metadata.suggested_type,
                    },
                )

        await self.database.update_chunk(chunk)
        self.vector_store.update_chunk(chunk)

    except Exception as e:
        logger.warning(
            f"Async tagging failed: {type(e).__name__}",
            component=LogComponent.MEMORY,
        )
```

- [ ] **Step 4: Add minimal sync-path check in store()**

In `hestia/memory/manager.py`, inside `store()`, after quick_tag (around line 244), before chunk creation:

```python
# Sync heuristic: only explicit ACTION_ITEM prefixes (high confidence)
if chunk_type == ChunkType.CONVERSATION and auto_tag:
    chunk_type = self.tagger.classify_chunk_type(
        content=content,
        metadata=metadata,
        llm_suggested_type=None,  # No LLM in sync path
        llm_type_confidence=0.0,
    )
```

This only triggers for explicit TODO:/action item: prefixes. All nuanced classification waits for the async LLM path.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_memory_classification.py -v`
Expected: All tests PASS

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All existing tests pass

- [ ] **Step 7: Commit**

```bash
git add hestia/memory/manager.py tests/test_memory_classification.py
git commit -m "feat: wire LLM classification into async tagger pipeline with quality gates"
```

---

## Task 3: Retroactive Reclassification Script

**Files:**
- Create: `scripts/reclassify-conversations.py`
- Reference: `scripts/reclassify-insights.py` (existing pattern)

Reclassifies existing CONVERSATION and qualifying OBSERVATION chunks. Updates **both SQLite and ChromaDB** for consistency.

- [ ] **Step 1: Create the reclassification script**

```python
#!/usr/bin/env python3
"""Retroactively reclassify memory chunks using LLM-backed classification.

Processes CONVERSATION chunks and qualifying OBSERVATION chunks (Intelligence
folder notes, non-promo emails). Uses the same AutoTagger pipeline as live
classification.

Usage:
    python scripts/reclassify-conversations.py              # Dry run
    python scripts/reclassify-conversations.py --apply       # Apply to SQLite + ChromaDB
"""

import argparse
import asyncio
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hestia.memory.tagger import (
    AutoTagger,
    PROMO_SIGNALS,
    MIN_CLASSIFICATION_LENGTH,
    CLASSIFICATION_CONFIDENCE_THRESHOLD,
    PROMOTABLE_TYPES,
)
from hestia.memory.models import (
    ChunkType,
    ChunkTags,
    ChunkMetadata,
    ConversationChunk,
    MemoryScope,
)

DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"


async def reclassify_chunks(apply: bool = False) -> None:
    """Scan chunks and reclassify using LLM tagger."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    tagger = AutoTagger()

    # Fetch CONVERSATION + OBSERVATION chunks
    rows = conn.execute(
        "SELECT id, content, chunk_type, tags, metadata FROM memory_chunks "
        "WHERE chunk_type IN ('conversation', 'observation') AND status = 'active'"
    ).fetchall()

    print(f"Found {len(rows)} active CONVERSATION + OBSERVATION chunks")

    # Pre-filter using quality gates
    candidates = []
    skipped = Counter()

    for row in rows:
        content = row["content"]
        source = ""
        folder = ""

        # Parse metadata
        try:
            meta_dict = json.loads(row["metadata"]) if row["metadata"] else {}
            source = meta_dict.get("source", "")
        except (json.JSONDecodeError, TypeError):
            meta_dict = {}

        # Parse tags for folder info
        try:
            tags_dict = json.loads(row["tags"]) if row["tags"] else {}
            folder = tags_dict.get("custom", {}).get("folder", "")
        except (json.JSONDecodeError, TypeError):
            tags_dict = {}

        # Apply quality gates
        if len(content.strip()) < MIN_CLASSIFICATION_LENGTH:
            skipped["too_short"] += 1
            continue

        if source == "mail":
            content_lower = content.lower()
            if any(signal in content_lower for signal in PROMO_SIGNALS):
                skipped["promo_email"] += 1
                continue

        if source == "notes":
            if not folder or "intelligence" not in folder.lower():
                skipped["wrong_folder"] += 1
                continue

        candidates.append(row)

    print(f"Candidates after filtering: {len(candidates)}")
    print(f"Skipped: {dict(skipped)}")

    # Classify candidates using LLM tagger
    promotions: dict[str, list[str]] = {t: [] for t in PROMOTABLE_TYPES}
    errors = 0

    for i, row in enumerate(candidates):
        if (i + 1) % 50 == 0:
            print(f"  Processing {i + 1}/{len(candidates)}...")

        try:
            new_tags, new_metadata = await tagger.extract_tags(row["content"])
            if (
                new_metadata.suggested_type
                and new_metadata.suggested_type in PROMOTABLE_TYPES
                and new_metadata.type_confidence >= CLASSIFICATION_CONFIDENCE_THRESHOLD
            ):
                promotions[new_metadata.suggested_type].append(row["id"])
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  Error on chunk {row['id']}: {type(e).__name__}")

    # Report
    total_promoted = sum(len(ids) for ids in promotions.values())
    print(f"\n--- Reclassification Results ---")
    print(f"Total to promote: {total_promoted} / {len(candidates)} candidates")
    for chunk_type, ids in promotions.items():
        if ids:
            print(f"  {chunk_type}: {len(ids)}")
    if errors:
        print(f"  errors: {errors}")

    if not apply:
        print(f"\nDry run complete. Use --apply to commit changes.")
        conn.close()
        return

    # Apply to SQLite
    cursor = conn.cursor()
    for chunk_type, ids in promotions.items():
        if not ids:
            continue
        placeholders = ",".join("?" * len(ids))
        cursor.execute(
            f"UPDATE memory_chunks SET chunk_type = ? WHERE id IN ({placeholders})",
            [chunk_type] + ids,
        )
        print(f"SQLite: updated {len(ids)} chunks to {chunk_type}")

    conn.commit()
    conn.close()

    # Update ChromaDB metadata
    try:
        from hestia.memory.vector_store import get_vector_store
        vs = get_vector_store()
        updated_chroma = 0
        for chunk_type, ids in promotions.items():
            for chunk_id in ids:
                try:
                    vs._collection.update(
                        ids=[chunk_id],
                        metadatas=[{"chunk_type": chunk_type}],
                    )
                    updated_chroma += 1
                except Exception:
                    pass
        print(f"ChromaDB: updated {updated_chroma} chunk metadata entries")
    except Exception as e:
        print(f"ChromaDB update failed: {type(e).__name__} — SQLite changes committed, ChromaDB skipped")

    print(f"\nDone. {total_promoted} chunks reclassified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reclassify memory chunks via LLM")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    args = parser.parse_args()
    asyncio.run(reclassify_chunks(apply=args.apply))
```

- [ ] **Step 2: Run dry run locally to validate**

Run: `python scripts/reclassify-conversations.py`
Expected: Counts per type, filtering stats. Review that numbers are reasonable.

- [ ] **Step 3: Sanity check**

Verify:
- Total promotions < 30% of candidates (classification is conservative)
- Decisions < 10%, Actions < 15%, Preferences < 5%, Research < 10%
- If any type exceeds these bounds, review sample chunks before applying

- [ ] **Step 4: Commit**

```bash
chmod +x scripts/reclassify-conversations.py
git add scripts/reclassify-conversations.py
git commit -m "feat: retroactive LLM-backed reclassification script (SQLite + ChromaDB)"
```

---

## Task 4: Debug and Fix Fact Extraction Pipeline

**Files:**
- Modify: `hestia/research/fact_extractor.py` (add logging)
- Modify: `hestia/orchestration/handler.py:1917-1925` (_maybe_extract_facts)
- Test: `tests/test_fact_extraction_debug.py` (new file)

The fact extraction pipeline has produced **zero facts**. Hypothesis: the lazy `_get_inference_client()` call inside a fire-and-forget `asyncio.create_task` fails silently because the research manager or inference client isn't initialized in the background task context.

- [ ] **Step 1: Write diagnostic tests**

```python
# tests/test_fact_extraction_debug.py
"""Diagnostic tests for fact extraction pipeline."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hestia.research.fact_extractor import FactExtractor
from hestia.research.entity_registry import EntityRegistry


@pytest.mark.asyncio
class TestFactExtractionDiagnostic:
    """Isolate which phase of fact extraction fails."""

    async def test_extract_from_text_with_mock_client(self) -> None:
        """Full pipeline with mocked inference — should produce facts."""
        mock_db = AsyncMock()
        mock_db.create_fact = AsyncMock(return_value=None)
        mock_db.check_contradictions = AsyncMock(return_value=[])
        mock_registry = AsyncMock(spec=EntityRegistry)
        mock_entity = MagicMock()
        mock_entity.id = "test-entity-1"
        mock_entity.name = "PostgreSQL"
        mock_registry.resolve_entity = AsyncMock(return_value=mock_entity)

        extractor = FactExtractor(mock_db, mock_registry)

        # Mock inference client with valid 3-phase responses
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(side_effect=[
            MagicMock(content='["Hestia", "PostgreSQL"]'),
            MagicMock(content='["Hestia", "PostgreSQL"]'),
            MagicMock(content='[{"subject": "Hestia", "predicate": "uses", "object": "PostgreSQL", "confidence": 0.9, "durability": 2}]'),
        ])

        with patch('hestia.research.fact_extractor._get_inference_client', new_callable=AsyncMock, return_value=mock_client):
            facts = await extractor.extract_from_text(
                "Hestia uses PostgreSQL as its primary database for structured data storage.",
                source_chunk_id="test-chunk-1",
            )

        # Verify the pipeline attempted to create a fact
        assert mock_db.create_fact.called, "create_fact was never called — pipeline failed before fact creation"

    async def test_inference_client_initialization(self) -> None:
        """Verify _get_inference_client() doesn't fail in isolation."""
        try:
            from hestia.research.fact_extractor import _get_inference_client
            client = await _get_inference_client()
            assert client is not None, "Inference client is None"
        except Exception as e:
            pytest.fail(f"_get_inference_client() raised {type(e).__name__}: {e}")
```

- [ ] **Step 2: Run diagnostic tests**

Run: `python -m pytest tests/test_fact_extraction_debug.py -v -s`
Expected: First test should pass (mocked). Second test reveals if client init is the problem.

- [ ] **Step 3: Add logging to fact_extractor.py**

In `hestia/research/fact_extractor.py`, ensure logger exists at module level:

```python
from hestia.logging import get_logger

logger = get_logger()
```

Add logging at the start and end of each phase in `extract_from_text()`:

```python
logger.info("Fact extraction starting", component=LogComponent.RESEARCH,
            data={"text_length": len(text)})

# After Phase 1
logger.info("Fact extraction Phase 1 complete", component=LogComponent.RESEARCH,
            data={"entity_count": len(entities)})

# After Phase 2
logger.info("Fact extraction Phase 2 complete", component=LogComponent.RESEARCH,
            data={"significant_count": len(significant)})

# After Phase 3
logger.info("Fact extraction Phase 3 complete", component=LogComponent.RESEARCH,
            data={"triplet_count": len(triplets)})

# After processing
logger.info("Fact extraction complete", component=LogComponent.RESEARCH,
            data={"facts_created": len(created_facts)})
```

- [ ] **Step 4: Replace silent except in handler._maybe_extract_facts()**

In `hestia/orchestration/handler.py`, replace the bare `except: pass`:

```python
async def _maybe_extract_facts(self, text: str) -> None:
    """Fire-and-forget: extract facts from qualifying chat content."""
    try:
        from hestia.research.manager import get_research_manager
        research_mgr = await get_research_manager()
        if not research_mgr or not hasattr(research_mgr, '_fact_extractor') or not research_mgr._fact_extractor:
            logger.warning("Research manager not initialized for fact extraction",
                          component=LogComponent.RESEARCH)
            return
        facts = await research_mgr._fact_extractor.extract_from_text(text=text[:2000])
        if facts:
            logger.info("Facts extracted from conversation",
                       component=LogComponent.RESEARCH,
                       data={"facts_created": len(facts), "text_length": len(text)})
    except Exception as e:
        logger.error("Fact extraction failed",
                    component=LogComponent.RESEARCH,
                    data={"error": type(e).__name__, "detail": str(e)[:200]})
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_fact_extraction_debug.py -v -s`
Expected: Tests pass, logging visible

- [ ] **Step 6: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add hestia/research/fact_extractor.py hestia/orchestration/handler.py tests/test_fact_extraction_debug.py
git commit -m "fix: add diagnostic logging to fact extraction, replace silent except"
```

---

## Task 5: End-to-End Verification

**Files:** None — verification task

- [ ] **Step 1: Verify chunk distribution in database**

```bash
sqlite3 data/memory.db "SELECT chunk_type, COUNT(*) as cnt FROM memory_chunks WHERE status='active' GROUP BY chunk_type ORDER BY cnt DESC;"
```

Expected: Multiple types with non-zero counts.

- [ ] **Step 2: Verify graph endpoint returns diverse categories**

```bash
curl -k -H "Authorization: Bearer <token>" \
  "https://localhost:8443/v1/research/graph?limit=200&mode=legacy" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); cats=set(n['category'] for n in d.get('nodes',[])); print(f'Categories: {cats}'); print(f'Nodes: {len(d.get(\"nodes\",[]))}')"
```

Expected: Categories include conversation, observation, decision, action_item, etc.

- [ ] **Step 3: Trigger fact extraction**

```bash
curl -k -X POST -H "Authorization: Bearer <token>" \
  "https://localhost:8443/v1/research/facts/extract?time_range_days=30"
```

Check for `facts_created > 0`. Check server logs for Phase 1-3 logging.

- [ ] **Step 4: Verify graph visually in macOS app**

Open Research view. Confirm diverse node colors. Check legend shows multiple active types.

- [ ] **Step 5: Document final distribution and any issues**

Record chunk type counts, graph node diversity, and any follow-up items.

---

## Task 6: Deploy to Mac Mini

- [ ] **Step 1: Push all changes**

```bash
git push origin main
```

- [ ] **Step 2: Pull on Mac Mini**

```bash
ssh andrewroman117@hestia-3.local 'cd ~/hestia && git pull'
```

- [ ] **Step 3: Run retroactive reclassification (dry run first)**

```bash
ssh andrewroman117@hestia-3.local 'cd ~/hestia && source .venv/bin/activate && python scripts/reclassify-conversations.py'
```

Review counts. If reasonable:

```bash
ssh andrewroman117@hestia-3.local 'cd ~/hestia && source .venv/bin/activate && python scripts/reclassify-conversations.py --apply'
```

- [ ] **Step 4: Restart server**

```bash
ssh andrewroman117@hestia-3.local 'lsof -i :8443 | grep LISTEN | awk "{print \$2}" | xargs kill -9 2>/dev/null; cd ~/hestia && source .venv/bin/activate && nohup python -m hestia.api.server &'
```

- [ ] **Step 5: Trigger fact extraction**

```bash
curl -k -X POST "https://hestia-3.local:8443/v1/research/facts/extract?time_range_days=30"
```

- [ ] **Step 6: Verify graph from macOS app**

Open Hestia macOS app → Research view. Confirm diverse node types visible.
