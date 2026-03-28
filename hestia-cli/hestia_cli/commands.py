"""
Slash command handlers for the REPL.

Minimal command set — natural language first, commands for control flow.
"""

import os
import subprocess
from typing import Dict, Optional, Tuple

import httpx
from rich.console import Console

from hestia_cli.auth import get_stored_token
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
        "/trust": _cmd_trust,
        "/memory": _cmd_memory,
        "/tools": _cmd_tools,
        "/cloud": _cmd_cloud,
        "/code": _cmd_code,
        "/dev": _cmd_dev,
        "/config": _cmd_config,
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
  /help                     Show this help
  /status                   Server health and connection info
  /mode [name]              Switch persona (tia, mira, olly)
  /trust                    Show current tool trust tiers
  /trust [tier] [level]     Set tier (e.g. /trust read auto)
  /trust save               Persist tiers to backend
  /trust reset              Reset to defaults
  /memory search [query]    Search Hestia memory
  /tools                    List available tools from the server
  /cloud                    Show cloud providers and routing state
  /cloud state [provider] [disabled|smart|full]
                            Set cloud routing state for a provider
  /code [task]              Start agentic coding session (iterative tool loop)
  /dev                      Show agentic dev session help
  /dev <task>               Create a new dev session
  /dev queue                List all dev sessions
  /dev proposals            List sessions awaiting approval
  /dev approve <id>         Approve a proposed session
  /dev cancel <id>          Cancel a session
  /dev status <id>          Show session detail
  /dev log <id>             Show session event log
  /config                   Open config in $EDITOR
  /session new              Start a fresh session
  /clear                    Clear the screen
  /exit                     Quit

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
    if client.trust_tiers:
        tiers = " ".join(f"{k}={v}" for k, v in client.trust_tiers.items())
        console.print(f"  Trust:  {tiers}")


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


async def _cmd_trust(args: str, client: HestiaWSClient, console: Console) -> None:
    """View or modify tool trust tiers."""
    VALID_TIERS = ("read", "write", "execute", "external")
    VALID_LEVELS = ("auto", "prompt")

    parts = args.strip().lower().split()

    if not parts:
        # Show current tiers
        tiers = client.trust_tiers or {"read": "auto", "write": "prompt", "execute": "prompt", "external": "prompt"}
        console.print("[bold]Tool Trust Tiers[/bold]")
        for tier in VALID_TIERS:
            level = tiers.get(tier, "prompt")
            color = "green" if level == "auto" else "yellow"
            console.print(f"  {tier:10s} [{color}]{level}[/{color}]")
        return

    if parts[0] == "reset":
        client.trust_tiers = {"read": "auto", "write": "prompt", "execute": "prompt", "external": "prompt"}
        console.print("[dim]Trust tiers reset to defaults (not saved — use /trust save).[/dim]")
        return

    if parts[0] == "save":
        # Persist to backend via PUT /v1/user/settings
        token = get_stored_token()
        if not token:
            console.print("[red]No auth token. Run 'hestia auth login' first.[/red]")
            return
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as http:
                response = await http.put(
                    f"{client.server_url}/v1/user/settings",
                    headers={"X-Hestia-Device-Token": token},
                    json={"tool_trust_tiers": client.trust_tiers},
                )
                if response.status_code == 200:
                    console.print("[green]Trust tiers saved to backend.[/green]")
                else:
                    console.print(f"[red]Failed to save: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]Save failed: {type(e).__name__}[/red]")
        return

    if len(parts) >= 2:
        tier_name = parts[0]
        level = parts[1]

        if tier_name not in VALID_TIERS:
            console.print(f"[red]Invalid tier: {tier_name}. Choose from: {', '.join(VALID_TIERS)}[/red]")
            return
        if level not in VALID_LEVELS:
            console.print(f"[red]Invalid level: {level}. Choose from: {', '.join(VALID_LEVELS)}[/red]")
            return

        if not client.trust_tiers:
            client.trust_tiers = {"read": "auto", "write": "prompt", "execute": "prompt", "external": "prompt"}
        client.trust_tiers[tier_name] = level
        color = "green" if level == "auto" else "yellow"
        console.print(f"  {tier_name} → [{color}]{level}[/{color}] [dim](session only — /trust save to persist)[/dim]")
        return

    console.print("[yellow]Usage: /trust, /trust [tier] [auto|prompt], /trust save, /trust reset[/yellow]")


