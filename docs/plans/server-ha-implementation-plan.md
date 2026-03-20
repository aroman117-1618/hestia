# Server High Availability — Implementation Plan

**Created:** 2026-03-20
**Discovery basis:** `docs/discoveries/server-high-availability-2026-03-20.md`
**Investigation:** Direct SSH to Mac Mini (hestia-3.local) — all findings validated
**Target:** Enterprise-grade reliability — zero tolerance for downtime
**Estimated effort:** 3-4 hours

## Problem Statement

The Hestia server on Mac Mini M1 runs as a single Uvicorn process managed by launchd. Any crash, deploy restart, or resource exhaustion causes total downtime. The watchdog checks every 5 minutes with a 3-strike policy, meaning up to **15 minutes of silent downtime** before recovery. Trading bots run 24/7 during live trading — downtime means missed signals and potential financial impact.

**Goal:** Sub-60-second recovery from any server failure. Zero downtime during deploys. Phone notification within 60s of any outage.

---

## Current State (Validated via SSH)

| Component | Status | Finding |
|-----------|--------|---------|
| **pmset** | Mostly good | `sleep 0`, `autorestart 1`, `standby 0`. **Gap:** `disksleep 10` should be `0` |
| **FileVault** | OFF | Good — headless boot works after power loss |
| **Tailscale** | Homebrew daemon | `homebrew.mxcl.tailscale` in launchctl. Survives reboots, no GUI login needed |
| **Server process** | Single Uvicorn (PID 1349) | `python -m hestia.api.server` via launchd. No process manager. |
| **Gunicorn** | Not installed | The #1 gap |
| **Watchdog** | 5-min interval, 3-strike | Max 15 min silent downtime. `/v1/ready` health check is good. |
| **launchd plist** | Functional | `KeepAlive` on non-zero exit, 10s throttle, `RunAtLoad`. At `~/Library/LaunchAgents/com.hestia.server.plist` |
| **Ollama** | Separate keepalive service | `com.hestia.ollama-keepalive` running |

---

## Phase 1: Gunicorn Process Manager (2h)

### WS1.1: Install Gunicorn on Mac Mini (15 min)

```bash
ssh andrewroman117@hestia-3.local
cd /Users/andrewroman117/hestia
source .venv/bin/activate
pip install gunicorn uvicorn[standard]
pip freeze > requirements.txt  # or pip-compile
```

Verify: `gunicorn --version`

### WS1.2: Create gunicorn.conf.py (30 min)

New file: `gunicorn.conf.py` at project root.

```python
"""Gunicorn configuration for Hestia API server.

Runs 2 Uvicorn workers behind Gunicorn process manager.
Key benefits:
- Zero-downtime deploys via `kill -HUP` (graceful worker rotation)
- Automatic worker crash recovery
- Process isolation (one worker crash doesn't take down the server)
"""
import multiprocessing

# Worker configuration
workers = 2  # 2 workers on M1 16GB (leaves headroom for Ollama ~11GB)
worker_class = "uvicorn.workers.UvicornWorker"
preload_app = True  # Share app memory across workers via fork, reduces RAM ~40%

# Binding — match existing port
bind = "0.0.0.0:8443"

# SSL — match existing self-signed cert setup
keyfile = "certs/server.key"  # Adjust path to actual cert location
certfile = "certs/server.crt"

# Timeouts
timeout = 120  # Worker timeout (seconds) — allows long inference calls
graceful_timeout = 30  # Time for worker to finish requests during restart
keep_alive = 5

# Restart safety
max_requests = 1000  # Recycle workers after 1000 requests (prevents memory leaks)
max_requests_jitter = 100  # Random jitter to prevent all workers restarting at once

# Logging
accesslog = "/Users/andrewroman117/hestia/logs/gunicorn-access.log"
errorlog = "/Users/andrewroman117/hestia/logs/gunicorn-error.log"
loglevel = "info"

# Process naming
proc_name = "hestia-api"
```

