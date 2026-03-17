"""Tests for Rich renderer."""

import asyncio
import os
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from hestia_cli.renderer import HestiaRenderer, ThinkingAnimation, _get_agent_verbs


def make_renderer(use_markdown: bool = False) -> tuple:
    """Create a renderer with captured output.

    Args:
        use_markdown: If True, enable markdown rendering. Default False
            for backward-compatible raw-mode tests.
    """
    output = StringIO()
    console = Console(file=output, no_color=True, width=80)
    renderer = HestiaRenderer(console=console, use_markdown=use_markdown)
    return renderer, output


class TestRenderer:
    def test_render_token(self):
        renderer, output = make_renderer()
        renderer.render_event({"type": "token", "content": "Hello"})
        assert "Hello" in output.getvalue()

    def test_render_done_with_metrics(self):
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "done",
            "request_id": "req-1",
            "metrics": {"tokens_out": 42, "duration_ms": 1500.0, "model": "qwen3.5:9b"},
            "mode": "tia",
        })
        text = output.getvalue()
        assert "42 tokens" in text
        assert "1.5s" in text
        assert "qwen3.5:9b" in text

    def test_render_done_no_metrics(self):
        renderer, output = make_renderer()
        renderer.show_metrics = False
        renderer.render_event({
            "type": "done",
            "request_id": "req-1",
            "metrics": {"tokens_out": 42},
            "mode": "tia",
        })
        text = output.getvalue()
        assert "42 tokens" not in text

    def test_render_error(self):
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "error",
            "code": "rate_limited",
            "message": "Too many requests",
        })
        text = output.getvalue()
        assert "rate_limited" in text
        assert "Too many requests" in text

    def test_render_status(self):
        renderer, output = make_renderer()
        renderer.render_event({"type": "status", "stage": "inference"})
        text = output.getvalue()
        assert "Generating" in text

    def test_render_tool_request(self):
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "tool_request",
            "call_id": "tc-001",
            "tool_name": "run_command",
            "arguments": {"command": "ls -la"},
            "tier": "execute",
        })
        text = output.getvalue()
        assert "run_command" in text
        assert "execute" in text

    def test_startup_banner(self):
        renderer, output = make_renderer()
        asyncio.run(
            renderer.render_startup_banner(
                server_url="https://localhost:8443",
                mode="tia",
                version="0.1.0",
                first_run=False,  # Static banner for test
                device_id="dev-123456789",
            )
        )
        text = output.getvalue()
        assert "█████" in text  # Block letter pixel art
        assert "localhost:8443" in text
        assert "@tia" in text
        assert "v0.1.0" in text
        assert "local inference" in text

    def test_streaming_buffer(self):
        renderer, _ = make_renderer()
        renderer.start_streaming()
        renderer._render_token({"content": "Hello "})
        renderer._render_token({"content": "world"})
        assert renderer._streaming_buffer == "Hello world"


# ── Agent Theme Tests (Sprint 11.5 — Task B1) ────────────


from hestia_cli.models import AgentTheme


class TestAgentTheme:
    def test_default_agent_themes(self):
        """Known agents have default themes."""
        tia = AgentTheme.for_agent("tia")
        assert tia.name == "tia"
        assert tia.color_hex == "#FF9500"

        olly = AgentTheme.for_agent("olly")
        assert olly.name == "olly"
        assert olly.color_hex == "#2D8B73"

        mira = AgentTheme.for_agent("mira")
        assert mira.name == "mira"
        assert mira.color_hex == "#1C3A5F"

    def test_unknown_agent_defaults(self):
        """Unknown agent gets default amber theme."""
        custom = AgentTheme.for_agent("custom_agent")
        assert custom.name == "custom_agent"
        assert custom.color_hex == "#FF9500"  # Default

    def test_case_insensitive(self):
        """Agent name lookup is case-insensitive."""
        assert AgentTheme.for_agent("TIA").color_hex == "#FF9500"
        assert AgentTheme.for_agent("Olly").color_hex == "#2D8B73"


