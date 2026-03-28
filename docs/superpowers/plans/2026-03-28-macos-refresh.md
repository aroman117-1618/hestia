# macOS App Refresh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamline the macOS app from 5 sidebar tabs to 3, redesign the Command tab with hero + sub-tabs, add chat panel detach-to-window, and converge design language with iOS.

**Architecture:** Pure frontend refactor. No backend changes. Remove Explorer entirely (16 files), absorb Orders into Command tab's Newsfeed sub-tab, add 3 independent sub-tab ViewModels with lazy loading. Chat detach uses shared ViewModel injected into a standalone NSWindow.

**Tech Stack:** SwiftUI, AppKit (NSWindow, NSSplitViewController), EventKit, existing APIClient extensions.

**Spec:** `docs/superpowers/specs/2026-03-27-macos-refresh-design.md`
**Second Opinion:** `docs/plans/macos-refresh-second-opinion-2026-03-27.md`

---

## File Map

### Delete (16 files)
- `HestiaApp/macOS/Views/Explorer/` — all 13 files
- `HestiaApp/macOS/ViewModels/MacExplorerViewModel.swift`
- `HestiaApp/macOS/ViewModels/MacExplorerFilesViewModel.swift`
- `HestiaApp/macOS/ViewModels/MacExplorerResourcesViewModel.swift`

### Create (9 files)
- `HestiaApp/macOS/Views/Command/InternalTabView.swift`
- `HestiaApp/macOS/Views/Command/NewsfeedTabView.swift`
- `HestiaApp/macOS/Views/Command/SystemAlertsTabView.swift`
- `HestiaApp/macOS/Views/Command/TradingStatusView.swift`
- `HestiaApp/macOS/Views/Command/PLLookbackToggle.swift`
- `HestiaApp/macOS/Views/Command/WavelengthBand.swift`
- `HestiaApp/macOS/ViewModels/InternalTabViewModel.swift`
- `HestiaApp/macOS/ViewModels/NewsfeedTabViewModel.swift`
- `HestiaApp/macOS/ViewModels/SystemAlertsTabViewModel.swift`

### Modify (9 files)
- `HestiaApp/macOS/State/WorkspaceState.swift`
- `HestiaApp/macOS/Views/Chrome/IconSidebar.swift`
- `HestiaApp/macOS/Views/WorkspaceRootView.swift`
- `HestiaApp/macOS/Views/Command/CommandView.swift`
- `HestiaApp/macOS/Views/Command/HeroSection.swift`
- `HestiaApp/macOS/AppDelegate.swift`
- `HestiaApp/macOS/State/CommandPaletteState.swift`
- `HestiaApp/macOS/DesignSystem/Accessibility.swift`
- `HestiaApp/macOS/MainSplitViewController.swift`

---

## Task 1: Strip WorkspaceView enum and fix all references

This is the foundational change — everything else depends on it. Must be done atomically so the project builds.

**Files:**
- Modify: `HestiaApp/macOS/State/WorkspaceState.swift`
- Modify: `HestiaApp/macOS/Views/Chrome/IconSidebar.swift`
- Modify: `HestiaApp/macOS/Views/WorkspaceRootView.swift`
- Modify: `HestiaApp/macOS/AppDelegate.swift`
- Modify: `HestiaApp/macOS/State/CommandPaletteState.swift`
- Modify: `HestiaApp/macOS/DesignSystem/Accessibility.swift`
- Delete: `HestiaApp/macOS/Views/Explorer/` (entire directory)
- Delete: `HestiaApp/macOS/ViewModels/MacExplorerViewModel.swift`
- Delete: `HestiaApp/macOS/ViewModels/MacExplorerFilesViewModel.swift`
- Delete: `HestiaApp/macOS/ViewModels/MacExplorerResourcesViewModel.swift`

- [ ] **Step 1: Update WorkspaceView enum**

In `HestiaApp/macOS/State/WorkspaceState.swift`, replace the entire file:

```swift
import SwiftUI
import HestiaShared

// MARK: - Workspace Navigation State

enum WorkspaceView: String {
    case command
    case memory
    case settings
}

// MARK: - Persistence Keys

private enum WorkspaceDefaults {
    static let currentView = "hestia.workspace.currentView"
    static let chatPanelVisible = "hestia.workspace.chatPanelVisible"
    static let isChatDetached = "hestia.workspace.chatDetached"
}

@MainActor
@Observable
class WorkspaceState {
    var currentView: WorkspaceView {
        didSet {
            UserDefaults.standard.set(currentView.rawValue, forKey: WorkspaceDefaults.currentView)
        }
    }

    var isChatPanelVisible: Bool {
        didSet {
            UserDefaults.standard.set(isChatPanelVisible, forKey: WorkspaceDefaults.chatPanelVisible)
        }
    }

    var isChatDetached: Bool = false

    /// Which sub-tab is active in the Command tab
    var commandSubTab: CommandSubTab = .internal

    enum CommandSubTab: String, CaseIterable {
        case `internal` = "Internal"
        case newsfeed = "Newsfeed"
        case systemAlerts = "System Alerts"
    }

    init() {
        // Restore persisted state with migration for removed views
        let savedRaw = UserDefaults.standard.string(forKey: WorkspaceDefaults.currentView) ?? "command"
        // Migration: old values (.orders, .explorer, .workflow, .research, etc.) fall back to .command
        self.currentView = WorkspaceView(rawValue: savedRaw) ?? .command

        // Default to chat visible if never set (first launch)
        if UserDefaults.standard.object(forKey: WorkspaceDefaults.chatPanelVisible) != nil {
            self.isChatPanelVisible = UserDefaults.standard.bool(forKey: WorkspaceDefaults.chatPanelVisible)
        } else {
            self.isChatPanelVisible = true
        }
    }
}
```

