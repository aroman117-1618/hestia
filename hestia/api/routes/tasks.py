"""
Background task management routes for Hestia API.

Per ADR-021: Background Task Management
Per ADR-022: Governed Auto-Persistence for Background Tasks

Provides REST endpoints for task submission, tracking, and approval workflows.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.schemas import (
    TaskCreateRequest,
    TaskResponse,
    TaskListResponse,
    TaskApprovalResponse,
    TaskRetryResponse,
    TaskStatusEnum,
    TaskSourceEnum,
    ErrorResponse,
)
from hestia.api.middleware.auth import get_device_token
from hestia.tasks import get_task_manager, TaskStatus, TaskSource, BackgroundTask
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/tasks", tags=["tasks"])
logger = get_logger()


def _task_to_response(task: BackgroundTask) -> TaskResponse:
    """Convert a BackgroundTask to API response."""
    return TaskResponse(
        task_id=task.id,
        status=TaskStatusEnum(task.status.value),
        source=TaskSourceEnum(task.source.value),
        input_summary=task.input_summary,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        output_summary=task.output_summary,
        output_details=task.output_details,
        progress=task.progress,
        autonomy_level=task.autonomy_level,
        escalated=task.escalated,
        escalation_reason=task.escalation_reason,
        error_message=task.error_message,
        retry_count=task.retry_count,
    )


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Create background task",
    description="Submit a new background task for async execution (ADR-021)."
)
async def create_task(
    request: TaskCreateRequest,
    device_id: str = Depends(get_device_token),
) -> TaskResponse:
    """
    Create a new background task.

    Tasks are queued for execution based on their autonomy level:
    - Level 1-2: Await approval before execution
    - Level 3-4: Execute immediately

    Args:
        request: Task creation request with input and settings.
        device_id: Device ID from authentication token.

    Returns:
        TaskResponse with created task details.
    """
    try:
        manager = await get_task_manager()

        # Map API enum to internal enum
        source = TaskSource(request.source.value)

        task = await manager.create_task(
            input_summary=request.input,
            source=source,
            autonomy_level=request.autonomy_level,
            device_id=device_id,
        )

        logger.info(
            "Task created",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "task_id": task.id,
                "source": source.value,
                "autonomy_level": request.autonomy_level,
                "status": task.status.value,
            }
        )

        return _task_to_response(task)

    except ValueError as e:
        logger.warning(
            f"Invalid task request: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "message": "Invalid task parameters.",
            }
        )

    except Exception as e:
        logger.error(
            f"Failed to create task: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to create task.",
            }
        )


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List tasks",
    description="List background tasks with optional filters."
)
async def list_tasks(
    status_filter: Optional[TaskStatusEnum] = Query(
        None,
        alias="status",
        description="Filter by task status"
    ),
    source_filter: Optional[TaskSourceEnum] = Query(
        None,
        alias="source",
        description="Filter by task source"
    ),
    limit: int = Query(50, ge=1, le=100, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Results offset for pagination"),
    device_id: str = Depends(get_device_token),
) -> TaskListResponse:
    """
    List background tasks with optional filters.

    Supports filtering by status, source, and pagination.

    Args:
        status_filter: Optional status to filter by.
        source_filter: Optional source to filter by.
        limit: Maximum number of results (1-100).
        offset: Results offset for pagination.
        device_id: Device ID from authentication token.

    Returns:
        TaskListResponse with matching tasks.
    """
    try:
        manager = await get_task_manager()

        # Convert API enums to internal enums
        internal_status = TaskStatus(status_filter.value) if status_filter else None
        internal_source = TaskSource(source_filter.value) if source_filter else None

        tasks = await manager.list_tasks(
            status=internal_status,
            source=internal_source,
            device_id=device_id,
            limit=limit,
            offset=offset,
        )

        count = await manager.count_tasks(
            status=internal_status,
            source=internal_source,
            device_id=device_id,
        )

        logger.info(
            "Tasks listed",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "filter_status": status_filter.value if status_filter else None,
                "filter_source": source_filter.value if source_filter else None,
                "result_count": len(tasks),
                "total_count": count,
            }
        )

        return TaskListResponse(
            tasks=[_task_to_response(task) for task in tasks],
            count=count,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(
            f"Failed to list tasks: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to list tasks.",
            }
        )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get task details",
    description="Retrieve details of a specific task."
)
async def get_task(
    task_id: str,
    device_id: str = Depends(get_device_token),
) -> TaskResponse:
    """
    Get details of a specific task.

    Args:
        task_id: Task identifier.
        device_id: Device ID from authentication token.

    Returns:
        TaskResponse with task details.
    """
    try:
        manager = await get_task_manager()
        task = await manager.get_task(task_id)

        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "task_not_found",
                    "message": f"Task '{task_id}' not found.",
                }
            )

        logger.debug(
            "Task retrieved",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "task_id": task_id,
            }
        )

        return _task_to_response(task)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to get task: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to retrieve task.",
            }
        )


@router.post(
    "/{task_id}/approve",
    response_model=TaskApprovalResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Task cannot be approved"},
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Approve task",
    description="Approve a task that is awaiting approval (ADR-022)."
)
async def approve_task(
    task_id: str,
    device_id: str = Depends(get_device_token),
) -> TaskApprovalResponse:
    """
    Approve a task awaiting approval.

    This moves the task from AWAITING_APPROVAL to PENDING status,
    allowing it to be picked up for execution.

    Args:
        task_id: Task identifier.
        device_id: Device ID from authentication token.

    Returns:
        TaskApprovalResponse with new status.
    """
    try:
        manager = await get_task_manager()
        task = await manager.approve_task(task_id)

        logger.info(
            "Task approved",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "task_id": task_id,
            }
        )

        return TaskApprovalResponse(
            task_id=task.id,
            status=TaskStatusEnum(task.status.value),
            message="Task approved and queued for execution.",
        )

    except ValueError as e:
        error_msg = str(e)
        logger.warning(
            f"Task approval failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "task_not_found",
                    "message": f"Task '{task_id}' not found.",
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_operation",
                    "message": "Task cannot be approved in its current state.",
                }
            )

    except Exception as e:
        logger.error(
            f"Failed to approve task: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to approve task.",
            }
        )


@router.post(
    "/{task_id}/cancel",
    response_model=TaskApprovalResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Task cannot be cancelled"},
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Cancel task",
    description="Cancel a pending or awaiting approval task."
)
async def cancel_task(
    task_id: str,
    device_id: str = Depends(get_device_token),
) -> TaskApprovalResponse:
    """
    Cancel a task.

    Only tasks in PENDING or AWAITING_APPROVAL status can be cancelled.

    Args:
        task_id: Task identifier.
        device_id: Device ID from authentication token.

    Returns:
        TaskApprovalResponse with cancelled status.
    """
    try:
        manager = await get_task_manager()
        task = await manager.cancel_task(task_id)

        logger.info(
            "Task cancelled",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "task_id": task_id,
            }
        )

        return TaskApprovalResponse(
            task_id=task.id,
            status=TaskStatusEnum(task.status.value),
            message="Task has been cancelled.",
        )

    except ValueError as e:
        error_msg = str(e)
        logger.warning(
            f"Task cancellation failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "task_not_found",
                    "message": f"Task '{task_id}' not found.",
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_operation",
                    "message": "Task cannot be cancelled in its current state.",
                }
            )

    except Exception as e:
        logger.error(
            f"Failed to cancel task: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to cancel task.",
            }
        )


@router.post(
    "/{task_id}/retry",
    response_model=TaskRetryResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Task cannot be retried"},
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Retry task",
    description="Retry a failed task."
)
async def retry_task(
    task_id: str,
    device_id: str = Depends(get_device_token),
) -> TaskRetryResponse:
    """
    Retry a failed task.

    Only tasks in FAILED status can be retried. The task is reset
    to PENDING status with an incremented retry count.

    Args:
        task_id: Task identifier.
        device_id: Device ID from authentication token.

    Returns:
        TaskRetryResponse with new status and retry count.
    """
    try:
        manager = await get_task_manager()
        task = await manager.retry_task(task_id)

        logger.info(
            "Task retry initiated",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "task_id": task_id,
                "retry_count": task.retry_count,
            }
        )

        return TaskRetryResponse(
            task_id=task.id,
            status=TaskStatusEnum(task.status.value),
            retry_count=task.retry_count,
            message=f"Task queued for retry (attempt #{task.retry_count}).",
        )

    except ValueError as e:
        error_msg = str(e)
        logger.warning(
            f"Task retry failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )
        if "not found" in error_msg.lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "task_not_found",
                    "message": f"Task '{task_id}' not found.",
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_operation",
                    "message": "Task cannot be retried in its current state.",
                }
            )

    except Exception as e:
        logger.error(
            f"Failed to retry task: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"task_id": task_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to retry task.",
            }
        )
