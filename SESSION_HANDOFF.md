# Session Handoff — 2026-03-24 (Session D — Workflow Fix + Cloud Persona)

## Mission
Troubleshoot the failed Evening Research workflow, fix execution bugs, and enrich the cloud inference path so Andrew can use Hestia (via Anthropic) as a development interface with conversations feeding the memory pipeline.

## Completed
- **Evening Research workflow fixed** — 3 bugs in `hestia/workflows/nodes.py`:
  - `get_handler` → `get_request_handler` (ImportError, line 111)
  - `source="workflow"` → `context={"source": "workflow"}` on `create_bump()` (TypeError, line 195)
  - Added `config.get("message")` fallback for notify node body (config key mismatch)
- **Timeout infrastructure overhauled** — layered timeouts were too aggressive for R1 reasoning model:
  - `hestia/workflows/executor.py`: DEFAULT_PROMPT_TIMEOUT 120→600s, delay nodes exempt from timeout
  - `hestia/orchestration/state.py`: TaskState.PROCESSING 120→600s
- **Cloud persona wired** — `hestia/orchestration/prompt.py`:
  - Removed generic `CLOUD_SAFE_SYSTEM_PROMPT` constant
  - Cloud path now uses Tia/Mira/Olly persona (same as local), PII filtering unchanged
  - Principles and Knowledge Graph correctly excluded from cloud (they're Hestia-internal)
- **`/codebase-audit` skill enhanced** — Phase 9.5 added: Notion + GitHub sync verification
- **Hestia CLI installed on Mac Mini** — `pip install -e hestia-cli/`, alias added to `~/.zshrc`
- **Shipped v1.5.3** (build 25) — commit `e8fed52`, tag `v1.5.3`, pushed to main
- **CLAUDE.md test counts updated** — 2989 tests (2854 backend + 135 CLI), 93 test files

## In Progress
- **Evening Research workflow** — triggered on Mac Mini, R1 inference succeeded (93s), but the 4-hour delay node means the full run won't complete until ~4:30 AM UTC. Check `workflow_runs` table for `wf-3d895cc18f24` status.
- **Parallel session** building Notion-Level UI Redesign (Investigation Canvas, entity references, component library). Their uncommitted files are in `docs/` and `HestiaApp/WorkflowCanvas/`.

## Decisions Made
- **Principles stay Hestia-internal** — NOT sent to cloud providers. The pipeline is: Investigation Canvas → Principles → Knowledge Graph → local inference. Cloud is just the "smart engine" whose conversations feed memory.
- **Cloud persona YES, cloud Principles NO** — cloud Hestia gets personality for useful dev conversations, but behavioral rules stay local-only.
- **Timeout 600s for R1** — DeepSeek-R1:14b on M1 needs 90-120s for complex prompts with tool calls. 600s gives headroom for multi-turn tool chains.

## Test Status
- 2989 passing (2854 backend + 135 CLI), 0 failing, 0 skipped
- All tests green as of pre-push validation

## Uncommitted Changes
- `HestiaApp/WorkflowCanvas/src/research/PerformancePrototype.tsx` — parallel session's work
- `HestiaApp/macOS/Resources/WorkflowCanvas/index.html` — parallel session's work
- Multiple untracked `docs/` files — parallel session's discovery/plan documents
- `CLAUDE.md` — test count update (needs commit)

## Known Issues / Landmines
- **Mac Mini server was restarted 3x during debugging** — final PID is 11327 but CI/CD auto-deploy may have restarted it again after the push. Verify with `lsof -i :8443` on Mini.
- **Evening Research cron is `0 2 * * *` UTC** — that's 7 PM PT. The workflow will fire daily. If R1 is slow or Ollama is swapped to a different model, the 600s timeout should catch it.
- **Notify node uses `config.get("message")` fallback** — the workflow's notify config uses `"message"` key but the code expected `"body"`. Fixed with fallback, but new workflows should use `"body"` for consistency.
- **pytest conftest collision** — running `pytest` from root collects `hestia-cli/tests/` which conflicts with `tests/conftest.py`. Use `python -m pytest tests/` (not bare `pytest`).
- **Stale worktrees** — 9 agent worktrees in `.claude/worktrees/`. Not urgent but could be cleaned up.

## Process Learnings

### Config Gaps
- **Lazy import regressions are invisible to tests** — `nodes.py` imported `get_handler` (renamed months ago) but tests mock the handler layer. A lightweight integration test that resolves real imports would catch this.
  - **Proposal (SCRIPT)**: Add `test_import_smoke.py` that imports every lazy-imported function without mocking.
- **Layered timeouts need coordinated updates** — changing one timeout (executor) without the other (state machine) caused a second failure. Both referenced "Mixtral" in comments (stale).
  - **Proposal (CLAUDE.MD)**: Add "Timeout Coordination" note: grep all timeout layers when changing any inference timeout.

### First-Pass Success
- 4/5 tasks completed on first attempt (80%)
- **Rework cause**: Two independent timeout layers — first fix revealed the second
- **Top blocker**: Invisible layered timeouts with no single configuration point

### Agent Orchestration
- @hestia-explorer used effectively (2 deep traces: workflow architecture + cloud pipeline)
- @hestia-tester used after every code change (3 runs, all green)
- @hestia-deployer hung on pytest — worked around with direct rsync (known issue)

## Next Step
1. Verify Evening Research completed: `ssh andrewroman117@hestia-3.local "cd ~/hestia && sqlite3 data/workflows.db \"SELECT status, duration_ms, error_message FROM workflow_runs WHERE workflow_id='wf-3d895cc18f24' ORDER BY started_at DESC LIMIT 1;\""`
2. Open macOS app, set cloud to Full, send a message — verify Tia's personality and memory storage
3. Continue parallel session's UI Redesign work (Investigation Canvas, Phase 4a references)
