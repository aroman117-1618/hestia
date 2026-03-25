# iOS Refresh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh the Hestia iOS app: TestFlight pipeline, three-mode voice input (Chat/Voice Conversation/Voice Journal), card-based Mobile Command dashboard, Notion-style Settings rebuild.

**Architecture:** Native SwiftUI (no WebView). Three input modes sharing one ChatInputBar. Cards for viewing (Command), blocks for editing (Settings). Agent-mapped colors: Amber = Hestia, Teal = Artemis, Purple = Apollo.

**Tech Stack:** SwiftUI (iOS 26.0+), AVFoundation + SpeechAnalyzer (voice), FastAPI (backend), GitHub Actions (CI/CD)

**Spec:** `docs/superpowers/specs/2026-03-24-ios-refresh-design.md`

---

## File Structure Overview

### WS0: TestFlight Pipeline (~3-4h)
```
Create: HestiaApp/ExportOptions-iOS.plist
Create: .github/workflows/release-ios.yml
Modify: HestiaApp/iOS/Info.plist              (verify NSMicrophoneUsageDescription, NSSpeechRecognitionUsageDescription)
Modify: .claude/skills/ship-it/SKILL.md       (note dual-platform release)
```

### WS1: Chat + Voice Modes (~20-25h)
```
Create: HestiaApp/Shared/Models/ChatInputMode.swift
Create: HestiaApp/Shared/Views/Chat/ChatInputBar.swift
Create: HestiaApp/Shared/Views/Chat/VoiceConversationView.swift
Create: HestiaApp/Shared/Views/Chat/VoiceJournalView.swift
Create: HestiaApp/Shared/Views/Chat/WaveformView.swift
Create: HestiaApp/Shared/Views/Chat/ThinkingIndicator.swift
Create: HestiaApp/Shared/Models/JournalModels.swift
Modify: HestiaApp/Shared/Views/Chat/ChatView.swift           (extract input bar, add mode state)
Modify: HestiaApp/Shared/Views/Chat/MessageBubble.swift      (voice transcript bubble style)
Modify: HestiaApp/Shared/ViewModels/ChatViewModel.swift      (metadata param, stage display, mode routing)
Modify: HestiaApp/Shared/ViewModels/VoiceInputViewModel.swift (mode-aware behavior, skip quality check for conversation)
Modify: hestia/api/routes/chat.py                             (metadata field on ChatRequest)
Modify: hestia/orchestration/handler.py                        (agent_hint from journal metadata)
```

### WS2: Mobile Command (~15-20h)
```
Create: HestiaApp/Shared/Views/Command/MobileCommandView.swift
Create: HestiaApp/Shared/Views/Command/StatusCard.swift
Create: HestiaApp/Shared/Views/Command/TradingCard.swift
Create: HestiaApp/Shared/Views/Command/OrdersCard.swift
Create: HestiaApp/Shared/Views/Command/NewsfeedCard.swift
Create: HestiaApp/Shared/Views/Command/QuickActionsCard.swift
Create: HestiaApp/Shared/ViewModels/MobileCommandViewModel.swift
Modify: HestiaApp/Shared/Views/RootView.swift (or MainTabView.swift — add Command tab)
Modify: HestiaApp/project.yml                 (include new Command views in iOS target, ensure trading API methods in Shared)
```

### WS3: Settings Rebuild (~10-14h)
```
Create: HestiaApp/Shared/Views/Settings/MobileSettingsView.swift
Create: HestiaApp/Shared/Views/Settings/ResourcesDetailView.swift
Create: HestiaApp/Shared/Views/Settings/SystemDetailView.swift
Create: HestiaApp/Shared/DesignSystem/Components/HestiaSettingsBlock.swift
Create: HestiaApp/Shared/DesignSystem/Components/HestiaCard.swift
Create: HestiaApp/Shared/DesignSystem/Components/HestiaStatusBadge.swift
Create: HestiaApp/Shared/DesignSystem/Components/HestiaPillButton.swift
Create: HestiaApp/Shared/DesignSystem/Colors+iOS.swift
Modify: HestiaApp/Shared/Views/Settings/UserProfileView.swift  (cleanup for drill-in)
Modify: HestiaApp/project.yml                                   (wire new views)
```

---

## Task 1: TestFlight Pipeline (WS0)

**Sprint A — 1-2 days**

