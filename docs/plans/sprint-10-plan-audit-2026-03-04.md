# Plan Audit: Sprint 10 — Chat Redesign + OutcomeTracker

**Date:** 2026-03-04
**Auditor:** Claude (Plan Audit Agent)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Sprint 10 redesigns Hestia's chat with CLI-style input, rich markdown output, floating avatar animations, background session support via Orders, and builds the OutcomeTracker (Learning Cycle Phase A part 2). Six deliverables over ~11 working days. This is the most UI-heavy sprint in the project — the chat is the most-used view.

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | — | — |
| Family (2-5) | Yes | OutcomeTracker needs user_id scoping on all tables | LOW if built correctly now |
| Community | Mostly | Background sessions via Orders may need queue limits per user | MEDIUM |

---

## Front-Line Engineering Review

**Feasibility: MEDIUM-HIGH.** The plan is ambitious but technically sound.

**Hidden prerequisites found by explorer:**
1. **Orders execution engine isn't wired.** APScheduler integration exists but executions are just database records — no actual background execution. "Move to Background" (Task 10.4) requires building the execution pipeline, not just creating Order records. This is the biggest hidden cost.
2. **`ConversationMessage` model has no outcome fields.** Need to extend with `outcome_id`, `feedback_type` for thumbs-up/down.
3. **WKWebView for rich markdown** requires entitlements and CSP configuration on macOS.
4. **NSTextView wrapping for CLI input** is non-trivial (same lesson from Sprint 7 MarkdownEditorView).

**Effort assessment:**
- 10.1 CLI Input: 2 days → **3 days** (NSTextView wrapping, key event handling, slash command completion)
- 10.2 Rich Output: 2 days → **3 days** (markdown parser + code highlighting + WKWebView + XSS sanitization)
- 10.3 Avatar: 1 day — **accurate**
- 10.4 Background Sessions: 3 days → **4 days** (Orders execution engine doesn't exist yet)
- 10.5 Keyboard shortcuts: 0.5 day — **accurate**
- 10.6 OutcomeTracker: 2.5 days → **3 days** (new module + middleware + integration)
- **Revised total: ~14.5 days** (was 11)

**Recommendation:** Split into 10A (Chat UI: tasks 10.1-10.3, 10.5 — ~7 days) and 10B (OutcomeTracker + Background Sessions: tasks 10.4, 10.6 — ~7 days). Natural checkpoint after 10A: does the new chat feel right?

---

## Architecture Review

**API design — GOOD.** `POST /v1/orders/from-session` is clean. `GET /v1/learning/outcomes` follows existing patterns.

**OutcomeTracker module placement:** Plan says `hestia/learning/outcome_tracker.py`. Recommend `hestia/outcomes/` as a full module (models + database + manager pattern) — consistent with every other module. The `learning/` name implies a larger namespace that doesn't exist yet.

**Background session execution:** The plan assumes Orders can run chat prompts. Currently, `OrderManager.execute()` creates an `OrderExecution` record but doesn't actually call the chat pipeline. This needs: (1) connect OrderExecution to `RequestHandler.handle()`, (2) run in background task, (3) store result, (4) send push notification on completion.

**XSS in WKWebView:** Plan's `sanitizeForWebView()` is inadequate — simple string replacement is bypassable. Use a proper CSP header instead:
```
Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src data:;
```
This blocks all scripts regardless of encoding tricks.

---

## Product Review

**User value: VERY HIGH.** Chat is used daily. CLI input + rich output is a significant UX upgrade. Background sessions solve the "waiting for Hestia" problem. OutcomeTracker is invisible but foundational.

**Feature flag recommended:** Ship new chat behind toggle. Old chat preserved as fallback for 2 weeks. This is correctly noted in the plan.

**Edge cases to cover:**
- Empty chat (no messages) → avatar shows agent only
- Very long message (>10K chars) → truncation or collapsible
- Network loss mid-response → graceful error, preserve partial
- Slash command with no matches → show "no commands found"

---

## Executive Verdicts

**CISO: APPROVE WITH CONDITIONS**
- E1: WKWebView XSS — use CSP header, not string sanitization
- E2: Background sessions must not bypass auth — each execution validates JWT
- E3: OutcomeTracker stores user behavior patterns — same data protection tier as memory

**CTO: APPROVE WITH CONDITIONS**
- T1: Split into 10A (Chat UI) + 10B (OutcomeTracker + Background) — reduces risk
- T2: OutcomeTracker as `hestia/outcomes/` module (not `hestia/learning/`)
- T3: Orders execution engine is hidden prerequisite — budget 1.5 extra days
- T4: Feature flag for chat UI rollback

**CPO: APPROVE**
- This is the right sprint to build next — chat is the most-used view
- OutcomeTracker is invisible to user (good — no extra burden)
- Background sessions deliver immediate value

---

## Final Critiques

### 1. Most Likely Failure
**Rich markdown rendering will take longer than expected.** SwiftUI has no native markdown-to-view library for code highlighting, tables, and collapsible sections. You'll need either a third-party library (swift-markdown-ui) or custom parsing. WKWebView fallback adds complexity.

**Mitigation:** Start with basic markdown (headers, bold, code blocks) using `AttributedString`. Defer Mermaid/LaTeX/tables to a future sprint. Ship "good enough" first.

### 2. Critical Assumption
**The Orders execution engine can be built in the time budgeted.** The plan treats "Move to Background → Order" as 3 days, but the explorer found no actual execution wiring. If this takes 5+ days, it crowds out OutcomeTracker.

**Validation:** Build the execution pipeline first (Task 10.4) before UI work. If it takes >4 days, defer OutcomeTracker to 10B.

### 3. Half-Time Cut List
If Sprint 10 had to ship in 7 days:
- **CUT:** Mermaid/LaTeX rendering (use raw text fallback)
- **CUT:** Avatar glow animation (static avatar only)
- **CUT:** Slash command completion (just ⌘+Enter to send)
- **CUT:** Background sessions via Orders (defer entirely)
- **KEEP:** CLI-style input (monospace, dark bg, history)
- **KEEP:** Code block highlighting + copy button
- **KEEP:** OutcomeTracker backend + thumbs-up/down in chat

---

## Conditions for Approval

| ID | Condition | Severity |
|----|-----------|----------|
| T1 | Split into 10A (Chat UI) + 10B (Outcomes + Background) with checkpoint | HIGH |
| T2 | OutcomeTracker as `hestia/outcomes/` module, not `hestia/learning/` | MEDIUM |
| T3 | Budget 1.5 extra days for Orders execution engine (hidden prerequisite) | HIGH |
| T4 | Feature flag for new chat UI rollback | MEDIUM |
| E1 | WKWebView CSP header instead of string sanitization for XSS | HIGH |
| P1 | Start with basic markdown (AttributedString), defer Mermaid/LaTeX | MEDIUM |
