# CLI UX Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform the Hestia CLI from a functional chat wrapper into a coding-first power tool by fixing 2 broken paths, adding 3 missing feedback mechanisms, and introducing 3 differentiation/polish features.

**Architecture:** 8 changes across 4 phases (A→D). Phase A is a hotfix for blocking bugs (raw JSON, slow synthesis). Phase B adds UX feedback (tool status, model visibility, visual separator). Phase C introduces differentiation (insight callouts, tool insights). Phase D is polish (command palette, interactive config, /tools browser). All changes are additive — no breaking changes, no migrations.

**Tech Stack:** Python 3.12, FastAPI WebSocket, Rich (CLI rendering), prompt_toolkit (REPL), YAML config.

---

## Phase A: Hotfix (Ship Immediately)

### Task 1: Fix `_looks_like_tool_call()` to detect `"name":` JSON format

The model sometimes outputs tool calls as `{"name": "create_note", "arguments": {...}}` — a JSON format that Pattern D (brute-force `json.loads`) catches during execution, but `_looks_like_tool_call()` misses during the "should we show this to the user?" check. This means raw JSON leaks to the user when tool execution fails or is skipped.

**Files:**
- Modify: `hestia/orchestration/handler.py:1687-1713` (`_looks_like_tool_call()`)
- Test: `tests/test_handler_streaming.py` (extend `TestTextPatternToolDetection`)

**Step 1: Write the failing test**

Add to `TestTextPatternToolDetection` in `tests/test_handler_streaming.py`:

```python
def test_looks_like_tool_call_detects_name_json_format(self, handler):
    """_looks_like_tool_call catches {"name": "...", "arguments": {...}} format."""
    content = '{"name": "create_note", "arguments": {"title": "test", "content": "hello"}}'

    mock_registry = MagicMock()
    mock_registry.has_tool.return_value = False  # Not needed for JSON detection

    with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
        assert handler._looks_like_tool_call(content) is True

def test_looks_like_tool_call_detects_name_json_embedded(self, handler):
    """_looks_like_tool_call catches {"name": ...} embedded in surrounding text."""
    content = 'Sure, I\'ll create that note.\n{"name": "create_note", "arguments": {"title": "test"}}'

    mock_registry = MagicMock()
    mock_registry.has_tool.return_value = False

    with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
        assert handler._looks_like_tool_call(content) is True
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_handler_streaming.py::TestTextPatternToolDetection::test_looks_like_tool_call_detects_name_json_format tests/test_handler_streaming.py::TestTextPatternToolDetection::test_looks_like_tool_call_detects_name_json_embedded -v`
Expected: FAIL — both tests should fail because `_looks_like_tool_call()` only checks for `"tool_call"` and `"tool":` substrings, not `"name":`.

**Step 3: Write minimal implementation**

In `hestia/orchestration/handler.py`, update `_looks_like_tool_call()` (line 1687):

```python
def _looks_like_tool_call(self, content: str) -> bool:
    """
    Check if content looks like a raw tool_call JSON that shouldn't be shown to user.

    Also detects function-call syntax (e.g., ``read_note("hestia")``) when the
    function name matches a registered tool.
    """
    import json
    import re

    # Quick substring check for JSON-style tool calls
    if '"tool_call"' in content or '"tool":' in content or '"name":' in content:
        try:
            data = json.loads(content.strip())
            if "tool_call" in data or "tool" in data:
                return True
            # Detect {"name": "...", "arguments": {...}} format
            if "name" in data and "arguments" in data:
                return True
        except json.JSONDecodeError:
            if '{"tool_call"' in content or '{"tool":' in content:
                return True
            # Also catch embedded {"name": "...", "arguments": ...} patterns
            if '{"name":' in content and '"arguments"' in content:
                return True

    # Check for function-call syntax with known tool names
    registry = get_tool_registry()
    for func_match in re.finditer(r'(\w+)\([^)]*\)', content):
        if registry.has_tool(func_match.group(1)):
            return True

    return False
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_handler_streaming.py::TestTextPatternToolDetection -v`
Expected: All 7 tests PASS (5 existing + 2 new).

**Step 5: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add hestia/orchestration/handler.py tests/test_handler_streaming.py
git commit -m "fix: detect {\"name\": ...} JSON format in _looks_like_tool_call()"
```

---

### Task 2: Add `force_tier` to `chat_stream()` + route synthesis to cloud when hardware adapted

When the Mac Mini is under load (GPU shared with Claude Code), local inference runs at ~0.6 tok/s, causing 4-minute synthesis times. The `_stream_tool_result_with_personality()` method should use cloud routing when hardware adaptation has been applied (i.e., the router detected slow local inference).

**Files:**
- Modify: `hestia/inference/client.py:856-963` (`chat_stream()`)
- Modify: `hestia/orchestration/handler.py:1769+` (`_stream_tool_result_with_personality()`)
- Test: `tests/test_handler_streaming.py` (extend `TestStreamingSynthesis`)

**Step 1: Write the failing tests**

Add to `TestStreamingSynthesis` in `tests/test_handler_streaming.py`:

```python
@pytest.mark.asyncio
async def test_streaming_synthesis_uses_force_cloud_when_adapted(self, handler):
    """When hardware_adapted, synthesis passes force_tier='cloud' to chat_stream."""
    # Setup mock router with adaptation applied
    mock_router = MagicMock()
    mock_router._adaptation_applied = True
    handler._inference_client.router = mock_router

    async def mock_stream(**kwargs):
        yield "Cloud response"
        yield InferenceResponse(
            content="Cloud response", model="claude-3-haiku",
            tokens_in=10, tokens_out=5, duration_ms=500,
        )

    handler._inference_client.chat_stream = MagicMock(side_effect=mock_stream)
    handler.MAX_SYNTHESIS_CHARS = 4000

    request = make_request("read my note")
    messages = [Message(role="user", content="read my note")]

    tokens = []
    async for token in handler._stream_tool_result_with_personality(
        "Note content here", request, messages, 0.7, 1024
    ):
        tokens.append(token)

    assert "Cloud response" in tokens
    # Verify force_tier was passed
    call_kwargs = handler._inference_client.chat_stream.call_args[1]
    assert call_kwargs.get("force_tier") == "cloud"

