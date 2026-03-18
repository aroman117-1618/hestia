# Codebase Audit: Hestia
**Date:** 2026-03-18
**Sprint Context:** Post-Sprint 23 (Trading: position tracker, price validator, execution pipeline). Sprints 21-23 landed since last audit. Notifications relay (Sprint 20C WS6) complete. Research graph expansion (Sprint 20B WS5) complete.
**Auditor:** CISO / CTO / CPO panel
**Overall Health:** Healthy

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Exceptionally consistent manager pattern across 31 modules. Clean layer hierarchy with zero upward import violations. 212 endpoints across 29 route modules, all with consistent error envelopes and sanitize_for_log usage (172 occurrences across all 28 route files). Full async aiosqlite throughout. Robust JWT auth with Keychain-backed secret storage and constant-time comparison. 2465 total tests (2330 backend + 135 CLI). Trading module arrived with 180 tests from day one -- high-discipline test-first development. BaseDatabase ABC shared by 16+ SQLite modules. Prompt injection detection in validation.py with regex pattern blocking. | **Weaknesses:** handler.py god-object now at 2632 lines (up from 2492 in last audit -- growing, not shrinking). CLAUDE.md has pervasive count drift (see Documentation Currency). Learning scheduler accesses private _database and _principle_store attributes of other managers (encapsulation breach at 3 call sites). proactive/policy.py still uses blocking subprocess.run() from async context (2 calls, 2s timeout each). Trading module has no ADR in the decision log. .env file contains plaintext Anthropic API key (gitignored but present on disk). |
| **External** | **Opportunities:** Trading strategies (grid, mean_reversion) and data feed (WebSocket, indicators) already built -- Sprint 22 is more complete than SPRINT.md suggests. Notifications module (8 files, 6 endpoints) could be documented in CLAUDE.md. agents.py V1 could be sunset now that V2 is mature. Could add public database property to OutcomeManager and public principle_store property to ResearchManager to fix encapsulation breach. | **Threats:** Trading module interacts with real money (Coinbase adapter exists). No ADR, no security review, no audit trail for the exchange adapter decisions. 135 macOS Swift files (up from 126) -- no corresponding test infrastructure. qwen3:8b and deepseek-r1:14b still need manual pull on Mac Mini. In-memory rate limiting won't survive restart. |

---

## CISO Audit
**Rating:** Acceptable

### Critical Issues

| Issue | Location | Risk | Recommendation |
|-------|----------|------|----------------|
| Plaintext API key in .env | .env line 1 | Medium -- gitignored but disk-resident. Any process with read access sees it. | Move to Keychain. Delete .env or reduce to non-secret config only. |
| Trading exchange adapter has no security review | hestia/trading/exchange/coinbase.py | High -- handles real financial credentials and order execution | Create ADR for trading security posture. Document Keychain key names, order signing, and risk boundaries. |
| Fail-open on revocation check | hestia/api/middleware/auth.py:293 | Low -- documented ADR-034 trade-off, logged at WARNING | Acceptable as-is. Monitor logs for repeated failures. |

### Findings

**JWT Implementation**
- Algorithm: HS256. Acceptable for single-server personal use.
- Secret: Keychain-backed with env var fallback, then in-memory generation. The in-memory fallback path means tokens issued before vs after restart are incompatible -- correctly logged at WARNING.
- Expiry: 90 days device tokens, 10-minute invite tokens. Appropriate.
- Constant-time comparison for setup secret (secrets.compare_digest): correct.
- Rate limiting on invite generation: 5/hour in-memory sliding window. Adequate.

**Credential Management**
- Keychain constants for Coinbase (coinbase-api-key, coinbase-api-secret) defined but not hardcoded values. Correct.
- No hardcoded API keys, passwords, or secrets found in Python source.
- .env file with plaintext Anthropic key is the one exception -- should be remediated.

**Error Handling and Information Leakage**
- sanitize_for_log(e) used consistently across all 28 route files (172 total occurrences).
- str(e) appears in tasks.py (3 occurrences) for conditional routing logic only -- NOT leaked to HTTP responses. Acceptable.
- orders.py:370 uses str(e).lower() for similar routing. Acceptable.
- No raw exception strings in HTTP response details found.