### Step 1: Verify iOS Info.plist Keys
- [ ] Read `HestiaApp/iOS/Info.plist` — confirm `NSMicrophoneUsageDescription` and `NSSpeechRecognitionUsageDescription` exist
- [ ] If missing, add them with appropriate descriptions
- [ ] Verify `NSCameraUsageDescription` exists (for QR scanner onboarding)
- [ ] Verify bundle ID is `com.andrewlonati.hestia` and team ID is `563968AM8L`

### Step 2: Create ExportOptions-iOS.plist
- [ ] Create `HestiaApp/ExportOptions-iOS.plist` with `method: app-store`, `signingStyle: automatic`, `teamID: 563968AM8L`, `uploadSymbols: true`

### Step 3: Create release-ios.yml
- [ ] Create `.github/workflows/release-ios.yml`
- [ ] Trigger: tag push `v*` + manual dispatch
- [ ] Steps: checkout → xcodegen → SPM resolve → archive (iOS generic platform) → export → upload via App Store Connect API
- [ ] Runner: `[self-hosted, macos, hestia]`
- [ ] Secrets: `APP_STORE_CONNECT_API_KEY_ID`, `APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_KEY_BASE64`

### Step 4: Update ship-it Skill
- [ ] Update `.claude/skills/ship-it/SKILL.md` to note tag push triggers both macOS and iOS workflows
- [ ] No code changes needed — version/build numbers already shared via `project.yml`

### Step 5: Test Pipeline (requires Andrew's manual steps first)
- [ ] Andrew: Create app in App Store Connect
- [ ] Andrew: Generate API key, provide key ID + issuer ID + base64 .p8
- [ ] Andrew: Add secrets to GitHub repo
- [ ] Run `/ship-it` with a test version bump
- [ ] Verify both workflows trigger
- [ ] Verify iOS build appears in TestFlight
- [ ] Install on iPhone, verify app launches and auth works

---

## Task 2: Chat Input Mode System (WS1, Part 1)

**Sprint B — 3-4 days**

