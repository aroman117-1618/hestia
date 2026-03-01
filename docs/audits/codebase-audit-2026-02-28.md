# Codebase Audit: Hestia

**Date:** 2026-02-28
**Auditor:** Claude Code (Opus 4.6) — 4 parallel explorer agents + manual targeted review
**Overall Health:** Healthy

**Codebase Size:**
- Backend: 36,189 lines Python, 1,186 functions, 20 modules, 88 endpoints
- iOS/macOS: 130 Swift files (91 iOS + 35 macOS + shared)
- Tests: 892 collected (20 test files)
- Config: 4 YAML files, 414 lines

---

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Excellent layer architecture with clean boundaries. Zero upward imports. Strong security posture (double encryption, Keychain, parameterized SQL, communication gate). Comprehensive rate limiting. 892 tests with good fixture patterns. SwiftUI DesignSystem is exemplary — zero hardcoded values. | **Weaknesses:** 5 routes leak `str(e)` in HTTP details (wiki, agents_v2, tasks). 53 unguarded `print()` in Swift. Test suite hangs without per-test timeouts in some environments. No tests for logging/ or security/ modules. CLAUDE.md endpoint count stale (says 77, actual 88). |
| **External** | **Opportunities:** Council dual-path is elegant — easy to add new roles. Manager pattern is consistent enough to auto-scaffold new modules. API contract rewrite could auto-generate from OpenAPI spec. Swift DesignSystem tokens could generate from a single source of truth. | **Threats:** Self-signed TLS limits external integrations without cert pinning. JWT has no revocation mechanism (90-day tokens live until expiry). agents.py + agents_v2.py dual registration creates confusion. Test suite reliability depends on Ollama/ChromaDB availability. |

---

## CISO Audit

**Rating: Strong**

### Critical Issues

None.

### Findings

#### Authentication & Authorization

| Finding | Location | Status |
|---------|----------|--------|
| JWT HS256 with 90-day expiry, Keychain-stored secret | `hestia/api/middleware/auth.py:19-62` | Secure |
| 3-fallback key resolution (env → Keychain → generate) | `auth.py:36-62` | Secure |
| Device-type token validation | `auth.py:121` | Secure |
| All routes gated via `get_current_device` / `get_device_token` | All route files | Secure |
| `/v1/ping` intentionally unprotected (health check) | `routes/health.py` | Acceptable |
| No token revocation/blacklist mechanism | `auth.py` | **Advisory** — tokens live full 90 days |

#### Credential Management

| Finding | Location | Status |
|---------|----------|--------|
| Double encryption: Fernet (software) + Keychain AES-256 (hardware) | `security/credential_manager.py:176-177` | Secure |
| 3-tier partitioning: OPERATIONAL / SENSITIVE / SYSTEM | `credential_manager.py:27-31` | Enforced |
| Biometric ACL on SENSITIVE tier via Swift CLI | `credential_manager.py:320-348` | Secure |
| Master key rotation: infrastructure present, deferred to v1.5 | `credential_manager.py:350-378` | Documented |
| Credentials never logged | `credential_manager.py:183,246` | Secure |
| No hardcoded secrets in YAML, Python, or Swift | Full codebase grep | Clean |

#### Error Handling & Information Leakage

| Finding | Location | Severity |
|---------|----------|----------|
| `detail=str(e)` leaks ValueError content to HTTP response | `routes/wiki.py:186` | **Medium** |
| `detail=str(e)` leaks ValueError content to HTTP response | `routes/agents_v2.py:150,188,310` | **Medium** |
| `error_msg = str(e)` used in task status messages | `routes/tasks.py:341,426,514` | **Low** (wrapped in sanitized log, but str(e) in response dict) |
| `"not found" in str(e).lower()` pattern check in orders | `routes/orders.py:298` | **Low** (control flow, not leaked) |
| All other routes use `sanitize_for_log(e)` correctly | 14 route files | Compliant |
| Zero bare `except:` clauses in codebase | Full codebase grep | Excellent |

**Fix required:** Replace `detail=str(e)` with generic messages in wiki.py and agents_v2.py. ValueError messages can leak internal structure (e.g., "Agent 'foo' already exists in slot 2").

#### Attack Surface (OWASP Assessment)

| Vector | Status | Notes |
|--------|--------|-------|
| SQL Injection | **Immune** | All queries parameterized (verified across all DB files) |
| XSS | **N/A** | API-only, no HTML rendering |
| SSRF | **Mitigated** | Communication gate + sandbox allowlists |
| CSRF | **N/A** | JWT-based auth, no cookies |
| Prompt Injection | **Mitigated** | Role-based message separation, forbidden pattern detection (`validation.py:79-84`) |
| Path Traversal | **Immune** | `.resolve()` + `relative_to()` + allowlist in sandbox.py |
| Command Injection | **Mitigated** | Blocked command patterns in `sandbox.py:108-142` |
| Broken Access Control | **Secure** | All routes require device auth |
| Security Misconfiguration | **Clean** | Security headers (HSTS, CSP, X-Frame-Options) on all responses |

