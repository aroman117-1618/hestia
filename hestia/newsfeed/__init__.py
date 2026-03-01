"""
Newsfeed module — unified timeline for the Command Center.

Aggregates items from orders, memory, tasks, health, and calendar
into a materialized cache with per-user read/dismiss state.
"""

from .models import (
    NewsfeedItem,
    NewsfeedItemType,
    NewsfeedItemSource,
    NewsfeedItemPriority,
)
from .manager import NewsfeedManager, get_newsfeed_manager, close_newsfeed_manager

__all__ = [
    "NewsfeedItem",
    "NewsfeedItemType",
    "NewsfeedItemSource",
    "NewsfeedItemPriority",
    "NewsfeedManager",
    "get_newsfeed_manager",
    "close_newsfeed_manager",
]
