---
name: audit
description: Deep architecture, security, and project management audit — find gaps, inconsistencies, and simplification opportunities
user_invocable: true
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Task
  - TodoWrite
---

# Project Audit Skill

Run a comprehensive, critical audit of the Hestia project. This is not a style review — it's an architecture-level assessment covering code quality, security posture, structural simplification, and project management hygiene.

Approach this with deep expertise in software development, cybersecurity, and enterprise-grade LLM/ML architecture. Be ruthlessly honest — flag everything that matters, skip nothing.

## Part 1: Architecture & Code Audit

Use @hestia-explorer (Task with subagent_type=hestia-explorer) to investigate each area. Create a TodoWrite plan to track progress.

### 1.1 Layer Boundaries
- Verify no upward imports (security > logging > inference > memory > orchestration > execution > API)
- Check for circular dependencies or leaky abstractions
- Flag any module that's doing too much or too little

### 1.2 Security Posture
- Audit credential handling: are all secrets in Keychain? Any hardcoded values?
- Check error sanitization: any route using raw `{e}` or `str(e)` in responses?
- Verify JWT auth coverage: any unprotected routes that should be protected?
- Check for OWASP top 10 vulnerabilities (injection, XSS, SSRF, etc.)
- Validate the communication gate: can anything leave the system without approval?

### 1.3 Structural Simplification
- Identify dead code, unused imports, redundant abstractions
- Flag modules that could be merged or simplified
- Assess config sprawl: are YAML configs consistent and minimal?
- Check for duplicate logic across modules

### 1.4 Consistency & Cohesion
- Verify all modules follow the manager pattern (models + database + manager)
- Check logging: correct LogComponent usage everywhere?
- Verify error handling patterns are uniform across all routes
- Check that all Pydantic schemas follow consistent naming

### 1.5 LLM/ML Architecture
- Assess the inference pipeline: is the cloud/local routing robust?
- Review the council implementation: failure modes, fallback behavior
- Check temporal decay: edge cases, parameter tuning
- Evaluate prompt construction: injection risks, consistency

## Part 2: Project Management Audit

### 2.1 Documentation Currency
Read each of these files and check if they accurately reflect the current codebase:
- `CLAUDE.md` — project structure, endpoint counts, test counts, status
- `docs/api-contract.md` — do documented endpoints match actual routes?
- `docs/hestia-decision-log.md` — are recent decisions recorded?
- `docs/hestia-security-architecture.md` — does it match current implementation?
- `docs/hestia-development-plan.md` — is status current?

### 2.2 Skills & Agents
- Read all files in `.claude/skills/` and `.claude/agents/`
- Check: do skill instructions reference correct ports, paths, commands?
- Check: do agent definitions have accurate codebase maps and test inventories?
- Flag any skills or agents that reference outdated patterns

### 2.3 Config & Script Hygiene
- Check all scripts in `scripts/` — do they use correct paths, ports, URLs?
- Verify `config/*.yaml` files are consistent with code behavior
- Check `.claude/settings.json` hooks — are matchers and commands correct?

## Part 3: Session Retrospective

Review the current conversation history and assess:
- What questions needed clarifying that could have been pre-answered in CLAUDE.md or skills?
- What errors were encountered that better documentation would have prevented?
- What patterns emerged that should be codified in skills, agents, or hooks?
- What assumptions were made that turned out wrong?

## Output Format

Present findings in this structure:

```markdown
# Hestia Project Audit — [date]

## Critical Issues (fix immediately)
| Issue | Location | Impact | Recommendation |
|-------|----------|--------|----------------|

## Notable Gaps (fix soon)
| Gap | Location | Impact | Recommendation |
|-----|----------|--------|----------------|

## Simplification Opportunities
| What | Current State | Proposed Change | Effort |
|------|--------------|-----------------|--------|

## Documentation Drift
| Document | Issue | What needs updating |
|----------|-------|-------------------|

## Skills/Agents Improvements
| File | Issue | Recommendation |
|------|-------|----------------|

## Session Learnings
| Learning | Where to codify | Proposed change |
|----------|----------------|-----------------|

## Summary
- Critical: N issues
- Notable: N gaps
- Simplification: N opportunities
- Doc updates: N needed
```

Be specific. Include file paths and line numbers. Propose concrete fixes, not vague suggestions.
