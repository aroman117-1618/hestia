# iOS Refresh — Design Specification

**Date:** 2026-03-24
**Status:** Draft
**Confidence:** High
**Approach:** Vertical slices — ship TestFlight pipeline first, then features end-to-end, extract shared components as patterns emerge.

---

## Overview

Refresh the Hestia iOS app from a minimal 2-tab companion (Chat + Settings) into a full mobile experience with three-mode voice input, a card-based Command dashboard, and a rebuilt Settings view. TestFlight distribution pipeline enables continuous delivery to Andrew's iPhone.

**Design Principles:**
- Apple-native design language (SF Symbols, iOS semantic colors, standard tab bar)
- Cards for viewing, Notion-style blocks for editing/managing
- Colors map to agents: Amber/Orange = Hestia (conversation), Teal = Artemis (analysis/transcript), Purple = Apollo (execution)
- View and critical actions only on Command — no deep editing on mobile
- Voice Journal architecture designed for multi-speaker transcription (future)

---

## WS0: TestFlight Distribution Pipeline

### Goal
Automated CI/CD pipeline: tag push → GitHub Actions → build + archive + sign → upload to TestFlight → auto-update on Andrew's iPhone.

### Prerequisites (Andrew's Manual Steps)
1. **App Store Connect** — Create app entry for bundle ID `com.andrewlonati.hestia`
2. **App Store Connect API Key** — Generate under Users & Access → Keys (Admin role). Download `.p8` file.
3. **GitHub Secret** — Add `APP_STORE_CONNECT_API_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, and `APP_STORE_CONNECT_KEY_BASE64` (base64-encoded `.p8` content)
4. **Privacy Policy URL** — Required for TestFlight uploads (can be a simple GitHub Pages page)

### Files to Create

**`HestiaApp/ExportOptions-iOS.plist`**
- `method: app-store` (required for TestFlight)
- `signingStyle: automatic`
- `teamID: 563968AM8L`
- `uploadSymbols: true` (crash reporting)

**`.github/workflows/release-ios.yml`**
Mirrors `release-macos.yml` structure:
1. Trigger: tag push `v*` OR manual dispatch with version input
2. Checkout + xcodegen generate
3. Resolve SPM dependencies
4. Archive: `xcodebuild archive -scheme HestiaApp -destination 'generic/platform=iOS' -archivePath build/HestiaApp.xcarchive`
5. Export: `xcodebuild -exportArchive -archivePath build/HestiaApp.xcarchive -exportOptionsPlist HestiaApp/ExportOptions-iOS.plist -exportPath build/export`
6. Upload: Use App Store Connect API via `xcrun notarytool` or `xcodebuild -allowProvisioningUpdates -exportArchive` with API key auth. Note: `xcrun altool` is deprecated as of Xcode 14; prefer the App Store Connect API directly.
7. Runs on: `[self-hosted, macos, hestia]` (Mac Mini, has Xcode + certs)

### Changes to Existing Files

**`.claude/skills/ship-it/SKILL.md`**
- Update to note that tag push now triggers both `release-macos.yml` and `release-ios.yml`
- Version bump is already shared (both targets use same `MARKETING_VERSION` and `CURRENT_PROJECT_VERSION` in `project.yml`)

### Acceptance Criteria
- [ ] `git tag v1.6.0 && git push --tags` triggers iOS build + upload to TestFlight
- [ ] Build appears in TestFlight within 15 minutes
- [ ] Andrew can install and open the app on his iPhone
- [ ] Auth flow works (QR code onboarding or existing device token)

### Estimated Effort: 3-4 hours
- ExportOptions plist: 15 min
- GitHub Actions workflow: 1-2 hours (writing + debugging)
- App Store Connect setup: 30 min (Andrew's steps)
- Testing + debugging upload: 1 hour

---

## WS1: Chat + Voice Modes

### Goal
Transform the Chat tab from text-only input into a three-mode interface: Chat (text), Voice Conversation (Hestia/amber), and Voice Journal (Artemis/teal). Each mode has distinct UX optimized for its purpose.

### Architecture: Three Input Modes

| Mode | Icon | Color | Purpose | Transcript Display | Send Behavior |
|------|------|-------|---------|-------------------|---------------|
| Chat | `bubble.left.fill` | System Blue (#0A84FF) | Text messaging | N/A | Tap send button |
| Voice | `mic.fill` | Amber (#FF9F0A) | Conversational back-and-forth | Live chat bubbles | Tap stop → auto-sends → Hestia responds |
| Journal | `book.fill` | Teal (#30D5C8) | Long-form transcription | Flowing prose (serif font) | Tap checkmark → submits to Artemis |

### Mode Toggle Design
- **Location:** Circular icon button, left of the text input field
- **Behavior:** Tap to cycle through modes (Chat → Voice → Journal → Chat)
- **Visual feedback:** Icon changes, input bar border tints to mode color, placeholder text updates
- **Long-press:** Opens a picker menu showing all three modes with labels (for discoverability)

### Input Bar States

**Chat Mode (default):**
```
[💬] [Message Hestia...                    ] [→]
 ^mode   ^text field                         ^send (blue)
