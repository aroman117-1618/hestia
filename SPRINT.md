# Workflow Orchestrator P0: Handler Adapter (2026-03-20) — COMPLETE

**Started:** 2026-03-20
**Plan:** `docs/plans/workflow-orchestrator-p0-implementation-2026-03-20.md`
**Discovery:** `docs/discoveries/visual-workflow-orchestrator-2026-03-20.md`
**Second Opinion:** `docs/plans/visual-workflow-orchestrator-second-opinion-2026-03-20.md`

## What Was Built
- **WorkflowHandlerAdapter** (`hestia/workflows/adapter.py`) — bridge between workflow engine and RequestHandler with configurable session strategy (ephemeral/per-run/persistent), memory scope, agent routing, tool access
- **Workflow models** (`hestia/workflows/models.py`) — `SessionStrategy` enum, `WorkflowExecutionConfig` dataclass
- **Orders execution wired** — `execute_order()` now sends prompts through the full handler pipeline (replacing ADR-021 stub)
- **OrderScheduler callback wired** — APScheduler triggers route through real execution
- **Execute API updated** — `/v1/orders/{id}/execute` returns real LLM response content
- **Enums added** — `RequestSource.WORKFLOW`, `LogComponent.WORKFLOW`

## Decisions Made
- **Handler Adapter pattern (Option C)** chosen over direct inference bypass or separate pipeline. Gives full handler capabilities with per-node configuration.
- **WebView + React Flow** for canvas UI (P2) — not custom SwiftUI Canvas. Eliminates highest-risk item.
- **Full build approved** — P0-P4, estimated 102-135h

### Key Commits
- `82243fe` feat(workflow): add WORKFLOW to RequestSource and LogComponent enums
- `051dc38` feat(workflow): add SessionStrategy enum and WorkflowExecutionConfig
- `a6a83a9` feat(workflow): WorkflowHandlerAdapter with session strategy and memory scope
- `02469f7` feat(workflow): wire execute_order() to WorkflowHandlerAdapter — replaces stub (ADR-021)
- `2dad6c0` feat(workflow): wire OrderScheduler callback to real execution pipeline
- `f13d7d6` feat(workflow): update execute route to return real handler response
- `e14da21` chore: add workflow module to auto-test.sh mapping

### Test Results
- 18 new tests in `test_workflow_adapter.py`, all passing
- 2628 backend + 135 CLI = 2763 total

---

# Sprint 27A: ChatGPT History Backfill (2026-03-20) — PROPOSED

**Started:** 2026-03-20
**Plan:** `docs/plans/chatgpt-history-backfill-plan.md`
**Parallel to:** Sprint 27 Go-Live (paper soak)

## Scope
Import 518 ChatGPT conversations (89MB, Dec 2022–Mar 2026) into Hestia's memory pipeline.

### Workstreams
- **WS1: OpenAI Parser + Pipeline** (~4h) — DAG flattener, turn extractor, API endpoint, tests
- **WS2: Conversation Summarizer** (~3h) — LLM distillation for high-volume convos (>50 messages)
- **WS3: Import Execution + Validation** (~2h) — Phased import (high-value first), dedup, spot-check

### Phase 1 Target: 71 high-value conversations (Hestia project + personal preferences)
### Phase 2 Target: ~380 medium-value conversations (technical, professional, creative)

---

# Sprint 27: Go-Live (2026-03-19) — IN PROGRESS (Paper Soak)

**Started:** 2026-03-19
**Plan:** `docs/discoveries/sprint-27-go-live-2026-03-18.md`
**Safety Review:** `docs/plans/sprint-27-golive-second-opinion-2026-03-19.md`

## What Was Built
- **BotRunner** (`bot_runner.py`, 380 lines) — async poll loop: candles → indicators → strategy.analyze() → executor.execute_signal(). 3-strike exponential backoff, event publishing to TradingEventBus
- **BotOrchestrator** (`orchestrator.py`, 332 lines) — lifecycle mgmt, per-bot asyncio locks, crash detection, graceful shutdown, server startup resume
- **Market data polling** — Coinbase REST candles (7-day, 1h granularity), 15-min poll interval, ticker fallback
- **Execution pipeline** — Signal → Risk → Price Validation → Exchange, full audit trail + confidence scoring + decision trail
- **Safety hardening** — atomic trade recording (isolation_level fix), active reconciliation → kill switch, portfolio value outside tx
- **Coinbase SDK fixes** — response type handling, granularity mapping, 7-day fetch window
- **Server wiring** — `orchestrator.resume_running_bots()` on startup, start/stop API endpoints

