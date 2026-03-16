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

### Phase 3: Execute
- Implement precisely. Run **@hestia-tester** (Sonnet) after each significant change
- Fix issues immediately — never accumulate tech debt
- Commit after each logical unit of work (one feature, one fix, one refactor)
- Never combine unrelated changes in a single commit — enables git bisect and code review

### Phase 4: Review
- Run **@hestia-reviewer** (Sonnet) on all changed files — REQUIRED for any change touching >5 files
- Not optional when velocity is high — that's exactly when regressions hide
- Update affected docs (this file, `docs/api-contract.md`, `docs/hestia-decision-log.md`)

### Sub-Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| @hestia-explorer | Haiku | Phase 1: Find code, trace architecture |
| @hestia-tester | Sonnet | Phase 3: Run tests, diagnose failures |
| @hestia-reviewer | Sonnet | Phase 2: Plan audit, Phase 4: Code audit, Session retro + docs check |
| @hestia-deployer | Sonnet | Deploy to Mac Mini when requested |

Definitions: `.claude/agents/`. Read-only specialists — diagnose and report, never modify code.

### Hook Scripts

| Script | Trigger | Purpose |
|--------|---------|---------|
| `scripts/validate-security-edit.sh` | Before security file edits | Catches plaintext secrets, wildcard CORS, bare excepts |
| `scripts/auto-test.sh` | After Python source edits | Runs matching test file automatically |

---

## Server Management

After ANY backend code change, always kill stale server processes before restarting. Use `lsof -i :8443 | grep LISTEN` to find and `kill -9` old PIDs. Never assume the running server has picked up code changes without a full restart cycle. Stale processes are the #1 recurring time sink — old servers can run for weeks silently serving outdated code.

## Session Continuity

When resuming work from a previous session, FIRST read `SESSION_HANDOFF.md` (if it exists) and any TODO files. Do NOT search through bash history or compacted transcripts to recover context — use the structured handoff documents.

This is a multi-session project (Hestia). Key references:
- Project plans and workstreams are in `docs/`
- Previous session context may be compacted — check docs and CLAUDE.md FIRST before searching transcripts
- Current workstreams: Sprint 14 (Agent Orchestrator — coordinate/analyze/delegate model). Sprints 1-13 COMPLETE. See `SPRINT.md`.
- **2026-03-01:** Sprint 4 — audit remediation (proactive auth fix, auth dep standardization), macOS Wiki/Explorer Resources/Resources tab. 66 macOS files total.
- **2026-02-28:** macOS app renamed to "Hestia" — UX polished: keyboard shortcuts (⌘1-6/\), sidebar, responsive layout, app icon. Both Xcode schemes build clean.
- **2026-02-28:** Claude Code config refresh — new skills, CI/CD pipeline, sprint tracker. Direct API billing active.

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

**Three Agents:** Hestia (coordinator — single user interface), Artemis (analysis specialist), Apollo (execution specialist). Hestia routes internally. `@artemis`/`@apollo` override available. See ADR-042.

## Technical Stack

| Component | Technology |
|-----------|------------|
| Hardware | Mac Mini M1 (16GB) |
| Model | Qwen 3.5 9B primary + Qwen 2.5 Coder 7B specialist (Ollama, local) + cloud (Anthropic/OpenAI/Google) |
| SLM | qwen2.5:0.5b (council intent classification, ~100ms) |
| Backend | Python 3.9+, FastAPI, ~170 endpoints across 26 route modules |
| Storage | ChromaDB (vectors) + SQLite (structured) + macOS Keychain (credentials) |
| App | Native Swift/SwiftUI (iOS 26.0+) |
| API | REST on port 8443 with JWT auth, HTTPS with self-signed cert |
| Remote | Tailscale (`andrewroman117@hestia-3.local`) |
| Dev Tools | Claude Code (API billing) + Xcode |
| CI/CD | GitHub Actions → Mac Mini (auto-deploy on push to main) |

## Current Status