**Attack Surface**
- CORS: restricted to localhost origins (3000, 8080, 8443). Env-var configurable. Good.
- Allowed headers explicitly listed (no wildcard). Good.
- Self-signed TLS: appropriate for Tailscale-only access. Certificate pinning in iOS client would harden further.
- Prompt injection: 4 regex patterns in validation.py (ignore instructions, developer mode, jailbreak). Minimal but present. The investigate module adds a security preamble to analysis prompts. Inbox bridge has log-only monitoring for suspicious patterns.
- Communication gate in execution/gate.py: external communications require approval. Verified.
- Rate limiting: per-endpoint configs in middleware. Adequate for single-user.
- OWASP: No SQL injection risk (parameterized queries via aiosqlite). No XSS (API-only, no HTML rendering). SSRF risk exists in investigate/ URL fetching -- should validate/restrict destination URLs.

---

## CTO Audit
**Rating:** Acceptable

### Critical Issues

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| handler.py at 2632 lines | hestia/orchestration/handler.py | High -- growing, not shrinking. Testing, reasoning about changes, merge conflicts all scale with file size. | Extract command handling, tool execution, and streaming into separate modules. Target: under 800 lines per file. |
| Encapsulation breach in LearningScheduler | hestia/learning/scheduler.py:82,117,121,122 | Medium -- tight coupling between Learning, Outcomes, and Research internals | Add public accessor properties to OutcomeManager (database) and ResearchManager (principle_store, database). |
| Blocking subprocess in async context | hestia/proactive/policy.py:115,149 | Medium -- blocks event loop for up to 4 seconds total | Use asyncio.create_subprocess_exec() or loop.run_in_executor(). |
| Blocking file I/O in async route | hestia/api/routes/memory.py:728 | Low -- single with open() for YAML config read in async handler | Use aiofiles or run_in_executor(). |

### Findings

**Layer Boundaries**
- Zero upward import violations detected. The one near-violation (orchestration/agentic_handler.py importing hestia.api.errors.sanitize_for_log) is a cross-cut utility -- acceptable, though moving sanitize_for_log to hestia.logging would be cleaner.
- No circular dependencies found.
- 31 backend module directories. Clean separation of concerns.

**Pattern Consistency**
- Manager pattern (models + database + manager + get_X_manager()) adhered consistently.
- BaseDatabase ABC used by all SQLite modules.
- Logging: from hestia.logging import get_logger then logger = get_logger() -- no violations found.
- LogComponent enum: 23 values (CLAUDE.md says 22, missing NOTIFICATION which was added with Sprint 20C).
- Async/await: consistent throughout, except the proactive/policy.py subprocess calls noted above.
- Type hints: good coverage across all manager and route code examined.

**Code Health**
- Only 1 stale TODO in production code: hestia-cli/hestia_cli/repl.py:263 (Sprint 3C tier upgrade).
- No FIXME/HACK/XXX markers found in production code.
- No dead imports detected in spot checks.
- Config split: config/ (top-level, 2 files) vs hestia/config/ (6 files) is still inconsistent -- consolidation opportunity.

**LLM/ML Architecture**
- 4-tier model routing (PRIMARY to CODING to COMPLEX to CLOUD) working correctly per ADR-040.
- Council dual-path: cloud leads to parallel gather, local leads to SLM intent only. Failures wrapped in try/except with silent fallback. Correct.
- Temporal decay formula applied per-chunk-type with configurable lambda. Edge cases handled (facts/system never decay).
- Trading strategies (grid, mean_reversion) include proper indicator calculations (RSI, Bollinger bands via pandas-ta).

**Performance and Scalability**
- Single aiosqlite connection per database instance. Appropriate for single-user.
- No N+1 query patterns detected in spot checks.
- ChromaDB collections bounded by memory lifecycle (pruning over 60d, importance under 0.2).
- Parallel pre-inference pipeline (asyncio.gather for memory + profile + council) working correctly.
- SSE streaming for chat responses. WebSocket endpoint for CLI.

