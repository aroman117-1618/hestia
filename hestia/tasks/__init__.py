"""
Background task management module.

Per ADR-021: Background Task Management
Per ADR-022: Governed Auto-Persistence for Background Tasks

Provides fire-and-forget task submission from iOS Shortcuts and Quick Chat,
with asynchronous execution tracking and approval workflows.
"""

from hestia.tasks.models import (
    BackgroundTask,
    TaskStatus,
    TaskSource,
    AutonomyLevel,
)

from hestia.tasks.database import (
    TaskDatabase,
    get_task_database,
    close_task_database,
)

from hestia.tasks.manager import (
    TaskManager,
    get_task_manager,
    close_task_manager,
)


__all__ = [
    # Models
    "BackgroundTask",
    "TaskStatus",
    "TaskSource",
    "AutonomyLevel",
    # Database
    "TaskDatabase",
    "get_task_database",
    "close_task_database",
    # Manager
    "TaskManager",
    "get_task_manager",
    "close_task_manager",
]
