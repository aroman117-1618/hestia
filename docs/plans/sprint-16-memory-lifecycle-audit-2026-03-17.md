# Plan Audit: Sprint 16 — Memory Lifecycle

**Date:** 2026-03-17
**Plan Under Review:** `docs/discoveries/memory-lifecycle-importance-consolidation-pruning-2026-03-17.md`
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Build a 3-component memory lifecycle system: ImportanceScorer (nightly, retrieval-feedback composite score), MemoryConsolidator (weekly, embedding-similarity dedup), and MemoryPruner (weekly, age+importance-gated soft-delete). All SQL/embedding-based — no LLM inference. 5 new API endpoints. ~8 hours estimated.

---

## Phase 2: Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None | N/A |
| Family (2-5) | Yes | `DEFAULT_USER_ID` in scheduler needs per-user loops; importance scores are user-scoped via outcome metadata | Low — add user iteration to scheduler loops |
| Community | Partially | Consolidation cross-user is undefined; pruning policies may differ per user | Medium — needs per-user config + policy table |

**Assessment:** The plan correctly uses `user_id` scoping on all database operations (following Sprint 15 pattern). The only single-user assumption is the scheduler's `DEFAULT_USER_ID` constant — same pattern as the learning scheduler just shipped. Acceptable for current scale.

---

## Phase 3: Front-Line Engineering Review

**Feasibility:** High. All three components use proven patterns already in the codebase (soft-delete via MemoryStatus, supersede_chunk(), ChromaDB query/delete, SQL aggregation).

**Effort estimate:** 8 hours is **slightly optimistic**. Breakdown:
- ImportanceScorer: 2h (SQL aggregation from outcomes, score formula, batch update)
- MemoryConsolidator: 3h (ChromaDB pairwise similarity is the tricky part — need to sample efficiently, not O(n^2))
- MemoryPruner: 1.5h (straightforward status update + ChromaDB delete)
- API endpoints: 1.5h (5 endpoints, standard patterns)
- Tests: 2h (need outcome fixtures, mock ChromaDB similarity)
- **Revised estimate: 10h**

**Hidden prerequisites:**
1. **Migration for `access_count` + `last_accessed`** — the plan mentions these columns but doesn't scope the migration work. BaseDatabase supports migrations but the pattern varies across modules.
2. **Outcome data availability** — Sprint 15 landed today. There will be near-zero retrieval data by the time Sprint 16 executes. The fallback formula (type_bonus + recency) must be the default path, not the exception.
3. **ChromaDB pairwise similarity** — ChromaDB doesn't natively support "find all pairs above threshold." You'd need to query each chunk against the collection and filter. For 988 chunks, that's 988 queries. Need a sampling strategy.

**Testing strategy:** Mock ChromaDB for consolidation tests. Use fixture outcome records with known chunk IDs for importance scoring. Pruner tests need aged chunks (mock timestamps). Integration test: full cycle (score -> consolidate -> prune) on a small dataset.

**Developer experience:** Good. The memory module is well-structured and the patterns are established. The `supersede_chunk()` method is a proven template for consolidation.

---

## Phase 4: Backend Architecture Review

**Architecture fit:** Excellent. Three new files in `hestia/memory/` following the module pattern. Scheduler integration follows the learning scheduler pattern just shipped.

**API design:** Clean. Five endpoints under `/v1/memory/` with preview/execute split (dry-run safety). Consistent with existing patterns.

**Data model concern — `access_count` migration:**
The plan proposes adding `access_count INTEGER DEFAULT 0` and `last_accessed TEXT` to `memory_chunks`. This requires:
- SQLite ALTER TABLE (supported)
- Updating `MemoryDatabase._init_schema()` with migration logic
- Updating `search()` to increment access_count on retrieval

**Alternative:** Skip the migration entirely. Compute retrieval frequency from `outcome_metadata.retrieved_chunk_ids` at scoring time. This is a JOIN across outcomes + memory_chunks, but it avoids schema changes and uses the data source Sprint 15 already provides. The trade-off: slightly slower scoring query vs. zero migration risk.

**Recommendation:** Skip the migration. Use outcome metadata as the retrieval frequency source. Add `access_count` tracking later only if query performance becomes an issue.

**Integration points:**
- `MemoryManager.search()` — importance scoring composes with temporal decay
- `MemoryManager.build_context()` — already stashes chunk IDs (Sprint 15)
- `LearningScheduler` — add importance/consolidation/pruning loops
- `MemoryHealthMonitor` — wire `redundancy_estimate_pct` to consolidation stats

---

