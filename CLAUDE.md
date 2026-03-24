# CLAUDE.md - Hestia Project Context

---

## MANDATORY: 4-Phase Development Workflow

**Every non-trivial Hestia task MUST follow this 4-phase structure.**

### Phase 1: Research
- Explore relevant codebase before writing code (use **@hestia-explorer**, Haiku)
- Identify affected files, dependencies, patterns, edge cases
- Present findings with reasoning, not just conclusions

### Phase 2: Plan
- Confirm decisions with Andrew before implementing
- Draft specific implementation plan (files, changes)
- Pressure-test: What could go wrong? Edge cases? Iterate 3x before executing
- **Add a SPRINT.md stub** at sprint start (title + date) so board and docs stay in sync from day one — don't wait until Phase 4

### Phase 3: Execute
- Implement precisely. Run **@hestia-tester** (Sonnet) after each significant change
- Fix issues immediately — never accumulate tech debt
- Commit after each logical unit of work (one feature, one fix, one refactor)
- Never combine unrelated changes in a single commit — enables git bisect and code review
- **Move the sprint item to "In Progress" on the GitHub Project board** (`scripts/roadmap-sync.sh status <item-id> in_progress`)

### Phase 4: Review
- Run **@hestia-reviewer** (Sonnet) on all changed files — REQUIRED for any change touching >5 files
- Not optional when velocity is high — that's exactly when regressions hide
- **For UI sprints:** Run **@hestia-ui-auditor** (Sonnet) + capture visual validation screenshots of every affected screen. See `docs/discoveries/ui-wiring-audit-methodology-2026-03-19.md`
- Update affected docs (this file, `docs/api-contract.md`, `docs/hestia-decision-log.md`)
- **Mark the sprint item "Done" on the GitHub Project board** (`scripts/roadmap-sync.sh status <id> done`)
- If new work was identified during the session, **create issues** via `scripts/roadmap-sync.sh issue` (see "Add to Roadmap" workflow below)
- **REQUIRED: Run `scripts/sync-board-from-sprint.sh` before session end. This is not optional.**

### Sub-Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| @hestia-explorer | Haiku | Phase 1: Find code, trace architecture |
| @hestia-tester | Sonnet | Phase 3: Run tests, diagnose failures |
| @hestia-reviewer | Sonnet | Phase 2: Plan audit, Phase 4: Code audit, Session retro + docs check |
| @hestia-build-validator | Sonnet | Phase 3: Verify iOS + macOS Xcode builds compile |
| @hestia-simplifier | Sonnet | Post-Phase 3: Find dead code, over-abstraction, unnecessary complexity |
| @hestia-preflight-checker | Haiku | Fast environment health dashboard (server, git, processes, Ollama) |
| @hestia-critic | Sonnet | Strategic adversarial critique of architectural decisions and features |
| @hestia-ui-auditor | Sonnet | Phase 4: 4-layer UI wiring audit (hardcoded values, component cross-ref, error handling, endpoint gaps) |
| @hestia-deployer | Sonnet | Deploy to Mac Mini when requested |

Definitions: `.claude/agents/`. Read-only specialists — diagnose and report, never modify code.

### Hook Scripts

| Script | Trigger | Purpose |
|--------|---------|---------|
| `scripts/validate-security-edit.sh` | Before security file edits | Catches plaintext secrets, wildcard CORS, bare excepts |
| `scripts/auto-test.sh` | After Python source edits | Runs matching test file automatically |
| `scripts/roadmap-sync.sh` | Manual / Phase 2+3+4 | Full roadmap sync: issues, labels, dates, board |
| `scripts/sync-board-from-sprint.sh` | Phase 4 / /handoff | Reconcile board state from SPRINT.md (dry run by default, `--apply` to execute) |
| `scripts/audit-hardcoded.sh` | Phase 4 (UI sprints) | Layer 1: Find hardcoded values, empty closures, color literals in Views |
| `scripts/audit-endpoint-gaps.sh` | Phase 4 (UI sprints) | Layer 4: Cross-reference backend endpoints against client API calls |

