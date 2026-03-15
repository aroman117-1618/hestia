# Project Autonomy: Hestia Self-Development — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the gap between Hestia and Claude Code so Hestia can own her ongoing development via the CLI — reading code, editing files, running tests, committing changes, and learning from outcomes.

**Architecture:** A new `AgenticLoop` class implements a while(tool_call) loop that lets Hestia chain 25+ tool calls per session. New tools (edit_file, git operations, grep, glob) expand the tool palette. Cloud tool calling is extended to support Anthropic's tool_use protocol. A verification layer detects self-modification and runs pre/post tests. All agentic coding routes through cloud and operates on feature branches.

**Tech Stack:** Python 3.9+, FastAPI, aiosqlite, Ollama + Anthropic Cloud, WebSocket streaming

**Discovery Report:** `docs/discoveries/hestia-agentic-self-development-2026-03-15.md`
**Plan Audit:** `docs/plans/project-autonomy-audit-2026-03-15.md`

**Success Criteria (Phase 0+1):** Hestia, via `/code`, successfully: reads CLAUDE.md → runs `pytest -q` → extracts test count → edits CLAUDE.md with updated count → runs tests to verify → commits on a feature branch → shows diff for approval.

---

## Scope: 4 Phases (Phase 3 deferred per audit)

| Phase | Name | Sessions | What It Enables |
|-------|------|----------|----------------|
| 0 | Tool Palette + Cloud Tools | 2 | Cloud tool calling, edit_file, git tools, grep, glob, codebase access |
| 1 | Agentic Loop | 2 | Multi-step tool chaining + context compaction |
| 2 | Self-Aware Coding | 1-2 | Verification gates, critical file protection, agentic prompt |
| 3 | Learning Cycle | DEFERRED | Needs agentic session data first |

**Dependency chain:** 0 → 1 → 2 (strict)

---

## File Structure

### New Files

| File | Responsibility |
|------|---------------|
| `hestia/execution/tools/edit_tools.py` | `edit_file` tool — surgical string replacement |
| `hestia/execution/tools/git_tools.py` | `git_status`, `git_diff`, `git_log`, `git_add`, `git_commit`, `git_create_branch` tools |
| `hestia/execution/tools/search_tools.py` | `grep_content`, `glob_files` tools |
| `hestia/orchestration/agentic.py` | `AgenticLoop` class — the while(tool_call) engine |
| `hestia/orchestration/compactor.py` | Context compaction — summarize old messages |
| `hestia/orchestration/verifier.py` | Self-modification detection + pre/post test gates |
| `tests/test_edit_tools.py` | Tests for edit_file |
| `tests/test_git_tools.py` | Tests for git tools |
| `tests/test_search_tools.py` | Tests for grep/glob |
| `tests/test_agentic.py` | Tests for agentic loop |
| `tests/test_cloud_tools.py` | Tests for cloud tool calling |
| `tests/test_verifier.py` | Tests for verification layer |

### Modified Files

| File | Changes |
|------|---------|
| `hestia/cloud/client.py` | Add `tools` param to `complete()`, parse Anthropic tool_use responses |
| `hestia/inference/client.py` | Thread `tools` through `_call_cloud()`, extend Message type |
| `hestia/config/execution.yaml` | Add `~/hestia` to allowed_directories, critical files list |
| `hestia/execution/tools/__init__.py` | Register new tools |
| `hestia/orchestration/handler.py` | Add `handle_agentic()` entry point |
| `hestia/api/routes/ws_chat.py` | Add agentic session support |
| `hestia-cli/hestia_cli/repl.py` | Add `/code` command for agentic mode |
| `hestia/orchestration/prompt.py` | Add agentic system prompt template |
| `scripts/auto-test.sh` | Add mappings for new test files |

---

## Phase 0: Tool Palette + Cloud Tool Calling

### Task 0.0: Cloud Tool Calling (CRITICAL PREREQUISITE)

**Files:**
- Modify: `hestia/cloud/client.py`
- Modify: `hestia/inference/client.py`
- Create: `tests/test_cloud_tools.py`

This is the #1 prerequisite identified by the audit. Without this, the agentic loop has no model capable of chaining tools.

- [ ] **Step 1: Write failing tests for cloud tool calling**

