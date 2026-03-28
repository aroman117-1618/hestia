# Hestia Agentic Development System — Design Spec

**Date:** 2026-03-28
**Status:** Approved
**Author:** Andrew Lonati + Claude Opus 4.6
**Cross-Model Review:** Gemini 2.0 (11 findings, 10 accepted/partially accepted, 1 rejected)

---

## 1. Vision

Transform Hestia from a personal AI assistant into an enterprise-grade, staff-engineer-level autonomous development agent capable of:

- **Supervised coding** — Andrew describes a task, Hestia plans and executes with approval
- **Autonomous task execution** — Hestia receives an approved plan and delivers completed work end-to-end
- **Self-directed development** — Hestia discovers work (failing tests, issues, code quality), proposes plans, and executes after approval

All interactions feed into Hestia's memory pipeline. Every session makes the next session better.

### Core Principle: Observe Freely, Propose Freely, Execute Only With Approval

Hestia can continuously monitor, assess, and plan without restriction. But no code changes happen without Andrew's explicit approval of the plan. No exceptions.

---

## 2. Agent Hierarchy

Four tiers, each with a clear role, model, and authority level.

### 2.1 Architect — Claude Opus 4

- Reads task/issue, analyzes codebase
- Produces implementation plans
- Decomposes large tasks into subtasks
- Reviews Engineer's output (logic verification)
- Final merge decision
- Delegates to Researcher for complex/cross-cutting work
- Creates GitHub issues and PRs (soft approval for PRs)

**Authority:** Read any file, create plans, approve/reject work, create issues, create PRs (soft approval), merge approved PRs.

### 2.2 Researcher — Gemini 2.0 Pro

- Deep codebase analysis (leverages 1M context window)
- Cross-model code review (catches Claude blind spots)
- Architecture-level research and second opinions
- Dependency and impact assessment
- Delta research using past session summaries and technical learnings

**Authority:** Read-only. Advisory only — never writes code. Has memory retrieval for session summaries and technical learnings.

### 2.3 Engineer — Claude Sonnet 4

- Receives subtask plan from Architect
- Executes code changes (edit, write, shell)
- Runs targeted tests after each change
- Commits logical units of work
- Reports status back to Architect

**Authority:** Full tool access (edit, write, shell, git add/commit). Cannot push without soft approval. Cannot modify protected paths without Andrew's explicit approval. Cannot create PRs or issues.

### 2.4 Validator — Claude Haiku 4.5

- Runs full test suite after Engineer commits
- Lints and type-checks changed files
- Monitors for regressions (background, scheduled)
- Watches GitHub issues for new work
- Scans for code quality signals
- Reports findings to Architect (does NOT create issues directly)
- Runs pip-audit when dependency files change (via Sentinel integration)

**Authority:** Read-only on code. Can run tests, linters, xcodebuild, pip-audit (no writes). Reports to Architect. Cannot create issues or PRs directly.

### 2.5 Interaction Flow

```
Task arrives (CLI, GitHub, self-discovered)
  → Architect reads task, assesses complexity
  → [If complex] Researcher performs deep analysis (1M context)
  → Architect produces plan, decomposes subtasks
  → [APPROVAL GATE — Andrew approves plan]
  → For each subtask:
      → Engineer executes code changes
      → Engineer runs targeted tests, commits
      → Validator runs full test suite + lint (parallel)
      → [If tests fail] Architect decides: retry / replan / escalate
  → [If critical path] Researcher cross-model review of full diff
  → Architect reviews diff, creates PR
  → [Andrew approves PR on GitHub]
  → Architect merges PR → CI/CD runs on main
  → Notify Andrew → Store to memory
```

### 2.6 Model Cost Profile

| Task Type | Architect (Opus) | Engineer (Sonnet) | Researcher (Gemini) | Validator (Haiku) | Est. Cost |
|-----------|-----------------|-------------------|--------------------|--------------------|-----------|
| Bug fix (small) | 1 plan call | 3-5 tool loops | — | 1 test run | ~$0.50-1.00 |
| Feature (medium) | 2-3 plan/review | 10-20 tool loops | 1 research pass | 3-5 test runs | ~$2-5 |
| Refactor (large) | 5+ plan/review | 30-50 tool loops | 2 research + review | 10+ test runs | ~$8-15 |