async def _cmd_memory(args: str, client: HestiaWSClient, console: Console) -> None:
    """Search Hestia memory."""
    parts = args.strip().split(None, 1)
    action = parts[0].lower() if parts else ""
    query = parts[1] if len(parts) > 1 else ""

    if action != "search" or not query:
        console.print("[yellow]Usage: /memory search [query][/yellow]")
        return

    token = get_stored_token()
    if not token:
        console.print("[red]Not authenticated.[/red]")
        return

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as http:
            response = await http.post(
                f"{client.server_url}/v1/memory/search",
                headers={"X-Hestia-Device-Token": token},
                json={"query": query, "limit": 5},
            )
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                if not results:
                    console.print("[dim]  No memories found.[/dim]")
                    return
                console.print(f"\n[bold]Memory Search: {query}[/bold]")
                for i, r in enumerate(results, 1):
                    content = r.get("content", "")[:120]
                    score = r.get("score", 0)
                    console.print(f"  {i}. [dim]({score:.2f})[/dim] {content}")
                console.print()
            else:
                console.print(f"[red]Memory search failed: {response.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Memory search failed: {type(e).__name__}[/red]")


async def _cmd_tools(args: str, client: HestiaWSClient, console: Console) -> None:
    """List available tools from the server."""
    token = get_stored_token()
    if not token:
        console.print("[red]Not authenticated.[/red]")
        return

    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as http:
            response = await http.get(
                f"{client.server_url}/v1/tools",
                headers={"X-Hestia-Device-Token": token},
            )
            if response.status_code == 200:
                data = response.json()
                tools = data.get("tools", [])
                if not tools:
                    console.print("[dim]  No tools registered.[/dim]")
                    return

                # Group by category
                by_category: Dict[str, list] = {}
                for tool in tools:
                    cat = tool.get("category", "general")
                    by_category.setdefault(cat, []).append(tool)

                console.print(f"\n[bold]Available Tools[/bold] ({len(tools)} total)\n")
                for cat in sorted(by_category.keys()):
                    console.print(f"  [bold]{cat}[/bold]")
                    for tool in sorted(by_category[cat], key=lambda t: t["name"]):
                        name = tool["name"]
                        desc = tool.get("description", "")[:60]
                        approval = " [yellow]⚠ approval[/yellow]" if tool.get("requires_approval") else ""
                        console.print(f"    {name:30s} {desc}{approval}")
                    console.print()
            else:
                console.print(f"[red]Failed to fetch tools: {response.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Failed to fetch tools: {type(e).__name__}[/red]")


async def _cmd_cloud(args: str, client: HestiaWSClient, console: Console) -> None:
    """View and manage cloud LLM providers."""
    STATE_ALIASES = {
        "disabled": "disabled",
        "off": "disabled",
        "smart": "enabled_smart",
        "hybrid": "enabled_smart",
        "full": "enabled_full",
        "on": "enabled_full",
    }
    STATE_DISPLAY = {
        "disabled": ("[dim]disabled[/dim]", "gray"),
        "enabled_smart": ("[yellow]smart hybrid[/yellow]", "yellow"),
        "enabled_full": ("[green]full cloud[/green]", "green"),
    }

    token = get_stored_token()
    if not token:
        console.print("[red]Not authenticated.[/red]")
        return

    parts = args.strip().lower().split()

    if parts and parts[0] == "state" and len(parts) >= 3:
        # /cloud state <provider> <state>
        provider_name = parts[1]
        state_input = parts[2]

        valid_providers = ("anthropic", "openai", "google")
        if provider_name not in valid_providers:
            console.print(f"[red]Invalid provider: {provider_name}. Choose from: {', '.join(valid_providers)}[/red]")
            return

        api_state = STATE_ALIASES.get(state_input)
        if not api_state:
            console.print(f"[red]Invalid state: {state_input}. Choose from: disabled, smart, full[/red]")
            return

        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as http:
                response = await http.patch(
                    f"{client.server_url}/v1/cloud/providers/{provider_name}/state",
                    headers={"X-Hestia-Device-Token": token},
                    json={"state": api_state},
                )
                if response.status_code == 200:
                    display, _ = STATE_DISPLAY.get(api_state, (api_state, "white"))
                    console.print(f"  {provider_name} → {display}")
                elif response.status_code == 404:
                    console.print(f"[red]Provider '{provider_name}' is not configured. Add it via the iOS/macOS app first.[/red]")
                else:
                    console.print(f"[red]Failed to update state: {response.status_code}[/red]")
        except Exception as e:
            console.print(f"[red]Cloud state update failed: {type(e).__name__}[/red]")
        return

    # Default: list providers
    try:
        async with httpx.AsyncClient(verify=False, timeout=10.0) as http:
            response = await http.get(
                f"{client.server_url}/v1/cloud/providers",
                headers={"X-Hestia-Device-Token": token},
            )
            if response.status_code == 200:
                data = response.json()
                providers = data.get("providers", [])
                cloud_state = data.get("cloud_state", "disabled")
                effective_display, _ = STATE_DISPLAY.get(cloud_state, (cloud_state, "white"))

                console.print(f"\n[bold]Cloud LLM Routing[/bold]  (effective: {effective_display})\n")

                if not providers:
                    console.print("  [dim]No cloud providers configured.[/dim]")
                    console.print("  [dim]Add providers via the iOS or macOS app.[/dim]\n")
                    return

                for p in providers:
                    name = p.get("provider", "unknown")
                    state = p.get("state", "disabled")
                    model = p.get("active_model_id") or "default"
                    health = p.get("health_status", "unknown")
                    has_key = p.get("has_api_key", False)

                    display, color = STATE_DISPLAY.get(state, (state, "white"))
                    health_color = "green" if health == "healthy" else "yellow" if health == "unknown" else "red"
                    key_indicator = "key" if has_key else "[red]no key[/red]"

                    console.print(f"  [bold]{name:12s}[/bold] {display:30s} model={model}  [{health_color}]{health}[/{health_color}]  {key_indicator}")

                console.print(f"\n  [dim]Change state: /cloud state <provider> <disabled|smart|full>[/dim]\n")
            else:
                console.print(f"[red]Failed to fetch cloud providers: {response.status_code}[/red]")
    except Exception as e:
        console.print(f"[red]Cloud query failed: {type(e).__name__}[/red]")