## Paper Soak Status
- **Started:** 2026-03-19 at 11:52 UTC on Mac Mini (`hestia-3.local`)
- **Bots active:** 5 (Mean Reversion on BTC-USD) — `bot-0`, `bot-1`, `bot-2`, `alpha`, `beta`
- **Capital:** $250 paper balance, Quarter-Kelly sizing
- **Expected completion:** ~2026-03-22 (72h window)
- **Mac Mini:** running with `caffeinate -d`
- **Status:** Bots executing, risk manager active, no errors or kill switch triggers

## Remaining (post-soak)
- Review trade history + tax lots via API
- Confirm no kill switch triggers in logs
- If clean → flip `trading.yaml mode: coinbase`, start with $25 (10% ramp)
- Minor hardening: lock dependencies, dead circuit breaker cleanup, partial fill handling

### Key Commits
- `e80a512` fix(trading): Coinbase SDK response type + granularity mapping + 7-day window
- `f01265f` fix: defer vectorbt dep — requires Python 3.10+, Mac Mini runs 3.9
- `f8ef1f3` fix(trading): reviewer critical fixes — isolation_level + portfolio value outside tx

### Test Results
- 33 tests in `test_trading_golive.py`, all passing
- 2515 backend + 135 CLI = 2650 total

---

# Graph + Memory Browser Bug Fix Session (2026-03-18) — COMPLETE

**Started:** 2026-03-18

## What Was Done
- Fixed graph view showing "No memories yet" — `get_graph()` in `manager.py` returned empty arrays on every cache hit (nodes never deserialized from cached JSON)
- Fixed force-directed layout overflow with 200+ nodes (positions at 10^80) — per-step velocity cap + final normalization to target_radius=6.0
- Fixed memory browser returning empty list despite 1008 server chunks — `MemoryChunkItem` explicit snake_case `CodingKeys` conflicted with `APIClient.convertFromSnakeCase` decoder
- Fixed initial camera too zoomed in (z=8 → z=20) and `zFar` extended (100 → 200)
- Fixed legend missing Chat/Insight types + all 7 legend colors corrected to match backend `CATEGORY_COLORS`
- Added `strippingBracketPrefixes()` to `NodeDetailPopover` — strips `[IMPORTED CLAUDE HISTORY — Foo]: [User]:` noise from node content
- Fixed macOS app defaulting to `.local` instead of `.tailscale` (Mac Mini)
- Imported 78 conversations / 988 chunks of Claude history via SSH Python bypass on Mac Mini
- Added GitHub Project board workflow to CLAUDE.md + stop hook in settings.json

### Key Commits
- `b4b918c` fix: deserialize graph nodes/edges from cache instead of returning empty arrays
- `ae3f95a` fix: correct macOS environment default and research path prefixes
- `5c4e3a9` fix: graph position overflow + memory browser decode failure
- `94e746e` fix: graph camera distance, legend accuracy, and content prefix stripping
- `85f88a0` docs: add GitHub Project board workflow instructions + stop hook

### Test Results
- 2142 backend + 135 CLI = 2277 total, all passing

---

# Sprint 20: Neural Net Graph Phase 2 (2026-03-18) — COMPLETE

**Started:** 2026-03-18
**Plan:** `docs/plans/research-tab-development-plan.md`

### Phase 20A (~21h): Quality Framework, Principles Fix, UI Polish, Visual Weights — COMPLETE
- WS1: Insight Quality Framework — COMPLETE
  - DIKW 4-tier durability scoring (Ephemeral/Contextual/Durable/Principled)
  - 3-phase staged extraction pipeline (Entity ID → Significance Filter → PRISM Triple)
  - TemporalType + SourceCategory enums, backward-compat ALTER TABLE migrations
  - Importance formula: 0.2R + 0.2F + 0.3T + 0.3D (added durability weight)
  - Ephemeral fact filter in graph builder, durability-blended node/edge weights
  - Retroactive crystallization loop (weekly promotion of clustered ephemerals)
- WS2: Principles Pipeline Fix — COMPLETE
  - Distillation loop rewrite with bootstrap check (seeds from 30d memory if empty)
  - Config-driven intervals via memory.yaml principle_distillation section
  - 3-phase distillation: memory chunks → outcomes → corrections
  - ResearchView empty state: "tap" → "click", added auto-distillation note
- WS3: Memory Tab UI Polish — COMPLETE
  - Sort picker: external label + .labelsHidden()
  - Filter pill spacing: MacSpacing.sm → MacSpacing.md
  - Pagination bar: added top Divider for visual separation
  - Type badge width: 80px → 60px (tighter layout)
- WS4: Graph Visual Weight System — COMPLETE
  - Node opacity maps to confidence (0.3–1.0)
  - Node emission glow maps to recency (fades over 90 days)
  - Durability filter UI (segmented picker: All/Contextual+/Durable+/Principled)
  - Client-side durability filtering with edge pruning

