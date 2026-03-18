# Plan Audit: Sprint 20 — Verification UI Indicators + API Contract Catch-up
**Date:** 2026-03-17
**Verdict:** APPROVE WITH CONDITIONS

---

## Plan Summary

Sprint 20 pairs two workstreams: (1) update `api-contract.md` to reflect the current 186-endpoint, 27-module state (vs the documented 132/22), and (2) surface `HallucinationRisk` from Hestia's 3-layer verifier as an amber dot in the iOS and macOS chat UIs. The verifier already computes risk on every response — it currently discards the structured signal and only appends a text disclaimer to response content. Sprint 20 converts that silent signal into a user-visible trust indicator.

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|-----------------|-------------------|
| Single user (now) | Yes | None — schema field is additive, UI is per-message | — |
| Family (2-5 users) | Yes | `hallucination_risk` is response metadata, not user-scoped. ToolComplianceChecker is stateless. No per-user tuning. | Low — patterns in `memory.yaml` are global, but that's acceptable |
| Community (10+ users) | Yes | High amber trigger rates could differ across usage patterns; no per-user pattern tuning | Medium — would need per-user or per-domain pattern config |

The plan is scale-safe. The risk field is ephemeral response metadata, not stored state. No architectural decisions here close off future multi-tenancy.

---

## Front-Line Engineering

**Feasibility:** High for the REST path. The `bylines` field in `ChatResponse` was added the same way — optional field, threaded through handler, decoded in Swift. That's the exact pattern here.

**Hidden prerequisites:**

1. **Streaming path scope decision** (blocker): `handle_streaming()` emits SSE events. There is currently no mechanism to return `hallucination_risk` in a stream without adding a new SSE event type (`"verification"`). The iOS/macOS SSE parsers would also need to handle it. This is NOT in the plan's 4-file scope but is required if the indicator should work in practice — streaming is the default chat path. **Must be scoped explicitly before build starts.**

2. **Disclaimer duplication decision** (design blocker): The text disclaimer (`"⚠ I wasn't able to verify this..."`) is currently appended to `response.content`. With an amber dot, both will appear simultaneously — redundant UX. Three options, one must be chosen before code is written:
   - (A) Keep both — belt-and-suspenders, visually redundant
   - (B) Suppress text disclaimer when `hallucination_risk` is non-nil — cleaner, requires conditional in handler
   - (C) Move disclaimer text into the dot's popover — cleanest UX, requires popover content design

3. **Trigger rate validation** (quality gate): The actual false-positive rate of `ToolComplianceChecker` on production logs is unknown. Target is <5% of messages flagging amber. If it's higher, the patterns in `memory.yaml` must be tightened before the indicator goes live or alert fatigue kills the signal value immediately.

**Complexity:** The plan says "4 files." Actual count: `schemas/chat.py` + `handler.py` (two paths: `handle()` and `handle_streaming()`) + `APIModels.swift` + `MessageBubble.swift` + `MacMessageBubble.swift` + test updates = **6 files minimum**, 8 with SSE parser changes. Still manageable, but underscoped in the plan.

**Testing gaps:**
- The disclaimer text path is tested; the structured `hallucination_risk` field threading is not
- SSE event parsing for a new `verification` event type has no test coverage
- iOS/macOS amber dot rendering is not unit-testable (SwiftUI previews only)

---

## Architecture Review

