# Notion-Style Chat & Hero Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the split-view chat panel with a Notion-style floating chat overlay triggered by the profile avatar in the icon sidebar, and simplify the hero section to wavelength + stats only.

**Architecture:** The chat panel currently uses `NSSplitViewItem` in `MainSplitViewController` for a docked sidebar. We replace this with a floating `NSPanel` overlay (bottom-right of content area) as the default mode, while keeping sidebar and detached-window as opt-in modes. The hero section loses its avatar and greeting text — the wavelength fills the full header width. The greeting becomes the chat opener.

**Tech Stack:** SwiftUI, AppKit (NSPanel), NSSplitViewController, NotificationCenter bridging

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `HestiaApp/macOS/State/WorkspaceState.swift` | Modify | Add `ChatMode` enum (floating/sidebar/detached), replace boolean flags |
| `HestiaApp/macOS/Views/Chrome/IconSidebar.swift` | Modify | Replace chat toggle with profile avatar; add context menu for chat mode |
| `HestiaApp/macOS/Views/Command/HeroSection.swift` | Modify | Remove avatar + greeting, make wavelength fill full width |
| `HestiaApp/macOS/Views/Chat/FloatingChatPanel.swift` | Create | NSPanel-based floating chat window (bottom-right overlay) |
| `HestiaApp/macOS/MainSplitViewController.swift` | Modify | Add floating panel lifecycle, update toggle logic for 3 modes |
| `HestiaApp/macOS/Views/Chat/MacChatPanelView.swift` | Modify | Add greeting opener as empty-state content |
| `HestiaApp/macOS/Views/Common/ChatToggleButton.swift` | Modify | Add new notification name for chat mode switching |

---

### Task 1: Add ChatMode Enum to WorkspaceState

**Files:**
- Modify: `HestiaApp/macOS/State/WorkspaceState.swift`

- [ ] **Step 1: Add ChatMode enum and replace boolean flags**

```swift
// Add inside WorkspaceState class, after CommandSubTab enum:

enum ChatMode: String {
    case floating   // Notion-style overlay panel (default)
    case sidebar    // NSSplitViewItem docked right
    case detached   // Standalone NSWindow
    case hidden     // No chat visible
}
```

Replace the existing properties:

```swift
// REMOVE these two:
// var isChatPanelVisible: Bool { didSet { ... } }
// var isChatDetached: Bool = false

// REPLACE with:
var chatMode: ChatMode {
    didSet {
        UserDefaults.standard.set(chatMode.rawValue, forKey: WorkspaceDefaults.chatMode)
    }
}

// Convenience computed properties (backward compat for existing code)
var isChatPanelVisible: Bool {
    chatMode == .sidebar
}

var isChatDetached: Bool {
    chatMode == .detached
}

var isChatFloating: Bool {
    chatMode == .floating
}

var isChatVisible: Bool {
    chatMode != .hidden
}
```

- [ ] **Step 2: Update persistence key and init**

Add to `WorkspaceDefaults`:
```swift
static let chatMode = "hestia.workspace.chatMode"
```

Update `init()` — replace the `isChatPanelVisible` restoration block:

```swift
// Migrate from old boolean to new enum
if let savedMode = UserDefaults.standard.string(forKey: WorkspaceDefaults.chatMode),
   let mode = ChatMode(rawValue: savedMode) {
    self.chatMode = mode
} else if UserDefaults.standard.object(forKey: WorkspaceDefaults.chatPanelVisible) != nil {
    // Migration: old boolean → new enum
    let wasVisible = UserDefaults.standard.bool(forKey: WorkspaceDefaults.chatPanelVisible)
    self.chatMode = wasVisible ? .floating : .hidden
} else {
    // First launch: default to hidden (user clicks avatar to open)
    self.chatMode = .hidden
}
```

- [ ] **Step 3: Build to verify no type errors**

Run: `cd /Users/andrewlonati/hestia && xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -20`

