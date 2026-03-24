# Second Opinion: Workflow Step Builder UX

**Date:** 2026-03-24
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external) + @hestia-critic (adversarial)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Close the gap between the current empty React Flow canvas and a usable n8n-style visual workflow editor. Andrew's model: each step has Title, Trigger (immediate/delayed/scheduled), Prompt (LLM instructions), and Resources (Mail, Calendar, Notes, Web, etc). Steps link sequentially with output flowing forward.

## Critical Finding: Model Mismatch

**All three reviewers independently flagged the same issue.** Andrew's "Step" mental model doesn't map 1:1 to the backend's 8 node types. This is the #1 architectural decision.

| Andrew's Model | Backend Model | Gap |
|---------------|---------------|-----|
| Step with Prompt + Resources | `run_prompt` + `call_tool` (separate nodes) | One "Step" may compile to multiple nodes |
| Per-step Trigger (immediate/delayed/scheduled) | `Workflow.trigger_config` (workflow-level only) | No per-node delay/trigger mechanism exists |
| "Resources" (Mail, Calendar, Notes, Web) | `allowed_tools` (flat string list of internal names) | No categorized resource catalog or picker endpoint |

**Gemini's key insight:** The UI should act as a **compiler** — translating Andrew's intuitive "Step" config into the backend's DAG primitives. User sees simple steps; system generates the node graph.

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | Per-step delays need backend work | Low |
| Family | Yes | Same data model | Low |
| Community | No | Resource catalog is user-specific | Medium |

## Front-Line Engineering

- **Feasibility:** Yes, but requires backend changes the discovery didn't scope
- **Hidden prerequisites:**
  1. Per-step delay mechanism (new `delay` node type or edge property)
  2. Resource catalog endpoint (categorized tool listing)
  3. Step-to-DAG translation layer (one Step → multiple backend nodes)
- **Estimate:** Discovery says 10-14h. All three reviewers say **20-28h** realistic. The translation layer alone is 5-8h of design + implementation.
- **Testing gaps:** How to test the Step→DAG compilation? Need test cases for compound steps.

## Architecture Review

- **Fit:** Fits existing patterns if we add a translation layer between the UI "Step" model and backend node types
- **Data model change needed:** Either (a) add `delay_seconds` to `WorkflowEdge` or (b) add `NodeType.DELAY` with `asyncio.sleep` executor
- **Integration risk:** Medium. The translation layer is a new concept — it sits between the canvas and the API

## Product Review

- **User value:** VERY HIGH. This is the feature that makes workflows usable. Without it, the canvas is read-only.
- **Scope:** Right-sized IF the translation layer is included. Without it, Steps can't have triggers or resources.
- **Andrew's exact words:** "Each Step should include a Title, Trigger, Prompt, and Resources... the Prompt tells the LLM what to do with that step and those resources, the output of which is provided to the subsequent step."

## UX Review

- **Step model is the right abstraction** — unanimous across all reviewers
- **Resource picker:** Needs design. Flat checkbox list of 20+ tools is unusable. Recommend categorized tag-style picker with search.
- **Per-step triggers:** Show as a config field on each step (Immediately / After delay / On schedule), compiled to backend nodes transparently
- **Empty state:** Pre-populate trigger node on new workflow creation (industry standard)

## Infrastructure Review

- **Deployment impact:** Backend changes require server restart. New delay node type needs migration.
- **New dependencies:** None beyond existing React Flow
- **Rollback:** Canvas is additive. List view always works.

## Executive Verdicts

- **CISO:** Acceptable — no new attack surface, tool access uses existing auth
- **CTO:** Approve with conditions — translation layer must be designed before UI coding. Per-step delay needs backend work.
- **CPO:** Approve — this is exactly what Andrew asked for. The Step model matches his mental model.
- **CFO:** Approve with conditions — 20-28h realistic estimate (not 10-14h). High ROI given 40h+ backend investment.
- **Legal:** Acceptable — no new external dependencies or data handling

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | Tool access through existing authenticated API |
| Empathy | 5 | Step model matches exactly how Andrew thinks about workflows |
| Simplicity | 3 | Translation layer adds hidden complexity, but simplifies the UX |
| Joy | 5 | Building steps visually, watching them execute — the Jarvis moment |

## Cross-Model Validation (Gemini 2.5 Pro)

### Where All Three Models Agree
- The "Step" abstraction is the correct UX model (not raw node types)
- 10-14h estimate is optimistic — realistic is 20-28h
- Per-step triggers need backend work (not just UI)
- Resource picker needs dedicated design (not a flat checkbox list)
- Pre-populated trigger node is industry standard

### Where Models Diverge

| Topic | Claude | Gemini | @hestia-critic | Resolution |
|-------|--------|--------|----------------|------------|
| Translation layer complexity | Medium (5-8h) | High (core of the feature) | High (undefined, risky) | Gemini is right — this is the hardest part and must be designed first |
| Per-step delay implementation | Edge property | Auto-insert schedule node | New executor mechanism | Gemini's auto-insert approach is cleanest — UI stays simple, backend uses existing primitives |
| Resource = allowed_tools? | Partial match | Needs catalog | No mapping exists | All agree: need a categorized `/v1/tools/categories` response for the picker |

### Novel Insights from Gemini
1. **"Compiler" framing** — the UI should compile Steps into DAG nodes, not expose nodes directly. This is the key architectural insight.
2. **"Hybrid Step" problem** — a Step with both Prompt AND Resources may need to generate multiple backend nodes (run_prompt + call_tool). The translation layer must handle this.
3. **Vertical slice first** — build ONE complete Step end-to-end before building all 5 node types. Validates the architecture.

## Conditions for Approval

1. **Design the translation layer FIRST** — how does one "Step" (Title/Trigger/Prompt/Resources) compile to backend nodes? Write a spec covering: immediate steps, delayed steps, steps with resources, steps with resources AND prompt, condition steps.

2. **Add per-step delay to backend** — either `NodeType.DELAY` with `asyncio.sleep` executor, or `delay_seconds` on `WorkflowEdge`. Must work before the UI can offer "after X minutes" trigger option.

3. **Build one vertical slice** — implement a single "Prompt Step" end-to-end (canvas → bridge → API → canvas update) before building all step types. This validates the architecture and gives a real time estimate.

4. **Design the resource picker** — categorized tag-style component with search. Backend already has `GET /v1/tools/categories`. Map categories to human-readable names (Calendar, Mail, Notes, Reminders, Web, Files).

5. **Re-estimate at 20-28h** — the 10-14h discovery estimate doesn't include the translation layer, per-step delay backend work, or resource catalog.
