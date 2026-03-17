# Plan: Claude CLI Subscription Fallback

**Status**: APPROVED — building Phase 1 + Phase 2. Phase 3 deferred to roadmap.
**Sprint**: 14 (post-Sprint 13 landmine cleanup)
**Estimated effort**: ~1.5 hours (Phase 1 + Phase 2)

## Goal

Enable Hestia to fall back from the Anthropic API (prepaid credits) to the
Claude Code CLI (Max subscription) when the API returns billing or rate-limit
errors. Surface which inference path was used in the iOS/macOS UI.

## Architecture

```
Inference Request
       |
       v
  force_cloud?  --no-->  Normal routing (local primary/coding/cloud)
       |yes
       v
  _call_cloud()
       |
       v
  _call_anthropic()  --success-->  return (source="api")
       |
       | HTTP 400 (billing) or 429 (rate limit)
       v
  CLI available?  --no-->  raise CloudInferenceError
       |yes
       v
  _call_claude_cli()  --success-->  return (source="subscription")
       |
       | failure
       v
  raise CloudInferenceError
```

The fallback is automatic and transparent. No new CloudProvider enum value,
no database config, no API key management. The CLI uses OAuth/subscription auth
natively. We just unset ANTHROPIC_API_KEY from the subprocess env.

## Phase 1: CLI Inference Backend

**Files to modify:**
- `hestia/inference/client.py` -- add `_call_claude_cli()`, wire fallback in `_call_cloud()`
- `hestia/inference/models.py` -- add `inference_source` field to `InferenceResponse`

### 1.1 Add `inference_source` to InferenceResponse

Add `inference_source: str = "local"` field to `InferenceResponse` dataclass.
Values: `"local"`, `"api"`, `"subscription"`.

Set by:
- `_call_local_with_retries()` -> `"local"` (default, no change needed)
- `_call_cloud()` -> `"api"` (existing path)
- `_call_claude_cli()` -> `"subscription"` (new path)

### 1.2 Implement `_call_claude_cli()`

Signature:
- messages: List[Message]
- system: Optional[str]
- temperature: Optional[float]
- max_tokens: Optional[int]
- model: Optional[str]
- tool_instructions: Optional[str]

Implementation:
- Build a single prompt string from the messages list (last user message as
  primary, prior messages as context)
- If system or tool_instructions provided, pass via --append-system-prompt
- Run: env -u ANTHROPIC_API_KEY claude -p --output-format json --tools "" --model {model}
- Use asyncio.create_subprocess_exec() for non-blocking execution
- Parse JSON response: extract result, usage.input_tokens, usage.output_tokens,
  duration_api_ms, total_cost_usd
- Return InferenceResponse(content=result, inference_source="subscription", ...)
- Timeout: 120s (agentic tasks can be slow)

Key details:
- --tools "" disables Claude Code's built-in tools (we handle tools ourselves)
- env -u ANTHROPIC_API_KEY prevents the subprocess from using the API key
- --model sonnet to match API provider model (configurable)

### 1.3 Wire fallback in `_call_cloud()`

After the existing except block in _call_cloud(), before re-raising, check if:
1. The error is a billing/rate-limit error (HTTP 400 billing message, or 429)
2. The claude binary exists on PATH (cached at init)
3. A class-level flag self._cli_fallback_enabled is True (default True)

If all conditions met, log a warning and call _call_claude_cli() with the
same parameters. If CLI also fails, raise the original cloud error.

### 1.4 Health check for CLI availability

Static method _cli_available() that calls shutil.which("claude").
Called once at init, cached. Also exposed via the cloud health endpoint so the
UI can show CLI fallback status.

### Tests (Phase 1)

- [ ] test_call_claude_cli_basic -- mock subprocess, verify JSON parsing
- [ ] test_call_claude_cli_strips_api_key -- verify ANTHROPIC_API_KEY not in subprocess env
- [ ] test_cloud_fallback_on_billing_error -- mock API 400, verify CLI called
- [ ] test_cloud_no_fallback_on_auth_error -- mock API 401, verify CLI NOT called
- [ ] test_cloud_no_fallback_when_cli_missing -- mock shutil.which returning None
- [ ] test_inference_source_field -- verify field populates correctly for each path

---

## Phase 2: Tool Calling via Text Extraction (2A)

**Files to modify:**
- `hestia/inference/client.py` -- extend _call_claude_cli() to embed tool schemas
- `hestia/orchestration/handler.py` -- pass tool schemas to CLI path, parse text tool calls

### 2.1 Embed tool schemas in system prompt

When tool_instructions is provided (from the agentic handler), append to the
system prompt passed to claude -p. Format:

"You have access to the following tools. To call a tool, respond with a JSON block:
{"tool_call": {"name": "tool_name", "arguments": {"arg1": "value1"}}}

Available tools:
[tool schema list -- reuse existing tool_instructions format from PromptBuilder]"

This reuses the same prompt format Hestia already uses for local Ollama models.

### 2.2 Parse tool calls from CLI response

The CLI returns the model's full text response in the result field. Use the
existing _looks_like_tool_call() + _extract_tool_calls_from_text() pipeline
from the handler to detect and parse tool calls from the text.

In _call_claude_cli():
- After getting response text, scan for tool call patterns
- If found, populate InferenceResponse.tool_calls with extracted calls
- The agentic handler already knows how to process these

### 2.3 Thread tool_defs through the fallback path

In handle_agentic(), when calling inference.chat(force_cloud=True, tools=tool_defs):
- The existing _call_cloud() path passes tools to the Anthropic API natively
- The CLI fallback path converts tools to text-based tool_instructions
- Add a _tool_defs_to_instructions(tool_defs) helper that formats the
  OpenAI-compatible tool schemas into the text prompt format

### Tests (Phase 2)

- [ ] test_cli_tool_instructions_embedded -- verify tool schemas in system prompt
- [ ] test_cli_tool_call_extraction -- mock CLI response with tool call JSON
- [ ] test_agentic_loop_via_cli -- full mock of agentic loop using CLI path

---

## Phase 3: UI -- Inference Source Indicator (DEFERRED to roadmap)

Blend into existing UI enhancement roadmap. Scope:
- Backend: thread inference_source through chat/stream/agentic response metrics
- iOS/macOS: subtle badge on chat bubbles (api/subscription/local)
- Settings: CLI fallback status row in Cloud Settings

---

## Execution Order

1. Phase 1 -- CLI inference backend + fallback wiring
2. Phase 2 -- tool calling via text extraction
3. Phase 3 -- deferred to roadmap

## Decisions (confirmed)

1. Default model for CLI path: **sonnet** (cheaper, faster). Override via inference.yaml.
2. CLI fallback for non-agentic chat: **Yes, all cloud paths** get the fallback.
3. Cost tracking: **Yes**, store in cloud usage table with provider="claude_cli".
4. Mac Mini deployment: Add claude CLI install + auth to deploy checklist.

## Risks

- CLI latency (~5-6s overhead per call): Acceptable for agentic; log timing
- CLI not on Mac Mini: No fallback on prod; add to deploy script + health check
- CLI output format changes: Pin to --output-format json; add schema validation
- Subscription rate limits differ from API: Monitor; add backoff if needed
- ANTHROPIC_API_KEY env leaks to subprocess: Explicitly strip in subprocess call
