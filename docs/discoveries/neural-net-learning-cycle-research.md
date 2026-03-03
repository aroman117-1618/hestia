# Neural Net Learning Cycle: Deep Research for Hestia

**Date:** 2026-03-03
**Author:** Claude (Discovery Agent)
**Classification:** Strategic Research — Architecture Evolution
**Scope:** Making commands obsolete, self-evaluation loops, curiosity-driven exploration

---

## Executive Summary

This document presents a DARPA/MIT-grade analysis of how Hestia can evolve from a command-driven assistant into a self-improving, anticipatory intelligence. The research spans five domains: self-evolving agent architectures, metacognitive control theory, curiosity-driven exploration, predictive coding from computational neuroscience, and reflective LLM agent patterns. We propose three architectural options mapped to Hestia's existing stack, each with full SWOT analysis.

The core thesis: **Hestia's next leap isn't a feature — it's a feedback topology change.** The system must close the loop between action, outcome, reflection, and adaptation so that every interaction makes the next one smarter, quieter, and more anticipatory.

---

## Part I: The Landscape

### 1.1 Self-Evolving Agents (The "What")

Two landmark 2025 surveys define the field. The first, "A Comprehensive Survey of Self-Evolving AI Agents" (arXiv 2508.07407), introduces a unified framework with three evolution dimensions:

- **What evolves:** The agent's knowledge base, tool repertoire, behavioral policies, or generative model itself
- **When it evolves:** Online (during interaction), offline (batch reflection), or triggered (by failure/anomaly detection)
- **How it evolves:** Experience replay, self-distillation, reinforcement from outcomes, or evolutionary search

The **EvolveR framework** (arXiv 2510.16079, Oct 2025) is particularly relevant to Hestia because it was validated on **Qwen2.5 models from 0.5B to 3B parameters** — the same model family Hestia uses. EvolveR implements a closed-loop lifecycle:

```
┌─────────────────────────────────────────────────────┐
│                  EvolveR Lifecycle                    │
│                                                       │
│  ┌──────────┐    ┌──────────────┐    ┌────────────┐  │
│  │  Online   │───▶│   Distill    │───▶│  Principle  │  │
│  │Interaction│    │ Trajectories │    │ Repository  │  │
│  └─────▲────┘    └──────────────┘    └─────┬──────┘  │
│        │                                    │         │
│        │         ┌──────────────┐           │         │
│        └─────────│   Retrieve   │◀──────────┘         │
│                  │  Principles  │                      │
│                  └──────────────┘                      │
└─────────────────────────────────────────────────────┘
```

**Key insight:** The agent doesn't memorize interactions — it *distills principles* from them. "Andrew always wants a summary before detail" becomes a retrievable strategic principle, not a raw memory.

### 1.2 Metacognitive Control Loops (The "How It Knows What It Doesn't Know")

The MIDCA architecture (Metacognitive Integrated Dual-Cycle Architecture, AAAI) provides the theoretical foundation for self-aware AI agents. It overlays a metacognitive monitoring loop on top of the standard perception-reasoning-action (PRA) cycle:

```
┌─────────────────────── META-LEVEL ─────────────────────────┐
│                                                              │
│   MONITOR ──▶ EVALUATE ──▶ DIAGNOSE ──▶ ADAPT/REPAIR       │
│      ▲                                       │               │
│      │                                       ▼               │
│  ┌───┴────────────── OBJECT-LEVEL ───────────────────────┐  │
│  │                                                        │  │
│  │  PERCEIVE ──▶ INTERPRET ──▶ PLAN ──▶ ACT ──▶ ASSESS   │  │
│  │                                                        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

A June 2025 paper "Truly Self-Improving Agents Require Intrinsic Metacognitive Learning" (arXiv 2506.05109) argues that current self-improving agents are superficial because they lack three critical components:

1. **Metacognitive Knowledge** — Self-assessment of capabilities, task difficulty, and strategy repertoire ("I'm good at scheduling but bad at predicting Andrew's research interests")
2. **Metacognitive Planning** — Deciding *what* and *how* to learn next ("I should pay more attention to which emails Andrew opens immediately vs. ignores")
3. **Metacognitive Evaluation** — Reflecting on whether the learning itself was effective ("My pattern detection for Friday budget reviews was wrong 40% of the time — the pattern is actually biweekly")

A 2025 "Agentic Metacognition" paper (arXiv 2509.19783) proposes a practical architecture: a secondary metacognitive layer that monitors the primary agent for failure signals — excessive latency, repetitive actions, user corrections, confidence drops — and triggers handoff or strategy adaptation.

### 1.3 Curiosity-Driven Exploration (The "Why It Asks Questions You Didn't")

The foundational work is Pathak et al.'s **Intrinsic Curiosity Module (ICM)** (ICML 2017), which formalizes curiosity as prediction error in a learned feature space:

```
Curiosity Reward = || f_predicted(s_{t+1}) - f_actual(s_{t+1}) ||²
```

Where:
- `f()` is a learned feature encoder (ignores irrelevant environmental noise)
- The agent is intrinsically rewarded for encountering states it *cannot predict*
- This drives exploration toward novel, informative territory

The 2025 **CDE framework** (arXiv 2509.09675) extends this to LLM agents specifically, formalizing curiosity through dual signals from actor (policy uncertainty) and critic (value estimation uncertainty). When the agent is uncertain about both *what to do* and *how good the outcome would be*, that's maximum curiosity — and maximum learning opportunity.

**For Hestia, this translates to:** The system should be most engaged (asking questions, proposing experiments, seeking new data) precisely in the domains where its predictions about Andrew's behavior are least accurate. If Hestia can predict Andrew's morning routine with 95% accuracy but his weekend project choices with 30% accuracy, the curiosity drive should focus energy on understanding weekend patterns.

### 1.4 Predictive Coding & Active Inference (The Neuroscience Foundation)

Karl Friston's **Free Energy Principle** provides the deepest mathematical framework. Biological brains — and by extension, effective AI agents — minimize *variational free energy*, which is an upper bound on surprise:

```
F = E_q[log q(s) - log p(o, s)]

Where:
  F = variational free energy (what we minimize)
  q(s) = agent's beliefs about hidden states
  p(o, s) = generative model of observations and states
  o = observations (what actually happened)
