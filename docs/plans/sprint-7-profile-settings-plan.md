# Sprint 7: Profile & Settings Restructure

**Created:** 2026-03-03
**Status:** PLANNED
**Priority:** P0 — Ship first (highest user-facing impact, zero new backend work)
**Estimated Effort:** ~14.5 days (~87 hours at 6hr/week ≈ 14.5 weeks)
**Audit:** `docs/plans/sprint-7-9-audit-2026-03-03.md`
**Prerequisites:** None — all backend endpoints already exist

---

## Objective

Rebuild the Settings view as a 4-section accordion (Profile, Agents, Resources, Field Guide). Wire all sections to production backend APIs. Make everything editable and persistent. Apply global orange accent.

## Deliverables

1. Settings view restructured as accordion layout
2. User profile fully editable (name, photo with crop, MIND.md, BODY.md, settings)
3. Agent profiles wired to V2 API with Identity + Personality tabs
4. Resources section consolidates Cloud/LLMs, Integrations, Devices
5. Field Guide migrated from dedicated tab into Settings
6. Global orange accent applied to all interactive elements

---

## Task Breakdown

### 7.1 Settings Accordion Shell (~1 day)

**Goal:** Replace current Settings view with expandable-section layout.

**Files to create:**
- `macOS/Views/Settings/MacSettingsView.swift` — Main accordion container

**Files to modify:**
- `macOS/Views/` — Update sidebar navigation to point to new Settings view
- Remove or redirect old settings entry points

**Design:**
```
┌─────────────────────────────────────────────┐
│  ⚙️  Settings                                │
│                                               │
│  ▼ Profile                [expanded]          │
│  ┌─────────────────────────────────────────┐ │
│  │ [content]                                │ │
│  └─────────────────────────────────────────┘ │
│                                               │
│  ▶ Agents                 [collapsed]         │
│  ▶ Resources              [collapsed]         │
│  ▶ Field Guide            [collapsed]         │
└─────────────────────────────────────────────┘
```

**SwiftUI pattern:** `DisclosureGroup` with custom styling, or custom `AccordionSection` view with `@State` expansion tracking. Only one section expanded at a time (optional — ask Andrew during implementation).

**Acceptance criteria:**
- [ ] 4 sections visible, each expandable/collapsible
- [ ] Smooth animation on expand/collapse
- [ ] Remembers last-expanded section across view dismissals (UserDefaults)

---

### 7.2 User Profile Section (~4 days)

#### 7.2.1 Profile Header (Name + Description) — 0.5 day

**API:** `GET /v1/user/profile`, `PATCH /v1/user/profile`

**Files to create:**
- `macOS/Views/Settings/MacProfileView.swift` — Profile section content
- `macOS/ViewModels/MacUserSettingsViewModel.swift` — Manages all profile + settings state

**Behavior:**
- Display name + description as editable text fields
- Save on blur/commit (debounced 1s)
- Loading state while fetching, error state on failure
- Local cache: UserDefaults for instant display, server sync on load

#### 7.2.2 Profile Photo Editor — 1.5 days

**API:** `POST /v1/user/photo` (multipart), `GET /v1/user/photo`, `DELETE /v1/user/photo`

**Files to create:**
- `macOS/Views/Settings/ProfilePhotoEditor.swift` — Photo picker + crop + preview

**Flow:**
1. Display current photo (circular mask, 80pt diameter)
2. Tap → Sheet: "Choose from Library" / "Take Photo" (if camera available)
3. `NSOpenPanel` for photo library or `AVCaptureSession` for camera
4. Selected image → Crop overlay (circle mask, pinch-to-zoom on trackpad)
5. Preview with "Cancel" / "Save" buttons
6. On save: Compress to JPEG (quality 0.8, max 1024x1024), `POST /v1/user/photo`
7. On success: Update cached photo, animate transition (cross-dissolve)
8. Delete option: Long-press → "Remove Photo" confirmation

**Edge cases:**
- No photo set → show initials avatar (first letter of name, amber accent background)
- Upload failure → show error toast, keep previous photo
- Large image → resize before upload (max 1MB)