class TestAgentColoredRenderer:
    def test_set_agent_theme(self):
        """set_agent_theme updates renderer state."""
        renderer, _ = make_renderer()
        theme = AgentTheme(name="tia", color_hex="#FF9500")
        renderer.set_agent_theme(theme)
        assert renderer.agent_name == "Tia"
        assert renderer.agent_color == "#FF9500"

    def test_prompt_text_with_theme(self):
        """Prompt includes agent name in color."""
        renderer, _ = make_renderer()
        renderer.set_agent_theme(AgentTheme.for_agent("olly"))
        prompt = renderer.get_prompt_text()
        assert "@olly" in prompt
        assert "#2D8B73" in prompt

    def test_prompt_text_without_theme(self):
        """Prompt falls back to yellow without theme."""
        renderer, _ = make_renderer()
        prompt = renderer.get_prompt_text()
        assert "yellow" in prompt
        assert "@hestia" in prompt

    def test_response_header_with_agent(self):
        """First token shows agent name header."""
        renderer, output = make_renderer()
        renderer.set_agent_theme(AgentTheme.for_agent("tia"))
        renderer.render_event({"type": "token", "content": "Hello"})
        text = output.getvalue()
        assert "Tia:" in text

    def test_metrics_include_agent_name(self):
        """Done metrics include agent name."""
        renderer, output = make_renderer()
        renderer.set_agent_theme(AgentTheme.for_agent("olly"))
        renderer.render_event({
            "type": "done",
            "request_id": "req-1",
            "metrics": {"tokens_out": 10, "duration_ms": 500.0},
            "mode": "olly",
        })
        text = output.getvalue()
        assert "olly" in text

    def test_no_color_fallback(self):
        """Without theme, agent_color returns yellow."""
        renderer, _ = make_renderer()
        assert renderer.agent_color == "yellow"

    def test_render_tool_result_success_shows_status(self):
        """Successful tool result shows execution confirmation with separator."""
        renderer, output = make_renderer()
        renderer._in_streaming = True
        renderer._streaming_buffer = ""
        renderer.render_event({
            "type": "tool_result",
            "call_id": "call-1",
            "status": "success",
            "tool_name": "read_note",
            "output": "Note contents here...",
        })
        text = output.getvalue()
        assert "read_note" in text
        assert "⚙" in text or "─" in text

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

    def test_tool_output_escaped(self):
        """Tool result output is escaped to prevent Rich markup injection (SEC-5)."""
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "tool_result",
            "status": "error",
            "output": "[bold red]INJECTED[/bold red]",
        })
        text = output.getvalue()
        # The Rich markup should be escaped, not rendered
        assert "INJECTED" in text
        # Should NOT see Rich formatting applied
        assert "\\[bold red\\]" in text or "[bold red]" in text

    def test_tool_request_args_escaped(self):
        """Tool request arguments are escaped (SEC-5)."""
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "tool_request",
            "call_id": "tc-002",
            "tool_name": "test",
            "arguments": {"key": "[red]malicious[/red]"},
            "tier": "execute",
        })
        text = output.getvalue()
        assert "malicious" in text


# ── Insight Callout Tests ────────────────────────────────────


class TestInsightRendering:
    """Test insight callout rendering and auto-gating."""

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
        first_len = len(output.getvalue())
        assert "First cloud routing" in output.getvalue()

        # Same key again — should be suppressed
        renderer.render_event({
            "type": "insight",
            "content": "Second cloud routing insight.",
            "insight_key": "cloud_routing",
        })
        # Output length should not grow (suppressed)
        assert "Second cloud routing" not in output.getvalue()

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

    def test_insight_no_key_always_shown(self):
        """Insights without a key are always displayed (no gating)."""
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "insight",
            "content": "First ungated insight.",
            "insight_key": "",
        })
        renderer.render_event({
            "type": "insight",
            "content": "Second ungated insight.",
            "insight_key": "",
        })
        text = output.getvalue()
        assert "First ungated" in text
        assert "Second ungated" in text


