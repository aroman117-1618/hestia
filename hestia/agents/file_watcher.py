"""
Lightweight file watcher for agent config directories.

Uses polling (stat-based) rather than OS-level file events to avoid:
- watchdog dependency
- iCloud Drive notification quirks
- Cross-platform differences

Checks file modification times on a configurable interval (default 5s)
and invalidates ConfigLoader cache when changes are detected.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional, Set

from hestia.logging import get_logger, LogComponent

logger = get_logger()


class AgentFileWatcher:
    """
    Polls agent config directories for changes and triggers cache invalidation.

    Tracks file modification times and detects:
    - Modified files
    - New files
    - Deleted files
    - New or removed agent directories
    """

    def __init__(
        self,
        agents_root: Path,
        on_change: Callable[[str], None],
        poll_interval: float = 5.0,
    ):
        """
        Args:
            agents_root: Root directory containing agent subdirectories.
            on_change: Callback invoked with agent_name when changes detected.
            poll_interval: Seconds between polls.
        """
        self.agents_root = agents_root
        self.on_change = on_change
        self.poll_interval = poll_interval

        # State: {agent_name: {filename: mtime}}
        self._file_states: Dict[str, Dict[str, float]] = {}
        self._known_agents: Set[str] = set()
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def _scan_agent_dir(self, agent_dir: Path) -> Dict[str, float]:
        """Get modification times for all files in an agent directory."""
        mtimes = {}
        try:
            for f in agent_dir.rglob("*"):
                if f.is_file() and not f.name.startswith("."):
                    try:
                        mtimes[str(f.relative_to(agent_dir))] = f.stat().st_mtime
                    except OSError:
                        pass
        except OSError:
            pass
        return mtimes

    def _snapshot(self) -> None:
        """Take initial snapshot of all agent directories."""
        self._known_agents.clear()
        self._file_states.clear()

        if not self.agents_root.exists():
            return

        for d in self.agents_root.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                self._known_agents.add(d.name)
                self._file_states[d.name] = self._scan_agent_dir(d)

    def _detect_changes(self) -> Set[str]:
        """
        Compare current file states against snapshot.

        Returns:
            Set of agent names with detected changes.
        """
        changed_agents: Set[str] = set()

        if not self.agents_root.exists():
            return changed_agents

        # Current agent directories
        current_agents = {
            d.name for d in self.agents_root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        }

        # Detect new agents
        new_agents = current_agents - self._known_agents
        for name in new_agents:
            changed_agents.add(name)
            self._file_states[name] = self._scan_agent_dir(self.agents_root / name)

        # Detect removed agents
        removed_agents = self._known_agents - current_agents
        for name in removed_agents:
            changed_agents.add(name)
            self._file_states.pop(name, None)

        # Detect file changes in existing agents
        for name in current_agents & self._known_agents:
            agent_dir = self.agents_root / name
            current_mtimes = self._scan_agent_dir(agent_dir)
            prev_mtimes = self._file_states.get(name, {})

            if current_mtimes != prev_mtimes:
                changed_agents.add(name)
                self._file_states[name] = current_mtimes

        self._known_agents = current_agents
        return changed_agents

    async def _poll_loop(self) -> None:
        """Main polling loop."""
        self._snapshot()
        logger.info(
            f"File watcher started — polling {self.agents_root} "
            f"every {self.poll_interval}s"
        )

        while self._running:
            try:
                await asyncio.sleep(self.poll_interval)

                if not self._running:
                    break

                changed = self._detect_changes()
                for agent_name in changed:
                    logger.info(f"Change detected in agent config: {agent_name}")
                    try:
                        self.on_change(agent_name)
                    except Exception as e:
                        logger.warning(f"Error in change callback for '{agent_name}': {e}")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"File watcher error: {e}")
                await asyncio.sleep(self.poll_interval)

    def start(self) -> None:
        """Start the file watcher polling loop."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.get_event_loop().create_task(self._poll_loop())
        logger.info("Agent file watcher started")

    async def stop(self) -> None:
        """Stop the file watcher."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Agent file watcher stopped")

    @property
    def is_running(self) -> bool:
        """Whether the watcher is actively polling."""
        return self._running
