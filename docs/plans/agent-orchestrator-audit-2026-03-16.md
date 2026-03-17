# Plan Audit: Agent Orchestrator — Coordinate/Analyze/Delegate Model

**Date:** 2026-03-16
**Auditor:** Claude (Plan Audit Skill)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Evolve Hestia's 3-agent system from user-routed personality switching (`@tia`/`@mira`/`@olly`) to an orchestrator-delegate model where Hestia is the single user interface and internally coordinates Artemis (analysis) and Apollo (execution) as sub-agents. The council coordinator is extended (not replaced) to produce agent routing decisions. The architecture uses async interfaces that collapse to single-call on M1 16GB but genuinely parallelize on future M5 Ultra hardware.

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user (Andrew) | Yes | None — designed for this | N/A |
| Family (2-5 users) | Yes, with caveats | Routing audit log needs `user_id` scoping. Per-user routing preferences need isolation. Learning loop data must not cross users. | Medium — if `user_id` is baked into RoutingAuditEntry from day 1, family scale is trivial. If omitted, it's a migration + query audit. |
| Community (small group) | Partially | Shared specialists (Artemis/Apollo) would need per-user personality configs. Concurrent orchestration plans could contend on Ollama (even M5 Ultra has throughput limits). Resource scheduling needed. | High — requires a request queue with priority scheduling. Not needed now, but the ExecutionPlan abstraction naturally supports it. |
| Multi-tenant | No | Complete rearchitecture. Not relevant for Hestia's mission. | N/A — intentionally out of scope |

**Verdict:** Add `user_id` to `RoutingAuditEntry` and `ExecutionPlan` from day 1. Cost: 2 extra fields. Benefit: family scale works without migration.

## Front-Line Engineering Review

### Feasibility: HIGH

Technical validation confirms all integration points are ready:
- `IntentClassification` can be extended with 2 optional fields (no migration)
- `InferenceClient.chat()` already supports multiple calls with different system prompts
- `PromptBuilder` already supports per-mode prompt generation
- `ChatResponse` can add optional `byline` field (additive, non-breaking)
- SSE streaming can emit new `"byline"` event type (clients ignore unknown types)
- Handler pipeline has a clean insertion point after parallel pre-inference (step 6.5-7)

### Hidden Prerequisites

1. **Agent routing prompt engineering.** The SLM (`qwen2.5:0.5b`, 394MB) currently classifies into `IntentType` enum values using a simple text prompt. Extending it to also classify `AgentRoute` requires prompt redesign. The SLM's 0.5B parameter size may not have enough capacity for reliable agent routing on top of intent classification. **Risk: MEDIUM.** Mitigation: test SLM routing accuracy before committing. Fallback: use cloud-only routing classification, SLM returns `HESTIA_SOLO` always.

2. **Context slicing logic.** The ContextManager design says Artemis gets "full conversation history" while Apollo gets "only recent turns." This slicing logic doesn't exist today — PromptBuilder builds one context window for one inference call. Need to build context subsetting. **Risk: LOW.** The existing token budget system already truncates — this extends it to slice differently per agent.

3. **Response synthesis prompt.** When Hestia combines outputs from Artemis and Apollo, she needs a synthesis prompt. This is a new prompt template that doesn't exist. Quality depends heavily on prompt engineering. **Risk: LOW-MEDIUM.** Can start with simple concatenation + byline, evolve to LLM-synthesized responses later.

### Effort Estimate Assessment

Plan estimates ~50-60 new tests. Based on codebase patterns and the scope of changes:

| Component | Plan Estimate | Adjusted Estimate | Notes |
|-----------|--------------|-------------------|-------|
| OrchestrationPlanner | Part of 50-60 | 12-15 tests | Route selection, chain validation, confidence gating, fallback, plan collapsing |
| AgentExecutor | Part of 50-60 | 8-10 tests | Task execution, error handling, timeout, fallback |
| ContextManager | Part of 50-60 | 6-8 tests | Context slicing per agent, token budget enforcement, security (PII exclusion) |
| ResultSynthesizer | Part of 50-60 | 5-7 tests | Byline generation, multi-agent combination, empty result handling |
| Council extension | Part of 50-60 | 8-10 tests | AgentRoute classification, confidence scoring, fast-path bypass preserved |
| Handler integration | Part of 50-60 | 6-8 tests | Pipeline hook, streaming bylines, @mention override |
| Routing audit log | Part of 50-60 | 4-5 tests | Entry creation, querying, outcome tagging |
| **Total** | 50-60 | **49-63** | Estimate is realistic |