### GitHub Project Board & Roadmap Sync
Hestia roadmap lives at **GitHub Project #1** (`aroman117-1618/hestia`, Projects tab). **Use `scripts/roadmap-sync.sh` for ALL project board operations**.

#### "Add to Roadmap" Workflow (MANDATORY)
When Andrew says **"add it to the roadmap"** or **"let's put this on the roadmap"**, Claude MUST do ALL of the following automatically — no further prompting required:

1. **SPRINT.md** — Add/update the sprint entry with workstream details, hours, and phase
2. **Plan document** — Create or update the relevant `docs/plans/*.md` file with full scope, architecture, and acceptance criteria
3. **GitHub Issues** — Create proper issues via `scripts/roadmap-sync.sh issue`:
   ```bash
   scripts/roadmap-sync.sh issue "<title>" \
     --labels "sprint-XX,backend,macos" \
     --hours N \
     --sprint "Sprint XXA" \
     --start "YYYY-MM-DD" \
     --deadline "YYYY-MM-DD" \
     --depends "WS1,WS3" \
     --plan "docs/plans/plan-name.md"
   ```
4. **CLAUDE.md** — Update project structure, endpoint counts, test counts if they changed

#### Date Estimation Rules
- Andrew's availability: ~12 hours/week hands-on + autonomous Claude Code acceleration
- Quick wins (<3h): Same day as start
- Medium tasks (3-10h): 1-2 day span
- Large tasks (10-20h): 3-5 day span
- Multi-phase (20h+): 1-2 week spans with phase boundaries on Mondays

#### Daily Operations
- **At session start:** Run `scripts/roadmap-sync.sh list` to orient against current board state
- **Execution (Phase 3):** Move the item to In Progress — `scripts/roadmap-sync.sh status <id> in_progress`
- **Review (Phase 4 / handoff):** Mark it Done — `scripts/roadmap-sync.sh status <id> done`
- **Reconciliation:** If board state looks stale, run `scripts/roadmap-sync.sh reconcile`

---

## Server Management

After ANY backend code change, always kill stale server processes before restarting. Use `lsof -i :8443 | grep LISTEN` to find and `kill -9` old PIDs. Never assume the running server has picked up code changes without a full restart cycle. Stale processes are the #1 recurring time sink.

## Session Continuity

When resuming work, FIRST read `SESSION_HANDOFF.md` (if it exists) and any TODO files. Do NOT search through bash history or compacted transcripts — use the structured handoff documents. Project plans and workstreams are in `docs/`. Current focus: **Trading Module (Sprints 21–30)**. Plan: `docs/discoveries/trading-module-research-and-plan.md`. See `SPRINT.md`.

## Debugging Approach

When diagnosing bugs, consider the full stack before concluding root cause. Check:
1. Is the server running the latest code? (kill stale processes first)
2. Is this a backend issue or client-side issue?
3. Are permissions (TCC, entitlements) at the system level, not just app level?
4. What are the runtime environment constraints (simulator, sandbox, etc.)?

Do NOT assume the first hypothesis is correct — validate before implementing fixes. List 3 possible root causes, run a quick diagnostic for each, then fix the confirmed cause.

---

## What is Hestia?

Locally-hosted personal AI assistant on Mac Mini M1. Jarvis-like: competent, adaptive, sardonic, anticipates needs.

**Three Agents:** Hestia (coordinator), Artemis (analysis), Apollo (execution). Hestia routes internally. `@artemis`/`@apollo` override available. See ADR-042.

## Technical Stack

