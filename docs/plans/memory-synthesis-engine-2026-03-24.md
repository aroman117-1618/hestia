# Plan: Memory Synthesis Engine (Auto-Dream for Hestia)

**Date:** 2026-03-24
**Sprint:** S-MEM (Memory Synthesis — between-sprint work)
**Discovery:** `docs/discoveries/memory-synthesis-engine-2026-03-24.md`
**Estimated effort:** 12-16h (Phase 1: 8h, Phase 2: 4-8h)
**Priority:** Medium — fits between trading sprints or as autonomous Claude Code task
**Status:** PLANNED

## Motivation

Hestia has three knowledge stores that barely communicate:
1. **Memory** (ChromaDB + SQLite) — episodic chunks with importance scores
2. **PrincipleStore** (ChromaDB + SQLite) — distilled behavioral rules, pending approval
3. **Knowledge Graph** (SQLite) — entity-relationship facts with temporal metadata

Current cross-links are one-directional: ImportanceScorer reads KG durability, PrincipleStore distills from memory, crystallization promotes ephemeral facts. No feedback loops, no cross-store synthesis.

Inspired by Claude Code's unreleased "auto-dream" feature (periodic memory consolidation), this plan creates a Memory Cross-Pollination Loop that wires these stores together into a self-reinforcing learning cycle.

## Architecture

```
Chat Sessions → Memory Chunks
       ↓
[Existing] Consolidator (dedup >0.90 similarity)
[Existing] Pruner (>60d + low importance → archive)
       ↓
[NEW] MemorySynthesizer (Phase 2 only)
  • Groups thematically related chunks (0.70-0.89 similarity band)
  • SLM screening (qwen2.5:0.5b) → full model for confirmed candidates
  • Stores as chunk_type="synthesis" with higher importance floor
       ↓
[NEW] CrossPollinationLoop (Phase 1)
  • Principle → Memory feedback (importance boosts)
  • Fact cluster → Principle suggestion
  • Outcome → Fact confidence feedback
  • Embedding cross-domain detection
       ↓
[Upgraded] OutcomeDistiller + FactExtractor
  • Feed from synthesis chunks (Phase 2)
  • Broader coverage, higher quality
       ↓
PrincipleStore → Graph View (macOS SceneKit)
Knowledge Graph → Graph View
```

## Phase 1: Cross-Pollination Loop (8h, no new LLM calls)

Pure SQL/embedding wiring — creates feedback loops between existing stores.

### WS1: Principle → Memory Feedback (2h)
**File:** `hestia/learning/cross_pollination.py` (new)

- Query all APPROVED principles from PrincipleStore
- For each, look up `source_chunk_ids` in the principles table
- Boost those memory chunks' importance scores by +0.1 (capped at 1.0)
- Log adjustments to learning_db audit trail
- Schedule: nightly, after ImportanceScorer

**Why:** Source chunks that produced valuable (approved) principles should be preserved longer and retrieved more often. Currently, a chunk that generated a great principle gets no credit.

### WS2: Outcome → Fact Confidence Feedback (2h)
**File:** `hestia/learning/cross_pollination.py`

- Query outcomes with positive signals (user thumbs up, explicit confirmation)
- Find linked memory chunks via outcome metadata
- Find facts extracted from those chunks (match by source_chunk_id or temporal proximity)
- Boost fact confidence by +0.05 (capped at 1.0)
- Schedule: nightly, after outcome processing

**Why:** Facts that contributed to good responses should gain confidence. Currently, fact confidence is static after extraction.

### WS3: Fact Cluster → Principle Suggestion (2h)
**File:** `hestia/learning/cross_pollination.py`

- Query active facts grouped by (source_entity_id, target_entity_id) pairs
- Identify clusters of 3+ facts between the same entity pair
- For each cluster, check PrincipleStore for existing principle covering this domain
- If no existing principle, create a synthesis candidate record (new table: `synthesis_candidates`)
- Schedule: weekly, after fact extraction

**Why:** Repeated facts between the same entities suggest an underlying pattern worth codifying as a principle. E.g., 5 facts about "Andrew → USES → pytest" should generate a testing preferences principle.

### WS4: Scheduler Integration + Tests (2h)
**File:** `hestia/learning/scheduler.py` (modify), `tests/test_cross_pollination.py` (new)

