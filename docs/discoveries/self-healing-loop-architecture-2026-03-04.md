# Discovery Report: Self-Healing Loop Architecture

**Date:** 2026-03-04
**Confidence:** High
**Decision:** Implement a 4-component self-healing loop (timezone-aware context, settings tools, self-diagnosis, Learning Cycle integration) as a cross-cutting enhancement layered across Sprints 11-14, not as a standalone sprint.

## Hypothesis

Hestia can become significantly more autonomous and reliable by implementing a closed-loop system where the AI detects its own failures, diagnoses root causes, adjusts its own configuration (within safety bounds), and learns from the experience — turning operational friction into permanent improvements.

The four components investigated:
1. **Timezone handling** — Hestia currently stores/compares everything in UTC but surfaces no local-time awareness to the user or in scheduling logic
2. **Settings tools** — The AI has no tools to read or modify its own configuration (YAML configs, user settings, agent profiles)
3. **Self-diagnosis** — No mechanism to detect when it's performing poorly (beyond the planned MetaMonitor)
4. **Learning Cycle integration** — OutcomeTracker exists but doesn't yet close the loop back to behavior modification

---

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** OutcomeTracker already recording every chat outcome. PrincipleStore distilling knowledge. User profile system (IDENTITY.md) already has timezone field. Tool registry is extensible. Existing config YAML files are well-structured. Orders scheduler already uses APScheduler with timezone support. 1451 tests provide regression safety net. | **Weaknesses:** No timezone conversion anywhere in the stack — everything is naive UTC. No tools for self-modification (AI can read files but not its own config). MetaMonitor doesn't exist yet (Sprint 11). Outcome data is write-only — nothing reads it to change behavior. Settings tools would need a new safety tier (AI self-modification is higher risk than file I/O). |
| **External** | **Opportunities:** Industry moving toward self-healing AI (Ericsson, enterprise AIOps). OpenAI's self-evolving agents cookbook validates the feedback-loop-to-behavior-change pattern. The Learning Cycle roadmap (Sprints 13-14) already plans Active Inference, which is exactly the right place to close this loop. Timezone awareness is a prerequisite for accurate scheduling, briefings, and proactive intelligence. | **Threats:** Premature self-modification creates instability risk (AI changes settings, performance degrades, AI changes them back = oscillation). Timezone bugs are insidious and hard to test. Config self-modification without proper guardrails could corrupt system state. Scope creep — "self-healing" could expand indefinitely. |

---

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **Timezone-aware context injection** (every scheduling, briefing, and proactive feature depends on correct local time). **Read-only settings tools** (let AI see its own config to diagnose issues). **Outcome-to-principle pipeline** (close the gap between OutcomeTracker data and PrincipleStore learning). | **User-facing timezone display** (nice but non-critical — all times could just be correct without explicit display). |
| **Low Priority** | **Write settings tools** (AI modifying its own config — high value but high risk, needs careful gating). **Automatic self-remediation** (restart services, clear caches — powerful but premature before MetaMonitor proves useful). | **Multi-timezone support** (Hestia is single-user on a Mac Mini — one timezone is fine). **Config versioning/rollback** (would be nice but YAGNI until write tools prove useful). |

---

## Argue (Best Case)

### The case for building this now

**1. Timezone is a silent bug factory.** The codebase uses `datetime.now(timezone.utc)` consistently (good), but no component converts to user local time. This means:
- Orders scheduled at "7 AM" are 7 AM UTC, not 7 AM Pacific
- Daily briefings reference "today" in UTC, not the user's day boundary
- Quiet hours (22:00-07:00) are evaluated in UTC — 8 hours off for Pacific
- The scheduler's `timezone="UTC"` in APScheduler means cron triggers fire at UTC midnight, not local midnight

Evidence: `hestia/orders/scheduler.py:54` hardcodes `timezone="UTC"`. `hestia/user/models.py` defines `QuietHours` with no timezone conversion. `hestia/proactive/briefing.py` generates briefings using UTC timestamps.

**2. Read-only settings tools are low risk, high diagnostic value.** If Hestia can read its own `inference.yaml`, `execution.yaml`, and `memory.yaml`, it can:
- Answer "what model am I using?" without the user checking configs
- Diagnose "why was my response slow?" by checking cloud routing state
- Explain "why didn't you use that tool?" by reading tool availability

This is purely additive — read-only tools with no side effects. The existing tool registry supports this trivially.

