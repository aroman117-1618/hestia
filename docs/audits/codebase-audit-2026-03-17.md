# Codebase Audit: Hestia
**Date:** 2026-03-17
**Sprint Context:** Post-Sprint-17 (per-agent model specialization + reasoning streaming). Uncommitted Sprint 17.5 work (Memory Browser + Learning Metrics UI) in working tree.
**Auditor:** CISO / CTO / CPO panel
**Overall Health:** Healthy

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Exceptionally consistent manager pattern across all 20+ modules. Clean layer hierarchy with zero upward import violations detected. 186 endpoints across 27 route modules, all with consistent error envelopes. Full async aiosqlite throughout. Robust JWT auth with Keychain-backed secret storage. Comprehensive test coverage (2132 backend + 135 CLI). LearningScheduler provides 8-loop background lifecycle (monitor + memory + correction + distillation). Well-structured `BaseDatabase` ABC shared by all 16+ SQLite modules. | **Weaknesses:** `handler.py` god-object at 2492 lines (was 2510 in last audit — slight improvement). Config directory split: `config/` (2 files: `orchestration.yaml`, `triggers.yaml`) vs `hestia/config/` (6 files). `str(e)` used for conditional routing logic in `tasks.py` (not leaked but still a smell). `proactive/policy.py` calls blocking `subprocess.run()` inside methods called from async context. `inference/` module missing `models.py` (inconsistent with manager pattern). CLAUDE.md has multiple stale counts. |
| **External** | **Opportunities:** Sprint 17.5 Memory Browser adds visualization of importance scores — high user value. Agent definition files don't reference specific test counts or LogComponent values — could be enriched. `agents.py` (V1) could be sunset now that V2 is mature. `sanitize_for_log` lives in `hestia.api.errors` — moving it to `hestia.logging` would eliminate the one layer boundary smell. `config/orchestration.yaml` could move to `hestia/config/`. | **Threats:** 16 files modified/untracked from parallel worktree session not yet committed — risk of divergence. `qwen3:8b` and `deepseek-r1:14b` need manual pull on Mac Mini post-deploy (not automated). In-memory rate limiting (invite, session) won't survive process restart or multi-worker scale. Non-streaming `handle()` path doesn't emit reasoning events — iOS fallback REST clients miss reasoning entirely. |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues
None.

### Findings

**JWT Implementation**
- Algorithm: HS256. Acceptable for single-server personal use. RS256 would be better if multi-server scaling ever occurs, but current architecture doesn't warrant it.
- Secret storage: Keychain-backed with fallback to env var (`HESTIA_JWT_SECRET`) then in-memory generation. The in-memory fallback on Keychain failure is correct but tokens issued before vs after a restart would be incompatible — logged at WARNING.
- Token expiry: 90 days. Long but intentional (convenience over strict security for personal use).
- Invite tokens: 10-minute expiry. Correct.
- Rotation: No rotation mechanism. Mitigated by device revocation per ADR-034.

**Route Protection**
- 186 REST endpoints. Auth-protected route dependencies appear on 169 of 186 endpoints.
- Unprotected by design: `/v1/ping`, `/v1/health`, `/v1/ready` (3 health checks), `/v1/auth/register` (initial device enrollment), `/v1/auth/register-with-invite` (invite flow). These are correct and documented.
- WebSocket `/v1/ws/chat`: Uses `get_optional_device_token` — fails open if no token. This is a soft concern: the WebSocket path has weaker auth than the REST path. Worth hardening to required token.

**Credential Management**
- No hardcoded secrets found across the entire codebase.
- Three-tier Keychain partitioning enforced: `operational/sensitive/system` credential namespaces.
- Double encryption (Fernet + AES-256 Keychain) implemented in `hestia/security/credential_manager.py`.

