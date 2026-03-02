"""
SQLite persistence for background tasks.

Per ADR-021: Background Task Management

Provides async database operations for task storage, retrieval,
and status tracking using aiosqlite.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.database import BaseDatabase
from hestia.logging import get_logger, LogComponent

from .models import BackgroundTask, TaskStatus, TaskSource


# Schema version for migrations
SCHEMA_VERSION = 1


class TaskDatabase(BaseDatabase):
    """
    SQLite database for background task persistence.

    Uses async aiosqlite for non-blocking I/O.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("tasks", db_path)
        self.logger = get_logger()

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        await super().connect()
        self.logger.info(
            f"Task database connected: {self.db_path}",
            component=LogComponent.API,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS background_tasks (
                id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                source TEXT NOT NULL,
                input_summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                output_summary TEXT,
                output_details TEXT,
                autonomy_level INTEGER DEFAULT 3,
                escalated INTEGER DEFAULT 0,
                escalation_reason TEXT,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0,
                device_id TEXT,
                progress REAL DEFAULT 0.0
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON background_tasks(status);

            CREATE INDEX IF NOT EXISTS idx_tasks_created
                ON background_tasks(created_at DESC);

            CREATE INDEX IF NOT EXISTS idx_tasks_device
                ON background_tasks(device_id);

            CREATE INDEX IF NOT EXISTS idx_tasks_source
                ON background_tasks(source);

            -- Schema version tracking
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            );

            INSERT OR IGNORE INTO schema_version (version) VALUES (1);
        """)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self.logger.debug(
                "Task database closed",
                component=LogComponent.API,
            )
        await super().close()

    async def store_task(self, task: BackgroundTask) -> str:
        """
        Store a new task in the database.

        Args:
            task: BackgroundTask to store.

        Returns:
            Task ID.
        """
        row = task.to_sqlite_row()

        await self.connection.execute(
            """
            INSERT INTO background_tasks (
                id, status, source, input_summary, created_at,
                started_at, completed_at, output_summary, output_details,
                autonomy_level, escalated, escalation_reason,
                error_message, retry_count, device_id, progress
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        await self.connection.commit()

        self.logger.debug(
            f"Stored task: {task.id}",
            component=LogComponent.API,
            data={"task_id": task.id, "status": task.status.value},
        )

        return task.id

    async def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """
        Retrieve a task by ID.

        Args:
            task_id: Task identifier.

        Returns:
            BackgroundTask if found, None otherwise.
        """
        async with self.connection.execute(
            "SELECT * FROM background_tasks WHERE id = ?",
            (task_id,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                return BackgroundTask.from_sqlite_row(dict(row))

        return None

    async def update_task(self, task: BackgroundTask) -> bool:
        """
        Update an existing task.

        Args:
            task: BackgroundTask with updated fields.

        Returns:
            True if updated, False if task not found.
        """
        row = task.to_sqlite_row()

        cursor = await self.connection.execute(
            """
            UPDATE background_tasks SET
                status = ?,
                source = ?,
                input_summary = ?,
                created_at = ?,
                started_at = ?,
                completed_at = ?,
                output_summary = ?,
                output_details = ?,
                autonomy_level = ?,
                escalated = ?,
                escalation_reason = ?,
                error_message = ?,
                retry_count = ?,
                device_id = ?,
                progress = ?
            WHERE id = ?
            """,
            (
                row[1], row[2], row[3], row[4], row[5], row[6], row[7],
                row[8], row[9], row[10], row[11], row[12], row[13],
                row[14], row[15], row[0]
            ),
        )
        await self.connection.commit()

        updated = cursor.rowcount > 0

        if updated:
            self.logger.debug(
                f"Updated task: {task.id}",
                component=LogComponent.API,
                data={"task_id": task.id, "status": task.status.value},
            )

        return updated

    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task by ID.

        Args:
            task_id: Task identifier.

        Returns:
            True if deleted, False if not found.
        """
        cursor = await self.connection.execute(
            "DELETE FROM background_tasks WHERE id = ?",
            (task_id,),
        )
        await self.connection.commit()

        deleted = cursor.rowcount > 0

        if deleted:
            self.logger.debug(
                f"Deleted task: {task_id}",
                component=LogComponent.API,
            )

        return deleted

    async def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        source: Optional[TaskSource] = None,
        device_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[BackgroundTask]:
        """
        List tasks with optional filters.

        Args:
            status: Filter by status.
            source: Filter by source.
            device_id: Filter by device.
            limit: Maximum results.
            offset: Results offset for pagination.

        Returns:
            List of BackgroundTask objects.
        """
        query = "SELECT * FROM background_tasks WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if source:
            query += " AND source = ?"
            params.append(source.value)

        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        tasks = []
        async with self.connection.execute(query, params) as cursor:
            async for row in cursor:
                tasks.append(BackgroundTask.from_sqlite_row(dict(row)))

        return tasks

    async def count_tasks(
        self,
        status: Optional[TaskStatus] = None,
        source: Optional[TaskSource] = None,
        device_id: Optional[str] = None,
    ) -> int:
        """
        Count tasks with optional filters.

        Args:
            status: Filter by status.
            source: Filter by source.
            device_id: Filter by device.

        Returns:
            Count of matching tasks.
        """
        query = "SELECT COUNT(*) FROM background_tasks WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if source:
            query += " AND source = ?"
            params.append(source.value)

        if device_id:
            query += " AND device_id = ?"
            params.append(device_id)

        async with self.connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_pending_tasks(self, limit: int = 50) -> List[BackgroundTask]:
        """Get tasks waiting to be executed."""
        return await self.list_tasks(status=TaskStatus.PENDING, limit=limit)

    async def get_awaiting_approval(
        self,
        device_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[BackgroundTask]:
        """Get tasks awaiting user approval."""
        return await self.list_tasks(
            status=TaskStatus.AWAITING_APPROVAL,
            device_id=device_id,
            limit=limit,
        )

    async def get_active_tasks(self, limit: int = 50) -> List[BackgroundTask]:
        """Get currently running tasks."""
        return await self.list_tasks(status=TaskStatus.IN_PROGRESS, limit=limit)

    async def get_recent_completed(
        self,
        device_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[BackgroundTask]:
        """Get recently completed tasks."""
        return await self.list_tasks(
            status=TaskStatus.COMPLETED,
            device_id=device_id,
            limit=limit,
        )

    async def get_failed_tasks(
        self,
        device_id: Optional[str] = None,
        limit: int = 20,
    ) -> List[BackgroundTask]:
        """Get failed tasks that may be retried."""
        return await self.list_tasks(
            status=TaskStatus.FAILED,
            device_id=device_id,
            limit=limit,
        )


# Module-level singleton
_task_database: Optional[TaskDatabase] = None


async def get_task_database() -> TaskDatabase:
    """Get or create singleton task database."""
    global _task_database
    if _task_database is None:
        _task_database = TaskDatabase()
        await _task_database.connect()
    return _task_database


async def close_task_database() -> None:
    """Close the singleton task database."""
    global _task_database
    if _task_database is not None:
        await _task_database.close()
        _task_database = None
