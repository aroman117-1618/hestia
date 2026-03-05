"""
Status line rendering for REPL prompt.

Builds the dynamic prompt string showing mode and connection state.
"""

from hestia_cli.client import HestiaWSClient


def build_prompt(client: HestiaWSClient) -> str:
    """Build the REPL prompt string."""
    mode = client.mode
    if client.connected:
        return f"[@{mode}] > "
    else:
        return f"[@{mode}|disconnected] > "