#### Security Headers (server.py:70-96)

All present: HSTS (1yr), X-Content-Type-Options, X-Frame-Options: DENY, X-XSS-Protection, CSP: self, Referrer-Policy, Cache-Control: no-store.

#### CISO Advisory Items

1. **CORS validation** — No startup-time validation that `HESTIA_CORS_ORIGINS` doesn't contain wildcards. Low risk (env-controlled) but worth a 3-line guard. (`server.py:224-227`)
2. **Token revocation** — 90-day JWT with no revocation list. If a device is compromised, the token cannot be invalidated. Consider a lightweight SQLite blacklist checked on auth. (`auth.py`)
3. **Master key rotation** — Correctly deferred with `NotImplementedError`. Document procedure in ADR when implemented. (`credential_manager.py:350-378`)
4. **Rate limiter is in-memory** — Acceptable for single-instance Mac Mini, but add note for future multi-instance deployment. (`middleware/rate_limit.py`)

---

## CTO Audit

**Rating: Strong**

### Critical Issues

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| Test suite hangs without explicit timeouts | `tests/` (no global timeout) | CI blocks indefinitely | Add `pytest.ini` with `timeout = 30` default |
| Both agents.py (v1) and agents_v2.py registered simultaneously | `server.py:314,320` | Dual route sets for overlapping functionality | Document migration plan or deprecate v1 |

### Architecture & Layer Boundaries

**Layer hierarchy:** security → logging → inference → memory → orchestration → execution → API

| Check | Result |
|-------|--------|
| Security imports from upper layers | **None** — Clean |
| Inference imports from API/execution/orchestration | **None** — Clean |
| Execution imports from API/orchestration | **None** — Clean |
| `from hestia.api` usage outside API layer | **None** — all within api/ |
| Circular dependencies | **None detected** |

**Verdict: Layer boundaries are pristine.**

#### Pattern Consistency

| Pattern | Expected | Compliance |
|---------|----------|-----------|
| Manager pattern (models + database + manager) | All modules | 14/20 modules follow strictly. 6 simpler modules (apple, persona, config, api, logging, security) use appropriate variations. |
| `get_X_manager()` async factory | All managers | Compliant. Exception: `get_council_manager()` is synchronous (documented). |
| LogComponent enum usage | Every module | 13 components defined (ACCESS through WIKI). All modules use correct component. |
| Async/await for I/O | All I/O paths | Compliant. One `time.sleep(0.5)` in `logging/viewer.py:213` (sync utility, acceptable). |
| Type hints | All functions | High coverage. Some internal helpers lack return annotations but all public APIs typed. |
| `sanitize_for_log(e)` in routes | All except blocks in routes | 5 violations (see CISO section). |

#### Code Health

| Metric | Value | Assessment |
|--------|-------|-----------|
| Dead code / unused imports | Minimal | No significant dead code detected |
| Bare `except:` clauses | **Zero** | All exceptions typed (`except Exception:` with logging) |
| `except Exception:` without logging | ~16 instances | All have logging or are in defensive patterns (council fallback, config loading) |
| Blocking I/O in async | 1 instance | `time.sleep(0.5)` in sync log viewer — not in async path |
| Config consistency | 4 YAML files, all well-structured | Clean |
| requirements.txt | 18 packages, all reasonable versions | No deprecated packages |

#### LLM/ML Architecture

| Component | Assessment |
|-----------|-----------|
| Cloud routing (3-state) | Robust. `_sync_router_state()` propagates consistently. State stored in SQLite, resilient to restarts. |
| Council (dual-path) | Elegant. Cloud active → parallel roles via `asyncio.gather()`. Cloud disabled → SLM intent only. Every call wrapped in try/except (additive, never breaks). |
| CHAT optimization | Smart. Skips 3 API calls when confidence > 0.8. Saves cost. |
| Temporal decay | Correct. `adjusted = raw * e^(-λ * age_days) * recency_boost`. Per-chunk-type λ. Facts/system never decay. |
| Model router | Clean 3-state FSM. Transition guards prevent invalid states. |
| Council SLM fallback | `qwen2.5:0.5b` (~100ms, 394MB). Graceful degradation if unavailable. |

#### Performance & Scalability

| Concern | Status |
|---------|--------|
| N+1 queries | Not detected — bulk operations use single queries |
| SQLite connection pooling | aiosqlite handles correctly |
| Shared mutable state | Rate limiter is in-memory (dict). Thread-safe via async event loop. |
| ChromaDB collection sizes | Not bounded — potential growth issue over years. Consider periodic compaction. |

---

## CPO Audit

**Rating: Acceptable**

### Critical Issues

| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|
| CLAUDE.md says 77 endpoints, actual is 88 | `CLAUDE.md:79` | New developer confusion | Update to 88 |
| CLAUDE.md says 19 modules, actual is 20 | `CLAUDE.md:144` | Minor inaccuracy | Update to 20 (wiki added) |
| API contract doesn't document agents_v2.py | `docs/api-contract.md` | 10 undocumented endpoints | Add v2 agent endpoints |
| Health test failures undocumented | CLAUDE.md / test_health.py | Unknown test debt | Document which 3 fail and why |

