# Discovery Report: Anti-Hallucination Verifier Architecture for Hestia
**Date:** 2026-03-17
**Confidence:** High
**Decision:** Implement a 4-layer hallucination prevention stack: (1) tool-first enforcement at prompt injection, (2) logprob uncertainty gating post-generation, (3) promote existing Validator council role from cloud-only to local-SLM for grounding checks, and (4) retrieval quality scoring. All four layers are zero-cloud, additive to existing architecture, and achievable within one sprint.

---

## Hypothesis

Can Hestia implement enterprise-grade, multi-layer hallucination prevention for its local LLM inference pipeline (Qwen 3.5 9B primary, no cloud dependency) through: SLM post-generation verification, citation enforcement, tool-first grounding, and retrieval quality improvements — without adding cloud inference dependencies or unacceptable latency?

---

## Current State Audit

### What Hestia Already Has (Strengths to Build On)

**Existing Validator Role (council/roles.py:150)**
The `Validator` council role already evaluates response quality, accuracy, and tool usage — but it is **cloud-only**. When `cloud_routing.state == "disabled"` (the historic default, though currently `enabled_full`), the Validator is silently skipped. The validator prompt explicitly checks: "No hallucinated data, no made-up information" and "If the user asked about calendar/reminders/etc, did the response use tools?" — but this only runs on cloud.

**Tool-First System Prompt (handler.py:50-108)**
`TOOL_INSTRUCTIONS` injected into every chat prompt already instructs: "NEVER fabricate results or say you lack access — always call the tool." This is the right directive but it's enforced by model compliance only — no architectural gate.

**Bi-Temporal Contradiction Detection (research/fact_extractor.py)**
`FactExtractor.check_contradictions()` already does LLM-based fact contradiction detection between entity pairs. However, this is on-demand (invoked for knowledge graph building, not for every chat response) and operates on stored facts, not live responses.

**Correction Classifier (learning/correction_classifier.py)**
`CorrectionClassifier.heuristic_classify()` already categorizes user corrections with `CorrectionType.FACTUAL` as the default fallback. This is a post-hoc signal — it captures hallucinations after the user reports them, not before they reach the user.

**Memory Retrieval: all-MiniLM-L6-v2 via ChromaDB (memory/vector_store.py)**
The vector store uses ChromaDB's default embedding model (all-MiniLM-L6-v2, 22M params) for semantic search. Cosine similarity is computed but the similarity scores are not currently surfaced to the inference pipeline or used as quality gates.

**Ollama logprobs: Available as of v0.12.11**
Ollama now supports `logprobs: true` in API requests. This provides per-token log-probability data that can be used to compute uncertainty entropy without any external model. Not currently used in `_call_ollama()`.

### What's Missing (Gap Analysis)

| Gap | Location | Impact |
|-----|----------|--------|
| Validator skips entirely when cloud disabled | council/manager.py | Zero hallucination checking in local-only mode |
| No retrieval quality score injected into prompt | memory/build_context() | LLM doesn't know when retrieved context is weak |
| Logprobs not requested from Ollama | inference/client.py `_call_ollama()` | Can't compute entropy-based uncertainty signal |
| Tool compliance not verified post-generation | handler.py post-inference | LLM can fabricate tool results undetected |
| Contradiction check only for knowledge graph | research/fact_extractor.py | Not applied to chat responses |
| No citation requirement in grounded responses | TOOL_INSTRUCTIONS | Model can assert facts without grounding marker |

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Validator role exists but cloud-gated; qwen2.5:0.5b already deployed for SLM intent classification; FactExtractor contradiction detection pattern proven; tool-first system prompt already enforces the right behavior direction; ChromaDB similarity scores computable cheaply | **Weaknesses:** Validator currently fails open (returns `is_safe=True` on parse error); logprobs not requested from Ollama; retrieval quality not surfaced to LLM; no post-generation tool compliance check; correction classifier is reactive not proactive |
| **External** | **Opportunities:** Ollama now exposes logprobs for entropy-based uncertainty gating (v0.12.11+); "SLM-default, LLM-fallback" enterprise pattern well-validated (Strathweb, 2025); Citation-grounded architecture proven at 92% accuracy in code comprehension systems (arxiv 2512.12117); RAGAS faithfulness metric is evaluatable locally | **Threats:** qwen2.5:0.5b hallucination rate documented (known DLA inference issues, MediaTek research); SLM Validator adds 80-150ms per response (same as O2 bypass saves); local verifier cannot itself be trusted without meta-verification; Ollama token probability API adds response payload size |

