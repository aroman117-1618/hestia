---
name: handoff
description: Session wrap-up — document work, spot-check docs, clean workspace, prepare for the next session to pick up seamlessly
user_invocable: true
allowed_tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - TaskCreate
  - TaskUpdate
  - TaskList
---

# Session Handoff Skill

Wrap up the current session and prepare a complete handoff so the next session (or a fresh Claude instance) can pick up immediately without searching transcripts or guessing context.

Think of this as briefing the night shift: be precise, be complete, leave nothing ambiguous.

## Phase 1: Gather State

Run these in parallel:

1. `git log --oneline -10` — recent commits
2. `git status --short` — uncommitted changes
3. `git diff --stat` — what's modified
4. `source .venv/bin/activate && python -m pytest --tb=line -q 2>&1 | tail -15` — test status
5. `lsof -i :8443 | grep LISTEN || echo 'No server running'` — server state

Also review:
- Conversation history for work done, decisions made, blockers hit
- Current `SPRINT.md` for phase updates needed
- Current `CLAUDE.md` for any status changes

## Phase 2: Documentation Spot-Check

Quickly verify these files still reflect reality:

| File | Check |
|------|-------|
| `CLAUDE.md` | Test counts, endpoint counts, project status, workstream status |
| `docs/api-contract.md` | Any new/changed endpoints documented? |
| `docs/hestia-decision-log.md` | Any decisions from this session that need recording? |
| `SPRINT.md` | Phase markers updated for topics worked on? |

If anything is stale, fix it now (use Edit tool). Don't leave documentation drift for the next session.

## Phase 3: Workspace Cleanup

1. **Stale files** — any temporary files, scratch files, or debug artifacts to clean up?
2. **Uncommitted changes** — should they be committed, stashed, or discarded? (Ask Andrew if unclear)
3. **Orphaned branches** — any local branches that are no longer needed?
4. **Server state** — is the server in a good state, or should it be restarted before handoff?

## Phase 4: Write Handoff

Write `SESSION_HANDOFF.md` in the project root with this exact structure:

```markdown
# Session Handoff — [today's date]

## Mission
[What was the goal of this session? 1-2 sentences]

## Completed
- [Bullet list of what was accomplished, with specific file paths]
- [Include commit hashes where relevant]

## In Progress
- [Anything started but not finished]
- [Include: specific file, current state, what's left to do]

## Decisions Made
- [Decision]: [reasoning] — [ADR number if logged]

## Test Status
- X passing, Y failing, Z skipped
- Failures: [list specific test names and brief cause]

## Uncommitted Changes
- [List files with brief description of changes, or "None — all committed"]

## Known Issues / Landmines
- [Things that LOOK fine but AREN'T — this is the most important section]
- [Things the next session might trip over]
- [Environment state that's non-obvious]

## Next Step
[The EXACT next action. Not "continue working on X" — specific like:]
[- "Run `python -m pytest tests/test_health.py -v` to reproduce the 3 failing tests"]
[- "Open `hestia/health/manager.py:142` and fix the date range query"]
[- "Then run full suite to verify no regressions"]
```

## Phase 5: Update SPRINT.md

If `SPRINT.md` exists, update phase markers for any topics worked on this session:
- Move topics to their current phase (Research → Plan → Execute → Review → Done)
- Add any new topics discovered during the session
- Note any blockers

## Phase 6: Update CLAUDE.md (if needed)

Only update `CLAUDE.md` if:
- Workstream status changed (e.g., "IN PROGRESS" → "COMPLETE")
- Test counts changed significantly
- New modules or endpoints were added
- Project structure changed

Update the "Context Continuity" section with a one-line note about this session.

## Verification

Before finishing, confirm:
- [ ] SESSION_HANDOFF.md is written and specific
- [ ] No documentation drift left behind
- [ ] Workspace is clean (no stale files, no ambiguous uncommitted changes)
- [ ] SPRINT.md phases are current
- [ ] CLAUDE.md status is accurate
- [ ] The "Next Step" in handoff is specific enough that a fresh session could start immediately
