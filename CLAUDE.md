# CLAUDE.md - Hestia Project Context

This file provides Claude with persistent context about the Hestia project.

---

## MANDATORY: 4-Phase Development Workflow

**Every non-trivial Hestia task MUST follow this 4-phase structure.** This is not optional. Skipping phases leads to rework, missed context, and documentation drift.

### Phase 1: Research
- Explore the relevant codebase before writing any code
- Use **@hestia-explorer** sub-agent (Haiku, fast/cheap) for codebase navigation
- Identify affected files, dependencies, existing patterns, and edge cases
- Consider pros, cons, trade-offs, security implications
- Present findings as though teaching a packed auditorium — IQ 175 software development specialist
- **Output**: Clear analysis with reasoning, not just conclusions

### Phase 2: Plan
- Confirm decisions with Andrew before implementing
- Draft a specific implementation plan (files to create/modify, changes to make)
- Pressure-test the plan: What could go wrong? What are the edge cases? What breaks?
- Audit, revise, and iterate the plan at least 3 times before proceeding
- **Output**: Approved implementation plan with Andrew's sign-off

### Phase 3: Execute
- Implement the approved plan precisely
- Run **@hestia-tester** sub-agent after each significant change
- Fix issues immediately — never accumulate tech debt
- Verify the build is fully functional before declaring done
- **Output**: Working implementation with all tests passing

### Phase 4: Review
- Run **@hestia-reviewer** sub-agent on all changed files
- Update ALL affected documentation:
  - This file (CLAUDE.md) — session log, project structure, phase status
  - `docs/api-contract.md` — if endpoints changed
  - `docs/hestia-decision-log.md` — if architectural decisions were made
  - Any other docs affected by the changes
- Ensure historical context is preserved (session log entries)
- Confirm the project is primed for the next Claude Code session
- **Output**: Updated docs, clean review, session log entry

### When to Use Sub-Agents

| Sub-Agent | Model | When to Use |
|-----------|-------|-------------|
| **@hestia-explorer** | Haiku | Phase 1: Find code, trace architecture, answer "where/how" questions |
| **@hestia-tester** | Sonnet | Phase 3: Run tests, diagnose failures |
| **@hestia-reviewer** | Sonnet | Phase 4: Code review before commits |
| **@hestia-deployer** | Sonnet | After Phase 4: Deploy to Mac Mini when requested |

Sub-agent definitions live in `.claude/agents/`. They are read-only specialists — they diagnose and report, they never modify code.

### Output Style

Use the **Hestia Development** output style (`.claude/output-styles/hestia-development.md`) for all Hestia work sessions. It enforces project conventions automatically.

### Hook Scripts

| Script | Trigger | Purpose |
|--------|---------|---------|
| `scripts/validate-security-edit.sh` | Before edits to security files | Catches plaintext secrets, wildcard CORS, bare excepts |
| `scripts/auto-test.sh` | After edits to Python source | Runs the matching test file automatically |

---

## What is Hestia?

Hestia is a locally-hosted personal AI assistant running on a Mac Mini M1. Think Jarvis from Iron Man: competent, adaptive, occasionally sardonic, anticipates needs without being emotionally solicitous.

**Key characteristics:**
- Single-agent architecture (one model, three personas)
- Local-only (Qwen 2.5 7B via Ollama, no cloud LLM)
- Pentagon-level security (Secure Enclave, biometric auth, defense-in-depth)
- Native Swift apps for iOS/macOS
- Full REST API (FastAPI)

## Three Modes

| Invoke | Name | Focus |
|--------|------|-------|
| `@Tia` | Hestia | Default: daily ops, quick queries |
| `@Mira` | Artemis | Learning: Socratic teaching, research |
| `@Olly` | Apollo | Projects: focused dev, minimal tangents |

## Technical Stack

- **Hardware**: Mac Mini M1 (16GB) | Future: 64GB for Mixtral
- **Model**: Qwen 2.5 7B via Ollama (local only, no cloud LLM)
- **Backend**: Python 3.9+, FastAPI
- **API**: REST on port 8443 with JWT authentication (65 endpoints across 14 route modules)
- **Storage**: ChromaDB (vectors) + SQLite (structured) + macOS Keychain (credentials)
- **App**: Native Swift/SwiftUI (iOS + macOS)
- **Remote Access**: Tailscale
- **Development**: Claude Code + Xcode (two tools only)

## Development Phases

### MVP (v1.0)
```
Phase 0   : Environment Setup ..................... COMPLETE
Phase 0.5 : Security Foundation ................... COMPLETE
Phase 1   : Logging Infrastructure ................ COMPLETE
Phase 2   : Inference Layer ....................... COMPLETE (Qwen 2.5 7B, local only)
Phase 3   : Memory Layer .......................... COMPLETE
Phase 3.5 : Tag-Based Memory ...................... (merged into Phase 3)
Phase 4   : Orchestration ......................... COMPLETE
Phase 4.5 : Background Task Management ............ COMPLETE (7 endpoints, 60 tests)
Phase 5   : Execution Layer ....................... COMPLETE
Phase 5.5 : Apple Ecosystem ....................... COMPLETE
Phase 6a  : REST API .............................. COMPLETE (18 core endpoints)
Phase 6b  : Native App Integration ................ IN PROGRESS (SwiftUI app built)
Phase 7   : Integration & Hardening ............... COMPLETE (TLS, Tailscale, iOS config)
Phase 8   : Foundation Iteration .................. (observational - use system 2+ weeks)
```

### Intelligence Enhancements (v1.5 / v2.0)
```
Phase 9   : Proactive Intelligence ................ COMPLETE (briefings, patterns, policy)
Phase 3.6 : Confidence-Tracked Preferences ........ (v1.5)
Phase 8.5 : Learning from History ................. (v1.5)
Phase 10  : Task Decomposition .................... (v2.0)
```

## Key Architectural Decisions (ADRs)

### Core Architecture (v1.0)
- **ADR-001**: Qwen 2.5 7B as primary model (fits 16GB, upgrade to Mixtral with 64GB)
- **ADR-002**: Governed memory persistence (staged commits, human review)
- **ADR-003**: Single-agent architecture (predictable, debuggable)
- **ADR-004**: Observability over determinism (log everything)
- **ADR-009**: Credential management via macOS Keychain + Secure Enclave
- **ADR-011**: Context window management (32K budget allocation)
- **ADR-012**: Apple ecosystem via native APIs (no OAuth in v1.0)
- **ADR-013**: Tag-based memory schema (semantic + temporal + categorical)
- **ADR-021**: Background task management (SQLite queue, 7 API endpoints) - IMPLEMENTED
- **ADR-022**: Governed auto-persistence for background tasks (autonomy levels) - IMPLEMENTED

### Intelligence Enhancements (v1.5+)
- **ADR-013 ext**: Temporal decay for memory relevance (per-chunk-type exponential decay) - IMPLEMENTED
- **ADR-014**: Confidence-based preference learning (decay over time)
- **ADR-017**: Proactive intelligence framework (interruption policy) - IMPLEMENTED
- **ADR-018**: Task decomposition strategy (subtasks + checkpoints)

### Deprecated ADRs
- **ADR-015**: ~~Background task architecture~~ (superseded by ADR-021)
- **ADR-016**: ~~Hybrid inference with cloud fallback~~ (local-only architecture)

## Security Posture

- Biometric auth (Face ID/Touch ID) for sensitive data
- Three-tier credential partitioning (operational/sensitive/system)
- Double encryption (Fernet + Keychain AES-256)
- External communication gate (nothing sent without approval)
- 7-year audit log retention for credential access
- JWT device authentication for API access

## Code Conventions

- **File naming**: snake_case for Python (`inference_client.py`)
- **Type hints**: Always use them
- **Logging**: Every significant operation logged with request ID; use correct `LogComponent` per module
- **Config**: YAML files, never hardcode
- **Error handling in routes**: Use `sanitize_for_log(e)` from `hestia.api.errors` in log messages (never raw `{e}`). Use generic messages in HTTP responses (never `detail=str(e)`). See `hestia/api/errors.py`.
- **New module checklist**: When adding a module, also: (1) add `LogComponent` enum value, (2) update `auto-test.sh` mapping, (3) add to `validate-security-edit.sh` if it handles credentials, (4) update sub-agent definitions, (5) add to project structure in CLAUDE.md

## Andrew's Context

- **Skills**: Strong SQL/APIs, growing Python/infra, learning as we build
- **Time**: ~6 hours/week
- **Style**: 70% teach-as-we-build, 30% just-make-it-work
- **Tools**: Claude Code implements, Xcode reviews

## Effective Prompts

**Good:**
- "Build the memory manager with these specs..."
- "Debug this error: [paste full traceback]"
- "Review this implementation against ADR-009"

**Less effective:**
- "Build Hestia" (too broad)
- "Is this good?" (no context)

## Documentation

- `docs/hestia-project-context-enhanced.md` - Quick reference
- `docs/hestia-initiative-enhanced.md` - Full specification
- `docs/hestia-development-plan.md` - Phase-by-phase guide
- `docs/hestia-security-architecture.md` - Security design
- `docs/hestia-decision-log.md` - All ADRs
- `docs/api-contract.md` - REST API specification
- `docs/ui-data-models.md` - Frontend data structures

---

