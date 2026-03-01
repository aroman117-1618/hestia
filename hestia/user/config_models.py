"""
Data models for the markdown-based user profile configuration system.

The user has a single profile directory (data/user/) containing .md files
that define identity, values, environment, memory, and custom commands.
This mirrors the agent v2 config pattern (hestia/agents/config_models.py).

The markdown profile is separate from the SQLite UserProfile (user/models.py):
- SQLite: runtime settings (push notifications, quiet hours, auto-lock)
- Markdown: identity/context that shapes agent behavior
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone, date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class UserConfigFile(Enum):
    """Known .md config files in the user profile directory."""
    IDENTITY = "USER-IDENTITY.md"   # Name, avatar, timezone, job, contacts
    MIND = "MIND.md"                # Standards, morals, requirements
    TOOLS = "TOOLS.md"              # Machine-local: paths, SSH hosts, env quirks
    MEMORY = "MEMORY.md"            # Curated long-term memory (agent-maintained)
    BODY = "BODY.md"                # Health: meds, supplements, routines
    SPIRIT = "SPIRIT.md"            # Lore, philosophy, personal narrative
    VITALS = "VITALS.md"            # Recurring checklist (30-min eval)
    SETUP = "SETUP.md"              # One-time onboarding (archived after config)


# Always loaded into every request (core identity)
ALWAYS_LOAD_FILES = {
    UserConfigFile.IDENTITY,
    UserConfigFile.MIND,
    UserConfigFile.TOOLS,
}

# Loaded based on conversation topic (keyword detection)
TOPIC_LOAD_FILES = {
    UserConfigFile.BODY,      # health, medication, workout, supplement, sleep
    UserConfigFile.SPIRIT,    # philosophy, meaning, values, reflection, lore
    UserConfigFile.VITALS,    # checklist, vitals, status, check
}

# Agent can write autonomously
AGENT_WRITABLE_FILES = {UserConfigFile.MEMORY}

# User-only files (agent cannot modify)
USER_ONLY_FILES = {
    UserConfigFile.IDENTITY,
    UserConfigFile.MIND,
    UserConfigFile.TOOLS,
    UserConfigFile.BODY,
    UserConfigFile.SPIRIT,
    UserConfigFile.VITALS,
    UserConfigFile.SETUP,
}

# Required files for a valid user profile
REQUIRED_FILES = {UserConfigFile.IDENTITY}

# Topic keyword mapping for selective loading
TOPIC_KEYWORDS: Dict[UserConfigFile, List[str]] = {
    UserConfigFile.BODY: [
        "health", "medication", "medicine", "supplement", "workout",
        "exercise", "sleep", "weight", "diet", "nutrition", "fitness",
        "heart rate", "steps", "calories", "blood pressure",
    ],
    UserConfigFile.SPIRIT: [
        "philosophy", "meaning", "values", "reflection", "lore",
        "purpose", "belief", "wisdom", "spiritual", "growth",
        "mindfulness", "meditation", "journal",
    ],
    UserConfigFile.VITALS: [
        "checklist", "vitals", "status check", "how am i doing",
        "daily check", "routine check",
    ],
}

# Files that should NOT be sent to cloud providers (PII safety)
LOCAL_ONLY_FILES = {
    UserConfigFile.IDENTITY,
    UserConfigFile.BODY,
}


@dataclass
class UserIdentity:
    """
    Parsed from USER-IDENTITY.md.

    Contains the user's name, role, timezone, and key contacts.
    """
    name: str
    timezone: str = ""
    job: str = ""
    avatar_path: Optional[str] = None
    contacts: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        """Validate identity fields."""
        errors = []
        if not self.name or len(self.name) > 100:
            errors.append("Name must be 1-100 characters")
        return errors


@dataclass
class UserConfig:
    """
    Complete user profile loaded from data/user/ directory.

    Mirrors AgentConfig pattern from agents/config_models.py.
    """
    directory_path: Path
    config_version: str = "1.0"

    # Parsed from USER-IDENTITY.md
    identity: UserIdentity = field(default_factory=lambda: UserIdentity(name=""))

    # Raw .md file contents
    identity_md: str = ""       # USER-IDENTITY.md
    mind_md: str = ""           # MIND.md - standards, values
    tools_md: str = ""          # TOOLS.md - machine-local config
    memory_md: str = ""         # MEMORY.md - curated long-term memory
    body_md: str = ""           # BODY.md - health context
    spirit_md: str = ""         # SPIRIT.md - philosophy/lore
    vitals_md: str = ""         # VITALS.md - recurring checklist
    setup_md: str = ""          # SETUP.md - onboarding interview

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def name(self) -> str:
        """User display name."""
        return self.identity.name or "User"

    @property
    def has_setup(self) -> bool:
        """Whether onboarding is pending (SETUP.md exists with content)."""
        return bool(self.setup_md.strip())

    @property
    def context_block(self) -> str:
        """
        Assemble user profile context for injection into prompts.

        Only includes always-load files. Topic files are added separately
        by the PromptBuilder based on keyword detection.
        """
        parts = []

        if self.identity_md.strip():
            parts.append(f"## User Profile\n\n{self.identity_md.strip()}")

        if self.mind_md.strip():
            parts.append(f"## User Standards & Values\n\n{self.mind_md.strip()}")

        if self.tools_md.strip():
            parts.append(f"## User Environment\n\n{self.tools_md.strip()}")

        return "\n\n".join(parts) if parts else ""

    def get_topic_context(self, topic_files: List[UserConfigFile]) -> str:
        """Get context for topic-specific files."""
        parts = []
        for f in topic_files:
            content = self.get_file_content(f)
            if content.strip():
                label = f.value.replace(".md", "").replace("-", " ").title()
                parts.append(f"## {label}\n\n{content.strip()}")
        return "\n\n".join(parts) if parts else ""

    def get_cloud_safe_context(self) -> str:
        """
        Context block with PII-sensitive files excluded.

        Used when routing to cloud providers (Anthropic/OpenAI/Google).
        Excludes USER-IDENTITY.md and BODY.md.
        """
        parts = []
        if self.mind_md.strip():
            parts.append(f"## User Standards & Values\n\n{self.mind_md.strip()}")
        if self.tools_md.strip():
            parts.append(f"## User Environment\n\n{self.tools_md.strip()}")
        return "\n\n".join(parts) if parts else ""

    def get_file_content(self, config_file: UserConfigFile) -> str:
        """Get the raw content of a specific config file."""
        field_map = {
            UserConfigFile.IDENTITY: "identity_md",
            UserConfigFile.MIND: "mind_md",
            UserConfigFile.TOOLS: "tools_md",
            UserConfigFile.MEMORY: "memory_md",
            UserConfigFile.BODY: "body_md",
            UserConfigFile.SPIRIT: "spirit_md",
            UserConfigFile.VITALS: "vitals_md",
            UserConfigFile.SETUP: "setup_md",
        }
        attr = field_map.get(config_file, "")
        return getattr(self, attr, "")

    def validate(self) -> List[str]:
        """Validate the user configuration."""
        errors = self.identity.validate()
        if not self.identity_md.strip():
            errors.append("USER-IDENTITY.md must have content")
        return errors

    @property
    def is_valid(self) -> bool:
        return len(self.validate()) == 0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses."""
        return {
            "name": self.name,
            "identity": {
                "name": self.identity.name,
                "timezone": self.identity.timezone,
                "job": self.identity.job,
                "avatar_path": self.identity.avatar_path,
                "contacts": self.identity.contacts,
            },
            "has_setup": self.has_setup,
            "config_version": self.config_version,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "files": {
                f.value: bool(self.get_file_content(f).strip())
                for f in UserConfigFile
            },
        }


@dataclass
class UserCommand:
    """A single user command parsed from commands/ directory."""
    name: str                           # Command name (filename without .md)
    file_path: Path                     # Absolute path to command file
    system_instructions: str = ""       # System instructions section
    resources: List[str] = field(default_factory=list)  # MCP resource hints
    raw_content: str = ""               # Full file content
    description: str = ""               # Brief description

    def expand(self, arguments: str = "") -> str:
        """Expand command template with arguments."""
        return self.raw_content.replace("$ARGUMENTS", arguments)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API responses."""
        return {
            "name": self.name,
            "description": self.description,
            "resources": self.resources,
            "has_system_instructions": bool(self.system_instructions),
        }


@dataclass
class DailyNote:
    """A single daily note entry for the user."""
    date: date
    content: str

    @property
    def filename(self) -> str:
        return f"{self.date.isoformat()}.md"

    @property
    def relative_path(self) -> str:
        return f"memory/{self.filename}"
