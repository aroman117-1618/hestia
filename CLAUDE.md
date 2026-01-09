# CLAUDE.md - Hestia Project Context

This file provides Claude with persistent context about the Hestia project.

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
- **API**: REST on port 8443 with JWT authentication (47 endpoints)
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
- **Logging**: Every significant operation logged with request ID
- **Config**: YAML files, never hardcode

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
├── hestia/                          # Python package (v0.1.0)
│   ├── __init__.py
│   ├── security/
│   │   ├── __init__.py
│   │   └── credential_manager.py    # CredentialManager with Keychain + Fernet
│   ├── logging/
│   │   ├── __init__.py
│   │   ├── structured_logger.py     # HestiaLogger with JSON, sanitization
│   │   ├── audit_logger.py          # AuditLogger (7-year retention)
│   │   └── viewer.py                # CLI log viewer
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── client.py                # InferenceClient (Ollama, retry, streaming)
│   │   └── router.py                # Local model routing (Qwen 2.5 7B)
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── models.py                # ConversationChunk, ChunkTags, MemoryQuery
│   │   ├── database.py              # SQLite storage (async aiosqlite)
│   │   ├── vector_store.py          # ChromaDB for semantic search
│   │   ├── tagger.py                # AutoTagger (LLM + heuristic)
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
│   ├── api/                         # REST API (Phase 6a - COMPLETE)
│   │   ├── __init__.py
│   │   ├── server.py                # FastAPI app with lifecycle management
│   │   ├── schemas.py               # Pydantic request/response models
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   └── auth.py              # JWT device token authentication
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── auth.py              # POST /v1/auth/register
│   │       ├── health.py            # GET /v1/health, /v1/ping
│   │       ├── chat.py              # POST /v1/chat
│   │       ├── mode.py              # GET/POST /v1/mode/*
│   │       ├── memory.py            # GET/POST /v1/memory/*
│   │       ├── sessions.py          # GET/POST/DELETE /v1/sessions/*
│   │       ├── tools.py             # GET /v1/tools/*
│   │       └── tasks.py             # Background task endpoints (Phase 4.5)
│   ├── tasks/                       # Background Task Management (Phase 4.5)
│   │   ├── __init__.py
│   │   ├── models.py                # BackgroundTask, TaskStatus, TaskSource
│   │   ├── database.py              # SQLite persistence (async aiosqlite)
│   │   └── manager.py               # TaskManager (lifecycle, approval workflow)
│   ├── persona/                     # Placeholder (not yet implemented)
│   └── config/
│       ├── __init__.py
│       ├── inference.yaml           # Inference configuration
│       └── execution.yaml           # Execution layer configuration
├── hestia-cli-tools/
│   ├── hestia-keychain-cli/         # Swift CLI for Secure Enclave
│   ├── hestia-calendar-cli/         # Swift CLI for Calendar (EventKit)
│   ├── hestia-reminders-cli/        # Swift CLI for Reminders (EventKit)
│   └── hestia-notes-cli/            # Swift CLI for Notes (AppleScript)
├── HestiaApp/                       # Native iOS/macOS SwiftUI app
│   ├── Shared/                      # Shared code (43 Swift files)
│   │   ├── App/                     # Entry point
│   │   ├── DesignSystem/            # Colors, Typography, Spacing
│   │   ├── Models/                  # Data models
│   │   ├── Services/                # API client, Auth, Network
│   │   ├── ViewModels/              # MVVM controllers
│   │   └── Views/                   # SwiftUI screens
│   └── iOS/                         # iOS-specific assets
├── data/                            # SQLite + ChromaDB storage
├── logs/                            # Application logs
├── docs/                            # Project documentation
│   └── archive/                     # Superseded documents
├── tests/
│   ├── test_inference.py            # 11 inference tests
│   ├── test_memory.py               # 33 memory tests
│   ├── test_orchestration.py        # 42 orchestration tests
│   ├── test_execution.py            # 47 execution tests
│   ├── test_apple.py                # 30 Apple integration tests
│   └── test_tasks.py                # 60 task management tests
├── scripts/
│   ├── deploy-to-mini.sh            # Deploy to Mac Mini
│   ├── sync-swift-tools.sh          # Build & sync CLI tools
│   ├── test-api.sh                  # API testing script
│   └── ollama-*.sh                  # Ollama management scripts
├── .venv/                           # Python 3.9 virtual environment
├── requirements.txt                 # 36 Python dependencies
├── pytest.ini                       # pytest configuration (600s timeout)
├── README.md
└── CLAUDE.md
```

---

## API Endpoints (Phase 6a)

The REST API runs on port 8443 with JWT device authentication.

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/ping | No | Connectivity check |
| GET | /v1/health | No | System health status |
| POST | /v1/auth/register | No | Register device, get JWT token |
| POST | /v1/chat | Yes | Send message to Hestia |
| GET | /v1/mode | Yes | Get current mode |
| POST | /v1/mode/switch | Yes | Switch persona mode |
| GET | /v1/memory/staged | Yes | List pending memory reviews |
| POST | /v1/memory/approve/{id} | Yes | Approve staged memory |
| POST | /v1/memory/reject/{id} | Yes | Reject staged memory |
| GET | /v1/memory/search | Yes | Semantic search |
| POST | /v1/sessions | Yes | Create session |
| GET | /v1/sessions/{id}/history | Yes | Get conversation history |
| GET | /v1/tools | Yes | List available tools |
| POST | /v1/tasks | Yes | Create background task |
| GET | /v1/tasks | Yes | List tasks (with filters) |
| GET | /v1/tasks/{id} | Yes | Get task details |
| POST | /v1/tasks/{id}/approve | Yes | Approve awaiting task |
| POST | /v1/tasks/{id}/cancel | Yes | Cancel task |
| POST | /v1/tasks/{id}/retry | Yes | Retry failed task |

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
| Inference | 11 | Passing (2 require Ollama) |
| Memory | 33 | Passing |
| Orchestration | 61 | Passing |
| Execution | 47 | Passing |
| Apple | 30 | Passing |
| Tasks | 60 | Passing |
| **Total** | **242** | **All passing** |

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
│   ├── ViewModels/ChatViewModel.swift, CommandCenterViewModel.swift, etc.
│   └── Views/Chat/, CommandCenter/, Settings/, etc.
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

## CURRENT ENHANCEMENT ROADMAP (2026-01-17)

Phase 6 is essentially complete. Now working through 5 enhancement phases:

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
```