```
- Mode icon: `bubble.left.fill` in blue circle
- Right button: Send arrow (appears when text field is non-empty)
- When text field is empty, right button is hidden or mic icon for quick voice

**Voice Conversation Mode:**
```
[🎤] [|||||||||| waveform ||||||||||] [■]
 ^mode  ^live waveform replaces text    ^stop (amber)
```
- Mode icon: `mic.fill` in amber circle
- Text field replaced by waveform visualization during recording
- Right button: Stop square (amber fill)
- Tap stop → transcript sent as user message → Hestia responds via normal chat streaming
- Header subtitle changes to "Listening..." with timer badge

**Voice Journal Mode:**
```
[📖] [|||||||||| waveform ||||||||||] [✓]
 ^mode  ^live waveform                  ^done (teal)
```
- Mode icon: `book.fill` in teal circle
- Right button: Checkmark (teal fill)
- Tap checkmark → journal entry submitted for Artemis analysis
- Header shows "Journal Entry" badge with timer

### Chat View Changes

**File: `HestiaApp/Shared/Views/Chat/ChatView.swift`**
Major refactor — extract input bar into a separate component, add mode state management.

**New: `HestiaApp/Shared/Views/Chat/ChatInputBar.swift`**
- Extracted input bar component
- `@Binding var inputMode: ChatInputMode`
- Mode icon button with cycle behavior + long-press picker
- Adaptive right button (send/stop/checkmark based on mode)
- Waveform visualization component (shown during Voice/Journal recording)

**New: `HestiaApp/Shared/Views/Chat/VoiceConversationView.swift`**
- Replaces the current `VoiceRecordingOverlay` full-screen approach
- Live transcript appears inline as tinted chat bubbles (amber background)
- Waveform indicator beside the latest transcript bubble
- No separate review step — transcript sends immediately on stop (quality check runs in background, flags issues post-send if needed)

**New: `HestiaApp/Shared/Views/Chat/VoiceJournalView.swift`**
- Full-screen journal experience (presented as a sheet or replaces chat content area)
- Serif font rendering (Georgia) for flowing prose
- Pause detection inserts paragraph breaks (visual divider + "pause detected" label)
- Optional journal prompt at top (from Hestia's proactive system or hardcoded starters)
- Checkmark submits entry

**New: `HestiaApp/Shared/Views/Chat/WaveformView.swift`**
- Reusable audio waveform visualization
- Accepts `audioLevel: CGFloat` binding (from SpeechService)
- Renders animated bars with mode-appropriate tint color
- Used in both VoiceConversation and VoiceJournal input bars

**Modified: `HestiaApp/Shared/Views/Chat/MessageBubble.swift`**
- New bubble style for voice transcript messages (tinted background matching mode color)
- Visual indicator that a message came from voice input (small mic or book icon in bubble)

### ViewModel Changes

**New: `HestiaApp/Shared/Models/ChatInputMode.swift`**
```swift
enum ChatInputMode: String, CaseIterable {
    case chat       // Text messaging
    case voice      // Voice conversation (Hestia/amber)
    case journal    // Voice journal/transcript (Artemis/teal)

    var icon: String {
        switch self {
        case .chat: return "bubble.left.fill"
        case .voice: return "mic.fill"
        case .journal: return "book.fill"
        }
    }

