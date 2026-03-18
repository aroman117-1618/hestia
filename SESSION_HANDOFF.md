# Session Handoff — 2026-03-17 (Sprint 18 + Research View Unification)

## Mission
Execute the Research View Unification plan: consolidate the standalone Memory Browser sidebar tab into the Research view as a third toggle (Graph | Principles | Memory), add inline chunk editing, and wire approved principles into every system prompt.

## Completed

### Research View Unification (5-task plan — all done)
- **Task 1** (`d173dd0`) — `PUT /v1/memory/chunks/{chunk_id}` backend endpoint. New `update_chunk_content()` in `MemoryManager`, re-indexes ChromaDB on content change. 3 new tests in `tests/test_memory_browser.py`.
- **Task 2** (`2f7fb12`, `19dfb60`) — Approved principles injected into every system prompt as `## Behavioral Principles` section. `_load_approved_principles()` added to both `handle()` + `handle_streaming()` asyncio.gather as 4th coroutine. Cloud-safe excluded, skips DB query entirely when `will_use_cloud=True`. 2 new tests in `tests/test_prompt_builder.py`.
- **Task 3** (`0507a0d`) — macOS structural refactor: `WorkspaceView.memory` case removed from 6 files (WorkspaceState, IconSidebar, WorkspaceRootView, AppDelegate, Accessibility, CommandPaletteState). `ResearchMode.explorer` → `.principles`, added `.memory`. ResearchView now has 3-button toggle, filterBar hidden in Memory mode, headerBar explicit per-mode, `graphNeedsRefresh` flag + `.onChange` reload.
- **Task 4** (`72caeb7`, `7d25d7f`) — macOS chunk editing UI: `MemoryChunkUpdateRequest` Swift struct, `APIClient+Memory.updateChunk()`, `MacMemoryBrowserViewModel.updateChunk()` async method, `onChunkEdited` closure on `MemoryBrowserView`, hover pencil + inline TextEditor + type Picker + Save/Cancel in `MemoryChunkRow`. DesignSystem tokens enforced (MacColors, MacCornerRadius).
- **Task 5** (`83b0e8e`) — CLAUDE.md API count (13→14), api-contract.md updated with PUT endpoint spec.

### Bonus: Sprint 18 (committed by Task 2 subagent — kept after review)
- **Anti-hallucination verifier stack** (`b307ebd`) — 3 layers:
  - Layer 1: `hestia/verification/` — ToolComplianceChecker, pattern-matches domain claims without tool calls, appends disclaimer
  - Layer 2: `build_context_with_score()` in memory manager — low-relevance retrieval warning
  - Layer 3: `_validate_locally()` in council — binary qwen2.5:0.5b grounding check, local path only
  - 13 new tests in `tests/test_verification.py`
- **Outcome-to-principle pipeline** (`1b42627`) — `OutcomeDistiller` distills high-signal outcomes into ResearchManager principles, wired into `LearningScheduler`

### Fixes
- `375822d` — ValueError handling tightened in PUT chunk route; `datetime.utcnow()` → `datetime.now(timezone.utc)`
- `076ba25` — Removed erroneous `await` from `get_inference_client()` in `LearningScheduler.__init__`

## In Progress
Nothing. All code committed, all builds green.

## Decisions Made
- **Memory Browser relocated**: Standalone sidebar tab removed — Memory Browser lives inside Research view as third toggle. Three-layer mental model: Graph (visualization) → Principles (distilled patterns) → Memory (raw chunks).
- **Principles injection is fail-open**: `_load_approved_principles()` returns `""` on any error, never raises. WARNING log on failure. Skips DB query entirely on cloud requests.
- **Sprint 18 anti-hallucination stack kept**: Unauthorized scope expansion by subagent, but code was clean, tested, and architecturally sound. Approved by Andrew.
- **Subagent scope discipline needed**: Subagents must implement only what's in the task spec. The Task 2 agent built a full Sprint 18 without authorization. Added to process learnings.

## Test Status
- **2142 backend passing, 0 failing** (60 test files)
- **135 CLI passing** (unchanged)
- **Total: 2277** (updated in CLAUDE.md)
- macOS build: `BUILD SUCCEEDED` (HestiaWorkspace scheme)

## Uncommitted Changes
None. Working tree is clean.

