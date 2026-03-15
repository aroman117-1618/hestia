# Plan Audit: Sprint 13 — Hestia Evolution
**Date:** 2026-03-15
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
Sprint 13 evolves Hestia across 4 workstreams: completing the knowledge graph (episodic nodes, temporal queries), trimming iOS to Chat+Voice+Settings while filling macOS gaps, importing Claude conversation history (78 convos, 796 msgs + 563 thinking blocks), and building agentic self-development tools (iterative tool loop, code/git tools, verification layer). Estimated 6-8 sessions.

## Scale Assessment

| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None — designed for Andrew | N/A |
| Family (2-5) | Mostly | Import pipeline uses file paths (not multi-tenant uploads). `user_id` scoping exists on memory but episodic nodes don't scope by user. Git tools assume single repo. | Medium — add user_id to episodic_nodes, convert file paths to upload endpoint |
| Community | No | Agentic coding shares one sandbox. Import needs per-user isolation. Knowledge graph is global. | High — would need tenant isolation |

**Assessment:** Single-user focus is correct for current stage. The episodic_nodes table should include `user_id` column now (cheap) to avoid migration later.

## Front-Line Engineering Review

**Feasibility:** High. All 4 workstreams build on existing infrastructure. The explorer confirmed: Fact model has temporal fields, source_dedup works, ToolExecutor supports batch, WS streaming has tool approval flow.

**Hidden prerequisites:**
1. **MemorySource enum needs `CLAUDE_HISTORY` value** — enum is extensible but requires code change before import works
2. **JSON1 SQLite extension** — `json_each()` for episodic entity lookup needs runtime validation. Most macOS SQLite ships with JSON1, but should check.
3. **ChromaDB collection namespace** — all memory shares one collection (`hestia_memory`). Imported chunks will intermingle with conversation memory. Need metadata filtering to distinguish sources.
4. **`store()` method signature** — MemoryManager's `store()` accepts `ConversationChunk` objects. The import pipeline needs to convert `ImportChunk` → `ConversationChunk` before storage. This adapter is not in the plan.

**Effort realism:**
- WS1 (knowledge graph): 1-2 sessions — **realistic**
- WS2 (app trimming): 1-2 sessions — **optimistic for macOS gaps**. Memory review + neural net wiring + proactive settings is 3 distinct UI features. More like 2 sessions.
- WS3 (Claude import): 1-2 sessions — **realistic** if parser + pipeline are clean
- WS4 (agentic): 2-3 sessions — **optimistic**. The iterative tool loop alone is a significant handler refactor. Context compaction adds another session. Suggest 3-4 sessions.

**Testing gaps:**
- No integration test for the full import pipeline (parse → dedup → store → embed → extract facts)
- Agentic loop termination conditions need fuzzing (what if model returns tool_calls AND text?)
- Self-modification verification: no test for the "Hestia modifies her own test file" scenario

## Architecture Review

**Fit:** Good. All workstreams follow the manager pattern. New tools register via existing ToolRegistry. New endpoints follow existing route patterns.

**Data model concerns:**
1. **EpisodicNode entity_ids as JSON array in SQLite** — works but `json_each()` queries can't use indexes. For <10K episodes this is fine. Add a junction table (`episodic_entity_links`) if scale becomes a concern.
2. **ImportChunk vs ConversationChunk** — the plan introduces `ImportChunk` as a new dataclass but the memory pipeline expects `ConversationChunk`. Need an explicit adapter/conversion step.
3. **Thinking blocks at 348K chars** — these will create ~175 INSIGHT chunks. Combined with conversation chunks and summaries, expect ~300-400 chunks from the Claude import. ChromaDB handles this easily.

**Integration risk:**
- **handler.py is the riskiest file** — WS1 (auto-extraction hook) and WS4 (agentic loop) both modify it. Must be sequenced carefully.
- **auto-test.sh mapping** — new modules need entries added, or the hook won't auto-run tests.

## Product Review

**User value:** HIGH. Each workstream delivers tangible value:
- WS1: "When did we discuss X?" queries
- WS2: Focused iOS experience + complete macOS
- WS3: Hestia knows Andrew's conversation history from Claude
- WS4: Hestia can fix her own bugs

**Scope:** Right-sized for 4 workstreams, but WS2 and WS4 are each borderline too large. WS2 could be split (trim iOS = 1 task, fill macOS = separate sprint). WS4 Phase 2 (verification + compaction) could be deferred.

**Opportunity cost:** While building Sprint 13, we're NOT building:
- Sprint 11B MetaMonitor (deferred — correct, needs data)
- Google Workspace integration (approved, low effort, independent)
- OpenAI history import (deferred — correct, same pattern later)
- Bright Data MCP (1-hour setup, independent)

## UX Review

**iOS trimming:**
- Removing Command Center, Explorer, Wiki from iOS tabs is clean. Settings stays comprehensive.
- **Gap:** No migration UX — users who relied on iOS Command Center get no redirect or explanation. Add a "Use macOS for full features" note in About/Settings.
- **Voice tab** is iOS's differentiator. Make sure it's prominent (tab position 2, not buried).

