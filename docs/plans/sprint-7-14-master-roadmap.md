# Hestia Master Roadmap: Sprints 7–22

**Created:** 2026-03-03
**Last Major Revision:** 2026-03-16 (Post-Sprint 14 roadmap overhaul)
**Status:** APPROVED
**Owner:** Andrew Lonati
**Architect:** Claude (Discovery Agent)

---

## Vision

Transform Hestia from a functional backend into a sovereign personal AI with genuine intelligence — where every interaction improves retrieval, routing, and anticipation. The roadmap is organized into three eras: **Foundation** (complete), **Intelligence Infrastructure** (current), and **Anticipatory Autonomy** (future).

---

## Era Overview

| Era | Sprints | Focus | Status |
|-----|---------|-------|--------|
| **Foundation** | 7–13 | UI wiring, data breadth, CLI, agentic coding, knowledge graph | COMPLETE |
| **Intelligence Infrastructure** | 14–18 | Agent orchestrator, memory lifecycle, Graph RAG, MetaMonitor, trigger metrics | IN PROGRESS |
| **Anticipatory Autonomy** | 19–22 | Active inference, anticipatory execution, health/Whoop, multimodal | PLANNED |

---

## Completed Sprints (7–14)

| Sprint | Focus | Status |
|--------|-------|--------|
| **7** | Profile & Settings Restructure | COMPLETE |
| **8** | Research & Graph + PrincipleStore | COMPLETE |
| **9A** | Explorer: Files | COMPLETE |
| **9B** | Explorer: Inbox | COMPLETE |
| **9-KG** | Knowledge Graph Evolution (bi-temporal facts, entities, communities) | COMPLETE |
| **10** | Chat Redesign + OutcomeTracker | COMPLETE |
| **11A** | Model Swap + Coding Specialist | COMPLETE |
| **11.5** | Memory Pipeline + CLI Polish | COMPLETE |
| **12** | Architecture Efficiency (parallel pre-inference, SSE, ETag) | COMPLETE |
| **13** | Hestia Evolution (episodic nodes, app strategy, Claude import, agentic coding) | COMPLETE |
| **14** | Agent Orchestrator (coordinate/analyze/delegate, ADR-042) | COMPLETE |

**Current test count:** 2,012 backend + 135 CLI = 2,147 total
**Current endpoint count:** ~170 across 26 route modules

---

## Intelligence Infrastructure Era (Sprints 15–18)

### Sprint 15: MetaMonitor + Memory Health + Trigger Metrics
**Priority:** P1 — Foundation for all learning cycle work
**Estimated Effort:** ~14 days
**Prerequisites:** Sprint 14 (orchestrator routing audit data), Sprint 10 (OutcomeTracker)
**Decision Gate 2:** Is OutcomeTracker collecting meaningful signals? Memory + CPU profile acceptable on M1?

**Scope:** Three workstreams that share infrastructure.

#### WS1: MetaMonitor (from old Sprint 11B)
Consumes OutcomeTracker data to detect behavioral patterns. Now also consumes routing audit data from Sprint 14.

- MetaMonitor background manager — pattern detection across outcomes + routing
- Routing quality analysis: "ARTEMIS-routed responses have 87% positive signals vs. 61% for solo"
- Confidence calibrator — adjusts routing thresholds based on observed outcome quality
- ConfidenceCalibrator + KnowledgeGapDetector
- Command Center contextual metrics (Personal ↔ System)
- ~3 new endpoints: `/v1/monitor/patterns`, `/v1/monitor/routing-quality`, `/v1/monitor/gaps`
- ~35 tests

#### WS2: Memory Quality Monitor (NEW)
First mechanism to analyze the health of all three memory systems.

- **Retrieval Quality Feedback Loop** — when PromptBuilder includes memory chunks, log chunk IDs to outcome metadata. Correlate: which chunks appear in positive vs. negative outcomes?
- **ChromaDB health metrics** — chunk count, redundancy rate (% of retrieved chunks with cosine similarity >0.92 to each other), never-retrieved chunk count
- **Knowledge graph health metrics** — entity staleness (no new facts in N days), community stability, contradiction count
- **Cross-system drift detection** — flag when knowledge graph facts disagree with most recent vector chunks
- Daily health report in proactive briefing (or surfaced in Command Center)
- ~20 tests