---

## Priority × Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **Layer 1: Tool-first enforcement gate** — Detect post-generation tool compliance violations (response claims data without tool call). Zero latency, pure string analysis. | **Logprob entropy threshold as soft warning** — Flag responses where per-token entropy > threshold for logging/metrics without blocking |
| **High Priority** | **Layer 2: Retrieval quality score injection** — Compute ChromaDB cosine scores, inject low-confidence context warning into system prompt. Pure Python, <1ms. | **Correction classifier upgrade** — Add hallucination-pattern matching to CorrectionType enum for analytics |
| **Low Priority** | **Layer 3: Local SLM Validator** — Promote Validator role to run on qwen2.5:0.5b when cloud disabled. Adds 80-150ms but catches broader hallucination categories. | **RAGAS-style faithfulness eval** — Offline batch evaluation harness (useful for regression testing, not runtime) |
| **Low Priority** | **Layer 4: Citation requirement for factual responses** — Inject citation enforcement into system prompt for FACTUAL intent class. Medium impact, requires intent routing change. | **Fine-tuned verifier model** — Overkill for single-user system; reserved for M5 Ultra upgrade era |

---

## Argue (Best Case)

### The Case for a Multi-Layer Hallucination Stack

**Evidence 1: The Validator already exists with the right prompt — just cloud-gated.**
The `Validator` role at `council/roles.py:150` already prompts for "No hallucinated data, no made-up information" and "did the response use tools?" The architectural work is already done. Promoting it to run locally on `qwen2.5:0.5b` (already deployed on Mac Mini) is a one-file change to `council/manager.py`. This is the highest-leverage move available.

**Evidence 2: Tool-first instruction exists; what's missing is a compliance check.**
The `TOOL_INSTRUCTIONS` string in `handler.py` already tells the model it must "NEVER fabricate results." The gap is post-generation verification: did the model actually call a tool when it referenced data? A string-pattern check against the response — "does this response reference data (calendar, health, notes, weather) without a corresponding tool call in the message history?" — catches the most common hallucination pattern with zero inference cost.

**Evidence 3: Retrieval quality signals are already computed, just not surfaced.**
ChromaDB returns cosine similarity scores alongside results. The vector store already uses `hnsw:space: cosine`. When the top-retrieved chunk has similarity < 0.6, the model is essentially generating from weak grounding. Injecting "WARNING: retrieved context has low relevance (score: X)" into the memory context section of the prompt is documented to reduce confabulation in RAG settings (RAGAS faithfulness research, 2025).

**Evidence 4: Ollama logprobs are production-ready.**
As of Ollama v0.12.11, `logprobs: true` in the request body returns per-token log probabilities. Computing per-response mean entropy is a 5-line addition to `_call_ollama()`. High entropy (> 2.0 nats) correlates with factual uncertainty and hallucination risk. This is the grey-box technique validated in arxiv 2405.19648.

**Evidence 5: SLM-as-verifier is an established enterprise pattern.**
The "SLM-default, LLM-fallback" pattern (Strathweb, 2025) and the SLM+LLM hybrid hallucination detection framework (arxiv 2408.12748) both demonstrate that an SLM used as a lightweight verifier — not generator — achieves acceptable accuracy at low latency. `qwen2.5:0.5b` runs at ~100ms on Ollama (confirmed for intent classification). A binary yes/no hallucination verdict is a much simpler task than intent classification.

**Evidence 6: The citation-grounded architecture achieves 92% accuracy in analogous systems.**
arxiv 2512.12117 documents a code comprehension system achieving 92% citation accuracy via mechanical verification that every cited range overlaps retrieved chunks. The same principle applies to Hestia: require that factual claims reference a source (tool result, memory chunk, knowledge graph fact) and mechanically verify presence before sending.

---

## Refute (Devil's Advocate)

### The Case Against Building This Now

