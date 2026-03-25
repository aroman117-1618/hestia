---
name: codebase-audit
description: Full-stack SWOT analysis with CISO, CTO, and CPO critiques — comprehensive codebase health assessment
user_invocable: true
context: fork
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Task
  - TaskCreate
  - TaskUpdate
  - TaskList
---

# Codebase Audit Skill

Run a comprehensive, critical audit of the Hestia codebase. This is not a style review — it's an architecture-level assessment from three executive perspectives, with concrete findings and actionable recommendations.

**Persona:** IQ 175. Panel of three executives — CISO, CTO, CPO — each with deep expertise in their domain and zero tolerance for hand-waving. Be ruthlessly honest. Flag everything that matters, skip nothing.

## Phase 1: Scan

1. Read `CLAUDE.md` for current project state, conventions, and architecture
2. Use @hestia-explorer (Agent with subagent_type=hestia-explorer) to map the current codebase state
3. Create a TaskCreate plan tracking each audit section below

## Phase 2: SWOT Analysis (Codebase as a Whole)

Assess the full codebase:
- **Strengths** — what's well-built, what patterns are working
- **Weaknesses** — what's fragile, inconsistent, or poorly tested
- **Opportunities** — what could be improved with low effort, what's underutilized
- **Threats** — what could break in production, what's a ticking time bomb

## Phase 3: CISO Audit

Security and risk assessment across the full stack:

### Authentication & Authorization
- JWT implementation: algorithm, expiry, rotation, storage
- Route protection: any unprotected endpoints that should be gated?
- Device registration: enrollment flow, revocation capability

### Credential Management
- Are ALL secrets in Keychain? Grep for hardcoded values
- 3-tier partitioning: operational/sensitive/system — is it enforced?
- Double encryption (Fernet + AES-256): implementation correctness

### Error Handling & Information Leakage
- `sanitize_for_log(e)` usage: any routes using raw `{e}` or `str(e)`?
- HTTP responses: any leaking internal state or stack traces?
- Log files: any sensitive data in plaintext?

### Attack Surface
- OWASP top 10 assessment (injection, XSS, SSRF, CSRF, etc.)
- Prompt injection risks in LLM pipeline
- Communication gate: can anything leave the system without approval?
- Self-signed TLS: implications and hardening options

### Verdict
**CISO Rating:** Critical / Needs Work / Acceptable / Strong

## Phase 4: CTO Audit

Architecture and engineering quality assessment:

### Layer Boundaries
- Verify no upward imports (security > logging > inference > memory > orchestration > execution > API)
- Check for circular dependencies or leaky abstractions
- Flag any module doing too much or too little

### Pattern Consistency
- Manager pattern adherence: models.py + database.py + manager.py + get_X_manager()
- Logging: correct LogComponent usage in every module
- Async/await: any blocking I/O in async contexts?
- Type hints: coverage and correctness

### Code Health
- Dead code and unused imports
- Duplicate logic across modules
- Config sprawl: YAML consistency and minimality
- Dependency hygiene: requirements.txt currency and vulnerability scan

### LLM/ML Architecture
- Inference pipeline: cloud/local routing robustness
- Council implementation: failure modes, fallback behavior, timeout handling
- Temporal decay: edge cases, parameter tuning correctness
- Model router: 3-state transitions, state consistency

### Performance & Scalability
- Database query patterns: any N+1 problems?
- Memory management: ChromaDB collection sizes, SQLite connection pooling
- Concurrent request handling: any shared mutable state?

### Verdict
**CTO Rating:** Critical / Needs Work / Acceptable / Strong

## Phase 5: CPO Audit

Product quality and usability assessment:

### API Usability
- Are endpoints intuitive and well-documented?
- Response schemas: consistent envelope format?
- Error messages: helpful to consumers?
- API contract (`docs/api-contract.md`): accurate and complete?

### Feature Completeness
- Do implemented features match the roadmap?
- Any half-built features lingering?
- Are all three modes (Tia/Mira/Olly) fully functional?

### UI Wiring Health (4-Layer Audit)
Run the 4-layer parallel audit methodology (see `docs/discoveries/ui-wiring-audit-methodology-2026-03-19.md`):

**Layer 1 — Hardcoded Values:** `grep` for string literals in View files that look like real data (timestamps, counts, status messages). `grep` for numeric constants in Views that aren't spacing/sizing. `grep` for `Color(hex:)` literals outside DesignSystem files. Verify each in context.

**Layer 2 — Component Cross-Reference:** List all `Shared/` components. Check which are used by macOS (or iOS). Compare completeness of duplicates. Flag "built but not connected" — e.g., a Shared `OrderInlineForm` that exists but the macOS `OrdersPanel` doesn't use.

