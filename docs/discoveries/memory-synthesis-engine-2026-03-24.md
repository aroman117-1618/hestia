# Discovery Report: Memory Synthesis Engine

**Date:** 2026-03-24
**Confidence:** High
**Decision:** Build a lightweight Memory Synthesis Engine as a new scheduled loop in LearningScheduler, connecting the existing but currently isolated memory, principle, and knowledge graph systems into a unified reflective cycle. Hestia already has 80% of the pieces — this is integration work, not a greenfield build.

## Hypothesis

An autonomous, periodic "dream-like" synthesis process that reviews accumulated memories, detects cross-domain patterns, extracts higher-order principles, and feeds them into the PrincipleStore and Knowledge Graph would significantly improve Hestia's long-term reasoning quality, reduce redundant memory retrieval, and create a self-reinforcing learning loop.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Separate episodic (ChromaDB) and semantic (KG) stores already exist. PrincipleStore + distillation pipeline operational. 10-loop LearningScheduler provides scheduling infrastructure. Crystallization loop already demonstrates pattern promotion. ImportanceScorer already bridges memory + KG (durability_score). | **Weaknesses:** Current distillation is batch-only with no cross-domain pattern detection. No feedback loop from KG insights back to memory scoring. PrincipleStore distillation and fact extraction operate in isolation — principles don't inform fact extraction, and facts don't inform principle distillation. No "reflection" step that synthesizes across all three stores. |
| **External** | **Opportunities:** Cross-system synthesis (memories + facts + outcomes + principles = new insights). Principle reinforcement via usage tracking. Automated knowledge graph enrichment from principle clusters. Temporal pattern detection (user behavior changes over weeks/months). Hestia could generate its own "morning briefing" of what it learned overnight. | **Threats:** LLM cost on M1 (each synthesis cycle = multiple inference calls). Over-consolidation losing valuable specifics (the "banality trap" from Stanford's Generative Agents). Complexity creep in an already rich learning pipeline. Incorrect synthesized principles polluting downstream reasoning. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Cross-store pattern detection (memories → facts → principles feedback loop). KG-to-memory feedback (fact durability influences memory importance). Synthesis scheduling in existing LearningScheduler. | Principle usage tracking (which principles get retrieved and help). |
| **Low Priority** | Temporal behavioral drift detection (multi-month patterns). Auto-generated "dream journal" / morning briefing. | Custom visualization of synthesis results in macOS app. Fancy sleep-phase naming conventions. |

## Argue (Best Case)

**The integration gap is real and measurable.** Hestia currently has three knowledge stores that barely talk to each other:

1. **Memory** (ChromaDB + SQLite) — episodic chunks with importance scores
2. **PrincipleStore** (ChromaDB + SQLite) — distilled behavioral rules, pending approval
3. **Knowledge Graph** (SQLite) — entity-relationship facts with temporal metadata

The only current cross-system links are:
- ImportanceScorer reads durability scores from KG facts (one-directional)
- PrincipleStore distills from memory chunks (one-directional)
- Crystallization promotes ephemeral facts (KG-internal only)

**Missing connections that synthesis would create:**
- Principles should inform which facts are worth extracting (if a principle says "user prefers morning meetings," new calendar facts about morning meetings should get higher durability)
- Clusters of related facts should generate principle candidates (if 5 facts involve "Andrew + Python + testing," a principle about testing preferences should emerge)
- Memory importance should factor in principle relevance (chunks that sourced approved principles should get importance boosts)
- Outcome signals should propagate to the KG (if a response using KG facts got positive feedback, those facts should get confidence boosts)

**Evidence from research:**
- Stanford Generative Agents showed reflection was **critical** for agents to connect disparate observations into coherent understanding
- Voyager (NVIDIA) achieved 63% more unique discoveries and 15.3x faster tool-building through its synthesis/skill-library loop
- A-MEM (NeurIPS 2025) demonstrated that Zettelkasten-style interconnected memory notes with dynamic re-linking outperformed static memory baselines
- EverMemOS (Jan 2026) achieved 83% accuracy on LongMemEval with a 20.6% gain specifically on knowledge update tasks — exactly the kind of task synthesis enables
- Zep's temporal knowledge graph with bi-temporal fact tracking (which Hestia already has) is cited as the foundation for sophisticated memory consolidation

**Hestia's advantage:** Most of these systems built their memory infrastructure from scratch. Hestia already has the stores, the scheduling, the distillation prompts, and the entity resolution. This is a **wiring project**, not a new module.

## Refute (Devil's Advocate)

**1. The "Banality Trap" is real.**
Stanford's Generative Agents research explicitly documents that without careful prompt engineering, reflections degenerate into trivial statements ("I should make breakfast tomorrow"). Hestia's current PrincipleStore already has a quality gate (MIN_PRINCIPLE_WORDS=10, generic blacklist), but synthesis across multiple stores creates new failure surfaces. A synthesized principle like "Andrew uses Python" is true but worthless.

**2. LLM resource contention on M1.**
Each synthesis cycle would require multiple LLM calls (pattern detection, principle extraction, fact enrichment). On a 16GB M1 running Ollama with qwen3.5:9b, this means:
- ~1-2GB VRAM per inference call
- ~2-5 seconds per call
- A full synthesis cycle might need 5-10 LLM calls
- During synthesis, chat latency could spike

The existing LearningScheduler already runs 10 loops — adding more LLM-heavy tasks compounds the risk. The crystallization loop already runs at "low priority" (2-hour startup delay) because of this concern.

**3. Complexity vs. value at current scale.**
Hestia has one user (Andrew) with ~12 hours/week of interaction. The volume of memories, facts, and outcomes is relatively low. The marginal value of cross-store synthesis when you have 200 memory chunks is different from when you have 20,000. The current isolated pipelines may be sufficient for the current scale.

**4. Principle approval bottleneck.**
All principles enter as "pending" and require user approval. If synthesis generates 10 new cross-domain principles per week, that's 10 more items Andrew needs to review. Without auto-approval for high-confidence principles, the synthesis output may pile up unused.

**5. Incorrect synthesis can poison downstream.**
A synthesis that incorrectly links "Andrew mentioned Bitcoin" (trading context) with "Andrew's friend mentioned cryptocurrency" (social context) could generate a principle that distorts both domains.

## Third-Party Evidence

### Confirming Evidence
- **EverMemOS** (Jan 2026) validates the three-phase architecture (episodic → semantic consolidation → retrieval) that Hestia's synthesis engine would formalize. Their 20.6% gain on knowledge updates is directly relevant.
- **Zep/Graphiti** (Jan 2025) validates bi-temporal knowledge graphs as the right foundation for agent memory. Hestia already has this via the research module (ADR-041).
- **A-MEM** (NeurIPS 2025) validates that memory systems benefit from dynamic re-linking and context evolution, not just static storage.

### Contradicting Evidence
- No major production personal assistant (Siri, Alexa, Google Assistant) has publicly documented deploying dream-like synthesis. The risk profile for incorrect principles is too high without human-in-the-loop — which Hestia already has via the approval gate.
- Gemini's research confirms that catastrophic forgetting (overwriting useful specifics during consolidation) is a real failure mode documented in DeepMind's work.

### Alternative Approaches Not Initially Considered
- **Embedding-only synthesis (no LLM):** Instead of using LLM for pattern detection, use ChromaDB embedding clustering (HDBSCAN or similar) to find memory clusters, then only invoke LLM for the final principle extraction from pre-identified clusters. This reduces LLM calls by 60-80%.
- **Tiered model cascade:** Use qwen2.5:0.5b (the existing council SLM, ~100ms) for initial pattern screening, then qwen3.5:9b only for confirmed synthesis candidates. Mirrors the O2 fast-path bypass pattern already in the council.

## Gemini Web-Grounded Validation

**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- Dream-like synthesis is not yet standard in production personal assistants — confirming that this is cutting-edge but not proven at consumer scale
- Stanford Generative Agents' reflection mechanism is the closest analogue and demonstrated clear value for connecting disparate observations
- The "banality trap" (trivial reflections) is a documented failure mode requiring explicit quality gates
- M1 hardware is viable for on-device LLM synthesis using quantized models via Ollama/llama.cpp, with 4-bit quantization leaving ample headroom

### Contradicted Findings
- None of the SWOT items were directly contradicted by web evidence

### New Evidence
- **Voyager** (NVIDIA, 2023): 63% more unique discoveries and 15.3x faster tool-building through synthesis loop — quantifies the value of a store-and-synthesize approach
- **Catastrophic forgetting** is a well-documented failure mode from DeepMind's work — consolidation can overwrite previously learned patterns. Mitigation: never delete source memories during synthesis, only create new derived artifacts
- **Process scheduling**: macOS `nice` command and `launchd` idle-time triggers are practical ways to prevent synthesis from starving interactive processes

### Sources
- [Stanford Generative Agents (2023)](https://arxiv.org/abs/2304.03442)
- [A-MEM: Agentic Memory for LLM Agents (NeurIPS 2025)](https://arxiv.org/abs/2502.12110)
- [EverMemOS: Self-Organizing Memory OS (Jan 2026)](https://arxiv.org/abs/2601.02163)
- [Zep: Temporal Knowledge Graph for Agent Memory (Jan 2025)](https://arxiv.org/abs/2501.13956)
- [Voyager: Open-Ended Embodied Agent (NVIDIA, 2023)](https://voyager.minedojo.org/)
- [Memory in the Age of AI Agents survey (Dec 2025)](https://arxiv.org/abs/2512.13564)
- [ICLR 2026 MemAgents Workshop Proposal](https://openreview.net/pdf?id=U51WxL382H)

## Philosophical Layer

### Ethical Check
Memory synthesis is inherently about building a model of the user's behavior and preferences. This is ethical in Hestia's context because:
- All data stays local (Mac Mini, no cloud storage)
- User has explicit approval gate on all principles
- Synthesis is transparent (logged, auditable, reversible)
- No data leaves the system without approval (CommGate)

The risk is more about **correctness than ethics** — an incorrect principle could subtly degrade response quality without the user noticing.

### First Principles Challenge
**Why periodic synthesis at all?** The alternative is real-time synthesis — extracting patterns and updating the KG immediately after each conversation. This is what A-MEM does. But real-time synthesis on M1 hardware would add 2-5 seconds to every chat response, which violates the latency budget. Periodic (nightly) synthesis decouples learning from serving, which is the right tradeoff for resource-constrained hardware.

**Is there a simpler approach?** Yes: instead of building a new "synthesis engine," wire the existing components together with a single new scheduled loop that:
1. Queries approved principles → boosts importance of source memory chunks
2. Queries high-durability facts → suggests principle candidates
3. Queries positive-signal outcomes → boosts linked fact confidence

This is 90% of the value for 30% of the complexity. Call it "Memory Cross-Pollination" instead of "Synthesis Engine."

### Moonshot: Self-Evolving Knowledge Architecture
**What it is:** Instead of separate stores with cross-links, build a unified "engram" store where every piece of knowledge (memory chunk, fact, principle, outcome) is a node in a single graph, with typed edges representing all relationships. The graph itself has a "metabolism" — edges decay, strengthen, or form based on usage patterns. No explicit consolidation needed; the graph structure IS the synthesis.

**Technical viability:** Partially. Neo4j or a similar graph DB could replace the current SQLite+ChromaDB split. But:
- Requires migrating all existing data
- Graph DB performance on M1 is unproven at scale
- ChromaDB's embedding search is hard to replicate in a graph DB
- The existing module architecture (clean manager pattern) would need significant restructuring

**Effort:** 80-120 hours (including migration, testing, UI updates)
**Risk:** High — too many moving parts change at once
**MVP:** Could prototype with a "virtual graph" overlay on existing stores (computed views, not physical migration)
**Verdict:** SHELVE. The simpler cross-pollination approach gets most of the value. Revisit for M5 Ultra when hardware isn't a constraint.

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | All local, no new external data flows, existing audit trail covers synthesis |
| Empathy | 4 | Directly improves Hestia's understanding of Andrew over time; -1 for risk of incorrect principles |
| Simplicity | 4 | Leverages existing infrastructure; the "cross-pollination" framing keeps it minimal |
| Joy | 4 | The idea of Hestia "dreaming" and getting smarter overnight is genuinely compelling |

## Recommendation

**Build the Memory Cross-Pollination Loop** — a single new scheduled task in LearningScheduler that wires together the existing memory, principle, and knowledge graph systems. This is NOT a new module; it's a new loop function (~200-300 lines) that:

1. **Principle → Memory feedback** (nightly): Query approved principles, find their source chunk IDs, boost those chunks' importance scores by 0.1
2. **Fact cluster → Principle suggestion** (weekly): Query facts grouped by entity pair, identify clusters of 3+ facts between the same entities, generate principle candidates via LLM
3. **Outcome → Fact confidence** (nightly): Query positive-signal outcomes, find linked memory chunks, find facts extracted from those chunks, boost their confidence by 0.05
4. **Embedding-based cross-domain detection** (weekly): Use ChromaDB to find memory clusters that span multiple chunk_types (e.g., a conversation chunk similar to a research chunk similar to a decision chunk), surface these as synthesis candidates

**Confidence: High.** The evidence strongly supports cross-store integration, the existing infrastructure is ready, and the incremental approach minimizes risk. The M1 hardware constraint is manageable with the tiered model approach (SLM screening + full model for confirmed candidates).

**Estimated effort:** 12-16 hours total
- Phase 1 (8h): Cross-pollination loop with steps 1-3 (no new LLM calls, pure SQL/embedding queries)
- Phase 2 (4-8h): Step 4 (embedding clustering + LLM synthesis for cross-domain patterns)

**What would change this recommendation:**
- If M1 inference latency during synthesis causes noticeable chat degradation → defer Phase 2 to M5 Ultra
- If principle approval queue grows faster than Andrew reviews → add auto-approval for principles with confidence > 0.85 and matching existing approved domain
- If synthesis generates mostly trivial principles → tighten quality gate, add diversity scoring

## Final Critiques

### The Skeptic: "Why won't this work?"
**Challenge:** "The existing distillation pipeline already generates principles weekly. Adding cross-store links won't generate meaningfully better principles — you'll just get the same insights from a different angle."

**Response:** The current pipeline operates in silos. Outcome distillation sees outcomes. Memory distillation sees chunks. Fact extraction sees text. None of them see the full picture. The value isn't in better individual principles — it's in the *connections between systems* that no single pipeline can see. Example: if fact extraction finds "Andrew → USES → Coinbase" and outcome tracking shows positive responses about trading, the cross-pollination can suggest a principle about trading preferences that neither system would generate alone.

### The Pragmatist: "Is the effort worth it?"
**Challenge:** "12-16 hours for incremental improvement to a system with one user. Is this the highest-value use of time compared to, say, finishing Sprint 27.5 or starting Sprint 28?"

**Response:** Fair point. Phase 1 (8h, no LLM) is the high-value slice — it's pure wiring that makes existing data more useful with zero ongoing cost. Phase 2 can wait. The trading module sprints have clear priority. This is a "between sprints" project or a good autonomous Claude Code task.

### The Long-Term Thinker: "What happens in 6 months?"
**Challenge:** "In 6 months, Hestia will have 6 months more memories, facts, and principles. Will the cross-pollination loop still work, or will it become a bottleneck?"

**Response:** Phase 1 (SQL queries + importance adjustments) scales linearly with data volume — even with 10x more data, the queries are indexed and fast. Phase 2 (embedding clustering) could become expensive at scale, but ChromaDB supports efficient approximate nearest neighbor search. The bigger risk is principle queue growth — auto-approval with confidence gating is the planned mitigation. On M5 Ultra (summer 2026), the hardware constraint disappears entirely.

## Open Questions

1. **Auto-approval threshold:** What confidence level justifies auto-approving principles? 0.85? 0.90? Needs experimentation.
2. **Synthesis cadence:** Nightly for feedback loops, weekly for LLM synthesis — is this right, or should both be weekly to reduce resource pressure?
3. **Cross-domain diversity:** How to ensure synthesis doesn't over-index on the most active domain (currently trading)? May need domain-balanced sampling.
4. **Observability:** Should synthesis results be surfaced in the macOS app (a "what Hestia learned" panel) or just logged?
5. **Principle retirement:** If a principle hasn't influenced any response in 90 days, should it be auto-archived?
