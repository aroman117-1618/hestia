# Second Opinion: Fact Extraction Pipeline Fix
**Date:** 2026-03-23
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
Fix the broken fact extraction pipeline in the Research module. The 3-phase LLM pipeline (entity identification, significance filtering, PRISM triple extraction) has never worked because the fact extractor calls `client.generate()` — a method that doesn't exist on `InferenceClient` (which only has `complete()`). Every phase silently catches the `AttributeError`. The original SESSION_HANDOFF diagnosis (prompts routing to COMPLEX tier) was a theory never validated against actual behavior.

## Critical Discovery
**The root cause is NOT model routing — it's a method name mismatch.** The fact extractor was written referencing `client.generate()` which was likely renamed to `client.complete()` at some point. The 3-phase pipeline has never executed a single LLM call in production.

## Scale Assessment
| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes (after fix) | 3 LLM calls/chunk x N chunks = sequential bottleneck | Low |
| Family (2-5) | Partially | Concurrent extractions could queue-block inference | Medium — needs per-user queuing |
| Community | No | 150+ LLM calls per extraction run doesn't scale | High — needs batch/cloud path |

## Front-Line Engineering
- **Feasibility:** Method rename is trivial. `format` param threading requires 3-layer change (moderate but clean).
- **Hidden prerequisites:** `complete()` doesn't accept `format="json"` — needs to be added to `complete()` → `_call_with_routing()` → `_call_ollama()`. Similarly, `force_tier` exists on `router.route()` but isn't exposed through `complete()`.
- **Testing gaps:** Existing tests mock the inference client with arbitrary methods, so `generate()` vs `complete()` mismatch was never caught. Need a contract test or at least `hasattr()` assertion.

## Architecture Review
- **Fit:** The method rename follows existing patterns. The `force_tier` parameter already exists in the router — exposing it is architecturally consistent.
- **Data model:** No schema changes needed.
- **Integration risk:** Low — fact extractor is isolated from core chat pipeline.

**Key finding:** Truncating input from 2000 to 500 chars to avoid COMPLEX tier routing is treating a symptom with permanent data loss. The `force_tier` parameter (already in the router) is the correct architectural solution — callers should declare their tier needs explicitly.

## Product Review
- **User value:** High — unblocks knowledge graph (currently shows 0 facts, 0 entities)
- **Scope:** Right-sized for the bug fix. 3-phase vs single-phase is a separate architectural decision.
- **Opportunity cost:** Minimal — small fix with high impact

## Infrastructure Review
- **Deployment impact:** Server restart required (standard)
- **Rollback strategy:** Clean — only affects extraction pipeline, not core chat
- **Resource impact:** Once fixed, 3 phases x 20 chunks = 60 LLM calls per extraction run, ~2-5 minutes on M1. Acceptable for background operation but should not block UI.

## Executive Verdicts
- **CISO:** Acceptable — no change to attack surface or credential handling
- **CTO:** Approve with conditions — fix method bug separately from routing concern; use `force_tier` not truncation
- **CPO:** Acceptable — unblocks a visible broken feature with minimal risk
- **CFO:** Acceptable — ~2h build cost, $0 runtime (local inference), pure recovery of sunk cost
- **Legal:** Acceptable — no external API, PII, or license changes

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No attack surface change |
| Empathy | 4 | Fixes a broken user-visible feature |
| Simplicity | 3 | 3-phase pipeline is complex; single-phase alternative is simpler |
| Joy | 4 | Satisfying to find the real root cause vs. treating symptoms |

## Final Critiques

### Devil's Advocate — Counter-Plan
**Single-phase extraction:** Fix the method name, but collapse to the existing legacy single-prompt `EXTRACTION_PROMPT` (one LLM call per chunk instead of three). Simpler, 3x faster, still extracts entities and relations. The 3-phase pipeline has zero empirical evidence of producing better results — it was designed from theory. Add phases back only when data justifies the cost.

### Future Regret Analysis
- **3 months:** If truncating to 500 chars, knowledge graph will be sparse/low-quality. If using `force_tier`, no regret.
- **6 months:** Without `force_tier` exposed on `complete()`, every new module needing PRIMARY-tier extraction will re-discover the token threshold and apply ad-hoc truncation.
- **12 months:** 60 LLM calls per extraction will be a bottleneck when knowledge graph is a core feature. Need batched extraction or cloud offloading.

### Uncomfortable Questions
1. **"Do we need 3 phases?"** — Zero empirical evidence. The pipeline has never produced data. Single-phase exists and works.
2. **"What's the cost of doing nothing?"** — Empty Research tab graph. Low immediate impact if nobody's using it yet.
3. **"Are we building for curiosity or value?"** — The 3-phase pipeline is intellectually interesting but unproven.

### Final Stress Tests
1. **Most likely failure:** After fixing `generate()` → `complete()`, prompts route to COMPLEX tier and timeout — exactly what the handoff predicted. **Mitigation:** Add `force_tier` to `complete()`.
2. **Critical assumption:** `complete()` without `format="json"` will produce parseable JSON from prompt instructions alone. **Validation:** Test with actual Ollama before deploying.
3. **Half-time cut list:** Keep: (1) fix method name, (2) add `think=False`, (3) reduce chunks to 10. Cut: `format` param threading, `force_tier`. These reveal what's truly essential.

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment
Gemini correctly identified the plan as **"tactical, not strategic"** — fixing immediate bugs but perpetuating core architectural problems (sequential processing, unproven 3-phase complexity).