**Error Handling & Information Leakage**
- `sanitize_for_log(e)` from `hestia.api.errors` present in 26/28 route files.
- `tasks.py:341,426,514`: `error_msg = str(e)` used for `"not found" in error_msg.lower()` routing — NOT leaked to HTTP response. Low risk, but `type(e).__name__` check against ValueError subclasses would be cleaner.
- `auth.py:296`: `import logging` (stdlib) instead of `from hestia.logging import get_logger`. Minor — only used in the exception handler for revocation check fail-open path.
- HTTP responses: All use generic messages. No stack traces, internal paths, or exception details observed in `detail=` fields.
- Routes leaking user-controlled values in `detail=` (e.g., `orders.py:312`: `detail=f"Order not found: {order_id}"`): these echo back user-provided IDs. Not sensitive, but inconsistent with the "no detail=str(e)" convention.

**Attack Surface**
- CORS: `localhost:3000,8080,8443` hardcoded defaults. Clean. Customizable via `HESTIA_CORS_ORIGINS` env var.
- Communication gate: `ExternalCommunicationGate` in `hestia/execution/gate.py` requires explicit approval for external calls. Correctly enforced through `ToolExecutor`.
- Prompt injection: No sanitization layer between user input and LLM prompt. Acceptable for personal-use assistant where the user is the attacker. Would need a content filter layer for multi-tenant scenarios.
- SSRF: `investigate/` module fetches arbitrary URLs. Mitigated by CommGate approval flow.
- Self-signed TLS on port 8443: accepted known trade-off for local deployment.
- `proactive/policy.py`: `subprocess.run()` with `["defaults", "read", ...]` and `["plutil", ...]`. Uses fixed command arrays (no shell=True). Path validation present for DND assertions file. Clean.

**Verdict:** Acceptable. No critical vulnerabilities. Primary residual risk is the fail-open revocation check (documented in ADR-034) and the WebSocket auth gap.

---

## CTO Audit
**Rating:** Acceptable

### Critical Issues
None.

### Findings

**Layer Boundaries**
- Zero upward imports detected. `hestia/memory/`, `hestia/inference/`, `hestia/security/`, `hestia/logging/` contain no imports from `hestia.api` or `hestia.orchestration`.
- `hestia/learning/` correctly imports from `hestia.research.models` (lateral, same tier) — not an upward import.
- `sanitize_for_log` lives in `hestia.api.errors` but is called from routes only. The import direction is correct but its _location_ is wrong — it's a utility that belongs in `hestia.logging` or `hestia.errors`. No functional harm, but creates mild conceptual friction.

**Pattern Consistency**
- Manager pattern (`models.py` + `database.py` + `manager.py` + `get_X_manager()`) held by: memory, health, explorer, tasks, orders, research, learning, outcomes, inbox, files, apple_cache. Full compliance.
- `inference/` module has only `client.py` + `router.py` — no `models.py`. The inference models are scattered (response types in `client.py`, router config in `router.py`). Minor but inconsistent.
- `get_council_manager()` is synchronous — correctly documented in CLAUDE.md, but breaks the async factory pattern expected everywhere else.
- Logging: `logger = get_logger()` pattern followed consistently. No instances of `HestiaLogger(component=...)` or positional args found.
- Async/await: All database operations use `aiosqlite`. Apple tool CLIs use `asyncio.subprocess` wrappers. Only exception is `proactive/policy.py:_check_focus_mode()` which calls `subprocess.run()` synchronously. This method is called from the briefing pipeline — any async caller blocks the event loop for up to 2 seconds. **Fix**: wrap in `asyncio.get_event_loop().run_in_executor(None, self._check_focus_mode)`.

