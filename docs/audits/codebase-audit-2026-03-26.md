# Codebase Audit: Hestia
**Date:** 2026-03-26
**Overall Health:** Healthy

**Codebase:** 83K LOC Python (294 files), 301 Swift files, 252 endpoints across 30 route modules, 3054 tests (2915 backend + 139 CLI), 97 test files. All tests passing.

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Consistent manager pattern across 22 database modules (all extend BaseDatabase). 160 files use `get_logger()` correctly. Zero bare `except:` clauses. Clean layer boundaries (no upward imports detected). 44 ADRs documenting every major decision. Comprehensive credential management (Fernet + Keychain). Log sanitization via `CredentialSanitizer` with regex-based redaction. | **Weaknesses:** `workflows.py` routes leak `ValueError` messages via `str(e)` in 9 places (violates error sanitization convention). 3 empty `Button {}` closures in macOS Views (compile but do nothing). `tasks.py` uses `str(e)` for conditional error branching. No `pip-audit` in CI for vulnerability scanning. CLAUDE.md says "250 endpoints" but actual count is 252; says "30 route modules" which is correct; says "3050 tests" but actual is 3054. |
| **External** | **Opportunities:** Trading module live with real capital — highest-value work. Workflow orchestrator canvas (React Flow) provides visual differentiation. 22 outdated pip packages could be bulk-updated. Knowledge graph on SQLite is portable and avoids heavy infra. | **Threats:** Self-signed TLS means no certificate rotation automation. Single-server architecture with in-memory state (rate limiter, session cache) resets on worker recycle. Crypto trading with market orders on real capital requires extreme reliability. `chromadb` 1.4.0 is behind 1.5.5 — breaking changes possible on upgrade. |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues
| Issue | Location | Risk | Recommendation |
|-------|----------|------|----------------|
| Error message leakage in workflows routes | `hestia/api/routes/workflows.py:120,176,191,319,338,375,409,425,463` | Medium — ValueError messages from business logic exposed to clients | Replace `str(e)` with generic messages; log with `sanitize_for_log(e)` |
| `str(e)` in tasks routes for branching | `hestia/api/routes/tasks.py:341,426,514` | Low — used for "not found" detection, actual HTTP response is generic | Refactor to use typed exceptions (NotFoundError, InvalidStateError) |

### Findings

**Authentication & Authorization**
- JWT: HS256, 90-day expiry, secret stored in `~/.hestia/jwt-secret` (chmod 600) with Keychain fallback. Auto-generates on first run. Constant-time comparison for setup secrets.
- Route protection: 28 of 30 route modules use `get_device_token` dependency. Exceptions are appropriate: `health.py` (public health check) and `ws_chat.py` (authenticates via first WebSocket message with `verify_device_token`).
- Device registration: Invite-based with QR code, one-time nonce, rate-limited (5/hour), 10-minute expiry. Revocation supported via `revoked_at` column.

**Credential Management**
- All API keys in Keychain. Encrypted file fallback (`.cloud_api_key_*.enc`) for launchd headless restarts.
- 3-tier partitioning enforced: `hestia.operational`, `hestia.sensitive`, `hestia.system` service names.
- Double encryption (Fernet + Keychain AES-256) confirmed in `credential_manager.py`.
- No hardcoded secrets found in codebase.

**Error Handling & Information Leakage**
- `sanitize_for_log(e)` imported in all 30 route modules. Used correctly in general `Exception` handlers.
- **Gap:** `workflows.py` passes `str(e)` directly to `JSONResponse` for `ValueError` handlers (9 instances). This leaks internal validation messages.
- Structured logger redacts API keys, bearer tokens, passwords via regex patterns.

**Attack Surface**
- Sandbox runner validates paths against allowlist. Blocked commands configured.
- Communication gate exists for external sends.
- Prompt injection: System prompts are code-defined, not user-controllable. Tool calls validated against registry.
- No CSRF risk (JWT bearer auth, not cookies).
- Self-signed TLS: acceptable for Tailscale-only access (private tailnet). Would need real certs for public exposure.
- WebSocket has auth timeout (10s), idle timeout (30min), message size limit (64KB), rate limit (60/min).

---

