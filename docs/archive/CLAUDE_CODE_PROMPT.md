# HestiaApp Phase 6b - Claude Code Execution Prompt

**Date**: January 13, 2026
**Source**: Principal Engineering Review (2026-01-13)
**Project**: HestiaApp iOS Application
**Architecture**: MVVM + SwiftUI
**Target**: iOS 16+ (Core Data for persistence)

---

## Executive Context

You are a Principal-level full stack developer implementing critical fixes for HestiaApp, a SwiftUI iOS application that serves as a personal AI assistant interface. A comprehensive engineering review has identified blocking issues that prevent calendar and reminders functionality from working.

**Critical Finding**: The iOS app cannot access calendar or reminders because the Xcode project is missing an entitlements file. The CLI tools work correctly on macOS because they access the system EventKit store, but the iOS Simulator has its own isolated database AND lacks the required entitlements.

---

## Project Location

```
/path/to/hestia/HestiaApp/
├── HestiaApp.xcodeproj/       # Xcode project (needs entitlements added)
├── Shared/
│   ├── App/                   # App entry, state management
│   ├── DesignSystem/          # Colors, Typography, Spacing, Animations
│   ├── Models/                # Data models (CalendarEvent.swift exists)
│   ├── Services/              # CalendarService.swift exists, needs RemindersService
│   ├── ViewModels/            # MVVM view models
│   ├── Views/
│   │   ├── Chat/              # Chat interface
│   │   ├── CommandCenter/     # Dashboard widgets (NextMeetingCard.swift)
│   │   ├── Common/            # Shared components
│   │   ├── Memory/            # Memory review
│   │   └── Settings/          # Settings views
│   ├── Persistence/           # Core Data stack
│   └── Utilities/             # Extensions, Constants
└── iOS/
    ├── Info.plist             # Has legacy keys, needs iOS 17+ keys
    └── Assets.xcassets/       # Images, colors
```

---

## Task Execution Order

Execute these tasks in strict sequence. Each task builds on the previous one.

---

## TASK 1: Create iOS Entitlements File [CRITICAL - BLOCKING]

**Priority**: P0 - This blocks ALL calendar/reminders functionality
**Estimated Time**: 5 minutes
**Files to Create**: `HestiaApp/iOS/HestiaApp.entitlements`

### Problem Statement

The Xcode project has NO entitlements file. Without this:
- `EKEventStore.authorizationStatus(for: .event)` returns `.notDetermined` perpetually
- `requestFullAccessToEvents()` returns `false` without prompting user
- CalendarService.swift cannot ever receive authorization

### Implementation

Create file at `HestiaApp/iOS/HestiaApp.entitlements`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.personal-information.calendars</key>
    <true/>
    <key>com.apple.security.personal-information.reminders</key>
    <true/>