    var color: Color { ... }        // amber, teal, blue
    var placeholder: String { ... } // "Message...", "Tap to speak...", "Begin journal entry..."
    var agent: String { ... }       // "hestia", "hestia", "artemis"
}
```

**Modified: `HestiaApp/Shared/ViewModels/VoiceInputViewModel.swift`**
- Add `inputMode: ChatInputMode` property to distinguish conversation vs journal behavior
- Voice Conversation: `stopRecording()` → skip quality check → auto-send transcript
- Voice Journal: `stopRecording()` → present as flowing text → user taps checkmark → send with `context: { source: "journal" }` metadata
- Quality check becomes background/post-send (not blocking)

**Modified: `HestiaApp/Shared/ViewModels/ChatViewModel.swift`**
- `sendMessage()` accepts optional `metadata: [String: Any]` parameter
- Metadata includes `source: "voice"` or `source: "journal"` + `input_mode: "conversation"` or `input_mode: "journal"`
- Backend uses this metadata to route journal entries to Artemis for deeper analysis

### Thought Streaming (Visible Reasoning)

**Modified: `HestiaApp/Shared/ViewModels/ChatViewModel.swift`**
The backend already sends SSE events with stage metadata (`preparing`, `thinking`, `responding`, `tool_call`, `done`). Currently the stages are parsed but not displayed.

- Add `@Published var currentStage: String?` property
- Parse SSE `stage` field and update `currentStage`
- Display in ChatView as a faded italic bubble below the latest assistant message: "Checking memory...", "Routing to Artemis...", "Analyzing..."
- Stage bubble disappears when actual response text starts streaming

**New: `HestiaApp/Shared/Views/Chat/ThinkingIndicator.swift`**
- Subtle animated indicator showing current processing stage
- Faded bubble with italic text + subtle pulse animation
- Positioned below the last assistant message, above the input bar

### Voice Journal Architecture (Multi-Speaker Ready)

**Data Model (future-proof, built now):**
```swift
struct JournalEntry {
    let id: UUID
    let timestamp: Date
    let segments: [TranscriptSegment]
    let metadata: JournalMetadata
}

struct TranscriptSegment {
    let text: String
    let startTime: TimeInterval
    let endTime: TimeInterval
    let speakerId: String?      // nil for single-speaker (v1)
    let speakerLabel: String?   // nil for single-speaker (v1)
    let confidence: Float
    let isParagraphBreak: Bool
}

