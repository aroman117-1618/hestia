# Codebase Audit: Hestia
**Date:** 2026-03-16
**Auditor:** Claude Opus 4.6 (IQ 175 panel: CISO/CTO/CPO)
**Overall Health:** Healthy

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Disciplined manager pattern across 27+ modules. Clean layer boundaries (zero upward imports from core to API, except one justified case). Comprehensive auth on all sensitive routes. 2012 tests across 58 files. Error sanitization (`sanitize_for_log`) enforced across all 26 route modules. Graceful startup/shutdown lifecycle with parallel init + readiness gate. BaseDatabase ABC eliminates boilerplate across 16 SQLite modules. | **Weaknesses:** Handler.py at 2510 lines is a god-object. CLAUDE.md has stale counts (endpoints, tests, test files). Two config directories (`hestia/config/` and `config/`) cause confusion. `str(e)` used in 3 places in tasks.py for conditional logic (safe but breaks convention). No connection pooling for SQLite. |
| **External** | **Opportunities:** Handler decomposition would unlock testability and reduce cognitive load. Consolidate `config/` to single location. Agent orchestrator (Sprint 14) is well-designed — extend golden test dataset as patterns emerge. Principle store + temporal facts are underutilized by the chat pipeline. | **Threats:** Self-signed TLS means no cert rotation or pinning. Fail-open revocation check (ADR-034) could allow revoked devices during invite store downtime. Single-process architecture with in-memory rate limiting won't survive multi-worker scaling. 2510-line handler is a regression magnet. |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues
| Issue | Location | Risk | Recommendation |
|-------|----------|------|----------------|
| Fail-open device revocation | `hestia/api/middleware/auth.py:293` | Revoked device access during store outage | Add circuit breaker with configurable fail-closed mode |
| `str(e)` in route error handling | `hestia/api/routes/tasks.py:341,426,514` | Convention violation, potential info leak in future refactors | Replace with pattern matching on exception type, not message content |

### Findings

**Authentication & Authorization**
- JWT: HS256, 90-day expiry, Keychain-stored secret. Algorithm pinned in `algorithms=[ALGORITHM]` -- good.
- All 26 route modules import `get_device_token` from auth middleware. Health endpoints (`/v1/health`, `/v1/ping`, `/v1/ready`) correctly unauthenticated.
- Invite tokens: 10-minute expiry, one-time nonce, constant-time comparison via `secrets.compare_digest`. Solid.
- Rate limiting on auth endpoints: 5 req/min for `/v1/auth/register`. Good.
- Device revocation: fail-open by design (ADR-034). Documented trade-off. Uses `import logging` directly instead of `get_logger()` at line 297 -- minor inconsistency.

**Credential Management**
- Zero hardcoded secrets in config YAML files (verified: inference, execution, memory, wiki, investigate, files, orchestration).
- `.env` exists (1 line) and is properly in `.gitignore`.
- Keychain-backed JWT secret with environment variable override for testing. Three-tier partitioning (`operational/sensitive/system`) in CredentialManager. Double encryption (Fernet + Keychain AES-256).
- No plaintext secrets found anywhere in source.

**Error Handling & Information Leakage**
- `sanitize_for_log()` used 153 times across all 26 route modules. Comprehensive.
- Global exception handler in `server.py:704` returns generic "internal_error" with request_id only. Tracebacks logged server-side only. Good.
- Validation errors stripped of Pydantic internals at `server.py:687`. Good.
- Three `str(e)` usages in `tasks.py` for "not found" detection -- values are from internal `ValueError` raised by the task manager, not user input. Low risk but breaks the established pattern.
- One `str(e).lower()` in `orders.py:370` -- same pattern, same risk profile.