There WILL be build errors — `isChatPanelVisible` and `isChatDetached` are now read-only computed properties instead of settable stored properties. These are fixed in Task 5 when we update `MainSplitViewController`. Note the errors and proceed to Task 2.

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/macOS/State/WorkspaceState.swift
git commit -m "refactor(state): add ChatMode enum replacing boolean chat flags"
```

---

### Task 2: Redesign HeroSection — Wavelength Full Width, No Avatar/Greeting

**Files:**
- Modify: `HestiaApp/macOS/Views/Command/HeroSection.swift`

- [ ] **Step 1: Remove avatar and greeting, expand wavelength**

Replace the entire `leftSide` and `avatar` computed properties with:

```swift
// MARK: - Wavelength Hero

private var wavelengthHero: some View {
    HestiaWavelengthView(mode: .idle, waveScale: 0.25)
        .frame(height: 40)
        .frame(maxWidth: .infinity)
        .allowsHitTesting(false)
}
```

Update the `body` to use the new property:

```swift
var body: some View {
    HStack(alignment: .center) {
        wavelengthHero
        Spacer(minLength: MacSpacing.lg)
        rightStats
    }
    .padding(.horizontal, MacSpacing.xxl)
    .padding(.vertical, MacSpacing.xl)
}
```

- [ ] **Step 2: Delete dead code**

Remove these computed properties entirely — they are no longer referenced:
- `private var leftSide: some View` (lines 20–36)
- `private var avatar: some View` (lines 39–69)
- `private var greetingText: String` (lines 132–137)

Keep `dateByline` — it's still used by `rightStats`.

- [ ] **Step 3: Build to verify HeroSection compiles**

Run: `cd /Users/andrewlonati/hestia && xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | grep -E "error:|Build Succeeded" | head -10`

Expected: HeroSection itself should compile clean. Other errors from Task 1 may still exist.

- [ ] **Step 4: Commit**

```bash
git add HestiaApp/macOS/Views/Command/HeroSection.swift
git commit -m "feat(hero): remove avatar and greeting, wavelength fills full header width"
```

---

### Task 3: Transform Icon Sidebar — Profile Avatar as Chat Trigger

**Files:**
- Modify: `HestiaApp/macOS/Views/Chrome/IconSidebar.swift`
- Modify: `HestiaApp/macOS/Views/Common/ChatToggleButton.swift`

- [ ] **Step 1: Add chat mode switch notification**

In `ChatToggleButton.swift`, add a new notification name:

```swift
static let hestiaChatModeSwitch = Notification.Name("hestia.chatPanel.modeSwitch")
```

- [ ] **Step 2: Replace chatToggleButton with profile avatar chat trigger**

In `IconSidebar.swift`, replace the `chatToggleButton` computed property (lines 149–186) with:

```swift
// MARK: - Chat Avatar (bottom, Notion-style AI chat trigger)