**3. The Outcome-to-Principle pipeline is the missing link.** OutcomeTracker (Sprint 10) collects signals. PrincipleStore (Sprint 8) stores distilled principles. But nothing connects them. The pipeline would:
- Periodically scan outcomes with negative signals (thumbs-down, corrections, quick_followup)
- Feed those into PrincipleStore's distillation prompt
- Produce principles like: "[communication] User prefers bullet points, not paragraphs" or "[scheduling] User considers 9am to mean local time, not UTC"
- These principles then appear in the prompt context, modifying future behavior

This is exactly the "learning from mistakes" pattern validated by OpenAI's self-evolving agents research and the REFLEX architecture.

**4. Self-diagnosis via structured introspection.** Before MetaMonitor (Sprint 11) exists, a lightweight version can work: after any error response, log the failure context (what was asked, what went wrong, what config state was active). When the same failure pattern repeats 3+ times, surface it in the daily briefing as a "recurring issue."

---

## Refute (Devil's Advocate)

### The case against building this now

**1. Timezone handling is mostly cosmetic right now.** The single user (Andrew) is in one timezone. The Mac Mini server is in the same timezone. Most interactions are real-time chat, not scheduled operations. The Orders system exists but isn't heavily used yet. The ROI of fixing timezone handling is low until scheduling and proactive features become daily-use.

Counter-counter: This is true today but becomes a blocker the moment Sprint 11 (Command Center with week calendar) or Sprint 14 (Anticipatory Execution) ships. Better to fix the plumbing now than retrofit later.

**2. Settings write tools are premature and dangerous.** The Sprint 14 plan explicitly marks `modify_settings: ActionRisk.NEVER`. There's good reason: an AI modifying its own configuration creates a feedback loop that's hard to debug. If Hestia changes its inference config and performance degrades, who fixes it? The user, who may not know what changed?

Counter-counter: Write tools aren't proposed for v1. Read-only tools provide 80% of the diagnostic value with 0% of the risk.

**3. The Outcome-to-Principle pipeline requires Sprint 11's MetaMonitor.** The pipeline needs something to analyze patterns in outcome data — that's literally what MetaMonitor does. Building it independently duplicates effort.

Counter-counter: A simple cron-based batch job can scan outcomes weekly without MetaMonitor. MetaMonitor adds real-time and multi-signal analysis, but a batch distillation pipeline is valuable independently.

**4. "Self-healing" is a buzzword that inflates scope.** The research shows enterprise self-healing is about restarting services and scaling infrastructure — not relevant to a single-user personal AI. What Hestia actually needs is a "learning loop," which is already planned in Sprints 13-14.

Counter-counter: Fair. The "self-healing" framing is enterprise-borrowed. But the concrete components (timezone, settings tools, diagnosis, learning integration) are all specific and bounded.

---

## Third-Party Evidence

### Validating approaches