**Attack Surface**
- No `shell=True` in any subprocess call. All subprocess invocations use list arguments. Good.
- No SQL injection risk: f-strings in SQL are only for building static column lists/placeholders, never user input interpolation.
- File system: PathValidator with allowlist-first, denylist, symlink resolution, null-byte protection, TOCTOU-safe reads. Thorough.
- CORS: restricted to localhost origins by default, configurable via env var. Not wildcard.
- Security headers: HSTS, CSP, X-Frame-Options, X-XSS-Protection, nosniff, referrer-policy. Comprehensive.
- Prompt injection: User input flows through council classification and prompt builder without sanitization. LLM-level prompt injection remains an inherent risk for any system passing user input to LLMs. The communication gate provides an output-side control.
- Self-signed TLS: acceptable for Tailscale mesh (encrypted tunnel), but no cert rotation mechanism exists.

---

## CTO Audit
**Rating:** Acceptable

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| God-object handler | `hestia/orchestration/handler.py` (2510 lines, 22 async methods) | Regression risk, test complexity, onboarding friction | Extract into RequestPipeline, ToolExecutionMixin, SessionManager, MemoryGatherer |
| Config directory split | `hestia/config/` (6 files) vs `config/` (1 file) | Confusion on where to put new configs | Move `config/orchestration.yaml` into `hestia/config/` |
| CLAUDE.md stale counts | Multiple locations | Misleading onboarding docs | Run `count-check.sh` and update |

### Findings

**Layer Boundaries**
- Clean separation verified. Zero upward imports from `memory/`, `inference/`, `security/`, `execution/` into `hestia.api`.
- One justified exception: `handler.py:1756` imports `sanitize_for_log` from `hestia.api.errors` -- this utility should arguably live in a shared module rather than `api.errors`, but the import direction (orchestration importing from api) is the standard flow, not a violation.
- No circular dependencies detected.

**Pattern Consistency**
- Manager pattern: Consistent across all modules. Each has `models.py` + `database.py` + `manager.py` + `get_X_manager()` factory.
- Logger pattern: 103 correct `get_logger()` calls with zero argument. Zero incorrect calls with arguments. Perfect compliance.
- LogComponent enum: 19 values covering all modules. CLAUDE.md lists only 14 -- missing FILE, INBOX, OUTCOMES, APPLE_CACHE, RESEARCH. Stale.
- Async/await: No blocking I/O detected in async contexts. Subprocess calls are in synchronous tool functions, not async handlers.
- Type hints: Present on all handler methods checked. Return type annotations consistent.

**Code Health**
- Only 1 TODO/FIXME/HACK comment in entire Python backend (`config_loader.py:345` -- a comment about gradient parsing, not a real TODO).
- No dead imports detected in route modules (all imports used).
- BaseDatabase ABC eliminates duplication across 16 SQLite modules.
- `requirements.txt` exists with `requirements.in` (pip-compile lockfile pattern). Good.

**LLM/ML Architecture**
- Inference pipeline: 3-state cloud routing with `_sync_router_state()` propagation. 4-tier model routing (PRIMARY/CODING/COMPLEX/CLOUD). Fallback chains at every level.
- Council: try/except wrapping on all paths, dual-path (cloud vs SLM), CHAT bypass optimization. Robust.
- Agent orchestrator (Sprint 14): confidence-gated dispatch, kill switch in config, golden test dataset (33 cases). Well-designed.
- Temporal decay: configurable per-chunk-type lambda in `memory.yaml`. Correct exponential decay formula.

**Performance & Scalability**
- Parallel manager init with `asyncio.gather()` + sequential retry on failure. Good pattern.
- Uvicorn request recycling at 5000 requests. Memory leak protection.
- ETag conditional GET on wiki/tools endpoints. Cache-Control headers per path.
- SQLite: No connection pooling (single connection per database instance). Acceptable for single-server, but would need rework for multi-worker.
- Rate limiting: In-memory sliding window. Won't survive process restart or multi-worker. Acceptable for current architecture.
- Handler pre-inference: `asyncio.gather()` for memory + profile + council. Good parallelization.

---

## CPO Audit
**Rating:** Strong

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| None critical | -- | -- | -- |

### Findings

**API Usability**
- 170 endpoints across 26 route modules + 1 WebSocket. Well-organized by domain.
- Consistent error envelope: `{"error": "code", "message": "text"}` pattern across all routes.
- Swagger docs available at `/docs` and `/redoc`. Auto-generated from Pydantic schemas.
- Pydantic schemas in dedicated `api/schemas/` package (18 modules). Clean separation.
- API contract doc exists at `docs/api-contract.md`.