private var chatAvatarButton: some View {
    let isActive = workspace.isChatVisible

    return ZStack {
        // Avatar circle with gradient (same style as old hero avatar)
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

        if let image = appState.currentMode.avatarImage {
            image
                .resizable()
                .scaledToFill()
                .frame(width: 30, height: 30)
                .clipShape(Circle())
        } else {
            Text(appState.currentMode.displayName.prefix(1))
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(MacColors.amberAccent)
        }

        Circle()
            .strokeBorder(
                isActive ? MacColors.amberAccent : (hoveredChat ? MacColors.avatarBorder : MacColors.avatarBorder.opacity(0.5)),
                lineWidth: isActive ? 1.5 : 1
            )
    }
    .frame(width: MacSize.navIconButton, height: MacSize.navIconButton)
    .opacity(hoveredChat && !isActive ? 0.85 : 1.0)
    .contentShape(Circle())
    .onTapGesture {
        NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
    }
    .onHover { hovering in
        withAnimation(.easeInOut(duration: MacAnimation.fast)) {
            hoveredChat = hovering
        }
    }
    .contextMenu {
        Button {
            NotificationCenter.default.post(
                name: .hestiaChatModeSwitch,
                object: nil,
                userInfo: ["mode": "floating"]
            )
        } label: {
            Label("Floating", systemImage: "rectangle.bottomhalf.inset.filled")
        }

        Button {
            NotificationCenter.default.post(
                name: .hestiaChatModeSwitch,
                object: nil,
                userInfo: ["mode": "sidebar"]
            )
        } label: {
            Label("Sidebar", systemImage: "sidebar.trailing")
        }

        Button {
            NotificationCenter.default.post(
                name: .hestiaChatModeSwitch,
                object: nil,
                userInfo: ["mode": "detached"]
            )
        } label: {
            Label("Detach to Window", systemImage: "rectangle.portrait.on.rectangle.portrait")
        }
    }
    .accessibilityLabel(isActive ? "Hide Chat" : "Open Chat")
    .accessibilityHint("Click to toggle. Right-click for chat mode options.")
    .hoverCursor()
}
```

- [ ] **Step 3: Add appState dependency to IconSidebar**

IconSidebar needs `appState` for the avatar image. Add at the top of the struct:

```swift
@EnvironmentObject var appState: AppState
```

- [ ] **Step 4: Update body to use chatAvatarButton**

In the `body` property, replace `chatToggleButton` with `chatAvatarButton`:

```swift
// Chat avatar (bottom, sticky — Notion-style AI chat trigger)
chatAvatarButton
    .padding(.bottom, MacSpacing.xxl)
```

- [ ] **Step 5: Remove the old chatToggleButton property entirely**

Delete the old `chatToggleButton` computed property that was replaced in Step 2.

- [ ] **Step 6: Commit**

```bash
git add HestiaApp/macOS/Views/Chrome/IconSidebar.swift HestiaApp/macOS/Views/Common/ChatToggleButton.swift
git commit -m "feat(sidebar): replace chat toggle with profile avatar, add chat mode context menu"
```

---

### Task 4: Create FloatingChatPanel (NSPanel Overlay)

**Files:**
- Create: `HestiaApp/macOS/Views/Chat/FloatingChatPanel.swift`

- [ ] **Step 1: Create the FloatingChatPanel class**

This is an `NSPanel` subclass that renders as a floating overlay anchored to the bottom-right of the main window. It's NOT a child window — it's drawn as part of the content area via SwiftUI overlay.

Actually, the cleanest approach for a floating panel inside the SwiftUI content area is a **SwiftUI overlay**, not an NSPanel. This avoids fighting the AppKit split view system and keeps it simple.

Create `HestiaApp/macOS/Views/Chat/FloatingChatPanel.swift`:

```swift
import SwiftUI
import HestiaShared

struct FloatingChatOverlay: View {
    @Environment(WorkspaceState.self) private var workspace
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var networkMonitor: NetworkMonitor
    @State private var overlaySize = CGSize(width: 400, height: 520)
    @State private var isHoveredClose = false