# ── Progressive Markdown Rendering Tests ────────────────────


class TestMarkdownFlushPoint:
    """Test _find_flush_point() — pure logic, no IO."""

    def _make_md_renderer(self) -> HestiaRenderer:
        """Create a renderer with markdown enabled (no console output needed)."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        return HestiaRenderer(console=console, use_markdown=True)

    def test_no_flush_for_single_paragraph(self):
        """No flush point when buffer has no paragraph break."""
        r = self._make_md_renderer()
        r._streaming_buffer = "Hello world, this is a test."
        assert r._find_flush_point() is None

    def test_flush_on_double_newline(self):
        """Paragraph boundary (\\n\\n) triggers flush."""
        r = self._make_md_renderer()
        r._streaming_buffer = "First paragraph.\n\nSecond paragraph."
        point = r._find_flush_point()
        assert point is not None
        assert r._streaming_buffer[:point] == "First paragraph.\n\n"

    def test_flush_multiple_paragraphs_takes_last_break(self):
        """With multiple \\n\\n, flush point is at the LAST break."""
        r = self._make_md_renderer()
        r._streaming_buffer = "Para 1.\n\nPara 2.\n\nPara 3 still typing"
        point = r._find_flush_point()
        assert point is not None
        complete = r._streaming_buffer[:point]
        assert "Para 1." in complete
        assert "Para 2." in complete
        assert "Para 3" not in complete

    def test_code_block_detection(self):
        """Opening ``` enters code block mode."""
        r = self._make_md_renderer()
        r._streaming_buffer = "```python\nprint('hello')\n```\nMore text"
        point = r._find_flush_point()
        assert point is not None
        complete = r._streaming_buffer[:point]
        assert "```python" in complete
        assert "print('hello')" in complete
        assert "```" in complete

    def test_code_block_not_flushed_until_close(self):
        """Unclosed code block is NOT flushed."""
        r = self._make_md_renderer()
        r._streaming_buffer = "```python\nprint('hello')\nstill typing"
        r._in_code_block = False
        point = r._find_flush_point()
        # The fence opens but doesn't close — enters code block mode
        if point is not None:
            # Should not flush the incomplete code block
            assert "still typing" not in r._streaming_buffer[:point]

    def test_code_block_mode_waits_for_close(self):
        """In code block mode, waits for closing ```."""
        r = self._make_md_renderer()
        r._in_code_block = True
        r._streaming_buffer = "print('hello')\nmore code"
        assert r._find_flush_point() is None

    def test_code_block_mode_flushes_on_close(self):
        """In code block mode, closing ``` triggers flush."""
        r = self._make_md_renderer()
        r._in_code_block = True
        r._streaming_buffer = "print('hello')\n```\nAfter code"
        point = r._find_flush_point()
        assert point is not None
        assert not r._in_code_block  # Should exit code block mode

    def test_text_before_code_fence_flushed(self):
        """Text before a code fence opening is flushed as a paragraph."""
        r = self._make_md_renderer()
        r._streaming_buffer = "Here's some code:\n```python\ncode"
        point = r._find_flush_point()
        assert point is not None
        complete = r._streaming_buffer[:point]
        assert "Here's some code:" in complete
        assert "```python" not in complete


