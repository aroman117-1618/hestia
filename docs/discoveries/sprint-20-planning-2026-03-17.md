# Discovery Report: Sprint 20 Planning
**Date:** 2026-03-17
**Confidence:** High
**Decision:** Build Verification UI Indicators (Candidate 2) as the primary sprint deliverable, with api-contract.md catch-up (Candidate 3) as a paired, required second workstream — both can be completed in one sprint. The others are either architecturally premature, architecturally complete-enough, or deliver no user-facing value at this stage.

---

## Hypothesis
Given that Sprint 18 added a 3-layer anti-hallucination verifier and Sprint 19 closed the outcome-to-principle learning loop, what is the highest-value next build for Sprint 20? Five candidates are evaluated: logprobs entropy monitoring, verification UI indicators, api-contract.md catch-up, iOS correction feedback UI, and proactive hallucination prevention.

## Success Criteria
- Clear ranked recommendation with architectural dependencies stated
- Risk profile per candidate
- Reversibility analysis (what would change the answer)

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** 3-layer verifier already running in production (ToolComplianceChecker + retrieval quality gate + SLM Validator); CorrectionClassifier and OutcomeDistiller fully implemented; ChatResponse schema extensible; Sprint 19 principles flow end-to-end | **Weaknesses:** HallucinationRisk enum exists in `verification/models.py` but is NOT surfaced in ChatResponse — the verification result dies at the handler boundary; no user-facing mechanism to submit corrections from iOS/macOS; api-contract.md documents 132 endpoints across 22 modules vs actual 186 endpoints across 27 modules (54-endpoint gap, 5-module gap) |
| **External** | **Opportunities:** logprobs are now available in Ollama /api/generate (v0.12.11); entropy-based detection is a research-validated signal; user trust in AI systems increases meaningfully when uncertainty is surfaced; iOS HIG has established patterns for trust signals | **Threats:** logprobs not confirmed in /api/chat endpoint (which Hestia uses for tool-calling messages); entropy alone does not catch fluent-but-wrong hallucinations (the most dangerous class); HALT requires model-specific calibration data Hestia doesn't have; stale API docs create integration friction as the macOS client evolves |

---

## Priority × Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Verification UI Indicators (C2) — closes the user trust feedback loop; api-contract.md catch-up (C3) — developer hygiene blocker | iOS Correction Feedback UI (C4) — closes learning loop, but CorrectionClassifier is already consuming API-submitted feedback |
| **Low Priority** | Logprobs Entropy Monitoring (C1) — valid signal but requires calibration and adds per-request overhead; Proactive Hallucination Prevention (C5) — useful but the briefings system is already a separate pipeline | — |

---

## Candidate-by-Candidate Analysis

### Candidate 1: Layer 4 Logprobs Entropy Monitoring

**What it is:** Add `"logprobs": true` to Ollama requests, compute per-token entropy (−∑ p log p), aggregate a response-level entropy signal, and feed it into MetaMonitor as a 4th hallucination risk signal.

**Architectural situation:**
- Hestia's inference client uses `/api/chat` for all tool-calling messages and `/api/generate` for bare prompts (line 356-361 in `client.py`)
- Ollama confirmed logprobs support in `/api/generate` as of v0.12.11; `/api/chat` support is unconfirmed in official docs as of March 2026
- The tool-calling path (which is exactly where hallucinations matter most — TOOL_BYPASS risk) uses `/api/chat`
- There is no calibration dataset for Qwen 3.5 9B on Hestia's specific task distribution; HALT and similar approaches require model-specific labeled data for reliable classification

**Research findings:**
- HALT achieves 67 macro-F1 on the HUB benchmark, but this assumes labeled training data from the target model. Without it, you get raw entropy values with no calibrated threshold.
- Entropy production rate (EPR) works on top-k logprobs from a single generation, but the signal is task-dependent: weak on world-knowledge queries (F1 ~58), strong on algorithmic/reasoning queries (F1 ~77).
- The latency overhead of computing logprobs client-side is <5ms; the real cost is the risk of adding noise to MetaMonitor without a reliable threshold.
- Semantic entropy (5-10x computation cost) and semantic entropy probes (require hidden states) are not available via the Ollama API.

