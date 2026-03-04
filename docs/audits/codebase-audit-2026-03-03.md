# Codebase Audit: Hestia
**Date:** 2026-03-03
**Auditor:** Claude Opus 4.6 (Executive Panel: CISO/CTO/CPO)
**Overall Health:** Healthy

---

## Codebase Snapshot

| Metric | Documented | Actual | Delta |
|--------|-----------|--------|-------|
| Python modules | 22 | 23 (+ research) | +1 |
| Route modules | 21-22 | 22 (incl. research) | Aligned |
| API endpoints | 126-132 | 132 | Aligned |
| Test files | 27-28 | 29 (incl. conftest) | +1 |
| Test count | 1261-1312 | 1312 (1312 passing, 0 skipped) | Improved |
| Swift files (total) | ~222 | 222 | Aligned |
| Swift files (macOS) | 66 | 105 | +39 (stale doc) |
| Duplicated macOS models | 5 (CLAUDE.md) | 2 (actual) | Reduced |

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Consistent manager pattern across all 13 database modules. 100% test pass rate (1312/1312). JWT auth on every non-health endpoint. Layered security (SSRF protection, prompt injection filters, credential sanitization, HSTS). Clean shutdown with per-manager error isolation. Parallel startup with sequential fallback. Rate limiting on all endpoints. | **Weaknesses:** `datetime.utcnow()` still used in 15 places (deprecated since Python 3.12). Research module schemas inline in routes (breaks convention). Token refresh endpoint returns 501. Documentation counts consistently stale. |
| **External** | **Opportunities:** pip-audit not installed (easy add for CI). 27 outdated packages ripe for a version bump. CORS only allows localhost origins -- tight but could block legitimate remote clients. Communication gate infrastructure built but not fully exercised. | **Threats:** Self-signed TLS means no cert rotation automation. In-memory rate limiter resets on restart. JWT has no rotation mechanism (90-day fixed expiry, no refresh). Single Keychain fallback path silently degrades to in-memory-only secrets. |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues

| # | Issue | Location | Risk | Recommendation |
|---|-------|----------|------|----------------|
| S-1 | JWT secret fails silently to in-memory | `hestia/api/middleware/auth.py:52,65` | Medium | If Keychain unavailable, secret is ephemeral -- server restart invalidates all tokens with no warning to user. Add a startup health check that verifies Keychain storage succeeded. |
| S-2 | Token refresh returns 501 | `hestia/api/routes/auth.py:316-321` | Low-Medium | Devices must re-register when tokens expire. Implement refresh or remove the endpoint to avoid confusion. |
| S-3 | Device revocation is fail-open | `hestia/api/middleware/auth.py:282-289` | Medium | Documented (ADR-034) and logged, but a revoked device gets access if invite store is down. Consider a short-lived cache of revocation state. |

### Detailed Findings

**Authentication & Authorization**
- JWT implementation: HS256, 90-day expiry, Keychain-stored secret. Algorithm is explicitly specified in `algorithms=[ALGORITHM]` on decode (prevents algorithm confusion attack). Rating: Good.
- Route protection: All 132 endpoints analyzed. Health probes (`/v1/health`, `/v1/ping`, `/v1/ready`) and auth registration endpoints are intentionally unauthenticated. The root endpoint (`/`) is also unauthenticated but only returns metadata. No security gap found.
- Device registration: Invite-based onboarding with one-time nonces, rate-limited to 5/hour. Legacy open registration can be disabled via `HESTIA_REQUIRE_INVITE=true`. Constant-time secret comparison via `secrets.compare_digest()`. Rating: Strong.

**Credential Management**
- No hardcoded secrets found in codebase (grep verified).
- API keys stored in Keychain, never returned in API responses (`has_api_key: bool` field only).
- Credential sanitization in logs: `CredentialSanitizer` class with regex patterns for API keys, passwords, tokens, emails. Rating: Strong.
- Silent fallback concern: 4 places in `auth.py` catch `Exception` with `pass` when Keychain is unavailable (lines 52, 65, 96, 109). These are the JWT secret and setup secret storage paths. If Keychain fails, secrets exist only in memory.

