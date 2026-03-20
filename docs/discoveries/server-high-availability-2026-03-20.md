# Discovery Report: Server High Availability

**Date:** 2026-03-20
**Confidence:** High
**Decision:** Implement a 3-tier HA stack: (1) Gunicorn multi-worker for process resilience + zero-downtime deploys, (2) hardened watchdog + external monitoring with alerting, (3) cloud failover proxy on a $5/mo VPS for last-resort reachability. Skip Kubernetes and container orchestration entirely.

## Hypothesis

The Hestia backend on Mac Mini M1 has unacceptable downtime characteristics for 24/7 trading bots and always-on personal AI. The current launchd + watchdog setup is a solid foundation but has gaps: up to 15 minutes of silent downtime, zero alerting, deploy-induced outages, and no redundancy for hardware/network failures. What is the right HA architecture for a single-machine, single-user system that runs trading bots?

## Current Infrastructure Audit

What already exists (read from codebase):

| Component | Status | File |
|-----------|--------|------|
| launchd server service | `KeepAlive: true`, `ThrottleInterval: 5s`, `RunAtLoad: true` | `scripts/com.hestia.server.plist` |
| Watchdog | Polls `/v1/ready` every 5 min, restarts after 3 failures via `launchctl kickstart` | `scripts/hestia-watchdog.sh` |
| Graceful shutdown | SIGTERM/SIGINT handlers, 15s drain, manager cleanup in reverse order | `hestia/api/server.py` lifespan |
| Uvicorn recycling | `limit_max_requests: 5000`, launchd restarts process | `hestia/api/server.py` |
| Ollama keepalive | Separate launchd job, polls every 10 min | `scripts/com.hestia.ollama-keepalive.plist` |
| CI/CD deploy | rsync + SSH + kill PIDs + launchd reload + readiness poll (40s timeout) | `.github/workflows/deploy.yml` |
| Tailscale | Remote access via `hestia-3.local` | Manual setup |

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** launchd KeepAlive auto-restarts crashes; watchdog catches stuck states; graceful shutdown prevents data corruption; Uvicorn request-limit recycling prevents memory leaks; trading bot has 3-strike error handling with exponential backoff | **Weaknesses:** Single Uvicorn process = any restart is total downtime; 5-min watchdog interval = up to 15 min silent downtime; zero external monitoring or alerting; deploy kills server for 25-40s; no Gunicorn = no worker supervision; Mac sleep settings not enforced in code/config |
| **External** | **Opportunities:** Gunicorn multi-worker gives zero-downtime HUP restarts; external monitoring (UptimeRobot/Healthchecks.io) is free and takes 5 min to set up; cloud failover proxy pattern is proven and cheap ($5/mo VPS); Tailscale Funnel could replace port forwarding; macOS `pmset` can be enforced via deploy script | **Threats:** Mac Mini hardware failure = total loss (SSD soldered, not replaceable); macOS forced updates reboot the machine; Tailscale can be slow to reconnect after wake; power outage without UPS = unclean shutdown + potential data loss; FileVault blocks headless boot |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **Gunicorn multi-worker** (eliminates deploy downtime, worker crash isolation); **External monitoring + alerting** (know immediately when down); **macOS sleep/power hardening** (`pmset`, disable auto-updates, UPS) | **Reduce watchdog interval** to 60s (quick win, marginal improvement) |
| **Low Priority** | **Cloud failover proxy** on VPS (handles Mac Mini total failure, network outages); **Tailscale Funnel** for public ingress | **Docker/container orchestration** (massive overhead for single-user system); **Second Mac Mini** (expensive, complex) |

## Argue (Best Case)

**The 3-tier approach solves 95% of downtime for under $10/mo and ~8 hours of work.**

1. **Gunicorn with 2-3 Uvicorn workers** eliminates the single biggest pain: deploy downtime. `kill -HUP` the Gunicorn master, it spins up new workers with the new code, drains old workers gracefully. Zero dropped requests. This also means a single worker crash doesn't kill the whole server — Gunicorn respawns it. On Mac Mini M1 with 16GB RAM, 2-3 workers at ~200MB each is easily affordable even with Ollama's ~11GB footprint.

2. **External monitoring** (UptimeRobot free tier: 50 monitors, 5-min intervals; or Healthchecks.io for cron/heartbeat monitoring) gives you push notifications within 5 minutes of any outage. Combined with reducing the watchdog to 60s intervals, worst-case silent downtime drops from 15 minutes to ~2 minutes.

3. **macOS hardening** (`sudo pmset -a sleep 0 disksleep 0 displaysleep 0`, disable automatic macOS updates, configure "restart after power failure") eliminates the OS-level causes of unexpected downtime. A $30 UPS handles the power outage scenario.

