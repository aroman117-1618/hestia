"""
Agent Profiles module for persona customization.

Provides CRUD operations for agent profiles with snapshot/restore capability.
Supports 3 agent slots (Tia, Mira, Olly).
"""

from .models import (
    AgentProfile,
    AgentSnapshot,
    SnapshotReason,
    DEFAULT_AGENTS,
)
from .database import AgentDatabase, get_agent_database, close_agent_database
from .manager import AgentManager, get_agent_manager, close_agent_manager

__all__ = [
    # Models
    "AgentProfile",
    "AgentSnapshot",
    "SnapshotReason",
    "DEFAULT_AGENTS",
    # Database
    "AgentDatabase",
    "get_agent_database",
    "close_agent_database",
    # Manager
    "AgentManager",
    "get_agent_manager",
    "close_agent_manager",
]
