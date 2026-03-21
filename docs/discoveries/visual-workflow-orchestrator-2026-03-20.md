# Discovery Report: Visual Workflow Orchestrator
**Date:** 2026-03-20
**Confidence:** High
**Decision:** The existing brainstorm plan is architecturally sound but should be re-scoped: start with a leaner P1 (backend engine + list-based UI, no canvas), defer canvas to P2, and decouple from the trading module until P3.

## Hypothesis
Can Hestia's Orders system be evolved into an n8n-level visual DAG workflow engine that unifies all background automation (orders, trading, learning, notifications) under a single visual canvas, and is the existing 85-hour, 4-phase plan from March 16 still the right approach?

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Existing APScheduler + OrderScheduler infrastructure. Trading module's BotOrchestrator/EventBus proves the async task pattern. LearningScheduler has 9 monitors already running on independent schedules. Full-stack ownership enables deep integration. 2706 tests provide a safety net for migration. | **Weaknesses:** Orders `execute_order()` is still a stub ("Orchestration integration deferred"). No event bus exists outside trading module. SwiftUI Canvas requires manual hit-testing, layout, and connection management. Single developer with 12h/week. Current Orders UI is a simple card list, not a canvas. |
| **External** | **Opportunities:** Unifies 3 separate schedulers (Orders, Learning, Wiki) into one visual system. Trading bots become workflow nodes users can see and configure. Workflow templates create immediate value (Morning Brief, Market Watch). Export/import enables sharing. | **Threats:** n8n has 400+ integrations and 100+ contributors -- feature parity is impossible and the wrong goal. SwiftUI Canvas node editor is uncharted territory (no production examples found). Scope creep is the primary risk -- the brainstorm already grew from 75h to 85h during Gemini review. |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | DAG execution engine with TaskGroup + checkpointing. Workflow CRUD + migration from Orders. Variable interpolation. Schedule + Manual triggers. 4 core action nodes (RunPrompt, CallTool, Notify, Log). | Keyed debouncing. Token budget enforcement. |
| **Low Priority** | Canvas UI with drag-drop nodes and visual execution feedback. Sub-Workflow node. Sugiyama auto-layout. | Semantic zoom (3 levels). Workflow export/import. Pre-built templates beyond 2-3. HMAC webhook auth. EventKit/FSEvents OS-native hooks. |

---

## Argue (Best Case)

**1. The unified orchestration layer is genuinely needed.** Right now Hestia has 3 independent scheduling systems:
- `OrderScheduler` (APScheduler, 7 API endpoints, time-based only)
- `LearningScheduler` (9 async background loops, hardcoded schedules in triggers.yaml)
- `WikiScheduler` (APScheduler, periodic refresh)

Plus the trading `BotOrchestrator` which manages its own asyncio.Task lifecycle. Unifying these under a single DAG engine with visible execution history would eliminate duplicated scheduling infrastructure and give Andrew a single pane of glass for all background automation.

**2. The execution engine architecture is solid.** The brainstorm's DAGExecutor design (TaskGroup for structured concurrency, dead path elimination, SQLite checkpointing) is the right level of sophistication. It's significantly simpler than Temporal/Airflow while covering 90%+ of single-user needs. The data model (Workflow -> WorkflowNode[] -> WorkflowEdge[] -> WorkflowRun -> NodeExecution[]) is clean and maps naturally to SQLite.

**3. Trading module integration is a natural fit.** The BotOrchestrator already publishes events via TradingEventBus. A "Market Condition" trigger node that subscribes to these events would let users build workflows like: "When BTC drops 5% -> Run analysis prompt -> If bearish -> Pause bot -> Notify iPhone." This creates real compound value.

**4. SwiftUI Canvas is viable for the target scale.** Gemini research confirms 100-500 complex interactive nodes are feasible with view culling and Canvas symbols. With a 50-node-per-workflow limit, this is well within bounds.

