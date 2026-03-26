---
name: pickup
description: Read session handoff, check environment health, and resume where the last session left off
user_invocable: true
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# Session Pickup Skill

Start a new session by loading context from the last session and validating the environment.

## Steps

1. Read `SESSION_HANDOFF.md` — this has what was done last, what's in progress, and the exact next step
2. Read `CLAUDE.md` — check the Session Continuity and Current Status sections
3. **Read Notion whiteboard** — run `source .venv/bin/activate && python scripts/sync-notion.py read-whiteboard 2>&1` to check for notes Andrew left between sessions. Summarize any new content in the pickup summary.
4. Run `git log --oneline -5` to see what's been committed since the handoff
5. Run `git status --short` to check for uncommitted work
6. Run `lsof -i :8443 | grep LISTEN || echo 'No server running'` to check server state
7. Run `source .venv/bin/activate && python -m pytest --tb=short -q --timeout=30 2>&1 | tail -10` to verify test baseline
8. **Sync Notion** — run `source .venv/bin/activate && python scripts/sync-notion.py sync-all --incremental 2>&1` to push any docs changed between sessions. If it fails, note in pickup summary but don't block.
9. **Conditional Xcode check** — only if Swift files changed since last session:
   ```bash
   if git diff --name-only HEAD~5 2>/dev/null | grep -q '\.swift$'; then
     xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5
   else
     echo "No Swift changes — skipping Xcode build"
   fi
   ```

Present a summary in this format:

```
## Session Pickup Summary

**Last session** ([date]): [1-line summary of what was done]
**In progress**: [anything unfinished]
**Whiteboard notes**: [summary of new Notion whiteboard content, or "No new notes"]
**Server**: Running / Not running
**Tests**: X passing, Y failing
**macOS build**: Clean / Skipped (no Swift changes) / Failing ([error])
**Uncommitted changes**: Yes (list) / None
**Next step**: [from SESSION_HANDOFF.md]

Ready to continue — should I pick up with [next step]?
```

Do NOT start any implementation work. Just present the summary and wait for direction.
