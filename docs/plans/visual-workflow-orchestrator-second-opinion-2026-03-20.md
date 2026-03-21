# Second Opinion: Visual Workflow Orchestrator (P0-P4)

**Date:** 2026-03-20
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external) + @hestia-critic (adversarial)
**Verdict:** APPROVED — Full build authorized. WebView + React Flow for canvas (P2). P0 starts immediately.

## Plan Summary

Transform Hestia's Orders system (scheduled prompts with stubbed execution) into an n8n-level DAG workflow engine. 5 phases (P0-P4), estimated 91-127h over 8-11 weeks. Engine-first approach: list-based UI in P1, visual canvas deferred to P2. DAGExecutor uses asyncio.TaskGroup with SQLite checkpointing and dead path elimination.

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user (Andrew) | Yes | None | N/A |
| Family (2-5) | Yes, with caveats | `workflow_runs` needs direct `user_id` column (currently inherited via FK). EventBus listeners need per-user isolation. | Low if `user_id` added from day 1 |
| Community (small group) | Partially | Concurrent DAG executions contend on Ollama (one model in GPU on M1). Needs execution queue with priority. | High — requires request scheduler |
| Multi-tenant | No | Not relevant | N/A |

---

## Front-Line Engineering

- **Feasibility:** HIGH. All integration points exist. Handler is callable, APScheduler is proven, manager pattern is established. No new paradigms required.
- **Hidden prerequisites:**
  1. Handler expects fully-formed `Request` with `session_id`, `mode`, auth context. Workflow node must construct this — no JWT device token for background jobs. This is the P0 complexity the 6h estimate underestimates.
  2. `create_from_session()` in OrderManager creates orders with `status=WORKING` and placeholder prompts — no clean mapping to workflow nodes. Migration needs special-case handling.
  3. Circular dependency detection not mentioned in plan. Must be validated at workflow save time.
- **Testing gaps:**
  - Topology coverage needed: linear, fan-out, fan-in, dead-path, checkpoint resume, checkpoint resume after failure, malformed configs.
  - ~120 tests may be insufficient. Recommend 150-180 to cover graph combinatorics.
  - Canvas UI has no automated test path — manual + SwiftUI previews only.
- **Estimate assessment:** 91h is optimistic. Adjusted: **102-135h** (canvas is the wildcard at 25-45h).

---

## Architecture Review

- **Fit:** EXCELLENT. New `hestia/workflows/` module follows established patterns (models + database + manager). Singleton factory, async interfaces, config-driven thresholds.
- **Data model:** Solid. JSON config columns are correct for 20+ node subtypes. Version snapshotting on activate is well-designed. **Gaps:** Missing `retry_count` on `node_executions`. Missing direct `user_id` on `workflow_runs`.
- **API design:** 14 endpoints follow Hestia conventions. **Gap:** No SSE endpoint for real-time execution feedback — should add `/v1/workflows/{id}/runs/{run_id}/stream` to P1.
- **Integration risk:** Low. All integration points are additive (consuming existing managers, not modifying them). No high-risk coupling.
- **Dependencies:** No new Python deps for P1. P2 adds `jmespath` (MIT, pure Python). Canvas Swift deps need license check.

---

## Product Review