---

## 3. Session Lifecycle & State Machine

### 3.1 DevSession States

```
QUEUED → PLANNING → [RESEARCHING] → PROPOSED → [APPROVAL GATE] → EXECUTING → VALIDATING → REVIEWING → COMPLETE
                                                                      ↑              |
                                                                      └──────────────┘ (more subtasks)

Side states: FAILED, BLOCKED, CANCELLED
```

### 3.2 The Approval Gate

Everything left of the gate is autonomous and continuous. Everything right requires Andrew's explicit approval.

- **QUEUED → PROPOSED:** Fully autonomous. Validator discovers, Architect assesses and plans.
- **PROPOSED → EXECUTING:** Requires Andrew's approval of the plan. No exceptions.
- **EXECUTING → COMPLETE:** Fully autonomous within the approved plan.
- **Replan → PROPOSED:** If the Architect changes the plan during execution, the new plan returns to Andrew for approval.

### 3.3 State Transitions

| Transition | Trigger | Side Effects |
|-----------|---------|--------------|
| QUEUED → PLANNING | Scheduler picks up task | Create git branch `hestia/dev-{session_id_short}` |
| PLANNING → RESEARCHING | Architect flags as complex | Invoke Researcher with file manifest |
| PLANNING/RESEARCHING → PROPOSED | Architect produces plan | Plan stored, proposal delivered to Andrew |
| PROPOSED → EXECUTING | Andrew approves plan | Invoke Engineer with first subtask |
| EXECUTING → VALIDATING | Engineer commits | Invoke Validator (test suite + lint) |
| VALIDATING → EXECUTING | Tests pass, more subtasks | Next subtask to Engineer |
| VALIDATING → FAILED | Tests fail | Architect decides: retry (→ EXECUTING, max 3), replan (→ PROPOSED, max 2), escalate (→ BLOCKED) |
| VALIDATING → REVIEWING | All subtasks done, tests pass | Architect reviews; Researcher if critical |
| REVIEWING → COMPLETE | Architect approves, PR merged | Merge branch, notify, store to memory, run compensating cleanup |
| Any → BLOCKED | Needs human input | Notification to Andrew |
| Any → CANCELLED | Andrew cancels | Compensating actions: delete remote branch, close PR, tag issues |

### 3.4 Failure Recovery

The Architect is the failure handler:

- **Retry** (max 3 per subtask) — "Engineer made a mistake, send it back with the error"
- **Replan** (max 2 per session, returns to PROPOSED for re-approval) — "Approach is wrong, need a different strategy"
- **Escalate** (→ BLOCKED) — "I don't understand this failure, Andrew needs to look"

**Token budget kill switch:** Per-session budget (configurable, default 500K tokens). If exceeded without reaching COMPLETE, force-kill → BLOCKED → notify Andrew.

### 3.5 Persistence

**`dev_sessions` table (SQLite):**

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT PK | Session identifier |
| source | TEXT | cli, github, self_discovered, scheduled |
| source_ref | TEXT | Issue #, CLI session ID, etc. |
| title | TEXT | Task title |
| description | TEXT | Full task description |
| state | TEXT | Current state (enum) |
| priority | INTEGER | 1 (critical) to 5 (background) |
| complexity | TEXT | simple, medium, complex, critical |
| branch_name | TEXT | Git branch for this session |
| plan | TEXT | Architect's plan (JSON) |
| subtasks | TEXT | Decomposed subtasks (JSON) |
| current_subtask | INTEGER | Progress tracker |
| architect_model | TEXT | Model used |
| engineer_model | TEXT | Model used |
| created_at | TEXT | Timestamp |
| started_at | TEXT | Execution start |
| completed_at | TEXT | Completion timestamp |
| total_tokens | INTEGER | Token usage |
| total_cost_usd | REAL | Cost tracking |
| error_log | TEXT | Failures, retries, escalations |

