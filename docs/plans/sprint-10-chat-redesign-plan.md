# Sprint 10: Chat Redesign + OutcomeTracker

**Created:** 2026-03-03
**Status:** PLANNED
**Priority:** P0 — Most-used view, highest UX impact
**Estimated Effort:** ~11 days (~66 hours)
**Prerequisites:** Sprint 7 (CacheManager), Sprint 8 (PrincipleStore)
**Learning Cycle Phase:** A (part 2) — OutcomeTracker

---

## Objective

Redesign the chat experience with CLI-style input (Claude Code-inspired), rich markdown output (Cowork-level), floating avatar swap animation, background session support integrated into Orders, and the OutcomeTracker for Learning Cycle Phase A.

## Deliverables

1. CLI-style input box (monospace, dark bg, prompt char, history, slash commands)
2. Rich output renderer (markdown, code highlighting, tool cards, collapsible sections)
3. Floating avatar header with swap animation
4. "Move to Background" flow → session becomes Order with `working` status
5. "Add Session" button removed; ⌘N for new session
6. OutcomeTracker middleware logging implicit feedback signals

---

## Task Breakdown

### 10.1 CLI-Style Input Box (~2 days)

**File:** `macOS/Views/Chat/ChatInputView.swift` (refactor existing)

**Visual design:**
```
┌─────────────────────────────────────────────────────────┐
│ ┌─────────────────────────────────────────────────────┐ │
│ │ $ ▌                                                  │ │
│ │                                                      │ │
│ │  SF Mono 13pt · #E0E0E0 on #1E1E1E · cursor blink   │ │
│ └─────────────────────────────────────────────────────┘ │
│  ⌘+Enter to send    Shift+Enter newline    /commands    │
└─────────────────────────────────────────────────────────┘
```

**Features:**
- **Font:** SF Mono 13pt (monospace)
- **Colors:** Background #1E1E1E, text #E0E0E0, prompt char orange (#FF6B35)
- **Prompt character:** Per-agent: `$` for Olly (dev), `~` for Tia (daily), `?` for Mira (teaching)
- **Multi-line:** Shift+Enter inserts newline, ⌘+Enter sends
- **History recall:** Up-arrow cycles through previous messages (last 50)
- **Slash commands:** Type `/` → dropdown of available commands (from `/v1/user-profile/commands`)
- **Syntax highlighting:** Basic highlighting for code blocks typed in input (using regex)
- **Auto-resize:** Input box grows with content (max 40% of chat height)
- **Cursor blink:** Standard text cursor, orange tint

**Implementation notes:**
- Use `NSTextView` wrapped in SwiftUI (for richer text handling than `TextEditor`)
- Key event handling for Up-arrow history, ⌘+Enter send, Shift+Enter newline
- Slash command completion: filter command list as user types after `/`

### 10.2 Rich Output Renderer (~2 days)

**File:** `macOS/Views/Chat/ChatOutputRenderer.swift` (new)

**Rendering capabilities:**
| Content Type | Rendering Method |
|-------------|-----------------|
| Markdown headers | Native `Text` with Typography tokens |
| Bold, italic, links | `AttributedString` |
| Code blocks | Syntax-highlighted view with copy button and language label |
| Inline code | Monospace `Text` with background |
| Tables | Native SwiftUI `Grid` |
| Lists (ordered/unordered) | Custom list view with proper indentation |
| Images | `AsyncImage` with loading placeholder |
| Tool call cards | Custom card view: tool name, params, result |
| Collapsible sections | `DisclosureGroup` for long outputs |
| Mermaid diagrams | WKWebView with mermaid.js (fallback: raw text) |
| LaTeX math | WKWebView with KaTeX (fallback: raw text) |

**Architecture choice: Hybrid rendering**
- Simple markdown (text, headers, lists, code): Native SwiftUI (fast, scrollable)
- Complex content (Mermaid, LaTeX, rich tables): WKWebView embedded inline
- Decision boundary: if content contains `\`\`\`mermaid` or `$$`, use WebView for that block

> ⚠️ **Audit finding:** Prototype BOTH approaches with a 50-message conversation before committing. WKWebView has security implications — LLM output could contain `<script>` tags or other injection vectors. **XSS prevention required:** Sanitize all LLM output before rendering in WKWebView. Use a strict Content Security Policy (CSP) that blocks inline scripts. Never use `evaluateJavaScript` with user-generated content.

**XSS prevention (audit addition):**
```swift
// Before rendering LLM output in WKWebView:
func sanitizeForWebView(_ content: String) -> String {
    return content
        .replacingOccurrences(of: "<script", with: "&lt;script", options: .caseInsensitive)
        .replacingOccurrences(of: "javascript:", with: "", options: .caseInsensitive)
        .replacingOccurrences(of: "onerror=", with: "", options: .caseInsensitive)
        .replacingOccurrences(of: "onload=", with: "", options: .caseInsensitive)
}
```

