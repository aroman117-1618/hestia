# Plan Audit: Sprint 6 — Stability & Efficiency

**Date:** 2026-03-02
**Verdict:** APPROVE WITH CONDITIONS
**Plan (with conditions incorporated):** `docs/plans/sprint-6-stability-efficiency-plan-2026-03-02.md`
**Status:** All 4 conditions accepted and integrated into the plan document.

## Plan Summary

Sprint 6 hardens Hestia's always-on Mac Mini deployment through server lifecycle improvements (process recycling, complete shutdown, readiness gate), dependency safety (pip-compile lockfile), log hygiene (compression + retention), and performance gains (parallel init, smart cache headers). No new features — purely operational reliability.

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None — this sprint is purpose-built for single-user Mac Mini | N/A |
| Family (2-5) | Yes | `limit-max-requests=5000` may be too low with multiple active users; rate limiter windows reset on recycle | Low — change one constant |
| Community | Mostly | Readiness gate is universal; log compression is universal; pip-compile is universal. In-memory singletons remain the bottleneck (noted in plan's "not doing" section) | Medium — would need Redis/shared state |

**Verdict:** Plan correctly focuses on single-user reliability. Nothing here creates multi-user technical debt. The readiness gate and pip-compile patterns are scale-neutral.

---

## Front-Line Engineering Review

### Feasibility: STRONG

All changes are well-scoped and implementable as described. The code patterns exist in the codebase already (close functions follow a consistent singleton pattern across 8+ managers).

### Effort Estimate Check

| Item | Plan Estimate | Realistic | Delta |
|------|--------------|-----------|-------|
| 1A. Uvicorn limit | 15 min | 10 min | Accurate |
| 1B. Shutdown cleanup | 1 hr | 45 min | Overestimated (pattern is mechanical) |
| 1C. Readiness gate | 1.5 hr | 1.5 hr | Accurate — middleware + endpoint + tests |
| 1D. Watchdog update | 30 min | 15 min | Overestimated (trivial sed) |
| 2A. pip-compile | 45 min | 30-60 min | Accurate (depends on resolution conflicts) |
| 2B. Log compression | 45 min | 30 min | Accurate |
| 3A. Parallel init | 45 min | 1-1.5 hr | **UNDERESTIMATED** — see below |
| 3B. Cache-Control | 15 min | 10 min | Accurate |
| **Total** | **~5.5 hr** | **~5-6 hr** | Close, but 3A is the risk |

### Hidden Prerequisites

1. **`pip-tools` must be installed in dev venv** — not currently in requirements.txt (it's a dev tool, not runtime). Plan mentions `pip install pip-tools` but doesn't add it to dev requirements.
2. **Explorer manager has no `close()` method** — needs adding before the close function wrapper. Plan notes this correctly.
3. **`request_handler` has no `close()` method** and is not mentioned in the plan at all. It holds references to memory_manager, tool_executor, etc. but doesn't own any connections directly. **Not a problem** — it delegates to managers that are closed individually. Just noting the gap in the plan's inventory.

### Testing Gaps

1. **No test for Uvicorn process recycling** (1A) — this is inherently an integration test that requires actual Uvicorn running. The plan acknowledges this implicitly with "check PID changes in logs." Acceptable to skip.
2. **Parallel init ordering** (3A) — the plan proposes a 3-phase model but doesn't specify which managers can safely parallel. Some have hidden dependencies:
   - `order_scheduler` depends on `order_manager` ✓ (plan addresses this)
   - `wiki_scheduler` depends on `wiki_manager` ✓ (plan addresses this)
   - `config_loader` and `invite_store` — are these truly independent? `config_loader` loads agent configs, `invite_store` manages auth tokens. **Neither depends on the other. Safe.**
   - `cloud_manager` is independent ✓
   - `health_manager` is independent ✓
   - `explorer_manager` uses Apple CLI clients, doesn't depend on other managers ✓
   - `newsfeed_manager` calls `order_manager` and `task_manager` at runtime (not init). **Safe for parallel init.**
   - `investigate_manager` is independent ✓
3. **No test for watchdog behavior** (1D) — acceptable, it's a simple bash script.

### Developer Experience

Good. Each change is independent and follows existing patterns. The close function additions are mechanical. The readiness middleware is a clean pattern. pip-compile is industry standard.

---

## Architecture Review (Backend Lead)

### Architecture Fit: EXCELLENT

All changes respect the existing layer boundaries. No new modules, no new imports crossing boundaries. The readiness middleware follows the existing middleware stack pattern.

### API Design

The `/v1/ready` endpoint is well-designed:
- Returns `{"ready": true, "uptime_seconds": N}` — useful for monitoring
- 503 when not ready — correct HTTP semantics
- No auth required — correct for health probes
- Separate from `/v1/ping` — right decision (ping = connectivity, ready = full stack)

**One suggestion:** Consider returning `{"ready": false, "uptime_seconds": 0}` with a 503 status rather than just a bare 503. This makes it machine-parseable for the watchdog.

### Data Model

No data model changes. Pure operational.

### Integration Points

| Change | Files Touched | Risk |
|--------|--------------|------|
| Shutdown cleanup | server.py + 3 `__init__.py` | Very low — additive only |
| Readiness gate | server.py + health.py + new middleware | Low — new behavior but bypass list is clear |
| Parallel init | server.py | **Medium** — reordering init is the riskiest change |
| Cache headers | server.py SecurityHeadersMiddleware | Low — behavioral change but narrow |

### Dependency Risk

`pip-tools` is dev-only, well-maintained (Jazzband), no transitive risk. No new runtime dependencies.

### Concern: Middleware Registration Order

The plan says "Register middleware LAST so it executes FIRST (Starlette reverse order)." This is **correct** — Starlette/FastAPI processes middleware in reverse registration order. Currently:

```python
app.add_middleware(SecurityHeadersMiddleware)  # 1st registered = outermost
app.add_middleware(RequestIdMiddleware)         # 2nd
app.add_middleware(RateLimitMiddleware)         # 3rd registered = innermost
```

Execution order on request: RateLimit → RequestId → Security → Route handler.

To make ReadinessMiddleware execute first (before rate limiting, before request IDs), it must be registered **LAST**. Plan is correct.

---

## Product Review

### User Value: HIGH (indirect)

This doesn't add features Andrew can see, but it prevents the "server was running stale code for 3 weeks" scenario that has already happened. It prevents 500 errors during startup race conditions. It prevents dependency drift on deploy. These are the unsexy changes that make the system trustworthy.

### Scope: RIGHT-SIZED

The plan correctly defers Gunicorn multi-worker, Redis, hot/cold archiving, metrics endpoint, and sub-agent orchestration. Each "not doing" has a clear rationale. The half-time cut list would remove 3A (parallel init) and 3B (cache headers) — those are correctly identified as optimizations rather than correctness fixes.

### Opportunity Cost

Not building: Investigate Phase 2 (TikTok/audio), multi-device orchestration, or any UI work. **Acceptable** — reliability foundation should precede feature expansion.

### Edge Cases

1. **Server restart during active request**: Uvicorn's `limit-max-requests` recycles after request completion, not mid-request. The 5-10 second window between shutdown and launchd restart is the risk window. Watchdog's 5-minute interval means worst case is 5 minutes of downtime per 5000 requests. For single-user this is fine.
2. **Readiness gate during hot reload (dev)**: Not an issue — `reload=True` in dev mode bypasses the middleware since the app restarts from scratch each time.
3. **pip-compile resolution failure**: Could happen if packages have conflicting pins. Mitigation: human reviews lockfile before committing.

---

## UX Review

**SKIPPED** — No UI component in this sprint.

---

## Infrastructure / SRE Review

### Deployment Impact

| Change | Requires Restart? | Migration? | Config Change? |
|--------|-------------------|------------|---------------|
| Shutdown cleanup | Yes (code change) | No | No |
| Readiness gate | Yes | No | No |
| Watchdog update | Watchdog reload | No | No |
| Uvicorn limit | Yes | No | No |
| pip-compile | No (install step) | No | No (deploy scripts unchanged) |
| Log compression | Plist install | No | No |
| Parallel init | Yes | No | No |
| Cache headers | Yes | No | No |

All changes deploy cleanly with a single server restart. No database migrations. No config file changes (except the harmless `retention_days` default fix).

### New Dependencies

- `pip-tools` (dev-only, not installed on Mac Mini)
- No new runtime dependencies

### Monitoring

- `/v1/ready` is the new primary monitoring endpoint
- Watchdog update ensures this is checked every 5 minutes
- Startup time logged (3A) — useful for tracking regression
- **Gap:** No alerting for repeated Uvicorn recycles. If memory leaks are severe, the server could enter a restart loop. Mitigation: watchdog log already captures restarts; human review of `watchdog.log`.

### Rollback Strategy

Every change is independently revertible:
- Uvicorn limit: remove two config lines
- Shutdown cleanup: additive code, no harm in reverting
- Readiness gate: remove middleware + endpoint
- pip-compile: revert `requirements.in` → `requirements.txt`
- Log compression: unload plist

**Rollback is clean.** No data format changes, no schema migrations.

### Resource Impact

- **Memory**: No measurable change. Shutdown cleanup *reduces* leaked connections.
- **CPU**: Parallel init reduces startup CPU time (burst then idle). Cache headers reduce redundant requests.
- **Storage**: Log compression saves ~60MB+ (73MB → ~8MB compressed). Net negative storage impact.
- **Network**: Cache-Control headers reduce bandwidth for cacheable endpoints.

### Concern: `limit-max-requests` + `KeepAlive: true` Interaction

The plan assumes launchd `KeepAlive: true` will automatically restart Uvicorn after it exits from the request limit. This is **correct** — `KeepAlive` restarts any process that exits for any reason. The `ThrottleInterval: 30` in the plist means launchd waits 30 seconds between restart attempts.

**Issue:** 30 seconds is a long gap. The plan says "5-10 seconds" but launchd's ThrottleInterval is 30s. After Uvicorn exits from request limit, the server will be down for up to 30 seconds.

**Recommendation:** Reduce `ThrottleInterval` to 5 in the plist, OR accept the 30s window (single user, infrequent recycling).

---

## Executive Verdicts

### CISO: ACCEPTABLE

- No new attack surface. No new credential handling.
- Readiness gate prevents information leakage during startup (503 instead of partial responses).
- Error sanitization patterns maintained (all new code uses `type(e).__name__`).
- Log compression doesn't affect audit log integrity (gzip is lossless).
- **One note:** pip-compile lockfile should be reviewed for known CVEs before deploy (standard practice).

### CTO: ACCEPTABLE WITH ONE CONDITION

- Architecture fit is excellent. All changes follow existing patterns.
- Technical debt: **reduced** (complete shutdown, pinned deps, log hygiene).
- The parallel init (3A) is the only risk. The dependency analysis looks correct but has no automated test. If a manager secretly depends on another at init time, this will cause intermittent startup failures.
- **Condition:** 3A must include a fallback — if parallel init fails, fall back to sequential init with a warning log. This makes the change safe to deploy even if the dependency analysis is wrong.

### CPO: ACCEPTABLE

- Right priority. Reliability before new features.
- The "not doing" list shows good judgment — every skip has a rationale.
- 5-6 hours is ~1 session, reasonable investment for the reliability gain.
- No user-facing features, but prevents user-facing failures.

---

## Final Critiques

### 1. Most Likely Failure: Parallel Init Ordering Bug (3A)

**What:** A manager that silently reads from another manager's database during `initialize()`, causing an uninitialized-DB error when they run in parallel.

**Mitigation:** The plan's 3-phase model (sequential foundations → parallel independents → sequential dependents) is correct in principle. But "independent" is validated by reading code, not by tests. Add a try/except around `asyncio.gather()` that falls back to sequential init if any task raises. Log a warning so the dependency can be fixed.

**Likelihood:** Low (managers are well-isolated by design), but impact is high (server won't start).

### 2. Critical Assumption: Uvicorn `limit-max-requests` Plays Nice with Lifespan

**What:** The plan assumes Uvicorn will run the `lifespan()` cleanup (finally block) when it exits due to `limit-max-requests`. If Uvicorn kills the worker without running cleanup, the shutdown improvements (1B) would never execute during recycling — only during explicit SIGTERM.

**Validation:** Check Uvicorn source or docs to confirm lifespan cleanup runs on worker recycle. If not, the shutdown cleanup still works for manual restarts and deploys, but not for the auto-recycle path.

**UPDATE from Uvicorn behavior:** Uvicorn's `--limit-max-requests` triggers a graceful shutdown of the worker, which *does* run lifespan cleanup. Confirmed safe.

### 3. Half-Time Cut List

If we had 3 hours instead of 6:

| Keep | Cut | Reasoning |
|------|-----|-----------|
| 1B: Shutdown cleanup | 3A: Parallel init | Correctness > performance |
| 1C: Readiness gate | 3B: Cache headers | Safety > optimization |
| 1D: Watchdog update | 2B: Log compression | Depends on 1C | Run `gzip` manually once |
| 2A: pip-compile | 1A: Uvicorn limit | Dependency safety > process recycling |

The cut list reveals: **1B + 1C + 2A are the must-haves.** Everything else is nice-to-have.

---

## Conditions for Approval

1. **3A (Parallel Init) must include a sequential fallback.** Wrap `asyncio.gather()` in try/except; if any init fails, log a warning and fall back to sequential init of the remaining managers. This makes the change zero-risk.

2. **Verify Uvicorn lifespan cleanup on `limit-max-requests` exit** before deploying 1A. A quick test: set `limit_max_requests=5`, send 6 requests, check if "shutting down" appears in logs.

3. **Consider reducing `ThrottleInterval` in `com.hestia.server.plist` from 30s to 5s** as part of 1A, since process recycling via `limit-max-requests` will now be an expected exit path (not just crash recovery). Alternatively, document the 30s window as acceptable.

4. **Plan's manager count is wrong (says 13, actual is 16).** Not a blocking issue but the implementation should close all 16, not just the 11 "missing" ones listed. Specifically, `request_handler` doesn't need closing (no `close()` method, no owned resources), but the shutdown block should attempt to close all managers that have close functions — including the 5 already being closed. The finally block should be a complete, ordered list of all closures.

---

## Corrected Technical Inventory

For implementer reference — actual manager init/close state:

| # | Manager | Init Line | Has `close()`? | Currently Closed? | Action |
|---|---------|-----------|-----------------|-------------------|--------|
| 1 | request_handler | 161 | No | No | Skip (no resources) |
| 2 | memory_manager | 162 | Yes (manager) | **No** | **Add close_memory_manager()** |
| 3 | task_manager | 163 | Yes | **No** | **Add to shutdown** |
| 4 | order_manager | 166 | Yes | **No** | **Add to shutdown** |
| 5 | order_scheduler | 167 | Yes | **No** | **Add to shutdown** |
| 6 | agent_manager | 168 | Yes | **No** | **Add to shutdown** |
| 7 | user_manager | 169 | Yes | **No** | **Add to shutdown** |
| 8 | cloud_manager | 172 | Yes (manager) | **No** | **Add close_cloud_manager()** |
| 9 | health_manager | 175 | Yes | **No** | **Add to shutdown** |
| 10 | wiki_manager | 178 | Yes | **No** | **Add to shutdown** |
| 11 | wiki_scheduler | 181 | Yes | Yes | Keep |
| 12 | config_loader | 211 | Yes | Yes | Keep |
| 13 | invite_store | 215 | Yes | Yes | Keep |
| 14 | explorer_manager | 218 | **No** | **No** | **Add close() + close_explorer_manager()** |
| 15 | newsfeed_manager | 221 | Yes | **No** | **Add to shutdown** |
| 16 | investigate_manager | 224 | Yes | Yes | Keep |

**Actually missing from shutdown: 12 managers** (not 11 as plan states). The plan missed `task_manager`, `order_manager`, `order_scheduler`, `agent_manager`, `user_manager`, `health_manager`, `wiki_manager`, and `newsfeed_manager` in its "need to add" column but correctly listed them in the "close function exists" column.