- [ ] **Step 2: Update IconSidebar — remove Explorer/Orders, replace logo with avatar, add chat toggle**

In `HestiaApp/macOS/Views/Chrome/IconSidebar.swift`, replace the entire file:

```swift
import SwiftUI
import HestiaShared

struct IconSidebar: View {
    @Environment(WorkspaceState.self) private var workspace
    @State private var hoveredView: WorkspaceView?
    @State private var hoveredChat = false
    @Namespace private var indicatorNamespace

    var body: some View {
        VStack(spacing: 0) {
            // Settings avatar (top — replaces logo)
            settingsButton
                .padding(.top, MacSpacing.xl)

            // Nav icons
            VStack(spacing: 6) {
                navIcon(.command, systemName: "house", shortcut: 1)
                    .padding(.top, MacSpacing.lg)
                navIcon(.memory, systemName: "brain.head.profile", shortcut: 2)
            }
            .padding(.top, MacSpacing.xxl)

            Spacer()

            // Chat panel toggle (bottom)
            chatToggleButton
                .padding(.bottom, MacSpacing.xxl)
        }
        .frame(width: MacSize.iconSidebarWidth)
        .background(MacColors.sidebarBackground)
        .overlay(alignment: .trailing) {
            MacColors.sidebarBorder.frame(width: 1)
        }
    }

    // MARK: - Nav Icon

    private func navIcon(_ view: WorkspaceView, systemName: String, shortcut: Int) -> some View {
        let isActive = workspace.currentView == view
        let isHovered = hoveredView == view

        return Button {
            withAnimation(MacAnimation.normalSpring) {
                workspace.currentView = view
            }
        } label: {
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                    .fill(isActive ? MacColors.activeNavBackground : (isHovered ? MacColors.activeNavBackground.opacity(0.5) : Color.clear))
                    .overlay {
                        if isActive {
                            RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                                .strokeBorder(MacColors.activeNavBorder, lineWidth: 1)
                        }
                    }
                    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)

                if isActive {
                    UnevenRoundedRectangle(
                        topLeadingRadius: 0,
                        bottomLeadingRadius: 0,
                        bottomTrailingRadius: 8,
                        topTrailingRadius: 8
                    )
                    .fill(MacColors.activeIndicatorGradient)
                    .frame(width: MacSize.activeIndicatorWidth, height: MacSize.activeIndicatorHeight)
                    .offset(x: -1, y: 0)
                    .matchedGeometryEffect(id: "activeIndicator", in: indicatorNamespace)
                }

                Image(systemName: systemName)
                    .font(.system(size: MacSize.navIcon))
                    .foregroundStyle(isActive ? MacColors.amberAccent : (isHovered ? MacColors.textPrimary : MacColors.textSecondary))
                    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
            }
        }
        .buttonStyle(.hestiaNav)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: MacAnimation.fast)) {
                hoveredView = hovering ? view : nil
            }
        }
        .accessibilityLabel(accessibilityLabel(for: view))
        .accessibilityHint("Keyboard shortcut: Command \(shortcut)")
        .hoverCursor()
    }

    private func accessibilityLabel(for view: WorkspaceView) -> String {
        switch view {
        case .command: "Command Center"
        case .memory: "Memory"
        case .settings: "Settings"
        }
    }

    // MARK: - Settings Button (top avatar)

    private var settingsButton: some View {
        let isActive = workspace.currentView == .settings
        let isHovered = hoveredView == .settings

        return Button {
            withAnimation(MacAnimation.normalSpring) {
                workspace.currentView = .settings
            }
        } label: {
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color(red: 70/255, green: 25/255, blue: 1/255).opacity(0.8),
                                Color(red: 254/255, green: 154/255, blue: 0).opacity(0.3)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                Circle()
                    .strokeBorder(
                        isActive ? MacColors.amberAccent : MacColors.avatarBorder,
                        lineWidth: isActive ? 1.5 : 1
                    )

                Text("HS")
                    .font(MacTypography.caption)
                    .tracking(0.065)
                    .foregroundStyle(MacColors.textPrimary)
            }
            .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
            .opacity(isHovered && !isActive ? 0.85 : 1.0)
        }
        .buttonStyle(.hestiaNav)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: MacAnimation.fast)) {
                hoveredView = hovering ? .settings : nil
            }
        }
        .accessibilityLabel("Settings")
        .accessibilityHint("Keyboard shortcut: Command 3")
        .hoverCursor()
    }

    // MARK: - Chat Toggle Button

    private var chatToggleButton: some View {
        Button {
            NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
        } label: {
            let isOpen = workspace.isChatPanelVisible
            let isDetached = workspace.isChatDetached

            Image(systemName: isDetached ? "rectangle.portrait.on.rectangle.portrait" : "sidebar.trailing")
                .font(.system(size: MacSize.navIcon))
                .foregroundStyle(
                    isDetached ? MacColors.amberAccent :
                    (isOpen ? MacColors.textPrimary :
                    (hoveredChat ? MacColors.textPrimary : MacColors.textSecondary))
                )
                .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
                .background(
                    RoundedRectangle(cornerRadius: MacCornerRadius.navIcon)
                        .fill(isOpen || isDetached ? MacColors.activeNavBackground : Color.clear)
                )
        }
        .buttonStyle(.hestiaNav)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: MacAnimation.fast)) {
                hoveredChat = hovering
            }
        }
        .accessibilityLabel("Chat Panel")
        .accessibilityHint("Click to toggle, double-click to detach")
        .hoverCursor()
    }
}
```