**5. Existing community packages can accelerate.** [schwa/SwiftNodeEditor](https://github.com/schwa/SwiftNodeEditor) provides a protocol-based node/socket/wire system. [yukiny0811/easy-node-editor](https://github.com/yukiny0811/easy-node-editor) is another option. [SwiftDocOrg/GraphViz](https://github.com/SwiftDocOrg/GraphViz) or [Chronaemia/GraphKit](https://github.com/Chronaemia/GraphKit) can handle Sugiyama layout via Graphviz.

---

## Refute (Devil's Advocate)

**1. The 85-hour estimate is optimistic -- likely 120-140h.** The brainstorm lists 35h for Phase 1, which includes: data models, SQLite tables, DAGExecutor with TaskGroup + checkpointing + dead path elimination + version snapshotting, WorkflowScheduler, 4 action nodes, 2 trigger nodes, migration script, 10 API endpoints, AND a macOS canvas UI with drag-drop, connection drawing, inspector panel, run button, and real-time execution feedback. At 12h/week, that's 3 weeks just for P1 -- and canvas UIs always take 2-3x longer than estimated due to gesture handling, edge cases, and visual polish.

**2. The canvas UI is the riskiest part and delivers the least initial value.** No production-quality SwiftUI node graph editor exists in the wild. SwiftNodeEditor's API is "not yet stable" per its README. Building a canvas with drag-drop nodes, connection drawing (click-click), bezier edge routing, an inspector panel, and real-time execution feedback is a massive UI engineering effort. Meanwhile, most of the *functional* value comes from the backend engine -- a simple list-based UI (like the current OrdersPanel but for workflows) would deliver 80% of the value at 20% of the UI effort.

**3. The Orders system execution is still stubbed.** `OrderManager.execute_order()` says "Orchestration integration deferred (see ADR-021)." Before building a visual workflow orchestrator, the basic Order -> prompt execution pipeline needs to actually work. Building a DAG executor on top of a system that can't execute a single prompt is architecturally backwards.

**4. Trading module coupling is premature.** The BotOrchestrator manages asyncio.Tasks with per-bot locks, crash detection, exchange reconciliation, and its own error state machine. Wrapping this in a workflow node introduces a coupling that could compromise trading safety. If a workflow engine bug causes a bot to start/stop unexpectedly, that's a financial risk. The trading module should remain independently managed until both systems are proven stable.

**5. Feature parity with n8n is a trap.** n8n has: 400+ integrations, credential encryption, multi-user RBAC, execution queue with concurrency limits, webhook tunneling, binary data streaming between nodes, expression editor with autocomplete, workflow tags/folders, node pinning for debugging, execution data pruning, external storage backends. Chasing any of this is scope creep. The question isn't "what does n8n have" -- it's "what does Andrew actually need for Hestia?"

**6. Three schedulers running simultaneously is not actually a problem.** The LearningScheduler's 9 monitors work. The OrderScheduler works. The WikiScheduler works. "Unification" sounds elegant but carries migration risk (breaking working systems) for aesthetic benefit. The real need is *visibility* into what's running, which could be achieved with a simple `/v1/system/background-tasks` endpoint without replacing the schedulers.

---

## Third-Party Evidence

### n8n Core Architecture (from research)
n8n's power comes from:
1. **Sub-workflows** -- the #1 power user feature. Encapsulate reusable logic, keep main graphs to 4-6 nodes.
2. **Credential isolation** -- never hardcoded, environment-based switching.
3. **Per-node error handling + retries** -- define "On Error" paths per node, built-in retry with exponential backoff.
4. **Version history** -- save and revert workflow versions safely.
5. **Data pinning** -- run workflow to a node, pin its output, build downstream using cached data. Dramatically speeds development.

### SwiftUI Canvas Performance (from Gemini)
- Simple geometry: 5,000-10,000 elements at 60fps on Apple Silicon.
- Complex interactive nodes with text + bezier edges: 100-500 nodes realistic.
- Critical optimizations: view culling (only render visible nodes), Canvas symbols API, separate static/dynamic content with `.drawingGroup()`.
- Key bottleneck: text rendering (`context.resolve(Text(...))`) is expensive per frame.
- Manual hit-testing required -- recommend quadtree for O(log n) lookups.

### Sugiyama Layout
Solved problem in Swift via Graphviz wrappers:
- [Chronaemia/GraphKit](https://github.com/Chronaemia/GraphKit) -- native SwiftUI, uses Graphviz `dot` engine async.
- [SwiftDocOrg/GraphViz](https://github.com/SwiftDocOrg/GraphViz) -- Swift wrapper, returns layout coordinates for custom rendering.

### Common Failure Modes in Custom Workflow Engines
From industry postmortems and HN discussions:
1. **Underestimating the execution engine complexity** -- error handling, retries, timeouts, and partial failure recovery are where 60% of the bugs live.
2. **Building the UI before the engine is solid** -- visual polish masks broken execution semantics.
3. **Tight coupling between visual representation and execution model** -- the canvas position of a node should have zero effect on execution order.
4. **Not handling "stuck" executions** -- nodes that hang forever without timeout, consuming resources.
5. **Migration regret** -- replacing a working simple system with a complex one and losing reliability.

---

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- SwiftUI Canvas is viable for 50-node workflows with proper optimization (view culling, symbols API).
- n8n's core value is in the execution engine, not the canvas -- sub-workflows, error handling, versioning are what power users need.
- Sugiyama layout is available via Graphviz Swift wrappers (no need to implement from scratch).

### Contradicted Findings
- The brainstorm assumed SwiftUI Canvas could hit 50+ nodes without optimization. In fact, text rendering and manual hit-testing require deliberate engineering. The plan underestimates canvas UI effort.
- The plan assumes building canvas UI and engine in parallel (P1). Evidence strongly suggests building engine first, UI second.

### New Evidence
- **Data pinning** (n8n's most praised debugging feature) is missing from the brainstorm entirely. This should be added to P2.
- **GraphKit** library for Sugiyama layout was unknown at brainstorm time. Eliminates the open question about "write our own or use a Swift port."
- **Code node** (custom Python/JS escape hatch) is the #2 most valued n8n feature after sub-workflows. The brainstorm has "Call Tool" but not "Run Code."

### Sources
- [n8n Power User Tips (Reddit)](https://www.reddit.com/r/n8n/comments/1bowm1z/what_are_some_n8n_power_user_tips_and_best/)
- [n8n Error Handling Docs](https://docs.n8n.io/flow-logic/error-handling/)
- [SwiftNodeEditor (GitHub)](https://github.com/schwa/SwiftNodeEditor)
- [EasyNodeEditor (GitHub)](https://github.com/yukiny0811/easy-node-editor)
- [GraphKit for Sugiyama (GitHub)](https://github.com/Chronaemia/GraphKit)
- [n8n Overview 2025](https://www.baytechconsulting.com/blog/n8n-overview-2025)
- [n8n Features](https://n8n.io/features/)

---

## Codebase Delta Since March 16

Changes since the brainstorm was written that affect feasibility:

1. **BotRunner + BotOrchestrator are now complete and running.** The trading module's async task lifecycle pattern (orchestrator spawns runners, monitors crashes, reconciles on startup) is a proven pattern that the workflow engine can learn from -- but should NOT try to replace.

2. **Trading EventBus exists** (`hestia/trading/event_bus.py`) -- a working pub/sub system with bounded queues and priority events. This could be generalized into the workflow EventBus rather than building from scratch. However, it's tightly coupled to SSE streaming for the trading dashboard.

3. **LearningScheduler has 9 monitors.** These are hardcoded async loops, not APScheduler jobs. Migration to workflow nodes would require: (a) wrapping each monitor in a node interface, (b) preserving the exact scheduling semantics (hourly, 6-hourly, daily, weekly, nightly), (c) testing that behavior is identical. This is a non-trivial migration that should be deferred.

4. **Orders execution is still stubbed.** `OrderManager.execute_order()` has not been wired to the orchestration handler. This is actually a *positive* finding -- it means there's no working execution to break during migration, so the workflow engine can provide the execution implementation that Orders never got.

5. **macOS OrdersPanel is a simple card list.** The existing UI shows order name, status badge, timestamps, and a progress bar. No canvas, no node editor, no connections. The UI gap between current state and the brainstorm's canvas vision is massive.

---

## Revised Recommendation: Re-Scoped Phase Plan

### Phase 0: Fix Orders Execution (prerequisite, ~6h)
Before building a workflow engine, make `OrderManager.execute_order()` actually work by wiring it to the orchestration handler. This proves the execution pipeline and gives immediate value to the existing Orders system.

### Phase 1: Workflow Engine + List UI (~30h)
**Backend (20h):**
- Workflow/Node/Edge data models + SQLite tables (reuse brainstorm schema)
- DAGExecutor with `asyncio.TaskGroup`, dead path elimination, SQLite checkpointing
- WorkflowScheduler wrapping APScheduler
- 4 Action nodes: RunPrompt, CallTool, Notify, Log
- 2 Trigger nodes: Schedule, Manual
- If/Else condition node (simple expression evaluator)
- Migration script: Orders -> single-trigger + single-action Workflows
- 12 API endpoints (CRUD + activate/deactivate + trigger + runs)
- Per-node error handling + retry (n8n's #3 must-have)
- Version snapshotting on activate

**macOS UI (10h):**
- Workflow list sidebar (replaces OrdersPanel)
- Workflow detail view: node list (not canvas), drag to reorder
- Node configuration forms per node type
- Run button + execution history with per-node status
- Real-time execution feedback via SSE (reuse TradingEventBus pattern)

**Why no canvas yet:** The list-based UI delivers 80% of the value (create workflows, configure nodes, see execution results) at 20% of the UI effort. The canvas is visual sugar that can be layered on top.

### Phase 2: Canvas + Conditions + Data Pinning (~25h)
**Backend (8h):**
- Switch condition node
- Confidence Gate node
- Variable interpolation: `{{node.output.field}}` templates
- Data pinning (persist node output, replay from pinned data)
- Sub-Workflow node (call another workflow)

**macOS Canvas UI (17h):**
- SwiftUI Canvas with node rendering (use Canvas symbols API)
- View culling for performance
- Click-click connection model (not drag)
- Node palette sidebar (drag to add)
- Inspector panel for selected node
- Sugiyama auto-layout via GraphKit/Graphviz
- Visual execution replay (green/red node borders from run history)

### Phase 3: Events + Trading Integration (~20h)
**Backend (12h):**
- Generalized EventBus (evolve from TradingEventBus)
- Email, Calendar, Health, Webhook trigger nodes
- Market Condition trigger (subscribes to trading events)
- "Start Bot" / "Stop Bot" / "Pause Bot" action nodes (wraps BotOrchestrator)
- Token budget enforcement
- Keyed debouncing

**macOS UI (8h):**
- Event trigger configuration forms
- Join node visualization
- Error path styling
- Semantic zoom (3 levels)

### Phase 4: Polish + Templates (~10h)
- 6 pre-built workflow templates
- Export/import (JSON)
- Duplicate workflow
- Execution replay with checkpoint visualization
- Keyboard shortcuts
- iOS summary view (read-only workflow status)

**Revised Total: ~91h (~8 sprint weeks at 12h/week)**

### Key Differences from Original Plan:
1. **Phase 0 added** -- fix the Orders execution stub first.
2. **Canvas deferred to P2** -- engine-first, UI-second. P1 uses list-based UI.
3. **Data pinning added to P2** -- n8n's most praised debugging feature.
4. **Trading integration isolated in P3** -- no coupling until both systems are stable.
5. **LearningScheduler migration explicitly deferred** -- works fine as-is, migrate opportunistically in P4+.
6. **Per-node error handling + retry elevated to P1** -- n8n power users say this is non-negotiable.

---

## BotOrchestrator / Workflow Interaction Model

The trading module's BotOrchestrator should remain the authority for bot lifecycle. Workflow nodes should be thin wrappers:

```
WorkflowNode("start_bot")  -->  calls BotOrchestrator.start_runner(bot)
WorkflowNode("stop_bot")   -->  calls BotOrchestrator.stop_runner(bot_id)
WorkflowNode("pause_bot")  -->  calls TradingManager.update_bot(id, {status: "paused"})
```

The workflow engine does NOT manage bot Tasks directly. It sends commands through the existing BotOrchestrator API. If the orchestrator rejects the command (e.g., bot already running), the workflow node gets a failure result and can route to an error path.

For Market Condition triggers: the workflow EventBus subscribes to TradingEventBus events (one-way). Trading publishes, workflows consume. No reverse dependency.

---

## Migration Path from Current Orders

1. **Phase 0:** Wire `execute_order()` to handler pipeline. Existing Orders start working for real.
2. **Phase 1:** Run migration script that converts each Order to a 2-node Workflow (Schedule trigger -> RunPrompt action). Keep `/v1/orders` as deprecated aliases that proxy to `/v1/workflows`.
3. **Phase 1+:** OrdersPanel in macOS app switches to WorkflowListView. Same data, new model.
4. **Phase 2:** Remove Orders module entirely once no clients reference `/v1/orders`.

---

## n8n Feature Parity Gaps -- What to Skip

| n8n Feature | Include? | Rationale |
|-------------|----------|-----------|
| 400+ integrations | NO | Hestia has its own tool registry. Nodes wrap Hestia capabilities, not external SaaS. |
| Multi-user RBAC | NO | Single-user system. |
| Execution queue + concurrency limits | YES (P1) | Prevent multiple workflows from overwhelming M1 memory with parallel LLM calls. |
| Binary data streaming between nodes | NO | All Hestia data is text/JSON. |
| Expression editor with autocomplete | DEFER | Simple `{{}}` templates first. Autocomplete is polish. |
| Workflow tags/folders | YES (P1) | Cheap to implement, helps organization. |
| Webhook tunneling | NO | Tailscale handles network access. |
| External storage backends | NO | SQLite is the right choice for single-user. |
| Data pinning | YES (P2) | Power user #1 debugging feature. |
| Code node (Python) | YES (P2) | "Escape hatch" -- run arbitrary Python. Sandboxed via existing Sandbox. |
| Sub-workflows | YES (P2) | Power user #1 architectural pattern. |
| Credential isolation | PARTIAL | Already have Keychain. Workflow-level credential scoping not needed for single-user. |
| Version history | YES (P1) | Snapshot on activate. Already in brainstorm. |

---

## Philosophical Layer

### Ethical Check
Building a personal automation engine is ethically sound. No user data leaves the system. Workflows are transparent (visible execution history). The trading safety boundary is preserved by keeping BotOrchestrator independent.

### First Principles Challenge
**Why build this at all?** Strip away the n8n aspiration: Andrew needs (1) scheduled prompts that actually execute, (2) event-driven automation (email arrives -> do something), (3) visibility into what Hestia does in the background. These three needs could be met with:
- (1) Fix `execute_order()` -- 6 hours
- (2) A simple EventBus + listener registration -- 10 hours
- (3) A `/v1/system/background-tasks` endpoint + UI panel -- 5 hours

Total: ~21 hours for 80% of the practical value, no DAG engine, no canvas, no migration.

**Counterargument:** The 21-hour approach creates a fourth scheduling system and more divergence. The DAG engine is an investment that pays off as Hestia grows. Every future background task becomes a visible, configurable, debuggable workflow instead of a hardcoded async loop.

**Verdict:** The DAG engine is the right long-term investment, but the 21-hour quick approach should inform Phase 0 and early Phase 1. Get Orders actually executing ASAP, then layer the DAG engine on top.

### Moonshot: AI-Generated Workflows
**What if Hestia could build workflows from natural language?** "Every morning at 8am, check my email for anything from my boss, summarize it, and ping my phone if it's urgent."

- **Technical viability:** Yes -- Hestia already has LLM inference, tool schemas, and the workflow data model. An "AI Workflow Builder" prompt could generate the JSON workflow definition.
- **Effort estimate:** 8-12 hours on top of a working workflow engine (P2+).
- **Risk:** LLM-generated workflows could have subtle logic errors (wrong condition operators, missing error paths).
- **MVP:** Natural language -> workflow JSON -> human reviews in canvas before activation.
- **Verdict:** SHELVE until P2 canvas is working. Then it becomes a compelling demo and daily-use feature.

---

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 4 | Credential isolation via Keychain, sandboxed execution, trading safety boundary preserved. -1 for webhook auth deferred to P3. |
| Empathy | 5 | Directly serves Andrew's need for visibility and control over Hestia's background behavior. |
| Simplicity | 3 | 91 hours is not simple. The re-scoped plan is significantly simpler than the original (engine-first, list UI in P1), but still a large investment. |
| Joy | 5 | A visual workflow canvas where you can see Hestia executing multi-step automations in real-time? That's the Jarvis dream. |

---

## Recommendation

**Proceed with the re-scoped 4-phase plan (91h).** The existing brainstorm is architecturally sound but the phase ordering was wrong -- it front-loaded canvas UI risk. The revised plan:

1. **Starts with Phase 0** (6h) to fix the Orders execution stub, delivering immediate value.
2. **Phase 1** (30h) builds the engine with a pragmatic list-based UI, not a canvas. This proves the execution model and delivers working workflows.
3. **Phase 2** (25h) adds the visual canvas and advanced features (conditions, data pinning, sub-workflows) once the engine is battle-tested.
4. **Phases 3-4** (30h) add event triggers, trading integration, and polish.

**Confidence: High** that the architecture is correct. **Medium** that the 91h estimate holds -- canvas UI is the wildcard.

**What would change this recommendation:**
- If the M5 Ultra Mac Studio arrives before P3, the token budget and concurrency concerns change significantly.
- If Andrew decides he doesn't need the canvas and a list-based workflow manager is sufficient, skip P2's canvas work (save ~17h) and focus on event triggers instead.
- If a production-quality SwiftUI node editor library emerges, P2 canvas effort drops by 50%.

---

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** You're a single developer building a workflow engine. Airflow has 2000+ contributors. n8n has 100+. You'll hit edge cases in DAG execution (circular dependency detection, parallel branch deadlocks, partial failure recovery) that take weeks to debug.

**Response:** Fair, but the scope is radically different. This is single-user, single-machine, max 50 nodes per workflow. No distributed execution, no multi-tenant isolation, no plugin marketplace. The DAGExecutor with TaskGroup + SQLite checkpointing is ~200 lines of Python for the core algorithm. The brainstorm already addresses the hardest edge cases (dead path elimination for join deadlocks, version snapshotting for edit-during-execution). The remaining risk is in the unknown unknowns -- which is why P1 has no canvas (reduce variables, prove the engine first).

### The Pragmatist: "Is the effort worth it?"
**Challenge:** 91 hours = 7.5 weeks at 12h/week. That's 2 months where Trading Sprints 28-30 don't advance. Is a workflow engine more valuable than Alpaca stock trading, regime detection, and Optuna optimization?

**Response:** The workflow engine is infrastructure that accelerates everything after it. Trading Sprint 28 (Alpaca) is self-contained and could run in parallel during P1 (they touch different code). But the honest answer is: if trading is generating real returns by the time this starts, prioritize trading. The workflow engine is a "force multiplier" -- it makes the system more capable but doesn't generate direct value the way trading does.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** In 6 months, you'll have a custom workflow engine that only you use. n8n will have added AI features, more integrations, and community-built templates. Was building custom the right call?

**Response:** Yes, because the value proposition is *integration depth*, not *integration breadth*. n8n can't route prompts through Hestia's council, can't access HealthKit data, can't manage trading bots, can't query the knowledge graph. The workflow engine is the glue that connects all of Hestia's unique capabilities. n8n would be a foreign body that can't access any of this. The custom engine's moat is that it *is* Hestia.

---

## Open Questions

1. **Phase 0 priority vs. Sprint 28:** Should Phase 0 (fix Orders execution) happen before or after Sprint 28 (Alpaca stocks)? They're independent -- could run in parallel.
2. **iOS workflow view:** The brainstorm defers iOS to "command-center summary." Should P1 include a basic iOS workflow list (read-only)?
3. **LearningScheduler migration timeline:** When (if ever) do the 9 learning monitors become workflow nodes? Recommendation: never force it -- migrate opportunistically when a monitor needs changes.
4. **EventKit entitlements:** macOS Sequoia tightened Calendar/Reminders access. Need to verify entitlements for background EventKit observers before P3 planning.
5. **Canvas technology decision:** Use SwiftNodeEditor (unstable API), build custom on SwiftUI Canvas, or hybrid approach (Canvas rendering + AppKit for complex gestures)?
