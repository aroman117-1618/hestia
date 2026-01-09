"""
Orders API routes.

CRUD operations for scheduled orders and execution tracking.
"""

from datetime import datetime, time, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.middleware.auth import get_current_device
from hestia.api.schemas import (
    OrderCreateRequest,
    OrderUpdateRequest,
    OrderResponse,
    OrderListResponse,
    OrderDeleteResponse,
    OrderExecutionsResponse,
    OrderExecutionDetail,
    OrderExecuteResponse,
    OrderFrequency as OrderFrequencySchema,
    OrderFrequencyTypeEnum,
    OrderStatusEnum,
    ExecutionStatusEnum,
    MCPResourceEnum,
    OrderExecutionSummary,
)
from hestia.orders import (
    get_order_manager,
    get_order_scheduler,
    Order,
    OrderFrequency,
    FrequencyType,
    OrderStatus,
    ExecutionStatus,
    MCPResource,
)
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/orders", tags=["orders"])
logger = get_logger()


# =============================================================================
# Helper Functions
# =============================================================================

def _parse_time(time_str: str) -> time:
    """Parse time string (HH:MM:SS or HH:MM)."""
    try:
        if len(time_str) == 5:
            return datetime.strptime(time_str, "%H:%M").time()
        return datetime.strptime(time_str, "%H:%M:%S").time()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time format: {time_str}. Use HH:MM:SS or HH:MM."
        )


def _map_frequency_type(schema_type: OrderFrequencyTypeEnum) -> FrequencyType:
    """Map schema frequency type to domain model."""
    mapping = {
        OrderFrequencyTypeEnum.ONCE: FrequencyType.ONCE,
        OrderFrequencyTypeEnum.DAILY: FrequencyType.DAILY,
        OrderFrequencyTypeEnum.WEEKLY: FrequencyType.WEEKLY,
        OrderFrequencyTypeEnum.MONTHLY: FrequencyType.MONTHLY,
        OrderFrequencyTypeEnum.CUSTOM: FrequencyType.CUSTOM,
    }
    return mapping[schema_type]


def _map_status(schema_status: OrderStatusEnum) -> OrderStatus:
    """Map schema status to domain model."""
    mapping = {
        OrderStatusEnum.ACTIVE: OrderStatus.ACTIVE,
        OrderStatusEnum.INACTIVE: OrderStatus.INACTIVE,
    }
    return mapping[schema_status]


def _map_resources(schema_resources: list[MCPResourceEnum]) -> set[MCPResource]:
    """Map schema resources to domain model."""
    mapping = {
        MCPResourceEnum.FIRECRAWL: MCPResource.FIRECRAWL,
        MCPResourceEnum.GITHUB: MCPResource.GITHUB,
        MCPResourceEnum.APPLE_NEWS: MCPResource.APPLE_NEWS,
        MCPResourceEnum.FIDELITY: MCPResource.FIDELITY,
        MCPResourceEnum.CALENDAR: MCPResource.CALENDAR,
        MCPResourceEnum.EMAIL: MCPResource.EMAIL,
        MCPResourceEnum.REMINDER: MCPResource.REMINDER,
        MCPResourceEnum.NOTE: MCPResource.NOTE,
        MCPResourceEnum.SHORTCUT: MCPResource.SHORTCUT,
    }
    return {mapping[r] for r in schema_resources}