- [ ] **Step 3: Update WorkspaceRootView — remove Explorer/Orders cases, fix deep links**

In `HestiaApp/macOS/Views/WorkspaceRootView.swift`, replace the content switch and deep link handler:

Replace the `switch workspace.currentView` block (lines 23-34) with:

```swift
switch workspace.currentView {
case .command:
    CommandView()
case .memory:
    ResearchView()
case .settings:
    MacSettingsView()
}
```

Replace the `navigate(to:)` method (lines 90-133) with:

```swift
private func navigate(to link: HestiaDeepLink) {
    switch link {
    case .entity(let id):
        withAnimation(.hestiaNavSwitch) { workspace.currentView = .memory }
        NotificationCenter.default.post(
            name: .hestiaResearchNavigate,
            object: nil,
            userInfo: ["mode": "canvas", "entityId": id]
        )

    case .fact(let id):
        withAnimation(.hestiaNavSwitch) { workspace.currentView = .memory }
        NotificationCenter.default.post(
            name: .hestiaResearchNavigate,
            object: nil,
            userInfo: ["mode": "graph", "factId": id]
        )

    case .workflow(let id, let stepId):
        // Redirect: Orders absorbed into Command/Newsfeed
        withAnimation(.hestiaNavSwitch) {
            workspace.currentView = .command
            workspace.commandSubTab = .newsfeed
        }

    case .researchCanvas(let boardId, let entityId):
        withAnimation(.hestiaNavSwitch) { workspace.currentView = .memory }
        var info: [String: String] = ["mode": "canvas", "boardId": boardId]
        if let eid = entityId { info["entityId"] = eid }
        NotificationCenter.default.post(
            name: .hestiaResearchNavigate,
            object: nil,
            userInfo: info
        )

    case .chat:
        break
    }
}
```

- [ ] **Step 4: Update AppDelegate — remove Orders/Explorer menu items, renumber shortcuts**

In `HestiaApp/macOS/AppDelegate.swift`:

Remove the `ordersItem` menu item (lines ~91-93) and `expItem` (lines ~99-100). Remove `showOrdersView` and `showExplorerView` methods (lines ~174, ~176). Remove the corresponding shortcut observers (lines ~136, ~142). Renumber Memory to ⌘2 and Settings to ⌘3.

- [ ] **Step 5: Update CommandPaletteState — remove Orders/Explorer palette commands**

In `HestiaApp/macOS/State/CommandPaletteState.swift`:

Remove the palette command entries with ids `"nav.orders"` (lines ~63-67) and `"nav.explorer"` (lines ~75-79).

- [ ] **Step 6: Update Accessibility labels**

In `HestiaApp/macOS/DesignSystem/Accessibility.swift`:

Remove the `.orders` and `.explorer` cases (lines ~39, ~41) from the accessibility label switch.

- [ ] **Step 7: Delete Explorer files**

```bash
rm -rf HestiaApp/macOS/Views/Explorer/
rm HestiaApp/macOS/ViewModels/MacExplorerViewModel.swift
rm HestiaApp/macOS/ViewModels/MacExplorerFilesViewModel.swift
rm HestiaApp/macOS/ViewModels/MacExplorerResourcesViewModel.swift
```

- [ ] **Step 8: Verify build compiles**