**MVP (v1.0): Phases 0-7 COMPLETE.** All core layers built and deployed.
**Intelligence (v1.5):** WS1 Cloud LLM, WS2 Voice, WS3 Council, WS4 Temporal Decay — ALL COMPLETE.
**UI Phase 3 (Lottie, Settings, Neural Net): COMPLETE.**
**UI Phase 4 (Integrations UI, API contract rewrite): COMPLETE.**
**Apple HealthKit Integration: COMPLETE.** 28 metric types, daily sync, coaching preferences, briefing integration, 5 chat tools.
**Field Guide UI Restructure: COMPLETE.** 5 thematic tabs, native SwiftUI diagrams, structured roadmap with `/v1/wiki/roadmap` endpoint.

2012 tests (2009 passing, 3 skipped), 58 test files (51 backend + 7 CLI). Full details: `python -m pytest tests/ -v --timeout=30`

---

## Code Conventions

- **Type hints**: Always. Every function signature.
- **Async/await**: For all I/O (database, inference, network).
- **Logging**: `logger = get_logger()` — no arguments. Never `HestiaLogger(component=...)` or `get_logger(component=...)`. Import: `from hestia.logging import get_logger`. LogComponent enum: ORCHESTRATION, MEMORY, INFERENCE, EXECUTION, SECURITY, API, SYSTEM, VOICE, COUNCIL, HEALTH, WIKI, EXPLORER, NEWSFEED, INVESTIGATE, RESEARCH, FILE, INBOX, OUTCOMES, APPLE_CACHE. (19 components total)
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
- Mac Mini deployment target: `andrewroman117@hestia-3.local` (via Tailscale)
- **APIClient HTTP methods**: `get()`, `put()`, `delete()` are internal (not private). ViewModels can call them directly with generic return types: `let response: MyType = try await APIClient.shared.get("/v1/path")`.

## Multi-Target Builds (macOS + iOS)

This project has both macOS and iOS targets. When creating or editing Swift files:
- Check which targets the file belongs to before editing
- Verify imports and APIs are available on both platforms (e.g., `OnboardingViewModel`, `APIClientProvider` may be iOS-only)
- Use `#if os(macOS)` / `#if os(iOS)` guards when needed
- Always build BOTH targets after changes: `xcodebuild -scheme HestiaWorkspace` and `xcodebuild -scheme HestiaApp`

### macOS Model Files
`macOS/Models/` contains 2 files: `HealthDataModels.swift` (Mac-specific response types + bundled `AnyCodableValue`) and `ResearchModels.swift` (macOS-only research graph types). WikiModels, ToolModels, DeviceModels, and NewsfeedModels are in `Shared/Models/` and included in the macOS target via `project.yml` selective includes — they are NOT duplicated.

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
- **Time**: ~6 hours/week
- **Style**: 70% teach-as-we-build, 30% just-make-it-work
- **Tools**: Claude Code implements, Xcode reviews

---

## Project Structure