| Component | Technology |
|-----------|------------|
| Hardware | Mac Mini M1 (16GB) |
| Model | Qwen 3.5 9B (Hestia) + DeepSeek-R1-14B (Artemis) + Qwen 3 8B (Apollo) + cloud (Anthropic/OpenAI/Google) |
| SLM | qwen2.5:0.5b (council intent classification, ~100ms) |
| Backend | Python 3.12, FastAPI, 240 endpoints across 30 route modules |
| Storage | ChromaDB (vectors) + SQLite (structured) + macOS Keychain (credentials) |
| App | Native Swift/SwiftUI (iOS 26.0+, macOS 15.0+) |
| API | REST on port 8443 with JWT auth, HTTPS with self-signed cert |
| Remote | Tailscale (`andrewroman117@hestia-3.local`) |
| Dev Tools | Claude Code (API billing) + Xcode |
| CI/CD | GitHub Actions → Mac Mini (auto-deploy on push to main) |

## Current Status

**All foundation work complete** (MVP phases 0-7, Intelligence WS1-4, UI phases 1-4, Frontend Wiring sprints 1-5, CLI sprints 1-5, Stability sprints 6-7+12, HealthKit, Wiki, macOS app). See `SPRINT.md` for full history.

**Active: Trading Module (Sprints 21-30).** Sprints 21-27 COMPLETE. **Live trading active on Mac Mini since 2026-03-24** — 4 Mean Reversion bots (BTC/ETH/SOL/DOGE) running via `bot_service.py` launchd service, market orders on Coinbase. Alpaca (stocks) paused — API key pending with support team.

2979 tests (2844 backend + 135 CLI), 92 test files. Full details: `python -m pytest tests/ -v --timeout=30`

---

## Code Conventions

- **"Orders" = "Workflows"**: The user-facing term is **Orders** (sidebar, Command Center, sheets). The backend module, API paths, and Swift types use `workflow`/`Workflow` internally. Never introduce "Workflow" in user-visible strings.
- **Type hints**: Always. Every function signature.
- **Async/await**: For all I/O (database, inference, network).
- **Logging**: `logger = get_logger()` — no arguments. Never `HestiaLogger(component=...)` or `get_logger(component=...)`. Import: `from hestia.logging import get_logger`. LogComponent enum: ORCHESTRATION, MEMORY, INFERENCE, EXECUTION, SECURITY, API, SYSTEM, VOICE, COUNCIL, HEALTH, WIKI, EXPLORER, NEWSFEED, INVESTIGATE, RESEARCH, FILE, INBOX, OUTCOMES, APPLE_CACHE, LEARNING, VERIFICATION, TRADING, NOTIFICATION. (23 components total)
- **Config**: YAML files, never hardcode.
- **Error handling in routes**: `sanitize_for_log(e)` from `hestia.api.errors` in logs (never raw `{e}`). Generic messages in HTTP responses (never `detail=str(e)`).
- **File naming**: `snake_case.py` (Python), UpperCamelCase.swift (iOS).
- **Manager pattern**: `models.py` + `database.py` + `manager.py` per module. Singleton via `get_X_manager()` async factory.
- **iOS patterns**: `@MainActor ObservableObject` with `@Published`. DesignSystem tokens. No force-unwraps. `[weak self]` in closures. `#if DEBUG` for all `print()`.
- **New module checklist**: (1) `LogComponent` enum, (2) `auto-test.sh` mapping, (3) `validate-security-edit.sh` if creds, (4) sub-agent definitions, (5) project structure in CLAUDE.md.

## Testing

Always run the full test suite (`python -m pytest`) after making changes and ensure all tests pass before considering a task complete. If tests are failing at session end, explicitly note which tests fail and why in a summary.

**pytest hang:** The pytest process may hang after all tests pass (ChromaDB background threads). In shell scripts, use the `run_with_timeout` pattern from `scripts/pre-push.sh`. In Claude Code, the Bash tool handles this automatically.

## iOS / Swift Specifics