async def _cmd_code(args: str, client: HestiaWSClient, console: Console) -> None:
    """Start an agentic coding session via /v1/chat/agentic SSE endpoint.

    Usage: /code fix the typo in hestia/memory/manager.py
    """
    if not args.strip():
        console.print("[yellow]Usage: /code <task description>[/yellow]")
        console.print("[dim]Example: /code fix the failing test in test_memory.py[/dim]")
        return

    from hestia_cli.auth import get_stored_token
    from rich.panel import Panel

    token = get_stored_token()
    if not token:
        console.print("[red]Not authenticated. Run 'hestia setup' first.[/red]")
        return

    console.print(Panel(
        f"[bold]Agentic coding session[/bold]\n[dim]{args}[/dim]",
        border_style="bright_cyan",
        width=60,
    ))

    try:
        from hestia_cli.config import load_config
        config = load_config()
        base_url = config.get("server_url", "https://localhost:8443")

        # Stream SSE events from the agentic endpoint
        import json
        async with httpx.AsyncClient(verify=False, timeout=httpx.Timeout(300.0)) as http:
            async with http.stream(
                "POST",
                f"{base_url}/v1/chat/agentic",
                json={"message": args, "mode": "tia"},
                headers={"X-Hestia-Device-Token": token, "Accept": "text/event-stream"},
            ) as response:
                if response.status_code != 200:
                    console.print(f"[red]Server returned {response.status_code}[/red]")
                    return

                current_event = ""
                current_data = ""
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        current_event = line[7:]
                    elif line.startswith("data: "):
                        current_data = line[6:]
                    elif line == "":
                        if current_data:
                            try:
                                event = json.loads(current_data)
                                _render_agentic_event(event, console)
                            except json.JSONDecodeError:
                                pass
                        current_event = ""
                        current_data = ""

    except httpx.ConnectError:
        console.print("[red]Cannot connect to server. Is it running?[/red]")
    except Exception as e:
        console.print(f"[red]Agentic session failed: {type(e).__name__}[/red]")


