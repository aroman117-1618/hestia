# Codebase Audit: Hestia
**Date:** 2026-03-01
**Auditor:** Claude Opus 4.6 (CISO/CTO/CPO panel)
**Overall Health:** Healthy

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Consistent manager pattern across all 21 modules. Full async I/O (aiosqlite everywhere). Comprehensive error sanitization in route handlers. Strong credential management (double encryption, Keychain-backed). Excellent test coverage (1085+ tests, 25 files). Security headers on all responses. Rate limiting with per-endpoint tuning. Audit logging for credential access. Well-maintained decision log (35 ADRs). | **Weaknesses:** Schema location split (schemas.py vs inline in routes). Proactive routes use wrong auth dependency (`verify_device_token` instead of `get_device_token`). No SQLite connection pooling. Single-process singletons via global variables (thread safety concern for multi-worker). CLAUDE.md endpoint count drifts from reality (says 118, actual 116). |
| **External** | **Opportunities:** Newsfeed module is well-designed for multi-user from day one. User profile markdown system is unique and extensible. Consolidate all Pydantic schemas into `schemas.py` for consistency. Add connection pooling for concurrent requests. Formalize the auth dependency pattern (one function, one name). | **Threats:** Device revocation fail-open policy (ADR-034) means a compromised device stays active if invite store is down. Self-signed TLS with no certificate rotation. JWT secret stored in memory as module-level global (process restart regenerates if Keychain unavailable). No request signing or mTLS for Tailscale access. Orders execution is stub-only (TODO in manager.py:438). |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues

| Issue | Location | Risk | Recommendation |
|-------|----------|------|----------------|
| Proactive routes use wrong auth dependency | `hestia/api/routes/proactive.py:20,142` | Medium: `verify_device_token` is not a proper FastAPI dependency; takes `token: str` not Header. FastAPI resolves it as a query parameter, bypassing header-based auth pattern. | Replace `verify_device_token` with `get_device_token` in all proactive route signatures. |
| Device revocation fail-open | `hestia/api/middleware/auth.py:283-289` | Medium: If invite store is unavailable, revoked devices are still allowed through. Logged but not blocked. | Accept as documented trade-off (ADR-034) but add a metric/alert for revocation check failures so they are surfaced quickly. |
| JWT secret in-memory fallback | `hestia/api/middleware/auth.py:54-66` | Low: If Keychain is unavailable, JWT secret is generated in-memory only. Server restart would invalidate all tokens. | Acceptable for single-server. Document the failure mode. |

### Findings

**Authentication & Authorization**

- JWT uses HS256 with 90-day expiry. Adequate for single-server deployment. No token rotation or refresh mechanism beyond re-registration.
- `get_secret_key()` correctly uses Keychain-first, environment variable, then generates new. Constant-time comparison via `secrets.compare_digest` for setup secret.
- All 116 endpoints are auth-gated except: `/v1/health`, `/v1/ping`, `/v1/auth/register`, `/v1/auth/register-with-invite` (intentionally public). Root `/` endpoint is also public but informational only.
- Invite rate limiting: 5 per hour, in-memory counter. Adequate for single-server.
- **Bug found**: `hestia/api/routes/proactive.py` uses `Depends(verify_device_token)` which is a regular function taking `token: str`, not a FastAPI dependency function. FastAPI will resolve `token` as a query parameter, not from the `X-Hestia-Device-Token` header. This means proactive endpoints may accept auth tokens via query string instead of header, and `device_id` receives a dict (the decoded payload) instead of a string. The `device_id[:8]` at line 148 would slice the dict's string repr, not a device ID.

**Credential Management**

- Three-tier partitioning (operational/sensitive/system) correctly implemented in `hestia/security/credential_manager.py`.
- Double encryption: Fernet (master key) + Keychain AES-256. Master key stored in system partition.
- No hardcoded secrets found in codebase. All API keys flow through `CredentialManager` or environment variables.
- `validate-security-edit.sh` hook enforces no plaintext secrets in security-critical files.

**Error Handling & Information Leakage**

- `sanitize_for_log(e)` used consistently across 18 of 20 route modules (all that have error handling). Two exceptions:
  - `hestia/api/routes/voice.py` uses `type(e).__name__` (safe but inconsistent).
  - `hestia/api/routes/orders.py:298` uses `str(e)` for control flow only (not logged or returned to client).
- Global exception handler in `server.py:329` correctly sanitizes all unhandled exceptions. Returns generic message + request_id only.
- No stack traces returned to clients. Traceback logged internally only.
- Health check response includes `sanitize_for_log(e)` in error fields -- this is slightly risky as it returns sanitized error info to unauthenticated clients. The sanitization removes secrets but may still reveal internal component names.

**Attack Surface**

