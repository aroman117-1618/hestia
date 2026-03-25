# Session Handoff — 2026-03-25 (Workflow Engine Deep Fix)

## Mission
Investigate why "Evening Research" order showed success but produced no Notes output. Turned into a deep-dive fixing 12+ issues across the workflow engine, inference routing, tool execution, cloud provider integration, and macOS app UI.

## Completed

### Workflow Engine Fixes (7 commits)
- **False success reporting** — `run_prompt` nodes with `error_code` in output now fail instead of false-success (`executor.py`)
- **`allowed_tools` filtering** — handler now filters tool definitions by workflow node's `allowed_tools` config (`handler.py`)
- **PRIMARY model timeout** — bumped 90s to 180s for complex prompts (`inference.yaml`)
- **Fire-and-forget trigger** — "Run Now" returns immediately, executes via `asyncio.create_task()` (`workflows.py`, `manager.py`)
- **Gate bypass for workflows** — `skip_gate` param on ToolExecutor, set for WORKFLOW-sourced requests (`executor.py`, `handler.py`)
- **Autonomous execution directive** — prepended to all workflow prompts so LLM acts without asking permission (`adapter.py`)
- **CODING model timeout** — bumped to 180s to match PRIMARY (`inference.yaml`)

### Inference Routing Fixes (3 commits)
- **Skip complex model for tool requests** — R1 (no tool support) skipped when `has_tools=True` (`router.py`)
- **Route tool-calling to CODING tier** — `has_tools` requests go to Qwen 3 8B instead of 9B PRIMARY (`router.py`)
- **force_cloud synthesis** — tool result synthesis now honors `inference_route: full_cloud` and skips council synthesis path (`handler.py`)

### Tool Execution Optimizations (1 commit)
- **Parallel tool execution** — `asyncio.gather()` for native tool calls instead of sequential loop (`handler.py`)
- **investigate_url timeout** — 120s to 300s (`tools.py`)
- **trafilatura fetch timeout** — 30s to 15s for faster fail on slow CDNs (`web.py`)

### Cloud Provider Infrastructure (1 commit)
- **Encrypted file fallback for API keys** — survives launchd restarts when Keychain is inaccessible. Store: Keychain + `.enc` file. Retrieve: Keychain -> file -> in-memory. Init seeds file from Keychain on GUI-session startups (`cloud/manager.py`)

### Server Stability (1 commit)
- **Request recycle limit** — `limit_max_requests` bumped 5000 to 50000. Was the root cause of server crashes during workflow execution (`server.py`)

### macOS App UI (3 commits)
- **Research tab renamed to Memory** — sidebar, accessibility, view header, menu bar (`IconSidebar.swift`, `Accessibility.swift`, `ResearchView.swift`, `AppDelegate.swift`)
- **Workflow editing** — Edit button in action bar, edit sheet for name/description, `updateWorkflow()` wired in ViewModel. Config/label edits allowed on active workflows (`MacEditWorkflowSheet.swift`, `MacWorkflowDetailPane.swift`, `MacWorkflowViewModel.swift`, `manager.py`)
- **Per-node inference route toggle** — Local/Smart/Cloud segmented picker replaces Force Local toggle + Model picker (`MacNodeInspectorView.swift`, `models.py`, `nodes.py`, `adapter.py`, `handler.py`)
- **Expandable run history with error logs** — failed runs show `errorMessage` inline, tap to expand shows per-node execution status/duration/errors via new `GET /workflows/{id}/runs/{run_id}` endpoint (`MacWorkflowDetailPane.swift`, `WorkflowModels.swift`, `APIClient+Workflows.swift`, `workflows.py`)
- **Node rows tappable in list view** — opens inspector sheet for editing without canvas
- **Pre-push hook** — now runs `xcodegen generate` before `xcodebuild` to pick up new files (`pre-push.sh`)

### Config
- Anthropic cloud provider configured on Mac Mini (claude-sonnet-4-20250514, enabled_smart)
- Evening Research workflow node set to `inference_route: full_cloud` with 13 allowed tools

## In Progress / NOT DONE

### CRITICAL: Multi-Turn Tool Loop for Cloud Inference
**This is the remaining blocker for Evening Research actually writing to Notes.**

**What happens now:** Claude Sonnet receives the prompt + tool definitions, returns a response with `stop_reason: "tool_use"` containing `list_events` as a native tool call. The handler executes `list_events`, gets calendar data, then does a **synthesis** call (personality formatting). The synthesis response contains the research content — but Claude wrote `<create_note>` and `<search_web>` as **XML in the text** instead of native tool calls, because it was a synthesis/follow-up call that didn't include tool definitions.