#### WS3: Trigger Metrics Infrastructure (from Research Brief)
Turns the research brief from a static document into an active system.

- `GET /v1/system/metrics` endpoint returning: `memory.total_chunks`, `memory.total_tokens_est`, `memory.tokens_by_source`, `knowledge.entity_count`, `knowledge.fact_count`, `system.unified_memory_gb`, `system.chip_generation`, `inference.median_latency_ms`
- Daily Orders job checking metrics against trigger thresholds (defined in `config/triggers.yaml`)
- When threshold crossed → inject note into proactive briefing: *"[Metric] crossed [threshold]. Research brief Opportunity [N] may be actionable."*
- ~10 tests

#### Additional (carried from old Sprint 11B)
- Read settings tools (Tia can diagnose her own config)
- Outcome → Principle pipeline (corrections become knowledge)
- Correction classification (categorize mistake types)

**Total tests:** ~65
**Key deliverables:** MetaMonitor, memory health dashboard, trigger metric automation, routing quality feedback loop

---

### Sprint 16: Memory Lifecycle — Importance Scoring + Consolidation
**Priority:** P1 — Highest-ROI personalization work
**Estimated Effort:** ~10 days
**Prerequisites:** Sprint 15 (memory health metrics to measure improvement)

#### WS1: Importance Scoring at Ingest
Tag every chunk with a priority level (1-5) that affects decay rate and retrieval ranking.

- Extend auto-tagger LLM prompt to output importance score: 1 (trivial/social), 2 (informational), 3 (decision/preference), 4 (commitment/plan), 5 (identity/value)
- Store as chunk metadata in ChromaDB
- Retrieval scoring: `adjusted = raw_score * decay * importance_weight`
- High-importance chunks decay slower (λ reduced by importance tier)
- Backfill: batch job to score existing chunks (run once)
- ~15 tests

#### WS2: Memory Consolidation
Merge redundant chunks into authoritative summaries.

- Nightly batch job via Orders scheduler
- Group chunks by entity/topic (using knowledge graph communities as clustering signal)
- For clusters with >3 chunks on the same topic: LLM-summarize into one consolidated chunk
- Mark originals as `consolidated_into: <new_chunk_id>` — excluded from primary retrieval but kept for provenance
- Consolidation audit log — what was merged, when, why
- Configurable: `config/memory.yaml` → `consolidation.enabled`, `min_cluster_size`, `schedule`
- ~20 tests

#### WS3: Active Pruning
Remove demonstrably low-value chunks.

- Monthly pruning job (runs after consolidation)
- Prune criteria: zero retrievals in 90 days AND importance score ≤ 2 AND superseded by consolidated chunk
- Move to `memory_archive` table (soft delete, not hard delete — provenance preserved)
- Report pruning stats in proactive briefing
- ~10 tests

**Total tests:** ~45
**Key deliverables:** Every new chunk gets an importance score. Old chunks consolidate. Dead weight gets pruned. Memory system gets healthier over time.

---

### Sprint 17: Graph RAG Lite — Dual-Path Retrieval
**Priority:** P1 — Connects the knowledge graph to the retrieval pipeline
**Estimated Effort:** ~8 days
**Prerequisites:** Sprint 15 (SYNTHESIS intent detection), Sprint 9-KG (knowledge graph with entities/facts)
**Trigger:** Knowledge graph has ≥500 entities with ≥1,000 relationships, OR user asks cross-domain synthesis questions

#### WS1: SYNTHESIS Intent Type
Detect "global synthesis" vs. "local retrieval" queries in the council.

- Add `SYNTHESIS` to `IntentType` enum
- SLM/keyword detection for synthesis patterns: "how does X relate to Y?", "what themes connect...", "what patterns do you see across...", "summarize everything about..."
- Router maps `SYNTHESIS` → `ARTEMIS` (analysis agent handles synthesis)
- ~8 tests

#### WS2: Graph-Enriched Context for Synthesis Queries
When intent is SYNTHESIS, the context manager pulls from the knowledge graph in addition to vector chunks.