**Trading Module Assessment**
- 7 test files, 180 tests -- strong coverage for new module.
- Database uses WAL mode -- correct for concurrent reads during trading.
- Risk manager with kill switch, circuit breakers, position limits. Good safety layering.
- Paper adapter for testing before live trading. Correct approach.
- Missing: No ADR in decision log. No entry in docs/hestia-security-architecture.md.
- exchange/coinbase.py references Keychain constants but actual adapter implementation needs security review before live use.

---

## CPO Audit
**Rating:** Acceptable

### Critical Issues

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| API contract doc severely stale | docs/api-contract.md | Medium -- misleads new sessions. Claims 186 endpoints / 27 route modules. Actual: 212 / 29. | Update endpoint counts. Add Notifications (6), ws_chat, and new Learning endpoints (10 total, not 5). |
| CLAUDE.md count drift | CLAUDE.md multiple lines | Medium -- incorrect counts propagate to sub-agents and session context | Full count refresh needed (see Documentation Currency table below). |

### Findings

**API Usability**
- All routes use structured error envelopes: error code + human-readable message. Consistent.
- Swagger UI at /docs auto-generated from Pydantic schemas. Works.
- Rate limiting returns standard 429 with Retry-After header. Correct.
- Endpoint naming follows REST conventions (/v1/resource with CRUD verbs). Consistent.

**Feature Completeness**
- All planned sprints through 23 are implemented and tested.
- Trading Sprint 21 marked "TODO" in CLAUDE.md but is actually implemented with 180 tests. SPRINT.md may be more current.
- Notifications module fully functional but not documented in CLAUDE.md project structure or API summary table.
- Three agent modes (Tia/Mira/Olly) functional via V1 + V2 APIs.
- WebSocket chat (ws_chat) endpoint exists but not listed in API summary.

**Documentation Quality**
- Decision log: 42 ADRs, comprehensive. Missing ADR for trading module and notifications relay.
- CLAUDE.md: comprehensive but has accumulated count drift. Structure tree doesn't include notifications/.
- Agent definitions: accurate for their scope. Don't reference specific test counts (which is actually safer since counts change frequently).

---

## Adversarial Critique -- "What Will We Regret?"

### 7.1 Three Most Load-Bearing Decisions

1. **ADR-003: Single-Agent Architecture** (now extended by ADR-042: Agent Orchestrator)
2. **ADR-009: Keychain + Credential Manager** (security foundation)
3. **ADR-013: Tag-Based Memory with Temporal Decay** (extended by ADR-028, ADR-041)

### 7.2 Challenge Each Decision

#### Decision 1: Single-Agent to Orchestrated Multi-Agent (ADR-003 + ADR-042)

**Steel-man:** Started as single-agent for simplicity. As capabilities grew, added orchestrator with coordinator (Hestia) routing to specialists (Artemis, Apollo). Confidence gating prevents unnecessary specialist dispatch. Kill switch falls back to single-agent. On M1, common case (HESTIA_SOLO) has zero overhead.

**Attack:**
- **Premises:** Assumes that routing intent to the right specialist is a solved problem. But the routing is keyword-based heuristic (_matches_routing_patterns), not learned. As the system grows, the keyword list will become unwieldy or miss novel intents.
- **Hidden costs:** Every new capability must be manually classified into HESTIA_SOLO/ARTEMIS/APOLLO routing. The orchestrator adds complexity that only pays off when specialists genuinely outperform the coordinator -- which on M1 (single GPU, sequential model loading) means specialist dispatch is actually slower due to model swaps.
- **Time horizon:** On M5 Ultra with parallel GPU inference, this pays off. On M1, the orchestrator overhead rarely justifies itself except for clearly specialist tasks.

**Counter-argument:** A simpler approach -- drop the orchestrator entirely and use prompt-based mode switching. The coordinator already has full context; adding a routing layer is premature optimization for hardware that doesn't exist yet.