**Feature flag (audit addition):** Ship new chat UI behind a feature flag. Keep old chat as fallback for 2 weeks after launch. Toggle in Settings → Resources → Experimental.

**Code block component:**
```
┌────────────────────────────────────────┐
│ python                          [Copy] │
│ ┌────────────────────────────────────┐ │
│ │ def hello():                       │ │
│ │     print("Hello, World!")         │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

**Tool call card component:**
```
┌────────────────────────────────────────┐
│ 🔧 apple_calendar_today               │
│ ┌────────────────────────────────────┐ │
│ │ Checked your calendar — 3 events   │ │
│ │ today. Team sync at 10am.          │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

### 10.3 Floating Avatar Header (~1 day)

**File:** `macOS/Views/Chat/FloatingAvatarView.swift` (new)

**Design:**
```
┌──────────────────────────────────┐
│         ┌──────────┐             │
│         │          │             │
│         │  [Photo] │  ← 60pt    │
│         │          │     circle  │
│         └──────────┘             │
│          Tia  🌊                 │
│    ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔            │
│    orange glow ring              │
│    when responding               │
└──────────────────────────────────┘
```

**Animation spec:**
- **Swap trigger:** Agent → User when user sends message; User → Agent when response starts
- **Swap animation:** Cross-dissolve (300ms ease-in-out) with subtle scale bounce (1.0 → 0.95 → 1.05 → 1.0)
- **Active glow:** Pulsing orange ring (`MacColors.accentPrimary.opacity(0.3–0.6)`) when agent is generating response
- **Idle state:** No glow, static avatar display
- **Name label:** Below photo, updates with swap animation

**Data source:**
- Agent photo: `GET /v2/agents/{name}` → photo URL
- User photo: `GET /v1/user/photo` → photo data
- Active speaker: tracked by ViewModel based on message flow

### 10.4 Background Session → Orders (~3 days)

**Backend changes:**

1. **Extend `OrderStatusEnum`:**
```python
class OrderStatusEnum(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFTED = "drafted"      # NEW
    SCHEDULED = "scheduled"  # NEW
    WORKING = "working"      # NEW
    COMPLETED = "completed"  # NEW (for one-time orders)
```

2. **New endpoint:** `POST /v1/orders/from-session`
```python
class SessionToOrderRequest(BaseModel):
    session_id: str
    name: Optional[str] = None  # Auto-generated if not provided

# Creates an order from an active chat session
# Copies conversation context into order prompt
# Sets status to "working"
# Hestia continues processing in background task system
```

3. **Order lifecycle for background sessions:**
```
User in chat → "Move to Background" → POST /v1/orders/from-session
→ Order created (status: working) → Chat clears to fresh session
→ Hestia processes in background → status: completed
→ Push notification: "Background task complete"
→ User taps notification or visits Orders → sees result
```

**macOS implementation:**

**Files to create/modify:**
- `macOS/Views/Chat/BackgroundSessionButton.swift` — "↗ Move to Background" button
- `macOS/Views/Command/OrderSessionCard.swift` — Card variant for background sessions

**"Move to Background" button:**
- Positioned in chat toolbar (where "Add Session" button was)
- Only visible when there's an active conversation (≥1 message)
- Tap → confirmation: "Move this conversation to background? Hestia will continue processing."
- On confirm: `POST /v1/orders/from-session` → clear chat → fresh session

**Order session card in Command:**
```
┌─────────────────────────────────────────┐
│ ● Working    Background Session          │
│              Started 2:45 PM             │
│                                          │
│ "Help me research competitor pricing..." │
│                                          │
│ [View] [Cancel]                          │
└─────────────────────────────────────────┘
```

### 10.5 Remove "Add Session" + Keyboard Shortcuts (~0.5 day)

**Changes:**
- Remove "Add Session" button from chat toolbar
- Add keyboard shortcut: `⌘N` → create new session (POST /v1/sessions)
- The "Move to Background" button occupies the freed toolbar space
- If user wants a fresh session without backgrounding: just ⌘N

### 10.6 OutcomeTracker (Learning Cycle Phase A, Part 2) (~2.5 days)

**New module:** `hestia/learning/outcome_tracker.py`

**Implicit signals tracked (no extra burden on Andrew):**

| Signal | Measurement | Interpretation |
|--------|------------|---------------|
| Response accepted without edits | No follow-up correction within session-scoped window | Positive — response was useful |
| Follow-up clarification | Same topic, rephrased within session | Negative — didn't understand need |
| Time to next message | Long gap (>5 min) after response | Likely positive — response was sufficient |
| Immediate follow-up | <30s after response | Likely negative — response was insufficient |
| Background session completed | Order status → completed, user viewed result | Neutral — need to check if user acted on it |
| Same request recurring | Similar query within 7 days | Pattern — should have been anticipated |
| Thumbs up/down | If UI implements rating | Direct signal |