- Extract key entities from the user's question
- Query knowledge graph: find entities in related communities, traverse fact relationships (up to 2 hops)
- Pull connecting facts with temporal validity
- Also run ChromaDB vector search for supporting detail
- Inject BOTH graph relationships AND vector chunks into Artemis's context slice
- Format graph context as structured relationships, not raw triplets: "Entity A → relation → Entity B (since [date])"
- ~15 tests

#### WS3: Synthesis Quality Metrics
Track whether Graph RAG Lite actually improves synthesis responses.

- Tag outcomes with `retrieval_mode: "vector_only" | "graph_enriched"`
- MetaMonitor (Sprint 15) compares outcome quality between the two modes
- If graph-enriched doesn't measurably improve quality after 30 days → auto-disable and surface briefing note
- ~5 tests

**Total tests:** ~28
**Key deliverables:** The knowledge graph finally participates in retrieval. Synthesis queries get relationship-aware context. Quality is measured.

---

### Sprint 18: Command Center + Settings Write Tools
**Priority:** P2 — UI polish and self-correction capability
**Estimated Effort:** ~10 days
**Prerequisites:** Sprint 15 (MetaMonitor data for Command Center)

#### WS1: Command Center Redesign (from old Sprint 11B)
- Contextual metrics (Personal ↔ System auto-switch)
- Calendar week grid (7-day overview)
- Order creation wizard (multi-step)
- Routing regime visualization (orchestrator stats from Sprint 14 audit data)
- Memory health dashboard (from Sprint 15 WS2 data)
- ~20 tests

#### WS2: Write Settings Tools (from old Sprint 13.4)
Enable Hestia to apply approved corrections to user settings.

- `update_user_setting(key, value)` tool with risk-gated approval
- Tiered risk: Display preferences (SUGGEST) → Behavioral preferences (SUGGEST) → Security (NEVER) → System (NEVER)
- CorrectionConfidence scoring (urgency, impact, security_risk, frequency)
- Suggested corrections surface in principles view with `source=correction` tag
- ~12 tests

**Total tests:** ~32

---

## Anticipatory Autonomy Era (Sprints 19–22)

### Sprint 19: Active Inference Foundation (from old Sprint 13)
**Priority:** P2 — World model + prediction engine
**Estimated Effort:** ~12 days
**Prerequisites:** Sprint 15 (MetaMonitor), Sprint 16 (consolidated memory), Sprint 18 (write settings tools)
**Decision Gate 3:** Is MetaMonitor producing meaningful patterns? Is memory consolidation improving retrieval quality? → Go/No-Go on Active Inference vs. simplified heuristics.

- Generative World Model (3 layers: Abstract/Routine/Situational)
- EMA belief updater (not Bayesian — validated in original plan audit)
- Prediction Engine (time-based, context-based, pattern-based predictions)
- Surprise Detector (per-domain EMA, quadratic error)
- Curiosity Drive (Shannon entropy, information gain ranking)
- 4 new endpoints: `/v1/learning/world-model`, `/v1/learning/predictions`, `/v1/learning/surprise`, `/v1/learning/curiosity`
- ~45 tests

### Sprint 20: Anticipatory Execution (from old Sprint 14)
**Priority:** P2 — Three operating regimes go live
**Estimated Effort:** ~10 days
**Prerequisites:** Sprint 19 (World Model, Prediction Engine, Surprise Detector)

- Three operating regimes: Anticipatory (>0.8 confidence, act proactively), Curious (<0.4, ask questions), Observant (middle, watch and learn)
- AnticipationExecutor with ActionRisk classification (SILENT/DRAFT/SUGGEST/NEVER)
- Regime selector with hysteresis (configurable thresholds in `config/learning.yaml`)
- Auto-generated draft orders for high-confidence predictions
- Curiosity questions in daily briefing (max 1/day, respects interruption policy)
- Command Center regime visualization
- "Was this proactive action helpful?" feedback button
- ~30 tests

