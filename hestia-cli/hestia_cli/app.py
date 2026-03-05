"""
Hestia CLI application entry point.

Provides:
  hestia              — Interactive REPL
  hestia "query"      — Single-shot batch mode
  hestia auth login   — Device authentication
  hestia auth status  — Check auth status
  hestia auth logout  — Clear credentials
"""

import asyncio
import json
import sys
from typing import Optional

import typer
from rich.console import Console

from hestia_cli import __version__

app = typer.Typer(
    name="hestia",
    help="Terminal interface for Hestia personal AI assistant.",
    no_args_is_help=False,
    invoke_without_command=True,
)

auth_app = typer.Typer(help="Authentication commands.")
app.add_typer(auth_app, name="auth")

console = Console()


_SUBCOMMANDS = {"auth"}


@app.callback(invoke_without_command=True)
def main_callback(
    ctx: typer.Context,
    mode: Optional[str] = typer.Option(None, "-m", "--mode", help="Persona: tia, mira, olly"),
    json_output: bool = typer.Option(False, "--json", help="Output raw JSON (for scripting)"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color output"),
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
):
    """Hestia CLI — chat with your personal AI assistant."""
    if version:
        console.print(f"hestia-cli {__version__}")
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return

    if no_color:
        console_override = Console(no_color=True)
    else:
        console_override = console

    # Batch message extracted in main() before Typer runs
    message = _stashed_batch_message.pop() if _stashed_batch_message else None

    if message:
        asyncio.run(_batch_mode(message, mode, json_output, console_override))
    elif not sys.stdin.isatty():
        stdin_content = sys.stdin.read().strip()
        if stdin_content:
            asyncio.run(_batch_mode(stdin_content, mode, json_output, console_override))
    else:
        asyncio.run(_interactive_mode(mode, console_override))


async def _interactive_mode(mode: Optional[str], con: Console) -> None:
    """Launch the interactive REPL."""
    from hestia_cli.client import HestiaWSClient
    from hestia_cli.repl import repl_loop

    client = HestiaWSClient()
    if mode:
        client.mode = mode

    await repl_loop(client, con)


async def _batch_mode(
    message: str,
    mode: Optional[str],
    json_output: bool,
    con: Console,
) -> None:
    """Send a single message, print response, exit."""
    from hestia_cli.client import HestiaWSClient, ConnectionError, AuthenticationError
    from hestia_cli.models import ServerEventType
    from hestia_cli.renderer import HestiaRenderer

    client = HestiaWSClient()
    if mode:
        client.mode = mode

    try:
        await client.connect()
    except AuthenticationError as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            con.print(f"[red]Auth error: {e}[/red]", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as e:
        if json_output:
            print(json.dumps({"error": str(e)}))
        else:
            con.print(f"[red]{e}[/red]", file=sys.stderr)
        sys.exit(1)

    # Send repo context in batch mode too
    from hestia_cli.config import load_config
    from hestia_cli.context import get_repo_context
    config = load_config()
    auto_context = config.get("preferences", {}).get("auto_context", True)
    context_hints = get_repo_context() if auto_context else {}

    response_content = ""
    metrics = {}
    error_msg = None

    async for event in client.send_message(content=message, context_hints=context_hints):
        event_type = event.get("type")

        if event_type == ServerEventType.TOKEN:
            response_content += event.get("content", "")
        elif event_type == ServerEventType.DONE:
            metrics = event.get("metrics", {})
        elif event_type == ServerEventType.ERROR:
            error_msg = event.get("message", "Unknown error")
            break

    await client.disconnect()

    if error_msg:
        if json_output:
            print(json.dumps({"error": error_msg}))
        else:
            con.print(f"[red]Error: {error_msg}[/red]", file=sys.stderr)
        sys.exit(1)

    if json_output:
        print(json.dumps({
            "content": response_content,
            "metrics": metrics,
            "mode": client.mode,
        }))
    else:
        con.print(response_content)


# --- Auth subcommands ---


@auth_app.command("login")
def auth_login(
    server_url: Optional[str] = typer.Option(None, "--server", "-s", help="Server URL"),
    invite_token: Optional[str] = typer.Option(None, "--token", "-t", help="Invite token"),
):
    """Authenticate with Hestia server using an invite token."""
    asyncio.run(_auth_login_flow(server_url, invite_token))


async def _auth_login_flow(
    server_url: Optional[str],
    invite_token: Optional[str],
) -> None:
    from hestia_cli.auth import register_with_invite, check_connection
    from hestia_cli.config import load_config, save_config, get_server_url

    config = load_config()

    if not server_url:
        server_url = typer.prompt(
            "Server URL",
            default=get_server_url(config),
        )

    # Update config with server URL
    config["server"]["url"] = server_url
    save_config(config)

    if not invite_token:
        invite_token = typer.prompt("Invite token")

    console.print(f"\n  Registering with [cyan]{server_url}[/cyan]...")

    try:
        verify_ssl = config.get("server", {}).get("verify_ssl", False)
        token, device_id = await register_with_invite(
            server_url, invite_token, verify_ssl=verify_ssl
        )
        console.print(f"  [green]Authenticated![/green] Device: {device_id[:12]}...")

        # Test connection
        reachable = await check_connection(server_url, verify_ssl=verify_ssl)
        if reachable:
            console.print("  [green]Server reachable.[/green]")
        else:
            console.print("  [yellow]Warning: Server ping failed.[/yellow]")

        console.print("\n  Run [bold]hestia[/bold] to start chatting.\n")

    except Exception as e:
        console.print(f"\n  [red]Registration failed: {e}[/red]")
        console.print("  Check the invite token and server URL.\n")
        raise typer.Exit(1)


@auth_app.command("status")
def auth_status():
    """Check authentication status."""
    from hestia_cli.auth import get_stored_token, get_stored_device_id

    token = get_stored_token()
    device_id = get_stored_device_id()

    if token and device_id:
        console.print(f"  [green]Authenticated[/green]")
        console.print(f"  Device: {device_id[:12]}...")
        console.print(f"  Token:  {token[:20]}...")
    else:
        console.print("  [yellow]Not authenticated.[/yellow]")
        console.print("  Run 'hestia auth login' to authenticate.")


@auth_app.command("logout")
def auth_logout():
    """Clear stored credentials."""
    from hestia_cli.auth import clear_credentials

    clear_credentials()
    console.print("  [green]Credentials cleared.[/green]")


def main():
    """Entry point for the CLI.

    Pre-parses sys.argv to separate batch messages from subcommands,
    working around Click/Typer's inability to mix optional positional
    arguments with subcommands.
    """
    # Detect batch mode: first non-flag arg that isn't a subcommand
    # e.g. hestia "what time is it?" or hestia -m tia "hello"
    args = sys.argv[1:]
    batch_message = None
    cleaned_args: list[str] = []
    skip_next = False

    for i, arg in enumerate(args):
        if skip_next:
            skip_next = False
            cleaned_args.append(arg)
            continue
        # Options that take a value
        if arg in ("-m", "--mode"):
            cleaned_args.append(arg)
            skip_next = True
            continue
        # Flags
        if arg.startswith("-"):
            cleaned_args.append(arg)
            continue
        # Subcommands
        if arg in _SUBCOMMANDS:
            cleaned_args.append(arg)
            # Pass remaining args through unchanged
            cleaned_args.extend(args[i + 1:])
            break
        # First bare string = batch message
        if batch_message is None:
            batch_message = arg
        else:
            cleaned_args.append(arg)

    if batch_message:
        sys.argv = [sys.argv[0]] + cleaned_args
        # Stash message where the callback can find it
        _stashed_batch_message.append(batch_message)

    app()


# Thread-safe stash for batch message (populated before Typer runs)
_stashed_batch_message: list[str] = []