**Code Health**
- `handler.py`: 2492 lines, 22+ methods. Reduction from 2510 is cosmetic. This remains the largest single debt item. The session handoff identifies this but defers it. Suggested decomposition: `ContextGatherer`, `ToolPipeline`, `ResponseSynthesizer`, `StreamingCoordinator` — each testable in isolation.
- Config directory split: `config/orchestration.yaml` and `config/triggers.yaml` live at project root while all other config lives in `hestia/config/`. Moved during agent orchestrator work. No functional impact but causes confusion when grepping. One-line fix in `scheduler.py` and `handler.py` import paths.
- Dead code: None found. The V1 agents API (`agents.py`) still registers its 10 endpoints alongside V2 — intentional coexistence. But V1 has been stable for months; a sunset timeline should be set.
- `agents/config_loader.py:154,219,251` and `agents/file_watcher.py:147,152`: use `f"...: {e}"` in logger calls (raw exception message). These are in non-API layers where `sanitize_for_log` isn't appropriate — `type(e).__name__` is the documented convention here, but it's not followed. The risk is logging internal file paths or config values at WARNING/ERROR level.

**LLM/ML Architecture**
- Inference routing (3-tier: PRIMARY → CODING → COMPLEX → CLOUD) is clean. `route_for_agent()` added in Sprint 17 for per-agent model preferences. Correct design.
- Council dual-path: cloud → `asyncio.gather()` 4 roles; local → SLM only. O2 fast-path bypass (<8 words, no trigger keywords) skips SLM entirely. Both paths wrapped in try/except with silent fallback.
- Sprint 17 reasoning streaming: `<think>` block parser intercepts DeepSeek R1 tokens mid-stream. Routes as `reasoning` events. Does NOT apply to the non-streaming `handle()` path — REST clients get no reasoning events. This is a known gap noted in session handoff.
- Temporal decay: `adjusted = raw_score * e^(-λ * age_days) * recency_boost`. Per-chunk-type λ in `memory.yaml`. Correct.
- Memory Lifecycle (Sprint 16): importance scorer, consolidator, pruner all scheduled via `LearningScheduler`. Zero-LLM. Clean design.

**Performance & Scalability**
- SQLite single-connection-per-database pattern (`BaseDatabase`). Correct for single-server personal use. `aiosqlite` serializes writes, preventing corruption. WAL mode would help concurrency but isn't needed yet.
- ChromaDB: No collection size caps observed. At scale, embedding dimensions × chunk count could become a memory pressure issue. Not urgent for personal use.
- Handler `asyncio.gather()` for memory + profile + council pre-inference. Saves 150-350ms. Correct.
- In-memory rate limiting (invite: 5/hour, session auto-lock): resets on process restart. Documented trade-off.
- N+1 queries: No pattern detected. Managers batch fetch with WHERE IN clauses where appropriate.

**Verdict:** Acceptable. `handler.py` god-object is the primary structural debt. `_check_focus_mode()` sync-in-async is the primary runtime risk. Both are known and bounded.

---

## CPO Audit
**Rating:** Strong

### Critical Issues
None.

### Findings

**API Usability**
- 186 REST + 1 WebSocket = 187 total endpoints across 27 route modules. Well-organized by domain.
- Consistent error envelope: `{"error": "code", "message": "text"}` across all routes.
- Swagger docs at `/docs`. Pydantic schemas in `api/schemas/` (16 modules).
- Some routes leak user-controlled IDs in error `detail=` fields (e.g., `orders.py:312`, `agents_v2.py:114,179`): `detail=f"Order not found: {order_id}"`. Consistent with UX guidance but diverges from the "no detail=str(e)" convention — these echo back user data not exception internals. Low risk.

**Feature Completeness**
- All three agents (Tia/Mira/Olly) functional. Sprint 17 adds per-agent model specialization — Artemis→DeepSeek-R1-14B, Apollo→Qwen3-8B. Well-designed.
- Reasoning streaming live in streaming path for both CLI and iOS/macOS.
- Sprint 17.5 Memory Browser (in working tree, uncommitted): backend routes in `memory.py` + `research.py`, macOS views, 12 tests. ~60% complete based on file count. Not yet committed.
- All workstreams claimed complete in CLAUDE.md are verified complete: WS1-4, CLI 1-5, UI Phases 1-4, Sprints 1-17.

