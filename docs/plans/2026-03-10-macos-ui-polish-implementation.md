# macOS UI Polish Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modernize the Hestia macOS chat panel toggle and input bar to match Claude Desktop's clean UI patterns.

**Architecture:** Three independent visual changes to the macOS SwiftUI layer — a floating sidebar toggle overlay, simplified input bar, and avatar-free message bubbles. All changes are cosmetic (no backend, no data model changes). The NSSplitViewController plumbing and Notification-based chat toggle mechanism are preserved.

**Tech Stack:** Swift 6.1, SwiftUI, AppKit (NSTextView wrapper), xcodegen (project.yml)

**Design Doc:** `docs/plans/2026-03-10-macos-ui-polish-design.md`

---

### Task 1: Create ChatPanelToggleOverlay

**Files:**
- Create: `HestiaApp/macOS/Views/Chrome/ChatPanelToggleOverlay.swift`

**Step 1: Create the new overlay view**

```swift
import SwiftUI
import HestiaShared

/// Floating toggle button at the bottom-right of the main content area.
/// Always visible — shows/hides the right chat panel via notification.
struct ChatPanelToggleOverlay: View {
    @Environment(WorkspaceState.self) private var workspace
    @State private var isHovered = false

    private var isVisible: Bool { workspace.isChatPanelVisible }

    var body: some View {
        Button {
            NotificationCenter.default.post(name: .hestiaChatPanelToggle, object: nil)
        } label: {
            Image(systemName: isVisible ? "sidebar.trailing" : "sidebar.trailing")
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(isHovered ? MacColors.amberAccent : MacColors.textSecondary)
                .frame(width: 28, height: 28)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(isHovered ? MacColors.activeNavBackground : MacColors.windowBackground.opacity(0.8))
                )
                .overlay {
                    RoundedRectangle(cornerRadius: 6)
                        .strokeBorder(MacColors.sidebarBorder, lineWidth: 0.5)
                }
        }
        .buttonStyle(.hestiaIcon)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                isHovered = hovering
            }
        }
        .help(isVisible ? "Hide right sidebar (⌘\\)" : "Show right sidebar (⌘\\)")
        .accessibilityLabel(isVisible ? "Hide chat panel" : "Show chat panel")
        .accessibilityHint("Keyboard shortcut: Command backslash")
        .hoverCursor()
        .padding(MacSpacing.md)
    }
}
```

**Step 2: Verify it compiles in isolation**

Run: `cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED (the file will be auto-discovered by xcodegen's macOS source group)

Note: If xcodegen needs regeneration first, run `xcodegen generate` from `HestiaApp/`.

**Step 3: Commit**

```bash
git add HestiaApp/macOS/Views/Chrome/ChatPanelToggleOverlay.swift
git commit -m "feat(macOS): add ChatPanelToggleOverlay view"
```

---

### Task 2: Wire overlay into WorkspaceRootView + remove sidebar toggle

**Files:**
- Modify: `HestiaApp/macOS/Views/WorkspaceRootView.swift:19-41` (content area ZStack)
- Modify: `HestiaApp/macOS/Views/Chrome/IconSidebar.swift:31-33` (remove SidebarChatToggle)

**Step 1: Add overlay to the content area in WorkspaceRootView**

In `WorkspaceRootView.swift`, the content area is the inner `ZStack(alignment: .top)` at line 20. Add a `.overlay(alignment: .bottomTrailing)` with the new toggle after the environment modifier on line 40:

Replace lines 20-41 (the inner ZStack through `.animation(...)`) with:

```swift
                    // Center: Content area (flex)
                    ZStack(alignment: .top) {
                        Group {
                            switch workspace.currentView {
                            case .command:
                                CommandView()
                            case .health:
                                HealthView()
                            case .research:
                                ResearchView()
                            case .explorer:
                                ExplorerView()
                            case .settings:
                                MacSettingsView()
                            }
                        }
                        .frame(maxWidth: .infinity, maxHeight: .infinity)

                        // Global error banner overlay
                        GlobalErrorBanner()
                    }
                    .overlay(alignment: .bottomTrailing) {
                        ChatPanelToggleOverlay()
                    }
                    .environment(\.layoutMode, layoutMode)
                    .animation(.hestiaNavSwitch, value: workspace.currentView)