**Critical considerations:**
- `preload_app = True` means the FastAPI app loads once and is forked. All singleton managers (MemoryManager, TradingManager, etc.) must handle fork correctly. Since they use `async` init via `get_X_manager()`, they'll be re-initialized per-worker after fork. Need to verify.
- SSL cert paths must match the Mac Mini's actual cert location.
- `timeout = 120` is generous to handle long Ollama inference calls (some can take 30-60s).

### WS1.3: Create ASGI Entry Point (15 min)

Gunicorn needs an importable ASGI app object. Check if `hestia.api.server` already exposes one.

The current server likely does `uvicorn.run(app, ...)` in `__main__`. Gunicorn needs: `from hestia.api.server import app` (the FastAPI instance).

If the app is created inside a function or `if __name__ == "__main__"` block, extract it to module level:

```python
# hestia/api/server.py
app = create_app()  # Must be importable at module level

if __name__ == "__main__":
    uvicorn.run(app, ...)
```

### WS1.4: Update launchd Plist (15 min)

Update `~/Library/LaunchAgents/com.hestia.server.plist`:

```xml
<key>ProgramArguments</key>
<array>
    <string>/Users/andrewroman117/hestia/.venv/bin/gunicorn</string>
    <string>hestia.api.server:app</string>
    <string>--config</string>
    <string>/Users/andrewroman117/hestia/gunicorn.conf.py</string>
</array>
```

Remove any Uvicorn-specific args. Gunicorn config file handles everything.

### WS1.5: Deploy Script Update (15 min)

Update `scripts/deploy-to-mini.sh` to use graceful restart:

```bash
# Instead of: launchctl kickstart -k ...
# Use: kill -HUP $(cat /var/run/hestia-api.pid)
# Gunicorn master receives HUP → spawns new workers → gracefully shuts old ones
ssh andrewroman117@hestia-3.local "kill -HUP \$(pgrep -f 'gunicorn.*hestia')"
```

This achieves **zero-downtime deploys** — new workers start serving before old ones stop.

### WS1.6: Verify Trading Bot Safety (30 min)

The trading BotOrchestrator runs async bot loops inside the server process. With Gunicorn + preload:
- The orchestrator starts on the first worker that handles a `/v1/trading/bots/{id}/start` request
- SIGTERM during worker rotation must not corrupt trading state

**Test plan:**
1. Start a paper trading bot
2. Send `kill -HUP` to Gunicorn master
3. Verify: bot continues running on surviving worker? Or does it restart cleanly?
4. Check: no duplicate trades, no orphaned orders, kill switch not triggered

**If bots can't survive worker rotation:** Pin bot execution to a separate process (background task runner) outside of Gunicorn workers. This is the safer architecture anyway — web request handlers shouldn't host long-running bot loops.

---

## Phase 2: Watchdog Tightening (15 min)

### WS2.1: Reduce Interval to 60 Seconds

Create/update `~/Library/LaunchAgents/com.hestia.watchdog.plist`:

```xml
<key>StartInterval</key>
<integer>60</integer>
```

### WS2.2: Reduce Strike Count to 2

In `scripts/hestia-watchdog.sh`:
```bash
MAX_FAILURES=2  # Was 3 — faster recovery
```

**Result:** Max silent downtime drops from **15 min → 2 min**.

### WS2.3: Add Watchdog Alerting

After a restart action, the watchdog should notify:

```bash
# After successful restart:
osascript -e 'display notification "Server restarted after health check failure" with title "Hestia Watchdog"'
# OR push via ntfy.sh / Pushover for remote notification
```

---

## Phase 3: macOS Hardening (5 min)

```bash
ssh andrewroman117@hestia-3.local "sudo pmset -a disksleep 0"
```

Current `disksleep 10` means the disk can sleep after 10 minutes of inactivity. SQLite + ChromaDB on a sleeping disk = I/O errors. Set to 0.

Also verify automatic macOS updates are disabled:
```bash
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticDownload -bool false
sudo defaults write /Library/Preferences/com.apple.SoftwareUpdate AutomaticallyInstallMacOSUpdates -bool false
```

---

## Phase 4: External Monitoring (10 min)

### Option A: UptimeRobot (Free Tier)
- Monitor `https://hestia-3.local:8443/v1/ready` every 60s
- **Problem:** UptimeRobot can't reach Tailscale IPs (private network)
- **Solution:** Use Healthchecks.io ping model instead — watchdog pings OUT, not monitored from outside