**Root cause:** The handler's tool execution is **single-turn**. It calls inference once, executes any returned tool calls, then does synthesis. But Claude's intended workflow is multi-turn:
1. Call `list_events` -> get results
2. Call `investigate_url` (anthropic.com) -> get results
3. Call `investigate_url` (arxiv.org) -> get results
4. Call `create_note` with compiled research -> done

The handler only does step 1, then synthesizes. Steps 2-4 never happen because the handler doesn't feed tool results back and let Claude make more tool calls.

**Fix needed:** Implement a tool-calling loop in `_execute_native_tool_calls` (or a new method):
```
while response.tool_calls and iteration < MAX_TOOL_ITERATIONS:
    execute tool calls in parallel
    append tool results as messages
    call inference again with updated messages + tools
```

This is the same pattern as OpenAI's function calling loop or Anthropic's agentic loop. The handler currently does one-shot tool execution — it needs to loop until `stop_reason: "end_turn"` (Anthropic) or `finish_reason: "stop"` (OpenAI).

**Files to modify:**
- `hestia/orchestration/handler.py` — `_call_inference_with_retries()` method (lines ~1740-1870). Add a loop that checks `inference_response.tool_calls`, executes them, appends results as messages, and re-calls inference.
- `hestia/inference/client.py` — `InferenceResponse.finish_reason` is already populated. Check for `"tool_use"` (Anthropic) or `"tool_calls"` (OpenAI) to decide whether to loop.
- Consider a `MAX_TOOL_ITERATIONS = 10` safety limit to prevent infinite loops.
- The `force_cloud` flag must persist across all iterations of the loop.

**Estimated effort:** 2-3 hours. Medium complexity — the handler refactor is the hard part.

### Inspector Config Preservation
When saving a node from the inspector, the entire config dict is replaced with only the fields the inspector manages. Fields like `allowed_tools` (set during workflow creation) get wiped.

**Fix:** Inspector's `saveChanges()` should merge with existing config instead of replacing. Read current config, overlay changed fields, send merged result.

**File:** `MacNodeInspectorView.swift` — `saveChanges()` method (~line 496)

## Decisions Made
- `limit_max_requests: 50000` (was 5000) — Uvicorn worker recycling was the #1 cause of mid-run server restarts
- Tool-calling requests route to CODING tier (Qwen 3 8B) — optimized for native tool calling, smaller than PRIMARY
- Workflow tool calls bypass the external communication gate — orders are pre-approved directives
- Autonomous execution directive prepended to ALL workflow prompts — prevents LLM from asking for confirmation
- Encrypted file fallback for cloud API keys — workaround for launchd Keychain access limitations
- Council synthesis skipped for `force_cloud` requests — council has its own routing that doesn't honor `inference_route`

## Test Status
- 2906 tests collected, all passing (backend)
- Pre-existing: `test_inference.py::test_simple_completion` times out intermittently (Ollama integration test, hardware-dependent)

## Uncommitted Changes
- `hestia/data/` — runtime data directory (gitignored)
- No code changes uncommitted

## Known Issues / Landmines
1. **Multi-turn tool loop not implemented** — Cloud inference returns one round of tool calls, but complex workflows need multiple rounds (see "In Progress" above)
2. **Inspector config wipe** — Saving from node inspector replaces full config, dropping `allowed_tools`. Workaround: manually restore via DB after inspector save
3. **Canvas not rendering nodes** — The React Flow canvas shows empty for the Evening Research workflow. List view works. Likely a node position issue (all at 0,0) or WebView loading issue
4. **Duplicate runs on "Run Now"** — Sometimes two runs are created per click (visible in logs as two `force_cloud` routing decisions with near-identical timestamps). Likely a double-tap or missing debounce in the macOS app
5. **Cloud model detection HTTPStatusError** — Anthropic model list endpoint fails during provider setup. Doesn't block functionality (fallback model list works)

## Process Learnings (Retrospective)

### Session Metrics
- **Duration:** ~6 hours
- **Commits:** 15+
- **First-pass success rate:** ~4/15 commits (27%) — most required follow-up fixes
- **Rework causes:** Incomplete understanding of execution chain, testing in production instead of locally, cascading dependencies between fixes
- **Top blocker:** Lack of end-to-end integration test for workflow execution with cloud inference

### What Went Wrong: The Debugging Spiral