</dict>
</plist>
```

### Xcode Project Update

The `project.pbxproj` file must be updated to:
1. Add the entitlements file to the project
2. Reference it in the build settings under `CODE_SIGN_ENTITLEMENTS`

Add to the HestiaApp target build settings:
```
CODE_SIGN_ENTITLEMENTS = iOS/HestiaApp.entitlements
```

### Verification

After implementation:
1. Open Xcode project
2. Select HestiaApp target
3. Go to "Signing & Capabilities" tab
4. Verify "Calendars" and "Reminders" capabilities appear
5. If not visible, click "+" and add them manually

---

## TASK 2: Add iOS 17+ Info.plist Keys [HIGH]

**Priority**: P1 - Required for iOS 17+ devices
**Estimated Time**: 5 minutes
**Files to Modify**: `HestiaApp/iOS/Info.plist`

### Problem Statement

iOS 17 changed the EventKit authorization model:
- iOS 16 and earlier: `requestAccess(to: .event)` with `NSCalendarsUsageDescription`
- iOS 17+: `requestFullAccessToEvents()` with `NSCalendarsFullAccessUsageDescription`

The current Info.plist only has the legacy iOS 16 keys. iOS 17+ devices will not show the authorization prompt.

### Current State

```xml
<key>NSCalendarsUsageDescription</key>
<string>Hestia needs calendar access to show your upcoming events and help manage your schedule.</string>
<key>NSRemindersUsageDescription</key>
<string>Hestia needs reminders access to help you manage tasks and to-dos.</string>
```

### Required Addition

Add these keys to Info.plist (keep the existing keys for iOS 16 compatibility):

```xml
<key>NSCalendarsFullAccessUsageDescription</key>
<string>Hestia needs full calendar access to show your upcoming events, create new events, and help manage your schedule.</string>
<key>NSRemindersFullAccessUsageDescription</key>
<string>Hestia needs full reminders access to show your tasks, create new reminders, and help you stay organized.</string>
```

### Implementation

Edit `HestiaApp/iOS/Info.plist` to add the new keys after the existing calendar/reminders keys.

---

## TASK 3: Create RemindersService [MEDIUM]

**Priority**: P2 - Backend supports reminders, iOS app doesn't expose them
**Estimated Time**: 30 minutes
**Files to Create**: `HestiaApp/Shared/Services/RemindersService.swift`
**Files to Reference**: `HestiaApp/Shared/Services/CalendarService.swift` (use as template)

### Problem Statement

The backend has full reminders support via `hestia-reminders-cli`, but the iOS app has no corresponding service to display or interact with reminders.

### Implementation

Create `RemindersService.swift` mirroring the `CalendarService.swift` pattern:

```swift
import Foundation
import EventKit
import Combine

/// Service for accessing device reminders via EventKit
@MainActor
class RemindersService: ObservableObject {
    // MARK: - Published State

    @Published private(set) var isAuthorized = false
    @Published private(set) var isLoading = false
    @Published private(set) var pendingReminders: [ReminderItem] = []
    @Published private(set) var error: Error?

    // MARK: - Private

    private let eventStore = EKEventStore()
    private var refreshTimer: Timer?

    // MARK: - Initialization

    init() {
        checkAuthorizationStatus()
    }

    // MARK: - Authorization

    private func checkAuthorizationStatus() {
        let status = EKEventStore.authorizationStatus(for: .reminder)
        isAuthorized = (status == .fullAccess || status == .authorized)
    }

    func requestAccess() async -> Bool {
        do {
            if #available(iOS 17.0, *) {
                let granted = try await eventStore.requestFullAccessToReminders()
                await MainActor.run { isAuthorized = granted }
                return granted
            } else {
                let granted = try await eventStore.requestAccess(to: .reminder)
                await MainActor.run { isAuthorized = granted }
                return granted
            }
        } catch {
            await MainActor.run { self.error = error }
            return false
        }
    }

    // MARK: - Fetch Reminders

    func fetchPendingReminders(from lists: [String]? = nil) async -> [ReminderItem] {
        guard isAuthorized else { return [] }

        await MainActor.run { isLoading = true }
        defer { Task { @MainActor in isLoading = false } }

        let calendars: [EKCalendar]?
        if let listNames = lists {
            calendars = eventStore.calendars(for: .reminder).filter { listNames.contains($0.title) }
        } else {
            calendars = eventStore.calendars(for: .reminder)
        }

        let predicate = eventStore.predicateForIncompleteReminders(
            withDueDateStarting: nil,
            ending: nil,
            calendars: calendars
        )

        return await withCheckedContinuation { continuation in
            eventStore.fetchReminders(matching: predicate) { reminders in
                let items = (reminders ?? []).map { reminder in
                    ReminderItem(
                        id: reminder.calendarItemIdentifier,
                        title: reminder.title ?? "Untitled",
                        dueDate: reminder.dueDateComponents?.date,
                        priority: ReminderPriority(from: reminder.priority),
                        listName: reminder.calendar?.title ?? "Unknown",
                        notes: reminder.notes,
                        isCompleted: reminder.isCompleted
                    )
                }
                .sorted { ($0.dueDate ?? .distantFuture) < ($1.dueDate ?? .distantFuture) }

                Task { @MainActor in
                    self.pendingReminders = items
                }
                continuation.resume(returning: items)
            }
        }
    }

    // MARK: - Auto Refresh

    func startAutoRefresh(interval: TimeInterval = 300) {
        stopAutoRefresh()
        refreshTimer = Timer.scheduledTimer(withTimeInterval: interval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                _ = await self?.fetchPendingReminders()
            }
        }
    }

    func stopAutoRefresh() {
        refreshTimer?.invalidate()
        refreshTimer = nil
    }

    func setup() {
        checkAuthorizationStatus()
    }
}