**Argument 1: qwen2.5:0.5b cannot reliably verify hallucinations in qwen3.5:9b output.**
The verifier must be more capable than the generator for reliable detection. A 0.5B model verifying a 9B model's output on complex factual claims is architecturally unsound. The MediaTek research on Qwen2.5-0.5B DLA inference shows known hallucination issues in the 0.5B model itself. A false-negative from the verifier is worse than no verification (false confidence).

_Counter:_ The SLM Validator is not asked to generate facts — it's asked to classify a binary signal: "Does this response contain data claims that weren't grounded in the provided context?" This is a discrimination task, not generation. 0.5B models perform well on binary classification even when they're poor generators. Additionally, the logprob entropy gate is model-agnostic and does not rely on the SLM at all.

**Argument 2: The latency cost is unacceptable for a responsive personal assistant.**
Adding a 100ms SLM Validator to every response means: intent classification (100ms) + main inference (2-8s) + SLM Validator (100ms) = 200ms pure overhead. The O2 fast-path bypass explicitly saves 80-150ms for 65% of messages. This architecture gives back all those savings.

_Counter:_ The SLM Validator should only run on responses that (a) are not CHAT-classified (i.e., factual queries, data lookups) and (b) did not pass the Layer 1 tool compliance check (which is zero-latency). The O2 fast-path (chat messages under 8 words) would be explicitly excluded. Estimated exposure: ~15-25% of requests. Additionally, the Validator is already in `asyncio.gather()` for cloud mode — integrating it locally follows the same pattern.

**Argument 3: This duplicates the existing Correction Classifier — just let users report errors.**
The reactive signal from `CorrectionClassifier` already captures hallucination patterns as `CorrectionType.FACTUAL`. Adding proactive verification is over-engineering for a single-user system.

_Counter:_ The CorrectionClassifier operates on user-reported feedback. A hallucination that the user doesn't notice — or that causes them to make a wrong decision before noticing — is not captured at all. For health data, financial questions, or calendar queries, silent hallucinations are the dangerous category. Reactive correction is insufficient for factual domains.

**Argument 4: The Validator already fails open on parse errors, making it unreliable.**
`Validator.parse_response()` at `council/roles.py:187` returns `is_safe=True, is_high_quality=True` on any parse error. This means the verification is a false confidence signal — a parse failure looks identical to a clean response.

