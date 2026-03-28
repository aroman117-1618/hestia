# macOS App Refresh — Design Spec

**Date:** 2026-03-27
**Status:** Approved
**Scope:** Navigation restructure, Command tab redesign, chat panel detach, design system convergence with iOS

---

## 1. Navigation — Refreshed Vertical Sidebar

The sidebar is streamlined from 5 tabs to 3 (Command, Memory, Settings) with a chat toggle. Same 56px width (`MacSize.iconSidebarWidth`), same dark background (`MacColors.sidebarBackground`).

### Layout (top to bottom)

| Position | Element | Icon / Visual | Action | Shortcut |
|----------|---------|---------------|--------|----------|
| Top | User avatar | Gradient circle with user initials (e.g., "HS") | Opens Settings view | ⌘3 |
| Mid | Command | SF Symbol: `house` | Switches to Command tab | ⌘1 |
| Mid | Memory | SF Symbol: `brain.head.profile` | Switches to Memory tab | ⌘2 |
| Bottom | Chat toggle | Cursor-style right-sidebar panel icon | Toggles chat panel | ⌘\ |

### Removed

- **Hestia logo** — replaced by user avatar at top
- **Explorer tab** (`magnifyingglass`) — removed entirely
- **Orders tab** (`bolt.fill`) — moved into Command tab

### Active state

Same pattern as current: amber-tinted background with gradient indicator pill on left edge, matched geometry effect for animation between icons.

### Chat toggle behavior

- **Panel closed** → single click opens the right-side chat panel
- **Panel open** → single click closes the panel
- **Panel open** → double-click detaches the panel into a standalone `NSWindow`
- When detached, the toggle icon should reflect the detached state (e.g., highlighted/tinted differently)
- Closing the detached window re-docks the chat panel

---

## 2. Command Tab

The Command tab is the primary view. It consists of a hero section and 3 sub-tabs: Internal, Newsfeed, System Alerts.

### 2.1 Hero Section

Split left/right layout within a bordered section (`border-bottom: 0.5px solid MacColors.cardBorder`).

**Left side (identity cluster):**
- Hestia profile avatar — 64pt circle with gradient ring (amber → purple), `H` initial, amber glow shadow
- Wavelength band — condensed horizontal particle wave (260pt wide, 22pt tall), positioned above the greeting text. Amber gradient fading left-to-right. This is a decorative SVG/SwiftUI animation, NOT the full `HestiaWavelengthView` from iOS.
- Greeting — "Good [morning/afternoon/evening], [name]" (20pt, semibold)
- Date byline — "Thursday, March 27" (11pt, `MacColors.textSecondary`)

**Right side (stats, pinned):**
- 4 stat columns separated by 0.5px dividers:
  - **P&L** — value colored by sign (green positive, red negative), label "P&L (7D)"
  - **Bots** — count of active bots
  - **Fills** — total fill count
  - **Alerts** — count, amber if > 0
- Font: 17pt semibold for values, 10pt secondary for labels

### 2.2 Sub-Tab Bar

Horizontal tab bar below hero: Internal | Newsfeed | System Alerts

- Active tab: amber text + 2px amber underline
- Inactive: `MacColors.textSecondary`
- Padding: 10px vertical, 16px horizontal per tab
- Font: 11pt, weight 500
- **Lazy loading:** Each sub-tab has its own ViewModel. Data is only fetched when the tab is selected, not on Command tab entry. The parent `CommandView` uses a `switch` on the selected tab to render only the active sub-view.

### 2.3 Internal Sub-Tab

Two-column grid layout (`grid-template-columns: 1fr 1fr`, 12px gap).

**Left column — Calendar card:**
- Card: `HestiaCard` pattern (`#110B03` background, `#1A1408` border, 12px radius)
- Header: blue dot + "Calendar" (12pt semibold)
- Week strip: 7-day horizontal strip, current day highlighted with amber background
- Event list: time (blue, 40pt width) | event name | duration (right-aligned, secondary text)
- Data source: EventKit, today only

**Right column — Tasks & Reminders card:**
- Card: same `HestiaCard` pattern
- Header: amber dot + "Tasks & Reminders" (12pt semibold)
- Task rows: circular checkbox (13pt, 1.5px border) | task name | due time (right-aligned)
- Completed tasks: green filled checkbox with checkmark, strikethrough text, secondary color
- Data source: Reminders, today only

### 2.4 Newsfeed Sub-Tab

