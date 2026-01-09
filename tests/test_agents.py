"""
Tests for Hestia Agent Profiles module.

Phase 6b: Agent Profiles API - customizable agent personas.

Run with: python -m pytest tests/test_agents.py -v
"""

import asyncio
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Generator
from uuid import uuid4

import pytest
import pytest_asyncio

from hestia.agents.models import (
    AgentProfile,
    AgentSnapshot,
    SnapshotReason,
    DEFAULT_AGENTS,
)
from hestia.agents.database import AgentDatabase
from hestia.agents.manager import AgentManager


# ============== Fixtures ==============

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_agent() -> AgentProfile:
    """Create a sample agent profile."""
    return AgentProfile(
        id=f"agent-{uuid4().hex[:12]}",
        slot_index=0,
        name="Custom Tia",
        instructions="Be helpful and concise. This instruction is long enough.",
        gradient_color_1="FF6B35",
        gradient_color_2="8B4513",
        is_default=False,
    )


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> AgentDatabase:
    """Create a test database."""
    db = AgentDatabase(db_path=temp_dir / "test_agents.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(temp_dir: Path) -> AgentManager:
    """Create a test agent manager."""
    photos_dir = temp_dir / "photos"
    photos_dir.mkdir()

    db = AgentDatabase(db_path=temp_dir / "test_agents.db")
    await db.connect()

    mgr = AgentManager(database=db, photos_dir=photos_dir)
    await mgr.initialize()

    yield mgr

    await mgr.close()
    await db.close()


# ============== Model Tests ==============

class TestAgentProfile:
    """Tests for AgentProfile dataclass."""

    def test_agent_create(self):
        """Test agent creation with constructor."""
        agent = AgentProfile(
            id=f"agent-{uuid4().hex[:12]}",
            slot_index=1,
            name="Test Mira",
            instructions="Be patient and educational. This is long enough.",
            gradient_color_1="4A90D9",
            gradient_color_2="1E3A5F",
            is_default=False,
        )

        assert agent.id.startswith("agent-")
        assert agent.slot_index == 1
        assert agent.name == "Test Mira"
        assert agent.gradient_color_1 == "4A90D9"
        assert agent.is_default is False

    def test_agent_can_be_deleted(self):
        """Test that non-slot-0 agents can be deleted."""
        agent = AgentProfile(
            id=f"agent-{uuid4().hex[:12]}",
            slot_index=1,  # Slot 1 can be deleted
            name="Custom Agent",
            instructions="Custom instructions that are long enough.",
            gradient_color_1="FF0000",
            gradient_color_2="00FF00",
            is_default=False,
        )

        assert agent.can_be_deleted is True

    def test_slot_0_cannot_be_deleted(self):
        """Test that slot 0 cannot be deleted (regardless of is_default)."""
        agent = AgentProfile(
            id=f"agent-{uuid4().hex[:12]}",
            slot_index=0,  # Slot 0 cannot be deleted
            name="Tia",
            instructions="Default instructions long enough here.",
            gradient_color_1="FF6B35",
            gradient_color_2="8B4513",
            is_default=True,
        )

        # Slot 0 cannot be deleted
        assert agent.can_be_deleted is False

    def test_agent_to_dict(self):
        """Test agent serialization to dict."""
        agent = AgentProfile(
            id=f"agent-{uuid4().hex[:12]}",
            slot_index=2,
            name="Olly",
            instructions="Focus on projects. Long enough instruction.",
            gradient_color_1="34D399",
            gradient_color_2="065F46",
            is_default=False,
        )

        data = agent.to_dict()

        assert data["slot_index"] == 2
        assert data["name"] == "Olly"
        assert data["gradient_color_1"] == "34D399"

    def test_agent_from_dict(self):
        """Test agent deserialization from dict."""
        data = {
            "id": "agent-test-123",
            "slot_index": 0,
            "name": "Test",
            "instructions": "Test instructions",
            "gradient_color_1": "AABBCC",
            "gradient_color_2": "DDEEFF",
            "photo_path": None,
            "is_default": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        agent = AgentProfile.from_dict(data)

        assert agent.id == "agent-test-123"
        assert agent.name == "Test"


class TestAgentSnapshot:
    """Tests for AgentSnapshot dataclass."""

    def test_snapshot_create(self, sample_agent: AgentProfile):
        """Test snapshot creation."""
        snapshot = AgentSnapshot.create(
            agent=sample_agent,
            reason=SnapshotReason.EDITED,
        )

        assert snapshot.id.startswith("snap-")
        assert snapshot.agent_id == sample_agent.id
        assert snapshot.slot_index == sample_agent.slot_index
        assert snapshot.reason == SnapshotReason.EDITED
        assert snapshot.name == sample_agent.name
        assert snapshot.instructions == sample_agent.instructions

    def test_snapshot_for_deletion(self, sample_agent: AgentProfile):
        """Test snapshot for deletion reason."""
        snapshot = AgentSnapshot.create(
            agent=sample_agent,
            reason=SnapshotReason.DELETED,
        )

        assert snapshot.reason == SnapshotReason.DELETED


class TestDefaultAgents:
    """Tests for DEFAULT_AGENTS configuration."""

    def test_default_agents_count(self):
        """Test there are exactly 3 default agents."""
        assert len(DEFAULT_AGENTS) == 3

    def test_default_agents_slots(self):
        """Test default agents cover all 3 slots."""
        slots = {a.slot_index for a in DEFAULT_AGENTS}
        assert slots == {0, 1, 2}

    def test_default_agents_names(self):
        """Test default agent names."""
        names = {a.name for a in DEFAULT_AGENTS}
        assert names == {"Tia", "Mira", "Olly"}

    def test_default_agents_marked_default(self):
        """Test all default agents are marked as default."""
        for agent in DEFAULT_AGENTS:
            assert agent.is_default is True


# ============== Database Tests ==============

class TestAgentDatabase:
    """Tests for AgentDatabase persistence."""

    @pytest.mark.asyncio
    async def test_default_agents_created_on_connect(self, database: AgentDatabase):
        """Test default agents are created on first connect."""
        agents = await database.list_agents()
        assert len(agents) == 3

        # Check all slots filled
        slots = {a.slot_index for a in agents}
        assert slots == {0, 1, 2}

    @pytest.mark.asyncio
    async def test_get_agent(self, database: AgentDatabase):
        """Test getting agent by slot index."""
        agent = await database.get_agent(0)
        assert agent is not None
        assert agent.slot_index == 0
        assert agent.name == "Tia"

    @pytest.mark.asyncio
    async def test_update_agent(self, database: AgentDatabase):
        """Test updating an agent."""
        agent = await database.get_agent(0)

        agent.name = "Custom Tia"
        agent.instructions = "New instructions long enough for validation"
        agent.is_default = False

        await database.update_agent(agent)

        updated = await database.get_agent(0)
        assert updated.name == "Custom Tia"
        assert updated.instructions == "New instructions long enough for validation"
        assert updated.is_default is False

    @pytest.mark.asyncio
    async def test_reset_to_default(self, database: AgentDatabase):
        """Test resetting an agent to default."""
        # First customize it
        agent = await database.get_agent(1)
        agent.name = "Custom Mira"
        agent.is_default = False
        await database.update_agent(agent)

        # Now reset
        await database.reset_to_default(1)

        reset = await database.get_agent(1)
        assert reset.name == "Mira"
        assert reset.is_default is True

    @pytest.mark.asyncio
    async def test_store_and_list_snapshots(self, database: AgentDatabase):
        """Test storing and listing snapshots."""
        agent = await database.get_agent(0)

        snapshot = AgentSnapshot.create(
            agent=agent,
            reason=SnapshotReason.EDITED,
        )

        await database.store_snapshot(snapshot)

        snapshots = await database.list_snapshots(0)
        assert len(snapshots) == 1
        assert snapshots[0].id == snapshot.id

    @pytest.mark.asyncio
    async def test_get_snapshot(self, database: AgentDatabase):
        """Test getting a specific snapshot."""
        agent = await database.get_agent(0)

        snapshot = AgentSnapshot.create(
            agent=agent,
            reason=SnapshotReason.DELETED,
        )

        await database.store_snapshot(snapshot)

        retrieved = await database.get_snapshot(snapshot.id)
        assert retrieved is not None
        assert retrieved.reason == SnapshotReason.DELETED


# ============== Manager Tests ==============

class TestAgentManager:
    """Tests for AgentManager lifecycle."""

    @pytest.mark.asyncio
    async def test_get_agent(self, manager: AgentManager):
        """Test getting an agent through manager."""
        agent = await manager.get_agent(0)

        assert agent is not None
        assert agent.slot_index == 0
        assert agent.name == "Tia"

    @pytest.mark.asyncio
    async def test_update_agent_creates_snapshot(self, manager: AgentManager):
        """Test updating an agent creates a snapshot."""
        # Update the agent
        updated = await manager.update_agent(
            slot_index=0,
            name="Custom Tia",
            instructions="Custom instructions",
            gradient_color_1="AA0000",
            gradient_color_2="550000",
        )

        assert updated.name == "Custom Tia"
        assert updated.is_default is False

        # Check snapshot was created
        snapshots = await manager.list_snapshots(0)
        assert len(snapshots) == 1
        assert snapshots[0].reason == SnapshotReason.EDITED

    @pytest.mark.asyncio
    async def test_delete_agent_resets_to_default(self, manager: AgentManager):
        """Test deleting an agent resets to default."""
        # First customize it
        await manager.update_agent(
            slot_index=1,
            name="Custom Mira",
            instructions="Custom instructions long enough for validation",
            gradient_color_1="0000AA",
            gradient_color_2="000055",
        )

        # Delete (reset) - returns the reset AgentProfile
        reset_agent = await manager.delete_agent(1)

        # Verify returned agent is reset
        assert reset_agent.name == "Mira"
        assert reset_agent.is_default is True

        # Double-check from database
        agent = await manager.get_agent(1)
        assert agent.name == "Mira"
        assert agent.is_default is True

    @pytest.mark.asyncio
    async def test_restore_from_snapshot(self, manager: AgentManager):
        """Test restoring an agent from snapshot."""
        # Update to create snapshot
        await manager.update_agent(
            slot_index=2,
            name="Custom Olly",
            instructions="Custom instructions long enough for validation",
            gradient_color_1="00AA00",
            gradient_color_2="005500",
        )

        # Get the snapshot
        snapshots = await manager.list_snapshots(2)
        assert len(snapshots) == 1
        snapshot_id = snapshots[0].id

        # Update again
        await manager.update_agent(
            slot_index=2,
            name="Another Olly",
            instructions="Different instructions long enough for validation",
            gradient_color_1="AAAAAA",
            gradient_color_2="555555",
        )

        # Restore from first snapshot
        restored = await manager.restore_from_snapshot(2, snapshot_id)

        # Should restore the original Olly values (from before first edit)
        assert restored.name == "Olly"

    @pytest.mark.asyncio
    async def test_list_all_agents(self, manager: AgentManager):
        """Test listing all agents."""
        agents = await manager.list_agents()

        assert len(agents) == 3
        names = {a.name for a in agents}
        assert "Tia" in names
        assert "Mira" in names
        assert "Olly" in names

    @pytest.mark.asyncio
    async def test_save_and_delete_photo(self, manager: AgentManager):
        """Test photo management."""
        # Save a photo
        photo_data = b"fake image data for testing"
        filename = await manager.save_photo(0, photo_data, "image/jpeg")

        assert filename.endswith(".jpg")

        # Check agent has photo
        agent = await manager.get_agent(0)
        assert agent.photo_path is not None

        # Delete the photo
        deleted = await manager.delete_photo(0)
        assert deleted is True

        # Check photo is gone
        agent = await manager.get_agent(0)
        assert agent.photo_path is None

    @pytest.mark.asyncio
    async def test_sync_agents_latest_wins(self, manager: AgentManager):
        """Test syncing agents with latest_wins strategy."""
        # Create device data with newer timestamp
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)

        device_agents = [
            {
                "slot_index": 0,
                "name": "Device Tia",
                "instructions": "Device instructions long enough for validation",
                "gradient_color_1": "FF0000",
                "gradient_color_2": "AA0000",
                "updated_at": future_time.isoformat(),
            }
        ]

        result = await manager.sync_agents(
            device_agents=device_agents,
            device_id="test-device",
            sync_strategy="latest_wins",
        )

        assert result["synced_count"] == 1

        # Device version should win (newer)
        agent = await manager.get_agent(0)
        assert agent.name == "Device Tia"

    @pytest.mark.asyncio
    async def test_sync_agents_server_wins(self, manager: AgentManager):
        """Test syncing agents with server_wins strategy."""
        # Update server version
        await manager.update_agent(
            slot_index=0,
            name="Server Tia",
            instructions="Server instructions long enough for validation",
            gradient_color_1="00FF00",
            gradient_color_2="00AA00",
        )

        # Create device data
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        device_agents = [
            {
                "slot_index": 0,
                "name": "Device Tia",
                "instructions": "Device instructions long enough for validation",
                "gradient_color_1": "FF0000",
                "gradient_color_2": "AA0000",
                "updated_at": future_time.isoformat(),
            }
        ]

        result = await manager.sync_agents(
            device_agents=device_agents,
            device_id="test-device",
            sync_strategy="server_wins",
        )

        # Server version should win
        agent = await manager.get_agent(0)
        assert agent.name == "Server Tia"


# ============== Snapshot Retention Tests ==============

class TestSnapshotRetention:
    """Tests for snapshot retention policy."""

    @pytest.mark.asyncio
    async def test_snapshots_retained(self, database: AgentDatabase):
        """Test that recent snapshots are retained."""
        agent = await database.get_agent(0)

        # Create multiple snapshots
        for i in range(5):
            snapshot = AgentSnapshot.create(
                agent=agent,
                reason=SnapshotReason.EDITED,
            )
            await database.store_snapshot(snapshot)

        snapshots = await database.list_snapshots(0)
        assert len(snapshots) == 5


# ============== Edge Cases ==============

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_slot(self, database: AgentDatabase):
        """Test getting a non-existent slot returns None."""
        # Slots 0-2 should exist, slot 3 should not
        agent = await database.get_agent(3)
        assert agent is None

    @pytest.mark.asyncio
    async def test_update_maintains_id(self, manager: AgentManager):
        """Test that updating preserves the agent ID."""
        original = await manager.get_agent(0)
        original_id = original.id

        await manager.update_agent(
            slot_index=0,
            name="Updated",
            instructions="Updated instructions long enough for validation",
            gradient_color_1="000000",
            gradient_color_2="111111",
        )

        updated = await manager.get_agent(0)
        assert updated.id == original_id