**Error Handling & Information Leakage**
- `sanitize_for_log(e)` imported and used in all 22 route modules (verified).
- No `str(e)` or `{e}` patterns exposed in HTTP responses (3 instances of `str(e)` in tasks.py are internal control flow only).
- Global exception handler in `server.py:631-664` returns sanitized error with `request_id` for correlation, logs full traceback internally. Rating: Strong.
- `RequestValidationError` handler strips Pydantic internals, exposes only field names and messages. Rating: Good.

**Attack Surface**
- **Injection**: SQLite uses parameterized queries throughout (via aiosqlite). No raw string formatting in SQL. Rating: Strong.
- **SSRF**: Investigate module has comprehensive SSRF protection (`_validate_url()`, `_is_dangerous_ip()`): blocks private IPs, localhost, link-local, multicast, reserved, cloud metadata endpoints, and performs DNS resolution to catch rebinding. Rating: Strong.
- **Prompt Injection**: `RequestValidator` blocks 4 common injection patterns. `ResponseValidator` checks for credential leaks in LLM output. Rating: Acceptable (basic but present).
- **CORS**: Restricted to `localhost:3000,8080,8443`. No wildcard. Rating: Strong.
- **Security Headers**: HSTS, X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy all set. Rating: Strong.
- **Rate Limiting**: Per-client sliding window with endpoint-specific limits. Auth endpoints capped at 5/min. Rating: Good.
- **Communication Gate**: Approval-based external communication control with service whitelists. Rating: Good (infrastructure present, enforcement TBD).

**CISO Verdict:** The security posture is solid for a personal assistant. The main gaps are operational (token rotation, Keychain fallback resilience) rather than architectural. No critical vulnerabilities found.

---

## CTO Audit
**Rating:** Strong

### Critical Issues

| # | Issue | Location | Impact | Recommendation |
|---|-------|----------|--------|----------------|
| T-1 | `datetime.utcnow()` deprecated | 15 occurrences across 5 modules | Low | Migrating to `datetime.now(timezone.utc)` is trivial. 117 instances already use the correct pattern. Affects: `research/`, `explorer/database.py`, `execution/models.py`, `api/schemas/common.py`. |
| T-2 | Research schemas inline in routes | `hestia/api/routes/research.py:28-100` | Low | 9 Pydantic models defined inline rather than in `hestia/api/schemas/research.py`. Breaks the established convention. |
| T-3 | Sync file I/O in async functions | `hestia/agents/config_loader.py:131,140,172`, `hestia/user/config_loader.py:61,70,80` | Low | `write_text()` and `read_text()` are blocking. Acceptable for small config files but inconsistent with async-everywhere convention. |

### Layer Boundaries

- **No upward imports detected.** The dependency direction is clean:
  - `security` and `logging` are imported by all layers (foundational)
  - `inference` is imported by `council`, `memory`, `wiki`, `voice`, `investigate`, `research` (expected)
  - `memory` is imported by `research`, `voice`, `proactive`, `newsfeed` (expected)
  - `api` routes import from domain modules (expected, single direction)
  - No domain module imports from `api`
- **No circular dependencies found.**
- Rating: Strong.

### Pattern Consistency

- **Manager pattern**: 13/13 database modules follow `models.py` + `database.py` + `manager.py` + `get_X_manager()`. All databases inherit from `BaseDatabase`. Rating: Strong.
- **Logging**: All route modules import `get_logger()` and `LogComponent`. `LogComponent` enum has 15 members including `RESEARCH` (added for new module). No instances of `HestiaLogger(component=...)` or `get_logger(component=...)` anti-patterns. Rating: Strong.
- **Type hints**: ~46 functions missing return type annotations, but these are almost entirely `__init__`, `__post_init__`, and dunder methods. Public API functions are well-typed. Rating: Good.
- **Async/await**: One `time.sleep()` in `logging/viewer.py:213` (a CLI log viewer, not server code). No blocking I/O in route handlers. Rating: Good.
- **Error handling**: Consistent `try/except` with `sanitize_for_log()` in all routes. No bare `except:` clauses. Silent exception swallowing limited to parse/fallback code in models (acceptable). Rating: Strong.