Run xcodegen (if needed) and verify the macOS target builds:
```bash
cd HestiaApp && xcodegen generate && cd ..
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -20
```

Fix any remaining references to `.orders`, `.explorer`, `ExplorerView`, or `MacWorkflowView` that the compiler flags.

- [ ] **Step 9: Commit**

```bash
git add -A HestiaApp/macOS/
git commit -m "refactor(macos): strip sidebar to 3 tabs — remove Explorer, absorb Orders into Command

Remove .explorer and .orders from WorkspaceView enum. Delete 16 Explorer
files. Replace logo with avatar in sidebar. Add chat toggle icon. Redirect
deep links for removed tabs. Update menu shortcuts and command palette."
```

---

## Task 2: Redesign Hero Section

**Files:**
- Modify: `HestiaApp/macOS/Views/Command/HeroSection.swift`
- Create: `HestiaApp/macOS/Views/Command/WavelengthBand.swift`

- [ ] **Step 1: Create WavelengthBand view**

Create `HestiaApp/macOS/Views/Command/WavelengthBand.swift`:

```swift
import SwiftUI

/// Decorative amber wavelength animation for the Command hero section.
/// Lightweight SwiftUI Path — NOT the Metal particle system from iOS.
struct WavelengthBand: View {
    @State private var phase: CGFloat = 0

    var body: some View {
        Canvas { context, size in
            let midY = size.height / 2
            let amplitude: CGFloat = 8
            let wavelength: CGFloat = 40

            // Primary wave
            var path1 = Path()
            path1.move(to: CGPoint(x: 0, y: midY))
            for x in stride(from: 0, through: size.width, by: 2) {
                let y = midY + sin((x / wavelength + phase) * .pi * 2) * amplitude
                path1.addLine(to: CGPoint(x: x, y: y))
            }
            context.stroke(
                path1,
                with: .linearGradient(
                    Gradient(colors: [
                        Color(red: 1, green: 0.624, blue: 0.039).opacity(1),
                        Color(red: 1, green: 0.624, blue: 0.039).opacity(0.5),
                        Color(red: 1, green: 0.624, blue: 0.039).opacity(0)
                    ]),
                    startPoint: .zero,
                    endPoint: CGPoint(x: size.width, y: 0)
                ),
                lineWidth: 1.6
            )

            // Secondary wave (offset, fainter)
            var path2 = Path()
            path2.move(to: CGPoint(x: 0, y: midY + 4))
            for x in stride(from: 0, through: size.width, by: 2) {
                let y = midY + 4 + sin((x / wavelength + phase + 0.3) * .pi * 2) * (amplitude * 0.6)
                path2.addLine(to: CGPoint(x: x, y: y))
            }
            context.stroke(
                path2,
                with: .linearGradient(
                    Gradient(colors: [
                        Color(red: 1, green: 0.624, blue: 0.039).opacity(0.3),
                        Color(red: 1, green: 0.624, blue: 0.039).opacity(0.15),
                        Color(red: 1, green: 0.624, blue: 0.039).opacity(0)
                    ]),
                    startPoint: .zero,
                    endPoint: CGPoint(x: size.width, y: 0)
                ),
                lineWidth: 1.0
            )
        }
        .frame(width: 260, height: 22)
        .onAppear {
            withAnimation(.linear(duration: 4).repeatForever(autoreverses: false)) {
                phase = 1
            }
        }
    }
}
```

- [ ] **Step 2: Rewrite HeroSection**

Replace `HestiaApp/macOS/Views/Command/HeroSection.swift` entirely with the new design — avatar + wavelength left, stats right. Remove the old progress rings, status badges, and action buttons. The new hero reads trading stats from the ViewModel (wired in Task 4).