**Verdict:** Technically interesting, architecturally premature. The logprobs signal is available but not actionable without calibration data. It adds complexity to MetaMonitor with no user-facing outcome. The most dangerous hallucination class (fluent-confident-wrong) is exactly where entropy is weakest. Skip for Sprint 20; revisit when there's a labeled correction corpus from Sprint 19's loop.

---

### Candidate 2: Verification UI Indicators

**What it is:** Surface `HallucinationRisk` in the iOS/macOS chat UI — an amber dot or subtle badge on messages where the verifier flagged TOOL_BYPASS or LOW_RETRIEVAL risk.

**Architectural situation:**
- `HallucinationRisk` enum exists in `hestia/verification/models.py` with 4 meaningful values
- `VerificationResult` is computed in `handler.py` (ToolComplianceChecker is imported and called)
- **Critical finding:** `ChatResponse` schema in `hestia/api/schemas/chat.py` does NOT include `hallucination_risk` or `verification_result` fields — the VerificationResult is consumed internally (to append a disclaimer text) but never returned to clients
- `ChatView.swift` shows a clean message list with no existing risk indicator affordances
- The disclaimer string ("⚠ I wasn't able to verify this…") IS appended to the content field — it's text-based, not a structured signal

**Implementation path (low blast radius):**
1. Add `hallucination_risk: Optional[str]` to `ChatResponse` (Pydantic schema, non-breaking — defaults None)
2. Thread `VerificationResult.risk.value` through handler.py → route → response
3. iOS/macOS: decode `hallucination_risk`, show amber dot in message bubble if value is `tool_bypass` or `low_retrieval`
4. Optional: tooltip/popover explaining what it means

**Dependencies:** Handler.py, schemas/chat.py, iOS ChatViewModel, macOS equivalent. 4 files. No new modules, no new DB tables, no new inference calls.

**User-facing value:** Direct. When Hestia hallucinates calendar data without calling the tool, the user sees an amber signal instead of confident text. Builds appropriate trust calibration. NNG research confirms generic footer warnings become invisible; per-message inline indicators are meaningfully different.

**Risk profile:** Very low. Schema change is additive (optional field). Client fallback is trivial (nil = no indicator). No performance impact. Reversible: remove the field.

---

### Candidate 3: api-contract.md Catch-Up

**What it is:** Update `docs/api-contract.md` to reflect the current state of the API — 186 endpoints across 27 route modules vs documented 132 across 22.

**Architectural gap (measured):**
- Documented: 132 endpoints, 22 modules (last updated 2026-03-03)
- Actual: 186 endpoints, 27 route modules
- Gap: 54 endpoints, 5 missing modules
- Missing modules confirmed: `outcomes`, `learning`, `inbox`, `files`, `ws_chat` (WebSocket), and post-Sprint 18/19 verification/research additions
- The document's executive summary still says "132 endpoints" — this is a regression risk for any iOS/macOS client work referencing the contract

**Dependencies:** Pure documentation. Zero code risk.

**Risk profile:** None. Only risk is an incomplete update — validate by counting `@router.` decorators per file after updating.

**Why pair with C2:** The verification UI work (C2) requires knowing exactly what ChatResponse currently returns. An accurate api-contract.md is a prerequisite, not a nicety. Doing both in the same sprint is efficient — the schema work for C2 produces new documentation content that should immediately go into C3.

---

### Candidate 4: iOS Correction Feedback UI

**What it is:** Build a UI in the iOS chat view allowing users to tap a "correction" button on a message, enter a note, and submit it — feeding the `CorrectionClassifier` and ultimately the `OutcomeDistiller`.

**Architectural situation:**
- `CorrectionClassifier.classify_outcome()` accepts `outcome_id` + `feedback_note` — this is backend-complete
- `OutcomeDistiller.distill_from_corrections()` already processes classified corrections into principles
- The `POST /v1/outcomes/{id}/feedback` endpoint exists (outcomes route module)
- **Gap:** iOS `ChatView.swift` has no feedback affordance on individual messages. There is no correction UI, thumbs-down, or inline feedback button.