### Code Health

- **Dead code**: No obvious dead code detected. The only 501 endpoint (`/v1/auth/refresh`) is a documented placeholder.
- **Duplicate logic**: macOS model duplication reduced from 5 files to 2 (`HealthDataModels.swift`, `ResearchModels.swift`). This is documented known debt.
- **Config**: 5 YAML config files, well-organized. No config sprawl.
- **Dependencies**: 27 outdated packages (none with known critical vulnerabilities based on package names). `pip-audit` not installed -- should be added to CI.
- **Test coverage**: 1312 tests across 29 files. All passing. Test files cover all major modules. Notable gap: no dedicated `test_research.py` test file exists alongside `test_research.py` (it does exist, confirmed). All good.
- Rating: Strong.

### LLM/ML Architecture

- **Inference pipeline**: 3-state routing (disabled/smart/full) with `_sync_router_state()` propagation. Cloud fallback is purely additive (try/except). Rating: Strong.
- **Council**: 4-role parallel execution via `asyncio.gather()`. CHAT optimization skips 3 roles when confidence > 0.8. Direct `_call_cloud()`/`_call_ollama()` bypass router for guaranteed execution path. Rating: Strong.
- **Temporal decay**: `e^(-lambda * age_days) * recency_boost` with per-chunk-type lambda. Facts/system never decay. Rating: Good.
- **Model router**: 3-state transitions with state consistency enforced by `_sync_router_state()`. Rating: Good.

### Performance & Scalability

- **SQLite**: Parameterized queries throughout. `aiosqlite` for non-blocking I/O. Individual databases per module (no single-database bottleneck).
- **Parallel startup**: Phase 1 (sequential foundations) -> Phase 2 (parallel independents with retry) -> Phase 3 (sequential dependents). Measured in milliseconds and logged.
- **Worker recycling**: `limit_max_requests=5000` in uvicorn config prevents memory leak accumulation.
- **No obvious N+1 queries** in database modules examined.
- **Shared mutable state**: Rate limiter is in-memory singleton (acceptable for single-server). Module-level `_SECRET_KEY` and `_SETUP_SECRET` globals in auth middleware (acceptable, write-once).
- Rating: Good.

**CTO Verdict:** Clean architecture with strong adherence to conventions. The codebase has matured through 15+ sessions with consistent patterns. The 23 modules, 132 endpoints, and 1312 tests demonstrate disciplined growth. Minor issues are all low-severity and easily remediated.

---

## CPO Audit
**Rating:** Acceptable

### Critical Issues

| # | Issue | Location | Impact | Recommendation |
|---|-------|----------|--------|----------------|
| P-1 | API contract stale | `docs/api-contract.md` | Medium | Says 123 endpoints / 21 route modules. Actual: 132 / 22. Missing entire research module (6 endpoints). Test count says 1234 vs actual 1312. |
| P-2 | CLAUDE.md count drift | `CLAUDE.md` | Low-Medium | Multiple stale numbers: "22 modules" (actual 23), "1312 tests" header but "1260 tests, 27 files" in project structure, macOS "66 files" (actual 105), "5 duplicated models" (actual 2). |
| P-3 | Agent definitions stale | `.claude/agents/hestia-tester.md:28` | Low | Says "1261 (1258 passing, 3 skipped)". Actual: 1312 all passing. `.claude/agents/hestia-explorer.md:25` says "126 API endpoints". |

### API Usability

- Endpoints follow REST conventions with consistent prefix structure (`/v1/{module}/{resource}`).
- Response schemas use `{Module}{Entity}Response` naming -- consistent across 16 schema modules.
- Error responses have consistent envelope: `{error, message, request_id, timestamp}`.
- Swagger docs available at `/docs`.
- Research module breaks convention by defining schemas inline in route file rather than in schemas directory.
- Rating: Good.