- **User value:** HIGH. This is the feature that makes Hestia an automation platform vs. a chat assistant. P0 alone fixes a real bug (Orders that don't execute).
- **Scope:** Right-sized for the n8n-level goal. Phased delivery means each phase is independently valuable.
- **Opportunity cost:** Trading Sprints 28-30 delayed by 8-11 weeks. If trading is generating returns, this is a concrete cost. Mitigation: P0 can parallel current trading work.
- **Edge cases addressed:** Version snapshotting (edit during execution), execution timeouts (60s node / 300s workflow), empty states.
- **Missing:** Global concurrency limit for parallel LLM calls on M1.

---

## UX Review

### Current Orders UI Wiring Status
| Issue | File | Severity |
|-------|------|----------|
| `resources: []` hardcoded in save | `NewOrderSheet.swift:145` | HIGH (moot — replaced by migration) |
| `onViewAll` callback unused by parent | `OrdersPanel.swift` | Medium (moot) |
| No execution history UI | N/A | Medium (moot) |

### Canvas Plan (P2)
- Click-click connection model: Correct for trackpad. Better than drag.
- Semantic zoom (3 levels): Smart for 30-50 node workflows.
- Inspector panel: Combinatorial explosion of 20+ node config forms. **Recommendation: build form-from-schema system (JSON schema → SwiftUI form) instead of hand-coding each.**
- Node type color palette not defined. Recommend: Triggers=Amber, Actions=Blue, Conditions=Purple, Control=Grey.

### Accessibility
- VoiceOver labels needed per node (type + label + status)
- Tab navigation between nodes missing from plan
- Dynamic Type: list UI (P1) handles natively; canvas (P2) needs manual text scaling

---

## Infrastructure Review

- **Deployment impact:** Server restart required (new route module, new SQLite tables). No ALTER on existing tables. Safe forward migration.
- **Rollback strategy:** Clean. `DROP TABLE workflows, workflow_nodes, workflow_edges, workflow_runs, node_executions, workflow_versions` — no other tables affected. Orders stay functional during transition via deprecated aliases.
- **Resource impact:** Acceptable. SQLite is negligible. DAGExecutor memory <100MB for 5 concurrent workflows. **Key constraint:** Ollama contention — parallel RunPrompt nodes serialize. A global inference semaphore (max 1-2 concurrent calls) would be more effective than per-workflow token budgets.
- **New `LogComponent`:** Add `WORKFLOW` to the enum.

---

## Executive Verdicts

- **CISO:** ACCEPTABLE — Existing JWT auth, sandbox, Keychain cover new endpoints. **Conditions:** (1) Credential reference pattern for HTTP Request node configs (never store API keys in `workflow_nodes.config`). (2) Retention policy for `node_executions` — auto-purge after 30-90 days (PII in email/health workflow data).
- **CTO:** ACCEPTABLE — Excellent architecture fit. Net positive on tech debt (replaces stubbed execution). **Conditions:** (1) Validate handler integration in P0 before committing to P1. (2) Budget 40h for canvas, declare victory at 30h. WebView + React Flow as escape hatch.
- **CPO:** ACCEPTABLE — High user value, correct priority ordering (engine before canvas). **Condition:** Define "n8n-level" concretely — enumerate the 15-20 features that matter, mark P1/P2/P3/P4/NEVER.
- **CFO:** ACCEPTABLE WITH CONDITIONS — 91-135h is a significant investment with indirect ROI. **Conditions:** (1) P0 parallel to current trading work. (2) Go/No-Go gate between P0 and P1 — validate handler integration works before committing 80+ more hours.
- **Legal:** ACCEPTABLE — Local-only data, no new regulatory exposure. JMESPath is MIT. GraphKit license needs check before P2.

---

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 4 | Existing auth + sandbox. -1 for PII retention policy gap (fixable). |
| Empathy | 5 | Directly serves Andrew's need for visible, configurable automation. |
| Simplicity | 3 | 91-135h is not simple. Phased list-first approach is significantly simpler than canvas-first. |
| Joy | 5 | Visual workflow canvas executing in real-time = the Jarvis dream. |

---

## Final Critiques

### 1. Most Likely Failure
SwiftUI Canvas node editor (P2) takes 40-50h instead of 25-35h, stretching total timeline to 4+ months.
**Mitigation:** Set 35h time-box. If not working at 35h, pivot to WebView + React Flow (Gemini's strong recommendation).

### 2. Critical Assumption
"The handler can be called from a workflow node without modification." If the handler has implicit dependencies on HTTP context (device JWT, request middleware), synthetic Request construction will break.
**Validation:** P0 must literally call `handler.handle()` with a synthetic Request in a test. If this fails cleanly, the integration path is proven. If it requires handler refactoring, the estimate changes significantly.

### 3. Half-Time Cut List (45h budget)
- **Keep:** P0, P1 backend, P1 list UI
- **Cut:** P2 canvas (list UI forever), P3 event triggers (schedule-only), P4 templates
- **Result:** Working DAG engine with list UI and schedule triggers. Minimum viable workflow engine.

---

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment

**Strengths identified:**
- Pragmatic technology choices (TaskGroup, SQLite checkpointing) — avoids Temporal/Kafka overhead
- Sound architectural boundaries (trading independence, new EventBus)
- Engine-first sequencing is industry standard
- Orders migration shows foresight

**Weaknesses identified:**
- Resource contention is critical — not just Ollama but any intensive node
- PII in node_executions is the most severe issue
- "90% of Temporal's value" masks significant state management complexity

**Gemini's Verdict:** APPROVE WITH CONDITIONS

### Where Both Models Agree (High-Confidence Signals)

1. **Engine-first, canvas-second is correct.** Both models confirm industry evidence supports this sequencing.
2. **Global inference concurrency control is mandatory for P1.** Not optional, not P3 — must be in the engine from day one.
3. **PII retention policy is non-negotiable.** `node_executions` storing email/health data without auto-purge is a security gap.
4. **P0 must be a standalone deliverable.** Both models agree P0 should ship independently before P1 begins.
5. **91h estimate is optimistic.** Both models adjust upward (Claude: 102-135h, Gemini: implicit agreement via "underestimated complexity" finding).
6. **Circular dependency detection is missing from the plan.** Must be added to P1 (validate at workflow save time).

### Where Models Diverge

| Topic | Claude's View | Gemini's View | Resolution |
|-------|--------------|---------------|------------|
| **Canvas technology** | Build custom on SwiftUI Canvas with GraphKit for layout. WebView as escape hatch. | **Strongly reject custom SwiftUI.** Use WebView + React Flow (proven, feature-rich, supported). | **Gemini is more decisive here.** WebView + React Flow is the pragmatic choice — eliminates the highest-risk item entirely. The single-user context means WebView performance is fine. Recommend adopting Gemini's position. |
| **Node limit** | 50 nodes per workflow (from brainstorm) | Start at 20, raise based on usage | **Gemini is right.** 20 is sufficient for all planned templates (Morning Brief = 3 nodes, Email Triage = 4 nodes). Raise to 50 when real usage demands it. |
| **Testing density** | ~120 tests | 150-180 tests with explicit topology coverage | **Gemini is right.** DAG engines have combinatorial state spaces. Budget for 150+ tests with explicit graph topology test fixtures. |
| **P1 UI spike for canvas** | Defer canvas entirely to P2 | Run a non-blocking UI spike in P1 to validate UX assumptions | **Gemini adds nuance.** A throwaway WebView prototype in P1 (1-2 days) could validate the data model and API design against visual requirements. Worth doing if it doesn't slow P1. |
| **Workflow versioning** | Covered by `workflow_versions` table + snapshot on activate | Asks: what happens when a paused workflow's structure changes? State migration between versions. | **Gemini surfaces a real gap.** The brainstorm handles the happy path (snapshot immutability) but not the edge case (resume from checkpoint after structural edit). Add to P1 design: paused runs are bound to their version snapshot; structural edits create a new version but don't affect in-flight runs. |

### Novel Insights from Gemini (Not in Internal Audit)

1. **Debugging must be in P1/P2, not P4.** Execution replay was deferred to P4 as polish. Gemini argues basic debugging (see data that flowed into a failed node) is a core requirement, not polish. **Agree — add execution data inspection to P1 list UI.**
2. **Data merging at fan-in.** The plan covers fan-out (dead path elimination) but is silent on how data from multiple upstream branches merges at a join node. Must be explicitly designed: does the join run once with all inputs, or once per input? **Add to P1 design.**
3. **Workflow versioning and state migration.** What happens when a checkpointed workflow's structure changes between checkpoint and resume? The plan's version snapshotting handles the happy path but not structural divergence. **Add explicit rule: paused runs stay on their snapshot version.**

### @hestia-critic Novel Insights (Adversarial)

1. **The stub was stubbed deliberately.** ADR-021 deferred `execute_order()` not by oversight but by design — the integration complexity was known. P0's 6h estimate may not account for session management (what conversation ID for a background job?), auth context (no device JWT), and memory scope (does execution write to conversation memory?).
2. **Three schedulers coexisting is not a problem.** The discovery doc's own "Refute" section (line 60-61) concluded this, then the recommendation overruled that conclusion. The unification justification may be momentum-driven rather than need-driven.
3. **APScheduler already does most of what the plan proposes.** OrderScheduler already handles cron triggers, interval triggers, date triggers, coalescing, and misfire grace. The DAG engine is adding graph traversal on top of scheduling that already works.
4. **Canvas is the author projecting, not responding to user pain.** No documented instance of Andrew asking for visual workflow editing. The LearningScheduler's 10 monitors are invisible and fine.
5. **`create_from_session()` migration gap.** This method creates orders with `status=WORKING`, placeholder prompts, and skipped validation — no clean mapping to workflow nodes.

### Reconciliation

The internal audit, Gemini, and the critic converge on the same core conclusion: **the engine architecture is sound but the plan needs tightening.** The biggest divergence is on the canvas — Claude was open to custom SwiftUI, Gemini strongly recommends WebView + React Flow, and the critic questions whether the canvas is needed at all.

The resolution: **Build the engine (P0-P1). Validate with real usage. Then decide canvas technology based on what you've learned.** If Andrew uses 5+ workflows regularly, the canvas is justified. If usage is 2-3 workflows, the list UI may be permanent — and that's fine.

The critic's strongest argument — that the unification justification is momentum-driven — is valid but doesn't invalidate the plan. Even without unification, a working DAG engine with visible execution history is genuinely more valuable than a stubbed Orders system. The question isn't "is this better than nothing?" (yes) but "is this the best use of 100+ hours?" (that's a priority call, not an architecture call).

---

## Conditions for Approval

### MUST (block P1 start if unmet)

1. **P0 as standalone deliverable.** Ship `execute_order()` wired to handler. Validate with a test that calls `handler.handle()` with a synthetic Request. If this requires handler refactoring, the P1 estimate changes — stop and re-scope.
2. **Go/No-Go gate after P0.** After P0 ships, Andrew explicitly decides: proceed to P1, or redirect to Sprint 28 (Alpaca). This is a priority decision, not an architecture decision.
3. **Global inference semaphore in P1.** Max N concurrent Ollama calls (start with N=1 on M1). Not optional.
4. **Circular dependency detection in P1.** Validate at workflow save time. Reject cycles.
5. **`node_executions` retention policy in P1.** Auto-purge after configurable TTL (default 30 days). Non-negotiable for PII safety.

### SHOULD (strongly recommended)

6. **Canvas technology: WebView + React Flow.** Eliminates the highest-risk item. If Andrew wants native SwiftUI, set a 35h time-box with React Flow as the explicit escape hatch.
7. **Node limit: start at 20.** Raise to 50 based on real usage, not projection.
8. **Fan-in data merging designed in P1.** How do join nodes handle multiple upstream outputs?
9. **Execution data inspection in P1 list UI.** Basic debugging (see input/output per node in a failed run) is core, not polish.
10. **Define "n8n-level" concretely.** List 15-20 specific features. Mark each P1/P2/P3/P4/NEVER.
11. **Test budget: 150+ tests** with explicit graph topology fixtures (linear, fan-out, fan-in, dead-path, checkpoint-resume, cycle-rejection).

### NICE TO HAVE (P2+)

12. Non-blocking canvas UI spike during P1 (1-2 days, throwaway prototype).
13. Form-from-schema system for node inspector (JSON schema → SwiftUI form).
14. Handler context adapter (dedicated `WorkflowRequest` subclass that pre-fills session/auth/mode).