## Current Project Structure

```
hestia/
├── hestia/                          # Python package (v0.1.0) — 17 modules
│   ├── __init__.py
│   ├── security/
│   │   ├── __init__.py
│   │   └── credential_manager.py    # CredentialManager with Keychain + Fernet
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── structured_logger.py     # HestiaLogger with JSON, sanitization, LogComponent enum
│   │   ├── audit_logger.py          # AuditLogger (7-year retention)
│   │   └── viewer.py                # CLI log viewer
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── client.py                # InferenceClient (Ollama + cloud, retry, streaming)
│   │   └── router.py                # Model routing (local + cloud, 3-state)
│   ├── cloud/
│   │   ├── __init__.py
│   │   ├── models.py                # CloudProvider, ProviderConfig, CloudUsageRecord
│   │   ├── database.py              # SQLite persistence for providers + usage
│   │   ├── manager.py               # CloudManager (CRUD, model detection, health, keys)
│   │   └── client.py                # CloudInferenceClient (Anthropic/OpenAI/Google calls)
│   ├── council/
│   │   ├── __init__.py
│   │   ├── models.py                # IntentType, IntentClassification, ToolExtraction, CouncilConfig
│   │   ├── roles.py                 # Coordinator, Analyzer, Validator, Responder (ABC)
│   │   ├── prompts.py               # System prompt templates for each role
│   │   └── manager.py               # CouncilManager (dual-path orchestration, singleton)
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── models.py                # ConversationChunk, ChunkTags, MemoryQuery
│   │   ├── database.py              # SQLite storage (async aiosqlite)
│   │   ├── vector_store.py          # ChromaDB for semantic search
│   │   ├── tagger.py                # AutoTagger (LLM + heuristic)
│   │   ├── decay.py                 # TemporalDecay (per-chunk-type exponential decay)
│   │   └── manager.py               # MemoryManager (unified interface)
│   ├── orchestration/
│   │   ├── __init__.py
│   │   ├── models.py                # Request, Response, Task, Mode enums
│   │   ├── state.py                 # TaskStateMachine with validated transitions
│   │   ├── mode.py                  # ModeManager (Tia/Mira/Olly personas)
│   │   ├── prompt.py                # PromptBuilder with token budget (ADR-011)
│   │   ├── validation.py            # Request/Response validation pipeline
│   │   └── handler.py               # RequestHandler (main orchestration)
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── models.py                # Tool, ToolCall, ToolResult, GateDecision
│   │   ├── registry.py              # ToolRegistry for tool management
│   │   ├── executor.py              # ToolExecutor (sandboxed execution)
│   │   ├── sandbox.py               # SandboxRunner (subprocess isolation)
│   │   ├── gate.py                  # ExternalCommunicationGate (approval system)
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── file_tools.py        # read_file, write_file handlers
│   │       └── shell_tools.py       # run_command handler
│   ├── apple/
│   │   ├── __init__.py
│   │   ├── models.py                # Calendar, Event, Reminder, Note, Email
│   │   ├── calendar.py              # CalendarClient (EventKit wrapper)
│   │   ├── reminders.py             # RemindersClient (EventKit wrapper)
│   │   ├── notes.py                 # NotesClient (AppleScript wrapper)
│   │   ├── mail.py                  # MailClient (SQLite reader)
│   │   └── tools.py                 # 20 Apple tools for execution layer
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── models.py                # BackgroundTask, TaskStatus, TaskSource
│   │   ├── database.py              # SQLite persistence (async aiosqlite)
│   │   └── manager.py               # TaskManager (lifecycle, approval workflow)
│   ├── orders/
│   │   ├── __init__.py
│   │   ├── models.py                # Order, OrderExecution, OrderFrequency, MCPResource
│   │   ├── database.py              # SQLite persistence (async aiosqlite)
│   │   ├── manager.py               # OrderManager (lifecycle management)
│   │   └── scheduler.py             # APScheduler integration
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── models.py                # AgentProfile, AgentSnapshot, DEFAULT_AGENTS
│   │   ├── database.py              # SQLite with snapshot support (90-day retention)
│   │   └── manager.py               # AgentManager (CRUD, photos, sync)
│   ├── user/
│   │   ├── __init__.py
│   │   ├── models.py                # UserProfile, UserSettings, PushToken, QuietHours
│   │   ├── database.py              # Single-user persistence
│   │   └── manager.py               # UserManager (profile, photos, push tokens)
│   ├── proactive/
│   │   ├── __init__.py
│   │   ├── models.py                # Briefing, Pattern, InterruptionPolicy
│   │   ├── briefing.py              # ProactiveBriefingManager
│   │   ├── patterns.py              # PatternDetector
│   │   ├── policy.py                # InterruptionPolicy engine
│   │   └── config_store.py          # Proactive config persistence
│   ├── voice/
│   │   ├── __init__.py
│   │   ├── models.py                # TranscriptSegment, QualityReport, JournalAnalysis
│   │   ├── quality.py               # TranscriptQualityChecker (LLM-powered)
│   │   └── journal.py               # JournalAnalyzer (3-stage pipeline)
│   ├── api/                         # REST API — 65 endpoints
│   │   ├── __init__.py
│   │   ├── server.py                # FastAPI app with lifecycle management
│   │   ├── schemas.py               # Pydantic request/response models
│   │   ├── errors.py                # Error sanitization (sanitize_for_log, safe_error_detail)
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   └── auth.py              # JWT device token authentication
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py              # /v1/auth/* (1 endpoint)
│   │       ├── health.py            # /v1/ping, /v1/health (2 endpoints)
│   │       ├── chat.py              # /v1/chat (1 endpoint)
│   │       ├── mode.py              # /v1/mode/* (2 endpoints)
│   │       ├── memory.py            # /v1/memory/* (4 endpoints)
│   │       ├── sessions.py          # /v1/sessions/* (3 endpoints)
│   │       ├── tools.py             # /v1/tools/* (1 endpoint)
│   │       ├── tasks.py             # /v1/tasks/* (6 endpoints)
│   │       ├── cloud.py             # /v1/cloud/* (7 endpoints)
│   │       ├── voice.py             # /v1/voice/* (2 endpoints)
│   │       ├── orders.py            # /v1/orders/* (7 endpoints)
│   │       ├── agents.py            # /v1/agents/* (10 endpoints)
│   │       ├── user.py              # /v1/user/* (7 endpoints)
│   │       └── proactive.py         # /v1/proactive/* (12 endpoints)
│   ├── persona/                     # Placeholder (not yet implemented)
│   └── config/
│       ├── __init__.py
│       ├── inference.yaml           # Inference + cloud routing configuration
│       ├── execution.yaml           # Execution layer configuration
│       └── memory.yaml              # Memory config (temporal decay rates)
├── hestia-cli-tools/
│   ├── hestia-keychain-cli/         # Swift CLI for Secure Enclave
│   ├── hestia-calendar-cli/         # Swift CLI for Calendar (EventKit)
│   ├── hestia-reminders-cli/        # Swift CLI for Reminders (EventKit)
│   └── hestia-notes-cli/            # Swift CLI for Notes (AppleScript)
├── HestiaApp/                       # Native iOS/macOS SwiftUI app
│   ├── Shared/
│   │   ├── App/                     # Entry point, ContentView
│   │   ├── DesignSystem/            # Colors, Typography, Spacing, Animations
│   │   ├── Models/                  # APIModels, CloudProvider, Order, AgentProfile, etc.
│   │   ├── Services/                # APIClient, AuthService, NetworkMonitor, CalendarService
│   │   ├── ViewModels/              # Chat, CommandCenter, MemoryReview, Settings, CloudSettings
│   │   ├── Views/                   # Chat, CommandCenter, Settings (incl. Cloud), Memory
│   │   ├── Utilities/               # Shared utility code
│   │   └── Persistence/             # Core Data stack (PersistenceController, entities)
│   └── iOS/                         # iOS-specific assets
├── data/                            # SQLite + ChromaDB storage
├── logs/                            # Application logs
├── docs/                            # Project documentation
│   └── archive/                     # Superseded documents
├── tests/                           # 731 tests (17 test files)
│   ├── test_inference.py            # 22 inference tests
│   ├── test_memory.py               # 33 memory tests
│   ├── test_temporal_decay.py       # 45 temporal decay tests
│   ├── test_orchestration.py        # 42 orchestration tests
│   ├── test_execution.py            # 47 execution tests
│   ├── test_apple.py                # 33 Apple integration tests
│   ├── test_tasks.py                # 60 task management tests
│   ├── test_orders.py               # 27 orders tests
│   ├── test_agents.py               # 28 agent profile tests
│   ├── test_user.py                 # 41 user settings tests
│   ├── test_proactive.py            # 29 proactive intelligence tests
│   ├── test_cloud.py                # 48 cloud module tests
│   ├── test_cloud_client.py         # 39 cloud client + routing tests
│   ├── test_cloud_routes.py         # 39 cloud API route tests
│   ├── test_council.py              # 124 council tests (models, roles, manager, handler integration)
│   ├── test_voice.py                # 52 voice module tests
│   └── test_voice_routes.py         # 25 voice API route tests
├── scripts/
│   ├── deploy-to-mini.sh            # Deploy to Mac Mini (rsync + SSH + pytest + launchd)
│   ├── sync-swift-tools.sh          # Build & sync CLI tools
│   ├── test-api.sh                  # API testing script (14 tests incl. cloud smoke)
│   ├── validate-security-edit.sh    # Pre-edit security hook
│   ├── auto-test.sh                 # Post-edit test hook (maps source → test files)
│   └── ollama-*.sh                  # Ollama management scripts
├── .claude/
│   ├── settings.local.json          # Permissions allowlist
│   ├── agents/
│   │   ├── hestia-tester.md         # Test runner sub-agent (Sonnet)
│   │   ├── hestia-reviewer.md       # Code review sub-agent (Sonnet)
│   │   ├── hestia-explorer.md       # Codebase navigator sub-agent (Haiku)
│   │   └── hestia-deployer.md       # Deployment sub-agent (Sonnet)
│   └── output-styles/
│       └── hestia-development.md    # Hestia coding conventions
├── .venv/                           # Python 3.9 virtual environment
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # pytest configuration (600s timeout)
├── PLUGIN-INSTALL-GUIDE.md          # Claude Code plugin install instructions
├── README.md
└── CLAUDE.md
```

