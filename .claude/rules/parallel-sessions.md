---
paths:
  - "**/*"
---

# Parallel Session Safety Rules

When multiple Claude Code sessions may be running simultaneously on the same repo:

1. **Before editing any file, read it first** to check for concurrent modifications. The file may have changed since you last read it.

2. **Prefer narrow, targeted edits over full file rewrites.** Small Edit operations reduce merge conflicts. Only use Write for new files.

3. **Never assume you're the only session running.** Another Claude session may be editing other files in this repo right now.

4. **Use `git status` before committing** to verify you're only staging your own changes. Don't accidentally commit another session's work.

5. **If editing shared config files** (CLAUDE.md, settings.json, server.py), confirm with Andrew first. These files are high-conflict zones.

6. **Prefer creating new files over modifying shared files** when possible. This enables parallel work on independent slices without conflicts.

7. **When running tests, check for port conflicts.** Another session may have a server running on port 8443. Use `lsof -i :8443` before starting a server.

8. **Use `isolation: worktree`** for any sub-agent that writes code (scaffold sub-agents, bugfix agents). This gives each agent an isolated copy of the repo.
