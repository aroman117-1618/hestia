"""
Interactive REPL loop for Hestia CLI.

Uses prompt_toolkit for input (history, auto-suggest, completion)
and Rich for output (streaming, markdown, panels).
"""

import asyncio
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from rich.console import Console

from hestia_cli.client import HestiaWSClient, ConnectionError, AuthenticationError
from hestia_cli.commands import handle_slash_command, detect_mode_prefix
from hestia_cli.config import get_config_dir, load_config
from hestia_cli.context import get_repo_context
from hestia_cli.models import ServerEventType
from hestia_cli.renderer import HestiaRenderer


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

    # Connect
    try:
        result = await client.connect()
        renderer.render_startup_banner(
            server_url=client.server_url,
            mode=client.mode,
            device_id=client.device_id,
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
        vi_mode=vi_mode,
    )

    while True:
        try:
            # Build prompt string
            prompt_str = f"[@{client.mode}] > "

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

                if event_type == ServerEventType.TOOL_REQUEST:
                    # Pause streaming for tool approval
                    tool_request_pending = event
                    renderer.render_event(event)

                    # Prompt for approval
                    approval = await _prompt_tool_approval(session, console)
                    await client.send_tool_approval(
                        event.get("call_id", ""),
                        approved=approval,
                    )
                    tool_request_pending = None
                else:
                    renderer.render_event(event)

            renderer.finish_streaming()

        except KeyboardInterrupt:
            # Ctrl+C: cancel current generation
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


async def _prompt_tool_approval(session: PromptSession, console: Console) -> bool:
    """Prompt user for tool approval. Returns True if approved."""
    try:
        with patch_stdout():
            response = await session.prompt_async(
                "Execute? [y/n] > "
            )
        return response.strip().lower() in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        return False
