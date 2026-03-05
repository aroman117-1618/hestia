# Current Sprint: Chat Redesign + OutcomeTracker (Sprint 10) — COMPLETE

**Started:** 2026-03-04
**Plan:** `docs/plans/sprint-10-chat-redesign-plan.md`
**Audit:** `docs/plans/sprint-10-plan-audit-2026-03-04.md`
**Master Roadmap:** `docs/plans/sprint-7-14-master-roadmap.md`

## Sprint 10 Summary

### OutcomeTracker (Learning Cycle Phase A part 2)
- `hestia/outcomes/` module: database, manager, 5 API endpoints
- Auto-tracks every chat response (duration, type, tool calls)
- Implicit signal detection: quick_followup (<30s), accepted (30-300s), long_gap (>300s)
- Wired into POST /v1/chat — fires on every response + detects signals on incoming messages
- Explicit feedback: thumbs-up/down via POST /v1/outcomes/{id}/feedback

### Chat UI Redesign
- CLITextView: NSTextView wrapper with SF Mono, dark bg, Cmd+Enter send, Up-arrow history
- MarkdownMessageView: AttributedString rendering, CodeBlockView with copy, ToolCallCardView
- FloatingAvatarView: 60pt circle, cross-dissolve swap, pulsing orange glow ring
- OutcomeFeedbackRow: hover-triggered thumbs-up/down on AI messages

### Background Sessions
- OrderStatus extended: DRAFTED, SCHEDULED, WORKING, COMPLETED
- POST /v1/orders/from-session: creates Order from active chat
- BackgroundSessionButton replaces "+" in chat toolbar

### Test Results
- 37 new tests (30 outcomes + 7 orders)
- 1611 total (1608 passing, 3 skipped) — includes 66 CLI tests
- macOS build: clean

---

## Previous: Hestia CLI (CLI Sprints 1-5 + Bootstrap) — COMPLETE

Terminal-native interface for Hestia. `hestia-cli/` package with WebSocket streaming, prompt_toolkit REPL, Rich rendering, tool trust tiers, repo context injection, zero-friction bootstrap (auto-server-start + auto-register for localhost). 7 commits, 66 tests across 6 test files.

Key commits:
- `330bfb2` Sprint 1: WebSocket streaming backend
- `76fdf3a` Sprint 2: REPL + auth + streaming
- `bc0a9f3` Sprint 3: Tool trust tiers
- `bc38820` Sprint 4: Repo context + project file injection
- `1591264` Sprint 5: Polish + error handling
- `3945682` Bootstrap: auto-start server + auto-register
- `80a3f59` Fix: context instruction for small model prompting

## Previous: Explorer Files (Sprint 9A) — COMPLETE

Security-hardened file system CRUD. `hestia/files/` module with PathValidator (allowlist-first, TOCTOU-safe), FileAuditDatabase, FileManager. 9 API endpoints. macOS file browser. 66 tests.

## Previous: Unified Inbox (Sprint 9B) — COMPLETE

Apple Mail + Reminders + Calendar aggregation. `hestia/inbox/` module. 7 API endpoints. macOS inbox view with source filtering. Gmail OAuth eliminated (Apple Mail syncs all accounts). 36 tests.

## Previous: Research & Graph (Sprint 8) — COMPLETE
## Previous: Profile & Settings (Sprint 7) — COMPLETE
## Previous: Stability & Efficiency (Sprint 6) — COMPLETE
## Previous Sprints (1-5): COMPLETE

---

## Current: Sprint 11A — Model Swap + Coding Specialist

**Started:** 2026-03-05
**Design:** `docs/plans/2026-03-05-model-swap-planning-design.md`
**Plan:** `docs/plans/2026-03-05-sprint-11a-model-swap.md`
**ADR:** ADR-040

### Changes
- Primary model: `qwen2.5:7b` → `qwen3.5:9b` (better instruction following, 262K native context)
- New coding specialist: `qwen2.5-coder:7b` via `ModelTier.CODING` (88.4% HumanEval)
- Council SLM unchanged: `qwen2.5:0.5b`
- Routing: `complex_patterns` keyword matching → coding tier before complex tier
- CLI context budget: 6K → 16K chars, CLAUDE.md first in priority order
- Test fixtures: bulk update across 6 test files

### Hardware Upgrade Playbook
M5 Ultra Mac Studio (H2-2026, expected 256GB+ unified memory) — documented in design doc.

---

## Next: Sprint 11B — Command Center + MetaMonitor

**Plan:** `docs/plans/sprint-11-command-center-plan.md`
**Effort:** ~15 working days

### Decision Gate 2 (before Sprint 11B)
- Is OutcomeTracker collecting meaningful signals?
- Memory + CPU profile acceptable on M1?
- → Go/No-Go on MetaMonitor

### Sprint 11B Scope
1. MetaMonitor: consumes OutcomeTracker data, detects behavioral patterns
2. Command Center redesign: contextual metrics (Personal ↔ System), calendar week grid
3. Order creation wizard (multi-step)
4. ~42 new tests