### Sprint 21: Health Dashboard + Whoop (from old Sprint 12)
**Priority:** P3 — Feature breadth (moved down from original P1)
**Estimated Effort:** ~17 days
**Prerequisites:** Sprint 19 (World Model consumes health signals)
**Decision Gate 4:** Is Whoop developer access approved? Is health data compliance policy defined?

- Whoop integration (OAuth2, Strain/Recovery/Sleep stages)
- Health dashboard (macOS + iOS)
- Labs & prescriptions (manual + Apple Health Records FHIR)
- Clinical data disclaimers (post-processing filter)
- OAuthManager base class (shared with future integrations)
- ~65 tests

> **Rationale for deferral:** Health Dashboard is feature breadth, not intelligence infrastructure. The World Model (Sprint 19) needs health signals, but HealthKit integration (already complete) provides sufficient data. Whoop adds depth but isn't on the critical path.

### Sprint 22: Multimodal Vision + Explainable Memory
**Priority:** P3 — Requires hardware upgrade
**Estimated Effort:** ~10 days
**Prerequisites:** M5 Ultra Mac Studio (≥64GB unified memory), Sprint 16 (memory consolidation for provenance)
**Trigger:** Hardware upgrade detected + multimodal model available in Ollama

#### WS1: Vision Integration
- Ollama multimodal model (LLaVA or equivalent) for image understanding
- Orchestrator routes image-bearing messages to vision-capable model
- Apollo handles "what's in this image?" queries
- iOS/macOS image picker integration
- ~20 tests

#### WS2: Explainable Memory ("Why do you think that?")
- Provenance trace from claims → source memory/fact
- `@hestia why do you think [X]?` query pattern → traces through consolidated chunks to originals
- Knowledge graph fact attribution with source_chunk_id links
- ~15 tests

**Total tests:** ~35

---

## Future Adaptations (Trigger-Based, Not Scheduled)

These opportunities are documented in `../hestia-atlas-future-research.md` and activate when specific thresholds are crossed. Hestia monitors triggers via Sprint 15's trigger metrics infrastructure.

| Opportunity | Trigger | Current Status |
|------------|---------|---------------|
| MLX Inference Backend | M5 Ultra + MLX ships API server mode | Dormant — Ollama is correct tool |
| QLoRA Fine-Tuning | ≥5M tokens + hardware ≥32GB + RAG quality ceiling documented | Dormant — RAG handles personalization |
| MoE Architecture | Closed by ADR-042 | **Addressed** — agent orchestrator is the solution |
| Federated Learning (Atlas) | Atlas phases A1-A6 complete + ≥5 deployments | Dormant — no federation participants |
| Continual Learning | QLoRA validated + eval pipeline + rollback infra | Dormant — depends on QLoRA |
| Self-Sovereign/Blockchain | Open-source or multi-user decision | Dormant — great content, premature engineering |

---

## Sprint Overview (Upcoming)

| Sprint | Focus | Backend | Tests | Days |
|--------|-------|---------|-------|------|
| **15** | MetaMonitor + Memory Health + Trigger Metrics | ~3 endpoints + bg managers + metrics | ~65 | ~14 |
| **16** | Memory Lifecycle (Importance, Consolidation, Pruning) | ~2 batch jobs + chunk metadata | ~45 | ~10 |
| **17** | Graph RAG Lite (SYNTHESIS intent + dual-path retrieval) | ~1 intent type + context enrichment | ~28 | ~8 |
| **18** | Command Center + Write Settings Tools | ~6 views + settings tools | ~32 | ~10 |
| **19** | Active Inference Foundation | ~1 module, ~4 endpoints | ~45 | ~12 |
| **20** | Anticipatory Execution | ~3 endpoints + regime system | ~30 | ~10 |
| **21** | Health Dashboard + Whoop | ~2 modules, ~10 endpoints | ~65 | ~17 |
| **22** | Multimodal Vision + Explainable Memory | ~1 model route + provenance UI | ~35 | ~10 |
| **Total** | | | **~345** | **~91** |

---

## Intelligence Threading (Updated)

The Learning Cycle is reorganized around memory system maturation:

```
Sprint 14: Agent Orchestrator (COMPLETE)     ← Routing audit data feeds all downstream
Sprint 15: MetaMonitor + Memory Health       ← Learning Cycle Phase B: self-awareness
        ↳ Memory Quality Monitor              ← First cross-system health analysis
        ↳ Retrieval quality feedback loop     ← Closes outcome → chunk attribution gap
        ↳ Trigger metrics infrastructure      ← Research brief becomes active
Sprint 16: Memory Lifecycle                  ← Memory Maturation Phase 1
        ↳ Importance scoring at ingest        ← Not all memories are equal
        ↳ Consolidation (nightly)             ← Redundancy → authoritative summaries
        ↳ Active pruning (monthly)            ← Dead weight removed
Sprint 17: Graph RAG Lite                    ← Knowledge graph joins retrieval
        ↳ SYNTHESIS intent type               ← Council detects cross-domain questions
        ↳ Graph-enriched context              ← Relationships inform synthesis
Sprint 18: Command Center + Write Settings   ← UI for monitoring + self-correction
Sprint 19: Active Inference Foundation       ← Learning Cycle Phase C (part 1)
        ↳ World Model (3 layers)              ← Consumes MetaMonitor + consolidated memory
        ↳ Prediction Engine                   ← Pre-interaction predictions
Sprint 20: Anticipatory Execution            ← Learning Cycle Phase C (part 2)
        ↳ Three operating regimes             ← Anticipatory/Curious/Observant
Sprint 21: Health Dashboard + Whoop          ← Feature breadth (parallel track)
Sprint 22: Multimodal + Explainable Memory   ← Hardware-gated future
```

---

## Memory System Lifecycle (NEW)

The five memory components mature across sprints:

```
              Sprint 15          Sprint 16          Sprint 17          Sprint 22
              ─────────          ─────────          ─────────          ─────────
Ingest:       [existing]    →   [+importance]   →   [+graph-aware]
                                  scoring

Retrieval:    [vector RAG]  →   [+importance     →  [+graph context
                                  weighting]         for SYNTHESIS]

Maintenance:  [NONE]        →   [consolidation   →  [+synthesis
                                  + pruning]          quality tracking]

Monitoring:   [NONE]        →   [memory health   →  [+graph health     →  [+provenance
                                  + retrieval         + drift              tracing]
                                  feedback]           detection]
```

---

## Timeline (Updated)

**Remaining effort:** ~91 working days (~546 hours)
**At 6hr/week:** 546hr ÷ 6hr = 91 weeks ≈ **21 calendar months**
**At 12hr/week (stretch):** ~10.5 calendar months

**Recommended pace:** 2-week sprint cycles. Intelligence Infrastructure era (Sprints 15-18) is ~42 days — achievable in ~6 months at 6hr/week.

### Decision Gates (Updated)

| Gate | After Sprint | Decision |
|------|-------------|----------|
| **Gate 2** | Sprint 15 | Is MetaMonitor collecting meaningful patterns? Is memory health data useful? → Go/No-Go on Memory Lifecycle (Sprint 16) |
| **Gate 3** | Sprint 17 | Is Graph RAG Lite improving synthesis quality? Is importance scoring measurably helping retrieval? → Go/No-Go on Active Inference (Sprint 19) vs. simplified heuristics |
| **Gate 4** | Sprint 20 | Is anticipatory execution reliable? Is Whoop developer access approved? → Go/No-Go on Health Dashboard (Sprint 21) |
| **Gate 5** | Hardware | M5 Ultra purchased? → Unlock Sprint 22 (Vision + Explainable Memory) + research brief triggers |

---

## Dependency Chain (Updated)

```
Sprint 14 (Agent Orchestrator) — COMPLETE
    ├── Sprint 15 (MetaMonitor + Memory Health + Triggers)
    │   ├── Sprint 16 (Memory Lifecycle: importance + consolidation + pruning)
    │   │   └── Sprint 19 (World Model) ← consumes consolidated memory
    │   ├── Sprint 17 (Graph RAG Lite) ← uses SYNTHESIS intent from 15
    │   │   └── Sprint 19 (World Model) ← graph-enriched context
    │   └── Sprint 18 (Command Center + Write Settings)
    │       └── Sprint 19-20 (Active Inference + Anticipatory)
    │           └── Sprint 21 (Health + Whoop) ← World Model consumes health signals
    └── Sprint 22 (Multimodal + Explainable) ← hardware-gated, independent
```