**Fit:** Excellent. The `bylines: Optional[List[AgentBylineSchema]]` field was added to `ChatResponse` in Sprint 17 via the exact same pattern. `hallucination_risk: Optional[str]` is a direct analogue — optional, non-breaking, backward-compatible (old clients that don't decode the field see `None` and render nothing).

**Data model:** No DB changes. Risk is computed at response time and discarded after the response is sent. No persistence needed — if re-queried, the risk would be recomputed. This is correct.

**API design concern:** `hallucination_risk: Optional[str]` returns the `HallucinationRisk` enum value as a string (`"tool_bypass"`, `"low_retrieval"`, etc.). This is forward-compatible for adding new enum values, but loses type safety on the client. Acceptable for now — document in api-contract.md that the field is an enum string with defined values.

**Integration risk — streaming path:** This is the highest-risk integration point. The current SSE stream ends with a content chunk, then closes. Adding a `verification` event after the final content chunk requires:
  1. A new `ChatStreamEvent` case in `HestiaApp/Shared/Models/`
  2. Handler to yield the event after `final_content` is assembled
  3. iOS/macOS stream consumers to update `message.hallucinationRisk` on receipt

This is well-defined work but non-trivial. The streaming path handles ~90% of chat traffic — if it's excluded, the indicator effectively doesn't exist for most conversations.

**Integration risk — macOS hover affordance:** `MacMessageBubble` already has a hover-triggered feedback row (`onFeedback`, `onReaction`). The amber dot must be positioned to not conflict with this affordance. Best placement: inline with the bylines/timestamp row, always visible (not hover-gated), since risk indicators that only appear on hover create inconsistent awareness.

---

## Product Review

**User value:** High and concrete. The 3-layer verifier (Sprints 18-19) currently catches hallucinations silently — it appends a text disclaimer that users can easily miss as part of the response content. An inline amber dot on a specific message is categorically different from a footer warning. NNG research confirms per-message contextual signals are engaged with; generic footer warnings are ignored within days.

**Scope:** Right-sized. API contract catch-up is pure documentation hygiene with zero code risk. Verification UI is 6-8 files of additive changes. Neither workstream is over-engineered.

**Opportunity cost:** Sprint 21 (Correction Feedback UI) is the natural follow-on — users can't easily correct a flagged response until they can see which responses were flagged. Building C2 now directly enables C4 in Sprint 21. The sequencing is correct.

**Edge cases:**
- What if the verifier fails (exception)? Fail-open — `hallucination_risk` is `None`, no dot shown. Correct behavior.
- What if risk is `HallucinationRisk.NONE`? No dot shown. UI is unchanged. Good.
- What if the user is offline? Not applicable — the field comes from the server response.
- First-time user seeing amber dot with no explanation? The popover/tooltip is required — not optional.

---

## UX Review

**Design system compliance:**
- `MacColors.statusWarning` (`#FF9800`) is the correct token for the amber dot — it's the semantic warning orange used across the macOS design system
- `MacColors.amberBright` (`#FFB900`) is an alternative — this is what unread dots and active states use; slightly more on-brand but less "warning" semantically
- iOS: HestiaColors equivalent — confirm `HestiaColors.warning` or use the system `.orange` token; amber accents are established across the design system
- Recommendation: `MacColors.statusWarning` for macOS, equivalent warning token for iOS — consistent semantic meaning

**Interaction model:**
- Amber dot: always visible on flagged messages, not hover-gated
- Tap (iOS) / click (macOS): shows popover explaining the risk type
- Popover content must explain: (1) what happened, (2) what the user should do — vague "this response may be unverified" is insufficient
  - TOOL_BYPASS: "Hestia described your calendar/health data without checking it. Tap to verify with the original source."
  - LOW_RETRIEVAL: "Hestia's memory search returned low-confidence results. This response may not reflect your actual data."
- No action required from the user unless they want to verify — the dot is informational, not a blocker

**Platform divergence:**
- iOS: tap gesture on amber dot → sheet or popover
- macOS: hover → tooltip, or click → popover. The existing `.onHover` affordance in `MacMessageBubble` can host the tooltip without new interaction model changes
- Ensure the dot is at the same visual position (end of bylines row) on both platforms

**Accessibility:**
- The amber dot MUST have `.accessibilityLabel("Response may be unverified. Tap for details.")` — non-negotiable
- `.accessibilityHint("Activate to learn more about this response's verification status")`
- VoiceOver must read the warning before or after the message content, not skip it

**Disclaimer duplication (must resolve before build):**
The current text disclaimer `"⚠ I wasn't able to verify this against your calendar or health data..."` is in `response.content` and appears inline in the message bubble. With an amber dot, users see:
1. The message content
2. The text disclaimer (appended to content)
3. The amber dot

This is triple-redundant. Recommendation: **Option B** — suppress the text disclaimer when `hallucination_risk` is non-nil. The dot + popover replace the text. This requires a conditional in `handler.py` but produces significantly cleaner UX. The text disclaimer can remain as fallback for clients that don't decode `hallucination_risk`.

---

## Infrastructure Review

**Deployment impact:** Server restart required after `ChatResponse` schema change. No DB migration. No config change. The schema change is additive — old clients that don't decode `hallucination_risk` receive `None` by default and render nothing.

**New dependencies:** None — no new Python packages, no new Swift packages.

**Monitoring:** Add a log line in `handler.py` when `hallucination_risk` is non-None and threaded into the response. Use `LogComponent.VERIFICATION`. This enables future log-based trigger rate analysis without additional instrumentation.

**Rollback strategy:** Fully reversible. Remove `hallucination_risk` from `ChatResponse`, remove threading in `handler.py`, remove the field from `ConversationMessage` and the dot from `MessageBubble`. No data to migrate. Clean revert in < 1 hour.

**Resource impact:** Zero. Risk is already computed by `ToolComplianceChecker` in the handler pipeline. Returning it in the response adds one string field to the response payload (~15 bytes). No additional inference calls, no additional DB queries.

---

## Executive Verdicts

- **CISO:** Acceptable — `hallucination_risk` returns an enum string (`"tool_bypass"`, `"low_retrieval"`). No PII, no credentials, no new external communication. The field reflects Hestia's internal classification of its own uncertainty. The amber dot's popover content must not leak internal system state (e.g., specific patterns that triggered the flag) — popover text must be user-facing only.

- **CTO:** Approve with conditions — schema change follows the established `bylines` precedent exactly. The streaming path is underscoped and must be explicitly decided before build begins. The disclaimer duplication is a design debt that will compound if not resolved now. Both are fixable pre-build decisions, not architectural problems.

- **CPO:** Approve — this converts silent infrastructure into a user-visible trust signal. The 3-layer verifier was built over two sprints and currently has no user-facing expression. Sprint 20 closes that gap. The api-contract catch-up eliminates a growing integration risk. Both workstreams are correctly scoped for a single sprint.

---

## Devil's Advocate

### 9.1 Counter-Plan

**The alternative:** Skip the amber dot. Instead, spend Sprint 20 improving retrieval quality so the verifier triggers less — tighten memory retrieval parameters, improve ChromaDB similarity thresholds, and reduce the root cause of LOW_RETRIEVAL flags. If fewer responses need disclaimers, the UI problem disappears.

**Why the counter-plan loses:** The verifier's three layers are independent. TOOL_BYPASS (claiming calendar data without a tool call) is a model behavior, not a retrieval issue — improving retrieval doesn't reduce it. The amber dot and retrieval improvements address different failure modes and are not mutually exclusive. The counter-plan would also leave the API contract stale, which is pure regression.

**Counter-plan verdict:** Not a credible substitute. The sprint plan is stronger.

### 9.2 Future Regret Analysis

- **3 months:** If the trigger rate is high (>5%) and patterns weren't tightened first, the amber dot appears on too many messages and becomes noise. Andrew stops noticing it. The signal value is destroyed. **Mitigation: measure trigger rate before build.**

- **6 months:** The disclaimer text suppression (Option B) means clients that don't decode `hallucination_risk` see no disclaimer at all — not the text version, not the dot. If a third client (e.g., CLI v2, web app) is built without the dot, it silently swallows risk. **Mitigation: keep the text disclaimer as fallback for non-UI clients; suppress only in iOS/macOS bubbles via client-side logic, not by omitting the text from the server response.**

- **12 months:** The `hallucination_risk: Optional[str]` field stores the enum value string. If Sprint 22+ adds logprobs entropy as a continuous score, a string field can't carry a float confidence value. Consider whether `verification: Optional[VerificationSummary]` (an object with `risk: str`, `score: float`, `reason: str`) is a better one-time design. Adding fields to a nested object is less visible to clients than adding top-level response fields.

### 9.3 Uncomfortable Questions

- **"How often does this actually trigger?"** Unknown. This is the most important pre-build question and the plan doesn't answer it. Measure on Mac Mini production logs before writing a line of code.

- **"Will the amber dot make Andrew trust Hestia more, or just make him more anxious?"** If the dot appears on 15% of messages, the emotional effect is anxiety, not trust calibration. The pattern thresholds in `memory.yaml` were set conservatively but were never validated against real production traffic. This must be measured.

- **"Is the text disclaimer actually getting read today?"** If the existing text disclaimer is already providing the trust signal (Andrew reads it, adjusts behavior), then the amber dot adds redundancy without new value. The amber dot's value is highest if the text disclaimer is NOT being read — which is likely, given it's embedded in the response content and easy to miss.

### 9.4 Final Stress Tests

1. **Most likely failure:** The streaming path is excluded (too complex for the sprint scope), but streaming is the default chat path. The amber dot then only appears on REST API calls (CLI, direct API) — never in the iOS/macOS chat UI during normal use. The feature ships but is invisible in practice. **Mitigation: explicitly commit to the SSE approach in Phase 2 scope, or explicitly cut macOS/iOS streaming support and document the limitation. No ambiguity.**

2. **Critical assumption:** That `ToolComplianceChecker`'s trigger rate is low enough to be a meaningful signal. If wrong, the sprint delivers an amber indicator that fires constantly and destroys user trust in the system itself (not just in specific responses). **Validate early: run `grep -c "domain_claim"` patterns against recent Mac Mini logs before writing the schema change.**

3. **Half-time cut list:** If half the time available: (1) Do api-contract.md fully — this is zero-risk, high-value hygiene. (2) Implement `hallucination_risk` in ChatResponse and handler (REST path only, no streaming). (3) Skip iOS/macOS UI — return the field in the API, document it, let the next sprint build the dot. This gives the schema foundation without the UI complexity.

---

## Conditions for Approval

The plan is approved conditional on resolving these four items **before writing implementation code:**

1. **Streaming scope decision (required):** Explicitly decide whether Sprint 20 includes the SSE `verification` event for `handle_streaming()`. If yes, add iOS/macOS SSE parser changes to the file list. If no, document the limitation in api-contract.md and plan for Sprint 21. No ambiguity — one path or the other.

2. **Trigger rate measurement (required):** On Mac Mini production server, run the ToolComplianceChecker patterns against the last 7 days of chat responses in the outcomes table. Target: <5% of responses flag amber. If higher, tighten `memory.yaml` domain_claim_patterns before building the UI.

3. **Disclaimer duplication resolution (required):** Choose one of three options explicitly:
   - Option A: Keep text disclaimer in content AND add amber dot (redundant but safe)
   - Option B: Suppress text disclaimer in content when `hallucination_risk` is non-nil (cleaner, done client-side in iOS/macOS only — server still returns the text)
   - Option C: Remove text from content, put it in popover only (cleanest, requires server-side change)
   Recommendation: Option B — suppress in bubble rendering, keep in server content for non-UI clients.

4. **Popover content drafted (required):** Write the user-facing copy for each risk type before building the dot:
   - TOOL_BYPASS: what to say, what action to suggest
   - LOW_RETRIEVAL: what to say, what action to suggest
   - SLM_FLAG: what to say (optional — if this risk type should also show the dot)
   The amber dot without a useful popover is worse than no dot — it creates anxiety with no resolution path.

**Recommended macOS color token:** `MacColors.statusWarning` (`#FF9800`) for the risk dot.
**Recommended iOS color token:** Match the iOS design system warning color — confirm via `HestiaColors` before build.