**`dev_session_events` table:**

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Event ID |
| session_id | TEXT FK | References dev_sessions |
| timestamp | TEXT | Event time |
| agent | TEXT | architect, engineer, researcher, validator |
| event_type | TEXT | plan_created, file_edited, test_run, commit, review, approval_requested, approval_granted, state_change, error |
| detail | TEXT | JSON blob (varies by type) |
| tokens_used | INTEGER | Tokens consumed |
| model | TEXT | Model used |
| files_affected | TEXT | JSON array of paths |

### 3.6 Rollback

Three levels, plus compensating actions for external side effects:

1. **Per-edit rollback** — Event log has before-hash. Restore file to pre-edit state.
2. **Per-subtask rollback** — Git revert the subtask's commits.
3. **Full session abort** — Delete the feature branch. Main untouched.
4. **Compensating actions** — On abort/cancel: delete remote branch, close PR with "cancelled" label, tag related issues as stale. Send follow-up notification "Session #X cancelled."

---

## 4. Context Management & Memory Integration

### 4.1 Context Assembly Per Tier

Each tier gets a tailored context builder. No shared context window.

**Architect (Opus, ~25-35K tokens):**
- System prompt: CLAUDE.md conventions (~2K), SPRINT.md (~1K), project file tree (~3K), Architect role instructions (~1K)
- Context: memory recall — session summaries + failure patterns (top 5 by relevance, ~5K), git log (~2K), git status (~500), task description (~2K), relevant file summaries (~10-20K)

**Researcher (Gemini 2.0 Pro, ~80-500K tokens):**
- Context: Architect's analysis + questions (~3K), full source of affected modules (~50-200K), full test files (~20-50K), architecture docs (~10-30K), session summaries + technical learnings from memory (~5-10K)

**Engineer (Sonnet, ~15-60K tokens, dynamic):**
- System prompt: code conventions (~2K), tool definitions (~3K), Engineer role instructions (~1K)
- Context: subtask plan from Architect (~1-3K), target files full content (~5-20K), related test files (~3-10K), Researcher findings distilled by Architect (~2-5K), technical learnings from memory for target files (~1-3K), codebase invariants (~1K)
- **Dynamic scaling:** If subtask touches >3 files, Architect must decompose further OR increase Engineer budget (up to 60K)

**Validator (Haiku, ~5-18K tokens):**
- Context: git diff (~2-10K), pytest output (~2-5K), lint/type-check output (~1-2K), changed file list (~500)
- No memory retrieval — works purely on current state

### 4.2 Memory Types (4 types)

**1. Session Summaries** — stored on COMPLETE
- What was done, why, key decisions, files changed
- Retrieved by: Architect (semantic search), Researcher (delta research)
- Example: "Refactored memory consolidator — similarity threshold needed per-type tuning, not a global value"

**2. Technical Learnings** — stored per-subtask
- File-specific gotchas and patterns
- **Stored with file content hash** for staleness detection
- Retrieved by: Engineer (tag-based lookup on file paths), Researcher (delta research)
- On retrieval: if current file hash differs from stored hash, flag as "Unverified" in context
- Example: "handler.py: _store_conversation must be called AFTER streaming completes, not inside the generator"

**3. Failure Patterns** — stored on FAILED/retry
- What approach was tried, why it failed, what worked instead
- Retrieved by: Architect (semantic search on similar tasks)
- Example: "Attempted to mock ToolRegistry — doesn't work because singleton caches. Must use fresh registry fixture."

**4. Codebase Invariants** — stored when discovered during development
- Runtime-discovered "never do X" rules that aren't in CLAUDE.md
- **Always injected** into Architect and Engineer system prompts
- Promoted to CLAUDE.md during handoff if broadly applicable
- Example: "Never import from hestia.logging.logger — module doesn't exist. Always use hestia.logging"

### 4.3 Memory Retrieval Matrix

| Agent | Session Summaries | Technical Learnings | Failure Patterns | Codebase Invariants |
|-------|------------------|--------------------|-----------------|--------------------|
| Architect | Semantic search (top 5) | — | Semantic search (top 5) | Always injected |
| Researcher | Semantic search (top 10) | Tag-based (affected files) | — | — |
| Engineer | — | Tag-based (subtask files) | — | Always injected |
| Validator | — | — | — | — |

