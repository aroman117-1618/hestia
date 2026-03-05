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
