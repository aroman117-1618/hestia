# Phase 6 Gap Analysis & Enhancement Roadmap

**Status**: Phase 6b COMPLETE - Moving to Enhancement Phases
**Last Updated**: 2026-01-17
**Last Review**: Staff Engineering Audit (2026-01-17)

This document tracks Phase 6 completion and the 5-phase enhancement roadmap.

---

## Enhancement Roadmap (Post Phase 6)

### Phase 1: Critical Bug Fixes ✅ COMPLETE (2026-01-17)

| Bug | Root Cause | Fix | Status |
|-----|-----------|-----|--------|
| Face ID lock state | LockScreenView used isolated AuthViewModel | Use @EnvironmentObject for shared AuthService | ✅ FIXED |
| Apple Notes -1728 error | AppleScript container property fails on global notes | Iterate through folders to access notes | ✅ FIXED |
| Tool call JSON display | Failed tool_call JSON passed to UI | Backend fallback + iOS "Working on that..." UI | ✅ FIXED |

**Files Modified:**
- `HestiaApp/Shared/Views/Auth/LockScreenView.swift`
- `hestia-cli-tools/hestia-notes-cli/Sources/hestia-notes-cli/main.swift`
- `hestia/orchestration/handler.py`
- `HestiaApp/Shared/Views/Chat/Components/MessageBubble.swift`

### Phase 2: UI Quick Wins (NEXT)

| Change | Location | Effort |
|--------|----------|--------|
| Remove byline from chat | ChatView.swift | 15 min |
| Change CTA to "Authenticate" | LockScreenView.swift | ✅ DONE |
| Remove "Default Mode" setting | SettingsView.swift | 30 min |
| Move Memory to Command Center | CommandCenterView.swift, SettingsView.swift | 1 hour |

### Phase 3: Lottie Animations + Loading Bylines

| Feature | Description | Priority |
|---------|-------------|----------|
| Lottie integration | Add lottie-ios package | HIGH |
| Loading animations | Replace spinner with Lottie during inference | HIGH |
| Snarky loading bylines | Random rotating messages (2-3s each) | MEDIUM |

**Sample Bylines:**
- "Consulting the oracle..."
- "Summoning the wisdom of the ancients..."
- "Brewing some digital coffee..."
- "Teaching hamsters to run faster..."
- "Convincing the AI it's not a Monday..."

### Phase 4: Settings Integrations Section

| Integration | Type | Status |
|-------------|------|--------|
| Calendar | Native EventKit | Available |
| Reminders | Native EventKit | Available |
| Apple Notes | AppleScript CLI | Available |
| Apple Mail | SQLite reader | Available |
| Weather | API | Available |
| Stocks | API | Planned |
| Future MCP Resources | Extensible | Planned |

### Phase 5: Neural Net Graph Visualization

| Component | Technology | Status |
|-----------|------------|--------|
| Graph library | Grape (Swift) | Research |
| Data source | Memory tags + conversation clusters | Design |
| Visualization | Force-directed graph | Design |
| Location | Command Center tab | Planned |

---

---

## Summary

| Category | Completeness | Status |
|----------|-------------|--------|
| Inference Layer | 100% | Complete (Qwen 2.5 7B) |
| Memory Layer | 100% | Complete |
| Orchestration | 100% | Complete |
| Background Tasks | 100% | Phase 4.5 COMPLETE (6 endpoints, 60 tests) |
| Execution Layer | 100% | Complete |
| Apple Integration | 100% | Complete |
| **REST API** | **100%** | **Complete (24 endpoints: 18 core + 6 tasks)** |
| **Authentication** | **100%** | **Complete (JWT tokens)** |
| **Native App** | **85%** | **Built, needs entitlements fix (Phase 6b)** |
| **iOS Entitlements** | **100%** | **FIXED - Calendar and Reminders keys added** |
| iOS Shortcuts | 0% | v1.0 scope, not started |
| WebSocket/Streaming | 0% | Deferred to v1.5 |
| Push Notifications | 0% | Deferred to v1.5 |
| Rate Limiting | 0% | Non-blocking |