### 4.4 Memory Lifecycle

- **Storage:** Architect generates summaries, learnings, and failure patterns at state transitions (COMPLETE, per-subtask, FAILED). Stored via existing MemoryManager pipeline.
- **Staleness:** Technical learnings store file content hash. On retrieval, if hash mismatches, memory is flagged "Unverified" — included in context but clearly marked.
- **Pruning:** Existing ImportanceScorer + Consolidator + Pruner extended to dev-session memories. Hash-invalidated learnings get lower importance scores → pruned faster.
- **Invariant promotion:** During `/handoff`, review accumulated codebase invariants. Broadly applicable ones get promoted to CLAUDE.md. Session-specific ones remain in memory.

### 4.5 The Learning Loop

```
Session N: Engineer struggles with memory consolidator tests (3 retries)
  → Failure pattern stored: "consolidator tests need isolated ChromaDB instance"
  → Technical learning stored: "test_memory_consolidator.py requires fresh DB fixture"

Session N+1: New task touches consolidator
  → Engineer's context includes both learnings (tagged to file paths)
  → Zero retries. First-pass success.

Session N+5: consolidator.py refactored significantly (hash changed)
  → Learnings flagged as "Unverified" — still included but marked
  → Engineer validates or discards based on current code
  → If still valid, new learning stored with updated hash
```

---

## 5. Tool System & Safety

### 5.1 Tool Authority Matrix

| Tool | Architect | Researcher | Engineer | Validator | Approval |
|------|-----------|-----------|----------|-----------|----------|
| read_file | ✓ | ✓ | ✓ | ✓ | Auto |
| glob_files / grep_files | ✓ | ✓ | ✓ | ✓ | Auto |
| git_status / git_diff / git_log | ✓ | ✓ | ✓ | ✓ | Auto |
| edit_file | — | — | ✓ | — | Auto (within plan) |
| write_file | — | — | ✓ | — | Auto (within plan) |
| git_add / git_commit | — | — | ✓ | — | Auto ([hestia-auto] prefix) |
| git_branch | ✓ | — | ✓ | — | Auto |
| run_tests | ✓ | — | ✓ | ✓ | Auto |
| xcode_build | — | — | ✓ | ✓ | Auto |
| run_command (non-test) | — | — | ✓ | — | Soft approval |
| server_restart | ✓ | — | ✓ | — | Auto (logged) |
| git_push | ✓ | — | ✓ | — | Soft approval (feature branches only) |
| edit_file (protected paths) | — | — | ✓ | — | **Andrew's explicit approval** |
| create_github_issue | ✓ | — | — | — | Auto ([hestia-discovered] tag) |
| create_github_pr | ✓ | — | — | — | Soft approval |
| merge_github_pr | ✓ | — | — | — | After Andrew's GitHub approval |
| notify_andrew | ✓ | — | ✓ | ✓ | Auto (rate-limited) |
| pip_audit | — | — | — | ✓ | Auto (on dependency changes) |

### 5.2 Protected Path Handling

Protected paths: `hestia/security/`, `hestia/config/`, `.env`, `.claude/`

Flow: Engineer requests edit → Architect reviews and recommends → **Andrew explicitly approves** (via CLI, macOS app, or GitHub) → Engineer executes the edit → Andrew notified of completion.

Elevation is per-file, per-session. Not a blanket unlock.

### 5.3 Approval Definitions

- **Auto:** No approval needed. Tool executes immediately. Logged.
- **Soft approval:** Hestia asks Andrew to confirm before proceeding. Delivered via whichever surface Andrew is on (CLI prompt, macOS notification action, GitHub comment). Non-blocking — session pauses at this step until approved, other sessions continue.
- **Andrew's explicit approval:** Hard gate. Same delivery as soft approval, but for higher-risk operations (protected paths, PR merges). Requires affirmative action — no timeout-based auto-approve.

### 5.4 Safety Invariants (Never Violated)

**Hard stops:**
- Never push directly to main (always via approved PR merge)
- Never modify .env files
- Never bypass sandbox blocked patterns (sudo, rm -rf /, chmod 777, etc.)
- Never execute code changes without an approved plan
- Max 3 retries per subtask before escalation
- Max 2 replans per session before escalation (each replan returns to Andrew for approval)
- Per-session token budget (default 500K, configurable) — force-kill on exceed