## Phase 5: Product Review

**User value:** Medium-high. No visible UI changes, but:
- Retrieval quality improves (higher-importance chunks surface first)
- The 988 Claude history chunks contain known redundancy that currently dilutes search
- Prerequisite for autonomy era (Sprints 19-22) — the learning cycle needs to close

**Edge cases:**
- **Empty memory:** ImportanceScorer no-ops. Consolidator/Pruner find nothing. Safe.
- **First-time user:** All chunks score at type_bonus + recency (fallback formula). Fine.
- **Single-chunk memory:** No pairs to consolidate. Pruner won't touch it (not old enough). Safe.

**Scope:** Right-sized for a backend sprint. Three well-scoped components, each independently testable and deployable.

**Opportunity cost:** We're not building Sprint 16 alternatives: UI memory browser, outcome-to-principle pipeline, or correction classifier. The discovery correctly defers these — the lifecycle system is the higher-leverage prerequisite.

---

## Phase 6: UX Review

**Skipped** — no UI component in this sprint. The 5 API endpoints are backend-only. A future UI sprint could add a memory health dashboard using these endpoints.

---

## Phase 7: Infrastructure Review

**Deployment impact:** Server restart required (new scheduler jobs). No database migration if we skip `access_count` columns (recommended). Config changes: add consolidation/pruning thresholds to `memory.yaml` or `triggers.yaml`.

**New dependencies:** None. All existing libraries (ChromaDB, SQLite, asyncio).

**Monitoring:** LearningScheduler already logs each run. New triggers in `triggers.yaml` (`low_importance_ratio`, `consolidation_candidates`) will fire alerts via the briefing injection just wired.

**Rollback strategy:** Strong. All operations are soft-delete (ARCHIVED/SUPERSEDED). Undo endpoint exists for pruning. Consolidation preserves originals. Worst case: set all ARCHIVED chunks back to COMMITTED.

**Resource impact on M1 (16GB):**
- ImportanceScorer: SQL aggregation, negligible CPU/memory
- MemoryConsolidator: ChromaDB similarity queries — needs sampling cap (100 chunks per run) to avoid memory pressure. 988 chunks × embedding dimension = ~4MB in memory if loaded at once.
- MemoryPruner: Batch SQL + ChromaDB delete, negligible

**Verdict:** Acceptable with sampling cap on consolidation.

---

## Phase 8: Executive Verdicts

### CISO Review
**Verdict: Acceptable**

No new attack surface. No new credential handling, external communication, or data exposure. Soft-delete preserves data (no information loss). The consolidation merge doesn't generate new content (keeps existing text, no LLM synthesis). Audit logging via LearningDatabase's trigger_log. One note: ensure pruning logs include the original chunk content hash for forensic recovery.

### CTO Review
**Verdict: Approve with Conditions**

Architecture is clean and well-scoped. The zero-LLM approach is the right call for M1. Two conditions:

1. **Skip `access_count` migration.** Use outcome metadata as the retrieval frequency source. Avoid schema changes in the most-queried table.
2. **Cap consolidation batch size.** The pairwise similarity approach is O(n*k) where k = sample size. Cap at 50-100 random samples per run. Don't attempt exhaustive comparison.

The importance scoring formula is well-designed, but the adaptive weight rebalancing (shifting when data is sparse) adds complexity. Consider starting with fixed weights and only implementing adaptive rebalancing if needed.

### CPO Review
**Verdict: Acceptable**

User value is indirect but real — retrieval quality improvement compounds over every conversation. The dry-run/preview pattern for consolidation and pruning is the right safety model. The 5 API endpoints position well for a future memory health dashboard.

Priority ordering is correct: importance scoring first (immediate retrieval benefit), consolidation second (dedup), pruning third (cleanup). This matches the dependency chain.

---

## Phase 9: Devil's Advocate

### 9.1 The Counter-Plan

**Alternative:** Instead of building three separate components, implement a single `MemoryRanker` that:
1. Recomputes chunk scores at query time (not nightly batch)
2. Uses `score = similarity * decay * type_bonus` (no retrieval frequency — avoid the cold-start problem)
3. Adds a `/v1/memory/cleanup` endpoint that manually triggers dedup + prune on demand

**Why it might be better:**
- Zero background jobs (no scheduler complexity)
- No stale scores (computed fresh each query)
- Simpler to implement (~4h vs 10h)
- No migration, no new scheduler, no batch processing

**Why the plan is better:**
- Query-time scoring adds latency to every search (~50ms for score computation)
- Retrieval frequency is a genuinely useful signal that the counter-plan discards
- On-demand cleanup means it never happens (human nature)
- The batch approach lets us run dry-runs and preview changes before committing

