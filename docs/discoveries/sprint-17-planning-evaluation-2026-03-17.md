# Discovery Report: Sprint 17 Planning — Candidate Evaluation & Sequencing

**Date:** 2026-03-17
**Confidence:** High
**Decision:** Sprint 17 should be a focused **Correction Classifier + Outcome-to-Principle Pipeline** sprint (the "Learning Closure" sprint), deferring all three UI candidates. The two backend features compose naturally, close the Sprint 15-16 learning loop, and avoid the data-starved trap that would hobble UI-heavy sprints.

## Hypothesis

*Which of the 5 Sprint 17 candidates should be selected, and in what sequence, to maximize value given the current system state: near-zero retrieval density, M1 constraints, and the Sprint 15-16 learning arc?*

## Candidates Under Evaluation

| # | Candidate | Type | Estimated Effort |
|---|-----------|------|-----------------|
| C1 | Outcome-to-Principle pipeline | Backend (LLM) | 6-8h |
| C2 | Correction Classifier | Backend (heuristic + optional LLM) | 4-6h |
| C3 | Memory UI Browser | Frontend (iOS + macOS) | 8-12h |
| C4 | Command Center Redesign | Frontend (macOS) | 8-10h |
| C5 | Neural Net Graph Phase 2 | Frontend (macOS) + Backend | 6-8h |

## Critical Context: Data Readiness

The session handoff flagged a critical validation query:

```sql
SELECT COUNT(*) FROM outcomes WHERE json_extract(metadata, '$.retrieved_chunk_ids') IS NOT NULL
```