**Audit trail guarantees:**
- Every file edit logged with before/after content hash
- Every tool call logged with args + result
- Every state transition logged with timestamp
- Every approval/denial logged with source (CLI, macOS, GitHub)
- Every commit tagged with session ID in message
- Every push logged with branch + commit SHA
- All events queryable via API + CLI
- Full session replay from event log

### 5.4 Rollback + Compensating Actions

| Level | Action | Scope |
|-------|--------|-------|
| Per-edit | Restore file from before-hash in event log | Single file |
| Per-subtask | Git revert subtask commits | One logical unit |
| Full session | Delete feature branch | All session work |
| Compensating | Delete remote branch, close PR (label: cancelled), tag issues as stale, send cancellation notification | External side effects |

### 5.5 Notification Rate Limiting

- Critical: Unlimited (security vulnerabilities, tests broken on main)
- High: Max 10/hour (new assigned issues, dependency alerts)
- Normal: Batched into daily briefing
- Background: Batched into weekly summary

---

## 6. Work Discovery & Proposal Delivery

### 6.1 Discovery Sources

The Validator runs on a configurable schedule (default: every 30 minutes when server is running):

1. **Test monitor** — runs pytest full suite. New failures → critical proposal.
2. **GitHub poll** — checks project board for new/assigned issues. Creates proposals for unplanned items.
3. **Code quality scan** — dead imports, type errors, TODO comments with dates. Batches into weekly summary.
4. **Dependency check** — pip-audit + outdated package scan. Monthly cadence.

Each discovery → `dev_sessions` row (QUEUED) → Architect assesses and plans → proposal delivered.

### 6.2 Proposal Delivery (Three Surfaces)

**Primary — GitHub Issues:**
- Each proposal becomes an issue tagged `[hestia-proposal]`
- Plan in the issue body: title, context, plan steps, files, risk, time estimate
- Approve via comment command (`/approve`) or reaction
- Tagged with priority label

**Primary — macOS Command Tab:**
- Proposals surface as actionable cards in the System Alerts / Internal section
- One-tap approve / skip / modify
- Same data as GitHub issue: plan, files, risk, estimate
- Approval syncs with backend immediately

**Secondary — CLI:**
- `/dev proposals` lists pending proposals
- `/dev approve [id]` approves inline
- Available for terminal-first workflows, not the primary review surface

First approval from any surface wins — no double-execution risk. Backend tracks which surface the approval came from in the audit log.

### 6.3 Priority-Based Delivery

| Priority | Delivery | Example |
|----------|----------|---------|
| Critical | Immediate macOS notification + push + GitHub issue | Tests broken on main, security vulnerability |
| High | macOS notification + GitHub issue | New assigned issue, dependency update |
| Normal | Daily briefing + GitHub issue | Code quality improvement, refactor opportunity |
| Background | Weekly summary only | Style inconsistencies, documentation drift |

### 6.4 Briefing Integration

Existing proactive briefing system (`hestia/proactive/`) extended with:

- **"Development Proposals"** section — pending proposals awaiting approval
- **"Dev Session Summary"** section — completed sessions since last briefing
- **"Needs Attention"** section — failed/blocked sessions
- Batch approval supported from briefing review

---

## 7. CLI Integration

### 7.1 New Commands

| Command | Purpose |
|---------|---------|
| `/dev <task>` | Start supervised dev session — Architect plans, Andrew approves inline, full execution |
| `/dev queue` | Show queued/active/completed dev sessions |
| `/dev status [id]` | Session detail: state, subtask progress, events |
| `/dev approve [id]` | Approve a pending proposal |
| `/dev cancel [id]` | Cancel a session (triggers compensating actions) |
| `/dev rollback [id]` | Interactive rollback: per-edit, per-subtask, or full branch delete |
| `/dev log [id]` | Full event audit log for a session |
| `/dev proposals` | List pending proposals |
| `/dev config` | Configure: notification cadence, model overrides, token budgets, discovery schedule |