def _render_agentic_event(event: Dict, console: Console) -> None:
    """Render a single agentic SSE event in the CLI."""
    from rich.panel import Panel

    event_type = event.get("type", "")

    if event_type == "status":
        stage = event.get("stage", "")
        detail = event.get("detail", "")
        console.print(f"[dim]  [{stage}] {detail}[/dim]")

    elif event_type == "token":
        content = event.get("content", "")
        console.print(content, end="")

    elif event_type == "tool_start":
        tool = event.get("tool_name", "?")
        iteration = event.get("iteration", "?")
        console.print(f"\n[bright_cyan]  [Tool] {tool}[/bright_cyan] [dim](iteration {iteration})[/dim]")

    elif event_type == "tool_result":
        tool = event.get("tool_name", "?")
        status = event.get("status", "?")
        output = event.get("output", "")
        icon = "[green]OK[/green]" if status == "success" else f"[red]{status}[/red]"
        console.print(f"  [Tool] {tool} → {icon}")
        if output and len(output) < 200:
            console.print(f"    [dim]{output[:200]}[/dim]")

    elif event_type == "agentic_done":
        iterations = event.get("iterations", 0)
        duration = event.get("duration_ms", 0)
        console.print(f"\n[bold green]  Agentic session complete[/bold green]")
        console.print(f"  [dim]{iterations} iterations, {duration:.0f}ms[/dim]\n")

    elif event_type == "error":
        msg = event.get("message", "Unknown error")
        console.print(f"\n[red]  Error: {msg}[/red]")


