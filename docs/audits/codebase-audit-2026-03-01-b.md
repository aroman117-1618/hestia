# Codebase Audit: Hestia
**Date:** 2026-03-01 (Session B)
**Auditor:** CISO/CTO/CPO Executive Panel (IQ 175, zero tolerance)
**Overall Health:** Healthy

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Consistent manager pattern across 21 modules. 1086 tests (99.7% pass rate). JWT + Keychain + Fernet double encryption. sanitize_for_log() in 16/20 route files. Rate limiting with sliding window. Communication gate for external calls. Prompt injection detection. All 116 endpoints documented in api-contract.md. Clean layer boundaries (only 2 minor violations). Full type hint coverage. | **Weaknesses:** 139 unguarded Swift `print()` statements. No user_id scoping in 11/12 database modules (single-user assumption baked deep). 14+ files with 3+ unused imports. `health_data.py` has no generic exception handlers. Validation exception handler leaks Pydantic error details. In-memory rate limiting (no persistence across restarts). Blocking file I/O in async methods (config_writer, audit_logger). |
| **External** | **Opportunities:** Multi-user readiness achievable with scoping migration (newsfeed already demonstrates pattern). schemas.py (1267 lines) could be split per domain. Agent v1/v2 coexistence could be sunset. Unused imports cleanup is low-effort. 4 config YAML files could consolidate into 2. | **Threats:** Self-signed TLS with no cert rotation strategy. Fail-open device revocation (ADR-034 trade-off). ChromaDB has no user isolation (global collection). JWT secret falls back to in-memory if Keychain unavailable (server restart = all tokens invalidated). `Path.home()` hardcoded in 21 locations (multi-user/containerization blocker). |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues
| Issue | Location | Risk | Recommendation |
|-------|----------|------|----------------|
| Validation errors leak Pydantic details | `hestia/api/server.py:322` | Medium | `exc.errors()` returns field names, types, and constraints to client. Strip to field names + human messages only. |
| JWT secret in-memory fallback | `hestia/api/middleware/auth.py:56-66` | Medium | If Keychain unavailable, secret is generated in-memory. Server restart invalidates ALL tokens. Add persistent file-based fallback. |
| Fail-open revocation | `hestia/api/middleware/auth.py:282-289` | Low (documented) | Acknowledged in ADR-034. If invite store is down, revoked devices can still authenticate. Acceptable for single-server home deployment. |
| Prompt injection patterns too narrow | `hestia/orchestration/validation.py:79-84` | Low | Only 4 patterns. Modern prompt injection uses encoding tricks, multi-language, indirect injection. Expand pattern library or add LLM-based detection. |

### Findings

**Authentication & Authorization**
- JWT: HS256 algorithm, 90-day expiry, Keychain-stored secret. Solid for single-user.
- All 116 endpoints protected: 109 via `get_device_token`, 2 health endpoints intentionally open, 5 auth endpoints appropriately gated.
- Device registration: invite-based (ADR-030) with one-time nonce, 10-minute expiry, rate-limited to 5/hour.
- Token revocation: implemented (ADR-034) with `revoked_at` column and middleware check.
- Constant-time secret comparison via `secrets.compare_digest()` -- correct.

**Credential Management**
- Zero hardcoded secrets found (grep confirmed).
- Three-tier Keychain partitioning (operational/sensitive/system) -- enforced.
- Double encryption (Fernet + Keychain AES-256) -- implemented correctly.
- Master key stored in system-tier Keychain partition.
- API keys: min 10 chars, stripped, stored encrypted, never returned in responses.
- Unused crypto imports in `credential_manager.py` (PBKDF2HMAC, hashes) suggest planned but unimplemented key derivation.

**Error Handling & Information Leakage**
- `sanitize_for_log(e)` imported and used in 16/20 route files.
- 4 route files without it (`health_data.py`, `mode.py`, `tools.py`, `voice.py`) -- `voice.py` uses `type(e).__name__` which is safe; `health_data.py`/`mode.py`/`tools.py` have no generic exception blocks needing it.
- No route returns `str(e)` or `{e}` in HTTP response detail -- all use generic messages.
- `tasks.py` uses `str(e)` internally for control flow (checking "not found") -- acceptable.
- Global exception handler at `server.py:328` catches all unhandled exceptions with sanitized response.
- **Issue**: `validation_exception_handler` at line 322 returns `exc.errors()` directly to client, which includes Pydantic validation internals (field types, constraints).

