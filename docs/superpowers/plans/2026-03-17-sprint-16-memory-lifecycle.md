# Sprint 16: Memory Lifecycle Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add importance scoring, consolidation, and pruning to Hestia's memory system so retrieval quality improves over time and storage stays lean.

**Architecture:** Three new files in `hestia/memory/` (importance.py, consolidator.py, pruner.py) following the existing module pattern. ImportanceScorer uses SQL aggregation over outcome metadata — no LLM inference. MemoryConsolidator detects near-duplicates via ChromaDB embedding similarity. MemoryPruner soft-deletes old low-importance chunks. All composable with existing temporal decay. Scheduled via LearningScheduler extension.

**Tech Stack:** Python 3.9, SQLite (aiosqlite), ChromaDB, FastAPI, pytest

**Key audit conditions applied:**
1. No `access_count`/`last_accessed` migration — retrieval frequency computed from outcome metadata
2. Fixed importance weights (configurable in memory.yaml, no adaptive rebalancing)
3. Consolidation capped at 50 samples per run
4. Pluggable merge strategy interface for future LLM merge on M5 Ultra

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `hestia/memory/importance.py` | ImportanceScorer: compute + batch-update importance scores |
| Create | `hestia/memory/consolidator.py` | MemoryConsolidator: detect + merge near-duplicate chunks |
| Create | `hestia/memory/pruner.py` | MemoryPruner: archive old low-importance chunks |
| Modify | `hestia/memory/manager.py:410-420` | Apply importance multiplier in search scoring |
| Modify | `hestia/memory/__init__.py` | Export new classes |
| Modify | `hestia/config/memory.yaml` | Add importance/consolidation/pruning config section |
| Modify | `hestia/api/routes/memory.py` | Add 5 new endpoints |
| Modify | `hestia/api/schemas/memory.py` | Add Pydantic schemas for new endpoints |
| Modify | `hestia/learning/scheduler.py` | Add importance/consolidation/pruning loops |
| Modify | `hestia/config/triggers.yaml` | Add new threshold triggers |
| Create | `tests/test_importance.py` | ImportanceScorer tests |
| Create | `tests/test_consolidator.py` | MemoryConsolidator tests |
| Create | `tests/test_pruner.py` | MemoryPruner tests |

---

## Chunk 1: ImportanceScorer (Core Value)

### Task 1: Importance config in memory.yaml

**Files:**
- Modify: `hestia/config/memory.yaml`

- [ ] **Step 1: Add importance config section to memory.yaml**

```yaml
# Add after the existing temporal_decay section:
importance:
  enabled: true
  weights:
    recency: 0.3
    retrieval: 0.4
    type_bonus: 0.3
  type_bonuses:
    fact: 0.8
    decision: 0.7
    preference: 0.6
    research: 0.5
    insight: 0.8
    action_item: 0.4
    conversation: 0.3
    system: 1.0
  recency_max_days: 90
  min_importance: 0.05
```

- [ ] **Step 2: Commit**

```bash
git add hestia/config/memory.yaml
git commit -m "config: add importance scoring weights to memory.yaml"
```

### Task 2: ImportanceScorer — tests first

**Files:**
- Create: `tests/test_importance.py`

- [ ] **Step 1: Write failing tests for ImportanceScorer**

Test the core scoring logic: recency score, retrieval score from outcome data, type bonus, composite formula, batch scoring. Test edge cases: no outcome data (fallback to type+recency), chunk with zero retrievals, system chunks get floor score.

Key test cases:
- `test_recency_score_fresh_chunk` — chunk from today scores 1.0
- `test_recency_score_old_chunk` — chunk from 90+ days ago scores at min floor
- `test_retrieval_score_with_outcomes` — chunk retrieved in 5 outcomes with positive signals scores high
- `test_retrieval_score_no_data` — chunk never retrieved scores 0.0
- `test_type_bonus_fact_vs_conversation` — fact gets 0.8, conversation gets 0.3
- `test_composite_score` — full formula produces expected value
- `test_batch_score_updates_confidence` — batch run updates ChunkMetadata.confidence
- `test_system_chunk_floor` — system chunks never go below 0.5

