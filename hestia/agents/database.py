"""
SQLite persistence for agent profiles.

Provides async database operations for agent storage, snapshots,
and recovery using aiosqlite.
"""

import aiosqlite
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import AgentProfile, AgentSnapshot, SnapshotReason, DEFAULT_AGENTS


class AgentDatabase:
    """
    SQLite database for agent profile persistence.

    Uses async aiosqlite for non-blocking I/O.
    """

    # Snapshot retention period (90 days)
    SNAPSHOT_RETENTION_DAYS = 90

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize agent database.

        Args:
            db_path: Path to SQLite database file.
                     Defaults to ~/hestia/data/agents.db
        """
        if db_path is None:
            db_path = Path.home() / "hestia" / "data" / "agents.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection: Optional[aiosqlite.Connection] = None
        self.logger = get_logger()

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()
        await self._ensure_default_agents()

        self.logger.info(
            f"Agent database connected: {self.db_path}",
            component=LogComponent.API,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS agent_profiles (
                id TEXT PRIMARY KEY,
                slot_index INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                instructions TEXT NOT NULL,
                gradient_color_1 TEXT NOT NULL,
                gradient_color_2 TEXT NOT NULL,
                is_default INTEGER NOT NULL DEFAULT 1,
                photo_path TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_agents_slot
                ON agent_profiles(slot_index);

            CREATE TABLE IF NOT EXISTS agent_snapshots (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                slot_index INTEGER NOT NULL,
                snapshot_date TEXT NOT NULL,
                reason TEXT NOT NULL,
                name TEXT NOT NULL,
                instructions TEXT NOT NULL,
                gradient_color_1 TEXT NOT NULL,
                gradient_color_2 TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_slot
                ON agent_snapshots(slot_index);

            CREATE INDEX IF NOT EXISTS idx_snapshots_date
                ON agent_snapshots(snapshot_date DESC);
        """)
        await self._connection.commit()

    async def _ensure_default_agents(self) -> None:
        """Ensure default agents exist for all slots."""
        for default in DEFAULT_AGENTS:
            async with self.connection.execute(
                "SELECT id FROM agent_profiles WHERE slot_index = ?",
                (default.slot_index,),
            ) as cursor:
                row = await cursor.fetchone()

                if not row:
                    await self.store_agent(default)

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self.logger.debug(
                "Agent database closed",
                component=LogComponent.API,
            )

    async def __aenter__(self) -> "AgentDatabase":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get active connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # =========================================================================
    # Agent CRUD
    # =========================================================================

    async def store_agent(self, agent: AgentProfile) -> str:
        """Store a new or updated agent."""
        row = agent.to_sqlite_row()

        await self.connection.execute(
            """
            INSERT OR REPLACE INTO agent_profiles (
                id, slot_index, name, instructions, gradient_color_1,
                gradient_color_2, is_default, photo_path, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        await self.connection.commit()

        self.logger.debug(
            f"Stored agent: {agent.id}",
            component=LogComponent.API,
            data={"agent_id": agent.id, "slot": agent.slot_index},
        )

        return agent.id

    async def get_agent(self, slot_index: int) -> Optional[AgentProfile]:
        """Get an agent by slot index."""
        async with self.connection.execute(
            "SELECT * FROM agent_profiles WHERE slot_index = ?",
            (slot_index,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                return AgentProfile.from_sqlite_row(dict(row))

        return None

    async def get_agent_by_id(self, agent_id: str) -> Optional[AgentProfile]:
        """Get an agent by ID."""
        async with self.connection.execute(
            "SELECT * FROM agent_profiles WHERE id = ?",
            (agent_id,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                return AgentProfile.from_sqlite_row(dict(row))

        return None

    async def list_agents(self) -> List[AgentProfile]:
        """List all agents ordered by slot index."""
        agents = []
        async with self.connection.execute(
            "SELECT * FROM agent_profiles ORDER BY slot_index",
        ) as cursor:
            async for row in cursor:
                agents.append(AgentProfile.from_sqlite_row(dict(row)))

        return agents

    async def update_agent(self, agent: AgentProfile) -> bool:
        """Update an existing agent."""
        agent.updated_at = datetime.now(timezone.utc)
        row = agent.to_sqlite_row()

        cursor = await self.connection.execute(
            """
            UPDATE agent_profiles SET
                name = ?,
                instructions = ?,
                gradient_color_1 = ?,
                gradient_color_2 = ?,
                is_default = ?,
                photo_path = ?,
                updated_at = ?
            WHERE slot_index = ?
            """,
            (
                row[2], row[3], row[4], row[5], row[6],
                row[7], row[9], row[1]
            ),
        )
        await self.connection.commit()

        return cursor.rowcount > 0

    async def update_photo_path(self, slot_index: int, photo_path: Optional[str]) -> bool:
        """Update only the photo path for an agent."""
        cursor = await self.connection.execute(
            """
            UPDATE agent_profiles SET
                photo_path = ?,
                updated_at = ?
            WHERE slot_index = ?
            """,
            (photo_path, datetime.now(timezone.utc).isoformat(), slot_index),
        )
        await self.connection.commit()

        return cursor.rowcount > 0

    async def reset_to_default(self, slot_index: int) -> Optional[AgentProfile]:
        """Reset an agent to default configuration."""
        if slot_index not in (0, 1, 2):
            return None

        default = DEFAULT_AGENTS[slot_index]

        # Create new profile with same ID but default values
        agent = await self.get_agent(slot_index)
        if agent:
            agent.name = default.name
            agent.instructions = default.instructions
            agent.gradient_color_1 = default.gradient_color_1
            agent.gradient_color_2 = default.gradient_color_2
            agent.is_default = True
            agent.updated_at = datetime.now(timezone.utc)
            await self.update_agent(agent)
            return agent

        return None

    # =========================================================================
    # Snapshot Management
    # =========================================================================

    async def store_snapshot(self, snapshot: AgentSnapshot) -> str:
        """Store a snapshot."""
        row = snapshot.to_sqlite_row()

        await self.connection.execute(
            """
            INSERT INTO agent_snapshots (
                id, agent_id, slot_index, snapshot_date, reason,
                name, instructions, gradient_color_1, gradient_color_2
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        await self.connection.commit()

        self.logger.debug(
            f"Stored snapshot: {snapshot.id}",
            component=LogComponent.API,
            data={"snapshot_id": snapshot.id, "slot": snapshot.slot_index},
        )

        return snapshot.id

    async def get_snapshot(self, snapshot_id: str) -> Optional[AgentSnapshot]:
        """Get a snapshot by ID."""
        async with self.connection.execute(
            "SELECT * FROM agent_snapshots WHERE id = ?",
            (snapshot_id,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                return AgentSnapshot.from_sqlite_row(dict(row))

        return None

    async def list_snapshots(
        self,
        slot_index: int,
        limit: int = 50,
    ) -> List[AgentSnapshot]:
        """List snapshots for a slot, newest first."""
        snapshots = []
        async with self.connection.execute(
            """
            SELECT * FROM agent_snapshots
            WHERE slot_index = ?
            ORDER BY snapshot_date DESC
            LIMIT ?
            """,
            (slot_index, limit),
        ) as cursor:
            async for row in cursor:
                snapshots.append(AgentSnapshot.from_sqlite_row(dict(row)))

        return snapshots

    async def count_snapshots(self, slot_index: int) -> int:
        """Count snapshots for a slot."""
        async with self.connection.execute(
            "SELECT COUNT(*) FROM agent_snapshots WHERE slot_index = ?",
            (slot_index,),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def cleanup_old_snapshots(self) -> int:
        """Remove snapshots older than retention period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.SNAPSHOT_RETENTION_DAYS)

        cursor = await self.connection.execute(
            "DELETE FROM agent_snapshots WHERE snapshot_date < ?",
            (cutoff.isoformat(),),
        )
        await self.connection.commit()

        deleted = cursor.rowcount

        if deleted > 0:
            self.logger.info(
                f"Cleaned up {deleted} old snapshots",
                component=LogComponent.API,
            )

        return deleted


# Module-level singleton
_agent_database: Optional[AgentDatabase] = None


async def get_agent_database() -> AgentDatabase:
    """Get or create singleton agent database."""
    global _agent_database
    if _agent_database is None:
        _agent_database = AgentDatabase()
        await _agent_database.connect()
    return _agent_database


async def close_agent_database() -> None:
    """Close the singleton agent database."""
    global _agent_database
    if _agent_database is not None:
        await _agent_database.close()
        _agent_database = None