### Phase 20B (Adapted — ~14.25h): Gemini CLI, /second-opinion Skill, Source Infrastructure
- WS7: Gemini CLI + /second-opinion skill (4.25h) — replaces /plan-audit — **do first**
- WS5: Graph Source Expansion — infrastructure only (10h) — SourceCategory enum, paste/ingest API, staging workflow, External Research pipeline
  - Deferred: ChatGPT/Gemini provider-specific parsers (no sample files, speculative value)

### Phase 20C (~20h): Notification Relay — COMPLETE
- WS6: Intelligent Notification Relay (20h) — COMPLETE
  - 7 source files in `hestia/notifications/` (models, database, idle_detector, macos_notifier, apns_client, router, manager)
  - 5-check routing chain: rate limit → session cooldown → quiet hours → Focus mode → idle detection
  - APNs HTTP/2 JWT auth (ES256, 50-min token cache, Keychain credentials)
  - macOS local notifications via osascript
  - Batch consolidation (3+ bumps in 60s → single summary)
  - 6 API endpoints, Pydantic schemas, server lifecycle wiring
  - 42 tests, all passing

### Plans (see `docs/plans/`)
- `research-tab-development-plan.md` — v2, Gemini-reconciled (quality framework, source expansion, principles, notification relay, /second-opinion skill)
- `visual-workflow-orchestrator-brainstorm.md` — v2, Gemini-reconciled (DAG engine, visual canvas, event triggers, 85h across 4 phases)

---

# Future: Visual Workflow Orchestrator (~85h, 4 phases)

**Plan:** `docs/plans/visual-workflow-orchestrator-brainstorm.md`
**Replaces:** Orders system (7 endpoints) + LearningScheduler (6 loops) → unified visual DAG engine

- Phase 1 (35h): DAG engine + TaskGroup + checkpointing + linear canvas UI + Orders migration
- Phase 2 (18h): Conditions + JMESPath interpolation + Pydantic schemas + keyed debouncing
- Phase 3 (22h): EventKit/FSEvents triggers + HMAC webhooks + token budgets + advanced control
- Phase 4 (10h): Templates + semantic zoom + Sugiyama auto-layout + execution replay

**Prerequisite:** Sprint 20C (Notification Relay) — the Notify action node wraps WS6.
**Feeds into:** Sprint 21+ (Trading Module) — market condition triggers, portfolio workflows.

---

# Sprints 21-25: Trading Module Build (2026-03-18) — COMPLETE

**Started:** 2026-03-18
**Plan:** `docs/discoveries/trading-module-research-and-plan.md`
**All 5 sprints completed in a single session.**

### Capital & Parameters
- Starting capital: $250 (Coinbase, Consumer Default Spot portfolio)
- Position sizing: Quarter-Kelly for months 1-3
- API keys: macOS Keychain (`coinbase-api-key`, `coinbase-api-secret`)
- SDK: `coinbase-advanced-py` (handles auth, signing, WebSocket reconnection)

### Sprint 21: Foundation — COMPLETE
- Module structure: `hestia/trading/` (models, database, manager, exchange adapters)
- TradingDatabase with WAL mode + 256MB MMIO, 5 tables (bots, trades, tax_lots, daily_summaries, reconciliation_log)
- PaperAdapter (realistic slippage + Coinbase fee tiers), CoinbaseAdapter skeleton
- RiskManager: 8 circuit breakers, Quarter-Kelly, kill switch, position limits
- 1099-DA tax lot tracking (HIFO/FIFO) from day one
- API routes (12 endpoints), LogComponent.TRADING, auto-test.sh, trading.yaml config
- 103 tests

### Sprint 22: Strategy Engine — COMPLETE
- BaseStrategy ABC with Signal model (buy/sell/hold + confidence)
- GridStrategy: geometric spacing, Post-Only, ATR grid width validation, auto re-grid
- MeanReversionStrategy: RSI-7/9, 20/80 thresholds, volume + trend filter, hard stop-loss
- Technical indicators layer (wraps `ta` library): RSI, SMA, EMA, Bollinger, ATR, ADX, volume ratio
- MarketDataFeed for OHLCV candle management
- 42 tests

### Sprint 23: Risk Pipeline — COMPLETE
- PositionTracker: real-time exposure, unrealized P&L, 60-second reconciliation loop
- PriceValidator: cross-feed price verification (Layer 7 safety)
- TradeExecutor: Signal → Risk → Price → Exchange pipeline with full audit trail
- 35 tests

### Sprint 24: Backtesting Engine — COMPLETE
- DataLoader: synthetic data, Coinbase public API fetcher, CSV cache
- BacktestEngine: maker/taker fees, slippage, look-ahead bias prevention (signal shift)
- BacktestReport: Sharpe, Sortino, max drawdown, win rate, profit factor, equity curve
- Walk-forward validation (30d train / 7d test sliding windows)
- Train/test split (70/30) with overfit risk assessment
- Overfit detection: auto-warns on Sharpe >3.0, win rate >70%, profit factor >3.0
- 35 tests

