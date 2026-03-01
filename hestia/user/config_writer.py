"""
User profile configuration writer.

Atomic writes to user profile .md files in data/user/.
Mirrors the agent v2 ConfigWriter pattern (agents/config_writer.py).
"""

import os
import tempfile
from datetime import datetime, timezone, date as date_type
from pathlib import Path
from typing import Optional

from hestia.logging import get_logger
from hestia.user.config_models import (
    AGENT_WRITABLE_FILES,
    USER_ONLY_FILES,
    DailyNote,
    UserConfigFile,
)

logger = get_logger()


class UserConfigWriter:
    """
    Writes user profile files atomically.

    Uses temp-file-then-rename pattern for crash safety.
    Invalidates the UserConfigLoader cache after writes.
    """

    def __init__(self) -> None:
        self._loader: Optional["UserConfigLoader"] = None

    async def _get_loader(self) -> "UserConfigLoader":
        """Lazy-load the config loader for cache invalidation."""
        if self._loader is None:
            from hestia.user.config_loader import get_user_config_loader
            self._loader = await get_user_config_loader()
        return self._loader

    def _atomic_write(self, path: Path, content: str) -> None:
        """Write file atomically using temp-file-then-rename."""
        parent = path.parent
        parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.replace(tmp_path, str(path))
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    async def write_config_file(
        self,
        config_file: UserConfigFile,
        content: str,
        source: str = "user",
    ) -> None:
        """
        Write a user profile .md file.

        Args:
            config_file: Which file to write.
            content: New file content.
            source: Who is writing ("user" or "agent").

        Raises:
            PermissionError: If agent tries to write user-only file.
        """
        # Permission check
        if source == "agent" and config_file in USER_ONLY_FILES:
            raise PermissionError(
                f"Agent cannot write {config_file.value} (user-only file)"
            )

        if source == "agent" and config_file not in AGENT_WRITABLE_FILES:
            raise PermissionError(
                f"Agent cannot write {config_file.value} without confirmation"
            )

        loader = await self._get_loader()
        file_path = loader.user_root / config_file.value

        self._atomic_write(file_path, content)
        loader.invalidate_cache()

        logger.info(f"Wrote {config_file.value} (source={source})")

    async def append_memory(self, entry: str, source: str = "agent") -> None:
        """Append an entry to MEMORY.md with date stamp."""
        loader = await self._get_loader()
        memory_path = loader.user_root / UserConfigFile.MEMORY.value

        existing = ""
        if memory_path.exists():
            existing = memory_path.read_text(encoding="utf-8")

        date_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_entry = f"\n\n### {date_stamp}\n{entry}"

        self._atomic_write(memory_path, existing + new_entry)
        loader.invalidate_cache()

        logger.info("Appended to user MEMORY.md")

    # ─── Daily Notes ─────────────────────────────

    async def write_daily_note(
        self,
        content: str,
        note_date: Optional[date_type] = None,
    ) -> DailyNote:
        """Write (overwrite) a daily note."""
        note_date = note_date or date_type.today()
        loader = await self._get_loader()
        note_path = loader.user_root / "memory" / f"{note_date.isoformat()}.md"

        self._atomic_write(note_path, content)

        logger.info(f"Wrote daily note: {note_date.isoformat()}")
        return DailyNote(date=note_date, content=content)

    async def append_daily_note(
        self,
        entry: str,
        note_date: Optional[date_type] = None,
    ) -> DailyNote:
        """Append an entry to a daily note with timestamp."""
        note_date = note_date or date_type.today()
        loader = await self._get_loader()
        note_path = loader.user_root / "memory" / f"{note_date.isoformat()}.md"

        existing = ""
        if note_path.exists():
            existing = note_path.read_text(encoding="utf-8")
        else:
            # Create with header
            existing = f"# Daily Notes — {note_date.isoformat()}\n"

        timestamp = datetime.now(timezone.utc).strftime("%H:%M UTC")
        new_entry = f"\n\n**{timestamp}:** {entry}"

        content = existing + new_entry
        self._atomic_write(note_path, content)

        logger.info(f"Appended to daily note: {note_date.isoformat()}")
        return DailyNote(date=note_date, content=content)

    # ─── Commands ────────────────────────────────

    async def write_command(self, name: str, content: str) -> None:
        """Write a command .md file."""
        loader = await self._get_loader()
        cmd_path = loader.user_root / "commands" / f"{name}.md"

        self._atomic_write(cmd_path, content)
        loader.invalidate_commands_cache()

        logger.info(f"Wrote command: {name}")

    async def delete_command(self, name: str) -> bool:
        """Delete a command .md file."""
        loader = await self._get_loader()
        cmd_path = loader.user_root / "commands" / f"{name}.md"

        if not cmd_path.exists():
            return False

        cmd_path.unlink()
        loader.invalidate_commands_cache()

        logger.info(f"Deleted command: {name}")
        return True

    # ─── Setup ───────────────────────────────────

    async def complete_setup(self) -> None:
        """Archive SETUP.md after onboarding is complete."""
        loader = await self._get_loader()
        setup_path = loader.user_root / UserConfigFile.SETUP.value

        if setup_path.exists():
            # Move to archived location
            archive_path = loader.user_root / ".archived-SETUP.md"
            os.replace(str(setup_path), str(archive_path))
            loader.invalidate_cache()
            logger.info("Archived SETUP.md (onboarding complete)")


# ─── Module-Level Singleton ──────────────────────

_writer_instance: Optional[UserConfigWriter] = None


async def get_user_config_writer() -> UserConfigWriter:
    """Get or create the UserConfigWriter singleton."""
    global _writer_instance
    if _writer_instance is None:
        _writer_instance = UserConfigWriter()
    return _writer_instance