This session fell into a **serial debugging spiral** — each fix revealed the next issue in the chain, and we tested each fix by triggering a manual run on the Mac Mini (30-60s per attempt), only to discover the next layer of the problem. The chain was:

1. False success reporting -> fix
2. Tool definitions not filtered -> fix
3. Model timeout too low -> fix
4. Run Now button blocks HTTP -> fix
5. LLM asks for permission instead of acting -> fix (autonomous directive)
6. Wrong model (R1) selected for tool calls -> fix
7. Coding model timeout also too low -> fix
8. Communication gate blocks create_note -> fix
9. investigate_url timeout too low + sequential execution -> fix
10. Cloud API key not on Mac Mini -> manual config
11. API key returns 401 -> re-add key
12. Keychain inaccessible after launchd restart -> fix (file fallback)
13. Server recycling mid-run (limit_max_requests: 5000) -> fix
14. Council synthesis doesn't honor force_cloud -> fix
15. Multi-turn tool loop needed -> NOT YET FIXED

**Each fix was individually correct but none were tested in combination before deploying.** We should have:
- Traced the FULL execution chain in Phase 1 research before writing ANY code
- Built a local integration test that simulates the workflow instead of testing on the live Mini
- Identified ALL the layers (routing, gating, timeouts, cloud, synthesis) upfront

### Specific Lessons

**LESSON 1: Trace before you fix.**
The initial investigation correctly identified 3 issues (false success, tool filtering, timeout). But we missed 12 more because we didn't trace the complete path: prompt -> routing -> inference -> tool calls -> gate -> execution -> synthesis -> response. A complete trace in Phase 1 would have revealed most issues upfront.

**LESSON 2: Don't test infrastructure changes on production.**
Every "Run Now" test was a 30-60s cycle with a 50% chance of hitting a new issue. A local integration test (mock Ollama + mock Anthropic + real workflow engine) would have caught issues in seconds.

**LESSON 3: limit_max_requests is a time bomb.**
5000 sounds high but with health checks (1/min), trading bots (4 bots * 30 min cycles), macOS app polling, and workflow tool calls, it exhausts in hours. This should have been caught by the server lifecycle tests.

**LESSON 4: Cloud inference needs an agentic tool loop.**
The handler was designed for local Ollama single-turn tool calling. Cloud models (Claude, GPT) expect multi-turn agentic loops where tool results are fed back and the model makes more calls. This is a fundamental architecture gap, not a bug.

### Process Improvement Proposals (Priority Order)

1. **SCRIPT: Workflow integration test** — Create `scripts/test-workflow-e2e.sh` that triggers a workflow run on the local server with mocked inference and verifies: routing, tool execution, gate bypass, note creation, error handling. Impact: Would have caught 10+ issues in this session. Effort: 3h.

2. **CLAUDE.MD: Document `limit_max_requests`** — Add to Server Management section. Note that it causes server recycling and should be set high enough for long-running workflows. Impact: Prevents future debugging of "server restarts mid-run". Effort: 5min.

3. **HOOK: Validate cloud inference path** — Pre-deploy check that verifies cloud provider is configured and key is retrievable when any workflow node has `inference_route: full_cloud`. Impact: Prevents "No API key" failures in production. Effort: 1h.

4. **AGENT: @hestia-reviewer should check for single-turn tool assumptions** — When reviewing handler changes involving tool calls, flag if there's no loop for multi-turn execution. Impact: Would have caught the agentic loop gap during code review. Effort: 30min (agent definition update).

5. **CLAUDE.MD: Document inference routing chain** — Add a section explaining: prompt -> council -> routing -> model selection -> inference -> tool execution -> synthesis. The full chain is non-obvious and critical for debugging workflow issues. Impact: Saves hours of tracing in future sessions. Effort: 15min.

## Next Step

**Implement the multi-turn tool calling loop.** This is the ONE remaining fix to make Evening Research work end-to-end.

Specific actions:
1. Read `hestia/orchestration/handler.py:1740-1870` — understand the current single-turn flow
2. Read `hestia/inference/client.py` — check `InferenceResponse.finish_reason` values for cloud vs local
3. Implement a loop in `_call_inference_with_retries` that:
   - After executing tool calls, appends tool results as messages
   - Re-calls inference with updated messages + same tools
   - Continues until `finish_reason != "tool_use"` or `MAX_TOOL_ITERATIONS` reached
   - Passes `force_cloud` on every iteration
4. Test locally with a mock cloud response that returns tool_calls
5. Deploy and trigger Evening Research — verify `create_note` is called
6. Fix inspector config merge (preserving `allowed_tools` on save)
