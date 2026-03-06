"""
Rich terminal renderer for Hestia CLI.

Handles all visual output: streaming tokens, status spinners,
markdown rendering, error panels, and metrics display.
"""

import asyncio
import os
import random
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.markup import escape

from hestia_cli.models import (
    AgentTheme, ASCII_FRAMES, COMMON_VERBS, DoneMetrics, FIRE_FRAMES,
    MIRA_VERBS, OLLY_VERBS, PipelineStage, STAGE_LABELS,
    TIA_VERBS, ToolRequest,
)


def _clear_line() -> None:
    """Clear the current terminal line using ANSI escape directly to stdout."""
    sys.stdout.write("\r\033[K")
    sys.stdout.flush()


class HestiaRenderer:
    """Renders Hestia events to the terminal using Rich."""

    def __init__(self, console: Optional[Console] = None, show_metrics: bool = True):
        self.console = console or Console()
        self.show_metrics = show_metrics
        self._streaming_buffer = ""
        self._status_text = ""
        self._in_streaming = False
        self._status_visible = False
        self._agent_theme: Optional[AgentTheme] = None
        self._animation = ThinkingAnimation(self.console)

    def set_agent_theme(self, theme: AgentTheme) -> None:
        """Set the active agent theme for colored prompts."""
        self._agent_theme = theme

    @property
    def agent_color(self) -> str:
        """Rich color string for the active agent."""
        if self._agent_theme:
            return self._agent_theme.color_hex
        return "yellow"

    @property
    def agent_name(self) -> str:
        """Display name of the active agent."""
        if self._agent_theme:
            return self._agent_theme.name.capitalize()
        return "Hestia"

    async def start_thinking(self) -> None:
        """Start the thinking animation."""
        agent = self._agent_theme.name if self._agent_theme else "hestia"
        await self._animation.start(agent)

    async def stop_thinking(self) -> None:
        """Stop the thinking animation (call before first token)."""
        if self._animation.is_active:
            await self._animation.stop()

    def get_prompt_text(self) -> str:
        """Get the Rich-formatted prompt string."""
        name = self._agent_theme.name if self._agent_theme else "hestia"
        color = self.agent_color
        return f"[{color}][@{name}][/{color}] > "

    def render_event(self, event: Dict[str, Any]) -> None:
        """Dispatch an event to the appropriate renderer."""
        event_type = event.get("type", "")

        if event_type == "status":
            self._render_status(event)
        elif event_type == "token":
            self._render_token(event)
        elif event_type == "tool_request":
            self._render_tool_request(event)
        elif event_type == "tool_result":
            self._render_tool_result(event)
        elif event_type == "done":
            self._render_done(event)
        elif event_type == "error":
            self._render_error(event)
        elif event_type == "pong":
            pass  # Silent

    def start_streaming(self) -> None:
        """Begin a new streaming response."""
        self._streaming_buffer = ""
        self._status_text = ""
        self._in_streaming = False
        self._status_visible = False

    def finish_streaming(self) -> None:
        """Finalize streaming output — no re-render, tokens already printed."""
        self._streaming_buffer = ""
        self._in_streaming = False

    def render_startup_banner(
        self,
        server_url: str,
        mode: str,
        device_id: Optional[str] = None,
        trust_tiers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Render the startup banner."""
        self.console.print()
        self.console.print(
            f"[bold]Hestia CLI[/bold] v0.1 — connected to [cyan]{server_url}[/cyan]"
        )
        color = self.agent_color
        info_parts = [f"[{color}]@{mode}[/{color}]"]
        if device_id:
            info_parts.append(f"device:{device_id[:8]}")
        if trust_tiers:
            tier_summary = " ".join(
                f"{k}={'[green]auto[/green]' if v == 'auto' else '[yellow]prompt[/yellow]'}"
                for k, v in trust_tiers.items()
            )
            info_parts.append(f"trust: {tier_summary}")
        self.console.print(" | ".join(info_parts))
        self.console.print(
            "[dim]Type a message to chat. /help for commands. Ctrl+C to cancel. Ctrl+D to exit.[/dim]"
        )
        self.console.print()

    def render_reconnecting(self, attempt: int) -> None:
        """Show reconnection status."""
        self.console.print(f"[yellow]Reconnecting... (attempt {attempt})[/yellow]")

    def render_disconnected(self) -> None:
        """Show disconnection message."""
        self.console.print("[red]Disconnected from server.[/red]")

    # --- Private renderers ---

    def _render_status(self, event: Dict[str, Any]) -> None:
        """Show pipeline stage as a spinner line."""
        stage = event.get("stage", "")
        label = STAGE_LABELS.get(stage, event.get("detail", stage))
        self._status_text = label

        # Clear previous status line via raw ANSI, then write new one via Rich
        _clear_line()
        self.console.print(f"  [dim]⟳ {label}...[/dim]", end="")
        self._status_visible = True

    def _render_token(self, event: Dict[str, Any]) -> None:
        """Append streaming token to output."""
        content = event.get("content", "")
        if content:
            # Clear status line before first token
            if self._status_visible:
                _clear_line()
                self._status_visible = False
            if not self._in_streaming:
                self._in_streaming = True
                # Agent name header before first token
                color = self.agent_color
                name = self.agent_name
                self.console.print(f"\n[{color}]{name}:[/{color}]")

            self._streaming_buffer += content
            # Print raw token for immediate feedback
            self.console.print(content, end="", highlight=False)

    def _render_tool_request(self, event: Dict[str, Any]) -> None:
        """Render tool approval request."""
        req = ToolRequest(**{k: v for k, v in event.items() if k != "type"})
        self.console.print()

        args_display = ""
        if req.arguments:
            args_lines = [f"  {escape(str(k))}: {escape(str(v))}" for k, v in req.arguments.items()]
            args_display = "\n".join(args_lines)

        panel_content = f"[bold]{req.tool_name}[/bold]\n{args_display}\n[dim]tier: {req.tier}[/dim]"
        self.console.print(Panel(
            panel_content,
            title="Tool Request",
            border_style="yellow",
            width=60,
        ))

    def _render_tool_result(self, event: Dict[str, Any]) -> None:
        """Render tool execution result."""
        status = event.get("status", "")
        output = escape(str(event.get("output", "")))  # SEC-5: escape Rich markup

        if status == "denied":
            self.console.print("[yellow]Tool execution denied.[/yellow]")
        elif status == "error":
            self.console.print(f"[red]Tool error: {output}[/red]")
        # Success output will be rendered as part of the streamed response

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

            parts = []
            if self._agent_theme:
                parts.append(self._agent_theme.name)
            if tokens_out:
                parts.append(f"{tokens_out} tokens")
            if duration:
                parts.append(f"{duration/1000:.1f}s")
            if model:
                parts.append(model)
            if cached:
                parts.append("cached")

            if parts:
                self.console.print(f"[dim]  {' · '.join(parts)}[/dim]")
        self.console.print()

    def _render_error(self, event: Dict[str, Any]) -> None:
        """Render error message."""
        # Clear any lingering status line
        if self._status_visible:
            _clear_line()
            self._status_visible = False

        code = event.get("code", "error")
        message = event.get("message", "Unknown error")
        self.console.print(f"\n[red]Error ({code}): {message}[/red]\n")


# ── Thinking Animation (Sprint 11.5 B2) ────────────────────


def _get_agent_verbs(agent_name: str) -> List[str]:
    """Get verb pool for an agent (common + agent-specific)."""
    agent_verbs = {
        "tia": TIA_VERBS,
        "olly": OLLY_VERBS,
        "mira": MIRA_VERBS,
    }
    specific = agent_verbs.get(agent_name.lower(), [])
    return COMMON_VERBS + specific


class ThinkingAnimation:
    """
    Animated thinking indicator with fire emoji and rotating verbs.

    Display: 🔥 Chewing on this...
    Fire emoji color-cycles at 200ms, verb rotates every 2s.
    Race-condition safe: asyncio.Lock ensures clean stop→token transition.
    """

    def __init__(self, console: Console) -> None:
        self._console = console
        self._task: Optional[asyncio.Task] = None
        self._lock: Optional[asyncio.Lock] = None
        self._active = False
        self._use_emoji = os.environ.get("HESTIA_NO_EMOJI") is None
        self._use_color = os.environ.get("HESTIA_NO_COLOR") is None

    def _get_lock(self) -> asyncio.Lock:
        """Lazy-init asyncio.Lock (requires running event loop, not available at __init__ on Python 3.9)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @property
    def is_active(self) -> bool:
        return self._active

    async def start(self, agent_name: str = "hestia") -> None:
        """Start the animation loop."""
        async with self._get_lock():
            if self._active:
                return
            self._active = True
            verbs = _get_agent_verbs(agent_name)
            self._task = asyncio.create_task(self._animate(verbs))

    async def stop(self) -> None:
        """Stop animation and clear the line."""
        async with self._get_lock():
            if not self._active:
                return
            self._active = False
            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            self._task = None
            _clear_line()

    async def _animate(self, verbs: List[str]) -> None:
        """Animation loop: cycle frames at 200ms, verbs at 2s."""
        frames = FIRE_FRAMES if (self._use_emoji and self._use_color) else ASCII_FRAMES
        frame_idx = 0
        verb_idx = random.randint(0, len(verbs) - 1)
        ticks = 0  # Each tick = 200ms, verb changes every 10 ticks (2s)

        try:
            while self._active:
                frame = frames[frame_idx % len(frames)]
                verb = verbs[verb_idx % len(verbs)]

                if not self._use_color:
                    frame = frames[frame_idx % len(frames)] if self._use_emoji else ASCII_FRAMES[frame_idx % len(ASCII_FRAMES)]
                    line = f"  {frame} {verb}..."
                else:
                    line = f"  {frame} [dim]{verb}...[/dim]"

                _clear_line()
                self._console.print(line, end="", highlight=False)

                await asyncio.sleep(0.2)
                frame_idx += 1
                ticks += 1
                if ticks % 10 == 0:
                    verb_idx = random.randint(0, len(verbs) - 1)
        except asyncio.CancelledError:
            pass
