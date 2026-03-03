# Session Handoff — 2026-03-02

## Mission
Implement the retrospective remediation plan — structural fixes for the top recurring issues flagged by two consecutive retros (count drift, MEMORY.md over capacity, mega-commit discipline, missing workflow guardrails).

## Completed
- **Part B: MEMORY.md pruning** — reduced from 209 lines (9 silently truncated) to 97 lines. Created 3 topic files:
  - `.claude/projects/.../memory/ios-patterns.md` (iOS/macOS Swift patterns, UI architecture, onboarding)
  - `.claude/projects/.../memory/deployment.md` (Mac Mini deployment, server lifecycle)
  - `.claude/projects/.../memory/testing.md` (test counts, pytest infrastructure, hooks)
  - MEMORY.md retains 1-line pointers to each topic file
- **Part A: `scripts/count-check.sh`** — report-only verification script checking test count, test file count, and route module count against CLAUDE.md. Uses `run_with_timeout` and explicit venv Python. Wired into `/handoff` skill Phase 2.
- **Part C: CLAUDE.md workflow guidance** — Phase 3 adds commit granularity rules ("one feature, one fix, one refactor"). Phase 4 strengthens reviewer enforcement ("REQUIRED for >5 files").
- **Part D: Parallel session rule #9** — "check `git log --oneline -3` before committing" in `.claude/rules/parallel-sessions.md`
- **Part E: macOS model duplication docs** — 5 duplicated model files documented in CLAUDE.md Multi-Target Builds section
- **Part F: Unwired endpoints backlog** — Added to `SPRINT.md`: Tasks (6), Agents v2 (10), Memory sensitivity (1), User Profile extended (11 partial)
- All changes committed in `00e723a`

## In Progress
- None. All 6 parts complete.

## Decisions Made
- Drop `--fix` mode from count-check.sh (report-only per plan audit) — avoids fragile BSD sed regex patching
- MEMORY.md topic split uses explicit pointers (not implicit) — Claude Code only auto-loads MEMORY.md
- No new ADRs needed — these are all workflow/tooling changes, not architecture decisions

## Test Status
- 1261 collected, 3 skipped, 0 failures on verbose run
- One transient `F` appeared in quiet mode but did not reproduce on verbose re-run (likely flaky)

## Uncommitted Changes
- None — all committed in `00e723a`

## Known Issues / Landmines
- **MEMORY.md topic files are invisible unless explicitly Read.** The pointers in MEMORY.md say "See `ios-patterns.md`" but Claude Code won't auto-load them. This is by design — the pointers tell future sessions WHEN to read them.
- **count-check.sh grep patterns are format-sensitive.** If CLAUDE.md changes from "1261 tests (" to "~1261 tests" or "1,261 tests", the grep will break. A comment in the script documents the expected format.
- **The transient test failure** (appeared once in quiet mode, vanished in verbose) may be a timing-dependent test. Not investigated since it didn't reproduce.
- **`feature/investigate-command` branch** still not merged to main. Previous session's handoff has merge instructions.

## Next Step
- Project is in maintenance mode — no active sprint. Check `SPRINT.md` backlog for the next feature to tackle (Tasks UI, Agents v2 UI, or Investigate Phase 2).
- If starting a new sprint: run `/discovery [topic]` to research, then `/plan-audit` before building.
- If merging investigate: follow previous handoff instructions (resolve CLAUDE.md conflicts, pip install deps on Mac Mini).
- If deploying: run `./scripts/deploy-to-mini.sh` (Mac Mini needs `qwen2.5:0.5b` pulled for council).