#### 7.2.3 MIND.md / BODY.md Markdown Editor — 3 days

> **Audit adjustment (2026-03-03):** Increased from 2 days to 3. SwiftUI's `TextEditor` lacks line numbers and syntax highlighting. Requires `NSTextView` wrapped in `NSViewRepresentable` with custom `NSTextStorage` for syntax highlighting. This is non-trivial macOS AppKit integration.

**API:** `GET /v1/user-profile/files/{file_name}`, `PUT /v1/user-profile/files/{file_name}`

**Files to create:**
- `macOS/Views/Common/MarkdownEditorView.swift` — Reusable markdown editor component

**Features:**
- Full-width text editor with monospace font (SF Mono 13pt)
- Dark background matching the CLI input aesthetic (#1E1E1E)
- Toggle between Edit mode (raw markdown) and Preview mode (rendered)
- Syntax highlighting for: headers (`#`), bold (`**`), lists (`-`), code (`` ` ``), links
- Auto-save on blur or after 2s of inactivity (debounced)
- Undo/Redo via standard ⌘Z / ⌘⇧Z
- Line numbers in edit mode
- Unsaved changes indicator (dot in tab/section header)

**API integration:**
- On section expand: `GET /v1/user-profile/files/MIND.md` → populate editor
- On save: `PUT /v1/user-profile/files/MIND.md` with full content
- Error handling: retry on 5xx, alert on 4xx (file not found → create on first save)

**Reusability:** This component will be reused for:
- BODY.md (same profile section)
- ANIMA.md (agent personality editor)
- Order prompt drafting (Sprint 11)
- Explorer file editing (Sprint 9)

---

### 7.3 Agent Profiles Section (~3 days)

**API (V2 only — V1 becomes legacy):**
- `GET /v2/agents` — list all agents
- `GET /v2/agents/{name}` — get agent config
- `GET /v2/agents/{name}/config/IDENTITY.md` — identity details
- `PUT /v2/agents/{name}/config/IDENTITY.md` — update identity
- `GET /v2/agents/{name}/config/ANIMA.md` — personality/instructions
- `PUT /v2/agents/{name}/config/ANIMA.md` — update personality

> **Audit fix (2026-03-03):** V2 agent API uses `/config/{file_name}`, NOT `/files/{file_name}`. The `AgentConfigFile` enum validates allowed file names. Verified in `hestia/api/routes/agents_v2.py`.

**Files to create:**
- `macOS/Views/Settings/MacAgentsView.swift` — Grid of 3 agent cards
- `macOS/Views/Settings/AgentCardView.swift` — Individual agent card
- `macOS/Views/Settings/AgentDetailSheet.swift` — Two-tab editor
- `macOS/Views/Settings/AgentIdentityEditor.swift` — Name, emoji, vibe, colors, temperature
- `macOS/Views/Settings/AgentPersonalityEditor.swift` — Markdown editor for ANIMA.md
- `macOS/ViewModels/MacAgentsViewModel.swift` — V2 API integration
- `macOS/Services/APIClient+AgentsV2.swift` — V2 endpoint wrapper

#### Agent Card Layout
```
┌──────────────────────┐
│  ┌────┐              │
│  │    │  Tia  🌊     │
│  │photo│              │
│  └────┘              │
│  "Sardonic daily ops" │
│                       │
│  [Edit →]            │
└──────────────────────┘
```

#### Agent Detail Sheet (2 tabs)

**Identity Tab:**
| Field | Type | API Field |
|-------|------|-----------|
| Name | Text field | `name` in IDENTITY.md |
| Emoji | Emoji picker | `emoji` |
| Vibe | Text field | `vibe` |
| Primary Color | Color picker | `colors.primary` |
| Secondary Color | Color picker | `colors.secondary` |
| Temperature | Slider (0.0–2.0) | `temperature` |
| Invoke Pattern | Text field | `invoke_pattern` (e.g., "@Tia") |

**Personality Tab:**
- Full markdown editor (reuse `MarkdownEditorView`) for ANIMA.md
- Contains: personality description, focus areas, behavioral instructions
- Auto-save with same debounce pattern as MIND.md

**Photo upload:** Same `ProfilePhotoEditor` component, adapted for agent photos.

---

### 7.4 Resources Consolidation (~2 days)

**Replaces:** `MacCloudSettingsView`, `MacIntegrationsView`, `ResourcesView` (6 files)

**Files to create:**
- `macOS/Views/Settings/MacResourcesView.swift` — Resources accordion sub-section

**Sub-sections within Resources:**

#### LLMs (Cloud Providers)
- **API:** `/v1/cloud/providers/*` (7 endpoints)
- **Existing view to migrate:** `MacCloudSettingsView` → embed as sub-section
- Provider cards: Anthropic, OpenAI, Google with status indicators
- Add/remove providers, toggle state (disabled/smart/full), select model
- Usage summary with token counts and costs

#### Integrations
- **API:** `/v1/tools` (dynamic discovery)
- **Existing view to migrate:** `MacIntegrationsView` → embed as sub-section
- Integration cards: Calendar, Reminders, Notes, Mail, HealthKit
- Status indicator (connected/disconnected)
- Future: Whoop, Gmail (added in later sprints)

#### Devices
- **API:** `/v1/user/devices`, `/v1/user/devices/{id}/revoke`, `/v1/user/devices/{id}/unrevoke`
- **Existing view to migrate:** Device management from `MacUserProfileView`
- Device list with name, last seen, revocation status
- Revoke/unrevoke actions

**Migration strategy:**
1. Create new `MacResourcesView` with 3 sub-sections
2. Extract content from existing views into embedded components
3. Update navigation references to point to new location
4. Remove old standalone views after verification
5. Ensure no broken references in sidebar/tab navigation

---

### 7.5 Field Guide Migration (~1 day)

**Migrates from:** Dedicated Wiki tab → Settings accordion section

**Existing macOS views to relocate (no code changes needed, just navigation):**
- `MacWikiView` — article list with type filters
- `MacWikiArticleListView` — filtered article grid
- `MacWikiArticleDetailView` — full article reader
- `MacWikiDiagramView` — Mermaid diagram renderer

**API:** `/v1/wiki/*` (6 endpoints) — already wired via `APIClient+Wiki.swift`

**Implementation:**
1. Field Guide accordion section expands to show `MacWikiView`
2. Full NavigationStack within the section for drill-down
3. Expanding Field Guide → article list → tap article → detail view
4. Back navigation stays within the accordion section (doesn't pop to Settings root)

**Sidebar update:** Remove dedicated "Wiki" tab from sidebar. Update sidebar item count (was 6, now 5: Command, Chat, Explorer, Research, Settings).

**Roadmap data wiring:** The Field Guide's Roadmap tab (`WikiRoadmapView`) pulls structured data from `GET /v1/wiki/roadmap`, which is parsed from `docs/hestia-development-plan.md` by `WikiScanner.parse_roadmap()`. As part of this sprint:
1. `docs/hestia-development-plan.md` has been updated with Sprint 7–14 milestone groups (PLANNED status) and a new "What's Next" narrative covering the three arcs (UI Maturity, Self-Awareness, Active Inference).
2. The WikiRoadmapView will automatically display the new sprints — no parser changes needed (same `### Title` + `| Title | Scope | Status |` table format).
3. Ensure the "What's Next" banner in WikiRoadmapView renders the updated strategic narrative.
4. After Sprint 7 UI is wired, run `POST /v1/wiki/refresh-static` to update the SQLite article cache.
5. Individual sprint plans are cross-referenced from `docs/plans/sprint-7-14-master-roadmap.md` for deep-dive details.

---

### 7.6 Amber Accent Consistency + Design Token Expansion (~1.5 days)

> **Audit fix (2026-03-03):** Original plan specified `#FF6B35` (bright orange), but `MacColors.swift` already uses a Figma-derived amber palette (`E0A050`/`FFB900`/`FF8904`). Per Andrew's decision, the **existing amber palette is the source of truth**. This task ensures consistency and adds missing tokens, not a palette swap.

**Files to modify:**
- `macOS/DesignSystem/MacColors.swift` — Add missing interaction/status/animation tokens

**Existing accent tokens (KEEP AS-IS — source of truth):**
```swift
static let amberAccent = Color(hex: "E0A050")   // Primary accent
static let amberBright = Color(hex: "FFB900")   // Bright variant
static let amberDark = Color(hex: "FF8904")     // Dark variant
```

**New tokens to add:**
```swift
// Interactive states — needed by all future sprints
static let hoverBackground = amberAccent.opacity(0.08)
static let pressedBackground = amberAccent.opacity(0.20)
static let disabledForeground = Color.white.opacity(0.3)
static let focusRing = amberAccent.opacity(0.5)

// Semantic status colors — extend existing healthGreen/healthRed/etc.
// Use the existing health* tokens where possible; add only what's missing.
// healthGreen (00D492), healthRed (FF6467), healthGold (FEE685), healthAmber (FFB900) already exist.
static let statusWarning = Color(hex: "FF9800")   // Distinct from healthAmber (more orange)
static let statusCritical = Color(hex: "D32F2F")  // Distinct from healthRed (darker, more urgent)
static let statusInfo = amberAccent                // Info = accent color

// Animation timing tokens — prevent per-view hardcoding
static let animationFast: Double = 0.15
static let animationNormal: Double = 0.25
static let animationSlow: Double = 0.4
```

> **Status color reconciliation:** The existing `healthGreen`, `healthRed`, `healthGold`, `healthAmber` tokens remain for health-specific UI. The new `statusWarning` and `statusCritical` are for non-health contexts (order status, error states, alerts). Avoid duplicating: use `healthGreen` for "normal/success" everywhere (don't add `statusNormal`).

**Views to audit for hardcoded blue:**
- All `Button` styles
- All `Toggle` styles
- `Picker` / `Segmented Control` selections
- `TextField` focus rings
- `List` selection highlights
- `ProgressView` tints
- Tab bar indicators
- Any `.accentColor(.blue)` or `.tint(.blue)` calls

**System-level elements (cannot be themed — document as known limitation):**
- macOS menu bar focus rings (system accent)
- Window chrome (title bar close/minimize/zoom)
- System alerts/sheets (`NSAlert`)
- Context menus (system highlight)
- Scroll indicators

**Accessibility:** All new interactive elements must include `accessibilityLabel`. Views that display data should support VoiceOver navigation. Dynamic Type compliance is not required for this sprint but should be tracked as future debt.

**Testing:** Visual review of every view after token addition. Verify amber consistency across all interactive elements. Screenshot comparison.

---

### 7.7 Local Cache Layer (~1 day)

**Files to create:**
- `macOS/Services/CacheManager.swift` — UserDefaults-backed cache with TTL

**Pattern:**
```swift
class CacheManager {
    static let shared = CacheManager()

    func cache<T: Codable>(_ value: T, forKey key: String, ttl: TimeInterval = 300)
    func get<T: Codable>(_ type: T.Type, forKey key: String) -> T?
    func invalidate(forKey key: String)
    func invalidateAll()
}
```

**Usage in ViewModels:**
```swift
// On view appear: show cached data immediately, then fetch fresh
func loadProfile() async {
    if let cached = CacheManager.shared.get(UserProfile.self, forKey: "user_profile") {
        self.profile = cached  // Instant display
    }
    let fresh = try await APIClient.shared.get("/v1/user/profile")
    self.profile = fresh
    CacheManager.shared.cache(fresh, forKey: "user_profile")
}
```

**Cache keys:**
- `user_profile` — User profile data
- `user_settings` — User settings
- `user_photo` — Photo data (Base64 or file URL)
- `agents_list` — V2 agent list
- `agent_{name}_identity` — Per-agent identity
- `agent_{name}_personality` — Per-agent ANIMA.md
- `cloud_providers` — LLM provider list
- `tools_list` — Integration/tool discovery
- `devices_list` — Registered devices

---

### 7.8 Model Deduplication (Audit Addition) (~0.5 day)

**Problem:** 5 model files are duplicated between `macOS/Models/` and `Shared/Models/` (WikiModels, ToolModels, DeviceModels, HealthDataModels, NewsfeedModels). Every future sprint that touches API models doubles the maintenance burden.

**Action:** Before Sprint 8 compounds the problem:
1. Consolidate duplicate models into `Shared/Models/` as the single source of truth
2. Update macOS target membership to include `Shared/Models/` files
3. Remove `macOS/Models/` duplicates
4. Verify both Xcode targets build clean
5. Add CI check: fail if any file exists in both `macOS/Models/` and `Shared/Models/`

---

## Testing Plan

| Area | Test Count | Type |
|------|-----------|------|
| Settings accordion navigation | 3 | UI state |
| Profile CRUD (name, description) | 4 | API integration |
| Photo upload/delete flow | 3 | API + file handling |
| Photo crop edge cases (oversized, corrupt, zero-byte) | 2 | Edge case |
| MIND.md / BODY.md read/write | 4 | API integration |
| Agent V2 list/detail/update | 6 | API integration |
| Agent photo upload | 2 | API + file handling |
| Resources section rendering | 2 | UI state |
| Cache manager operations | 4 | Unit |
| Cache invalidation + TTL expiry | 3 | Unit |
| Accordion state persistence across dismissals | 2 | UI state |
| Empty state rendering (no photo, no MIND.md, no agents) | 3 | UI state |
| MarkdownEditorView undo/redo (⌘Z/⌘⇧Z) | 2 | UI |
| Photo crop with non-square / very small images | 2 | Edge case |
| **Total** | **~42** | |

## SWOT

| | Positive | Negative |
|---|---|---|
| **Strengths** | All backend endpoints exist. Zero new backend work. Accordion is native SwiftUI. V2 agent API is clean. MarkdownEditorView is highly reusable. | Consolidating Resources means removing/refactoring 6 existing views. Risk of breaking existing Cloud/Integrations during migration. |
| **Opportunities** | Clean settings becomes foundation for future config (Whoop auth, Gmail auth). Markdown editor reused in 4+ future sprints. | Field Guide inside Settings may feel buried. Users who relied on Wiki tab might be confused. |

## Dependencies

- **Blocked by:** Nothing
- **Blocks:** Sprint 9 (Explorer needs cache layer), Sprint 11 (Command needs Resources data)
- **Shared components:** `MarkdownEditorView` → Sprints 9, 10, 11. `ProfilePhotoEditor` → Agent photos. `CacheManager` → all future sprints.

## Definition of Done

- [ ] All 4 accordion sections expand/collapse correctly
- [ ] User profile editable: name, description, photo (with crop)
- [ ] MIND.md and BODY.md editable with live preview toggle
- [ ] All 3 agents editable via V2 API (Identity + Personality tabs)
- [ ] Resources shows LLMs, Integrations, Devices — all wired to production data
- [ ] Field Guide accessible within Settings, full navigation preserved
- [ ] Roadmap tab shows Sprint 7–14 milestones with PLANNED status
- [ ] "What's Next" banner displays updated strategic narrative (3 arcs)
- [ ] Amber accent consistent globally — no remaining blue interactive elements
- [ ] Local cache provides instant load for all settings data
- [ ] Design tokens expanded: interactive states (hover/pressed/disabled/focus), semantic status (warning/critical/info), animation timing
- [ ] Existing health color tokens reused where applicable (no duplicate status palette)
- [ ] V2 agent API calls use `/config/{file_name}` path (not `/files/`)
- [ ] Model deduplication complete: 5 duplicate files consolidated into Shared/Models/
- [ ] Empty states implemented: no-photo initials avatar, blank MIND.md prompt, agent defaults
- [ ] VoiceOver `accessibilityLabel` on all new interactive elements
- [ ] All tests passing (existing 1258 + ~42 new)
- [ ] Both Xcode targets build clean