**Layer 3 — Error & Offline Behavior:** Read all ViewModel `catch` blocks — are errors surfaced or silently swallowed? Check if `errorMessage`/`isLoading` are displayed in Views. Check for `NetworkMonitor` usage. Trace the "server is down" path end-to-end. **Key anti-pattern:** "It calls an API" ≠ "It's wired" — verify the response is actually DISPLAYED, not just fetched.

**Layer 4 — Backend Endpoint Gaps:** List all backend endpoints. List all client-side API calls. Cross-reference for uncalled endpoints relevant to the platform. Flag entire subsystems that are hidden from the UI.

**CRITICAL:** Do NOT trust surface-level "yes it calls the API" checks. Verify with direct file reads. Empty closures (`Button { }`) compile and render but do nothing. Hardcoded fake data displays beautifully. Always spot-check at least 30% of claimed "wired" features.

### Documentation Quality
- CLAUDE.md: accurate? comprehensive? up to date?
- Decision log: recent decisions recorded?
- Skills/agents: do they reference correct patterns and paths?
- Onboarding friction: could a new session start productively from docs alone?

### Verdict
**CPO Rating:** Critical / Needs Work / Acceptable / Strong

## Phase 5.5: CFO & Legal Audit

### CFO Review
- **Infrastructure costs**: Compute, storage, cloud API spend — is this sustainable?
- **Resource allocation**: Are engineer-hours going to the highest-value work?
- **ROI assessment**: What's the return on the last 3 sprints? Where was effort wasted?
- **Maintenance burden**: Which modules have the highest ongoing cost vs. value delivered?
- **Verdict:** Critical / Needs Work / Acceptable / Strong

### Legal Review
- **Data handling**: PII exposure, GDPR/CCPA implications, data retention policies
- **Dependencies**: License compatibility scan (GPL contamination?), vendor lock-in risk
- **API ToS compliance**: External service terms (Coinbase, cloud providers, Ollama)
- **IP exposure**: Open-source risk for proprietary logic
- **Regulatory**: Crypto trading compliance, financial data handling
- **Verdict:** Critical / Needs Work / Acceptable / Strong

## Phase 6: Simplification Opportunities

Actively look for ways to reduce complexity while preserving functionality:
- Modules that could be merged
- Abstractions that don't earn their complexity
- Config files that could be consolidated
- Scripts with overlapping functionality
- Dead endpoints, unused models, orphaned test helpers

## Phase 7: Adversarial Critique — "What Will We Regret?"

This is NOT another assessment pass. This is a sustained devil's advocate challenge to the project's most significant architectural decisions. The previous phases asked "is this correct?" — this phase asks "is this the right thing?"

### 7.1 Identify the 3 Most Load-Bearing Decisions

Read `docs/hestia-decision-log.md` and the codebase. Find the 3 architectural decisions that:
- The most code depends on (highest coupling)
- Would be most expensive to reverse
- Were made earliest (and thus with the least information)

### 7.2 Challenge Each Decision

For each of the 3 decisions:

**Steel-man first**: State the decision and its rationale accurately. Show you understand why it was made.

**Then attack**:
- **Premises**: What assumptions does this rest on? Are they still true?
- **Alternatives dismissed**: What was the alternative? Was it dismissed too quickly?
- **Hidden costs**: What has this decision made harder over time? What can't change independently?
- **Time horizon**: Will this approach survive the next major capability addition?

**Build a counter-argument**: Construct a coherent case for how the project would be better with a different approach. Not a list of complaints — a real alternative with trade-offs acknowledged.

### 7.3 Project-Level Strategic Challenges

Zoom out from individual decisions:
- **What is the project optimizing for that it shouldn't be?** (e.g., flexibility over simplicity, features over depth)
- **What capability will be hardest to add in 6 months?** Why?
- **Where is complexity accumulating fastest?** Is that where the value is, or where the debt is?
- **What would a competitor (or a rewrite) do differently?**

### 7.4 Verdict per Decision

For each of the 3 decisions:
- **VALIDATED**: Holds up under scrutiny. Alternatives are worse.
- **WATCH**: Defensible now but has a shelf life. State the trigger for reassessment.
- **RECONSIDER**: Costs accumulating faster than benefits. Propose migration path.
- **REVERSE**: Actively causing harm. Propose immediate action.

## Phase 8: Cohesion & Consistency

Cross-cutting assessment:
- Naming conventions: consistent across Python and Swift?
- Error handling: same pattern everywhere?
- Schema naming: Pydantic models follow a convention?
- Logging levels: appropriate severity assignments?
- HTTP status codes: semantically correct?

## Phase 9: Documentation Currency & Workspace Hygiene

### Documentation Accuracy
- Verify CLAUDE.md counts match reality (modules, endpoints, tests, route modules)
- Verify `docs/api-contract.md` matches actual routes in `hestia/api/routes/`
- Verify `docs/hestia-decision-log.md` has entries for recent architectural decisions
- Verify agent definitions (`.claude/agents/`) have accurate test counts, module lists, LogComponent enums
- Verify skill definitions (`.claude/skills/`) reference correct tool names, paths, patterns

