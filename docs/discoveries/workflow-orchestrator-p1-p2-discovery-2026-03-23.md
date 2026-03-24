# Discovery Report: Workflow Orchestrator P1 (Engine + List UI) & P2 (Canvas + Conditions)

**Date:** 2026-03-23
**Confidence:** High
**Decision:** Build custom DAG executor using graphlib.TopologicalSorter + asyncio.TaskGroup with SQLite persistence. For P2 canvas, use WebView + React Flow (bundled offline) as the primary path, with AudioKit Flow as the native SwiftUI alternative to evaluate during a P1 spike.

## Hypothesis

Can we build a production-quality DAG workflow execution engine (P1) and visual node editor (P2) for Hestia that delivers n8n-level capability at single-user scale, using Python's standard library for graph execution and either native SwiftUI or WebView+React Flow for the canvas UI?

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** P0 adapter proven (handler.handle() works from background context). Established manager pattern (models+database+manager) eliminates architecture decisions. SQLite sufficient for single-user workloads. WKWebView already used in codebase (MarkdownWebView for wiki). APScheduler integration battle-tested in OrderScheduler. graphlib.TopologicalSorter is stdlib (zero deps). asyncio.TaskGroup provides structured concurrency with proper cleanup. | **Weaknesses:** No production Python DAG library fits (all too minimal or too heavy). 20+ node config forms = significant UI work regardless of canvas tech. SQLite checkpointing is unconventional (no documented precedent in async DAG engines). SwiftUI node editor ecosystem is immature (390-star AudioKit Flow is the best option). Gemini flagged: TopologicalSorter+TaskGroup requires careful deadlock prevention (signaling mechanism needed). |
| **External** | **Opportunities:** React Flow v12 (@xyflow/react) is the dominant node editor library (mature, well-documented, MIT). Bundling React app into WKWebView is a proven pattern (Vite base:'./' + loadFileURL). AudioKit Flow (MIT, 390 stars) is the first credible native SwiftUI node editor. objc.io published an 8-part SwiftUI node editor tutorial series (July 2025). Python graphlib+asyncio pattern documented by multiple authors. | **Threats:** React Flow bundle is ~1.2MB (acceptable but adds build complexity). WKWebView<->Swift bridge adds a communication layer to debug. AudioKit Flow API may not be stable enough for production. n8n's execution model is fundamentally different (streaming item-based, not topological sort) — we're building a novel executor, not copying a proven one. Scope creep from n8n feature-parity ambitions. |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Custom DAGExecutor with TopologicalSorter+TaskGroup (core engine). SQLite persistence model (workflows/nodes/edges/runs). Workflow CRUD API (14 endpoints). Inference semaphore (max 1-2 concurrent Ollama calls). Circular dependency detection at save time. | Orders-to-Workflows migration script. node_executions retention policy (30-day auto-purge). |
| **Low Priority** | WebView+React Flow canvas (P2, high value but deferrable). AudioKit Flow evaluation spike (1-2 days). | Sugiyama auto-layout. Semantic zoom. Execution replay. Form-from-schema system. |

---

## Argue (Best Case)

**The custom DAG executor is the right call:**
- graphlib.TopologicalSorter handles the hard graph traversal problem (cycle detection, level ordering) in stdlib
- asyncio.TaskGroup provides structured concurrency — if one node fails, all parallel nodes are cancelled cleanly, which is exactly the behavior we want
- The integration depth with Hestia (InferenceClient, ToolExecutor, MemoryManager, NotificationRelay) makes wrapping an external engine more work than building from scratch
- n8n, Prefect, Temporal are all massively overbuilt for single-user — n8n alone is 100K+ lines of TypeScript
- The pattern is documented: TopologicalSorter.prepare() -> get_ready() -> execute parallel -> done() -> repeat. Multiple blog posts and SO answers validate it

**WebView+React Flow for P2 canvas is pragmatic:**
- React Flow has 25K+ GitHub stars, active development, comprehensive docs, and handles all the hard UX (zoom, pan, minimap, edge routing, drag, selection, keyboard shortcuts)
- Building this from scratch in SwiftUI would be 40-50h of uncertain work
- The Hestia codebase already has WKWebView infrastructure (MarkdownWebView) with JS bridge patterns
- Bundle size (~1.2MB) is trivial for a local-only macOS app
- Offline loading via loadFileURL is proven (Vite base:'./' config)
- Bidirectional communication via WKScriptMessageHandlerWithReply provides clean Swift<->JS messaging