**macOS memory review:**
- Empty state: What does the memory review view show when there are 0 pending chunks? Need a "No pending reviews" placeholder.
- Neural Net rendering: Existing `MacNeuralNetViewModel` may need SceneKit permissions on macOS (no TCC prompt needed, but sandbox entitlements should be checked).

## Infrastructure Review

**Deployment impact:**
- Database migration: New `episodic_nodes` table auto-creates on init (existing pattern). No manual migration needed.
- New Python files: `hestia/memory/importers/`, `hestia/execution/tools/code_tools.py`, `hestia/execution/tools/git_tools.py`, `hestia/execution/verification.py`. All standard imports.
- Config change: `execution.yaml` allowlist expansion (`~/hestia`). This is the highest-risk change — opens source code to file tools.

**New dependencies:** None. All workstreams use existing libraries (SQLite, ChromaDB, asyncio, subprocess).

**Rollback strategy:**
- WS1-3: Clean rollback via git revert. No schema changes that break existing data.
- WS4: Allowlist expansion in execution.yaml is the sticky change. If agentic coding causes issues, revert the config line.

**Resource impact:**
- Import: ~400 ChromaDB embeddings (negligible, <50MB)
- Episodic nodes: SQLite table, <1MB
- Agentic sessions: Cloud API cost (~$0.30-0.50 per session)
- Memory: No significant increase on M1

## Executive Verdicts

### CISO: APPROVE WITH CONDITIONS
The agentic coding workstream (WS4) expands the attack surface by adding `~/hestia` to the sandbox allowlist and introducing git tools. The defense-in-depth model is sound (5 layers), but:
- **Condition 1:** `~/hestia/hestia/security/` must be EXCLUDED from edit_file allowlist. Security module is never self-modifiable.
- **Condition 2:** git_commit must include a `[hestia-auto]` prefix in commit messages so human reviewer can filter automated changes.
- **Condition 3:** Import pipeline must NOT store raw API keys or tokens found in Claude conversation text. Add a credential-stripping preprocessor.

### CTO: APPROVE WITH CONDITIONS
Architecture is solid and builds on existing patterns. Concerns:
- **Condition 1:** Add `ImportChunk → ConversationChunk` adapter explicitly in the plan. The current gap between the two types will cause runtime errors.
- **Condition 2:** WS4 `handle_agentic()` must be a NEW method, not a modification of existing `handle()`. The current handler serves all production chat — don't risk regressions.
- **Condition 3:** Add `user_id` column to `episodic_nodes` table from the start.

### CPO: APPROVE
Priority ordering is correct. WS3 (import) is the highest-value workstream — it directly feeds Gate 2 for MetaMonitor. WS4 is high-value but higher-risk; the phased approach (0→1→2) with human gates is appropriate. iOS trimming is overdue — maintaining feature parity across both apps isn't sustainable at 6hrs/week.

## Final Critiques

### 1. Most Likely Failure
**The import pipeline produces low-quality chunks that pollute memory search.** If 400 chunks of varying quality enter ChromaDB, semantic search may return irrelevant imported content over fresh conversation context.

**Mitigation:** Tag all imported chunks with `source=claude_history` and add a relevance penalty (0.9x score multiplier) for imported chunks in memory search. This ensures fresh conversation memory always ranks higher while imported history remains findable.

### 2. Critical Assumption
**That the iterative tool loop (WS4) will work reliably with Anthropic's API.** The plan assumes cloud models will chain 10+ tool calls correctly. If the model hallucinates tool names, returns malformed arguments, or fails to terminate, the loop becomes a cost sink.

**Validation:** Before building the full loop, run a proof-of-concept: send a multi-tool prompt to Anthropic API with Hestia's tool definitions and verify the model chains read→edit→verify correctly. This takes 30 minutes and de-risks WS4 entirely.

### 3. Half-Time Cut List
If we had half the time (3-4 sessions):
1. **KEEP WS3** (Claude import) — highest user value, feeds Gate 2
2. **KEEP WS4 Phase 0** (tool foundation) — independent value, enables future work
3. **CUT WS1** (knowledge graph) — nice-to-have, episodic nodes can come later
4. **CUT WS2** (app trimming) — iOS works fine today, macOS gaps aren't blocking
5. **CUT WS4 Phases 1-2** (agentic loop + verification) — defer to Sprint 14

## Conditions for Approval

1. **CRITICAL:** Add `ImportChunk → ConversationChunk` adapter to WS3 parser
2. **CRITICAL:** Exclude `hestia/security/` from edit_file allowlist in WS4
3. **CRITICAL:** `handle_agentic()` is a new method, not a modification of `handle()`
4. **HIGH:** Add `user_id` column to `episodic_nodes` table
5. **HIGH:** Add `[hestia-auto]` prefix to automated git commits
6. **HIGH:** Add credential-stripping step to import preprocessor
7. **HIGH:** Run WS4 proof-of-concept (multi-tool API call) before building the full loop
8. **MEDIUM:** Add relevance penalty for imported chunks in memory search
9. **MEDIUM:** Add `MemorySource.CLAUDE_HISTORY` to enum before import
10. **MEDIUM:** Validate JSON1 extension availability at database init
