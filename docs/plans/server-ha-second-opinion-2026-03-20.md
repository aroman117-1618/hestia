# Second Opinion: Server High Availability Implementation

**Date:** 2026-03-20
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Verdict:** APPROVE WITH CONDITIONS (significant rearchitecture required)

## Plan Summary

5-phase plan (3-4h) to achieve enterprise-grade server reliability on Mac Mini M1. Core: Gunicorn + 2 Uvicorn workers for zero-downtime deploys and crash recovery, plus watchdog tightening (5 min → 60s), macOS hardening, and external monitoring via Healthchecks.io.

---

## Critical Finding: The Plan Has Two Showstoppers

### Showstopper 1: Trading Bot Duplication

The `BotOrchestrator.resume_running_bots()` runs inside the FastAPI lifespan. With 2 Gunicorn workers:

1. **Worker A starts** → lifespan → `resume_running_bots()` → bots start in Worker A
2. **Worker B starts** → lifespan → `resume_running_bots()` → **same bots start in Worker B**
3. **Result: 2 copies of every bot running → duplicate trades → financial loss**

During `kill -HUP` (deploy restart), old and new workers overlap briefly — creating a window where 3+ copies could run simultaneously.

**This is not fixable within the current architecture.** Bots must be extracted to a separate process.

### Showstopper 2: SQLite Write Contention

Two Uvicorn workers both writing to SQLite → frequent `database is locked` errors. SQLite supports one writer at a time (file-level lock). WAL mode helps concurrent reads but writes still serialize. Under load, API requests in Worker A waiting for Worker B's write lock = 500 errors and degraded performance.