**Verdict: WATCH** -- Defensible given the M5 upgrade path. Trigger for reassessment: if M5 acquisition is delayed beyond 6 months, consider simplifying back to single-agent with enriched prompts.

#### Decision 2: Keychain + Credential Manager (ADR-009)

**Steel-man:** macOS Keychain provides hardware-backed encryption (Secure Enclave on Apple Silicon), per-item access control, and biometric gating. Double encryption (Fernet + Keychain) adds defense-in-depth. Three tiers (operational/sensitive/system) partition risk.

**Attack:**
- **Premises:** Assumes macOS will always be the host platform. This is correct for now but the trading module introduces a financial dimension -- if the system ever needs to run in a container or cloud VM for uptime, Keychain is unavailable.
- **Hidden costs:** Every test that touches credentials needs mocking. The get_credential_manager() synchronous factory means credentials can't be lazily loaded in async contexts without blocking.
- **Time horizon:** For personal use on Mac hardware, this is optimal. For any future deployment diversity, it's a hard constraint.

**Counter-argument:** For a personal system that will always run on Mac hardware, Keychain is the best possible choice. The constraint only matters if the deployment model changes, which is not planned.

**Verdict: VALIDATED** -- Keychain is the right choice for this system's deployment model. The constraint is real but acceptable.

#### Decision 3: Tag-Based Memory with Temporal Decay (ADR-013 + ADR-028 + ADR-041)

**Steel-man:** ChromaDB for vector search, SQLite for structured metadata, temporal decay for relevance, bi-temporal facts for knowledge graph. Memory lifecycle (importance scoring, consolidation, pruning) keeps the system manageable over time.

**Attack:**
- **Premises:** Assumes embedding-based similarity is the right retrieval primitive. But the knowledge graph (ADR-041) introduced fact-based structured retrieval -- these two systems overlap. A memory chunk and a fact can encode the same information in different forms.
- **Hidden costs:** Two parallel retrieval systems (ChromaDB vectors + SQLite facts) mean the orchestration layer must decide which to query, or query both and merge. The handler.py already does this ad-hoc. As the knowledge graph matures, the boundary between "memory" and "knowledge" will blur further.
- **Time horizon:** The bi-temporal fact model is more expressive than raw memory chunks for structured knowledge. Over time, more information should migrate from memory to knowledge graph, making the memory module primarily a conversation buffer rather than a knowledge store.

**Counter-argument:** Unify memory and knowledge into a single retrieval system. Use the knowledge graph as the primary store and reduce ChromaDB to a conversation-history cache with aggressive TTL.

**Verdict: WATCH** -- Both systems work today. Trigger for reassessment: when the knowledge graph has over 1000 facts and memory search results frequently duplicate graph content, consider consolidation. The LearningScheduler's memory lifecycle already creates natural pressure toward this unification.

### 7.3 Project-Level Strategic Challenges

- **What is the project optimizing for that it shouldn't be?** Feature breadth over depth. 31 backend modules, 212 endpoints, 29 route modules -- for a single-user system. Each module is individually clean, but the aggregate surface area is large. The trading module (9 files, 3 subdirectories) is a mini-application embedded in the monolith.
- **What capability will be hardest to add in 6 months?** Multi-user support. Every database is single-user by design. User-scoped state (newsfeed, inbox, outcomes) exists for multi-device but not multi-user. The Keychain-based credential system is per-machine.
- **Where is complexity accumulating fastest?** handler.py (2632 lines, up 140 since last audit) and the trading module (2257 lines of core code + strategies + exchange + data). The trading module is well-structured but its rate of growth will test the current module pattern.
- **What would a rewrite do differently?** Split handler.py into a pipeline of discrete stages (validate, enrich, route, infer, execute, persist). Each stage is a separate module with a clear interface. The current handler is a procedural script with methods, not a composable pipeline.

---

## Simplification Opportunities

| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| handler.py decomposition | 2632 lines, growing | Extract command handling, tool execution, streaming into separate modules | High (8-12h) | High -- most impactful maintainability improvement |
| V1 agent API sunset | agents.py (V1) + agents_v2.py (V2) both registered | Deprecate V1, migrate any remaining consumers to V2 | Medium (3-5h) | Medium -- reduces route surface area |
| Config directory consolidation | config/ (2 files) + hestia/config/ (6 files) | Move all to hestia/config/ | Low (1h) | Low -- removes confusion |
| sanitize_for_log location | hestia.api.errors (imported by orchestration/agentic_handler.py) | Move to hestia.logging to eliminate cross-layer import | Low (1h) | Low -- cleanest import graph |
| Encapsulation fix | 3 _database / _principle_store accesses in scheduler | Add public properties to OutcomeManager and ResearchManager | Low (30min) | Low -- removes code smell |

---

## Consistency Issues

| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|
| Error sanitization | sanitize_for_log(e) everywhere | str(e) used for routing logic (not leaked) | hestia/api/routes/tasks.py:341,426,514, orders.py:370 |
| Async subprocess | asyncio.create_subprocess_exec | Blocking subprocess.run() | hestia/proactive/policy.py:115,149 |
| Manager encapsulation | Public accessors only | Direct ._database access | hestia/learning/scheduler.py:82,117,121,122 |
| Async file I/O | aiofiles or run_in_executor | Blocking with open() in async handler | hestia/api/routes/memory.py:728 |
| LogComponent enum | Documented 22 in CLAUDE.md | Actual: 23 (NOTIFICATION added) | hestia/logging/structured_logger.py:66 |

---

## Documentation Currency

| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md (tech stack line 146) | Stale | Says "approximately 200 endpoints across 28 route modules" -- actual: 212 / 29 |
| CLAUDE.md (project structure line 298) | Stale | Says "208 endpoints, 29 route modules" -- actual: 212 / 29. Also says "26 modules (+1 trading planned)" but there are 31 module directories. |
| CLAUDE.md (test counts line 338) | Stale | Says "2245 tests, 64 files" for backend -- actual: 2330 tests, 69 files. Total: 2465, not 2380. CLI: 9 test files, not 7. |
| CLAUDE.md (API Summary table) | Stale | Missing: Notifications (6 endpoints), ws_chat (1 endpoint). Learning listed as 5 endpoints -- actual: 10. |
| CLAUDE.md (LogComponent count) | Stale | Lists 22 components -- actual: 23 (NOTIFICATION added) |
| CLAUDE.md (macOS file count) | Stale | Says 126 macOS files -- actual: 135 |
| CLAUDE.md (project structure tree) | Stale | Missing notifications/ module entirely. verification/ has no detail. |
| docs/api-contract.md (header) | Stale | Says "186 across 27 route modules" -- actual: 212 / 29. Missing notifications, new learning endpoints, trading routes. |

---

## Workspace Hygiene

- **Untracked files:** 3 items (HestiaApp/data/, hestia-cli/data/, scripts/sync-board-from-sprint.sh)
- **Modified files:** 2 items (.gitignore, SESSION_HANDOFF.md)
- **Unpushed commits:** 2 ahead of origin/main
- **Stale TODOs:** 1 in production code (hestia-cli/hestia_cli/repl.py:263 -- Sprint 3C tier upgrade, low priority)
- **.env file on disk:** Contains plaintext Anthropic API key. Gitignored but should be cleaned up.
- **Archive candidates:** None identified -- docs/ folder is well-organized with proper subdirectories.

---

## Summary

- **CISO:** Acceptable -- Strong credential management and error sanitization. Remediate .env plaintext key and create trading security ADR before live trading.
- **CTO:** Acceptable -- Clean architecture with consistent patterns. handler.py at 2632 lines is the top technical debt item, growing rather than shrinking. Trading module is well-built but needs formal ADR.
- **CPO:** Acceptable -- Feature delivery outpacing documentation. 26 endpoints and 2 route modules exist that the docs don't describe. Test counts stale by 85 tests.
- **Critical issues:** 0 (no blockers)
- **High-priority issues:** 3 (handler.py size, .env key, trading security ADR)
- **Simplification opportunities:** 5
- **Consistency violations:** 5
- **Documentation drift:** 8 items across 3 documents
