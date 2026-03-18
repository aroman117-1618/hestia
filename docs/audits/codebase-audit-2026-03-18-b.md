# Codebase Audit: Hestia
**Date:** 2026-03-18
**Auditor:** Opus 4.6 (1M context)
**Overall Health:** Healthy (with targeted issues requiring attention)

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Consistent manager pattern across 19 modules. Comprehensive test suite (2426+135). Robust auth with JWT+Keychain+biometric. 42 ADRs documenting every major decision. Clean layer separation (routes never touch raw SQL directly, with one exception). | **Weaknesses:** Learning routes have NO auth (10 endpoints). CLAUDE.md endpoint count stale (says 208, actual 209). `triggers.yaml` referenced in code but missing from `hestia/config/`. 4 `str(e)` leaks in routes. Private member access from routes layer (`_database`, `_principle_store`). |
| **External** | **Opportunities:** WAL mode only on trading DB -- other high-write DBs (memory, outcomes) would benefit. Consolidate the 19 global singletons into a dependency injection container. Learning routes could use the same `get_device_token` pattern as every other module. | **Threats:** Trading module going live without auth on learning routes = data exposure vector. Self-signed TLS limits trust chain. Single-server architecture (no HA). Growing module count (31 dirs) increases startup time and memory footprint. |

---

## CISO Audit
**Rating:** Acceptable (one Critical finding)

### Critical Issues

| Issue | Location | Risk | Recommendation |
|-------|----------|------|----------------|
| **Learning routes have NO authentication** | `hestia/api/routes/learning.py` (all 10 endpoints) | HIGH — anyone with network access can read/write learning data, trigger distillation, acknowledge alerts. `user_id` is a raw query param, not derived from JWT. | Add `Depends(get_device_token)` to all endpoints. Derive `user_id` from device context, not from caller-supplied query param. |
| `str(e)` in route error handling | `hestia/api/routes/tasks.py:341,426,514`, `orders.py:370` | MEDIUM — internal exception messages exposed to error-routing logic. While not directly returned to client in most cases, creates leakage path. | Replace with `sanitize_for_log(e)` for logging, use generic messages for routing. |

### Findings

**Authentication & Authorization**
- JWT: HS256, 90-day expiry, Keychain-stored secret with env var fallback. Solid.
- Constant-time secret comparison (`secrets.compare_digest`) for setup secret. Good.
- Device revocation implemented (ADR-034) with `revoked_at` column.
- Health routes (`/v1/ping`, `/v1/health`, `/v1/ready`) intentionally unauthenticated. Appropriate for monitoring.
- WebSocket auth: JWT verified via first message, not query params. Good security practice.
- **Trading routes** use `Depends(get_device_token)`. Properly secured.
- **Learning routes** use `user_id: str = Query(...)` with zero auth. This is an IDOR vulnerability -- any caller can specify any user_id.

**Credential Management**
- No hardcoded secrets found in Python source. API keys stored in Keychain.
- Structured logger has regex-based secret redaction (passwords, tokens, API keys). Good.
- Audit logger checks for secret-like values before logging. Good defense in depth.

**Error Handling & Information Leakage**
- 178 uses of `sanitize_for_log(e)` across 28 route files. Excellent adoption.
- 4 instances of `str(e)` remaining (tasks.py x3, orders.py x1). Minor but should be cleaned.
- No `detail=str(e)` found in HTTP responses. Good.

**Attack Surface**
- CORS restricted to localhost origins by default. Configurable via env var.
- Prompt injection: 4 regex patterns in `orchestration/validation.py`. Minimal but present. Consider expanding coverage.
- Rate limiting on auth, chat, and expensive endpoints. Missing on learning routes.
- Communication gate enforced for external tool execution. Good.
- Self-signed TLS: acceptable for Tailscale-only access. Would need real certs for broader exposure.

**CISO Verdict: Acceptable** -- the learning auth gap is the one item that must be fixed before any production-like deployment. Everything else is well-designed for a single-user system.

---

## CTO Audit
**Rating:** Strong

### Critical Issues

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| Raw SQL in route layer | `hestia/api/routes/research.py:532-536` | Layer violation -- route directly executes SQL via `manager._database._connection.execute()` | Move `invalidate_fact()` to ResearchManager or ResearchDatabase. |
| Private member access from routes | `hestia/api/routes/learning.py:127-128` | Encapsulation breach -- `outcome_mgr._database`, `research_mgr._principle_store` | Expose public methods on managers instead. |
| Missing `triggers.yaml` | `hestia/config/` (referenced by `learning/scheduler.py:172`) | Trigger monitor silently disabled. Code handles gracefully but config should exist. | Create the config file or remove the code path. |

### Findings