class TestMarkdownRendering:
    """Test markdown rendering output."""

    def test_finish_streaming_renders_markdown(self):
        """finish_streaming() renders remaining buffer as markdown."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        renderer = HestiaRenderer(console=console, use_markdown=True)

        renderer._in_streaming = True
        renderer._streaming_buffer = "## Hello World\n\nThis is **bold** text."
        renderer.finish_streaming()

        text = output.getvalue()
        # Rich Markdown should render the heading and bold
        assert "Hello World" in text
        assert "bold" in text

    def test_finish_streaming_raw_mode(self):
        """In raw mode, finish_streaming prints raw text."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        renderer = HestiaRenderer(console=console, use_markdown=False)

        renderer._in_streaming = True
        renderer._streaming_buffer = "## Hello World"
        renderer.finish_streaming()

        text = output.getvalue()
        # Should contain the raw markdown syntax
        assert "## Hello World" in text

    def test_start_streaming_resets_state(self):
        """start_streaming() resets all markdown state."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        renderer = HestiaRenderer(console=console, use_markdown=True)

        renderer._streaming_buffer = "leftover"
        renderer._committed_text = "old"
        renderer._in_streaming = True
        renderer._in_code_block = True

        renderer.start_streaming()

        assert renderer._streaming_buffer == ""
        assert renderer._committed_text == ""
        assert not renderer._in_streaming
        assert not renderer._in_code_block

    def test_empty_buffer_not_rendered(self):
        """Empty/whitespace buffer doesn't produce output on finish."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        renderer = HestiaRenderer(console=console, use_markdown=True)

        renderer._in_streaming = True
        renderer._streaming_buffer = "   "
        renderer.finish_streaming()

        # Should not render whitespace-only content
        text = output.getvalue().strip()
        assert text == ""

    def test_use_markdown_defaults_to_env(self):
        """use_markdown defaults based on HESTIA_NO_COLOR env var."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)

        # Without env var — markdown enabled
        renderer = HestiaRenderer(console=console)
        assert renderer._use_markdown is True

        # With env var — markdown disabled
        with patch.dict(os.environ, {"HESTIA_NO_COLOR": "1"}):
            renderer2 = HestiaRenderer(console=console)
            assert renderer2._use_markdown is False

    def test_use_markdown_explicit_override(self):
        """Explicit use_markdown param overrides env var."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)

        with patch.dict(os.environ, {"HESTIA_NO_COLOR": "1"}):
            renderer = HestiaRenderer(console=console, use_markdown=True)
            assert renderer._use_markdown is True


# ── Thinking Animation Tests (Sprint 11.5 — Task B2) ────────────


from hestia_cli.models import (
    COMMON_VERBS, TIA_VERBS, OLLY_VERBS, MIRA_VERBS,
    FIRE_FRAMES, ASCII_FRAMES,
)


class TestThinkingVerbs:
    def test_common_verbs_nonempty(self):
        assert len(COMMON_VERBS) >= 10

    def test_tia_verbs(self):
        verbs = _get_agent_verbs("tia")
        assert all(v in verbs for v in TIA_VERBS)
        assert all(v in verbs for v in COMMON_VERBS)

    def test_olly_verbs(self):
        verbs = _get_agent_verbs("olly")
        assert all(v in verbs for v in OLLY_VERBS)

    def test_mira_verbs(self):
        verbs = _get_agent_verbs("mira")
        assert all(v in verbs for v in MIRA_VERBS)

    def test_unknown_agent_gets_common_only(self):
        verbs = _get_agent_verbs("unknown")
        assert verbs == COMMON_VERBS

    def test_fire_frames_count(self):
        assert len(FIRE_FRAMES) == 4

    def test_ascii_frames_count(self):
        assert len(ASCII_FRAMES) >= 4