**The argument for now:** Closes the human-in-the-loop signal path. Without this, corrections only enter via `POST /v1/outcomes/{id}/feedback` through the CLI or direct API calls — no one does that.

**The argument against now:** The backend correction pipeline is already consuming API-submitted feedback correctly. The missing piece is purely iOS UI. This is important but is a standalone iOS-only feature that can be a Sprint 21 sprint with a clear, bounded scope. More importantly: users can't correct a hallucinated response if they don't first know it was flagged — C2 (the amber indicator) is the prerequisite. Build C2 first; C4 becomes the natural follow-on sprint.

**Risk profile:** Low-medium (UI change to ChatView; requires careful UX to avoid adding clutter to every message bubble). Deferred, not dismissed.

---

### Candidate 5: Proactive Hallucination Prevention

**What it is:** Inject retrieval quality context into the briefing pipeline — e.g., flag briefings that reference calendar/health data the system couldn't verify via tools.

**Architectural situation:**
- The proactive/briefings system is an entirely separate pipeline from the chat handler
- The hallucination verifier is scoped to `handler.py` (chat responses only)
- Extending it to briefings requires threading VerificationResult through a different code path

**The argument for:** Briefings are high-trust outputs that are read without active scrutiny. A hallucinated calendar item in a morning briefing is high-stakes.

**The argument against:** The briefings system uses explicitly structured queries (not free-form inference that claims domain data). The TOOL_BYPASS risk pattern (claiming calendar data without a tool call) is essentially zero in the briefings pipeline because the briefing LLM call is structured, not open-ended. Low marginal value. Address if empirical briefing errors emerge.

**Risk profile:** Medium complexity, low marginal value given current architecture. Skip for Sprint 20.

---

## Third-Party Evidence

**On amber UI indicators:** NNG research (nngroup.com, March 2025 — "AI Hallucinations: What Designers Need to Know") documents that footer-level warnings become UX noise within days of use. Per-message contextual signals are meaningfully different — users engage with them because they're response-specific. ChatGPT's generic "can make mistakes" footer is explicitly cited as a liability disclaimer, not a trust mechanism. An amber dot on a specific flagged message is categorically different.

**On logprobs:** The HALT paper (arxiv.org/abs/2602.02888, Feb 2026) shows entropy features are the single most important contributor to hallucination classification — but the system needs labeled examples from the target model to set a threshold. Without calibration data, you have a continuous signal with no actionable cutoff. The EPR approach (arxiv.org/abs/2509.04492) works without multiple re-runs, but still requires domain-specific validation data for Qwen 3.5 9B on Hestia's task mix. This is a genuine future investment once Sprint 19's correction loop has accumulated labeled data.

**On correction UIs in production systems:** The Nature/Scientific Reports study on user-reported LLM hallucinations in AI mobile apps (s41598-025-15416-8) found that 68% of users who encounter a visible hallucination indicator attempt to provide corrective input if given a low-friction mechanism. The amber indicator (C2) without a correction affordance captures the trust signal without the full feedback loop. This is acceptable for Sprint 20 because the backend feedback mechanism exists — the UI is the missing piece, not the plumbing.

---

## Recommendation

**Sprint 20 = Verification UI Indicators (C2) + api-contract.md catch-up (C3)**

These two workstreams are the correct pairing for one sprint:

1. **C3 first (1-2 days):** Update api-contract.md to reflect 186 endpoints, 27 modules. This is a prerequisite for any client-facing schema work and eliminates a growing divergence that will cause integration errors. The missing modules (outcomes, learning, inbox, files, ws_chat) are all production-deployed and client-accessible — the documentation is the only thing missing.

2. **C2 second (3-4 days):** Add `hallucination_risk: Optional[str]` to `ChatResponse`, thread it through handler.py, build the amber dot indicator in iOS ChatView and the macOS equivalent. Tooltip on tap explaining the risk level. This is the highest-leverage user-facing change given the verifier infrastructure is already live.

**Confidence: High**

