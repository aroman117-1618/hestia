---
name: preflight
description: Full environment validation with auto-remediation — kill stale processes, check connectivity, verify permissions, run tests
user_invocable: true
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# Environment Preflight Skill

Run a complete Hestia environment health check. Fix anything broken automatically, flag what needs manual intervention.

## Steps — execute all autonomously

1. **Stale Processes**: Run `lsof -i :8443 | grep LISTEN` — kill any zombie server processes with `kill -9`, then confirm they're gone

2. **Server Health**: Start the backend:
   ```
   cd /Users/andrewlonati/hestia && source .venv/bin/activate && nohup python -m hestia.api.server > /dev/null 2>&1 &
   ```
   Wait 5 seconds, then hit `curl -sk https://localhost:8443/v1/ping`. If non-200, read recent logs from `logs/` and diagnose.

3. **Auth Tokens**: Verify JWT auth by making an authenticated test request. If the server just restarted, tokens from previous sessions will be invalid — note this.

4. **Test Suite Baseline**: Run `python -m pytest --tb=line -q` and record the pass/fail count.

5. **Remote Infrastructure**: Check if Mac Mini is reachable: `ping -c 2 -W 3 hestia-3.local 2>/dev/null`. If unreachable, note it as a deployment blocker (not a dev blocker).

6. **TCC/Permissions**: Check that the server process can access calendar data by running the calendar CLI tool: `./hestia-cli-tools/.build/release/hestia-calendar list 2>&1 | head -3`. If permission denied, flag for manual intervention.

7. **Git Status**: Run `git status --short` and `git log --oneline -3`.

## Output

Present a status dashboard:

```
## Preflight Status

| Check | Status | Notes |
|-------|--------|-------|
| Stale processes | OK / Fixed | Killed N processes / None found |
| Server | Running | Healthy on :8443 |
| Auth | OK / Stale | Tokens valid / Need re-registration |
| Tests | X pass, Y fail | [list failures if any] |
| Mac Mini | Reachable / Unreachable | Via Tailscale |
| TCC Permissions | OK / Blocked | Calendar/Contacts access |
| Git | Clean / Dirty | [uncommitted files] |

[Any items needing manual intervention listed here]
```

Do NOT proceed with any development work. Just present the dashboard and wait for direction.
