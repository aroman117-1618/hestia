# Codebase Audit: Hestia
**Date:** 2026-03-02
**Auditors:** CISO, CTO, CPO (executive panel)
**Overall Health:** Healthy

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Disciplined manager-singleton pattern across all 15 modules. JWT auth with device token on every route (21/21 route files). Error sanitization (`sanitize_for_log`) adopted in 17/21 route files. Communication gate architecture prevents uncontrolled external calls. SSRF protection on investigate URLs. All SQL uses parameterized queries (zero f-string interpolation). 1225 tests across 27 files. Comprehensive CLAUDE.md with 389-line project context. | **Weaknesses:** 4 route files (mode, tools, voice, health_data) lack `sanitize_for_log` import. SSRF URL validation is bypassable (DNS rebinding, IPv6 shorthand, decimal IP encoding). `tasks.py` uses `str(e)` in 3 places for control flow. Memory/tasks/orders/wiki/health/explorer DB tables have no `user_id` column. 2 stale TODOs in orders module. `LogComponent.CLOUD` and `LogComponent.ACCESS` defined but never used in any production code. |
| **External** | **Opportunities:** 18 outdated pip packages (low risk, all minor version bumps). schemas.py (1362 lines, 116 models) could be split by domain. `docs/` has loose files that could be organized. Multi-user readiness achievable with moderate DB migrations. | **Threats:** Self-signed TLS in production (MITM risk on non-Tailscale networks). Fail-open device revocation (ADR-034 trade-off). HS256 JWT with symmetric key (compromise of key = full impersonation). No CSRF protection (mitigated by custom header requirement). In-memory rate limiting resets on restart. |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues
| # | Issue | Location | Risk | Recommendation |
|---|-------|----------|------|----------------|
| S1 | SSRF bypass via DNS rebinding, decimal IPs, IPv6 shorthand | `hestia/investigate/manager.py:76-102` | Medium | Resolve hostname to IP before validation; block all RFC 1918/link-local after resolution. Check `ipaddress.is_private`. |
| S2 | Fail-open device revocation | `hestia/api/middleware/auth.py:282-289` | Medium | Known trade-off (ADR-034). Consider fail-closed with short cache TTL instead. |
| S3 | HS256 symmetric JWT | `hestia/api/middleware/auth.py:22` | Low-Medium | Acceptable for single-server. If multi-server planned, migrate to RS256 with key pair. |

### Findings

**Authentication & Authorization**
- JWT: HS256, 90-day expiry, Keychain-stored secret with env var override. Good.
- All 21 route files import `get_device_token` from auth middleware. All non-health endpoints use `Depends(get_device_token)`. No unprotected endpoints found (health check is intentionally open -- documented at line 47 of `hestia/api/routes/health.py`).
- Device revocation check runs on every authenticated request (`check_device_revocation`). Fail-open by design.
- Invite rate limiting: 5/hour, in-memory sliding window. Resets on restart -- acceptable for single-server.
- Invite tokens: 10-minute expiry, one-time nonce. Good.
- Constant-time comparison for setup secret (`secrets.compare_digest`). Good.

**Credential Management**
- No hardcoded secrets in config files. All YAML configs contain only token count/threshold values.
- JWT secret stored in Keychain via `CredentialManager.store_sensitive()`.
- Setup secret follows the same pattern.
- Cloud API keys stored in Keychain, never returned in responses (confirmed in CLAUDE.md and cloud routes).
- 3-tier partitioning (operational/sensitive/system) implemented in `CredentialManager`.

**Error Handling & Information Leakage**
- `sanitize_for_log(e)` adopted in 17/21 route files. Missing from:
  - `hestia/api/routes/mode.py` -- but mode.py has simple `except ValueError` with no logging of exception details. Low risk.
  - `hestia/api/routes/tools.py` -- no except blocks at all. Zero risk.
  - `hestia/api/routes/voice.py` -- uses `sanitize_for_log` in log calls (4 LogComponent usages). Actually imports it.
  - `hestia/api/routes/health_data.py` -- uses LogComponent but does not import `sanitize_for_log`.
