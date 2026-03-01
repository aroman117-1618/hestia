"""
Order manager for orchestrating order operations.

Coordinates order lifecycle including creation, updates,
execution tracking, and scheduling integration.
"""

from datetime import datetime, time, timezone
from typing import Any, Dict, List, Optional, Set

from hestia.logging import get_logger, LogComponent

from .models import (
    Order,
    OrderExecution,
    OrderStatus,
    OrderFrequency,
    FrequencyType,
    ExecutionStatus,
    MCPResource,
)
from .database import OrderDatabase, get_order_database


class OrderManager:
    """
    Manages order lifecycle.

    Handles order CRUD, execution tracking, and coordinates
    with the scheduler for recurring execution.
    """

    def __init__(self, database: Optional[OrderDatabase] = None):
        """
        Initialize order manager.

        Args:
            database: OrderDatabase instance. If None, uses singleton.
        """
        self._database = database
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the order manager and its dependencies."""
        if self._database is None:
            self._database = await get_order_database()

        self.logger.info(
            "Order manager initialized",
            component=LogComponent.EXECUTION,
        )

    async def close(self) -> None:
        """Close order manager resources."""
        self.logger.debug(
            "Order manager closed",
            component=LogComponent.EXECUTION,
        )

    async def __aenter__(self) -> "OrderManager":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def database(self) -> OrderDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("Order manager not initialized. Call initialize() first.")
        return self._database

    # =========================================================================
    # Order CRUD
    # =========================================================================

    async def create_order(
        self,
        name: str,
        prompt: str,
        scheduled_time: time,
        frequency: OrderFrequency,
        resources: Set[MCPResource],
        status: OrderStatus = OrderStatus.ACTIVE,
    ) -> Order:
        """
        Create a new order.

        Args:
            name: Human-readable name.
            prompt: The prompt to execute.
            scheduled_time: Time of day to execute.
            frequency: Execution frequency.
            resources: MCP resources to use.
            status: Initial status.

        Returns:
            Created Order.

        Raises:
            ValueError: If order validation fails.
        """
        order = Order.create(
            name=name,
            prompt=prompt,
            scheduled_time=scheduled_time,
            frequency=frequency,
            resources=resources,
            status=status,
        )

        errors = order.validate()
        if errors:
            raise ValueError(f"Order validation failed: {', '.join(errors)}")

        await self.database.store_order(order)

        self.logger.info(
            f"Order created: {order.id}",
            component=LogComponent.EXECUTION,
            data={
                "order_id": order.id,
                "name": name,
                "frequency": frequency.type.value,
            },
        )

        return order

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Get an order by ID."""
        return await self.database.get_order(order_id)

    async def update_order(
        self,
        order_id: str,
        name: Optional[str] = None,
        prompt: Optional[str] = None,
        scheduled_time: Optional[time] = None,
        frequency: Optional[OrderFrequency] = None,
        resources: Optional[Set[MCPResource]] = None,
        status: Optional[OrderStatus] = None,
    ) -> Order:
        """
        Update an existing order.

        Args:
            order_id: Order ID to update.
            name: New name (optional).
            prompt: New prompt (optional).
            scheduled_time: New scheduled time (optional).
            frequency: New frequency (optional).
            resources: New resources (optional).
            status: New status (optional).

        Returns:
            Updated Order.

        Raises:
            ValueError: If order not found or validation fails.
        """
        order = await self.database.get_order(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        # Apply updates
        if name is not None:
            order.name = name
        if prompt is not None:
            order.prompt = prompt
        if scheduled_time is not None:
            order.scheduled_time = scheduled_time
        if frequency is not None:
            order.frequency = frequency
        if resources is not None:
            order.resources = resources
        if status is not None:
            order.status = status

        # Validate
        errors = order.validate()
        if errors:
            raise ValueError(f"Order validation failed: {', '.join(errors)}")

        await self.database.update_order(order)

        self.logger.info(
            f"Order updated: {order_id}",
            component=LogComponent.EXECUTION,
            data={"order_id": order_id},
        )

        return order

    async def delete_order(self, order_id: str) -> bool:
        """
        Delete an order.

        Args:
            order_id: Order ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        deleted = await self.database.delete_order(order_id)

        if deleted:
            self.logger.info(
                f"Order deleted: {order_id}",
                component=LogComponent.EXECUTION,
            )

        return deleted

    async def list_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """List orders with optional filters."""
        return await self.database.list_orders(
            status=status,
            limit=limit,
            offset=offset,
        )

    async def count_orders(self, status: Optional[OrderStatus] = None) -> int:
        """Count orders with optional filter."""
        return await self.database.count_orders(status=status)

    async def get_active_orders(self) -> List[Order]:
        """Get all active orders."""
        return await self.database.get_active_orders()

    # =========================================================================
    # Execution Management
    # =========================================================================

    async def start_execution(self, order_id: str) -> OrderExecution:
        """
        Start a new execution for an order.

        Args:
            order_id: Order to execute.

        Returns:
            New OrderExecution in RUNNING status.

        Raises:
            ValueError: If order not found.
        """
        order = await self.database.get_order(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        execution = OrderExecution.create(order_id)
        await self.database.store_execution(execution)

        self.logger.info(
            f"Execution started: {execution.id}",
            component=LogComponent.EXECUTION,
            data={
                "execution_id": execution.id,
                "order_id": order_id,
                "order_name": order.name,
            },
        )

        return execution

    async def complete_execution(
        self,
        execution_id: str,
        hestia_read: Optional[str] = None,
        full_response: Optional[str] = None,
        resources_used: Optional[List[MCPResource]] = None,
    ) -> OrderExecution:
        """
        Complete an execution successfully.

        Args:
            execution_id: Execution ID.
            hestia_read: Summary for user display.
            full_response: Full response text.
            resources_used: Resources that were used.

        Returns:
            Updated OrderExecution.

        Raises:
            ValueError: If execution not found.
        """
        execution = await self.database.get_execution(execution_id)
        if execution is None:
            raise ValueError(f"Execution not found: {execution_id}")

        execution.complete(
            hestia_read=hestia_read,
            full_response=full_response,
            resources_used=resources_used,
        )

        await self.database.update_execution(execution)
        await self.database.increment_execution_counts(execution.order_id, success=True)

        self.logger.info(
            f"Execution completed: {execution_id}",
            component=LogComponent.EXECUTION,
            data={
                "execution_id": execution_id,
                "order_id": execution.order_id,
                "duration_ms": execution.duration_ms,
            },
        )

        return execution

    async def fail_execution(
        self,
        execution_id: str,
        error_message: str,
    ) -> OrderExecution:
        """
        Mark an execution as failed.

        Args:
            execution_id: Execution ID.
            error_message: Error description.

        Returns:
            Updated OrderExecution.

        Raises:
            ValueError: If execution not found.
        """
        execution = await self.database.get_execution(execution_id)
        if execution is None:
            raise ValueError(f"Execution not found: {execution_id}")

        execution.fail(error_message)

        await self.database.update_execution(execution)
        await self.database.increment_execution_counts(execution.order_id, success=False)

        self.logger.warning(
            f"Execution failed: {execution_id}",
            component=LogComponent.EXECUTION,
            data={
                "execution_id": execution_id,
                "order_id": execution.order_id,
                "error": error_message,
            },
        )

        return execution

    async def get_execution(self, execution_id: str) -> Optional[OrderExecution]:
        """Get an execution by ID."""
        return await self.database.get_execution(execution_id)

    async def list_executions(
        self,
        order_id: str,
        status: Optional[ExecutionStatus] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OrderExecution]:
        """List executions for an order."""
        return await self.database.list_executions(
            order_id=order_id,
            status=status,
            since=since,
            limit=limit,
            offset=offset,
        )

    async def count_executions(
        self,
        order_id: str,
        status: Optional[ExecutionStatus] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Count executions for an order."""
        return await self.database.count_executions(
            order_id=order_id,
            status=status,
            since=since,
        )

    async def list_recent_executions(
        self,
        since: Optional[datetime] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """
        List recent executions across all orders with order names. [T1]

        Bulk query avoids per-order iteration for newsfeed aggregation.
        """
        return await self.database.list_recent_executions(
            since=since,
            limit=limit,
        )

    # =========================================================================
    # Execution (Placeholder - actual execution delegated to orchestration)
    # =========================================================================

    async def execute_order(self, order_id: str) -> OrderExecution:
        """
        Execute an order immediately.

        This method starts the execution and returns immediately.
        The actual prompt execution is handled asynchronously.

        In the full implementation, this would:
        1. Start execution tracking
        2. Call the orchestration handler with the prompt
        3. Use the specified MCP resources
        4. Complete or fail the execution based on result

        Args:
            order_id: Order to execute.

        Returns:
            New OrderExecution.
        """
        order = await self.database.get_order(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")

        # Start execution
        execution = await self.start_execution(order_id)

        # TODO: Integrate with orchestration handler
        # For now, simulate a successful execution
        self.logger.info(
            f"Order execution triggered: {order.name}",
            component=LogComponent.EXECUTION,
            data={
                "order_id": order_id,
                "execution_id": execution.id,
                "prompt_preview": order.prompt[:100],
                "resources": [r.value for r in order.resources],
            },
        )

        return execution


# Module-level singleton
_order_manager: Optional[OrderManager] = None


async def get_order_manager() -> OrderManager:
    """Get or create singleton order manager."""
    global _order_manager
    if _order_manager is None:
        _order_manager = OrderManager()
        await _order_manager.initialize()
    return _order_manager


async def close_order_manager() -> None:
    """Close the singleton order manager."""
    global _order_manager
    if _order_manager is not None:
        await _order_manager.close()
        _order_manager = None
