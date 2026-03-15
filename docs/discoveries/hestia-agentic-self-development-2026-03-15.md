# Discovery Report: Closing the Gap Between Hestia and Claude Code

**Date:** 2026-03-15
**Confidence:** High
**Decision:** Hestia can become a capable self-development system through four incremental phases, but the architecture requires a fundamentally different execution model than what exists today. The single biggest gap is the absence of an iterative tool loop.

## Hypothesis

Can Hestia evolve from a chat assistant with tools into an agentic coding system capable of owning her own ongoing development via the CLI? What are the specific architectural gaps, and what is a realistic phased approach?

## Architecture Comparison

### What Claude Code Actually Does

Claude Code's architecture is deceptively simple. The core is a **while-loop that runs until the model stops calling tools**:

```
while True:
    response = llm.call(messages, tools)
    if response.stop_reason != "tool_use":
        break  # Natural termination — model has nothing more to do
    for tool_call in response.tool_calls:
        result = execute_tool(tool_call)
        messages.append(tool_call)
        messages.append(tool_result)
```

This minimal loop produces high agency because:

1. **Iterative execution**: The model sees tool results and decides what to do next. It can chain 50+ tool calls in a single turn — read a file, edit it, run tests, see failures, fix them, run tests again.
2. **Self-correction**: When a tool returns `is_error: true`, the model adapts. No special error-handling code needed — the model *is* the error handler.
3. **Context accumulation**: Each tool result feeds back into the message history, building a progressively richer picture of the codebase.
4. **Natural termination**: The loop ends when the model decides it's done (emits a text response with no tool calls), not when an arbitrary counter hits a limit.

**Key tools** (the "tool palette" that enables coding):
- **Bash**: Arbitrary shell commands (git, pytest, grep, build commands)
- **Read**: File content examination
- **Edit**: Surgical string replacement in files
- **Write**: Full file creation/overwrite
- **Glob**: Fast file pattern matching
- **Grep**: Content search across codebase
- **WebSearch/WebFetch**: External information retrieval

**Context management**: Claude Code operates within a ~200K token window. At ~80% capacity, it triggers automatic **compaction** — summarizing conversation history while preserving critical artifacts (file paths, function signatures, error messages). This lets long coding sessions (100+ tool calls) avoid hitting the wall.

**Verification pattern**: The model naturally gravitates toward read-edit-verify cycles. After editing a file, it runs tests or reads the file back to confirm the change. This isn't programmed — it emerges from the training + system prompt.

**Git workflow**: Claude Code can stage, commit, create branches, push, and create PRs. It treats git as just another tool in the palette.

### What Hestia Can Do Today

Hestia's orchestration pipeline in `handler.py`:

```
Request → Validation → Memory Retrieval → Prompt Building → Council Intent Classification
→ Inference (single call) → Tool Detection (3-tier) → Tool Execution (single pass)
→ Response Formatting → Response
```

**Critical architectural facts from the codebase:**

1. **Single inference call, single tool pass**: `_run_inference_with_retry()` makes one LLM call, detects tool calls (via 3-tier priority: native Ollama → council analyzer → regex fallback), executes them once, formats the result, and returns. There is **no iteration**. The model cannot see tool results and decide to call more tools.

2. **Retry is for validation, not iteration**: The retry loop (max 3 attempts) only triggers when `ValidationPipeline` rejects the response (e.g., empty content). It re-runs inference with guidance, but this is not agentic iteration — it's quality assurance.

3. **Tool executor is capable but underused**: `ToolExecutor` supports batch execution (up to 3 concurrent), sandbox validation, communication gating, and approval workflows. The execution infrastructure is solid. The problem is it's called once per request.

4. **Council is classification-only**: The CouncilManager classifies intent (CHAT, TOOL, QUESTION, etc.) and optionally runs post-inference analysis/validation. It does not plan multi-step task decomposition.

5. **File operations exist**: `read_file`, `write_file`, `list_directory`, `search_files` are registered tools with PathValidator security (allowlist-first, denylist defense, TOCTOU-safe reads, soft delete).

6. **Shell execution exists**: `SandboxRunner.run_shell_command()` can execute arbitrary shell commands with blocked-pattern filtering and timeout enforcement.

7. **CLI repo context is injected**: The CLI sends `context_hints` with git branch, status, recent commits, and project file snippets (CLAUDE.md, SPRINT.md) — truncated to 16KB budget.

8. **WebSocket streaming supports tool approval**: The WS protocol already has `tool_request`/`tool_approval` events for interactive mid-stream tool authorization.

