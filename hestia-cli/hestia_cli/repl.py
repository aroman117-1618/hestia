"""
Interactive REPL loop for Hestia CLI.

Uses prompt_toolkit for input (history, auto-suggest, completion)
and Rich for output (streaming, markdown, panels).
"""

import asyncio
import traceback
from datetime import datetime
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from hestia_cli.bootstrap import ensure_server_running, ensure_authenticated, ensure_models_available
from hestia_cli.client import HestiaWSClient, ConnectionError, AuthenticationError
from hestia_cli.commands import handle_slash_command, detect_mode_prefix
from hestia_cli.config import get_config_dir, load_config
from hestia_cli.context import get_repo_context
from hestia_cli.models import ServerEventType
from hestia_cli.renderer import HestiaRenderer


SLASH_COMMANDS = {
    "/help": "Show available commands",
    "/status": "Server health and connection info",
    "/mode": "Switch persona (tia, mira, olly)",
    "/trust": "View or modify tool trust tiers",
    "/memory": "Search Hestia memory",
    "/tools": "List available tools from the server",
    "/config": "Open config in $EDITOR",
    "/session": "Session management",
    "/clear": "Clear the screen",
    "/exit": "Quit",
    "/quit": "Quit",
}


class SlashCommandCompleter(Completer):
    """Tab-complete slash commands and @mode prefixes."""

    def get_completions(self, document: Document, complete_event):
        text = document.text_before_cursor
        # Only complete at the start of input
        if " " in text:
            return

        if text.startswith("/"):
            for cmd, desc in SLASH_COMMANDS.items():
                if cmd.startswith(text):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display_meta=desc,
                    )
        elif text.startswith("@"):
            for mode in ("@tia", "@mira", "@olly"):
                if mode.startswith(text):
                    yield Completion(
                        mode + " ",
                        start_position=-len(text),
                        display_meta=f"Send as {mode[1:].capitalize()}",
                    )


def _log_error(error: Exception) -> None:
    """Append error details to ~/.hestia/error.log."""
    try:
        log_path = get_config_dir() / "error.log"
        with open(log_path, "a") as f:
            f.write(f"\n--- {datetime.now().isoformat()} ---\n")
            traceback.print_exception(type(error), error, error.__traceback__, file=f)
    except Exception:
        pass  # Don't fail on logging failures


async def repl_loop(client: HestiaWSClient, console: Console) -> None:
    """
    Main interactive REPL loop.

    Reads input, sends to Hestia, renders streaming response.
    """
    config = load_config()
    show_metrics = config.get("preferences", {}).get("show_metrics", True)
    auto_context = config.get("preferences", {}).get("auto_context", True)
    vi_mode = config.get("preferences", {}).get("vi_mode", False)

    renderer = HestiaRenderer(console=console, show_metrics=show_metrics)

    # Bootstrap: ensure models, server, and auth
    models_ok = await ensure_models_available(console)
    if not models_ok:
        return
    auto_start = config.get("server", {}).get("auto_start", True)
    server_ok = await ensure_server_running(client.server_url, client.verify_ssl, console, auto_start=auto_start)
    if not server_ok:
        return
    auth_ok = await ensure_authenticated(client.server_url, client.verify_ssl, console)
    if not auth_ok:
        return

    # Connect
    try:
        result = await client.connect()

        # Fetch agent theme for colored prompts
        theme = await client.fetch_agent_theme()
        renderer.set_agent_theme(theme)

        renderer.render_startup_banner(
            server_url=client.server_url,
            mode=client.mode,
            device_id=client.device_id,
            trust_tiers=client.trust_tiers,
        )
    except AuthenticationError as e:
        console.print(f"[red]Authentication failed: {e}[/red]")
        console.print("[dim]Run 'hestia auth login' to authenticate.[/dim]")
        return
    except ConnectionError as e:
        console.print(f"[red]{e}[/red]")
        return

    # Set up prompt
    history_path = get_config_dir() / "history"
    session: PromptSession = PromptSession(
        history=FileHistory(str(history_path)),
        auto_suggest=AutoSuggestFromHistory(),
        completer=SlashCommandCompleter(),
        vi_mode=vi_mode,
    )

    while True:
        try:
            # Build prompt string (agent-colored)
            prompt_str = f"[@{client.mode}] > "  # Plain text for prompt_toolkit

            with patch_stdout():
                user_input = await session.prompt_async(prompt_str)

            user_input = user_input.strip()
            if not user_input:
                continue

            # Handle slash commands
            if user_input.startswith("/"):
                await handle_slash_command(user_input, client, console)
                continue

            # Detect @mode prefix
            mode_override, cleaned_content = detect_mode_prefix(user_input)
            if mode_override:
                client.mode = mode_override

            # Build context hints
            context_hints = get_repo_context() if auto_context else {}

            # Send message and stream response
            if not client.connected:
                console.print("[yellow]Reconnecting...[/yellow]")
                reconnected = await client.reconnect()
                if not reconnected:
                    console.print("[red]Failed to reconnect. Try 'hestia auth login'.[/red]")
                    continue

            renderer.start_streaming()

            tool_request_pending = None

            async for event in client.send_message(
                content=cleaned_content,
                mode=mode_override,
                context_hints=context_hints,
            ):
                event_type = event.get("type")

                # Start animation on inference stage
                if event_type == "status" and event.get("stage") == "inference":
                    await renderer.start_thinking()

                # Stop animation before first token
                if event_type == "token":
                    await renderer.stop_thinking()

                if event_type == ServerEventType.TOOL_REQUEST:
                    await renderer.stop_thinking()
                    tool_request_pending = event
                    renderer.render_event(event)

                    approval = await _prompt_tool_approval(session, console)
                    await client.send_tool_approval(
                        event.get("call_id", ""),
                        approved=approval,
                    )
                    tool_request_pending = None
                elif event_type in ("done", "error"):
                    await renderer.stop_thinking()
                    renderer.render_event(event)
                else:
                    renderer.render_event(event)

            renderer.finish_streaming()

        except KeyboardInterrupt:
            # Ctrl+C: cancel current generation
            await renderer.stop_thinking()
            if client.connected:
                await client.send_cancel()
            console.print("\n[dim]Cancelled.[/dim]")
            renderer.finish_streaming()
            continue

        except EOFError:
            # Ctrl+D: exit
            console.print("\n[dim]Goodbye.[/dim]")
            await client.disconnect()
            return

        except SystemExit:
            # /exit command
            await client.disconnect()
            return

        except ConnectionError:
            renderer.finish_streaming()
            console.print("[yellow]Connection lost. Attempting to reconnect...[/yellow]")
            reconnected = await client.reconnect()
            if reconnected:
                console.print("[green]Reconnected.[/green]")
            else:
                console.print("[red]Failed to reconnect.[/red]")

        except Exception as e:
            # Catch-all: log and continue
            renderer.finish_streaming()
            _log_error(e)
            console.print(f"[red]Unexpected error: {type(e).__name__}. Details logged to ~/.hestia/error.log[/red]")


async def _prompt_tool_approval(session: PromptSession, console: Console) -> bool:
    """
    Prompt user for tool approval. Returns True if approved.

    Options: y(es), n(o), a(lways for this tier — future Sprint 3C).
    """
    try:
        with patch_stdout():
            response = await session.prompt_async(
                "Execute? [y/n/a(lways)] > "
            )
        answer = response.strip().lower()
        # TODO (Sprint 3C): "a" / "always" should upgrade the tier to auto
        # and persist via /trust save. For now, treat as "yes for this call".
        return answer in ("y", "yes", "a", "always")
    except (KeyboardInterrupt, EOFError):
        return False