- Simulator has Face ID limitations — use mock auth for development builds
- Asset catalogs must have matching JSON metadata files; don't just copy images
- Always verify SwiftUI previews compile after changes
- **Xcode build cache**: After committing Swift changes, MUST clean build (Shift+Cmd+K) or changes won't appear. Xcode aggressively caches and won't pick up file changes without a clean.
- Mac Mini deployment target: `andrewroman117@hestia-3.local` (via Tailscale)
- **APIClient HTTP methods**: `get()`, `put()`, `delete()` are internal (not private). ViewModels can call them directly with generic return types: `let response: MyType = try await APIClient.shared.get("/v1/path")`.

## Multi-Target Builds (macOS + iOS)

When creating or editing Swift files:
- Check which targets the file belongs to before editing
- Verify imports and APIs are available on both platforms
- Use `#if os(macOS)` / `#if os(iOS)` guards when needed
- Always build BOTH targets after changes: `xcodebuild -scheme HestiaWorkspace` and `xcodebuild -scheme HestiaApp`

`macOS/Models/` contains 2 Mac-specific files: `HealthDataModels.swift` and `ResearchModels.swift`. WikiModels, ToolModels, DeviceModels, and NewsfeedModels are in `Shared/Models/` (included in macOS target via `project.yml` — NOT duplicated).

## Python Environment

Use Python 3.12 (not 3.13+). Pin version in pyproject.toml with `requires-python = ">=3.11,<3.13"`. Python 3.14 is known to cause MCP server incompatibilities.

## Security Posture

- Biometric auth (Face ID/Touch ID) for sensitive data
- Three-tier credential partitioning (operational/sensitive/system)
- Double encryption (Fernet + Keychain AES-256)
- External communication gate (nothing sent without approval)
- JWT device auth, 90-day expiry, Keychain-stored secret
- Invite-based device registration (QR code onboarding, one-time nonce tokens)
- Error sanitization in all API routes

## Andrew's Context

- **Skills**: Strong SQL/APIs, growing Python/infra
- **Time**: ~12 hours/week (hands-on) + autonomous Claude Code acceleration
- **Style**: 70% teach-as-we-build, 30% just-make-it-work
- **Tools**: Claude Code (Opus 4.6, API billing) + Xcode reviews

---

## Project Structure