_Counter:_ This is a real bug, but the fix is a two-line change: log parse failures as verification_status = "unknown" rather than "passed". The fail-open behavior makes sense for safety (don't block responses) but should not be logged as "passed." This is fixable independently of the larger architecture.

---

## Third-Party Evidence

**HaluGate (vLLM blog, Dec 2025):** Token-level hallucination detection in production LLMs uses per-token conditional entropy. No secondary model required. Fast, explainable, and works on any model returning logprobs. Directly applicable to Hestia's Ollama `logprobs` integration.

**SLM Meets LLM (arxiv 2408.12748):** Hybrid SLM+LLM hallucination detection framework. The SLM does initial binary classification; the larger model provides explanations only when flagged. At Hestia's scale (single-user, personal assistant), the explanation layer can be skipped — only the binary flag matters.

**Citation-Grounded Code Comprehension (arxiv 2512.12117):** 92% citation accuracy via mechanical interval overlap verification. Zero hallucinations when citation is enforced architecturally. Key insight: enforcement through architecture beats probabilistic detection every time.

**AWS Automated Reasoning Checks (Nov 2025):** Up to 99% verification accuracy using formal verification constraints on factual claims. Overkill for Hestia but validates the principle that rule-based verification outperforms LLM-as-judge for structured facts.

**RAGAS Faithfulness (docs.ragas.io):** Fraction of statements in answer that can be confirmed by retrieved docs. Offline evaluation harness that can be used to benchmark Hestia's retrieval quality before and after improvements. Useful for establishing a baseline, not for runtime gating.

**Alternative approaches missed in initial research:**
- **Consistency sampling:** Generate N=3 responses at temperature 0.5, compare for factual consistency. High variance = high hallucination risk. Expensive (3x inference) but no secondary model required.
- **Structured output enforcement:** Require LLM to output JSON with `{"sources": [...], "response": "..."}` for factual queries, then verify source IDs exist in retrieved context. Tool-level grounding.
- **Negative prompting:** Inject "If you are not certain, say so rather than speculating" into system prompt for factual queries. Low-cost, degrades gracefully, does not require verification infrastructure.

---

## Recommendation

**Implement the 4-Layer Hallucination Prevention Stack in priority order:**

### Layer 1: Tool Compliance Gate (High Priority, High Impact, ~2 hours)
Add a post-generation check in `handler.py` after `_run_inference_with_retry()`. If the response references domain data (calendar, health, notes, email) without a corresponding tool call in the message context, flag it with `HallucinationRisk.TOOL_BYPASS` and append a soft disclaimer: *"[Note: I wasn't able to verify this from your actual data — please confirm.]"*

Implementation: pure string matching against response content and `conversation.messages[-1]` tool call history. Zero inference cost. No new dependencies.

**Confidence: High.** Catches the most common and highest-impact hallucination pattern (fabricated personal data) with minimal engineering.

### Layer 2: Retrieval Quality Score Injection (High Priority, High Impact, ~3 hours)
Modify `memory/manager.py build_context()` to return the top similarity score alongside the context string. In `handler.py`, inject a warning into the memory context block when the top score is < 0.6:

```
[Memory context — relevance: LOW (0.43). The retrieved context may not match the query precisely. Be explicit about uncertainty.]
```

This is the cheapest possible RAG faithfulness improvement: the model is told when its grounding is weak, shifting the probability toward uncertainty acknowledgment over confabulation.

**Confidence: High.** Documented to reduce hallucination in RAG settings. <1ms overhead. No new dependencies beyond what ChromaDB already returns.

### Layer 3: Local SLM Validator (Medium Priority, High Impact, ~4 hours)
Promote `Validator` from cloud-only to dual-path in `council/manager.py`. When cloud is disabled, run the Validator on `qwen2.5:0.5b` with the response text and the retrieved memory context as input. Parse the `ValidationReport` with `is_high_quality=False` + `quality_score < 0.5` as a soft flag, not a block.

Fix the fail-open logging bug: rename `is_safe=True` on parse error to `verification_status="parse_error"` so dashboards don't show false positives.

**Confidence: Medium.** The SLM will catch obvious hallucinations (responses with fabricated dates, names, numbers) but may miss subtle confabulation. Acceptable for a single-user system where the cost of false negatives is low.

### Layer 4: Logprob Entropy Gate (Low Priority, High Impact, ~3 hours)
Add `logprobs: true` to the Ollama `/api/chat` request body in `inference/client.py _call_ollama()`. Compute mean log probability across response tokens. Attach as `InferenceResponse.mean_logprob`. Surface in API response metadata and `learning/meta_monitor.py` metrics. Use entropy > 2.5 nats as a soft flag for logging and future model tuning signals.

Do not use logprob entropy as a hard block (too many false positives). Use as a signal for the MetaMonitor's hallucination tracking dashboard.

**Confidence: Medium.** Ollama's logprob API is confirmed production-ready. Entropy correlates with hallucination risk but is not a reliable per-claim detector. Best used for aggregate monitoring rather than per-response gating.

### What to Skip

- **Fine-tuned verifier model:** Overkill. Reserve for M5 Ultra era when 14B+ verifier models can run without swapping.
- **Consistency sampling (N=3):** 3x inference cost is prohibitive on M1.
- **RAGAS offline evaluation:** Valuable for benchmarking retrieval quality improvements, but not a runtime concern. Defer to a dedicated evaluation sprint.
- **Structured output enforcement for all factual queries:** Too disruptive to the current response format. Implement selectively (health data queries only) if Layer 1 fails to close the gap.

**What would change this recommendation:**
- If logprob entropy achieves >85% hallucination detection F1 in offline testing → promote Layer 4 to a hard gate for factual queries.
- If the SLM Validator triggers false positives on >10% of responses → demote it to metrics-only and invest in retrieval quality instead.
- If cloud routing moves back to `disabled` as the default → Layer 3 becomes critical path.

---

## Final Critiques

### The Skeptic — "Why won't this work?"

**Challenge:** "The Validator is already in the codebase and already doesn't work — it fails open on parse errors, it's cloud-only, and the system has been running for 16+ sprints without it being fixed. If it mattered, it would have been fixed already. This is archaeology."

**Response:** The Validator was originally designed as a cloud enhancement — a nice-to-have when Anthropic is already paying for tokens. The decision to run it locally never came up because cloud was off by default. The architectural gap is real; the oversight is timing, not neglect. Layer 1 (tool compliance) and Layer 2 (retrieval quality injection) have no history of being bypassed — they've simply never been built. The fail-open Validator bug is a 2-line fix that predates any new architecture.

### The Pragmatist — "Is the effort worth it?"

**Challenge:** "This is a personal assistant for one user. How often does Andrew actually receive and act on a hallucinated response? The correction classifier would catch it. The real ROI is unclear for 12 hours of implementation."

**Response:** The ROI argument is strongest for health data (get_vitals, get_health_trend) and calendar queries — the two domains where acting on a fabricated response has real-world consequences. Even one incorrect health metric surfaced as a confident assertion is a category mismatch with Hestia's design intent. Layers 1 and 2 are each under 3 hours and require no new infrastructure. The full 4-layer stack is a 12-hour sprint, not a 4-week project. The incremental cost per layer is low; the incremental risk reduction per layer is not.

### The Long-Term Thinker — "What happens in 6 months?"

**Challenge:** "In 6 months, you're on an M5 Ultra with DeepSeek-R1-70B as primary. Qwen3.5-9B hallucination rate becomes irrelevant. All this verification infrastructure is dead weight."

**Response:** Layer 1 (tool compliance gate) and Layer 2 (retrieval quality injection) are model-agnostic — they operate on context quality and response structure, not model-specific behavior. They will be valuable for any model tier. Layer 3 (SLM Validator) and Layer 4 (logprobs) may need tuning for larger models but the architecture ports cleanly. The MetaMonitor integration (Layer 4) becomes more valuable on M5 Ultra — you'll have richer entropy data for model comparison. The code cost is low; the forward compatibility is high.

---

## Open Questions

1. **What is the current hallucination rate?** There is no baseline. Before implementing, run a 20-query offline test across health, calendar, notes, and general chat domains to establish a measurement baseline. Log `CorrectionType.FACTUAL` corrections for the past 30 days from the LearningDatabase.

2. **Does Ollama on the Mac Mini support logprobs?** Confirm Ollama version on `andrewroman117@hestia-3.local`. The feature requires v0.12.11+. Run `curl http://localhost:11434/api/version` post-deploy.

3. **What is qwen2.5:0.5b's binary classification accuracy for "is this a hallucination"?** Run a 10-sample offline test with known hallucinated responses before trusting it as a verification layer. Use `FactExtractor`'s contradiction dataset for test cases.

4. **Should the retrieval quality threshold (< 0.6) be configurable?** Consider adding `hallucination_guard.retrieval_quality_threshold: 0.6` to `memory.yaml` for tunability without code changes.

5. **How should the iOS/macOS app surface verification warnings?** A subtle indicator (amber dot, asterisk) on responses with `HallucinationRisk.TOOL_BYPASS` or low retrieval confidence would be cleaner than inline text disclaimers. This requires API schema changes and a Sprint 18 iOS/macOS task.

---

## Implementation Sketch (Sprint 18 Candidate)

```
New module: hestia/verification/
├── models.py          — HallucinationRisk enum, VerificationResult dataclass
├── tool_compliance.py — Layer 1: post-generation tool bypass detector
├── verifier.py        — Layer 3: SLM Validator bridge (delegates to council)
└── manager.py         — VerificationManager singleton, routes all 4 layers

Modifications:
├── hestia/memory/manager.py         — build_context() returns (str, float) with top score
├── hestia/orchestration/handler.py  — inject retrieval score, call VerificationManager
├── hestia/council/manager.py        — Validator dual-path (cloud OR local SLM)
├── hestia/inference/client.py       — Add logprobs to _call_ollama(), attach to InferenceResponse
└── hestia/learning/meta_monitor.py  — Track verification_flags in MetaMonitorReport

New LogComponent: VERIFICATION (add to enum)
New config block: memory.yaml → hallucination_guard section
```

**Estimated effort:** 12-16 hours. Fits a single sprint as a parallel track alongside Sprint 18 feature work, or as a dedicated Sprint 18 if quality is the sprint theme.
