"""
State machine for Hestia task management.

Manages task lifecycle with validated transitions and logging.
"""

import asyncio
from datetime import datetime, timezone
from typing import Callable, Dict, Optional

from hestia.logging import get_logger, LogComponent
from hestia.orchestration.models import (
    Task,
    TaskState,
    Request,
    Response,
    ResponseType,
    VALID_TRANSITIONS,
    is_valid_transition,
)


class InvalidTransitionError(Exception):
    """Raised when attempting an invalid state transition."""
    pass


class TaskTimeoutError(Exception):
    """Raised when a task times out."""
    pass


class TaskStateMachine:
    """
    Manages task state with logged transitions.

    Enforces valid state transitions and handles timeouts.
    """

    # Default timeouts per state (seconds)
    DEFAULT_TIMEOUTS = {
        TaskState.RECEIVED: 5.0,       # Should move to processing quickly
        TaskState.PROCESSING: 600.0,   # R1 reasoning model needs 5+ min on M1
        TaskState.AWAITING_TOOL: 60.0, # Tool execution timeout
    }

    def __init__(
        self,
        timeouts: Optional[Dict[TaskState, float]] = None,
    ):
        """
        Initialize state machine.

        Args:
            timeouts: Optional custom timeouts per state.
        """
        self.timeouts = {**self.DEFAULT_TIMEOUTS, **(timeouts or {})}
        self.logger = get_logger()
        self._tasks: Dict[str, Task] = {}

    def create_task(self, request: Request) -> Task:
        """
        Create a new task from a request.

        Args:
            request: The incoming request.

        Returns:
            A new Task in RECEIVED state.
        """
        task = Task(request=request)
        self._tasks[request.id] = task

        self.logger.info(
            f"Task created: {request.id}",
            component=LogComponent.ORCHESTRATION,
            data={
                "request_id": request.id,
                "mode": request.mode.value,
                "source": request.source.value,
                "session_id": request.session_id,
            }
        )

        return task

    def get_task(self, request_id: str) -> Optional[Task]:
        """Get a task by request ID."""
        return self._tasks.get(request_id)

    def transition(
        self,
        task: Task,
        new_state: TaskState,
        reason: str = "",
    ) -> None:
        """
        Transition a task to a new state.

        Args:
            task: The task to transition.
            new_state: The target state.
            reason: Optional reason for the transition.

        Raises:
            InvalidTransitionError: If the transition is not allowed.
        """
        old_state = task.state

        if not is_valid_transition(old_state, new_state):
            raise InvalidTransitionError(
                f"Invalid transition: {old_state.value} -> {new_state.value}"
            )

        task.transition_to(new_state, reason)

        self.logger.log_state_change(
            from_state=old_state.value,
            to_state=new_state.value,
            reason=f"{reason} (request: {task.request.id})"
        )

    def start_processing(self, task: Task) -> None:
        """Move task to PROCESSING state."""
        self.transition(task, TaskState.PROCESSING, "Starting inference")

    def await_tool(self, task: Task, tool_name: str) -> None:
        """Move task to AWAITING_TOOL state."""
        self.transition(task, TaskState.AWAITING_TOOL, f"Awaiting tool: {tool_name}")

    def resume_processing(self, task: Task) -> None:
        """Resume processing after tool execution."""
        self.transition(task, TaskState.PROCESSING, "Tool execution complete")

    def complete(self, task: Task, response: Response) -> None:
        """Mark task as completed with response."""
        task.response = response
        self.transition(task, TaskState.COMPLETED, "Task completed successfully")

        # Log completion metrics
        self.logger.info(
            f"Task completed: {task.request.id}",
            component=LogComponent.ORCHESTRATION,
            data={
                "request_id": task.request.id,
                "duration_ms": task.duration_ms,
                "tokens_in": response.tokens_in,
                "tokens_out": response.tokens_out,
            }
        )

    def fail(self, task: Task, error: Exception) -> None:
        """Mark task as failed with error."""
        # Guard: if already in a terminal state, just log and return
        if task.state in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}:
            self.logger.warning(
                f"Task already in terminal state {task.state.value}, ignoring fail({type(error).__name__})",
                component=LogComponent.ORCHESTRATION,
                data={"request_id": task.request.id, "state": task.state.value},
            )
            return

        task.error = error
        task.response = Response(
            request_id=task.request.id,
            content="I encountered an error processing your request.",
            response_type=ResponseType.ERROR,
            mode=task.request.mode,
            error_code=type(error).__name__,
            error_message=str(error),
        )

        self.transition(task, TaskState.FAILED, f"Error: {type(error).__name__}")

        # Log error
        self.logger.error(
            f"Task failed: {task.request.id} - {type(error).__name__}: {error}",
            component=LogComponent.ORCHESTRATION,
            data={"request_id": task.request.id, "error_type": type(error).__name__}
        )

    def cancel(self, task: Task, reason: str = "User cancelled") -> None:
        """Cancel a task."""
        task.response = Response(
            request_id=task.request.id,
            content="Request cancelled.",
            response_type=ResponseType.TEXT,
            mode=task.request.mode,
        )

        self.transition(task, TaskState.CANCELLED, reason)

    async def run_with_timeout(
        self,
        task: Task,
        coroutine: Callable,
        *args,
        **kwargs
    ):
        """
        Run a coroutine with state-appropriate timeout.

        Args:
            task: The task being processed.
            coroutine: The async function to run.
            *args, **kwargs: Arguments to pass to the coroutine.

        Returns:
            The result of the coroutine.

        Raises:
            TaskTimeoutError: If the operation times out.
        """
        timeout = self.timeouts.get(task.state, 60.0)

        try:
            return await asyncio.wait_for(
                coroutine(*args, **kwargs),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            raise TaskTimeoutError(
                f"Task {task.request.id} timed out in state {task.state.value} "
                f"after {timeout}s"
            )

    def cleanup_old_tasks(self, max_age_seconds: float = 3600) -> int:
        """
        Remove completed/failed tasks older than max_age.

        Args:
            max_age_seconds: Maximum age in seconds.

        Returns:
            Number of tasks removed.
        """
        now = datetime.now(timezone.utc)
        to_remove = []

        for task_id, task in self._tasks.items():
            if task.state in {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}:
                age = (now - task.updated_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(task_id)

        for task_id in to_remove:
            del self._tasks[task_id]

        if to_remove:
            self.logger.debug(
                f"Cleaned up {len(to_remove)} old tasks",
                component=LogComponent.ORCHESTRATION
            )

        return len(to_remove)

    @property
    def active_task_count(self) -> int:
        """Count of tasks in non-terminal states."""
        terminal = {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}
        return sum(1 for t in self._tasks.values() if t.state not in terminal)

    def get_state_summary(self) -> Dict[str, int]:
        """Get count of tasks per state."""
        summary = {state.value: 0 for state in TaskState}
        for task in self._tasks.values():
            summary[task.state.value] += 1
        return summary
