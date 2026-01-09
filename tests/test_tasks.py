"""
Tests for Hestia background task management.

Per ADR-021: Background Task Management
Per ADR-022: Governed Auto-Persistence for Background Tasks

Run with: python -m pytest tests/test_tasks.py -v
"""

import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import pytest
import pytest_asyncio

from hestia.tasks.models import (
    BackgroundTask,
    TaskStatus,
    TaskSource,
    AutonomyLevel,
)
from hestia.tasks.database import TaskDatabase
from hestia.tasks.manager import TaskManager


# ============== Fixtures ==============

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_task() -> BackgroundTask:
    """Create a sample background task."""
    return BackgroundTask.create(
        input_summary="Add groceries to shopping list",
        source=TaskSource.CONVERSATION,
        autonomy_level=3,
        device_id="test-device-001",
    )


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> TaskDatabase:
    """Create a test database."""
    db = TaskDatabase(db_path=temp_dir / "test_tasks.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(temp_dir: Path) -> TaskManager:
    """Create a test task manager."""
    db = TaskDatabase(db_path=temp_dir / "test_tasks.db")
    await db.connect()

    mgr = TaskManager(database=db)
    await mgr.initialize()

    yield mgr

    await mgr.close()
    await db.close()


# ============== Model Tests ==============

class TestBackgroundTask:
    """Tests for BackgroundTask dataclass."""

    def test_task_create(self):
        """Test task creation with factory method."""
        task = BackgroundTask.create(
            input_summary="Test task",
            source=TaskSource.QUICK_CHAT,
            autonomy_level=3,
        )

        assert task.id.startswith("task-")
        assert task.input_summary == "Test task"
        assert task.source == TaskSource.QUICK_CHAT
        assert task.autonomy_level == 3
        assert task.status == TaskStatus.PENDING
        assert task.created_at is not None
        assert task.retry_count == 0
        assert task.progress == 0.0

    def test_task_create_awaiting_approval(self):
        """Test task with low autonomy starts awaiting approval."""
        task = BackgroundTask.create(
            input_summary="Sensitive task",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )

        assert task.status == TaskStatus.AWAITING_APPROVAL

    def test_task_create_with_level_2(self):
        """Test task with autonomy level 2 awaits approval."""
        task = BackgroundTask.create(
            input_summary="Send email",
            source=TaskSource.IOS_SHORTCUT,
            autonomy_level=2,
        )

        assert task.status == TaskStatus.AWAITING_APPROVAL

    def test_task_status_transitions_valid(self):
        """Test valid status transitions."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        # PENDING -> IN_PROGRESS
        assert task.can_transition_to(TaskStatus.IN_PROGRESS)
        assert task.can_transition_to(TaskStatus.CANCELLED)

        task.start()
        assert task.status == TaskStatus.IN_PROGRESS

        # IN_PROGRESS -> COMPLETED or FAILED
        assert task.can_transition_to(TaskStatus.COMPLETED)
        assert task.can_transition_to(TaskStatus.FAILED)

    def test_task_status_transitions_invalid(self):
        """Test invalid status transitions."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        # Cannot go directly to COMPLETED from PENDING
        assert not task.can_transition_to(TaskStatus.COMPLETED)
        assert not task.can_transition_to(TaskStatus.FAILED)

        with pytest.raises(ValueError):
            task.complete("Done", {})

    def test_task_start(self):
        """Test starting a task."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        task.start()

        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None

    def test_task_complete(self):
        """Test completing a task."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        task.start()
        task.complete("Successfully added items", {"items_added": 3})

        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        assert task.output_summary == "Successfully added items"
        assert task.output_details == {"items_added": 3}
        assert task.progress == 1.0

    def test_task_fail(self):
        """Test failing a task."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        task.start()
        task.fail("Connection timeout")

        assert task.status == TaskStatus.FAILED
        assert task.completed_at is not None
        assert task.error_message == "Connection timeout"

    def test_task_cancel(self):
        """Test cancelling a task."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        task.cancel()

        assert task.status == TaskStatus.CANCELLED
        assert task.completed_at is not None

    def test_task_approve(self):
        """Test approving a task awaiting approval."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )

        assert task.status == TaskStatus.AWAITING_APPROVAL

        task.approve()

        assert task.status == TaskStatus.PENDING

    def test_task_retry(self):
        """Test retrying a failed task."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        task.start()
        task.fail("Error")

        task.prepare_retry()

        assert task.status == TaskStatus.PENDING
        assert task.retry_count == 1
        assert task.started_at is None
        assert task.completed_at is None
        assert task.error_message is None
        assert task.progress == 0.0

    def test_task_escalate(self):
        """Test escalating a task."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
            autonomy_level=4,  # Silent
        )

        task.escalate("External API call required")

        assert task.escalated is True
        assert task.escalation_reason == "External API call required"
        assert task.status == TaskStatus.AWAITING_APPROVAL

    def test_task_update_progress(self):
        """Test updating task progress."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        task.update_progress(0.5)
        assert task.progress == 0.5

        # Clamp to bounds
        task.update_progress(-0.5)
        assert task.progress == 0.0

        task.update_progress(1.5)
        assert task.progress == 1.0

    def test_task_to_dict(self):
        """Test serialization to dictionary."""
        task = BackgroundTask.create(
            input_summary="Test task",
            source=TaskSource.QUICK_CHAT,
            device_id="device-001",
        )

        d = task.to_dict()

        assert d["id"] == task.id
        assert d["input_summary"] == "Test task"
        assert d["source"] == "quick_chat"
        assert d["status"] == "pending"
        assert d["device_id"] == "device-001"
        assert "created_at" in d

    def test_task_from_dict(self):
        """Test deserialization from dictionary."""
        original = BackgroundTask.create(
            input_summary="Test task",
            source=TaskSource.QUICK_CHAT,
        )

        d = original.to_dict()
        restored = BackgroundTask.from_dict(d)

        assert restored.id == original.id
        assert restored.input_summary == original.input_summary
        assert restored.source == original.source
        assert restored.status == original.status

    def test_task_to_sqlite_row(self):
        """Test conversion to SQLite row tuple."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        row = task.to_sqlite_row()

        assert isinstance(row, tuple)
        assert len(row) == 16
        assert row[0] == task.id
        assert row[1] == "pending"
        assert row[2] == "conversation"

    def test_task_from_sqlite_row(self):
        """Test creation from SQLite row."""
        original = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )
        original.start()
        original.complete("Done", {"key": "value"})

        row = original.to_sqlite_row()

        # Simulate SQLite row as dict
        row_dict = {
            "id": row[0],
            "status": row[1],
            "source": row[2],
            "input_summary": row[3],
            "created_at": row[4],
            "started_at": row[5],
            "completed_at": row[6],
            "output_summary": row[7],
            "output_details": row[8],
            "autonomy_level": row[9],
            "escalated": row[10],
            "escalation_reason": row[11],
            "error_message": row[12],
            "retry_count": row[13],
            "device_id": row[14],
            "progress": row[15],
        }

        restored = BackgroundTask.from_sqlite_row(row_dict)

        assert restored.id == original.id
        assert restored.status == original.status
        assert restored.output_details == {"key": "value"}

    def test_task_is_terminal(self):
        """Test terminal state checking."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        assert task.is_terminal is False

        task.start()
        task.complete("Done")

        assert task.is_terminal is True

    def test_task_can_cancel(self):
        """Test can_cancel property."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        assert task.can_cancel is True

        task.start()
        assert task.can_cancel is False

    def test_task_can_retry(self):
        """Test can_retry property."""
        task = BackgroundTask.create(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        assert task.can_retry is False

        task.start()
        task.fail("Error")

        assert task.can_retry is True


# ============== Database Tests ==============

class TestTaskDatabase:
    """Tests for TaskDatabase."""

    @pytest.mark.asyncio
    async def test_store_task(self, database: TaskDatabase, sample_task: BackgroundTask):
        """Test storing a task."""
        task_id = await database.store_task(sample_task)

        assert task_id == sample_task.id

    @pytest.mark.asyncio
    async def test_get_task(self, database: TaskDatabase, sample_task: BackgroundTask):
        """Test retrieving a task."""
        await database.store_task(sample_task)

        retrieved = await database.get_task(sample_task.id)

        assert retrieved is not None
        assert retrieved.id == sample_task.id
        assert retrieved.input_summary == sample_task.input_summary
        assert retrieved.source == sample_task.source

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, database: TaskDatabase):
        """Test retrieving a nonexistent task."""
        retrieved = await database.get_task("nonexistent-task-id")

        assert retrieved is None

    @pytest.mark.asyncio
    async def test_update_task(self, database: TaskDatabase, sample_task: BackgroundTask):
        """Test updating a task."""
        await database.store_task(sample_task)

        sample_task.start()
        sample_task.complete("Done", {"items": 5})

        updated = await database.update_task(sample_task)

        assert updated is True

        retrieved = await database.get_task(sample_task.id)
        assert retrieved.status == TaskStatus.COMPLETED
        assert retrieved.output_summary == "Done"
        assert retrieved.output_details == {"items": 5}

    @pytest.mark.asyncio
    async def test_delete_task(self, database: TaskDatabase, sample_task: BackgroundTask):
        """Test deleting a task."""
        await database.store_task(sample_task)

        deleted = await database.delete_task(sample_task.id)

        assert deleted is True

        retrieved = await database.get_task(sample_task.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_task(self, database: TaskDatabase):
        """Test deleting a nonexistent task."""
        deleted = await database.delete_task("nonexistent-task-id")

        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_tasks(self, database: TaskDatabase):
        """Test listing tasks."""
        # Create multiple tasks
        for i in range(5):
            task = BackgroundTask.create(
                input_summary=f"Task {i}",
                source=TaskSource.CONVERSATION,
            )
            await database.store_task(task)

        tasks = await database.list_tasks()

        assert len(tasks) == 5

    @pytest.mark.asyncio
    async def test_list_tasks_by_status(self, database: TaskDatabase):
        """Test listing tasks filtered by status."""
        # Create tasks with different statuses
        pending = BackgroundTask.create(
            input_summary="Pending task",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )
        await database.store_task(pending)

        awaiting = BackgroundTask.create(
            input_summary="Awaiting approval task",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )
        await database.store_task(awaiting)

        # Filter by pending
        pending_tasks = await database.list_tasks(status=TaskStatus.PENDING)
        assert len(pending_tasks) == 1
        assert pending_tasks[0].id == pending.id

        # Filter by awaiting approval
        awaiting_tasks = await database.list_tasks(status=TaskStatus.AWAITING_APPROVAL)
        assert len(awaiting_tasks) == 1
        assert awaiting_tasks[0].id == awaiting.id

    @pytest.mark.asyncio
    async def test_list_tasks_by_source(self, database: TaskDatabase):
        """Test listing tasks filtered by source."""
        task1 = BackgroundTask.create(
            input_summary="Quick chat task",
            source=TaskSource.QUICK_CHAT,
        )
        await database.store_task(task1)

        task2 = BackgroundTask.create(
            input_summary="iOS shortcut task",
            source=TaskSource.IOS_SHORTCUT,
        )
        await database.store_task(task2)

        quick_chat_tasks = await database.list_tasks(source=TaskSource.QUICK_CHAT)
        assert len(quick_chat_tasks) == 1
        assert quick_chat_tasks[0].source == TaskSource.QUICK_CHAT

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, database: TaskDatabase):
        """Test pagination of task listing."""
        for i in range(10):
            task = BackgroundTask.create(
                input_summary=f"Task {i}",
                source=TaskSource.CONVERSATION,
            )
            await database.store_task(task)

        # First page
        page1 = await database.list_tasks(limit=3, offset=0)
        assert len(page1) == 3

        # Second page
        page2 = await database.list_tasks(limit=3, offset=3)
        assert len(page2) == 3

        # Ensure no overlap
        page1_ids = {t.id for t in page1}
        page2_ids = {t.id for t in page2}
        assert page1_ids.isdisjoint(page2_ids)

    @pytest.mark.asyncio
    async def test_count_tasks(self, database: TaskDatabase):
        """Test counting tasks."""
        for i in range(7):
            task = BackgroundTask.create(
                input_summary=f"Task {i}",
                source=TaskSource.CONVERSATION,
            )
            await database.store_task(task)

        count = await database.count_tasks()
        assert count == 7

    @pytest.mark.asyncio
    async def test_get_pending_tasks(self, database: TaskDatabase):
        """Test getting pending tasks."""
        pending = BackgroundTask.create(
            input_summary="Pending",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )
        await database.store_task(pending)

        awaiting = BackgroundTask.create(
            input_summary="Awaiting",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )
        await database.store_task(awaiting)

        pending_tasks = await database.get_pending_tasks()
        assert len(pending_tasks) == 1
        assert pending_tasks[0].status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_awaiting_approval(self, database: TaskDatabase):
        """Test getting tasks awaiting approval."""
        pending = BackgroundTask.create(
            input_summary="Pending",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )
        await database.store_task(pending)

        awaiting = BackgroundTask.create(
            input_summary="Awaiting",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )
        await database.store_task(awaiting)

        awaiting_tasks = await database.get_awaiting_approval()
        assert len(awaiting_tasks) == 1
        assert awaiting_tasks[0].status == TaskStatus.AWAITING_APPROVAL


# ============== Manager Tests ==============

class TestTaskManager:
    """Tests for TaskManager."""

    @pytest.mark.asyncio
    async def test_create_task(self, manager: TaskManager):
        """Test creating a task through manager."""
        task = await manager.create_task(
            input_summary="Test task",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )

        assert task.id.startswith("task-")
        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_create_task_invalid_autonomy(self, manager: TaskManager):
        """Test creating task with invalid autonomy level."""
        with pytest.raises(ValueError):
            await manager.create_task(
                input_summary="Test",
                source=TaskSource.CONVERSATION,
                autonomy_level=5,
            )

    @pytest.mark.asyncio
    async def test_get_task(self, manager: TaskManager):
        """Test retrieving a task through manager."""
        task = await manager.create_task(
            input_summary="Test task",
            source=TaskSource.CONVERSATION,
        )

        retrieved = await manager.get_task(task.id)

        assert retrieved is not None
        assert retrieved.id == task.id

    @pytest.mark.asyncio
    async def test_approve_task(self, manager: TaskManager):
        """Test approving a task."""
        task = await manager.create_task(
            input_summary="Sensitive task",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )

        assert task.status == TaskStatus.AWAITING_APPROVAL

        approved = await manager.approve_task(task.id)

        assert approved.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_approve_non_awaiting_task_fails(self, manager: TaskManager):
        """Test approving a non-awaiting task fails."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )

        with pytest.raises(ValueError, match="not awaiting approval"):
            await manager.approve_task(task.id)

    @pytest.mark.asyncio
    async def test_cancel_pending_task(self, manager: TaskManager):
        """Test cancelling a pending task."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        cancelled = await manager.cancel_task(task.id)

        assert cancelled.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_awaiting_task(self, manager: TaskManager):
        """Test cancelling an awaiting approval task."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )

        cancelled = await manager.cancel_task(task.id)

        assert cancelled.status == TaskStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_running_task_fails(self, manager: TaskManager):
        """Test cancelling a running task fails."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        await manager.start_task(task.id)

        with pytest.raises(ValueError, match="cannot be cancelled"):
            await manager.cancel_task(task.id)

    @pytest.mark.asyncio
    async def test_retry_failed_task(self, manager: TaskManager):
        """Test retrying a failed task."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        await manager.start_task(task.id)
        await manager.fail_task(task.id, "Error occurred")

        retried = await manager.retry_task(task.id)

        assert retried.status == TaskStatus.PENDING
        assert retried.retry_count == 1

    @pytest.mark.asyncio
    async def test_retry_completed_task_fails(self, manager: TaskManager):
        """Test retrying a completed task fails."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        await manager.start_task(task.id)
        await manager.complete_task(task.id, "Done")

        with pytest.raises(ValueError, match="cannot be retried"):
            await manager.retry_task(task.id)

    @pytest.mark.asyncio
    async def test_start_task(self, manager: TaskManager):
        """Test starting a task."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        started = await manager.start_task(task.id)

        assert started.status == TaskStatus.IN_PROGRESS
        assert started.started_at is not None

    @pytest.mark.asyncio
    async def test_complete_task(self, manager: TaskManager):
        """Test completing a task."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        await manager.start_task(task.id)
        completed = await manager.complete_task(task.id, "Successfully completed", {"items": 3})

        assert completed.status == TaskStatus.COMPLETED
        assert completed.output_summary == "Successfully completed"
        assert completed.output_details == {"items": 3}

    @pytest.mark.asyncio
    async def test_fail_task(self, manager: TaskManager):
        """Test failing a task."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        await manager.start_task(task.id)
        failed = await manager.fail_task(task.id, "Connection error")

        assert failed.status == TaskStatus.FAILED
        assert failed.error_message == "Connection error"

    @pytest.mark.asyncio
    async def test_update_progress(self, manager: TaskManager):
        """Test updating task progress."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        await manager.start_task(task.id)
        updated = await manager.update_progress(task.id, 0.5)

        assert updated.progress == 0.5

    @pytest.mark.asyncio
    async def test_escalate_task(self, manager: TaskManager):
        """Test escalating a task."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
            autonomy_level=4,
        )

        escalated = await manager.escalate_task(task.id, "External API required")

        assert escalated.escalated is True
        assert escalated.escalation_reason == "External API required"
        assert escalated.status == TaskStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_list_tasks_pagination(self, manager: TaskManager):
        """Test task listing with pagination."""
        for i in range(10):
            await manager.create_task(
                input_summary=f"Task {i}",
                source=TaskSource.CONVERSATION,
            )

        page1 = await manager.list_tasks(limit=5, offset=0)
        page2 = await manager.list_tasks(limit=5, offset=5)

        assert len(page1) == 5
        assert len(page2) == 5

    @pytest.mark.asyncio
    async def test_get_pending_tasks(self, manager: TaskManager):
        """Test getting pending tasks."""
        await manager.create_task(
            input_summary="Pending 1",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )
        await manager.create_task(
            input_summary="Pending 2",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )
        await manager.create_task(
            input_summary="Awaiting",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )

        pending = await manager.get_pending_tasks()

        assert len(pending) == 2
        assert all(t.status == TaskStatus.PENDING for t in pending)

    @pytest.mark.asyncio
    async def test_get_awaiting_approval(self, manager: TaskManager):
        """Test getting tasks awaiting approval."""
        await manager.create_task(
            input_summary="Normal",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )
        await manager.create_task(
            input_summary="Needs approval",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )

        awaiting = await manager.get_awaiting_approval()

        assert len(awaiting) == 1
        assert awaiting[0].status == TaskStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_get_active_tasks(self, manager: TaskManager):
        """Test getting active (in progress) tasks."""
        task1 = await manager.create_task(
            input_summary="Task 1",
            source=TaskSource.CONVERSATION,
        )
        task2 = await manager.create_task(
            input_summary="Task 2",
            source=TaskSource.CONVERSATION,
        )

        await manager.start_task(task1.id)

        active = await manager.get_active_tasks()

        assert len(active) == 1
        assert active[0].id == task1.id

    @pytest.mark.asyncio
    async def test_delete_task(self, manager: TaskManager):
        """Test deleting a task."""
        task = await manager.create_task(
            input_summary="Test",
            source=TaskSource.CONVERSATION,
        )

        deleted = await manager.delete_task(task.id)

        assert deleted is True

        retrieved = await manager.get_task(task.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, manager: TaskManager):
        """Test getting a nonexistent task."""
        task = await manager.get_task("nonexistent-id")
        assert task is None

    @pytest.mark.asyncio
    async def test_approve_nonexistent_task_fails(self, manager: TaskManager):
        """Test approving a nonexistent task fails."""
        with pytest.raises(ValueError, match="not found"):
            await manager.approve_task("nonexistent-id")