- Add `CrossPollinationLoop` as 11th monitor in LearningScheduler
- Nightly cadence for WS1+WS2, weekly for WS3
- 15 unit tests covering each feedback path
- Integration test: end-to-end from approved principle → boosted chunk importance

## Phase 2: Embedding Synthesis (4-8h, requires LLM)

### WS5: Similarity-Band Grouping (3h)
**File:** `hestia/memory/synthesizer.py` (new)

- Query ChromaDB for chunks in the 0.70-0.89 similarity band (thematically related but not duplicates)
- Group into clusters using single-linkage clustering
- Filter clusters spanning 2+ chunk_types (cross-domain signal)
- Cap at 10 clusters per run

**Why:** The 0.70-0.89 band is the sweet spot — too similar (>0.90) and the Consolidator already handles it, too different (<0.70) and it's noise.

### WS6: LLM Synthesis Pass (3h)
**File:** `hestia/memory/synthesizer.py`

- For each cluster, use tiered model cascade:
  - SLM (qwen2.5:0.5b): "Is this cluster worth synthesizing?" (yes/no, ~100ms)
  - Full model (qwen3.5:9b): Generate synthesis summary + extract entities/topics
- Store as new `ConversationChunk` with `chunk_type="synthesis"`, `source_chunk_ids=[...]`
- Importance floor: 0.6 (higher than regular chunks)

### WS7: Distiller/Extractor Upgrade + Tests (2h)
**Files:** `hestia/research/principle_store.py`, `hestia/research/fact_extractor.py`, `tests/test_synthesizer.py`

- Modify `distill_principles()` to prefer synthesis chunks over raw chunks
- Modify fact extraction to use synthesis chunks as supplementary input
- 10 unit tests for synthesizer, 5 integration tests for upgraded distiller

## Graph View Impact

Three visible improvements in the macOS Research graph (no frontend code changes needed):

1. **Richer principle nodes** — Principles distilled from thematic summaries (not random chunks) → more meaningful approval queue
2. **Higher-confidence fact edges** — Facts backed by positive outcomes get confidence boosts → graph shows more stable knowledge
3. **Better entity clustering** — Synthesis pre-extracts entities → EntityRegistry gets cleaner input → communities become more coherent

## Acceptance Criteria

### Phase 1
- [ ] Approved principles boost source chunk importance (verified via SQL query)
- [ ] Positive outcomes boost linked fact confidence (verified via SQL query)
- [ ] Fact clusters of 3+ generate synthesis candidates (verified via new table)
- [ ] CrossPollinationLoop runs on LearningScheduler nightly/weekly cadence
- [ ] All tests pass, including 15+ new tests
- [ ] No regression in existing memory/research tests

### Phase 2
- [ ] Similarity-band grouping identifies cross-domain clusters
- [ ] SLM screening filters trivial clusters (>50% rejection rate)
- [ ] Synthesis chunks created with proper provenance (source_chunk_ids)
- [ ] OutcomeDistiller prefers synthesis chunks
- [ ] No chat latency impact during synthesis (runs idle-time only)
- [ ] 15+ new tests passing

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Banality trap (trivial principles) | Quality gate: MIN_PRINCIPLE_WORDS=10, generic blacklist, SLM screening |
| M1 resource contention during synthesis | Tiered model cascade, idle-time scheduling, 2-hour startup delay |
| Incorrect cross-domain linking | Source provenance preserved, principles require approval, facts keep source_chunk_ids |
| Principle approval queue overflow | Future: auto-approval for confidence >0.85 in existing approved domains |
| Over-consolidation losing specifics | Never delete source chunks — synthesis creates new derived chunks |

## Dependencies

- None on active trading sprints (S27.5, S28)
- No new Python packages required
- No API endpoint changes (graph view improvements are automatic)
- No Swift/UI changes needed

## Schedule

Phase 1 is a "between sprints" or autonomous task — no dependency on trading work.
Phase 2 can wait until after S28 (regime detection) or M5 Ultra hardware upgrade.

| Phase | Hours | Target | Depends On |
|-------|-------|--------|------------|
| Phase 1 (cross-pollination) | 8h | Next available between-sprint slot | Nothing |
| Phase 2 (LLM synthesis) | 4-8h | After S28 or M5 Ultra | Phase 1 complete |