## CTO Audit
**Rating:** Strong

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| No vulnerability scanning | CI pipeline | Could miss known CVEs in dependencies | Add `pip-audit` to pre-push or CI |
| chromadb 1.4.0 behind 1.5.5 | `requirements.txt` | Potential breaking changes accumulating | Schedule upgrade with test validation |

### Findings

**Layer Boundaries**
- Clean separation confirmed. No upward imports from lower layers (security, logging, inference, memory) into higher layers (orchestration, execution, API).
- No circular dependencies detected.
- Manager pattern consistent across all 22 database modules: `models.py` + `database.py` + `manager.py` + `get_X_manager()`.

**Pattern Consistency**
- Logging: All 160 files use `get_logger()` with no arguments. One internal `HestiaLogger()` instantiation in `structured_logger.py:522` (the singleton factory itself — correct).
- LogComponent enum: 25 members covering all modules including WORKFLOW (recently added).
- BaseDatabase ABC: All 22 database classes extend it properly.
- Type hints: Broadly used across the codebase.
- Async/await: Consistent in I/O paths. No blocking calls detected in async handlers.

**Code Health**
- Zero `TODO`/`FIXME`/`HACK` comments in production code (only 1 `TODO:` in memory tagger as part of a prompt template, 1 comment about gradient parsing).
- No dead imports flagged.
- Config: YAML files in `hestia/config/` — inference, execution, memory, triggers, wiki, workflow, orchestration.
- 22 outdated packages (chromadb, fastapi, cryptography, grpcio among them). No known critical CVEs detected manually but automated scanning missing.

**LLM/ML Architecture**
- 4-tier routing (PRIMARY > CODING > COMPLEX > CLOUD) with keyword-pattern matching.
- Council dual-path: cloud active = parallel gather, cloud off = SLM-only. All failures silently fall back.
- O2 fast-path bypass for short messages (<8 words) saves 80-150ms.
- Agent orchestrator with confidence gating and kill switch (`orchestration.yaml`).

**Performance & Scalability**
- SQLite with WAL mode for concurrent access in workflows and trading databases.
- ChromaDB used for vector store with separate collections (memory + principles).
- In-memory singletons acceptable for single-user architecture.
- `limit_max_requests: 50000` with launchd auto-restart.
- No N+1 query patterns detected in route handlers (managers handle batching).

---

## CPO Audit
**Rating:** Acceptable

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| 3 empty Button closures | `macOS/Views/Explorer/FilePreviewArea.swift:125`, `macOS/Views/Command/ActivityFeed.swift:48`, `macOS/Views/Research/ResearchView.swift:467` | Buttons render but do nothing when clicked | Wire up actions or remove |
| No NetworkMonitor usage on iOS | `Shared/` Views | iOS has no offline handling | Add offline state to iOS views |

### Findings

**API Usability**
- 252 endpoints across 30 route modules. Well-organized by domain.
- Swagger docs available at `/docs`.
- Consistent error envelope in most routes (except workflows — see CISO findings).
- Response schemas use Pydantic models with validation.

**Feature Completeness**
- Trading module live with 4 bots (BTC/ETH/SOL/DOGE) on Coinbase. Mean Reversion strategy active.
- Workflow orchestrator P0 complete (DAG engine, SSE streaming, canvas).
- All three agents (Hestia/Artemis/Apollo) functional with confidence-gated routing.
- iOS refresh: 3-tab app (Chat, Command, Settings), voice input, TestFlight pipeline.

**UI Wiring Health**

*Layer 1 — Hardcoded Values:* Color usage in Views is clean — all use design system tokens (`.textPrimary`, `.textSecondary`, `.textTertiary`, `MacColors.*`). No raw hex colors in View files. DesignSystem components use `.white` which is acceptable for glass effects.

*Layer 2 — Component Cross-Reference:* macOS has 15 APIClient extensions covering most backend modules. iOS (Shared) has 6 APIClient extensions — significantly fewer. Major backend subsystems without iOS API client wiring: Trading, Research, Learning, Memory, Health, Inbox, Files, Outcomes, Workflows, Investigate.

