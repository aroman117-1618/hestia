# Hestia UI Requirements

**Status**: Phase 6b Complete + Enhancement Phases Active
**Last Updated**: 2026-01-17

This document defines concrete UI requirements based on what the backend actually provides.

---

## Enhancement Phase Requirements

### Phase 1: Bug Fixes ✅ COMPLETE

| Fix | Requirement | Status |
|-----|-------------|--------|
| Face ID unlock | Use shared AuthService via @EnvironmentObject | ✅ Done |
| Tool call display | Show "Working on that..." spinner instead of JSON | ✅ Done |
| CTA button text | Change from "Unlock" to "Authenticate" | ✅ Done |

### Phase 2: UI Quick Wins (NEXT)

| Change | Requirement | Status |
|--------|-------------|--------|
| Remove byline | Remove any byline/tagline from ChatView | Pending |
| Remove Default Mode | Remove default mode selector from Settings | Pending |
| Move Memory | Move Memory section from Settings to Command Center | Pending |

### Phase 3: Lottie Animations + Loading Bylines

| Requirement | Details | Status |
|-------------|---------|--------|
| Lottie package | Add `lottie-ios` via SPM | Pending |
| Loading animation | Replace ProgressView spinner with Lottie during inference | Pending |
| Snarky bylines | Rotate through messages every 2-3 seconds randomly | Pending |

**Loading Byline Examples:**
- "Consulting the oracle..."
- "Summoning the wisdom of the ancients..."
- "Brewing some digital coffee..."
- "Teaching hamsters to run faster..."
- "Convincing the AI it's not a Monday..."
- "Searching through the void..."
- "Asking the magic 8-ball..."

**Implementation:**
```swift
struct LoadingView: View {
    @State private var currentByline = 0
    let bylines = ["Consulting the oracle...", "Brewing digital coffee...", ...]

    var body: some View {
        VStack {
            LottieView(name: "loading-animation")
            Text(bylines[currentByline])
                .onReceive(Timer.publish(every: 2.5, on: .main, in: .common).autoconnect()) { _ in
                    currentByline = Int.random(in: 0..<bylines.count)
                }
        }
    }
}
```

### Phase 4: Settings Integrations Section

| Requirement | Details | Status |
|-------------|---------|--------|
| New Settings section | "Integrations" section in SettingsView | Pending |
| Integration list | Show all available integrations with status | Pending |
| Connection status | Green/gray indicator for each integration | Pending |

**Integrations to display:**
- Calendar (EventKit) - Native
- Reminders (EventKit) - Native
- Apple Notes (AppleScript) - Native
- Apple Mail (SQLite) - Native
- Weather API - Connected
- Stocks API - Planned
- MCP Resources - Extensible

### Phase 5: Neural Net Graph

| Requirement | Details | Status |
|-------------|---------|--------|
| Grape library | Add Swift Grape package for force-directed graphs | Pending |
| New Command Center tab | "Neural Net" tab alongside Orders/Alerts | Pending |
| Graph visualization | Memory tags as nodes, clusters as edges | Pending |
| Interactive | Tap nodes to see related memories | Pending |

---

---

## Overview

| Platform | Primary Use | Priority |
|----------|-------------|----------|
| iPhone | Chat interface, quick queries | P0 |
| iPad | Command center, research sessions | P1 |
| macOS | Mirrored from iPad, keyboard-first | P2 |

---

## iPhone App Requirements

### ChatView (Primary Screen)

#### Message Display

| Requirement | Source | Status |
|------------|--------|--------|
| Display user messages (right-aligned bubbles) | `Request.content` | Needed |
| Display assistant messages (left-aligned bubbles) | `Response.content` | Needed |
| Show message timestamp | `Response.timestamp` | Optional |
| Support markdown rendering | Response content may include markdown | Needed |
| Support code blocks with syntax highlighting | `ChunkMetadata.has_code` indicates code | Nice-to-have |
| Loading state during inference | Backend takes 1-5 seconds | Needed |
| Error state for failed requests | `Response.response_type == ERROR` | Needed |

#### Mode Indicator

| Requirement | Source | Status |
|------------|--------|--------|
| Show current mode (Tia/Mira/Olly) | `Response.mode` | Needed |
| Visual differentiation by mode | Mode-specific accent colors | Needed |
| Mode switch announcement | Detect mode change between messages | Nice-to-have |
| Tap to manually switch mode | `POST /v1/mode/switch` | P1 |