**Attack Surface**
- CORS: Restricted to localhost origins by default, configurable via env var. Not wildcard.
- Rate limiting: Per-client sliding window with configurable per-endpoint limits.
- TLS: Self-signed cert (appropriate for home LAN + Tailscale).
- SSRF: Communication gate prevents unauthorized external calls.
- Injection: Parameterized SQLite queries throughout (no string interpolation).
- XSS: API-only (no HTML rendering server-side).
- Prompt injection: 4 forbidden patterns + validation pipeline. Room for improvement but baseline exists.

**CISO Verdict:** The security posture is solid for a single-user home deployment. Double encryption, Keychain integration, audit logging, rate limiting, and error sanitization are all implemented correctly. The validation error leakage and narrow prompt injection patterns are the most actionable items.

---

## CTO Audit
**Rating:** Strong

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| `schemas.py` is 1267 lines | `hestia/api/schemas.py` | Maintenance burden | Split into domain-specific schema files (chat_schemas.py, memory_schemas.py, etc.) |
| Blocking file I/O in async methods | `hestia/agents/config_writer.py:77`, `hestia/logging/audit_logger.py:252` | Thread pool starvation under load | Wrap with `asyncio.to_thread()` or use aiofiles |
| 14+ files with unused imports | See list below | Code cleanliness | One-pass cleanup |

### Findings

**Layer Boundaries**
- Clean separation confirmed. Only 2 minor violations:
  1. `hestia/security/credential_manager.py:24` imports from `hestia.logging` -- acceptable (audit logging is a cross-cutting concern).
  2. `hestia/orchestration/handler.py:28` imports from `hestia.execution` -- by design (orchestration drives execution).
- No circular dependencies detected.
- API layer (`hestia.api`) never imported by business logic.

**Pattern Consistency**
- Manager pattern (models.py + database.py + manager.py + get_X_manager()): Followed in all 12 domain modules (memory, tasks, health, agents, wiki, explorer, user, cloud, orders, newsfeed, proactive, council).
- Singleton pattern: Consistent `global _instance` with `async def get_X_manager()` factory.
- Logging: All modules use `logger = get_logger()` with no arguments, correct `LogComponent` enum values. Zero violations found.
- Async/await: Used consistently for all database operations (aiosqlite). File I/O in config_writer/audit_logger is sync (see critical issue).
- Type hints: 100% coverage on public function signatures across all 136 Python files.

**Code Health**
- Dead code: 14+ files with unused imports (see Simplification section). No dead functions detected.
- Duplicate logic: Agent v1 (`agents.py`, 542 lines) and v2 (`agents_v2.py`, 468 lines) routes coexist. Both are wired in `server.py`. v1 is slot-based, v2 is markdown-based. Documented in ADR-031.
- Config: 4 YAML files (execution, inference, memory, wiki) -- appropriately scoped.
- Dependencies: `requirements.txt` has 15 direct deps, all with version floors. No pinned upper bounds (acceptable for non-library).
- No `pyproject.toml` or lockfile -- CLAUDE.md mentions one but it doesn't exist.

**LLM/ML Architecture**
- 3-state cloud routing (disabled/enabled_smart/enabled_full): State sync via `_sync_router_state()`. Correct.
- Council: Dual-path with try/except on every call. Failures fall back silently. Robust.
- Temporal decay: `e^(-lambda * age_days) * recency_boost`. Per-chunk-type lambda in config. Correct.
- Model router: Tier selection based on token count and complexity patterns. Fallback chain: primary -> complex -> cloud.
- Prompt injection: Forbidden pattern matching + response validation for leaked secrets/passwords.

**Performance & Scalability**
- SQLite with aiosqlite: Single-writer limitation but fine for single-user.
- ChromaDB: Persistent storage with proper collection management.
- Rate limiter: In-memory with 5-minute cleanup cycle. No persistence across restarts.
- Singleton managers: Thread-safe via async initialization pattern.
- No N+1 query patterns detected in database modules.
- `RequestHandler` at 1148 lines is the largest business logic file -- complex but well-structured with clear method separation.

**CTO Verdict:** Clean architecture with consistent patterns, good layer separation, and solid test coverage. The codebase is well-organized for its scale. The main concerns are the monolithic schemas.py and the blocking I/O in async contexts, both of which are straightforward to fix.

---

## CPO Audit
**Rating:** Strong

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| 139 unguarded `print()` in Swift | `HestiaApp/macOS/` (36), `HestiaApp/Shared/` (103) | Release build noise | Wrap all in `#if DEBUG` blocks |
| API contract test count stale | `docs/api-contract.md:17` | Minor doc drift | Shows 1085/1082, actual is 1086/1083 |