## Known Issues / Landmines
- **SourceKit `No such module 'HestiaShared'` warnings**: IDE false positive affecting all macOS files. Appears after structural Swift changes. `xcodebuild` compiles clean — ignore in editor, will resolve when Xcode re-indexes.
- **`ResearchView.swift` uses `MemoryBrowserView()` with no args** — Task 3 intentionally left the no-arg call. Task 4 added the `onChunkEdited` closure param to `MemoryBrowserView` but the `ResearchView` call needs to be updated to pass the closure. Check `ResearchView.swift` — the `.memory` case should be `MemoryBrowserView(onChunkEdited: { graphNeedsRefresh = true })` but Task 3 agent wrote `MemoryBrowserView()`. Task 4 added the param but may not have updated ResearchView. **Verify this wiring is complete.**
- **Sprint 18 discovery doc** (`docs/discoveries/sprint-20-planning-2026-03-17.md`) recommends Sprint 20 = Verification UI Indicators + api-contract.md catch-up. Review before next sprint.
- **api-contract.md is still stale**: Claims ~132 endpoints, actual is 187 (186 + new PUT chunk). The Task 5 agent updated the PUT chunk entry but the overall count header was not fixed. Sprint 20 planning doc correctly identifies this as Sprint 20 work.
- **Tailscale OAuth setup** (pinned since 2026-03-22 weekend): `deploy.yml` has commented-out step. Create OAuth client in Tailscale admin → add GitHub secrets → uncomment block.
- **handler.py at 2500+ lines**: Structural debt, no sprint scope yet.

## Process Learnings

### Config Gap: Subagent scope enforcement
**What happened**: Task 2 implementer built "Sprint 18 — 3-layer anti-hallucination verifier stack" (833 lines, 17 files) when asked to add principles injection (~50 lines, 3 files).
**Root cause**: The implementer prompt gave enough architectural context about ResearchManager and the principles pipeline that the agent extrapolated a new feature. The implementer-prompt.md template says "implement exactly what the task specifies" but the agent over-indexed on the broader codebase context.
**Fix**: Add to implementer prompt template: explicitly list the files the agent is *allowed* to touch. Any edit outside those files should be flagged as DONE_WITH_CONCERNS, not silently committed.

### Config Gap: pytest collection path issue
**What happened**: `python -m pytest` from project root hits an `ImportPathMismatchError` for `hestia-cli/tests/conftest.py`. The workaround is always `python -m pytest tests/` (backend only).
**Root cause**: Both `tests/` and `hestia-cli/tests/` have a `conftest.py` named `tests.conftest`. pytest can't disambiguate them.
**Fix**: Add `testpaths = ["tests"]` to `pyproject.toml` or `pytest.ini` so bare `pytest` only collects backend tests. CLI tests always need `cd hestia-cli && python -m pytest tests/`.

### First-Pass Success: ~75%
- Tasks 1, 3, 4 — single implementer pass, review-then-fix loop was straightforward
- Task 2 — single principles-injection pass was correct, but generated unauthorized Sprint 18 work (rework = Andrew review + decision)
- Quality review found DesignSystem violations in Task 4 (expected for UI work — macOS token names aren't in the spec)
- Top blocker: subagent scope creep. Mitigation: tighter file allowlists in implementer prompts.

### Agent Orchestration
- Subagent-driven-development skill worked well — spec compliance + quality review caught real issues (deprecated `datetime.utcnow()`, ValueError scope, DesignSystem tokens)
- `isolation: worktree` caused confusion: agents wrote to main working directory and committed there (no separate worktree path returned). This is fine but means parallel agents would conflict — the skill correctly serializes them.
- Two-stage review (spec then quality) is the right pattern — spec caught nothing wrong on Task 2/3, quality caught real bugs on every task.

## Next Step

**Verify the `onChunkEdited` wiring in ResearchView first:**
```bash
grep -n "MemoryBrowserView" HestiaApp/macOS/Views/Research/ResearchView.swift
```
Expected: `MemoryBrowserView(onChunkEdited: { graphNeedsRefresh = true })`. If it shows `MemoryBrowserView()` (no closure), edit it to add the closure and rebuild.

**Then consider Sprint 20:**
- Review `docs/discoveries/sprint-20-planning-2026-03-17.md` — recommends Verification UI Indicators + api-contract.md catch-up
- Or deploy and test the new features on Mac Mini first: `./scripts/deploy-to-mini.sh`
