"""
Data models for the .md-based agent configuration system.

Each agent has a directory of .md files that define its identity,
personality, rules, tools, memory, and lifecycle hooks. This module
defines the data structures for loading, validating, and working
with those configurations.

Designed to coexist with the legacy SQLite-backed AgentProfile system
during migration. The v2 API uses these models; the v1 API continues
using models.py.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


class AgentConfigFile(Enum):
    """Known .md config files in an agent directory."""
    AGENT = "AGENT.md"          # Operating rules, priorities, safety, quality bar
    ANIMA = "ANIMA.md"          # Personality, voice, values, behavioral constraints
    USER = "USER.md"            # User preferences, timezone, communication style
    IDENTITY = "IDENTITY.md"    # Name, emoji, vibe, avatar, gradient colors
    TOOLS = "TOOLS.md"          # Machine-local notes: paths, SSH hosts, environment
    HEARTBEAT = "HEARTBEAT.md"  # Recurring 30-min checklist
    BOOT = "BOOT.md"            # Startup ritual on restart
    MEMORY = "MEMORY.md"        # Curated long-term memory (agent-maintained)
    BOOTSTRAP = "BOOTSTRAP.md"  # One-time onboarding interview (deleted after setup)


# Files the agent can write to autonomously (no confirmation needed)
AGENT_WRITABLE_FILES = {AgentConfigFile.MEMORY}

# Files that require user confirmation before the agent modifies them
AGENT_CONFIRM_FILES = {AgentConfigFile.ANIMA, AgentConfigFile.AGENT, AgentConfigFile.USER, AgentConfigFile.IDENTITY}

# Files that are user-controlled only (agent cannot modify)
USER_ONLY_FILES = {AgentConfigFile.HEARTBEAT, AgentConfigFile.BOOT, AgentConfigFile.TOOLS, AgentConfigFile.BOOTSTRAP}

# Required files for a valid agent directory
REQUIRED_FILES = {AgentConfigFile.IDENTITY, AgentConfigFile.ANIMA, AgentConfigFile.AGENT}


@dataclass
class AgentIdentity:
    """
    Parsed from IDENTITY.md.

    Contains the agent's name, visual identity, and display properties.
    These are extracted from YAML frontmatter in the .md file.
    """
    name: str
    full_name: str = ""
    emoji: str = ""
    vibe: str = ""                     # Short personality descriptor
    avatar_path: Optional[str] = None  # Relative path to avatar image
    gradient_color_1: str = "808080"   # 6-char hex, no #
    gradient_color_2: str = "404040"   # 6-char hex, no #
    invoke_pattern: str = ""           # Regex for @-mention detection
    temperature: float = 0.0           # Default inference temperature

    def validate(self) -> List[str]:
        """Validate identity fields."""
        errors = []
        if not self.name or len(self.name) > 50:
            errors.append("Name must be 1-50 characters")
        if self.gradient_color_1 and not re.match(r'^[0-9A-Fa-f]{6}$', self.gradient_color_1):
            errors.append("gradient_color_1 must be 6 hex characters")
        if self.gradient_color_2 and not re.match(r'^[0-9A-Fa-f]{6}$', self.gradient_color_2):
            errors.append("gradient_color_2 must be 6 hex characters")
        return errors


@dataclass
class AgentConfig:
    """
    Complete agent configuration loaded from a directory of .md files.

    This is the unified representation of all agent config files.
    The ConfigLoader populates this from disk; the ConfigWriter
    persists changes back.
    """
    # Directory identity
    directory_name: str          # Folder name (e.g., "tia")
    directory_path: Path         # Absolute path to agent directory
    config_version: str = "1.0"  # For future schema migrations

    # Parsed from IDENTITY.md
    identity: AgentIdentity = field(default_factory=lambda: AgentIdentity(name=""))

    # Raw .md file contents (loaded on demand or eagerly)
    agent_md: str = ""       # AGENT.md - operating rules
    anima_md: str = ""       # ANIMA.md - personality
    user_md: str = ""        # USER.md - user preferences
    tools_md: str = ""       # TOOLS.md - machine-local config
    heartbeat_md: str = ""   # HEARTBEAT.md - recurring checklist
    boot_md: str = ""        # BOOT.md - startup ritual
    memory_md: str = ""      # MEMORY.md - curated long-term memory
    bootstrap_md: str = ""   # BOOTSTRAP.md - onboarding interview

    # Metadata
    is_default: bool = False  # One of the built-in agents (Tia/Mira/Olly)
    is_archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Cached state
    _files_loaded: bool = field(default=False, repr=False)

    @property
    def name(self) -> str:
        """Agent display name from identity."""
        return self.identity.name or self.directory_name

    @property
    def has_bootstrap(self) -> bool:
        """Whether onboarding is pending (BOOTSTRAP.md exists)."""
        return bool(self.bootstrap_md.strip())

    @property
    def system_prompt(self) -> str:
        """
        Assemble the full system prompt from config files.

        Order: AGENT.md (rules) → ANIMA.md (personality) → USER.md (preferences)
        """
        parts = []

        if self.anima_md.strip():
            parts.append(self.anima_md.strip())

        if self.agent_md.strip():
            parts.append(f"\n## Operating Rules\n\n{self.agent_md.strip()}")

        if self.user_md.strip():
            parts.append(f"\n## User Context\n\n{self.user_md.strip()}")

        if self.tools_md.strip():
            parts.append(f"\n## Environment\n\n{self.tools_md.strip()}")

        if self.memory_md.strip():
            parts.append(f"\n## Long-Term Memory\n\n{self.memory_md.strip()}")

        return "\n".join(parts) if parts else f"You are {self.name}, a personal AI assistant."

    def validate(self) -> List[str]:
        """Validate the complete agent configuration."""
        errors = self.identity.validate()

        if not self.directory_name:
            errors.append("directory_name is required")

        if not self.anima_md.strip() and not self.agent_md.strip():
            errors.append("At least ANIMA.md or AGENT.md must have content")

        return errors

    @property
    def is_valid(self) -> bool:
        """Check if configuration is valid."""
        return len(self.validate()) == 0

    def get_file_content(self, config_file: AgentConfigFile) -> str:
        """Get the raw content of a specific config file."""
        field_map = {
            AgentConfigFile.AGENT: "agent_md",
            AgentConfigFile.ANIMA: "anima_md",
            AgentConfigFile.USER: "user_md",
            AgentConfigFile.IDENTITY: "_identity_raw",  # Special case
            AgentConfigFile.TOOLS: "tools_md",
            AgentConfigFile.HEARTBEAT: "heartbeat_md",
            AgentConfigFile.BOOT: "boot_md",
            AgentConfigFile.MEMORY: "memory_md",
            AgentConfigFile.BOOTSTRAP: "bootstrap_md",
        }
        attr = field_map.get(config_file, "")
        if attr == "_identity_raw":
            return self._render_identity_md()
        return getattr(self, attr, "")

    def _render_identity_md(self) -> str:
        """Render IDENTITY.md content from the identity dataclass."""
        lines = [
            f"# {self.identity.name}",
            "",
        ]
        if self.identity.full_name:
            lines.append(f"**Full Name:** {self.identity.full_name}")
        if self.identity.emoji:
            lines.append(f"**Emoji:** {self.identity.emoji}")
        if self.identity.vibe:
            lines.append(f"**Vibe:** {self.identity.vibe}")
        if self.identity.avatar_path:
            lines.append(f"**Avatar:** {self.identity.avatar_path}")
        lines.append(f"**Gradient:** #{self.identity.gradient_color_1} → #{self.identity.gradient_color_2}")
        if self.identity.invoke_pattern:
            lines.append(f"**Invoke:** `{self.identity.invoke_pattern}`")
        lines.append(f"**Temperature:** {self.identity.temperature}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            "directory_name": self.directory_name,
            "name": self.name,
            "identity": {
                "name": self.identity.name,
                "full_name": self.identity.full_name,
                "emoji": self.identity.emoji,
                "vibe": self.identity.vibe,
                "avatar_path": self.identity.avatar_path,
                "gradient_color_1": self.identity.gradient_color_1,
                "gradient_color_2": self.identity.gradient_color_2,
                "invoke_pattern": self.identity.invoke_pattern,
                "temperature": self.identity.temperature,
            },
            "is_default": self.is_default,
            "is_archived": self.is_archived,
            "has_bootstrap": self.has_bootstrap,
            "config_version": self.config_version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "files": {
                f.value: bool(self.get_file_content(f).strip())
                for f in AgentConfigFile
            },
        }

    def to_legacy_profile(self, slot_index: int = -1) -> "AgentProfile":
        """
        Convert to legacy AgentProfile for v1 API compatibility.

        Args:
            slot_index: Slot index for legacy system (-1 if not mapped).
        """
        from hestia.agents.models import AgentProfile
        return AgentProfile(
            id=f"agent-{self.directory_name}",
            slot_index=slot_index,
            name=self.identity.name,
            instructions=self.system_prompt,
            gradient_color_1=self.identity.gradient_color_1,
            gradient_color_2=self.identity.gradient_color_2,
            is_default=self.is_default,
            photo_path=self.identity.avatar_path,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


@dataclass
class AgentRegistry:
    """
    Registry of all known agents, loaded from .hestia-agents.yaml.

    Tracks the agent list, default agent, and sync metadata.
    """
    default_agent: str = "tia"
    agents: List[str] = field(default_factory=list)  # Directory names
    last_sync: Optional[datetime] = None
    registry_version: str = "1.0"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "default_agent": self.default_agent,
            "agents": self.agents,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "registry_version": self.registry_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentRegistry":
        """Create from dictionary."""
        return cls(
            default_agent=data.get("default_agent", "tia"),
            agents=data.get("agents", []),
            last_sync=datetime.fromisoformat(data["last_sync"]) if data.get("last_sync") else None,
            registry_version=data.get("registry_version", "1.0"),
        )


@dataclass
class DailyNote:
    """A single daily note entry for an agent."""
    date: date
    content: str
    agent_name: str

    @property
    def filename(self) -> str:
        """Generate the filename for this daily note."""
        return f"{self.date.isoformat()}.md"

    @property
    def relative_path(self) -> str:
        """Relative path within agent directory."""
        return f"memory/{self.filename}"
