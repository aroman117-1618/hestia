# Plan Audit: Project Autonomy — Hestia Self-Development

**Date:** 2026-03-15
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Transform Hestia from a single-pass chat assistant into an agentic coding system capable of multi-step tool chaining, self-modification with verification gates, and continuous learning — enabling Hestia to own routine development tasks via the CLI. Five phases: tool palette, agentic loop, self-aware coding, learning cycle, autonomous maintenance.

---

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None — designed for this | N/A |
| Family (2-5) | Partial | Agentic sessions are singleton — concurrent coding sessions from multiple users would conflict. Git operations on shared repo are unsafe. Token budget is global, not per-user. | Medium — would need session isolation and per-user budgets |
| Community | No | Self-modification of shared infrastructure by any user is a non-starter. No RBAC for who can trigger agentic coding. | High — fundamentally different trust model |

**Assessment:** Scale is correctly scoped for single-user. The `user_id` omission on agentic session tracking is consistent with the rest of the codebase but worth noting.

---

## Front-Line Engineering Review

### Feasibility
The plan is **feasible** with one critical correction. The core while(tool_call) loop is straightforward (~150 lines), and the tool palette expansion is well-defined. The architecture correctly separates the loop (`AgenticLoop`) from the handler (composition pattern).

### Hidden Prerequisites — CRITICAL

1. **Cloud tool calling is not implemented.** `CloudInferenceClient.complete()` has no `tools` parameter. The Anthropic API supports tool_use, but Hestia doesn't thread tool definitions through to cloud providers. **This must be Phase 0, Task 0.0 — before any tool palette work.**

2. **Message type needs extension.** The `Message` dataclass only has `role` and `content`. The agentic loop needs `tool_calls` on assistant messages and `tool_call_id` on tool result messages. Either extend `Message` or use raw dicts for the agentic loop's internal message history.

3. **Cloud response tool_call parsing.** Anthropic returns tool_use blocks in `content[]` array, not in a separate `tool_calls` field like Ollama. The response parser needs to extract these and normalize to the Ollama format (or a common format) that the agentic loop expects.

### Effort Estimates
| Phase | Plan Estimate | Revised Estimate | Why |
|-------|--------------|-------------------|-----|
| 0 | 1 session (~2hr) | 2 sessions (~4hr) | Cloud tool calling adds a full task. Message type extension. |
| 1 | 1-2 sessions (~4hr) | 2 sessions (~4hr) | Accurate, IF Phase 0 prerequisite is solid |
| 2 | 1-2 sessions (~4hr) | 2 sessions (~4hr) | Pre/post test gating is straightforward but integration testing is hard |
| 3 | 1 session (~3hr) | 1 session (~2hr) | Simpler than estimated — mostly prompt engineering |
| 4 | Ongoing | Ongoing | Design-only, no code estimate needed |