**Critical path:** 14 → 15 → 16 → 19 → 20. Memory maturation (15-16) feeds Active Inference (19-20). Graph RAG (17) enriches the World Model but isn't blocking.

---

## Known Risks (Updated)

1. **M1 16GB memory ceiling** — Profile at Sprint 16 completion (consolidation may reduce RAM pressure, or may increase it during batch processing)
2. **Retrieval feedback loop cold start** — Sprint 15's feedback loop needs volume to produce meaningful signals. May need 2-3 months of data before MetaMonitor routing quality analysis is useful
3. **Graph RAG quality uncertainty** — Sprint 17 may show that graph-enriched context doesn't measurably improve synthesis. That's fine — the A/B measurement system will tell us, and we auto-disable if it doesn't help
4. **Active Inference theoretical risk** — Decision gate after Sprint 17; have simplified fallback (heuristics)
5. **Whoop developer access** — Required for Sprint 21. Apply immediately; design module as optional

---

## Detailed Plans

| Sprint | Plan Document |
|--------|---------------|
| 7 | [sprint-7-profile-settings-plan.md](sprint-7-profile-settings-plan.md) |
| 8 | [sprint-8-research-graph-plan.md](sprint-8-research-graph-plan.md) |
| 9A + 9B | [sprint-9-explorer-files-inbox-plan.md](sprint-9-explorer-files-inbox-plan.md) |
| 10 | [sprint-10-chat-redesign-plan.md](sprint-10-chat-redesign-plan.md) |
| 11A | [2026-03-05-sprint-11a-model-swap.md](2026-03-05-sprint-11a-model-swap.md) |
| 11.5 | [sprint-12-plan-audit-2026-03-05.md](sprint-12-plan-audit-2026-03-05.md) |
| 12 | [architecture-efficiency-plan-2026-03-15.md](architecture-efficiency-plan-2026-03-15.md) |
| 13 | `docs/superpowers/plans/2026-03-15-hestia-evolution-sprint-13.md` |
| 14 | `docs/superpowers/plans/2026-03-16-agent-orchestrator.md` |
| 15–18 | TBD — detailed plans written at sprint start |
| 19–20 | [sprint-13-14-learning-cycle-plan.md](sprint-13-14-learning-cycle-plan.md) (renumbered) |
| 21 | [sprint-12-health-whoop-plan.md](sprint-12-health-whoop-plan.md) (renumbered) |

---

## Related Documents

| Document | Location |
|----------|----------|
| Discovery (full analysis + SWOT) | `docs/discoveries/ui-wiring-discovery-roadmap.md` |
| Neural Net Learning Cycle Research | `docs/discoveries/neural-net-learning-cycle-research.md` |
| Future Adaptations Research Brief | `../hestia-atlas-future-research.md` |
| Agent Orchestrator Design Spec | `docs/superpowers/specs/2026-03-16-agent-orchestrator-design.md` |
| Agent Orchestrator Audit | `docs/plans/agent-orchestrator-audit-2026-03-16.md` |
| API Contract | `docs/api-contract.md` |
| Decision Log | `docs/hestia-decision-log.md` |
| Sprint Tracker | `SPRINT.md` |

---

> **Revision history:**
> - **2026-03-16:** Major overhaul. Sprints 7-14 marked COMPLETE. Roadmap reorganized into three eras. Old Sprints 11B/12/13/14 renumbered to 15/21/19/20 with priority reordering. New Sprints 16 (Memory Lifecycle), 17 (Graph RAG Lite), 22 (Multimodal + Explainable Memory) added. Memory lifecycle maturation pipeline threaded across sprints. Research brief trigger monitoring integrated. Future adaptations reference added.
> - **2026-03-05:** Sprint 11 split into 11A + 11.5 + 11B. Sprint 11.5 inserted.
> - **2026-03-03:** Sprint 9 split into 9A + 9B. Effort estimates revised upward. Test counts increased.