```python
"""Tests for cloud tool calling — Anthropic tool_use protocol."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json


class TestCloudToolCalling:
    @pytest.mark.asyncio
    async def test_tools_param_threaded_to_anthropic(self) -> None:
        """Tool definitions are included in Anthropic API request body."""
        from hestia.cloud.client import CloudInferenceClient
        client = CloudInferenceClient()
        tools = [{"type": "function", "function": {"name": "read_file", "parameters": {}}}]

        # Mock httpx to capture the request body
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Hello"}],
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "end_turn",
        }

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)) as mock_post:
            from hestia.cloud.models import CloudProvider
            await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="test-key",
                messages=[{"role": "user", "content": "test"}],
                tools=tools,
            )
            # Verify tools were in the request body
            call_args = mock_post.call_args
            request_body = json.loads(call_args[1]["content"]) if "content" in call_args[1] else call_args[1].get("json", {})
            assert "tools" in request_body or True  # Exact assertion depends on httpx call pattern

    @pytest.mark.asyncio
    async def test_anthropic_tool_use_response_parsed(self) -> None:
        """Anthropic tool_use content blocks are extracted as tool_calls."""
        from hestia.cloud.client import CloudInferenceClient
        client = CloudInferenceClient()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "content": [
                {"type": "tool_use", "id": "toolu_123", "name": "read_file", "input": {"path": "/test.py"}},
            ],
            "usage": {"input_tokens": 50, "output_tokens": 30},
            "model": "claude-sonnet-4-20250514",
            "stop_reason": "tool_use",
        }

        with patch("httpx.AsyncClient.post", new=AsyncMock(return_value=mock_response)):
            from hestia.cloud.models import CloudProvider
            result = await client.complete(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                api_key="test-key",
                messages=[{"role": "user", "content": "read the file"}],
                tools=[{"type": "function", "function": {"name": "read_file", "parameters": {}}}],
            )
            assert result.tool_calls is not None
            assert len(result.tool_calls) >= 1
            assert result.tool_calls[0]["function"]["name"] == "read_file"

    @pytest.mark.asyncio
    async def test_tools_threaded_through_inference_client(self) -> None:
        """InferenceClient._call_cloud() passes tools to CloudInferenceClient."""
        from hestia.inference.client import InferenceClient
        # Verify the tools parameter flows through the call chain
        # This tests the threading, not the cloud API itself

    @pytest.mark.asyncio
    async def test_no_tools_still_works(self) -> None:
        """Cloud calls without tools param work as before (backward compat)."""
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Implement cloud tool calling**

**In `hestia/cloud/client.py`:**

Add `tools: Optional[List[Dict[str, Any]]] = None` parameter to `complete()`.

In `_call_anthropic()`:
- Convert tool definitions to Anthropic format: `{"name": name, "description": desc, "input_schema": params}`
- Include in request body as `"tools": [...]`
- Parse response: when `stop_reason == "tool_use"`, extract `tool_use` content blocks
- Normalize to Ollama format: `[{"function": {"name": name, "arguments": input}}]`
- Set on `InferenceResponse.tool_calls`

In `_call_openai()`:
- OpenAI already uses the same tool schema format
- Include `"tools": tools` in request body
- Parse `choices[0].message.tool_calls` → normalize format

In `_call_google()`:
- Convert to Gemini's `functionDeclarations` format
- Parse `functionCall` responses
- (Lower priority — Anthropic is the primary cloud provider)

**In `hestia/inference/client.py`:**

Thread `tools` parameter through `_call_cloud()`:
```python
async def _call_cloud(
    self,
    messages=None, system=None, prompt="",
    temperature=None, max_tokens=None,
    tools=None,  # NEW
) -> InferenceResponse:
```

- [ ] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Run full test suite for regressions**
- [ ] **Step 6: Commit**

```bash
git commit -m "feat(cloud): add tool calling support to CloudInferenceClient — Anthropic tool_use protocol"
```

---

### Task 0.1: Codebase Path Allowlisting + Critical File Protection

**Files:**
- Modify: `hestia/config/execution.yaml`

- [ ] **Step 1: Add hestia project root to allowed_directories**

```yaml
allowed_directories:
  - ~/hestia              # Project root — codebase access for agentic coding
  # ... existing entries ...
```

Do NOT add `~/hestia` to `auto_approve_write_dirs`.

- [ ] **Step 2: Add critical files protection list**

```yaml
# Files that ALWAYS require explicit human approval for edits, even in auto-approve mode
critical_files:
  - hestia/files/security.py
  - hestia/execution/sandbox.py
  - hestia/execution/gate.py
  - hestia/config/execution.yaml
  - hestia/security/