**Layer Boundaries**
- Clean separation overall. Routes import managers, managers import databases. No upward imports detected.
- One exception: `research.py` route reaches through manager to raw SQLite connection. This is the only instance.
- Learning routes use a module-level `_learning_db_instance` global instead of the standard `get_X_manager()` singleton pattern. Inconsistent with the 18 other modules.

**Pattern Consistency**
- Manager pattern: 19/19 modules follow `models.py + database.py + manager.py` with `get_X_manager()`. Learning is the outlier (no manager, route instantiates DB directly).
- Logging: All 23 LogComponent enum values defined. Usage is consistent across modules.
- Logger initialization: `logger = get_logger()` with no args. Correct everywhere checked.
- Type hints: Present on all public method signatures. Good.
- BaseDatabase: 19 subclasses, all consistent. Only `TradingDatabase` uses WAL mode.

**Code Health**
- 72,737 lines of Python across 265 files. Reasonable for the feature set.
- No dead imports detected in routes.
- Largest route files: `memory.py` (911 LOC), `research.py` (739 LOC). Both are feature-dense but not unreasonable.
- Config: 8 YAML files. Clean. `triggers.yaml` is referenced but missing.
- `time.sleep()` in async context: Only in `logging/viewer.py:213` (log viewer utility, not server path). Acceptable.

**LLM/ML Architecture**
- 4-tier model routing (Primary -> Coding -> Complex -> Cloud). Well-designed with state machine.
- Council dual-path: Cloud active = parallel gather, cloud disabled = SLM only. Failures silently fall back. Robust.
- Hardware adaptation: auto-measures tok/s and adapts. Smart for resource-constrained hardware.
- Temporal decay formula is clean with per-type lambda values.

**Performance & Scalability**
- BaseDatabase uses aiosqlite throughout. No blocking I/O in async paths (except log viewer).
- No N+1 query patterns detected in routes.
- Parallel pre-inference pipeline (`asyncio.gather`) for memory + profile + council. Good optimization.
- 19 singleton managers initialized at startup. Each opens a SQLite connection. Not a problem for single-server, but would need connection pooling for scale.

**CTO Verdict: Strong** -- architecture is clean, patterns are consistent, and the few violations are localized and fixable. The learning module is the main outlier in pattern adherence.

---

## CPO Audit
**Rating:** Acceptable

### Critical Issues

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| `api-contract.md` says "186 endpoints across 27 route modules" | `docs/api-contract.md:10` | Documentation drift -- actual count is 209 endpoints across 29 route modules | Update the contract header. Add learning (10), trading (14), notifications (6) routes to the contract. |
| CLAUDE.md says "208 endpoints across 29 route modules" | `CLAUDE.md:146,298,337` | Minor drift -- actual is 209 (learning grew from 5 to 10 in Sprint 17) | Update to 209. |
| CLAUDE.md says "2561 tests (2426 backend + 135 CLI), 77 test files (70 backend + 7 CLI)" | `CLAUDE.md:163` | Tests accurate (2426+135=2561). Test files: 70+7=77. Both match reality. | Current. No action needed. |

### Findings

**API Usability**
- Endpoints are well-organized with consistent prefix patterns (`/v1/{module}/...`).
- Swagger auto-docs available at `/docs`. Good discoverability.
- Response schemas are mostly consistent (many use `{"data": ...}` envelope).
- Learning routes return raw `{"data": ...}` without Pydantic response models. Inconsistent with other routes that use typed response models.

**Feature Completeness**
- All 42 ADRs documented. Roadmap aligns with implementation.
- Trading module (Sprints 21-25) is actively being built. Foundation, strategies, risk, backtesting, and Coinbase integration appear structurally complete.
- No half-built features detected. Deferred items (O5 MLX benchmark) are documented.

**Documentation Quality**
- CLAUDE.md is comprehensive (500+ lines). Project structure section is detailed and mostly accurate.
- Decision log has 42 ADRs, all with context/decision/alternatives/consequences. Excellent institutional memory.
- Sprint tracker (`SPRINT.md`) is actively maintained.
- `api-contract.md` last updated 2026-03-17 but endpoint count is 23 behind reality.

**CPO Verdict: Acceptable** -- documentation is thorough but has measurable drift in counts. The API contract not covering learning/trading/notification routes is the main gap.

---

## Simplification Opportunities

| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| Learning module inline DB | Routes instantiate `LearningDatabase` directly via module global | Create `LearningManager` + `get_learning_manager()` to match other 18 modules | 2h | Pattern consistency |
| 19 global singletons | Each manager has its own `global _instance` pattern | Consider a `ManagerRegistry` that manages lifecycle centrally | 4h | Reduced boilerplate, cleaner shutdown |
| Research route raw SQL | `research.py:532` executes SQL directly | Add `invalidate_fact(fact_id)` method to `ResearchManager` | 30min | Layer boundary fix |
| BaseDatabase WAL mode | Only TradingDatabase enables WAL | Add WAL as default in `BaseDatabase.connect()` | 30min | Better concurrent read performance for all modules |