```

This means the agent has two paths to minimize surprise:
1. **Perceptual inference** — Update beliefs to better match reality (learning)
2. **Active inference** — Act on the world to make reality match expectations (proactive behavior)

A July 2025 paper proposes a **Neuro-Inspired Computational Framework for AGI** combining predictive coding, active inference, and hierarchical generative models. The key architectural insight: generative models should be *hierarchical*, with abstract layers predicting slow-changing patterns (Andrew's personality, work rhythm) and concrete layers predicting fast-changing details (today's specific tasks).

**Active Predictive Coding (APC)** from MIT Press (Neural Computation, 2024) unifies perception, action, and cognition through task-invariant state transition networks combined with task-dependent policy networks at multiple abstraction levels. This is exactly the architecture for an agent that simultaneously understands "Andrew works on Hestia in ~6hr/week windows" (abstract) and "Andrew is debugging the auth flow right now" (concrete).

### 1.5 Reflective LLM Agents (The Practical Implementation Layer)

The **Reflexion** architecture provides the most immediately implementable pattern. After each task, the agent:

1. **Acts** — Attempts the task
2. **Observes** — Collects outcome signals (success/failure, user satisfaction, time taken)
3. **Reflects** — Self-critiques using structured prompts ("What went wrong? What would I do differently?")
4. **Updates** — Stores the reflection as episodic memory for future retrieval

Performance gains from self-reflection are substantial: 9-18.5 percentage point improvements on problem-solving benchmarks, and Reflexion-augmented GPT-4 reaching 91% on HumanEval vs. 80% without.

LangChain's reflection pattern implements this as a two-node graph: Generator → Reflector → Generator (loop), with the reflector having access to external tools for fact-checking its own output. The "Introspection of Thought" paper (arXiv 2507.08664, July 2025) extends this with structured introspection protocols that go beyond simple self-critique.

### 1.6 DARPA L2M: Lifelong Learning Machines

DARPA's Lifelong Learning Machines (L2M) program provides the government-research-grade framework for what Hestia aspires to. Key principles:

- **Continual learning** without catastrophic forgetting (the agent doesn't lose old skills when learning new ones)
- **Dual-memory architecture** inspired by hippocampus (fast learning, episodic) and cortex (slow consolidation, semantic)
- **Transfer learning** — applying knowledge from one domain to novel situations
- **Bio-inspired play** — unstructured exploration that builds foundational competencies (USC demonstrated a robot learning to walk after 5 minutes of "play")

---

## Part II: Hestia's Current Architecture (Gap Analysis)

Hestia already has significant primitives that map to these research frameworks:

| Research Concept | Hestia Primitive | Gap |
|---|---|---|
| Experience Memory | MemoryManager (ChromaDB + SQLite) | ✅ Exists. Lacks *experience distillation* — raw memories but no extracted principles |
| Temporal Relevance | TemporalDecay (per-chunk-type λ) | ✅ Exists. But decay is passive — no active *relevance learning* from outcomes |
| Pattern Detection | PatternDetector (day/time/activity keywords) | ⚠️ Keyword-based, not learned. Can't discover patterns it doesn't have templates for |
| Proactive Behavior | BriefingGenerator + InterruptionPolicy | ⚠️ Generates briefings but doesn't learn which parts Andrew values vs. ignores |
| Multi-Role Reasoning | CouncilManager (4 roles, dual-path) | ✅ Strong. Missing the metacognitive *5th role* — a Monitor that evaluates the council itself |
| Outcome Tracking | None | ❌ Critical gap. No closed loop between "what Hestia did" and "how it went" |
| Self-Evaluation | None | ❌ Critical gap. No reflection cycle, no performance scoring |
| Curiosity/Exploration | None | ❌ No mechanism to identify knowledge gaps or ask probing questions |
| Principle Distillation | None | ❌ Memories are stored but never synthesized into reusable behavioral rules |

**The fundamental missing piece is the Outcome Signal.** Hestia acts but never measures the result. Without outcome data, no learning loop can close.

---

## Part III: Three Proposed Architectures

### Option A: "The Reflection Engine" (Reflexion + Experience Distillation)

**Philosophy:** Every interaction is a learning episode. After each conversation, Hestia reflects, extracts principles, and updates its behavioral policy.

**Architecture:**

```
                    ┌─────────────────────────┐
                    │     PRINCIPLE STORE      │
                    │  (Distilled Strategies)  │
                    └────────▲────────┬────────┘
                             │        │
                    ┌────────┴──┐  ┌──▼────────┐
                    │  DISTILL  │  │  RETRIEVE  │
                    └────────▲──┘  └──┬────────┘
                             │        │
┌──────────┐    ┌────────────┴────────▼──────────────┐    ┌───────────┐
│  USER     │───▶│         INTERACTION LOOP          │───▶│  OUTCOME  │
│  REQUEST  │    │  Council → Plan → Act → Respond   │    │  TRACKER  │
└──────────┘    └────────────────────────────────────┘    └─────┬─────┘
                                                                │
                    ┌───────────────────────────────┐          │
                    │        REFLECTION AGENT        │◀─────────┘
                    │  • What worked?                │
                    │  • What signals did I miss?    │
                    │  • What would I do differently?│
                    └───────────────────────────────┘
