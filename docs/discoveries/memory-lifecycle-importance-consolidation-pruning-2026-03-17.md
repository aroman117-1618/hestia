# Discovery Report: Sprint 16 — Memory Lifecycle (Importance Scoring, Consolidation, Pruning)

**Date:** 2026-03-17
**Confidence:** High
**Decision:** Build a 3-layer memory lifecycle system: retrieval-feedback importance scoring, embedding-similarity consolidation, and age+importance-gated pruning — all operating on existing SQLite + ChromaDB without new infrastructure.

## Hypothesis

Hestia's memory system stores chunks indefinitely with no mechanism to rank, merge, or remove them. As chunk count grows (currently ~988 imported + ongoing conversation history), retrieval quality will degrade — important memories compete equally with trivial ones, near-duplicates dilute search results, and ChromaDB's HNSW index bloats without reclamation. Sprint 16 should add importance scoring (using retrieval feedback from Sprint 15), consolidation (merge near-duplicate chunks), and pruning (remove low-value chunks) to create a self-maintaining memory system.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Sprint 15 already wired retrieval feedback loop (`_last_retrieved_chunk_ids` + outcome metadata). Temporal decay infrastructure exists. MemoryHealthMonitor collects chunk counts and source distribution. Outcome tracker captures implicit/explicit quality signals. `ChunkMetadata.confidence` field exists but is unused (always 1.0). `MemoryStatus` enum already has SUPERSEDED/ARCHIVED states. Source dedup table exists for import tracking. | **Weaknesses:** No importance score on chunks today — confidence field is static. ChromaDB HNSW index never shrinks (delete doesn't reclaim space). No similarity detection between chunks. MemoryHealthMonitor's `redundancy_estimate_pct` is a placeholder (always 0.0). Memory database has no `access_count` or `last_accessed` tracking. No batch operations for bulk status changes. |
| **External** | **Opportunities:** Mem0 research shows 26% accuracy boost from importance-scored retrieval. Industry consolidation (0.85 similarity threshold) cuts storage 60% and raises precision 22%. Graphiti's bi-temporal model already partially implemented in research module — patterns transferable. Sprint 15 data accumulating now — by Sprint 16 execution, there should be meaningful outcome/retrieval data. | **Threats:** LLM-based importance scoring adds inference overhead per chunk (M1 constraint). Aggressive pruning could delete memories that become relevant later (irreversible). ChromaDB re-indexing (the only way to reclaim HNSW space) requires collection recreation — downtime risk. Over-consolidation could merge distinct memories that share vocabulary but differ in context. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Importance scoring (retrieval count + outcome signal composite). Consolidation via embedding similarity detection + merge. Age+importance pruning with dry-run safety. | `access_count` / `last_accessed` columns on memory_chunks (tracking infrastructure). |
| **Low Priority** | ChromaDB collection compaction (recreate to reclaim HNSW space) — schedule monthly. Outcome-to-Principle pipeline (deferred from Sprint 15). | Correction classification (CorrectionType enum exists, classifier deferred). LLM-based importance re-evaluation (expensive, defer to M5 Ultra). |

## Argue (Best Case)

**Evidence supporting this approach:**

1. **Retrieval feedback loop is already wired.** Sprint 15 stashes chunk IDs in outcome metadata. Every chat response already records which chunks were retrieved and whether the user was satisfied (implicit signal). This is free signal — we just need to aggregate it.

2. **Industry validation is strong.** Mem0's research demonstrates 26% retrieval accuracy improvement from importance scoring. The Chroma Cookbook documents consolidation at 0.85 similarity threshold achieving 60% storage reduction and 22% precision improvement. These are production systems, not academic papers.

3. **Existing infrastructure supports this.** `ChunkMetadata.confidence` (currently always 1.0) can be repurposed as the importance score with zero schema migration. `MemoryStatus.ARCHIVED` exists for pruned chunks. The `source_dedup` table pattern shows the codebase handles dedup tracking well.

4. **The M1 can handle this.** Importance scoring is pure SQL aggregation (no inference). Consolidation uses ChromaDB's existing embeddings for similarity detection (no new embedding generation). Pruning is a batch SQL + ChromaDB delete operation. None of these require LLM inference.

5. **Safety is achievable.** Soft-delete via `MemoryStatus.ARCHIVED` (not hard delete) means pruning is reversible. Consolidation creates a new merged chunk and marks originals as SUPERSEDED (existing pattern from `supersede_chunk()`). Dry-run mode lets Andrew review before committing.

**Upside scenario:** Memory retrieval precision improves measurably (outcome positive_ratio increases). ChromaDB stays lean. Context windows are filled with higher-quality memories. The learning module (Sprint 15) can now close the feedback loop — it observes, and now the system acts.

## Refute (Devil's Advocate)

**Strongest arguments against:**

1. **Premature optimization.** With ~988 imported chunks + maybe a few hundred from conversations, the memory system isn't under stress yet. ChromaDB handles 10K+ chunks fine. The M5 Ultra upgrade (summer 2026) will make this even less urgent. Are we solving a problem that doesn't exist yet?

   *Counter:* The point isn't to solve a crisis — it's to build the infrastructure before it's needed. Importance scoring improves retrieval quality NOW regardless of chunk count. And the 988 Claude history chunks include significant redundancy that currently dilutes search results.

2. **Consolidation is dangerous.** Merging chunks loses context. Two chunks about "security" from different conversations have different temporal context, different decisions being made, different participants. An averaged embedding and merged text flattens this nuance.

   *Counter:* Consolidation should only merge chunks with >0.90 embedding similarity AND the same session OR same chunk_type. This is a conservative threshold that catches true duplicates (e.g., re-imported content, repeated questions) without merging contextually distinct memories. Additionally, originals are kept as SUPERSEDED, not deleted.

3. **Importance scoring could create filter bubbles.** If we boost chunks that get retrieved often, they get retrieved more, which boosts them more. Rarely-retrieved but important chunks (facts, decisions) get buried.

   *Counter:* The formula weights retrieval count at only 30%, with chunk_type weight at 40% (facts/decisions get innate bonus) and recency at 30%. Facts and system chunks have decay rate 0.0 and get importance floor = 0.5. The formula is designed to prevent this exact failure mode.

4. **ChromaDB HNSW never shrinks.** Even after pruning chunks from SQLite, the HNSW index retains memory for deleted vectors. True space reclamation requires collection recreation.

   *Counter:* This is a real limitation but not a blocker. We do soft-delete (ARCHIVED status) in SQLite and stop returning those chunks in queries. ChromaDB hard-delete removes them from search results even if HNSW space isn't reclaimed. Monthly compaction (collection recreate) handles the rest as a maintenance task.

## Third-Party Evidence

### Mem0 (Production memory system)
Mem0's architecture uses a composite importance score: `importance = 0.3 * recency + 0.4 * usage_frequency + 0.3 * confidence`. Their research paper reports 26% accuracy improvement on retrieval benchmarks. They prune memories below a configurable floor (default 0.1) after 90 days.

### Graphiti / Zep (Temporal knowledge graphs)
Graphiti uses a dual-stream approach: fast ingestion stream + async consolidation stream. New entries go into both global memory and a buffer. Obsolete or low-value traces are periodically pruned. Their bi-temporal model (valid_at/invalid_at) — which Hestia already partially implements in the research module — enables "soft invalidation" without data loss.

### MemGPT / Letta (Memory-augmented LLMs)
MemGPT uses hierarchical memory with explicit compaction: main context (working memory) overflows into archival storage, which is periodically compacted. Their compaction is LLM-driven (summarization), which is expensive but produces high-quality consolidated memories.

### EverMem (Persistent AI Agent OS, March 2026)
EverMem uses FAISS + SQLite with automated memory consolidation. Their approach: cluster embeddings, detect near-duplicates (>0.85 cosine similarity), merge via LLM conflict resolution, then deduplicate clusters at 0.9 threshold. Reports 60% storage reduction.

### Alternative approach considered: LLM-based importance scoring
Instead of SQL aggregation, use the LLM to evaluate each chunk's importance (1-10 scale). This is how MemGPT and some academic systems work. **Rejected for Hestia** because: (a) M1 can't afford per-chunk inference at scale, (b) retrieval feedback provides a stronger signal than LLM judgment, (c) we already have outcome data. Reserve LLM-based evaluation for the M5 Ultra era.

### Alternative approach considered: Graph-based consolidation
Use the knowledge graph (research module) to identify redundant memories by entity overlap. **Deferred** because: (a) knowledge graph is on-demand, not comprehensive, (b) entity coverage is sparse, (c) embedding similarity is simpler and more reliable for this use case.

## Recommendation

Build Sprint 16 as a 3-component system within `hestia/memory/`:

### Component 1: ImportanceScorer (`importance.py`)
- **Formula:** `importance = (0.3 * recency_score) + (0.4 * retrieval_score) + (0.3 * type_bonus)`
  - `recency_score`: 1.0 for <7 days, linear decay to 0.2 at 90 days, 0.1 floor
  - `retrieval_score`: normalized retrieval count from outcome metadata (0.0 if never retrieved, 1.0 at 95th percentile). Explicit positive feedback = +0.3 bonus. Negative feedback = -0.2 penalty.
  - `type_bonus`: fact=0.8, decision=0.7, preference=0.6, research=0.5, insight=0.8, action_item=0.4, conversation=0.3, system=1.0
- **Storage:** Repurpose `ChunkMetadata.confidence` field as importance score (rename in code, no schema change needed since it's stored as JSON)
- **Schedule:** Run nightly via APScheduler (batch score all active chunks)
- **New columns on memory_chunks:** `access_count INTEGER DEFAULT 0`, `last_accessed TEXT` (migration)

### Component 2: MemoryConsolidator (`consolidator.py`)
- **Detection:** Sample N random chunks, compute pairwise embedding similarity via ChromaDB. Flag pairs with cosine similarity >0.90 AND (same session OR same chunk_type).
- **Merge strategy:** Keep the higher-importance chunk as the survivor. Mark the lower one as SUPERSEDED with `supersedes` pointing to survivor. If both have unique content (different entities/topics in tags), skip merge.
- **No LLM involved.** Pure embedding + metadata comparison. LLM-based merge text generation deferred to M5 Ultra.
- **Schedule:** Run weekly. Cap at 100 merges per run to bound execution time.
- **Dry-run mode:** Default first run produces a report without making changes. API endpoint to review and approve.

### Component 3: MemoryPruner (`pruner.py`)
- **Eligibility:** Chunks older than 60 days AND importance score < 0.2 AND not in status [committed, system].
- **Action:** Set status to ARCHIVED (soft delete). Remove from ChromaDB search results via metadata filter.
- **Monthly compaction:** Optional ChromaDB collection recreation (backup -> recreate -> re-add non-archived chunks). Manual trigger only.
- **Safety:** Pruning log in learning.db (chunk_id, previous_importance, pruned_at). Undo endpoint to un-archive.
- **Schedule:** Run weekly, after consolidation.

### API Endpoints (5 new under `/v1/memory/`)
1. `GET /v1/memory/importance-stats` — distribution of importance scores
2. `POST /v1/memory/consolidation/preview` — dry-run consolidation report
3. `POST /v1/memory/consolidation/execute` — run consolidation
4. `GET /v1/memory/pruning/preview` — chunks eligible for pruning
5. `POST /v1/memory/pruning/execute` — run pruning (with undo window)

### Integration with Sprint 15
- ImportanceScorer reads from outcome metadata's `retrieved_chunk_ids` to compute retrieval frequency
- MemoryHealthMonitor's `redundancy_estimate_pct` placeholder gets wired to MemoryConsolidator's similarity detection
- TriggerMonitor gets new thresholds: `low_importance_ratio` (>50% chunks below 0.3) and `consolidation_candidates` (>100 pairs above 0.90 similarity)

**Confidence: High.** The approach uses existing infrastructure, avoids LLM inference overhead, follows industry-validated patterns, and is fully reversible via soft-delete.

**What would change this recommendation:**
- If chunk count stays below 500 for months, deprioritize consolidation/pruning (importance scoring still valuable)
- If M5 Ultra arrives before Sprint 16 execution, consider adding LLM-based merge text generation to consolidation
- If outcome data quality is poor (insufficient signals), importance scoring falls back to type_bonus + recency only

## Final Critiques

### The Skeptic: "Why won't this work?"

*Challenge:* The retrieval feedback loop has been live for less than a week. You don't have enough outcome data to compute meaningful retrieval scores. The importance scorer will be running on insufficient data, producing scores that are mostly just type_bonus + recency — which is barely different from temporal decay that already exists.

*Response:* Valid concern. The implementation should degrade gracefully: when retrieval_score has <20 data points for a chunk, weight shifts to `(0.45 * recency) + (0.1 * retrieval) + (0.45 * type_bonus)`. As data accumulates, weights rebalance toward the target formula. The system improves with usage rather than requiring a cold-start dataset. And even the fallback formula (type_bonus + recency) is an improvement over the current system where all chunks have confidence=1.0.

### The Pragmatist: "Is the effort worth it?"

*Challenge:* This is a backend-only sprint with no user-visible UI changes. Andrew gets no new features to interact with. The memory system works fine today — is polishing the internals the best use of 12 hours?

*Response:* The 5 new API endpoints enable future Command Center metrics (memory health dashboard). More importantly, this is prerequisite infrastructure for the autonomy era (Sprints 19-22). Without importance scoring, the learning cycle can't close — Sprint 15 observes but Sprint 16 acts. Also, the 988 Claude history chunks are known to contain redundancy that currently dilutes search quality. Estimated effort: ~8 hours (no UI, no iOS, well-scoped backend patterns).

### The Long-Term Thinker: "What happens in 6 months?"

*Challenge:* By September 2026, you'll have the M5 Ultra with 192GB RAM. ChromaDB performance won't be a concern. The careful pruning and consolidation logic built for M1 constraints becomes over-engineering for M5 Ultra capabilities.

*Response:* The importance scoring infrastructure transfers directly — it's about retrieval quality, not resource constraints. Consolidation and pruning logic remains valuable even on M5 Ultra (deduplication improves precision regardless of hardware). What changes is the merge strategy: M5 Ultra enables LLM-based merge text generation, which produces higher-quality consolidated chunks. The Sprint 16 framework is designed to be extended with LLM merge as a drop-in upgrade. The conservative non-LLM approach built now becomes the fast fallback path.

## Open Questions

1. **Should importance scores be visible in the iOS/macOS memory UI?** Currently no memory browser exists in the app. If one is planned, importance scores would be useful sort/filter criteria. Defer to UI sprint.

2. **Should consolidation affect the knowledge graph?** When two chunks are merged, should entities/facts extracted from both be re-linked to the survivor chunk? Currently no — the research module operates independently. Revisit when graph coverage improves.

3. **What's the right consolidation similarity threshold?** Industry uses 0.85-0.90. Starting at 0.90 (conservative) with a config knob in memory.yaml. Tune based on dry-run results.

4. **Should pruning affect ChromaDB immediately or batch?** Immediate per-chunk delete is simple but HNSW space isn't reclaimed. Batch monthly compaction is thorough but requires downtime. Recommendation: immediate delete for search quality, monthly compaction for space (manual trigger).

5. **Interaction with temporal decay.** Importance scoring and temporal decay both modify retrieval ranking. Should they compose (multiply) or should importance replace decay? Recommendation: compose — `final_score = raw_similarity * decay_factor * importance_weight`. This means importance is a multiplier on the existing decay-adjusted score, not a replacement.

---

*Research sources:*
- [Mem0 Research: 26% Accuracy Boost](https://mem0.ai/research)
- [Memory in the Age of AI Agents (arXiv, Dec 2025)](https://arxiv.org/abs/2512.13564)
- [Graphiti: Knowledge Graph Memory (Neo4j)](https://neo4j.com/blog/developer/graphiti-knowledge-graph-memory/)
- [Zep: Temporal Knowledge Graph Architecture (arXiv)](https://arxiv.org/abs/2501.13956)
- [ChromaDB Memory Management Cookbook](https://cookbook.chromadb.dev/strategies/memory-management/)
- [EverMem: Persistent AI Agent OS (March 2026)](https://earezki.com/ai-news/2026-03-04-how-to-build-an-evermem-style-persistent-ai-agent-os-with-hierarchical-memory-faiss-vector-retrieval-sqlite-storage-and-automated-memory-consolidation/)
- [6 Best AI Agent Memory Frameworks (2026)](https://machinelearningmastery.com/the-6-best-ai-agent-memory-frameworks-you-should-try-in-2026/)
- [MAGMA: Multi-Graph Agentic Memory Architecture](https://arxiv.org/html/2601.03236v1)