### Sprint 25: Coinbase Live — COMPLETE
- CoinbaseAdapter: full REST via SDK (limit orders, accounts, fills, ticker, order book)
- CoinbaseWebSocketFeed: ticker/candles/user channels, sequence gap detection, exponential backoff reconnection
- HealthMonitor: heartbeat, avg/p95 latency, uptime, disconnect count
- Live paper mode validated (real prices + virtual PaperAdapter fills)
- 26 tests

### Key Commits
- `e5858c4` feat: Sprint 21 — trading module foundation
- `589bc13` feat: register trading routes in server.py
- `b0fc5c2` feat: Sprint 22 — strategy engine
- `b1dbd02` feat: Sprint 23 — position tracker, price validator, execution pipeline
- `6bc3079` feat: Sprint 24 — backtesting engine
- `8fb03d2` feat: Sprint 25 — Coinbase live integration

### Test Results
- 241 new trading tests across 9 test files, all passing
- Full suite: 2426 backend + 135 CLI = 2561 total

---

# Sprint 19: Trading Module — Research & Planning (2026-03-18) — COMPLETE

**Started:** 2026-03-18

## What Was Done
- Full research and architectural design for autonomous cryptocurrency trading module
- 4-strategy suite designed: Grid Trading (geometric, 35%), Mean Reversion (crypto-optimized RSI-7/9, 20%), Signal-Enhanced DCA (25%), Bollinger Breakout (20%)
- 8-layer safety architecture: API key scoping, position limits, Quarter-Kelly sizing, drawdown/daily/latency/price-divergence circuit breakers, reconciliation loop, kill switch
- Gemini Deep Research adversarial review conducted — 11 critical/high-impact findings integrated (geometric grid spacing, Post-Only maker orders, 1099-DA tax lot tracking from day one, WAL mode SQLite, on-chain PiT ingestion)
- Full sprint breakdown: S21 Foundation → S22 Strategy Engine → S23 Risk → S24 Backtesting → S25 Coinbase Live → S26 Dashboard → S27 Portfolio → S28 Sentiment → S29 On-Chain+ML → S30 Go-Live

### Output
- `docs/discoveries/trading-module-research-and-plan.md` — approved plan, ready for Sprint 21 build

### Notes
- Tailscale OAuth (originally co-labeled Sprint 19 on GitHub board) is a standalone 30-min maintenance task, not a sprint — moved to its own board item

---

# Research View Unification + Sprint 18 (2026-03-17) — COMPLETE

**Started:** 2026-03-17

## What Was Done
- Executed Research View Unification plan (5 tasks): PUT memory chunk endpoint, principles injection, macOS structural refactor, chunk editing UI, docs
- Memory Browser moved from sidebar into Research view as third toggle (Graph | Principles | Memory)
- Inline chunk editing with hover pencil, TextEditor, type Picker, Save/Cancel, graph refresh on mode switch
- Approved principles now injected into every system prompt (cloud-safe excluded)
- Sprint 18 anti-hallucination verifier stack (3 layers: tool compliance gate, retrieval quality score, SLM validator)
- Outcome-to-principle pipeline: distills high-signal outcomes into ResearchManager principles
- Tests: 2277 (2142 backend + 135 CLI). macOS: BUILD SUCCEEDED

---



# CI/CD Pipeline Fix + Codebase Audit Session (2026-03-17) — COMPLETE

## What Was Done
- Fixed all CI/CD pipeline failures (backports-asyncio-runner phantom dep, continue-on-error gate removal, claude action perms)
- Recompiled requirements.txt for Python 3.11 via uv
- Committed 3 missing Sprint 17 macOS files (LearningModels, APIClient+Learning, LearningMetricsPanel)
- xcodebuild + GitHub Actions CI now fully green
- Tailscale OAuth pinned for weekend (2026-03-22) — placeholder in deploy.yml ready to uncomment
- Codebase audit completed: `docs/audits/codebase-audit-2026-03-17.md`
- CLAUDE.md counts corrected (tests: 2267, endpoints: 186, files: 66)

## Pinned: Tailscale OAuth Setup (Weekend 2026-03-22)
1. Create OAuth client in Tailscale admin console with `tag:ci`
2. Add `TS_OAUTH_CLIENT_ID` + `TS_OAUTH_SECRET` as GitHub secrets
3. Add `tag:ci → Mac Mini :22` ACL rule
4. Uncomment the Tailscale step in `.github/workflows/deploy.yml`

---

# Previous: Agent Model Specialization + Reasoning Streaming (Sprint 17) — COMPLETE

**Started:** 2026-03-17
**Plan:** `.claude/plans/parallel-baking-pebble.md`