### Option B: Healthchecks.io (Recommended)
- Free tier: unlimited checks, 20 team members
- Watchdog appends a curl to each successful health check:
  ```bash
  # In hestia-watchdog.sh, after successful ready check:
  curl -fsS --retry 3 https://hc-ping.com/<CHECK_UUID> > /dev/null 2>&1
  ```
- If the ping stops arriving (server down + watchdog down), Healthchecks.io sends email/push
- **This monitors the watchdog itself** — defense in depth

### Option C: ntfy.sh (Self-Hostable)
- Simple HTTP push notifications
- Watchdog sends alerts on restart events
- Free, no account needed, works from Tailscale network

**Recommendation:** Healthchecks.io (Option B) + ntfy.sh (Option C) together. Healthchecks.io catches "everything is down" scenarios. ntfy.sh gives real-time restart notifications.

---

## Phase 5: Graceful Shutdown Verification (30 min)

### Trading Bot Lifecycle

Current bot lifecycle:
1. `POST /v1/trading/bots/{id}/start` → `BotOrchestrator.start_bot()` → `BotRunner` async loop
2. Bot runs inside the same process as the web server
3. Graceful shutdown: `BotOrchestrator.shutdown()` cancels all tasks

**Risk with Gunicorn:** Worker rotation (HUP) sends SIGTERM to old worker. If bot is mid-trade:
- `BotRunner._tick()` could be interrupted during exchange API call
- Atomic trade recording (isolation_level fix from Sprint 27) protects DB consistency
- But the exchange order might be placed without the local record

**Mitigation options:**
1. **Signal handler in BotRunner:** Catch SIGTERM, finish current tick, then exit. (Already exists: `asyncio.shield` in executor)
2. **Separate bot process:** Run BotOrchestrator in a dedicated process, not inside Gunicorn workers. Web API communicates via IPC/signals. (More complex but bulletproof)
3. **Reconciliation on startup:** `orchestrator.resume_running_bots()` already runs on server startup — it reconciles state. This is the safety net.

**Recommendation:** Start with option 1 + 3 (existing safety nets). If trading moves to real money at scale, implement option 2.

---

## Effort Summary

| Phase | Hours | Impact |
|-------|-------|--------|
| Phase 1: Gunicorn setup | 2h | Zero-downtime deploys, crash recovery, process isolation |
| Phase 2: Watchdog tightening | 15 min | Max downtime 15 min → 2 min |
| Phase 3: macOS hardening | 5 min | Prevent disk sleep I/O errors |
| Phase 4: External monitoring | 10 min | Phone alerts within 60s |
| Phase 5: Graceful shutdown verify | 30 min | Trading safety during restarts |
| **Total** | **~3-4h** | |

## Out of Scope (But Documented for Future)

- **Secondary server:** A $5/mo VPS as a degraded-mode failover proxy. Implement if monitoring shows >0.1% downtime after Gunicorn.
- **Container orchestration:** Docker/Kubernetes — only if we need horizontal scaling or multi-machine deployment.
- **Database replication:** SQLite WAL mode already handles concurrent reads. If write contention becomes an issue, consider PostgreSQL.
- **CDN/edge caching:** Not applicable for a local-network API server.
- **M5 Ultra migration path:** When the M5 Ultra arrives, this entire stack carries over. Gunicorn workers can scale from 2 to 4+ with more RAM.

## Key Decision Needed

**Bot process isolation:** Should trading bots run inside Gunicorn workers (current) or in a separate dedicated process?

- **Inside workers (simpler):** Current architecture. Risk: worker rotation can interrupt bot ticks. Mitigation: signal handlers + reconciliation.
- **Separate process (safer):** Bot orchestrator runs as its own launchd service. Web API sends start/stop commands via Unix socket or HTTP to the bot process. Eliminates worker rotation risk entirely.

**Recommendation for now:** Keep bots in workers. The existing signal handling + reconciliation + atomic recording is sufficient for paper trading and early live trading ($25-250). Revisit when capital exceeds $1K or when moving to the M5 Ultra (natural migration point).
