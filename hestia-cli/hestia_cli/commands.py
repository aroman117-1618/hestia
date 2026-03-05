"""
Slash command handlers for the REPL.

Minimal command set — natural language first, commands for control flow.
"""

from typing import Optional, Tuple

from rich.console import Console

from hestia_cli.client import HestiaWSClient


async def handle_slash_command(
    raw_input: str,
    client: HestiaWSClient,
    console: Console,
) -> bool:
    """
    Process a slash command. Returns True if handled, False otherwise.
    """
    parts = raw_input.strip().split(None, 1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    handlers = {
        "/help": _cmd_help,
        "/status": _cmd_status,
        "/mode": _cmd_mode,
        "/session": _cmd_session,
        "/clear": _cmd_clear,
        "/exit": _cmd_exit,
        "/quit": _cmd_exit,
    }

    handler = handlers.get(command)
    if handler:
        await handler(args, client, console)
        return True

    console.print(f"[yellow]Unknown command: {command}. Type /help for available commands.[/yellow]")
    return True


async def _cmd_help(args: str, client: HestiaWSClient, console: Console) -> None:
    """Show available commands."""
    console.print("""
[bold]Commands[/bold]
  /help              Show this help
  /status            Server health and connection info
  /mode [name]       Switch persona (tia, mira, olly)
  /session new       Start a fresh session
  /clear             Clear the screen
  /exit              Quit

[bold]Shortcuts[/bold]
  @mira [message]    Send as Mira persona
  @olly [message]    Send as Olly persona
  Ctrl+C             Cancel current generation
  Ctrl+D             Exit
""")


async def _cmd_status(args: str, client: HestiaWSClient, console: Console) -> None:
    """Show connection and server status."""
    connected = "connected" if client.connected else "disconnected"
    color = "green" if client.connected else "red"
    console.print(f"  Server: [{color}]{connected}[/{color}] ({client.server_url})")
    console.print(f"  Device: {client.device_id or 'unknown'}")
    console.print(f"  Mode:   @{client.mode}")
    if client._session_id:
        console.print(f"  Session: {client._session_id[:12]}...")


async def _cmd_mode(args: str, client: HestiaWSClient, console: Console) -> None:
    """Switch persona mode."""
    valid_modes = ("tia", "mira", "olly")
    mode = args.strip().lower()

    if not mode:
        console.print(f"  Current mode: [yellow]@{client.mode}[/yellow]")
        console.print(f"  Available: {', '.join(valid_modes)}")
        return

    if mode not in valid_modes:
        console.print(f"[red]Invalid mode: {mode}. Choose from: {', '.join(valid_modes)}[/red]")
        return

    client.mode = mode
    console.print(f"  Switched to [yellow]@{mode}[/yellow]")


async def _cmd_session(args: str, client: HestiaWSClient, console: Console) -> None:
    """Session management."""
    if args.strip().lower() == "new":
        client._session_id = None
        console.print("  Started new session.")
    else:
        if client._session_id:
            console.print(f"  Session: {client._session_id}")
        else:
            console.print("  No active session.")


async def _cmd_clear(args: str, client: HestiaWSClient, console: Console) -> None:
    """Clear the terminal."""
    console.clear()


async def _cmd_exit(args: str, client: HestiaWSClient, console: Console) -> None:
    """Signal exit — handled by REPL loop."""
    raise SystemExit(0)


def detect_mode_prefix(content: str) -> Tuple[Optional[str], str]:
    """
    Detect @mode prefix in message content.

    Returns (mode_or_none, cleaned_content).
    """
    prefixes = {"@tia": "tia", "@mira": "mira", "@olly": "olly"}
    for prefix, mode in prefixes.items():
        if content.lower().startswith(prefix):
            remainder = content[len(prefix):].strip()
            if remainder:
                return mode, remainder
    return None, content