4. **Cloud failover proxy** (optional, Phase 2): A $5/mo VPS running Nginx with health checks. When Mac Mini is reachable, proxy passes through. When it's down, returns a cached "Hestia is temporarily offline, trading bots paused" response. The iOS/macOS app can detect this and show a meaningful status instead of spinning forever.

**Evidence supporting this approach:**
- Gunicorn + Uvicorn workers is the industry-standard FastAPI production pattern, documented by FastAPI's own deployment guide
- `kill -HUP` zero-downtime restart is a Gunicorn core feature, battle-tested for 15+ years
- UptimeRobot has monitored millions of endpoints; Healthchecks.io is specifically designed for cron/heartbeat monitoring
- The "cloud failover proxy" pattern is used by self-hosters running services behind Cloudflare Tunnel and Tailscale Funnel

## Refute (Devil's Advocate)

**Counter-arguments and hidden costs:**

1. **Gunicorn on macOS is not Linux:** Gunicorn uses `fork()` for workers, which works on macOS but has quirks. Apple Silicon's unified memory architecture means forked processes don't benefit from Linux's copy-on-write optimization as cleanly. With Ollama consuming 8-11GB, there's genuinely limited headroom. If each Uvicorn worker loads the full FastAPI app with all 18+ manager singletons, memory could spike during parallel init. **Mitigation:** Use `--preload` flag to load app before forking; test actual memory usage with 2 workers + Ollama running.

2. **Trading bot state during worker restart:** If a bot is mid-trade when a Gunicorn worker restarts, what happens? The bot runner uses `asyncio` tasks within the Uvicorn event loop. A graceful worker shutdown should drain, but if the bot is waiting on an exchange API call, the 30s Gunicorn timeout might kill it. **Mitigation:** Trading bots need to be idempotent and recover state from the database on restart. The existing 3-strike error handling helps.

3. **Complexity creep:** Adding Gunicorn + external monitoring + cloud proxy + UPS + pmset hardening is 5 new moving parts. Each one is simple, but together they create a surface area for config drift. A launchd plist that worked for bare Uvicorn needs updating for Gunicorn. The deploy script changes. The watchdog needs to health-check differently. **Mitigation:** Implement in phases. Phase 1 (Gunicorn + monitoring) is the 80/20. Phase 2 (cloud proxy) only if Phase 1 proves insufficient.

4. **The VPS failover proxy is a new SPOF:** Now you're depending on a VPS provider's uptime too. If the VPS goes down, your failover is down. And the VPS needs its own monitoring, updates, and SSH key management. **Mitigation:** Use a minimal VPS (DigitalOcean/Hetzner) with automatic OS updates; monitor the VPS with UptimeRobot too.

5. **Is this actually a problem?** If Hestia is down for 10 minutes while you're sleeping, does it matter? The trading bots have circuit breakers. The iOS app can show "offline." The real question is: how much money has downtime actually cost? If the answer is "none yet," the ROI on enterprise HA is negative. **Mitigation:** Track downtime incidents for 2 weeks with external monitoring before investing in the cloud proxy.

## Third-Party Evidence

**Mac Mini as always-on server — documented failure modes:**
- SSD wear from heavy logging/writes (soldered, not replaceable)
- FileVault blocks headless boot after power loss (must enter password locally)
- macOS auto-updates force unexpected reboots
- Thermal throttling under sustained load in poor airflow
- Headless GPU quirks (dummy HDMI plug sometimes needed)

**Gunicorn + Uvicorn on macOS:**
- Works identically to Linux for ASGI apps; the `uvicorn.workers.UvicornWorker` class is platform-independent
- Standard command: `gunicorn hestia.api.server:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8443`
- `--preload` reduces memory via shared app state before fork
- `max_requests` + `max_requests_jitter` replaces the current `limit_max_requests: 5000` in uvicorn config

**Tailscale reconnection after sleep:**
- No widely reported data on exact reconnection times
- Headless Tailscale via `tailscaled` (Homebrew + launchd) is more reliable than the Mac App Store version for always-on servers
- GitHub issue tailscale/tailscale#1134 documents reconnection delays; workaround is to prevent sleep entirely

**Cloud failover proxy pattern:**
- Nginx `proxy_pass` with `proxy_connect_timeout` + `error_page 502` serves a static fallback
- Cloudflare Tunnel has built-in health checks that can switch DNS within 30s of detecting failure
- Tailscale Funnel with `-bg` flag persists across reboots and resumes automatically

## Gemini Web-Grounded Validation