```
hestia/
├── hestia/                          # Python backend — 26 modules
│   ├── database.py                  # BaseDatabase ABC (shared by all 11 SQLite modules)
│   ├── security/                    # CredentialManager (Keychain + Fernet)
│   ├── logging/                     # HestiaLogger, AuditLogger, LogComponent enum
│   ├── inference/                   # InferenceClient (Ollama + cloud), ModelRouter (3-state)
│   ├── cloud/                       # CloudManager, CloudInferenceClient (Anthropic/OpenAI/Google)
│   ├── council/                     # CouncilManager (4-role, dual-path), IntentType, prompts
│   ├── memory/                      # MemoryManager, ChromaDB, SQLite, TemporalDecay, AutoTagger
│   ├── orchestration/               # RequestHandler, StateMachine, ModeManager, PromptBuilder, AgentOrchestrator
│   ├── execution/                   # ToolExecutor, ToolRegistry, Sandbox, CommGate
│   ├── apple/                       # 20 tools (Calendar, Reminders, Notes, Mail)
│   ├── health/                      # HealthKit sync, metrics DB, coaching, 5 chat tools
│   ├── explorer/                    # ExplorerManager, resource aggregation, draft CRUD, TTL cache
│   ├── tasks/                       # BackgroundTask lifecycle + approval workflow
│   ├── orders/                      # Scheduled prompts + APScheduler
│   ├── agents/                      # AgentProfile CRUD + snapshots (Tia/Mira/Olly)
│   ├── user/                        # UserProfile + settings + push tokens
│   ├── proactive/                   # Briefings, PatternDetector, InterruptionPolicy
│   ├── voice/                       # TranscriptQualityChecker, JournalAnalyzer (3-stage)
│   ├── wiki/                        # Architecture field guide (AI-generated + static docs)
│   ├── newsfeed/                    # Materialized timeline, source aggregation, per-user state
│   ├── outcomes/                    # Chat outcome tracking for Learning Cycle
│   │   ├── database.py             # OutcomeDatabase (user-scoped, implicit signal detection)
│   │   └── manager.py              # OutcomeManager (track_response, detect_implicit_signal)
│   ├── inbox/                       # Unified inbox (mail + reminders + calendar aggregation)
│   │   ├── database.py             # InboxDatabase (items cache + per-user read/archive state)
│   │   └── manager.py              # InboxManager (Apple client aggregation, 30s cache TTL)
│   ├── files/                       # Secure filesystem CRUD with audit trail
│   │   ├── security.py             # PathValidator (allowlist, TOCTOU-safe, null-byte protection)
│   │   ├── database.py             # FileAuditDatabase (user-scoped audit log)
│   │   └── manager.py              # FileManager (list, read, create, update, delete, move)
│   ├── apple_cache/                 # FTS5 metadata cache for Apple ecosystem fuzzy resolution
│   │   ├── database.py             # AppleCacheDatabase (FTS5 virtual table, sync tracking)
│   │   ├── resolver.py             # SmartResolver (FTS5 candidates + rapidfuzz scoring)
│   │   └── manager.py              # AppleCacheManager (TTL sync, write-through, singleton)
│   ├── research/                    # Knowledge graph + PrincipleStore + Temporal Facts + Episodic Nodes (ADR-041)
│   │   ├── models.py              # Fact, Entity, Community, EpisodicNode, Principle dataclasses + graph types
│   │   ├── database.py            # SQLite: facts, entities, communities, principles, episodic_nodes, graph_cache
│   │   ├── graph_builder.py       # Co-occurrence graph (legacy) + fact-based graph (mode=facts)
│   │   ├── entity_registry.py     # Entity resolution (canonical dedup) + label propagation communities
│   │   ├── fact_extractor.py      # LLM triplet extraction + bi-temporal contradiction detection
│   │   ├── principle_store.py     # ChromaDB `hestia_principles` + LLM distillation
│   │   └── manager.py            # ResearchManager singleton (graph, facts, entities, principles)
│   ├── investigate/                 # URL content analysis (web articles, YouTube), LLM analysis pipeline
│   │   └── extractors/             # BaseExtractor ABC, WebArticleExtractor, YouTubeExtractor
│   ├── api/                         # FastAPI — 163 endpoints, 26 route modules
│   │   ├── errors.py                # sanitize_for_log(), safe_error_detail()
│   │   ├── schemas/                  # Pydantic request/response models (15 domain modules)
│   │   ├── server.py                # App lifecycle, manager initialization
│   │   ├── middleware/auth.py        # JWT device authentication
│   │   └── routes/                  # auth, health, chat, mode, memory, sessions, tools,
│   │                                # tasks, cloud, voice, orders, agents, agents_v2, user, user_profile, proactive, health_data, wiki, explorer, newsfeed, investigate, research, files, inbox, outcomes
│   └── config/                      # inference.yaml, execution.yaml, memory.yaml, wiki.yaml
├── hestia-cli/                      # Python CLI package — 72 tests, 6 test files
│   ├── hestia_cli/                  # CLI source (app, repl, client, auth, bootstrap, config, commands, context, renderer, models)
│   └── tests/                       # CLI tests (bootstrap, client, config, context, renderer)
├── hestia-cli-tools/                # Swift CLIs (keychain, calendar, reminders, notes)
├── HestiaApp/                       # iOS SwiftUI app
│   ├── Shared/
│   │   ├── App/                     # Entry point, ContentView
│   │   ├── DesignSystem/            # Colors, Typography, Spacing, Animations
│   │   ├── Models/                  # APIModels, CloudProvider, Order, AgentProfile, MemoryChunk, HealthModels, WikiModels, NewsfeedModels, BriefingModels, ToolModels, DeviceModels, ProactiveModels, InvestigationModels
│   │   ├── Resources/Animations/    # Lottie JSONs (ai_blob, typing_indicator)
│   │   ├── Services/                # APIClient, AuthService, SpeechService, CalendarService, HealthKitService
│   │   ├── ViewModels/              # Chat, Newsfeed, CloudSettings, Integrations, NeuralNet, Resources, Settings, Wiki, DeviceManagement, ProactiveSettings
│   │   ├── Views/                   # Chat, CommandCenter (+ NeuralNet), Settings (+ Resources, Integrations, Wiki, DeviceManagement, ProactiveSettings), Auth
│   │   ├── Views/Common/            # LottieAnimationView, LoadingView, GradientBackground
│   │   └── Persistence/             # Core Data stack
│   ├── macOS/                       # macOS app (126 files)
│   │   ├── Views/                   # Command, Explorer (Files+Resources), Health, Profile, Wiki (4 views), Resources (6 views), Chat, Chrome, Auth
│   │   ├── ViewModels/              # MacChat, MacExplorer, MacExplorerResources, MacCloudSettings, MacIntegrations, MacWiki, MacHealth, MacUserProfile, MacCommandCenter
│   │   ├── Models/                  # WikiModels, ToolModels, NewsfeedModels, HealthDataModels, DeviceModels
│   │   ├── Services/                # APIClient+Wiki, APIClient+Tools, APIClient+Newsfeed, APIClient+Health, APIClient+Devices, APIClient+Investigate
│   │   └── DesignSystem/            # MacColors, MacSpacing, MacTypography
│   └── project.yml                  # xcodegen config (iOS 26.0, macOS 15.0, Swift 6.1)
├── tests/                           # 1611 tests, 36 files
├── scripts/                         # deploy, test-api, auto-test, validate-security, ollama
├── .claude/                         # agents/, output-styles/, settings
├── docs/                            # api-contract, decision-log, security-architecture
└── data/ + logs/                    # Runtime storage
```