**Verdict:** The plan is stronger. The counter-plan trades capability for simplicity, but the capability (retrieval feedback) is the whole point of Sprint 15 → 16 continuity.

### 9.2 Future Regret Analysis

**3 months (June 2026):** The adaptive weight rebalancing logic may be more complex than needed. If retrieval data is still sparse, we'll be debugging weight-shifting edge cases. **Mitigation:** Start with fixed weights.

**6 months (September 2026):** M5 Ultra arrives. The careful "no LLM" constraint becomes unnecessary. We'll want to add LLM-based merge text for consolidation. The plan's architecture supports this (consolidator is a separate component), but we'll still be carrying the non-LLM merge logic as dead code. **Mitigation:** Design the consolidator with a pluggable merge strategy interface.

**12 months (March 2027):** The importance formula's fixed weights (0.3/0.4/0.3) may not be optimal. We'll wish we had A/B testing infrastructure to tune them. **Mitigation:** Make weights configurable in `memory.yaml`.

### 9.3 The Uncomfortable Questions

**"Do we actually need this?"**
Yes, but not urgently. The 988 imported chunks have measurable redundancy, and retrieval quality will degrade as conversations accumulate. The question is timing — building now vs. waiting for more outcome data. Building now is slightly premature but the infrastructure cost is low.

**"Are we building this because it's valuable, or because it's interesting?"**
Honest answer: 60% valuable, 40% interesting. The importance scoring is genuinely valuable. The consolidation and pruning are more speculative — they solve a problem that's ~6 months away. But the effort is modest (10h) and the risk is low (all reversible).

**"What's the cost of doing nothing?"**
Low in the short term. ChromaDB handles 10K+ chunks fine. Retrieval quality degrades gradually, not catastrophically. The real cost of waiting is that Sprint 15's retrieval feedback data goes unused — we collected it but don't act on it.

**"Who benefits?"**
Andrew, immediately — better retrieval quality from importance-scored search. Future Hestia, significantly — the lifecycle system is prerequisite for the autonomy era sprints.

### 9.4 Final Stress Tests

**1. Most likely failure:** Consolidation produces false positives — merges chunks that are semantically similar but contextually distinct (same topic, different decisions). **Mitigation:** 0.90 threshold (conservative), same-session OR same-type constraint, dry-run default, SUPERSEDED preserves originals.

**2. Critical assumption:** "Sprint 15 retrieval feedback provides sufficient signal for importance scoring." If outcome data is too sparse (few `retrieved_chunk_ids` entries), the importance scorer degrades to type_bonus + recency, which is barely different from existing temporal decay. **Validation:** Before implementation, query outcome metadata to count how many unique chunk IDs have retrieval data. If <100, defer retrieval_score to Sprint 17 and ship type_bonus + recency only.

**3. Half-time cut list:** If we had 5 hours instead of 10:
- **Keep:** ImportanceScorer (the core value proposition)
- **Keep:** 2 API endpoints (importance-stats + pruning/preview)
- **Cut:** MemoryConsolidator (defer to Sprint 17 — dedup is lower priority than scoring)
- **Cut:** Monthly compaction (nice-to-have, not essential)
- **Simplify:** Pruner uses fixed age threshold only (no importance gate)

---

## Conditions for Approval

1. **Skip `access_count`/`last_accessed` migration.** Compute retrieval frequency from outcome metadata instead. Revisit only if query performance is measurably impacted.

2. **Start with fixed importance weights** (no adaptive rebalancing). The sparse-data fallback formula adds complexity for a scenario that's temporary. Use `(0.3 * recency) + (0.4 * retrieval_score) + (0.3 * type_bonus)` as-is, with retrieval_score defaulting to 0.0 when data is absent.

3. **Cap consolidation at 50 random samples per run.** Do not attempt exhaustive pairwise comparison. Scale the sample size with chunk count if needed later.

4. **Make importance weights configurable** in `memory.yaml`. Don't hardcode 0.3/0.4/0.3.

5. **Validate retrieval data density before implementation.** Query outcome metadata: `SELECT COUNT(DISTINCT json_extract(metadata, '$.retrieved_chunk_ids')) FROM outcomes`. If <50 records, defer retrieval_score component and ship type_bonus + recency only as v1.

6. **Design consolidator with pluggable merge strategy** (interface/protocol). The non-LLM strategy is Sprint 16; the LLM strategy drops in on M5 Ultra without refactoring.
