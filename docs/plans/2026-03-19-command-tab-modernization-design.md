# Command Tab Modernization — Design Spec

**Date:** 2026-03-19
**Status:** Approved
**Estimated effort:** ~18h

## Goal

Remove the 70px FloatingAvatarView chat header, redesign the input bar with mic support, and move Orders under the System tab with Past/Upcoming views.

## Design Decisions

### 1. Chat Header Removal

**Delete `FloatingAvatarView` entirely.** Redistribute its functionality:

| Component | Current Location | New Location |
|-----------|-----------------|--------------|
| Agent avatar + name | Center of header | Removed — Hestia is always the interface (ADR-042 orchestrator routes internally) |
| Mode picker dropdown | Chevron in header | Removed — no manual mode switching. Users tag `@artemis`/`@apollo` in chat input for specialist override |
| BackgroundSessionButton (new session / move to background) | Left side of header | Right side of input bar, before send/mic button |
| HeaderChatToggle (collapse panel) | Right side of header | Stays in parent view (`MacContentView` or equivalent) — not the chat panel's responsibility |
| Glow ring animation (agent typing) | Around avatar | Input bar border glow (already exists — amber glow when composing) |

**Space reclaimed:** 70px of vertical space returned to the message scroll area.

### 2. Input Bar Redesign — Three States

The input bar (`MacMessageInputBar`) gains a session button and a mic button. The send/mic button swaps based on text field state, matching iOS `ChatView` pattern.

**State 1: Empty**
```
┌─────────────────────────────────────────────────┐
│  Message Hestia...                    [ + ] [🎙] │
└─────────────────────────────────────────────────┘
```
- `+` button: new session (no messages) or move-to-background (has messages)
- Mic button: starts voice recording via existing `SpeechService`

**State 2: Typing**
```
┌─────────────────────────────────────────────────┐
│  How are the trades? @artemis         [ + ] [ ↑] │
└─────────────────────────────────────────────────┘
  (amber glow border)
```
- Mic swaps to send button (paperplane icon)
- Amber border glow appears (already exists)

**State 3: Recording**
```
┌─────────────────────────────────────────────────┐
│  ● Listening...  0:03                       [ ■] │
└─────────────────────────────────────────────────┘
  (red glow border)
```
- Red recording dot + "Listening..." + duration counter
- Stop button (red square) replaces mic/send
- Red border glow replaces amber
- On stop: transcribed text populates the text field (returns to State 2)

### 3. Orders Under System Tab

**Remove standalone `OrdersPanel` from Command Center.** Orders become a section within `SystemActivityView`.

**Layout:**
- Segmented picker: Upcoming / Past
- **Upcoming:** Active/scheduled orders sorted by next execution time. Shows: name, status badge (Active/Scheduled), recurrence indicator (🔁 Daily/Weekly/etc.), next run time, last run time + result
- **Past:** Recent executions sorted by timestamp DESC. Shows: name, success/failure indicator, timestamp, duration
- Color coding: green left-border = active, amber = scheduled
- `+ New Order` button at bottom (dashed border, opens existing order creation form)

**Order card fields:**
- Name (from `OrderResponse.name`)
- Status badge: Active (green) / Scheduled (amber) / Inactive (gray)
- Recurrence: frequency from `OrderResponse.frequency` + 🔁 icon
- Next execution: computed from `scheduled_time` + `frequency`
- Last run: from `OrderResponse.last_execution` with success/failure from `execution_history`

## Files to Modify

### Delete
- `HestiaApp/macOS/Views/Chat/FloatingAvatarView.swift` (214 lines — entire file)

### Modify
- `HestiaApp/macOS/Views/Chat/MacChatPanelView.swift` — Remove FloatingAvatarView usage, remove mode-related callbacks
- `HestiaApp/macOS/Views/Chat/MacMessageInputBar.swift` — Add BackgroundSessionButton, mic button, three-state logic
- `HestiaApp/macOS/Views/Command/SystemActivityView.swift` — Add Orders section with Upcoming/Past views
- `HestiaApp/macOS/ViewModels/MacCommandCenterViewModel.swift` — Ensure orders data is available for System tab

### May Need Changes
- `HestiaApp/macOS/Views/Chat/BackgroundSessionButton.swift` — May need size adjustments for input bar context
- `HestiaApp/macOS/Views/Common/ChatToggleButton.swift` — Verify it works without FloatingAvatarView parent
- `HestiaApp/macOS/ViewModels/MacChatViewModel.swift` — Remove mode switching methods if they exist
- Parent view that hosts MacChatPanelView — needs to own HeaderChatToggle directly

## What's NOT Changing
- iOS `ChatView` — already has the right pattern (no decorative header, mic/send swap)
- Backend Orders API — no changes needed, existing CRUD is sufficient
- `BackgroundSessionButton` logic — same behavior, just relocated
- Message bubble layout — untouched
- `CLITextView` — untouched (multi-line, amber cursor, CLI history)

## Testing
- Manual: verify chat panel renders without header, input bar shows correct state for empty/typing/recording
- Manual: verify Orders appear in System tab with correct data
- Build: both iOS and macOS targets must compile
- Verify: BackgroundSessionButton works from new location (new session + move to background flows)
- Verify: HeaderChatToggle works from parent view