**Overall effort: ~8-12 working days.** Consistent with sprint-sized work at Andrew's pace.

### Testing Gaps

1. **SLM routing accuracy testing.** How do you test that `qwen2.5:0.5b` correctly classifies "analyze the trade-offs" → ARTEMIS vs "write the migration" → APOLLO? Integration tests hit Ollama and are slow/flaky. Mock tests don't validate real model behavior. **Recommendation:** Create a golden dataset of 30-50 example inputs with expected routes. Run against real SLM once, record results, use as regression baseline.

2. **End-to-end chain testing.** Testing Artemis → Apollo chains requires either multiple real inference calls (slow, expensive) or careful mocking of the orchestration pipeline. **Recommendation:** Test the orchestrator logic (planning, routing, fallback) with mocks. Test individual agent prompts with a smaller integration suite.

3. **Byline rendering across platforms.** iOS and macOS clients need to parse and render byline metadata. If they're not updated, bylines are silently dropped — invisible to the user. **Recommendation:** Treat iOS/macOS byline rendering as a hard requirement, not "future work." The byline IS the user-facing value of this feature.

### Developer Experience: GOOD

The plan follows Hestia's established patterns:
- New files in existing `hestia/orchestration/` directory (no new modules)
- Manager pattern with singleton factory
- Async interfaces throughout
- Config-driven thresholds (not hardcoded)
- Existing test patterns (pytest + asyncio + mocks)

The 4 new files (planner, executor, context_manager, synthesizer) are well-scoped and don't create a new module — they extend orchestration, which is architecturally correct.

## Architecture Review

### Fit: EXCELLENT

The orchestrator sits exactly where it should — in the orchestration layer, between council classification and inference. It doesn't violate layer boundaries:
- Council (below) → produces routing decision
- Orchestrator (this layer) → plans and executes
- Inference (below) → called N times by orchestrator
- API (above) → receives response with byline metadata

### Data Model

**RoutingAuditEntry** — SQLite table in existing orchestration scope. No new database module needed. Fields are all primitive types (str, float, datetime, bool). No migration complexity.