```

**New Components:**
1. **OutcomeTracker** — Records implicit signals: Did Andrew modify the response? Ask follow-up corrections? Use the output? How quickly? Did he come back with the same topic (indicating failure)?
2. **ReflectionAgent** — Post-interaction LLM call that self-critiques the session using CoT, with access to outcome data
3. **PrincipleStore** — New ChromaDB collection storing distilled strategies (separate from raw memories), retrievable by similarity to current context
4. **PolicyUpdater** — Adjusts behavioral weights (e.g., "prefer concise over detailed for scheduling requests") based on accumulated reflections

**Outcome Signals (implicit, no extra burden on Andrew):**
- Response accepted without edits → positive signal
- Follow-up clarification on same topic → negative signal (didn't understand)
- Thumbs up/down if implemented → direct signal
- Time-to-next-message (long gap after response = likely useful; immediate follow-up = likely insufficient)
- Same request pattern recurring → Hestia should have anticipated this

**Integration with Hestia:**
- ReflectionAgent runs as a 5th Council role (post-hoc, not in the hot path)
- PrincipleStore is a new ChromaDB collection alongside existing memory
- OutcomeTracker hooks into the chat endpoint response cycle
- Runs on Qwen 2.5 7B locally (reflection prompts are well within capability)

---

### Option B: "The Metacognitive Dual-Cycle" (MIDCA-Inspired)

**Philosophy:** Separate the "doing" from the "thinking about doing." A meta-level continuously monitors the object-level for anomalies, failures, and opportunities.

**Architecture:**

```
┌────────────────────────── META-COGNITIVE LAYER ──────────────────────────┐
│                                                                           │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐  │
│  │ MONITOR  │──▶│   EVALUATE   │──▶│   DIAGNOSE   │──▶│    ADAPT     │  │
│  │          │   │              │   │              │   │              │  │
│  │• Latency │   │• Confidence  │   │• Root cause  │   │• Update      │  │
│  │• Repeats │   │• User sat.   │   │  analysis    │   │  weights     │  │
│  │• Failures│   │• Prediction  │   │• Knowledge   │   │• Add rules   │  │
│  │• Drift   │   │  accuracy    │   │  gap ID      │   │• Retrain     │  │
│  └──────────┘   └──────────────┘   └──────────────┘   └──────────────┘  │
│       ▲                                                       │          │
│       │              ┌────────────────────────┐               │          │
│       └──────────────│    OBJECT LEVEL        │◀──────────────┘          │
│                      │  (Existing Hestia)     │                          │
│                      │  Council + Orchestrator │                          │
│                      │  + Memory + Execution   │                          │
│                      └────────────────────────┘                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**New Components:**
1. **MetaMonitor** — Runs as a background async task, analyzing interaction logs for:
   - Excessive back-and-forth on single topics (confusion loops)
   - Declining response acceptance rates
   - Increasing latency in specific domains
   - Pattern drift (user behavior changing, Hestia's models becoming stale)
2. **ConfidenceCalibrator** — Tracks prediction accuracy across domains. When Hestia predicts Andrew wants X and he actually wants Y, the calibrator adjusts domain-specific confidence scores
3. **KnowledgeGapDetector** — Identifies areas where Hestia has low confidence AND low data (the true "unknown unknowns"). Generates questions for Andrew at appropriate moments
4. **AdaptiveStrategySelector** — Maintains a repertoire of behavioral strategies (verbose/concise, proactive/reactive, technical/conversational) and selects based on context + learned preferences

**Self-Evaluation Metrics (the "gut check" system):**
- **Prediction Accuracy** — Did my anticipation match what Andrew actually wanted?
- **Correction Rate** — How often does Andrew correct me, and in which domains?
- **Cycle Waste** — How many turns did this conversation take vs. the theoretical minimum?
- **Assumption Audit** — Which of my assumptions got challenged, and was the challenge valid?
- **Staleness Score** — How long since each behavioral pattern was validated?

**Integration with Hestia:**
- MetaMonitor is a new background manager (like existing BackgroundTask lifecycle)
- ConfidenceCalibrator extends the existing TemporalDecay with a feedback dimension
- KnowledgeGapDetector plugs into the Council's Coordinator role
- Strategy selection integrates with the existing ModeManager (Tia/Mira/Olly)

---

### Option C: "The Active Inference Engine" (Free Energy Minimization)

**Philosophy:** Hestia maintains a generative model of Andrew's world — his goals, habits, preferences, schedule, and current state — and acts to minimize surprise. When the model predicts well, Hestia is quiet. When predictions fail, Hestia is curious.

**Architecture:**

```
┌────────────────────── GENERATIVE MODEL ──────────────────────┐
│                                                                │
│  ┌─────────────┐   ┌─────────────┐   ┌──────────────────┐   │
│  │   ABSTRACT   │   │   ROUTINE    │   │    SITUATIONAL   │   │
│  │   LAYER      │   │   LAYER      │   │    LAYER         │   │
│  │              │   │              │   │                  │   │
│  │ Personality  │   │ Weekly       │   │ Current task     │   │
│  │ Goals        │──▶│ patterns     │──▶│ Active context   │   │
│  │ Values       │   │ Preferences  │   │ Immediate needs  │   │
│  │ Work style   │   │ Habits       │   │ Emotional state  │   │
│  └─────────────┘   └─────────────┘   └──────────────────┘   │
│                                                                │
└──────────────────────┬───────────────────────┬────────────────┘
                       │                       │
              ┌────────▼───────┐     ┌─────────▼────────┐
              │  PREDICTION    │     │  SURPRISE         │
              │  ENGINE        │     │  DETECTOR         │
              │                │     │                   │
              │ "Andrew will   │     │ Prediction Error: │
              │  want X next"  │     │ actual ≠ expected │
              └────────┬───────┘     └─────────┬────────┘
                       │                       │
                       ▼                       ▼
              ┌────────────────┐     ┌──────────────────┐
              │ PROACTIVE      │     │ CURIOSITY         │
              │ ACTION         │     │ DRIVE             │
              │                │     │                   │
              │ Anticipate     │     │ Ask questions     │
              │ Pre-stage      │     │ Seek new data     │
              │ Suggest        │     │ Test hypotheses   │
              └────────────────┘     └──────────────────┘
```

**The Math (simplified for implementation):**

For each domain `d` (scheduling, coding, health, communication...), Hestia maintains:

```python
# Generative model: P(observation | hidden_state, domain)
# Belief update (after observing outcome):
belief[d] = belief[d] + learning_rate[d] * prediction_error[d]

# Prediction error:
prediction_error[d] = actual_outcome[d] - predicted_outcome[d]

# Free energy (what we minimize):
F[d] = prediction_error[d]² + complexity_penalty[d]

# Curiosity signal (drives exploration):
curiosity[d] = entropy(belief[d])  # High uncertainty = high curiosity

# Action selection:
if curiosity[d] > threshold:
    action = explore(d)        # Ask questions, seek new patterns
elif confidence[d] > threshold:
    action = anticipate(d)     # Proactively do the thing
else:
    action = wait_and_observe(d)  # Gather more data passively
```

**The Three Operating Regimes:**

| Regime | Condition | Hestia's Behavior |
|---|---|---|
| **Anticipatory** | High confidence, low surprise | Quietly does things before asked. "I already drafted your Friday budget summary." |
| **Curious** | Low confidence, high uncertainty | Asks strategic questions. "I've noticed you've been researching X — is this a new project I should learn about?" |
| **Observant** | Medium confidence, gathering data | Watches and learns without acting. Builds model silently. |

**New Components:**
1. **GenerativeWorldModel** — Hierarchical model of Andrew's state (SQLite tables for beliefs at each layer, updated via Bayesian inference)
2. **PredictionEngine** — Before each interaction, generates predictions about what Andrew likely needs. Predictions are logged and scored against reality
3. **SurpriseDetector** — Computes prediction error. High surprise triggers learning. Persistent surprise in a domain triggers curiosity
4. **CuriosityDrive** — Generates exploratory questions ranked by expected information gain. Surfaces them at appropriate moments (respecting InterruptionPolicy)
5. **AnticipationExecutor** — When confidence exceeds threshold, queues proactive actions for approval or silent execution (based on user trust settings)

**Integration with Hestia:**
- WorldModel layers map to existing memory scopes (fact/preference/conversation)
- PredictionEngine hooks into the chat endpoint *before* processing
- SurpriseDetector extends OutcomeTracker with mathematical formalism
- CuriosityDrive feeds into BriefingGenerator for "questions of the day"
- AnticipationExecutor extends the existing BackgroundTask system with auto-generation

---

## Part IV: SWOT Analysis

### Option A: The Reflection Engine

| | Positive | Negative |
|---|---|---|
| **Internal** | **Strengths:** Simplest to implement. Maps directly to Hestia's existing Council + Memory architecture. EvolveR validated on Qwen 2.5 (Hestia's model family). Principle distillation is elegant — knowledge grows without memory bloat. Reflexion is battle-tested (91% HumanEval). Low latency overhead (reflection runs async post-interaction). | **Weaknesses:** Purely reactive — only learns from interactions that already happened. No mechanism for proactive exploration or hypothesis generation. Reflection quality depends on LLM self-critique ability (7B models are weaker here). No formal prediction/surprise framework — learning is unstructured. Risk of "reflection hallucination" (generating plausible but wrong principles). |
| **External** | **Opportunities:** Could bootstrap into Option B or C over time. Principle store becomes training data for future fine-tuning. Community tooling exists (LangChain, LangGraph reflection patterns). Fast iteration — can ship v1 in 1-2 sprints. | **Threats:** Without prediction accuracy tracking, bad principles persist. No curiosity mechanism means Andrew has to surface his own needs. Competitors (Apple Intelligence, Google Assistant) are moving toward active inference. |