**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- Mac Mini M1 SSD wear is a real concern for server workloads (soldered, finite TBW)
- FileVault blocks headless boot — confirmed as a major gotcha for unattended servers
- Gunicorn + Uvicorn workers on macOS is standard and practical
- `sudo pmset -a sleep 0 disksleep 0 displaysleep 0` is the correct incantation for preventing sleep
- Cloud failover proxy with Nginx health checks is a proven, achievable pattern

### Contradicted Findings
- None materially contradicted. Gemini confirmed the overall architecture direction.

### New Evidence
- **Dummy HDMI plug** may be needed for headless Mac Mini to keep GPU active (some apps fail without it)
- **"Start up automatically after power failure"** setting in macOS can be unreliable — UPS is essential, not optional
- Tailscale's headless mode (`tailscaled` via Homebrew + launchd) is more reliable than the App Store version for servers
- Trading bot idempotency is critical for Gunicorn worker restarts — bots must recover state from DB

### Sources
- [Mac Mini sleep prevention - MacRumors](https://forums.macrumors.com/threads/how-to-prevent-mac-mini-m1-from-sleeping-disable-sleep.2280226/)
- [Tailscale headless macOS](https://github.com/MrCee/tailscale-headless-macos)
- [Tailscale sleep reconnection issue](https://github.com/tailscale/tailscale/issues/1134)
- [FastAPI deployment with workers](https://fastapi.tiangolo.com/deployment/server-workers/)
- [Zero-downtime FastAPI with Gunicorn](https://blog.naveenpn.com/zero-downtime-deployments-in-python-with-uvicorn-gunicorn-and-async-fastapi-apis)
- [Gunicorn graceful restart](https://blog.pecar.me/gunicorn-restart/)
- [Tailscale Funnel docs](https://tailscale.com/kb/1223/funnel)
- [Cloudflare Tunnel vs Tailscale comparison](https://dev.to/mechcloud_academy/cloudflare-tunnel-vs-ngrok-vs-tailscale-choosing-the-right-secure-tunneling-solution-4inm)
- [UptimeRobot](https://uptimerobot.com/)
- [Healthchecks.io](https://healthchecks.io/)
- [Uptime Kuma](https://github.com/louislam/uptime-kuma)

## Philosophical Layer

### Ethical Check
This is straightforward infrastructure hardening for a personal system. No ethical concerns. Making trading bots more reliable prevents accidental losses from unhandled downtime — this serves the user well.

### First Principles Challenge
**Why a single Mac Mini at all?** The ultimate first-principles answer is: because Hestia's value proposition is local-first AI with privacy, low latency, and no recurring cloud costs for inference. Moving to a cloud VM would undermine the core thesis. The Mac Mini is the right hardware choice; the question is purely about making it resilient.

**What would 10x better look like?** Two Mac Minis in active-passive failover with shared state via SQLite Litestream replication to S3, Tailscale as the mesh, and automatic DNS failover. This is achievable with the planned M5 Ultra Mac Studio upgrade (the M1 becomes the standby). But that's Sprint 30+ territory.

### Moonshot: Active-Active Dual Mac Setup
- **What:** M5 Ultra (primary) + M1 Mini (standby) with Litestream SQLite replication, shared ChromaDB via S3, and Tailscale subnet routing for automatic failover
- **Technical viability:** High. Litestream is production-ready for SQLite replication. Tailscale supports subnet routing for failover. ChromaDB can use S3 as backing store.
- **Effort:** 20-30 hours (after M5 arrives)
- **Risk:** State synchronization edge cases (in-flight trades, memory consolidation)
- **MVP:** Litestream replication + manual failover script
- **Verdict:** SHELVE — pursue after M5 Ultra arrives. The single-machine 3-tier approach is sufficient for now.

### Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 4 | No new attack surface except VPS SSH; Tailscale already provides encrypted mesh |
| Empathy | 5 | Eliminates the "dead dashboard" experience; trading bots stay protected |
| Simplicity | 4 | Each tier is simple; combined complexity is manageable in phases |
| Joy | 4 | Knowing the server self-heals and alerts you is genuinely satisfying |

## Recommendation

**Implement in two phases:**

### Phase 1: Process Resilience + Monitoring (4-6 hours, do now)

1. **Switch from bare Uvicorn to Gunicorn + 2 Uvicorn workers**
   - Install gunicorn: `pip install gunicorn`
   - Update `com.hestia.server.plist` ProgramArguments to:
     ```
     gunicorn hestia.api.server:app
       --workers 2
       --worker-class uvicorn.workers.UvicornWorker
       --bind 0.0.0.0:8443
       --certfile /path/to/hestia.crt
       --keyfile /path/to/hestia.key
       --preload
       --max-requests 5000
       --max-requests-jitter 500
       --graceful-timeout 30
       --timeout 120
     ```
   - Update `deploy.yml` to send `kill -HUP` to Gunicorn master PID instead of kill-and-reload
   - Update `hestia-watchdog.sh` to check Gunicorn master PID file

2. **macOS hardening** (run once on Mac Mini via deploy script)
   - `sudo pmset -a sleep 0 disksleep 0 displaysleep 0`
   - `sudo pmset -a autorestart 1` (restart after power failure)
   - Disable automatic macOS updates: `sudo softwareupdate --schedule off`
   - Verify FileVault is OFF (or accept the risk of needing local access after power loss)
   - Consider UPS ($30-50)

3. **External monitoring**
   - Sign up for UptimeRobot free tier (or Healthchecks.io)
   - Monitor `https://<tailscale-ip>:8443/v1/ready` every 5 min
   - Configure push notifications to phone (iOS UptimeRobot app)
   - Add a heartbeat monitor for the watchdog script itself (Healthchecks.io ping)

4. **Reduce watchdog interval** from 300s to 60s in `com.hestia.watchdog.plist`

### Phase 2: Cloud Failover Proxy (4-6 hours, do after 2 weeks of Phase 1 data)

Only if Phase 1 monitoring shows >1% downtime or trading-impacting outages:

1. **$5/mo VPS** (DigitalOcean, Hetzner, or Vultr)
2. **Nginx reverse proxy** with health checks against Mac Mini Tailscale IP
3. **Failover page**: static JSON response when Mac Mini unreachable
4. **iOS app update**: detect failover response, show "Hestia offline — trading paused" banner
5. **Monitor the VPS itself** with UptimeRobot

**Confidence: High.** Phase 1 alone will eliminate 90%+ of the current downtime risk. The Gunicorn migration is the single highest-ROI change.

**What would change this recommendation:**
- If memory profiling shows Gunicorn + 2 workers + Ollama exceeds 16GB -> drop to 1 worker (still get graceful restarts)
- If trading bot losses from downtime exceed $50/mo -> accelerate Phase 2
- If M5 Ultra arrives -> pursue the active-passive moonshot instead of VPS proxy

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** Gunicorn's `fork()` model on macOS with Ollama eating 11GB RAM might cause OOM kills. And trading bots running in Uvicorn workers may lose state during graceful restarts.

**Response:** `--preload` means the app is loaded once before forking, so workers share most memory pages. Two workers at ~150-200MB each on top of the shared base is well within the ~5GB remaining after Ollama. Trading bots already write state to SQLite on every trade — the bot runner's `_save_state()` is called after each signal evaluation. A graceful 30s timeout is more than enough for the current 15-minute poll interval bots. The real risk is during a mid-execution exchange API call, but the exchange adapters have their own timeouts (10s) and the risk manager records pending orders in the database.

### The Pragmatist: "Is the effort worth it?"
**Challenge:** 4-6 hours for Phase 1 when you could be building Sprint 28 (Alpaca stocks). The current setup "mostly works."

**Response:** Trading bots running 24/7 during paper soak need reliable infrastructure before real money flows. One missed signal during a crash could invalidate the entire soak period. More practically: the Gunicorn migration also improves deploy experience (no more "is the server up yet?" after CI/CD pushes). This is a force multiplier for all future development velocity.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** In 6 months you'll have the M5 Ultra Mac Studio. This whole single-machine HA setup becomes obsolete when you can do active-passive with the M1 as standby.

**Response:** Phase 1 investment (Gunicorn, monitoring, pmset hardening) transfers directly to the M5 setup — you'll still want multi-worker Gunicorn and external monitoring on the primary. The VPS proxy (Phase 2) becomes optional with a standby machine but could remain as a third layer. Nothing here is throwaway work.

## Open Questions

1. **Memory profiling needed:** Run `gunicorn --preload --workers 2` alongside Ollama and measure actual RSS per worker. If >500MB per worker, drop to 1 worker.
2. **Trading bot restart safety:** Verify that `BotRunner` recovers cleanly from a SIGTERM during exchange API calls. Write a test that kills a bot mid-poll and confirms no orphaned orders.
3. **Tailscale headless mode:** Is the Mac Mini running `tailscaled` (Homebrew) or the App Store version? The headless daemon is more reliable for servers.
4. **UPS purchase:** Specific model recommendation for Mac Mini M1 (APC BE425M or similar, ~$40).
5. **Gunicorn PID file location:** Needed for the watchdog and deploy scripts. Standard: `/tmp/hestia-gunicorn.pid` via `--pid` flag.
