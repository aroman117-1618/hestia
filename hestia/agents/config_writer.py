"""
Agent configuration writer for the .md-based config system.

Handles writing and updating agent config files with:
- Atomic writes (write to temp, then rename) for safety
- Permission enforcement (agent-writable vs user-only files)
- Daily note creation and appending
- MEMORY.md curation
"""

import asyncio
import os
import tempfile
from datetime import datetime, timezone, date
from pathlib import Path
from typing import Optional

from hestia.agents.config_models import (
    AgentConfig,
    AgentConfigFile,
    AgentIdentity,
    AGENT_WRITABLE_FILES,
    AGENT_CONFIRM_FILES,
    USER_ONLY_FILES,
    DailyNote,
)
from hestia.logging import get_logger, LogComponent

logger = get_logger()


class ConfigWriteError(Exception):
    """Raised when a config write fails."""
    pass


class ConfigPermissionError(ConfigWriteError):
    """Raised when trying to write to a file without permission."""
    pass


class ConfigWriter:
    """
    Writes agent configuration files to disk.

    Supports three permission levels:
    - Agent-writable: MEMORY.md, daily notes (no confirmation needed)
    - Confirmation required: ANIMA.md, AGENT.md, USER.md, IDENTITY.md
    - User-only: HEARTBEAT.md, BOOT.md, TOOLS.md, BOOTSTRAP.md

    All writes use atomic file operations (write temp → rename)
    to prevent corruption from interrupted writes.
    """

    def __init__(self, config_loader: "ConfigLoader"):
        """
        Initialize the writer with a reference to the loader for cache invalidation.

        Args:
            config_loader: The ConfigLoader instance to invalidate after writes.
        """
        self.config_loader = config_loader

    def _atomic_write(self, path: Path, content: str) -> None:
        """
        Write content to a file atomically.

        Writes to a temporary file in the same directory, then renames.
        This ensures the file is never in a partially-written state.
        """
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)

        # Write to temp file in same directory (same filesystem for rename)
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(content)
            # Atomic rename
            os.replace(tmp_path, str(path))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    # ─────────────────────────────────────────────
    # Config File Writing
    # ─────────────────────────────────────────────

    async def write_config_file(
        self,
        agent_name: str,
        config_file: AgentConfigFile,
        content: str,
        source: str = "user",
        confirmed: bool = False,
    ) -> None:
        """
        Write a config file for an agent.

        Args:
            agent_name: Directory name of the agent.
            config_file: Which config file to write.
            content: New content for the file.
            source: Who is writing ("user", "agent", "system").
            confirmed: Whether the user has confirmed this write
                       (required for AGENT_CONFIRM_FILES when source="agent").

        Raises:
            ConfigPermissionError: If the write is not permitted.
            ConfigWriteError: If the write fails.
        """
        # Permission check
        if source == "agent":
            if config_file in USER_ONLY_FILES:
                raise ConfigPermissionError(
                    f"Agent cannot modify {config_file.value} — this is a user-only file"
                )
            if config_file in AGENT_CONFIRM_FILES and not confirmed:
                raise ConfigPermissionError(
                    f"Agent modification of {config_file.value} requires user confirmation"
                )

        # Resolve path
        agent_dir = self.config_loader.agents_root / agent_name
        if not agent_dir.is_dir():
            raise ConfigWriteError(f"Agent directory not found: {agent_name}")

        file_path = agent_dir / config_file.value

        try:
            await asyncio.to_thread(self._atomic_write, file_path, content)
            logger.info(
                f"Wrote {config_file.value} for agent '{agent_name}' "
                f"(source={source}, {len(content)} chars)"
            )
        except Exception as e:
            raise ConfigWriteError(f"Failed to write {config_file.value}: {e}") from e

        # Invalidate cache so next read picks up changes
        self.config_loader.invalidate_cache(agent_name)

    async def update_identity(
        self,
        agent_name: str,
        identity: AgentIdentity,
        source: str = "user",
        confirmed: bool = False,
    ) -> None:
        """
        Update an agent's IDENTITY.md from an AgentIdentity object.

        Args:
            agent_name: Directory name of the agent.
            identity: The new identity to write.
            source: Who is writing.
            confirmed: Whether user has confirmed (if source="agent").
        """
        # Render identity to markdown format
        lines = [
            f"# {identity.name}",
            "",
        ]
        if identity.full_name:
            lines.append(f"**Full Name:** {identity.full_name}")
        if identity.emoji:
            lines.append(f"**Emoji:** {identity.emoji}")
        if identity.vibe:
            lines.append(f"**Vibe:** {identity.vibe}")
        if identity.avatar_path:
            lines.append(f"**Avatar:** {identity.avatar_path}")
        lines.append(f"**Gradient:** #{identity.gradient_color_1} → #{identity.gradient_color_2}")
        if identity.invoke_pattern:
            lines.append(f"**Invoke:** `{identity.invoke_pattern}`")
        lines.append(f"**Temperature:** {identity.temperature}")
        lines.append("")

        content = "\n".join(lines)
        await self.write_config_file(
            agent_name, AgentConfigFile.IDENTITY, content,
            source=source, confirmed=confirmed,
        )

    # ─────────────────────────────────────────────
    # Daily Notes
    # ─────────────────────────────────────────────

    async def write_daily_note(
        self,
        agent_name: str,
        content: str,
        note_date: Optional[date] = None,
    ) -> DailyNote:
        """
        Write or overwrite a daily note for an agent.

        Args:
            agent_name: Directory name of the agent.
            content: Full content for the daily note.
            note_date: Date for the note (defaults to today).

        Returns:
            The created DailyNote.
        """
        note_date = note_date or date.today()
        note = DailyNote(date=note_date, content=content, agent_name=agent_name)

        # Ensure memory directory exists
        memory_dir = self.config_loader.agents_root / agent_name / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        file_path = memory_dir / note.filename
        await asyncio.to_thread(self._atomic_write, file_path, content)

        logger.info(f"Wrote daily note for '{agent_name}': {note.filename}")
        return note

    async def append_daily_note(
        self,
        agent_name: str,
        entry: str,
        note_date: Optional[date] = None,
    ) -> DailyNote:
        """
        Append an entry to today's daily note (creates if doesn't exist).

        Args:
            agent_name: Directory name of the agent.
            entry: Text to append.
            note_date: Date for the note (defaults to today).

        Returns:
            The updated DailyNote.
        """
        note_date = note_date or date.today()
        memory_dir = self.config_loader.agents_root / agent_name / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{note_date.isoformat()}.md"
        file_path = memory_dir / filename

        # Read existing content or create header
        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
        else:
            existing = f"# Daily Notes — {note_date.isoformat()}\n\n"

        # Append with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%H:%M UTC")
        new_content = f"{existing}\n### {timestamp}\n\n{entry}\n"

        await asyncio.to_thread(self._atomic_write, file_path, new_content)

        logger.info(f"Appended to daily note for '{agent_name}': {filename}")
        return DailyNote(date=note_date, content=new_content, agent_name=agent_name)

    async def read_daily_note(
        self,
        agent_name: str,
        note_date: Optional[date] = None,
    ) -> Optional[DailyNote]:
        """
        Read a daily note for an agent.

        Args:
            agent_name: Directory name of the agent.
            note_date: Date to read (defaults to today).

        Returns:
            DailyNote if exists, None otherwise.
        """
        note_date = note_date or date.today()
        filename = f"{note_date.isoformat()}.md"
        file_path = self.config_loader.agents_root / agent_name / "memory" / filename

        if not file_path.exists():
            return None

        content = file_path.read_text(encoding="utf-8")
        return DailyNote(date=note_date, content=content, agent_name=agent_name)

    async def list_daily_notes(
        self,
        agent_name: str,
        limit: int = 30,
    ) -> list[DailyNote]:
        """
        List recent daily notes for an agent.

        Args:
            agent_name: Directory name of the agent.
            limit: Maximum notes to return.

        Returns:
            List of DailyNote objects, most recent first.
        """
        memory_dir = self.config_loader.agents_root / agent_name / "memory"
        if not memory_dir.exists():
            return []

        notes = []
        for f in sorted(memory_dir.iterdir(), reverse=True):
            if f.suffix == ".md" and f.stem != "":
                try:
                    note_date = date.fromisoformat(f.stem)
                    content = f.read_text(encoding="utf-8")
                    notes.append(DailyNote(date=note_date, content=content, agent_name=agent_name))
                except ValueError:
                    continue  # Skip files that don't match YYYY-MM-DD.md

            if len(notes) >= limit:
                break

        return notes

    # ─────────────────────────────────────────────
    # MEMORY.md Helpers
    # ─────────────────────────────────────────────

    async def append_memory(
        self,
        agent_name: str,
        entry: str,
    ) -> None:
        """
        Append an entry to an agent's MEMORY.md.

        This is an agent-writable operation (no confirmation needed).

        Args:
            agent_name: Directory name of the agent.
            entry: Text to append to long-term memory.
        """
        agent_dir = self.config_loader.agents_root / agent_name
        memory_path = agent_dir / AgentConfigFile.MEMORY.value

        # Read existing content
        if memory_path.exists():
            existing = memory_path.read_text(encoding="utf-8")
        else:
            existing = f"## Long-Term Memory\n\n*Maintained by {agent_name}.*\n\n---\n"

        # Append with date stamp
        date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_content = f"{existing}\n### {date_stamp}\n\n{entry}\n"

        await asyncio.to_thread(self._atomic_write, memory_path, new_content)
        self.config_loader.invalidate_cache(agent_name)

        logger.info(f"Appended to MEMORY.md for '{agent_name}' ({len(entry)} chars)")

    # ─────────────────────────────────────────────
    # Bootstrap
    # ─────────────────────────────────────────────

    async def complete_bootstrap(self, agent_name: str) -> None:
        """
        Mark onboarding as complete by removing BOOTSTRAP.md.

        Args:
            agent_name: Directory name of the agent.
        """
        bootstrap_path = self.config_loader.agents_root / agent_name / AgentConfigFile.BOOTSTRAP.value
        if bootstrap_path.exists():
            bootstrap_path.unlink()
            self.config_loader.invalidate_cache(agent_name)
            logger.info(f"Completed bootstrap for agent '{agent_name}'")


# ─────────────────────────────────────────────
# Module-level factory
# ─────────────────────────────────────────────

_config_writer: Optional[ConfigWriter] = None


async def get_config_writer() -> ConfigWriter:
    """Get or create the singleton ConfigWriter."""
    global _config_writer
    if _config_writer is None:
        from hestia.agents.config_loader import get_config_loader
        loader = await get_config_loader()
        _config_writer = ConfigWriter(loader)
    return _config_writer


async def close_config_writer() -> None:
    """Clean up the config writer."""
    global _config_writer
    _config_writer = None