9. **Cloud routing provides access to capable models**: 3-state routing (disabled/smart/full) with Anthropic/OpenAI/Google. Cloud models are dramatically better at agentic coding than local 9B models.

10. **Knowledge graph + PrincipleStore**: Entity/fact graph with communities, plus distilled behavioral principles. These feed context but don't yet influence coding decisions.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Solid tool infrastructure (executor, sandbox, registry, gating). File security already defense-in-depth (allowlist, denylist, TOCTOU, soft delete). WebSocket streaming with tool approval protocol. Cloud routing to capable models. Knowledge graph for codebase understanding. CLI already sends repo context. 1683 tests, mature codebase. | **Weaknesses:** No iterative tool loop (single-pass architecture). No context window management/compaction. Council does classification, not task planning. Local models (9B) too weak for agentic coding. Tool palette missing Edit/Glob/Grep equivalents. No git tools. Sandbox allows only pre-configured paths (hestia source code not in allowlist). Blocked commands include `sudo` and `chmod` (reasonable) but nothing for safe git operations. |
| **External** | **Opportunities:** Claude API tool_use protocol is well-documented. Hestia could use cloud models (Opus/Sonnet) for agentic coding sessions specifically. PrincipleStore could capture coding preferences/patterns. Knowledge graph could map codebase architecture. Self-improving system could learn from its own changes. CLI already has the UX foundation. | **Threats:** Self-modifying AI is a top-tier security risk (prompt injection → code injection). Local model quality may not support reliable tool chaining. Token costs for long agentic sessions via cloud API. Regression risk if Hestia modifies her own tests. Infinite loops if termination conditions fail. Andrew has ~6 hrs/week — oversight bandwidth is limited. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | **Iterative tool loop** (the single biggest gap). **Codebase path allowlisting** (can't edit own source without it). **Edit tool** (surgical replacement vs. full file writes). **Context compaction** (long sessions will exhaust context). | **Glob/Grep tools** (nice but Bash+find works). **Git convenience tools** (can use Bash). |
| **Low Priority** | **Task planning/decomposition** (multi-step plans from natural language). **Knowledge graph integration** (codebase architecture awareness). **PrincipleStore for coding patterns** (learn coding preferences). **Self-healing from test failures**. | **Local model agentic coding** (9B models can't do this reliably). **Docker sandbox** (subprocess is fine for now). **Automatic PR creation** (manual git push is fine). |

## Argue (Best Case)

The case FOR Hestia self-development is strong:

1. **90% of the infrastructure exists.** ToolExecutor, SandboxRunner, PathValidator, file tools, shell execution, WebSocket streaming, cloud routing — all built and tested. The gap is architectural (loop structure), not foundational.

2. **Cloud models are excellent at agentic coding.** Anthropic's Sonnet/Opus via the existing cloud routing infrastructure can handle multi-step coding tasks. The `_call_cloud()` method already exists and supports tool definitions.

3. **The CLI is the natural interface.** `hestia-cli` already sends repo context, supports streaming, handles tool approvals. It's a short path from "chat assistant with tools" to "agentic coding assistant."

4. **Self-improvement creates a virtuous cycle.** Hestia improving her own code means every session makes the next session more capable. The PrincipleStore can capture "when I edit Python files, run the matching test" as a learned behavior.

5. **The security model is already conservative.** PathValidator's allowlist-first approach, soft delete, communication gating, and tool approval workflows provide a solid foundation. Adding the hestia source directory to the allowlist with write-approval requirements is a natural extension.

6. **Andrew's time constraint makes this MORE valuable, not less.** If Hestia can handle routine maintenance (dependency updates, test fixes, lint cleanup, doc updates) autonomously with approval gates, it amplifies Andrew's limited hours.

## Refute (Devil's Advocate)

The case AGAINST is also serious:

1. **Self-modifying code is inherently dangerous.** A prompt injection in a conversation could lead Hestia to modify her own security layer, disable sandboxing, or exfiltrate credentials. The attack surface is not theoretical — it's the #1 risk in agentic AI systems per OWASP and NVIDIA's security guidance.

2. **The model quality gap is real.** Local Qwen 3.5 9B cannot reliably chain tools, plan multi-step edits, or recover from errors. This means agentic coding REQUIRES cloud models, which means every self-development session costs API tokens and sends code to external providers.

3. **Quis custodiet ipsos custodes?** If Hestia modifies her own tests, she can make a broken change pass. If she modifies her own validator, she can bypass security checks. The system that validates changes cannot also be the system making changes — there must be an external verification layer.

4. **Context window costs compound.** A typical Claude Code session for a non-trivial change uses 50-200 tool calls. At ~200K tokens per session with cloud pricing, self-development sessions could cost $2-10 each. With ~6 hours/week of oversight, Andrew needs to prioritize which changes are worth the cost.

5. **The "retry until green" failure mode.** An agentic system that can modify code and run tests can theoretically enter a loop where it "fixes" test failures by weakening assertions rather than fixing bugs. This requires careful termination conditions and human review.

6. **Infinite loop risk.** Without proper termination (max iterations, token budget, time limit), a coding session could run indefinitely, accumulate huge API costs, and produce a git history of increasingly confused changes.

## Third-Party Evidence

**Supporting patterns from industry:**

- **Claude Code itself** demonstrates that the while(tool_call) loop architecture works at massive scale ($1B+ ARR). The pattern is validated.
- **Anthropic's Agent SDK** documents the exact loop structure and provides reference implementations. The pattern is well-understood.
- **Temporal.io's agentic cookbook** shows production patterns for Claude tool calling with retry, error handling, and workflow management.

**Contradicting evidence:**

- **OpenClaw** (autonomous coding agent) had critical security vulnerabilities discovered in 2025-2026 — missing file isolation, dependency injection attacks, cross-session leakage. Self-modifying systems are hard to secure.
- **NVIDIA's security guidance** (2026) explicitly warns that container isolation alone is insufficient; defense-in-depth combining OS primitives, hardware virtualization, and network segmentation is "now mandatory" for untrusted AI-generated code.
- No known production system allows an AI to modify its own codebase without human review gates. Even Claude Code requires the developer to approve changes.

**Alternative approaches considered:**

1. **MCP-based approach**: Instead of building an iterative loop into Hestia's handler, expose Hestia's development tools as an MCP server that Claude Code connects to. Hestia becomes the tool provider, Claude Code remains the agent. *Verdict: Clever but misses the point — the goal is Hestia's autonomy, not delegating to Claude Code.*

2. **GitHub Actions approach**: Hestia creates PRs, GitHub Actions runs tests, Andrew reviews. *Verdict: This is actually part of the solution (verification layer), but doesn't address the agentic coding loop itself.*

3. **Diff-and-approve approach**: Hestia generates diffs but never applies them directly. Andrew reviews and applies. *Verdict: This is a good safety layer for Phase 1 but prevents autonomous operation.*

## The Specific Gaps

### Gap 1: No Iterative Tool Loop (CRITICAL)
**Current**: Single inference → single tool pass → response.
**Needed**: `while model.wants_tools: execute → feed_back → re-infer`.
**Effort**: Medium. The handler needs a new method (`handle_agentic()`) that wraps the existing inference + tool execution in a loop with termination conditions (max iterations, token budget, natural stop).

### Gap 2: No Codebase Access (CRITICAL)
**Current**: Sandbox `allowed_directories` only includes `~/hestia/data`, `~/hestia/logs`, `/tmp/hestia`, `~/Documents`, `~/Desktop`, and iCloud.
**Needed**: `~/hestia` (the project root) must be in the allowlist, with write operations requiring approval.
**Effort**: Low. Config change + ensuring PathValidator covers `.py`, `.swift`, `.yaml`, `.md` files.

### Gap 3: Missing Edit Tool (HIGH)
**Current**: `write_file` does full file overwrites. No surgical edit capability.
**Needed**: An `edit_file` tool that takes `(file_path, old_string, new_string)` — exact match replacement, fails if not unique.
**Effort**: Low-medium. The tool itself is simple; the security validation (ensuring old_string actually exists, handling encoding) needs care.

### Gap 4: No Context Compaction (HIGH)
**Current**: No mechanism to manage growing context during multi-tool sessions.
**Needed**: After N tool calls or at X% context usage, summarize older messages while preserving recent tool results and key decisions.
**Effort**: Medium. Requires LLM call for summarization + message list management.

### Gap 5: No Git Tools (MEDIUM)
**Current**: No git operations in tool registry. `run_command` exists but blocked patterns are overly broad.
**Needed**: `git_status`, `git_diff`, `git_add`, `git_commit`, `git_log` tools with appropriate safeguards (no force push, no hard reset).
**Effort**: Low. Wrapper tools around shell commands with validation.

### Gap 6: No Task Planning (MEDIUM)
**Current**: Council classifies intent. No multi-step planning.
**Needed**: For complex requests, decompose into a plan before executing. The model can do this naturally if the system prompt instructs it, but structured planning (with checkpoints) is more reliable.
**Effort**: Medium. Could be as simple as a system prompt addition, or as complex as a formal planning agent.

### Gap 7: No Verification Layer for Self-Modification (CRITICAL for security)
**Current**: No distinction between "editing Andrew's documents" and "editing Hestia's own source code."
**Needed**: When the target is Hestia's own codebase, mandatory verification: (1) run affected tests before and after, (2) git diff review, (3) optional human approval gate.
**Effort**: Medium-high. Requires awareness of "self" (paths under `~/hestia/hestia/`), pre/post test execution, and a hold-for-review mechanism.

### Gap 8: Cloud-Only for Agentic Coding
**Current**: Local 9B models can handle single tool calls.
**Needed**: Agentic coding sessions must route to cloud (Sonnet/Opus). The existing `enabled_smart` and `enabled_full` routing modes support this, but the system needs to recognize "this is a coding task" and force cloud routing.
**Effort**: Low. Intent classification already exists; adding a CODING intent that forces cloud is straightforward (and already partially done with ADR-040's CODING tier).

## Recommendation

### Phased Approach

**Phase 0: Foundation (1 session, ~2 hours)**
- Add `~/hestia` to sandbox `allowed_directories`
- Create `edit_file` tool (old_string/new_string replacement)
- Create basic git tools (`git_status`, `git_diff`, `git_add`, `git_commit`)
- Add `CODING` intent type that forces cloud routing
- No behavioral changes — just expanding the tool palette

**Phase 1: Iterative Loop (2 sessions, ~4 hours)**
- Implement `handle_agentic()` in handler.py — the while(tool_call) loop
- Add termination conditions: max_iterations=25, max_tokens_used, timeout=300s
- Add context budget tracking (count accumulated tokens, warn at 70%)
- Wire into WS streaming so CLI can observe multi-step execution
- Test with simple tasks: "read file X and tell me what it does", "fix the typo in this file"

**Phase 2: Self-Aware Coding (2 sessions, ~4 hours)**
- Add verification layer for self-modification:
  - Detect when edit target is under `~/hestia/hestia/` or `~/hestia/tests/`
  - Run `pytest` on affected test file before AND after edit
  - Generate `git diff` and stream to client for review
  - Add `approve_change` / `reject_change` client interaction
- Add context compaction (summarize older messages when at 60% capacity)
- System prompt additions for coding discipline (test before commit, one change at a time)

**Phase 3: Learning Cycle Integration (1-2 sessions, ~3 hours)**
- PrincipleStore captures coding patterns: "always run tests after editing handler.py", "prefer Edit over Write for existing files", "check imports after adding new modules"
- Knowledge graph maps codebase architecture: module dependencies, test coverage, file ownership
- Principles are injected into agentic session system prompts
- Outcomes tracking records which self-modifications succeeded vs. reverted

**Phase 4: Autonomous Maintenance (ongoing)**
- Hestia can be asked: "update the test count in CLAUDE.md", "add the new LogComponent to the enum", "fix the failing test in test_research.py"
- For routine tasks (doc updates, count fixes, lint), auto-approve after test pass
- For code changes, always hold for Andrew's review
- CI/CD integration: Hestia creates branch, pushes, CI runs, Andrew reviews PR

### What Would Change This Recommendation

- **If local model quality improves dramatically** (e.g., a 14B model that reliably chains 20+ tools): Phase 0-1 become viable without cloud dependency.
- **If a security incident occurs** during self-modification: Tighten to diff-and-approve only, remove auto-approve for any code changes.
- **If token costs are prohibitive**: Limit agentic sessions to pre-approved task types with cost caps.
- **If Andrew gets more time**: Accelerate toward Phase 4 with more ambitious autonomous tasks.

## Final Critiques

### The Skeptic: "Why won't this work?"

**Challenge**: "Local models can't do agentic coding. Cloud costs will be prohibitive. Self-modification is too dangerous for a hobby project with one developer."

**Response**: Valid concerns, but mitigated by design:
- Cloud routing already works and is necessary for non-trivial tasks anyway. Agentic coding is an incremental cost, not a new category.
- The phased approach starts with human-in-the-loop (Phase 1-2) before any autonomy (Phase 4). Each phase is independently valuable.
- The security model (allowlist + soft delete + test verification + git diff review + human approval) provides defense-in-depth. A prompt injection that tries to modify security code would need to: bypass the sandbox allowlist, trick the model into calling edit_file on security.py, pass the pre/post test gate, AND get approved by Andrew. That's four independent barriers.
- The real risk is not malicious self-modification — it's *incompetent* self-modification (broken code that passes weak tests). This is mitigated by the same code review process used for any PR.

### The Pragmatist: "Is the effort worth it?"

**Challenge**: "This is 4+ sessions of work for a system that Andrew uses 6 hours/week. Just use Claude Code directly."

**Response**:
- Claude Code already handles Hestia development. The question is whether Hestia should be able to handle *routine* development tasks herself — doc updates, count fixes, dependency bumps, test fixes. These consume 20-30% of development time and don't require strategic thinking.
- Phase 0-1 alone (~6 hours) provide value: the iterative tool loop makes Hestia dramatically more capable for ALL tasks (not just coding), because multi-step operations (read, analyze, act) work instead of one-shot responses.
- The learning cycle (Phase 3) is where the real ROI compounds: every self-development session teaches Hestia something about her own codebase that makes future sessions faster.

### The Long-Term Thinker: "What happens in 6 months?"

**Challenge**: "In 6 months, local models will be 3x better, cloud APIs will have native agent orchestration, and Claude Code will have an SDK. Will this be wasted work?"

**Response**:
- The iterative tool loop (Phase 1) is foundational regardless of model improvements. Better models make it MORE valuable, not less.
- If Anthropic releases an Agent SDK that Hestia could use directly, the tool palette (Phase 0) still applies — those tools become MCP-compatible endpoints.
- The knowledge graph + PrincipleStore integration (Phase 3) is Hestia-specific and won't be obsoleted by external tooling. No external system knows Hestia's architecture.
- The phased approach means each phase is independently deployable. If the landscape shifts after Phase 1, the remaining phases can be re-evaluated.

## Open Questions

1. **Token budget per agentic session**: What's a reasonable cap? $1? $5? Should it vary by task type?
2. **Auto-approve scope**: Which changes are safe to auto-approve after tests pass? Documentation only? Config-only? Any file with >80% test coverage?
3. **Rollback mechanism**: If a self-modification breaks something discovered later, should Hestia have a `git revert` tool, or should Andrew handle rollbacks manually?
4. **Concurrent sessions**: Can Hestia run an agentic coding session while also serving chat requests from the iOS app? The current singleton handler doesn't support this.
5. **Test oracle problem**: How does Hestia verify that a change is *correct* vs. merely *passing tests*? Tests can have gaps. Should there be a secondary verification (e.g., type checking, lint, or a "reviewer" LLM pass)?

---

Sources:
- [How Claude Code Works](https://code.claude.com/docs/en/how-claude-code-works)
- [How the Agent Loop Works - Claude API](https://platform.claude.com/docs/en/agent-sdk/agent-loop)
- [Tracing Claude Code's LLM Traffic](https://medium.com/@georgesung/tracing-claude-codes-llm-traffic-agentic-loop-sub-agents-tool-use-prompts-7796941806f5)
- [Claude Code: A Simple Loop That Produces High Agency](https://medium.com/@aiforhuman/claude-code-a-simple-loop-that-produces-high-agency-814c071b455d)
- [Context Window Management in Claude Code](https://deepwiki.com/FlorianBruniaux/claude-code-ultimate-guide/3.3-context-window-management)
- [How Agents Like Claude Code Manage Their Context Window](https://newsletter.victordibia.com/p/context-engineering-101-how-agents)
- [NVIDIA: Practical Security Guidance for Sandboxing Agentic Workflows](https://developer.nvidia.com/blog/practical-security-guidance-for-sandboxing-agentic-workflows-and-managing-execution-risk/)
- [NVIDIA: Code Execution Risks in Agentic AI](https://developer.nvidia.com/blog/how-code-execution-drives-key-risks-in-agentic-ai-systems/)
- [NCC Group: Securing Agentic AI](https://www.nccgroup.com/securing-agentic-ai-what-openclaw-gets-wrong-and-how-to-do-it-right/)
- [OWASP Agentic AI Risks](https://www.kaspersky.com/blog/top-agentic-ai-risks-2026/55184/)
- [Agentic Coding Security: Risks When AI Takes Control](https://vibeappscanner.com/agentic-coding-security)
- [The Complete Guide to Agentic Coding in 2026](https://www.teamday.ai/blog/complete-guide-agentic-coding-2026)
- [Anthropic 2026 Agentic Coding Trends Report](https://resources.anthropic.com/hubfs/2026%20Agentic%20Coding%20Trends%20Report.pdf)
- [Temporal.io Agentic Loop with Claude](https://docs.temporal.io/ai-cookbook/agentic-loop-tool-call-claude-python)
- [Sitepoint: Agentic Design Patterns 2026](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/)