**Documentation Quality**
- CLAUDE.md is comprehensive (700+ lines) but has multiple stale counts (see Documentation Currency section).
- Decision log last meaningful entry is ADR-042 (Agent Orchestrator). No ADR for Sprint 16 (Memory Lifecycle), Sprint 17 (Agent Model Specialization), or Sprint 17 (Reasoning Streaming). Three major architectural decisions are undocumented.
- `docs/superpowers/` directory has 9 files — purpose unclear, not referenced in CLAUDE.md. Potential doc sprawl.
- API contract (`docs/api-contract.md`) says "132 endpoints across 22 route modules" — actual is 187 endpoints, 27 route modules. Significantly stale.

**Verdict:** Strong. All features functional. Documentation drift is the main CPO concern.

---

## Simplification Opportunities

| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| Config directory split | `config/` (2 files) + `hestia/config/` (6 files) | Move `config/orchestration.yaml` + `config/triggers.yaml` into `hestia/config/`. Update 2 import paths. | 30 min | Low — removes confusion |
| `sanitize_for_log` location | Lives in `hestia.api.errors` | Move to `hestia.logging` (or `hestia.errors`). Update 26 imports. | 1 hour | Low — better layer alignment |
| V1 agents API | `agents.py` (10 endpoints) coexists with `agents_v2.py` (10 endpoints) | Set 2-sprint sunset on V1. Add deprecation header to V1 responses. Remove after. | Low | Medium — reduces surface area |
| `handler.py` decomposition | 2492 lines, 22+ methods | Extract `ContextGatherer`, `ToolPipeline`, `StreamingCoordinator`. Each ~300-500 lines. | High | High — testability, maintainability |
| `_check_focus_mode()` async fix | Blocking `subprocess.run()` in sync method called from async | Wrap in `run_in_executor`. 5-line change. | Low | Medium — prevents event loop blocking |

---

## Adversarial Critique — "What Will We Regret?"

### 7.1 The 3 Most Load-Bearing Decisions