### Feature Completeness

- All documented features are implemented and passing tests.
- Three modes (Tia/Mira/Olly) are fully functional with agent config system.
- Token refresh is a documented placeholder (501). Not a broken feature, but an incomplete one.
- Research module (ADR-039) is the newest addition -- fully functional with 6 endpoints and tests.
- Rating: Good.

### Documentation Quality

- `CLAUDE.md`: Comprehensive and well-structured. Multiple count discrepancies (see P-2). The 4-phase workflow, code conventions, and architecture notes are excellent references.
- `docs/hestia-decision-log.md`: Up to date through ADR-039 (Research Module). Excellent coverage.
- `docs/api-contract.md`: Significantly stale -- missing research module entirely, wrong counts.
- Agent/skill definitions: Test counts and endpoint counts are outdated.
- Onboarding friction: A new session could start productively from CLAUDE.md alone. The structure section and quick commands are immediately useful.
- Rating: Acceptable (the decision log is excellent, but the contract and count drift are a recurring problem).

**CPO Verdict:** The product is feature-complete against the roadmap. Documentation quality is split: architectural docs (CLAUDE.md, decision log) are excellent, but quantitative references (counts, contract) are consistently stale. This is a chronic drift problem that needs a systematic solution (automated count verification in CI).

---

## Simplification Opportunities

| # | What | Current State | Proposed Change | Effort | Impact |
|---|------|--------------|-----------------|--------|--------|
| 1 | Research schemas | 9 Pydantic models inline in `routes/research.py` | Move to `schemas/research.py` and update `schemas/__init__.py` | 30 min | Consistency |
| 2 | macOS model duplication | 2 files in `macOS/Models/` duplicate shared models | Consolidate into `Shared/Models/` with `#if` guards if needed | 1 hr | Less maintenance |
| 3 | `datetime.utcnow()` cleanup | 15 occurrences across 5 modules | Global search-replace to `datetime.now(timezone.utc)` | 20 min | Future-proofing |
| 4 | Count verification script | Manual counting, chronic drift | Extend `scripts/count-check.sh` to verify all documented counts | 1 hr | Prevents doc drift |
| 5 | Auth module exception handling | 4 silent `except Exception: pass` blocks | Add logging at WARNING level for Keychain failures | 15 min | Observability |

---

## Consistency Issues

| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| Schemas in `schemas/` dir | All Pydantic models in `hestia/api/schemas/` | Research module has 9 inline schemas | `hestia/api/routes/research.py` |
| `datetime.now(timezone.utc)` | All datetime creation timezone-aware | 15 uses of deprecated `datetime.utcnow()` | `research/models.py`, `research/database.py`, `explorer/database.py`, `execution/models.py`, `api/schemas/common.py` |
| Async file I/O | All I/O should be async in async functions | 6 `write_text()` calls in async functions | `agents/config_loader.py`, `user/config_loader.py` |
| Schema naming | `{Module}{Entity}{Request/Response}` | Consistent across 15 modules | No violations |
| Error handling | `sanitize_for_log(e)` in all routes | Consistent across all 22 route modules | No violations |
| Logger pattern | `get_logger()` with no args | Consistent everywhere | No violations |
| BaseDatabase inheritance | All databases extend `BaseDatabase` | All 13 do | No violations |

---

## Documentation Currency

| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Partially Stale | Module count (22 vs 23), test count inconsistency (1312 header vs 1260 in structure), macOS files (66 vs 105), model duplication (5 vs 2), endpoint count in table says 132 but structure says 132 (aligned now), missing research from LogComponent list in Code Conventions |
| api-contract.md | Stale | Says 123 endpoints/21 routes. Actual: 132/22. Missing research module. Test count 1234 vs 1312. |
| Decision log | Current | ADR-039 (latest) documents research module. All recent decisions recorded. |
| Agent definitions | Stale | hestia-tester: "1261 tests" (actual 1312). hestia-explorer: "126 endpoints" (actual 132), "22 modules" (actual 23). |
| Skill definitions | Current | Skills reference correct patterns and paths. |