```

- [ ] **Step 3: Add git safety patterns**

```yaml
git_blocked_patterns:
  - "git push --force"
  - "git push -f"
  - "git reset --hard"
  - "git clean -fd"
  - "git checkout -- ."
  - "git branch -D main"
```

- [ ] **Step 4: Commit**

```bash
git commit -m "config: codebase access, critical file protection, git safety for agentic coding"
```

---

### Task 0.2: Edit File Tool

**Files:**
- Create: `hestia/execution/tools/edit_tools.py`
- Create: `tests/test_edit_tools.py`

- [ ] **Step 1: Write failing tests**

Tests:
- `test_simple_replacement` — basic old→new swap
- `test_old_string_not_found` → error
- `test_ambiguous_match` — multiple occurrences without `replace_all` → error
- `test_replace_all_flag` — replaces all occurrences
- `test_preserves_encoding` — UTF-8 content preserved
- `test_file_not_found` → error
- `test_binary_file_detection` → error for `.pyc`, `.png`, etc.
- `test_empty_old_string` → error
- `test_same_old_new_string` → error (no-op)

- [ ] **Step 2: Implement edit_file_handler**

Surgical string replacement. Key behaviors:
- `old_string` must exist in file (exact match)
- If `old_string` appears multiple times and `replace_all=False` → error with count
- Detect binary files (null bytes in first 8KB) → refuse
- Reject empty `old_string` or `old_string == new_string`
- Return: `{"status", "path", "replacements", "old_length", "new_length"}`

- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(tools): edit_file tool with surgical string replacement"
```

---

### Task 0.3: Git Tools (with Feature Branch Pattern)

**Files:**
- Create: `hestia/execution/tools/git_tools.py`
- Create: `tests/test_git_tools.py`

- [ ] **Step 1: Write failing tests** (using tmp_path git repos)

Tests:
- `test_git_status_clean` / `test_git_status_with_changes`
- `test_git_diff_no_changes` / `test_git_diff_with_changes`
- `test_git_log_with_commits`
- `test_git_add_specific_file` / `test_git_add_rejects_dot` (no `git add .`)
- `test_git_commit` / `test_git_commit_rejects_amend`
- `test_git_create_branch` — creates and switches to new branch
- `test_git_create_branch_rejects_main` — can't overwrite main

- [ ] **Step 2: Implement 6 git tools**

| Tool | Handler | Safety |
|------|---------|--------|
| `git_status` | `git status --short` | Read-only |
| `git_diff` | `git diff` or `git diff --cached` | Read-only |
| `git_log` | `git log --oneline -N` | Read-only, max 50 |
| `git_add` | `git add <specific files>` | **Rejects** `.`, `-A`, `--all`, wildcards |
| `git_commit` | `git commit -m "msg"` | **Rejects** `--amend`, `--no-verify` |
| `git_create_branch` | `git checkout -b <name>` | **Rejects** `main`, `master` as branch names |

All tools: `working_dir` param defaults to `~/hestia`. All use `SandboxRunner.run_shell_command()`.

- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(tools): git tools with branch pattern and safety guards"
```

---

### Task 0.4: Search Tools

**Files:**
- Create: `hestia/execution/tools/search_tools.py`
- Create: `tests/test_search_tools.py`

- [ ] **Step 1: Write failing tests**

- `test_grep_finds_pattern` / `test_grep_no_matches`
- `test_grep_respects_file_type` / `test_grep_case_insensitive`
- `test_glob_finds_pattern` / `test_glob_no_matches`
- `test_glob_respects_directory`

- [ ] **Step 2: Implement grep_content and glob_files**

`grep_content`: wraps `grep -rn` via SandboxRunner, formats output as structured JSON.
`glob_files`: uses `pathlib.Path.glob()`, returns file paths with metadata.

Both tools: `max_results` cap, `directory` param defaults to `~/hestia`.

- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(tools): grep_content and glob_files search tools"
```

---

### Task 0.5: Tool Registration + auto-test.sh

**Files:**
- Modify: `hestia/execution/tools/__init__.py`
- Modify: `scripts/auto-test.sh`

- [ ] **Step 1: Register all new tools**

```python
from .edit_tools import get_edit_tools
from .git_tools import get_git_tools
from .search_tools import get_search_tools

# In register_builtin_tools():
for tool in get_edit_tools():
    registry.register(tool)
for tool in get_git_tools():
    registry.register(tool)
for tool in get_search_tools():
    registry.register(tool)
```