---

## API Summary (163 endpoints, 26 route modules)

| Module | Endpoints | Key Routes |
|--------|-----------|------------|
| Health & Auth | 8 | `/v1/ping`, `/v1/health`, `/v1/ready`, `/v1/auth/register`, `/v1/auth/refresh`, `/v1/auth/invite`, `/v1/auth/register-with-invite`, `/v1/auth/re-invite` |
| Chat & Mode | 6 | `/v1/chat`, `/v1/chat/stream` (SSE), `/v1/chat/agentic` (iterative tool loop), `/v1/mode/*` |
| Memory | 7 | `/v1/memory/staged`, `approve`, `reject`, `search`, `ingest`, `import/claude` |
| Sessions | 3 | `/v1/sessions` CRUD |
| Tools | 3 | `/v1/tools` list, details, schema |
| Tasks | 6 | `/v1/tasks` CRUD + approve/cancel/retry |
| Cloud | 7 | `/v1/cloud/providers` CRUD, state, model, usage, health |
| Voice | 2 | `/v1/voice/quality-check`, `journal-analyze` |
| Orders | 7 | `/v1/orders` CRUD + executions + execute |
| Agents (v1) | 10 | `/v1/agents/{slot}` CRUD + photos + snapshots + sync |
| Agents (v2) | 10 | `/v2/agents` .md-based config CRUD + notes + reload |
| User | 12 | `/v1/user/profile`, `photo`, `settings`, `push-token`, `devices`, `devices/{id}/revoke`, `devices/{id}/unrevoke` |
| User Profile | 11 | `/v1/user/profile/*` extended CRUD |
| Proactive | 6 | `/v1/proactive/briefing`, `policy`, `patterns`, `notifications` |
| Health Data | 7 | `/v1/health_data/sync`, `summary`, `trend`, `coaching` |
| Wiki | 6 | `/v1/wiki/articles`, `generate`, `generate-all`, `refresh-static`, `roadmap` |
| Explorer | 6 | `/v1/explorer/resources` list/detail/content, drafts CRUD |
| Newsfeed | 5 | `/v1/newsfeed/timeline`, `unread-count`, `items/{id}/read`, `items/{id}/dismiss`, `refresh` |
| Investigate | 5 | `/v1/investigate/url`, `history`, `compare`, `{id}` (GET), `{id}` (DELETE) |
| Research | 18 | `/v1/research/graph` (legacy+facts mode), `facts/extract`, `facts` (list), `facts/timeline`, `facts/at-time`, `facts/{id}/invalidate`, `entities` (list), `entities/search`, `entities/communities`, `communities` (list), `episodes` (list), `episodes/for-entity/{id}`, `principles/distill`, `principles` (list), `principles/{id}/approve`, `principles/{id}/reject`, `principles/{id}` (PUT) |
| Files | 9 | `/v1/files` (list, create), `/v1/files/content`, `/v1/files/metadata`, `/v1/files` (PUT, DELETE), `/v1/files/move`, `/v1/files/delete` (POST alias), `/v1/files/audit-log` |
| Inbox | 7 | `/v1/inbox` (list), `/v1/inbox/unread-count`, `/v1/inbox/{id}`, `/v1/inbox/{id}/read`, `/v1/inbox/mark-all-read`, `/v1/inbox/{id}/archive`, `/v1/inbox/refresh` |
| Outcomes | 5 | `/v1/outcomes` (list), `/v1/outcomes/stats`, `/v1/outcomes/{id}`, `/v1/outcomes/{id}/feedback`, `/v1/outcomes/track` |