## Sprint 17 Summary

Per-agent model specialization (Artemis→DeepSeek-R1-14B, Apollo→Qwen 3 8B) and Claude Code-style reasoning streaming across all apps (CLI, iOS, macOS). Reasoning events show pipeline decisions in real-time: intent, agent routing, memory retrieval, model selection, and DeepSeek R1 `<think>` blocks.

### What Was Built
- **Per-agent model routing** — `AgentModelPreference` dataclass, `route_for_agent()` in ModelRouter, `force_tier` wired through executor
- **Reasoning events** — 5 yield points in `handle_streaming()`: intent, agent, memory, model, thinking
- **`<think>` block parser** — intercepts DeepSeek R1 reasoning tokens mid-stream, strips from stored content
- **CLI rendering** — transient `⟳`/`💭` status lines (Claude Code style)
- **iOS/macOS** — `ReasoningStep` model, `ReasoningStepsSection` collapsible view, `.reasoning` case in `ChatStreamEvent`

### Key Commits
- `220e709` feat: Sprint 17 — per-agent model specialization + reasoning streaming
- `6bb97fb` fix: update test assertions for Sprint 17 model changes

### Test Results
- 2132 backend + 135 CLI = 2267 total, all passing

---

# Previous: Memory Lifecycle (Sprint 16) — COMPLETE

**Started:** 2026-03-17
**Discovery:** `docs/discoveries/memory-lifecycle-importance-consolidation-pruning-2026-03-17.md`
**Plan Audit:** `docs/plans/sprint-16-memory-lifecycle-audit-2026-03-17.md`
**Implementation Plan:** `docs/superpowers/plans/2026-03-17-sprint-16-memory-lifecycle.md`

## Sprint 16 Summary

Memory lifecycle system: importance scoring, consolidation, and pruning. Zero-LLM — all SQL aggregation + embedding similarity. Closes the Sprint 15 feedback loop (observe → act).

### What Was Built
- **ImportanceScorer** (`hestia/memory/importance.py`) — composite score: 0.3 recency + 0.4 retrieval frequency (from outcome metadata) + 0.3 type bonus. Repurposes `ChunkMetadata.confidence`. Nightly batch via scheduler.
- **MemoryConsolidator** (`hestia/memory/consolidator.py`) — embedding-similarity dedup (>0.90 threshold, 50-sample cap). Pluggable `MergeStrategy` protocol (ImportanceBasedMerge default, LLM merge for M5 Ultra future). Weekly via scheduler.
- **MemoryPruner** (`hestia/memory/pruner.py`) — archives chunks >60 days old with importance <0.2. Soft-delete (ARCHIVED status) + ChromaDB removal. Undo capability. Weekly via scheduler.
- **Search integration** (`hestia/memory/manager.py:415`) — importance multiplier between import penalty and temporal decay
- **5 API endpoints** under `/v1/memory/`: importance-stats, consolidation/preview, consolidation/execute, pruning/preview, pruning/execute
- **Scheduler loops** in `hestia/learning/scheduler.py`: 6 total (3 Sprint 15 + 3 Sprint 16)
- **Config** — `hestia/config/memory.yaml` (importance/consolidation/pruning), `config/triggers.yaml` (+low_importance_ratio)

### Also Completed (Sprint 15 wiring)
- **Briefing injection** — system alerts section at priority 95 in daily briefing
- **Learning schedulers** — MetaMonitor hourly, MemoryHealth daily, TriggerMonitor daily
- **CLI animated banner** — campfire + pixel-font HESTIA, first-run animation

### Key Commits
- `4ebc84e` feat(cli): animated ASCII startup banner
- `90352e6` feat: wire Sprint 15 learning schedulers + briefing injection
- `ba88757` fix: correct research manager import path
- `b4b23b2` feat: ImportanceScorer — retrieval-feedback composite scoring
- `6dcddbe` feat: MemoryConsolidator — embedding-similarity dedup
- `e4f9ba3` feat: MemoryConsolidator + MemoryPruner
- `ea448f4` feat: 5 memory lifecycle API endpoints
- `d9fa3ff` feat: schedule importance/consolidation/pruning in LearningScheduler

### Test Results
- 45 new tests across 3 test files (test_importance, test_consolidator, test_pruner)
- Full suite: ~2080 passing, 1 pre-existing skip (Ollama integration)

---

# Previous: MetaMonitor + Memory Health + Trigger Metrics (Sprint 15) — COMPLETE

**Started:** 2026-03-16
**Discovery:** `docs/discoveries/metamonitor-memory-health-triggers-2026-03-16.md`
**Plan Audit:** `docs/plans/sprint-15-metamonitor-audit-2026-03-16.md`
**Implementation Plan:** `docs/superpowers/plans/2026-03-16-sprint-15-metamonitor.md`

