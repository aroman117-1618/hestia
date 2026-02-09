"""
Order scheduler using APScheduler.

Manages recurring order execution based on configured schedules.
Integrates with the OrderManager for execution tracking.
"""

import asyncio
from datetime import datetime, time, timezone, timedelta
from typing import Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger

from hestia.logging import get_logger, LogComponent

from .models import Order, FrequencyType, OrderStatus
from .manager import OrderManager, get_order_manager


class OrderScheduler:
    """
    Schedules and executes orders using APScheduler.

    Supports:
    - One-time execution (once)
    - Daily execution at specified time
    - Weekly execution
    - Monthly execution
    - Custom interval (minutes)
    """

    def __init__(self, manager: Optional[OrderManager] = None):
        """
        Initialize order scheduler.

        Args:
            manager: OrderManager instance. If None, uses singleton.
        """
        self._manager = manager
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._scheduled_jobs: Dict[str, str] = {}  # order_id -> job_id
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the scheduler and load existing orders."""
        if self._manager is None:
            self._manager = await get_order_manager()

        # Create scheduler
        self._scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,  # Combine missed executions
                "max_instances": 1,  # Only one instance per order
                "misfire_grace_time": 60 * 60,  # 1 hour grace period
            },
        )

        # Start scheduler
        self._scheduler.start()

        # Load and schedule all active orders
        await self._load_active_orders()

        self.logger.info(
            "Order scheduler initialized",
            component=LogComponent.EXECUTION,
            data={"scheduled_orders": len(self._scheduled_jobs)},
        )

    async def close(self) -> None:
        """Shutdown the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

        self._scheduled_jobs.clear()

        self.logger.debug(
            "Order scheduler closed",
            component=LogComponent.EXECUTION,
        )

    async def __aenter__(self) -> "OrderScheduler":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def manager(self) -> OrderManager:
        """Get order manager."""
        if self._manager is None:
            raise RuntimeError("Scheduler not initialized. Call initialize() first.")
        return self._manager

    @property
    def scheduler(self) -> AsyncIOScheduler:
        """Get APScheduler instance."""
        if self._scheduler is None:
            raise RuntimeError("Scheduler not initialized. Call initialize() first.")
        return self._scheduler

    # =========================================================================
    # Schedule Management
    # =========================================================================

    async def _load_active_orders(self) -> None:
        """Load and schedule all active orders."""
        orders = await self.manager.get_active_orders()

        for order in orders:
            try:
                await self.schedule_order(order)
            except Exception as e:
                self.logger.error(
                    f"Failed to schedule order {order.id}: {type(e).__name__}",
                    component=LogComponent.EXECUTION,
                )

    async def schedule_order(self, order: Order) -> None:
        """
        Schedule an order for execution.

        Args:
            order: Order to schedule.
        """
        if order.status != OrderStatus.ACTIVE:
            return

        # Remove existing job if any
        await self.unschedule_order(order.id)

        # Create trigger based on frequency
        trigger = self._create_trigger(order)

        if trigger is None:
            self.logger.warning(
                f"Could not create trigger for order {order.id}",
                component=LogComponent.EXECUTION,
            )
            return

        # Schedule the job
        job = self.scheduler.add_job(
            self._execute_order,
            trigger=trigger,
            id=f"order-{order.id}",
            name=f"Order: {order.name}",
            kwargs={"order_id": order.id},
            replace_existing=True,
        )

        self._scheduled_jobs[order.id] = job.id

        self.logger.debug(
            f"Scheduled order: {order.id}",
            component=LogComponent.EXECUTION,
            data={
                "order_id": order.id,
                "name": order.name,
                "frequency": order.frequency.type.value,
                "next_run": str(job.next_run_time),
            },
        )

    async def unschedule_order(self, order_id: str) -> None:
        """
        Remove an order from the schedule.

        Args:
            order_id: Order ID to unschedule.
        """
        job_id = self._scheduled_jobs.pop(order_id, None)

        if job_id:
            try:
                self.scheduler.remove_job(job_id)
                self.logger.debug(
                    f"Unscheduled order: {order_id}",
                    component=LogComponent.EXECUTION,
                )
            except Exception:
                pass  # Job may not exist

    async def reschedule_order(self, order: Order) -> None:
        """
        Reschedule an order (after update).

        Args:
            order: Updated order.
        """
        if order.status == OrderStatus.ACTIVE:
            await self.schedule_order(order)
        else:
            await self.unschedule_order(order.id)

    def _create_trigger(self, order: Order):
        """Create APScheduler trigger for an order."""
        freq = order.frequency
        sched_time = order.scheduled_time

        if freq.type == FrequencyType.ONCE:
            # Schedule for next occurrence of the time
            now = datetime.now(timezone.utc)
            run_date = datetime.combine(now.date(), sched_time, tzinfo=timezone.utc)

            if run_date <= now:
                # If time has passed today, schedule for tomorrow
                run_date += timedelta(days=1)

            return DateTrigger(run_date=run_date)

        elif freq.type == FrequencyType.DAILY:
            return CronTrigger(
                hour=sched_time.hour,
                minute=sched_time.minute,
                second=sched_time.second,
            )

        elif freq.type == FrequencyType.WEEKLY:
            # Execute on the same day of week as creation
            return CronTrigger(
                day_of_week="*",
                hour=sched_time.hour,
                minute=sched_time.minute,
                second=sched_time.second,
            )

        elif freq.type == FrequencyType.MONTHLY:
            # Execute on the first of each month
            return CronTrigger(
                day=1,
                hour=sched_time.hour,
                minute=sched_time.minute,
                second=sched_time.second,
            )

        elif freq.type == FrequencyType.CUSTOM:
            if freq.minutes and freq.minutes >= 15:
                return IntervalTrigger(minutes=freq.minutes)

        return None

    # =========================================================================
    # Execution
    # =========================================================================

    async def _execute_order(self, order_id: str) -> None:
        """
        Execute an order (called by scheduler).

        Args:
            order_id: Order to execute.
        """
        try:
            execution = await self.manager.execute_order(order_id)

            self.logger.info(
                f"Scheduled execution started: {execution.id}",
                component=LogComponent.EXECUTION,
                data={
                    "execution_id": execution.id,
                    "order_id": order_id,
                },
            )

            # TODO: When orchestration integration is complete,
            # the execution completion/failure will be handled there.
            # For now, we just start the execution.

        except Exception as e:
            self.logger.error(
                f"Failed to execute order {order_id}: {type(e).__name__}",
                component=LogComponent.EXECUTION,
                data={"order_id": order_id, "error_type": type(e).__name__},
            )

    def get_next_execution_time(self, order_id: str) -> Optional[datetime]:
        """
        Get the next scheduled execution time for an order.

        Args:
            order_id: Order ID.

        Returns:
            Next execution datetime or None if not scheduled.
        """
        job_id = self._scheduled_jobs.get(order_id)
        if not job_id:
            return None

        try:
            job = self.scheduler.get_job(job_id)
            if job:
                return job.next_run_time
        except Exception:
            pass

        return None

    def is_order_scheduled(self, order_id: str) -> bool:
        """Check if an order is currently scheduled."""
        return order_id in self._scheduled_jobs


# Module-level singleton
_order_scheduler: Optional[OrderScheduler] = None


async def get_order_scheduler() -> OrderScheduler:
    """Get or create singleton order scheduler."""
    global _order_scheduler
    if _order_scheduler is None:
        _order_scheduler = OrderScheduler()
        await _order_scheduler.initialize()
    return _order_scheduler


async def close_order_scheduler() -> None:
    """Close the singleton order scheduler."""
    global _order_scheduler
    if _order_scheduler is not None:
        await _order_scheduler.close()
        _order_scheduler = None