**The persistence model is sound:**
- SQLite JSON columns for node config is correct for 20+ subtypes (no schema migration per node type)
- Version snapshotting on activate prevents edit-during-execution bugs
- The schema matches the brainstorm doc exactly and has been reviewed twice (internal + Gemini)

---

## Refute (Devil's Advocate)

**Custom DAG executor risks:**
- **No production precedent.** Gemini found zero production frameworks using TopologicalSorter+TaskGroup. We're building novel infrastructure, not copying proven patterns. Every DAG engine that exists (Temporal, Prefect, Airflow) uses fundamentally different execution models.
- **Deadlock risk.** TopologicalSorter + TaskGroup has a known deadlock trap: if get_ready() returns empty but is_active() is true, the executor busy-waits forever. Requires an asyncio.Event signaling mechanism. This is a subtle bug that tests may not catch.
- **Error propagation complexity.** TaskGroup cancels all tasks on first failure. But TopologicalSorter requires done() to be called for failed nodes too. The interaction between these two cleanup mechanisms needs careful design.
- **SQLite checkpointing is unconventional.** Gemini explicitly flagged this: "no significant evidence of SQLite being used as a primary checkpointing store for production async DAG engines." Concurrent writes from parallel tasks could cause issues (SQLite WAL mode mitigates but doesn't eliminate).

**WebView+React Flow risks:**
- **Two tech stacks.** The canvas is React/JS, everything else is Swift. Debugging crosses language boundaries. Build pipeline now includes npm/Vite alongside Xcode.
- **Communication overhead.** Every node move, connection, and config change crosses the WKWebView bridge. Latency is low (~1-5ms per message) but it's another layer of indirection.
- **React Flow dependency.** Pinning to a specific version of a JS library means monitoring for breaking changes. React Flow v12 had breaking changes from v11.
- **Non-native feel.** Despite dark theme CSS, WebView content doesn't perfectly match native SwiftUI look and feel (selection, right-click menus, accessibility, keyboard shortcuts may behave differently).

**AudioKit Flow as alternative:**
- Only 390 stars, 29 forks, 5 releases. Not battle-tested at scale.
- Built for audio signal chains, not workflow automation. May lack condition node semantics (true/false ports), execution state visualization, inspector panels.
- Would require significant extension for Hestia's use case.

**Scope concerns:**
- The brainstorm doc lists 10 trigger types, 10 action types, 6 condition types, 6 control types = 32 node types total. Even implementing 10 for P1+P2 is substantial.
- n8n has 400+ node types built by a team over 7 years. "n8n-level" is an impossible bar for a solo project.

---

## Third-Party Evidence

**graphlib.TopologicalSorter + asyncio:**
- Simon Willison documented using TopologicalSorter for parallel downloads (til.simonwillison.net)
- DEV Community article by Roman K. shows the full async pattern with create_task and done() callbacks
- Stack Overflow thread discusses the deadlock pitfall and signaling solution

**React Flow adoption:**
- Used by Stripe, Discord, and other major companies for internal tooling
- npm weekly downloads: 500K+ for @xyflow/react
- 8 example projects on reactflow.dev covering custom nodes, subflows, validation

**n8n execution model (Gemini finding):**
- n8n does NOT use topological sort. It uses dynamic, streaming, item-based execution — walking connections node by node. This means our approach is architecturally different from n8n, which is fine but means we can't use n8n as a direct reference implementation.

**SwiftUI Canvas performance:**
- Tests show Canvas uses significantly less CPU and memory than stacked Views for 50+ elements
- AsyncCanvas extension available for intensive rendering
- objc.io 8-part tutorial demonstrates production-quality node editor patterns in pure SwiftUI

---

## Gemini Web-Grounded Validation

**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- asyncio.TaskGroup + TopologicalSorter is a viable pattern for custom DAG execution (documented in community, though not in production frameworks)
- React Flow can be bundled into self-contained static files and loaded via WKWebView.loadFileURL() for fully offline use
- Vite `base: './'` + Xcode "Create folder references" is the correct bundling approach

### Contradicted Findings
- **SQLite checkpointing:** Gemini found "no significant evidence" of SQLite as a primary checkpoint store for async DAG engines. This was presented as a strength in the brainstorm but is actually an unconventional choice without documented precedent. Mitigation: WAL mode for concurrent writes, and the single-user constraint means contention is minimal.
- **n8n's execution model:** The brainstorm implied our TopologicalSorter approach mirrors n8n. Gemini revealed n8n uses a fundamentally different streaming, item-based model. Our approach is novel, not n8n-inspired.

### New Evidence
- **AudioKit Flow** (github.com/AudioKit/Flow, MIT, 390 stars) is a generic SwiftUI node graph editor using single-Canvas rendering. This was not in the original research. It's the most credible native SwiftUI option if we want to avoid WebView.
- **Deadlock prevention:** TopologicalSorter + TaskGroup requires an asyncio.Event signaling mechanism to prevent busy-waiting when get_ready() returns empty but is_active() is true.
- **Concurrency limiting:** TopologicalSorter can return many ready nodes at once. An asyncio.Semaphore is needed to cap concurrent execution (critical for Ollama on M1 with single GPU).

### Sources
- [Stack Overflow: asyncio + graphlib](https://stackoverflow.com/questions/69359364/python-asyncio-how-to-process-a-dependency-graph-asynchronously)
- [Stack Overflow: Loading local files in WKWebView](https://stackoverflow.com/questions/24022890/how-to-load-local-files-in-wkwebview)
- [AudioKit Flow](https://github.com/AudioKit/Flow)
- [n8n Data Flow docs](https://docs.n8n.io/concepts/data-flow/)
- [React Flow](https://reactflow.dev)
- [DEV: Processing DAGs with async Python and graphlib](https://dev.to/romank/processing-dags-with-async-python-and-graphlib-2c0g)

---

## Deep-Dive: Key Architecture Decisions

### Decision 1: DAGExecutor Implementation

**Recommended pattern (revised from brainstorm):**

```python
class DAGExecutor:
    async def execute(self, workflow, trigger_data):
        sorter = TopologicalSorter(self._build_graph(workflow))
        sorter.prepare()

        ready_event = asyncio.Event()
        semaphore = asyncio.Semaphore(2)  # Max 2 concurrent nodes (Ollama constraint)

        while sorter.is_active():
            ready_nodes = sorter.get_ready()
            if not ready_nodes:
                ready_event.clear()
                await ready_event.wait()  # Prevents busy-wait deadlock
                continue

            async with asyncio.TaskGroup() as tg:
                for node in ready_nodes:
                    tg.create_task(self._execute_node(node, sorter, semaphore, ready_event))

    async def _execute_node(self, node, sorter, semaphore, ready_event):
        async with semaphore:
            try:
                result = await self._run_node(node)
                await self._checkpoint(node, result)
            finally:
                sorter.done(node.id)  # ALWAYS call done, even on failure
                ready_event.set()  # Wake up main loop
```

Key differences from brainstorm:
1. **asyncio.Event signaling** prevents busy-wait deadlock (Gemini finding)
2. **asyncio.Semaphore(2)** caps concurrent Ollama calls (second opinion requirement)
3. **done() in finally block** prevents graph hang on failure
4. Uses stdlib TopologicalSorter instead of custom in-degree tracking

### Decision 2: Canvas Technology — Three Options Evaluated

| Criteria | WebView + React Flow | AudioKit Flow (Native) | Custom SwiftUI Canvas |
|----------|---------------------|----------------------|---------------------|
| **Effort (P2)** | 20-25h | 25-35h | 40-50h |
| **Risk** | Low (proven library) | Medium (390 stars, audio-focused) | High (no production reference) |
| **Native feel** | 85% (CSS theming) | 100% (pure SwiftUI) | 100% |
| **Feature completeness** | Zoom, pan, minimap, edge routing, keyboard shortcuts, selection, subflows — all built-in | Nodes, wires, Canvas rendering — built-in. Inspector, conditions, execution state — must build | Everything must be built |
| **Build pipeline** | Adds npm/Vite to build | Swift Package Manager | No new deps |
| **Debugging** | Cross-language (Swift + JS) | Swift only | Swift only |
| **Accessibility** | Requires custom work | Requires custom work | Full SwiftUI integration |
| **Precedent in codebase** | Yes (MarkdownWebView) | No | No |

**Recommendation: WebView + React Flow as primary, with a 2-day AudioKit Flow spike during P1.**

Rationale: React Flow eliminates 70% of the canvas work (zoom/pan/edge routing/selection/minimap are the hardest parts). The 15% native-feel gap is acceptable for a power-user automation tool. AudioKit Flow is the only credible native alternative — if the spike shows it can handle workflow semantics (multi-port nodes, condition branching, execution state overlay), it becomes viable for P2.

### Decision 3: Persistence Model

The brainstorm schema is sound. Two additions based on research:

1. **`retry_count` on `node_executions`** (second opinion gap)
2. **`user_id` on `workflow_runs`** (future multi-user support, add column now even if always 'default')
3. **WAL mode** for SQLite (Gemini flag about concurrent writes from parallel tasks)
4. **30-day retention policy** with auto-purge on `node_executions` (CISO requirement for PII safety)

---

## Philosophical Layer

### Ethical Check
Building workflow automation for a personal assistant is productive and ethical. No PII leaves the device. The retention policy ensures health/email data in node_executions is auto-purged. No concerns.

### First Principles Challenge
**Why build a custom DAG engine instead of using Prefect/Temporal?**
- Prefect requires a server component and cloud account for full functionality
- Temporal requires a separate Go/Java service
- Both are 100x overbuilt for single-user workflows
- The integration depth with Hestia's inference pipeline, tool executor, and memory system means wrapping an external engine would be more code than building from scratch
- The core algorithm (TopologicalSorter + TaskGroup) is ~200 lines of Python. The bulk of P1 effort is in the persistence layer, API endpoints, and node implementations — work that's needed regardless of execution engine choice.

### Moonshot: Natural Language Workflow Builder
**What if you could say "Every morning, check my email for anything urgent, summarize it, and notify my phone" and Hestia builds the workflow automatically?**

- Technical viability: HIGH. The node taxonomy is well-defined. An LLM can map natural language to a DAG of typed nodes. The constraint (fixed node types with known config schemas) makes this tractable.
- Effort: 15-20h on top of P1+P2 (needs: prompt engineering, DAG construction from LLM output, validation, preview-before-activate)
- Risk: LLM may produce invalid graphs. Mitigation: circular dependency detection + config schema validation before save.
- MVP: "Describe a workflow in one sentence" -> Hestia generates the DAG -> user reviews on canvas -> activate
- **Verdict: SHELVE for now, PURSUE after P2 is stable.** This is the killer feature that would make workflow orchestration truly Jarvis-like. What would change the answer: if P2 canvas proves too complex, NL builder could bypass it entirely.

### Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 4 | Local-only, existing auth. -1 for PII retention gap (fixable with auto-purge). |
| Empathy | 5 | Directly serves Andrew's automation needs. Visible execution = trust. |
| Simplicity | 3 | 100+ hours is not simple. But phased delivery means each phase is independently valuable. Custom engine is simpler than wrapping Temporal. |
| Joy | 5 | Visual workflows executing in real-time with green/red/amber node feedback = the dream. |

---

## Recommendation

**Build P1 and P2 as planned, with these specific refinements:**

### P1: Engine + List UI (~35h)
1. **DAGExecutor** using `graphlib.TopologicalSorter` + `asyncio.TaskGroup` with Event signaling and Semaphore(2) concurrency limit
2. **SQLite persistence** with WAL mode, the brainstorm schema + retry_count + user_id columns
3. **4 action nodes** (RunPrompt, CallTool, Notify, Log) + 2 trigger nodes (Schedule, Manual)
4. **14 API endpoints** per brainstorm
5. **Circular dependency detection** at workflow save time (TopologicalSorter raises CycleError — use this directly)
6. **30-day auto-purge** on node_executions
7. **Orders migration** script
8. **macOS list UI** with execution data inspection (input/output per node in failed runs)
9. **2-day AudioKit Flow spike** (non-blocking, throwaway prototype to evaluate native canvas feasibility)
10. **150+ tests** with explicit topology fixtures (linear, fan-out, fan-in, dead-path, checkpoint-resume, cycle-rejection)

### P2: Canvas + Conditions (~18-25h)
- **Primary path: WebView + React Flow** (bundled via Vite, loaded from app bundle via loadFileURL)
- **If AudioKit Flow spike succeeds:** Evaluate native path (may add 10h but eliminate JS build pipeline)
- **ConditionEvaluator** with expression engine
- **If/Else and Switch** condition nodes with multi-port routing
- **Variable interpolation** (simple templates P1, JMESPath P2)
- **Edge port routing** (true/false/error paths)

### Confidence: HIGH

The engine architecture is sound. The canvas technology choice (WebView+React Flow) eliminates the highest-risk item from the original plan. The only remaining uncertainty is whether AudioKit Flow could replace React Flow for a fully native solution — the 2-day spike resolves this without blocking P1.

### What would change the recommendation:
- If AudioKit Flow spike shows it can handle multi-port nodes, condition branching, and execution state overlay with <25h effort, switch to native
- If TopologicalSorter+TaskGroup deadlock issues surface in testing, fall back to manual in-degree tracking (the brainstorm's original approach, which avoids the signaling complexity)
- If P1 takes >45h, cut P2 canvas and keep list UI permanently (the "half-time cut" from the second opinion)

---

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** The TopologicalSorter+TaskGroup pattern has zero production precedents. You're building novel infrastructure on a pattern that exists only in blog posts and SO answers.
**Response:** The pattern is simple enough that "no production precedent" is less alarming than it sounds. TopologicalSorter is stdlib — it's been in CPython since 3.9 and is well-tested. TaskGroup is stdlib since 3.11. The novel part is combining them, which is ~200 lines of code with 3 known pitfalls (deadlock, error propagation, concurrency), all of which have documented solutions. The real complexity is in the node implementations and persistence, which are standard Hestia patterns.

### The Pragmatist: "Is the effort worth it?"
**Challenge:** 53-60h for P1+P2. That's 4-5 weeks of Andrew's time. Trading sprints 28-30 are delayed. What's the ROI?
**Response:** P1 alone (35h) delivers a working DAG engine that replaces the stubbed Orders system, enables multi-step automation, and provides visible execution history. This is the feature that makes Hestia an automation platform vs. a chat bot. P2 (canvas) is deferrable — the list UI is permanently viable. The half-time cut (P1 only, 35h) delivers 80% of value. Trading sprints can resume after P1 if P2 is deferred.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** In 6 months, you'll have 15-20 workflows running. Will the single-process executor hold up? Will SQLite checkpointing work at scale?
**Response:** At 15-20 workflows with M1's single GPU, the Semaphore(2) constraint means at most 2 LLM calls run concurrently. SQLite handles thousands of writes/second — workflow execution generates maybe 10 writes per run. The real constraint is Ollama, not the engine. When the M5 Ultra Mac Studio arrives (summer 2026), the Semaphore can be raised to 4-8. The architecture scales linearly with hardware.

---

## Open Questions

1. **AudioKit Flow evaluation:** Can it handle multi-port output nodes (true/false for conditions)? Does it support edge labels? Custom node shapes/colors? This is the 2-day spike deliverable.
2. **React Flow build pipeline:** Exact Vite config for bundling. Should the React app be a separate repo or a subdirectory of HestiaApp? Recommend: `HestiaApp/WorkflowCanvas/` subdirectory with its own package.json.
3. **Ollama semaphore scope:** Should the semaphore be per-workflow or global? Global is simpler and correct for M1 (one GPU). Per-workflow would allow multiple workflows to each use one slot — but that's the same as global with a higher limit.
4. **Fan-in data merging:** How do join nodes handle multiple upstream outputs? Options: (a) dict of {source_node_id: output}, (b) merge all into flat dict (conflict resolution?), (c) array of outputs. Recommend (a) — explicit and no ambiguity.
5. **EventKit entitlements:** macOS Sequoia tightened Calendar/Reminders access for background processes. Need to verify entitlements before P3 (event triggers).