```

**Step 2: Remove SidebarChatToggle from IconSidebar**

In `IconSidebar.swift`, remove lines 31-33:

```swift
            // Chat panel toggle (always visible at sidebar bottom)
            SidebarChatToggle()
                .padding(.bottom, MacSpacing.xxl)
```

The settings button at the bottom (line 28-29) becomes the last item before the closing `}` of the VStack. Adjust its bottom padding from `.lg` to `.xxl` to maintain visual balance:

Replace line 29:
```swift
                .padding(.bottom, MacSpacing.lg)
```
With:
```swift
                .padding(.bottom, MacSpacing.xxl)
```

**Step 3: Build and verify**

Run: `cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

**Step 4: Commit**

```bash
git add HestiaApp/macOS/Views/WorkspaceRootView.swift HestiaApp/macOS/Views/Chrome/IconSidebar.swift
git commit -m "feat(macOS): wire ChatPanelToggleOverlay, remove sidebar chat toggle"
```

---

### Task 3: Simplify MacMessageInputBar

**Files:**
- Modify: `HestiaApp/macOS/Views/Chat/MacMessageInputBar.swift` (major simplification)

**Step 1: Remove terminal button, prompt char, mic button**

Replace the entire `body` computed property (lines 29-113) with:

```swift
    var body: some View {
        HStack(alignment: .bottom, spacing: MacSpacing.sm) {
            // CLI text view (preserves history recall, multi-line, amber cursor)
            CLITextView(
                text: $messageText,
                placeholder: "Message Hestia...",
                promptChar: "",
                onSend: handleSend,
                onEscape: { /* clear handled inside CLITextView */ },
                history: $history,
                historyIndex: $historyIndex
            )
            .frame(minHeight: 30, maxHeight: 200)
            .fixedSize(horizontal: false, vertical: true)
            .clipShape(RoundedRectangle(cornerRadius: 8))

            // Send button with pulse micro-interaction
            Button(action: handleSend) {
                Image(systemName: "paperplane.fill")
                    .font(.system(size: 16))
                    .foregroundStyle(MacColors.buttonTextDark)
                    .frame(width: MacSize.sendButtonSize, height: MacSize.sendButtonSize)
                    .background(MacColors.amberAccent)
                    .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.sendButton))
            }
            .buttonStyle(.hestia)
            .scaleEffect(sendPulseScale)
            .disabled(isEmpty)
            .opacity(isEmpty ? 0.5 : 1)
            .accessibilityLabel("Send message")
            .padding(.bottom, 6)
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, MacSpacing.sm)
        .background(MacColors.aiBubbleBackground)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        // Focus glow — amber border fades in when content is being composed
        .overlay {
            RoundedRectangle(cornerRadius: 16)
                .strokeBorder(
                    MacColors.amberAccent.opacity(!isEmpty ? 0.4 : 0),
                    lineWidth: 1.5
                )
                .animation(.easeInOut(duration: 0.2), value: isEmpty)
        }
        .padding(.horizontal, 33)
        .padding(.vertical, MacSpacing.lg)
        .background(MacColors.chatInputBackground)
        // Haptic feedback on message send
        .sensoryFeedback(.success, trigger: sendTrigger)
    }
```

**Step 2: Remove unused state and computed properties**