```swift
import SwiftUI
import HestiaShared

struct HeroSection: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    var body: some View {
        HStack(alignment: .center) {
            // LEFT: Avatar + Wavelength + Greeting
            HStack(spacing: MacSpacing.xxl) {
                hestiaAvatar

                VStack(alignment: .leading, spacing: 0) {
                    WavelengthBand()
                        .padding(.bottom, MacSpacing.xs)

                    Text(greetingText)
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundStyle(MacColors.textPrimaryAlt)

                    Text(dateText)
                        .font(.system(size: 11))
                        .foregroundStyle(MacColors.textSecondary)
                        .padding(.top, 2)
                }
            }

            Spacer()

            // RIGHT: Stats
            HStack(spacing: MacSpacing.lg) {
                statColumn(
                    value: viewModel.tradingPnLDisplay,
                    label: "P&L (7D)",
                    color: viewModel.tradingPnL >= 0 ? MacColors.healthGreen : MacColors.healthRed
                )
                statDivider
                statColumn(value: "\(viewModel.activeBotCount)", label: "Bots", color: MacColors.textPrimary)
                statDivider
                statColumn(value: "\(viewModel.totalFills)", label: "Fills", color: MacColors.textPrimary)
                statDivider
                statColumn(
                    value: "\(viewModel.alertCount)",
                    label: "Alerts",
                    color: viewModel.alertCount > 0 ? MacColors.amberAccent : MacColors.textPrimary
                )
            }
        }
        .padding(.horizontal, MacSpacing.xxl)
        .padding(.vertical, MacSpacing.xl)
    }

    // MARK: - Avatar

    private var hestiaAvatar: some View {
        ZStack {
            Circle()
                .fill(
                    LinearGradient(
                        colors: [MacColors.amberAccent, Color(red: 191/255, green: 90/255, blue: 242/255)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 64, height: 64)
                .shadow(color: MacColors.amberAccent.opacity(0.25), radius: 10)

            Circle()
                .fill(MacColors.aiAvatarBackground)
                .frame(width: 58, height: 58)

            Text("H")
                .font(.system(size: 24, weight: .semibold))
                .foregroundStyle(MacColors.amberAccent)
        }
    }

    // MARK: - Stat Helpers

    private func statColumn(value: String, label: String, color: Color) -> some View {
        VStack(spacing: 1) {
            Text(value)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(color)
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    private var statDivider: some View {
        Rectangle()
            .fill(MacColors.cardBorder)
            .frame(width: 0.5, height: 26)
    }

    // MARK: - Text Helpers

    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        if hour < 12 { return "Good morning, Andrew" }
        else if hour < 17 { return "Good afternoon, Andrew" }
        else { return "Good evening, Andrew" }
    }

    private var dateText: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d"
        return formatter.string(from: Date())
    }
}
```

- [ ] **Step 3: Verify build and commit**

```bash
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -10
git add HestiaApp/macOS/Views/Command/HeroSection.swift HestiaApp/macOS/Views/Command/WavelengthBand.swift
git commit -m "feat(macos): redesign hero — avatar + wavelength left, stats right"
```

---

## Task 3: Create sub-tab ViewModels

**Files:**
- Create: `HestiaApp/macOS/ViewModels/InternalTabViewModel.swift`
- Create: `HestiaApp/macOS/ViewModels/NewsfeedTabViewModel.swift`
- Create: `HestiaApp/macOS/ViewModels/SystemAlertsTabViewModel.swift`

- [ ] **Step 1: Create InternalTabViewModel**

Create `HestiaApp/macOS/ViewModels/InternalTabViewModel.swift`:

```swift
import SwiftUI
import EventKit
import HestiaShared

@MainActor
class InternalTabViewModel: ObservableObject {
    @Published var todayEvents: [EKEvent] = []
    @Published var todayReminders: [EKReminder] = []
    @Published var isLoading = false

    private let eventStore = EKEventStore()

    func loadData() async {
        isLoading = true
        defer { isLoading = false }

        await loadCalendarEvents()
        await loadReminders()
    }

    private func loadCalendarEvents() async {
        let status = EKEventStore.authorizationStatus(for: .event)
        guard status == .fullAccess || status == .authorized else { return }

        let calendar = Calendar.current
        let startOfDay = calendar.startOfDay(for: Date())
        guard let endOfDay = calendar.date(byAdding: .day, value: 1, to: startOfDay) else { return }

        let predicate = eventStore.predicateForEvents(withStart: startOfDay, end: endOfDay, calendars: nil)
        let events = eventStore.events(matching: predicate)
        todayEvents = events.sorted { $0.startDate < $1.startDate }
    }

    private func loadReminders() async {
        let status = EKEventStore.authorizationStatus(for: .reminder)
        guard status == .fullAccess || status == .authorized else { return }

        let predicate = eventStore.predicateForReminders(in: nil)
        let allReminders = await withCheckedContinuation { continuation in
            eventStore.fetchReminders(matching: predicate) { reminders in
                continuation.resume(returning: reminders ?? [])
            }
        }

        // Filter to today's reminders (due today or overdue incomplete)
        let calendar = Calendar.current
        todayReminders = allReminders.filter { reminder in
            if reminder.isCompleted { return calendar.isDateInToday(reminder.completionDate ?? .distantPast) }
            guard let dueDate = reminder.dueDateComponents?.date else { return false }
            return calendar.isDateInToday(dueDate) || dueDate < Date()
        }
    }
}
```

- [ ] **Step 2: Create NewsfeedTabViewModel**

Create `HestiaApp/macOS/ViewModels/NewsfeedTabViewModel.swift`:

```swift
import SwiftUI
import HestiaShared

@MainActor
class NewsfeedTabViewModel: ObservableObject {
    @Published var tradingSummary: TradingSummary?
    @Published var positions: [TradingPosition] = []
    @Published var bots: [TradingBot] = []
    @Published var orders: [OrderResponse] = []
    @Published var investigations: [InvestigationItem] = []
    @Published var lookbackPeriod: LookbackPeriod = .sevenDay
    @Published var isLoading = false

    enum LookbackPeriod: String, CaseIterable {
        case twentyFourHour = "24H"
        case sevenDay = "7D"
        case thirtyDay = "30D"
        case all = "ALL"
    }

    func loadData() async {
        isLoading = true
        defer { isLoading = false }

        async let tradingTask: () = loadTrading()
        async let ordersTask: () = loadOrders()
        async let investigationsTask: () = loadInvestigations()

        _ = await (tradingTask, ordersTask, investigationsTask)
    }

    private func loadTrading() async {
        do {
            async let summary = APIClient.shared.getTradingSummary()
            async let pos = APIClient.shared.getTradingPositions()
            async let botList = APIClient.shared.getTradingBots()

            tradingSummary = try await summary
            positions = (try? await pos)?.positions ?? []
            bots = (try? await botList)?.bots ?? []
        } catch {
            #if DEBUG
            print("[NewsfeedTab] Trading load failed: \(error)")
            #endif
        }
    }

    private func loadOrders() async {
        let (data, _) = await CacheFetcher.load(key: CacheKey.orders, ttl: CacheTTL.frequent) {
            try await APIClient.shared.listOrders(limit: 20)
        }
        orders = data?.orders ?? []
    }

    private func loadInvestigations() async {
        do {
            let response = try await APIClient.shared.getInvestigations(limit: 5)
            investigations = response.investigations
        } catch {
            #if DEBUG
            print("[NewsfeedTab] Investigations load failed: \(error)")
            #endif
        }
    }
}
```

- [ ] **Step 3: Create SystemAlertsTabViewModel**

Create `HestiaApp/macOS/ViewModels/SystemAlertsTabViewModel.swift`:

```swift
import SwiftUI
import HestiaShared

@MainActor
class SystemAlertsTabViewModel: ObservableObject {
    @Published var successAlerts: [SystemAlert] = []
    @Published var errorAlerts: [SystemAlert] = []
    @Published var atlasAlerts: [SystemAlert] = []
    @Published var isLoading = false

    struct SystemAlert: Identifiable {
        let id = UUID()
        let icon: String
        let iconColor: Color
        let title: String
        let detail: String
        let timestamp: Date
    }

    func loadData() async {
        isLoading = true
        defer { isLoading = false }

        // Load order execution history for success/error categorization
        do {
            let ordersResponse = try await APIClient.shared.listOrders(limit: 50)
            categorizeOrderAlerts(ordersResponse.orders)
        } catch {
            #if DEBUG
            print("[SystemAlerts] Orders load failed: \(error)")
            #endif
        }

        // Load sentinel status for Atlas alerts
        do {
            let sentinel = try await APIClient.shared.getSentinelStatus()
            if let alerts = sentinel.alerts {
                atlasAlerts = alerts.map { alert in
                    SystemAlert(
                        icon: "exclamationmark.triangle",
                        iconColor: MacColors.amberAccent,
                        title: alert.title,
                        detail: alert.detail ?? "",
                        timestamp: alert.timestamp
                    )
                }
            }
        } catch {
            // Sentinel may not be running — not an error
            atlasAlerts = []
        }
    }

    private func categorizeOrderAlerts(_ orders: [OrderResponse]) {
        var successes: [SystemAlert] = []
        var errors: [SystemAlert] = []

        for order in orders {
            guard let lastExec = order.lastExecution else { continue }
            if order.status == .active || order.status == .completed {
                successes.append(SystemAlert(
                    icon: "checkmark",
                    iconColor: MacColors.healthGreen,
                    title: "\(order.name) completed successfully",
                    detail: order.description ?? "",
                    timestamp: lastExec
                ))
            }
            if order.status == .failed {
                errors.append(SystemAlert(
                    icon: "xmark",
                    iconColor: MacColors.healthRed,
                    title: "\(order.name) failed",
                    detail: order.errorMessage ?? "Unknown error",
                    timestamp: lastExec
                ))
            }
        }

        successAlerts = successes.sorted { $0.timestamp > $1.timestamp }
        errorAlerts = errors.sorted { $0.timestamp > $1.timestamp }
    }
}
```

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/macOS/ViewModels/InternalTabViewModel.swift \
       HestiaApp/macOS/ViewModels/NewsfeedTabViewModel.swift \
       HestiaApp/macOS/ViewModels/SystemAlertsTabViewModel.swift
git commit -m "feat(macos): add sub-tab ViewModels for Command tab