**OpenAI Self-Evolving Agents Cookbook** ([link](https://cookbook.openai.com/examples/partners/self_evolving_agents/autonomous_agent_retraining)): Documents a repeatable retraining loop that captures issues, learns from feedback, and promotes improvements. Key insight: separate the evaluation system from the execution system to prevent self-improvement cycles from corrupting live data. This directly validates the Outcome-to-Principle pipeline approach.

**REFLEX Agent Architecture** ([link](https://medium.com/@nomannayeem/lets-build-a-self-improving-ai-agent-that-learns-from-your-feedback-722d2ce9c2d9)): Combines RL + RAG + feedback loops. When ratings are given, feedback becomes training data — the agent learns which approaches users prefer. Maps directly to OutcomeTracker's thumbs-up/down → PrincipleStore distillation path.

**Self-Healing AI Systems Overview** ([link](https://www.msrcosmos.com/blog/self-healing-ai-systems-and-adaptive-autonomy-the-next-evolution-of-agentic-ai/)): Core architecture layers: Continuous Monitoring, Anomaly Detection, Automated Diagnosis, Self-Repair Mechanisms, Learning Capability. Hestia already has monitoring (logging) and learning (PrincipleStore). The gap is diagnosis and (carefully bounded) repair.

**Dual-Component Reflection Architecture** ([link](https://datagrid.com/blog/7-tips-build-self-improving-ai-agents-feedback-loops)): Recommends separating performance measurement from business execution, preventing self-improvement cycles from corrupting live data. This is exactly why read-only settings tools are the right first step — the AI can diagnose but not modify.

### Contradicting evidence

**Enterprise self-healing ≠ Personal AI self-healing.** Most production implementations (Ericsson NetCloud, AIOps platforms) are about infrastructure — restarting pods, scaling horizontally, rerouting traffic. A personal AI assistant's "self-healing" is fundamentally different: it's about behavior adaptation, not infrastructure recovery. The architecture patterns don't transfer directly.

**Feedback loop instability.** Zendesk's research ([link](https://www.zendesk.com/blog/ai-feedback-loop/)) warns about amplifying bias through feedback loops. If the AI learns from its own mistakes but the mistake detection is imperfect, it can learn the wrong lessons. Mitigation: human approval gate on principles (already in PrincipleStore — principles start as "pending").

---

## Recommendation

### Architecture: Four components, phased delivery

**Component 1: Timezone-Aware Context (Immediate — pre-Sprint 11)**

Add timezone awareness to the orchestration layer:

```python
# In handler.py, Step 6.3 (user profile loading)
# Extract timezone from USER-IDENTITY.md (already has "Timezone: America/Los_Angeles")
# Inject into system prompt: "Current local time: Wednesday 2026-03-04 14:23 PST"
# Convert Orders scheduler from UTC to user's local timezone
# Fix QuietHours evaluation to use local time
```

Implementation:
- Parse `USER-IDENTITY.md` for `**Timezone:**` field (already there in template)
- Add `get_user_timezone() -> str` to `UserConfigLoader` (returns IANA tz string)
- Inject local time/date into system prompt (1 line addition in `handler.py`)
- Change APScheduler from `timezone="UTC"` to user's timezone
- Fix `QuietHours` evaluation to convert UTC now to local time before comparison

Effort: ~2 hours. Risk: minimal.

**Component 2: Read-Only Settings Tools (Sprint 11 scope)**

Register 3 new tools with the ToolRegistry:

```python
Tool(name="get_system_config",
     description="Read Hestia's current system configuration (inference, memory, execution settings)",
     handler=_get_system_config,
     category="system")

Tool(name="get_user_settings",
     description="Read the current user's preferences and settings",
     handler=_get_user_settings,
     category="system")

Tool(name="get_system_status",
     description="Get Hestia's current operational status (model state, cloud routing, manager health)",
     handler=_get_system_status,
     category="system")
```

These are pure reads. No side effects. Registered alongside existing builtin tools. The AI can now answer "what's my config?" and diagnose issues.

Effort: ~4 hours. Risk: information exposure (mitigated by not returning API keys or secrets).

**Component 3: Outcome-to-Principle Batch Pipeline (Sprint 11 scope)**

A scheduled job (daily or weekly) that:
1. Queries OutcomeDatabase for records with negative signals (thumbs_down, correction, quick_followup)
2. Groups them by topic/domain using simple keyword extraction
3. Feeds grouped excerpts into PrincipleStore's existing `distill_principles()` method
4. Stores resulting principles as "pending" (existing approval workflow)

```python
class OutcomeLearner:
    """Batch pipeline: negative outcomes → distilled principles."""

    async def run(self) -> int:
        """Run one learning cycle. Returns count of new principles."""
        negative_outcomes = await self._get_negative_outcomes(days=7)
        if len(negative_outcomes) < 3:
            return 0  # Not enough signal

        # Group by response_type and metadata
        groups = self._group_by_domain(negative_outcomes)

        total_principles = 0
        for domain, outcomes in groups.items():
            # Convert outcomes to memory-chunk-like format for PrincipleStore
            chunks = self._outcomes_to_chunks(outcomes)
            principles = await self.principle_store.distill_principles(chunks)
            total_principles += len(principles)

        return total_principles
```

This connects OutcomeTracker (Sprint 10) to PrincipleStore (Sprint 8). When MetaMonitor (Sprint 11) lands, it replaces the batch job with real-time analysis.

Effort: ~6 hours. Risk: low (distillation produces pending principles, never auto-approved).

**Component 4: Lightweight Self-Diagnosis (Sprint 11 scope, pre-MetaMonitor)**

Before MetaMonitor exists, a simple diagnostic that runs on each error response:

```python
# In chat route, after error responses:
async def _log_diagnostic(request, error, config_snapshot):
    """Log structured diagnostic for error responses."""
    await diagnostic_db.store({
        "request_content": request.message[:200],
        "error_type": type(error).__name__,
        "cloud_state": config_snapshot["cloud_routing"],
        "model": config_snapshot["primary_model"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

# In briefing generator, add section:
async def _get_recurring_issues(self) -> Optional[str]:
    """Surface recurring error patterns in daily briefing."""
    recent_errors = await diagnostic_db.get_recent(days=7)
    if len(recent_errors) < 3:
        return None
    # Group by error_type, surface if same type > 3 times
    ...
```

Effort: ~4 hours. Risk: none (logging + read-only briefing addition).

### What NOT to build

- **Write settings tools** — Defer to Sprint 14+ after Active Inference proves the pattern. The `ActionRisk.NEVER` classification for `modify_settings` is correct.
- **Automatic remediation** — No service restarts, cache clears, or model switches by the AI. This is enterprise AIOps territory and inappropriate for a personal AI.
- **Real-time self-monitoring** — MetaMonitor handles this in Sprint 11. Don't duplicate.

### Confidence and reversibility

**Confidence: High.** All four components are bounded, low-risk, and build on existing infrastructure. None require new dependencies or architectural changes.

**Reversibility triggers:**
- If timezone conversion causes scheduling regressions → revert to UTC-only (one config change)
- If settings tools expose sensitive info → unregister them (one line in tool registration)
- If Outcome-to-Principle generates bad principles → they sit as "pending" until manually reviewed. No auto-approval.
- If diagnostic logging adds measurable latency → disable with feature flag

---

## Final Critiques

### The Skeptic: "Why won't this work?"

**Challenge:** "Timezone is a solved problem, yet you're proposing to thread it through a complex system with 26 modules. You'll introduce bugs in at least 3 places."

**Response:** The proposal deliberately limits timezone awareness to four touch points: (1) system prompt injection (one line), (2) APScheduler timezone config (one line), (3) QuietHours evaluation (one function), (4) briefing "today" boundary (one comparison). It does NOT propose converting all 105 files that import `datetime`. The risk is bounded because we're adding local time awareness at the edges, not converting the internal representation from UTC.

### The Pragmatist: "Is the effort worth it?"

**Challenge:** "You're proposing ~16 hours of work (across 4 components) for features that are 'nice to have' until Sprint 11-14 make them critical. Why not wait?"

**Response:** Components 1 (timezone) and 4 (diagnostic logging) are genuinely immediate value — every briefing and scheduled order benefits from correct timezone handling today. Component 2 (read-only tools) costs 4 hours and pays for itself the first time someone asks "what model are you using?" Components 3 (outcome pipeline) is the only one that could wait, but building it now means Sprint 11's MetaMonitor has real data to consume from day one instead of starting cold.

The total investment is roughly 2 sessions of work. The payoff is every subsequent sprint builds on correct infrastructure instead of retrofitting.

### The Long-Term Thinker: "What happens in 6 months?"

**Challenge:** "In 6 months, Sprints 13-14 will be in progress. Does this foundation actually help, or does Active Inference replace everything?"

**Response:** Active Inference (Sprints 13-14) is the full-stack version of what these components start. Specifically:
- Timezone awareness is a permanent infrastructure need — Active Inference needs it more, not less
- Read-only settings tools become the diagnostic layer for the SurpriseDetector
- The Outcome-to-Principle pipeline is exactly what the CuriosityDrive feeds on
- Diagnostic logging becomes the data source for the MetaMonitor

None of this work is throwaway. It's the foundation that Active Inference stands on. The risk is building it too late, not too early.

---

## Open Questions

1. **Where should `OutcomeLearner` live?** Options: `hestia/outcomes/learner.py` (near data source) or `hestia/learning/outcome_learner.py` (near consumers). Recommendation: `hestia/learning/` since it crosses module boundaries.

2. **Should read-only settings tools return cloud provider names?** The current security posture never returns API keys. Provider names (e.g., "anthropic") seem safe, but configuration details about which models are enabled could be considered operational intelligence. Recommendation: return provider names and model names, not keys or usage counts.

3. **What triggers the OutcomeLearner batch job?** Options: APScheduler (consistent with Orders), server startup + daily interval, or manual trigger via API endpoint. Recommendation: APScheduler with configurable daily schedule (default: 3 AM local time, benefiting from Component 1's timezone fix).

4. **Decision Gate alignment:** Should Component 3 (Outcome-to-Principle pipeline) be gated behind the Sprint 10 Decision Gate 2 ("Is OutcomeTracker collecting meaningful signals?")? Recommendation: Yes — wait for 1-2 weeks of OutcomeTracker data before building the pipeline to ensure there's signal to learn from.

---

## Implementation Sequence

```
Immediate (pre-Sprint 11):
  1. Timezone-aware context injection (~2 hours)

Sprint 11 (alongside MetaMonitor):
  2. Read-only settings tools (~4 hours)
  3. Lightweight self-diagnosis (~4 hours)
  4. Outcome-to-Principle batch pipeline (~6 hours)

Sprint 13-14 (subsumes into Active Inference):
  5. Write settings tools (if proven safe)
  6. Real-time self-monitoring replaces batch diagnosis
  7. CuriosityDrive replaces OutcomeLearner
```

Total new effort: ~16 hours across 2 sprints. No new modules required (extends existing ones). No new dependencies.