Remove these from the top of the struct (they're no longer referenced):

- Line 7: `@State private var showCommandPicker = false` — delete
- Lines 21-27: `promptChar` computed property — delete

**Step 3: Build and verify**

Run: `cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

**Step 4: Commit**

```bash
git add HestiaApp/macOS/Views/Chat/MacMessageInputBar.swift
git commit -m "feat(macOS): simplify input bar — remove terminal, prompt char, mic"
```

---

### Task 4: Remove agent avatar from AI message bubbles

**Files:**
- Modify: `HestiaApp/macOS/Views/Chat/MacMessageBubble.swift:85-110` (aiBubble)

**Step 1: Replace the aiBubble computed property**

Replace lines 85-141 (the entire `aiBubble` computed property) with:

```swift
    private var aiBubble: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            VStack(alignment: .leading, spacing: MacSpacing.xs) {
                // Sender label (no avatar)
                Text(message.mode?.displayName ?? "Tia")
                    .font(MacTypography.senderLabel)
                    .foregroundStyle(MacColors.textSender)
                    .padding(.horizontal, MacSpacing.sm)

                // Message bubble with markdown rendering
                MarkdownMessageView(content: message.content)
                    .padding(.horizontal, MacSpacing.lg)
                    .padding(.vertical, MacSpacing.md)
                    .background(MacColors.aiBubbleBackground)
                    .clipShape(UnevenRoundedRectangle(
                        topLeadingRadius: MacCornerRadius.chatBubble,
                        bottomLeadingRadius: 0,
                        bottomTrailingRadius: MacCornerRadius.chatBubble,
                        topTrailingRadius: MacCornerRadius.chatBubble
                    ))
            }

            // Reactions row (reduced leading padding since no avatar)
            MacReactionsRow(
                messageId: message.id,
                activeReactions: reactions,
                onReaction: onReaction
            )
            .padding(.leading, MacSpacing.sm)

            // Outcome feedback (visible on hover or when feedback already submitted)
            if isHovered || feedbackState != nil {
                OutcomeFeedbackRow(
                    messageId: message.id,
                    currentFeedback: feedbackState,
                    onFeedback: { feedback, note in
                        onFeedback(message.id, feedback, note)
                    }
                )
                .padding(.leading, MacSpacing.sm)
                .transition(.opacity)
            }
        }
        .padding(.top, MacSpacing.sm)
        .padding(.bottom, MacSpacing.lg)
        .padding(.trailing, 96)
        .onHover { hovering in
            withAnimation(.easeInOut(duration: 0.15)) {
                isHovered = hovering
            }
        }
    }
```

Key changes:
- Removed the outer `HStack` that held the avatar + content
- Removed `agentAvatar(for:size:)` call
- Changed reactions/feedback leading padding from `48` (avatar width offset) to `MacSpacing.sm`

**Step 2: Optionally remove `agentAvatar` helper**

The `agentAvatar(for:size:)` function (lines 60-81) is now unused. Remove it to keep the file clean.

**Step 3: Build and verify**

Run: `cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

**Step 4: Commit**

```bash
git add HestiaApp/macOS/Views/Chat/MacMessageBubble.swift
git commit -m "feat(macOS): remove agent avatar from AI message bubbles"
```

---

### Task 5: Final build + visual verification

**Files:** None (verification only)

**Step 1: Clean build both targets**

```bash
cd HestiaApp
xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' clean build 2>&1 | tail -10
xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16' clean build 2>&1 | tail -10
```

Expected: Both BUILD SUCCEEDED (iOS build confirms no shared code was broken)

**Step 2: Verify no dead code warnings**

Check that `SidebarChatToggle` is still referenced (it's in `ChatToggleButton.swift` — it should NOT be deleted since `HeaderChatToggle` from the same file is still used in `FloatingAvatarView`). If `SidebarChatToggle` now has zero references, it can be removed from `ChatToggleButton.swift` in a cleanup step.

```bash
cd HestiaApp && grep -r "SidebarChatToggle" macOS/ Shared/
```

If no references remain, remove the `SidebarChatToggle` struct from `ChatToggleButton.swift` (keep `HeaderChatToggle` and the `Notification.Name` extensions).

**Step 3: Commit cleanup if needed**

```bash
git add -A && git commit -m "chore(macOS): remove unused SidebarChatToggle struct"
```

---

## Summary

| Task | Description | Files | Commit |
|------|-------------|-------|--------|
| 1 | Create ChatPanelToggleOverlay | 1 new | `feat(macOS): add ChatPanelToggleOverlay view` |
| 2 | Wire overlay + remove sidebar toggle | 2 modified | `feat(macOS): wire ChatPanelToggleOverlay, remove sidebar chat toggle` |
| 3 | Simplify input bar | 1 modified | `feat(macOS): simplify input bar` |
| 4 | Remove avatar from AI bubbles | 1 modified | `feat(macOS): remove agent avatar from AI message bubbles` |
| 5 | Final build verification | 0-1 cleanup | `chore(macOS): remove unused SidebarChatToggle struct` |

**Total: 1 new file, 4 modified files, 4-5 commits**

## Success Criteria

1. Chat panel toggles from bottom-right overlay button (both show and hide)
2. ⌘\ keyboard shortcut still works
3. Input bar shows only text field + send button (no terminal/mic/prompt char)
4. CLITextView placeholder "Message Hestia..." shows when empty
5. AI message bubbles show sender name without avatar circle
6. History recall (up/down arrow), multi-line, Enter-to-send all still work
7. Both macOS and iOS targets build clean