    var body: some View {
        VStack(spacing: 0) {
            // Header bar
            floatingHeader

            MacColors.divider.frame(height: 0.5)

            // Chat content (reuse existing chat view)
            MacChatPanelView()
                .environmentObject(appState)
                .environmentObject(networkMonitor)
        }
        .frame(width: overlaySize.width, height: overlaySize.height)
        .background(floatingBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.panelBorder.opacity(0.4), lineWidth: 1)
        }
        .shadow(color: .black.opacity(0.4), radius: 20, x: 0, y: 8)
        .padding(.trailing, MacSpacing.lg)
        .padding(.bottom, MacSpacing.lg)
        .transition(.asymmetric(
            insertion: .scale(scale: 0.9, anchor: .bottomTrailing).combined(with: .opacity),
            removal: .scale(scale: 0.95, anchor: .bottomTrailing).combined(with: .opacity)
        ))
    }

    // MARK: - Header

    private var floatingHeader: some View {
        HStack {
            Text("Hestia")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(MacColors.textPrimary)

            Spacer()

            // Mode switcher buttons
            Button {
                NotificationCenter.default.post(
                    name: .hestiaChatModeSwitch,
                    object: nil,
                    userInfo: ["mode": "sidebar"]
                )
            } label: {
                Image(systemName: "sidebar.trailing")
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.hestiaIcon)
            .help("Dock as sidebar")

            Button {
                NotificationCenter.default.post(
                    name: .hestiaChatModeSwitch,
                    object: nil,
                    userInfo: ["mode": "detached"]
                )
            } label: {
                Image(systemName: "rectangle.portrait.on.rectangle.portrait")
                    .font(.system(size: 11))
                    .foregroundStyle(MacColors.textSecondary)
            }
            .buttonStyle(.hestiaIcon)
            .help("Detach to window")

            Button {
                withAnimation(MacAnimation.fastSpring) {
                    workspace.chatMode = .hidden
                }
            } label: {
                Image(systemName: "minus")
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(isHoveredClose ? MacColors.amberAccent : MacColors.textSecondary)
            }
            .buttonStyle(.hestiaIcon)
            .onHover { isHoveredClose = $0 }
            .help("Minimize chat")
        }
        .padding(.horizontal, MacSpacing.md)
        .padding(.vertical, MacSpacing.sm)
    }

    // MARK: - Background

    private var floatingBackground: some View {
        ZStack {
            MacColors.windowBackground
            MacColors.panelBackground.opacity(0.5)
        }
    }
}
```

- [ ] **Step 2: Commit**

```bash
git add HestiaApp/macOS/Views/Chat/FloatingChatPanel.swift
git commit -m "feat(chat): add FloatingChatOverlay for Notion-style floating chat panel"
```

---

### Task 5: Wire Up MainSplitViewController for 3 Chat Modes

**Files:**
- Modify: `HestiaApp/macOS/MainSplitViewController.swift`

- [ ] **Step 1: Add mode switch observer**

In `viewDidLoad()`, after the existing `detachObserver` setup (line 136), add:

```swift
// Bridge: SwiftUI chat mode switch → AppKit panel management
NotificationCenter.default.addObserver(
    forName: .hestiaChatModeSwitch,
    object: nil,
    queue: .main
) { [weak self] notification in
    guard let modeString = notification.userInfo?["mode"] as? String,
          let mode = WorkspaceState.ChatMode(rawValue: modeString) else { return }
    self?.switchChatMode(to: mode)
}
```

- [ ] **Step 2: Add switchChatMode method**

Add below `toggleChatPanel()`:

```swift
// MARK: - Chat Mode Switching

func switchChatMode(to mode: WorkspaceState.ChatMode) {
    let currentMode = workspaceState.chatMode

    // Tear down current mode
    switch currentMode {
    case .sidebar:
        if chatItem != nil && !chatItem.isCollapsed {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.25
                context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
                chatItem.animator().isCollapsed = true
            }
        }
    case .detached:
        detachedChatWindow?.close()
        detachedChatWindow = nil
    case .floating, .hidden:
        break // SwiftUI overlay handles its own visibility
    }

    // Set up new mode
    switch mode {
    case .floating, .hidden:
        // SwiftUI overlay reads workspaceState.chatMode directly
        break
    case .sidebar:
        if chatItem != nil {
            NSAnimationContext.runAnimationGroup { context in
                context.duration = 0.25
                context.timingFunction = CAMediaTimingFunction(name: .easeInEaseOut)
                chatItem.animator().isCollapsed = false
            }
        }
    case .detached:
        detachChatPanel()
        return // detachChatPanel sets state internally
    }

    workspaceState.chatMode = mode
}
```

- [ ] **Step 3: Update toggleChatPanel to use ChatMode**

Replace the existing `toggleChatPanel()` method:

```swift
func toggleChatPanel() {
    guard chatItem != nil else { return }

    // If detached, bring the detached window to front
    if workspaceState.chatMode == .detached, let window = detachedChatWindow {
        window.makeKeyAndOrderFront(nil)
        return
    }

    // Toggle: if any chat is visible, hide it. If hidden, open floating.
    if workspaceState.isChatVisible {
        switchChatMode(to: .hidden)
    } else {
        // Restore last non-hidden mode, default to floating
        let lastMode = UserDefaults.standard.string(forKey: "hestia.workspace.lastChatMode")
            .flatMap { WorkspaceState.ChatMode(rawValue: $0) } ?? .floating
        switchChatMode(to: lastMode == .hidden ? .floating : lastMode)
    }
}
```

- [ ] **Step 4: Update detachChatPanel to set chatMode**

In the existing `detachChatPanel()` method, replace:
```swift
// REMOVE:
workspaceState.isChatDetached = true
workspaceState.isChatPanelVisible = false

