# Codebase Audit: Hestia
**Date:** 2026-03-15
**Overall Health:** Healthy

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Disciplined layer boundaries (zero upward imports found). Uniform manager pattern across 16 database modules all inheriting `BaseDatabase`. Comprehensive test suite (1819 collected). Clean logger convention (`get_logger()` with zero-arg) enforced everywhere. 87% response_model coverage (142/163 endpoints). CORS locked to specific origins. Security headers middleware solid. | **Weaknesses:** Documentation counts stale (CLAUDE.md says 154 endpoints / 25 route modules / 1683 tests; reality is 163 endpoints / 26 route modules / 1819 tests). `api-contract.md` says 132 endpoints / 22 route modules. `str(e)` pattern in `tasks.py` (lines 341, 426, 514) and `orders.py` (line 370) leaks exception internals for control flow. No WAL mode on any SQLite database. Single aiosqlite connection per database module (no pooling). 4 route handlers in `proactive.py` missing return type hints. |
| **External** | **Opportunities:** WAL mode would improve concurrent read performance for free. `str(e)` in tasks/orders can be replaced with specific exception subclasses. Worktree cleanup (165MB `.claude/worktrees/`). 24 Sprint-12 files in `docs/discoveries/` could be archived. Research module has 12 endpoints -- highest of any module -- could benefit from splitting. | **Threats:** Single SQLite connection per manager means concurrent requests to the same module serialize. Self-signed TLS means no certificate validation by default (`curl -k`). `invite_store.py` manages its own connection outside `BaseDatabase` pattern. Tests pass but `test_inference.py::TestInferenceClientIntegration::test_simple_completion` fails (requires live Ollama). |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues
| Issue | Location | Risk | Recommendation |
|-------|----------|------|----------------|
| `str(e)` used for control flow | `hestia/api/routes/tasks.py:341,426,514`, `orders.py:370` | Low — message checked internally, not returned raw to client | Replace with typed exception subclasses (e.g., `TaskNotFoundError`) |
| `invite_store.py` outside BaseDatabase | `hestia/api/invite_store.py:40` | Low — duplicates PRAGMA setup, could drift | Refactor to extend `BaseDatabase` |
| Weather API key env var fallback | `hestia/proactive/briefing.py:88` | Low — logged warning, Keychain preferred | Document as intentional fallback |

### Findings

**Authentication & Authorization**
- JWT: HS256, 90-day expiry, secret sourced from Keychain with env var fallback, generated on first run. Solid.
- Route protection: All 25 REST route modules (excluding `health.py`) use `Depends(get_device_token)`. Health endpoints (`/v1/health`, `/v1/ping`, `/v1/ready`) are intentionally unauthenticated. WebSocket (`ws_chat.py`) implements its own auth handshake at connection time.
- Device revocation: `check_device_revocation()` with fail-open if invite store unavailable (documented in ADR-034).
- Auth dependency count: 156 `Depends(get_device_token)` calls across 24 route files. Every authenticated endpoint is covered.

**Credential Management**
- No hardcoded secrets found (grep for `password=`, `secret=`, `api_key=` returned zero hits in source).
- All API keys stored in Keychain via `CredentialManager`. Never returned in API responses.
- `get_secret_key()` generates and stores JWT secret in Keychain on first run.

**Error Handling & Information Leakage**
- `sanitize_for_log(e)` imported in all 26 route files. No raw `{e}` in f-strings in route files.
- `str(e)` appears in `tasks.py` (3 locations) and `orders.py` (1 location) but only for internal string matching ("not found"), never passed to HTTP response `detail`. HTTP responses use generic messages.
- Zero bare `except:` clauses in routes. 122 `except Exception` blocks -- all with sanitized logging.

**Attack Surface**
- CORS: Restricted to `localhost:3000,8080,8443` by default, configurable via `HESTIA_CORS_ORIGINS`.
- Security headers: HSTS, X-Frame-Options DENY, CSP `default-src 'self'`, nosniff, XSS protection all present.
- Cache-Control: Path-aware with `no-store, no-cache` default. Read-heavy endpoints cached (ping 10s, tools 60s, wiki 30s).
- Rate limiting middleware registered.
- Self-signed TLS: acceptable for local/Tailscale network. Consider Let's Encrypt if ever exposed publicly.
- Prompt injection: Council dual-path with fallback means LLM output never directly controls system operations without tool executor sandbox.
- Communication gate: All external tool execution gated through `CommGate`.

