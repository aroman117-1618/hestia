"""
Rich terminal renderer for Hestia CLI.

Handles all visual output: streaming tokens, status spinners,
markdown rendering, error panels, and metrics display.

Progressive markdown rendering: tokens stream into a buffer.
Complete blocks (paragraphs separated by \\n\\n, or closed code fences)
are flushed as Rich Markdown. Incomplete blocks show as raw text
in a transient Live display for immediate feedback.
"""

import asyncio
import os
import random
import sys
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.live import Live
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
    """Renders Hestia events to the terminal using Rich.

    Supports two rendering modes:
    - **Markdown mode** (default): Buffers tokens and renders complete
      blocks (paragraphs, code blocks) as Rich Markdown. Incomplete
      text shows as raw preview in a transient Live display.
    - **Raw mode** (HESTIA_NO_COLOR): Prints tokens immediately as
      plain text, no markdown processing.
    """

    def __init__(
        self,
        console: Optional[Console] = None,
        show_metrics: bool = True,
        use_markdown: Optional[bool] = None,
    ):
        self.console = console or Console()
        self.show_metrics = show_metrics
        self._streaming_buffer = ""
        self._committed_text = ""  # Already-rendered text (for metrics tracking)
        self._status_text = ""
        self._in_streaming = False
        self._status_visible = False
        self._agent_theme: Optional[AgentTheme] = None
        self._animation = ThinkingAnimation(self.console)

        # Markdown streaming state
        self._live: Optional[Live] = None
        self._in_code_block = False

        # Insight auto-gating: show each insight type once per session
        self._seen_insight_keys: set = set()
        # use_markdown can be explicitly set (for tests), otherwise check env var
        if use_markdown is not None:
            self._use_markdown = use_markdown
        else:
            self._use_markdown = os.environ.get("HESTIA_NO_COLOR") is None

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
        elif event_type == "insight":
            self._render_insight(event)
        elif event_type == "clear_stream":
            self._clear_streamed_content()
        elif event_type == "pong":
            pass  # Silent

    def start_streaming(self) -> None:
        """Begin a new streaming response."""
        self._streaming_buffer = ""
        self._committed_text = ""
        self._status_text = ""
        self._in_streaming = False
        self._status_visible = False
        self._in_code_block = False
        self._stop_live()

    def finish_streaming(self) -> None:
        """Finalize streaming output — commit transient content permanently."""
        self._stop_live()  # Clears transient Live display

        # Permanently render the full accumulated buffer
        full_text = (self._committed_text + self._streaming_buffer).strip()
        if full_text:
            if self._use_markdown:
                try:
                    self.console.print(Markdown(full_text))
                except Exception:
                    self.console.print(full_text)
            else:
                self.console.print(full_text, end="", highlight=False)

        self._streaming_buffer = ""
        self._committed_text = ""
        self._in_streaming = False
        self._in_code_block = False

    def _clear_streamed_content(self) -> None:
        """Discard previously-streamed raw tokens (e.g., tool-call JSON).

        Called when the backend detects a tool call was executed from text
        that was already streamed as tokens. Stops the Live preview and
        clears the buffer so the synthesized response starts clean.
        """
        self._stop_live()
        self._streaming_buffer = ""
        self._committed_text = ""
        self._in_code_block = False
        # Don't reset _in_streaming — the synthesized response tokens will follow

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
        """Buffer streaming token and render in a transient Live display.

        All streamed content stays in a transient Live display until
        finish_streaming() commits it permanently. This allows clear_stream
        to atomically discard all streamed content (e.g., raw tool-call JSON).

        In raw mode (HESTIA_NO_COLOR): prints tokens immediately.
        """
        content = event.get("content", "")
        if not content:
            return

        # Clear status line before first token
        if self._status_visible:
            _clear_line()
            self._status_visible = False

        if not self._in_streaming:
            self._in_streaming = True
            color = self.agent_color
            name = self.agent_name
            self.console.print(f"\n[{color}]{name}:[/{color}]")

        if not self._use_markdown:
            # Raw mode — print immediately (original behavior)
            self._streaming_buffer += content
            self.console.print(content, end="", highlight=False)
            return

        # Markdown mode — buffer all content in transient Live display
        self._streaming_buffer += content

        # Render full accumulated buffer as Markdown in the Live display
        if self._live is None:
            self._start_live_markdown(self._streaming_buffer)
        else:
            self._update_live_markdown(self._streaming_buffer)

    def _flush_completed_blocks(self) -> None:
        """Render completed markdown blocks, keep incomplete remainder.

        Block boundaries:
        - Paragraph: \\n\\n (outside code fences)
        - Code block: closing ``` (inside code fences)

        When a boundary is found, everything before it is rendered as
        Rich Markdown. The remainder stays in the buffer for the next flush.
        """
        flush_point = self._find_flush_point()
        if flush_point is None:
            return

        # Split at flush point
        complete = self._streaming_buffer[:flush_point]
        remainder = self._streaming_buffer[flush_point:]

        # Stop transient Live (clears raw preview)
        self._stop_live()

        # Render completed blocks as formatted markdown
        if complete.strip():
            try:
                self.console.print(Markdown(complete))
            except Exception:
                self.console.print(complete, highlight=False)
            self._committed_text += complete

        # Reset buffer to remainder
        self._streaming_buffer = remainder

        # Start new Live for remainder if there's content
        if remainder:
            self._start_live(remainder)

    def _find_flush_point(self) -> Optional[int]:
        """Find the next point where buffer can be split into complete blocks.

        Returns the index to split at, or None if no complete block found.
        """
        buf = self._streaming_buffer

        if self._in_code_block:
            # Inside a code block — look for closing ```
            # Search from after the opening fence
            search_start = 0
            close_idx = buf.find("```", search_start)
            if close_idx == -1:
                return None  # Still in code block

            # Find end of the closing fence line
            newline_after = buf.find("\n", close_idx + 3)
            if newline_after == -1:
                # Closing fence at very end, no trailing newline yet
                flush_point = close_idx + 3
            else:
                flush_point = newline_after + 1

            self._in_code_block = False
            return flush_point

        # Not in a code block — check for code block opening and paragraph boundary
        fence_idx = buf.find("```")
        para_idx = buf.rfind("\n\n")

        if fence_idx != -1 and (para_idx == -1 or fence_idx < para_idx):
            # Code fence opens before any paragraph break
            # Flush everything before the fence as a paragraph, enter code block mode
            if fence_idx > 0 and buf[:fence_idx].strip():
                # There's content before the fence — flush it
                return fence_idx
            else:
                # Fence is at the start — enter code block mode, look for close
                self._in_code_block = True
                close_idx = buf.find("```", fence_idx + 3)
                if close_idx == -1:
                    return None  # Code block still open
                # Found closing fence
                newline_after = buf.find("\n", close_idx + 3)
                flush_point = (newline_after + 1) if newline_after != -1 else close_idx + 3
                self._in_code_block = False
                return flush_point

        if para_idx != -1:
            # Paragraph boundary found — flush up to and including \n\n
            return para_idx + 2

        return None

    # --- Live display management ---

    def _start_live(self, initial_text: str = "") -> None:
        """Start a transient Live display for raw token preview."""
        if self._live is not None:
            return
        try:
            self._live = Live(
                Text(initial_text, style=""),
                console=self.console,
                transient=True,
                auto_refresh=False,
            )
            self._live.start()
        except Exception:
            # Fallback: if Live fails, print raw
            self._live = None

    def _stop_live(self) -> None:
        """Stop the Live display (transient=True clears it)."""
        if self._live is not None:
            try:
                self._live.stop()
            except Exception:
                pass
            self._live = None

    def _update_live(self, text: str) -> None:
        """Update the Live display with current raw text."""
        if self._live is not None:
            try:
                self._live.update(Text(text, style=""))
                self._live.refresh()
            except Exception:
                pass

    def _start_live_markdown(self, text: str) -> None:
        """Start a transient Live display rendering Markdown."""
        if self._live is not None:
            return
        try:
            renderable = Markdown(text) if text.strip() else Text("")
            self._live = Live(
                renderable,
                console=self.console,
                transient=True,
                auto_refresh=False,
            )
            self._live.start()
        except Exception:
            self._live = None

    def _update_live_markdown(self, text: str) -> None:
        """Update the Live display with Markdown-rendered content."""
        if self._live is not None:
            try:
                self._live.update(Markdown(text) if text.strip() else Text(""))
                self._live.refresh()
            except Exception:
                pass

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
        """Render tool execution result with visual separator.

        For success: flushes any pending streaming text, then shows a
        separator line with tool name, arguments, and output size.
        For denied/error: shows a status message.
        """
        status = event.get("status", "")
        output = escape(str(event.get("output", "")))  # SEC-5: escape Rich markup
        tool_name = event.get("tool_name", "")
        tool_args = event.get("tool_args", {})

        if status == "denied":
            self.console.print("[yellow]  ✗ Tool execution denied.[/yellow]")
        elif status == "error":
            self.console.print(f"[red]  ✗ Tool error: {output}[/red]")
        elif status == "success":
            # Flush any pending streaming content before the separator
            if self._in_streaming:
                self._stop_live()
                if self._streaming_buffer.strip():
                    if self._use_markdown:
                        try:
                            self.console.print(Markdown(self._streaming_buffer))
                        except Exception:
                            self.console.print(self._streaming_buffer, highlight=False)
                    self._committed_text += self._streaming_buffer
                self._streaming_buffer = ""

            # Build tool execution summary
            args_summary = ""
            if tool_args and tool_name:
                arg_parts = []
                for k, v in tool_args.items():
                    arg_parts.append(f'{k}="{v}"' if isinstance(v, str) else f'{k}={v}')
                args_summary = f"({', '.join(arg_parts)})"
            elif tool_name:
                args_summary = "()"

            output_len = len(event.get("output", ""))
            size_hint = f" · {output_len:,} chars" if output_len > 0 else ""
            display_name = f"{tool_name}{args_summary}" if tool_name else "Tool executed"
            separator_label = f" ⚙️  {display_name}{size_hint} "
            pad_len = max(3, 50 - len(separator_label))
            self.console.print(
                f"\n[dim]{'─' * 3}{separator_label}{'─' * pad_len}[/dim]"
            )

    def _render_done(self, event: Dict[str, Any]) -> None:
        """Render completion with optional metrics, bylines, and routing indicator."""
        # Clear any lingering status line
        if self._status_visible:
            _clear_line()
            self._status_visible = False

        self.console.print()  # Newline after streaming

        # Agent bylines — show when specialists contributed
        bylines = event.get("bylines")
        if bylines:
            for byline in bylines:
                agent = byline.get("agent", "")
                summary = byline.get("summary", "")
                icon = {"artemis": "\U0001f4d0", "apollo": "\u26a1"}.get(agent, "")
                name = {"artemis": "Artemis", "apollo": "Apollo"}.get(agent, agent.capitalize())
                self.console.print(f"[dim]  {icon} {name} \u2014 {summary}[/dim]")

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
                # Append routing indicator (cloud/local)
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

    def _render_insight(self, event: Dict[str, Any]) -> None:
        """Render an insight callout (auto-gated by insight_key).

        Each unique insight_key is displayed at most once per CLI session.
        Events without an insight_key are always shown.
        """
        content = event.get("content", "")
        insight_key = event.get("insight_key", "")

        # Auto-gate: skip if this insight_key was already shown
        if insight_key and insight_key in self._seen_insight_keys:
            return
        if insight_key:
            self._seen_insight_keys.add(insight_key)

        # Clear lingering status line if needed
        if self._status_visible:
            _clear_line()
            self._status_visible = False

        self.console.print(Panel(
            f"[dim]{content}[/dim]",
            title="💡 Insight",
            border_style="dim",
            width=60,
            padding=(0, 1),
        ))

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
