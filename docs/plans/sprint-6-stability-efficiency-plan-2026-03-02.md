# Sprint 6: Stability & Efficiency — Enterprise-Grade Reliability

**Created:** 2026-03-02
**Audit:** `docs/plans/sprint-6-stability-efficiency-audit-2026-03-02.md`
**Status:** APPROVED WITH CONDITIONS (all conditions incorporated below)

## Context

Hestia runs on a hardwired Mac Mini M1 that should be "always on." In practice, recurring issues undermine reliability: stale server processes running for weeks without recycling, incomplete shutdown leaking database connections, no readiness gate causing 500s during startup, loosely pinned dependencies risking silent breakage on deploy, and uncompressed logs growing unbounded (73MB currently, one 42MB file from a single day). This sprint hardens the foundation.

## Audit Conditions (Incorporated)

These conditions were identified during plan audit and are now part of the plan:

1. **3A must include sequential fallback** — `asyncio.gather()` wrapped in try/except; on failure, fall back to sequential init with warning log. Zero-risk deployment.
2. **Verify Uvicorn lifespan cleanup on `limit-max-requests` exit** — smoke test before deploying 1A (set limit=5, send 6 requests, confirm shutdown logs appear).
3. **Reduce `ThrottleInterval` in server plist from 30s to 5s** — process recycling is now an expected exit path, not just crash recovery.
4. **Shutdown block must close all 12 missing managers** — corrected inventory below replaces original plan's incomplete list.

## Corrected Manager Inventory (16 total)

| # | Manager | Init Line | Has `close()`? | Currently Closed? | Sprint 6 Action |
|---|---------|-----------|-----------------|-------------------|-----------------|
| 1 | request_handler | 161 | No | No | Skip (no owned resources) |
| 2 | memory_manager | 162 | Yes (on class) | **No** | **Add `close_memory_manager()` wrapper + call** |
| 3 | task_manager | 163 | Yes | **No** | **Add to shutdown** |
| 4 | order_manager | 166 | Yes | **No** | **Add to shutdown** |
| 5 | order_scheduler | 167 | Yes | **No** | **Add to shutdown** |
| 6 | agent_manager | 168 | Yes | **No** | **Add to shutdown** |
| 7 | user_manager | 169 | Yes | **No** | **Add to shutdown** |
| 8 | cloud_manager | 172 | Yes (on class) | **No** | **Add `close_cloud_manager()` wrapper + call** |
| 9 | health_manager | 175 | Yes | **No** | **Add to shutdown** |
| 10 | wiki_manager | 178 | Yes | **No** | **Add to shutdown** |
| 11 | wiki_scheduler | 181 | Yes | Yes (already) | Keep |
| 12 | config_loader/writer | 211 | Yes | Yes (already) | Keep |
| 13 | invite_store | 215 | Yes | Yes (already) | Keep |
| 14 | explorer_manager | 218 | **No** | **No** | **Add `close()` method + `close_explorer_manager()` wrapper + call** |
| 15 | newsfeed_manager | 221 | Yes | **No** | **Add to shutdown** |
| 16 | investigate_manager | 224 | Yes | Yes (already) | Keep |

**Total missing from shutdown: 12 managers.** 3 need new close function wrappers (memory, cloud, explorer). Explorer also needs a `close()` method on the class.

---

## Phase 1: Server Reliability (~3 hours, highest impact)

### 1B. Complete shutdown cleanup (45 min) — FIRST

**Files**:
- `hestia/memory/__init__.py` — add `close_memory_manager()`
- `hestia/cloud/__init__.py` — add `close_cloud_manager()`
- `hestia/explorer/manager.py` — add `close()` method to `ExplorerManager`
- `hestia/explorer/__init__.py` — add `close_explorer_manager()`
- `hestia/api/server.py` — add all 12 missing closures to `lifespan()` finally block

**Pattern** (identical across all modules):
```python
async def close_X_manager() -> None:
    """Close the singleton X manager."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
```

**Shutdown order** (reverse of init — last initialized = first closed):
1. investigate_manager (already)
2. newsfeed_manager (ADD)
3. explorer_manager (ADD)
4. invite_store (already)
5. config_loader/writer (already)
6. wiki_scheduler (already)
7. wiki_manager (ADD)
8. health_manager (ADD)
9. cloud_manager (ADD)
10. user_manager (ADD)
11. agent_manager (ADD)
12. order_scheduler (ADD)
13. order_manager (ADD)
14. task_manager (ADD)
15. memory_manager (ADD)