Mock: `MemoryDatabase` (for chunk listing), `OutcomeDatabase` (for retrieval data). No ChromaDB needed.

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_importance.py -v --timeout=30
```
Expected: FAIL (ImportanceScorer not yet created)

- [ ] **Step 3: Commit test file**

```bash
git add tests/test_importance.py
git commit -m "test: add ImportanceScorer test cases"
```

### Task 3: ImportanceScorer — implementation

**Files:**
- Create: `hestia/memory/importance.py`

- [ ] **Step 1: Implement ImportanceScorer**

Class structure:
```python
class ImportanceScorer:
    """Computes importance scores for memory chunks using retrieval feedback."""

    def __init__(self, memory_db: Any, outcome_db: Any, config: Dict[str, Any]) -> None:
        ...

    async def score_all(self, user_id: str = "default") -> Dict[str, Any]:
        """Batch-score all active chunks. Returns stats dict."""
        ...

    def _compute_recency_score(self, chunk_timestamp: datetime) -> float:
        """Linear decay from 1.0 (today) to min at recency_max_days."""
        ...

    async def _compute_retrieval_scores(self, chunk_ids: List[str], user_id: str) -> Dict[str, float]:
        """Aggregate retrieval frequency + outcome signals from outcome metadata."""
        # Query outcomes where metadata->retrieved_chunk_ids contains each chunk ID
        # Normalize: 0.0 (never retrieved) to 1.0 (95th percentile)
        # Positive feedback bonus: +0.3, negative penalty: -0.2
        ...

    def _get_type_bonus(self, chunk_type: str) -> float:
        """Look up type bonus from config."""
        ...

    def _compute_importance(self, recency: float, retrieval: float, type_bonus: float) -> float:
        """Weighted composite: w_r * recency + w_t * retrieval + w_b * type_bonus."""
        ...
```

Key implementation details:
- Load weights from config (`importance.weights.recency`, etc.)
- Query outcome metadata: `SELECT metadata FROM outcomes WHERE user_id = ?` then parse `retrieved_chunk_ids` from each JSON blob to build per-chunk retrieval counts
- Normalize retrieval counts: divide by 95th percentile value (or max if <20 data points)
- Update `ChunkMetadata.confidence` with the new importance score via `database.update_chunk()`
- System chunks get `max(computed_score, 0.5)` floor
- Return stats: `{"scored": N, "avg_importance": X, "below_threshold": Y}`

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_importance.py -v --timeout=30
```
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add hestia/memory/importance.py
git commit -m "feat: ImportanceScorer — retrieval-feedback composite scoring"
```

### Task 4: Wire importance into search scoring

**Files:**
- Modify: `hestia/memory/manager.py:410-420`

- [ ] **Step 1: Apply importance multiplier in MemoryManager.search()**

In `manager.py`, after the import penalty and before temporal decay, multiply score by the chunk's importance (stored in `chunk.metadata.confidence`):

```python
# After line 414 (import penalty):
# Importance scoring (Sprint 16): boost by chunk importance
importance = chunk.metadata.confidence
if importance < 1.0:  # Only apply if scored (default 1.0 = unscored)
    score *= importance