struct JournalMetadata {
    let inputMode: ChatInputMode     // .journal
    let duration: TimeInterval
    let speakerCount: Int            // 1 for v1
    let prompt: String?              // optional journal prompt
}
```

The `speakerId`/`speakerLabel` fields are nullable in v1 (single speaker). When multi-speaker diarization is added later, the same data model works — no migration needed. The `TranscriptSegment` array structure naturally supports interleaved speakers.

**Post-processing pipeline (extensible):**
- v1: Journal entry → send to chat as message with `source: "journal"` → Artemis analyzes via normal inference
- Future: Journal entry → `POST /v1/voice/process-journal` → pluggable processors (recap, insights, action items, speaker attribution)

### Backend Changes

**Modified: `hestia/api/routes/chat.py`**
- `ChatRequest` model: add optional `metadata: dict` field
- If `metadata.source == "journal"`, set `agent_hint: "artemis"` for the orchestrator
- Journal entries get special handling: stored with `source: "journal"` tag in memory for recall

**Modified: `hestia/orchestration/handler.py`**
- Respect `agent_hint` in request metadata to route journal entries to Artemis
- No forced override — just a hint that influences routing confidence

### Acceptance Criteria
- [ ] Mode toggle icon cycles Chat → Voice → Journal with tint color changes
- [ ] Long-press on mode icon shows picker menu
- [ ] Voice Conversation: tap mic → record → live transcript in amber bubbles → stop → auto-send → Hestia responds
- [ ] Voice Journal: tap mic → record → flowing prose in serif font → checkmark → submits to Artemis
- [ ] Thought streaming: "Checking memory...", "Routing to Artemis..." visible during processing
- [ ] Journal entries tagged with `source: "journal"` metadata in backend
- [ ] TranscriptSegment model includes nullable speaker fields

### Estimated Effort: 20-25 hours
- ChatInputBar extraction + mode toggle: 3-4h
- VoiceConversationView (inline recording): 4-5h
- VoiceJournalView (prose rendering + pause detection): 5-6h
- WaveformView component: 2h
- ViewModel changes (mode routing, metadata): 3-4h
- Thought streaming (stage display): 2-3h
- Backend changes (metadata, routing hint): 1-2h
- Testing on device: 2-3h

---

## WS2: Mobile Command Dashboard

### Goal
New Command tab with a card-based, view-focused dashboard showing system status, trading, active orders, and critical quick actions.

### Tab Structure
- Standard iOS large title navigation: "Command"
- Scrollable card stack (no sub-tabs on mobile — single scrollable view)
- Pull-to-refresh for all data

### Cards (top to bottom)

**1. Status Card**
- Compact system overview: bot count, 24h P&L, fill count
- Status badge: "All Systems Go" (green), "Degraded" (amber), "Offline" (red)
- Data source: `GET /health/status` + `GET /trading/summary`

**2. Trading Card**
- Bot list: pair name + strategy + P&L percentage
- Color-coded P&L (green positive, red negative)
- **Kill Switch** button (red pill, top-right of card) — critical action
- **Autonomous Trading** toggle — critical action
- Data source: `GET /trading/bots`, `GET /trading/risk/status`

**3. Orders Card**
- Active workflow list: name + status badge (Running/Scheduled/Failed)
- Status badges: green (Running), gray (Scheduled), red (Failed)
- Collapsed by default if >3 orders — "View all" expands
- Data source: `GET /workflows`

**4. Newsfeed Card**
- Latest 3-5 newsfeed items (title + source + relative time)
- Unread dot indicator
- "View all" link at bottom
- Data source: `GET /newsfeed/timeline?limit=5`

**5. Quick Actions Card**
- Tinted pill buttons for critical actions:
  - **Cloud Mode** (blue) — toggle disabled/smart/full
  - **Investigate** (teal) — opens URL input sheet, sends to `/investigate`
  - **Voice Journal** (amber) — switches to Chat tab in Journal mode
  - **Lock** (gray) — locks the app immediately
- Each pill is a single-tap action or opens a minimal sheet

### Files to Create

**`HestiaApp/Shared/Views/Command/MobileCommandView.swift`**
- Main scrollable card stack
- Pull-to-refresh
- `@StateObject var viewModel: MobileCommandViewModel`

**`HestiaApp/Shared/ViewModels/MobileCommandViewModel.swift`**
- `@Published` properties: systemStatus, tradingBots, tradingRisk, workflows, newsfeedItems
- `loadAll()` — parallel fetch via `async let` / `TaskGroup`
- CacheFetcher pattern (matching macOS) with TTLs:
  - Trading: 60s (frequent)
  - Workflows: 5min (standard)
  - Newsfeed: 5min (standard)
  - System health: 60s (frequent)

**`HestiaApp/Shared/Views/Command/StatusCard.swift`**
- Compact 3-column metric display (bots | P&L | fills)
- Status badge with color

**`HestiaApp/Shared/Views/Command/TradingCard.swift`**
- Bot list rows with P&L
- Kill Switch button (confirmation alert before executing)
- Autonomous trading toggle

**`HestiaApp/Shared/Views/Command/OrdersCard.swift`**
- Workflow list with status badges
- Collapsible beyond 3 items

**`HestiaApp/Shared/Views/Command/NewsfeedCard.swift`**
- Compact news item rows
- Unread indicator

**`HestiaApp/Shared/Views/Command/QuickActionsCard.swift`**
- Horizontal flow of tinted pill buttons
- Cloud Mode: cycles through states on tap, shows current state
- Investigate: presents sheet with URL text field
- Voice Journal: `tabSelection = .chat` + `inputMode = .journal`
- Lock: calls `authService.lock()`

### Files to Modify

**`HestiaApp/Shared/Views/MainTabView.swift`** (or equivalent root view)
- Add Command tab between Chat and Settings
- Tab icon: `square.grid.2x2.fill` (SF Symbol)
- Wire `MobileCommandView`

**`HestiaApp/project.yml`**
- Ensure new Command views are included in iOS target sources
- Update excludes list (remove `Views/CommandCenter/**` exclusion — we're creating NEW `Views/Command/` for mobile, distinct from macOS `Views/CommandCenter/`)

**`HestiaApp/Shared/Services/APIClient+Trading.swift`** (or create if doesn't exist in Shared)
- Ensure trading API methods are available on iOS (currently may be macOS-only)
- Methods needed: `getTradingBots()`, `getTradingRiskStatus()`, `getTradingSummary()`, `toggleKillSwitch()`, `toggleAutonomousTrading()`

### API Endpoints Used
| Endpoint | Card | Method |
|----------|------|--------|
| `GET /health/status` | Status | Read |
| `GET /trading/summary` | Status | Read |
| `GET /trading/bots` | Trading | Read |
| `GET /trading/risk/status` | Trading | Read |
| `POST /trading/kill-switch` | Trading | Action |
| `GET /workflows` | Orders | Read |
| `GET /newsfeed/timeline?limit=5` | Newsfeed | Read |
| `POST /v1/cloud/state` | Quick Actions | Action |
| `POST /investigate/url` | Quick Actions | Action |

### Acceptance Criteria
- [ ] Command tab appears as middle tab with `square.grid.2x2.fill` icon
- [ ] Pull-to-refresh reloads all cards
- [ ] Status card shows live bot count, P&L, fills with colored status badge
- [ ] Trading card shows all bots with P&L, Kill Switch button works (with confirmation)
- [ ] Orders card shows active workflows with status badges
- [ ] Quick Actions: Cloud Mode toggle, Investigate sheet, Journal mode switch, Lock all work
- [ ] Data refreshes automatically every 60s for trading, 5min for others

### Estimated Effort: 15-20 hours
- MobileCommandView + ViewModel: 3-4h
- StatusCard + TradingCard: 4-5h
- OrdersCard + NewsfeedCard: 3-4h
- QuickActionsCard + sheets: 3-4h
- API client wiring (Shared trading methods): 1-2h
- Tab integration + testing: 2-3h

---

## WS3: Settings Rebuild

### Goal
Replace the current 7-section grouped list with 4 focused Notion-style blocks: Profile, Agents, Resources, System.

### Block Architecture

**1. Profile Block**
- User avatar (photo or initials gradient), name, subtitle
- Taps into `UserProfileView` (existing, cleaned up)
- Subtitle: version + server status ("v1.6.0 · Server Online")

**2. Agents Block**
- Visual card showing all 3 agent slots (Tia/Mira/Olly)
- Each agent: avatar circle + name + role label + active indicator
- Taps into `AgentProfileView` (existing)
- Active agent highlighted with tinted background

**3. Resources Block**
- Unified section for everything Hestia connects to
- Sub-rows (inline, not separate navigation):
  - **Cloud LLMs** — Provider count + active state ("Full · Anthropic") → drills to `CloudSettingsView`
  - **Integrations** — Connected services count ("Calendar, Reminders, HealthKit") → drills to `IntegrationsView`
  - **Health** — HealthKit coaching preferences → drills to `HealthCoachingPreferencesView`
- Each sub-row: icon + label + summary + chevron

**4. System Block**
- Security: Face ID status + auto-lock timeout → drills to security detail
- Devices: registered device count → drills to `DeviceManagementView`
- Server: health status (inline, no drill-in needed)
- Version: build info (inline)
- **Danger Zone** (bottom, separated): Unregister Device (red, destructive)

### Notion Block Component

**New: `HestiaApp/Shared/DesignSystem/Components/HestiaSettingsBlock.swift`**
Reusable block component used by all 4 settings sections:
```swift
struct HestiaSettingsBlock<Content: View>: View {
    let icon: String           // SF Symbol name
    let iconColor: Color       // Tint color
    let title: String
    let subtitle: String?
    let content: Content?      // Optional expandable content (e.g., agent cards)
    let destination: AnyView?  // Optional navigation destination
}
```

Visual spec:
- Background: `#1C1C1E` (iOS `secondarySystemBackground`)
- Corner radius: 14px
- Border: 0.5px `#2C2C2E`
- Icon: 28x28 rounded square with 12% opacity tint background
- Title: 15px semibold white
- Subtitle: 12px `#8E8E93`
- Chevron: `chevron.right` in `#48484A` (when navigable)

### Files to Create

**`HestiaApp/Shared/Views/Settings/MobileSettingsView.swift`**
- Replaces current `SettingsView.swift` on iOS (use `#if os(iOS)` guard or separate file in project.yml)
- Profile header + 4 blocks in a ScrollView
- No grouped list style — standalone blocks with spacing

**`HestiaApp/Shared/DesignSystem/Components/HestiaSettingsBlock.swift`**
- Reusable block component (described above)

**`HestiaApp/Shared/Views/Settings/ResourcesDetailView.swift`**
- New unified view for Resources block drill-in
- Sections: Cloud LLMs, Integrations, Health
- Each section links to existing detail views

**`HestiaApp/Shared/Views/Settings/SystemDetailView.swift`**
- New view for System block drill-in
- Sections: Security (Face ID toggle, auto-lock picker), Devices (link to DeviceManagementView), Server Status, Version Info
- Danger Zone at bottom with Unregister button

### Files to Modify

**`HestiaApp/Shared/Views/Settings/UserProfileView.swift`**
- Light cleanup — ensure it works well as a drill-in from the Profile block
- Remove any redundant navigation chrome

**`HestiaApp/project.yml`**
- Ensure new settings files are in iOS sources
- Keep existing settings sub-views (CloudSettingsView, IntegrationsView, etc.) included — they're drill-in destinations

### What Gets Removed from iOS Settings
- System Status section (→ moved to Command tab Status card)
- "MCPs (Coming Soon)" row
- "Lock Now" button (→ moved to Command Quick Actions)
- Wiki Field Guide stub (already macOS-only)
- Intelligence as top-level section (→ merged into Resources or accessible from Agent profile)

### Color-Coded Block Icons
| Block | SF Symbol | Color |
|-------|-----------|-------|
| Profile | `person.crop.circle.fill` | System Blue (#0A84FF) |
| Agents | `person.3.fill` | Blue (#0A84FF) |
| Resources | `square.stack.3d.up.fill` | Orange (#FF9F0A) |
| System | `gearshape.fill` | Gray (#8E8E93) |

### Acceptance Criteria
- [ ] Settings tab shows Profile header + 4 Notion-style blocks
- [ ] Profile block: avatar + name + version subtitle, taps to UserProfileView
- [ ] Agents block: 3 agent cards visible inline, taps to agent editing
- [ ] Resources block: Cloud + Integrations + Health sub-rows, each drills to detail
- [ ] System block: Security + Devices + Server + Version + Danger Zone
- [ ] No scrolling to find anything — everything visible in one screen (or near it)
- [ ] HestiaSettingsBlock is reusable across all blocks

### Estimated Effort: 10-14 hours
- HestiaSettingsBlock component: 2h
- MobileSettingsView layout: 2-3h
- ResourcesDetailView: 2-3h
- SystemDetailView: 2-3h
- Profile header + agent inline cards: 2-3h
- Cleanup + testing: 1-2h

---

## WS4: UI Foundation (Extracted During WS1-3)

### Goal
As WS1-3 are built, extract shared patterns into reusable components. Not a separate build phase — components are extracted as they emerge.

### Expected Components

**`HestiaApp/Shared/DesignSystem/Components/HestiaCard.swift`**
- Reusable card container (from Command cards)
- Background, corner radius, border, section label
- Used by: StatusCard, TradingCard, OrdersCard, NewsfeedCard, QuickActionsCard

**`HestiaApp/Shared/DesignSystem/Components/HestiaSettingsBlock.swift`**
- Reusable settings block (from Settings rebuild)
- Icon + title + subtitle + chevron + optional content

**`HestiaApp/Shared/DesignSystem/Components/HestiaStatusBadge.swift`**
- Reusable status badge (green/amber/red with text)
- Used by: StatusCard, TradingCard, OrdersCard

**`HestiaApp/Shared/DesignSystem/Components/HestiaPillButton.swift`**
- Tinted pill button for quick actions
- Used by: QuickActionsCard, mode toggle picker

**`HestiaApp/Shared/DesignSystem/Colors+iOS.swift`**
- iOS-specific color extensions mapping to Apple semantic colors
- Mode colors: `.hestiaAmber`, `.artemisTeal`, `.apolloPurple`
- Card colors: `.cardBackground`, `.cardBorder`
- Status colors: `.statusGreen`, `.statusAmber`, `.statusRed`

### Design Token Mapping
| Token | Value | Usage |
|-------|-------|-------|
| Card Background | `#1C1C1E` (secondarySystemBackground) | All cards, blocks |
| Card Border | `#2C2C2E` at 0.5px | All cards, blocks |
| Card Radius | 14px | All cards, blocks |
| Section Label | 12px semibold uppercase, `#8E8E93`, 0.8px tracking | Card section headers |
| Hestia Amber | `#FF9F0A` | Voice conversation, Hestia agent |
| Artemis Teal | `#30D5C8` | Voice journal, Artemis agent |
| Apollo Purple | `#BF5AF2` | Apollo agent, intelligence |
| System Blue | `#0A84FF` | Default accent, chat mode, send button |
| Status Green | `#34C759` | Healthy, running, positive |
| Status Red | `#FF453A` | Error, kill switch, negative |
| Status Amber | `#FF9F0A` | Warning, degraded |

---

## Build Order & Dependencies

```
WS0: TestFlight Pipeline
 ↓ (unblocks device testing)
WS1: Chat + Voice Modes
 ↓ (establishes input patterns, waveform component)
WS2: Mobile Command
 ↓ (establishes card patterns, status components)
WS3: Settings Rebuild
 ↓ (uses block components, completes the app)
WS4: Component extraction happens DURING WS1-3
```

### Sprint Mapping (at ~12h/week + Claude Code acceleration)

| Sprint | Scope | Duration | Deliverable |
|--------|-------|----------|-------------|
| Sprint A | WS0: TestFlight Pipeline | 1-2 days | Working TestFlight build on iPhone |
| Sprint B | WS1: Chat Input Bar + Mode Toggle | 3-4 days | Three-mode input, basic mode switching |
| Sprint C | WS1: Voice Conversation | 3-4 days | Inline recording, live transcript, auto-send |
| Sprint D | WS1: Voice Journal + Thought Streaming | 3-4 days | Prose rendering, journal mode, visible reasoning |
| Sprint E | WS2: Mobile Command | 4-5 days | Card dashboard, trading, orders, quick actions |
| Sprint F | WS3: Settings Rebuild | 3-4 days | 4-block settings, Notion style |
| Sprint G | Polish + Component Extraction | 2-3 days | Shared components, edge cases, testing |

**Total: ~5-7 weeks** with first usable build on phone after Sprint A (day 2).

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| App Store Connect setup blocks TestFlight | Medium | High | Andrew does manual setup first; pipeline work proceeds in parallel on simulator |
| Voice recording doesn't work on first TestFlight build | Medium | Medium | Test SpeechAnalyzer entitlements in Xcode first; verify `NSMicrophoneUsageDescription` and `NSSpeechRecognitionUsageDescription` in iOS/Info.plist. SpeechAnalyzer requires iOS 26+ (matches our deployment target). |
| iOS 26.0 deployment target limits test devices | Low | Medium | Andrew's phone is on latest iOS; only affects if he needs to test on older devices |
| Trading API methods not available in Shared target | Medium | Low | Create shared APIClient extensions; most methods are simple GET wrappers |
| WKWebView/React Flow in chat (future consideration) | Low | Low | Not in scope for this refresh — all native SwiftUI |
| Kill Switch accidental trigger on mobile | Medium | High | Confirmation alert with explicit text confirmation ("Type KILL to confirm") |

---

## Out of Scope (Noted for Future)

- **Multi-speaker diarization** — Architecture is ready (nullable speaker fields), implementation deferred
- **Journal post-processing pipeline** — v1 sends to chat; dedicated `/v1/voice/process-journal` endpoint is future work
- **Newsfeed detail view** — v1 shows titles only; drill-in to full articles is future
- **Investigation detail view** — Quick Action submits URL; viewing results is via Chat or macOS
- **Workflow editing** — Command shows status only; editing workflows stays on macOS
- **Health Dashboard** — Stays macOS-only for now
- **Memory Browser** — Stays macOS-only for now
- **Push notifications for trading alerts** — APNs infrastructure exists but alert-specific triggers not wired