This query has NOT been run against the live DB yet (handoff item #4). The retrieval feedback loop (Sprint 15) has been live for approximately 1 day. This means:

- **Importance scoring** is currently operating on type_bonus + recency only (retrieval weight is effectively 0)
- **MetaMonitor** likely returns `INSUFFICIENT_DATA` status (MIN_SAMPLE_SIZE = 20 outcomes)
- **No principles have been distilled** from outcomes (the pipeline doesn't exist yet)
- **No corrections have been classified** (CorrectionType enum exists but no classifier)

**Implication:** Any UI that visualizes learning data (Memory Browser, Command Center metrics) will show empty or near-empty states. Building UI for data that doesn't exist yet is premature.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Sprint 15-16 built the observe+act infrastructure. Outcome tracking is wired into every chat response. Retrieval feedback loop stashes chunk IDs. ImportanceScorer, Consolidator, and Pruner all run on schedule. CorrectionType enum is pre-defined (4 types). PrincipleStore has distillation prompt + ChromaDB storage ready. Learning scheduler has 6 background loops. | **Weaknesses:** Zero retrieval data density (feedback loop live ~1 day). No corrections detected or classified. No principles distilled from outcomes. Memory UI has no existing iOS/macOS foundation (would be built from scratch). Command Center shows static data (hero + calendar + orders + newsfeed). Neural Net graph has uncommitted parallel-session work creating merge risk. |
| **External** | **Opportunities:** Closing the learning loop (observe -> classify -> distill) completes the Intelligence era before the Autonomy era. Industry trend (ICLR 2026 MemAgents workshop, Mem0, Graphiti) shows consolidation → distillation pipelines are the differentiator. Correction classification enables self-improvement without LLM overhead. | **Threats:** LLM-dependent principle distillation adds inference cost on M1. Over-engineering the learning pipeline before sufficient data exists. Splitting focus across backend + frontend in one sprint risks incomplete delivery. The parallel session's uncommitted orchestration changes may conflict with handler.py modifications. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **C2: Correction Classifier** — enables the learning loop to detect specific failure modes. Zero LLM cost. Feeds MetaMonitor with actionable data. **C1: Outcome-to-Principle** — closes observe->act->learn loop. Principles influence future responses via PrincipleStore. | **C5: Neural Net Phase 2** — graph mode switching wires existing backend to existing frontend. But blocked by uncommitted parallel work. |
| **Low Priority** | **C3: Memory Browser** — high utility but premature (no importance data to show yet). **C4: Command Center Redesign** — contextual metrics need MetaMonitor data to be meaningful. | Adding more UI polish before the backend learning loop is closed. |

## Candidate Deep Dives

### C1: Outcome-to-Principle Pipeline

**What it is:** Auto-distill behavioral principles from tracked outcomes. When enough positive outcomes accumulate around a pattern, extract a reusable principle via LLM and store it in PrincipleStore.

**Prerequisites satisfied:**
- OutcomeManager tracks every chat response (Sprint 10)
- PrincipleStore exists with `distill_principles()` method and DISTILLATION_PROMPT (Sprint 11.5)
- ChromaDB `hestia_principles` collection is initialized
- ResearchDatabase has `create_principle()`, `list_principles()`, `update_principle_status()`
- Daily auto-distill scheduler exists (Sprint 11.5 A7)

**What's missing:**
- The daily auto-distill currently runs on ALL memory chunks, not filtered by outcome quality
- No outcome-aware filtering: "distill from chunks that were retrieved in positive-outcome conversations"
- No dedup against existing principles (could re-distill the same principle repeatedly)
- No feedback integration: principles should be weighted by outcome positive_ratio

**Implementation scope:**
1. `OutcomePrincipleDistiller` class in `hestia/learning/` (~150 lines)
2. Filter outcomes by positive_ratio > 0.6, extract their `retrieved_chunk_ids`
3. Feed those chunks to `PrincipleStore.distill_principles()`
4. Dedup via semantic similarity against existing principles (ChromaDB query)
5. Schedule weekly via LearningScheduler (after importance scoring)
6. 1 new API endpoint: `POST /v1/learning/distill-principles` (manual trigger)

**Risk:** LLM inference on M1 for distillation. Mitigated by: batch weekly, cap at 20 chunks per run, skip if cloud disabled. Cost: ~1 inference call per week.

**Data readiness:** PARTIAL. Needs accumulated outcomes with `retrieved_chunk_ids` populated. Currently near-zero. By Sprint 17 execution (likely 1-2 sessions from now), there should be 50-100 outcomes from normal usage. That's enough for a first distillation pass.

### C2: Correction Classifier

**What it is:** Detect when a user corrects Hestia ("No, I meant...", "That's wrong", "Actually...") and classify the correction type (timezone, factual, preference, tool_usage).

**Prerequisites satisfied:**
- `CorrectionType` enum already defined in `hestia/learning/models.py` (4 types)
- OutcomeManager has `detect_implicit_signal()` for behavioral signals
- `OutcomeFeedback.CORRECTION` exists as an explicit feedback type
- Handler pipeline processes every message through `handle()`

**What's missing:**
- No heuristic to detect correction patterns in user messages
- No storage for classified corrections
- No integration with MetaMonitor (corrections aren't counted in routing quality)
- No feedback to handler (corrections don't influence next response)

**Implementation scope:**
1. `CorrectionClassifier` in `hestia/learning/correction.py` (~120 lines)
2. Heuristic detection: regex patterns for correction language + comparison to previous response
3. Classification via keyword matching (zero LLM): "timezone"/"time"/"when" -> TIMEZONE, "wrong"/"incorrect"/"actually" -> FACTUAL, "prefer"/"rather"/"instead" -> PREFERENCE, "use"/"tool"/"command" -> TOOL_USAGE
4. Storage: new `corrections` table in LearningDatabase
5. Integration: call from `detect_implicit_signal()` when `quick_followup` detected
6. MetaMonitor extension: correction rate per session, correction type distribution
7. 1-2 API endpoints: `GET /v1/learning/corrections` (list), `GET /v1/learning/corrections/stats`

**Risk:** Low. Pure heuristic, no LLM cost. False positives are acceptable (corrections are advisory, not action-triggering).

**Data readiness:** IMMEDIATE. Works on the next user message. No accumulated data needed.

### C3: Memory UI Browser

**What it is:** iOS + macOS view showing all memory chunks with importance scores, consolidation history, and archive status.

**Prerequisites satisfied:**
- 5 memory lifecycle API endpoints exist (Sprint 16)
- ImportanceScorer populates `confidence` field on chunks
- Memory search API returns chunks with metadata

**What's missing:**
- No iOS or macOS view for browsing memories (would be entirely new)
- No API endpoint for paginated memory listing with sort-by-importance
- No consolidation history API (which chunks were merged into what)
- No UI design for importance visualization

**Implementation scope:**
- New `MemoryBrowserView` (macOS) + `MemoryListView` (iOS)
- New ViewModels for both platforms
- New API endpoint: `GET /v1/memory/browse` with pagination, sort, filter
- Importance bar visualization, chunk type badges, archive/restore actions
- Estimated: 8-12 hours across backend + iOS + macOS

**Risk:** High scope for a single sprint. Two-platform UI work is always slower than estimated.

**Data readiness:** POOR. Importance scores are all type_bonus + recency (no retrieval signal). Consolidation hasn't run yet (sample_size=50, first run pending). No pruned chunks to show. The UI would launch showing flat, uninteresting data.

### C4: Command Center Redesign

**What it is:** Replace static hero/calendar/orders layout with contextual metrics dashboard showing learning insights, memory health, trigger alerts.

**Prerequisites satisfied:**
- CommandView exists with HeroSection, StatCardsRow, CalendarWeekStrip, OrdersPanel, ActivityFeed
- MacCommandCenterViewModel loads data from multiple endpoints
- Learning endpoints exist (MetaMonitor report, memory health, alerts)

**What's missing:**
- No learning metrics in Command Center (would need new API integration)
- No visual design for metrics cards (positive_ratio gauge, latency trend spark line, alert badges)
- StatCardsRow currently shows... what? Need to check. Likely static/placeholder counts.

**Implementation scope:**
- Extend `MacCommandCenterViewModel` to fetch learning data
- New stat card components: PositiveRatioGauge, LatencyTrendSparkline, AlertBadge
- Wire memory health snapshot data (chunk count, redundancy, entity count)
- Estimated: 8-10 hours

**Risk:** MetaMonitor returns INSUFFICIENT_DATA until 20+ outcomes accumulate. Command Center would show "Insufficient data" badges for the learning section until enough conversations happen. Not a great first impression.

**Data readiness:** POOR. Same as Memory Browser — the data pipeline needs time to accumulate meaningful metrics.

### C5: Neural Net Graph Phase 2

**What it is:** Wire `mode=facts` to macOS graph, expand filter panel to 7 node types, add time slider for bi-temporal exploration, upgrade edge styling.

**Prerequisites satisfied:**
- `GraphBuilder.build_fact_graph()` exists with full entity/community/episode support
- `point_in_time` parameter already accepted by `build_fact_graph()`
- Discovery report completed with detailed visual encoding spec
- Backend supports all 7 node types and 9 edge types

**What's missing:**
- macOS graph only sends `mode=legacy` (no mode selector UI)
- GraphControlPanel only shows 3 of 7 node types
- Legend doesn't reflect expanded type system
- No time slider component
- NodeDetailPopover incomplete for fact/community/episode types

**Implementation scope:**
- Add mode toggle to GraphControlPanel
- Expand node type filters (4 new entries)
- Update legend to use CATEGORY_COLORS from API
- Add time slider UI component
- Extend NodeDetailPopover for all node types
- Estimated: 6-8 hours

**Risk:** MEDIUM. Uncommitted parallel session work (12 files modified per `git status`) includes research-related Swift files. Starting Neural Net Phase 2 before that work is resolved creates merge conflicts. The discovery doc itself was from a parallel session.

**Data readiness:** MODERATE. Knowledge graph has entities, facts, and communities from Sprint 9-KG and Claude history import. Episodic nodes may be sparse. The fact graph mode would show meaningful data immediately.

## Argue: Why C1+C2 (Learning Closure Sprint)

**The case for pairing Correction Classifier + Outcome-to-Principle:**

1. **They compose naturally.** Corrections feed into the outcome quality signal. When a correction is detected, the implicit signal shifts to negative, which reduces the importance of the retrieved chunks. When principles are distilled, they come from high-quality (non-corrected) interactions. The correction classifier makes the principle pipeline more precise.

2. **Zero UI work, maximum backend value.** Both candidates are backend-only. No two-platform development overhead. No design decisions. No "empty state" problem. The code runs in background schedulers and produces data that will make C3/C4/C5 dramatically more useful in Sprint 18+.

3. **Closes the learning arc.** Sprint 15 = observe (MetaMonitor, triggers). Sprint 16 = act (importance, consolidation, pruning). Sprint 17 = learn (classify corrections, distill principles). This completes the Intelligence era's learning cycle: observe -> act -> learn.

4. **Data pipeline fills while you build.** Every chat conversation during Sprint 17 development generates outcome data with retrieval chunk IDs. By the time Sprint 18 (UI sprint) starts, there will be 100+ outcomes, importance scores with real retrieval signal, and distilled principles. The UI will launch with meaningful data.

5. **Effort estimate is right-sized.** C2 (~4-6h) + C1 (~6-8h) = 10-14h total. That fits Andrew's ~12h/week window with margin for testing and iteration. No risk of scope creep.

6. **No merge conflicts.** Both features touch `hestia/learning/` (correction.py, models.py) and `hestia/learning/scheduler.py`. No overlap with the parallel session's orchestration/handler changes.

## Refute: Why NOT C1+C2

**Counter-argument 1: Premature backend without user-visible value.**
Andrew has been doing backend-only work for Sprint 15 and Sprint 16. Three consecutive backend sprints with no UI changes means no tangible product improvement from the user's perspective. Sprint fatigue is real.

*Response:* Valid concern. However, the learning pipeline IS the product differentiator. And the principles distilled in Sprint 17 will appear in the Neural Net graph (principle nodes) and future briefings. The user-visible payoff comes in Sprint 18, but only if Sprint 17 builds the pipeline.

**Counter-argument 2: C5 (Neural Net Phase 2) has the most immediately visible impact.**
The graph mode switch and time slider are the most "wow" features. They wire existing backend capability to existing frontend UI. The discovery report is already done with detailed specs.

*Response:* True, but blocked by the uncommitted parallel session work. Those 12 modified files need to be resolved before touching the same Swift files. And C5 without importance-weighted nodes (no retrieval data) would show a flat, unweighted graph -- missing the "importance sizing" feature that makes it compelling.

**Counter-argument 3: Correction classifier is low-value without enough correction examples.**
If users don't frequently correct Hestia, the classifier produces nothing. The current outcome data suggests Hestia mostly gets things right (positive_ratio likely high for simple conversations).

*Response:* The classifier detects corrections retroactively too -- it processes historical outcomes. Even a few corrections per week is valuable signal. And the heuristic is so cheap (regex + keyword, no LLM) that it's worth having even at low volume. The false-positive cost is zero (corrections are advisory).

## Third-Party Evidence

**ICLR 2026 MemAgents Workshop** proposes conversion pathways from episodic to semantic memory and explicit-to-implicit knowledge. The outcome-to-principle pipeline is exactly this: converting episodic conversation outcomes into semantic principles.

**Mem0 (2026)** and **MemOS** both describe active memory management where agents learn from interaction patterns, not just store them. The correction classifier + principle distillation pipeline mirrors their "memory governance" layer.

**SCoRe (ICLR 2025)** demonstrates multi-turn reinforcement learning for self-correction. While Hestia doesn't do RL, the correction classifier captures the same signal: "this response was wrong, here's what went wrong, learn from it."

**Hermes Agent (Nous Research, Feb 2026)** uses multi-level memory with dedicated learning from failures. Their approach: detect failure -> classify -> store as negative example -> avoid in future. Hestia's correction classifier follows the same pattern but with domain-specific categories (timezone, factual, preference, tool_usage).

## Recommended Sprint 17 Scope

### Sprint 17: Learning Closure (~10-14h)

**C2: Correction Classifier (first)**
1. `CorrectionClassifier` class in `hestia/learning/correction.py`
   - Heuristic detection: regex patterns for correction language
   - Classification: keyword -> CorrectionType mapping
   - Context capture: previous response content + correction message
2. `corrections` table in LearningDatabase (migration)
3. Integration with `detect_implicit_signal()` in OutcomeManager
4. MetaMonitor extension: correction rate, correction type distribution
5. 2 API endpoints: `GET /v1/learning/corrections`, `GET /v1/learning/corrections/stats`
6. Tests: ~15-20

**C1: Outcome-to-Principle Pipeline (second)**
1. `OutcomePrincipleDistiller` in `hestia/learning/distiller.py`
   - Filter outcomes by positive_ratio > 0.6
   - Extract retrieved_chunk_ids from qualifying outcomes
   - Feed chunks to PrincipleStore.distill_principles()
   - Dedup via ChromaDB semantic similarity (>0.85 = skip)
2. Weekly scheduler loop in LearningScheduler
3. 1 API endpoint: `POST /v1/learning/distill-principles`
4. Config in triggers.yaml: `min_outcomes_for_distillation: 50`
5. Tests: ~10-15

**Total: ~25-35 new tests, 2-3 new files, 3 new API endpoints**

### Proposed Sprint 18-19 Sequencing

| Sprint | Scope | Rationale |
|--------|-------|-----------|
| Sprint 18 | **Neural Net Phase 2 (C5)** — graph mode switching, expanded filters, time slider | Parallel session work resolved. Importance data accumulated. Principles exist to display. |
| Sprint 19 | **Memory Browser (C3) + Command Center Learning Metrics (C4 partial)** | 100+ outcomes accumulated. Meaningful importance scores. Correction stats available. MetaMonitor has sufficient data. |

## Final Critiques

### The Skeptic: "Why won't this work?"

*Challenge:* The correction classifier is heuristic-only. "Actually" and "no" appear in normal conversation constantly. You'll get 80% false positives.

*Response:* The classifier runs ONLY when `quick_followup` is detected (user replied within 30 seconds). A 30-second follow-up saying "Actually, I meant X" is almost certainly a correction. A 5-minute follow-up saying "Actually, let me also ask about Y" won't trigger. The timing filter is the primary signal; the keyword classifier refines it. And false positives are cheap -- they're advisory data for MetaMonitor, not action-triggering.

### The Pragmatist: "Is the effort worth it?"

*Challenge:* Three backend-only sprints in a row. Andrew doesn't see anything new on screen. The principle distillation pipeline won't produce principles until there's enough data. Is this sprint just building plumbing?

*Response:* Yes, it's plumbing -- but it's the last piece of plumbing before the Intelligence era is complete. After Sprint 17, the full learning cycle is: chat -> outcome tracked -> retrieval feedback captured -> importance scored -> corrections classified -> principles distilled -> principles influence future responses. That's a closed loop. Sprint 18 makes it visible. And the pipeline runs automatically -- once built, it produces value with zero ongoing effort.

### The Long-Term Thinker: "What happens in 6 months?"

*Challenge:* On M5 Ultra, you could do LLM-based correction classification with much higher accuracy. The heuristic classifier becomes tech debt.

*Response:* The heuristic classifier is a 120-line file with clear keyword maps. It's trivially replaceable with an LLM classifier by changing the `classify()` method. The storage schema, MetaMonitor integration, and API endpoints all stay the same. The heuristic is not tech debt -- it's the fast path that continues to work as a fallback even when LLM classification is available. Same pattern as ImportanceScorer (heuristic now, LLM merge later) and MemoryConsolidator (embedding similarity now, LLM-based merge later).

## Open Questions

1. **Retrieval data density check.** Before starting Sprint 17, validate with the SQL query from the handoff: `SELECT COUNT(*) FROM outcomes WHERE json_extract(metadata, '$.retrieved_chunk_ids') IS NOT NULL`. If < 10, the principle pipeline should be configured with a higher `min_outcomes_for_distillation` threshold.

2. **Parallel session resolution.** The 12 uncommitted files from the orchestration/byline session need to be committed or stashed before Sprint 18 (Neural Net Phase 2). Not blocking for Sprint 17.

3. **Principle dedup threshold.** Should semantic dedup against existing principles use 0.85 or 0.90 similarity? The consolidator uses 0.90 for memory chunks, but principles are more abstract -- 0.85 may be appropriate.

4. **Correction classifier scope.** Should it also detect POSITIVE corrections ("Yes, exactly!" / "Perfect, thanks")? These would feed into positive outcome signals. Could be v2.

---

*Research sources:*
- [ICLR 2026 MemAgents Workshop Proposal](https://openreview.net/pdf?id=U51WxL382H)
- [MemOS: A Memory OS for AI System](https://arxiv.org/pdf/2507.03724)
- [Long Term Memory: The Foundation of AI Self-Evolution](https://arxiv.org/html/2410.15665v4)
- [Top 10 AI Memory Products 2026](https://medium.com/@bumurzaqov2/top-10-ai-memory-products-2026-09d7900b5ab1)
- [Nous Research Hermes Agent](https://www.marktechpost.com/2026/02/26/nous-research-releases-hermes-agent-to-fix-ai-forgetfulness-with-multi-level-memory-and-dedicated-remote-terminal-access-support/)
- [Training Language Models to Self-Correct via RL (SCoRe)](https://openreview.net/forum?id=CjwERcAU7w)
- [When Can LLMs Actually Correct Their Own Mistakes?](https://direct.mit.edu/tacl/article/doi/10.1162/tacl_a_00713/125177/)
- [S2R: Self-verify and Self-correct via RL](https://aclanthology.org/2025.acl-long.1104/)
- [Mem0 Research](https://mem0.ai/research)
- [Sprint 16 Discovery: Memory Lifecycle](docs/discoveries/memory-lifecycle-importance-consolidation-pruning-2026-03-17.md)
- [Neural Net Graph View Evolution Discovery](docs/discoveries/neural-net-graph-view-evolution-2026-03-17.md)