**Trading section (top):**
- Section header: "TRADING" (uppercase, secondary, 11pt) with P&L lookback toggle pinned right
- Lookback toggle: segmented control with options 24H | 7D | 30D | ALL — active segment uses amber background
- Two-column layout:
  - **Left — Status card**: online indicator (green dot + "All Systems Live"), 2×2 grid of stats (P&L, Fills, Win Rate, Drawdown)
  - **Right — Active Positions card**: table with columns Pair | Side | Entry | Current | P&L. Side colored (green LONG, red SHORT). P&L colored by value.

**Orders + Investigations section (bottom):**
- Two-column layout:
  - **Left — Orders card**: list of scheduled/completed/running orders with status indicators (green triangle = scheduled, green check = completed, amber circle = running)
  - **Right — Investigation Findings card**: investigation results with purple dot indicators, title, time, and one-line summary

### 2.5 System Alerts Sub-Tab

Three severity sections, each with a colored section header (dot + uppercase label).

**Success (green):**
- Standard card with green-accented header
- Items: green checkmark + description + detail line + timestamp
- Content: completed orders, Hestia proposed principles (purple diamond icon)

**Errors (red):**
- Card with red-tinted border (`rgba(255,69,58,0.2)`)
- Items: red X + description + detail line + timestamp
- Content: order failures with error details

**Atlas Alerts (amber):**
- Card with amber-tinted border (`rgba(255,159,10,0.2)`)
- Items: amber warning icon + description + detail line + timestamp
- Content: Sentinel findings, security alerts

---

## 3. Chat Panel

### Persistent right panel (existing behavior, kept)
- Collapsible right panel, 520px max width (per `MainSplitViewController`)
- Contains `MacChatPanelView` (message history, input bar, reactions)
- Toggle via sidebar icon or ⌘\

### Detach to window (new)
- Double-click on sidebar chat toggle detaches the panel into a standalone `NSWindow`
- **State architecture:** Use a single shared `MacChatViewModel` instance. Do NOT move the `NSHostingController` between containers — re-create the SwiftUI view hierarchy in the new window, injecting the same ViewModel instance. This ensures state synchronization (messages, typing state) between docked and detached contexts.
- The detached window:
  - Contains a new `NSHostingController` wrapping `MacChatPanelView` with the shared ViewModel
  - Minimum size: 400×500
  - Title bar: "Hestia Chat" or similar
  - Dark theme matching main window (`#0D0802` background)
  - Remembers position/size via `NSWindow.FrameAutosaveName`
  - Must receive full environment setup (AppState, AuthService, NetworkMonitor, APIClientProvider)
- While detached:
  - Main window's chat panel area is hidden (content expands to fill)
  - Sidebar chat icon reflects detached state (tinted/highlighted)
  - Single-click on sidebar icon brings detached window to front
  - ⌘\ works regardless of which window is focused
- Window lifecycle:
  - Closing the detached window re-docks the chat panel into the main window
  - Closing the main window also closes the detached chat window (`NSWindow.ChildBehavior`)
  - Sidebar icon returns to normal toggle behavior after re-dock
- **Budget: 8-10h** — AppKit↔SwiftUI interop is the riskiest piece in this sprint

---

## 4. Memory Tab

**No changes.** Research canvas, knowledge graph, and sidebar remain as-is.

---

## 5. Design System Convergence

Apply the iOS Notion-block pattern throughout the macOS app where cards are used.

### Shared components to adopt
- `HestiaCard` — dark card container with label and border (already in `Shared/DesignSystem/Components/`)
- `HestiaStatusBadge` — colored dot + text indicator
- `HestiaPillButton` — tinted pill-shaped button with icon + text

### Color tokens (existing `MacColors`, no changes needed)
- Card background: `#110B03`
- Card border: `#1A1408`
- Text primary: `#E8E2D9`
- Text secondary: `#807B74`
- Amber accent: `#FF9F0A`
- Status green: `#34C759`
- Error red: `#FF453A`
- Info blue: `#0A84FF`
- Apollo purple: `#BF5AF2`

### Typography
- Hero greeting: 20pt semibold
- Card headers: 12pt semibold
- Card body: 11pt regular
- Stat values: 17pt semibold
- Stat labels: 10pt regular, secondary color
- Sub-tab labels: 11pt, weight 500
- Section headers: 11pt uppercase, 0.8px letter-spacing, secondary color

---

## 6. Empty States

Every card must handle the "no data" case gracefully.

| Card | Empty State |
|------|-------------|
| Calendar | "No events today" with subtle calendar icon |
| Tasks & Reminders | "All clear" with checkmark icon |
| Trading Status | "No bots active" — show "Set up trading" link if no bots configured |
| Active Positions | "No open positions" |
| Orders | "No orders scheduled" with "Create Order" action |
| Investigation Findings | "No recent investigations" |
| Success alerts | "No recent activity" |
| Errors | "All systems nominal" (green) |
| Atlas Alerts | "No security alerts" (green) |