*Layer 3 — Error & Offline Behavior:* ViewModels consistently implement `isLoading` and `errorMessage` patterns. Catch blocks surface errors to UI (not silently swallowed). macOS has `OfflineBanner.swift` and `NetworkMonitor` integration. iOS has `NetworkMonitor` in `ContentView.swift` and `HestiaApp.swift` but no `OfflineBanner` equivalent visible.

*Layer 4 — Backend Endpoint Gaps:* iOS connects to ~40 of 252 endpoints (16%). This is expected — iOS is a 3-tab focused app (Chat, Command, Settings) while macOS is the full desktop experience. The gap is by design, not a bug.

**3 Dead Buttons (confirmed):**
1. `FilePreviewArea.swift:125` — "More" menu button, no action
2. `ActivityFeed.swift:48` — feed item button, no action
3. `ResearchView.swift:467` — search button in compact mode, no action

---

## CFO Audit
**Rating:** Strong

### Assessment
- **Infrastructure costs:** Near-zero. Mac Mini M1 is owned hardware. Ollama runs free local models. Cloud API spend is usage-based (Anthropic/OpenAI) with smart routing to minimize cloud calls.
- **Resource allocation:** Last 3 sprints focused on highest-value work: trading module (live capital), iOS refresh (user-facing), workflow orchestrator (platform capability). Good prioritization.
- **ROI:** Trading module generating real financial returns. iOS TestFlight pipeline enables rapid iteration. CLI complete and functional.
- **Maintenance burden:** 22 database modules is high count but pattern consistency makes them low-cost. Trading module is highest ongoing cost due to live-capital risk.

---

## Legal Audit
**Rating:** Acceptable

### Assessment
- **PII:** User profile data stored locally (Markdown files + SQLite). No cloud sync of PII. Cloud-safe context excludes IDENTITY and BODY.
- **Dependencies:** Python packages are mostly Apache-2.0/MIT/BSD. No GPL contamination detected in core dependencies (fastapi, chromadb, cryptography, ccxt, pydantic).
- **Crypto trading:** Personal use on Coinbase with proper API key management. No advisory services to third parties. Tax lot tracking present for compliance.
- **API ToS:** Coinbase API used within documented rate limits. Ollama is open-source. Cloud providers (Anthropic/OpenAI) used within standard API terms.
- **IP exposure:** Codebase is private GitHub repo. No open-source publication risk.

---

## Simplification Opportunities
| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| agents.py + agents_v2.py coexistence | Both registered in server.py, 20 endpoints total | Sunset v1 once v2 is stable | Low | Reduces confusion and endpoint count |
| 22 database modules all follow same pattern | Each has ~80-150 lines of boilerplate | Consider a code generator or shared mixin for common CRUD | Medium | Reduces drift risk |
| Config YAML files (7 files) | Separate files per module | Could merge into single `hestia.yaml` with sections | Low | Easier to manage |

---

## Adversarial Critique — "What Will We Regret?"

### 3 Most Load-Bearing Decisions

**1. Single-Server SQLite Architecture (ADR-002, ADR-037)**

*Steel-man:* For a single-user personal assistant on a Mac Mini, SQLite is ideal — zero-config, fast, reliable, backed up with Time Machine. No need for PostgreSQL/Redis overhead.

*Attack:*
- **Premise:** "Single user forever." If family members (the `user_id` columns suggest multi-user readiness) actually start using it, SQLite write contention becomes real.
- **Hidden cost:** 22 separate SQLite database files. No cross-database transactions. No unified backup/restore.
- **Counter-argument:** A single PostgreSQL instance would give you transactions across all modules, proper connection pooling, and a migration framework (Alembic). The migration cost grows with every new module.

**Verdict: WATCH** — Holds for single user. If multi-user materializes, migration to PostgreSQL becomes urgent. Trigger: more than 1 active user.

**2. In-Memory Singletons for Managers (Manager Pattern throughout)**

*Steel-man:* Clean factory pattern. Single process = single instance. No coordination needed. Fast.

*Attack:*
- **Premise:** "Single process forever." Worker recycling (`limit_max_requests: 50000`) already causes state loss. If you ever need horizontal scaling, every singleton is a rewrite.
- **Hidden cost:** Manager initialization order matters (some depend on others). Server startup is a carefully ordered sequence. Adding new managers requires touching `server.py` lifecycle.
- **Time horizon:** M5 Ultra Mac Studio could support multiple workers.