```

This composes: `final = similarity * import_penalty * importance * decay * recency_boost`

- [ ] **Step 2: Add test for importance-weighted search**

In `tests/test_memory.py` or a new focused test, verify that a chunk with importance=0.5 scores lower than one with importance=1.0 at the same similarity.

- [ ] **Step 3: Run memory tests**

```bash
python -m pytest tests/test_memory.py -v --timeout=30 -k "importance or search"
```

- [ ] **Step 4: Commit**

```bash
git add hestia/memory/manager.py tests/test_memory.py
git commit -m "feat: apply importance multiplier in memory search scoring"
```

---

## Chunk 2: MemoryConsolidator

### Task 5: MemoryConsolidator — tests first

**Files:**
- Create: `tests/test_consolidator.py`

- [ ] **Step 1: Write failing tests**

Key test cases:
- `test_find_similar_pairs` — mock ChromaDB returns similar embeddings, consolidator detects pairs above 0.90 threshold
- `test_skip_different_types` — two chunks above 0.90 similarity but different chunk_types are skipped
- `test_preview_returns_candidates` — dry-run mode returns list without modifying anything
- `test_execute_marks_superseded` — lower-importance chunk gets SUPERSEDED status
- `test_execute_respects_cap` — with 100 candidates, only processes up to cap (50)
- `test_merge_strategy_interface` — verify MergeStrategy protocol is satisfied

Mock: `VectorStore` (for embedding queries), `MemoryDatabase` (for chunk operations), `MemoryManager.supersede_chunk()`.

- [ ] **Step 2: Run and verify failures**
- [ ] **Step 3: Commit tests**

### Task 6: MemoryConsolidator — implementation

**Files:**
- Create: `hestia/memory/consolidator.py`

- [ ] **Step 1: Implement MemoryConsolidator**

```python
class MergeStrategy(Protocol):
    """Pluggable merge strategy — non-LLM for M1, LLM for M5 Ultra."""
    def select_survivor(self, chunk_a: ConversationChunk, chunk_b: ConversationChunk) -> str:
        """Return ID of chunk to keep. Other gets SUPERSEDED."""
        ...

class ImportanceBasedMerge:
    """Default strategy: keep the higher-importance chunk."""
    def select_survivor(self, chunk_a, chunk_b):
        if chunk_a.metadata.confidence >= chunk_b.metadata.confidence:
            return chunk_a.id
        return chunk_b.id

class MemoryConsolidator:
    def __init__(self, memory_manager: Any, vector_store: Any, config: Dict, strategy: Optional[MergeStrategy] = None):
        self._manager = memory_manager
        self._vector_store = vector_store
        self._config = config
        self._strategy = strategy or ImportanceBasedMerge()

    async def find_candidates(self, sample_size: int = 50) -> List[Tuple[str, str, float]]:
        """Sample chunks, find pairs with >threshold similarity. Returns (id_a, id_b, score)."""
        # 1. Get sample_size random active chunk IDs from database
        # 2. For each, query ChromaDB for top-5 similar (excluding self)
        # 3. Filter: similarity > threshold AND (same session OR same chunk_type)
        # 4. Deduplicate pairs
        ...

    async def preview(self) -> Dict[str, Any]:
        """Dry-run: return candidate pairs without executing."""
        candidates = await self.find_candidates()
        return {"candidates": len(candidates), "pairs": candidates[:20]}

    async def execute(self, dry_run: bool = True) -> Dict[str, Any]:
        """Run consolidation. dry_run=True for preview only."""
        candidates = await self.find_candidates()
        if dry_run:
            return {"mode": "dry_run", "candidates": len(candidates)}

        merged = 0
        for id_a, id_b, sim_score in candidates:
            chunk_a = await self._manager.database.get_chunk(id_a)
            chunk_b = await self._manager.database.get_chunk(id_b)
            if not chunk_a or not chunk_b:
                continue
            survivor_id = self._strategy.select_survivor(chunk_a, chunk_b)
            loser = chunk_b if survivor_id == chunk_a.id else chunk_a
            loser.status = MemoryStatus.SUPERSEDED
            loser.supersedes = survivor_id  # Points to survivor
            await self._manager.database.update_chunk(loser)
            merged += 1

        return {"mode": "execute", "merged": merged, "candidates": len(candidates)}