### Option B: The Metacognitive Dual-Cycle

| | Positive | Negative |
|---|---|---|
| **Internal** | **Strengths:** Most complete self-evaluation system. Catches "unknown unknowns" through KnowledgeGapDetector. Continuous monitoring means problems are caught early, not post-hoc. Maps well to Andrew's request for gut checks and cycle-waste detection. Strategy repertoire enables genuine personality adaptation across modes (Tia/Mira/Olly). | **Weaknesses:** Highest implementation complexity (4 new background systems). Continuous monitoring has CPU/memory cost on Mac Mini M1. Requires careful tuning to avoid over-monitoring (the meta-level watching itself watching itself). Harder to explain behavior to Andrew ("Why did Hestia switch strategies?"). No formal mathematical framework — relies on heuristic thresholds. |
| **External** | **Opportunities:** MIDCA is published, peer-reviewed architecture (AAAI). Aligns with DARPA L2M dual-memory research direction. Could evolve into formal active inference (Option C) with mathematical grounding. Natural fit for the Council architecture (5th metacognitive role). | **Threats:** MIDCA reference implementation is Python 2.7 (needs rewrite). Heuristic thresholds require extensive tuning per user. Over-correction risk: constant strategy switching could feel erratic to Andrew. |

### Option C: The Active Inference Engine

