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

### Phase 4: Review
- Run **@hestia-reviewer** (Sonnet) on all changed files
- Update affected docs (this file, `docs/api-contract.md`, `docs/hestia-decision-log.md`)

### Sub-Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| @hestia-explorer | Haiku | Phase 1: Find code, trace architecture |
| @hestia-tester | Sonnet | Phase 3: Run tests, diagnose failures |
| @hestia-reviewer | Sonnet | Phase 4: Code review before commits |
| @hestia-deployer | Sonnet | Deploy to Mac Mini when requested |

Definitions: `.claude/agents/`. Read-only specialists — diagnose and report, never modify code.

### Hook Scripts

| Script | Trigger | Purpose |
|--------|---------|---------|
| `scripts/validate-security-edit.sh` | Before security file edits | Catches plaintext secrets, wildcard CORS, bare excepts |
| `scripts/auto-test.sh` | After Python source edits | Runs matching test file automatically |

---

## What is Hestia?

Locally-hosted personal AI assistant on Mac Mini M1. Jarvis-like: competent, adaptive, sardonic, anticipates needs.

**Three Modes:** `@Tia` (Hestia — daily ops), `@Mira` (Artemis — Socratic teaching), `@Olly` (Apollo — focused dev)

## Technical Stack

| Component | Technology |
|-----------|------------|
| Hardware | Mac Mini M1 (16GB) |
| Model | Qwen 2.5 7B (Ollama, local) + cloud providers (Anthropic/OpenAI/Google) |
| SLM | qwen2.5:0.5b (council intent classification, ~100ms) |
| Backend | Python 3.9+, FastAPI, 65 endpoints across 14 route modules |
| Storage | ChromaDB (vectors) + SQLite (structured) + macOS Keychain (credentials) |
| App | Native Swift/SwiftUI (iOS 26.0+) |
| API | REST on port 8443 with JWT auth, HTTPS with self-signed cert |
| Remote | Tailscale (`andrewroman117@hestia-3.local`) |
| Dev Tools | Claude Code + Xcode |

## Current Status

**MVP (v1.0): Phases 0-7 COMPLETE.** All core layers built and deployed.
**Intelligence (v1.5):** WS1 Cloud LLM, WS2 Voice, WS3 Council, WS4 Temporal Decay — ALL COMPLETE.
**Next:** UI Phase 2 quick wins, then Lottie animations, then Settings integrations.

731 tests passing (3 skipped). Full details: `python -m pytest tests/ -v`

---

## Code Conventions

- **Type hints**: Always. Every function signature.
- **Async/await**: For all I/O (database, inference, network).
- **Logging**: `HestiaLogger` with correct `LogComponent` per module (ACCESS, ORCHESTRATION, MEMORY, INFERENCE, EXECUTION, SECURITY, API, SYSTEM, VOICE, CLOUD, COUNCIL).
- **Config**: YAML files, never hardcode.
- **Error handling in routes**: `sanitize_for_log(e)` from `hestia.api.errors` in logs (never raw `{e}`). Generic messages in HTTP responses (never `detail=str(e)`).
- **File naming**: `snake_case.py` (Python), UpperCamelCase.swift (iOS).
- **Manager pattern**: `models.py` + `database.py` + `manager.py` per module. Singleton via `get_X_manager()` async factory.
- **iOS patterns**: `@MainActor ObservableObject` with `@Published`. DesignSystem tokens. No force-unwraps. `[weak self]` in closures. `#if DEBUG` for all `print()`.
- **New module checklist**: (1) `LogComponent` enum, (2) `auto-test.sh` mapping, (3) `validate-security-edit.sh` if creds, (4) sub-agent definitions, (5) project structure in CLAUDE.md.

## Security Posture

