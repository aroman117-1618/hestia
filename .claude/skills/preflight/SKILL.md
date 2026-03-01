---
name: preflight
description: Full environment validation with auto-remediation — kill stale processes, restart server, check connectivity, verify permissions, run tests
user_invocable: true
disable-model-invocation: true
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
---

# Environment Preflight Skill

Run a complete Hestia environment health check. This skill combines server restart (formerly `/restart`) with full environment validation. Fix anything broken automatically, flag what needs manual intervention.

## Phase 1: Kill Stale Processes

```bash
PIDS=$(lsof -ti :8443 2>/dev/null)
if [ -n "$PIDS" ]; then
    echo "$PIDS" | xargs kill -9 2>/dev/null
fi
```

Confirm they're gone: `lsof -i :8443 | grep LISTEN` should return nothing.

## Phase 2: Start Server

```bash
cd /Users/andrewlonati/hestia && source .venv/bin/activate && nohup python -m hestia.api.server > /dev/null 2>&1 &
```

Wait 5 seconds for startup, then verify:
```bash
curl -sk https://localhost:8443/v1/ping
```

If non-200, read recent logs from `logs/` and diagnose. Do NOT proceed with tests if the server isn't healthy.

## Phase 3: Run Full Test Suite

```bash
cd /Users/andrewlonati/hestia && source .venv/bin/activate && python -m pytest --timeout=30 -q
```

Record the pass/fail/skip count. If tests fail, note which ones and the failure reason.

## Phase 4: Git Context

```bash
git status --short | head -15
git log --oneline -3
```

Note uncommitted changes and recent commits.

## Phase 5: Deep Checks (optional — run if time permits)

These are secondary checks. If Phase 1-4 all pass, these provide additional confidence:

1. **Mac Mini reachability**: `ping -c 2 -W 3 hestia-3.local 2>/dev/null` — if unreachable, note as deployment blocker (not dev blocker)

2. **TCC/Permissions**: `./hestia-cli-tools/.build/release/hestia-calendar list 2>&1 | head -3` — if permission denied, flag for manual intervention

3. **Auth tokens**: Verify JWT auth by making an authenticated test request. Note if tokens are stale after restart.

## Output

Present a status dashboard:

```
## Preflight Status

| Check | Status | Notes |
|-------|--------|-------|
| Stale processes | OK / Fixed | Killed N processes / None found |
| Server | Running / Failed | Healthy on :8443 / [error] |
| Tests | X pass, Y fail, Z skip | [list failures if any] |
| Git | Clean / Dirty | [uncommitted files count] |
| Mac Mini | Reachable / Unreachable | Via Tailscale (optional) |
| TCC Permissions | OK / Blocked | Calendar access (optional) |

[Any items needing manual intervention listed here]
```

Do NOT proceed with any development work. Just present the dashboard and wait for direction.