Full endpoint details: `docs/api-contract.md` or `/docs` (Swagger)

---

## Key Architecture Notes

**Cloud Routing (3-state):** disabled (local-only, default) → enabled_smart (local-first, cloud spillover) → enabled_full (cloud-first). State propagation via `_sync_router_state()` after every mutation. API keys in Keychain, never returned.

**Council (dual-path):** Cloud active → 4 roles in parallel via `asyncio.gather`. Cloud disabled → SLM intent classification only + existing pipeline. Purely additive (try/except, failures fall back silently). CHAT optimization skips Analyzer/Validator/Responder when confidence > 0.8.

**Temporal Decay:** `adjusted = raw_score * e^(-λ * age_days) * recency_boost`. Per-chunk-type λ in `config/memory.yaml`. Facts/system never decay.

**Voice Pipeline:** iOS SpeechAnalyzer → transcript → quality check (LLM flags words) → user review → journal analysis (intent extraction + cross-referencing + action plan).

**Hardware Adaptation:** After first inference, measures tok/s. If below 8 tok/s, swaps primary model to `qwen2.5:7b` and enables cloud smart mode. Override: `HESTIA_PRIMARY_MODEL=qwen2.5:7b`. Config: `inference.yaml → hardware_adaptation`.

**Apple Metadata Cache:** FTS5 SQLite cache of Notes/Calendar/Reminders titles with rapidfuzz fuzzy resolution. TTL-based sync (6h notes, 2h calendar, 4h reminders). Write-through on create/update/delete. Eliminates multi-step tool chains — `read_note("sprint plan")` resolves + fetches in one call. 20 Apple tools (was 17).

**Knowledge Graph (Sprint 9 — Graphiti-inspired):** Bi-temporal facts (`valid_at`, `invalid_at`, `expired_at`) on SQLite edges between entities. Entity resolution via canonical name dedup. Community detection via label propagation (no graph DB). LLM-powered triplet extraction + contradiction detection. Two graph modes: `mode=legacy` (co-occurrence) and `mode=facts` (entity-relationship). On-demand extraction (not per-chat) to avoid inference overhead.

**Agent Orchestrator (ADR-042):** Hestia is the single user interface. Council coordinator classifies intent, then `AgentRouter` maps intent → `AgentRoute` (HESTIA_SOLO, ARTEMIS, APOLLO, ARTEMIS_THEN_APOLLO) via deterministic keyword heuristic. Confidence gating: >0.8 = full specialist dispatch, 0.5-0.8 = enriched solo, <0.5 = pure solo. Chains validated before execution. `asyncio.gather` for parallel groups (genuine on M5 Ultra, sequential on M1). Byline attribution in responses. Kill switch: `orchestration.yaml → enabled: false`.

**Key ADRs** (full list: `docs/hestia-decision-log.md`):
- ADR-001/040: Dual local model — Qwen 3.5 9B primary + Qwen 2.5 Coder 7B specialist
- ADR-041: Knowledge Graph Evolution — bi-temporal facts on SQLite, Graphiti-inspired without graph DB
- ADR-042: Agent Orchestrator — coordinate/analyze/delegate model, council extension, byline attribution
- ADR-003: Single-agent architecture
- ADR-009: Keychain + Secure Enclave credentials
- ADR-013: Tag-based memory with temporal decay
- ADR-021/022: Background task management with governed auto-persistence
- ADR-032/033: Newsfeed materialized cache + user-scoped state for multi-device

