---
name: _archive_restart
description: "[ARCHIVED] Kill stale Hestia server processes, restart the backend, verify health, and run tests. Superseded by /preflight."
user_invocable: false
allowed_tools:
  - Bash
  - Read
---

# ARCHIVED — Server Restart Skill

> **This skill has been archived.** All functionality has been merged into `/preflight`.
> Use `/preflight` instead.

Original functionality (preserved for reference):

1. Find all processes listening on port 8443: `lsof -i :8443 | grep LISTEN`
2. Kill any found processes with `kill -9 <pid>` for each PID
3. Activate the venv and start the server in the background:
   ```
   cd /Users/andrewlonati/hestia && source .venv/bin/activate && nohup python -m hestia.api.server > /dev/null 2>&1 &
   ```
4. Wait 5 seconds for startup, then verify with `curl -sk https://localhost:8443/v1/ping`
5. Run the test suite: `cd /Users/andrewlonati/hestia && python -m pytest --tb=short -q`
6. Report results: how many processes killed, whether health check passed, test pass/fail count
