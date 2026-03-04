"""
User profile configuration loader.

Reads and caches user profile from data/user/ directory.
Mirrors the agent v2 ConfigLoader pattern (agents/config_loader.py).
"""

import asyncio
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from hestia.logging import get_logger
from hestia.user.config_models import (
    DailyNote,
    UserCommand,
    UserConfig,
    UserConfigFile,
    UserIdentity,
)
from hestia.user.templates import COMMAND_TEMPLATES, USER_TEMPLATES

logger = get_logger()


class UserConfigLoader:
    """
    Reads and caches user profile configuration from data/user/.

    Singleton via get_user_config_loader(). Thread-safe with asyncio.Lock.
    """

    def __init__(self, user_root: Optional[Path] = None) -> None:
        self._user_root = user_root or Path("data/user")
        self._cache: Optional[UserConfig] = None
        self._commands_cache: Dict[str, UserCommand] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    @property
    def user_root(self) -> Path:
        return self._user_root

    async def initialize(self) -> None:
        """Ensure user profile directory exists with default files."""
        async with self._lock:
            if self._initialized:
                return

            self._user_root.mkdir(parents=True, exist_ok=True)
            (self._user_root / "memory").mkdir(exist_ok=True)
            (self._user_root / "commands").mkdir(exist_ok=True)

            # Scaffold default files if missing
            for config_file, content in USER_TEMPLATES.items():
                file_path = self._user_root / config_file.value
                if not file_path.exists() and content.strip():
                    file_path.write_text(content, encoding="utf-8")
                    logger.info(f"Scaffolded {config_file.value}")

            # Scaffold default commands if commands/ is empty
            commands_dir = self._user_root / "commands"
            existing_commands = list(commands_dir.glob("*.md"))
            if not existing_commands:
                for name, content in COMMAND_TEMPLATES.items():
                    cmd_path = commands_dir / f"{name}.md"
                    cmd_path.write_text(content, encoding="utf-8")
                    logger.info(f"Scaffolded command: {name}")

            # Create metadata file if missing
            meta_path = self._user_root / ".user-meta.yaml"
            if not meta_path.exists():
                meta = {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "config_version": "1.0",
                }
                meta_path.write_text(yaml.dump(meta), encoding="utf-8")

            self._initialized = True
            logger.info("User profile directory initialized")

    async def load(self, force_reload: bool = False) -> UserConfig:
        """
        Load user profile from disk.

        Returns cached version unless force_reload=True.
        """
        if self._cache is not None and not force_reload:
            return self._cache

        async with self._lock:
            # Double-check after acquiring lock
            if self._cache is not None and not force_reload:
                return self._cache

            config = await self._read_user_directory()
            self._cache = config
            return config

    async def _read_user_directory(self) -> UserConfig:
        """Read all .md files from user profile directory."""
        file_contents: Dict[UserConfigFile, str] = {}

        for config_file in UserConfigFile:
            file_path = self._user_root / config_file.value
            if file_path.exists():
                try:
                    file_contents[config_file] = file_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Failed to read {file_path}: {type(e).__name__}")
                    file_contents[config_file] = ""
            else:
                file_contents[config_file] = ""

        # Parse identity from USER-IDENTITY.md
        identity = self._parse_identity_md(
            file_contents.get(UserConfigFile.IDENTITY, "")
        )

        # Get timestamps
        meta_path = self._user_root / ".user-meta.yaml"
        created_at = datetime.now(timezone.utc)
        if meta_path.exists():
            try:
                meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
                if meta.get("created_at"):
                    created_at = datetime.fromisoformat(meta["created_at"])
            except Exception:
                pass

        # Updated at = most recent file mtime
        updated_at = created_at
        for config_file in UserConfigFile:
            file_path = self._user_root / config_file.value
            if file_path.exists():
                mtime = datetime.fromtimestamp(
                    file_path.stat().st_mtime, tz=timezone.utc
                )
                if mtime > updated_at:
                    updated_at = mtime

        return UserConfig(
            directory_path=self._user_root,
            identity=identity,
            identity_md=file_contents.get(UserConfigFile.IDENTITY, ""),
            mind_md=file_contents.get(UserConfigFile.MIND, ""),
            tools_md=file_contents.get(UserConfigFile.TOOLS, ""),
            memory_md=file_contents.get(UserConfigFile.MEMORY, ""),
            body_md=file_contents.get(UserConfigFile.BODY, ""),
            spirit_md=file_contents.get(UserConfigFile.SPIRIT, ""),
            vitals_md=file_contents.get(UserConfigFile.VITALS, ""),
            setup_md=file_contents.get(UserConfigFile.SETUP, ""),
            created_at=created_at,
            updated_at=updated_at,
        )

    def _parse_identity_md(self, content: str) -> UserIdentity:
        """Parse USER-IDENTITY.md into UserIdentity."""
        if not content.strip():
            return UserIdentity(name="User")

        # Parse name from # heading
        name_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        name = name_match.group(1).strip() if name_match else "User"

        # Parse key-value fields
        def extract(pattern: str) -> str:
            m = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
            return m.group(1).strip() if m else ""

        timezone_val = extract(r'\*\*Timezone:\*\*\s*(.+)')
        job = extract(r'\*\*Job:\*\*\s*(.+)')
        avatar = extract(r'\*\*Avatar:\*\*\s*(.+)')

        # Parse contacts from ## Top Contacts section
        contacts: List[str] = []
        contacts_match = re.search(
            r'##\s+Top\s+Contacts\s*\n((?:- .+\n?)+)',
            content, re.MULTILINE | re.IGNORECASE
        )
        if contacts_match:
            for line in contacts_match.group(1).strip().split("\n"):
                line = line.strip().lstrip("- ").strip()
                if line and not line.startswith("("):
                    contacts.append(line)

        return UserIdentity(
            name=name,
            timezone=timezone_val,
            job=job,
            avatar_path=avatar if avatar and not avatar.startswith("(") else None,
            contacts=contacts,
        )

    # ─── Commands ────────────────────────────────

    async def load_commands(self, force_reload: bool = False) -> Dict[str, UserCommand]:
        """Load all commands from commands/ directory."""
        if self._commands_cache and not force_reload:
            return self._commands_cache

        commands_dir = self._user_root / "commands"
        if not commands_dir.exists():
            return {}

        commands: Dict[str, UserCommand] = {}
        for cmd_path in sorted(commands_dir.glob("*.md")):
            try:
                cmd = self._parse_command(cmd_path)
                commands[cmd.name] = cmd
            except Exception as e:
                logger.warning(f"Failed to parse command {cmd_path.name}: {type(e).__name__}")

        self._commands_cache = commands
        return commands

    def _parse_command(self, path: Path) -> UserCommand:
        """Parse a command .md file."""
        content = path.read_text(encoding="utf-8")
        name = path.stem  # filename without .md

        # Extract description (first non-heading, non-empty line)
        description = ""
        for line in content.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("##"):
                description = line
                break

        # Extract ## System Instructions section
        system_instructions = self._extract_section(content, "System Instructions")

        # Extract ## Resources section
        resources_text = self._extract_section(content, "Resources")
        resources = [
            r.strip() for r in resources_text.split(",")
            if r.strip()
        ] if resources_text else []

        return UserCommand(
            name=name,
            file_path=path,
            system_instructions=system_instructions,
            resources=resources,
            raw_content=content,
            description=description,
        )

    def _extract_section(self, content: str, heading: str) -> str:
        """Extract content under a ## heading until the next ## or end of file."""
        pattern = rf'##\s+{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        return match.group(1).strip() if match else ""

    async def get_command(self, name: str) -> Optional[UserCommand]:
        """Get a single command by name."""
        commands = await self.load_commands()
        return commands.get(name)

    # ─── Daily Notes ─────────────────────────────

    async def list_daily_notes(self, limit: int = 30) -> List[DailyNote]:
        """List daily notes, most recent first."""
        memory_dir = self._user_root / "memory"
        if not memory_dir.exists():
            return []

        notes: List[DailyNote] = []
        for path in sorted(memory_dir.glob("*.md"), reverse=True):
            try:
                from datetime import date as date_type
                note_date = date_type.fromisoformat(path.stem)
                content = path.read_text(encoding="utf-8")
                notes.append(DailyNote(date=note_date, content=content))
            except (ValueError, OSError):
                continue

            if len(notes) >= limit:
                break

        return notes

    async def get_daily_note(self, note_date: Any) -> Optional[DailyNote]:
        """Get a specific daily note by date."""
        path = self._user_root / "memory" / f"{note_date.isoformat()}.md"
        if not path.exists():
            return None

        content = path.read_text(encoding="utf-8")
        return DailyNote(date=note_date, content=content)

    # ─── Cache Management ────────────────────────

    def invalidate_cache(self) -> None:
        """Clear cached user profile."""
        self._cache = None

    def invalidate_commands_cache(self) -> None:
        """Clear cached commands."""
        self._commands_cache = {}


# ─── Module-Level Singleton ──────────────────────

_loader_instance: Optional[UserConfigLoader] = None


async def get_user_config_loader(
    user_root: Optional[Path] = None,
) -> UserConfigLoader:
    """Get or create the UserConfigLoader singleton."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = UserConfigLoader(user_root=user_root)
        await _loader_instance.initialize()
    return _loader_instance


def get_user_timezone() -> str:
    """
    Get the user's IANA timezone string.

    Reads from UserSettings.timezone (persisted in DB), falling back to
    the system's local timezone if not set.

    Returns:
        IANA timezone string (e.g., "America/Los_Angeles").
    """
    # Default — matches UserSettings.timezone default
    default_tz = "America/Los_Angeles"

    try:
        # Try to read from the loaded user config cache
        # This is synchronous because timezone is needed in sync contexts too
        # (e.g., APScheduler timezone param)
        if _loader_instance is not None and _loader_instance._cache is not None:
            identity = _loader_instance._cache.identity
            if identity and identity.timezone:
                return identity.timezone
    except Exception:
        pass

    return default_tz
