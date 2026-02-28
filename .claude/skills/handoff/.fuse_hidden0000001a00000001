---
name: handoff
description: Write a structured session handoff file so the next session starts with full context
user_invocable: true
allowed_tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
---

# Session Handoff Skill

Write a structured handoff file at `SESSION_HANDOFF.md` in the project root. This preserves context across sessions so the next Claude Code session doesn't waste time searching transcripts.

## Steps

1. Read `CLAUDE.md` for current project status
2. Run `git log --oneline -5` to see recent commits
3. Run `git status --short` to check uncommitted changes
4. Run `source .venv/bin/activate && python -m pytest --tb=line -q 2>&1 | tail -10` to get current test status
5. Review your conversation history for what was worked on, decisions made, and any blockers

Write `SESSION_HANDOFF.md` with this exact structure:

```markdown
# Session Handoff — [today's date]

## Completed This Session
- [Bullet list of what was accomplished, with specific file paths]

## In Progress
- [Anything started but not finished, with specific file paths and current state]

## Decisions Made
- [Any architectural or design decisions, with reasoning]

## Test Status
- [X passing, Y failing — list any failures with file:test_name]

## Uncommitted Changes
- [List files or "None — all committed"]

## Known Issues / Blockers
- [Anything that needs attention next session]

## Next Step
- [The exact next thing to pick up — be specific enough that a fresh Claude session can start immediately]
```

Also update the "Context Continuity" section of CLAUDE.md if the current workstream status has changed.