```

Key details:
- Similarity threshold from config (default 0.90)
- Sample cap from config (default 50, per audit condition)
- ChromaDB query: use `vector_store.search_by_embedding()` with the chunk's own embedding
- Need to retrieve chunk embeddings from ChromaDB — add `get_embedding(chunk_id)` to VectorStore if not present

- [ ] **Step 2: Run tests**
- [ ] **Step 3: Commit**

```bash
git add hestia/memory/consolidator.py
git commit -m "feat: MemoryConsolidator — embedding-similarity dedup with pluggable merge"
```

---

## Chunk 3: MemoryPruner

### Task 7: MemoryPruner — tests first

**Files:**
- Create: `tests/test_pruner.py`

- [ ] **Step 1: Write failing tests**

Key test cases:
- `test_find_eligible` — chunks >60 days old with importance <0.2 are eligible
- `test_committed_chunks_excluded` — committed status chunks are never pruned
- `test_system_chunks_excluded` — system chunk_type never pruned
- `test_preview_returns_list` — preview mode returns eligible without modifying
- `test_execute_archives_chunks` — eligible chunks get ARCHIVED status
- `test_execute_deletes_from_chromadb` — ChromaDB delete called for archived chunks
- `test_undo_restores_chunk` — un-archive sets status back to previous

- [ ] **Step 2: Run and verify failures**
- [ ] **Step 3: Commit tests**

### Task 8: MemoryPruner — implementation

**Files:**
- Create: `hestia/memory/pruner.py`

- [ ] **Step 1: Implement MemoryPruner**

```python
class MemoryPruner:
    def __init__(self, memory_db: Any, vector_store: Any, learning_db: Any, config: Dict):
        ...

    async def find_eligible(self, user_id: str = "default") -> List[ConversationChunk]:
        """Find chunks eligible for pruning: old + low importance + not protected."""
        # Query: status IN ('active', 'staged') AND
        #        timestamp < (now - max_age_days) AND
        #        json_extract(metadata, '$.confidence') < importance_threshold AND
        #        chunk_type NOT IN ('system') AND
        #        status != 'committed'
        ...

    async def preview(self, user_id: str = "default") -> Dict[str, Any]:
        """Dry-run: list eligible chunks."""
        eligible = await self.find_eligible(user_id)
        return {"eligible": len(eligible), "chunks": [{"id": c.id, "type": c.chunk_type.value, "importance": c.metadata.confidence, "age_days": ...} for c in eligible[:50]]}

    async def execute(self, user_id: str = "default") -> Dict[str, Any]:
        """Archive eligible chunks + remove from ChromaDB."""
        eligible = await self.find_eligible(user_id)
        archived_ids = []
        for chunk in eligible:
            chunk.status = MemoryStatus.ARCHIVED
            await self._memory_db.update_chunk(chunk)
            archived_ids.append(chunk.id)

        # Batch delete from ChromaDB
        if archived_ids:
            self._vector_store.delete_chunks(archived_ids)

        # Log to learning DB for audit trail
        # ...

        return {"archived": len(archived_ids)}

    async def undo(self, chunk_ids: List[str]) -> int:
        """Restore archived chunks to ACTIVE status."""
        restored = 0
        for cid in chunk_ids:
            chunk = await self._memory_db.get_chunk(cid)
            if chunk and chunk.status == MemoryStatus.ARCHIVED:
                chunk.status = MemoryStatus.ACTIVE
                await self._memory_db.update_chunk(chunk)
                # Note: ChromaDB embedding is gone — would need re-embed to restore search
                restored += 1
        return restored
```

Config: `pruning.max_age_days` (default 60), `pruning.importance_threshold` (default 0.2).

- [ ] **Step 2: Run tests**
- [ ] **Step 3: Commit**

```bash
git add hestia/memory/pruner.py
git commit -m "feat: MemoryPruner — age+importance-gated soft-delete with undo"
```

---

## Chunk 4: API Endpoints + Scheduler Wiring

### Task 9: Pydantic schemas for new endpoints

**Files:**
- Modify: `hestia/api/schemas/memory.py` (or create if needed)

- [ ] **Step 1: Add response schemas**

```python
class ImportanceStatsResponse(BaseModel):
    scored: int
    avg_importance: float
    below_threshold: int
    distribution: Dict[str, int]  # {"0.0-0.2": N, "0.2-0.4": N, ...}

class ConsolidationPreviewResponse(BaseModel):
    candidates: int
    pairs: List[Dict[str, Any]]  # [{id_a, id_b, similarity, types}]