- CORS restricted to localhost origins by default. Configurable via `HESTIA_CORS_ORIGINS` env var.
- Security headers comprehensive: HSTS, CSP, X-Frame-Options, X-XSS-Protection, Referrer-Policy, Cache-Control.
- Rate limiting on all endpoints with per-category tuning (5/min for auth, 20/min for chat, 120/min for health).
- SQL injection: All database queries use parameterized `?` placeholders. No string concatenation of user input into SQL.
- Prompt injection: `ValidationPipeline` in orchestration/validation.py has pattern detection for secrets in prompts. Council/inference pipeline handles untrusted input.
- Communication gate (`execution/gate.py`) enforces approval for outbound operations.
- Self-signed TLS: Adequate for Tailscale tunnel (which provides its own encryption). No certificate rotation mechanism.
- `X-Forwarded-For` trusted without validation in rate limiter (`rate_limit.py:100`). Could allow rate limit bypass if attacker controls this header. Low risk on Tailscale-only network.

---

## CTO Audit
**Rating:** Strong

### Critical Issues

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| Schema location inconsistency | 6 route files define inline schemas | Maintenance burden: developers must check two locations. | Migrate all inline schemas to `hestia/api/schemas.py` or adopt explicit per-module schema files. |
| No SQLite connection pooling | All 13 database modules | Under concurrent load, single connection could become bottleneck. | For single-user this is fine. For multi-user, add aiosqlite connection pool or migrate to PostgreSQL. |
| Singleton singletons via global variables | All manager modules | Not thread-safe for multi-worker uvicorn. | Fine for single-worker. If scaling to multi-worker, use proper DI container or per-request factories. |

### Findings

**Layer Boundaries**

- Import hierarchy is clean:
  - `security/` imports only from `logging/` (correct -- lowest layer)
  - `inference/` imports only from `logging/`, `cloud/` (correct)
  - `memory/` imports from `logging/` only (correct)
  - `orchestration/` imports from `inference/`, `memory/`, `execution/`, `council/`, `logging/` (correct -- orchestration layer)
  - `api/` imports from all layers (correct -- top layer)
- No upward imports detected. No circular dependencies.
- One noteworthy coupling: `orchestration/handler.py:28` imports from `execution/` (tool execution), which is architecturally correct (orchestration coordinates execution).

**Pattern Consistency**

- Manager pattern (models.py + database.py + manager.py + `get_X_manager()`) followed in: memory, tasks, orders, agents, user, cloud, health, wiki, explorer, newsfeed. Consistent.
- Logging: `logger = get_logger()` with `LogComponent` enum used correctly in all modules. `LogComponent` enum includes all 15 components: ACCESS, ORCHESTRATION, MEMORY, INFERENCE, EXECUTION, SECURITY, API, SYSTEM, VOICE, CLOUD, COUNCIL, HEALTH, WIKI, EXPLORER, NEWSFEED.
- Async/await: All I/O is async. All database modules use `aiosqlite`. HTTP clients use `httpx` (async). Only blocking call found: `time.sleep(0.5)` in `logging/viewer.py:213` (a dev-only log viewer, not in request path).
- Type hints: Good coverage across all modules. Function signatures consistently typed.

**Code Health**

- Dead code: Minimal. Two TODO comments:
  - `hestia/orders/manager.py:438`: "TODO: Integrate with orchestration handler" (order execution is still a stub).
  - `hestia/orders/scheduler.py:272`: Related TODO about orchestration integration.
