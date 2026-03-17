# Session Handoff — 2026-03-17 (Session 7)

## Mission
Complete Sprint 17 deployment: commit the parallel session's Memory Browser + Learning Metrics work, install all three new Ollama models on the Mac Mini (updated Ollama 0.11→0.18 in the process), and verify the Mac Mini is fully operational.

## Completed

### Parallel Session Work — Committed + Pushed
- `1c78ee0` — macOS Memory Browser (MemoryBrowserView, MemoryChunkRow, MacMemoryBrowserViewModel), Learning Metrics Panel, Research graph improvements (bi-temporal filtering, center entity resolution), backend `/v1/memory/chunks` endpoint, 12 new tests
- All 24 modified/untracked files from the parallel worktree session reviewed, tested, and merged to main

### Mac Mini Model Installation
- SSH'd into `andrewroman117@hestia-3.local` via Tailscale
- Discovered Ollama was on **v0.11.11** — too old to resolve `qwen3.5:9b` (released after 0.11)
- Upgraded Ollama to **v0.18.0** via `brew upgrade ollama && brew services restart ollama`
- Pulled all three Sprint 17 models:
  - `qwen3.5:9b` (6.6 GB) — Hestia primary ✅
  - `deepseek-r1:14b` (9.0 GB) — Artemis reasoning specialist ✅
  - `qwen3:8b` (5.2 GB) — Apollo tool calling ✅

### Infrastructure
- Stale worktree (`awesome-nash`) cleaned up
- SPRINT.md + CLAUDE.md updated with accurate counts

## In Progress
- Nothing. All code committed, all models installed, CI is green.

## Decisions Made
- **Ollama must be updated alongside model changes**: v0.11 didn't know about models released after it. Add "check Ollama version on Mac Mini" to the deployment checklist for new model pulls.
- **Parallel Ollama restart kills in-progress pulls**: When restarting the service mid-download, blobs are discarded and must re-pull from scratch. Lesson: update Ollama BEFORE starting pulls, not after.

## Test Status
- **2132 backend passing, 0 failing** (all dots, no F/E markers)
- **135 CLI passing** (no changes, verified in previous session)
- **Pre-push gate**: clean on last push (`1c78ee0`)
- Mac Mini: `qwen2.5:0.5b` (SLM) was already present — unchanged

## Uncommitted Changes
None. Working tree is clean.

## Known Issues / Landmines
- **Tailscale OAuth not set up**: `deploy.yml` has a commented-out Tailscale step. Deploys work via direct SSH on the same Tailscale network. Weekend 2026-03-22 task: create OAuth client, add GitHub secrets, uncomment the block.
- **Mac Mini disk pressure**: Now has `mixtral:8x22b` (79GB), `mixtral:8x7b` (28GB), plus the 3 new models (~21GB). That's ~130GB in models alone. Worth pruning `olmo2:7b`, `mistral:instruct`, and possibly `mixtral:8x22b` if disk gets tight.
- **api-contract.md is ~55 endpoints stale**: Claims 132 across 22 modules, actual is 186 across 27. Swagger at `/docs` is always current; markdown has drifted since Sprint 9.
- **count-check.sh false alarm**: Script compares CLAUDE.md total (2267 = backend + CLI) against pytest backend-only (2132). The counts are actually correct — the script needs to be fixed to compare the right values.
- **handler.py at 2492 lines**: Known structural debt. No sprint scope yet.
- **Reasoning events not in non-streaming path**: `handle()` (REST) doesn't emit reasoning events — only `handle_streaming()` does. Low priority since streaming is the default.

## Process Learnings

### Config Gaps
- **Ollama version not in deployment checklist**: When a new model requires a newer Ollama version, there's no guard. Add `ollama --version` check to `scripts/deploy-to-mini.sh` or document minimum Ollama version in CLAUDE.md.
- **count-check.sh compares wrong denominators**: Script compares total test count from CLAUDE.md against backend-only pytest collection. Either fix the script to strip the "backend + CLI" parenthetical, or document that count-check false positives are expected when CLI tests are counted separately.

### First-Pass Success: ~90%
- Parallel session work was clean and merged without issues — all 12 tests passed first try
- One rework: Ollama pull failed on `qwen3.5:9b` due to version incompatibility → discovered version issue → upgraded → re-pulled all three (restart wiped in-progress downloads)
- No code changes this session — pure ops/deployment work

### Agent Orchestration
- @hestia-explorer used well for parallel session code review (one agent, focused prompt, fast)
- No tester/reviewer/builder agents needed — no code was written
- Parallelism used correctly: model pulls kicked off in parallel (3 simultaneous SSH commands)

## Next Step

**The Mac Mini is ready. Test the full stack:**

1. Start the server if it's not running (CI/CD should have deployed already):
   ```bash
   ssh andrewroman117@hestia-3.local "curl -sk https://localhost:8443/v1/ping"
   ```

2. Test agent specialization — send a research query and verify Artemis routes to deepseek-r1:14b:
   ```
   hestia "analyze the trade-offs between ChromaDB and Qdrant for long-term memory storage"
   ```
   Expected: reasoning stream shows "Agent: Artemis → deepseek-r1:14b", thinking lines from `<think>` blocks

3. Test Apollo tool calling with the new model:
   ```
   hestia "what's on my calendar tomorrow"
   ```
   Expected: Apollo routes to qwen3:8b, tool call to `list_calendar_events`

4. Check Memory Browser in macOS app — should show paginated chunk list with sort/filter controls

5. If any issues: `ssh andrewroman117@hestia-3.local "journalctl -u hestia -n 50"` for server logs