---

## Adversarial Critique -- "What Will We Regret?"

### 7.1 Three Most Load-Bearing Decisions

1. **ADR-009: Keychain Credential Management** (2025-01-08) -- All secrets flow through macOS Keychain
2. **ADR-013: Dual-Store Memory (ChromaDB + SQLite)** (2025-01-08) -- Every memory operation touches two storage systems
3. **ADR-003/042: Single-Agent (then Orchestrator)** (2025-01-08, extended 2026) -- All intelligence routed through one model with code-based orchestration

### 7.2 Challenge Each Decision

#### ADR-009: Keychain Credentials

**Steel-man:** macOS Keychain gives hardware-backed security (Secure Enclave), biometric gates, and zero-config. For a single-user Mac system, this is the ideal credential store. Double encryption (Fernet + AES-256) is defense in depth.

**Attack:**
- **Premises:** Assumes macOS-only deployment forever. If Hestia ever runs on Linux (server, Docker, cloud), Keychain is unavailable. The entire security layer would need rewriting.
- **Hidden costs:** Every test that touches credentials needs mocking. `get_credential_manager()` appears in 6+ modules. The Keychain dependency is viral.
- **Time horizon:** M5 Ultra Mac Studio keeps this viable. But if Andrew wants to run Hestia headless on any non-Mac hardware, this breaks.

**Counter-argument:** A secrets manager abstraction layer (interface with Keychain, HashiCorp Vault, or env-var backends) would preserve the Keychain benefits while enabling portability. Cost: ~4h refactor.

**Verdict: VALIDATED** -- For a personal Mac system, Keychain is the right choice. The portability concern is real but not pressing given the hardware roadmap.

#### ADR-013: Dual-Store Memory

**Steel-man:** ChromaDB for semantic search + SQLite for structured queries gives the best of both worlds. Tag-based filtering + vector similarity is genuinely more powerful than either alone.

**Attack:**
- **Premises:** Assumes semantic search and structured queries are equally important. In practice, chat memory retrieval is 90%+ semantic search. The structured query surface (tag filters, temporal ranges) is underutilized in the chat pipeline.
- **Hidden costs:** Every memory operation is a dual-write. Consistency between ChromaDB and SQLite is maintained by application code, not transactions. A crash between the two writes creates orphaned records. The consolidator/pruner must operate on both stores.
- **Alternatives dismissed:** pgvector or SQLite-VSS could provide both capabilities in a single store. These didn't exist (or were immature) when ADR-013 was written in Jan 2025.

**Counter-argument:** SQLite-VSS (or DuckDB with vector support) could unify both stores. This would eliminate the consistency problem, simplify the memory lifecycle (consolidation, pruning), and reduce the memory module from ~1600 LOC to ~800. Trade-off: SQLite-VSS embedding quality may be lower than ChromaDB's.

**Verdict: WATCH** -- The dual-store works but the consistency gap is a real risk. Reassess when SQLite-VSS matures or when memory corruption is detected.

#### ADR-003/042: Single-Agent with Orchestrator

**Steel-man:** Code-based orchestration (state machines, routing rules) is predictable and debuggable. The Orchestrator extension (ADR-042) adds specialist routing without multi-agent chaos. Confidence gating prevents bad routing.

**Attack:**
- **Premises:** Assumes that code-based decomposition can keep pace with capability growth. With 31 modules and growing, the orchestration handler is becoming a bottleneck -- every new capability requires explicit routing logic.
- **Hidden costs:** The handler pipeline (`handle()`) is now a 700+ LOC function with parallel gather, memory retrieval, profile loading, council intent, command expansion, tool execution, and streaming. Adding new capabilities (trading signals, notifications) requires threading through this monolith.
- **Time horizon:** Trading module (Sprint 21-30) will need real-time decision-making that doesn't fit the request/response chat paradigm. The handler will need a separate event-driven path.

**Counter-argument:** Extract the handler into smaller, composable middleware (memory middleware, auth middleware, routing middleware, execution middleware). This preserves the single-agent model but makes the pipeline extensible without editing a monolith.

**Verdict: WATCH** -- The current design works but the handler is approaching its complexity ceiling. The trading module's real-time needs will likely force a refactor. Consider middleware decomposition before Sprint 26.

### 7.3 Project-Level Strategic Challenges

