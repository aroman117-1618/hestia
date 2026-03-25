# Chat Empty Bubble Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate empty AI response bubbles caused by streaming failures, clearStream without follow-up tokens, and duplicate messages from REST fallback.

**Architecture:** Three fixes applied identically to both `MacChatViewModel.swift` (macOS) and `ChatViewModel.swift` (iOS): (1) defer-based typing state cleanup, (2) empty content fallback at stream end, (3) placeholder removal before REST fallback.

**Tech Stack:** Swift/SwiftUI, no new dependencies.

**Mockup:** `docs/mockups/chat-ui-fix-mockup.html`

---

### Task 1: Fix MacChatViewModel (macOS)

**Files:**
- Modify: `HestiaApp/macOS/ViewModels/MacChatViewModel.swift`

- [ ] **Step 1: Add defer block for typing state cleanup in sendMessageStreaming**

In `sendMessageStreaming()`, after setting `isTyping = true` and `currentTypingText = ""` (lines 240-241), add a defer block. This ensures typing state is always cleaned up, even if the stream throws mid-iteration.

```swift
isTyping = true
currentTypingText = ""

defer {
    isTyping = false
    currentTypingText = nil
}
```

Remove the manual cleanup at lines 294-295 (after the for loop) since defer now handles it.

- [ ] **Step 2: Add empty content guard at stream end**

After the stream for-loop completes (before the defer runs), check if the message content is empty. This catches the case where `clearStream` fired but no re-synthesis tokens followed.

```swift
// After the for-await loop ends, before defer runs:

// Guard against empty content (clearStream with no follow-up tokens)
if messages[messageIndex].content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
    messages[messageIndex].content = "Sorry, I ran into a problem processing that. Want me to try again?"
}
```

- [ ] **Step 3: Remove empty placeholder before REST fallback in sendMessage**

In `sendMessage()`, inside the streaming catch block (line 92-96), remove the empty streaming placeholder before falling back to REST. This prevents duplicate bubbles.

```swift
} catch {
    #if DEBUG
    print("[MacChatVM] Streaming failed, falling back to REST: \(error)")
    #endif
    // Remove empty streaming placeholder before REST fallback
    if let lastMsg = messages.last, lastMsg.role == .assistant, lastMsg.content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
        messages.removeLast()
    }
    // Also reset typing state in case defer hasn't run yet
    isTyping = false
    currentTypingText = nil

    try await sendMessageREST(text, sessionId: sessionId, forceLocal: wasForceLocal, appState: appState)
}
```

- [ ] **Step 4: Build macOS target to verify compilation**

Run: `xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

---

### Task 2: Fix ChatViewModel (iOS) — Mirror same changes

**Files:**
- Modify: `HestiaApp/Shared/ViewModels/ChatViewModel.swift`

- [ ] **Step 1: Add defer block for typing state cleanup in sendMessageStreaming**

Same pattern as Task 1 Step 1. Add defer after lines 198-199, remove manual cleanup at lines 258-259.

- [ ] **Step 2: Add empty content guard at stream end**

Same pattern as Task 1 Step 2, after the for-await loop.

- [ ] **Step 3: Remove empty placeholder before REST fallback in sendMessage**

Same pattern as Task 1 Step 3, in the streaming catch block at lines 104-108.

- [ ] **Step 4: Build iOS target to verify compilation**

Run: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 16' build 2>&1 | tail -5`
Expected: BUILD SUCCEEDED

- [ ] **Step 5: Commit**

```bash
git add HestiaApp/macOS/ViewModels/MacChatViewModel.swift HestiaApp/Shared/ViewModels/ChatViewModel.swift
git commit -m "fix: prevent empty chat bubbles from streaming failures and REST fallback duplicates"
```