---

## Enhancement Roadmap

### Intelligence Workstreams — ALL COMPLETE
| WS | Status | Scope |
|----|--------|-------|
| WS4: Temporal Decay | COMPLETE | Per-chunk-type decay in memory search |
| WS1: Cloud LLM | COMPLETE | 3 providers, 3-state routing, 7 endpoints, iOS UI |
| WS2: Voice Journaling | COMPLETE | SpeechAnalyzer + quality gate + journal analysis |
| WS3: Council + SLM | COMPLETE | 4-role council, dual-path, handler integration |

### UI Enhancement Phases
| Phase | Status | Scope |
|-------|--------|-------|
| Phase 1: Bug Fixes | COMPLETE | Face ID, Notes CLI, tool call JSON |
| Phase 2: Quick Wins | COMPLETE | Memory already in CC, byline/Default Mode already removed |
| Phase 3: Lottie + Neural Net | COMPLETE | Lottie animations, Settings restructure, 3D Neural Net graph |
| Phase 4: Settings Integrations | COMPLETE | IntegrationsView (Calendar, Reminders, Notes, Mail), API contract rewrite |
| Apple HealthKit Integration | COMPLETE | 27 metric types, daily sync, coaching preferences, briefing integration, 5 chat tools, iOS HealthKitService |
| Wiki / Architecture Field Guide | COMPLETE | AI-generated narratives, module deep dives, ADR browser, roadmap, Mermaid diagrams, iOS tabbed UI |
| macOS App (Hestia) | COMPLETE | 126 files, 6 views (Command/Explorer/Health/Profile/Wiki/Resources), icon sidebar, chat panel, keyboard shortcuts ⌘1-6/\, responsive layout, app icon. |

### Frontend Wiring — COMPLETE
| Sprint | Status | Scope |
|--------|--------|-------|
| Sprint 1: DevOps & Deployment | COMPLETE | QR invite onboarding (4 endpoints), iOS/macOS flows, permissions harmony, 28 tests |
| Sprint 2: Explorer | COMPLETE | Backend module + 6 API endpoints + iOS Explorer tab + 41 tests. macOS enhancement deferred. |
| Sprint 3: Command Center | COMPLETE | Backend newsfeed module + 5 API endpoints + iOS Command Center rewrite (BriefingCard, FilterBar, NewsfeedTimeline) + macOS wiring + 42 tests |
| Sprint 4: Settings + Health | COMPLETE | Dynamic tool discovery, device management UI, macOS health redesign (ADR-036), proactive intelligence settings |
| Sprint 5: Audit + macOS Wiring | COMPLETE | Proactive auth fix, auth dep standardization (10 route files), macOS Wiki (4 views), Explorer Resources mode, Resources tab (LLMs/Integrations/MCPs) |

### Stability & Efficiency
| Sprint | Status | Scope |
|--------|--------|-------|
| Sprint 12: Architecture Efficiency | COMPLETE | Parallel pre-inference pipeline (asyncio.gather), council bypass heuristic, SSE streaming (POST /v1/chat/stream + iOS/macOS), ETag conditional GET (wiki/tools) |
| Sprint 7: Profile & Settings | COMPLETE | Settings accordion (4 sections), profile editing, agent V2 API, Resources consolidation, Field Guide migration, CacheManager, MarkdownEditor line numbers, amber accent audit, VoiceOver a11y |
| Sprint 6: Stability & Efficiency | COMPLETE | Readiness gate, complete shutdown (15 managers), Uvicorn recycling (5K req), parallel init, pip-compile lockfile, log compression, Cache-Control |

### Hestia CLI
| Sprint | Status | Scope |
|--------|--------|-------|
| CLI Sprint 1: WebSocket Streaming | COMPLETE | Backend WebSocket endpoint, streaming protocol, auth handshake |
| CLI Sprint 2: REPL + Auth | COMPLETE | prompt_toolkit REPL, Rich rendering, Keychain auth, invite registration |
| CLI Sprint 3: Tool Trust Tiers | COMPLETE | Per-device read/write/execute/external tiers, prompt-based approval |
| CLI Sprint 4: Repo Context | COMPLETE | Git state injection, project file snippets, agentic coding context |
| CLI Sprint 5: Polish | COMPLETE | Error logging, /memory /config /trust commands, HESTIA_NO_COLOR |
| CLI Bootstrap | COMPLETE | Zero-friction cold start: auto-server-start (launchd/subprocess), auto-register (localhost), `hestia setup` |