### API Usability

| Aspect | Assessment |
|--------|-----------|
| Endpoint naming | Consistent `/v1/{resource}/{action}` pattern |
| Response envelope | Consistent across all modules |
| Error messages | Good for consumers. **Exception:** `detail=str(e)` in 5 routes leaks internals |
| Swagger docs | Auto-generated at `/docs` — complete |
| HTTP verbs | Semantically correct (GET reads, POST creates, etc.) |

### Feature Completeness

| Feature | Status | Notes |
|---------|--------|-------|
| Three modes (Tia/Mira/Olly) | Complete | Mode switching, per-mode prompts |
| Cloud LLM routing | Complete | 3 providers, 3 states, 7 endpoints |
| Voice journaling | Complete | Quality check → journal analysis pipeline |
| Council + SLM | Complete | 4-role, dual-path, CHAT optimization |
| Temporal decay | Complete | Per-chunk-type λ |
| HealthKit | Complete | 28 metrics, coaching, briefing |
| Wiki | Complete | AI generation, ADR browser, Mermaid diagrams |
| macOS app | Complete | 2-pane layout, keyboard shortcuts |
| agents_v2.py | **Partial** | .md-based system coexists with v1 — migration not complete |

### Documentation Quality

| Document | Status | Issues |
|----------|--------|--------|
| CLAUDE.md | **Stale counts** | 77→88 endpoints, 19→20 modules, 16→17 route modules |
| api-contract.md | **Missing v2 agents** | 10 endpoints undocumented |
| hestia-decision-log.md | Current | ADRs through 025. Some early ADRs have placeholder dates ("[Your start date]") |
| SPRINT.md | Current | Updated 2026-02-28 |
| CHEATSHEET.md | Current | Quick reference accurate |
| security-architecture.md | Current | Matches implementation |

### Onboarding Assessment

Could a new Claude Code session start productively from docs alone? **Yes, with caveats.** CLAUDE.md is comprehensive but the stale endpoint/module counts could cause confusion. The decision log is excellent for understanding "why" decisions were made. The missing agents_v2.py documentation is the biggest gap.

---

## Simplification Opportunities

| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|
| agents.py + agents_v2.py | Both registered, overlapping CRUD | Complete v2 migration, deprecate v1 | Medium | Removes 10 duplicate endpoints, reduces confusion |
| `detail=str(e)` in 5 routes | Inconsistent error handling | Replace with `safe_error_detail()` from errors.py | Low | Consistent security posture |
| CLAUDE.md line counts | Manual maintenance | Auto-generate counts from codebase in /handoff | Low | Always-accurate docs |
| Constants.swift `baseURL` | Deprecated HTTP endpoint, unused | Delete the constant | Trivial | Remove dead code |
| `persona/` module | Exists but minimal usage | Evaluate if it should merge into `agents/` | Low | Cleaner module tree |

---

## Consistency Issues

| Pattern | Expected | Violations | Files |
|---------|----------|-----------|-------|
| Error sanitization in HTTP details | Generic message or `safe_error_detail()` | `detail=str(e)` | `wiki.py:186`, `agents_v2.py:150,188,310` |
| `#if DEBUG` around `print()` | All print statements | 53 unguarded prints | APIClient.swift, Services/, ViewModels/ |
| Module count in docs | 20 | Says 19 | CLAUDE.md |
| Endpoint count in docs | 88 | Says 77 | CLAUDE.md, api-contract.md |
| Route module count in docs | 17 (incl. agents_v2) | Says 16 | CLAUDE.md |
| ADR dates | Actual dates | Placeholder "[Your start date]" | ADR-001, ADR-002 in decision-log.md |
| Test timeout config | Global default | No pytest.ini timeout | `tests/` directory |
| iOS deployment target in CLAUDE.md | 26.0 | Says "iOS 16+" in Swift conventions section | CLAUDE.md Swift section |

---

## Summary

| Perspective | Rating | One-Line Summary |
|-------------|--------|------------------|
| **CISO** | **Strong** | No critical vulnerabilities. Defense-in-depth across auth, credentials, input validation, SQL, file access, and HTTP layers. 5 minor `detail=str(e)` leaks to fix. |
| **CTO** | **Strong** | Pristine layer boundaries. Consistent patterns. Elegant LLM architecture (council, routing, decay). Dual agents registration and test timeout config are the main concerns. |
| **CPO** | **Acceptable** | Features complete and well-designed. Documentation has stale counts and a 10-endpoint gap (agents_v2). Onboarding experience is good but not perfect. |

**Metrics:**
- Critical issues: **0**
- High-priority fixes: **2** (test timeout config, `detail=str(e)` in routes)
- Medium-priority fixes: **5** (doc count updates, agents_v2 docs, ADR dates, agents migration plan)
- Low-priority fixes: **4** (CORS validation, Constants.swift cleanup, persona/ module eval, print() wrapping)
- Simplification opportunities: **5**
- Consistency violations: **8**
