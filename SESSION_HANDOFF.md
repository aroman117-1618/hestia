# Session Handoff — 2026-03-24 (Session C — Step Builder)

## Mission
Build the Workflow Step Builder — the UX layer that lets Andrew create, configure, and link workflow steps from the visual canvas. Then fix bugs found during live testing and ship to production.

## Completed

### Step Builder (11 tasks, 15 new tests)
- `ba82fe5` feat: DELAY node type — asyncio.sleep executor with 180-day cap
- `d46083f` feat: enhance GET /v1/tools/categories — labels, icons, parameter schemas
- `c983d06` feat: POST /nodes/from-step — Step-to-DAG translation endpoint (the "compiler")
- `f9070f1` feat: Swift models — StepCreateRequest, ToolCategory, NodeCreateRequest
- `86460f1` feat: 6 custom React Flow node components with typed handles
- `f800c21` feat: Add Step menu — right-click canvas + edge "+" button
- `fac8060` feat: bridge addStep handler — canvas → translation API → inspector auto-open
- `613bc89` feat: resource picker, DELAY inspector, auto-trigger on new workflow

### Bug Fixes (live testing)
- `8a5e8c6` fix: handle all step types in addStepFromCanvas (non-prompt types used direct node API)
- `7b6ca1c` fix: canvas re-renders on node add (tracked node/edge count, not just workflow ID)
- `c910dd2` fix: enlarge canvas handles for reliable edge connections
- `6aac9f3` fix: remove /v1 double prefix from all direct API calls in ViewModel
- `6aac9f3` fix: tool step defaults to read_file (backend rejects empty tool_name)
- `6aac9f3` fix: notification channel is segmented picker (macOS/Push/Both)
- `79b48a3` fix: delay limits — minutes/hours/days, min 1, max 180 days
- `1acffea` feat: memory_write + force_local toggles in prompt step inspector
- `2fe1392` feat: wire Workflows into Command Center System Activity card
- `ec20923` fix: rename "Workflows" to "Orders" across all user-facing strings

### Shipped
- v1.5.0 (build 22) — Step Builder core
- v1.5.1 (build 23) — Bug fixes + toggles
- v1.5.2 (build 24) — Orders rename + Command Center card

## In Progress
- None — all work completed and shipped

## Decisions Made
- **"Orders" not "Workflows"**: Andrew's intended terminology is "Orders" for user-facing UI. Backend stays `workflows` internally (API paths, type names, module names). Only display strings changed.
- **Step = compiler abstraction**: The UI presents Andrew's "Step" model (Title/Trigger/Prompt/Resources). The `POST /nodes/from-step` endpoint compiles this to backend DAG nodes (e.g., prompt step -> run_prompt node, delayed step -> delay + run_prompt nodes). Non-prompt types (notify, condition, tool, delay) use direct node creation.
- **DELAY node cap: 180 days**: Originally 1 hour, raised to 180 days per Andrew's request. Both backend executor and Swift UI enforce this.
- **Tool categories from registry**: The `Tool` dataclass already had `category` field and `ToolRegistry` had `get_tools_by_category()`. Enhanced existing `GET /v1/tools/categories` (was dict-keyed, now array with labels/icons/schemas).

## Test Status
- 2844 tests collected, 92 test files
- 216 workflow-specific tests pass (15 new this session)
- Full suite passes (hangs on exit due to ChromaDB background threads — known issue)
- 1 pre-existing skip: `test_inference.py::test_simple_completion` (Ollama integration)

## Uncommitted Changes
- Untracked discovery/plan docs from earlier sessions (not blocking):
  - `docs/discoveries/workflow-step-builder-ux-2026-03-24.md`
  - `docs/plans/workflow-step-builder-second-opinion-2026-03-24.md`
  - `docs/superpowers/plans/2026-03-24-workflow-step-builder.md`
  - Several other discovery/plan docs from parallel sessions

## Known Issues / Landmines
- **Mac Mini server needs the v1.5.2 deploy to complete** before the enhanced tools/categories endpoint works. The old format (dict-keyed) causes a Swift decode error. CI/CD should handle this automatically.
- **`handleEdgeCreated` in ViewModel** creates edges via direct `client.post("/workflows/...")` — not through a dedicated APIClient method. Works but inconsistent with other CRUD operations.
- **Canvas node config serialization**: `injectWorkflow` serializes `node.config` (which is `[String: AnyCodableValue]`) via JSONEncoder + JSONSerialization double-pass. Works but fragile for deeply nested configs.
- **Tool categories cached per-session**: `fetchToolCategories()` only fetches once. If tools are added/removed on the server, the app needs restart to see them.
- **SSE URL was double-prefixed**: Fixed from `/v1/workflows/stream` to `/workflows/stream` — but SSE streaming for workflow execution hasn't been tested end-to-end this session.

## Process Learnings
- **First-pass success**: 11/11 plan tasks completed on first subagent dispatch (100%). Bug fixes during live testing added 8 additional commits — these were UX issues only discoverable by using the app.
- **Top blocker**: The `/v1` double-prefix bug (pre-existing from prior session) caused 3 separate failures. A URL prefix lint hook would catch this pattern.
- **Subagent-driven development worked well**: Fresh context per task prevented confusion. Combined Tasks 5+6 (canvas) and 7-10 (Swift) for efficiency. Plan review caught 2 real blockers before execution.
- **Live testing is essential**: 8 of 18 commits were fixes discovered during Andrew's hands-on testing. No amount of unit tests catches "the canvas doesn't show my new node" or "I can't drag to connect nodes."

### Proposals
1. **HOOK: URL prefix lint** — Grep for `"/v1/` in Swift ViewModels. Expected: 0 occurrences. Impact: prevents the #1 recurring bug.
2. **CLAUDE.MD: Add "Orders = Workflows"** note — So future sessions don't re-introduce "Workflows" in user-facing strings.
3. **SCRIPT: Canvas visual regression** — After canvas TypeScript changes, screenshot a test workflow to catch rendering regressions.

## Next Step
- **Monitor the Evening Research workflow**: Andrew created a scheduled workflow (2 AM daily). After the Mac Mini deploy lands, activate it and verify the first execution completes:
  ```bash
  ssh andrewroman117@hestia-3.local 'sqlite3 ~/hestia/data/workflows.db "SELECT * FROM workflow_runs WHERE workflow_id = \"wf-3d895cc18f24\" ORDER BY started_at DESC LIMIT 3;"'
  ```
- **Commit the untracked docs**: The discovery/plan docs from this session should be committed.
- **Next feature work**: Step Builder Phase 1 complete. Phase 2 (drag-from-sidebar, auto-layout, Cmd+K search) deferred. Check SPRINT.md for next priority.