```
hestia/
├── hestia/                          # Python backend — 31 modules
│   ├── database.py                  # BaseDatabase ABC (shared by all SQLite modules)
│   ├── security/                    # CredentialManager (Keychain + Fernet)
│   ├── logging/                     # HestiaLogger, AuditLogger, LogComponent enum
│   ├── inference/                   # InferenceClient (Ollama + cloud), ModelRouter
│   ├── cloud/                       # CloudManager, CloudInferenceClient (Anthropic/OpenAI/Google)
│   ├── council/                     # CouncilManager (4-role, dual-path), IntentType, prompts
│   ├── memory/                      # MemoryManager, ChromaDB, SQLite, TemporalDecay, ImportanceScorer, Consolidator, Pruner
│   ├── orchestration/               # RequestHandler, StateMachine, ModeManager, PromptBuilder, AgentOrchestrator
│   ├── execution/                   # ToolExecutor, ToolRegistry, Sandbox, CommGate
│   ├── apple/                       # 20 tools (Calendar, Reminders, Notes, Mail)
│   ├── health/                      # HealthKit sync, metrics DB, coaching, 5 chat tools
│   ├── explorer/                    # ExplorerManager, resource aggregation, draft CRUD, TTL cache
│   ├── tasks/                       # BackgroundTask lifecycle + approval workflow
│   ├── orders/                      # Scheduled prompts + APScheduler
│   ├── agents/                      # AgentProfile CRUD + snapshots
│   ├── user/                        # UserProfile + settings + push tokens
│   ├── proactive/                   # Briefings, PatternDetector, InterruptionPolicy
│   ├── voice/                       # TranscriptQualityChecker, JournalAnalyzer (3-stage)
│   ├── wiki/                        # Architecture field guide (AI-generated + static docs)
│   ├── newsfeed/                    # Materialized timeline, source aggregation, per-user state
│   ├── notifications/               # Intelligent notification relay (macOS + APNs)
│   ├── outcomes/                    # Chat outcome tracking for Learning Cycle
│   ├── inbox/                       # Unified inbox (mail + reminders + calendar aggregation)
│   ├── files/                       # Secure filesystem CRUD with audit trail
│   ├── apple_cache/                 # FTS5 metadata cache for Apple ecosystem fuzzy resolution
│   ├── learning/                    # MetaMonitor, Memory Health, Trigger Metrics, Scheduling
│   ├── verification/                # Response verification module
│   ├── trading/                     # Autonomous crypto trading (Sprint 21+)
│   ├── workflows/                   # Workflow orchestration engine (P0 complete, P1-P4 planned)
│   ├── research/                    # Knowledge graph + PrincipleStore + Temporal Facts + Episodic Nodes
│   ├── investigate/                 # URL content analysis (web articles, YouTube)
│   ├── workflows/                   # DAG workflow engine (executor, nodes, scheduler, migration, interpolation)
│   ├── api/                         # FastAPI — 240 endpoints, 30 route modules
│   └── config/                      # inference.yaml, execution.yaml, memory.yaml, triggers.yaml, wiki.yaml, workflow.yaml
├── hestia-cli/                      # Python CLI (REPL, auth, bootstrap, context, renderer)
├── hestia-cli-tools/                # Swift CLIs (keychain, calendar, reminders, notes)
├── HestiaApp/                       # iOS + macOS SwiftUI app
│   ├── Shared/                      # Cross-platform: App, DesignSystem, Models, Services, ViewModels, Views
│   ├── macOS/                       # macOS app: Views, ViewModels, Models, Services, DesignSystem
│   ├── WorkflowCanvas/              # React Flow + Vite project (bundled → macOS/Resources/WorkflowCanvas/index.html)
│   └── project.yml                  # xcodegen config (iOS 26.0, macOS 15.0, Swift 6.1)
├── tests/                           # 2979 tests, 92 files
├── scripts/                         # deploy, test-api, auto-test, validate-security, ollama
├── docs/                            # api-contract, decision-log, security-architecture
└── data/ + logs/                    # Runtime storage
```

Full API details: `docs/api-contract.md` or `/docs` (Swagger)

---

## Key Architecture Notes

**Cloud Routing (3-state):** disabled → enabled_smart (local-first, cloud spillover) → enabled_full (cloud-first). State propagation via `_sync_router_state()` after every mutation. API keys in Keychain, never returned.

**Council (dual-path):** Cloud active → 4 roles in parallel via `asyncio.gather`. Cloud disabled → SLM intent only + existing pipeline. Purely additive (try/except, failures fall back silently). CHAT optimization skips Analyzer/Validator/Responder when confidence > 0.8.

**Agent Orchestrator (ADR-042):** Council classifies intent → `AgentRouter` maps to route (HESTIA_SOLO, ARTEMIS, APOLLO, ARTEMIS_THEN_APOLLO). Confidence gating: >0.8 = specialist, 0.5-0.8 = enriched solo, <0.5 = pure solo. Kill switch: `orchestration.yaml → enabled: false`.

**Memory Lifecycle:** ImportanceScorer (0.3 recency + 0.4 retrieval freq + 0.3 type bonus), Consolidator (embedding dedup >0.90), Pruner (>60d + importance <0.2, soft-delete). Zero-LLM. Scheduled via LearningScheduler.

**Knowledge Graph (ADR-041):** Bi-temporal facts on SQLite edges between entities. Entity resolution via canonical dedup. Two modes: `legacy` (co-occurrence) and `facts` (entity-relationship). On-demand extraction.

**Key ADRs** (full list: `docs/hestia-decision-log.md`):
- ADR-001/040: Dual local model — 4-tier routing (PRIMARY → CODING → COMPLEX → CLOUD)
- ADR-041: Knowledge Graph — bi-temporal facts on SQLite, Graphiti-inspired
- ADR-042: Agent Orchestrator — coordinate/analyze/delegate, council extension