---

## API Endpoints (65 total across 14 route files)

The REST API runs on port 8443 with JWT device authentication.

### Health & Auth (4 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/ping | No | Connectivity check |
| GET | /v1/health | No | System health status |
| POST | /v1/auth/register | No | Register device, get JWT token |
| POST | /v1/auth/refresh | Yes | Refresh JWT token |

### Chat & Mode (4 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /v1/chat | Yes | Send message to Hestia |
| GET | /v1/mode | Yes | Get current mode |
| POST | /v1/mode/switch | Yes | Switch persona mode |
| GET | /v1/mode/available | Yes | List available modes |

### Memory (4 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/memory/staged | Yes | List pending memory reviews |
| POST | /v1/memory/approve/{id} | Yes | Approve staged memory |
| POST | /v1/memory/reject/{id} | Yes | Reject staged memory |
| GET | /v1/memory/search | Yes | Semantic search |

### Sessions (3 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /v1/sessions | Yes | Create session |
| GET | /v1/sessions/{id}/history | Yes | Get conversation history |
| DELETE | /v1/sessions/{id} | Yes | End session |

### Tools (3 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/tools | Yes | List available tools |
| GET | /v1/tools/{name} | Yes | Get tool details |
| GET | /v1/tools/{name}/schema | Yes | Get tool schema |

### Tasks (6 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /v1/tasks | Yes | Create background task |
| GET | /v1/tasks | Yes | List tasks (with filters) |
| GET | /v1/tasks/{id} | Yes | Get task details |
| POST | /v1/tasks/{id}/approve | Yes | Approve awaiting task |
| POST | /v1/tasks/{id}/cancel | Yes | Cancel task |
| POST | /v1/tasks/{id}/retry | Yes | Retry failed task |

### Cloud (7 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/cloud/providers | Yes | List cloud providers |
| POST | /v1/cloud/providers | Yes | Add cloud provider |
| DELETE | /v1/cloud/providers/{provider} | Yes | Remove cloud provider |
| PATCH | /v1/cloud/providers/{provider}/state | Yes | Update routing state |
| PATCH | /v1/cloud/providers/{provider}/model | Yes | Select active model |
| GET | /v1/cloud/usage | Yes | Cloud usage/cost summary |
| POST | /v1/cloud/providers/{provider}/health | Yes | Health check provider |

### Voice (2 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /v1/voice/quality-check | Yes | Quality check a transcript |
| POST | /v1/voice/journal-analyze | Yes | Analyze journal transcript |

### Orders (7 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | /v1/orders | Yes | Create order |
| GET | /v1/orders | Yes | List orders |
| GET | /v1/orders/{id} | Yes | Get order details |
| PATCH | /v1/orders/{id} | Yes | Update order |
| DELETE | /v1/orders/{id} | Yes | Delete order |
| GET | /v1/orders/{id}/executions | Yes | List executions |
| POST | /v1/orders/{id}/execute | Yes | Execute order now |

### Agents (10 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/agents | Yes | List agent profiles |
| GET | /v1/agents/{slot} | Yes | Get agent profile |
| PUT | /v1/agents/{slot} | Yes | Update agent profile |
| DELETE | /v1/agents/{slot} | Yes | Reset agent to default |
| POST | /v1/agents/{slot}/photo | Yes | Upload agent photo |
| GET | /v1/agents/{slot}/photo | Yes | Get agent photo |
| DELETE | /v1/agents/{slot}/photo | Yes | Delete agent photo |
| GET | /v1/agents/{slot}/snapshots | Yes | List snapshots |
| POST | /v1/agents/{slot}/restore | Yes | Restore from snapshot |
| POST | /v1/agents/sync | Yes | Sync agent profiles |

### User (8 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/user/profile | Yes | Get user profile |
| PATCH | /v1/user/profile | Yes | Update user profile |
| POST | /v1/user/photo | Yes | Upload user photo |
| GET | /v1/user/photo | Yes | Get user photo |
| DELETE | /v1/user/photo | Yes | Delete user photo |
| GET | /v1/user/settings | Yes | Get user settings |
| PATCH | /v1/user/settings | Yes | Update user settings |
| POST | /v1/user/push-token | Yes | Register push token |
| DELETE | /v1/user/push-token | Yes | Remove push token |

### Proactive (6 endpoints)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/proactive/briefing | Yes | Get today's briefing |
| GET | /v1/proactive/policy | Yes | Get interruption policy |
| POST | /v1/proactive/policy | Yes | Update interruption policy |
| GET | /v1/proactive/patterns | Yes | List detected patterns |
| GET | /v1/proactive/notifications | Yes | Get notification history |
| POST | /v1/proactive/notifications/dismiss | Yes | Dismiss notification |

**Start the server:**
```bash
source .venv/bin/activate
python -m hestia.api.server
```

**API docs:** http://localhost:8443/docs

---

## Test Coverage Summary

| Component | Tests | Status |
|-----------|-------|--------|
| Inference | 22 | Passing (2 require Ollama) |
| Memory | 33 | Passing |
| Temporal Decay | 45 | Passing |
| Orchestration | 42 | Passing |
| Execution | 47 | Passing |
| Apple | 33 | Passing |
| Tasks | 60 | Passing |
| Orders | 27 | Passing |
| Agents | 28 | Passing |
| User | 41 | Passing |
| Proactive | 29 | Passing |
| Cloud (models/db/mgr) | 48 | Passing |
| Cloud (client/routing) | 39 | Passing |
| Cloud (API routes) | 39 | Passing |
| Voice (quality/journal) | 52 | Passing |
| Voice (API routes) | 25 | Passing |
| Council (models/roles/mgr/handler) | 124 | Passing |
| **Total** | **731** | **All passing (3 skipped)** |