@pytest.mark.asyncio
async def test_streaming_synthesis_no_force_when_not_adapted(self, handler):
    """When hardware NOT adapted, no force_tier is passed."""
    mock_router = MagicMock()
    mock_router._adaptation_applied = False
    handler._inference_client.router = mock_router

    async def mock_stream(**kwargs):
        yield "Local response"
        yield InferenceResponse(
            content="Local response", model="qwen2.5:7b",
            tokens_in=10, tokens_out=5, duration_ms=500,
        )

    handler._inference_client.chat_stream = MagicMock(side_effect=mock_stream)
    handler.MAX_SYNTHESIS_CHARS = 4000

    request = make_request("read my note")
    messages = [Message(role="user", content="read my note")]

    tokens = []
    async for token in handler._stream_tool_result_with_personality(
        "Note content here", request, messages, 0.7, 1024
    ):
        tokens.append(token)

    assert "Local response" in tokens
    # Verify force_tier was NOT passed (or is None)
    call_kwargs = handler._inference_client.chat_stream.call_args[1]
    assert call_kwargs.get("force_tier") is None
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_handler_streaming.py::TestStreamingSynthesis::test_streaming_synthesis_uses_force_cloud_when_adapted tests/test_handler_streaming.py::TestStreamingSynthesis::test_streaming_synthesis_no_force_when_not_adapted -v`
Expected: FAIL — `chat_stream()` doesn't accept `force_tier` yet.

**Step 3: Add `force_tier` parameter to `chat_stream()` in `hestia/inference/client.py`**

At line 856, update the signature:

```python
async def chat_stream(
    self,
    messages: List[Message],
    system: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    force_tier: Optional[str] = None,
) -> AsyncGenerator[Union[str, InferenceResponse], None]:
```

At line 892-896, add force_tier routing override BEFORE the existing `self.router.route()` call:

```python
    # Force-tier override (e.g., for synthesis when hardware is adapted)
    if force_tier == "cloud" and self.router.cloud_routing.state != "disabled":
        try:
            response = await self._call_cloud(
                messages=messages,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            self.router.record_success(ModelTier.CLOUD)
            if response.content:
                yield response.content
            yield response
            return
        except Exception:
            self.logger.warning(
                "Force-tier cloud failed, falling back to normal routing",
                component=LogComponent.INFERENCE,
            )
            # Fall through to normal routing

    # Determine routing (same logic as _call_with_routing but we need the decision)
    routing = self.router.route(
        prompt=messages[-1].content if messages else "",
        token_count=token_count,
    )
```

**Step 4: Update `_stream_tool_result_with_personality()` in `hestia/orchestration/handler.py`**

Update the method to check hardware adaptation and pass `force_tier`:

```python
async def _stream_tool_result_with_personality(
    self,
    tool_result: str,
    request: Request,
    original_messages: list,
    temperature: float,
    max_tokens: int,
) -> AsyncGenerator[str, None]:
    """Stream synthesis of tool results through the LLM with personality.

    Uses chat_stream() to avoid wall-clock timeout on slow hardware.
    When hardware adaptation has been applied (model was swapped due to slow
    tok/s), routes synthesis to cloud for faster response.
    """
    display_result = tool_result
    if len(tool_result) > self.MAX_SYNTHESIS_CHARS:
        display_result = (
            tool_result[:self.MAX_SYNTHESIS_CHARS]
            + f"\n\n[... {len(tool_result) - self.MAX_SYNTHESIS_CHARS} chars truncated]"
        )

    follow_up_messages = original_messages.copy()
    follow_up_messages.append(
        Message(role="assistant", content=f"[Tool output:\n{display_result}]")
    )
    follow_up_messages.append(
        Message(role="user", content="Now respond to my original request based on that data.")
    )

    # Route synthesis to cloud when hardware is adapted (slow local inference)
    force_tier = None
    try:
        if self.inference_client.router._adaptation_applied:
            force_tier = "cloud"
    except AttributeError:
        pass  # Router not available (e.g., in tests)

    try:
        async for item in self.inference_client.chat_stream(
            messages=follow_up_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            force_tier=force_tier,
        ):
            if isinstance(item, str):
                yield item
    except Exception as e:
        self.logger.warning(
            f"Failed to stream tool result synthesis: {type(e).__name__}",
            component=LogComponent.ORCHESTRATION,
        )
        yield tool_result
```

**Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_handler_streaming.py::TestStreamingSynthesis -v`
Expected: All 5 tests PASS (3 existing + 2 new).

**Step 6: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=30`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add hestia/inference/client.py hestia/orchestration/handler.py tests/test_handler_streaming.py
git commit -m "feat: route synthesis to cloud when hardware adapted (force_tier)"
```

---

## Phase B: Feedback & Transparency

### Task 3: Tool execution status line in renderer

When tools execute, the CLI is completely silent — the user sees the thinking animation stop and then... nothing for seconds. Add a visible status indicator showing which tool is executing.

**Files:**
- Modify: `hestia-cli/hestia_cli/renderer.py:391-400` (`_render_tool_result()`)
- Test: `hestia-cli/tests/test_renderer.py` (extend `TestRenderer`)

**Step 1: Write the failing test**

Add to `TestRenderer` in `hestia-cli/tests/test_renderer.py`:

```python
def test_render_tool_result_success_shows_status(self):
    """Successful tool result shows execution confirmation."""
    renderer, output = make_renderer()
    renderer.render_event({
        "type": "tool_result",
        "call_id": "call-1",
        "status": "success",
        "tool_name": "read_note",
        "output": "Note contents here...",
    })
    text = output.getvalue()
    assert "read_note" in text
    assert "✓" in text or "success" in text.lower()

def test_render_tool_result_success_no_output_leak(self):
    """Tool result success status does NOT leak the full tool output."""
    renderer, output = make_renderer()
    renderer.render_event({
        "type": "tool_result",
        "call_id": "call-1",
        "status": "success",
        "tool_name": "read_note",
        "output": "SECRET_NOTE_CONTENT_SHOULD_NOT_APPEAR",
    })
    text = output.getvalue()
    assert "SECRET_NOTE_CONTENT_SHOULD_NOT_APPEAR" not in text
```

**Step 2: Run tests to verify they fail**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py::TestRenderer::test_render_tool_result_success_shows_status tests/test_renderer.py::TestRenderer::test_render_tool_result_success_no_output_leak -v`
Expected: FAIL — current `_render_tool_result()` only handles `denied` and `error` statuses, ignoring `success`.

**Step 3: Write minimal implementation**

In `hestia-cli/hestia_cli/renderer.py`, update `_render_tool_result()`:

```python
def _render_tool_result(self, event: Dict[str, Any]) -> None:
    """Render tool execution result."""
    status = event.get("status", "")
    output = escape(str(event.get("output", "")))  # SEC-5: escape Rich markup
    tool_name = event.get("tool_name", "")

    if status == "denied":
        self.console.print("[yellow]  ✗ Tool execution denied.[/yellow]")
    elif status == "error":
        self.console.print(f"[red]  ✗ Tool error: {output}[/red]")
    elif status == "success":
        # Show tool execution confirmation (not the full output — synthesis handles that)
        output_len = len(event.get("output", ""))
        size_hint = f" ({output_len:,} chars)" if output_len > 0 else ""
        if tool_name:
            self.console.print(f"[dim]  ✓ {tool_name}{size_hint}[/dim]")
        else:
            self.console.print(f"[dim]  ✓ Tool executed{size_hint}[/dim]")
```

**Step 4: Emit `tool_name` in the backend `tool_result` event**

In `hestia/orchestration/handler.py`, update the tool_result yield at line 912:

```python
yield {
    "type": "tool_result",
    "call_id": "aggregate",
    "status": "success",
    "output": tool_result,
    "tool_name": tool_name if tool_name else "",
}
```

We need to capture `tool_name` during tool execution. Find where `tool_result` is set and capture the tool name alongside it. Check where `_execute_streaming_tool_calls`, `_execute_council_tools`, and `_try_execute_tool_from_response` are called (lines 888-908).

Add a `tool_name` variable before the tool execution block:

```python
# Step 7.75: Tool execution (3-tier priority — same as handle())
tool_result = None
tool_name = ""

# Priority 1: Native tool calls from Ollama API
if inference_response.tool_calls:
    yield {"type": "status", "stage": "tools", "detail": "Executing tool calls"}
    tool_name = inference_response.tool_calls[0].get("function", {}).get("name", "") if inference_response.tool_calls else ""
    tool_result = await self._execute_streaming_tool_calls(
        inference_response.tool_calls, request, task,
        tool_approval_callback, trust_tiers,
    )
# Priority 2: Council Analyzer tool extraction
elif (
    council_result
    and council_result.tool_extraction
    and council_result.tool_extraction.tool_calls
    and council_result.tool_extraction.confidence > 0.7
):
    yield {"type": "status", "stage": "tools", "detail": "Executing tool calls"}
    tool_name = council_result.tool_extraction.tool_calls[0].tool_name if council_result.tool_extraction.tool_calls else ""
    tool_result = await self._execute_council_tools(
        council_result.tool_extraction.tool_calls, request, task
    )
else:
    # Priority 3: Text regex fallback
    tool_result = await self._try_execute_tool_from_response(content, request, task)
    if tool_result is not None:
        # Extract tool name from content for display
        import re
        registry = get_tool_registry()
        for func_match in re.finditer(r'(\w+)\([^)]*\)', content):
            if registry.has_tool(func_match.group(1)):
                tool_name = func_match.group(1)
                break
```

Then update the yield to include tool_name (line 912):

```python
if tool_result is not None:
    yield {
        "type": "tool_result",
        "call_id": "aggregate",
        "status": "success",
        "output": tool_result,
        "tool_name": tool_name,
    }
```

**Step 5: Run tests to verify they pass**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py::TestRenderer -v`
Expected: All tests PASS.

Run: `python -m pytest tests/test_handler_streaming.py -v`
Expected: All tests PASS.

**Step 6: Run full test suites**

Run: `python -m pytest tests/ -v --timeout=30`
Run: `cd hestia-cli && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add hestia/orchestration/handler.py hestia-cli/hestia_cli/renderer.py hestia-cli/tests/test_renderer.py
git commit -m "feat: show tool execution status line in CLI (tool name + output size)"
```

---

### Task 4: Model/routing indicator in metrics footer

Show which model and routing tier (local/cloud) produced the response, so the user can see if they're getting cloud speed or local latency.

**Files:**
- Modify: `hestia/orchestration/handler.py:976-986` (done event yield)
- Modify: `hestia-cli/hestia_cli/renderer.py:402-433` (`_render_done()`)
- Test: `hestia-cli/tests/test_renderer.py`

**Step 1: Write the failing test**

Add to `TestRenderer` in `hestia-cli/tests/test_renderer.py`:

```python
def test_render_done_shows_cloud_indicator(self):
    """Done metrics show cloud routing indicator."""
    renderer, output = make_renderer()
    renderer.render_event({
        "type": "done",
        "request_id": "req-1",
        "metrics": {
            "tokens_out": 42,
            "duration_ms": 1500.0,
            "model": "claude-3-haiku",
            "routing_tier": "cloud",
        },
        "mode": "tia",
    })
    text = output.getvalue()
    assert "cloud" in text.lower() or "☁" in text

def test_render_done_shows_local_indicator(self):
    """Done metrics show local routing indicator."""
    renderer, output = make_renderer()
    renderer.render_event({
        "type": "done",
        "request_id": "req-1",
        "metrics": {
            "tokens_out": 132,
            "duration_ms": 241300.0,
            "model": "qwen2.5:7b",
            "routing_tier": "local",
        },
        "mode": "tia",
    })
    text = output.getvalue()
    assert "local" in text.lower() or "💻" in text
```

**Step 2: Run tests to verify they fail**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py::TestRenderer::test_render_done_shows_cloud_indicator tests/test_renderer.py::TestRenderer::test_render_done_shows_local_indicator -v`
Expected: FAIL — `_render_done()` doesn't handle `routing_tier`.

**Step 3: Update `_render_done()` in `hestia-cli/hestia_cli/renderer.py`**

```python
def _render_done(self, event: Dict[str, Any]) -> None:
    """Render completion with optional metrics."""
    # Clear any lingering status line
    if self._status_visible:
        _clear_line()
        self._status_visible = False

    self.console.print()  # Newline after streaming

    if self.show_metrics:
        metrics = event.get("metrics", {})
        tokens_in = metrics.get("tokens_in", 0)
        tokens_out = metrics.get("tokens_out", 0)
        duration = metrics.get("duration_ms", 0)
        model = metrics.get("model", "")
        cached = metrics.get("cached", False)
        routing_tier = metrics.get("routing_tier", "")

        parts = []
        if self._agent_theme:
            parts.append(self._agent_theme.name)
        if tokens_out:
            parts.append(f"{tokens_out} tokens")
        if duration:
            parts.append(f"{duration/1000:.1f}s")
        if model:
            # Append routing indicator
            if routing_tier == "cloud":
                parts.append(f"{model} (cloud) ☁️")
            elif routing_tier in ("local", "primary", "coding"):
                parts.append(f"{model} (local) 💻")
            else:
                parts.append(model)
        if cached:
            parts.append("cached")

        if parts:
            self.console.print(f"[dim]  {' · '.join(parts)}[/dim]")
    self.console.print()
```

**Step 4: Add `routing_tier` to the backend done event**

In `hestia/orchestration/handler.py`, update the done event yield (line 976):

```python
yield {
    "type": "done",
    "request_id": request.id,
    "metrics": {
        "tokens_in": inference_response.tokens_in,
        "tokens_out": inference_response.tokens_out,
        "duration_ms": response.duration_ms,
        "model": inference_response.model,
        "routing_tier": getattr(inference_response, 'tier', ''),
    },
    "mode": request.mode.value,
}
```

**Step 5: Run tests to verify they pass**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py::TestRenderer -v`
Expected: All tests PASS.

**Step 6: Run full test suites**

Run: `python -m pytest tests/ -v --timeout=30`
Run: `cd hestia-cli && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add hestia/orchestration/handler.py hestia-cli/hestia_cli/renderer.py hestia-cli/tests/test_renderer.py
git commit -m "feat: show model + routing tier (cloud/local) in CLI metrics footer"
```

---

### Task 5: Visual separator between initial text and synthesis

When the model outputs text before a tool call (e.g., "I'll read your note for you."), then the tool executes and synthesis begins, the initial text bleeds into the synthesized response. Add a visual separator (Rule) to delineate "model reasoning" from "actual answer."

**Files:**
- Modify: `hestia-cli/hestia_cli/renderer.py:391+` (`_render_tool_result()`)
- Test: `hestia-cli/tests/test_renderer.py`

**Step 1: Write the failing test**

```python
def test_render_tool_result_success_shows_separator(self):
    """Successful tool result shows a visual separator with tool name."""
    renderer, output = make_renderer()
    # Simulate streaming state (as if tokens were being rendered)
    renderer._in_streaming = True
    renderer._streaming_buffer = "I'll read your note."
    renderer.render_event({
        "type": "tool_result",
        "call_id": "call-1",
        "status": "success",
        "tool_name": "read_note",
        "output": "Note contents...",
    })
    text = output.getvalue()
    # Should contain a separator with the tool name
    assert "read_note" in text
    assert "⚙" in text or "───" in text or "─" in text
```

**Step 2: Run test to verify it fails**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py::TestRenderer::test_render_tool_result_success_shows_separator -v`
Expected: FAIL

**Step 3: Update `_render_tool_result()` to include separator**

Update the success branch in `_render_tool_result()`:

```python
elif status == "success":
    # Flush any streaming content before the separator
    if self._in_streaming:
        self._stop_live()
        if self._streaming_buffer.strip():
            if self._use_markdown:
                try:
                    self.console.print(Markdown(self._streaming_buffer))
                except Exception:
                    self.console.print(self._streaming_buffer, highlight=False)
            else:
                pass  # Raw mode already printed tokens directly
            self._committed_text += self._streaming_buffer
        self._streaming_buffer = ""

    # Visual separator showing tool execution
    output_len = len(event.get("output", ""))
    size_hint = f" · {output_len:,} chars" if output_len > 0 else ""
    separator_label = f" ⚙️  {tool_name}{size_hint} " if tool_name else f" ⚙️  Tool executed{size_hint} "
    self.console.print(f"\n[dim]{'─' * 3}{separator_label}{'─' * max(3, 50 - len(separator_label))}[/dim]")
```

Also add `from rich.rule import Rule` to imports if needed (or use manual `─` characters as shown).

**Step 4: Run tests to verify they pass**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py -v`
Expected: All tests PASS.

**Step 5: Run full CLI test suite**

Run: `cd hestia-cli && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add hestia-cli/hestia_cli/renderer.py hestia-cli/tests/test_renderer.py
git commit -m "feat: visual separator between initial text and synthesis on tool execution"
```

---

## Phase C: Differentiation

### Task 6: Insight callouts — new event type + renderer

Add Claude Code–style insight callouts that surface operational transparency: why cloud was used, which tool ran, cache hits. Gate insights behind `auto` verbosity — each unique insight type is shown only once per session.

**Files:**
- Modify: `hestia-cli/hestia_cli/models.py:14-23` (`ServerEventType`)
- Modify: `hestia-cli/hestia_cli/renderer.py:109-126` (`render_event()`)
- Modify: `hestia/orchestration/handler.py:976+` (insight emission in streaming pipeline)
- Test: `hestia-cli/tests/test_renderer.py` + `tests/test_handler_streaming.py`

**Step 1: Write the failing tests**

In `hestia-cli/tests/test_renderer.py`, add new test class:

```python
class TestInsightRendering:
    """Test insight callout rendering."""

    def test_render_insight_event(self):
        """Insight events render as a bordered panel."""
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "insight",
            "content": "Routed to cloud — local model too slow.",
            "insight_key": "cloud_routing",
        })
        text = output.getvalue()
        assert "cloud" in text.lower()
        assert "💡" in text or "Insight" in text

    def test_insight_auto_gating_suppresses_repeat(self):
        """Same insight_key shown only once in auto mode."""
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "insight",
            "content": "First cloud routing insight.",
            "insight_key": "cloud_routing",
        })
        first_text = output.getvalue()
        assert "First cloud routing" in first_text

        # Same key again — should be suppressed
        renderer.render_event({
            "type": "insight",
            "content": "Second cloud routing insight.",
            "insight_key": "cloud_routing",
        })
        # The second insight should NOT appear
        full_text = output.getvalue()
        assert "Second cloud routing" not in full_text

    def test_insight_different_keys_both_shown(self):
        """Different insight_keys are both displayed."""
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "insight",
            "content": "Cloud routing insight.",
            "insight_key": "cloud_routing",
        })
        renderer.render_event({
            "type": "insight",
            "content": "Tool execution insight.",
            "insight_key": "tool_execution",
        })
        text = output.getvalue()
        assert "Cloud routing" in text
        assert "Tool execution" in text
```

**Step 2: Run tests to verify they fail**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py::TestInsightRendering -v`
Expected: FAIL — no `_render_insight()` method, no `insight` event type handling.

**Step 3: Add INSIGHT to ServerEventType**

In `hestia-cli/hestia_cli/models.py`, add to `ServerEventType`:

```python
class ServerEventType(str, Enum):
    """Server-to-client event types."""
    AUTH_RESULT = "auth_result"
    STATUS = "status"
    TOKEN = "token"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    DONE = "done"
    ERROR = "error"
    PONG = "pong"
    INSIGHT = "insight"
```

**Step 4: Add insight rendering + auto-gating to renderer**

In `hestia-cli/hestia_cli/renderer.py`:

Add to `__init__()`:
```python
self._seen_insight_keys: set = set()  # Auto-gating: show each insight type once
```

Add to `start_streaming()` — do NOT reset `_seen_insight_keys` here (it persists across messages within a session).

Add to `render_event()` dispatch (after the `elif event_type == "pong":` line):
```python
elif event_type == "insight":
    self._render_insight(event)
```

Add new method:
```python
def _render_insight(self, event: Dict[str, Any]) -> None:
    """Render an insight callout panel.

    Auto-gating: each unique insight_key is displayed only once per session.
    """
    content = event.get("content", "")
    insight_key = event.get("insight_key", "")

    # Auto-gate: suppress repeated insight types
    if insight_key and insight_key in self._seen_insight_keys:
        return
    if insight_key:
        self._seen_insight_keys.add(insight_key)

    # Clear status line if visible
    if self._status_visible:
        _clear_line()
        self._status_visible = False

    color = self.agent_color
    self.console.print(Panel(
        f"[dim]{content}[/dim]",
        title="💡 Insight",
        border_style="dim",
        width=60,
        padding=(0, 1),
    ))
```

**Step 5: Add insight emission to backend streaming pipeline**

In `hestia/orchestration/handler.py`, add insight yields in key decision points.

After cloud routing decision (inside `handle_streaming()`, after `will_use_cloud` is determined, ~line 840):

```python
# Insight: cloud routing
if will_use_cloud:
    yield {
        "type": "insight",
        "content": f"Routed to cloud — {'hardware adapted, local too slow' if getattr(self.inference_client.router, '_adaptation_applied', False) else 'cloud routing active'}.",
        "insight_key": "cloud_routing",
    }
```

After tool result is computed (inside the `if tool_result is not None:` block, ~line 910):

```python
yield {
    "type": "insight",
    "content": f"Tool '{tool_name}' returned {len(tool_result):,} chars. Synthesizing response...",
    "insight_key": "tool_synthesis",
}
```

**Step 6: Run tests to verify they pass**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py -v`
Run: `python -m pytest tests/test_handler_streaming.py -v`
Expected: All tests PASS.

**Step 7: Run full test suites**

Run: `python -m pytest tests/ -v --timeout=30`
Run: `cd hestia-cli && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 8: Commit**

```bash
git add hestia-cli/hestia_cli/models.py hestia-cli/hestia_cli/renderer.py hestia-cli/tests/test_renderer.py hestia/orchestration/handler.py
git commit -m "feat: insight callouts with auto-gating (cloud routing, tool synthesis)"
```

---

### Task 7: Tool execution insight — what tool, what data, why

Enhance tool result rendering to show meaningful context about what the tool did. This compounds with the tool execution status line (Task 3) and the visual separator (Task 5).

**Files:**
- Modify: `hestia/orchestration/handler.py` (emit richer tool_result events)
- Modify: `hestia-cli/hestia_cli/renderer.py` (`_render_tool_result()`)
- Test: `hestia-cli/tests/test_renderer.py`

**Step 1: Write the failing test**

```python
def test_render_tool_result_shows_argument_summary(self):
    """Tool result shows a summary of the arguments used."""
    renderer, output = make_renderer()
    renderer.render_event({
        "type": "tool_result",
        "call_id": "call-1",
        "status": "success",
        "tool_name": "read_note",
        "tool_args": {"title": "hestia"},
        "output": "Note contents...",
    })
    text = output.getvalue()
    assert "read_note" in text
    assert "hestia" in text
```

**Step 2: Run test to verify it fails**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py::TestRenderer::test_render_tool_result_shows_argument_summary -v`
Expected: FAIL

**Step 3: Update `_render_tool_result()` in renderer**

Enhance the separator to include argument summary:

```python
elif status == "success":
    # Flush any streaming content before the separator
    if self._in_streaming:
        self._stop_live()
        if self._streaming_buffer.strip():
            if self._use_markdown:
                try:
                    self.console.print(Markdown(self._streaming_buffer))
                except Exception:
                    self.console.print(self._streaming_buffer, highlight=False)
            else:
                pass
            self._committed_text += self._streaming_buffer
        self._streaming_buffer = ""

    # Build tool execution summary
    tool_args = event.get("tool_args", {})
    args_summary = ""
    if tool_args and tool_name:
        # Format as function call: tool_name(key=value, ...)
        arg_parts = [f'{k}="{v}"' if isinstance(v, str) else f'{k}={v}' for k, v in tool_args.items()]
        args_summary = f"({', '.join(arg_parts)})"
    elif tool_name:
        args_summary = "()"

    output_len = len(event.get("output", ""))
    size_hint = f" · {output_len:,} chars" if output_len > 0 else ""
    display_name = f"{tool_name}{args_summary}" if tool_name else "Tool executed"
    separator_label = f" ⚙️  {display_name}{size_hint} "
    self.console.print(f"\n[dim]{'─' * 3}{separator_label}{'─' * max(3, 50 - len(separator_label))}[/dim]")
```

**Step 4: Emit `tool_args` in the backend tool_result event**

In `hestia/orchestration/handler.py`, capture tool arguments alongside tool_name. Update the tool_result yield:

```python
yield {
    "type": "tool_result",
    "call_id": "aggregate",
    "status": "success",
    "output": tool_result,
    "tool_name": tool_name,
    "tool_args": tool_args,
}
```

Add `tool_args = {}` alongside `tool_name = ""` initialization.

For Priority 1 (native tool calls):
```python
tool_args = inference_response.tool_calls[0].get("function", {}).get("arguments", {}) if inference_response.tool_calls else {}
```

For Priority 2 (council):
```python
tool_args = council_result.tool_extraction.tool_calls[0].arguments if council_result.tool_extraction.tool_calls else {}
```

For Priority 3 (regex):
```python
# Already parsed in _try_execute_tool_from_response — extract from content
import re
for func_match in re.finditer(r'(\w+)\(([^)]*)\)', content):
    if registry.has_tool(func_match.group(1)):
        tool_name = func_match.group(1)
        # Parse args from the match
        args_str = func_match.group(2)
        for kv_match in re.finditer(r'(\w+)\s*=\s*"([^"]*)"', args_str):
            tool_args[kv_match.group(1)] = kv_match.group(2)
        if not tool_args:
            # Positional arg — map to first parameter
            for pos_match in re.finditer(r'"([^"]*)"', args_str):
                tool_args["arg"] = pos_match.group(1)
                break
        break
```

**Step 5: Run tests to verify they pass**

Run: `cd hestia-cli && python -m pytest tests/test_renderer.py -v`
Run: `python -m pytest tests/test_handler_streaming.py -v`
Expected: All tests PASS.

**Step 6: Run full test suites**

Run: `python -m pytest tests/ -v --timeout=30`
Run: `cd hestia-cli && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add hestia/orchestration/handler.py hestia-cli/hestia_cli/renderer.py hestia-cli/tests/test_renderer.py
git commit -m "feat: show tool arguments and execution context in CLI separator"
```

---

## Phase D: Polish

### Task 8: Command palette — `/tools` command + interactive `/config` with YAML validation

Add a `/tools` command to browse available tools, and add YAML validation to `/config` so malformed config doesn't crash the CLI on next load.

**Files:**
- Modify: `hestia-cli/hestia_cli/commands.py:30-41` (command registry + new handlers)
- Modify: `hestia-cli/hestia_cli/commands.py:213-224` (`_cmd_config()`)
- Test: `hestia-cli/tests/test_commands.py` (if exists, else create)

**Step 1: Check if test file exists and write tests**

Check: `ls hestia-cli/tests/test_commands.py` — if not exists, create it.

```python
"""Tests for slash commands."""

import asyncio
from io import StringIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from hestia_cli.commands import handle_slash_command


def make_console():
    output = StringIO()
    console = Console(file=output, no_color=True, width=80)
    return console, output


class TestToolsCommand:
    @pytest.mark.asyncio
    async def test_tools_lists_available_tools(self):
        """The /tools command lists tools from the server."""
        console, output = make_console()
        client = MagicMock()
        client.server_url = "https://localhost:8443"
        client.connected = True

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "tools": [
                {"name": "read_note", "description": "Read a note by title"},
                {"name": "create_note", "description": "Create a new note"},
            ]
        }

        with patch("hestia_cli.commands.httpx.AsyncClient") as MockClient:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_http

            await handle_slash_command("/tools", client, console)

        text = output.getvalue()
        assert "read_note" in text
        assert "create_note" in text

    @pytest.mark.asyncio
    async def test_tools_handles_disconnected(self):
        """The /tools command shows error when disconnected."""
        console, output = make_console()
        client = MagicMock()
        client.connected = False

        await handle_slash_command("/tools", client, console)

        text = output.getvalue()
        assert "connect" in text.lower() or "disconnect" in text.lower()


class TestConfigValidation:
    @pytest.mark.asyncio
    async def test_config_validates_yaml_after_edit(self):
        """Config validates YAML syntax after editor closes."""
        console, output = make_console()
        client = MagicMock()

        with patch("hestia_cli.commands.get_config_path") as mock_path, \
             patch("subprocess.call", return_value=0), \
             patch("builtins.open", create=True) as mock_open:

            import tempfile
            tmp = tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w")
            tmp.write("valid_key: valid_value\n")
            tmp.close()
            mock_path.return_value = tmp.name

            await handle_slash_command("/config", client, console)

        text = output.getvalue()
        # Should NOT show a YAML error for valid YAML
        assert "invalid" not in text.lower() or "yaml" not in text.lower()
```

**Step 2: Run tests to verify they fail**

Run: `cd hestia-cli && python -m pytest tests/test_commands.py -v`
Expected: FAIL — `/tools` command doesn't exist, config has no YAML validation.

**Step 3: Add `/tools` command**

In `hestia-cli/hestia_cli/commands.py`:

Add to the handlers dict:
```python
"/tools": _cmd_tools,
```

Add the handler:

```python
async def _cmd_tools(args: str, client: HestiaWSClient, console: Console) -> None:
    """Browse available tools from the server."""
    if not client.connected:
        console.print("[yellow]Not connected. Connect to the server first.[/yellow]")
        return

    token = get_stored_token()
    if not token:
        console.print("[red]Not authenticated.[/red]")
        return

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as http:
            response = await http.get(
                f"{client.server_url}/v1/tools",
                headers={"X-Hestia-Device-Token": token},
            )
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                if not tools:
                    console.print("[dim]  No tools available.[/dim]")
                    return
                console.print(f"\n[bold]Available Tools ({len(tools)})[/bold]")
                for tool in tools:
                    name = tool.get("name", "unknown")
                    description = tool.get("description", "")
                    tier = tool.get("tier", "")
                    tier_color = {"read": "green", "write": "yellow", "execute": "red", "external": "magenta"}.get(tier, "dim")
                    console.print(f"  [{tier_color}]{name:25s}[/{tier_color}] {description}")
                console.print()
            else:
                console.print(f"[red]Failed to fetch tools: {response.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to fetch tools: {type(e).__name__}[/red]")
```

**Step 4: Add YAML validation to `/config`**

Update `_cmd_config()`:

```python
async def _cmd_config(args: str, client: HestiaWSClient, console: Console) -> None:
    """Open config file in $EDITOR, validate YAML on save."""
    import yaml
    from hestia_cli.config import get_config_path

    config_path = get_config_path()
    editor = os.environ.get("EDITOR", "nano")

    console.print(f"[dim]  Opening {config_path} in {editor}...[/dim]")
    try:
        subprocess.call([editor, str(config_path)])
    except FileNotFoundError:
        console.print(f"[red]Editor not found: {editor}. Set $EDITOR environment variable.[/red]")
        return

    # Validate YAML after editor closes
    try:
        with open(config_path, "r") as f:
            yaml.safe_load(f)
        console.print("[dim]  Config saved ✓[/dim]")
    except yaml.YAMLError as e:
        console.print(f"[red]  ⚠ Invalid YAML in config file: {e}[/red]")
        console.print("[yellow]  Config changes may not apply until the YAML is corrected.[/yellow]")
    except FileNotFoundError:
        pass  # File doesn't exist yet — that's fine
```

**Step 5: Update `/help` to include `/tools`**

In `_cmd_help()`, add:
```
  /tools                    List available tools
```

**Step 6: Run tests to verify they pass**

Run: `cd hestia-cli && python -m pytest tests/test_commands.py -v`
Expected: All tests PASS.

**Step 7: Run full test suites**

Run: `cd hestia-cli && python -m pytest tests/ -v`
Expected: All tests pass.

**Step 8: Commit**

```bash
git add hestia-cli/hestia_cli/commands.py hestia-cli/tests/test_commands.py
git commit -m "feat: /tools command + YAML validation on /config save"
```

---

### Task 9: Prompt_toolkit command completion

Add tab-completion for slash commands so the user can discover available commands by typing `/` and pressing Tab.

**Files:**
- Modify: `hestia-cli/hestia_cli/repl.py` (completer setup)
- Modify: `hestia-cli/hestia_cli/commands.py` (export command list)

**Step 1: Export command metadata from commands.py**

Add to the top of `commands.py`:

```python
# Command metadata for tab completion and help display
COMMAND_METADATA = {
    "/help": "Show available commands",
    "/status": "Server health and connection info",
    "/mode": "Switch persona (tia, mira, olly)",
    "/trust": "View/set tool trust tiers",
    "/memory": "Search Hestia memory",
    "/config": "Configure CLI preferences",
    "/tools": "Browse available tools",
    "/session": "Manage sessions",
    "/clear": "Clear the screen",
    "/exit": "Quit",
}
```

**Step 2: Add slash command completer to repl.py**

Find the `PromptSession` instantiation in `repl.py` and add a `WordCompleter` or `NestedCompleter`:

```python
from prompt_toolkit.completion import WordCompleter
from hestia_cli.commands import COMMAND_METADATA

slash_completer = WordCompleter(
    list(COMMAND_METADATA.keys()),
    sentence=True,  # Complete full words
)
```

Pass the completer to `PromptSession`:

```python
session = PromptSession(
    completer=slash_completer,
    # ... existing params
)
```

**Step 3: Verify manually** (no automated test — prompt_toolkit completion is interactive)

Manual test: `hestia` → type `/` → press Tab → should show all commands.

**Step 4: Commit**

```bash
git add hestia-cli/hestia_cli/commands.py hestia-cli/hestia_cli/repl.py
git commit -m "feat: tab completion for slash commands in CLI"
```

---

## Verification

1. `python -m pytest tests/ -v --timeout=30` — full backend suite
2. `cd hestia-cli && python -m pytest tests/ -v` — full CLI suite
3. Manual E2E test #1: `hestia` → "read my hestia note and analyze the CLI section"
   - Expected: tool status line, visual separator, synthesized response with markdown, model indicator in metrics
4. Manual E2E test #2: `hestia` → type `/` → Tab
   - Expected: command list appears with descriptions
5. Manual E2E test #3: `hestia` → `/tools`
   - Expected: list of available tools with names, descriptions, tiers
6. Manual E2E test #4: `hestia` → `/config` → save invalid YAML → exit editor
   - Expected: YAML validation warning

---

## Summary of All Commits

| Phase | Commit | Description |
|-------|--------|-------------|
| A | 1 | fix: detect `{"name": ...}` JSON format in `_looks_like_tool_call()` |
| A | 2 | feat: route synthesis to cloud when hardware adapted (`force_tier`) |
| B | 3 | feat: show tool execution status line in CLI (tool name + output size) |
| B | 4 | feat: show model + routing tier (cloud/local) in CLI metrics footer |
| B | 5 | feat: visual separator between initial text and synthesis on tool execution |
| C | 6 | feat: insight callouts with auto-gating (cloud routing, tool synthesis) |
| C | 7 | feat: show tool arguments and execution context in CLI separator |
| D | 8 | feat: `/tools` command + YAML validation on `/config` save |
| D | 9 | feat: tab completion for slash commands in CLI |