---

## Active Roadmap

### Trading Module — Sprints 21–30 (APPROVED 2026-03-18)
Sprints 21-27 COMPLETE. Paper soak LIVE on Mac Mini since 2026-03-19. Coinbase adapter live-ready.

| Sprint | Status | Scope |
|--------|--------|-------|
| Sprint 27: Go-Live | LIVE (Coinbase) | 4 MR bots live since 2026-03-24, market orders, 8-layer risk armed |
| Sprint 27.5: Validation | WS1 DONE, WS2-3 TODO | Backtest validation complete (strategy issues found), infra hardening remaining |
| Sprint 28: Regime Detection | TODO (after 30+ fills) | Rule-based regime detection (ADX+SMA+ATR), strategy router |
| Sprint 29: Alpaca + Stocks | BLOCKED | Alpaca API key pending — Andrew working with support team |
| Sprint 30: Portfolio Optimization | TODO | Rebalancing, dashboard, walk-forward validation |

**Plan:** `docs/discoveries/trading-module-research-and-plan.md`
**Critical path:** S27.5 remaining → $25 live capital → 30+ fills → S28. Alpaca (S29) unblocked when API key resolves.

### Known Issues (Mac Mini)
- Council needs `qwen2.5:0.5b` pulled on Mac Mini
- Server must be restarted after code deploys (no hot-reload)

---

## Quick Commands

```bash
source .venv/bin/activate
hestia                                 # CLI — auto-starts server, auto-registers
python -m hestia.api.server            # Start server manually
python -m pytest tests/ -v             # Run tests
./scripts/test-api.sh                  # API smoke tests (14)
./scripts/deploy-to-mini.sh            # Deploy to Mac Mini
hestia-preflight                       # On-demand validation (shell function)
```

## Validation Tiers

| Tier | Trigger | Checks |
|------|---------|--------|
| Pre-push (feature) | `git push` on any branch | Kill stale servers + pytest |
| Pre-push (main) | `git push` on main | + xcodebuild |
| On-demand | `hestia-preflight` in terminal | Same as main pre-push |
| Full | `/preflight` in Claude Code | Server restart + tests + connectivity + permissions |

## Skills — Invocation Matrix

Use this to pick the right skill. If unsure, start with `/discovery`.

| Scenario | Skill | Why |
|----------|-------|-----|
| Investigating a new topic, technology, or approach | `/discovery` | SWOT + argue/refute + Gemini web-grounded validation |
| Reviewing a plan before building | `/second-opinion` | 9-phase internal audit + Gemini cross-model critique |
| Assessing overall codebase health | `/codebase-audit` | Full-stack SWOT with CISO/CTO/CPO panel |
| Wrapping up a session | `/handoff` | Handoff notes, doc spot-check, retro, workspace cleanup |
| Checking environment health | `/preflight` | Server restart + tests + connectivity + permissions |
| Building a new feature (guided) | `/scaffold` | Parallel multi-agent feature buildout |
| Fixing a specific bug | `/bugfix` | Autonomous test-driven fix pipeline |

Workflow: `/discovery` → `/second-opinion` → `/scaffold` or manual → `/handoff`

Definitions: `.claude/skills/`. Output to `docs/discoveries/`, `docs/plans/`, `docs/audits/`.

---

## Design Principles

- **CLI > SDK > MCP**: Prefer shell scripts and CLI tools (lowest token cost, ambient auth). Use SDKs when CLIs aren't enough. Use MCP only when per-user auth and governance require it.
- **Parallel session safety**: See `.claude/rules/parallel-sessions.md` — narrow edits, check for concurrent modifications, avoid shared config files.

## Key Documentation

- API Contract: `docs/api-contract.md`
- Decision Log (ADRs): `docs/hestia-decision-log.md`
- Security Architecture: `docs/hestia-security-architecture.md`
- Sprint Tracker: `SPRINT.md`
- Future Adaptations: `../hestia-atlas-future-research.md`