class TestThinkingAnimation:
    @pytest.mark.asyncio
    async def test_start_creates_task(self):
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        anim = ThinkingAnimation(console)
        await anim.start("tia")
        assert anim.is_active
        await anim.stop()
        assert not anim.is_active

    @pytest.mark.asyncio
    async def test_stop_clears_line(self):
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        anim = ThinkingAnimation(console)
        await anim.start("tia")
        await asyncio.sleep(0.3)  # Let a few frames render
        await anim.stop()
        assert not anim.is_active

    @pytest.mark.asyncio
    async def test_stop_without_start(self):
        """Stopping without starting is a no-op."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        anim = ThinkingAnimation(console)
        await anim.stop()  # Should not raise

    @pytest.mark.asyncio
    async def test_double_start_idempotent(self):
        """Multiple starts don't create multiple tasks."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        anim = ThinkingAnimation(console)
        await anim.start("tia")
        await anim.start("tia")
        assert anim.is_active
        await anim.stop()

    @pytest.mark.asyncio
    async def test_no_emoji_uses_ascii(self):
        """HESTIA_NO_EMOJI env var triggers ASCII fallback."""
        output = StringIO()
        console = Console(file=output, no_color=True, width=80)
        with patch.dict(os.environ, {"HESTIA_NO_EMOJI": "1"}):
            anim = ThinkingAnimation(console)
            assert not anim._use_emoji


class TestInsightRendering:
    """Tests for insight callout rendering and auto-gating."""

    def test_render_insight_event(self):
        """Insight event renders as a Panel with content."""
        renderer, output = make_renderer()
        renderer.render_event({
            "type": "insight",
            "content": "Routed to cloud model for higher quality response.",
            "insight_key": "cloud_routing",
        })
        text = output.getvalue()
        assert "Insight" in text
        assert "cloud" in text.lower()

    def test_insight_auto_gating_suppresses_repeat(self):
        """Same insight_key only displays once per session."""
        renderer, output = make_renderer()

        # First time — should render
        renderer.render_event({
            "type": "insight",
            "content": "Cloud routing active.",
            "insight_key": "cloud_routing",
        })
        first_output = output.getvalue()
        assert "Cloud routing" in first_output

        # Second time — should be suppressed
        output.truncate(0)
        output.seek(0)
        renderer.render_event({
            "type": "insight",
            "content": "Cloud routing active.",
            "insight_key": "cloud_routing",
        })
        second_output = output.getvalue()
        assert second_output.strip() == ""

    def test_insight_different_keys_both_shown(self):
        """Different insight_keys are each shown once."""
        renderer, output = make_renderer()

        renderer.render_event({
            "type": "insight",
            "content": "Cloud routing active.",
            "insight_key": "cloud_routing",
        })
        renderer.render_event({
            "type": "insight",
            "content": "Tool returned 5,000 chars.",
            "insight_key": "tool_synthesis",
        })
        text = output.getvalue()
        assert "Cloud routing" in text
        assert "Tool returned" in text

    def test_insight_no_key_always_shown(self):
        """Insight events without insight_key are always displayed."""
        renderer, output = make_renderer()

        renderer.render_event({
            "type": "insight",
            "content": "One-off message.",
        })
        renderer.render_event({
            "type": "insight",
            "content": "Another one-off.",
        })
        text = output.getvalue()
        assert "One-off message" in text
        assert "Another one-off" in text


class TestClearStream:
    """Tests for clear_stream event that discards raw tool-call JSON."""

    def test_clear_stream_resets_buffer(self):
        """clear_stream event clears the streaming buffer."""
        renderer, output = make_renderer()
        renderer.start_streaming()
        # Simulate streaming some raw JSON tokens
        renderer.render_event({"type": "token", "content": '{"name": "create_note"'})
        renderer.render_event({"type": "token", "content": ', "arguments": {"title": "test"}}'})
        assert renderer._streaming_buffer != ""

        # clear_stream should wipe the buffer
        renderer.render_event({"type": "clear_stream"})
        assert renderer._streaming_buffer == ""
        assert renderer._committed_text == ""

    def test_clear_stream_preserves_streaming_state(self):
        """clear_stream keeps _in_streaming True so synthesized tokens render."""
        renderer, output = make_renderer()
        renderer.start_streaming()
        renderer.render_event({"type": "token", "content": '{"name": "read_note"}'})
        assert renderer._in_streaming is True

        renderer.render_event({"type": "clear_stream"})
        # Still in streaming mode — synthesized response will follow
        assert renderer._in_streaming is True