### Known Issues (Mac Mini)
- Council needs `qwen2.5:0.5b` pulled on Mac Mini
- Server must be restarted after code deploys (no hot-reload)

---

## Quick Commands

```bash
source .venv/bin/activate
hestia                                 # CLI — auto-starts server, auto-registers
python -m hestia.api.server            # Start server manually
python -m pytest tests/ -v             # Run backend tests
cd hestia-cli && python -m pytest tests/ -v  # Run CLI tests
./scripts/test-api.sh                  # API smoke tests (14)
./scripts/deploy-to-mini.sh            # Deploy to Mac Mini
./scripts/pre-session.sh               # Headless pre-session health check
./scripts/post-commit.sh               # Headless post-commit lint + test
hestia-preflight                       # On-demand validation (shell function)
```

## Validation Tiers

| Tier | Trigger | Checks |
|------|---------|--------|
| Pre-push (feature) | `git push` on any branch | Kill stale servers + pytest |
| Pre-push (main) | `git push` on main | + xcodebuild |
| On-demand | `hestia-preflight` in terminal | Same as main pre-push |
| Full | `/preflight` in Claude Code | Server restart + tests + connectivity + permissions |

Hook source: `scripts/pre-push.sh` (symlinked from `.git/hooks/pre-push`). Bypass: `git push --no-verify`.

## Skills (Slash Commands)

### Strategic (opt-in for planning/analysis work)

| Skill | Command | Purpose |
|-------|---------|---------|
| Discovery | `/discovery` | Deep research with SWOT, argue/refute, priority matrix |
| Plan Audit | `/plan-audit` | CISO/CTO/CPO critique of proposed plans |
| Codebase Audit | `/codebase-audit` | Full-stack health assessment with executive panel |
| Retrospective | `/retrospective` | [DEPRECATED] Merged into `/handoff` Phase 3 |

### Operational (day-to-day development)

| Skill | Command | Purpose |
|-------|---------|---------|
| Handoff | `/handoff` | Wrap up session — handoff notes, doc spot-check, workspace cleanup |
| Restart | `/restart` | Kill stale server, restart, health check, run tests |
| Preflight | `/preflight` | Full stack validation with auto-remediation |
| Bug Fix | `/bugfix` | Autonomous test-driven fix pipeline (one-at-a-time verification) |
| Scaffold | `/scaffold` | Parallel multi-agent feature buildout with interface contracts |

### Sprint Workflow (typical sequence)

```
/discovery [topic]  →  /plan-audit  →  /scaffold or manual  →  /handoff
```

Definitions: `.claude/skills/`. Output saved to `docs/discoveries/`, `docs/plans/`, `docs/audits/`, `docs/retrospectives/`.

---

## Documentation

| Doc | Location |
|-----|----------|
| API Contract | `docs/api-contract.md` |
| Decision Log (ADRs) | `docs/hestia-decision-log.md` |
| Security Architecture | `docs/hestia-security-architecture.md` |
| Development Plan | `docs/hestia-development-plan.md` |
| UI Data Models | `docs/reference/ui-data-models.md` |
| Cheat Sheet | `CHEATSHEET.md` |
| Sprint Tracker | `SPRINT.md` |
| Config Refresh Plan | `claude-config-refresh-plan.md` |
| Session Log Archive | `docs/archive/session-log-2025-01-08-to-2026-02-08.md` |
| Future Adaptations | `../hestia-atlas-future-research.md` — trigger-based roadmap for Edge AI, QLoRA, Graph RAG, MoE, federated Atlas. Reference when system conditions change (hardware upgrades, dataset milestones). |

---

## Development History

Built Jan 2025 – Feb 2026 across ~15 sessions. MVP phases 0–7 (security, logging, inference, memory, orchestration, execution, Apple ecosystem, REST API, iOS app). Intelligence workstreams WS1–4 (cloud LLM, voice journaling, council + SLM, temporal decay). Full session history: `docs/archive/session-log-2025-01-08-to-2026-02-08.md`