**Phase 6 Infrastructure Completeness: ~90%**

The Python backend (core), REST API (24 endpoints), and native SwiftUI app are built. Remaining work:
- **Phase 6b**: Critical entitlements fix + App polish
- **Phase 6c**: iOS Shortcuts integration

---

## Summary

| Category | Completeness | Status |
|----------|-------------|--------|
| Inference Layer | 100% | Complete (Qwen 2.5 7B) |
| Memory Layer | 100% | Complete |
| Orchestration | 100% | Complete |
| Background Tasks | 100% | Phase 4.5 COMPLETE (6 endpoints, 60 tests) |
| Execution Layer | 100% | Complete |
| Apple Integration | 100% | Complete |
| **REST API** | **100%** | **Complete (47 endpoints)** |
| **Authentication** | **100%** | **Complete (JWT tokens)** |
| **Native App** | **95%** | **Built, Phase 1 bugs fixed** |
| **iOS Entitlements** | **100%** | **FIXED - Calendar and Reminders keys** |
| Enhancement Phase 1 | 100% | ✅ COMPLETE |
| Enhancement Phase 2 | 0% | NEXT |
| Enhancement Phase 3 | 0% | Planned |
| Enhancement Phase 4 | 0% | Planned |
| Enhancement Phase 5 | 0% | Planned |

**Phase 6 Infrastructure Completeness: ~95%**

---

## CRITICAL: iOS Entitlements Issue (2026-01-13)

**Status**: RESOLVED (2026-01-17) - Entitlements file updated with both Calendar and Reminders capabilities.

### Why CLI Works But Simulator Doesn't

| Component | EventKit Store | Result |
|-----------|---------------|--------|
| Mac CLI tools (`hestia-calendar-cli`) | macOS system store | Works - accesses real iCloud calendars |
| iOS Simulator | Isolated sandbox store | Fails - empty database + no entitlements |
| Physical iOS device | Device iCloud store | Will work with proper entitlements |

The Simulator has its own completely separate EventKit database. Even with proper entitlements, it will return empty results unless test events are manually added in the Simulator's Calendar app.

### Required Fix

1. **Create entitlements file**: `HestiaApp/iOS/HestiaApp.entitlements`
2. **Add to Xcode**: Target → Signing & Capabilities → + Capability → Calendars, Reminders
3. **Update Info.plist for iOS 17+**:
   - Add `NSCalendarsFullAccessUsageDescription`
   - Add `NSRemindersFullAccessUsageDescription`
4. **Clean build**: Cmd+Shift+K, then rebuild
5. **Test on physical device** for real calendar data

---

## Phase 6a: Completed Work

### REST API Implementation

**Status**: COMPLETE

**Files created:**
```
hestia/api/
├── __init__.py              # Package exports
├── server.py                # FastAPI app, lifecycle, CORS
├── schemas.py               # Pydantic request/response models
├── middleware/
│   ├── __init__.py
│   └── auth.py              # JWT device token authentication
└── routes/
    ├── __init__.py
    ├── auth.py              # POST /v1/auth/register
    ├── health.py            # GET /v1/health, /v1/ping
    ├── chat.py              # POST /v1/chat
    ├── mode.py              # GET/POST /v1/mode/*
    ├── memory.py            # GET/POST /v1/memory/*
    ├── sessions.py          # POST/GET/DELETE /v1/sessions/*
    └── tools.py             # GET /v1/tools/*
```