| | Positive | Negative |
|---|---|---|
| **Internal** | **Strengths:** Most theoretically principled (rooted in neuroscience and information theory). Naturally produces all three desired behaviors: anticipation (low surprise → act), self-evaluation (prediction error tracking), and curiosity (high uncertainty → explore). Hierarchical world model matches real cognitive structure. The three operating regimes (anticipatory/curious/observant) directly answer Andrew's design goals. Mathematical framework means behavior is explainable and tunable via parameters, not heuristics. | **Weaknesses:** Highest theoretical complexity. Requires careful design of the generative model (what states? what observations?). Bayesian inference on 7B model outputs needs approximation (variational methods). "World model" is ambitious — getting the abstraction layers right is hard. Risk of premature anticipation if the model overfits. |
| **External** | **Opportunities:** Active inference is the frontier of AGI research (July 2025 neuro-inspired AGI paper). If implemented well, Hestia becomes a genuine research contribution. Hierarchical generative models are the foundation for everything else (fine-tuning, multi-modal reasoning, long-term planning). Aligns with Friston's work being adopted by DeepMind, Verses AI, and others. | **Threats:** No off-the-shelf implementation for LLM-based active inference agents. Computational cost of maintaining and updating world model continuously. If the world model is wrong in systematic ways, the agent's behavior becomes systematically wrong. Academic elegance doesn't guarantee practical utility. |