1. **SQLite as the only structured store** (ADR-001 era, every sprint since). 11+ independent `.db` files, all using `BaseDatabase` ABC. Every new feature gets its own SQLite file.
2. **Single-server personal AI** — all architecture optimizations (in-memory rate limits, single SQLite connection, single-process uvicorn) assume one user, one process, one machine.
3. **ChromaDB as the embedding store** — all vector search, memory retrieval, and semantic similarity (including consolidation's 0.90 dedup threshold) depends on ChromaDB remaining healthy.

---

### Decision 1: SQLite Fragmentation

**Steel-man:** SQLite is zero-infrastructure, zero-ops, crash-safe, and the correct choice for a single-user application on Apple Silicon. 11 independent `.db` files give clean separation of concerns. `BaseDatabase` ABC provides a uniform lifecycle. No network calls, no connection pooling complexity, no external process.

**Attack:**

*Premises:* The fragmentation assumes each domain's data is truly independent. That's increasingly false. `learning/scheduler.py` imports from `research/manager.py`. `outcomes/` feeds `learning/`. `memory/` feeds `learning/`. `research/` feeds `orchestration/handler.py`. The data model is growing relational across nominal module boundaries.

*Hidden costs:* Cross-domain queries require loading multiple managers, doing in-process joins, and coordinating transactions across connections. The `_gather_metrics()` in `scheduler.py` queries `memory`, `research`, `outcomes`, and `learning` databases independently. If any connection is slow, the entire metrics pass serializes. There's no atomic transaction that touches two `.db` files — if an `OutcomeDistiller` write succeeds but the corresponding `research` principle write fails, there's no rollback.

*Time horizon:* The Memory Browser (Sprint 17.5) is the first feature that needs to present data from multiple domains simultaneously (memory chunks + importance scores + consolidation history + research facts). The current approach requires the browser to call 3-4 separate managers. If the next 3-4 sprints follow this pattern, the inter-module data fetching code will grow faster than the features themselves.

*Alternative:* A single `hestia.db` with all tables and a proper schema migration system (Alembic). Still SQLite, zero new infrastructure. One connection, real cross-table joins, real transactions. `BaseDatabase` becomes a schema contributor, not a lifecycle owner. Migration: create a migration script that copies all 11 `.db` files into one. 2-3 days of work.

**Counter-argument:** Hestia would be easier to reason about with a single database. The module boundary abstraction could be preserved at the manager/query layer. Cross-domain features (Learning, Memory Browser) would be trivially implementable. The "separate files = separate concerns" pattern is a good idea that has outlived its usefulness as the system became more integrated.

**Verdict:** WATCH. Defensible today. The trigger for reassessment is when cross-domain queries require more than 2 manager imports in a single method. We're already at 4 in `_gather_metrics()`. Recommend migrating to a single `hestia.db` during a stability sprint before the Autonomy era (Sprint 19+).

---

### Decision 2: Single-Server Personal AI (Architecture-Wide)

**Steel-man:** This is a personal AI assistant for one user on one machine. Multi-user, multi-server complexity would be pure waste. In-memory rate limits are fine when there's no horizontal scale. Single JWT secret is correct. The explicit single-user assumption keeps the entire codebase simpler and faster.

**Attack:**

*Premises:* The "single user" assumption is baked into every layer — `DEFAULT_USER_ID` appears throughout the codebase, device-scoped JWT is the only auth concept, `data/user/` is a single path. But the outcomes table stores `user_id`. The `devices` table stores multiple device IDs. The architecture is quietly half-multi-user already — some features scoped, some not.

*Hidden costs:* When Andrew wants to give Hestia to a family member or deploy a second instance, the refactoring surface is enormous. Every manager, database schema, and route handler has implicit `DEFAULT_USER_ID` assumptions. The cost of adding a second user is not incremental — it requires auditing the entire codebase.

*Time horizon:* The roadmap mentions "family-scale readiness" (ADR-042, routing audit log). Sprint goals mention multi-device support. There's an explicit future intent to scale beyond one user. The longer the single-user assumption stays embedded, the more expensive the eventual refactor.

*Alternative:* Enforce user_id as a required, validated parameter everywhere — even for the current single user. Make `DEFAULT_USER_ID` a constant that's passed explicitly rather than hardcoded. This is a cosmetic refactor (no behavior change for one user) that makes the multi-user path dramatically cheaper.

**Verdict:** WATCH. No urgency. Trigger: when a second user (family, friend) is added. At that point, the refactor becomes a critical path blocker. Recommend a 1-sprint hardening exercise to pass `user_id` explicitly through all manager calls before the Autonomy era.

---

### Decision 3: On-Demand Knowledge Graph Extraction (ADR-041)

**Steel-man:** LLM-powered triplet extraction (fact_extractor.py) is expensive (~2-3 inference calls per extraction). Running it on every chat message would add 2-6 seconds per turn. The "on-demand" approach (explicit POST to `/v1/research/facts/extract`) avoids this overhead entirely. The graph grows only when the user explicitly requests extraction.

**Attack:**

*Premises:* The value of a knowledge graph scales with density. A graph that grows only via explicit user action will always be sparse relative to what was actually said. Most users (including Andrew) will not manually trigger extraction after meaningful conversations. The expected steady-state is a graph that's weeks behind the conversation history.

*Hidden costs:* The principle distillation pipeline (`OutcomeDistiller`, Sprint 17) is designed to surface patterns from outcomes. But if the knowledge graph is sparse, the principles derived will be shallow. The learning loop's value proposition depends on the graph being populated — which depends on extraction being triggered — which depends on the user caring enough to do it.

*Alternative:* Background extraction on a configurable schedule (nightly, post-session). The `LearningScheduler` already runs 8 async loops. Adding a 9th `_graph_extraction_loop()` that processes the last N conversations not yet extracted would be ~50 lines of new code. Cost: 1 inference call per 10-20 conversations, running overnight when idle.

**Counter-argument:** The on-demand model gives the user control over what enters the graph. But the OutcomeDistiller already runs without user control. The distinction is inconsistent. If distillation is safe to run autonomously, extraction is too.

**Verdict:** RECONSIDER. The on-demand constraint was correct at the time (Sprint 8, before LearningScheduler existed). Now that there's an 8-loop scheduler architecture, the rationale is obsolete. Recommend adding `_graph_extraction_loop()` to `LearningScheduler` — nightly, processes last 20 conversations not yet extracted, guarded by the same `DEFAULT_USER_ID` pattern.

---

### 7.3 Project-Level Strategic Challenges

**What is the project optimizing for that it shouldn't be?**
Feature breadth over feature depth. Each sprint adds a new module (research, learning, outcomes, inbox, files, apple_cache) with its own database, manager, and endpoints. The architecture is coherent but the user-facing value of each module is thin relative to the effort. Sprint 17.5 (Memory Browser) is the first feature that surfaces existing data to the user in a novel way rather than adding new infrastructure. More of this.

**What capability will be hardest to add in 6 months?**
True background autonomy — Hestia proactively taking multi-step actions without a user request. The current architecture assumes request-response: a user sends a message, the handler processes it. The orders/tasks system is the closest to autonomy, but it still requires explicit user scheduling. Adding "Hestia notices X and does Y without being asked" requires a new event-driven pipeline that cuts across the entire orchestration layer. The `AgentOrchestrator` (ADR-042) provides the routing primitives but not the trigger substrate.

**Where is complexity accumulating fastest?**
`hestia/learning/`. Sprint 15 added MetaMonitor, MemoryHealthMonitor, TriggerMonitor. Sprint 16 added ImportanceScorer, Consolidator, Pruner. Sprint 17 added CorrectionClassifier, OutcomeDistiller. The scheduler now runs 8 loops. Each loop is well-tested individually but the interactions between them (what happens when consolidation runs immediately after importance scoring? what if pruning removes a memory that a principle references?) are untested. This is where the next regression will hide.

**What would a rewrite do differently?**
A greenfield Hestia would start with a single database, user_id as a first-class concept, and event-driven primitives for proactive behavior. The module-per-database pattern is the biggest structural choice that a rewrite would reverse. Everything else — the manager pattern, the async architecture, the council dual-path, the temporal decay — is solid and would be preserved.

---

## Cohesion & Consistency

| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| Error logging | `type(e).__name__` in non-API layers | `f"...: {e}"` (raw exception) | `agents/config_loader.py:154,219,251`, `agents/file_watcher.py:147,152` |
| Async factory | `async def get_X_manager()` | `get_council_manager()` is synchronous | `hestia/council/manager.py` |
| Module structure | `models.py + database.py + manager.py` | `inference/` has no `models.py` | `hestia/inference/` |
| Config location | All config in `hestia/config/` | `orchestration.yaml`, `triggers.yaml` in root `config/` | `config/` |
| Logger import | stdlib `logging` never used in application code | `import logging` used once | `auth.py:296` (in except block only) |
| Task str(e) routing | `type(e).__name__` check | `str(e).lower()` content-matching | `tasks.py:341,426,514` |

---

## Documentation Currency

| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Stale | Test count line 112: claims "2279 tests (2144 backend + 135 CLI), 64 test files (57 backend + 7 CLI)" — actual is 2132 backend + 135 CLI = 2267 total, 59 backend + 7 CLI = 66 test files. Project structure line 262: "1611 tests, 36 files" — severely stale (Sprint 1-era). API Summary header (line 271): says "181 endpoints" — actual is 186 REST + 1 WebSocket = 187. Tech stack table (line 95) says "~180 endpoints" — same drift. No ADRs for Sprint 16 (Memory Lifecycle), Sprint 17 (Agent Model Specialization), Sprint 17 (Reasoning Streaming). |
| api-contract.md | Stale | Says "132 endpoints across 22 route modules" (last updated 2026-03-03). Actual: 187 endpoints, 27 route modules. ~55-endpoint gap. Most stale document in the project. |
| hestia-decision-log.md | Stale | Last entry: ADR-042 (Agent Orchestrator, Sprint 14). Missing: Sprint 15 MetaMonitor/TriggerMonitor (no ADR), Sprint 16 Memory Lifecycle (no ADR), Sprint 17 per-agent model specialization (no ADR), Sprint 17 reasoning streaming (no ADR). 4 significant architectural decisions undocumented in 3 sprints. |
| Agent definitions | Acceptable | Files exist for all 8 agents. No test counts or LogComponent enums referenced — fine for their purpose. No critical staleness detected. |
| Skill definitions | Current | Present in `.claude/skills/`. No staleness issues found. |
| SESSION_HANDOFF.md | Current | Accurately documents Sprint 17 state including the 16 uncommitted files from parallel session. Trustworthy. |
| docs/superpowers/ | Ambiguous | 9 files not referenced in CLAUDE.md or any docs index. `plans/2026-03-17-sprint-16-memory-lifecycle.md` and `plans/2026-03-17-sprint-17-learning-closure.md` duplicate content in `docs/plans/`. Purpose unclear — archive or document. |

---

## Workspace Hygiene

- **Uncommitted Sprint 17.5 work:** 16 files (8 modified, 8 untracked) from parallel worktree session. Backend memory browser routes, macOS Memory Browser views, test files. Not yet committed. Session handoff warns against committing blindly. Status: actively in-flight, not abandoned.
- **Stale TODOs:** 1 benign comment in `agents/config_loader.py:345` (gradient format parsing note). Not actionable.
- **Untracked sprint planning docs:** `docs/discoveries/memory-lifecycle-importance-consolidation-pruning-2026-03-17.md`, `docs/plans/sprint-16-memory-lifecycle-audit-2026-03-17.md`, `docs/superpowers/plans/2026-03-17-sprint-16-memory-lifecycle.md` — three variants of similar planning content for Sprint 16. Should be committed or cleaned up.
- **Archive candidates:** `docs/plans/` has 20+ files from completed sprints (Sprints 1-12). Not urgent but directory is growing. `docs/discoveries/` similarly dense.
- **Debug artifacts:** None found.
- **`claude-config-refresh-plan.md`:** Still at project root (noted in previous audits). Should move to `docs/plans/` or archive.

---

## Summary

- **CISO:** Acceptable — No critical vulnerabilities. Credentials in Keychain, error sanitization consistent in routes, CommGate enforced. WebSocket auth gap (optional token) is the only new finding worth closing.
- **CTO:** Acceptable — Zero layer boundary violations, excellent pattern consistency. `handler.py` god-object remains the top structural debt. `_check_focus_mode()` blocks the event loop (fix is 5 lines). Config directory split is low-priority cleanup.
- **CPO:** Strong — 187 endpoints, all features functional through Sprint 17. `api-contract.md` is significantly stale (55-endpoint gap). Decision log missing 4 ADRs from last 3 sprints.
- **Critical issues:** 0
- **Significant issues:** 5 (handler size, _check_focus_mode blocking I/O, api-contract drift, missing ADRs, SQLite fragmentation watch)
- **Simplification opportunities:** 5
- **Consistency violations:** 6
- **Documentation drift:** 7 items across 4 documents
- **Strategic watch items:** 2 (SQLite fragmentation, single-user assumption hardening)
- **Strategic reconsider:** 1 (knowledge graph extraction should be scheduled, not on-demand)