InternalTabViewModel (EventKit calendar + reminders),
NewsfeedTabViewModel (trading + orders + investigations),
SystemAlertsTabViewModel (success/error/atlas categorization).
Each ViewModel loads data lazily when its tab is selected."
```

---

## Task 4: Build Command sub-tab views

**Files:**
- Create: `HestiaApp/macOS/Views/Command/InternalTabView.swift`
- Create: `HestiaApp/macOS/Views/Command/NewsfeedTabView.swift`
- Create: `HestiaApp/macOS/Views/Command/SystemAlertsTabView.swift`
- Create: `HestiaApp/macOS/Views/Command/TradingStatusView.swift`
- Create: `HestiaApp/macOS/Views/Command/PLLookbackToggle.swift`

These are the largest views in the sprint. Each sub-tab is a standalone SwiftUI view with its own ViewModel, handling its own empty states. The implementation follows the mockups from the brainstorming session.

Due to the size of these views (~150-250 lines each), they should be implemented directly from the spec's Section 2.3-2.5 and Section 6 (empty states). The key patterns:

- [ ] **Step 1: Create PLLookbackToggle** — small reusable segmented control

- [ ] **Step 2: Create TradingStatusView** — status card + positions table (used by NewsfeedTabView)

- [ ] **Step 3: Create InternalTabView** — two-column Calendar + Tasks with week strip and empty states

- [ ] **Step 4: Create NewsfeedTabView** — Trading section (TradingStatusView + PLLookbackToggle) + Orders + Investigations

- [ ] **Step 5: Create SystemAlertsTabView** — three severity sections with color-coded borders

- [ ] **Step 6: Verify build and commit**

```bash
git add HestiaApp/macOS/Views/Command/
git commit -m "feat(macos): build Command sub-tab views

InternalTabView (calendar + tasks two-column),
NewsfeedTabView (trading + orders + investigations),
SystemAlertsTabView (success/errors/atlas).
All views include empty states per spec Section 6."
```

---

## Task 5: Rewire CommandView with sub-tab architecture

**Files:**
- Modify: `HestiaApp/macOS/Views/Command/CommandView.swift`
- Modify: `HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift`

- [ ] **Step 1: Add hero stat properties to MacCommandCenterViewModel**

Add these published properties to `MacCommandCenterViewModel`:

```swift
@Published var tradingPnL: Double = 0
@Published var tradingPnLDisplay: String = "--"
@Published var activeBotCount: Int = 0
@Published var totalFills: Int = 0
@Published var alertCount: Int = 0
```

Update `loadAllData()` to populate them from the existing trading data load.

- [ ] **Step 2: Rewrite CommandView with sub-tab architecture**

Replace `HestiaApp/macOS/Views/Command/CommandView.swift`:

```swift
import SwiftUI
import HestiaShared

struct CommandView: View {
    @StateObject private var viewModel = MacCommandCenterViewModel()
    @Environment(WorkspaceState.self) private var workspace
    @Environment(ErrorState.self) private var errorState