**Implementation:**

```python
class OutcomeTracker:
    """Middleware that hooks into chat response cycle to log outcome signals."""

    async def on_response_sent(self, session_id: str, message_id: str,
                                response_content: str, duration_ms: int):
        """Called after every chat response. Starts tracking implicit signals."""
        self.pending_outcomes[message_id] = OutcomeRecord(
            session_id=session_id,
            message_id=message_id,
            response_sent_at=datetime.now(timezone.utc),
            duration_ms=duration_ms,
        )

    async def on_next_message(self, session_id: str, user_message: str):
        """Called when user sends follow-up. Analyzes timing and content.

        Audit note: Uses session-scoped correction detection instead of fixed 60s timer.
        Users may correct minutes or hours later — track correction windows per-domain
        and adapt thresholds over time.
        """
        pending = self._get_pending_for_session(session_id)
        if pending:
            elapsed = (datetime.now(timezone.utc) - pending.response_sent_at).total_seconds()
            is_correction = await self._is_correction(user_message, pending.response_content)
            pending.outcome = OutcomeSignal(
                elapsed_seconds=elapsed,
                is_correction=is_correction,
                is_same_topic=await self._is_same_topic(user_message, pending.response_content),
            )
            await self._store_outcome(pending)

    async def periodic_distill(self):
        """Run periodically to distill outcomes into principles."""
        recent_outcomes = await self._get_recent_outcomes(days=7)
        # Group by domain/topic
        # Identify patterns (recurring corrections, recurring successes)
        # Feed to PrincipleStore for distillation
```

**Integration point:** Hook into chat route as middleware — after response is sent, before next message is processed.

**New endpoint:**
```
GET /v1/learning/outcomes
  ?days=7&domain=scheduling
  → { outcomes: [OutcomeRecord], patterns: [OutcomePattern] }
```

---

## Testing Plan

| Area | Test Count | Type |
|------|-----------|------|
| CLI input key handling (history, shortcuts) | 4 | UI |
| Rich output rendering (markdown, code, tables) | 5 | UI |
| Rich output XSS prevention (LLM outputs `<script>` tag) | 3 | Security |
| Avatar swap animation triggers | 3 | UI state |
| Background session → Order creation | 4 | API integration |
| Background task → `working` Order migration (in-flight tasks) | 2 | Integration |
| Completed task → `completed` Order migration | 1 | Integration |
| Order status lifecycle (working → completed) | 3 | API |
| OutcomeTracker signal detection | 5 | Unit |
| OutcomeTracker session-scoped correction detection | 2 | Unit |
| OutcomeTracker signal decay over time | 1 | Unit |
| Feature flag toggle (old chat ↔ new chat) | 2 | UI |
| **Total** | **~35** | |

## SWOT

| | Positive | Negative |
|---|---|---|
| **Strengths** | Chat is most-used view — highest impact. CLI matches Hestia's dev personality. Background sessions leverage existing task infrastructure. OutcomeTracker is invisible to user. | Rich markdown in SwiftUI is non-trivial (may need WebView fallback). CLI input expectations are high (Claude Code quality bar). |
| **Opportunities** | CLI-style differentiates from all consumer AI chats. Background sessions solve "waiting for Hestia" flow problem. OutcomeTracker is the data foundation for all future learning. | Users expect Claude Code-level input quality. Rich output rendering has edge cases with complex markdown/LaTeX. |

## Definition of Done

- [ ] Input box: monospace, dark bg, agent-specific prompt char, multi-line, ⌘+Enter send
- [ ] Input history: up-arrow recalls previous messages
- [ ] Slash command completion: type `/` → command dropdown
- [ ] Output: full markdown rendering with syntax-highlighted code blocks + copy
- [ ] Output: tool call cards for tool executions
- [ ] Avatar: floating header with cross-dissolve swap animation
- [ ] Avatar: orange glow ring when agent is generating
- [ ] "Move to Background" creates order with `working` status
- [ ] Background order visible in Command Center
- [ ] "Add Session" button removed, ⌘N works
- [ ] OutcomeTracker logging implicit signals on every interaction
- [ ] OutcomeTracker uses session-scoped correction (not fixed 60s timer)
- [ ] XSS prevention: LLM output sanitized before WKWebView rendering
- [ ] Feature flag: old chat preserved as fallback for 2 weeks
- [ ] Background task → Order migration path tested (in-flight + completed)
- [ ] **Decision Gate 2:** OutcomeTracker collecting meaningful signals? M1 memory profile acceptable? → Go/No-Go
- [ ] All tests passing (existing + ~35 new)