- No unused imports detected via grep. No `# noqa` suppression markers.
- No bare `except:` clauses anywhere in the codebase.
- Config files: `hestia/config/` contains YAML files (inference.yaml, execution.yaml, memory.yaml, wiki.yaml). Well-organized, no sprawl.
- The `print()` on line 489 of `server.py` is unguarded (not wrapped in `#if DEBUG` -- but this is Python, not Swift, so the convention doesn't apply here).

**LLM/ML Architecture**

- Cloud routing 3-state model (disabled/enabled_smart/enabled_full) is well-designed with `_sync_router_state()` propagation.
- Council dual-path architecture is sound: cloud-active path uses parallel `asyncio.gather()`, cloud-disabled falls back to SLM-only. All council calls wrapped in try/except for graceful degradation.
- Temporal decay: `adjusted = raw_score * e^(-lambda * age_days) * recency_boost`. Per-chunk-type lambda in config. Facts/system never decay. Correct implementation.
- Model router handles 3-state transitions correctly.

**Performance & Scalability**

- Database: Single aiosqlite connection per module. No N+1 query patterns detected. Bulk queries used where appropriate (e.g., `list_recent_executions` in newsfeed aggregation).
- ChromaDB: Single vector store instance. Collection size not bounded -- could grow unbounded over time.
- Concurrent requests: Single-worker uvicorn with async handlers. Global singleton managers are not thread-safe but are fine for single-worker async. Rate limiter uses in-memory dict (not Redis) -- adequate for single-server.
- Newsfeed cache TTL of 30 seconds is reasonable. `asyncio.gather` for parallel aggregation from 4 sources is efficient.

---

## CPO Audit
**Rating:** Acceptable

### Critical Issues

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| Order execution is stub-only | `hestia/orders/manager.py:438` | Orders can be created and scheduled but execution does nothing. Core feature gap. | Wire order execution to orchestration handler. |
| 6 route modules define schemas inline | proactive.py, wiki.py, explorer.py, user_profile.py, health_data.py, newsfeed.py | API documentation inconsistency. Consumers must check multiple locations. | Consolidate into schemas.py or establish explicit per-module pattern. |

### Findings

**API Usability**

- Endpoints follow RESTful conventions consistently. CRUD operations use proper HTTP verbs.
- Response schemas use consistent envelope format with timestamps where appropriate.
- Error responses follow consistent pattern: `{"error": "code", "message": "description"}`.
- Swagger docs available at `/docs`. API contract document maintained at `docs/api-contract.md`.
- Rate limit headers (`X-RateLimit-Remaining`, `X-RateLimit-Reset`) on all responses -- good DX.
- Request ID header (`X-Request-ID`) for debugging correlation -- good DX.

**Feature Completeness**

- All intelligence workstreams (WS1-4) complete and functional.
- Sprint 1 (Invite onboarding), Sprint 2 (Explorer), Sprint 3 (Newsfeed) all complete.
- Three modes (Tia/Mira/Olly) implemented in orchestration layer.
- Order execution remains a TODO -- this is a notable gap for the scheduled prompts feature.
- Voice pipeline (quality check + journal analysis) complete.
- Apple ecosystem tools (Calendar, Reminders, Notes, Mail) complete.
- HealthKit integration complete.

**Documentation Quality**

- `CLAUDE.md`: Comprehensive and mostly accurate. Minor drift in endpoint count (says 118, actual 116).
- Decision log (`docs/hestia-decision-log.md`): Well-maintained with 35 ADRs, latest being ADR-035 (Session Auto-Lock).
- `docs/api-contract.md`: Comprehensive at 2005 lines. Claims 116 endpoints and 20 route modules (matches actual).
- Agent definitions: Test count says "1018 tests, 23 test files" but actual is ~1085 tests, 25 files. Stale.
- Skill definitions: Well-structured with clear instructions.
- Session handoff pattern (`SESSION_HANDOFF.md`) enables continuity -- good practice.

---

## Simplification Opportunities

| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| Schema consolidation | 6 route files define Pydantic models inline, 14 use `schemas.py` | Move all inline schemas to `schemas.py` or establish a `schemas/` directory | Medium | High: single source of truth for API models |
| Auth dependency names | 3 different names: `get_device_token`, `get_current_device`, `verify_device_token` | Standardize on one name (`get_device_token`) everywhere | Low | Medium: reduces cognitive load, prevents the proactive bug |
| Voice route error handling | Uses `type(e).__name__` instead of `sanitize_for_log(e)` | Switch to `sanitize_for_log(e)` like all other routes | Low | Low: consistency improvement |
| Proactive config global | `_config` global in `proactive.py` route file with `get_config()`/`set_config()` | Use FastAPI dependency injection or app state | Low | Low: cleaner pattern |

---

## Consistency Issues

| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| Pydantic schemas in `schemas.py` | All API schemas in `hestia/api/schemas.py` | 6 files define schemas inline | `proactive.py`, `wiki.py`, `explorer.py`, `user_profile.py`, `health_data.py`, `newsfeed.py` |
| Auth dependency: `get_device_token` | Uniform auth dependency name | 3 names used: `get_device_token` (9 files), `get_current_device` (9 files), `verify_device_token` (1 file) | All route files |
| Error logging: `sanitize_for_log(e)` | All routes use `sanitize_for_log(e)` | `voice.py` uses `type(e).__name__` | `hestia/api/routes/voice.py:93,184` |
| Schema naming: `XxxResponse`/`XxxRequest` | Consistent naming convention | Mostly consistent. `DailyNoteResponse` defined in both `schemas.py` and `user_profile.py` (duplicate names, different definitions) | `hestia/api/schemas.py:972`, `hestia/api/routes/user_profile.py:67` |

---

## Documentation Currency

| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Slightly stale | Says "118 endpoints across 20 route modules" -- actual is 116 endpoints, 20 route modules. Says "1086 tests, 25 files" -- needs verification against actual test run. Says "21 modules" which is correct including config. |
| api-contract.md | Current | Claims "116 across 20 route modules" which matches actual. Claims 1085 tests. Last updated 2026-03-01. |
| hestia-decision-log.md | Current | 35 ADRs, most recent ADR-035 (Session Auto-Lock). Well-maintained. |
| Agent definitions | Stale | `hestia-tester.md` says "1018 tests, 23 test files" -- actual is 25 test files and more tests. `hestia-explorer.md` says "1018 pytest tests (23 test files)" -- same staleness. |
| Skill definitions | Current | All skill definitions reference correct patterns and tools. |

---

## Workspace Hygiene

- **Orphaned untracked files**: 14 untracked files. Most are Sprint 3 work-in-progress (newsfeed module, iOS views, macOS models/services). Also `docs/plans/sprint3-newsfeed-audit-2026-03-01.md`. These appear to be active work, not orphans.
- **Stale TODOs**: 2 found:
  - `hestia/orders/manager.py:438` -- "TODO: Integrate with orchestration handler" (known, tracked)
  - `hestia/orders/scheduler.py:272` -- Related TODO about orchestration integration
- **Archive candidates**: None found. `docs/archive/` properly used for session log.
- **Debug artifacts**: None found. No scratch files, temp outputs, or debug prints in source.
- **Staged but not committed**: 36 files staged. These appear to be a large batch of changes (agent updates, skill updates, deployment improvements, newsfeed module, session TTL). Should be committed.

---

## Multi-User Readiness
**Rating:** Close (minor changes needed for most modules, significant for a few)

| Area | Status | Gap |
|------|--------|-----|
| SQLite user scoping (newsfeed) | Ready | `newsfeed_state` table has `user_id` column, all queries filter by it |
| SQLite user scoping (memory) | Not scoped | `memory_chunks`, `sessions`, `staged_memory` have no `user_id` column. All chunks are global. |
| SQLite user scoping (orders) | Not scoped | `orders`, `order_executions` have no `user_id` column |
| SQLite user scoping (tasks) | Not scoped | `background_tasks` has no `user_id` column |
| SQLite user scoping (agents) | Not scoped | `agent_profiles` has no `user_id` column (agents are global -- may be intentional) |
| SQLite user scoping (health) | Not scoped | `health_metrics`, `health_coaching_preferences` have no `user_id` column |
| SQLite user scoping (wiki) | Not applicable | Wiki articles are system-level documentation, not per-user |
| SQLite user scoping (cloud) | Not scoped | `cloud_providers`, `cloud_usage` are global (may be intentional for shared infra) |
| SQLite user scoping (user) | Partially ready | `user_profiles` table uses `DEFAULT_USER_ID = "user-default"`. Single-user assumption baked in. |
| ChromaDB isolation | Not scoped | Single global vector store collection. No per-user collections. |
| API user scoping via JWT | Partial | JWT contains `device_id` but no `user_id`. Routes identify by device, not user. Newsfeed routes hardcode `DEFAULT_USER_ID = "user-default"`. |
| Session isolation | Device-scoped | Sessions have `device_id` column but no `user_id`. Multiple devices can't share session history for same user. |
| Cross-device continuity | Not ready | User preferences tied to `DEFAULT_USER_ID`. Conversation history scoped by session (no cross-device sync). Newsfeed read/dismiss state is user-scoped (ready). |
| Keychain model | Per-device | Keychain is per-machine. Multi-user would need credential partitioning per user. |
| File paths | Hardcoded | `data/`, `logs/` paths are not parameterized per user. User profile files in `data/user/` assume single user. |
| Audit logging | Hardcoded | `audit_logger.py:51` and `structured_logger.py:89` both hardcode `user_id: str = "andrew"`. |

**Summary**: The newsfeed module (newest) was built multi-user-ready from the start. All older modules assume single user. Migrating to multi-user would require: (1) adding `user_id` columns to ~8 tables, (2) adding `user_id` to JWT claims, (3) parameterizing file paths, (4) per-user ChromaDB collections, (5) updating the hardcoded "andrew" references. Estimated effort: ~2 sprints.

---

## Summary

- **CISO:** Acceptable -- Strong credential management and error sanitization. Proactive route auth bug needs fixing. Fail-open revocation is a documented trade-off.
- **CTO:** Strong -- Clean layer boundaries, consistent patterns, full async I/O, comprehensive testing. Schema location split is the main consistency gap.
- **CPO:** Acceptable -- Feature-complete for current roadmap. Order execution stub is a notable gap. Documentation mostly current with minor drift.
- Critical issues: 1 (proactive auth dependency bug)
- Simplification opportunities: 4
- Consistency violations: 4
- Documentation drift: 3 items (CLAUDE.md counts, agent test counts)
- Multi-user readiness: Close (newsfeed ready, all other modules need user_id scoping)