**Total revised: ~14 hours (7 sessions at Andrew's pace)**

### Testing Gaps

1. **No integration test for the full loop.** The plan has unit tests for AgenticLoop with mocks, but no test that actually calls a (mocked) cloud API with tool definitions, gets tool_calls back, executes them, and feeds results back. This end-to-end test is critical.

2. **No test for context compaction correctness.** The compactor summarizes messages — how do we verify the summary preserves critical information? This is inherently hard to test deterministically.

3. **No test for concurrent agentic + chat.** The assumption validation says concurrent requests work via asyncio isolation, but there's no test proving a 5-minute agentic session doesn't block regular chat.

4. **edit_file needs a test for binary files.** What happens if someone passes a `.png` or `.pyc`? The handler should detect non-text files and refuse.

### Developer Experience
Good. The `AgenticLoop` as a separate class (not mixed into handler.py's 2200 lines) is the right call. The tool expansion follows existing patterns exactly. The CLI `/code` command is a natural UX extension.

---

## Architecture Review (Backend Lead)

### Architecture Fit
**Good.** The plan follows Hestia's patterns:
- New tools follow `get_X_tools() -> List[Tool]` factory pattern
- `AgenticLoop` uses composition with existing `InferenceClient` and `ToolExecutor`
- WebSocket extension follows existing message type dispatch

### API Design
**One concern:** The plan adds a new WS message type (`"agentic"`) but doesn't define a REST endpoint alternative. What if someone wants to trigger an agentic session from the iOS app (no WebSocket)? Consider a `POST /v1/agentic/run` endpoint that returns a session ID, with `GET /v1/agentic/{id}/events` for SSE streaming. Even if not built now, the `AgenticLoop` should be callable from either transport.

### Data Model
**Missing:** The plan mentions tracking agentic session results in Phase 3 (coding outcomes) but doesn't define a table. Where do agentic sessions, their events, token costs, and outcomes get persisted? The existing `OutcomeTracker` handles chat outcomes but not multi-step coding sessions. Either extend it or add an `agentic_sessions` table.

### Integration Risk
- **handler.py is 2200 lines.** Adding `handle_agentic()` is fine since it delegates to `AgenticLoop`, but the handler is already large. Consider whether pre-processing (session management, memory retrieval, prompt building) should be extracted into a shared helper used by both `handle()` and `handle_agentic()`.
- **Tool count explosion.** Phase 0 adds 8 new tools (edit_file + 5 git + grep + glob). Total goes from ~30 to ~38. The tool definitions JSON grows, consuming more of the 1000-token tool budget in PromptBuilder. For agentic sessions with cloud models (200K context), this is fine. For regular chat with local models (32K context), 38 tool schemas may exceed the budget. **Solution:** Only register agentic tools when in agentic mode, or use a tool filter.

---

## Product Review (CPO)

### User Value
**High for the right tasks.** Phase 0+1 make Hestia dramatically more capable for ALL multi-step tasks (not just coding). "Read this file and summarize it, then find all functions that call X, then update the docstring" becomes possible. This alone justifies the investment.

Phase 2-3 add safety and learning for self-modification specifically. Phase 4 is the aspirational autonomy goal.

### Edge Cases
1. **What happens if the cloud API is down during an agentic session?** The loop should fail gracefully and save partial progress, not lose 20 tool calls of work.
2. **What if a tool call takes 60+ seconds?** (e.g., running the full test suite). The per-tool timeout is 30s, but pytest can take 90s+. The agentic session timeout is 300s — a single slow tool call eats 30% of the budget.
3. **What if the user cancels mid-session?** The WS protocol needs a `cancel` type for agentic sessions. The plan doesn't specify how partial work is handled — do edits get reverted?

### Opportunity Cost
Building this over the next 7 sessions (~14 hours, 2-3 weeks at Andrew's pace) means NOT building:
- macOS Neural Net view updates for the Knowledge Graph (Sprint 9 follow-up)
- Bright Data MCP integration (1 hour, approved in discovery)
- Google Workspace CLI integration (2 hours, approved in discovery)
- MetaMonitor (Sprint 11B, deferred)

**Recommendation:** Do Phase 0 first (it's useful independently), then interleave Bright Data + gws setup (3 hours total) before continuing to Phase 1. The quick wins shouldn't wait for a multi-sprint initiative.

### Scope
**Right-sized for phases 0-2.** Phase 3 (learning cycle) is premature — it assumes enough agentic sessions have happened to generate meaningful coding patterns. Defer to when there's data. Phase 4 (autonomous maintenance) is correctly marked as design-only.

---

## Infrastructure Review (SRE)

### Deployment Impact
- **Phase 0:** Config change only (`execution.yaml`) + new tool files. No server restart for tools (registered at init).
- **Phase 1:** New module + handler modification. Requires server restart.
- **Phase 2-3:** Source modifications. Requires restart.
- **No database migrations** — the plan doesn't add tables (Phase 3 should, but doesn't).

### New Dependencies
None. All implementations use stdlib + existing packages (aiosqlite, pathlib, subprocess).

### Monitoring
**Gap:** The plan has no observability story. Agentic sessions should log:
- Session start/end with duration and token cost
- Each tool call with timing
- Termination reason
- Cumulative cost per day/week

Without this, Andrew can't track API spend or debug failed sessions.

### Rollback Strategy
- **Phase 0:** Remove tools from registry, revert config. Clean.
- **Phase 1:** Remove `handle_agentic()`, revert WS changes. Clean.
- **Git safety:** All agentic coding happens on the main repo. If Hestia makes a bad commit, `git revert` is the rollback. The plan should use a **feature branch pattern** — agentic sessions work on branches, not main.

### Resource Impact
- **Token cost:** MAX_TOKEN_BUDGET = 100K tokens per session. At Sonnet pricing (~$3/million input, ~$15/million output), a max session costs ~$0.50-$2. Reasonable for routine tasks.
- **Time:** 300s timeout per session. Occupies the inference client but doesn't block the event loop.
- **Memory:** Tool results accumulate in message history. A 25-iteration session with file reads could grow to 200K+ tokens in memory. Need context compaction BEFORE Phase 2, not in Phase 2.

---

## Executive Verdicts

### CISO: APPROVE WITH CONDITIONS

The attack surface expansion is significant but well-understood:
- **Codebase write access** is the biggest change — moving from "data files only" to "source code." Mitigated by: allowlist (only `~/hestia`), no auto-approve for writes, pre/post test gates (Phase 2), human approval for commits.
- **Git operations** add a new action class. Mitigated by: blocking force-push, reset --hard, `--no-verify`, `git add -A`.
- **Self-modification of security code** is the nightmare scenario. Mitigated by: PathValidator is under `~/hestia/hestia/files/security.py` which is in the allowlist but protected by the verification layer (Phase 2).

**Conditions:**
1. Phase 2 (verification layer) MUST be implemented before any unattended agentic sessions
2. `hestia/files/security.py`, `hestia/execution/sandbox.py`, `hestia/execution/gate.py` should be added to a **critical files list** that requires explicit human approval even in Phase 4
3. Agentic sessions must be logged with full audit trail (tool calls, edits, commits)
4. Add a hard kill switch: `/code stop` that immediately terminates the session and reverts uncommitted changes

### CTO: APPROVE WITH CONDITIONS

Architecture is sound. The `AgenticLoop` as a composition pattern is correct — not polluting handler.py. The tool palette follows established patterns. Cloud routing already exists.

**Conditions:**
1. **Add Task 0.0: Cloud tool calling** — extend `CloudInferenceClient.complete()` to accept `tools` param and parse Anthropic's tool_use response format. This is the critical prerequisite the plan misses.
2. **Move context compaction to Phase 1, not Phase 2** — without compaction, a 25-iteration session will exhaust the context window, making Phase 1 unusable for real tasks.
3. **Feature branch pattern** — agentic sessions should create and work on a branch, never commit directly to main. This is a safety net that costs almost nothing.
4. **Add agentic_sessions table** for persistence — don't just log to stdout. Track: session_id, user_instruction, tool_calls_json, tokens_used, cost_usd, outcome, duration_ms, branch_name.

### CPO: APPROVE WITH CONDITIONS

The value proposition is strong — Phase 0+1 alone make Hestia a fundamentally better tool for all multi-step tasks. The phased approach is correct.

**Conditions:**
1. **Interleave quick wins** — Bright Data (1hr) and Google Workspace CLI (2hr) should be done alongside or before Phase 1. They're approved, low-effort, and deliver immediate user value.
2. **Defer Phase 3** (learning cycle) until there's enough agentic session data to learn from. It's premature to build the learning infrastructure before the core loop has been used in anger.
3. **Define a "Phase 0+1 success criteria"** — what task, executed via `/code`, proves the system works? E.g., "Hestia updates the test count in CLAUDE.md after running pytest."

---

## Final Critiques

### 1. Most Likely Failure
**Cloud tool calling integration.** The plan assumes cloud models receive tool schemas and return structured tool_calls. This doesn't work today. If the Anthropic tool_use response parsing is buggy (different format than Ollama, different content block structure), the entire agentic loop breaks.

**Mitigation:** Task 0.0 (cloud tool calling) should include thorough integration tests with mocked Anthropic responses in the exact format the API returns. Test with real Anthropic API calls as a manual smoke test before Phase 1.

### 2. Critical Assumption
**"Cloud models can reliably chain 25+ tool calls."** The plan's MAX_ITERATIONS = 25 assumes the model maintains coherent context across that many iterations. Anthropic's Sonnet/Opus can do this — Claude Code proves it daily. But Hestia's message format, system prompt, and tool schemas may introduce confusion that doesn't exist in Claude Code's optimized setup.

**Validation:** After Phase 1, run 5 real tasks of increasing complexity. If the model loses coherence before iteration 15, reduce MAX_ITERATIONS and add a "planning step" where the model outputs its plan as text before tool calling begins.

### 3. Half-Time Cut List
If we had half the sessions (4 instead of 7):

| Keep | Cut |
|------|-----|
| Task 0.0: Cloud tool calling | Task 0.4: grep/glob tools (use `run_command` with grep/find) |
| Task 0.1: Codebase allowlisting | Phase 3: Learning cycle (premature) |
| Task 0.2: edit_file tool | Phase 4: Autonomous maintenance (design-only anyway) |
| Task 0.3: Git tools | Task 2.2: Context compaction (simplify: just cap at 15 iterations instead) |
| Task 1.1: AgenticLoop core | Task 2.3: Agentic system prompt (put it in config, not code) |
| Task 1.2: Handler + WS wiring | |
| Task 1.3: CLI `/code` command | |
| Task 2.1: Verification layer | |

**This reveals the true priorities:** Cloud tool calling → codebase access → edit tool → git tools → agentic loop → verification. Everything else is optimization.

---

## Conditions for Approval

The plan is **APPROVED** with these conditions that MUST be addressed before execution:

### Must-Fix (Block execution)

1. **Add Task 0.0: Cloud Tool Calling** — Extend `CloudInferenceClient.complete()` to accept `tools` parameter, thread through to Anthropic/OpenAI/Google API calls, parse tool_use response blocks, normalize to common format. This is the #1 prerequisite.

2. **Move context compaction from Phase 2 to Phase 1** — Without compaction, a 25-iteration session on a 32K context (or even 200K cloud context with large file reads) will exhaust the window. The loop is unusable for real tasks without it.

3. **Add feature branch pattern to git tools** — `git_commit` should work on a branch created at session start, never on main. Add `git_create_branch` and `git_checkout` tools.

4. **Add critical files protection list** — `security.py`, `sandbox.py`, `gate.py`, `execution.yaml` require explicit human approval for edits, even when auto-approve is enabled in Phase 4.

### Should-Fix (Address during execution)

5. **Add `agentic_sessions` table** for persistence and cost tracking
6. **Add observability/logging** for agentic sessions (token cost, duration, tool sequence)
7. **Define Phase 0+1 success criteria** — specific task that proves the system works
8. **Add binary file detection** to edit_file tool
9. **Handle cancellation** — `/code stop` kills session, reverts uncommitted changes

### Nice-to-Have (Can defer)

10. **REST endpoint alternative** to WebSocket for agentic sessions
11. **Per-user token budget tracking** (for future multi-user)
12. **Interleave Bright Data + gws quick wins** between Phase 0 and Phase 1