- **Optimizing for breadth over depth:** 31 modules, 209 endpoints, 42 ADRs. The system has enormous surface area for a single-user tool. Each new module adds startup time, test maintenance, and documentation burden. The trading module alone adds 14 endpoints.
- **Hardest capability to add in 6 months:** Multi-user support. The `user_id` parameter is inconsistently sourced (sometimes from JWT device, sometimes from query params, sometimes hardcoded as `"user-default"`). A multi-user migration would touch every database and most routes.
- **Complexity accumulating fastest:** The orchestration layer (handler + prompt builder + agent router + council). This is where features intersect and where bugs hide. It's also where the value is -- but the 700+ LOC handler is a code smell.
- **What a rewrite would do differently:** Use a proper dependency injection framework (like Python's `dependency-injector`) instead of 19 hand-rolled global singletons. Use a message bus for inter-module communication instead of direct imports. Use a single database with schema-per-module instead of 19 separate SQLite files.

### 7.4 Verdict Summary

| Decision | Verdict | Trigger for Reassessment |
|----------|---------|-------------------------|
| ADR-009: Keychain Credentials | **VALIDATED** | Deployment target changes to non-Mac |
| ADR-013: Dual-Store Memory | **WATCH** | Memory corruption detected, or SQLite-VSS reaches maturity |
| ADR-003/042: Single-Agent + Orchestrator | **WATCH** | Handler exceeds 1000 LOC, or trading real-time needs break request/response model |

---

## Consistency Issues

| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| Auth on all data routes | `Depends(get_device_token)` | Missing entirely | `hestia/api/routes/learning.py` |
| Manager pattern | `get_X_manager()` singleton | Module-level global `_learning_db_instance` | `hestia/api/routes/learning.py` |
| Error sanitization | `sanitize_for_log(e)` | `str(e)` used for error routing | `tasks.py:341,426,514`, `orders.py:370` |
| Private member encapsulation | Public methods on managers | Direct access to `._database`, `._connection`, `._principle_store` | `research.py:528-536`, `learning.py:127-128` |
| Config files referenced | All referenced configs exist | `triggers.yaml` missing | `hestia/config/` |

---

## Documentation Currency

| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | **Slightly Stale** | Says "~208 endpoints" -- actual is 209. Says "30 modules" in tech stack -- actual module dirs is 31. Learning endpoints grew from 5 to 10 in Sprint 17 but the API Summary table still says 5. |
| api-contract.md | **Stale** | Header says "186 endpoints across 27 route modules" -- actual is 209 across 29. Missing learning (Sprint 17 expansion), trading, and notifications route documentation. |
| Decision log | **Current** | 42 ADRs, most recent (ADR-042) covers Agent Orchestrator. No gaps detected. |
| Agent definitions | **Not verified** | Would require reading `.claude/agents/` files. |
| Skill definitions | **Not verified** | Would require reading `.claude/skills/` files. |

---

## Workspace Hygiene

**Orphaned/Untracked Files (from git status):**
- `HestiaApp/data/` -- data directory in app bundle, likely test data
- `HestiaApp/macOS/DesignSystem/StringExtensions.swift` -- new file, should be committed
- `HestiaApp/macOS/Services/APIClient+Investigate.swift` -- new service extension
- 7 new Command view files (`ActivityFeedView.swift`, `ExternalActivityView.swift`, etc.)
- `docs/plans/activity-feed-restructure-second-opinion-2026-03-18.md` -- plan doc
- `docs/plans/research-data-quality-plan.md` -- plan doc
- `scripts/backfill-apple-data.py`, `scripts/reclassify-insights.py` -- utility scripts
- `hestia-cli/data/` -- CLI data directory

**Modified but uncommitted (17 files):** Mix of backend (trading, inbox, learning, memory, research) and frontend (macOS views). Suggests active development across multiple workstreams simultaneously.

**Stale TODOs:** 0 TODO/FIXME/HACK comments found in backend Python code. Clean.

---

## Summary

| Perspective | Rating | Summary |
|-------------|--------|---------|
| **CISO** | Acceptable | One critical gap: learning routes have zero auth (10 endpoints). Fix is straightforward. Everything else is well-designed. |
| **CTO** | Strong | Clean architecture, consistent patterns across 19 manager modules. Minor violations (1 raw SQL in routes, 1 missing config). Learning module is the pattern outlier. |
| **CPO** | Acceptable | Thorough documentation with measurable drift. API contract is 23 endpoints behind reality. CLAUDE.md counts need a refresh. |

- **Critical issues:** 1 (learning auth)
- **Simplification opportunities:** 4
- **Consistency violations:** 5
- **Documentation drift:** 3 documents
- **Adversarial verdicts:** 1 VALIDATED, 2 WATCH