- Biometric auth (Face ID/Touch ID) for sensitive data
- Three-tier credential partitioning (operational/sensitive/system)
- Double encryption (Fernet + Keychain AES-256)
- External communication gate (nothing sent without approval)
- JWT device auth, 90-day expiry, Keychain-stored secret
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
├── hestia/                          # Python backend — 17 modules
│   ├── security/                    # CredentialManager (Keychain + Fernet)
│   ├── logging/                     # HestiaLogger, AuditLogger, LogComponent enum
│   ├── inference/                   # InferenceClient (Ollama + cloud), ModelRouter (3-state)
│   ├── cloud/                       # CloudManager, CloudInferenceClient (Anthropic/OpenAI/Google)
│   ├── council/                     # CouncilManager (4-role, dual-path), IntentType, prompts
│   ├── memory/                      # MemoryManager, ChromaDB, SQLite, TemporalDecay, AutoTagger
│   ├── orchestration/               # RequestHandler, StateMachine, ModeManager, PromptBuilder
│   ├── execution/                   # ToolExecutor, ToolRegistry, Sandbox, CommGate
│   ├── apple/                       # 20 tools (Calendar, Reminders, Notes, Mail)
│   ├── tasks/                       # BackgroundTask lifecycle + approval workflow
│   ├── orders/                      # Scheduled prompts + APScheduler
│   ├── agents/                      # AgentProfile CRUD + snapshots (Tia/Mira/Olly)
│   ├── user/                        # UserProfile + settings + push tokens
│   ├── proactive/                   # Briefings, PatternDetector, InterruptionPolicy
│   ├── voice/                       # TranscriptQualityChecker, JournalAnalyzer (3-stage)
│   ├── api/                         # FastAPI — 65 endpoints, 14 route modules
│   │   ├── errors.py                # sanitize_for_log(), safe_error_detail()
│   │   ├── schemas.py               # All Pydantic request/response models
│   │   ├── server.py                # App lifecycle, manager initialization
│   │   ├── middleware/auth.py        # JWT device authentication
│   │   └── routes/                  # auth, health, chat, mode, memory, sessions, tools,
│   │                                # tasks, cloud, voice, orders, agents, user, proactive
│   └── config/                      # inference.yaml, execution.yaml, memory.yaml
├── hestia-cli-tools/                # Swift CLIs (keychain, calendar, reminders, notes)
├── HestiaApp/                       # iOS SwiftUI app
│   ├── Shared/
│   │   ├── App/                     # Entry point, ContentView
│   │   ├── DesignSystem/            # Colors, Typography, Spacing, Animations
│   │   ├── Models/                  # APIModels, CloudProvider, Order, AgentProfile
│   │   ├── Services/                # APIClient, AuthService, SpeechService, CalendarService
│   │   ├── ViewModels/              # Chat, CommandCenter, CloudSettings, VoiceInput, Settings
│   │   ├── Views/                   # Chat (+ Voice overlay), CommandCenter, Settings (+ Cloud)
│   │   └── Persistence/             # Core Data stack
│   └── project.yml                  # xcodegen config (iOS 26.0, Swift 6.1)
├── tests/                           # 731 tests, 17 files
├── scripts/                         # deploy, test-api, auto-test, validate-security, ollama
├── .claude/                         # agents/, output-styles/, settings
├── docs/                            # api-contract, decision-log, security-architecture
└── data/ + logs/                    # Runtime storage
```

---

## API Summary (65 endpoints, 14 route modules)

| Module | Endpoints | Key Routes |
|--------|-----------|------------|
| Health & Auth | 4 | `/v1/ping`, `/v1/health`, `/v1/auth/register`, `/v1/auth/refresh` |
| Chat & Mode | 4 | `/v1/chat`, `/v1/mode/*` |
| Memory | 4 | `/v1/memory/staged`, `approve`, `reject`, `search` |
| Sessions | 3 | `/v1/sessions` CRUD |
| Tools | 3 | `/v1/tools` list, details, schema |
| Tasks | 6 | `/v1/tasks` CRUD + approve/cancel/retry |
| Cloud | 7 | `/v1/cloud/providers` CRUD, state, model, usage, health |
| Voice | 2 | `/v1/voice/quality-check`, `journal-analyze` |
| Orders | 7 | `/v1/orders` CRUD + executions + execute |
| Agents | 10 | `/v1/agents/{slot}` CRUD + photos + snapshots + sync |
| User | 9 | `/v1/user/profile`, `photo`, `settings`, `push-token` |
| Proactive | 6 | `/v1/proactive/briefing`, `policy`, `patterns`, `notifications` |

Full endpoint details: `docs/api-contract.md` or `/docs` (Swagger)

---

## Key Architecture Notes

**Cloud Routing (3-state):** disabled (local-only, default) → enabled_smart (local-first, cloud spillover) → enabled_full (cloud-first). State propagation via `_sync_router_state()` after every mutation. API keys in Keychain, never returned.

**Council (dual-path):** Cloud active → 4 roles in parallel via `asyncio.gather`. Cloud disabled → SLM intent classification only + existing pipeline. Purely additive (try/except, failures fall back silently). CHAT optimization skips Analyzer/Validator/Responder when confidence > 0.8.

**Temporal Decay:** `adjusted = raw_score * e^(-λ * age_days) * recency_boost`. Per-chunk-type λ in `config/memory.yaml`. Facts/system never decay.

**Voice Pipeline:** iOS SpeechAnalyzer → transcript → quality check (LLM flags words) → user review → journal analysis (intent extraction + cross-referencing + action plan).

**Key ADRs** (full list: `docs/hestia-decision-log.md`):
- ADR-001: Qwen 2.5 7B primary model (local)
- ADR-003: Single-agent architecture
- ADR-009: Keychain + Secure Enclave credentials
- ADR-013: Tag-based memory with temporal decay
- ADR-021/022: Background task management with governed auto-persistence

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
| **Phase 2: Quick Wins** | **NEXT** | Remove byline, remove Default Mode, move Memory to CC |
| Phase 3: Lottie Animations | Planned | Loading animations + snarky bylines |
| Phase 4: Settings Integrations | Planned | Calendar, Reminders, Notes, Mail, Weather, Stocks |
| Phase 5: Neural Net Graph | Planned | Force-directed memory visualization (Grape library) |

### Known Issues (Mac Mini)
- GET /v1/tools → 500 (Apple CLI init, pre-existing)
- POST /v1/sessions → 500 (orchestration handler init, pre-existing)
- Council needs `qwen2.5:0.5b` pulled on Mac Mini

---

## Quick Commands

```bash
source .venv/bin/activate
python -m hestia.api.server            # Start server
python -m pytest tests/ -v             # Run tests
./scripts/test-api.sh                  # API smoke tests (14)
./scripts/deploy-to-mini.sh            # Deploy to Mac Mini
```

---

## Documentation

| Doc | Location |
|-----|----------|
| API Contract | `docs/api-contract.md` |
| Decision Log (ADRs) | `docs/hestia-decision-log.md` |
| Security Architecture | `docs/hestia-security-architecture.md` |
| Development Plan | `docs/hestia-development-plan.md` |
| UI Data Models | `docs/ui-data-models.md` |
| Session Log Archive | `docs/archive/session-log-2025-01-08-to-2026-02-08.md` |

---

## Development History

Built Jan 2025 – Feb 2026 across ~15 sessions. MVP phases 0–7 (security, logging, inference, memory, orchestration, execution, Apple ecosystem, REST API, iOS app). Intelligence workstreams WS1–4 (cloud LLM, voice journaling, council + SLM, temporal decay). Full session history: `docs/archive/session-log-2025-01-08-to-2026-02-08.md`