## Sprint 15 Summary

Hestia's first self-awareness infrastructure. Hourly behavioral analysis, daily memory health diagnostics, configurable threshold monitoring. Prerequisite for all downstream learning (Sprints 16-20).

### What Was Built
- **Retrieval feedback loop** — `build_context()` stashes chunk IDs as `_last_retrieved_chunk_ids`; chat.py threads them into outcome metadata. Enables Sprint 16 importance scoring.
- **`hestia/learning/` module** — new module following manager pattern:
  - `models.py`: MetaMonitorReport, MemoryHealthSnapshot, TriggerAlert, CorrectionType, RoutingQualityStats
  - `database.py`: LearningDatabase (BaseDatabase) — 3 tables (monitor_reports, health_snapshots, trigger_log), all user_id-scoped
  - `meta_monitor.py`: MetaMonitorManager — hourly SQL analysis (routing quality correlation, acceptance trend, confusion loop detection, latency trend). Pure aggregation, no inference.
  - `memory_health.py`: MemoryHealthMonitor — daily ChromaDB + knowledge graph diagnostics (chunk count, source distribution, entity/fact/community counts, contradictions)
  - `trigger_monitor.py`: TriggerMonitor — configurable YAML thresholds with cooldown, briefing injection ready
- **handler.py decomposition** — extracted `AgenticHandler` (~145 lines) into `agentic_handler.py`, reducing handler.py from ~2440 to ~2300 lines
- **LEARNING LogComponent** — 20 components total
- **5 API endpoints** under `/v1/learning/` (report, memory-health, memory-health/history, alerts, alerts/{id}/acknowledge)
- **config/triggers.yaml** — 4 initial thresholds (chunk count, redundancy, entity count, latency)

### Deferred (per audit half-time cut list)
- Outcome → Principle pipeline (defer to Sprint 16)
- Correction classification (defer to Sprint 16)
- Read-only settings tools (defer to Sprint 18)
- Briefing injection wiring (infrastructure ready, wiring deferred)

### Key Commits
- `6c6020c` refactor: extract AgenticHandler + LEARNING LogComponent
- `fa7eb7d` feat: retrieval feedback loop — chunk IDs in outcome metadata
- `8eacb3e` feat: learning module — MetaMonitor, MemoryHealth, TriggerMonitor, 5 endpoints
- `097f798` docs: Sprint 15 discovery, plan audit, implementation plan

### Test Results
- 27 new tests in `tests/test_learning.py`
- Full suite: 2034 passing, 1 pre-existing skip (Ollama integration)

---

# Previous: Agent Orchestrator (Sprint 14) — COMPLETE

**Started:** 2026-03-16
**Design Spec:** `docs/superpowers/specs/2026-03-16-agent-orchestrator-design.md`
**Plan Audit:** `docs/plans/agent-orchestrator-audit-2026-03-16.md`
**Implementation Plan:** `docs/superpowers/plans/2026-03-16-agent-orchestrator.md`
**ADR:** ADR-042

## Sprint 14 Summary

Evolved Hestia from user-routed persona switching to a coordinator-delegate model. Hestia is the single user interface, orchestrating Artemis (analysis) and Apollo (execution) as internal sub-agents.

### What Was Built
- **AgentRoute enum** + orchestrator models (AgentTask, AgentResult, ExecutionPlan, AgentByline)
- **Intent-to-route heuristic** (AgentRouter) — deterministic mapping from council IntentType to AgentRoute via keyword matching
- **OrchestrationPlanner** with confidence gating (>0.8 dispatch, 0.5-0.8 enriched solo, <0.5 pure solo) and chain validation
- **AgentExecutor** with sequential chains, parallel groups (asyncio.gather), and fallback on error
- **Context slicing** per agent (Artemis gets full history, Apollo gets recent + tools)
- **Result synthesizer** with byline generation and footer formatting
- **Handler integration** — orchestrator hooks between pre-inference and inference, falls back to normal pipeline on solo/error
- **Council extension** — `agent_route` and `route_confidence` on IntentClassification
- **ChatResponse.bylines** — optional API field for client attribution rendering
- **Outcome tracking** — `agent_route` and `route_confidence` columns (migration)
- **Routing audit database** — SQLite, user_id-scoped, fire-and-forget logging
- **@artemis/@apollo invoke patterns** preserved as power-user override
- **orchestration.yaml** config with kill switch
- **Golden dataset** — 33 test cases, 100% routing accuracy

---

# Previous: Hestia Evolution (Sprint 13) — COMPLETE

**Started:** 2026-03-15
**Discovery:** `docs/discoveries/hestia-enhancement-candidates-2026-03-15.md`, `docs/discoveries/hestia-agentic-self-development-2026-03-15.md`
**Execution Plan:** `docs/superpowers/plans/2026-03-15-hestia-evolution-sprint-13.md`
**Plan Audit:** `docs/plans/sprint-13-evolution-audit-2026-03-15.md`