**24 Implemented Endpoints (18 core + 6 task management):**
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | /v1/ping | No | Connectivity check |
| GET | /v1/health | No | System health status |
| POST | /v1/auth/register | No | Register device, get JWT |
| POST | /v1/chat | Yes | Send message to Hestia |
| GET | /v1/mode | Yes | Get current mode |
| POST | /v1/mode/switch | Yes | Switch persona mode |
| GET | /v1/mode/{mode} | Yes | Get mode details |
| GET | /v1/memory/staged | Yes | List pending reviews |
| POST | /v1/memory/approve/{id} | Yes | Approve staged memory |
| POST | /v1/memory/reject/{id} | Yes | Reject staged memory |
| GET | /v1/memory/search | Yes | Semantic search |
| POST | /v1/sessions | Yes | Create session |
| GET | /v1/sessions/{id}/history | Yes | Get conversation |
| DELETE | /v1/sessions/{id} | Yes | End session |
| GET | /v1/tools | Yes | List available tools |
| GET | /v1/tools/categories | Yes | List tool categories |
| GET | /v1/tools/{name} | Yes | Get tool details |

**Dependencies added:**
- fastapi>=0.104.0
- uvicorn[standard]>=0.24.0
- python-jose[cryptography]>=3.3.0

**Test script:** `scripts/test-api.sh`

---

## Remaining Gaps

### Gap 1: Native iOS/macOS App (Phase 6b - MOSTLY COMPLETE)

**Status**: BUILT - Needs Polish

**What's done:**
- SwiftUI app with 43+ Swift files
- Design system (Colors, Typography, Spacing, Animations)
- HestiaClient networking layer (MockClient + APIClient)
- Chat UI with message bubbles and typewriter effect
- Mode indicator and switcher with ripple transitions
- Mode switching via @mentions (@tia, @mira, @olly)
- Memory review workflow (view, approve, reject)
- Settings screens with agent customization
- Face ID integration (skipped in simulator)
- Custom profile images for Tia and Olly

**What needs fixing (NEXT SESSION - Priority Order):**

1. **CRITICAL: Missing Entitlements File** - Blocks all EventKit functionality
   - Create `HestiaApp/iOS/HestiaApp.entitlements`
   - Add Calendar and Reminders capabilities in Xcode
   - See "CRITICAL: iOS Entitlements Issue" section above

2. **HIGH: iOS 17+ API Migration** - Current Info.plist has legacy keys only
   - Add `NSCalendarsFullAccessUsageDescription` (iOS 17+ requires this)
   - Add `NSRemindersFullAccessUsageDescription` (iOS 17+ requires this)
   - Current keys (`NSCalendarsUsageDescription`, `NSRemindersUsageDescription`) are iOS 16 only

3. **MEDIUM: No RemindersService in iOS App** - Backend has full support, iOS app doesn't
   - Create `RemindersService.swift` mirroring `CalendarService.swift` pattern
   - Wire up to CommandCenter for task display

4. **LOW: Color scheme persistence** - Mode gradient colors only show in ChatView
   - Pass currentMode to CommandCenterView and SettingsView
   - Update backgrounds to use mode-specific gradients

5. **LOW: Scrolling issue** - ScrollView not working in local build
   - Needs investigation on physical device vs simulator

**Reference:** `docs/ui-requirements.md`, `docs/ui-data-models.md`

---

### Gap 2: No WebSocket/Streaming

**Status**: DEFERRED to v1.5

The inference client supports streaming internally, but there's no HTTP streaming exposure. This is acceptable for v1.0 - responses are fast enough with local models that streaming isn't critical.

---

### Gap 3: No Push Notifications

**Status**: DEFERRED to v1.5

Would require:
- Apple Push Notification Service (APNS) setup
- Device token registration
- Background task to trigger notifications

Use cases:
- Memory review requests
- Calendar event reminders
- Proactive intelligence alerts (v1.5+)

---

### Gap 4: No Rate Limiting

**Status**: NOT IMPLEMENTED (non-blocking)

Should add for production:
- Per-device rate limits
- Per-endpoint limits
- 429 response handling

Libraries: `slowapi` or custom Redis-based

---

### Gap 5: No Request Logging Middleware

**Status**: PARTIAL

**What exists:**
- `HestiaLogger` with structured JSON logging
- `AuditLogger` for credential access
- Inference metrics logged per request

**What's missing:**
- Dedicated API request logging middleware
- Usage analytics (requests per device, popular modes, etc.)
- Dashboard/viewer for API metrics

---

## Security Gaps (Non-Blocking for MVP)

