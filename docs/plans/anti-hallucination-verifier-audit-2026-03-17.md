# Plan Audit: Anti-Hallucination Verifier Architecture
**Date:** 2026-03-17
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
4-layer hallucination prevention stack for Hestia's local LLM pipeline: (1) tool compliance gate, (2) retrieval quality score injection, (3) local SLM validator promoting existing cloud-only Validator role to qwen2.5:0.5b dual-path, (4) logprob entropy monitoring. New `hestia/verification/` module. ~12-16 hours. Zero cloud dependency.

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user (current) | ✅ Yes | None | — |
| Family (2-5 users) | ✅ Yes | SLM Validator is synchronous; concurrent requests queue at qwen2.5:0.5b | Low — wrap in asyncio.gather with timeout |
| Community (10+ users) | ⚠️ Partial | qwen2.5:0.5b is not concurrent-safe on Ollama (sequential model swap) | Medium — needs per-request timeout gate |

**Scale note:** `HallucinationRisk` logging in MetaMonitor must be `user_id`-scoped from day one — retroactive scoping is expensive.

---

## Front-Line Engineering

- **Feasibility:** All 4 layers are buildable with existing infrastructure. No blockers.
- **Hidden prerequisites:**
  - `VERIFICATION` LogComponent must be added to enum before any verification logging compiles
  - `build_context_with_score()` must be a NEW method — do NOT modify `build_context()` signature. It has 4 callers (handler.py:521, handler.py:796, agentic_handler.py:73, build_context_with_ids). Breaking the signature breaks the parallel pre-inference gather.
  - Validator fail-open bug fix (roles.py:188-193) must land in same PR as Layer 3
- **Testing gaps:**
  - Tool compliance regex false-positive rate on conversational responses is unknown — needs offline validation before shipping
  - qwen2.5:0.5b binary classification accuracy on known-hallucinated responses is unvalidated
  - Streaming path needs separate Layer 1 injection (not just handle())

---

## Architecture Review

- **Fit:** Clean. `hestia/verification/` follows module conventions (models.py + functional modules). No database needed — stateless pipeline.
- **Data model:** `HallucinationRisk` enum + `VerificationResult` dataclass. User-scoped via request context. ✅
- **Integration risk:** HIGH on handler.py — both `handle()` and `handle_streaming()` need updates. Streaming path post-content injection is more complex (content is built incrementally).
- **Dependency risk:** None. Pure Python, no new packages.

---

## Product Review

- **User value:** Direct. Prevents the class of failure witnessed today (confident fabricated roadmap). Health and calendar data fabrication has real-world consequences.
- **Scope:** Right-sized. Layers 1-3 deliver the core value. Layer 4 is measurement infra.
- **Opportunity cost:** Delays Sprint 18 feature work by ~12-16 hours. Worth it given the trust regression today.

---

## Infrastructure Review

- **Deployment impact:** Server restart required (new module, LogComponent enum change, config changes).
- **Rollback strategy:** All verification is fail-soft (try/except, never blocks response). Removing the module reverts cleanly.
- **Resource impact:** Layer 3 (SLM Validator) adds ~100ms per non-CHAT response. Acceptable on M1.

---

## Executive Verdicts

- **CISO:** APPROVE — no new attack surface. Verification is read-only pipeline. Domain patterns are internal config. Error sanitization patterns maintained.
- **CTO:** APPROVE WITH CONDITIONS — see conditions below.
- **CPO:** APPROVE — directly addresses witnessed user-facing failure. Right scope, right timing.

---

## Critical Conditions (applied to implementation plan)

1. **DO NOT modify `build_context()` signature.** Add `build_context_with_score()` as a new method. Existing callers untouched.
2. **Layer 3 SLM Validator MUST use a simplified binary prompt**, not the full cloud Validator prompt. qwen2.5:0.5b cannot reliably evaluate a complex rubric. Single question: "Does this response make claims not grounded in the provided context? YES or NO."
3. **Layer 3 must be non-blocking in all code paths.** Wrapped in try/except, failure = pass-through. Never raises to caller.
4. **CHAT-classified intents skip the SLM Validator** (same exemption as existing CHAT optimization). Conversational responses have no factual grounding requirement.
5. **Domain patterns must be configurable** in `memory.yaml → hallucination_guard`, not hardcoded.
6. **Layer 4 (logprobs) is metrics-only** — do not use as a runtime gate. Attach to `InferenceResponse` and surface in MetaMonitor only.
7. **Fix Validator fail-open bug** (roles.py:188-193) in same commit as Layer 3.

---

## Final Critiques

1. **Most likely failure:** Tool compliance regex fires on conversational responses that mention calendar/health in passing ("I remember you mentioned your heart rate last week"). Mitigation: require BOTH domain keyword AND a fabricated-result pattern ("your X is Y", "you have N events") — not just domain mention.
2. **Critical assumption:** qwen2.5:0.5b can reliably answer a binary grounding question. Validate with 10 known-hallucination samples before trusting. If accuracy < 70%, demote Layer 3 to metrics-only.
3. **Half-time cut list:** Cut Layer 4 (logprobs) from this sprint entirely. It's measurement infra with no user-facing impact. Move to Sprint 19 alongside MetaMonitor expansion.