// MARK: - Reminder Model

struct ReminderItem: Identifiable, Codable {
    let id: String
    let title: String
    let dueDate: Date?
    let priority: ReminderPriority
    let listName: String
    let notes: String?
    let isCompleted: Bool

    var formattedDueDate: String? {
        guard let date = dueDate else { return nil }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }

    var isOverdue: Bool {
        guard let date = dueDate else { return false }
        return date < Date() && !isCompleted
    }
}

enum ReminderPriority: Int, Codable {
    case none = 0
    case high = 1
    case medium = 5
    case low = 9

    init(from ekPriority: Int) {
        switch ekPriority {
        case 1...4: self = .high
        case 5: self = .medium
        case 6...9: self = .low
        default: self = .none
        }
    }

    var displayName: String {
        switch self {
        case .none: return ""
        case .high: return "High"
        case .medium: return "Medium"
        case .low: return "Low"
        }
    }
}
```

### Integration Points

After creating the service:
1. Add to `CommandCenterViewModel.swift` (similar to CalendarService integration)
2. Create `RemindersWidget.swift` in CommandCenter/Widgets/
3. Wire up to display pending reminders in CommandCenter

---

## TASK 4: Update CalendarService for iOS 17+ [HIGH]

**Priority**: P1 - Ensure compatibility with iOS 17+ authorization model
**Estimated Time**: 15 minutes
**Files to Modify**: `HestiaApp/Shared/Services/CalendarService.swift`

### Problem Statement

Verify CalendarService.swift properly handles both iOS 16 and iOS 17+ authorization APIs.

### Verification Checklist

1. Check `requestAccess()` method uses `#available(iOS 17.0, *)` to call correct API
2. Ensure `requestFullAccessToEvents()` is used for iOS 17+
3. Ensure `requestAccess(to: .event)` is used for iOS 16 fallback
4. Verify authorization status check handles both `.fullAccess` and `.authorized`

### Expected Pattern

```swift
func requestAccess() async -> Bool {
    do {
        if #available(iOS 17.0, *) {
            let granted = try await eventStore.requestFullAccessToEvents()
            await MainActor.run { isAuthorized = granted }
            return granted
        } else {
            let granted = try await eventStore.requestAccess(to: .event)
            await MainActor.run { isAuthorized = granted }
            return granted
        }
    } catch {
        await MainActor.run { self.error = error }
        return false
    }
}

private func checkAuthorizationStatus() {
    let status = EKEventStore.authorizationStatus(for: .event)
    // iOS 17 returns .fullAccess, iOS 16 returns .authorized
    isAuthorized = (status == .fullAccess || status == .authorized)
}
```

---

## TASK 5: Fix Color Scheme Persistence [LOW]

**Priority**: P3 - UI polish
**Estimated Time**: 30 minutes
**Files to Modify**:
- `HestiaApp/Shared/Views/CommandCenter/CommandCenterView.swift`
- `HestiaApp/Shared/Views/Settings/SettingsView.swift`
- `HestiaApp/Shared/App/ContentView.swift`

### Problem Statement

Mode gradient colors only appear in ChatView. CommandCenter and Settings use a static background instead of the mode-specific gradient.

### Implementation

1. Pass `currentMode` from `AppState` to CommandCenterView and SettingsView
2. Use `GradientBackground(mode: currentMode)` as the view background
3. Ensure mode changes propagate via `@EnvironmentObject` or binding

### Example Fix for CommandCenterView

```swift
struct CommandCenterView: View {
    @EnvironmentObject var appState: AppState
    @StateObject private var viewModel = CommandCenterViewModel()

    var body: some View {
        ZStack {
            // Use mode-specific gradient instead of static background
            GradientBackground(mode: appState.currentMode)
                .ignoresSafeArea()

            // Existing content...
            ScrollView {
                // widgets...
            }
        }
    }
}
```