Key Gemini findings:
- The truncation vs `force_tier` choice is a **critical architectural decision**, not an implementation detail. Truncating by 75% "should be considered an unacceptable compromise."
- The 5-10 minute sequential extraction run creates poor UX (fan noise, system slowdown) even in background
- No quality validation metrics — how do we know if the extraction is good?
- Silent error handling in chained pipeline is a "breeding ground for intermittent failures"

**Gemini's verdict:** APPROVE WITH CONDITIONS — deprecate 3-phase pipeline, use single-phase with `force_tier`, make it async, establish quality baselines before adding complexity.

### Where Both Models Agree (High Confidence)
- The root cause is a method name mismatch, not model routing
- `force_tier` is architecturally superior to prompt truncation
- 3-phase pipeline is unjustified without empirical evidence
- Chunk count should be reduced from 50 to 10-20
- `format="json"` should be plumbed through the API (lasting improvement)

### Where Models Diverge
| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| 3-phase pipeline | Keep but question; let data decide | Deprecate immediately, single-phase only | **Gemini is right** — no data to justify 3x cost. Start with single-phase. |
| Async execution | Not addressed | Mandatory — use `BackgroundTask`, return 202 | **Gemini raises a valid point** — but current API is already called manually (POST trigger). Async is a nice-to-have, not a blocker. |
| Quality metrics | Mentioned in passing | Central requirement before adding complexity | **Agree with Gemini** — need manual review of first extraction batch before iterating. |

### Novel Insights from Gemini
1. **UX of background GPU load** — even 1-2 minutes of extraction causes noticeable system impact on M1. Not addressed in internal audit.
2. **Dead-letter queue / retry strategy** — 60 sequential API calls with no retry or partial-failure handling is fragile. Each chunk failure should be logged, not swallowed.
3. **"Simplify, benchmark, then iterate"** — a methodical approach: single-phase first, measure quality, add phases only when justified by data.

### Reconciliation
Both models converge on a simplified approach: fix the method bug, expose `force_tier` for explicit tier control, start with single-phase extraction, and reduce chunk count. The 3-phase pipeline should be preserved in code but not used until empirical data justifies its overhead. Truncation is rejected by both models as architecturally wrong.

## @hestia-critic Findings (integrated post-audit)

The adversarial critic agent identified several findings not caught in the main audit:

1. **Five call sites, not three.** The legacy fallback `_extract_legacy()` (line 253) and `check_contradictions()` (line 384) also call `client.generate()`. All five must be fixed.
2. **Test mocks are wrong too.** Tests in `test_fact_extraction_debug.py` (lines 43, 55, 83, 96, 112) and `test_research_facts.py` (lines 882, 974, 1006) mock `mock_client.generate` — the nonexistent method. They pass green while testing nothing. Must update to mock `complete`.
3. **Contradiction checker is unbounded.** `check_contradictions()` runs per-triplet against existing facts. 5 triples with existing fact pairs = 5 additional unaccounted LLM calls.
4. **`format="json"` modifies production-critical shared path.** Adding `format` to `_call_ollama()` touches the inference core used by every LLM call in the system. This is blast radius risk — consider deferring to a separate PR.

**Critic's verdict:** Fix all five `generate()` → `complete()` call sites, add `think=False`, update test mocks, leave `MAX_TEXT_LENGTH` at 2000, defer `format="json"` plumbing. Run real extraction and measure before deciding on 3-phase vs single-phase.

## Conditions for Approval

The plan is APPROVED with these conditions:

### Must-Have (block implementation without these)
1. **Fix the method name at ALL FIVE call sites** — `generate()` → `complete()` in `_phase1_entities`, `_phase2_significance`, `extract_from_text` (Phase 3), `_extract_legacy`, and `check_contradictions`
2. **Update test mocks** — change `mock_client.generate` → `mock_client.complete` in `test_fact_extraction_debug.py` and `test_research_facts.py`
3. **Expose `force_tier` on `complete()`** — thread through `_call_with_routing()` to `router.route()`. Use `force_tier="primary"` for all extraction calls. Do NOT truncate input text.
4. **Add `think=False`** — suppress thinking tokens for structured JSON extraction (already supported in the call chain)
5. **Reduce chunk limit** — 50 → 15 in `manager.extract_facts()`

### Should-Have (implement if time permits)
6. **Add `format="json"` to `complete()` in a separate commit** — thread through to `_call_ollama()` request_data. Separate from fact extractor fix due to blast radius (shared inference path).
7. **Start with single-phase extraction** — use the legacy `EXTRACTION_PROMPT` path, skip 3-phase until quality baseline is established
8. **Add a contract test** — verify `InferenceClient` has the methods fact_extractor calls (prevents this class of bug from recurring)

### Nice-to-Have (defer to next sprint)
9. **Async extraction** — return 202, process in background, expose status endpoint
10. **Quality baseline** — manual review of first 50 extracted triplets to establish ground truth
11. **Retry strategy** — per-chunk retry with exponential backoff, dead-letter logging for persistent failures

## Revised Implementation Plan

```
Step 1: Expose `force_tier` param on complete() → _call_with_routing() (small, focused change)
Step 2: Fix all 5 generate() → complete() call sites in fact_extractor.py, add think=False + force_tier="primary"
Step 3: Update test mocks from generate → complete in test_fact_extraction_debug.py + test_research_facts.py
Step 4: Reduce manager chunk limit 50 → 15
Step 5: Run tests locally
Step 6: (Separate commit) Add format="json" param to complete() → _call_ollama()
Step 7: Deploy to Mac Mini, trigger extraction, verify graph populates
Step 8: Manually review extracted triplets for quality — decide 3-phase vs single-phase
```