Run tests:
```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

---

## Session Log

### 2025-01-08: Project Initialization

**Completed:**
- Phase 0: Created project structure, git repo, venv, requirements.txt
- Phase 0: Installed Ollama, pulled Mixtral 8x7B (28GB, Q4_K_M)
- Phase 0.5: Built `hestia-keychain-cli` Swift CLI
- Phase 0.5: Implemented `CredentialManager` with three-tier partitioning
- Phase 1: Implemented `HestiaLogger` with JSON logging, credential sanitization
- Phase 1: Implemented `AuditLogger` for 7-year credential access logs
- Phase 1: Created log viewer CLI
- Created CLAUDE.md for project context

### 2025-01-09: Phases 2-5.5 (Major Build Day)

**Completed:**
- Phase 2: Inference layer with local routing (Qwen 2.5 7B)
- Phase 3: Memory layer with ChromaDB + SQLite, ADR-013 tag schema
- Phase 4: Orchestration with state machine, modes, validation
- Phase 5: Execution layer with sandbox, gating, tool registry
- Phase 5.5: Apple ecosystem with 20 tools (Calendar, Reminders, Notes, Mail)
- Deployed all Swift CLIs to Mac Mini (~/.hestia/bin/)
- 182 unit tests passing

### 2025-01-11: Phase 6a REST API

**Completed:**
- Built complete FastAPI REST API layer
- JWT device authentication system
- 7 route modules (auth, health, chat, mode, memory, sessions, tools)
- Pydantic request/response schemas
- API documentation at /docs
- Test script (scripts/test-api.sh)

**Files Created:**
- `hestia/api/server.py` - FastAPI app with lifecycle
- `hestia/api/schemas.py` - Pydantic models
- `hestia/api/middleware/auth.py` - JWT authentication
- `hestia/api/routes/*.py` - 7 route modules

**API Stats:**
- 17 endpoints across 7 route modules
- ~1,800 lines of code
- Full Swagger documentation

**Next:**
- Phase 6b: Native app integration
- Deploy API to Mac Mini
- Test end-to-end with iOS app

### 2025-01-11: Phase 6b Native App (continued)

**Completed:**
- Built complete SwiftUI app (HestiaApp) with 43+ Swift files
- Design system: Colors (Figma-based gradients), Typography, Spacing, Animations
- Models: HestiaMode, Message, Response, MemoryChunk, SystemHealth, HestiaError
- Services: HestiaClientProtocol, MockHestiaClient, APIClient, AuthService, NetworkMonitor
- ViewModels: ChatViewModel, CommandCenterViewModel, MemoryReviewViewModel, SettingsViewModel
- Views: ChatView, CommandCenterView, MemoryReviewView, SettingsView, AgentCustomizationView
- Features implemented:
  - Mode-specific gradient backgrounds (Tia=Orange/Brown, Mira=Blue, Olly=Green)
  - Mode switching via @mentions in chat (@tia, @mira, @olly) with ripple transitions
  - Typewriter text effect for responses
  - Face ID authentication (skipped in simulator for dev)
  - Custom profile images for Tia (Hestia) and Olly (Apollo)
  - Message bubbles with mode indicators
- Used xcodegen for project file generation
- iOS 16+ target with ObservableObject pattern (not @Observable)

**Files Created:**
- `HestiaApp/project.yml` - xcodegen configuration
- `HestiaApp/Shared/` - 43 Swift files (design system, models, services, views)
- `HestiaApp/iOS/` - Assets, Info.plist, fonts

**App Structure:**
```
HestiaApp/
├── Shared/
│   ├── App/HestiaApp.swift, ContentView.swift
│   ├── DesignSystem/Colors.swift, Typography.swift, Spacing.swift, Animations.swift
│   ├── Models/HestiaMode.swift, Message.swift, Response.swift, etc.
│   ├── Services/HestiaClientProtocol.swift, MockHestiaClient.swift, APIClient.swift, etc.
│   ├── ViewModels/ChatViewModel.swift, VoiceInputViewModel.swift, CommandCenterViewModel.swift, etc.
│   └── Views/Chat/ (ChatView, VoiceRecordingOverlay, TranscriptReviewView), CommandCenter/, Settings/, etc.
├── iOS/Assets.xcassets, Info.plist
└── project.yml
```

### 2025-01-12: Comprehensive Audit & Fixes (Morning Session)

**Audit Scope:**
- Principal-level review of entire codebase (Python backend + iOS app)
- Cross-referenced all documentation against implementation
- Security vulnerability assessment
- Code quality and best practices review

**Critical Issues Found & Fixed:**
1. **Python async property bug** - `handler.py` had `@property async def memory_manager` which would crash at runtime (Python properties cannot be async)
2. **iOS force-unwrap crash** - `APIClient.swift` used `URL(string:)!` which could crash on invalid URLs
3. **JWT key persistence** - Server generated new JWT secret on every restart, invalidating all tokens

**Security Hardening:**
- Restricted CORS origins (was `allow_origins=["*"]`)
- Reduced token expiration from 365 days to 90 days
- Wrapped iOS debug print statements in `#if DEBUG`
- Implemented JWT secret storage in macOS Keychain via CredentialManager

**iOS Quality Fixes:**
- Added `scenePhase` observer to pause gradient animation when app backgrounded (battery)
- Added `[weak self]` to DispatchQueue closure to prevent retain cycle
- Added message array limit (100 messages) to prevent unbounded memory growth

**Backend Reliability:**
- Fixed race condition in session creation (was fire-and-forget, now awaited)
- Added 30s timeout to database initialization
- Removed deprecated `cloud.py.deprecated` file

**Documentation Updated:**
- Phase 4.5 status: Marked as COMPLETE (was incorrectly shown as incomplete)
- Endpoint count: Updated from 24 to 25
- ADR-021/ADR-022: Marked as IMPLEMENTED

**Files Modified:**
- `hestia/orchestration/handler.py` - Fixed async property bug
- `hestia/api/middleware/auth.py` - JWT Keychain persistence, 90-day expiry
- `hestia/api/server.py` - CORS restrictions
- `hestia/memory/manager.py` - Session race condition, init timeout
- `HestiaApp/Shared/Services/APIClient.swift` - Safe URL init, DEBUG guards
- `HestiaApp/Shared/Views/Common/GradientBackground.swift` - Battery optimization
- `HestiaApp/Shared/ViewModels/ChatViewModel.swift` - Memory fixes

### 2025-01-12: Phase 10 Security Hardening + Bug Fixes (Evening Session)

**Security Hardening Complete (Phase 10):**
- Certificate generation with 4096-bit keys
- iOS certificate pinning (CertificatePinning.swift)
- HTTPS-only configuration
- Rate limiting middleware
- Security headers (HSTS, CSP, X-Frame-Options)
- Error message sanitization (no internal paths leaked)
- Focus mode symlink attack prevention
- Weather API input validation
- Config persistence hardening

**Critical Bug: Tool Calling Not Working**
- **Root Cause:** `get_tool_definitions()` existed but was never injected into LLM prompts
- **Symptom:** Hestia asked "which calendar?" instead of checking tools
- **Fix:** Added tool definitions to system prompt with explicit instructions
- **File:** `hestia/orchestration/handler.py` - Added tool injection at Step 6
- **New method:** `_try_execute_tool_from_response()` - Parses and executes tool calls from LLM

**Mode Switching Fix:**
- **Issue:** "Hey Tia" didn't trigger mode switch (only @tia worked)
- **Fix:** Extended invoke patterns in `mode.py` to include: `hey tia`, `hi tia`, `hello tia`
- **iOS update:** `ChatViewModel.swift` also updated with greeting patterns

**Scroll View Fix Attempted:**
- Added `.allowsHitTesting(false)` to ripple effect overlay
- Restructured messageList with proper GeometryReader/ScrollViewReader hierarchy
- Changed to `ScrollView(.vertical, showsIndicators: true)`
- Added `.frame(minHeight: geometry.size.height)` for content sizing
- **Status:** Still under investigation - needs iOS rebuild to test

**Files Modified:**
- `hestia/orchestration/handler.py` - Tool injection, tool execution
- `hestia/orchestration/mode.py` - Added greeting patterns (hey/hi/hello)
- `HestiaApp/Shared/ViewModels/ChatViewModel.swift` - Added greeting patterns
- `HestiaApp/Shared/Views/Chat/ChatView.swift` - Scroll view restructure

**Server Status:**
- HTTPS server running on port 8443
- SSL certificates auto-detected from `certs/` directory
- All 242 tests passing

### 2025-01-12: iOS App Polish Session (Late Night)

**Major iOS Features Completed:**
1. **Chat Scroll Fixed** - Bottom-anchored with proper keyboard avoidance
2. **Calendar Integration** - Full EventKit integration via CalendarService protocol
3. **CommandCenter Rebuilt** - Modular widget architecture:
   - Orders Widget: CRUD for scheduled prompts with MCP resource selection
   - Alerts Widget: Execution history display (last 48 hours)
   - Calendar Widget: Next meeting card with countdown
   - Tab selector for Orders/Alerts switching
   - Neural Net placeholder (H2 2026)
4. **Settings Rebuilt** - Three sections:
   - System Status: Health indicators, server connection
   - User Profile: Name, email, preferences editing
   - Agent Profiles: 3-slot customization (Tia/Mira/Olly) with photos
5. **Core Data Setup** - Programmatic model definition:
   - OrderEntity with execution tracking
   - OrderExecutionEntity for history
   - AgentProfileEntity for persona customization
   - PersistenceController with shared/preview instances
6. **API Contract Design** - New endpoints defined:
   - Orders API: CRUD + execute + executions history
   - Agent Profiles API: CRUD + photos + snapshots + restore + sync
   - User Settings API: Profile + settings + push token

**Files Created/Modified:**
- `HestiaApp/Shared/Models/Order.swift` - Order domain model
- `HestiaApp/Shared/Models/CalendarEvent.swift` - Calendar event model
- `HestiaApp/Shared/Models/AgentProfile.swift` - Agent profile model
- `HestiaApp/Shared/Services/CalendarService.swift` - EventKit integration
- `HestiaApp/Shared/Services/OrdersService.swift` - Core Data persistence
- `HestiaApp/Shared/Views/CommandCenter/CommandCenterView.swift` - Main view
- `HestiaApp/Shared/Views/CommandCenter/Widgets/OrdersWidget.swift` - Orders UI
- `HestiaApp/Shared/Views/CommandCenter/Widgets/AlertsWidget.swift` - Alerts UI
- `HestiaApp/Shared/Views/Settings/SettingsView.swift` - Rebuilt
- `HestiaApp/Shared/ViewModels/CommandCenterViewModel.swift` - Widget orchestration
- `HestiaApp/Shared/Persistence/PersistenceController.swift` - Core Data stack
- `HestiaApp/Shared/Persistence/CoreDataModels.swift` - Programmatic entities
- `docs/api-contract.md` - Orders, Agent Profiles, User Settings APIs
- `hestia/api/schemas.py` - Pydantic schemas for new endpoints

**Architecture Validation:**
- Tag-based schema (ADR-013) confirmed as foundation for memory layer
- MCPResource enum uses categorical tagging (calendar, email, reminders, notes, weather, stocks)
- Orders use frequency-based scheduling (once, daily, weekly, monthly, custom)
- Agent profiles use slot-indexed storage (0-2) with snapshot/restore capability

### 2025-01-12: Phase 6b Backend Implementation (Continued)

**Completed: Full Backend for Orders, Agent Profiles, User Settings**

Created 3 complete Python modules with models, database, manager, and API routes:

**Orders Module (`hestia/orders/`):**
- `models.py` - Order, OrderExecution, OrderFrequency, MCPResource enums
- `database.py` - SQLite persistence with aiosqlite
- `manager.py` - OrderManager for lifecycle management
- `scheduler.py` - APScheduler integration (CronTrigger, IntervalTrigger, DateTrigger)
- 7 API endpoints in `hestia/api/routes/orders.py`:
  - POST/GET/PATCH/DELETE /v1/orders
  - GET /v1/orders/{id}/executions
  - POST /v1/orders/{id}/execute

**Agent Profiles Module (`hestia/agents/`):**
- `models.py` - AgentProfile, AgentSnapshot, DEFAULT_AGENTS (Tia/Mira/Olly)
- `database.py` - SQLite with snapshot support, 90-day retention
- `manager.py` - AgentManager with photo management and sync
- 9 API endpoints in `hestia/api/routes/agents.py`:
  - GET/PUT/DELETE /v1/agents/{slot_index}
  - POST/GET/DELETE /v1/agents/{slot_index}/photo
  - GET /v1/agents/{slot_index}/snapshots
  - POST /v1/agents/{slot_index}/restore
  - POST /v1/agents/sync

**User Settings Module (`hestia/user/`):**
- `models.py` - UserProfile, UserSettings, PushToken, QuietHours
- `database.py` - Single-user persistence
- `manager.py` - UserManager with photo and push token management
- 6 API endpoints in `hestia/api/routes/user.py`:
  - GET/PATCH /v1/user/profile
  - POST/GET/DELETE /v1/user/photo
  - GET/PATCH /v1/user/settings
  - POST/DELETE /v1/user/push-token

**Infrastructure Updates:**
- Added `apscheduler>=3.10.0` to requirements.txt
- Updated `hestia/api/routes/__init__.py` with new routers
- Updated `hestia/api/server.py` to initialize new managers
- Schemas already complete in `hestia/api/schemas.py`

**Tests Created:**
- `tests/test_orders.py` - ~45 tests for Orders module
- `tests/test_agents.py` - ~40 tests for Agent Profiles module
- `tests/test_user.py` - ~50 tests for User Settings module

**Total New Endpoints:** 22 endpoints (7 + 9 + 6)
**Total API Endpoints:** ~47 endpoints

---

### 2026-02-08: Claude Code Infrastructure Build

**Completed: Sub-Agents, Output Style, Hooks, 4-Phase Workflow**

Built the Claude Code development infrastructure for Hestia based on comprehensive ecosystem analysis (Skills, Sub-Agents, Plugins, Output Styles, MCPs, Hooks).

**Sub-Agents Created (`.claude/agents/`):**
- `hestia-tester.md` — Test runner + failure analyst (Sonnet, 15 turns max)
- `hestia-reviewer.md` — Code reviewer for security/architecture/quality (Sonnet, 12 turns, read-only)
- `hestia-explorer.md` — Codebase navigator (Haiku, 20 turns, read-only, fast/cheap)
- `hestia-deployer.md` — Deployment specialist (Sonnet, 10 turns, hard gate on test failures)

**Output Style Created (`.claude/output-styles/`):**
- `hestia-development.md` — Enforces Python conventions, API patterns, Swift standards, 4-phase workflow, sub-agent usage. Keeps built-in coding instructions.

**Hook Scripts Created (`scripts/`):**
- `validate-security-edit.sh` — Pre-edit security validation (credentials, CORS, exception handling)
- `auto-test.sh` — Post-edit auto-test runner (maps source modules to test files)

**Workflow Encoded:**
- 4-phase mandatory workflow (Research > Plan > Execute > Review) added to top of CLAUDE.md
- Sub-agent usage table with model assignments
- All future sessions must follow this structure

**Plugin Installation Guide:**
- `PLUGIN-INSTALL-GUIDE.md` — Instructions for pyright-lsp, github, commit-commands, pr-review-toolkit

**Analysis Document:**
- `bolstering-hestia-with-claude-code-ecosystem.md` — Full masterclass document covering Skills, Sub-Agents, Plugins, Output Styles, MCPs, and Hooks with Hestia-specific recommendations, trade-offs, and 4-week priority roadmap.

**Deferred (by design):**
- Skills (5 recommended, to be built when ready)
- MCP servers (GitHub, Filesystem, Firecrawl — designed but not configured)

### 2026-02-08: Enhancement Plan + Workstream 4 (Temporal Decay)

**Completed: Enhancement Plan Design + Temporal Decay Implementation**

Designed and approved a comprehensive 4-workstream enhancement plan covering Cloud LLM, Voice Journaling, Sub-Agent Council + SLM, and Temporal Semantic Search. Then executed Workstream 4 as the first deliverable.

**Enhancement Plan (`.claude/plans/hidden-sauteeing-gray.md`):**
- 4 workstreams with detailed file-level specs for every new/modified file
- 8 design decisions confirmed with Andrew (key storage, voice UX, council scope, speech engine, model selection, agent toggles, quality gate, temporal decay config)
- Build order: WS4 (Temporal Decay) → WS1 (Cloud LLM) → WS2 (Voice) → WS3 (Council + SLM)
- Estimated ~30+ new files, 12 new API endpoints, 200+ new tests across all workstreams

**Workstream 4: Temporal Decay — COMPLETE:**

*Files Created:*
- `hestia/config/memory.yaml` — Per-chunk-type decay rate configuration
- `hestia/memory/decay.py` — `TemporalDecay` class with exponential decay formula
- `tests/test_temporal_decay.py` — 45 tests across 6 test classes

*Files Modified:*
- `hestia/memory/models.py` — Added `decay_adjusted: bool` to `MemorySearchResult`
- `hestia/memory/manager.py` — Integrated decay into `search()`, `__init__()`, `initialize()`
- `hestia/api/schemas.py` — Added `decay_adjusted` to API `MemorySearchResult` schema

*Architecture:*
- Formula: `adjusted = raw_score * e^(-λ * age_days) * recency_boost`, clamped to `[0.1, 1.0]`
- Per-chunk-type λ: conversation=0.02 (~35d half-life), fact=0.0, preference=0.005 (~139d), decision=0.002 (~347d), action_item=0.01 (~69d), research=0.007 (~99d), system=0.0
- Recency boost: 1.2x for memories < 24h old
- Config-driven via YAML (no hardcoded values)

*Test Results:* 404 passed, 3 skipped, 0 failed (full regression clean)

**Next:** Workstream 1 — Cloud LLM Support

### 2026-02-08: WS1 Cloud LLM — Sessions 1 & 2 (Foundation + Inference Integration)

**Completed: Cloud module foundation + inference integration with 3-state routing**

WS1 builds cloud LLM support across 5 sessions. Sessions 1 and 2 completed in this day.

**Session 1 — Cloud Module Foundation (models, database, manager):**
- `hestia/cloud/models.py` — `CloudProvider` (Anthropic/OpenAI/Google), `CloudProviderState` (disabled/enabled_full/enabled_smart), `CloudModel`, `ProviderConfig`, `CloudUsageRecord`, `PROVIDER_DEFAULTS` with curated model lists and pricing, `calculate_cost()`
- `hestia/cloud/database.py` — SQLite persistence for provider configs + usage tracking
- `hestia/cloud/manager.py` — `CloudManager` with provider CRUD, model detection (live API calls to all 3 providers with curated fallbacks), health checks, usage/cost tracking, Keychain-backed API key storage with in-memory fallback for test environments
- `tests/test_cloud.py` — 48 tests all passing

**Session 2 — Inference Integration (client, router, cloud routing):**

*New Files:*
- `hestia/cloud/client.py` — `CloudInferenceClient` with provider-specific HTTP call formatting (Anthropic Messages API, OpenAI Chat Completions, Google Gemini generateContent), normalized `InferenceResponse`, error hierarchy (`CloudAuthError`, `CloudRateLimitError`, `CloudModelError`), usage record building
- `tests/test_cloud_client.py` — 39 tests (4 Anthropic, 3 OpenAI, 4 Google, 8 error handling, 2 usage tracking, 4 lifecycle, 14 router integration)

*Modified Files:*
- `hestia/inference/router.py` — Added `ModelTier.CLOUD`, `CloudRoutingConfig`, 3-state routing logic (disabled=local-only, enabled_full=always cloud with local fallback, enabled_smart=local-first with cloud spillover on failure or high token count), `set_cloud_state()` for dynamic updates, state validation
- `hestia/inference/client.py` — New `_call_cloud()` method that retrieves active provider + API key from `CloudManager`, delegates to `CloudInferenceClient`, tracks usage. Refactored `_call_with_routing()` to support cloud tier (direct or spillover). New `_call_local_with_retries()` extracted for clarity. Credential sanitization in error messages.
- `hestia/inference/__init__.py` — Updated exports for `CloudRoutingConfig`
- `hestia/config/inference.yaml` — Added `cloud:` section with `state`, `spillover_token_threshold` (16K), `spillover_on_local_failure`, `request_timeout` (60s), `max_retries` (2)

*Architecture:*
- Three routing states: disabled (local-only, default), enabled_full (all queries → cloud, local fallback), enabled_smart (local-first, cloud spillover)
- Smart spillover triggers: (1) token count > 16K threshold, (2) local model retries exhausted
- Cloud calls go through: `InferenceClient._call_cloud()` → `CloudManager.get_active_provider()` → `CloudManager.get_api_key()` → `CloudInferenceClient.complete()` → provider-specific HTTP call
- Provider priority: Anthropic > OpenAI > Google (first enabled wins)
- Usage recorded after every cloud call for cost tracking

*Review Findings Addressed:*
- Added cloud_state validation (ValueError on invalid state)
- Added error response parsing logging
- Added credential sanitization in error messages (prevent API key leakage)
- Noted: CredentialManager audit logging for cloud keys deferred (pre-existing pattern from Session 1)

*Test Results:* 491 passed, 3 skipped, 0 failed (full regression clean)

**WS1 Sessions (ALL COMPLETE):**
- ~~Session 1: Cloud module foundation (models, database, manager)~~ COMPLETE
- ~~Session 2: Inference integration (client, router, cloud routing)~~ COMPLETE
- ~~Session 3: API routes (7 cloud endpoints, Pydantic schemas)~~ COMPLETE
- ~~Session 4: iOS Settings UI (SwiftUI cloud provider management)~~ COMPLETE
- ~~Session 5: End-to-end testing + deploy~~ COMPLETE

### 2026-02-08: WS1 Cloud LLM — Session 3 (API Routes)

**Completed: 7 cloud API endpoints + Pydantic schemas + 39 tests**

*New Files:*
- `hestia/api/routes/cloud.py` — 7 REST endpoints for cloud provider management:
  - `GET /v1/cloud/providers` — List configured providers with effective cloud state
  - `POST /v1/cloud/providers` — Add provider (API key stored in Keychain, never returned)
  - `DELETE /v1/cloud/providers/{provider}` — Remove provider + delete API key
  - `PATCH /v1/cloud/providers/{provider}/state` — Update routing state (disabled/enabled_full/enabled_smart)
  - `PATCH /v1/cloud/providers/{provider}/model` — Select active model
  - `GET /v1/cloud/usage` — Usage/cost summary with per-provider and per-model breakdowns
  - `POST /v1/cloud/providers/{provider}/health` — Run health check
- `tests/test_cloud_routes.py` — 39 tests across 11 test classes

*Modified Files:*
- `hestia/api/schemas.py` — Added cloud schemas: `CloudProviderEnum`, `CloudProviderStateEnum`, `CloudProviderAddRequest`, `CloudProviderStateUpdateRequest`, `CloudProviderModelUpdateRequest`, `CloudModelInfo`, `CloudProviderResponse`, `CloudProviderListResponse`, `CloudProviderDeleteResponse`, `CloudUsageSummaryResponse`, `CloudHealthCheckResponse`
- `hestia/api/routes/__init__.py` — Added `cloud_router` export
- `hestia/api/server.py` — Added `CloudManager` initialization in lifespan, included `cloud_router`

*Key Design Decisions:*
- API keys accepted via POST body but never returned in responses (only `has_api_key: bool`)
- State propagation: every add/remove/state-change recomputes effective cloud state and pushes to `router.set_cloud_state()`
- Effective state priority: enabled_full > enabled_smart > disabled (any provider in full mode activates full for the system)
- Usage aggregation transforms database list format to dict format keyed by provider and model
- API key min-length validation (10 chars) before Keychain storage
- Router sync failures are defensive (log + continue) to avoid blocking API operations

*Review: 0 critical, 3 warnings addressed*
- Added API key length validation before storage
- Clarified SQL NULL handling in usage aggregation
- Strengthened health check test assertions

*Test Results:* 530 passed, 3 skipped, 0 failed (full regression clean)

### 2026-02-08: WS1 Cloud LLM — Session 4 (iOS Settings UI)

**Completed: SwiftUI cloud provider management screens — 6 new files, 3 modified files**

*New Files:*
- `HestiaApp/Shared/Models/CloudProvider.swift` — Local model with `ProviderType` (anthropic/openai/google), `ProviderState` (disabled/enabledFull/enabledSmart), display helpers, DesignSystem colors, conversion from API response
- `HestiaApp/Shared/ViewModels/CloudSettingsViewModel.swift` — @MainActor ObservableObject with CRUD operations, health checks, usage loading. All async methods use APIClient directly.
- `HestiaApp/Shared/Views/Settings/CloudSettingsView.swift` — Main view: effective cloud state summary, provider list with state badges + health indicators, usage summary (requests/tokens/cost), add provider button, empty state
- `HestiaApp/Shared/Views/Settings/CloudProviderDetailView.swift` — Detail view: state picker (disabled/smart/full) with descriptions, model selector, API key status, health check, remove provider (danger zone)
- `HestiaApp/Shared/Views/Settings/AddCloudProviderView.swift` — Sheet: provider picker with icons/colors, SecureField for API key, state selector, optional model override, 10-char minimum validation

*Modified Files:*
- `HestiaApp/Shared/Models/APIModels.swift` — Added 12 cloud API models: `APICloudProvider`, `APICloudProviderState`, `CloudProviderAddRequest`, `CloudProviderStateUpdateRequest`, `CloudProviderModelUpdateRequest`, `CloudModelInfo`, `CloudProviderResponse`, `CloudProviderListResponse`, `CloudProviderDeleteResponse`, `CloudUsageSummaryResponse`, `CloudUsageBreakdown`, `CloudHealthCheckResponse`
- `HestiaApp/Shared/Services/APIClient.swift` — Added 7 cloud API methods: `listCloudProviders()`, `addCloudProvider()`, `removeCloudProvider()`, `updateCloudProviderState()`, `updateCloudProviderModel()`, `getCloudUsage()`, `checkCloudProviderHealth()`
- `HestiaApp/Shared/Views/Settings/SettingsView.swift` — Added "Cloud Providers" section between System Status and User Profile with NavigationLink to CloudSettingsView
- `HestiaApp/Shared/DesignSystem/Colors.swift` — Added cloud provider brand colors: `anthropicBrand`, `openAIBrand`, `googleBrand`

*Architecture:*
- Follows existing MVVM pattern: View → ViewModel → APIClient → Backend
- All views use DesignSystem tokens (Spacing, CornerRadius, Colors)
- API keys handled via SecureField, stored in Keychain (never displayed after entry)
- Snake_case JSON auto-decoded by existing APIClient encoder/decoder
- Provider state changes propagated to backend, which syncs to inference router

*Review: 0 critical, 4 warnings (3 deferred as non-blocking, 1 addressed — provider colors moved to DesignSystem)*

*Backend Test Results:* 530 passed, 3 skipped, 0 failed (full regression clean)

### 2026-02-08: WS1 Cloud LLM — Session 5 (E2E Testing + Deploy)

**Completed: End-to-end verification + deployment to Mac Mini. WS1 COMPLETE.**

*What was tested:*
- Full backend regression: 530 passed, 3 skipped, 0 failed (both local and on Mac Mini)
- All 7 cloud endpoints verified on live Mac Mini (HTTPS):
  - GET /v1/cloud/providers → 200 (empty list, cloud_state: "disabled")
  - GET /v1/cloud/usage → 200 (all zeros)
  - POST health (unconfigured) → 404
  - POST add (short key) → 400 (key validation works)
  - DELETE (unconfigured) → 404
  - PATCH state (unconfigured) → 404
  - PATCH model (unconfigured) → 404
- Deployment script health check verified (HTTPS with retry)

*Modified Files:*
- `scripts/test-api.sh` — Added 4 cloud smoke tests (tests 10-13), changed default to HTTPS, added CURL_OPTS for self-signed certs with HESTIA_CA_CERT support, made tools endpoint non-blocking, strengthened cloud test assertions
- `scripts/deploy-to-mini.sh` — Fixed health check: HTTPS with retry loop (5 attempts, 10s total), HESTIA_CA_CERT support, removed HTTP fallback

*Pre-existing issues found (not WS1-related):*
- GET /v1/tools returns 500 on Mac Mini (Apple CLI tools initialization issue)
- POST /v1/sessions returns 500 on Mac Mini (orchestration handler initialization)
- Both are execution-layer issues that predate WS1 and don't affect cloud functionality

*Review: 2 criticals addressed (TLS -k flag gated behind HESTIA_CA_CERT), 2 warnings addressed (strict cloud assertions, retry health check)*

*Deployment:*
- Mac Mini: `andrewroman117@hestia-3.local:~/hestia`
- 530 tests passed on remote
- Service reloaded via launchd
- HTTPS health check passed

**WS1 Cloud LLM — COMPLETE. Next: WS2 (Voice Journaling) or WS3 (Council + SLM)**

### 2026-02-08: WS2 Voice Journaling — Session 1 (Backend Voice Module)

**Completed: Voice module with quality checker, journal analyzer, and 52 tests**

WS2 builds voice journaling across 3 sessions. Session 1 creates the backend voice module.

**Design Decisions Confirmed:**
- Voice UX: Mic button in Chat input bar (not separate tab)
- Speech engine: SpeechAnalyzer only (iOS 26+, no WhisperKit)
- Quality gate: LLM flags uncertain words + user editable transcript with highlights
- iOS target: Bump from 16.0 to 26.0 (clean break for SpeechAnalyzer)

*New Files:*
- `hestia/voice/__init__.py` — Module entry point, exports all public symbols
- `hestia/voice/models.py` — 9 data models: `TranscriptSegment`, `FlaggedWord`, `QualityReport`, `IntentType` (enum), `JournalIntent`, `CrossReferenceSource` (enum), `CrossReference`, `ActionPlanItem`, `JournalAnalysis`. All with `to_dict()`/`from_dict()`/`create()` factories.
- `hestia/voice/quality.py` — `TranscriptQualityChecker`: LLM-powered quality analysis. Flags homophones, misheard proper nouns, uncommon words. Cross-references known entities. Returns `QualityReport` with flagged words and confidence scores. Singleton via `get_quality_checker()`.
- `hestia/voice/journal.py` — `JournalAnalyzer`: 3-stage pipeline: (1) LLM intent extraction, (2) parallel cross-referencing against calendar/mail/memory/reminders via `asyncio.gather`, (3) LLM action plan generation with tool call mappings. Lazy imports for Apple clients. Singleton via `get_journal_analyzer()`.
- `tests/test_voice.py` — 52 tests across 10 test classes covering all models, quality checker, and journal analyzer

*Bug Found & Fixed:*
- `journal.py:336` — Missing `await` on `get_memory_manager()` (async factory). Would silently fail at runtime since the exception handler caught the coroutine error. Fixed to `await get_memory_manager()`.

*Review: 0 critical, 2 minor warnings (non-blocking)*
- LogComponent.MEMORY used for voice logging (acceptable, consider VOICE in future)
- Some magic numbers could be extracted to constants (deferred)

*Test Results:* 582 passed, 3 skipped, 0 failed (full regression clean)

**WS2 Sessions (ALL COMPLETE):**
- ~~Session 1: Backend voice module (models, quality, journal)~~ COMPLETE
- ~~Session 2: Backend API routes + schemas + iOS target bump~~ COMPLETE
- ~~Session 3: iOS SpeechService + Voice UI + ChatView integration~~ COMPLETE

### 2026-02-08: WS2 Voice Journaling — Session 2 (API Routes + iOS Target)

**Completed: 2 voice endpoints, 12 Pydantic schemas, iOS 26.0 target bump, 25 route tests**

*New Files:*
- `hestia/api/routes/voice.py` — 2 REST endpoints:
  - `POST /v1/voice/quality-check` — LLM flags uncertain words, returns flagged words + confidence
  - `POST /v1/voice/journal-analyze` — Full analysis pipeline: intents, cross-refs, action plan
- `tests/test_voice_routes.py` — 25 tests across 3 test classes (schemas, quality check route, journal analyze route)

*Modified Files:*
- `hestia/api/schemas.py` — Added 12 voice schemas: `VoiceFlaggedWord`, `VoiceQualityCheckRequest`, `VoiceQualityCheckResponse`, `VoiceIntentType`, `VoiceJournalIntent`, `VoiceCrossReferenceSource`, `VoiceCrossReference`, `VoiceActionPlanItem`, `VoiceJournalAnalyzeRequest`, `VoiceJournalAnalyzeResponse`
- `hestia/api/routes/__init__.py` — Added `voice_router` export
- `hestia/api/server.py` — Added `voice_router` import and include
- `HestiaApp/project.yml` — iOS target 16.0 → 26.0, Swift 5.9 → 6.1, Xcode 15.0 → 26.0, added Speech/Microphone usage descriptions

*Review Findings Addressed:*
- Changed LogComponent.MEMORY → LogComponent.API in route handlers (API routes should use API component)
- Sanitized error logs to use `type(e).__name__` instead of raw exception message
- iOS 26.0 target confirmed correct (Apple WWDC 2025, user has Xcode 26 beta)

*Test Results:* 607 passed, 3 skipped, 0 failed (full regression clean)

**WS2 Session 2 — COMPLETE. Next: Session 3 (iOS SpeechService + UI)**

### 2026-02-08: WS2 Voice Journaling — Session 3 (iOS SpeechService + Voice UI)

**Completed: SpeechService, VoiceInputViewModel, 3 new views, ChatView integration — WS2 COMPLETE**

*New Files:*
- `HestiaApp/Shared/Services/SpeechService.swift` — `@MainActor ObservableObject` wrapping SpeechAnalyzer + AVAudioEngine. On-device speech-to-text via `SpeechTranscriber` fed by `AsyncStream<AnalyzerInput>`. Includes permission checks, live transcript updates, recording duration timer.
- `HestiaApp/Shared/ViewModels/VoiceInputViewModel.swift` — Voice flow state machine (`VoicePhase`: idle → recording → qualityChecking → reviewing → analyzing). Manages recording lifecycle, API quality check, transcript editing, suggestion application with position-aware replacement.
- `HestiaApp/Shared/Views/Chat/VoiceRecordingOverlay.swift` — Full-screen overlay during recording: pulsing mic animation, live transcript preview, duration counter, cancel/done buttons.
- `HestiaApp/Shared/Views/Chat/TranscriptReviewView.swift` — Sheet for reviewing transcript: confidence badge (green/yellow/red), editable `TextEditor`, flagged word cards with suggestion chips, send/discard buttons.

*Modified Files:*
- `HestiaApp/Shared/Models/APIModels.swift` — Added voice API models: `VoiceQualityCheckRequest`, `VoiceFlaggedWordResponse` (with `uniqueKey`), `VoiceQualityCheckResponse`, `VoiceJournalAnalyzeRequest`, `VoiceJournalAnalyzeResponse`, intent/cross-ref/action-plan response types, `AnyCodableValue` type-erased Codable enum for dynamic JSON dicts
- `HestiaApp/Shared/Services/APIClient.swift` — Added `voiceQualityCheck(transcript:knownEntities:)` and `voiceJournalAnalyze(transcript:mode:)` methods
- `HestiaApp/Shared/Views/Chat/ChatView.swift` — Integrated voice flow: mic button (shows when text empty, like iMessage), `VoiceRecordingOverlay` via fullScreenCover, `TranscriptReviewView` via sheet, voiceViewModel configured with APIClient, accepted transcript sent through existing `sendMessage()` flow

*Review Findings Addressed:*
- Fixed `applySuggestion()` to use position-aware string replacement (reviewer warning: first-match-only was a UX bug for duplicate words)
- Added `uniqueKey` computed property to `VoiceFlaggedWordResponse` for collision-safe ForEach rendering
- Remaining warnings deferred as non-blocking: audio format nil check (iOS hardware guaranteed), ClearBackgroundView superview traversal (best-effort for fullScreenCover transparency)

*Review: 0 critical, 2 warnings addressed, 2 warnings deferred, 6 suggestions noted*

*Backend Test Results:* 607 passed, 3 skipped, 0 failed (full regression clean)

**WS2 Voice Journaling — COMPLETE (3/3 sessions). Next: WS3 (Council + SLM) or deployment**

**WS2 Sessions (ALL COMPLETE):**
- ~~Session 1: Backend voice module (models, quality, journal)~~ COMPLETE
- ~~Session 2: Backend API routes + schemas + iOS target bump~~ COMPLETE
- ~~Session 3: iOS SpeechService + Voice UI + ChatView integration~~ COMPLETE

### 2026-02-08: Hyper-Critical Audit + Quality Hardening

**Scope:** Principal-level audit of entire codebase followed by systematic fix of all findings.

**Audit Findings (prioritized):**
- P0: 25+ API route log messages leaked raw exception details via `{e}`
- P0: CLAUDE.md endpoint table stale (26 listed vs 65 actual), test counts wrong
- P1: No `LogComponent.VOICE` or `CLOUD` — all voice/cloud logs categorized as MEMORY or API
- P1: iOS `print()` statements unguarded in production code (3 files)
- P1: Sub-agent definitions stale (missing modules, wrong test counts)
- P2: Hook scripts missing new modules (cloud routes, voice routes)
- P2: Project structure tree missing orders/, agents/, user/, proactive/, voice/ modules

**All Findings Fixed:**

*P0: Error message sanitization*
- Created `hestia/api/errors.py` — `sanitize_for_log(e)` and `safe_error_detail()` helpers
- Updated all 14 route files: zero `{e}` in logs, zero `detail=str(e)` in HTTP responses
- Pattern: log `sanitize_for_log(e)` (exception type only), return generic messages to clients

*P1: LogComponent expansion*
- Added `VOICE = "voice"` and `CLOUD = "cloud"` to `LogComponent` enum in `structured_logger.py`
- Changed 15 references in `voice/quality.py` and `voice/journal.py` from MEMORY → VOICE

*P1: iOS print guards*
- Wrapped all `print()` in `#if DEBUG` in `AuthViewModel.swift`, `ChatViewModel.swift`, `HestiaApp.swift`

*P1: Sub-agent definitions*
- Updated all 4 sub-agents with: current test counts (610 total), all 16 backend modules, voice/cloud/proactive in codebase map, error sanitization conventions, deployment gotchas

*P2: Hook scripts*
- `auto-test.sh`: Added cloud route, voice route, and voice module mappings
- `validate-security-edit.sh`: Added cloud/manager.py, cloud/client.py, inference/client.py, cloud routes, auth routes

*Documentation: CLAUDE.md comprehensive update*
- Replaced 26-entry endpoint table with full 65-endpoint table (14 sections)
- Updated project structure tree with all 16 modules + errors.py + all route files
- Updated test coverage table with accurate counts (610 total)
- Added error handling conventions + new module checklist to Code Conventions
- Fixed "54 endpoints" → "65 endpoints" in Technical Stack

**Files Created:** `hestia/api/errors.py`
**Files Modified:** 14 route files, `structured_logger.py`, `voice/quality.py`, `voice/journal.py`, `AuthViewModel.swift`, `ChatViewModel.swift`, `HestiaApp.swift`, `auto-test.sh`, `validate-security-edit.sh`, `CLAUDE.md`, 4 sub-agent definitions

*Test Results:* 610 collected, 607 passed, 3 skipped, 0 failed

**Next Steps for New Session:**
1. WS3: Council + SLM (5-role council, intent classification, tool parsing) — or —
2. UI Phase 2: Quick wins (remove byline, remove Default Mode setting, move Memory to Command Center)
3. Deploy latest changes to Mac Mini (audit fixes not yet deployed)

### 2026-02-08: WS3 Council + SLM — Sessions 1-4 (Full Implementation)

**Completed: 4-role council with dual-path execution, handler integration, 124 tests. WS3 COMPLETE.**

WS3 adds a multi-role LLM council that provides intent classification, structured tool extraction, response validation, and personality synthesis. Dual-path execution: cloud active → parallel HTTP calls (~500ms), cloud disabled → SLM intent classification only (~100ms) + existing pipeline.

**Session 1 — Foundation (models, roles, prompts):**
- `hestia/council/models.py` — `IntentType` (13 values), `IntentClassification`, `ToolExtraction`, `ValidationReport`, `RoleResult`, `CouncilResult`, `CouncilConfig` with `from_dict()` YAML loading
- `hestia/council/roles.py` — `CouncilRole` ABC, `Coordinator` (intent JSON → IntentClassification), `Analyzer` (tool JSON → ToolExtraction), `Validator` (quality JSON → ValidationReport, fails open), `Responder` (plain text)
- `hestia/council/prompts.py` — 4 system prompt templates (coordinator, analyzer, validator, responder)
- `hestia/council/__init__.py` — Module exports
- `hestia/logging/structured_logger.py` — Added `LogComponent.COUNCIL`
- 59 tests passing

**Session 2 — Manager (dual-path orchestration):**
- `hestia/council/manager.py` — `CouncilManager` with:
  - `classify_intent()` — Coordinator via cloud or SLM
  - `run_council()` — Analyzer + Validator in parallel via `asyncio.gather`
  - `synthesize_response()` — Responder for personality synthesis (cloud-only)
  - CHAT optimization: skips post-inference roles when intent is CHAT + confidence > 0.8
  - `_call_role_cloud()` — direct `_call_cloud()` bypassing router
  - `_call_role_slm()` — direct `_call_ollama()` with `qwen2.5:0.5b`
  - `get_council_manager()` singleton factory
- `hestia/config/inference.yaml` — Added `council:` section with per-role config
- 55 new tests, 114 total council tests

**Session 3 — Handler integration:**
- `hestia/orchestration/handler.py` — 3 new integration points:
  - Step 6.5: Council pre-inference (intent classification → `task.context["intent"]`)
  - Step 7.5: Council post-inference (Analyzer + Validator → `task.context["council"]`)
  - Step 8.5: Response synthesis (Responder → personality-formatted tool results)
  - `_execute_council_tools()` — executes pre-parsed tool calls from Analyzer
  - Fallback: every council call wrapped in try/except, existing pipeline runs if council fails
- 10 new integration tests, 124 total council tests

**Session 4 — Review + documentation:**
- Reviewer: 0 P0, 2 P1 (both fixed), 6 P2 (noted)
- P1 fix: sanitized 5 raw `{e}` in handler.py error logs
- P1 fix: added justifying comments for private method access in manager.py
- Updated CLAUDE.md: project structure, test counts, workstream status, session log

*Files Created:* 5 (council/__init__.py, models.py, roles.py, prompts.py, manager.py)
*Files Modified:* 4 (handler.py, inference.yaml, structured_logger.py, test_council.py)
*Test Results:* 731 passed, 3 skipped, 0 failed

**Design Decisions:**
- Cloud calls: Direct `_call_cloud()` (bypasses router for guaranteed cloud execution)
- Default state: Enabled (fast SLM classification is valuable even locally)
- SLM model: `qwen2.5:0.5b` (394MB, ~100ms inference)
- Council is purely additive: never blocks main pipeline

**Next Steps:**
1. Deploy to Mac Mini with `scripts/deploy-to-mini.sh`
2. Pull `qwen2.5:0.5b` on Mac Mini: `ollama pull qwen2.5:0.5b`
3. Verify SLM intent classification works locally
4. UI Phase 2 (test production quality first)

---

## CURRENT ENHANCEMENT ROADMAP (2026-02-08)

Phase 6 is essentially complete. Now working through UI enhancements + 4 intelligence workstreams:

### Intelligence Workstreams (Active)

| Workstream | Status | Scope |
|-----------|--------|-------|
| WS4: Temporal Decay | ✅ COMPLETE | Per-chunk-type decay in memory search |
| WS1: Cloud LLM | ✅ COMPLETE | 3-state cloud routing, 3 providers, 7 endpoints, iOS Settings UI, deployed |
| WS2: Voice Journaling | ✅ COMPLETE | SpeechAnalyzer + quality gate + journal analysis + iOS voice UI |
| WS3: Council + SLM | COMPLETE | 4-role council, dual-path execution, handler integration |

Full plan: `.claude/plans/hidden-sauteeing-gray.md`

### UI Enhancement Phases

### Phase 1: Critical Bug Fixes ✅ COMPLETE

| Bug | Status | Files |
|-----|--------|-------|
| Face ID lock state stuck | ✅ FIXED | `LockScreenView.swift` |
| Apple Notes -1728 error | ✅ FIXED | `main.swift` (notes CLI) |
| Tool call JSON in chat | ✅ FIXED | `handler.py`, `MessageBubble.swift` |

**Deployment Note:** Notes CLI must be rebuilt on Mac Mini:
```bash
cd ~/hestia/hestia-cli-tools/hestia-notes-cli
swift build -c release
cp .build/release/hestia-notes-cli ~/.hestia/bin/
```

### Phase 2: UI Quick Wins (NEXT)

| Task | File | Time |
|------|------|------|
| Remove byline from chat | `ChatView.swift` | 15 min |
| Remove "Default Mode" setting | `SettingsView.swift` | 30 min |
| Move Memory to Command Center | Multiple | 1 hour |

### Phase 3: Lottie Animations

| Task | Description |
|------|-------------|
| Add lottie-ios package | SPM dependency |
| Replace loading spinner | Lottie animation during inference |
| Snarky loading bylines | Rotating messages every 2-3 seconds |

**Sample bylines:** "Consulting the oracle...", "Teaching hamsters to run faster...", "Brewing digital coffee..."

### Phase 4: Settings Integrations Section

New Settings section showing all available integrations:
- Calendar, Reminders, Notes, Mail (current)
- Weather, Stocks (API-based)
- Future MCP resources (extensible)

### Phase 5: Neural Net Graph

Force-directed graph visualization using Grape library:
- Shows memory tags as nodes
- Conversation clusters as connections
- Lives in Command Center as new tab

---

## Quick Commands

```bash
# Start API server
source .venv/bin/activate
python -m hestia.api.server

# Run tests
python -m pytest tests/ -v

# Test API
./scripts/test-api.sh

# Deploy to Mac Mini
./scripts/deploy-to-mini.sh

# Hook scripts (run manually or triggered by hooks)
./scripts/validate-security-edit.sh <file_path>
./scripts/auto-test.sh <file_path>
```

---

## Claude Code Infrastructure

### Sub-Agents (`.claude/agents/`)

| Agent | File | Model | Tools | Purpose |
|-------|------|-------|-------|---------|
| hestia-tester | `hestia-tester.md` | Sonnet | Bash, Read, Grep, Glob | Run tests, diagnose failures |
| hestia-reviewer | `hestia-reviewer.md` | Sonnet | Read, Grep, Glob, Bash | Code review (read-only) |
| hestia-explorer | `hestia-explorer.md` | Haiku | Read, Grep, Glob | Codebase navigation (read-only) |
| hestia-deployer | `hestia-deployer.md` | Sonnet | Bash, Read, Grep, Glob | Deployment to Mac Mini |

All sub-agents are **read-only** (no Write/Edit) except through their specific Bash permissions (tester runs pytest, deployer runs deploy scripts).

### Output Style (`.claude/output-styles/`)

- **Hestia Development** (`hestia-development.md`): Enforces Python conventions, API patterns, Swift/iOS standards, 4-phase workflow, and sub-agent usage. Set `keep-coding-instructions: true` to preserve Claude's built-in coding system prompt.

### Hook Scripts (`scripts/`)

- `validate-security-edit.sh`: Pre-edit validation for security-critical files. Warns on hardcoded credentials, wildcard CORS, bare excepts. Non-blocking (warns, doesn't prevent).
- `auto-test.sh`: Post-edit test runner. Maps Python source modules to their test files and runs the relevant tests automatically.

### Plugins (Install via Claude Code CLI)

See `PLUGIN-INSTALL-GUIDE.md` for installation instructions:
1. **pyright-lsp** — Real-time Python type checking
2. **github** — GitHub integration (issues, PRs, branches)
3. **commit-commands** — Standardized git workflows
4. **pr-review-toolkit** — Structured PR review