# ============== Autonomy Level Tests ==============

class TestAutonomyLevels:
    """Tests for autonomy level behavior."""

    def test_autonomy_level_enum(self):
        """Test AutonomyLevel enum values."""
        assert AutonomyLevel.EXPLICIT.value == 1
        assert AutonomyLevel.CONFIRM.value == 2
        assert AutonomyLevel.NOTIFY.value == 3
        assert AutonomyLevel.SILENT.value == 4

    @pytest.mark.asyncio
    async def test_level_1_requires_approval(self, manager: TaskManager):
        """Test level 1 (explicit) requires approval."""
        task = await manager.create_task(
            input_summary="Sensitive action",
            source=TaskSource.CONVERSATION,
            autonomy_level=1,
        )

        assert task.status == TaskStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_level_2_requires_approval(self, manager: TaskManager):
        """Test level 2 (confirm) requires approval."""
        task = await manager.create_task(
            input_summary="External communication",
            source=TaskSource.CONVERSATION,
            autonomy_level=2,
        )

        assert task.status == TaskStatus.AWAITING_APPROVAL

    @pytest.mark.asyncio
    async def test_level_3_is_pending(self, manager: TaskManager):
        """Test level 3 (notify) starts pending."""
        task = await manager.create_task(
            input_summary="Standard action",
            source=TaskSource.CONVERSATION,
            autonomy_level=3,
        )

        assert task.status == TaskStatus.PENDING

    @pytest.mark.asyncio
    async def test_level_4_is_pending(self, manager: TaskManager):
        """Test level 4 (silent) starts pending."""
        task = await manager.create_task(
            input_summary="Internal lookup",
            source=TaskSource.CONVERSATION,
            autonomy_level=4,
        )

        assert task.status == TaskStatus.PENDING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