### Workspace Hygiene
- Check for orphaned untracked files (`git status`)
- Scan for TODO/FIXME/HACK comments that are stale or untracked
- Verify `docs/` folder structure is organized (no loose files that should be in subdirectories)
- Check for stale files that should be archived to `docs/archive/`
- Verify no debug artifacts, scratch files, or temporary outputs left behind

## Phase 9.5: External Documentation Sync (Notion + GitHub)

Verify that all project documentation is synced to external systems. Drift between local docs and external platforms is invisible until it causes confusion.

### Notion Sync Verification

Run the Notion sync status check and compare against local state:

```bash
source .venv/bin/activate && python scripts/sync-notion.py status 2>&1
```

Verify:
- **Sync state freshness**: Check `data/notion-sync-state.json` — when was the last successful push? If >24h stale, flag it.
- **Content drift**: Compare local file hashes against last-synced hashes in the sync state file. Flag any docs that changed locally but weren't pushed.
- **ADR sync**: Check that `docs/hestia-decision-log.md` ADR count matches what's in Notion (via `push-adrs` state).
- **Whiteboard check**: Run `python scripts/sync-notion.py read-whiteboard 2>&1` — surface any notes Andrew left between sessions that haven't been acted on.
- **Key docs to verify synced**: SPRINT.md, docs/api-contract.md, docs/hestia-decision-log.md, docs/hestia-security-architecture.md

### GitHub Project Board Verification

Cross-reference the GitHub Project board against local sprint tracking:

```bash
scripts/roadmap-sync.sh list 2>&1
scripts/sync-board-from-sprint.sh 2>&1
```

Verify:
- **Board vs SPRINT.md alignment**: Run `sync-board-from-sprint.sh` (dry run) — flag any items where board status doesn't match SPRINT.md status (e.g., SPRINT.md says DONE but board says In Progress).
- **Orphan detection**: Check for draft items on the board that don't correspond to any issue or SPRINT.md entry.
- **Missing items**: Check for SPRINT.md workstreams that have no corresponding GitHub issue or board item.
- **Issue state**: Verify completed sprints have their issues closed (not just board status "Done" with issue still open).
- **Label consistency**: Check that issue labels match their sprint designation in SPRINT.md.

### Verdict
| System | Status | Issues Found |
|--------|--------|-------------|
| Notion sync | Current/Stale/Broken | [details] |
| Notion whiteboard | Empty/Has Notes | [details] |
| GitHub board | Aligned/Drifted | [details] |
| Board orphans | N items | [details] |
| Missing board items | N items | [details] |

## Output Format

Save the audit to `docs/audits/codebase-audit-[date].md` and present it:

```markdown
# Codebase Audit: Hestia
**Date:** [date]
**Overall Health:** Critical | Needs Work | Healthy | Strong

## SWOT

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** ... | **Weaknesses:** ... |
| **External** | **Opportunities:** ... | **Threats:** ... |

## CISO Audit
**Rating:** [rating]

### Critical Issues
| Issue | Location | Risk | Recommendation |
|-------|----------|------|----------------|

### Findings
[Detailed security findings with file paths and line numbers]

## CTO Audit
**Rating:** [rating]

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|

### Findings
[Detailed architecture findings with file paths and line numbers]

## CPO Audit
**Rating:** [rating]

### Critical Issues
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|

### Findings
[Detailed product findings]

## Simplification Opportunities
| What | Current State | Proposed Change | Effort | Impact |
|------|--------------|-----------------|--------|--------|

## Consistency Issues
| Pattern | Expected | Actual (violations) | Files |
|---------|----------|-------------------|-------|

## Documentation Currency
| Document | Status | Issues Found |
|----------|--------|-------------|
| CLAUDE.md | Current/Stale | [details] |
| api-contract.md | Current/Stale | [details] |
| Agent definitions | Current/Stale | [details] |
| Skill definitions | Current/Stale | [details] |

## Workspace Hygiene
- Orphaned files: [count and list]
- Stale TODOs: [count]
- Archive candidates: [list]

## External Sync (Notion + GitHub)
| System | Status | Issues Found |
|--------|--------|-------------|
| Notion sync | Current/Stale/Broken | [details] |
| Notion whiteboard | Empty/Has Notes | [details] |
| GitHub board | Aligned/Drifted | [details] |
| Board orphans | N items | [details] |
| Missing board items | N items | [details] |

## Summary
- **CISO:** [rating] — [one-line summary]
- **CTO:** [rating] — [one-line summary]
- **CPO:** [rating] — [one-line summary]
- **CFO:** [rating] — [one-line summary]
- **Legal:** [rating] — [one-line summary]
- Critical issues: N
- Simplification opportunities: N
- Consistency violations: N
- Documentation drift: N items
```

Be specific. File paths and line numbers for every finding. Concrete fix proposals, not vague suggestions.
