"""
Tests for Hestia Orders module.

Phase 6b: Orders API - standing orders/automated tasks.

Run with: python -m pytest tests/test_orders.py -v
"""

import asyncio
import tempfile
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Generator

import pytest
import pytest_asyncio

from hestia.orders.models import (
    Order,
    OrderExecution,
    OrderStatus,
    ExecutionStatus,
    OrderFrequency,
    FrequencyType,
    MCPResource,
)
from hestia.orders.database import OrderDatabase
from hestia.orders.manager import OrderManager


# ============== Fixtures ==============

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_order() -> Order:
    """Create a sample order."""
    return Order.create(
        name="Morning News Briefing",
        prompt="Summarize top tech news from Hacker News and Apple News",
        scheduled_time=time(8, 0, 0),
        frequency=OrderFrequency(type=FrequencyType.DAILY),
        resources={MCPResource.APPLE_NEWS, MCPResource.FIRECRAWL},
    )


@pytest.fixture
def sample_execution(sample_order: Order) -> OrderExecution:
    """Create a sample execution."""
    return OrderExecution.create(order_id=sample_order.id)


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> OrderDatabase:
    """Create a test database."""
    db = OrderDatabase(db_path=temp_dir / "test_orders.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(temp_dir: Path) -> OrderManager:
    """Create a test order manager."""
    db = OrderDatabase(db_path=temp_dir / "test_orders.db")
    await db.connect()

    mgr = OrderManager(database=db)
    await mgr.initialize()

    yield mgr

    await mgr.close()
    await db.close()


# ============== Model Tests ==============

class TestOrderModel:
    """Tests for Order dataclass."""

    def test_order_create(self):
        """Test order creation with factory method."""
        order = Order.create(
            name="Test Order",
            prompt="Do something useful",
            scheduled_time=time(9, 30, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.CALENDAR},
        )

        assert order.id.startswith("order-")
        assert order.name == "Test Order"
        assert order.prompt == "Do something useful"
        assert order.scheduled_time == time(9, 30, 0)
        assert order.frequency.type == FrequencyType.DAILY
        assert order.status == OrderStatus.ACTIVE
        assert MCPResource.CALENDAR in order.resources

    def test_order_with_custom_frequency(self):
        """Test order with custom frequency interval."""
        order = Order.create(
            name="Frequent Check",
            prompt="Check something",
            scheduled_time=time(0, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.CUSTOM, minutes=30),
            resources={MCPResource.GITHUB},
        )

        assert order.frequency.type == FrequencyType.CUSTOM
        assert order.frequency.minutes == 30

    def test_order_with_weekly_frequency(self):
        """Test order with weekly frequency."""
        order = Order.create(
            name="Weekly Report",
            prompt="Generate weekly summary",
            scheduled_time=time(17, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.WEEKLY),
            resources={MCPResource.EMAIL, MCPResource.CALENDAR},
        )

        assert order.frequency.type == FrequencyType.WEEKLY

    def test_order_status_toggle(self):
        """Test order status can be toggled."""
        order = Order.create(
            name="Test",
            prompt="Test prompt",
            scheduled_time=time(8, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.ONCE),
            resources={MCPResource.NOTE},
        )

        assert order.status == OrderStatus.ACTIVE
        order.status = OrderStatus.INACTIVE
        assert order.status == OrderStatus.INACTIVE

    def test_order_serialization(self):
        """Test order to/from dict for SQLite storage."""
        order = Order.create(
            name="Serialize Test",
            prompt="Test serialization",
            scheduled_time=time(12, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.MONTHLY),
            resources={MCPResource.FIDELITY, MCPResource.EMAIL},
        )

        # Convert to dict (for DB storage)
        data = order.to_dict()

        assert data["id"] == order.id
        assert data["name"] == "Serialize Test"
        assert data["scheduled_time"] == "12:00:00"
        assert data["frequency"]["type"] == "monthly"
        assert "fidelity" in data["resources"]

        # Recreate from dict
        restored = Order.from_dict(data)

        assert restored.id == order.id
        assert restored.name == order.name
        assert restored.scheduled_time == order.scheduled_time
        assert restored.frequency.type == FrequencyType.MONTHLY


class TestOrderExecutionModel:
    """Tests for OrderExecution dataclass."""

    def test_execution_create(self):
        """Test execution creation."""
        execution = OrderExecution.create(order_id="order-test-123")

        assert execution.id.startswith("exec-")
        assert execution.order_id == "order-test-123"
        # Execution starts in RUNNING status immediately
        assert execution.status == ExecutionStatus.RUNNING

    def test_execution_complete(self):
        """Test completing an execution."""
        execution = OrderExecution.create(order_id="order-test-123")
        # No separate start() - create() immediately starts running
        execution.complete(
            hestia_read="Top news: Apple announces new product",
            full_response="Full response text here...",
        )

        assert execution.status == ExecutionStatus.SUCCESS
        assert execution.completed_at is not None
        assert execution.hestia_read == "Top news: Apple announces new product"
        assert execution.duration_ms is not None
        assert execution.duration_ms >= 0

    def test_execution_fail(self):
        """Test failing an execution."""
        execution = OrderExecution.create(order_id="order-test-123")
        # No separate start() - create() immediately starts running
        execution.fail(error_message="API timeout")

        assert execution.status == ExecutionStatus.FAILED
        assert execution.error_message == "API timeout"
        assert execution.completed_at is not None


class TestMCPResource:
    """Tests for MCPResource enum."""

    def test_all_resources_exist(self):
        """Test all expected resources are defined."""
        expected = {
            "firecrawl", "github", "apple_news", "fidelity",
            "calendar", "email", "reminder", "note", "shortcut"
        }
        actual = {r.value for r in MCPResource}
        assert expected == actual


# ============== Database Tests ==============

class TestOrderDatabase:
    """Tests for OrderDatabase persistence."""

    @pytest.mark.asyncio
    async def test_store_and_retrieve_order(self, database: OrderDatabase, sample_order: Order):
        """Test storing and retrieving an order."""
        await database.store_order(sample_order)
        retrieved = await database.get_order(sample_order.id)

        assert retrieved is not None
        assert retrieved.id == sample_order.id
        assert retrieved.name == sample_order.name
        assert retrieved.prompt == sample_order.prompt

    @pytest.mark.asyncio
    async def test_list_orders_empty(self, database: OrderDatabase):
        """Test listing orders when empty."""
        orders = await database.list_orders()
        assert orders == []

    @pytest.mark.asyncio
    async def test_list_orders_with_status_filter(self, database: OrderDatabase):
        """Test listing orders with status filter."""
        active = Order.create(
            name="Active Order",
            prompt="Active",
            scheduled_time=time(8, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.CALENDAR},
            status=OrderStatus.ACTIVE,
        )
        inactive = Order.create(
            name="Inactive Order",
            prompt="Inactive",
            scheduled_time=time(9, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.EMAIL},
            status=OrderStatus.INACTIVE,
        )

        await database.store_order(active)
        await database.store_order(inactive)

        active_orders = await database.list_orders(status=OrderStatus.ACTIVE)
        assert len(active_orders) == 1
        assert active_orders[0].name == "Active Order"

    @pytest.mark.asyncio
    async def test_update_order(self, database: OrderDatabase, sample_order: Order):
        """Test updating an order."""
        await database.store_order(sample_order)

        sample_order.name = "Updated Name"
        sample_order.status = OrderStatus.INACTIVE
        await database.update_order(sample_order)

        retrieved = await database.get_order(sample_order.id)
        assert retrieved.name == "Updated Name"
        assert retrieved.status == OrderStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_delete_order(self, database: OrderDatabase, sample_order: Order):
        """Test deleting an order."""
        await database.store_order(sample_order)
        deleted = await database.delete_order(sample_order.id)

        assert deleted is True
        assert await database.get_order(sample_order.id) is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_order(self, database: OrderDatabase):
        """Test deleting a non-existent order."""
        deleted = await database.delete_order("order-nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_store_and_retrieve_execution(
        self, database: OrderDatabase, sample_order: Order, sample_execution: OrderExecution
    ):
        """Test storing and retrieving an execution."""
        await database.store_order(sample_order)
        await database.store_execution(sample_execution)

        executions = await database.list_executions(sample_order.id)
        assert len(executions) == 1
        assert executions[0].id == sample_execution.id

    @pytest.mark.asyncio
    async def test_increment_execution_counts(self, database: OrderDatabase, sample_order: Order):
        """Test execution count tracking."""
        await database.store_order(sample_order)

        # Create and complete an execution
        execution = OrderExecution.create(order_id=sample_order.id)
        execution.complete("Summary", "Full response")
        await database.store_execution(execution)
        await database.increment_execution_counts(sample_order.id, success=True)

        order = await database.get_order(sample_order.id)
        assert order.execution_count == 1
        assert order.success_count == 1

        # Create and fail an execution
        execution2 = OrderExecution.create(order_id=sample_order.id)
        execution2.fail(error_message="Error")
        await database.store_execution(execution2)
        await database.increment_execution_counts(sample_order.id, success=False)

        order = await database.get_order(sample_order.id)
        assert order.execution_count == 2
        assert order.success_count == 1


# ============== Manager Tests ==============

class TestOrderManager:
    """Tests for OrderManager lifecycle."""

    @pytest.mark.asyncio
    async def test_create_order(self, manager: OrderManager):
        """Test creating an order through manager."""
        order = await manager.create_order(
            name="Manager Test",
            prompt="Test prompt",
            scheduled_time=time(10, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.REMINDER},
        )

        assert order.id.startswith("order-")
        assert order.status == OrderStatus.ACTIVE

        # Verify it's persisted
        retrieved = await manager.get_order(order.id)
        assert retrieved is not None
        assert retrieved.name == "Manager Test"

    @pytest.mark.asyncio
    async def test_update_order(self, manager: OrderManager):
        """Test updating an order through manager."""
        order = await manager.create_order(
            name="Original Name",
            prompt="Original prompt",
            scheduled_time=time(8, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.CALENDAR},
        )

        updated = await manager.update_order(
            order_id=order.id,
            name="New Name",
            status=OrderStatus.INACTIVE,
        )

        assert updated.name == "New Name"
        assert updated.status == OrderStatus.INACTIVE
        # Prompt should remain unchanged
        assert updated.prompt == "Original prompt"

    @pytest.mark.asyncio
    async def test_delete_order(self, manager: OrderManager):
        """Test deleting an order through manager."""
        order = await manager.create_order(
            name="To Delete",
            prompt="Will be deleted",
            scheduled_time=time(12, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.ONCE),
            resources={MCPResource.NOTE},
        )

        deleted = await manager.delete_order(order.id)
        assert deleted is True

        # Verify it's gone
        retrieved = await manager.get_order(order.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_list_orders(self, manager: OrderManager):
        """Test listing orders through manager."""
        # Create multiple orders
        for i in range(5):
            await manager.create_order(
                name=f"Order {i}",
                prompt=f"This is a test prompt number {i} that is long enough for validation",
                scheduled_time=time(8 + i, 0, 0),
                frequency=OrderFrequency(type=FrequencyType.DAILY),
                resources={MCPResource.CALENDAR},
            )

        orders = await manager.list_orders()
        assert len(orders) == 5

    @pytest.mark.asyncio
    async def test_start_execution(self, manager: OrderManager):
        """Test starting an execution through manager."""
        order = await manager.create_order(
            name="Execution Test",
            prompt="Test execution",
            scheduled_time=time(8, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.GITHUB},
        )

        execution = await manager.start_execution(order.id)
        assert execution.status == ExecutionStatus.RUNNING
        assert execution.order_id == order.id

    @pytest.mark.asyncio
    async def test_complete_execution(self, manager: OrderManager):
        """Test completing an execution through manager."""
        order = await manager.create_order(
            name="Complete Test",
            prompt="Test completion",
            scheduled_time=time(8, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.APPLE_NEWS},
        )

        execution = await manager.start_execution(order.id)
        completed = await manager.complete_execution(
            execution_id=execution.id,
            hestia_read="Summary of news",
            full_response="Full response text",
        )

        assert completed.status == ExecutionStatus.SUCCESS
        assert completed.hestia_read == "Summary of news"

        # Check execution count was incremented
        updated_order = await manager.get_order(order.id)
        assert updated_order.execution_count == 1
        assert updated_order.success_count == 1

    @pytest.mark.asyncio
    async def test_fail_execution(self, manager: OrderManager):
        """Test failing an execution through manager."""
        order = await manager.create_order(
            name="Fail Test",
            prompt="Test failure",
            scheduled_time=time(8, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.FIDELITY},
        )

        execution = await manager.start_execution(order.id)
        failed = await manager.fail_execution(
            execution_id=execution.id,
            error_message="Connection timeout",
        )

        assert failed.status == ExecutionStatus.FAILED
        assert failed.error_message == "Connection timeout"

        # Check execution count was incremented but not success
        updated_order = await manager.get_order(order.id)
        assert updated_order.execution_count == 1
        assert updated_order.success_count == 0

    @pytest.mark.asyncio
    async def test_list_executions(self, manager: OrderManager):
        """Test listing executions through manager."""
        order = await manager.create_order(
            name="History Test",
            prompt="Test history",
            scheduled_time=time(8, 0, 0),
            frequency=OrderFrequency(type=FrequencyType.DAILY),
            resources={MCPResource.EMAIL},
        )

        # Create multiple executions
        for i in range(3):
            execution = await manager.start_execution(order.id)
            await manager.complete_execution(
                execution_id=execution.id,
                hestia_read=f"Summary {i}",
                full_response=f"Response {i}",
            )

        executions = await manager.list_executions(order.id)
        assert len(executions) == 3


# ============== Frequency Type Tests ==============

class TestFrequencyType:
    """Tests for FrequencyType enum."""

    def test_all_frequency_types(self):
        """Test all frequency types exist."""
        expected = {"once", "daily", "weekly", "monthly", "custom"}
        actual = {f.value for f in FrequencyType}
        assert expected == actual

    def test_custom_requires_minutes(self):
        """Test custom frequency requires minutes."""
        freq = OrderFrequency(type=FrequencyType.CUSTOM, minutes=60)
        assert freq.minutes == 60

        # Without minutes, should still create but be invalid for scheduling
        freq_no_min = OrderFrequency(type=FrequencyType.CUSTOM)
        assert freq_no_min.minutes is None
