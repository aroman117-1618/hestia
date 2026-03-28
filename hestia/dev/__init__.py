"""Hestia Agentic Development System."""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hestia.dev.manager import DevSessionManager

_manager: DevSessionManager | None = None


async def get_dev_session_manager() -> DevSessionManager:
    global _manager
    if _manager is None:
        from hestia.dev.manager import DevSessionManager
        _manager = DevSessionManager()
        await _manager.initialize()
    return _manager