### 7.2 Relationship to Existing Commands

- `/code` remains for quick single-pass agentic coding (existing behavior, unchanged)
- `/dev` is the full multi-tier system for serious development work
- `/cloud` controls routing mode (unchanged — full-cloud required for dev sessions)

### 7.3 Integration with Existing Systems

| System | Integration |
|--------|-------------|
| Orders (scheduled prompts) | Can trigger dev sessions on a schedule |
| Memory pipeline | All sessions → 4 memory types (summaries, learnings, failures, invariants) |
| Notification relay | `notify_andrew` uses existing macOS + APNs infrastructure |
| GitHub Project Board | `roadmap-sync.sh` updated to handle dev session issues |
| Proactive briefings | Proposals + summaries injected into briefing content |
| Sentinel | pip-audit integration for dependency security checks |

---

## 8. Cloud Model Registry Updates

### 8.1 New Models Required

| Model | ID | Context | Max Output | Role |
|-------|----|---------|------------|------|
| Claude Opus 4 | `claude-opus-4-20250514` | 200K | 32K | Architect |
| Claude Sonnet 4 | `claude-sonnet-4-20250514` | 200K | 8K | Engineer (existing) |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | 200K | 8K | Validator |
| Gemini 2.0 Pro | `gemini-2.0-pro` | 1M | 8K | Researcher (existing) |

### 8.2 Routing for Dev Sessions

Dev sessions bypass the normal inference router. Each tier calls its designated model directly via `force_model` parameter. The council SLM remains local (unchanged).

---

## 9. New Module Structure

```
hestia/dev/
├── __init__.py
├── models.py            # DevSession, DevSessionEvent, DevSubtask, Proposal enums/models
├── database.py          # SQLite persistence (dev_sessions, dev_session_events)
├── manager.py           # DevSessionManager — singleton, session lifecycle orchestration
├── architect.py         # Architect agent — planning, review, decomposition
├── engineer.py          # Engineer agent — code execution, tool loop
├── researcher.py        # Researcher agent — deep analysis, cross-model review
├── validator.py         # Validator agent — test/lint, background monitoring
├── context_builder.py   # Per-tier context assembly
├── memory_bridge.py     # Store/retrieve dev-specific memories (4 types)
├── discovery.py         # Background work discovery (test monitor, GitHub poll, quality scan)
├── proposal.py          # Proposal creation + delivery (GitHub, macOS, CLI)
├── safety.py            # Authority matrix enforcement, token budget, rate limiting
└── tools.py             # New tool definitions (run_tests, git_push, etc.)
```

API routes: `hestia/api/routes/dev.py` — session CRUD, approval endpoints, event queries.

CLI commands: extend `hestia-cli/hestia_cli/commands.py` with `/dev` command family.

macOS integration: new `ProposalCardView` in `Shared/Views/Command/` for the Command tab.

---

## 10. Gemini Critique Incorporation Summary

| # | Finding | Resolution |
|---|---------|------------|
| S3-1 | Context cliff (Researcher → Engineer) | Dynamic Engineer context budget; Architect distills Researcher output |
| S3-2 | Haiku as sole validator | Haiku for mechanical checks; Architect (Opus) + Researcher for logic review |
| S3-3 | Zombie learnings | File content hash stored with each learning; "Unverified" flag on mismatch |
| S3-4 | Researcher memory blindness | Researcher gets session summaries + technical learnings for delta research |
| S3-5 | Missing global constraints | 4th memory type: Codebase Invariants (always-inject, promote to CLAUDE.md) |
| S4-1 | LLM approving protected paths | Upgraded: Andrew's explicit approval required for protected path edits |
| S4-2 | Rollback doesn't undo externals | Compensating actions manifest: delete remote branch, close PR, tag issues |
| S4-3 | Validator issue spam | Removed issue creation from Validator; Architect decides |
| S4-4 | Docker containerization | Rejected — native macOS platform, scoped privilege is correct |
| S4-5 | Missing dependency auditor | Sentinel pip-audit wired into Validator post-commit checks |
| S4-6 | Token budget burn | Per-session token budget (500K default), force-kill on exceed |