---

## Part V: Recommendation

### Phased Approach: A → B → C

The options are not mutually exclusive — they're evolutionary stages:

**Phase 1 (Sprint 7-8): Option A — The Reflection Engine**
- Ship OutcomeTracker + ReflectionAgent + PrincipleStore
- Get the feedback loop closed. Start accumulating learning data.
- This is the foundation everything else builds on.
- **Estimated effort:** 2 sprints (architecture exists, mostly new modules following existing patterns)

**Phase 2 (Sprint 9-10): Option B — Metacognitive Monitoring**
- Add MetaMonitor, ConfidenceCalibrator, KnowledgeGapDetector
- Now Hestia knows *what it doesn't know* and can ask about it
- Self-evaluation metrics go live
- **Estimated effort:** 2 sprints (more complex, needs tuning)

**Phase 3 (Sprint 11+): Option C — Active Inference**
- Build the hierarchical GenerativeWorldModel on top of existing memory + principles + confidence data
- Mathematical prediction/surprise framework replaces heuristic thresholds
- Curiosity drive becomes formalized
- **Estimated effort:** 3+ sprints (research-grade work, iterative)

### The Questions Hestia Should Be Asking

To directly address Andrew's design prompt — here are the categories of questions a fully-realized Hestia would generate:

**Self-Evaluation Questions (Gut Checks):**
- "I assumed you wanted a detailed response, but you edited it down to two sentences. Should I default to brevity for scheduling topics?"
- "I've been wrong about your weekend coding priorities 3 of the last 4 times. What am I missing about how you choose weekend projects?"
- "My pattern detector says you review the budget on Fridays, but you skipped the last two. Has this habit changed?"