Empty states use `MacColors.textTertiary`, centered in the card with a relevant SF Symbol at 24pt above the text.

---

## 7. Migration & Deep Links

### UserDefaults migration

`WorkspaceView(rawValue:)` must handle unknown values gracefully. If the persisted raw value is `"orders"`, `"explorer"`, `"workflow"`, or `"research"`, fall back to `.command`. Implement in `WorkspaceState.init()`:

```swift
init() {
    let raw = UserDefaults.standard.string(forKey: "currentView") ?? "command"
    self.currentView = WorkspaceView(rawValue: raw) ?? .command
}
```

### Deep link redirection

Deep links that previously targeted Explorer or Orders must redirect:
- `hestia://orders/*` → Navigate to Command tab, switch to Newsfeed sub-tab
- `hestia://explorer/*` → Navigate to Command tab (no specific sub-tab)
- Deep links to entities/facts (Memory) are unchanged

Update the deep link handler in `WorkspaceRootView` to remap these.

---

## 8. Deferred

The following are explicitly out of scope for this sprint:
- Settings redesign (Notion-block pattern for settings)
- Onboarding refresh (Sign in with Apple, Touch ID)
- Apple ID integration (name, photo, email)
- Explorer rework (unified file view)

---

## 9. Files Affected

### Remove / Archive
- `HestiaApp/macOS/Views/Explorer/` — entire directory (12+ files)
- `HestiaApp/macOS/ViewModels/MacExplorerViewModel.swift`
- `HestiaApp/macOS/ViewModels/MacExplorerFilesViewModel.swift`
- `HestiaApp/macOS/ViewModels/MacExplorerResourcesViewModel.swift`

### Modify
- `HestiaApp/macOS/Views/Chrome/IconSidebar.swift` — remove Explorer/Orders icons, add chat toggle, replace logo with avatar
- `HestiaApp/macOS/State/WorkspaceState.swift` — remove `.explorer` and `.orders` cases from `WorkspaceView` enum
- `HestiaApp/macOS/Views/WorkspaceRootView.swift` — remove Explorer/Orders switch cases, update content routing
- `HestiaApp/macOS/Views/Command/CommandView.swift` — redesign with hero + 3 sub-tabs
- `HestiaApp/macOS/Views/Command/HeroSection.swift` — new layout: avatar + wavelength left, stats right
- `HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift` — add trading stats, calendar/tasks data
- `HestiaApp/macOS/MainSplitViewController.swift` — support chat panel detach/re-dock
- `HestiaApp/macOS/MainWindowController.swift` — manage detached chat NSWindow lifecycle
- `HestiaApp/macOS/Views/Chat/MacChatPanelView.swift` — support rendering in both panel and standalone window contexts

### Create
- `HestiaApp/macOS/Views/Command/InternalTabView.swift` — Calendar + Tasks two-column
- `HestiaApp/macOS/Views/Command/NewsfeedTabView.swift` — Trading + Orders + Investigations
- `HestiaApp/macOS/Views/Command/SystemAlertsTabView.swift` — Success/Errors/Atlas
- `HestiaApp/macOS/Views/Command/TradingStatusView.swift` — Status card + positions table
- `HestiaApp/macOS/Views/Command/PLLookbackToggle.swift` — Segmented control for P&L period
- `HestiaApp/macOS/ViewModels/InternalTabViewModel.swift` — Calendar + Tasks data (EventKit)
- `HestiaApp/macOS/ViewModels/NewsfeedTabViewModel.swift` — Trading + Orders + Investigations data
- `HestiaApp/macOS/ViewModels/SystemAlertsTabViewModel.swift` — Alerts data
- `HestiaApp/macOS/Views/Chat/DetachedChatWindow.swift` — NSWindow wrapper for detached chat

### WorkspaceView enum (updated)
```swift
enum WorkspaceView: String {
    case command
    case memory
    case settings  // navigated via avatar, not sidebar nav icons
}
```

---

## 10. Mockup Reference

Visual mockups from this brainstorming session are preserved in:
`.superpowers/brainstorm/77847-1774638794/content/`

Key files:
- `sidebar-refreshed.html` — final sidebar + Command tab layout
- `command-layout-v2.html` — Newsfeed and System Alerts sub-tabs
- `hero-refined-v2.html` — hero iteration (avatar + wavelength left, stats right)
