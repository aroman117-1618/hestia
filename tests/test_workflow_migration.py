"""Tests for orders-to-workflows migration — conversion, idempotency."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from hestia.orders.database import OrderDatabase
from hestia.workflows.database import WorkflowDatabase
from hestia.workflows.migration import (
    _frequency_to_trigger_config,
    migrate_orders_to_workflows,
)


@pytest_asyncio.fixture
async def dbs(tmp_path: Path):
    """Create fresh order and workflow databases."""
    order_db = OrderDatabase(tmp_path / "orders.db")
    await order_db.connect()
    workflow_db = WorkflowDatabase(tmp_path / "workflows.db")
    await workflow_db.connect()
    yield order_db, workflow_db
    await order_db.close()
    await workflow_db.close()


async def _insert_order(order_db, name="Test Order", prompt="Hello", freq="daily", time="07:00:00"):
    """Insert a minimal order for testing."""
    import uuid
    order_id = f"order-{uuid.uuid4().hex[:12]}"
    await order_db.connection.execute(
        """INSERT INTO orders (id, name, prompt, scheduled_time,
           frequency_type, frequency_minutes, resources, status,
           created_at, updated_at, execution_count, success_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            order_id, name, prompt, time, freq, None,
            json.dumps(["calendar"]), "active",
            datetime.now(timezone.utc).isoformat(),
            datetime.now(timezone.utc).isoformat(),
            0, 0,
        ),
    )
    await order_db.connection.commit()
    return order_id


async def _insert_execution(order_db, order_id, status="success"):
    """Insert a minimal execution record."""
    import uuid
    exec_id = f"exec-{uuid.uuid4().hex[:12]}"
    await order_db.connection.execute(
        """INSERT INTO order_executions (id, order_id, timestamp, status)
           VALUES (?, ?, ?, ?)""",
        (exec_id, order_id, datetime.now(timezone.utc).isoformat(), status),
    )
    await order_db.connection.commit()
    return exec_id


class TestFrequencyConversion:
    def test_daily(self) -> None:
        config = _frequency_to_trigger_config({
            "frequency_type": "daily",
            "scheduled_time": "08:30:00",
        })
        assert config == {"cron": "30 08 * * *"}

    def test_weekly(self) -> None:
        config = _frequency_to_trigger_config({
            "frequency_type": "weekly",
            "scheduled_time": "09:00:00",
        })
        assert config == {"cron": "00 09 * * 1"}

    def test_monthly(self) -> None:
        config = _frequency_to_trigger_config({
            "frequency_type": "monthly",
            "scheduled_time": "07:00:00",
        })
        assert config == {"cron": "00 07 1 * *"}

    def test_custom_interval(self) -> None:
        config = _frequency_to_trigger_config({
            "frequency_type": "custom",
            "frequency_minutes": 60,
        })
        assert config == {"interval_minutes": 60}

    def test_custom_interval_min_15(self) -> None:
        config = _frequency_to_trigger_config({
            "frequency_type": "custom",
            "frequency_minutes": 5,
        })
        # Falls through to default daily since < 15
        assert "cron" in config


class TestMigration:
    @pytest.mark.asyncio
    async def test_migrate_single_order(self, dbs) -> None:
        order_db, workflow_db = dbs
        order_id = await _insert_order(order_db, "Morning Brief", "Summarize my day")

        result = await migrate_orders_to_workflows(order_db, workflow_db)
        assert result["migrated"] == 1
        assert result["skipped"] == 0
        assert result["failed"] == 0

        # Verify workflow was created
        workflows, total = await workflow_db.list_workflows()
        assert total == 1
        assert workflows[0].name == "Morning Brief"
        assert workflows[0].migrated_from_order_id == order_id

        # Verify nodes were created
        nodes = await workflow_db.get_nodes_for_workflow(workflows[0].id)
        assert len(nodes) == 2  # trigger + prompt
        node_types = {n.node_type.value for n in nodes}
        assert "schedule" in node_types
        assert "run_prompt" in node_types

        # Verify edge was created
        edges = await workflow_db.get_edges_for_workflow(workflows[0].id)
        assert len(edges) == 1

    @pytest.mark.asyncio
    async def test_idempotent(self, dbs) -> None:
        order_db, workflow_db = dbs
        await _insert_order(order_db, "Test")

        # Migrate twice
        result1 = await migrate_orders_to_workflows(order_db, workflow_db)
        result2 = await migrate_orders_to_workflows(order_db, workflow_db)

        assert result1["migrated"] == 1
        assert result2["migrated"] == 0
        assert result2["skipped"] == 1

        # Only one workflow should exist
        _, total = await workflow_db.list_workflows()
        assert total == 1

    @pytest.mark.asyncio
    async def test_migrate_with_executions(self, dbs) -> None:
        order_db, workflow_db = dbs
        order_id = await _insert_order(order_db, "With History")
        await _insert_execution(order_db, order_id, "success")
        await _insert_execution(order_db, order_id, "failed")

        await migrate_orders_to_workflows(order_db, workflow_db)

        workflows, _ = await workflow_db.list_workflows()
        runs, total = await workflow_db.list_runs(workflows[0].id)
        assert total == 2

    @pytest.mark.asyncio
    async def test_migrate_multiple_orders(self, dbs) -> None:
        order_db, workflow_db = dbs
        await _insert_order(order_db, "Order A")
        await _insert_order(order_db, "Order B")
        await _insert_order(order_db, "Order C")

        result = await migrate_orders_to_workflows(order_db, workflow_db)
        assert result["migrated"] == 3

    @pytest.mark.asyncio
    async def test_orders_marked_completed(self, dbs) -> None:
        order_db, workflow_db = dbs
        order_id = await _insert_order(order_db)

        await migrate_orders_to_workflows(order_db, workflow_db)

        cursor = await order_db.connection.execute(
            "SELECT status FROM orders WHERE id = ?", (order_id,)
        )
        row = await cursor.fetchone()
        assert row[0] == "completed"

    @pytest.mark.asyncio
    async def test_empty_orders(self, dbs) -> None:
        order_db, workflow_db = dbs
        result = await migrate_orders_to_workflows(order_db, workflow_db)
        assert result["migrated"] == 0
        assert result["total_orders"] == 0