### Step 1: Create ChatInputMode Enum
- [ ] Create `HestiaApp/Shared/Models/ChatInputMode.swift`
- [ ] Enum with cases: `.chat`, `.voice`, `.journal`
- [ ] Computed properties: `icon` (SF Symbol name), `color` (SwiftUI Color), `placeholder` (String), `agentHint` (String?)
- [ ] Colors: chat = `.blue` (#0A84FF), voice = amber (#FF9F0A), journal = teal (#30D5C8)

### Step 2: Create WaveformView
- [ ] Create `HestiaApp/Shared/Views/Chat/WaveformView.swift`
- [ ] Accepts `audioLevel: CGFloat` binding + `tintColor: Color`
- [ ] Renders animated vertical bars (8-12 bars)
- [ ] Bars scale based on audio level with spring animation
- [ ] Idle state: subtle low-amplitude animation

### Step 3: Extract ChatInputBar
- [ ] Create `HestiaApp/Shared/Views/Chat/ChatInputBar.swift`
- [ ] Extract input bar logic from `ChatView.swift`
- [ ] Properties: `@Binding text: String`, `@Binding inputMode: ChatInputMode`, `isRecording: Bool`, `audioLevel: CGFloat`
- [ ] Mode icon button (left): circular, tinted, taps to cycle modes, long-press for picker
- [ ] Text field (center): placeholder changes per mode, border tints to mode color
- [ ] Right button: adaptive (send when text present, mic/record when empty in voice/journal, hidden in chat when empty)
- [ ] Waveform replaces text field during active recording

### Step 4: Wire Mode State into ChatView
- [ ] Add `@State private var inputMode: ChatInputMode = .chat` to ChatView
- [ ] Replace inline input bar with `ChatInputBar` component
- [ ] Pass mode binding through to input bar
- [ ] Mode persists across messages (doesn't reset after send)

### Step 5: Build + Test Mode Switching
- [ ] Run @hestia-build-validator for both iOS and macOS targets
- [ ] Verify mode cycling works (visual only — voice recording in next sprint)
- [ ] Verify long-press picker shows all 3 modes with labels
- [ ] Verify color tinting changes on mode switch

---

## Task 3: Voice Conversation Mode (WS1, Part 2)

**Sprint C — 3-4 days**

### Step 1: Create VoiceConversationView
- [ ] Create `HestiaApp/Shared/Views/Chat/VoiceConversationView.swift`
- [ ] NOT a full-screen overlay — integrates inline with ChatView
- [ ] During recording: live transcript appears as amber-tinted user bubble in the message list
- [ ] Bubble shows cursor/caret at end of live text
- [ ] Small waveform indicator beside the bubble

### Step 2: Wire Voice Recording to Chat Bubbles
- [ ] Modify `ChatViewModel` — add `@Published var liveTranscript: String?`
- [ ] When `inputMode == .voice` and recording starts, create a temporary message in the messages array with `isLiveTranscript: true`
- [ ] Update that message's text as `VoiceInputViewModel.rawTranscript` changes
- [ ] On stop: finalize the message, send via normal `sendMessage()` flow

### Step 3: Simplify Voice Flow (Skip Quality Check)
- [ ] Modify `VoiceInputViewModel` — when `inputMode == .voice`:
  - `stopRecording()` → get final transcript → call `onTranscriptReady(transcript)` callback immediately
  - Skip `runQualityCheck()` and review step entirely
  - Quality check can run in background and flag issues post-send (future enhancement)
- [ ] Remove `VoiceRecordingOverlay` presentation for voice conversation mode (keep it for journal mode if needed)

### Step 4: Update Header During Recording
- [ ] Modify `ChatView` header — when recording in voice mode:
  - Agent subtitle changes to "Listening..." in amber
  - Timer badge appears showing recording duration
  - Revert to "Online" when recording stops

### Step 5: Test End-to-End Voice Conversation
- [ ] On device: tap mode to Voice → tap record → speak → see live transcript → tap stop → message sends → Hestia responds
- [ ] Verify streaming response works after voice send
- [ ] Run @hestia-tester for backend (ensure chat endpoint handles voice messages normally)

---

## Task 4: Voice Journal Mode + Thought Streaming (WS1, Part 3)

**Sprint D — 3-4 days**

### Step 1: Create Journal Data Models
- [ ] Create `HestiaApp/Shared/Models/JournalModels.swift`
- [ ] `TranscriptSegment`: text, startTime, endTime, speakerId (optional), speakerLabel (optional), confidence, isParagraphBreak
- [ ] `JournalEntry`: id, timestamp, segments, metadata
- [ ] `JournalMetadata`: inputMode, duration, speakerCount, prompt

### Step 2: Create VoiceJournalView
- [ ] Create `HestiaApp/Shared/Views/Chat/VoiceJournalView.swift`
- [ ] Presented as sheet or replaces chat content area when journal mode recording starts
- [ ] Header: "Journal Entry" badge (teal) + timer
- [ ] Optional prompt text (italic, secondary color)
- [ ] Transcript area: Georgia serif font, 17px, 1.65 line height
- [ ] Pause detection: when SpeechService returns a gap >2 seconds, insert visual paragraph break ("pause detected" divider)
- [ ] Live text appears with teal-tinted cursor at end
- [ ] Checkmark button in input bar submits the entry

### Step 3: Wire Journal Submission
- [ ] On checkmark tap: collect all transcript text + segments
- [ ] Send via `ChatViewModel.sendMessage()` with metadata: `{ "source": "journal", "input_mode": "journal", "duration": N }`
- [ ] Message appears in chat as a condensed journal entry (not full prose — summary or "Journal entry submitted" with expandable detail)

### Step 4: Backend Journal Routing
- [ ] Modify `hestia/api/routes/chat.py` — add optional `metadata: Optional[dict] = None` to `ChatRequest` model
- [ ] Modify `hestia/orchestration/handler.py` — if `metadata.get("source") == "journal"`, set `agent_hint = "artemis"` on the request context
- [ ] Agent hint influences routing confidence (not a hard override — Artemis gets a boost)
- [ ] Run @hestia-tester to verify chat endpoint still works with and without metadata

### Step 5: Implement Thought Streaming
- [ ] Create `HestiaApp/Shared/Views/Chat/ThinkingIndicator.swift`
- [ ] Faded bubble with italic text + subtle pulse animation
- [ ] Modify `ChatViewModel` — parse SSE `stage` field, update `@Published var currentStage: String?`
- [ ] Display ThinkingIndicator below last assistant message when `currentStage != nil`
- [ ] Stage text mapping: "preparing" → "Preparing...", "thinking" → "Thinking...", "tool_call" → "Using tools...", custom stage names pass through
- [ ] Disappears when response text starts streaming

### Step 6: Build + Comprehensive Voice Testing
- [ ] Run @hestia-build-validator for both targets
- [ ] On device: test all 3 modes end-to-end
- [ ] Verify journal entries route to Artemis (check logs for agent_hint)
- [ ] Verify thought streaming shows stages during response

---

## Task 5: Mobile Command Dashboard (WS2)

**Sprint E — 4-5 days**

### Step 1: Create MobileCommandViewModel
- [ ] Create `HestiaApp/Shared/ViewModels/MobileCommandViewModel.swift`
- [ ] `@MainActor class MobileCommandViewModel: ObservableObject`
- [ ] Published properties: `systemHealth`, `tradingSummary`, `tradingBots`, `tradingRisk`, `workflows`, `newsfeedItems`, `isLoading`, `failedSections`
- [ ] `loadAll()` — parallel fetch via `async let` for all data sources
- [ ] Individual load methods with `try/catch` — failures add to `failedSections` set, don't block other cards
- [ ] Auto-refresh: trading every 60s, others every 5min
- [ ] Pull-to-refresh calls `loadAll()`

### Step 2: Ensure Trading API in Shared
- [ ] Check if `APIClient+Trading.swift` is in Shared or macOS-only
- [ ] If macOS-only: create `HestiaApp/Shared/Services/APIClient+Trading.swift` with methods: `getTradingBots()`, `getTradingSummary()`, `getTradingRiskStatus()`, `toggleKillSwitch()`, `getWorkflows()`, `getNewsfeedTimeline(limit:)`
- [ ] Verify these compile on iOS target

### Step 3: Create Card Components
- [ ] Create `HestiaApp/Shared/DesignSystem/Components/HestiaCard.swift` — reusable card container (background, radius, border, section label)
- [ ] Create `HestiaApp/Shared/DesignSystem/Components/HestiaStatusBadge.swift` — colored badge (green/amber/red + text)
- [ ] Create `HestiaApp/Shared/DesignSystem/Colors+iOS.swift` — iOS color tokens (card background, borders, agent colors, status colors)

### Step 4: Build Individual Cards
- [ ] Create `StatusCard.swift` — 3-column metrics (bots | P&L | fills) + status badge
- [ ] Create `TradingCard.swift` — bot list with P&L + Kill Switch button (with confirmation alert) + autonomous toggle
- [ ] Create `OrdersCard.swift` — workflow list with status badges, collapsible beyond 3 items
- [ ] Create `NewsfeedCard.swift` — compact news rows with unread indicator
- [ ] Create `QuickActionsCard.swift` — tinted pill buttons (Cloud Mode, Investigate, Journal, Lock)

### Step 5: Create MobileCommandView + Wire Tab
- [ ] Create `MobileCommandView.swift` — ScrollView with cards stacked vertically, large title "Command", pull-to-refresh
- [ ] Modify root tab view — add Command tab (middle position) with `square.grid.2x2.fill` icon
- [ ] Update `project.yml` if needed to include new Command directory in iOS target
- [ ] Wire Quick Actions: Cloud Mode → cycles cloud state, Investigate → sheet with URL field, Journal → switch to chat tab in journal mode, Lock → `authService.lock()`

### Step 6: Kill Switch Safety
- [ ] Kill Switch button shows confirmation alert: "Disable All Trading?" with explicit confirmation
- [ ] Consider requiring text input ("Type KILL to confirm") for extra safety on mobile
- [ ] API call: `POST /trading/kill-switch` with appropriate body

### Step 7: Build + Test Command Tab
- [ ] Run @hestia-build-validator
- [ ] On device: verify all cards load data
- [ ] Test Kill Switch with confirmation
- [ ] Test Quick Actions (Cloud toggle, Investigate sheet, Journal mode switch, Lock)
- [ ] Verify pull-to-refresh works
- [ ] Run @hestia-tester for backend endpoints

---

## Task 6: Settings Rebuild (WS3)

**Sprint F — 3-4 days**

### Step 1: Create HestiaSettingsBlock Component
- [ ] Create `HestiaApp/Shared/DesignSystem/Components/HestiaSettingsBlock.swift`
- [ ] Generic view: icon (SF Symbol + tint color) + title + subtitle + optional inline content + optional navigation destination
- [ ] Visual: #1C1C1E background, 14px radius, 0.5px border, chevron when navigable
- [ ] Create `HestiaPillButton.swift` — tinted pill for actions (reused from Quick Actions)

### Step 2: Create MobileSettingsView
- [ ] Create `HestiaApp/Shared/Views/Settings/MobileSettingsView.swift`
- [ ] Profile header: avatar (photo or initials gradient) + name + "v1.6.0 · Server Online" subtitle
- [ ] 4 blocks: Profile, Agents, Resources, System
- [ ] Use `#if os(iOS)` or project.yml to swap with existing SettingsView on iOS

### Step 3: Build Agents Block (Inline Cards)
- [ ] Agents block shows 3 agent cards horizontally: avatar circle + name + role + active indicator
- [ ] Active agent has tinted background
- [ ] Tap any agent → navigates to existing `AgentProfileView`
- [ ] Tap block header → navigates to agent list (or same behavior)

### Step 4: Create ResourcesDetailView
- [ ] Create `HestiaApp/Shared/Views/Settings/ResourcesDetailView.swift`
- [ ] Sections: Cloud LLMs (provider list + state), Integrations (Calendar/Reminders/HealthKit), Health (coaching preferences)
- [ ] Each section links to existing detail views (CloudSettingsView, IntegrationsView, HealthCoachingPreferencesView)
- [ ] Resources block on main settings shows: "Full · Anthropic | 3 integrations"

### Step 5: Create SystemDetailView
- [ ] Create `HestiaApp/Shared/Views/Settings/SystemDetailView.swift`
- [ ] Sections: Security (Face ID toggle, auto-lock picker), Devices (count + link to DeviceManagementView), Server (health status), Version (build info)
- [ ] Danger Zone at bottom: "Unregister Device" (red, destructive, with confirmation)
- [ ] System block on main settings shows: "Face ID · 2 devices"

### Step 6: Wire + Test
- [ ] Update `project.yml` to include new settings views in iOS target
- [ ] Verify navigation works: main → block → detail → sub-detail
- [ ] Verify all existing functionality preserved (cloud management, device management, etc.)
- [ ] Run @hestia-build-validator
- [ ] Run @hestia-tester

---

## Task 7: Polish + Component Extraction (WS4)

**Sprint G — 2-3 days**

### Step 1: Audit Shared Components
- [ ] Review HestiaCard, HestiaSettingsBlock, HestiaStatusBadge, HestiaPillButton for consistency
- [ ] Ensure all use Colors+iOS tokens, not hardcoded values
- [ ] Verify components work on both iOS and macOS (if applicable)

### Step 2: Edge Cases + Error Handling
- [ ] Voice modes: handle permission denied (microphone, speech recognition)
- [ ] Command cards: handle offline state (show cached data with "Last updated X ago")
- [ ] Settings: handle API failures gracefully (show cached state, retry button)
- [ ] Kill Switch: verify works when server is unreachable (show error, don't silently fail)

### Step 3: Visual Polish
- [ ] Consistent animation curves (spring animations for mode transitions)
- [ ] Loading states for all cards (skeleton/shimmer, not spinners)
- [ ] Empty states for cards with no data ("No active orders", "No recent trades")
- [ ] Dark mode consistency (should be fine — all using system colors)

### Step 4: Final Testing
- [ ] Full end-to-end test on device: all 3 tabs, all 3 voice modes, all quick actions
- [ ] Run @hestia-build-validator for both targets
- [ ] Run @hestia-tester for all backend changes
- [ ] Run @hestia-ui-auditor on all new views
- [ ] Run @hestia-reviewer on all changed files

### Step 5: Documentation
- [ ] Update CLAUDE.md: new file counts, endpoint counts, project structure
- [ ] Update docs/api-contract.md if new endpoints added
- [ ] Update SPRINT.md with iOS Refresh sprint entry

---

## Dependency Graph

```
Task 1 (TestFlight) ─────────────────────────────────────────────┐
                                                                  │
Task 2 (Input Mode System) ──→ Task 3 (Voice Conversation) ──→   │
                              ──→ Task 4 (Voice Journal)     ──→ │──→ Task 7 (Polish)
                                                                  │
Task 5 (Mobile Command) ─────────────────────────────────────────│
                                                                  │
Task 6 (Settings Rebuild) ───────────────────────────────────────┘
```

Tasks 2-6 depend on Task 1 (need TestFlight for device testing).
Tasks 3 and 4 depend on Task 2 (need input mode system).
Tasks 5 and 6 are independent of each other and of Tasks 3-4.
Task 7 depends on all others.

---

## Estimated Total: 48-63 hours (~5-7 weeks at 12h/week)

| Task | Hours | Calendar |
|------|-------|----------|
| Task 1: TestFlight | 3-4h | Days 1-2 |
| Task 2: Input Mode System | 6-8h | Days 3-6 |
| Task 3: Voice Conversation | 6-8h | Days 7-10 |
| Task 4: Voice Journal + Thought Streaming | 8-10h | Days 11-14 |
| Task 5: Mobile Command | 15-20h | Days 15-22 |
| Task 6: Settings Rebuild | 10-14h | Days 23-28 |
| Task 7: Polish | 4-6h | Days 29-32 |