### Gap S1: Face ID Not Enforced Server-Side

**Status**: CLIENT-SIDE ONLY (by design)

Face ID is a client-side authentication mechanism. Current design:
- Client triggers Face ID before sensitive operations
- Server trusts client assertion via JWT token

**Mitigation**: Tailscale provides network-level authentication.

---

### Gap S2: Session Auto-Lock

**Status**: NOT IMPLEMENTED

Auto-lock timeout is documented as a feature, but:
- Server doesn't track session activity for timeouts
- No session expiration mechanism beyond JWT expiry

**Fix**: Add `last_activity` tracking to sessions with TTL enforcement.

---

## Recommended Next Steps

### Phase 6b: Polish (NEXT SESSION)

1. **Fix Color Scheme Persistence** (~1 hour)
   - Pass currentMode to CommandCenterView and SettingsView
   - Update backgrounds to use mode-specific gradients
   - Ensure mode changes propagate across all views

2. **Fix Scrolling Issues** (~1-2 hours)
   - Investigate ScrollView in ChatView message list
   - Check Settings/MemoryReview list scrolling
   - May need `.scrollContentBackground(.hidden)` or frame constraints
   - Test on physical device vs simulator

3. **Connect to Real API** (~2 hours)
   - Replace MockHestiaClient with APIClient in production
   - Test device registration flow
   - Verify JWT token storage in Keychain

### Phase 6c: Integration Testing

4. **End-to-End Testing**
   - Start API server on Mac Mini
   - Connect iOS app via Tailscale
   - Test full chat flow with Qwen 2.5 7B

5. Rate limiting
6. Request logging middleware

### Phase 6c: iOS Shortcuts (v1.0)

7. **iOS Shortcut Integration**
   - QuickCaptureIntent.swift for Shortcuts app
   - Fire-and-forget input via `/v1/tasks` endpoint
   - Immediate "Got it" confirmation
   - Links to Activity Timeline for results

8. **Activity Timeline View**
   - List background tasks with status indicators
   - Approve/cancel/retry actions
   - Pull to refresh

### Phase 6d: Enhancements (v1.5)

9. WebSocket streaming
10. Push notifications (APNs)

---

## Closed Gaps (Completed in Phase 6a/6b)

The following gaps from the original analysis have been resolved:

**Phase 6a (REST API):**
- **Gap 1: No FastAPI Server** - RESOLVED: Full server with CORS, lifecycle, error handling
- **Gap 2: No Authentication System** - RESOLVED: JWT device tokens with middleware
- **Gap 3: No Session Persistence Endpoint** - RESOLVED: Sessions API with history retrieval
- **Gap 4: Memory Review Workflow Incomplete** - RESOLVED: Stage/approve/reject endpoints
- **Gap 5: Tool Approval Flow** - PARTIALLY RESOLVED: Tool listing available, approval flow deferred

**Phase 6b (Native App):**
- **SwiftUI App Skeleton** - RESOLVED: 43+ Swift files, full app structure
- **HestiaClient Networking** - RESOLVED: MockClient + APIClient with async/await
- **Chat UI** - RESOLVED: Message bubbles, typewriter effect, mode indicators
- **Mode Switcher** - RESOLVED: Via menu + @mention invocation with ripple transitions
- **Memory Review UI** - RESOLVED: Pending list with approve/reject actions
- **Settings/Customization** - RESOLVED: Agent customization, Face ID settings
- **Face ID Integration** - RESOLVED: AuthService with simulator bypass for dev

---

## Quick Start for Phase 6b

The API is ready. To start building the native app:

```bash
# Start the API server
cd /path/to/hestia
source .venv/bin/activate
python -m hestia.api.server

# Test connectivity
curl http://localhost:8443/v1/ping

# Register a device
curl -X POST http://localhost:8443/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"device_name": "dev-mac", "device_type": "macos"}'

# Use returned token for authenticated requests
curl http://localhost:8443/v1/mode \
  -H "X-Hestia-Device-Token: <token>"
```

**API Documentation**: http://localhost:8443/docs