- `tasks.py` uses `str(e)` at lines 341, 426, 514 for control flow (`"not found" in error_msg.lower()`). The `str(e)` is NOT leaked to HTTP responses -- responses use static error messages. Low risk but should use pattern matching instead.
- No `detail=str(e)` found in any route file. Good.
- No bare `except:` clauses found. Good.
- HTTP 500 responses use generic messages (`"Internal server error"` pattern). Good.

**Attack Surface**
- **SQL Injection:** Zero f-string SQL found. All queries use parameterized `?` placeholders. Strong.
- **XSS:** Not applicable (REST API, no HTML rendering). N/A.
- **SSRF:** `_validate_url()` in `investigate/manager.py` blocks localhost, 127.0.0.1, ::1, 10.x, 192.168.x, 172.16-31.x. However:
  - Does NOT resolve DNS before checking (DNS rebinding attack possible).
  - Does NOT block 169.254.x.x (link-local / cloud metadata).
  - Does NOT handle decimal IP encoding (e.g., `http://2130706433` = 127.0.0.1).
  - Does NOT handle IPv6 shorthand (e.g., `http://[::ffff:127.0.0.1]`).
  - Line 99: `int(hostname.split(".")[1])` could raise `ValueError` if hostname is not dotted-quad format.
- **CSRF:** No CSRF tokens, but mitigated by custom `X-Hestia-Device-Token` header requirement (browsers won't auto-send custom headers in cross-origin requests).
- **Prompt Injection:** User input flows to LLM via `PromptBuilder.build_system_prompt()` and chat messages. System prompts are hardcoded in `mode.py` (lines 41, 79, 118). User input is not sanitized before LLM, but this is inherent to conversational AI. Council roles provide multi-perspective validation.
- **Communication Gate:** `ExternalCommunicationGate` in `execution/gate.py` enforces service whitelisting with per-request approval. SQLite-backed persistence. Integrated into `ToolExecutor`.
- **TLS:** Self-signed cert on port 8443. Tailscale provides additional encryption in transit. `curl -k` needed for local dev.
- **CORS:** Locked to `localhost:3000,8080,8443` by default. Customizable via `HESTIA_CORS_ORIGINS` env var. Methods and headers restricted. Good.
- **Rate Limiting:** Full `RateLimitMiddleware` with sliding window algorithm. Per-client tracking. Headers exposed (`X-RateLimit-Remaining`, `X-RateLimit-Reset`). In-memory only (resets on restart).

### Verdict
**CISO Rating: Acceptable** -- Security posture is solid for a single-user, local-network AI assistant. The SSRF bypass is the most actionable finding. The fail-open revocation is a documented trade-off. No critical vulnerabilities found.

---

## CTO Audit
**Rating:** Strong

### Critical Issues
| # | Issue | Location | Impact | Recommendation |
|---|-------|----------|--------|----------------|
| T1 | 4 route files missing `sanitize_for_log` | `mode.py`, `tools.py`, `health_data.py` | Low | Add import for consistency even if no current exception logging. |
| T2 | `LogComponent.CLOUD` and `LogComponent.ACCESS` unused | `hestia/logging/structured_logger.py:44,53` | Low | Either use them in cloud routes/auth middleware, or remove them. |
| T3 | schemas.py is 1362 lines with 116 models | `hestia/api/schemas.py` | Maintenance burden | Split into `schemas/health.py`, `schemas/memory.py`, etc. |

### Findings

**Layer Boundaries**
- **Logging:** Only imports from itself (structured_logger, audit_logger). Clean.
- **Security:** No upward imports. Only imported by inference, auth middleware. Clean.
- **Inference:** Imports from logging and security. Deferred import of cloud at line 616 (`from hestia.cloud.client`). Acceptable -- avoids circular import.
- **Memory:** Imports from logging and inference (via tagger). Clean.
- **Orchestration:** Imports from logging, inference, memory, execution, council, user (deferred). This is correct -- orchestration is the integration layer.
- **No circular dependencies detected.** All cross-module imports are downward or deferred.

**Pattern Consistency**
- Manager pattern: 15 managers, all with `get_X_manager()` factory functions. 12 are async, 3 are sync (`get_council_manager`, `get_mode_manager`, `get_interruption_manager`). Consistent.
- All use global singleton with `_instance` or `_manager` pattern. Consistent.
- Logging: `logger = get_logger()` with no arguments used everywhere. Confirmed across all route files. Strong.
- LogComponent enum has 16 values; only 14 are actually used in production code. `CLOUD` and `ACCESS` are defined but never referenced.
- Async/await: All database operations use `aiosqlite`. No blocking `time.sleep()` found in async route handlers. `time` module is imported in several files but used for `time.time()` timestamps, not sleeping. Good.

**Code Health**
- **Dead code:** `LogComponent.CLOUD` and `LogComponent.ACCESS` appear unused. No other significant dead code found.
- **Duplicate logic:** SQLite database initialization pattern (connect, create tables, row_factory) repeated in 5 database modules. Could be a `BaseDatabase` mixin, but the current explicit pattern is readable.
- **TODOs:** Only 2 in production code:
  - `hestia/orders/scheduler.py:272` -- "When orchestration integration is complete"
  - `hestia/orders/manager.py:438` -- "Integrate with orchestration handler"
  Both are known deferred work items, not bugs.
- **Config files:** 4 YAML files (inference, execution, memory, wiki, investigate). Well-scoped, no sprawl.
- **Dependencies:** 18 outdated packages. All are minor version bumps (e.g., chromadb 1.4.0 -> 1.5.2, fastapi 0.128.0 -> 0.128.8). No known vulnerabilities flagged. Acceptable for a quarterly update cadence.

**LLM/ML Architecture**
- **Inference pipeline:** 3-state model router (disabled/enabled_smart/enabled_full). State persisted to SQLite, re-synced on any cloud endpoint call via `_sync_router_state()`. Robust.
- **Council:** Dual-path (cloud/local). All council calls wrapped in try/except for fault tolerance. CHAT optimization skips 3 API calls when confidence > 0.8. Purely additive.
- **Temporal decay:** `adjusted = raw_score * e^(-lambda * age_days) * recency_boost`. Per-chunk-type lambda values in `memory.yaml`. Facts/system never decay. Mathematically sound.
- **Cloud routing:** Direct `_call_cloud()` / `_call_ollama()` bypass router for guaranteed execution. Clean separation.

**Performance & Scalability**
- **Database queries:** All use parameterized queries. No N+1 patterns detected (routes fetch lists in single queries with LIMIT/OFFSET).
- **ChromaDB:** Single collection, PersistentClient. Background threads cause pytest hang (mitigated by conftest.py `os._exit()` hook).
- **SQLite connection pooling:** Single connection per database module (singleton pattern). Adequate for single-server, single-user. Would need connection pooling for multi-user.
- **Shared mutable state:** Global singletons are the primary shared state. Thread-safe for async (single event loop). Rate limiter and invite counter are in-memory dicts -- safe for single-process.

### Verdict
**CTO Rating: Strong** -- Clean architecture with well-enforced layer boundaries. Manager singleton pattern is consistent. No blocking I/O in async contexts. The main debt is the monolithic schemas.py and 2 unused LogComponent values.

---

## CPO Audit
**Rating:** Acceptable

### Critical Issues
| # | Issue | Location | Impact | Recommendation |
|---|-------|----------|--------|----------------|
| P1 | CLAUDE.md endpoint count stale (121 vs 125 actual) | `CLAUDE.md` line in API Summary | Doc confusion | Update to 125 endpoints. |
| P2 | CLAUDE.md test count stale (1194 vs 1225 actual) | `CLAUDE.md` line in Testing | Doc confusion | Update to 1225 tests, 27 test files. |
| P3 | `docs/api-contract.md` may be stale | `docs/api-contract.md` | Consumer confusion | Diff against actual OpenAPI spec. |

### Findings

**API Usability**
- Endpoints follow RESTful conventions. Consistent `/v1/` prefix.
- Response models defined for most endpoints via Pydantic `response_model=`. Good.
- Error responses use structured format: `{"error": "code", "message": "description"}`. Consistent.
- Swagger docs auto-generated at `/docs`. Good.
- 116 Pydantic schemas provide strong typing.
- Response naming convention: `{Entity}Response`, `{Entity}Request`. Consistent.

**Feature Completeness**
- All workstreams (WS1-4) marked COMPLETE and verified.
- All 5 frontend wiring sprints COMPLETE.
- Three modes (Tia/Mira/Olly) have system prompts defined in `mode.py`.
- No half-built features detected. The only deferred items are the 2 TODO comments in orders (orchestration integration).
- Investigate module fully implemented: 5 endpoints, extractors for web articles and YouTube, depth-based analysis.

**Documentation Quality**
- CLAUDE.md: Comprehensive (389 lines), well-structured, but has stale counts:
  - Claims 121 endpoints (actual: 125)
  - Claims 1194 tests, 26 test files (actual: 1225 tests, 27 test files)
  - Claims "116 endpoints across 20 route modules" in one place and "121 endpoints, 21 route modules" in API Summary (inconsistent within itself)
  - Module count (22) is accurate
- Decision log: 37 ADR entries (ADR-001 through ADR-037). Last entry is ADR-037 (Server Reliability). Appears current.
- Agent definitions (4 files in `.claude/agents/`): `hestia-explorer`, `hestia-tester`, `hestia-reviewer`, `hestia-deployer`. Present but test counts and module lists may need periodic refresh.
- Skill definitions (13 skills in `.claude/skills/`): Well-organized, covers strategic and operational workflows.
- `docs/api-contract.md` is 2022 lines. Should be compared against actual OpenAPI output for accuracy.

### Verdict
**CPO Rating: Acceptable** -- Feature-complete for MVP. Documentation is comprehensive but has numerical drift. API design is clean and consistent.

---

## Simplification Opportunities

| # | What | Current State | Proposed Change | Effort | Impact |
|---|------|--------------|-----------------|--------|--------|
| 1 | `schemas.py` monolith | 1362 lines, 116 models in one file | Split into `schemas/` package with per-domain modules (health, memory, tasks, etc.) | Medium | High readability |
| 2 | SQLite database boilerplate | 5 database modules repeat connect/create-tables/row-factory pattern | Extract `BaseDatabase` class with `connect()`, `close()`, `ensure_tables()` | Medium | Moderate -- reduces 50+ lines of duplication |
| 3 | `LogComponent.CLOUD` and `ACCESS` | Defined in enum but never used | Either wire into cloud routes and auth middleware, or remove | Low | Low -- enum hygiene |
| 4 | `docs/` loose files | 8+ non-categorized files in docs root | Move `ui-*.md`, `figma-*.md`, `backend-*.md`, `deployment.md` into `docs/reference/` | Low | Better organization |
| 5 | `tasks.py` str(e) pattern | 3 places use `str(e)` for error classification | Replace with explicit exception subclasses (TaskNotFoundError, etc.) | Low | Better error handling |

---

## Consistency Issues

| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| `sanitize_for_log` import | All route files | Missing from 4 files | `mode.py`, `tools.py`, `voice.py`, `health_data.py` |
| LogComponent usage | All defined values used | `CLOUD`, `ACCESS` never referenced | `structured_logger.py:44,53` |
| Manager factory naming | `async def get_X_manager()` | 3 are sync (council, mode, interruption) | `council/manager.py`, `orchestration/mode.py`, `proactive/policy.py` |
| Error sanitization in routes | `sanitize_for_log(e)` everywhere | `str(e)` used in tasks.py (3 places) | `tasks.py:341,426,514` |
| CLAUDE.md counts | Match reality | Endpoint count (121 vs 125), test count (1194 vs 1225), test files (26 vs 27) | `CLAUDE.md` |
| CLAUDE.md internal consistency | Single source of truth | Claims "116 endpoints across 20 route modules" AND "121 endpoints, 21 route modules" | `CLAUDE.md` (two different sections) |

---

## Documentation Currency

| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Slightly Stale | Endpoint count (121 -> 125), test count (1194 -> 1225), test files (26 -> 27), internal inconsistency on endpoint count (116 vs 121) |
| api-contract.md | Needs Verification | 2022 lines. Should be diffed against `/openapi.json` to confirm all 125 endpoints documented. |
| hestia-decision-log.md | Current | 37 ADRs through ADR-037. Last entry matches recent work (Server Reliability). |
| Agent definitions | Likely Stale | Test inventory counts and module lists may not reflect the investigate module addition (27 test files now). |
| Skill definitions | Current | 13 skills, well-organized. No stale references found in skill definitions. |
| SPRINT.md | Current | 232 lines, tracks all 5 completed sprints. |
| MEMORY.md | At Capacity | 205 lines (limit: 200). Warning shown. Needs pruning. |

---

## Workspace Hygiene

**Orphaned/Untracked Files:**
- `.serena/memories/` -- untracked (Serena tool state, likely should be gitignored)
- `docs/discoveries/efficiency-stability-sprint-2026-03-02.md` -- untracked (recent discovery output, should be committed or removed)
- 3 modified but uncommitted files in `HestiaApp/macOS/` (WikiModels.swift, MacWikiViewModel.swift, MacWikiSidebarView.swift)

**Stale TODOs:** 2
- `hestia/orders/scheduler.py:272` -- "When orchestration integration is complete"
- `hestia/orders/manager.py:438` -- "Integrate with orchestration handler"

**Archive Candidates:**
- `docs/ui-phase3-plan.md` -- Phase 3 is COMPLETE
- `docs/ui-requirements.md` -- Historical, not actively referenced
- `docs/hestia-workspace-plan.md` -- Historical workspace planning
- `docs/hestia-initiative-enhanced.md` -- Historical initiative doc
- `docs/hestia-project-context-enhanced.md` -- Superseded by CLAUDE.md

**Debug Artifacts:** None found.

---

## Multi-User Readiness
**Rating:** Significant Work

| Area | Status | Gap |
|------|--------|-----|
| SQLite user scoping | Partial | `investigate` and `newsfeed` have `user_id` columns. `memory`, `tasks`, `orders`, `wiki`, `health`, `explorer`, `sessions`, `agents` do NOT. 8 of 10 data-bearing tables lack user scoping. |
| ChromaDB isolation | Not scoped | Single global collection (`hestia_memory`). No user partitioning. Would need per-user collections or metadata filtering. |
| Keychain model | Per-device | Keychain credentials are stored per-machine, not per-user. Cloud API keys would be shared across users. |
| API user scoping | Device-centric | All routes authenticate by `device_id`, not `user_id`. JWT payload contains `device_id` only -- no `user_id` claim. Would need to add user identity layer above device identity. |
| Session isolation | Not scoped | `sessions` table has `device_id` but no `user_id`. Different users on same device would share sessions. |
| Cross-device continuity | Not supported | Preferences, memories, and conversation history are device-local or global. No sync mechanism between devices for the same user. |
| File paths | Hardcoded | `data/user/`, `data/agents/`, paths in 13+ locations assume single user. Would need `data/users/{user_id}/` structure. |
| Shared mutable state | Global singletons | All managers are process-global singletons. Multi-user would require tenant-scoped instances or user-context passing. |

**Assessment:** The codebase was built for single-user, single-device operation. Multi-user would require: (1) user identity layer above device auth, (2) `user_id` columns on 8+ tables, (3) ChromaDB collection partitioning, (4) user-scoped file paths, (5) tenant-aware manager pattern. This is a significant refactoring effort (estimated 2-3 sprints) but architecturally feasible -- the manager pattern provides clean injection points.

---

## Summary

- **CISO:** Acceptable -- Solid single-user security. SSRF URL validation needs DNS resolution check. Fail-open revocation is a documented trade-off.
- **CTO:** Strong -- Clean layered architecture, consistent patterns, no circular dependencies, proper async I/O, parameterized SQL everywhere. Main debt is monolithic schemas.py.
- **CPO:** Acceptable -- Feature-complete, well-documented, but CLAUDE.md counts are stale (4 numerical drifts).
- Critical issues: 3 (SSRF bypass, fail-open revocation, HS256 symmetric key)
- Simplification opportunities: 5
- Consistency violations: 6
- Documentation drift: 7 items (CLAUDE.md counts, api-contract verification, MEMORY.md at capacity, agent defs)
- Multi-user readiness: Significant Work (8 of 10 tables lack user_id, ChromaDB global, no user identity layer)