---

## TASK 6: Verify Xcode Project Configuration [VERIFICATION]

**Priority**: P0 - Must verify after Tasks 1-2
**Estimated Time**: 10 minutes

### Manual Verification Steps

After implementing Tasks 1 and 2, perform these manual checks in Xcode:

1. **Open Project**: Open `HestiaApp.xcodeproj` in Xcode
2. **Select Target**: Click on "HestiaApp" target in the project navigator
3. **Check Signing & Capabilities**:
   - Go to "Signing & Capabilities" tab
   - Verify "Calendars" capability is present
   - Verify "Reminders" capability is present
   - If missing, click "+" and add them
4. **Check Build Settings**:
   - Go to "Build Settings" tab
   - Search for "entitlements"
   - Verify `CODE_SIGN_ENTITLEMENTS` points to `iOS/HestiaApp.entitlements`
5. **Check Info.plist**:
   - Expand the target and find Info.plist
   - Verify all four calendar/reminders keys are present:
     - `NSCalendarsUsageDescription` (iOS 16)
     - `NSCalendarsFullAccessUsageDescription` (iOS 17+)
     - `NSRemindersUsageDescription` (iOS 16)
     - `NSRemindersFullAccessUsageDescription` (iOS 17+)

### Clean Build

After verification:
```
Cmd+Shift+K (Clean Build Folder)
Cmd+B (Build)
```

### Simulator Reset (if needed)

If authorization state is stuck:
1. In Simulator menu: Device → Erase All Content and Settings
2. Rebuild and run

---

## Testing Strategy

### Simulator Testing (Limited)

The iOS Simulator has its own isolated EventKit database. Even with proper entitlements:
- Calendar will be EMPTY (no events)
- Reminders will be EMPTY (no lists)

To test in Simulator:
1. Open Simulator's Calendar app
2. Manually add test events
3. Open Simulator's Reminders app
4. Manually add test reminders
5. Return to HestiaApp and verify it can read them

### Physical Device Testing (Recommended)

For real calendar/reminder data:
1. Connect physical iPhone/iPad
2. Select device as build target
3. Build and run
4. Grant calendar/reminders permissions when prompted
5. Verify real iCloud calendars appear

---

## Success Criteria

After completing all tasks:

1. **Entitlements**: Project has valid entitlements file with calendar + reminders capabilities
2. **Info.plist**: Contains all four privacy keys (iOS 16 + iOS 17 variants)
3. **Authorization**: App can successfully request and receive EventKit authorization
4. **Calendar Access**: NextMeetingCard displays real calendar events (on physical device)
5. **Reminders Access**: RemindersService can fetch pending reminders (on physical device)
6. **Mode Theming**: Gradient backgrounds appear consistently across all views

---

## Reference Files

These existing files provide patterns to follow:

- `HestiaApp/Shared/Services/CalendarService.swift` - EventKit calendar integration
- `HestiaApp/Shared/Models/CalendarEvent.swift` - Calendar event model
- `HestiaApp/Shared/Views/CommandCenter/Widgets/NextMeetingCard.swift` - Calendar UI
- `HestiaApp/Shared/ViewModels/CommandCenterViewModel.swift` - ViewModel pattern
- `HestiaApp/iOS/Info.plist` - Current privacy keys

---

## Documentation References

- `docs/phase-6-gaps.md` - Updated gap analysis with entitlements issue
- `docs/ui-data-models.md` - Frontend data structures
- `docs/api-contract.md` - REST API specification
- `CLAUDE.md` - Project context and session log

---

## Notes for Claude Code

1. **Do not skip the entitlements file** - This is the root cause of all calendar/reminders failures
2. **Test on physical device** - Simulator has empty EventKit database
3. **Keep both iOS 16 and iOS 17 keys** - Need backward compatibility
4. **Follow existing patterns** - CalendarService.swift is the template for RemindersService
5. **Verify in Xcode** - The pbxproj changes must result in visible capabilities in Xcode UI
