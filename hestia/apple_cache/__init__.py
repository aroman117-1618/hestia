"""
Apple metadata cache -- FTS5-backed local cache for Apple ecosystem entities.

Enables instant fuzzy title resolution for Notes, Calendar, and Reminders
without requiring slow multi-step AppleScript/EventKit tool chains.
"""

from .models import CachedEntity, EntitySource, ResolvedMatch
from .manager import get_apple_cache_manager, close_apple_cache_manager

__all__ = [
    "CachedEntity",
    "EntitySource",
    "ResolvedMatch",
    "get_apple_cache_manager",
    "close_apple_cache_manager",
]