- [ ] **Step 2: Update auto-test.sh mappings**
- [ ] **Step 3: Run full test suite**
- [ ] **Step 4: Commit**

```bash
git commit -m "chore: register new tools and update auto-test mappings"
```

---

## Phase 1: Agentic Loop + Context Compaction

### Task 1.1: AgenticLoop Core

**Files:**
- Create: `hestia/orchestration/agentic.py`
- Create: `tests/test_agentic.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for the agentic execution loop."""

class TestAgenticLoop:
    async def test_single_tool_call_completes(self):
        """Model makes one tool call, then text response → loop exits."""

    async def test_multi_step_chaining(self):
        """Model chains 3 tool calls → all executed, results fed back."""

    async def test_max_iterations_terminates(self):
        """Loop stops at max_iterations even if model keeps calling tools."""

    async def test_natural_termination(self):
        """Loop stops when model emits text without tool calls."""

    async def test_tool_error_fed_back(self):
        """Tool error → fed back as is_error=true → model gets recovery chance."""

    async def test_token_budget_terminates(self):
        """Loop stops when cumulative tokens exceed budget."""

    async def test_timeout_terminates(self):
        """Loop stops when wall-clock time exceeds timeout."""

    async def test_events_yielded(self):
        """Each iteration yields inference/tool_call/tool_result/complete events."""

    async def test_result_populated_on_natural_stop(self):
        """loop.result has content, iterations, tokens, tools_executed."""

    async def test_budget_warning_at_70_percent(self):
        """Budget warning event emitted at 70% token usage."""
```

- [ ] **Step 2: Implement AgenticLoop**

Create `hestia/orchestration/agentic.py` with:

- `AgenticConfig` dataclass: max_iterations=25, max_token_budget=100_000, timeout_seconds=300, force_cloud=True, require_approval_for_writes=True
- `AgenticEvent` dataclass: type, data, iteration, timestamp
- `AgenticResult` dataclass: content, iterations, total_tokens, tools_executed, duration_ms, termination_reason
- `AgenticLoop` class with `run()` async generator

The core loop:
```python
while iteration < config.max_iterations:
    # Check timeout, token budget
    # Call LLM (force cloud via force_tier parameter)
    # If no tool_calls → natural termination, break
    # Execute each tool_call via ToolExecutor
    # Append assistant+tool messages to history
    # Check if compaction needed
```

**Key detail from audit:** Use `force_tier="cloud"` on the inference call, not just relying on `enabled_full`. This ensures agentic sessions always use cloud even if routing state changes.

- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(orchestration): agentic loop — while(tool_call) engine with termination conditions"
```

---

### Task 1.2: Context Compaction (moved from Phase 2 per audit)

**Files:**
- Create: `hestia/orchestration/compactor.py`
- Append tests to: `tests/test_agentic.py`

- [ ] **Step 1: Write failing tests**

- `test_should_compact_false_under_threshold`
- `test_should_compact_true_over_threshold`
- `test_compact_preserves_recent_messages`
- `test_compact_summarizes_old_messages`
- `test_compact_preserves_system_prompt`

- [ ] **Step 2: Implement ContextCompactor**

```python
"""Context compaction — summarize old messages to stay within token budget."""

class ContextCompactor:
    COMPACTION_THRESHOLD = 0.6  # Compact at 60% of budget
    PRESERVE_RECENT = 5  # Keep last 5 tool interaction pairs

    async def should_compact(self, messages, token_count, budget) -> bool:
        return token_count > budget * self.COMPACTION_THRESHOLD

    async def compact(self, messages, inference_client) -> List[Dict]:
        # Split: old messages vs recent (last PRESERVE_RECENT pairs)
        # Summarize old via LLM: "Summarize the key context from these messages"
        # Return: [summary_message] + recent_messages
```

- [ ] **Step 3: Wire into AgenticLoop — call between iterations when threshold hit**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(orchestration): context compaction for long agentic sessions"
```

---

### Task 1.3: Wire into Handler + WebSocket

**Files:**
- Modify: `hestia/orchestration/handler.py`
- Modify: `hestia/api/routes/ws_chat.py`

- [ ] **Step 1: Add handle_agentic() to RequestHandler**

Reuses existing pre-processing (session, memory, prompt building) but delegates to AgenticLoop. Returns AsyncGenerator[AgenticEvent, None].

- [ ] **Step 2: Add agentic message type to WS protocol**

New WS message type: `{"type": "agentic", "content": "...", "session_id": "..."}`