class ConsolidationExecuteResponse(BaseModel):
    mode: str  # "dry_run" or "execute"
    merged: int
    candidates: int

class PruningPreviewResponse(BaseModel):
    eligible: int
    chunks: List[Dict[str, Any]]  # [{id, type, importance, age_days}]

class PruningExecuteResponse(BaseModel):
    archived: int
```

- [ ] **Step 2: Commit**

### Task 10: API endpoints

**Files:**
- Modify: `hestia/api/routes/memory.py`

- [ ] **Step 1: Add 5 endpoints**

```python
# GET /v1/memory/importance-stats
# POST /v1/memory/consolidation/preview
# POST /v1/memory/consolidation/execute
# GET /v1/memory/pruning/preview
# POST /v1/memory/pruning/execute
```

Each endpoint: lazy-init the scorer/consolidator/pruner from singletons, call the appropriate method, return schema response. Follow existing route patterns (error handling with `sanitize_for_log`, JWT middleware).

- [ ] **Step 2: Register routes in `__init__.py` if new router needed**
- [ ] **Step 3: Run API smoke tests**
- [ ] **Step 4: Commit**

```bash
git add hestia/api/routes/memory.py hestia/api/schemas/memory.py
git commit -m "feat: 5 memory lifecycle API endpoints (importance, consolidation, pruning)"
```

### Task 11: Scheduler integration

**Files:**
- Modify: `hestia/learning/scheduler.py`

- [ ] **Step 1: Add importance/consolidation/pruning loops to LearningScheduler**

Add three new background loops after the existing three:
- `_importance_scorer_loop()` — nightly (86400s), runs `ImportanceScorer.score_all()`
- `_consolidation_loop()` — weekly (604800s), runs `MemoryConsolidator.execute(dry_run=False)`
- `_pruning_loop()` — weekly (604800s, 1h after consolidation), runs `MemoryPruner.execute()`

Stagger startup delays: importance at 240s, consolidation at 300s, pruning at 360s.

- [ ] **Step 2: Update trigger thresholds**

Add to `config/triggers.yaml`:
```yaml
    low_importance_ratio:
      value: 50
      direction: above
      message: "{value}% of chunks have importance below 0.3. Consider reviewing consolidation settings."
      cooldown_days: 14
```

- [ ] **Step 3: Commit**

```bash
git add hestia/learning/scheduler.py hestia/config/triggers.yaml
git commit -m "feat: schedule importance/consolidation/pruning in LearningScheduler"
```

### Task 12: Exports + integration wiring

**Files:**
- Modify: `hestia/memory/__init__.py`

- [ ] **Step 1: Export new classes**

Add `ImportanceScorer`, `MemoryConsolidator`, `MemoryPruner` to `__all__`.

- [ ] **Step 2: Update CLAUDE.md**

Add to project structure: `importance.py`, `consolidator.py`, `pruner.py` descriptions. Update endpoint count. Update test count.

- [ ] **Step 3: Update SPRINT.md**

Add Sprint 16 section at the top.

- [ ] **Step 4: Final test run**

```bash
python -m pytest tests/test_importance.py tests/test_consolidator.py tests/test_pruner.py tests/test_memory.py tests/test_learning.py -v --timeout=30
```

- [ ] **Step 5: Commit**

```bash
git add hestia/memory/__init__.py CLAUDE.md SPRINT.md
git commit -m "docs: Sprint 16 complete — update CLAUDE.md, SPRINT.md, exports"
```

---

## Execution Notes

**Total tasks:** 12 across 4 chunks
**Estimated effort:** ~10 hours
**Commit cadence:** One commit per task (12 commits)
**Half-time cut list:** If constrained, cut Chunk 2 (consolidator) and simplify Chunk 3 (pruner = age-only, no importance gate). Chunk 1 (importance scoring) is the core value.

**Testing strategy:**
- Each component has its own test file with mocked dependencies
- Integration test: score → consolidate → prune cycle on fixture data
- Memory search test: verify importance affects result ordering
- No Ollama needed — all SQL/embedding operations