**Mode Colors (Suggested):**
- Tia: Blue (#007AFF) - calm, efficient
- Mira: Purple (#AF52DE) - learning, curious
- Olly: Orange (#FF9500) - focused, action

#### Input Area

| Requirement | Source | Status |
|------------|--------|--------|
| Text input field | `Request.content` | Needed |
| Send button | Triggers API call | Needed |
| Mode invocation shortcuts (@tia, @mira, @olly) | Handled by backend | Backend handles |
| Voice input (iOS native) | Converts to text | Nice-to-have |
| Character limit indicator | 32K char limit | Nice-to-have |

#### Session Management

| Requirement | Source | Status |
|------------|--------|--------|
| Auto-create session on app launch | Generate `session_id` | Needed |
| Maintain session across app backgrounding | Store session_id | Needed |
| New conversation button | Generate new `session_id` | Needed |
| Session history access | `GET /v1/sessions/{id}/history` | P1 |

---

### Memory Review Screen (ADR-002)

| Requirement | Source | Status |
|------------|--------|--------|
| List pending memory updates | `GET /v1/memory/staged` | Needed |
| Show chunk content | `ConversationChunk.content` | Needed |
| Show confidence score | `ChunkMetadata.confidence` | Needed |
| Show related tags | `ChunkTags.topics`, `.entities` | Nice-to-have |
| Approve button | `POST /v1/memory/approve/{id}` | Needed |
| Reject button | `POST /v1/memory/reject/{id}` | Needed |
| Optional reviewer notes | `reviewer_notes` field | Nice-to-have |
| Badge count on tab/icon | `pending.count` | Needed |

---

### Settings Screen

#### Authentication

| Requirement | Source | Status |
|------------|--------|--------|
| Face ID toggle | Client-side enforcement | Needed |
| Auto-lock timeout (15/30/60 min) | Client-side enforcement | Needed |
| Device registration status | From auth system | P1 |

#### Mode Preferences

| Requirement | Source | Status |
|------------|--------|--------|
| ~~Default mode selection~~ | ~~Local preference~~ | **REMOVED (Phase 2)** |
| View mode descriptions | `PersonaConfig.description` | Nice-to-have |
| View mode traits | `PersonaConfig.traits` | Nice-to-have |

**Note:** Default Mode setting removed in Phase 2 UI cleanup. Mode is determined by conversation context or @mention.

#### System Status

| Requirement | Source | Status |
|------------|--------|--------|
| Backend health indicator | `GET /v1/health` | Needed |
| Local model status | `health.components.inference.local` | Needed |
| Cloud fallback status | `health.components.inference.cloud` | Nice-to-have |
| Memory vector count | `health.components.memory.vector_count` | Nice-to-have |

---

## iPad App Requirements

### Command Center Layout

Split-view design with:
- **Primary pane (60%)**: Chat interface (same as iPhone)
- **Secondary pane (40%)**: Contextual widgets

### Widget Requirements

#### Recent Conversations Widget

| Requirement | Source | Status |
|------------|--------|--------|
| List recent sessions | Session list from memory | P1 |
| Show session summary/preview | First message preview | P1 |
| Tap to resume session | Load session into chat | P1 |

#### Pending Actions Widget

| Requirement | Source | Status |
|------------|--------|--------|
| List pending memory reviews | `GET /v1/memory/staged` count | Needed |
| List action items | `MemoryManager.get_action_items()` | P1 |
| Quick approve/dismiss | Inline actions | Nice-to-have |

#### Today's Schedule Widget (Apple Integration)

| Requirement | Source | Status |
|------------|--------|--------|
| Show today's calendar events | `get_today_events` tool | Needed |
| Show due reminders | `get_due_reminders` tool | Needed |
| Show overdue reminders (alert) | `get_overdue_reminders` tool | Nice-to-have |
| Unread email count | `get_unread_count` tool | Nice-to-have |

#### System Status Widget

| Requirement | Source | Status |
|------------|--------|--------|
| Health indicator (green/yellow/red) | `GET /v1/health` status | Needed |
| Active mode display | Current mode | Needed |
| Last response time | `Response.duration_ms` | Nice-to-have |

---

## Activity Timeline (v1.0)

### Background Task Display

| Requirement | Source | Status |
|------------|--------|--------|
| List all background tasks | `GET /v1/tasks` | Needed |
| Show task status indicator | `TaskStatus` enum | Needed |
| Expandable task details | `outputDetails` field | Needed |
| Approve button for escalated | `POST /v1/tasks/{id}/approve` | Needed |
| Cancel button for pending | `POST /v1/tasks/{id}/cancel` | Needed |
| Retry button for failed | `POST /v1/tasks/{id}/retry` | Needed |
| Filter by status | Query parameter | Nice-to-have |
| Pull to refresh | Standard iOS pattern | Needed |
| Task source indicator | `TaskSource` enum | Nice-to-have |

### Task Status Visual Indicators

| Status | Icon | Color |
|--------|------|-------|
| pending | Clock | Gray |
| in_progress | Spinner | Blue |
| completed | Checkmark | Green |
| failed | X circle | Red |
| awaiting_approval | Exclamation | Orange |
| cancelled | Slash circle | Gray |

---

## macOS App Requirements

### Menu Bar Quick Access

| Requirement | Source | Status |
|------------|--------|--------|
| Menu bar icon | Always accessible | P2 |
| Click to show/hide chat popover | Quick access pattern | P2 |
| Keyboard shortcut (⌘⇧H) | System-wide shortcut | P2 |

### Main Window

Mirror iPad interface with:
- Keyboard navigation support
- ⌘+Enter to send
- ⌘+1/2/3 for mode switching

---

## Cross-Platform Requirements

### Data Synchronization

| Requirement | Notes | Status |
|------------|-------|--------|
| Session continuity | Same session_id works across devices | Backend handles |
| Memory access | All devices see same memory | Backend handles |
| Settings sync | Via iCloud or backend | Future |

### Offline Behavior

| Requirement | Notes | Status |
|------------|-------|--------|
| Graceful offline handling | Show error, queue messages | Needed |
| Cached conversation display | Show last known state | Nice-to-have |
| Offline indicator | Visual cue | Needed |

### Accessibility

| Requirement | Notes | Status |
|------------|-------|--------|
| VoiceOver support | All UI elements labeled | Needed |
| Dynamic Type | Respect system font size | Needed |
| High contrast mode | Support increased contrast | Nice-to-have |
| Reduce Motion | Honor system preference | Needed |

---

## State Management

### App State Model

```swift
@Observable
class HestiaAppState {
    // Session
    var currentSessionId: String?
    var messages: [ConversationMessage] = []
    var isLoading: Bool = false

    // Mode
    var currentMode: HestiaMode = .tia

    // Memory
    var pendingReviewCount: Int = 0

    // System
    var systemHealth: SystemHealth?
    var isAuthenticated: Bool = false
}
```

### Network State

```swift
enum NetworkState {
    case idle
    case loading
    case success
    case error(HestiaError)
}

struct HestiaError: Error {
    let code: String
    let message: String
}
```

---

## Authentication Flow

### Initial Launch

```
1. Check for stored device token
   ↓ (none found)
2. Show registration screen
   ↓
3. User triggers Face ID
   ↓
4. POST /v1/auth/register (with device info)
   ↓
5. Store device token in Keychain
   ↓
6. Navigate to ChatView
```

### Subsequent Launches

```
1. Check for stored device token
   ↓ (found)
2. Check auto-lock timeout
   ↓ (expired)
3. Trigger Face ID
   ↓ (success)
4. Validate token with backend
   ↓
5. Navigate to ChatView
```

### Session Timeout

```
1. App enters foreground
   ↓
2. Check last_activity timestamp
   ↓ (> timeout threshold)
3. Show lock screen
   ↓
4. Require Face ID
```

---

## Error Handling Requirements

### User-Facing Errors

| Error Code | UI Message | Action |
|-----------|------------|--------|
| `validation_error` | "I couldn't understand that. Please try rephrasing." | Clear input |
| `timeout` | "That took too long. Please try again." | Retry button |
| `model_unavailable` | "I'm having trouble connecting. Is the server running?" | Retry/Settings |
| `rate_limited` | "Slow down! Try again in a moment." | Show countdown |
| `unauthorized` | "Please re-authenticate." | Trigger auth flow |

### Network Errors

| Condition | UI Behavior |
|-----------|-------------|
| No connection | Banner: "No connection" + cached messages |
| Timeout | Inline error with retry |
| Server error (5xx) | Banner: "Server issue" + retry later |

---

## Performance Requirements

| Metric | Target | Notes |
|--------|--------|-------|
| App launch to usable | < 2 seconds | Cold start |
| Message send to response start | < 500ms | Network only |
| Message list scroll | 60 FPS | Large conversations |
| Memory usage (iPhone) | < 100MB | Base memory |

---

## Feature Priority Matrix

### P0 (MVP - v1.0)

Must have for initial release:

- [ ] Chat view with message display
- [ ] Send message functionality
- [ ] Mode indicator
- [ ] Loading states
- [ ] Error handling
- [ ] Face ID authentication
- [ ] Auto-lock timeout
- [ ] Activity Timeline view
- [ ] Task status indicators
- [ ] Approve/cancel/retry actions

### P1 (Fast Follow - v1.0)

Should have for v1.0:

- [ ] Memory review screen
- [ ] Settings screen
- [ ] Health status indicator
- [ ] Session management
- [ ] iPad split view
- [ ] iOS Shortcuts integration (QuickCaptureIntent)

### P2 (Future - v1.5)

Nice to have:

- [ ] macOS app
- [ ] Menu bar quick access
- [ ] Push notifications (APNs)
- [ ] Voice input
- [ ] Code syntax highlighting
- [ ] Widget extensions

---

## Design Tokens

### Colors

```swift
extension Color {
    // Mode colors
    static let tiaPrimary = Color(hex: "#007AFF")
    static let miraPrimary = Color(hex: "#AF52DE")
    static let ollyPrimary = Color(hex: "#FF9500")

    // Semantic colors
    static let userBubble = Color(hex: "#007AFF")
    static let assistantBubble = Color(.systemGray5)
    static let errorRed = Color(hex: "#FF3B30")
    static let successGreen = Color(hex: "#34C759")
}
```

### Typography

```swift
extension Font {
    static let messageBody = Font.body
    static let messageTimestamp = Font.caption2
    static let modeIndicator = Font.caption.weight(.semibold)
    static let sectionHeader = Font.headline
}
```

### Spacing

```swift
enum Spacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 16
    static let lg: CGFloat = 24
    static let xl: CGFloat = 32
}
```

---

## Testing Requirements

### Unit Tests

- [ ] Message model encoding/decoding
- [ ] Network client mock responses
- [ ] State management logic
- [ ] Auth token storage

### UI Tests

- [ ] Send message flow
- [ ] Mode switching
- [ ] Error state display
- [ ] Settings navigation

### Integration Tests

- [ ] Full chat flow with mock server
- [ ] Memory review flow
- [ ] Authentication flow

---

## Dependencies (Recommended)

```swift
// Package.swift or SPM dependencies

// Networking
.package(url: "https://github.com/Alamofire/Alamofire.git", from: "5.8.0"),

// Markdown rendering
.package(url: "https://github.com/gonzalezreal/swift-markdown-ui", from: "2.0.0"),

// Keychain
.package(url: "https://github.com/evgenyneu/keychain-swift.git", from: "20.0.0"),

// Code highlighting (optional)
.package(url: "https://github.com/raspu/Highlightr.git", from: "2.1.0"),
```

---

## What Can Be Built Now (Without API)

While the API is being built, start with:

1. **App shell and navigation** - Tab bar, screens, transitions
2. **Chat UI with mock data** - Message bubbles, input field, loading states
3. **Mode indicator and switching UI** - Visual components
4. **Settings screens** - Local preferences
5. **Design system** - Colors, typography, components
6. **Authentication flow** - Face ID, lock screen
7. **Mock network client** - Returns canned responses

```swift
// MockHestiaClient.swift
class MockHestiaClient: HestiaClientProtocol {
    func sendMessage(_ message: String, sessionId: String) async throws -> HestiaResponse {
        // Simulate network delay
        try await Task.sleep(nanoseconds: 1_000_000_000)

        return HestiaResponse(
            requestId: UUID().uuidString,
            content: "This is a mock response to: \(message)",
            responseType: .text,
            mode: "tia",
            timestamp: Date(),
            metrics: ResponseMetrics(tokensIn: 10, tokensOut: 20, durationMs: 1000)
        )
    }
}
```
