# macOS UI Polish: Sidebar Toggle + Input Bar Redesign

**Date:** 2026-03-10
**Status:** Approved
**Reference:** Claude Desktop app UI patterns

---

## Motivation

The Hestia macOS app has a functional but CLI-heavy chat panel aesthetic. This design modernizes two areas — the chat panel toggle and the message input bar — to match the clean, minimal patterns seen in Claude Desktop, while preserving Hestia's unique features (history recall, multi-line input, mode system).

---

## Approach A: Minimal Footprint (Implementing Now)

### Change 1: Right Sidebar Toggle Overlay

**Current:** Chat panel toggle lives in the left `IconSidebar` as a `SidebarChatToggle` button at the bottom.

**New:** A floating `ChatPanelToggleOverlay` button anchored to the **bottom-right** of the main content area in `WorkspaceRootView`.

| Aspect | Detail |
|--------|--------|
| Visibility | Always visible (both when chat is open and closed) |
| Icon | `sidebar.right` SF Symbol — direction indicates current state |
| Tooltip | "Show right sidebar (⌘\)" / "Hide right sidebar (⌘\)" |
| Action | Posts `hestiaChatPanelToggle` notification (existing mechanism) |
| Style | Rounded rect, semi-transparent dark background, subtle hover highlight |
| Keyboard shortcut | ⌘\ (unchanged, handled by AppDelegate) |

**Files:**
- `IconSidebar.swift` — Remove `SidebarChatToggle` section at the bottom
- `WorkspaceRootView.swift` — Add `.overlay(alignment: .bottomTrailing)` with new toggle view
- **New:** `macOS/Views/Chrome/ChatPanelToggleOverlay.swift` (~40 lines)

### Change 2: Input Bar Simplification

**Current:**
```
[⌘ terminal] [~/?/$] [CLITextView multiline] [🎤] [send ➤]
```

**New:**
```
[CLITextView multiline with placeholder] [send ➤]
```

| Remove | Keep |
|--------|------|
| Terminal button (⌘ icon + command picker popover) | CLITextView (history recall, multi-line, amber cursor, monospace, Enter-to-send) |
| Per-mode prompt character (~/?/$) | Send button (32x32 amber, pulse animation) |
| Mic button (non-functional placeholder) | Mode selector in avatar header (unchanged) |

**Add:**
- Placeholder text "Message Hestia..." displayed in CLITextView when empty (subtle secondary color)

**Files:**
- `MacMessageInputBar.swift` — Remove terminal button, prompt char, mic; simplify HStack layout
- `CLITextView.swift` — Add placeholder text support (NSTextView placeholder overlay)

### Change 3: Message Bubble Cleanup

**Current:** Each AI message bubble has an agent avatar circle + agent name label.

**New:** Remove the avatar circle, keep only the text name label as sender identifier.

**Files:**
- `MacMessageBubble.swift` — Remove `agentAvatar()` call from `aiBubble`, adjust spacing

---

## Summary of All Files Affected

| File | Change Type |
|------|-------------|
| `macOS/Views/Chrome/IconSidebar.swift` | Modify — remove SidebarChatToggle |
| `macOS/Views/WorkspaceRootView.swift` | Modify — add overlay |
| `macOS/Views/Chrome/ChatPanelToggleOverlay.swift` | **New** (~40 lines) |
| `macOS/Views/Chat/MacMessageInputBar.swift` | Modify — simplify layout |
| `macOS/Views/Chat/CLITextView.swift` | Modify — add placeholder |
| `macOS/Views/Chat/MacMessageBubble.swift` | Modify — remove avatar |

Total: 5 modified + 1 new = **6 files**

---

## Approach B: Full Claude Desktop Mirror (Future Reference)

Documented here for potential Sprint 9+ consideration. **Not implementing now.**

### Window-Level Toggle
Instead of an overlay on the content area, place the toggle at the absolute bottom-right of the NSWindow, always above all content. Would require changes to `MainWindowController.swift` or `MainSplitViewController.swift` to add an AppKit-level overlay.

### SwiftUI TextEditor Input Bar
Replace CLITextView (NSTextView wrapper) with a native SwiftUI `TextEditor`:
- Rounded-rect text field with placeholder
- @ and / hints in placeholder text
- Inline mode selector pill (next to send button)

**Trade-offs:**
- **Gains:** Native SwiftUI, simpler code, easier to style
- **Losses:** History recall (up/down arrow), AppKit text customizations (amber cursor, monospace enforcement), Enter-to-send behavior (requires workaround in SwiftUI)
- **Risk:** Medium — reimplementing CLITextView features in SwiftUI is non-trivial

### Empty State Suggested Prompts
Add suggested action chips in the chat panel when no conversation is active (like Claude's "Document Athena collection" etc.). Would require:
- Backend endpoint for contextual suggestions
- New `SuggestedPromptsView` in the chat panel
- Empty state detection in `MacChatViewModel`

### Chat Header Simplification
Replace the floating avatar header with a minimal "New Chat" bar:
- Left: "New Chat" label
- Right: + button (new session) + history button
- No avatar, no mode display in header

---

## Success Criteria

1. Chat panel toggles correctly from the bottom-right overlay button
2. ⌘\ keyboard shortcut continues to work
3. Input bar is visually cleaner with no terminal/mic buttons
4. CLITextView placeholder shows when empty
5. AI message bubbles show name label without avatar
6. No regressions in: history recall, multi-line input, Enter-to-send, mode switching