    var body: some View {
        VStack(spacing: 0) {
            // Hero section
            HeroSection(viewModel: viewModel)

            MacColors.divider
                .frame(height: 0.5)

            // Sub-tab bar
            subTabBar

            MacColors.divider
                .frame(height: 0.5)

            // Sub-tab content (lazy — only active tab renders)
            Group {
                switch workspace.commandSubTab {
                case .internal:
                    InternalTabView()
                case .newsfeed:
                    NewsfeedTabView()
                case .systemAlerts:
                    SystemAlertsTabView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background(MacColors.windowBackground)
        .task {
            viewModel.configure(errorState: errorState)
            await viewModel.loadAllData()
        }
        .onReceive(NotificationCenter.default.publisher(for: .hestiaServerReconnected)) { _ in
            Task { await viewModel.loadAllData() }
        }
    }

    private var subTabBar: some View {
        HStack(spacing: 0) {
            ForEach(WorkspaceState.CommandSubTab.allCases, id: \.self) { tab in
                Button {
                    withAnimation(.easeInOut(duration: 0.2)) {
                        workspace.commandSubTab = tab
                    }
                } label: {
                    VStack(spacing: 0) {
                        Text(tab.rawValue)
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(workspace.commandSubTab == tab ? MacColors.amberAccent : MacColors.textSecondary)
                            .padding(.horizontal, MacSpacing.lg)
                            .padding(.vertical, 10)

                        Rectangle()
                            .fill(workspace.commandSubTab == tab ? MacColors.amberAccent : Color.clear)
                            .frame(height: 2)
                    }
                }
                .buttonStyle(.plain)
            }
            Spacer()
        }
        .padding(.leading, MacSpacing.xxl)
    }
}
```

- [ ] **Step 3: Verify build and commit**

```bash
git add HestiaApp/macOS/Views/Command/CommandView.swift HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift
git commit -m "feat(macos): rewire CommandView with sub-tab architecture

Hero section + 3 sub-tabs (Internal, Newsfeed, System Alerts).
Lazy loading — only the active sub-tab renders and fetches data.
Hero stats populated from MacCommandCenterViewModel trading data."
```

---

## Task 6: Chat panel detach-to-window

This is the riskiest task (~8-10h). The approach: shared `MacChatViewModel` instance, new `NSWindow` created on double-click, re-docking on window close.

**Files:**
- Modify: `HestiaApp/macOS/MainSplitViewController.swift`
- Modify: `HestiaApp/macOS/Views/Chat/MacChatPanelView.swift` (if needed for environment adaptation)

- [ ] **Step 1: Validate MacChatPanelView renders in a standalone NSHostingController**

Before building the toggle/detach logic, verify the chat view can render outside the split view. Create a test by temporarily instantiating it in a standalone window. If it crashes due to missing environment objects, fix the dependencies.

- [ ] **Step 2: Add detach state tracking to WorkspaceState**

Already done in Task 1 — `isChatDetached` property exists.

- [ ] **Step 3: Add double-click detection to chat toggle**

In `IconSidebar.swift`, replace the chat toggle button action with a gesture that distinguishes single/double click:

```swift
.simultaneousGesture(
    TapGesture(count: 2).onEnded {
        NotificationCenter.default.post(name: .hestiaChatPanelDetach, object: nil)
    }
)
.simultaneousGesture(
    TapGesture(count: 1).onEnded {
        NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
    }
)
```

Add the notification name:
```swift
extension Notification.Name {
    static let hestiaChatPanelDetach = Notification.Name("hestia.chatPanel.detach")
}
```

- [ ] **Step 4: Implement detach/re-dock in MainSplitViewController**

Add a detached window controller property, create a new `NSWindow` on detach, collapse the split view chat panel, and re-dock on window close. The key: inject the same environment objects (appState, workspaceState, networkMonitor) into the new hosting controller.

- [ ] **Step 5: Handle window lifecycle**

- Register the detached window as a child of the main window
- On main window close: close detached window too
- On detached window close: set `isChatDetached = false`, uncollapse the chat split view item

- [ ] **Step 6: Verify behavior and commit**

Test all three states: panel open, panel closed, panel detached. Verify:
- Messages typed in detached window appear after re-dock
- ⌘\ toggles correctly in all states
- Closing main window closes detached window

```bash
git add HestiaApp/macOS/
git commit -m "feat(macos): add chat panel detach-to-window

Double-click sidebar chat toggle detaches panel into standalone NSWindow.
Shared MacChatViewModel instance ensures state synchronization.
Close detached window re-docks panel. Main window close cascades."
```

---

## Task 7: Cleanup and final verification

- [ ] **Step 1: Remove unused Command view files**

Delete views that are no longer referenced after the redesign:
- `HestiaApp/macOS/Views/Command/OrdersPanel.swift` (absorbed into NewsfeedTabView)
- `HestiaApp/macOS/Views/Command/NewOrderSheet.swift` (if no longer referenced)
- `HestiaApp/macOS/Views/Command/ActivityFeedView.swift` (replaced by sub-tabs)
- `HestiaApp/macOS/Views/Command/ActivityFeed.swift` (replaced by sub-tabs)

Check each for remaining references before deleting.

- [ ] **Step 2: Run full build verification**

```bash
cd HestiaApp && xcodegen generate && cd ..
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -20
```

- [ ] **Step 3: Visual QA**

Launch the app and verify:
- Sidebar: avatar top, house + brain mid, chat toggle bottom
- Command tab: hero with wavelength, stats right, 3 sub-tabs
- Internal: calendar + tasks two-column
- Newsfeed: trading + orders + investigations
- System Alerts: success/errors/atlas sections
- Memory tab: unchanged
- Settings: unchanged, accessible via avatar
- Chat panel: toggle and detach work

- [ ] **Step 4: Commit cleanup**

```bash
git add -A HestiaApp/macOS/
git commit -m "chore(macos): remove unused Command view files post-redesign"
```

---

## Implementation Notes

**Build order matters:** Task 1 must complete first (enum change is atomic). Tasks 2-5 can be parallelized if using separate worktrees. Task 6 (chat detach) is independent of Tasks 2-5.

**xcodegen:** After any file creation/deletion, run `cd HestiaApp && xcodegen generate` to regenerate the Xcode project. The project uses `project.yml` — files aren't automatically picked up.

**Testing:** No automated Swift UI tests exist. Manual visual QA is required after each task. Use the @hestia-build-validator sub-agent after each task to verify compilation.

**API types:** Tasks 3-4 reference types like `TradingSummary`, `TradingPosition`, `TradingBot`, `OrderResponse`, `InvestigationItem`. These already exist in `HestiaApp/macOS/Models/TradingModels.swift` and related model files. If any type is missing, check `HestiaApp/macOS/Models/` and `HestiaApp/Shared/Models/` for the correct definition.

**Sentinel API:** The `getSentinelStatus()` method may not exist on `APIClient` yet. If missing, add it to `APIClient+Trading.swift` or create a small `APIClient+Sentinel.swift` extension:
```swift
func getSentinelStatus() async throws -> SentinelStatusResponse {
    return try await get("/v1/sentinel/status")
}
```
