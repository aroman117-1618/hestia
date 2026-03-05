"""
Zero-friction bootstrap for Hestia CLI.

Ensures the server is running and the CLI is authenticated before
entering the REPL or batch mode. Auto-start and auto-register are
restricted to localhost connections for security.
"""

import asyncio
import os
import socket
import subprocess
import sys
from urllib.parse import urlparse
from typing import Optional

import httpx
from rich.console import Console

from hestia_cli.auth import get_stored_token, store_credentials
from hestia_cli.config import load_config


def _is_localhost(server_url: str) -> bool:
    """Check if the server URL points to localhost."""
    parsed = urlparse(server_url)
    hostname = parsed.hostname or ""
    return hostname in {"localhost", "127.0.0.1", "::1"}


async def _ping_server(server_url: str, verify_ssl: bool, timeout: float = 2.0) -> bool:
    """Check if the Hestia server is reachable via /v1/ping."""
    try:
        async with httpx.AsyncClient(verify=verify_ssl, timeout=timeout) as client:
            resp = await client.get(f"{server_url}/v1/ping")
            return resp.status_code == 200
    except Exception:
        return False


def _start_server_launchd() -> bool:
    """Try to start the server via launchd. Returns True if kickstarted."""
    service_label = "com.hestia.server"
    uid = os.getuid()

    # Check if service is loaded
    try:
        result = subprocess.run(
            ["launchctl", "list", service_label],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            # Service loaded — kickstart it
            kick = subprocess.run(
                ["launchctl", "kickstart", f"gui/{uid}/{service_label}"],
                capture_output=True, timeout=5,
            )
            return kick.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Try to load plist if it exists
    plist_path = os.path.expanduser(f"~/Library/LaunchAgents/{service_label}.plist")
    if os.path.exists(plist_path):
        try:
            subprocess.run(
                ["launchctl", "load", plist_path],
                capture_output=True, timeout=5,
            )
            return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return False


def _start_server_subprocess() -> bool:
    """Start the server as a detached subprocess. Returns True if spawned."""
    # Resolve Python from the same venv as the CLI
    python_path = sys.executable

    log_dir = os.path.expanduser("~/.hestia")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "server.log")

    try:
        with open(log_file, "a") as log_f:
            subprocess.Popen(
                [python_path, "-m", "hestia.api.server"],
                stdout=log_f,
                stderr=log_f,
                start_new_session=True,
            )
        return True
    except Exception:
        return False


async def ensure_server_running(
    server_url: str,
    verify_ssl: bool,
    console: Console,
    auto_start: bool = True,
) -> bool:
    """
    Ensure the Hestia server is reachable.

    For localhost: attempts auto-start via launchd or subprocess.
    For remote: just checks reachability.

    Returns True if the server is reachable.
    """
    # Quick check — already running?
    if await _ping_server(server_url, verify_ssl):
        return True

    localhost = _is_localhost(server_url)

    if not localhost:
        console.print(f"[red]Server not reachable at {server_url}[/red]")
        console.print("[dim]Check that the server is running on your Mac Mini.[/dim]")
        return False

    if not auto_start:
        console.print(f"[red]Server not reachable at {server_url}[/red]")
        console.print("[dim]Start the server or set auto_start: true in ~/.hestia/config.yaml[/dim]")
        return False

    # Try launchd first, then subprocess fallback
    with console.status("[bold cyan]Starting Hestia server...", spinner="dots"):
        started = _start_server_launchd()
        if not started:
            started = _start_server_subprocess()

        if not started:
            console.print("[red]Failed to start server.[/red]")
            console.print("[dim]Start manually: python -m hestia.api.server[/dim]")
            return False

        # Poll until healthy (up to 14s)
        for i in range(7):  # 7 * 2s = 14s max
            await asyncio.sleep(2)
            if await _ping_server(server_url, verify_ssl):
                elapsed = (i + 1) * 2
                console.print(f"  [green]Server ready[/green] [dim]({elapsed}s)[/dim]")
                return True

    console.print("[red]Server did not become healthy within 14s.[/red]")
    console.print("[dim]Check ~/.hestia/server.log for details.[/dim]")
    return False


async def ensure_authenticated(
    server_url: str,
    verify_ssl: bool,
    console: Console,
) -> bool:
    """
    Ensure the CLI has stored credentials.

    For localhost: auto-registers via /v1/auth/register if no token found.
    For remote: requires explicit 'hestia auth login'.

    Returns True if authenticated.
    """
    if get_stored_token():
        return True

    localhost = _is_localhost(server_url)

    if not localhost:
        console.print("[yellow]Not authenticated.[/yellow]")
        console.print("[dim]Run 'hestia auth login' to authenticate with the remote server.[/dim]")
        return False

    # Auto-register on localhost
    device_name = f"cli-{socket.gethostname()[:40]}"
    try:
        async with httpx.AsyncClient(verify=verify_ssl, timeout=10.0) as client:
            resp = await client.post(
                f"{server_url}/v1/auth/register",
                json={
                    "device_name": device_name,
                    "device_type": "cli",
                },
            )

            if resp.status_code == 403:
                console.print("[yellow]Server requires invite-based registration.[/yellow]")
                console.print("[dim]Run 'hestia auth login --token <invite>' or disable HESTIA_REQUIRE_INVITE on the server.[/dim]")
                return False

            resp.raise_for_status()
            data = resp.json()

        token = data.get("token")
        device_id = data.get("device_id")
        if not token or not device_id:
            console.print("[red]Registration failed: unexpected server response.[/red]")
            return False
        store_credentials(token, device_id)
        console.print(f"  [green]Registered![/green] Device: {device_id[:12]}...")
        return True

    except httpx.HTTPStatusError as e:
        console.print(f"[red]Registration failed: HTTP {e.response.status_code}[/red]")
        return False
    except Exception as e:
        console.print(f"[red]Registration failed: {type(e).__name__}[/red]")
        return False
