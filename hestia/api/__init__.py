"""
Hestia API module - FastAPI REST endpoints.

Provides HTTP interface to Hestia's capabilities:
- Chat conversation
- Mode management
- Memory search and approval
- Session management
- Tool listing

Usage:
    python -m hestia.api.server

Or programmatically:
    from hestia.api.server import app, run_server
"""

from hestia.api.server import app, run_server

__all__ = ["app", "run_server"]
