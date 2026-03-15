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

### Documentation Quality
- CLAUDE.md: accurate? comprehensive? up to date?
- Decision log: recent decisions recorded?
- Skills/agents: do they reference correct patterns and paths?
- Onboarding friction: could a new session start productively from docs alone?

### Verdict
**CPO Rating:** Critical / Needs Work / Acceptable / Strong

## Phase 6: Simplification Opportunities

Actively look for ways to reduce complexity while preserving functionality:
- Modules that could be merged
- Abstractions that don't earn their complexity
- Config files that could be consolidated
- Scripts with overlapping functionality
- Dead endpoints, unused models, orphaned test helpers

## Phase 7: Cohesion & Consistency

Cross-cutting assessment:
- Naming conventions: consistent across Python and Swift?
- Error handling: same pattern everywhere?
- Schema naming: Pydantic models follow a convention?
- Logging levels: appropriate severity assignments?
- HTTP status codes: semantically correct?

## Phase 8: Documentation Currency & Workspace Hygiene

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

## Summary
- **CISO:** [rating] — [one-line summary]
- **CTO:** [rating] — [one-line summary]
- **CPO:** [rating] — [one-line summary]
- Critical issues: N
- Simplification opportunities: N
- Consistency violations: N
- Documentation drift: N items
```

Be specific. File paths and line numbers for every finding. Concrete fix proposals, not vague suggestions.