## Sprint 13 Summary

4 workstreams: knowledge graph completion, iOS/macOS app strategy, Claude history import, agentic self-development.

### WS1: Knowledge Graph (complete)
- EpisodicNode model + episodic_nodes table with user_id scoping
- Temporal fact queries: `get_facts_at_time(point_in_time, subject)` — "what did I know in January?"
- Fire-and-forget fact extraction after qualifying chat messages (>200 chars)
- 6 new endpoints: entity search, fact invalidation, temporal queries, episodic list/search
- 11 new tests

### WS2: App Strategy (complete)
- iOS trimmed to Chat + Settings (macOS is primary full-featured app)
- project.yml excludes: CommandCenter, Explorer, Wiki, NeuralNet views from iOS target
- Both Xcode schemes build clean

### WS3: Claude History Import (complete + executed)
- ClaudeHistoryParser: 4-layer extraction (text, thinking blocks, summaries, tool patterns)
- Credential stripping (API keys, PATs, passwords) — 7 redacted in real import
- Import pipeline with content-hash dedup via source_dedup table
- `POST /v1/memory/import/claude` endpoint
- **988 chunks imported from 78 conversations**, dedup verified on re-import
- 26 new tests

### WS4: Agentic Self-Development (Phases 0-2 complete)
- Phase 0: `edit_file`, `glob_files`, `grep_files`, `git_status/diff/add/commit/log` tools
- Phase 1: `handle_agentic()` iterative tool loop (while tool_calls, max 25 iterations)
- Phase 2: Self-modification verification layer + CLI `/code` command
- Security: `hestia/security/` excluded from edit, `[hestia-auto]` commit prefix, force-push blocked
- `CODING` intent type added to council, `~/hestia` in sandbox allowlist
- 44 new tests

### Key Commits
- `d87ca2f` feat: episodic memory nodes + temporal fact queries
- `6d0d7b2` feat: auto fact extraction + entity search + temporal queries + episodic endpoints
- `1642aee` feat: Claude history parser with credential stripping
- `601040a` feat: Claude history import pipeline + API endpoint
- `07baeb9` refactor(iOS): trim to Chat + Settings
- `e796b01` feat: code editing + git tools + CODING intent
- `1ea8d74` feat: agentic tool loop + /v1/chat/agentic SSE endpoint
- `bd466e3` feat: self-modification verification layer
- `e50176d` feat: CLI /code command

### Test Results
- 1900 collected, ~1897 passing, 3 skipped
- 81 new tests across 6 test files

---

# Previous: Knowledge Graph Evolution (Sprint 9-KG) — COMPLETE

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

## Next: Trading Module — Sprints 21–30 (APPROVED 2026-03-18)

**Workstream:** WS-TRADING — Autonomous Algorithmic Crypto Trading
**Milestone:** Hestia v2.0 — Personal Investment Platform (crypto + stocks)
**GitHub Label:** `workstream:trading`
**Plan:** `docs/discoveries/trading-module-research-and-plan.md`
**Capital:** $250 crypto + $500 equity (scaling to $5K+) | **Target:** 15–50% annualized | **Exchanges:** Coinbase (crypto) + Alpaca (stocks) | Kraken optional at $5K+

### Critical Path: S21 → S22 → S23 → S25 → S26 → S27 (Go-Live)

| Sprint | Title | Size | Priority | Phase | Depends | Status |
|--------|-------|------|----------|-------|---------|--------|
| S21 | Trading Foundation — module, DB (WAL), paper adapter, tax lots | L | P0 | Engine | — | **COMPLETE** |
| S22 | Strategy Engine — geometric grid, crypto RSI (7-9/20-80) | XL | P0 | Engine | S21 | **COMPLETE** |
| S23 | Risk Management — 8 circuit breakers, reconciliation, ¼-Kelly | L | P0 | Engine | S22 | **COMPLETE** |
| S24 | Backtesting — VectorBT, anti-overfit, walk-forward validation | XL | P0 | Engine | S22 | **COMPLETE** |
| S25 | Coinbase Live — WebSocket, Post-Only orders, sequence check | XL | P0 | Exchange | S23+S24 | **COMPLETE** |
| S25.5 | Activity Feed Restructure — Command Center → System/Internal/External tabs | L | P0 | UI | — | **COMPLETE** |
| S26 | Trading Dashboard — SSE streaming, confidence scoring, decision trails, alerts | XL | P0 | UI | S25.5 | **COMPLETE** |
| S27 | **Go-Live** — Bot Runner, orchestrator, market data, safety hardening, paper soak, capital deploy | XL | P0 | Launch | S26 | **IN PROGRESS** (paper soak) |
| S28A | Wire Bollinger + DCA for crypto, backtest 90d, CSV trade export | L | P0 | Strategies | S27 | TODO |
| S28B | AlpacaAdapter (read-only), market hours scheduler, simulated stock signals | XL | P0 | Platform | S28A | TODO |
| S29A | AlpacaAdapter (full), PDT enforcement, Alpaca paper soak | XL | P0 | Platform | S28B | TODO |
| S29B | Equity live ($100), regime detection (observe-only), CoinGecko feed | L | P1 | AI | S29A | TODO |
| S30 | **Optimization + On-Chain** — Optuna optimizer, walk-forward validation, wash sale PoC, CryptoQuant signals | XL | P1 | ML | S29B | TODO |
| EXT-1 | External Storage Setup — Ollama offload, backups, log archival | S | P1 | Infra | — | COMPLETE |
| DQ-1 | Research Data Quality — insight cleanup, Apple backfill, graph filters | L | P1 | Research | S20A | IN PROGRESS |

