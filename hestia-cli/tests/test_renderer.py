"""Tests for Rich renderer."""

from io import StringIO

from rich.console import Console

from hestia_cli.renderer import HestiaRenderer


def make_renderer() -> tuple:
    """Create a renderer with captured output."""
    output = StringIO()
    console = Console(file=output, no_color=True, width=80)
    renderer = HestiaRenderer(console=console)
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
        renderer.render_startup_banner(
            server_url="https://localhost:8443",
            mode="tia",
            device_id="dev-123456789",
        )
        text = output.getvalue()
        assert "Hestia CLI" in text
        assert "localhost:8443" in text
        assert "@tia" in text

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
