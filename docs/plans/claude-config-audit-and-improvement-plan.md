# Claude Configuration Audit & Improvement Plan

**Date:** 2026-03-19
**Author:** Andrew + Claude
**Status:** IMPLEMENTED — Phases A, B, C1-C4 complete (2026-03-19). Phase D partially complete. See implementation notes below.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Current State Audit](#2-current-state-audit)
3. [Andrew's Vision — Organized](#3-andrews-vision--organized)
4. [Gap Analysis: Vision vs. Current State](#4-gap-analysis-vision-vs-current-state)
5. [Improvement Plan](#5-improvement-plan)
6. [Implementation Roadmap](#6-implementation-roadmap)
7. [Open Questions](#7-open-questions)

---

## 1. Executive Summary

This document captures a full audit of the Hestia project's Claude Code configuration (skills, agents, hooks, scripts, plugins, CLAUDE.md) and synthesizes Andrew's notes into a structured improvement plan.

**Core finding:** The existing configuration is strong — 8 active skills, 8 specialized agents, 6 hook categories, 34 scripts. The infrastructure is there. What's missing is the *connective tissue*: a philosophical framework that ties it all together, an automated loop that enforces discipline, and multi-stakeholder review depth that catches problems before they ship.

**Three pillars of the improvement plan:**

1. **Deepen the review framework** — Add CFO + Legal lenses, philosophical/ethical checks, and a full-feasibility "moonshot" challenge to `/discovery` and `/second-opinion`
2. **Close the loop** — Evolve `/handoff` into the feedback engine: retro + config optimization proposals + lightweight metrics log. No new skills — strengthen what exists
3. **Tighten the foundation** — Fix documentation drift, archive dead code, tune hook timeouts, and create the missing invocation matrix

**Design principle:** Adapt and evolve existing skills rather than create new ones. Simplicity is key.

---

## 2. Current State Audit

### 2.1 Inventory Summary

| Category | Count | Grade | Key Strength | Key Gap |
|----------|-------|-------|-------------|---------|
| Skills | 8 active + 1 deprecated | A- | Multi-phase structured methodology with Gemini cross-validation | No invocation matrix; users don't know when to use which skill |
| Agents | 8 | A | Clear specialization; read-only enforcement; model-appropriate routing | @hestia-critic underutilized; no agent learning across sessions |
| Hooks | 6 categories | B+ | Full lifecycle coverage (session start → security → test → build → stop) | Aggressive timeouts; no selective execution; no pre-push hook in settings.json |
| Scripts | 34 | B | Well-organized by category; bash 3.2 compatible | Historical scripts not archived; duplicate log scripts; no inventory in CLAUDE.md |
| Plugins | 3 (pyright, github, commit-commands) | B | Essential set for Python + GitHub workflow | No MCP connectors for external services |
| CLAUDE.md | 1 (350+ lines) | B- | Comprehensive architecture docs; manager pattern documented | LogComponent drift; static counts risk drift; hooks/scripts not documented |
| Rules | 1 (parallel-sessions.md) | B+ | Clear concurrency safety guidance | Not referenced in CLAUDE.md |

### 2.2 Skills Detail

| Skill | Phases | Gemini? | Multi-Stakeholder? | Automated Loop? |
|-------|--------|---------|---------------------|-----------------|
| `/discovery` | 7 | Yes | Skeptic + Pragmatist + Long-Term Thinker | No |
| `/second-opinion` | 10 | Yes | IC + Tech Lead + PM + UX + SRE + CISO + CTO + CPO | No |
| `/codebase-audit` | 9 | No | CISO/CTO/CPO panel + SWOT | No |
| `/handoff` | 7 | No | Config gap scan + first-pass success + agent orchestration | Partial (retro) |
| `/preflight` | 1 | No | None | No |
| `/pickup` | 1 | No | None | No |
| `/bugfix` | Multi | No | None | Yes (test-driven) |
| `/scaffold` | Multi | No | None | Yes (parallel agents) |

### 2.3 What's Working Well

1. **Structured methodology** in every skill — numbered phases, concrete deliverables, edge cases
2. **Gemini cross-model validation** in discovery and second-opinion — genuinely novel
3. **Read-only agent enforcement** — agents diagnose, never modify; prevents runaway changes
4. **Security hooks** — plaintext secret detection + .env write blocking before any edit lands
5. **Session continuity** — SESSION_HANDOFF.md + PreCompact hook + /pickup + /handoff form a complete lifecycle
6. **Roadmap sync** — roadmap-sync.sh with 13+ subcommands provides full GitHub Project management

### 2.4 Critical Issues Found

1. **LogComponent enum mismatch** — CLAUDE.md lists 23, agent definitions list 19. Three components (LEARNING, VERIFICATION, NOTIFICATION) may not be reflected in agent context.
2. **Static count drift** — Test count (2634) and endpoint count (218) in CLAUDE.md are not automatically verified. count-check.sh exists but isn't wired into any hook.
3. **Hook timeouts too aggressive** — auto-build-swift.sh at 180s often insufficient for full dual-target build (real: 5+ min). auto-test.sh at 120s may skip integration tests.
4. **Missing pre-push hook wiring** — pre-push.sh exists as a script but isn't configured in .claude/settings.json hooks.
5. **Deprecated skill still present** — `/retrospective` is disabled but not archived.
6. **No invocation matrix** — Users must guess when to use `/discovery` vs `/second-opinion` vs `/codebase-audit`.
7. **@hestia-critic is a phantom agent** — Powerful adversarial critique agent exists in definitions but no skill invokes it and CLAUDE.md doesn't specify when to use it.

---

## 3. Andrew's Vision — Organized

Andrew's notes organize into four strategic themes:

### Theme 1: Deepen Multi-Stakeholder Review

**Current state:** `/second-opinion` already covers IC → Tech Lead → PM → UX → SRE → CISO → CTO → CPO.

**Andrew's additions:**

| Role | Lens | Gap in Current Skills |
|------|------|-----------------------|
| CFO | Cost optimization, ROI, resource allocation, budget implications | Missing from all skills |
| Legal | Regulatory compliance, contract risk, data handling, IP exposure | Missing from all skills |

**Philosophical layer (NEW — not in any current skill):**

- **Ethical check:** Is what we're doing ethical, moral, and productive?
- **First principles challenge:** Why this approach? Is there a better option we haven't considered?
- **Moonshot challenge:** What does the best possible version of this look like — the viable dream most people let go of?
- **Key principles filter:** Does this serve Security, Empathy, Simplicity, Joy?

### Theme 2: Automated Development Loop

**Current state:** Skills are manually invoked. No enforced loop.

**Andrew's vision — 5-stage automated cycle:**

```
┌──────────────┐
│  1. Discovery │ ── /discovery (enhanced)
└──────┬───────┘
       ▼
┌──────────────────────────┐
│  2. Devil's Advocate /    │ ── /second-opinion (enhanced)
│     Second Opinion        │
└──────┬───────────────────┘
       ▼
┌──────────────┐
│  3. Execution │ ── /scaffold or /bugfix + hooks
└──────┬───────┘
       ▼
┌──────────────────────┐
│  4. Validation /      │ ── /preflight + auto-test + build
│     Bug Fix           │
└──────┬───────────────┘
       ▼
┌──────────────────────────────┐
│  5. Retrospective            │ ── /handoff (enhanced) + NEW /insights
│     Post-mortem → Config     │
│     optimization feedback    │
└──────────────────────────────┘
```

**Key evolution: `/handoff` Phase 3 becomes the feedback engine** — expanded retro that identifies optimization opportunities against Claude skills, agents, hooks, and scripts, plus a lightweight metrics log. No new skill needed. Questions it answers:

- What changes would help avoid bug fixes in the future?
- What changes would help reach "production-ready" on the first pass?
- What changes would drive efficiency without compromising efficacy?

**Metrics captured per session (in SESSION_HANDOFF.md + rolling `docs/metrics/dev-loop-metrics.md`):**

Qualitative (already in retro, formalized):
- What caused rework this session? (wrong assumption / missing context / tool failure)
- Which config gap was the top blocker?
- Were agents used when they should have been?

Quantitative (new, lightweight):
- First-pass success rate (tasks done right on first try vs. requiring rework)
- Bug frequency by category (recurring patterns across sessions)
- Hook catch rate (how often security/test hooks flagged real issues)

### Theme 3: Collaborate vs. Operate Mode

Andrew distinguishes between two modes:

| Mode | Description | Implication |
|------|-------------|-------------|
| **Collaborate** | Andrew is present, making decisions, learning (70% teach-as-we-build) | Skills should explain reasoning, present options, wait for approval |
| **Operate** | Claude works autonomously (30% just-make-it-work) | Skills should execute decisively, report results, flag only blockers |

**Current state:** All skills implicitly assume Collaborate mode. No skill adapts its behavior based on mode.

**Impact:** In Operate mode, skills shouldn't pause for multi-phase review — they should compress discovery + second-opinion into a single pre-flight check, execute, and report. In Collaborate mode, they should expand to teach, explain trade-offs, and invite discussion.

### Theme 4: CLI > SDK > MCP Preference

Andrew's preference hierarchy for tooling:

1. **CLI first** — Shell scripts, command-line tools, native system commands (lowest token cost, ambient auth, LLMs trained on man pages)
2. **SDK when CLI isn't enough** — Python/Swift libraries for complex logic, type safety, custom business rules
3. **MCP as last resort** — External service connectors when per-user auth and governance are needed

**Current alignment:** Hestia already follows this — hestia-cli-tools (Swift CLIs) for Apple ecosystem, shell scripts for automation, MCP only implied for future multi-tenant scenarios.

**Action:** Codify this as a decision principle in CLAUDE.md so future work doesn't default to MCP when a CLI would suffice.

---

## 4. Gap Analysis: Vision vs. Current State

### 4.1 Review Framework Gaps

| Andrew's Vision | Current State | Gap | Effort |
|-----------------|--------------|-----|--------|
| CFO review in second-opinion | Not present | Add Phase 8.5: CFO Review | Small (add section to skill) |
| Legal review in second-opinion | Not present | Add Phase 8.5: Legal Review | Small (add section to skill) |
| Ethical/moral check | Not in any skill | Add philosophical layer to discovery + second-opinion | Medium (new section + principle definitions) |
| Full-feasibility moonshot challenge | Not in any skill | Add to discovery as Phase 5.5 with viability/effort/risk/MVP analysis | Medium (substantial new section) |
| Key principles (Security, Empathy, Simplicity, Joy) | Implicit in CLAUDE.md | Codify as explicit filter in review phases | Small (enumerated checklist) |

### 4.2 Automation Gaps

| Andrew's Vision | Current State | Gap | Effort |
|-----------------|--------------|-----|--------|
| Automated 5-stage loop | Manual skill invocation | Documented workflow + /handoff as feedback engine | Medium |
| Config optimization feedback | `/handoff` Phase 3 covers ~60% | Expand Phase 3 to classify → propose → rank → apply/defer | Medium |
| Post-mortem → config changes | Handoff records learnings but doesn't propose changes | Add structured proposal output + auto-apply for docs | Medium |
| First-pass success tracking | Handoff Phase 3b assesses it | Formalize as quantitative metric in markdown log | Small |

### 4.3 Collaborate vs. Operate Gap

| Andrew's Vision | Current State | Gap | Effort |
|-----------------|--------------|-----|--------|
| Mode-aware skills | All skills assume Collaborate | Add mode parameter to skills; adjust verbosity and approval gates | Medium |
| Compressed autonomous loop | No equivalent | Operate mode compresses 5-stage into: pre-check → execute → verify → report | Medium |

### 4.4 Infrastructure Gaps (from audit)

| Issue | Impact | Fix | Effort |
|-------|--------|-----|--------|
| LogComponent drift | Agent context may be incomplete | Count actual enum, update all references | Small |
| Static count drift | CLAUDE.md accuracy degrades | Wire count-check.sh into /handoff or pre-push | Small |
| Hook timeouts | Builds/tests may timeout incorrectly | Measure real durations, adjust settings.json | Small |
| Missing pre-push hook | Tests may not run before push | Add to settings.json | Small |
| No invocation matrix | Users guess which skill to use | Document in CLAUDE.md | Small |
| @hestia-critic unused | Powerful agent sits idle | Add to sprint boundary workflow or create /critique skill | Small-Medium |
| Deprecated skill | Clutter | Archive /retrospective | Trivial |
| Historical scripts | Clutter | Move to scripts/archive/ | Trivial |

---

## 5. Improvement Plan

### 5.1 Phase A: Foundation Fixes (Hygiene — Do First)

**Goal:** Clean up drift, archive dead code, fix timeouts, document what exists.

| # | Task | Files Affected | Est. Hours |
|---|------|---------------|------------|
| A1 | Resolve LogComponent enum drift | hestia/logging/__init__.py, CLAUDE.md, agent defs | 0.5 |
| A2 | Wire count-check.sh into /handoff Phase 2 | .claude/skills/handoff/SKILL.md | 0.25 |
| A3 | Add pre-push hook to settings.json | .claude/settings.json | 0.25 |
| A4 | Tune hook timeouts (measure real durations) | .claude/settings.json | 0.5 |
| A5 | Archive deprecated /retrospective skill | .claude/skills/retrospective/ → archive | 0.1 |
| A6 | Archive historical scripts | scripts/create-sprint20-*.sh → scripts/archive/ | 0.1 |
| A7 | Deduplicate archive-logs.sh and compress-logs.sh | scripts/ | 0.25 |
| A8 | Add invocation matrix to CLAUDE.md | CLAUDE.md | 0.5 |
| A9 | Document hooks in CLAUDE.md | CLAUDE.md | 0.5 |
| A10 | Document scripts inventory in CLAUDE.md or scripts/README.md | CLAUDE.md or scripts/README.md | 0.5 |
| A11 | Reference parallel-sessions.md in CLAUDE.md | CLAUDE.md | 0.1 |
| A12 | Codify CLI > SDK > MCP principle in CLAUDE.md | CLAUDE.md | 0.25 |

**Total Phase A:** ~3.75 hours

### 5.2 Phase B: Deepen Review Framework

**Goal:** Add CFO, Legal, ethical/philosophical, and moonshot lenses to discovery and second-opinion.

| # | Task | Files Affected | Est. Hours |
|---|------|---------------|------------|
| B1 | Add CFO Review phase to /second-opinion (Phase 8.4) | .claude/skills/second-opinion/SKILL.md | 0.5 |
| B2 | Add Legal Review phase to /second-opinion (Phase 8.5) | .claude/skills/second-opinion/SKILL.md | 0.5 |
| B3 | Add Philosophical Layer to /discovery (new Phase 5.5) | .claude/skills/discovery/SKILL.md | 1.0 |
| B4 | Add Moonshot Challenge with full feasibility analysis to /discovery (new Phase 5.5) | .claude/skills/discovery/SKILL.md | 1.0 |
| B5 | Add Key Principles filter (Security, Empathy, Simplicity, Joy) as checklist in both skills | Both skill files | 0.5 |
| B6 | Add CFO + Legal to /codebase-audit executive panel | .claude/skills/codebase-audit/SKILL.md | 0.5 |
| B7 | Wire @hestia-critic into /second-opinion Phase 9 (Devil's Advocate) | .claude/skills/second-opinion/SKILL.md | 0.5 |

**Phase B Detail — New Review Lenses:**

**CFO Review** should assess:
- What does this cost to build? (engineer-hours, cloud spend, infrastructure)
- What does this cost to maintain? (ongoing compute, monitoring, support)
- What's the ROI? (time saved, capability gained, risk reduced)
- Are we allocating resources to the highest-value work?
- What's the opportunity cost in dollar terms?

**Legal Review** should assess:
- Data handling: Does this touch PII? GDPR/CCPA implications?
- Third-party dependencies: License compatibility? Vendor lock-in?
- API usage: Terms of service compliance for any external APIs?
- IP exposure: Are we open-sourcing something we shouldn't?
- Regulatory: Any industry-specific compliance concerns?

**Philosophical Layer** should include:
- **Ethical check:** Is this ethical, moral, and productive? Would we be comfortable if this were public?
- **First principles challenge:** Why this approach? Have we considered alternatives that don't exist yet? What would a 10x better solution look like?
- **Moonshot challenge (full feasibility):** What's the viable dream version? The approach that sounds crazy but is suddenly feasible with current tools? The option most people dismiss too quickly? This is NOT a throwaway brainstorm — it gets a full feasibility analysis: technical viability, effort estimate, risk assessment, MVP scope, and a clear recommendation on whether to pursue it or shelve it (and what would change the answer).
- **Key principles filter:** Rate the proposed approach against Security (does it reduce attack surface?), Empathy (does it serve users well?), Simplicity (is this the simplest approach that works?), Joy (will building and using this bring satisfaction?)

**Total Phase B:** ~4.5 hours

### 5.3 Phase C: Automated Development Loop

**Goal:** Evolve existing skills into a 5-stage automated cycle. No new skills — strengthen what exists.

| # | Task | Files Affected | Est. Hours |
|---|------|---------------|------------|
| C1 | Expand /handoff Phase 3 into full config optimization engine (classify → propose → rank) | .claude/skills/handoff/SKILL.md | 2.0 |
| C2 | Create metrics log template + wire into /handoff output | docs/metrics/dev-loop-metrics.md (new file, not new skill) | 0.5 |
| C3 | Create automated loop documentation (workflow guide) | docs/plans/automated-dev-loop.md | 1.5 |
| C4 | Add Collaborate vs. Operate mode parameter to key skills | discovery, second-opinion, scaffold, bugfix SKILL.md files | 2.0 |
| C5 | Add compressed "Operate mode" pre-flight to /scaffold | .claude/skills/scaffold/SKILL.md | 1.0 |

**Phase C Detail — `/handoff` Phase 3 Evolution:**

Currently, /handoff Phase 3 does a "quick retro" with three sub-phases (config gap scan, first-pass success, agent orchestration). This gets expanded into a full config optimization engine:

```
/handoff Phase 3 (Enhanced)

3a: Config Gap Scan (existing — keep as-is)

3b: First-Pass Success (existing — formalize metrics output)

3c: Agent Orchestration (existing — keep as-is)

3d: Classify Improvements (NEW)
  For each learning from 3a-3c, classify as:
  - HOOK: Could a hook have caught this earlier?
  - SKILL: Should a skill have guided this better?
  - AGENT: Should an agent have been invoked?
  - CLAUDE.MD: Was context missing that caused wrong assumptions?
  - SCRIPT: Should automation exist for this?

3e: Generate Proposals (NEW)
  For each classified improvement:
  - What specific file would change?
  - What would the change look like?
  - What's the expected impact?

3f: Priority Ranking (NEW)
  Rank proposals by frequency × severity ÷ effort
  Present top 3-5 proposals in SESSION_HANDOFF.md
  Append quantitative metrics to docs/metrics/dev-loop-metrics.md

3g: Apply or Defer (NEW)
  - Collaborate mode: present proposals for Andrew's approval
  - Operate mode: apply non-breaking doc/config changes automatically, flag skill/hook changes for review
```

**Phase C Detail — Collaborate vs. Operate Mode:**

Skills should accept a mode signal. In practice this means:

- **Collaborate mode (default):** Full multi-phase review. Explain reasoning at each step. Wait for approval at key gates (plan approval, executive verdicts, deployment decisions). Teach patterns and trade-offs.

- **Operate mode:** Compress discovery + second-opinion into a single risk-aware pre-check. Execute without approval gates (except for irreversible actions). Report results concisely. Flag only blockers and significant risks.

Mode could be set via:
1. Explicit argument: `/discovery --mode operate "topic"`
2. Session-level setting in CLAUDE.md or SESSION_HANDOFF.md
3. Andrew saying "just make it work" (Claude recognizes the pattern)

**Total Phase C:** ~7.0 hours

### 5.4 Phase D: Agent & Infrastructure Enhancements

**Goal:** Activate underused agents, improve config validation, standardize outputs.

| # | Task | Files Affected | Est. Hours |
|---|------|---------------|------------|
| D1 | Add @hestia-critic to sprint boundary workflow | CLAUDE.md, sprint workflow docs | 0.5 |
| D2 | Create config validation schemas (pydantic) for YAML files | hestia/config/ (new validators) | 3.0 |
| D3 | Add selective hook execution (skip tests for .md edits) | .claude/settings.json, scripts/auto-test.sh | 1.0 |
| D4 | Standardize skill output format | All 8 active SKILL.md files | 1.5 |
| D5 | Add scripts/README.md with categorized inventory | scripts/README.md (new) | 0.5 |
| D6 | Create agent invocation decision tree | docs/agent-decision-tree.md (new) | 1.0 |

**Total Phase D:** ~7.5 hours

---

## 6. Implementation Roadmap

### Scheduling (Based on Andrew's ~12 hrs/week + Claude autonomy)

| Phase | Scope | Est. Hours | Timeline | Dependencies |
|-------|-------|-----------|----------|-------------|
| **A: Foundation** | Hygiene, docs, archival | 3.75h | Day 1 | None — can start immediately |
| **B: Review Depth** | CFO, Legal, philosophical, @hestia-critic wiring | 4.0h | Days 2-3 | Phase A (clean foundation) |
| **C: Automated Loop** | /handoff evolution, mode system, metrics log, loop docs | 7.0h | Days 4-6 | Phase B (enhanced skills to loop through) |
| **D: Infrastructure** | Schemas, selective hooks, standards | 7.5h | Days 7-9 | Phase A (hooks documented first) |

**Total: ~22.25 hours across ~9 working days (~2 weeks at 12 hrs/week)**

### Priority If Time-Constrained

If we need to cut scope, prioritize in this order:

1. **Phase A (all)** — Foundation fixes prevent ongoing drift and confusion
2. **B1-B5** — CFO + Legal + philosophical lenses are the highest-impact additions to existing skills
3. **C1** — `/handoff` Phase 3 evolution is the key feedback mechanism (no new skill needed)
4. **C4** — Collaborate vs. Operate mode eliminates the most friction
5. Everything else

### Relationship to Trading Module (Sprints 27-30)

This config improvement work is *orthogonal* to the Trading Module sprints. It can run in parallel because:
- Phase A changes are config/docs only (no backend code)
- Phase B changes are skill definitions only
- Phase C creates new skills but doesn't modify existing backend
- Phase D config validation could be deferred if Sprint 27 needs priority

Recommendation: Do Phase A+B before Sprint 27 Go-Live (better review framework for the most critical sprint). Do Phase C+D during Sprint 28-29 planning windows.

---

## 7. Open Questions

### Resolved

1. **~~Persistent metrics~~** → Qualitative (in handoff retros) + light quantitative (markdown log at `docs/metrics/dev-loop-metrics.md`). No SQLite.

2. **~~Moonshot scope~~** → Full feasibility analysis every time: technical viability, effort estimate, risk assessment, MVP scope, pursue/shelve recommendation.

3. **~~New skills vs. existing~~** → Adapt existing skills. `/insights` folded into `/handoff` Phase 3. `/critique` folded into `/second-opinion` via @hestia-critic wiring. No new skills created.

### Still Open

4. **Collaborate vs. Operate — signal mechanism:** How should Andrew signal mode? Explicit flag, session setting, or natural language detection? (Recommend: explicit flag + NL detection fallback — "just make it work" triggers Operate)

5. **Legal review depth:** How deep should the Legal lens go? Surface-level checklist (license, PII, ToS) or full regulatory analysis? (Recommend: checklist for all plans, deep analysis only when flagged)

6. **Config auto-apply in Operate mode:** Should /handoff Phase 3g auto-apply non-breaking config changes (CLAUDE.md updates, doc fixes) without approval? (Recommend: yes for doc updates, no for hook/skill changes)

7. **@hestia-critic invocation frequency:** At every sprint boundary, or only for high-risk architectural decisions? (Recommend: sprint boundaries + any decision that creates new modules or changes API contracts)

---

*This document is the Phase 1 deliverable. Next step: Review with Andrew, resolve remaining open questions, then execute Phase A.*