---

## CTO Audit
**Rating:** Healthy

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| No SQLite WAL mode | `hestia/database.py:52` | Read contention under concurrent requests | Add `PRAGMA journal_mode=WAL` after `PRAGMA foreign_keys = ON` |
| Single connection per DB module | `hestia/database.py:50` | Request serialization per module | Acceptable for single-user; document as known limitation |
| `invite_store.py` duplicates BaseDatabase | `hestia/api/invite_store.py` | Pattern inconsistency, maintenance drift | Refactor to inherit BaseDatabase |

### Findings

**Layer Boundaries**
- Zero upward imports found. Verified: `security/` does not import from `memory/orchestration/execution/inference`. `inference/` does not import from `api/orchestration/execution`. `memory/` does not import from `api/execution`. `orchestration/` does not import from `api/`. `council/` does not import from `api/`. Clean.
- Research module uses lazy imports (`from hestia.memory import get_memory_manager` inside methods) to avoid circular deps. Correct pattern.

**Pattern Consistency**
- All 16 domain database modules inherit `BaseDatabase`. Consistent `models.py` + `database.py` + `manager.py` + `get_X_manager()` async factory pattern.
- Logger: `get_logger()` called with zero arguments in every module. No violations found.
- `LogComponent` enum has 19 values covering all modules.
- Exception in pattern: `invite_store.py` manages its own SQLite connection (line 40) without inheriting `BaseDatabase`.

**Code Health**
- Only 1 TODO/FIXME found across entire Python codebase (a comment about gradient parsing in `agents/config_loader.py:345`). Extremely clean.
- No dead code detected via grep patterns.
- 27 top-level modules under `hestia/`. Well-organized.
- Type hints: Most function signatures have type hints. 4 route handlers in `proactive.py` and inner functions in `ws_chat.py` lack return type annotations -- minor.

**LLM/ML Architecture**
- 3-state cloud routing (disabled/enabled_smart/enabled_full) with `_sync_router_state()` after every mutation. State consistent.
- Council dual-path: cloud active = parallel `asyncio.gather`, cloud disabled = SLM intent only. All calls wrapped in try/except for fail-silent behavior.
- 4-tier model routing: PRIMARY -> CODING -> COMPLEX -> CLOUD. Clean separation.
- Hardware adaptation: auto-detects tok/s on first inference, swaps model if below threshold.

**Performance & Scalability**
- Single aiosqlite connection per database module. No connection pooling. This serializes concurrent reads to the same module. Acceptable for single-user personal assistant but would not scale to multi-user.
- No WAL mode set on any database. Adding `PRAGMA journal_mode=WAL` would improve concurrent read performance significantly.
- ChromaDB used for vector storage (memory + principles). No collection size limits documented.
- `CacheManager` in `orchestration/cache.py` handles request-level caching.
- Cache-Control headers on read-heavy endpoints reduce redundant requests.

---

## CPO Audit
**Rating:** Healthy

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| Documentation counts significantly stale | `CLAUDE.md`, `docs/api-contract.md` | Misleads new sessions, causes incorrect assumptions | Update all counts to current values |

### Findings

**API Usability**
- 163 endpoints across 26 route modules (+ 1 WebSocket).
- 87% of endpoints have `response_model` declarations (142/163). Remaining 21 likely return raw dicts or streaming responses.
- Consistent error format using `{"error": "error_code", "message": "..."}` in HTTP exception details.
- Swagger UI available at `/docs`.

**Feature Completeness**
- All workstreams (WS1-4), all UI phases, all sprints (1-8) marked COMPLETE. Feature set matches roadmap.
- Three modes (Tia/Mira/Olly) implemented via agent profiles (V1 slot-based + V2 markdown-based).
- Research module (Sprint 8) is the newest addition with 12 endpoints -- the largest of any single route module.

**Documentation Quality**
- `CLAUDE.md`: Comprehensive and well-structured but counts are stale (see Documentation Currency below).
- Decision log: 54 ADR references found. Latest entries cover Sprint 8 Research & Graph architecture.
- 4 agent definitions and 9 skill definitions present and structured.
- Onboarding friction: Low. `CLAUDE.md` provides enough context for a new session to be productive.