Each in own try/except, matching existing pattern.

### 1C. Startup readiness gate (1.5 hours)

**Files**:
- `hestia/api/server.py` — new `ReadinessMiddleware` class + `app.state.ready` flag
- `hestia/api/routes/health.py` — new `/v1/ready` endpoint

**Behavior**:
- `app.state.ready = False` at FastAPI creation
- Set `True` after all managers init in `lifespan()`
- `ReadinessMiddleware` returns 503 + `Retry-After: 5` for all requests except: `/v1/ping`, `/v1/ready`, `/docs`, `/redoc`, `/openapi.json`, `/`
- Register middleware **LAST** so it executes **FIRST** (Starlette reverse order)
- `/v1/ready` returns `{"ready": true, "uptime_seconds": N}` (200) or `{"ready": false, "uptime_seconds": 0}` (503) — machine-parseable for watchdog (audit recommendation)

### 1D. Enhanced watchdog (15 min)

**File**: `scripts/hestia-watchdog.sh`

**Depends on**: 1C

Change primary health check from `/v1/ping` to `/v1/ready`. Catches both down servers AND servers still initializing after restart. Parse JSON response for `"ready": true` instead of grepping for "pong".

### 1A. Uvicorn request limit (15 min)

**File**: `hestia/api/server.py` — `uvicorn_config` dict
**File**: `scripts/com.hestia.server.plist` — reduce `ThrottleInterval` (audit condition 3)

Add `"limit_max_requests": 5000` and `"limit_max_requests_jitter": 500` to uvicorn config.

Reduce `ThrottleInterval` from 30 to 5 in server plist — recycling is now expected, not exceptional.

**Verification** (audit condition 2): After implementing, set limit=5, send 6 requests, confirm "shutting down" and "cleaning up connections" appear in logs. Then restore to 5000.

**Trade-off**: In-memory state (response cache, rate limiter windows) resets on restart. Acceptable — cache is optimization, not correctness.

---

## Phase 2: Dependency & Log Safety (~1.5 hours)

### 2A. Pin dependencies with pip-compile (45 min)

**Files**:
- Rename `requirements.txt` → `requirements.in` (human-edited input, add header comment)
- Generate `requirements.txt` via `pip-compile` (machine-generated lockfile, all `==` pins)
- `.github/workflows/deploy.yml` — add lockfile freshness check step

**Steps**:
1. `pip install pip-tools` (dev tool, not added to requirements)
2. Rename current file to `requirements.in`, add header comment explaining the workflow
3. `pip-compile requirements.in --output-file=requirements.txt --no-emit-index-url`
4. Verify lockfile resolves correctly
5. Add CI check: `pip-compile --dry-run` + diff to catch stale lockfile

Deploy scripts (`deploy-to-mini.sh`, `deploy.yml`) already do `pip install -r requirements.txt` — no changes needed.

### 2B. Log compression (30 min)

**New files**:
- `scripts/compress-logs.sh` — gzip logs older than 7 days, delete compressed logs older than 90 days
- `scripts/com.hestia.log-compressor.plist` — launchd daily at 3 AM

**Also**: Fix `hestia/logging/structured_logger.py` constructor default `retention_days: 90` → `30`.

Note: This fix has zero runtime effect (config override always applies via `_read_retention_days_from_config()`), but corrects the documentation lie in the constructor signature.

**Impact**: Current ~73MB uncompressed → ~8MB compressed. Ongoing growth capped.

---

## Phase 3: Performance (~1.5 hours)

### 3A. Parallel manager initialization (1-1.5 hours)

**File**: `hestia/api/server.py` — lifespan startup

**Current**: 16 managers initialized sequentially.

**Proposed**: 3-phase parallel init with sequential fallback (audit condition 1):
```
Phase 1 (sequential): request_handler, memory_manager  (foundation — other managers may read memory)
Phase 2 (asyncio.gather, try/except → sequential fallback):
    task_manager, order_manager, agent_manager, user_manager,
    cloud_manager, health_manager, wiki_manager, config_loader,
    invite_store, explorer_manager, newsfeed_manager, investigate_manager
Phase 3 (sequential): order_scheduler, wiki_scheduler  (depend on Phase 2 managers)
Phase 4 (fire-and-forget): _post_deploy_wiki_refresh
```