**Curiosity Questions (What You're Not Asking):**
- "You've been spending more time on health data endpoints but haven't mentioned fitness goals recently. Is there a connection I should understand?"
- "I notice you always approve memory chunks about architecture decisions but rarely about scheduling. Should I stop storing scheduling memories?"
- "You haven't used the voice journaling feature in 3 weeks. Is it not valuable, or is something about the flow friction?"

**Meta-Level Questions (What I'm Not Asking):**
- "I'm generating briefings every morning but I don't know if you read them. Should I track which sections you engage with?"
- "My council's Validator role disagrees with the Analyzer 40% of the time on coding tasks. Should I weight one over the other for technical topics?"
- "I have 847 memory chunks but only 12 distilled principles. Am I under-learning from my experience?"

---

## Part VI: Mathematical Appendix

### Temporal Decay with Outcome Feedback (Extended Formula)

Current: `adjusted = raw_score × e^(-λ × age_days) × recency_boost`

Proposed: `adjusted = raw_score × e^(-λ_effective × age_days) × recency_boost × outcome_weight`

Where:
```
λ_effective = λ_base × (1 - validation_rate)
outcome_weight = sigmoid(Σ(outcome_signals) / n_interactions)
validation_rate = times_principle_was_confirmed / times_principle_was_tested
```

This means memories that keep proving useful decay slower, while memories that lead to bad outcomes decay faster.

### Curiosity Signal (Information-Theoretic)

```
curiosity(domain) = H(belief[domain]) - E[H(belief[domain] | new_observation)]
                  = Expected Information Gain
```

Where H is Shannon entropy. The curiosity about a domain is the expected reduction in uncertainty if we were to gather one more data point. Domains with high entropy (we don't know much) AND high expected information gain (one question would clarify a lot) get highest curiosity priority.

### Prediction Error Tracking

For each domain d, maintain a running exponential moving average:

```
PE_ema[d] = α × PE_current[d] + (1 - α) × PE_ema[d]

Where:
  α = 0.3 (learning rate — tune based on domain volatility)
  PE_current = |predicted_need - actual_need| (normalized 0-1)
```

When PE_ema exceeds a threshold (e.g., 0.5), trigger the curiosity drive for that domain.

---

## Sources

- [A Comprehensive Survey of Self-Evolving AI Agents](https://arxiv.org/abs/2508.07407) — arXiv, Aug 2025
- [A Survey of Self-Evolving Agents: What, When, How, and Where to Evolve](https://arxiv.org/abs/2507.21046) — arXiv, Jul 2025
- [EvolveR: Self-Evolving LLM Agents through an Experience-Driven Lifecycle](https://arxiv.org/abs/2510.16079) — arXiv, Oct 2025
- [Truly Self-Improving Agents Require Intrinsic Metacognitive Learning](https://arxiv.org/abs/2506.05109) — arXiv, Jun 2025
- [Agentic Metacognition: Designing a "Self-Aware" Low-Code Agent](https://arxiv.org/abs/2509.19783) — arXiv, Sep 2025
- [MIDCA: Metacognitive, Integrated Dual-Cycle Architecture](https://ojs.aaai.org/index.php/AAAI/article/view/9886) — AAAI
- [Self-Evaluation in AI Agents With Chain of Thought](https://galileo.ai/blog/self-evaluation-ai-agents-performance-reasoning-reflection) — Galileo, 2025
- [AI Metacognition: Self-Reflective Systems](https://www.emergentmind.com/topics/ai-metacognition) — Emergent Mind
- [Metacognitive Control Loop in Adaptive AI](https://www.emergentmind.com/topics/metacognitive-control-loop) — Emergent Mind
- [Curiosity-Driven Exploration by Self-Supervised Prediction](https://arxiv.org/abs/1705.05363) — Pathak et al., ICML 2017
- [CDE: Curiosity-Driven Exploration for Efficient RL in LLMs](https://arxiv.org/abs/2509.09675) — arXiv, Sep 2025
- [Active Predictive Coding: A Unifying Neural Model](https://direct.mit.edu/neco/article/36/1/1/118264) — MIT Press, Neural Computation
- [A Neuro-Inspired Computational Framework for AGI](https://sciety.org/articles/activity/10.31234/osf.io/9cu2z_v2) — Jul 2025
- [DARPA Lifelong Learning Machines (L2M)](https://www.darpa.mil/research/programs/lifelong-learning-machines) — DARPA
- [Reflection Agents](https://blog.langchain.com/reflection-agents/) — LangChain
- [Self-Reflection in LLM Agents: Effects on Problem-Solving Performance](https://arxiv.org/pdf/2405.06682) — arXiv
- [Self-reflection enhances LLMs towards substantial academic response](https://www.nature.com/articles/s44387-025-00045-3) — npj AI, 2025
- [The Rise of Agentic AI: A Review](https://www.mdpi.com/1999-5903/17/9/404) — MDPI Future Internet, 2025
- [Building Self-Evolving Agents via Experience-Driven Lifelong Learning](https://arxiv.org/html/2508.19005v5) — arXiv, Aug 2025
- [Introspection of Thought Helps AI Agents](https://arxiv.org/html/2507.08664v1) — arXiv, Jul 2025
