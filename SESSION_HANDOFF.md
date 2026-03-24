# Session Handoff — 2026-03-23

## Mission
Review trading module accuracy vs docs, fix trading strategy bugs, then plan and begin building the Workflow Orchestrator P1 engine.

## Completed

### Trading Module Fixes
- **Signal DCA indicator period fix** — backtest engine now passes strategy-specific periods to `add_all_indicators()` via new `indicator_periods()` method on `BaseStrategy` (`32664d8`)
- **Mean Reversion exit logic** — added RSI-based profit exits (RSI>70 after BUY, RSI<30 after SELL) + stop-loss enforcement with position state tracking (`32664d8`)
- **SPRINT.md/CLAUDE.md accuracy** — updated to reflect actual trading state: paper soak live since 2026-03-19, Alpaca blocked on API key, backtest results documented

### Workflow Orchestrator P1 Backend (Steps 1-8 of 9)
- **Step 1** (`65fc1ec`): Models — 5 enums, 5 dataclasses, 45 tests
- **Step 2** (`65fc1ec`): Database — 6 SQLite tables, WAL mode, 34 tests
- **Step 3** (`75d488f`): Node executors — 7 types with safe condition evaluator
- **Step 4** (`75d488f`): DAG executor — TopologicalSorter + asyncio, 35 tests
- **Step 5** (`75d488f`): Event bus — SSE pub/sub
- **Step 6** (`10fa8d5`): Manager — CRUD + lifecycle + execution, 27 tests
- **Step 7** (`b1db9a8`): Scheduler + 15 API endpoints + server wiring, 13 tests
- **Step 8** (`9846de9`): Orders migration script, 11 tests

### Documentation
- Memory files updated: `roadmap-eras.md`, `trading-platform-pivot.md`
- Discovery report: `docs/discoveries/workflow-orchestrator-p1-p2-discovery-2026-03-23.md`
- Plan file: `.claude/plans/nifty-wiggling-platypus.md`

## In Progress
- **Step 9: macOS List UI** (~7h) — Not started. Need 8 Swift files:
  - `Shared/Models/WorkflowModels.swift` — Codable types
  - `macOS/ViewModels/MacWorkflowViewModel.swift` — @MainActor ObservableObject
  - `macOS/Views/Workflow/MacWorkflowView.swift` — sidebar+detail HStack
  - `macOS/Views/Workflow/MacWorkflowSidebarView.swift` — list + filter tabs
  - `macOS/Views/Workflow/MacWorkflowDetailPane.swift` — node list + run history
  - `macOS/Views/Workflow/MacWorkflowNodeRow.swift` — row component
  - `macOS/Views/Workflow/MacNewWorkflowSheet.swift` — creation modal
  - `macOS/Views/Workflow/MacNodeConfigSheet.swift` — per-type config editor
  - Also: update `project.yml` and sidebar navigation

## Decisions Made
- **Full P1 scope** (35h) over lean backend-only (20h) — Andrew chose full scope after @hestia-critic review
- **P2 canvas immediately after P1** — not gated on usage as critic suggested
- **WebView + React Flow primary canvas tech** (P2) — with AudioKit Flow native spike as alternative
- **Safe condition evaluator** — uses `operator` module, never arbitrary code execution
- **DAGExecutor architecture** — TopologicalSorter + asyncio.Event signaling + Semaphore(2) for M1

## Test Status
- **2809 backend tests collected** (183 new workflow tests)
- **1 pre-existing failure**: `test_inference.py::test_simple_completion` — Ollama not running locally (integration test)
- All workflow tests green

## Uncommitted Changes
- `HestiaApp/macOS/Views/Research/MacSceneKitGraphView.swift` — minor graph view changes (from earlier session)
- `docs/discoveries/workflow-orchestrator-p1-p2-discovery-2026-03-23.md` — untracked doc
- `docs/discoveries/knowledge-graph-viz-refinements-2026-03-23.md` — untracked doc
- `docs/discoveries/scenekit-metal-shader-modifiers-2026-03-23.md` — untracked doc
- `docs/mockups/` — untracked directory
- `docs/plans/consumer-product-strategy.md` — untracked plan
- `CLAUDE.md` / `SPRINT.md` — count + status updates (need committing)

## Known Issues / Landmines
- **Workflow scheduler import chain**: `scheduler.py` imports `get_workflow_manager` inside methods (deferred import) to avoid circular deps. If someone moves this to top-level, server startup will fail.
- **Route error handling**: Routes use `JSONResponse` with explicit status codes. The initial implementation used tuple returns `(dict, status)` which FastAPI silently ignores the status — this was caught and fixed but watch for it in new endpoints.
- **Node executor registry is mutable**: Tests that swap executors (`NODE_EXECUTORS[NodeType.LOG] = failing_executor`) must restore the original in `finally` blocks. Two tests do this correctly.
- **Uncommitted SceneKit changes**: `MacSceneKitGraphView.swift` has uncommitted changes from a prior session — don't accidentally commit with workflow work.

## Process Learnings
- **First-pass success**: 9/9 implementation steps succeeded on first attempt. The fan-in test (Step 4) had one timing bug fixed in <2 minutes. Route tests (Step 7) had two issues: auth dependency override pattern and tuple-return error responses — both patterns now documented.
- **Top blocker**: FastAPI's `Depends()` resolution can't be patched with `unittest.mock.patch` — must use `app.dependency_overrides`. This cost ~5 minutes.
- **Agent orchestration**: @hestia-tester used effectively after each step. @hestia-explorer used for initial codebase research (3 parallel agents). @hestia-critic provided valuable scope challenge that Andrew explicitly overrode.
- **Config proposal**: Add `JSONResponse` import and error pattern to CLAUDE.md conventions — prevents the tuple-return anti-pattern.

## Next Step
1. Start Step 9: macOS list UI. Begin with `Shared/Models/WorkflowModels.swift` (Codable types matching the API responses)
2. Then `MacWorkflowViewModel.swift` following `MacWikiViewModel` pattern
3. Then views following `MacWikiView` sidebar+detail pattern
4. Update `project.yml` to include new files in HestiaWorkspace target
5. Build both targets: `xcodebuild -scheme HestiaWorkspace` and `xcodebuild -scheme HestiaApp`
6. After Step 9: commit, then begin P2 (canvas + conditions)

**Reference files for UI patterns:**
- `MacWikiView.swift` — sidebar+detail layout
- `MacWikiSidebarView.swift` — tab navigation
- `MacTradingViewModel.swift` — SSE streaming
- `MacColors.swift` / `MacSpacing.swift` / `MacTypography.swift` — design tokens
- `NewOrderSheet.swift` — creation modal pattern