**Note:** The fork safety concern (Gemini's "guaranteed corruption" claim) is actually overstated. With UvicornWorker, the lifespan runs per-worker, so each worker creates its own DB connections after fork. Connections are NOT shared across forks. However, write contention is real.

---

## Scale Assessment

| Scale | Works? | Breaking Points |
|-------|--------|----------------|
| Single user | Partially | Bot duplication, SQLite contention with multi-worker |
| Family | No | Multi-worker + SQLite = write contention under load |
| Enterprise | No | Single Mac Mini = single point of failure regardless |

---

## Front-Line Engineering

- **Feasibility:** The Gunicorn setup is mechanically straightforward. The plan correctly identified the module-level `app = FastAPI(...)` (line 677 of server.py). BUT trading bot decoupling is a prerequisite that adds 4-6h.
- **Hidden prerequisites:** Bot process separation, SQLite contention mitigation, memory validation
- **Testing gaps:** No load test defined for memory pressure. No test for concurrent SQLite writes from 2 workers. No test for bot duplication during worker rotation.

---

## Architecture Review

- **Fit:** Gunicorn is the standard Python deployment tool, but Gemini makes a strong case for `uvicorn --workers N` instead (purpose-built for ASGI, one less dependency).
- **Integration risk:** HIGH — trading bot lifecycle is tightly coupled to the web server lifespan. Decoupling requires new IPC mechanism.
- **Data model:** SQLite is the bottleneck for multi-worker. WAL mode + `busy_timeout` is the pragmatic fix; PostgreSQL is the enterprise fix but a much larger migration.

---

## Product Review

- **User value:** Very high — "app always works" is the goal. But value is only realized if the implementation doesn't introduce trading risks.
- **Scope:** Plan as written is too small. Needs bot decoupling + SQLite mitigation to be safe.
- **Opportunity cost:** 8-12h (revised) not spent on Trading Sprint 28 or macOS wiring Sprint 32.

---

## Infrastructure Review (Phase 7 — this is the critical phase)

- **Deployment impact:** Complete server restart architecture change. Requires launchd plist rewrite, new bot service plist, deploy script rewrite.
- **New dependencies:** Gunicorn (or none if using `uvicorn --workers`). Healthchecks.io free tier. ntfy.sh.
- **Memory pressure:** Gemini warns 2 workers may not fit on 16GB with Ollama. **MUST validate with actual measurement before deploying.**
- **Rollback strategy:** Revert launchd plist to single-process Uvicorn. Clean rollback.

---

## Executive Verdicts

- **CISO:** Acceptable — No new attack surface. Healthchecks.io ping-out model doesn't expose internal endpoints.
- **CTO:** Needs Remediation — Bot decoupling is mandatory. SQLite contention needs mitigation. Otherwise sound.
- **CPO:** Acceptable — Zero-downtime deploys and faster recovery directly serve the "always available" goal.
- **CFO:** Acceptable — 8-12h (revised) for eliminating the #1 operational pain point. Healthchecks.io is free.
- **Legal:** Acceptable — No regulatory concerns. Healthchecks.io processes only ping timestamps, no PII.

---

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 4 | No new attack surface. External monitoring uses ping-out model. |
| Empathy | 5 | Directly addresses "app is useless when server is down." |
| Simplicity | 2 | Multi-worker + bot decoupling + SQLite mitigation = significant complexity. |
| Joy | 3 | The result is satisfying but the implementation path is rough. |

**Flag:** Simplicity at 2 — the multi-worker approach introduces substantial architectural complexity (bot IPC, write contention, memory validation).

---

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment

Gemini rates **APPROVE WITH CONDITIONS** with 4 mandatory conditions:
1. Trading bots MUST be a separate launchd service (non-negotiable)
2. Migrate from SQLite to PostgreSQL (for write concurrency)
3. Use native `uvicorn --workers` instead of Gunicorn (simpler, purpose-built)
4. Perform memory load test before deploying

### Where Both Models Agree (High-Confidence)

- Trading bot duplication in multi-worker is a **showstopper** — bots MUST be decoupled
- Healthchecks.io + ntfy.sh is the right monitoring stack
- macOS hardening (pmset, disable auto-updates) is trivially correct
- Watchdog tightening from 5 min to 60s is correct
- Memory pressure on 16GB needs real measurement, not estimation
- Single Mac Mini is still SPOF — "enterprise-grade" on one machine has limits

### Where Models Diverge

| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| **Fork safety** | Safe — lifespan runs per-worker, connections created post-fork | "Guaranteed corruption" — SQLite not fork-safe | **Claude is right on the mechanism** (lifespan is per-worker), **Gemini is right on the risk** (write contention, not fork corruption). Net: connections are safe, concurrent writes are not. |
| **Gunicorn vs uvicorn --workers** | Gunicorn (standard, battle-tested) | Uvicorn native workers (simpler, purpose-built for ASGI) | **Gemini is right.** `uvicorn --workers 2` achieves the same goal with one fewer dependency. Gunicorn's WSGI heritage adds no value for a pure ASGI app. |
| **PostgreSQL migration** | Not proposed | Mandatory for enterprise-grade | **Pragmatic middle ground:** WAL mode + `busy_timeout=5000` handles the current load. PostgreSQL migration is a separate, larger project (8-16h) worth doing but not blocking the HA work. |
| **Worker count** | 2 workers | May need to be 1 after memory validation | **Gemini is right to flag this.** Measure first. If 2 workers + Ollama exceeds comfortable headroom, use 1 worker (still better than bare uvicorn via crash recovery and graceful restart). |

### Novel Insights from Gemini

1. **SQLite write contention** — Not just fork safety but actual `database is locked` errors under concurrent writes from multiple workers. WAL mode helps reads but writes still serialize.
2. **In-flight request handling during graceful timeout** — Long Ollama inference calls (30-60s) could be SIGKILL'd if they exceed `graceful_timeout`. Need to handle this in client retry logic.
3. **Configuration as code** — macOS hardening steps should be scripted (even a simple bash script) to prevent configuration drift after reboots or OS updates.
4. **Bot IPC mechanism** — Suggested Redis, database command queue, or internal API. For Hestia's scale, a database command queue (SQLite table) is simplest.

### Novel Insight from @hestia-critic

5. **Blue/green deploy as a simpler alternative to multi-worker.** Instead of Gunicorn/multi-worker (which introduces fork complexity), run a second Uvicorn instance on port 8444 during deploys. Deploy script starts new instance, waits for `/v1/ready`, switches traffic (via reverse proxy or client config), then stops old instance. Zero-downtime deploys WITHOUT fork safety concerns, worker duplication, or SQLite contention. Cost: 1-2h, zero fork risk. This achieves the same deploy-downtime goal through a fundamentally simpler mechanism.

6. **`preload_app=True` is worse than described.** The critic found that with preload, the lifespan runs in the MASTER process before forking — meaning singletons ARE initialized pre-fork, contradicting my earlier analysis that lifespan runs per-worker. If true, `get_X_manager()` finds `_instance != None` in forked workers and returns the fork-corrupted singleton. This needs definitive testing but significantly strengthens the case against multi-worker.

7. **Watchdog + Gunicorn conflict.** Both restart crashed processes. A worker crash could trigger: Gunicorn restarts worker immediately AND watchdog fires within 60s and `launchctl kickstart`s the Gunicorn master — potentially killing a healthy master mid-recovery.

---

## Revised Plan: What Actually Needs to Happen

### Phase 0: Bot Process Decoupling (4-6h) — MUST DO FIRST

This is the prerequisite that the original plan missed.

1. **Extract BotOrchestrator to standalone script** (`hestia/trading/bot_service.py`):
   - Standalone async Python script that initializes TradingManager + BotOrchestrator
   - Runs its own event loop, independent of FastAPI
   - Reads bot commands from a `bot_commands` SQLite table (start/stop/status)
   - Publishes events to `TradingEventBus` (existing)

2. **Create launchd service** (`com.hestia.trading-bots.plist`):
   - `RunAtLoad: true`, `KeepAlive: true`
   - Separate from web server lifecycle
   - Own logs: `logs/trading-bots.log`

3. **API routes communicate via command table:**
   - `POST /v1/trading/bots/{id}/start` → inserts command into `bot_commands` table
   - Bot service polls commands every 1s (or use SQLite `NOTIFY` if available)
   - Remove `orchestrator.resume_running_bots()` from web server lifespan

4. **Remove trading imports from server lifespan:**
   - Server no longer imports or manages `BotOrchestrator`
   - Web workers become stateless (safe to fork/scale)

### Phase 1: Deploy Resilience (1-2h)

**Two options — choose based on risk tolerance:**

**Option A: Blue/Green Deploy (recommended — simpler, zero fork risk)**
- Keep single Uvicorn process (no multi-worker, no fork complexity)
- Deploy script starts new instance on port 8444, waits for `/v1/ready`
- Switches traffic (update launchd plist port or nginx upstream), stops old instance
- Zero downtime, zero fork risk, zero SQLite contention
- Crash recovery via launchd `KeepAlive` (existing) + tightened watchdog (Phase 2)

**Option B: Multi-Worker (more resilient to worker crashes, more complex)**
Use `uvicorn --workers 2`** (not Gunicorn — per Gemini's recommendation).

Update launchd plist:
```xml
<key>ProgramArguments</key>
<array>
    <string>/Users/andrewroman117/hestia/.venv/bin/uvicorn</string>
    <string>hestia.api.server:app</string>
    <string>--host</string><string>0.0.0.0</string>
    <string>--port</string><string>8443</string>
    <string>--workers</string><string>2</string>
    <string>--ssl-keyfile</string><string>certs/server.key</string>
    <string>--ssl-certfile</string><string>certs/server.crt</string>
    <string>--limit-max-requests</string><string>1000</string>
</array>
```

**SQLite mitigation:** Add `busy_timeout=5000` to all `aiosqlite.connect()` calls (5s retry on lock). Verify WAL mode is enabled on all databases.

**Memory validation:** Run full stack, measure RSS of each process via `ps aux`. If >14GB total, reduce to 1 worker.

### Phase 2-4: Unchanged from Original Plan
- Watchdog tightening (60s, 2 strikes)
- macOS hardening (`disksleep 0`, disable auto-updates)
- External monitoring (Healthchecks.io + ntfy.sh)

### Revised Effort

| Phase | Hours | Notes |
|-------|-------|-------|
| Phase 0: Bot decoupling | 4-6h | NEW — prerequisite |
| Phase 1: Multi-worker | 2h | Uvicorn native, not Gunicorn |
| Phase 2: Watchdog | 15 min | Unchanged |
| Phase 3: macOS hardening | 5 min | Unchanged |
| Phase 4: Monitoring | 10 min | Unchanged |
| **Total** | **6.5-8.5h** | Up from 3-4h |

---

## Conditions for Approval

1. **Bot decoupling is mandatory and must be Phase 0.** Multi-worker serving CANNOT proceed until trading bots run in a separate process. Financial risk of duplicate trades is unacceptable.

2. **Use `uvicorn --workers` instead of Gunicorn.** Simpler, one fewer dependency, purpose-built for ASGI.

3. **Add `busy_timeout=5000` to all SQLite connections.** Mitigates write contention from multiple workers. WAL mode should be verified on all databases.

4. **Validate memory before deploying 2 workers.** If total RSS exceeds ~14GB, use 1 worker. One Uvicorn worker with crash recovery and graceful restart is still a significant improvement over bare single-process.

5. **Script the macOS hardening.** Create `scripts/harden-macos.sh` so it's reproducible after OS updates or reinstalls.

6. **PostgreSQL migration as a separate future sprint.** Worth doing for enterprise-grade concurrent writes, but not blocking the HA work. SQLite + WAL + busy_timeout is sufficient for current load.

---

*Audit generated by Claude Opus 4.6 with @hestia-explorer (technical validation), @hestia-critic (adversarial critique), and Gemini 2.5 Pro (cross-model validation).*
