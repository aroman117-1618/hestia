# Current Sprint: Knowledge Graph Evolution (Sprint 9-KG) — COMPLETE

**Started:** 2026-03-15
**Discovery:** `docs/discoveries/hestia-enhancement-candidates-2026-03-15.md`
**Execution Plan:** `docs/superpowers/plans/2026-03-15-knowledge-graph-evolution.md`
**ADR:** ADR-041

## Sprint 9-KG Summary

Evolved the Neural Net from a co-occurrence visualization into a temporal knowledge graph with bi-temporal facts, entity relationships, contradiction detection, and community clustering — all on existing SQLite + ChromaDB (no Neo4j/FalkorDB). Inspired by Graphiti framework.

### What Was Built
- **Fact model** with bi-temporal tracking (`valid_at`, `invalid_at`, `expired_at`)
- **Entity Registry** with canonical name dedup + label propagation community detection
- **Fact Extractor** with LLM triplet extraction + contradiction detection
- **Fact-based graph builder** (`mode=facts` on `/v1/research/graph`)
- **6 new API endpoints** (facts extract/list/timeline, entities list, communities detect/list)
- **~88 new tests** across 2 test files

### Key Commits
- `19fc9cb` feat: Fact, Entity, Community models with bi-temporal tracking
- `145c577` feat: facts, entities, communities tables with bi-temporal queries
- `e87bc5b` feat: entity registry with label propagation communities
- `5be2254` feat: LLM fact extraction with contradiction detection
- `fe2ddfd` feat: fact-based graph builder with entity nodes and relationship edges
- `73512f9` feat: 6 new research API endpoints
- `86a0c26` fix: align Fact model — add relation, source_chunk_id, rename weight→confidence
- `b7cdf03` merge: Sprint 9 Knowledge Graph Evolution

### Test Results
- Research tests: 158 passing
- Full suite: exit code 0 (all pass)

---

## Previous: Memory Pipeline + CLI Polish (Sprint 11.5) — COMPLETE

**Started:** 2026-03-05
**Discovery:** `docs/discoveries/sprint-12-cli-macos-polish-2026-03-05.md`
**Execution Plan:** `docs/plans/sprint-12-plan-audit-2026-03-05.md`
**Master Roadmap:** `docs/plans/sprint-7-14-master-roadmap.md`

## Sprint 11.5 Summary

### Phase A: Memory Pipeline + Research Wiring (8 tasks)
- A1: MemorySource enum + source param wiring + migration
- A2: Source dedup table + ingestion tracking + rollback
- A3: InboxMemoryBridge (preprocessing, encryption, sanitization, batch processing)
- A4: Daily ingestion background task (3 AM via Orders/APScheduler)
- A5: DataSource filter wiring + graph content truncation (200 char)
- A6: Fix graph black block (SceneKit opacity + ambient bg)
- A7: Principles loading + daily auto-distill + async safety
- A8: Profile full-window layout + MIND/BODY templates + agent icon

### Phase B: CLI + Agent Polish (5 tasks)
- B1: CLI agent-colored prompts (V2 API sync, escape sanitization, SEC-5)
- B2: Fire emoji thinking animation + per-agent personality verbs
- B3: Default agent per model tier (Tia->PRIMARY, Olly->CODING, Mira->COMPLEX)
- B4/B5 Polish: Agent save feedback toast, identity validation, QR camera permission check

### Security (resolved inline)
- SEC-1 through SEC-5 all addressed in Phase A/B tasks

### Key Commits
- `7f8838e` feat: default agent per model tier (B3)
- `123d553` polish: agent save toast + QR camera permission check (B4/B5)
- `49f5d5a` fix: lazy-init asyncio.Lock for Python 3.9 compat
- `81ae8e1` fix: router mock in council test handler setup
- `4d6b1e8` fix: MacColors tokens in AgentDetailSheet save toast

### Test Results
- Backend: ~1639 passing (3 skipped)
- CLI: 95 passing, 0 failures
- macOS build: clean

---

## Previous: Sprint 11A — Model Swap + Coding Specialist — COMPLETE

**Started:** 2026-03-05
**Design:** `docs/plans/2026-03-05-model-swap-planning-design.md`
**ADR:** ADR-040

- Primary model: `qwen2.5:7b` -> `qwen3.5:9b`
- New coding specialist: `qwen2.5-coder:7b` via `ModelTier.CODING`
- Routing: `complex_patterns` keyword matching -> coding tier before complex tier
- CLI context budget: 6K -> 16K chars
- Hardware upgrade playbook for M5 Ultra Mac Studio

---

## Previous: Chat Redesign + OutcomeTracker (Sprint 10) — COMPLETE

OutcomeTracker (auto-tracks chat responses, implicit signal detection, explicit feedback). Chat UI redesign (CLITextView, MarkdownMessageView, FloatingAvatarView, OutcomeFeedbackRow). Background sessions (OrderStatus extended, POST /v1/orders/from-session). 37 new tests.

## Previous: Hestia CLI (CLI Sprints 1-5 + Bootstrap) — COMPLETE

Terminal-native interface. WebSocket streaming, prompt_toolkit REPL, Rich rendering, tool trust tiers, repo context injection, zero-friction bootstrap. 66 tests.

## Previous: Explorer Files (Sprint 9A) — COMPLETE
## Previous: Unified Inbox (Sprint 9B) — COMPLETE
## Previous: Research & Graph (Sprint 8) — COMPLETE
## Previous: Profile & Settings (Sprint 7) — COMPLETE
## Previous: Stability & Efficiency (Sprint 6) — COMPLETE
## Previous Sprints (1-5): COMPLETE

---

## Next: Sprint 11B — Command Center + MetaMonitor (Deferred)

**Plan:** `docs/plans/sprint-11-command-center-plan.md`
**Effort:** ~15 working days
**Status:** Deferred — OutcomeTracker benefits from additional data collection time before Gate 2.

### Decision Gate 2 (before Sprint 11B)
- Is OutcomeTracker collecting meaningful signals?
- Memory + CPU profile acceptable on M1?
- Does multi-source memory (from 11.5) improve MetaMonitor input quality?
- -> Go/No-Go on MetaMonitor

### Sprint 11B Scope
1. MetaMonitor: consumes OutcomeTracker data, detects behavioral patterns
2. Command Center redesign: contextual metrics (Personal <-> System), calendar week grid
3. Order creation wizard (multi-step)
4. ~42 new tests
