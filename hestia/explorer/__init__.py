"""
Explorer module — unified resource aggregation across Apple ecosystem.

Aggregates mail, notes, reminders, files, and Hestia drafts into a single
searchable, filterable resource view.
"""

from .models import (
    ExplorerResource,
    ResourceType,
    ResourceSource,
    ResourceFlag,
)
from .manager import ExplorerManager, get_explorer_manager, close_explorer_manager

__all__ = [
    "ExplorerResource",
    "ResourceType",
    "ResourceSource",
    "ResourceFlag",
    "ExplorerManager",
    "get_explorer_manager",
    "close_explorer_manager",
]