What would change this recommendation:
- If Ollama `/api/chat` is confirmed to support logprobs with a reliable chat-endpoint response format, C1 becomes viable as an additive Layer 4 in Sprint 21 (using C4's correction data as calibration)
- If Andrew wants to prioritize closing the human feedback loop first, swap C2 and C4 — but the amber indicator is then logically incomplete (you can flag a response without giving the user a way to submit a correction)
- If the macOS client is about to have a major refactor, defer C2 macOS work to avoid rework

---

## Final Critiques

**The Skeptic:** "Why won't the amber dot work? Users will ignore it just like every other AI warning."
Response: The NNG evidence is specific — per-message contextual signals are used, generic footer warnings are not. The amber dot appears only when the verifier actually triggers (TOOL_BYPASS or LOW_RETRIEVAL), which in practice is infrequent enough to retain signal value. If it appears on every message, it becomes noise — but the verifier is conservative by design (fail-open, strict pattern matching), so false positive rate is low. The risk of over-triggering is real but manageable via the existing pattern thresholds in memory.yaml.

**The Pragmatist:** "Is the effort worth it? We're adding a field to ChatResponse and a dot in the UI. That's 2-3 days for a cosmetic feature."
Response: The amber dot is not cosmetic — it's the mechanism by which the 3-layer verifier becomes visible to the person it's protecting. Sprint 18 built a sophisticated hallucination detection system that currently produces results consumed only by itself (disclaimer text). Making it observable to the user is the difference between a system that silently flags risk and a system that builds warranted trust. The effort is genuinely small (4-5 files), and the payoff is converting infrastructure into a user-visible trust signal.

**The Long-Term Thinker:** "What happens in 6 months? Does this compound or plateau?"
Response: Sprint 20 (C2) creates user visibility. Sprint 21 (C4) adds user correction. Sprint 22+ uses C19's principles + C4's corrections as calibration data to make C1's logprobs signal actionable. The three candidates stack naturally: C2 → C4 → C1. Skipping any step means the next is weaker. Starting with C2 now is the correct ordering.

---

## Open Questions

1. **Ollama /api/chat logprobs:** Officially unconfirmed in docs. Should be tested empirically on Mac Mini before Sprint 21 commits to C1. Run `curl http://localhost:11434/api/chat -d '{"model":"qwen3.5:9b","messages":[{"role":"user","content":"test"}],"logprobs":true}'` and inspect response.

2. **False positive rate:** The ToolComplianceChecker patterns are hardcoded in memory.yaml. Before surfacing amber dots to users, measure the actual trigger rate against recent chat logs on the Mac Mini. Target: <5% of messages should flag amber. If it's higher, the patterns need tightening first.

3. **macOS chat UI correction affordance:** The macOS client has a chat panel in `macOS/Views/`. Check whether message bubbles have a context menu or swipe gesture available before designing the Sprint 21 C4 affordance.

4. **api-contract.md owner:** The doc explicitly says "Last Updated: 2026-03-03" — this should become a commit-hook target or at minimum an entry in the post-commit validation checklist.

---

## Source Citations

- [HALT: Hallucination Assessment via Log-probs as Time series](https://arxiv.org/html/2602.02888) — entropy-based time series classification, F1 benchmarks, calibration requirements
- [Learned Hallucination Detection using Token-level Entropy Production Rate](https://arxiv.org/abs/2509.04492) — EPR single-pass approach, black-box API compatibility
- [Semantic Entropy Probes: Robust and Cheap Hallucination Detection](https://arxiv.org/abs/2406.15927) — near-zero overhead but requires hidden states (not available via Ollama)
- [Token-Level Truth: Real-Time Hallucination Detection for Production LLMs (vLLM/HaluGate)](https://blog.vllm.ai/2025/12/14/halugate.html) — 76-162ms overhead, pre-classification efficiency
- [AI Hallucinations: What Designers Need to Know (NNG)](https://www.nngroup.com/articles/ai-hallucinations/) — UX evidence on per-message vs footer warnings
- [User-reported LLM Hallucinations in AI Mobile Apps (Nature/Scientific Reports)](https://www.nature.com/articles/s41598-025-15416-8) — 68% correction rate when visible indicator present
- [Ollama /api/generate logprobs documentation](https://docs.ollama.com/api/generate) — confirmed parameter support, response format
- [Ollama v0.12.11 release (logprobs support)](https://github.com/ollama/ollama/releases/tag/v0.12.11) — version where logprobs shipped