**Reordered 2026-03-18:** Go-Live moved to S27 (was S30). Grid + Mean Reversion strategies are sufficient for initial live validation. Enhancement sprints (S28-S30) build on live trading data rather than hypothetical backtests.

### Frontend Architecture Decisions (locked 2026-03-18)
- **Activity Feed restructure:** Command Center → 3 tabbed views (System / Internal / External)
  - System: Workflows/Orders, Memory Activity, System Alerts
  - Internal: Health Summary, Tasks/Reminders, Calendar Events
  - External: Trading Monitor, News Feed, Investigations
- **Trading Monitor location:** Full content area within External tab (~600-800px), NOT 320px inspector sidebar
- **Figma reference:** `hestia` Figma file, node 352-51 (Trading Monitor) + node 294-3081 (Command Center)
- **S25 Minimum Viable Monitor:** Portfolio snapshot + kill switch + basic trade feed + risk traffic light (embedded in Command Center until Activity Feed restructure lands in S25.5)
- **S25.5 Activity Feed Restructure:** Prerequisite for full Trading Dashboard in S26. Can run in parallel with S25 backend work.
- **S26 Full Dashboard (expanded scope):**
  - Hestia satisfaction score per trade (circular gauge, 0-100%, compares actual vs predicted fill)
  - User satisfaction feedback per trade (binary thumbs up/down, feeds into learning pipeline)
  - Decision Trail (expandable reasoning chain per trade: signal, strategy params, risk check, market conditions, Hestia reasoning)
  - Watchlist/Thesis view (pairs being monitored, bullish/bearish/neutral thesis, confidence bar, trigger conditions)
  - News Feed migration into External tab
  - Investigations migration into External tab
  - Notifications routed through Hestia relay (no Discord — in-house via WS6/Sprint 20C)
- **Design system:** All trading UI uses existing MacColors/MacSpacing/MacTypography tokens. SF Mono for prices, SF Pro for labels.

### Key Decisions (locked 2026-03-18)
- **4 strategies:** Grid 35% (geometric), Mean Reversion 20% (RSI-7/9, 20/80), DCA 25%, Bollinger Breakout 20%
- **Execution:** Post-Only maker orders default (fee efficiency critical at small capital)
- **Risk:** Quarter-Kelly months 1–3 → Half-Kelly after validation. 8 circuit breakers incl. API latency + price feed divergence
- **Tax:** HIFO/FIFO cost-basis from day one (1099-DA mandatory)
- **DB:** SQLite WAL mode + MMIO (concurrent WebSocket + trading writes)
- **AI:** Cloud inference → local after hardware upgrade. Sentiment = regime filter, not trade signal
- **Gemini review:** 11 critical findings incorporated (geometric grids, crypto RSI, Post-Only, tax lots, WAL, Bollinger strategy, ¼-Kelly, reconciliation, latency breaker, price validator, PiT data)

### Prerequisites
- [x] Coinbase API key (trade-only, no withdrawal, ECDSA, Consumer Default Spot) — stored in Keychain
- [x] APNs auth key (Production, Team Scoped) — Key ID URMG8N4HNT, stored in `data/credentials/`
- [x] Sign in with Apple capability registered (future auth upgrade path)
- [x] `pip install ccxt coinbase-advanced-py vectorbt pandas-ta scikit-optimize` — installed in S21
- [x] Cost-basis method decision: HIFO (confirmed)
- [x] Alert routing decision: In-house via Hestia notification relay (no Discord)
- [ ] Figma designs finalized for Activity Feed + Trading Monitor (in progress)

### Deferred Work
- iOS Correction Feedback UI (was Sprint 21 candidate — deferred, backend endpoint exists)
- Kraken/futures expansion (one-sprint effort when capital > $5K)
- handler.py refactor (2500+ lines, no sprint planned yet)