**Fallback mechanism**:
```python
try:
    results = await asyncio.gather(*phase2_tasks, return_exceptions=True)
    # Check for failures
    failures = [(name, r) for name, r in zip(names, results) if isinstance(r, Exception)]
    if failures:
        logger.warning("Parallel init had failures, falling back to sequential", ...)
        for name, task_fn in failed_items:
            await task_fn()
except Exception:
    logger.warning("Parallel init failed entirely, using sequential fallback", ...)
    # Sequential init of all Phase 2 managers
```

Log `startup_ms` for Phase 2 to track improvement. Expected: ~50% reduction in startup time.

### 3B. Cache-Control headers (15 min)

**File**: `hestia/api/server.py` — `SecurityHeadersMiddleware`

Currently sets `Cache-Control: no-store` on ALL responses. Make it path-aware:

| Path prefix | Cache-Control | Rationale |
|-------------|--------------|-----------|
| `/v1/ping` | `max-age=10` | Static health check |
| `/v1/ready` | `no-store` | Must always be fresh |
| `/v1/tools` | `max-age=60` | Tool list changes only on deploy |
| `/v1/wiki/articles` | `max-age=30` | Article list, short cache |
| Everything else | `no-store, no-cache` | Default (current behavior) |

---

## Implementation Sequence

```
1B (shutdown cleanup)     — safest, pure addition, no behavioral change
1C (readiness gate)       — new middleware + endpoint
1D (watchdog update)      — depends on 1C
1A (limit-max-requests)   — behavioral change, includes plist ThrottleInterval fix
2A (pip-compile)          — independent of Phase 1
2B (log compression)      — independent
3A (parallel init)        — includes sequential fallback per audit condition
3B (cache-control)        — trivial, last
```

Each change is independently deployable and testable.

## Half-Time Cut List

If time is cut to 3 hours:

| Keep | Cut | Reasoning |
|------|-----|-----------|
| 1B: Shutdown cleanup | 3A: Parallel init | Correctness > performance |
| 1C: Readiness gate | 3B: Cache headers | Safety > optimization |
| 1D: Watchdog update | 2B: Log compression | Depends on 1C; run gzip manually |
| 2A: pip-compile | 1A: Uvicorn limit | Dependency safety > process recycling |

---

## New Tests

- `tests/test_server_lifecycle.py`: readiness middleware (503 before ready, 200 after), `/v1/ready` endpoint, shutdown cleanup mocks
- Extend `tests/test_health.py`: `/v1/ready` integration test

## What We're NOT Doing (and why)

| Idea | Why skip |
|------|----------|
| Gunicorn multi-worker | Breaks ~15 in-memory singletons. Would need Redis. |
| Redis/external cache | 2.3MB total data, single user. |
| Hot/warm/cold archiving | Data is tiny. SQLite handles TB-scale. |
| Sub-agent orchestration | Council dual-path already has try/except fallback. |
| Multi-device message queue | Single user, 1-2 devices. |
| `/v1/metrics` endpoint | Nice-to-have, future sprint. |

## Files Modified (Summary)

| File | Changes |
|------|---------|
| `hestia/api/server.py` | Readiness middleware, readiness state, complete shutdown (12 managers), parallel init with fallback, cache-control, uvicorn limit |
| `hestia/api/routes/health.py` | `/v1/ready` endpoint |
| `hestia/memory/__init__.py` | Add `close_memory_manager()` export |
| `hestia/memory/manager.py` | Add `close_memory_manager()` function |
| `hestia/cloud/__init__.py` | Add `close_cloud_manager()` export |
| `hestia/cloud/manager.py` | Add `close_cloud_manager()` function |
| `hestia/explorer/__init__.py` | Add `close_explorer_manager()` export |
| `hestia/explorer/manager.py` | Add `close()` method + `close_explorer_manager()` function |
| `hestia/logging/structured_logger.py` | Fix retention_days default (90 → 30) |
| `scripts/hestia-watchdog.sh` | Check `/v1/ready` instead of `/v1/ping` |
| `scripts/com.hestia.server.plist` | Reduce ThrottleInterval 30 → 5 |
| `scripts/compress-logs.sh` | NEW — gzip + cleanup |
| `scripts/com.hestia.log-compressor.plist` | NEW — daily launchd schedule |
| `requirements.txt` → `requirements.in` | Rename (human-edited input) |
| `requirements.txt` | NEW — pip-compile lockfile |
| `.github/workflows/deploy.yml` | Lockfile freshness check |
| `tests/test_server_lifecycle.py` | NEW — readiness + shutdown tests |