**Verdict: VALIDATED** — For personal assistant scale, this is correct. The M5 upgrade doesn't change the single-user model.

**3. Monolith Architecture (everything in one Python process)**

*Steel-man:* Single deployment unit. Simple debugging. No service mesh. All code changes deploy atomically.

*Attack:*
- **Premise:** "Deployment simplicity > modularity." The trading module (running real capital) shares a process with the wiki generator and voice journal. A bug in wiki article generation could theoretically affect trading bot stability.
- **Hidden cost:** The bot service already runs as a separate process (`bot_service.py` via launchd). This suggests the monolith is being decomposed organically when stakes are high enough.
- **Counter-argument:** Trading bots should run in complete isolation from the chat/wiki/memory stack. A crash in any of the 22 modules shouldn't risk trading operations.

**Verdict: WATCH** — The bot_service.py separation is the right instinct. Consider isolating the entire trading module into its own process, not just the bot runner.

### Project-Level Strategic Challenges
- **Optimizing for breadth over depth.** 31 modules is impressive scope but each module is relatively thin. The trading module and workflow orchestrator are the highest-value — they could benefit from deeper investment.
- **Hardest capability to add in 6 months:** Multi-user. The `user_id` columns are scaffolding but auth, data isolation, and concurrent access patterns aren't proven.
- **Complexity accumulating fastest:** API routes (252 endpoints, 30 modules). Each new feature adds endpoints, models, and client extensions across Python + macOS + iOS.

---

## Consistency Issues
| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| Error sanitization in routes | `sanitize_for_log(e)` in logs, generic messages in responses | `str(e)` leaked to clients in ValueError handlers | `workflows.py` (9 instances) |
| Empty closures | All buttons should have actions | 3 `Button {} label:` instances | `FilePreviewArea.swift:125`, `ActivityFeed.swift:48`, `ResearchView.swift:467` |
| Logger convention | `logger = get_logger()` — no args | Correct everywhere (160 files) | None |
| BaseDatabase inheritance | All database classes extend BaseDatabase | Correct (22/22 classes) | None |

---

## Documentation Currency
| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Minor drift | Says "250 endpoints" (actual: 252), "3050 tests" (actual: 3054), "104 test files" (actual: 97 backend + 7 CLI = 104 — matches if CLI counted). Missing WORKFLOW from LogComponent list (25 total, doc says 23). |
| api-contract.md | Not verified line-by-line | 2263 lines, comprehensive |
| Decision log | Current | 44 ADRs, latest is ADR-042 (Agent Orchestrator, 2026-03-16). No ADR for trading go-live (Sprint 27). |
| Agent definitions | Not audited this pass | N/A |
| Skill definitions | Active | Skills match current patterns |

---

## Workspace Hygiene
- **Untracked files:** `hestia/data/` (encrypted API key fallbacks — should be in `.gitignore`), 3 HTML mockup files in `docs/superpowers/specs/`, 2 docs in `docs/discoveries/` and `docs/plans/`
- **Stale TODOs:** 0 in production code
- **Archive candidates:** `docs/audits/` has 13 audit files — consider archiving audits older than 30 days
- **`.DS_Store` in docs/:** Should be in `.gitignore`

---

## Summary
- **CISO:** Acceptable — Solid credential management, JWT auth, sandboxing. Fix the 9 `str(e)` leaks in workflows routes.
- **CTO:** Strong — Exemplary pattern consistency across 22 modules. Clean layer boundaries. Add vulnerability scanning.
- **CPO:** Acceptable — iOS is intentionally focused (16% endpoint coverage). 3 dead buttons need cleanup. macOS is comprehensive.
- **CFO:** Strong — Near-zero infrastructure cost. Resource allocation targeting highest-value work.
- **Legal:** Acceptable — No GPL contamination. PII handled locally. Trading is personal use.
- Critical issues: 2 (error leakage in workflows, no vulnerability scanning)
- Simplification opportunities: 3
- Consistency violations: 2
- Documentation drift: 3 items (endpoint count, test count, LogComponent count)