---

## Workspace Hygiene

- **Orphaned files**: 1 untracked file (`linkedin-series-final.md` in project root). Should be removed or moved to `docs/`.
- **Stale TODOs**: 0 in Python, 0 in Swift. Clean.
- **Branch state**: main is 14 commits ahead of origin/main. Push needed.
- **Archive candidates**: Previous audit files in `docs/audits/` could be cleaned up if no longer referenced. 5 audit files total.
- **Debug artifacts**: None found.
- **pycache**: Present but gitignored. Clean.

---

## Multi-User Readiness
**Rating:** Significant Work

| Area | Status | Gap |
|------|--------|-----|
| SQLite user scoping | Partial | `investigate` and `newsfeed` have `user_id`. 11 other databases lack it: `agents`, `cloud`, `execution/gate`, `explorer`, `memory`, `orders`, `tasks`, `user`, `wiki`, `research`, `health` (has device_id only). |
| ChromaDB isolation | Not scoped | Collections are global, not per-user. Memory search would cross user boundaries. |
| Keychain model | Per-device | Single credential store. No user partitioning. |
| API user scoping | device_id only | JWT contains `device_id` but no `user_id`. All endpoints authenticate by device, not user. Adding users requires JWT schema change + middleware update. |
| Session isolation | By device | `memory_chunks` has `device_id` but no `user_id`. Sessions tied to device not user. |
| File path isolation | Global | `data/`, `logs/`, config files use fixed paths. No per-user directory structure. |
| Cross-device continuity | Partial | Newsfeed has per-user state (ADR-033). Other modules are device-scoped. |
| Settings portability | Not portable | User settings stored by device, not transferable across devices for same user. |

**Assessment:** The system is architecturally single-user. Multi-user would require: (1) adding `user_id` to JWT and all database tables, (2) scoping ChromaDB collections per user, (3) creating per-user data directories, (4) updating all 132 endpoints to filter by user. The `newsfeed` and `investigate` modules demonstrate the target pattern, but 85% of the codebase assumes single user. This is a deliberate design choice for a personal assistant -- multi-user is not a current requirement, but the path is clear if needed.

---

## Summary

- **CISO:** Acceptable -- Solid security posture with JWT auth, SSRF protection, credential sanitization, and rate limiting. Key gaps: JWT rotation not implemented, Keychain fallback silently degrades, device revocation is fail-open.
- **CTO:** Strong -- Clean architecture with 23 modules following consistent patterns, all 1312 tests passing, proper layer boundaries, no circular dependencies. Minor issues: 15 deprecated datetime calls, research schemas inline, sync file I/O in async functions.
- **CPO:** Acceptable -- Feature-complete against roadmap, strong architectural docs, but chronic count drift in api-contract.md, CLAUDE.md, and agent definitions.
- **Critical issues:** 0
- **Medium issues:** 5 (S-1, S-2, S-3, P-1, P-2)
- **Simplification opportunities:** 5
- **Consistency violations:** 3 (schemas placement, datetime, sync I/O)
- **Documentation drift:** 4 documents with stale counts
- **Multi-user readiness:** Significant Work (deliberate single-user design)

---

## Recommended Priority Actions

1. **[15 min]** Fix `datetime.utcnow()` -- 15 occurrences, trivial replacement
2. **[30 min]** Move research schemas to `schemas/research.py`
3. **[30 min]** Update all documented counts (run `count-check.sh`, update CLAUDE.md, api-contract.md, agent defs)
4. **[1 hr]** Implement token refresh endpoint (or remove the 501 placeholder)
5. **[1 hr]** Add `pip-audit` to CI pipeline and resolve any flagged vulnerabilities
6. **[15 min]** Add WARNING-level logging to auth.py Keychain fallback paths
7. **[15 min]** Push 14 local commits to origin