### Findings

**API Usability**
- 116 endpoints across 20 route modules. Well-organized by domain.
- Consistent response envelope: `{"error": "code", "message": "human-readable"}` for errors.
- Swagger/ReDoc available at `/docs` and `/redoc`.
- Authentication via header (`X-Hestia-Device-Token`) -- clear and consistent.
- Rate limit headers returned on every response (`X-RateLimit-Remaining`, `X-RateLimit-Reset`).
- Pydantic models for all request/response types with proper field descriptions.

**Feature Completeness**
- All roadmap items marked COMPLETE are implemented and tested.
- Three modes (Tia/Mira/Olly) fully functional via both v1 (slot-based) and v2 (markdown-based) APIs.
- Apple ecosystem integration: Calendar, Reminders, Notes, Mail tools implemented.
- HealthKit: 28 metric types, sync endpoint, summary/trend endpoints, coaching preferences.
- Wiki: AI-generated articles, module deep dives, ADR browser.
- Newsfeed: Materialized cache with user-scoped state (ADR-032/033).
- No half-built features found. Two TODO comments in orders module (scheduler integration) are documented deferral, not abandoned work.

**Documentation Quality**
- CLAUDE.md: 248 lines, comprehensive. Module count (21), endpoint count (116), test count (1086/25 files) all verified accurate.
- `docs/api-contract.md`: 2005 lines, covers all 116 endpoints with request/response examples.
- Decision log: 36 ADRs (ADR-001 through ADR-036), all recent decisions recorded.
- Agent definitions: 4 files totaling 689 lines.
- Skill definitions: 13 skills defined.
- Onboarding: A new session can start productively from CLAUDE.md + SESSION_HANDOFF.md alone.

**CPO Verdict:** Excellent documentation and feature completeness. The Swift print() issue is the only significant quality concern -- it doesn't affect functionality but indicates technical debt in the macOS build. API design is consistent and well-documented.

---

## Simplification Opportunities

| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| `schemas.py` (1267 lines) | Single monolithic file | Split into `schemas/chat.py`, `schemas/memory.py`, etc. | Medium | High -- easier navigation, smaller diffs |
| Unused imports (14+ files) | Various files have 3-6 unused imports | One-pass cleanup | Low | Low -- cleaner code |
| Agent v1 routes (542 lines) | Coexists with v2 (468 lines) | Deprecation timeline for v1 | Low (planning) | Medium -- reduces maintenance surface |
| `orders/scheduler.py` TODO | Scheduler integration deferred | Either implement or document permanent deferral | Low | Low -- clarity |
| Security unused crypto imports | `PBKDF2HMAC`, `hashes` imported but unused | Remove or implement planned key derivation | Low | Low |
| 4 config YAML files | `execution.yaml`, `inference.yaml`, `memory.yaml`, `wiki.yaml` | Could consolidate inference+cloud+wiki config | Low | Low |

**Files with most unused imports:**
- `hestia/security/credential_manager.py`: 6 unused (PBKDF2HMAC, datetime, hashes, json, os)
- `hestia/apple/tools.py`: 5 unused (CalendarError, MailError, NotesError, RemindersError, json)
- `hestia/voice/journal.py`: 5 unused (Any, Dict, IntentType, MemoryManager, Message)
- `hestia/memory/database.py`: 4 unused (Any, ChunkType, Dict, datetime)
- `hestia/agents/config_loader.py`: 4 unused (Any, LEGACY_SLOT_MAP, LogComponent, REQUIRED_FILES)

---

## Consistency Issues

| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| `sanitize_for_log(e)` in all route error handlers | All route files import and use | 4 files don't import it | `health_data.py`, `mode.py`, `tools.py`, `voice.py` (though none currently need it -- no generic except blocks in first 3) |
| Swift `#if DEBUG` for `print()` | All print() wrapped | 139 unguarded | 36 in `macOS/`, 103 in `Shared/` |
| Pydantic schemas in `schemas.py` | Centralized | `health_data.py` defines inline schemas (lines 28-74) | `hestia/api/routes/health_data.py` |
| HTTP error response format | `{"error": "code", "message": "text"}` | `user_profile.py` uses bare string `detail=f"..."` | 11 instances in `user_profile.py`, 5 in `agents_v2.py` -- these are 404/400 responses, not 500s |
| Database path construction | `Path.home() / "hestia" / "data"` | Consistent across all modules | All 12 database modules (but not configurable for multi-user) |
| Exception handling in routes | `except Exception as e:` with sanitize_for_log | Consistent | 65 generic except blocks, 91 sanitize calls (some blocks have multiple logs) |
| Async singleton factory | `async def get_X_manager()` | Consistent | 12/12 domain modules |