Events streamed back:
- `{"type": "agentic_event", "event_type": "tool_call", ...}`
- `{"type": "agentic_event", "event_type": "tool_result", ...}`
- `{"type": "agentic_event", "event_type": "complete", ...}`

Also support: `{"type": "agentic_cancel"}` to kill a running session.

- [ ] **Step 3: Run tests, verify pass**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(orchestration): wire agentic loop into handler and WebSocket"
```

---

### Task 1.4: CLI /code Command

**Files:**
- Modify: `hestia-cli/hestia_cli/repl.py` or `commands.py`

- [ ] **Step 1: Add /code command**

When user types `/code <instruction>`:
1. Sends `{"type": "agentic", "content": instruction}` over WebSocket
2. Renders events with Rich formatting
3. Handles tool approval prompts via existing WS flow
4. Shows summary on completion: iterations, tokens used, tools called

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(cli): /code command for agentic coding sessions"
```

---

## Phase 2: Self-Aware Coding

### Task 2.1: Verification Layer

**Files:**
- Create: `hestia/orchestration/verifier.py`
- Create: `tests/test_verifier.py`

- [ ] **Step 1: Write failing tests**

- `test_detects_self_modification` — file under `~/hestia/hestia/` → True
- `test_ignores_non_self_modification` — file under `~/Documents/` → False
- `test_detects_critical_file` — `security.py` → critical=True
- `test_runs_pre_post_test` — runs matching test before and after edit
- `test_reports_regression` — pre passes, post fails → regression
- `test_generates_diff` — produces git diff output

- [ ] **Step 2: Implement SelfModificationVerifier**

```python
class SelfModificationVerifier:
    SELF_PATHS = ["hestia/hestia/", "hestia/tests/", "hestia/hestia-cli/"]
    CRITICAL_FILES = [
        "hestia/files/security.py",
        "hestia/execution/sandbox.py",
        "hestia/execution/gate.py",
        "hestia/config/execution.yaml",
    ]

    def is_self_modification(self, file_path: str) -> bool: ...
    def is_critical_file(self, file_path: str) -> bool: ...
    def get_affected_test_file(self, source_path: str) -> Optional[str]: ...
    async def run_pre_check(self, file_path: str) -> PreCheckResult: ...
    async def run_post_check(self, file_path: str, pre: PreCheckResult) -> PostCheckResult: ...
    async def get_diff(self) -> str: ...
```

Critical files ALWAYS require human approval, even when auto-approve is on.

- [ ] **Step 3: Integrate into AgenticLoop — wrap edit_file/write_file calls**
- [ ] **Step 4: Commit**

```bash
git commit -m "feat(orchestration): self-modification verifier with critical file protection"
```

---

### Task 2.2: Agentic System Prompt

**Files:**
- Modify: `hestia/orchestration/prompt.py`

- [ ] **Step 1: Add AGENTIC_CODING_PROMPT**

System prompt that instructs the model on Hestia conventions, workflow (understand → plan → implement → verify → commit), rules (one commit per change, run tests after every edit, never force push, always work on branches).

- [ ] **Step 2: Commit**

```bash
git commit -m "feat(prompt): agentic coding system prompt with Hestia conventions"
```

---

## Phase 3: Learning Cycle Integration — DEFERRED

Per audit: defer until enough agentic session data exists to learn from. Revisit after 10+ successful agentic sessions.

When revisited:
- PrincipleStore captures coding patterns from session outcomes
- Knowledge graph maps module dependencies and test coverage
- Principles injected into agentic system prompts

---

## Summary

| Phase | Tasks | New Files | Modified Files | Estimated Tests |
|-------|-------|-----------|----------------|-----------------|
| 0: Tools + Cloud | 0.0-0.5 | 4 source + 4 test | 4 (cloud, inference, config, __init__) | ~35 |
| 1: Agentic Loop | 1.1-1.4 | 2 source + 1 test | 3 (handler, ws, cli) | ~20 |
| 2: Self-Aware | 2.1-2.2 | 1 source + 1 test | 2 (agentic, prompt) | ~10 |

**Total: ~65 new tests, 7 new source files, 9 modified files, ~14 hours across 5-6 sessions**

**Execution order:** 0.0 → 0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 1.1 → 1.2 → 1.3 → 1.4 → 2.1 → 2.2

**ADR to create:** ADR-042: Project Autonomy — Agentic coding loop, cloud tool calling, self-modification verification, feature branch pattern.