---

## Simplification Opportunities
| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| Worktree cleanup | 165MB `.claude/worktrees/` (stale agent worktree) | Delete `agent-adfe4cec` worktree | 1 min | Disk space |
| Sprint-12 discovery files | 8 Sprint-12 files in `docs/discoveries/` | Archive to `docs/archive/sprint-12/` | 5 min | Cleaner docs structure |
| `invite_store.py` | Own connection management | Inherit `BaseDatabase` | 30 min | Pattern consistency |
| `tasks.py` exception control flow | `str(e)` matching for not-found | Typed exception subclasses | 20 min | Cleaner error handling |
| `agents.py` + `agents_v2.py` coexistence | Two separate route files, 10 endpoints each | Document deprecation timeline for V1 | 5 min | Reduce API surface long-term |

## Consistency Issues
| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| Return type hints on route handlers | All handlers annotated | 4 handlers missing in proactive.py | `hestia/api/routes/proactive.py:142,180,329,350` |
| BaseDatabase for all SQLite | All databases inherit BaseDatabase | `invite_store.py` manages own connection | `hestia/api/invite_store.py` |
| `str(e)` not used in routes | `sanitize_for_log(e)` only | 4 uses of `str(e)` for control flow | `hestia/api/routes/tasks.py:341,426,514`, `orders.py:370` |
| WAL mode | Should be enabled for concurrent reads | Not set on any database | `hestia/database.py:52` |

## Documentation Currency
| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Stale | Says "154 endpoints across 25 route modules" -- actual is 163 endpoints across 26 route modules. Says "1683 tests (1680 passing, 3 skipped)" -- actual is 1819 tests collected. Says "105 macOS files" -- actual is 126. |
| api-contract.md | Stale | Header says "132 endpoints across 22 route modules" and "1312 tests (1309 passing, 3 skipped)". Last updated 2026-03-03. Missing ws_chat, research expansion, user_profile expansion. |
| hestia-decision-log.md | Current | 54 ADR references. Latest covers Sprint 8 architecture. |
| Agent definitions | Current | 4 agents present in `.claude/agents/`. |
| Skill definitions | Current | 9 skills present in `.claude/skills/`. |
| BaseDatabase docstring | Stale | Says "all 11 database modules" -- actual is 16 database modules inheriting BaseDatabase. |
| LogComponent CLAUDE.md list | Stale | CLAUDE.md lists 14 LogComponent values but enum has 19 (missing FILE, INBOX, OUTCOMES, APPLE_CACHE, RESEARCH). |

## Workspace Hygiene
- **Orphaned worktrees:** `.claude/worktrees/agent-adfe4cec/` (165MB) -- stale agent worktree, safe to delete.
- **Untracked files:** `.serena/project.yml` (modified), `docs/discoveries/atlas-flipper-matter-iot-2026-03-14.md`, `docs/discoveries/hestia-enhancement-candidates-2026-03-15.md` -- intentional discovery outputs.
- **Stale TODOs:** 1 (gradient parsing comment in `agents/config_loader.py:345` -- not actionable).
- **Archive candidates:** 8 Sprint-12 files in `docs/discoveries/` (SPRINT-12-BLOCKERS.md, SPRINT-12-COUPLING-ANALYSIS.md, SPRINT-12-INDEX.md, SPRINT-12-PRE-IMPL-REVIEW.md, SPRINT-12-QUICK-FIX-GUIDE.md, SPRINT-12-REVIEW-SUMMARY.txt) could move to `docs/archive/`.
- **Debug artifacts:** None found.

---

## Summary
- **CISO:** Acceptable -- solid auth coverage, no leaked secrets, proper error sanitization. Minor `str(e)` usage for control flow in tasks/orders.
- **CTO:** Healthy -- clean layer boundaries, consistent patterns, excellent test coverage. SQLite WAL mode and `invite_store.py` pattern drift are the main technical debts.
- **CPO:** Healthy -- feature-complete against roadmap, good API design. Documentation counts are significantly stale and should be updated.
- **Critical issues:** 0
- **Moderate issues:** 3 (WAL mode, doc staleness, invite_store pattern)
- **Simplification opportunities:** 5
- **Consistency violations:** 4
- **Documentation drift:** 7 items across 4 documents