def _order_to_response(order: Order, next_execution: Optional[datetime] = None) -> OrderResponse:
    """Convert domain Order to API response."""
    last_exec = None
    if order.last_execution:
        last_exec = OrderExecutionSummary(
            execution_id=order.last_execution.id,
            timestamp=order.last_execution.timestamp,
            status=ExecutionStatusEnum(order.last_execution.status.value),
        )

    return OrderResponse(
        order_id=order.id,
        name=order.name,
        prompt=order.prompt,
        scheduled_time=order.scheduled_time.isoformat(),
        frequency=OrderFrequencySchema(
            type=OrderFrequencyTypeEnum(order.frequency.type.value),
            minutes=order.frequency.minutes,
        ),
        resources=[MCPResourceEnum(r.value) for r in order.resources],
        status=OrderStatusEnum(order.status.value),
        next_execution=next_execution,
        last_execution=last_exec,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


# =============================================================================
# Routes
# =============================================================================

@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new order",
    description="Create a scheduled recurring prompt (standing order).",
)
async def create_order(
    request: OrderCreateRequest,
    device_id: str = Depends(get_current_device),
):
    """Create a new order."""
    manager = await get_order_manager()
    scheduler = await get_order_scheduler()

    try:
        order = await manager.create_order(
            name=request.name,
            prompt=request.prompt,
            scheduled_time=_parse_time(request.scheduled_time),
            frequency=OrderFrequency(
                type=_map_frequency_type(request.frequency.type),
                minutes=request.frequency.minutes,
            ),
            resources=_map_resources(request.resources),
            status=_map_status(request.status),
        )

        # Schedule the order
        await scheduler.schedule_order(order)

        next_exec = scheduler.get_next_execution_time(order.id)

        logger.info(
            f"Order created via API: {order.id}",
            component=LogComponent.API,
            data={"order_id": order.id, "device_id": device_id},
        )

        return _order_to_response(order, next_exec)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.get(
    "",
    response_model=OrderListResponse,
    summary="List orders",
    description="List all orders with optional status filter.",
)
async def list_orders(
    status_filter: Optional[OrderStatusEnum] = Query(None, alias="status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_current_device),
):
    """List orders."""
    manager = await get_order_manager()
    scheduler = await get_order_scheduler()

    domain_status = None
    if status_filter:
        domain_status = _map_status(status_filter)

    orders = await manager.list_orders(
        status=domain_status,
        limit=limit,
        offset=offset,
    )

    total = await manager.count_orders(status=domain_status)

    order_responses = []
    for order in orders:
        next_exec = scheduler.get_next_execution_time(order.id)
        order_responses.append(_order_to_response(order, next_exec))

    return OrderListResponse(
        orders=order_responses,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Get order details",
    description="Get detailed information about a specific order.",
)
async def get_order(
    order_id: str,
    device_id: str = Depends(get_current_device),
):
    """Get order by ID."""
    manager = await get_order_manager()
    scheduler = await get_order_scheduler()

    order = await manager.get_order(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order not found: {order_id}",
        )

    next_exec = scheduler.get_next_execution_time(order_id)

    return _order_to_response(order, next_exec)


@router.patch(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Update order",
    description="Update an existing order. All fields are optional.",
)
async def update_order(
    order_id: str,
    request: OrderUpdateRequest,
    device_id: str = Depends(get_current_device),
):
    """Update an order."""
    manager = await get_order_manager()
    scheduler = await get_order_scheduler()

    try:
        # Build update kwargs
        kwargs = {}
        if request.name is not None:
            kwargs["name"] = request.name
        if request.prompt is not None:
            kwargs["prompt"] = request.prompt
        if request.scheduled_time is not None:
            kwargs["scheduled_time"] = _parse_time(request.scheduled_time)
        if request.frequency is not None:
            kwargs["frequency"] = OrderFrequency(
                type=_map_frequency_type(request.frequency.type),
                minutes=request.frequency.minutes,
            )
        if request.resources is not None:
            kwargs["resources"] = _map_resources(request.resources)
        if request.status is not None:
            kwargs["status"] = _map_status(request.status)

        order = await manager.update_order(order_id, **kwargs)

        # Reschedule
        await scheduler.reschedule_order(order)

        next_exec = scheduler.get_next_execution_time(order_id)

        logger.info(
            f"Order updated via API: {order_id}",
            component=LogComponent.API,
            data={"order_id": order_id, "device_id": device_id},
        )

        return _order_to_response(order, next_exec)

    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.delete(
    "/{order_id}",
    response_model=OrderDeleteResponse,
    summary="Delete order",
    description="Delete an order and all its execution history.",
)
async def delete_order(
    order_id: str,
    device_id: str = Depends(get_current_device),
):
    """Delete an order."""
    manager = await get_order_manager()
    scheduler = await get_order_scheduler()

    # Unschedule first
    await scheduler.unschedule_order(order_id)

    deleted = await manager.delete_order(order_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order not found: {order_id}",
        )

    logger.info(
        f"Order deleted via API: {order_id}",
        component=LogComponent.API,
        data={"order_id": order_id, "device_id": device_id},
    )

    return OrderDeleteResponse(
        order_id=order_id,
        deleted=True,
        message="Order deleted successfully",
    )


@router.get(
    "/{order_id}/executions",
    response_model=OrderExecutionsResponse,
    summary="List order executions",
    description="Get execution history for an order.",
)
async def list_executions(
    order_id: str,
    status_filter: Optional[ExecutionStatusEnum] = Query(None, alias="status"),
    since: Optional[datetime] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_current_device),
):
    """List executions for an order."""
    manager = await get_order_manager()

    # Verify order exists
    order = await manager.get_order(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order not found: {order_id}",
        )

    domain_status = None
    if status_filter:
        domain_status = ExecutionStatus(status_filter.value)

    executions = await manager.list_executions(
        order_id=order_id,
        status=domain_status,
        since=since,
        limit=limit,
        offset=offset,
    )

    total = await manager.count_executions(
        order_id=order_id,
        status=domain_status,
        since=since,
    )

    execution_details = [
        OrderExecutionDetail(
            execution_id=e.id,
            timestamp=e.timestamp,
            status=ExecutionStatusEnum(e.status.value),
            hestia_read=e.hestia_read,
            full_response=e.full_response,
            duration_ms=e.duration_ms,
            resources_used=[MCPResourceEnum(r.value) for r in e.resources_used],
        )
        for e in executions
    ]

    return OrderExecutionsResponse(
        order_id=order_id,
        executions=execution_details,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{order_id}/execute",
    response_model=OrderExecuteResponse,
    summary="Execute order now",
    description="Manually trigger an order execution.",
)
async def execute_order(
    order_id: str,
    device_id: str = Depends(get_current_device),
):
    """Execute an order immediately."""
    manager = await get_order_manager()

    try:
        execution = await manager.execute_order(order_id)

        logger.info(
            f"Manual execution triggered: {order_id}",
            component=LogComponent.API,
            data={
                "order_id": order_id,
                "execution_id": execution.id,
                "device_id": device_id,
            },
        )

        return OrderExecuteResponse(
            order_id=order_id,
            execution_id=execution.id,
            status=ExecutionStatusEnum(execution.status.value),
            message="Order execution started",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