**Feature Completeness**
- All three modes (Tia/Mira/Olly) functional via agent config system.
- Agent orchestrator (Sprint 14) adds coordinator-delegate model. Well-designed progression.
- All claimed workstreams verified complete: WS1-4, CLI Sprints 1-5, UI Phases 1-4, Sprints 1-14.
- Knowledge graph (facts, entities, communities, principles, episodic nodes) fully wired with 17 research endpoints.

**Documentation Quality**
- CLAUDE.md is comprehensive (700+ lines) with architecture, conventions, quick commands, and project structure.
- Decision log exists with 42+ ADRs.
- Session handoff workflow documented and enforced.
- Agent definitions (4 files) and skill definitions present in `.claude/`.
- Discovery and plan audit docs well-organized in `docs/discoveries/` and `docs/plans/`.

---

## Simplification Opportunities

| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| Handler decomposition | 2510 lines, 22+ methods | Extract SessionManager, ToolPipeline, MemoryGatherer | Medium | High -- testability, readability |
| Config directory | `hestia/config/` (6 files) + `config/` (1 file) | Move `config/orchestration.yaml` to `hestia/config/` | Low | Low -- removes confusion |
| `sanitize_for_log` location | Lives in `hestia.api.errors` | Move to `hestia.errors` or `hestia.logging` | Low | Low -- eliminates the one layer boundary smell |
| agents v1 + v2 coexistence | Both registered in server.py | Deprecate v1 with 6-month sunset, then remove | Low | Medium -- reduces surface area |

---

## Consistency Issues

| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| Error handling: `sanitize_for_log(e)` | All route error logging | `str(e)` used for conditional logic in 4 places | `tasks.py:341,426,514`, `orders.py:370` |
| Logger import | `import logging` nowhere in non-logging modules | `import logging` used in auth middleware | `auth.py:296` |
| Parameter naming | `device_id` | `device_token` in some routes | `memory.py:462,522`, `research.py:51+` |
| Endpoint count docs | Consistent number | "170" in tech stack, "163" in API section | `CLAUDE.md` |

---

## Documentation Currency

| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Stale | Endpoint count inconsistent (170 vs 163 -- actual is 170). Test count stale (says 1917, actual is 2012 collected, 51 backend + 7 CLI = 58 test files vs claimed 48). LogComponent enum list missing 5 entries. Backend modules listed as 26 but there are 27+ subdirectories. Config directory structure incomplete (missing top-level `config/`). |
| api-contract.md | Not verified in detail | Likely stale given endpoint count drift |
| Agent definitions | Current | 4 agents properly defined |
| Skill definitions | Current | Present in `.claude/skills/` |
| SPRINT.md | Current | Sprint 14 accurately documented |

---

## Workspace Hygiene

- **Orphaned files:** `claude-config-refresh-plan.md` in project root should move to `docs/plans/`
- **Stale TODOs:** 1 (benign comment in `config_loader.py:345`)
- **Archive candidates:** 60+ files in `docs/discoveries/` and `docs/plans/` from completed sprints could be archived for cleanliness
- **Debug artifacts:** None found
- **Git status:** Clean working tree (1 modified file: CLAUDE.md -- unstaged)
- **Unpushed commits:** 20 commits ahead of origin/main

---

## Summary
- **CISO:** Acceptable -- Strong credential management, comprehensive error sanitization, proper auth coverage. Fail-open revocation and self-signed TLS are documented trade-offs, not oversights.
- **CTO:** Acceptable -- Clean architecture, excellent pattern consistency, zero dead code or import violations. Handler god-object is the single biggest tech debt item. Config directory split is minor but confusing.
- **CPO:** Strong -- 170 well-organized endpoints, consistent API design, thorough documentation, all features complete.
- **Critical issues:** 0 (security trade-offs are documented and intentional)
- **Significant issues:** 3 (handler size, stale CLAUDE.md counts, config directory split)
- **Simplification opportunities:** 4
- **Consistency violations:** 4
- **Documentation drift:** 5 items in CLAUDE.md need updating
