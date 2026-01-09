"""
Agent manager for orchestrating agent profile operations.

Coordinates agent lifecycle including updates, snapshots,
restore, and multi-device sync.
"""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import AgentProfile, AgentSnapshot, SnapshotReason, DEFAULT_AGENTS
from .database import AgentDatabase, get_agent_database


class AgentManager:
    """
    Manages agent profile lifecycle.

    Handles agent CRUD with automatic snapshot creation,
    photo management, and sync coordination.
    """

    def __init__(
        self,
        database: Optional[AgentDatabase] = None,
        photos_dir: Optional[Path] = None,
    ):
        """
        Initialize agent manager.

        Args:
            database: AgentDatabase instance. If None, uses singleton.
            photos_dir: Directory for agent photos.
                       Defaults to ~/hestia/data/agent_photos/
        """
        self._database = database
        self.photos_dir = photos_dir or Path.home() / "hestia" / "data" / "agent_photos"
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the agent manager and its dependencies."""
        if self._database is None:
            self._database = await get_agent_database()

        self.logger.info(
            "Agent manager initialized",
            component=LogComponent.API,
        )

    async def close(self) -> None:
        """Close agent manager resources."""
        self.logger.debug(
            "Agent manager closed",
            component=LogComponent.API,
        )

    async def __aenter__(self) -> "AgentManager":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def database(self) -> AgentDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("Agent manager not initialized. Call initialize() first.")
        return self._database

    # =========================================================================
    # Agent CRUD
    # =========================================================================

    async def get_agent(self, slot_index: int) -> Optional[AgentProfile]:
        """Get an agent by slot index."""
        return await self.database.get_agent(slot_index)

    async def list_agents(self) -> List[AgentProfile]:
        """List all agents."""
        return await self.database.list_agents()

    async def update_agent(
        self,
        slot_index: int,
        name: str,
        instructions: str,
        gradient_color_1: str,
        gradient_color_2: str,
        create_snapshot: bool = True,
    ) -> AgentProfile:
        """
        Update an agent profile.

        Creates a snapshot of the current state before updating.

        Args:
            slot_index: Slot to update (0-2).
            name: New agent name.
            instructions: New instructions.
            gradient_color_1: Primary gradient color (hex).
            gradient_color_2: Secondary gradient color (hex).
            create_snapshot: Whether to create a snapshot before update.

        Returns:
            Updated AgentProfile.

        Raises:
            ValueError: If slot not found or validation fails.
        """
        agent = await self.database.get_agent(slot_index)
        if agent is None:
            raise ValueError(f"Agent not found at slot {slot_index}")

        # Create snapshot before updating
        if create_snapshot:
            snapshot = AgentSnapshot.create(agent, SnapshotReason.EDITED)
            await self.database.store_snapshot(snapshot)

        # Update agent
        agent.name = name
        agent.instructions = instructions
        agent.gradient_color_1 = gradient_color_1
        agent.gradient_color_2 = gradient_color_2
        agent.is_default = False
        agent.updated_at = datetime.now(timezone.utc)

        errors = agent.validate()
        if errors:
            raise ValueError(f"Validation failed: {', '.join(errors)}")

        await self.database.update_agent(agent)

        self.logger.info(
            f"Agent updated: slot {slot_index}",
            component=LogComponent.API,
            data={"slot": slot_index, "name": name},
        )

        return agent

    async def delete_agent(
        self,
        slot_index: int,
        create_snapshot: bool = True,
    ) -> AgentProfile:
        """
        Delete (reset to default) an agent profile.

        Slot 0 cannot be deleted.

        Args:
            slot_index: Slot to reset.
            create_snapshot: Whether to create a snapshot before reset.

        Returns:
            Reset AgentProfile.

        Raises:
            ValueError: If slot 0 or slot not found.
        """
        if slot_index == 0:
            raise ValueError("Primary agent (slot 0) cannot be deleted")

        agent = await self.database.get_agent(slot_index)
        if agent is None:
            raise ValueError(f"Agent not found at slot {slot_index}")

        # Create snapshot before reset
        if create_snapshot and not agent.is_default:
            snapshot = AgentSnapshot.create(agent, SnapshotReason.DELETED)
            await self.database.store_snapshot(snapshot)

        # Delete photo if exists
        if agent.photo_path:
            await self.delete_photo(slot_index)

        # Reset to default
        reset_agent = await self.database.reset_to_default(slot_index)

        self.logger.info(
            f"Agent reset to default: slot {slot_index}",
            component=LogComponent.API,
        )

        return reset_agent

    # =========================================================================
    # Photo Management
    # =========================================================================

    async def save_photo(
        self,
        slot_index: int,
        photo_data: bytes,
        content_type: str = "image/jpeg",
    ) -> str:
        """
        Save a photo for an agent.

        Args:
            slot_index: Agent slot.
            photo_data: Photo bytes.
            content_type: MIME type.

        Returns:
            Relative path to saved photo.

        Raises:
            ValueError: If agent not found or invalid image.
        """
        agent = await self.database.get_agent(slot_index)
        if agent is None:
            raise ValueError(f"Agent not found at slot {slot_index}")

        # Determine extension from content type
        ext_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
        }
        ext = ext_map.get(content_type, ".jpg")

        # Delete existing photo if any
        if agent.photo_path:
            old_path = self.photos_dir / agent.photo_path
            if old_path.exists():
                old_path.unlink()

        # Save new photo
        filename = f"agent_{slot_index}{ext}"
        photo_path = self.photos_dir / filename

        with open(photo_path, "wb") as f:
            f.write(photo_data)

        # Update database
        await self.database.update_photo_path(slot_index, filename)

        self.logger.info(
            f"Agent photo saved: slot {slot_index}",
            component=LogComponent.API,
        )

        return filename

    async def delete_photo(self, slot_index: int) -> bool:
        """
        Delete an agent's photo.

        Args:
            slot_index: Agent slot.

        Returns:
            True if photo was deleted, False if no photo existed.
        """
        agent = await self.database.get_agent(slot_index)
        if agent is None:
            raise ValueError(f"Agent not found at slot {slot_index}")

        if not agent.photo_path:
            return False

        # Delete file
        photo_path = self.photos_dir / agent.photo_path
        if photo_path.exists():
            photo_path.unlink()

        # Update database
        await self.database.update_photo_path(slot_index, None)

        self.logger.info(
            f"Agent photo deleted: slot {slot_index}",
            component=LogComponent.API,
        )

        return True

    def get_photo_path(self, slot_index: int, filename: str) -> Optional[Path]:
        """Get full path to a photo file."""
        photo_path = self.photos_dir / filename
        if photo_path.exists():
            return photo_path
        return None

    # =========================================================================
    # Snapshot Management
    # =========================================================================

    async def list_snapshots(
        self,
        slot_index: int,
        limit: int = 50,
    ) -> List[AgentSnapshot]:
        """List snapshots for an agent slot."""
        return await self.database.list_snapshots(slot_index, limit)

    async def count_snapshots(self, slot_index: int) -> int:
        """Count snapshots for a slot."""
        return await self.database.count_snapshots(slot_index)

    async def restore_from_snapshot(
        self,
        slot_index: int,
        snapshot_id: str,
    ) -> AgentProfile:
        """
        Restore an agent from a snapshot.

        Args:
            slot_index: Slot to restore.
            snapshot_id: Snapshot to restore from.

        Returns:
            Restored AgentProfile.

        Raises:
            ValueError: If snapshot not found or slot mismatch.
        """
        snapshot = await self.database.get_snapshot(snapshot_id)
        if snapshot is None:
            raise ValueError(f"Snapshot not found: {snapshot_id}")

        if snapshot.slot_index != slot_index:
            raise ValueError(f"Snapshot {snapshot_id} is for slot {snapshot.slot_index}, not {slot_index}")

        agent = await self.database.get_agent(slot_index)
        if agent is None:
            raise ValueError(f"Agent not found at slot {slot_index}")

        # Create snapshot of current state before restore
        current_snapshot = AgentSnapshot.create(agent, SnapshotReason.EDITED)
        await self.database.store_snapshot(current_snapshot)

        # Restore from snapshot
        agent.name = snapshot.name
        agent.instructions = snapshot.instructions
        agent.gradient_color_1 = snapshot.gradient_color_1
        agent.gradient_color_2 = snapshot.gradient_color_2
        agent.is_default = False
        agent.updated_at = datetime.now(timezone.utc)

        await self.database.update_agent(agent)

        self.logger.info(
            f"Agent restored from snapshot: slot {slot_index}",
            component=LogComponent.API,
            data={"slot": slot_index, "snapshot_id": snapshot_id},
        )

        return agent

    # =========================================================================
    # Multi-Device Sync
    # =========================================================================

    async def sync_agents(
        self,
        device_agents: List[Dict[str, Any]],
        device_id: str,
        sync_strategy: str = "latest_wins",
    ) -> Dict[str, Any]:
        """
        Sync agent profiles from a device.

        Args:
            device_agents: List of agent data from device.
            device_id: Device identifier.
            sync_strategy: How to resolve conflicts:
                - "latest_wins": Most recent updated_at wins
                - "server_wins": Server version always wins
                - "device_wins": Device version always wins

        Returns:
            Sync result with conflicts and final server state.
        """
        conflicts = []
        synced_count = 0

        for device_agent in device_agents:
            slot_index = device_agent["slot_index"]
            device_updated = datetime.fromisoformat(device_agent["updated_at"])

            server_agent = await self.database.get_agent(slot_index)
            if server_agent is None:
                continue

            server_updated = server_agent.updated_at

            # Determine winner
            if sync_strategy == "server_wins":
                # Keep server version
                pass
            elif sync_strategy == "device_wins":
                # Use device version
                await self.update_agent(
                    slot_index=slot_index,
                    name=device_agent["name"],
                    instructions=device_agent["instructions"],
                    gradient_color_1=device_agent["gradient_color_1"],
                    gradient_color_2=device_agent["gradient_color_2"],
                    create_snapshot=False,
                )
                synced_count += 1
            else:  # latest_wins
                if device_updated > server_updated:
                    # Device is newer
                    await self.update_agent(
                        slot_index=slot_index,
                        name=device_agent["name"],
                        instructions=device_agent["instructions"],
                        gradient_color_1=device_agent["gradient_color_1"],
                        gradient_color_2=device_agent["gradient_color_2"],
                        create_snapshot=False,
                    )
                    synced_count += 1

                    if server_updated != device_updated:
                        conflicts.append({
                            "slot_index": slot_index,
                            "device_updated_at": device_updated.isoformat(),
                            "server_updated_at": server_updated.isoformat(),
                            "resolution": "device_wins",
                        })
                elif device_updated < server_updated:
                    conflicts.append({
                        "slot_index": slot_index,
                        "device_updated_at": device_updated.isoformat(),
                        "server_updated_at": server_updated.isoformat(),
                        "resolution": "server_wins",
                    })

        # Get final server state
        server_agents = await self.list_agents()

        self.logger.info(
            f"Agent sync completed: {synced_count} synced, {len(conflicts)} conflicts",
            component=LogComponent.API,
            data={"device_id": device_id, "strategy": sync_strategy},
        )

        return {
            "synced_count": synced_count,
            "conflicts": conflicts,
            "server_agents": [
                {
                    "slot_index": a.slot_index,
                    "name": a.name,
                    "instructions": a.instructions,
                    "gradient_color_1": a.gradient_color_1,
                    "gradient_color_2": a.gradient_color_2,
                    "updated_at": a.updated_at.isoformat(),
                }
                for a in server_agents
            ],
        }


# Module-level singleton
_agent_manager: Optional[AgentManager] = None


async def get_agent_manager() -> AgentManager:
    """Get or create singleton agent manager."""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
        await _agent_manager.initialize()
    return _agent_manager


async def close_agent_manager() -> None:
    """Close the singleton agent manager."""
    global _agent_manager
    if _agent_manager is not None:
        await _agent_manager.close()
        _agent_manager = None