// REPLACE with:
workspaceState.chatMode = .detached
```

- [ ] **Step 5: Update windowWillClose to set chatMode**

In the existing `windowWillClose(_:)` method, replace:
```swift
// REMOVE:
workspaceState.isChatDetached = false
// ...
workspaceState.isChatPanelVisible = true

// REPLACE with (the full method):
func windowWillClose(_ notification: Notification) {
    guard let closingWindow = notification.object as? NSWindow,
          closingWindow === detachedChatWindow else { return }

    detachedChatWindow = nil

    // Re-dock: open as floating (not sidebar — less disruptive)
    workspaceState.chatMode = .floating
}
```

- [ ] **Step 6: Update viewDidLoad panel restore logic**

Replace the initial panel state restoration (lines 114–117):

```swift
// Restore persisted chat mode
if workspaceState.chatMode != .sidebar {
    chatItem.isCollapsed = true
}
```

- [ ] **Step 7: Store observer reference and clean up in deinit**

Store the new observer:
```swift
private nonisolated(unsafe) var modeSwitchObserver: NSObjectProtocol?
```

In `deinit`, add:
```swift
if let observer = modeSwitchObserver {
    NotificationCenter.default.removeObserver(observer)
}
```

- [ ] **Step 8: Commit**

```bash
git add HestiaApp/macOS/MainSplitViewController.swift
git commit -m "feat(chat): wire 3-mode chat switching (floating/sidebar/detached)"
```

---

### Task 6: Add Floating Overlay to WorkspaceRootView

**Files:**
- Modify: `HestiaApp/macOS/Views/WorkspaceRootView.swift`

- [ ] **Step 1: Read WorkspaceRootView.swift**

Read the current file to understand the exact structure before editing.

- [ ] **Step 2: Add floating chat overlay**

In WorkspaceRootView's `body`, add an overlay to the main content `ZStack` — this positions the floating chat in the bottom-right of the content area (not the full window, so it doesn't cover the icon sidebar):

After the main `HStack` containing `IconSidebar()` and the tab content `ZStack`, add an overlay:

```swift
.overlay(alignment: .bottomTrailing) {
    if workspace.chatMode == .floating {
        FloatingChatOverlay()
            .environment(workspace)
            .environmentObject(appState) // AppState is already in environment
            .environmentObject(networkMonitor) // add if not already available
    }
}
```

The overlay goes on the content `ZStack` (the part to the right of `IconSidebar`), NOT on the outermost container — so the floating panel sits over the content area but doesn't obscure the icon sidebar.

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/macOS/Views/WorkspaceRootView.swift
git commit -m "feat(chat): render floating chat overlay in content area"
```

---

### Task 7: Add Greeting as Chat Opener

**Files:**
- Modify: `HestiaApp/macOS/Views/Chat/MacChatPanelView.swift`

- [ ] **Step 1: Add empty-state greeting**

In `MacChatPanelView`, add a greeting view that shows when there are no messages. Insert it inside the `ScrollView`, before the `LazyVStack`:

```swift
// Empty state — greeting opener
if viewModel.messages.isEmpty && !viewModel.isLoading {
    VStack(spacing: MacSpacing.lg) {
        Spacer()

        if let image = appState.currentMode.avatarImage {
            image
                .resizable()
                .scaledToFill()
                .frame(width: 48, height: 48)
                .clipShape(Circle())
                .overlay {
                    Circle().strokeBorder(MacColors.amberAccent.opacity(0.5), lineWidth: 1)
                }
        }

        Text(chatGreeting)
            .font(.system(size: 18, weight: .semibold))
            .foregroundStyle(MacColors.textPrimaryAlt)

        Text("What can I help you with?")
            .font(.system(size: 13))
            .foregroundStyle(MacColors.textSecondary)

        Spacer()
    }
    .frame(maxWidth: .infinity, maxHeight: .infinity)
    .padding(.horizontal, MacSpacing.xxl)
}
```

- [ ] **Step 2: Add chatGreeting computed property**

Add at the bottom of `MacChatPanelView`:

```swift
// MARK: - Greeting

private var chatGreeting: String {
    let hour = Calendar.current.component(.hour, from: Date())
    if hour < 12 { return "Good morning, Andrew" }
    else if hour < 17 { return "Good afternoon, Andrew" }
    else { return "Good evening, Andrew" }
}
```

- [ ] **Step 3: Commit**

```bash
git add HestiaApp/macOS/Views/Chat/MacChatPanelView.swift
git commit -m "feat(chat): add greeting opener as empty-state content"
```

---

### Task 8: Build Verification & Cleanup

**Files:**
- All modified files

- [ ] **Step 1: Full macOS build**

Run: `cd /Users/andrewlonati/hestia && xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | grep -E "error:|warning:|Build Succeeded" | head -20`

Expected: `Build Succeeded`

- [ ] **Step 2: Fix any remaining compiler errors**

Common issues to watch for:
- Any code still trying to SET `isChatPanelVisible` or `isChatDetached` (now read-only computed properties) — these need to set `chatMode` instead
- Missing `appState` environment object injection where `IconSidebar` is used
- `FloatingChatOverlay` not added to the Xcode target

Search for remaining assignments: `grep -rn "isChatPanelVisible =" HestiaApp/` and `grep -rn "isChatDetached =" HestiaApp/` — all results should be in `WorkspaceState.swift` only (the computed property definitions). Any others need to be changed to `chatMode = .sidebar` / `chatMode = .detached` etc.

- [ ] **Step 3: iOS build check**

Run: `cd /Users/andrewlonati/hestia && xcodebuild -project HestiaApp/HestiaApp.xcodeproj -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build 2>&1 | grep -E "error:|Build Succeeded" | head -10`

`FloatingChatOverlay` and the modified `HeroSection` should NOT affect iOS (they're macOS-only files). Verify no shared file was broken.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git commit -m "fix(chat): resolve build errors from chat mode refactor"
```

---

## Architecture Notes for Implementer

### Why SwiftUI overlay instead of NSPanel?

An `NSPanel` floating window would work but creates complexity:
- Needs to track main window position/resize to stay anchored
- Z-ordering issues with other windows
- Can't use SwiftUI environment objects without bridging

A SwiftUI `.overlay(alignment: .bottomTrailing)` gives us:
- Automatic positioning relative to content area
- Full access to environment objects
- No AppKit bridging needed
- Built-in animation support

### Chat mode state flow

```
User clicks avatar → .hestiaChatPanelToggle notification
                    → MainSplitViewController.toggleChatPanel()
                    → switchChatMode(to: .floating or .hidden)
                    → workspaceState.chatMode updated
                    → SwiftUI overlay observes change, shows/hides FloatingChatOverlay

User right-clicks avatar → context menu
                         → .hestiaChatModeSwitch notification with mode string
                         → MainSplitViewController.switchChatMode(to:)
                         → tears down current mode, sets up new mode
```

### Backward compatibility

The computed properties `isChatPanelVisible`, `isChatDetached`, `isChatFloating`, `isChatVisible` maintain read compatibility. Any code that was READING these properties still works. Only code that was SETTING them needs to change to use `chatMode = ...`.

### What's NOT changing

- `MacChatPanelView` internals (messages, input bar, streaming)
- `MacChatViewModel` (all chat logic)
- Detached window flow (just triggered differently)
- Keyboard shortcut `Cmd+\` (still posts `.hestiaChatPanelToggle`)
