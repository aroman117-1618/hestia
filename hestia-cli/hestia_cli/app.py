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
import os
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


_SUBCOMMANDS = {"auth", "setup"}


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

    # Support HESTIA_NO_COLOR or NO_COLOR env vars
    env_no_color = os.environ.get("HESTIA_NO_COLOR") or os.environ.get("NO_COLOR")
    if no_color or env_no_color:
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

    # Bootstrap: ensure server is running and we're authenticated
    from hestia_cli.bootstrap import ensure_server_running, ensure_authenticated
    from hestia_cli.config import load_config
    from hestia_cli.context import get_repo_context
    config = load_config()
    auto_start = config.get("server", {}).get("auto_start", True)
    server_ok = await ensure_server_running(client.server_url, client.verify_ssl, con, auto_start=auto_start)
    if not server_ok:
        sys.exit(1)
    auth_ok = await ensure_authenticated(client.server_url, client.verify_ssl, con)
    if not auth_ok:
        sys.exit(1)

    try:
        await client.connect()
    except AuthenticationError:
        if json_output:
            print(json.dumps({"error": "authentication_failed"}))
        else:
            con.print("[red]Authentication failed.[/red]", file=sys.stderr)
        sys.exit(1)
    except ConnectionError:
        if json_output:
            print(json.dumps({"error": "connection_failed"}))
        else:
            con.print(f"[red]Cannot connect to server at {client.server_url}[/red]", file=sys.stderr)
        sys.exit(1)

    # Send repo context in batch mode too
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
        console.print(f"\n  [red]Registration failed: {type(e).__name__}[/red]")
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


setup_app = typer.Typer(help="Setup and service management commands.")
app.add_typer(setup_app, name="setup")


@setup_app.callback(invoke_without_command=True)
def setup_default(ctx: typer.Context):
    """Run full setup: start server, register CLI device."""
    if ctx.invoked_subcommand is not None:
        return
    asyncio.run(_setup_full())


async def _setup_full() -> None:
    """Full setup: ensure server running + ensure authenticated."""
    from hestia_cli.bootstrap import ensure_server_running, ensure_authenticated
    from hestia_cli.config import load_config as _load_config, get_server_url, get_verify_ssl

    config = _load_config()
    server_url = get_server_url(config)
    verify_ssl = get_verify_ssl(config)

    server_ok = await ensure_server_running(server_url, verify_ssl, console, auto_start=True)
    if not server_ok:
        raise typer.Exit(1)

    auth_ok = await ensure_authenticated(server_url, verify_ssl, console)
    if not auth_ok:
        raise typer.Exit(1)

    console.print("\n  [green]Setup complete![/green] Run [bold]hestia[/bold] to start chatting.\n")


@setup_app.command("install-service")
def setup_install_service():
    """Install the Hestia server as a launchd service."""
    import shutil

    plist_name = "com.hestia.server.plist"
    # Look for plist in repo scripts/
    source_candidates = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", plist_name),
    ]
    source = None
    for candidate in source_candidates:
        if os.path.exists(candidate):
            source = candidate
            break

    if not source:
        console.print(f"[red]Cannot find {plist_name} in scripts/[/red]")
        raise typer.Exit(1)

    dest_dir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, plist_name)

    shutil.copy2(source, dest)
    console.print(f"  Installed [cyan]{dest}[/cyan]")

    import subprocess as sp
    sp.run(["launchctl", "load", dest], capture_output=True)
    console.print("  [green]Service loaded.[/green] Server will auto-start on login.")


@setup_app.command("status")
def setup_status():
    """Show server and authentication status."""
    asyncio.run(_setup_status())


async def _setup_status() -> None:
    from hestia_cli.auth import get_stored_token, get_stored_device_id
    from hestia_cli.bootstrap import _ping_server, _is_localhost
    from hestia_cli.config import load_config as _load_config, get_server_url, get_verify_ssl

    config = _load_config()
    server_url = get_server_url(config)
    verify_ssl = get_verify_ssl(config)

    console.print(f"\n  Server: [cyan]{server_url}[/cyan]")
    console.print(f"  Local:  {'yes' if _is_localhost(server_url) else 'no'}")

    reachable = await _ping_server(server_url, verify_ssl)
    if reachable:
        console.print("  Status: [green]running[/green]")
    else:
        console.print("  Status: [red]not reachable[/red]")

    token = get_stored_token()
    device_id = get_stored_device_id()
    if token and device_id:
        console.print(f"  Auth:   [green]authenticated[/green] (device: {device_id[:12]}...)")
    else:
        console.print("  Auth:   [yellow]not authenticated[/yellow]")
    console.print()


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