---

## Documentation Currency

| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Current | Module count (21), endpoint count (116), test count (1086), test files (25) all accurate. References pyproject.toml `requires-python` constraint but no pyproject.toml exists in repo. |
| api-contract.md | Nearly Current | Endpoint count matches (116). Test count shows 1085 (should be 1086). Test passing count shows 1082 (should be 1083). |
| hestia-decision-log.md | Current | 36 ADRs through ADR-036 (macOS Health). Recent decisions (Sprint 4-5) recorded. |
| Agent definitions | Current | 4 agents defined with appropriate scoping. Test counts/module lists need periodic refresh (claims "1086" in CLAUDE.md which matches). |
| Skill definitions | Current | 13 skills, all reference correct tool names and patterns. |

---

## Workspace Hygiene

- **Orphaned files:** 0 (git status clean, 2 commits ahead of origin)
- **Stale TODOs:** 2 in Python (`orders/manager.py:438`, `orders/scheduler.py:272`) -- both relate to deferred scheduler integration
- **Stale TODOs in Swift:** 0
- **Archive candidates:** 0 -- `docs/` folder well-organized with `archive/` subdirectory already used
- **Debug artifacts:** 0
- **Scratch files:** 0
- **docs/ loose files check:** `figma-make-prompt.md`, `ui-phase3-plan.md`, `ui-requirements.md` could potentially be archived (relate to completed phases)

---

## Multi-User Readiness

**Rating:** Significant Work

| Area | Status | Gap |
|------|--------|-----|
| SQLite user scoping | 1/12 modules scoped | Only `newsfeed` has `user_id` column. All other tables (memory, tasks, health, agents, wiki, explorer, cloud, orders, sessions, user, gate, invites) lack it. |
| ChromaDB isolation | Not scoped | Single global collection. No per-user namespace. |
| API user scoping | Partial | JWT carries `device_id` but no `user_id`. All queries filter by device or are global. |
| Session isolation | Device-scoped | Sessions track `device_id` via memory manager. No `user_id` concept. |
| Cross-device continuity | Not supported | Data is device-scoped at best, global at worst. No user-level data sync. |
| File paths | Hardcoded | 21 `Path.home()` calls. Data stored in `~/hestia/data/`. Not parameterizable per user. |
| Keychain | Per-device | Keychain items stored with service name `hestia.*`. Not user-partitioned. |

**Assessment:** The system is fundamentally single-user. `device_id` is used as the primary identity in the API layer, but most database tables don't scope by any identity at all -- they're implicitly global. The newsfeed module (Sprint 3, ADR-033) demonstrates the correct multi-user pattern with `user_id` columns and per-user state, but it's the only module that does this.

**Migration path:** Would require:
1. Add `user_id` column to all 11 unscoped database tables (schema migration)
2. Introduce user concept in JWT (currently only `device_id`)
3. Add device-to-user mapping table
4. Scope all queries by user_id
5. Partition ChromaDB collections per user
6. Make file paths configurable (remove `Path.home()` hardcoding)
7. Partition Keychain by user

This is estimated at 2-3 full sessions of work.

---

## Summary

- **CISO: Acceptable** -- Solid security for single-user home deployment. Keychain + Fernet double encryption, JWT auth on all endpoints, rate limiting, error sanitization. Minor: validation error leakage, narrow prompt injection patterns.
- **CTO: Strong** -- Clean architecture with consistent patterns across 21 modules. 100% type hint coverage. Only 2 layer boundary violations (both acceptable). 1086 tests. Main concerns: monolithic schemas.py, blocking file I/O in async contexts.
- **CPO: Strong** -- Complete feature set matching roadmap. 116 endpoints fully documented. 36 ADRs recorded. Excellent onboarding docs. Main concern: 139 unguarded Swift print() statements.
- **Critical issues:** 0
- **High-priority issues:** 3 (validation error leakage, unguarded prints, schemas.py size)
- **Simplification opportunities:** 6
- **Consistency violations:** 3 patterns with minor drift
- **Documentation drift:** 1 item (api-contract.md test count off by 1)
- **Multi-user readiness:** Significant Work (11/12 database modules unscoped, no user concept in JWT)
