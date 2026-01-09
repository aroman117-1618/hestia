"""
Task manager for background task orchestration.

Per ADR-021: Background Task Management
Per ADR-022: Governed Auto-Persistence for Background Tasks

Coordinates task lifecycle including creation, approval,
execution tracking, and completion handling.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import BackgroundTask, TaskStatus, TaskSource
from .database import TaskDatabase, get_task_database


class TaskManager:
    """
    Manages background task lifecycle.

    Handles task creation, status transitions, approval workflow,
    and retry logic. Acts as the primary interface for task operations.
    """

    def __init__(self, database: Optional[TaskDatabase] = None):
        """
        Initialize task manager.

        Args:
            database: TaskDatabase instance. If None, uses singleton.
        """
        self._database = database
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the task manager and its dependencies."""
        if self._database is None:
            self._database = await get_task_database()

        self.logger.info(
            "Task manager initialized",
            component=LogComponent.API,
        )

    async def close(self) -> None:
        """Close task manager resources."""
        # Note: We don't close the singleton database here
        # as other components may still be using it
        self.logger.debug(
            "Task manager closed",
            component=LogComponent.API,
        )

    async def __aenter__(self) -> "TaskManager":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def database(self) -> TaskDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("Task manager not initialized. Call initialize() first.")
        return self._database

    async def create_task(
        self,
        input_summary: str,
        source: TaskSource,
        autonomy_level: int = 3,
        device_id: Optional[str] = None,
    ) -> BackgroundTask:
        """
        Create a new background task.

        Args:
            input_summary: Description of what the task should do.
            source: Where the task originated from.
            autonomy_level: Approval requirement level (1-4).
            device_id: Device that submitted the task.

        Returns:
            Created BackgroundTask.
        """
        # Validate autonomy level
        if not 1 <= autonomy_level <= 4:
            raise ValueError(f"Autonomy level must be 1-4, got {autonomy_level}")

        # Create task (initial status determined by autonomy level)
        task = BackgroundTask.create(
            input_summary=input_summary,
            source=source,
            autonomy_level=autonomy_level,
            device_id=device_id,
        )

        # Persist
        await self.database.store_task(task)

        self.logger.info(
            f"Task created: {task.id}",
            component=LogComponent.API,
            data={
                "task_id": task.id,
                "source": source.value,
                "autonomy_level": autonomy_level,
                "status": task.status.value,
            },
        )

        return task

    async def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        """
        Retrieve a task by ID.

        Args:
            task_id: Task identifier.

        Returns:
            BackgroundTask if found, None otherwise.
        """
        return await self.database.get_task(task_id)

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
        return await self.database.list_tasks(
            status=status,
            source=source,
            device_id=device_id,
            limit=limit,
            offset=offset,
        )

    async def count_tasks(
        self,
        status: Optional[TaskStatus] = None,
        source: Optional[TaskSource] = None,
        device_id: Optional[str] = None,
    ) -> int:
        """Count tasks with optional filters."""
        return await self.database.count_tasks(
            status=status,
            source=source,
            device_id=device_id,
        )

    async def approve_task(self, task_id: str) -> BackgroundTask:
        """
        Approve a task that is awaiting approval.

        Args:
            task_id: Task identifier.

        Returns:
            Updated BackgroundTask.

        Raises:
            ValueError: If task not found or not awaiting approval.
        """
        task = await self.database.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        if task.status != TaskStatus.AWAITING_APPROVAL:
            raise ValueError(
                f"Task {task_id} is not awaiting approval (status: {task.status.value})"
            )

        # Approve and move to pending
        task.approve()
        await self.database.update_task(task)

        self.logger.info(
            f"Task approved: {task_id}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )

        return task

    async def cancel_task(self, task_id: str) -> BackgroundTask:
        """
        Cancel a pending or awaiting approval task.

        Args:
            task_id: Task identifier.

        Returns:
            Updated BackgroundTask.

        Raises:
            ValueError: If task not found or cannot be cancelled.
        """
        task = await self.database.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        if not task.can_cancel:
            raise ValueError(
                f"Task {task_id} cannot be cancelled (status: {task.status.value})"
            )

        task.cancel()
        await self.database.update_task(task)

        self.logger.info(
            f"Task cancelled: {task_id}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )

        return task

    async def retry_task(self, task_id: str) -> BackgroundTask:
        """
        Retry a failed task.

        Args:
            task_id: Task identifier.

        Returns:
            Updated BackgroundTask (reset to PENDING).

        Raises:
            ValueError: If task not found or not in failed status.
        """
        task = await self.database.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        if not task.can_retry:
            raise ValueError(
                f"Task {task_id} cannot be retried (status: {task.status.value})"
            )

        task.prepare_retry()
        await self.database.update_task(task)

        self.logger.info(
            f"Task retry initiated: {task_id}",
            component=LogComponent.API,
            data={"task_id": task_id, "retry_count": task.retry_count},
        )

        return task

    async def start_task(self, task_id: str) -> BackgroundTask:
        """
        Mark a task as started/in progress.

        Args:
            task_id: Task identifier.

        Returns:
            Updated BackgroundTask.

        Raises:
            ValueError: If task not found or cannot be started.
        """
        task = await self.database.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.start()
        await self.database.update_task(task)

        self.logger.info(
            f"Task started: {task_id}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )

        return task

    async def complete_task(
        self,
        task_id: str,
        output_summary: str,
        output_details: Optional[Dict[str, Any]] = None,
    ) -> BackgroundTask:
        """
        Mark a task as completed.

        Args:
            task_id: Task identifier.
            output_summary: Summary of task output.
            output_details: Detailed output data.

        Returns:
            Updated BackgroundTask.

        Raises:
            ValueError: If task not found or cannot be completed.
        """
        task = await self.database.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.complete(output_summary, output_details)
        await self.database.update_task(task)

        self.logger.info(
            f"Task completed: {task_id}",
            component=LogComponent.API,
            data={
                "task_id": task_id,
                "output_summary": output_summary[:100] if output_summary else None,
            },
        )

        return task

    async def fail_task(self, task_id: str, error_message: str) -> BackgroundTask:
        """
        Mark a task as failed.

        Args:
            task_id: Task identifier.
            error_message: Description of the failure.

        Returns:
            Updated BackgroundTask.

        Raises:
            ValueError: If task not found or cannot be failed.
        """
        task = await self.database.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.fail(error_message)
        await self.database.update_task(task)

        self.logger.warning(
            f"Task failed: {task_id}",
            component=LogComponent.API,
            data={
                "task_id": task_id,
                "error": error_message,
            },
        )

        return task

    async def update_progress(self, task_id: str, progress: float) -> BackgroundTask:
        """
        Update task progress.

        Args:
            task_id: Task identifier.
            progress: Progress value (0.0 - 1.0).

        Returns:
            Updated BackgroundTask.

        Raises:
            ValueError: If task not found.
        """
        task = await self.database.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.update_progress(progress)
        await self.database.update_task(task)

        return task

    async def escalate_task(self, task_id: str, reason: str) -> BackgroundTask:
        """
        Escalate a task to require approval.

        Args:
            task_id: Task identifier.
            reason: Reason for escalation.

        Returns:
            Updated BackgroundTask.

        Raises:
            ValueError: If task not found.
        """
        task = await self.database.get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.escalate(reason)
        await self.database.update_task(task)

        self.logger.info(
            f"Task escalated: {task_id}",
            component=LogComponent.API,
            data={
                "task_id": task_id,
                "reason": reason,
            },
        )

        return task

    async def get_pending_tasks(self, limit: int = 50) -> List[BackgroundTask]:
        """Get tasks waiting to be executed."""
        return await self.database.get_pending_tasks(limit=limit)

    async def get_awaiting_approval(
        self,
        device_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[BackgroundTask]:
        """Get tasks awaiting user approval."""
        return await self.database.get_awaiting_approval(
            device_id=device_id,
            limit=limit,
        )

    async def get_active_tasks(self, limit: int = 50) -> List[BackgroundTask]:
        """Get currently running tasks."""
        return await self.database.get_active_tasks(limit=limit)

    async def delete_task(self, task_id: str) -> bool:
        """
        Delete a task (for cleanup/admin purposes).

        Args:
            task_id: Task identifier.

        Returns:
            True if deleted, False if not found.
        """
        deleted = await self.database.delete_task(task_id)

        if deleted:
            self.logger.info(
                f"Task deleted: {task_id}",
                component=LogComponent.API,
            )

        return deleted


# Module-level singleton
_task_manager: Optional[TaskManager] = None


async def get_task_manager() -> TaskManager:
    """Get or create singleton task manager."""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
        await _task_manager.initialize()
    return _task_manager


async def close_task_manager() -> None:
    """Close the singleton task manager."""
    global _task_manager
    if _task_manager is not None:
        await _task_manager.close()
        _task_manager = None
