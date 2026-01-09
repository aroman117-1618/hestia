"""
SQLite persistence for orders.

Provides async database operations for order storage, retrieval,
and execution tracking using aiosqlite.
"""

import aiosqlite
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import (
    Order,
    OrderExecution,
    OrderStatus,
    ExecutionStatus,
    MCPResource,
)


class OrderDatabase:
    """
    SQLite database for order persistence.

    Uses async aiosqlite for non-blocking I/O.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize order database.

        Args:
            db_path: Path to SQLite database file.
                     Defaults to ~/hestia/data/orders.db
        """
        if db_path is None:
            db_path = Path.home() / "hestia" / "data" / "orders.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection: Optional[aiosqlite.Connection] = None
        self.logger = get_logger()

    async def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row

        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._init_schema()

        self.logger.info(
            f"Order database connected: {self.db_path}",
            component=LogComponent.API,
        )

    async def _init_schema(self) -> None:
        """Initialize database schema."""
        await self._connection.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                prompt TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                frequency_type TEXT NOT NULL,
                frequency_minutes INTEGER,
                resources TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                execution_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_orders_status
                ON orders(status);

            CREATE INDEX IF NOT EXISTS idx_orders_scheduled_time
                ON orders(scheduled_time);

            CREATE TABLE IF NOT EXISTS order_executions (
                id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                status TEXT NOT NULL,
                completed_at TEXT,
                duration_ms REAL,
                hestia_read TEXT,
                full_response TEXT,
                resources_used TEXT,
                error_message TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_executions_order_id
                ON order_executions(order_id);

            CREATE INDEX IF NOT EXISTS idx_executions_timestamp
                ON order_executions(timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_executions_status
                ON order_executions(status);
        """)
        await self._connection.commit()

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self.logger.debug(
                "Order database closed",
                component=LogComponent.API,
            )

    async def __aenter__(self) -> "OrderDatabase":
        await self.connect()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get active connection."""
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection

    # =========================================================================
    # Order CRUD
    # =========================================================================

    async def store_order(self, order: Order) -> str:
        """Store a new order."""
        row = order.to_sqlite_row()

        await self.connection.execute(
            """
            INSERT INTO orders (
                id, name, prompt, scheduled_time, frequency_type,
                frequency_minutes, resources, status, created_at,
                updated_at, execution_count, success_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        await self.connection.commit()

        self.logger.debug(
            f"Stored order: {order.id}",
            component=LogComponent.API,
            data={"order_id": order.id, "name": order.name},
        )

        return order.id

    async def get_order(self, order_id: str) -> Optional[Order]:
        """Retrieve an order by ID."""
        async with self.connection.execute(
            "SELECT * FROM orders WHERE id = ?",
            (order_id,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                order = Order.from_sqlite_row(dict(row))
                # Load last execution
                order.last_execution = await self.get_last_execution(order_id)
                return order

        return None

    async def update_order(self, order: Order) -> bool:
        """Update an existing order."""
        order.updated_at = datetime.now(timezone.utc)
        row = order.to_sqlite_row()

        cursor = await self.connection.execute(
            """
            UPDATE orders SET
                name = ?,
                prompt = ?,
                scheduled_time = ?,
                frequency_type = ?,
                frequency_minutes = ?,
                resources = ?,
                status = ?,
                created_at = ?,
                updated_at = ?,
                execution_count = ?,
                success_count = ?
            WHERE id = ?
            """,
            (
                row[1], row[2], row[3], row[4], row[5], row[6], row[7],
                row[8], row[9], row[10], row[11], row[0]
            ),
        )
        await self.connection.commit()

        updated = cursor.rowcount > 0

        if updated:
            self.logger.debug(
                f"Updated order: {order.id}",
                component=LogComponent.API,
            )

        return updated

    async def delete_order(self, order_id: str) -> bool:
        """Delete an order (cascades to executions)."""
        cursor = await self.connection.execute(
            "DELETE FROM orders WHERE id = ?",
            (order_id,),
        )
        await self.connection.commit()

        deleted = cursor.rowcount > 0

        if deleted:
            self.logger.debug(
                f"Deleted order: {order_id}",
                component=LogComponent.API,
            )

        return deleted

    async def list_orders(
        self,
        status: Optional[OrderStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Order]:
        """List orders with optional filters."""
        query = "SELECT * FROM orders WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        orders = []
        async with self.connection.execute(query, params) as cursor:
            async for row in cursor:
                order = Order.from_sqlite_row(dict(row))
                order.last_execution = await self.get_last_execution(order.id)
                orders.append(order)

        return orders

    async def count_orders(self, status: Optional[OrderStatus] = None) -> int:
        """Count orders with optional filter."""
        query = "SELECT COUNT(*) FROM orders WHERE 1=1"
        params: List[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        async with self.connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def get_active_orders(self) -> List[Order]:
        """Get all active orders for scheduling."""
        return await self.list_orders(status=OrderStatus.ACTIVE, limit=1000)

    # =========================================================================
    # Execution CRUD
    # =========================================================================

    async def store_execution(self, execution: OrderExecution) -> str:
        """Store a new execution."""
        row = execution.to_sqlite_row()

        await self.connection.execute(
            """
            INSERT INTO order_executions (
                id, order_id, timestamp, status, completed_at,
                duration_ms, hestia_read, full_response,
                resources_used, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            row,
        )
        await self.connection.commit()

        self.logger.debug(
            f"Stored execution: {execution.id}",
            component=LogComponent.API,
            data={"execution_id": execution.id, "order_id": execution.order_id},
        )

        return execution.id

    async def update_execution(self, execution: OrderExecution) -> bool:
        """Update an execution."""
        row = execution.to_sqlite_row()

        cursor = await self.connection.execute(
            """
            UPDATE order_executions SET
                order_id = ?,
                timestamp = ?,
                status = ?,
                completed_at = ?,
                duration_ms = ?,
                hestia_read = ?,
                full_response = ?,
                resources_used = ?,
                error_message = ?
            WHERE id = ?
            """,
            (
                row[1], row[2], row[3], row[4], row[5],
                row[6], row[7], row[8], row[9], row[0]
            ),
        )
        await self.connection.commit()

        return cursor.rowcount > 0

    async def get_execution(self, execution_id: str) -> Optional[OrderExecution]:
        """Get an execution by ID."""
        async with self.connection.execute(
            "SELECT * FROM order_executions WHERE id = ?",
            (execution_id,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                return OrderExecution.from_sqlite_row(dict(row))

        return None

    async def get_last_execution(self, order_id: str) -> Optional[OrderExecution]:
        """Get the most recent execution for an order."""
        async with self.connection.execute(
            """
            SELECT * FROM order_executions
            WHERE order_id = ?
            ORDER BY timestamp DESC LIMIT 1
            """,
            (order_id,),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                return OrderExecution.from_sqlite_row(dict(row))

        return None

    async def list_executions(
        self,
        order_id: str,
        status: Optional[ExecutionStatus] = None,
        since: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[OrderExecution]:
        """List executions for an order."""
        query = "SELECT * FROM order_executions WHERE order_id = ?"
        params: List[Any] = [order_id]

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        executions = []
        async with self.connection.execute(query, params) as cursor:
            async for row in cursor:
                executions.append(OrderExecution.from_sqlite_row(dict(row)))

        return executions

    async def count_executions(
        self,
        order_id: str,
        status: Optional[ExecutionStatus] = None,
        since: Optional[datetime] = None,
    ) -> int:
        """Count executions for an order."""
        query = "SELECT COUNT(*) FROM order_executions WHERE order_id = ?"
        params: List[Any] = [order_id]

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        async with self.connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def increment_execution_counts(
        self,
        order_id: str,
        success: bool,
    ) -> None:
        """Increment execution counts on an order."""
        if success:
            await self.connection.execute(
                """
                UPDATE orders
                SET execution_count = execution_count + 1,
                    success_count = success_count + 1
                WHERE id = ?
                """,
                (order_id,),
            )
        else:
            await self.connection.execute(
                """
                UPDATE orders
                SET execution_count = execution_count + 1
                WHERE id = ?
                """,
                (order_id,),
            )
        await self.connection.commit()


# Module-level singleton
_order_database: Optional[OrderDatabase] = None


async def get_order_database() -> OrderDatabase:
    """Get or create singleton order database."""
    global _order_database
    if _order_database is None:
        _order_database = OrderDatabase()
        await _order_database.connect()
    return _order_database


async def close_order_database() -> None:
    """Close the singleton order database."""
    global _order_database
    if _order_database is not None:
        await _order_database.close()
        _order_database = None