**IntentClassification extension** — 2 new optional fields on a dataclass. No persistence (it's ephemeral per-request). No migration.

**ChatResponse extension** — 1 new optional field on a Pydantic model. Additive. No migration. Clients that don't parse it see no change.

**OutcomeRecord extension** — Plan proposes adding `agent_route` and `route_confidence`. The existing `OutcomeDatabase` uses SQLite. Two options:
- Add columns (requires migration) — clean but requires `ALTER TABLE`
- Use existing `metadata` JSON field — no migration, slightly less queryable

**Recommendation:** Use `metadata` dict for now. Promote to columns if routing analysis queries become frequent.

### Integration Risk

| Integration Point | Risk | Mitigation |
|-------------------|------|-----------|
| Handler pipeline hook | LOW | Clean insertion point, existing tests validate pipeline |
| Council model extension | LOW | Optional fields, backward compatible |
| Inference multi-call | NONE | Already supported, no changes needed |
| SSE streaming | LOW | New event type, clients ignore unknown types |
| Outcome tracking | LOW | Use metadata dict, no schema change |
| @mention override | NONE | Existing code, one conditional |

**Highest integration risk:** The handler pipeline. `handle()` and `handle_streaming()` are the two most complex methods in the codebase (~200 lines each). Any change risks regressions. **Mitigation:** The orchestrator should be called as a single method (`orchestrate(request, intent, memory_ctx, profile_ctx)`) that returns an `OrchestratedResponse`. The handler's only change is: call orchestrator instead of directly calling inference. This minimizes the diff in handler.py.

### API Design

**No new endpoints needed for the orchestrator itself** — it's internal to the request pipeline. The only API-visible changes are:
- `ChatResponse.byline` (optional field)
- SSE `"byline"` event (new event type)
- Routing audit could optionally expose `GET /v1/orchestration/audit` — but this is a nice-to-have, not required

This is correct. The orchestrator is infrastructure, not a user-facing feature. It should be invisible except through bylines.

### Dependency Risk: NONE

No new Python packages. No new Swift packages. Pure internal refactoring using existing libraries (asyncio, dataclasses, Pydantic).

## Product Review

### User Value: HIGH (but conditional)

The user value is **simplified interaction** — no more `@mention` juggling. But this value is only realized if:
1. Routing accuracy is high enough that users don't need to override frequently
2. Bylines are visible so users can see the system is working
3. The quality of specialist responses is noticeably better than Hestia-solo

If routing is wrong 30% of the time, this is worse than manual `@mentions`. The confidence gating (0.5-0.8 = enriched solo, <0.5 = pure solo) mitigates this, but it means many requests will fall through to Hestia-solo anyway during the learning period.

**Key question:** Is the routing accuracy of the SLM (or cloud classifier) good enough out of the gate to justify the architectural investment? This needs validation before sprint completion.

### Edge Cases

| Scenario | Handling |
|----------|---------|
| Empty conversation (first message) | No conversation context for routing. Use intent-only classification. Should default to HESTIA_SOLO for first interaction. |
| Very long request (>1000 tokens) | ContextManager must truncate intelligently per agent. Artemis gets the full request; Apollo gets a summary. |
| Conflicting @mention + intent | @mention wins (explicit override). Clear in design. |
| Cloud disabled + chain requested | Chain validation collapses to single call. Documented. |
| Specialist timeout | Fallback to Hestia-solo. Documented. |
| All agents return low confidence | Hestia-solo with default prompt. Needs explicit handling. |

### Multi-Device

Byline metadata flows through the API response. iOS and macOS both consume `ChatResponse`. As long as both clients parse `byline`, it works. The routing decision happens server-side, so device type is irrelevant to routing. **No platform divergence risk.**

### Opportunity Cost

While building this, we are NOT building:
- Sprint 11B (Command Center + MetaMonitor) — deferred, but MetaMonitor benefits from routing data
- Sprint 12 (Health Dashboard + Whoop) — independent, could run in parallel on a different sprint
- Agentic sandbox path improvements (from session handoff)
- Mac Mini deploy (41 commits ahead)

**Assessment:** The opportunity cost is acceptable. This is foundational work that improves every subsequent sprint. MetaMonitor specifically benefits from routing audit data.

### Scope: RIGHT-SIZED

4 new files, 3 modified files, ~50-60 tests. This is a single sprint. Not too big (no new modules, no new APIs), not too small (real architectural change with testing and documentation).

## UX Review

### Byline Rendering

The only UI component is the byline at the bottom of chat responses. This needs design attention:

```
[Response content...]

───
📐 Artemis — analyzed WebSocket vs SSE trade-offs
⚡ Apollo — scaffolded SSE implementation (3 files)
```

**Design system compliance:**
- Use `HestiaTypography.caption` for byline text
- Use `HestiaColors.secondaryText` for the attribution
- Agent icons/emoji should match existing agent color gradients
- Separator line should use `HestiaColors.separator`

**Platform parity:** Both iOS and macOS need to render bylines. iOS (Chat-only) and macOS (full app) both use `ChatResponse` — same data, same rendering.

**Empty state:** When `byline` is nil (Hestia-solo responses), show nothing. No "Hestia handled this alone" — that's noise.

**Accessibility:** Byline text must be VoiceOver-readable. Include agent name in accessibility label.

### Interaction Model

No new user flows. The user types a message and gets a response. The only new visual element is the byline. The @mention override uses existing input patterns. **No dead ends, no new navigation.**

## Infrastructure Review

### Deployment Impact

- **Server restart required:** Yes — new Python files in orchestration layer
- **Database migration:** No — routing audit uses a new table (auto-created), IntentClassification is ephemeral
- **Config change:** Yes — new section in `inference.yaml` or new `orchestration.yaml` for confidence thresholds
- **No new dependencies:** Pure Python standard library + existing packages

### Monitoring

- Routing audit log provides full observability (every routing decision logged with confidence, duration, outcome)
- Existing `get_logger()` pattern for operational logging
- No new health check endpoints needed — orchestrator health is implicit in chat response success

### Rollback Strategy

**Clean rollback path:**
1. If orchestrator is broken, handler can bypass it and call inference directly (existing code path)
2. Config flag: `orchestrator_enabled: false` in config → falls back to current behavior
3. No database migrations to reverse
4. No client-side changes required (byline is optional, absence is handled)

**Recommendation:** Add `orchestrator_enabled` config flag from day 1. Ship with `true` but have the kill switch.

### Resource Impact on M1 16GB

| Scenario | Additional Inference Calls | Latency Impact | Memory Impact |
|----------|---------------------------|---------------|---------------|
| HESTIA_SOLO (most common) | 0 (same as today) | ~0ms overhead (plan generation is pure Python) | Negligible |
| ARTEMIS or APOLLO | +0 if collapsed, +1 if full dispatch | +3-8s local, +1-3s cloud | Negligible (same model, sequential) |
| ARTEMIS_THEN_APOLLO | +1-2 additional calls | +6-16s local, +2-6s cloud | Negligible |

**The common case (HESTIA_SOLO for simple messages) has ZERO additional cost.** This is critical. The fast-path bypass ensures that "what's the weather" doesn't pay any orchestration tax.

**Concern:** Chains on local models (Artemis → Apollo = 2 extra inference calls at 3-8s each) will feel slow. The chain validation heuristic that collapses short requests helps, but users with complex requests on local-only will notice latency.

**Mitigation:** When cloud is enabled (which it currently is — `enabled_full`), chains go to cloud where latency is 1-3s per call. Local-only chains should trigger a user-visible "thinking deeper..." status in the SSE stream.

## Executive Verdicts

### CISO: ACCEPTABLE

**Attack surface change:** Minimal.
- No new external communication paths
- No new credential handling
- No new data exposure (bylines contain agent names, not sensitive data)
- Error sanitization patterns maintained (orchestrator uses `sanitize_for_log()`)
- Context slicing actually IMPROVES security — Apollo doesn't see full user profile

**One concern:** The routing audit log contains `input_summary` (first 100 chars of request). If this includes sensitive content (health questions, financial queries), the audit log becomes a data sensitivity concern. **Remediation:** Apply the same PII scrubbing used in cloud-safe context to the input summary. Or: don't store input content at all — store only the routing decision metadata.

**Verdict:** ACCEPTABLE with remediation — sanitize or omit `input_summary` from routing audit entries.

### CTO: ACCEPTABLE

**Architecture fit:** Excellent. Extends orchestration layer without violating boundaries. Uses existing interfaces (InferenceClient, PromptBuilder, council). No new modules.

**Technical debt:** Net negative (reduces debt). The current system has three PersonaConfigs that are functionally identical except for system prompts — the orchestrator gives them distinct purposes, which is cleaner.

**Simpler alternatives considered:**
- "Just improve the council to auto-switch modes" — this IS what the plan does, with the addition of multi-hop execution and synthesis. The plan is already the simplest viable version.
- "Skip orchestration, just switch system prompts" — this is the M1 degradation path, already in the plan. The orchestrator adds value only when it enables chaining and parallel execution.

**Concern:** The plan describes 4 new components (Planner, Executor, ContextManager, Synthesizer) which could become over-engineered if each is a heavy class. **Recommendation:** Start with the Planner and Executor as the core. ContextManager can be a set of utility functions (not a class with state). Synthesizer can be a function, not a class, until synthesis logic actually needs state.

**Verdict:** ACCEPTABLE — with recommendation to keep ContextManager and Synthesizer lightweight (functions, not stateful classes).

### CPO: ACCEPTABLE

**User value:** High — simplified interaction model aligns with the "Jarvis" vision. Byline attribution adds transparency without complexity.

**Priority ordering:** Correct. This is foundational work that enriches all downstream sprints (MetaMonitor, Active Inference). Building it before 11B means MetaMonitor gets routing data from day one.

**Concern:** The value is only realized if routing accuracy is high. If the SLM can't reliably distinguish "analyze this" from "build this," most requests fall through to HESTIA_SOLO and the feature is invisible. **Recommendation:** Define a routing accuracy target (e.g., >75% on a golden dataset) and validate before the sprint is marked complete. If accuracy is below target, the feature ships with cloud-only routing classification and SLM always returns HESTIA_SOLO.

**Verdict:** ACCEPTABLE — with routing accuracy validation gate.

## Final Critiques

### 1. Most Likely Failure: SLM Routing Accuracy

The `qwen2.5:0.5b` model (394MB) currently classifies ~15 intent types. Adding agent routing asks it to also determine HESTIA_SOLO vs ARTEMIS vs APOLLO vs ARTEMIS_THEN_APOLLO. This is a 60-category output space (15 intents x 4 routes) on a 0.5B parameter model.

**Likelihood:** MEDIUM-HIGH. Small models struggle with multi-dimensional classification.

**Mitigation:**
- Decouple intent and routing classification. SLM does intent only (existing, proven). A second lightweight heuristic maps intent → agent route (e.g., CODING → APOLLO, MEMORY_SEARCH → HESTIA_SOLO). The heuristic is simple, testable, and doesn't depend on model quality.
- Reserve SLM/cloud routing for ambiguous cases where the heuristic can't decide.
- This is the **recommended approach** — simpler, more reliable, more testable.

### 2. Critical Assumption: Specialist Prompts Improve Response Quality

The entire architecture assumes that routing "analyze trade-offs" to Artemis's analytical prompt produces a *better* response than Hestia's general-purpose prompt handling the same request. If the underlying model (Qwen 9B or cloud) doesn't meaningfully change behavior based on system prompt variations, the orchestrator adds latency without improving quality.

**Validation approach:** Before full implementation, run an A/B test with 10-15 representative requests:
- A: Current system (Hestia-solo with general prompt)
- B: Same model, Artemis system prompt
- C: Same model, Apollo system prompt

If B and C responses are indistinguishable from A in quality/style, the specialist prompt engineering needs more work before the orchestrator is worth building.

### 3. Half-Time Cut List

If we had half the time (~4-6 working days instead of 8-12):

**CUT:**
- ContextManager (use full context for all agents — less efficient but works)
- ResultSynthesizer as a separate component (last agent's output IS the response, add byline string directly)
- Routing audit log (defer to MetaMonitor sprint — log to existing logger instead)
- ARTEMIS_THEN_APOLLO chains (only support single-agent dispatch, not chains)

**KEEP (the true priorities):**
- Council extension with AgentRoute (the routing decision)
- OrchestrationPlanner with confidence gating (the intelligence)
- AgentExecutor (the execution)
- Byline metadata on ChatResponse (the user-facing value)
- @mention override (the escape hatch)
- `orchestrator_enabled` config flag (the kill switch)

This reveals the core: **routing decision + execution + byline.** Everything else is optimization.

## Conditions for Approval

1. **Add `user_id` to RoutingAuditEntry** — prevents family-scale migration later (5 min of work now vs hours later)
2. **Add `orchestrator_enabled` config flag** — kill switch for rollback (essential for safe deployment)
3. **Sanitize or omit `input_summary` from routing audit** — CISO finding, prevents PII in audit log
4. **Keep ContextManager and Synthesizer lightweight** — functions or thin classes, not stateful managers. Promote to full classes only when state is needed
5. **Intent-to-route heuristic as primary routing** — don't depend on SLM for routing classification. Map intent → route with a deterministic heuristic. Reserve model-based routing for ambiguous cases
6. **Define routing accuracy target (>75%)** — validate against a golden dataset before marking sprint complete. If below target, ship with heuristic-only routing
7. **iOS/macOS byline rendering is IN-SCOPE** — not "future work." The byline is the user-facing value. If it's not rendered, the feature is invisible
8. **A/B prompt quality validation** — before full implementation, confirm that Artemis/Apollo specialist prompts produce meaningfully different (better) responses than Hestia-solo on the same model. 10-15 test cases minimum

## Appendix: Recommended Execution Order

Based on the audit, the recommended build sequence:

1. **Intent-to-route heuristic** (deterministic mapping, fully testable)
2. **Council extension** (add optional fields to IntentClassification)
3. **OrchestrationPlanner** (route selection + confidence gating + chain validation)
4. **AgentExecutor** (single-agent dispatch with fallback)
5. **Byline on ChatResponse + SSE** (user-facing output)
6. **iOS/macOS byline rendering** (user-facing output)
7. **Routing audit log** (observability)
8. **ContextManager** (optimization — context slicing per agent)
9. **ResultSynthesizer** (optimization — multi-agent output combination)
10. **Chain execution** (ARTEMIS_THEN_APOLLO support)

Items 1-6 are the MVP. Items 7-10 are enhancements that can ship in a follow-up if time is constrained.