async def _cmd_dev(args: str, client: HestiaWSClient, console: Console) -> None:
    """Manage agentic dev sessions."""
    token = get_stored_token()
    if not token:
        console.print("[red]Not authenticated. Run 'hestia setup' first.[/red]")
        return

    # Derive base_url from the ws:// client URL
    raw_url = str(client._base_url) if hasattr(client, "_base_url") else client.server_url
    base_url = raw_url.replace("ws://", "https://").replace("wss://", "https://").rstrip("/")
    headers = {"X-Hestia-Device-Token": token}

    parts = args.strip().split(None, 1)
    sub = parts[0].lower() if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""

    # /dev — show help
    if not sub:
        console.print("""
[bold]Dev Session Commands[/bold]
  /dev <task>           Create a new agentic dev session
  /dev queue            List all sessions
  /dev proposals        List sessions awaiting approval
  /dev approve <id>     Approve a proposed session
  /dev cancel <id>      Cancel a session
  /dev status <id>      Show session detail
  /dev log <id>         Show session event log
""")
        return

    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as http:

            # /dev queue — list all sessions
            if sub == "queue":
                resp = await http.get(f"{base_url}/v1/dev/sessions", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    sessions = data.get("sessions", [])
                    if not sessions:
                        console.print("[dim]  No dev sessions.[/dim]")
                        return
                    console.print(f"\n[bold]Dev Sessions[/bold] ({len(sessions)} total)\n")
                    for s in sessions:
                        sid = s.get("id", "?")[:12]
                        state = s.get("state", "?")
                        title = s.get("title", "?")[:50]
                        console.print(f"  {sid}  [{_state_color(state)}]{state:<12}[/{_state_color(state)}]  {title}")
                    console.print()
                else:
                    console.print(f"[red]Failed to list sessions: {resp.status_code}[/red]")
                return

            # /dev proposals — list pending proposals
            if sub == "proposals":
                resp = await http.get(f"{base_url}/v1/dev/proposals", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    proposals = data.get("proposals", [])
                    if not proposals:
                        console.print("[dim]  No pending proposals.[/dim]")
                        return
                    console.print(f"\n[bold]Pending Proposals[/bold] ({len(proposals)} total)\n")
                    for s in proposals:
                        sid = s.get("id", "?")[:12]
                        title = s.get("title", "?")[:50]
                        plan = s.get("plan_summary", "")[:80]
                        console.print(f"  {sid}  {title}")
                        if plan:
                            console.print(f"           [dim]{plan}[/dim]")
                    console.print()
                else:
                    console.print(f"[red]Failed to list proposals: {resp.status_code}[/red]")
                return

            # /dev approve <id>
            if sub == "approve":
                if not rest:
                    console.print("[yellow]Usage: /dev approve <session-id>[/yellow]")
                    return
                resp = await http.post(f"{base_url}/v1/dev/sessions/{rest}/approve", headers=headers)
                if resp.status_code == 200:
                    console.print(f"[green]Session {rest[:12]} approved — executing.[/green]")
                else:
                    console.print(f"[red]Approve failed: {resp.status_code}[/red]")
                return

            # /dev cancel <id>
            if sub == "cancel":
                if not rest:
                    console.print("[yellow]Usage: /dev cancel <session-id>[/yellow]")
                    return
                resp = await http.post(f"{base_url}/v1/dev/sessions/{rest}/cancel", headers=headers)
                if resp.status_code == 200:
                    console.print(f"[yellow]Session {rest[:12]} cancelled.[/yellow]")
                else:
                    console.print(f"[red]Cancel failed: {resp.status_code}[/red]")
                return

            # /dev status <id>
            if sub == "status":
                if not rest:
                    console.print("[yellow]Usage: /dev status <session-id>[/yellow]")
                    return
                resp = await http.get(f"{base_url}/v1/dev/sessions/{rest}", headers=headers)
                if resp.status_code == 200:
                    s = resp.json()
                    state = s.get("state", "?")
                    console.print(f"\n[bold]{s.get('title', '?')}[/bold]")
                    console.print(f"  ID:          {s.get('id', '?')}")
                    console.print(f"  State:       [{_state_color(state)}]{state}[/{_state_color(state)}]")
                    console.print(f"  Source:      {s.get('source', '?')}")
                    console.print(f"  Created:     {s.get('created_at', '?')}")
                    if s.get("approved_by"):
                        console.print(f"  Approved by: {s['approved_by']}")
                    if s.get("completed_at"):
                        console.print(f"  Completed:   {s['completed_at']}")
                    if s.get("description"):
                        console.print(f"  Description: {s['description'][:120]}")
                    console.print()
                elif resp.status_code == 404:
                    console.print(f"[red]Session not found: {rest}[/red]")
                else:
                    console.print(f"[red]Status fetch failed: {resp.status_code}[/red]")
                return

            # /dev log <id>
            if sub == "log":
                if not rest:
                    console.print("[yellow]Usage: /dev log <session-id>[/yellow]")
                    return
                resp = await http.get(f"{base_url}/v1/dev/sessions/{rest}/events", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    events = data.get("events", [])
                    if not events:
                        console.print("[dim]  No events recorded.[/dim]")
                        return
                    console.print(f"\n[bold]Event Log[/bold] ({len(events)} events)\n")
                    for ev in events:
                        ts = ev.get("created_at", "?")[:19]
                        tier = ev.get("agent_tier", "?")
                        etype = ev.get("event_type", "?")
                        files = ev.get("files_affected", [])
                        files_str = f"  [dim]files: {', '.join(files[:3])}[/dim]" if files else ""
                        console.print(f"  {ts}  [dim]{tier:12s}[/dim]  {etype}{files_str}")
                    console.print()
                elif resp.status_code == 404:
                    console.print(f"[red]Session not found: {rest}[/red]")
                else:
                    console.print(f"[red]Log fetch failed: {resp.status_code}[/red]")
                return

            # /dev <task> — create a new session (sub is the first word of the task)
            task_text = (sub + (" " + rest if rest else "")).strip()
            resp = await http.post(
                f"{base_url}/v1/dev/sessions",
                headers=headers,
                json={"title": task_text, "description": task_text, "source": "cli"},
            )
            if resp.status_code in (200, 201):
                s = resp.json()
                sid = s.get("id", "?")
                console.print(f"[green]Dev session created:[/green] {sid[:12]}  [dim]{task_text[:60]}[/dim]")
                console.print(f"[dim]  Use '/dev status {sid[:12]}' to check progress.[/dim]")
            else:
                console.print(f"[red]Failed to create session: {resp.status_code}[/red]")

    except httpx.ConnectError:
        console.print("[red]Cannot connect to server. Is it running?[/red]")
    except Exception as e:
        console.print(f"[red]Dev command failed: {type(e).__name__}[/red]")


def _state_color(state: str) -> str:
    """Return a Rich color name for a dev session state."""
    mapping = {
        "queued": "dim",
        "planning": "cyan",
        "researching": "cyan",
        "proposed": "yellow",
        "executing": "bright_cyan",
        "validating": "blue",
        "reviewing": "magenta",
        "blocked": "red",
        "failed": "red",
        "complete": "green",
        "cancelled": "dim",
    }
    return mapping.get(state.lower(), "white")


async def _cmd_config(args: str, client: HestiaWSClient, console: Console) -> None:
    """Open config file in $EDITOR."""
    from hestia_cli.config import get_config_path

    config_path = get_config_path()
    editor = os.environ.get("EDITOR", "nano")

    console.print(f"[dim]  Opening {config_path} in {editor}...[/dim]")
    try:
        subprocess.call([editor, str(config_path)])
    except FileNotFoundError:
        console.print(f"[red]Editor not found: {editor}. Set $EDITOR environment variable.[/red]")


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
