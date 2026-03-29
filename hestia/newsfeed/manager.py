"""
Newsfeed manager — aggregation engine for the Command Center timeline.

Materializes items from source managers (orders, memory, tasks, health,
trading, sentinel) into a SQLite cache with configurable TTL. Read/dismiss
state is per-user for multi-device continuity.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.orders import get_order_manager
from hestia.memory import get_memory_manager
from hestia.tasks import get_task_manager
from hestia.health import get_health_manager
from hestia.workflows.manager import get_workflow_manager

from .database import NewsfeedDatabase, get_newsfeed_database
from .models import (
    NewsfeedItem,
    NewsfeedItemPriority,
    NewsfeedItemSource,
    NewsfeedItemType,
)

logger = get_logger()

CACHE_TTL_SECONDS = 30

_instance: Optional["NewsfeedManager"] = None


class NewsfeedManager:
    """
    Aggregates timeline items from multiple source managers.

    Serves from materialized cache, refreshes when stale (30s TTL).
    Each aggregator is wrapped in try/except so one failure doesn't
    block the others.
    """

    def __init__(self, database: Optional[NewsfeedDatabase] = None):
        self._database = database
        self._last_refresh: float = 0.0

    async def initialize(self) -> None:
        """Initialize database and run initial cleanup."""
        if self._database is None:
            self._database = await get_newsfeed_database()

        # Clean up old items on startup
        deleted = await self._database.cleanup_old_items(days=30)
        if deleted > 0:
            logger.info(
                f"Cleaned up {deleted} old newsfeed items",
                component=LogComponent.NEWSFEED,
            )

        logger.info(
            "Newsfeed manager initialized",
            component=LogComponent.NEWSFEED,
        )

    async def close(self) -> None:
        """Close manager resources."""
        logger.debug(
            "Newsfeed manager closed",
            component=LogComponent.NEWSFEED,
        )

    # ── Public API ──────────────────────────────────────────

    async def get_timeline(
        self,
        user_id: str,
        item_type: Optional[NewsfeedItemType] = None,
        source: Optional[NewsfeedItemSource] = None,
        include_dismissed: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[NewsfeedItem]:
        """
        Get timeline items, refreshing cache if stale.

        Args:
            user_id: User ID for read/dismiss state.
            item_type: Filter by item type.
            source: Filter by source.
            include_dismissed: Include dismissed items.
            limit: Max items to return.
            offset: Pagination offset.
        """
        if self._is_cache_stale():
            await self._aggregate_all()

        return await self._database.get_items(
            user_id=user_id,
            item_type=item_type,
            source=source,
            include_dismissed=include_dismissed,
            limit=limit,
            offset=offset,
        )

    async def mark_read(
        self, item_id: str, user_id: str, device_id: Optional[str] = None
    ) -> bool:
        """Mark an item as read."""
        return await self._database.mark_read(item_id, user_id, device_id)

    async def mark_dismissed(
        self, item_id: str, user_id: str, device_id: Optional[str] = None
    ) -> bool:
        """Mark an item as dismissed."""
        return await self._database.mark_dismissed(item_id, user_id, device_id)

    async def get_unread_count(
        self,
        user_id: str,
        item_type: Optional[NewsfeedItemType] = None,
    ) -> int:
        """Get unread count for a user."""
        return await self._database.get_unread_count(user_id, item_type)

    async def refresh(self) -> int:
        """Force re-aggregate from all sources. Returns item count."""
        return await self._aggregate_all()

    # ── Internal ────────────────────────────────────────────

    def _is_cache_stale(self) -> bool:
        """Check if cache needs refresh."""
        return (time.time() - self._last_refresh) > CACHE_TTL_SECONDS

    async def _aggregate_all(self) -> int:
        """
        Aggregate items from all source managers.

        Each aggregator is independent — one failure doesn't block others.
        Returns total number of items cached.
        """
        results = await asyncio.gather(
            self._aggregate_order_executions(),
            self._aggregate_memory_reviews(),
            self._aggregate_task_updates(),
            self._aggregate_health_insights(),
            self._aggregate_trading_alerts(),
            self._aggregate_sentinel_alerts(),
            self._aggregate_workflow_runs(),
            return_exceptions=True,
        )

        all_items: List[NewsfeedItem] = []
        for i, result in enumerate(results):
            source_name = ["orders", "memory", "tasks", "health", "trading", "sentinel", "workflows"][i]
            if isinstance(result, Exception):
                logger.warning(
                    f"Newsfeed aggregation failed for {source_name}: {type(result).__name__}",
                    component=LogComponent.NEWSFEED,
                )
                continue
            all_items.extend(result)

        count = await self._database.upsert_items(all_items)
        self._last_refresh = time.time()

        logger.debug(
            f"Newsfeed refreshed: {count} items from {len(all_items)} aggregated",
            component=LogComponent.NEWSFEED,
        )

        return count

    async def _aggregate_order_executions(self) -> List[NewsfeedItem]:
        """Aggregate recent order executions. [T1] Uses bulk query."""
        try:
            manager = await get_order_manager()
            since = datetime.now(timezone.utc) - timedelta(hours=48)

            executions = await manager.list_recent_executions(since=since, limit=50)

            items = []
            for exec_data in executions:
                status_icon = "checkmark.circle" if exec_data.get("status") == "success" else "xmark.circle"
                priority = NewsfeedItemPriority.NORMAL
                if exec_data.get("status") == "failed":
                    priority = NewsfeedItemPriority.HIGH

                items.append(NewsfeedItem(
                    id=f"order_exec:{exec_data['id']}",
                    item_type=NewsfeedItemType.ORDER_EXECUTION,
                    source=NewsfeedItemSource.ORDERS,
                    title=f"Order: {exec_data.get('order_name', 'Unknown')}",
                    body=exec_data.get("hestia_read") or exec_data.get("error_message"),
                    timestamp=datetime.fromisoformat(exec_data["timestamp"]) if exec_data.get("timestamp") else None,
                    priority=priority,
                    icon=status_icon,
                    color="#34C759" if exec_data.get("status") == "success" else "#FF3B30",
                    action_type="order",
                    action_id=exec_data.get("order_id"),
                    metadata={
                        "status": exec_data.get("status", ""),
                        "duration_ms": str(exec_data.get("duration_ms", "")),
                    },
                ))
            return items
        except Exception:
            raise

    async def _aggregate_workflow_runs(self) -> List[NewsfeedItem]:
        """Aggregate recent workflow runs (new DAG engine, not legacy orders)."""
        try:
            manager = await get_workflow_manager()
            since = datetime.now(timezone.utc) - timedelta(hours=48)
            runs = await manager.list_recent_runs(since=since.isoformat(), limit=50)

            items = []
            for run in runs:
                status = run.get("status", "unknown")
                is_success = status == "completed"
                is_failed = status == "failed"
                status_icon = "checkmark.circle" if is_success else ("xmark.circle" if is_failed else "clock")
                priority = NewsfeedItemPriority.HIGH if is_failed else NewsfeedItemPriority.NORMAL
                color = "#34C759" if is_success else ("#FF3B30" if is_failed else "#FF9F0A")

                workflow_name = run.get("workflow_name", "Unknown")
                body = run.get("error_message") or f"Completed in {run.get('duration_ms', 0):.0f}ms"

                items.append(NewsfeedItem(
                    id=f"wf_run:{run['id']}",
                    item_type=NewsfeedItemType.ORDER_EXECUTION,
                    source=NewsfeedItemSource.ORDERS,
                    title=f"Order: {workflow_name}",
                    body=body,
                    timestamp=datetime.fromisoformat(run["started_at"]) if run.get("started_at") else None,
                    priority=priority,
                    icon=status_icon,
                    color=color,
                    action_type="order",
                    action_id=run.get("workflow_id"),
                    metadata={
                        "status": status,
                        "duration_ms": str(run.get("duration_ms", "")),
                        "run_id": run.get("id", ""),
                        "workflow_id": run.get("workflow_id", ""),
                    },
                ))
            return items
        except Exception:
            raise

    async def _aggregate_memory_reviews(self) -> List[NewsfeedItem]:
        """Aggregate pending memory chunks awaiting review."""
        try:
            manager = await get_memory_manager()

            pending = await manager.get_pending_reviews()

            items = []
            for chunk in pending:
                chunk_dict = chunk if isinstance(chunk, dict) else chunk.to_dict() if hasattr(chunk, "to_dict") else {}
                chunk_id = chunk_dict.get("id", getattr(chunk, "id", ""))
                content = chunk_dict.get("content", getattr(chunk, "content", ""))
                tags = chunk_dict.get("tags", getattr(chunk, "tags", []))

                items.append(NewsfeedItem(
                    id=f"memory:{chunk_id}",
                    item_type=NewsfeedItemType.MEMORY_REVIEW,
                    source=NewsfeedItemSource.MEMORY,
                    title="Memory pending review",
                    body=content[:200] if content else None,
                    timestamp=datetime.now(timezone.utc),
                    priority=NewsfeedItemPriority.NORMAL,
                    icon="brain",
                    color="#AF52DE",
                    action_type="memory",
                    action_id=chunk_id,
                    metadata={
                        "tags": ",".join(tags) if isinstance(tags, list) else str(tags),
                    },
                ))
            return items
        except Exception:
            raise

    async def _aggregate_task_updates(self) -> List[NewsfeedItem]:
        """Aggregate recent non-terminal tasks."""
        try:
            manager = await get_task_manager()

            tasks = await manager.list_tasks(limit=20)

            items = []
            for task in tasks:
                task_dict = task if isinstance(task, dict) else task.to_dict()
                status = task_dict.get("status", "")
                if status in ("completed", "cancelled"):
                    continue

                priority = NewsfeedItemPriority.NORMAL
                if task_dict.get("requires_approval"):
                    priority = NewsfeedItemPriority.HIGH

                items.append(NewsfeedItem(
                    id=f"task:{task_dict.get('id', '')}",
                    item_type=NewsfeedItemType.TASK_UPDATE,
                    source=NewsfeedItemSource.TASKS,
                    title=task_dict.get("description", "Task update"),
                    body=task_dict.get("result"),
                    timestamp=datetime.fromisoformat(task_dict["created_at"]) if task_dict.get("created_at") else None,
                    priority=priority,
                    icon="checklist" if not task_dict.get("requires_approval") else "exclamationmark.circle",
                    color="#FF9500" if task_dict.get("requires_approval") else "#007AFF",
                    action_type="task",
                    action_id=task_dict.get("id"),
                    metadata={"status": status},
                ))
            return items
        except Exception:
            raise

    async def _aggregate_health_insights(self) -> List[NewsfeedItem]:
        """Aggregate notable health metrics from daily summary."""
        try:
            manager = await get_health_manager()

            summary = await manager.get_daily_summary()
            if not summary:
                return []

            items = []
            # Create a single insight item from the daily summary
            summary_dict = summary if isinstance(summary, dict) else summary.to_dict() if hasattr(summary, "to_dict") else {}
            if summary_dict:
                items.append(NewsfeedItem(
                    id=f"health:daily:{datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
                    item_type=NewsfeedItemType.HEALTH_INSIGHT,
                    source=NewsfeedItemSource.HEALTH,
                    title="Daily health summary",
                    body=summary_dict.get("summary", "Health data available"),
                    timestamp=datetime.now(timezone.utc),
                    priority=NewsfeedItemPriority.LOW,
                    icon="heart.fill",
                    color="#FF2D55",
                    action_type="health",
                    metadata={"date": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
                ))
            return items
        except Exception:
            raise


    async def _aggregate_trading_alerts(self) -> List[NewsfeedItem]:
        """Aggregate recent trading fills and risk alerts into newsfeed items."""
        items: List[NewsfeedItem] = []
        try:
            from hestia.trading.manager import get_trading_manager

            manager = await get_trading_manager()

            # Get recent trades (last 48h worth, capped at 20)
            trades = await manager.get_trades(user_id="user-default", limit=20)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

            for trade in trades:
                trade_ts = trade.get("timestamp")
                if trade_ts:
                    try:
                        ts = datetime.fromisoformat(trade_ts)
                    except (ValueError, TypeError):
                        ts = None
                else:
                    ts = None

                # Skip trades older than 48h
                if ts and ts.tzinfo and ts < cutoff:
                    continue

                side = trade.get("side", "trade").upper()
                pair = trade.get("pair", "")
                price = trade.get("price", 0)
                quantity = trade.get("quantity", 0)

                items.append(NewsfeedItem(
                    id=f"trading:{trade.get('id', '')}",
                    item_type=NewsfeedItemType.TRADING_ALERT,
                    source=NewsfeedItemSource.TRADING,
                    title=f"{side} {pair}",
                    body=f"{side} {quantity} {pair} @ ${price:.4f}",
                    timestamp=ts,
                    priority=NewsfeedItemPriority.NORMAL,
                    icon="arrow.left.arrow.right",
                    color="#FF9F0A",
                    action_type="trade",
                    action_id=trade.get("id"),
                    metadata={
                        "bot_id": trade.get("bot_id", ""),
                        "fee": str(trade.get("fee", 0)),
                        "order_type": trade.get("order_type", ""),
                    },
                ))

            # Check for active kill switch
            try:
                risk_status = manager.get_risk_status()
                if risk_status and risk_status.get("kill_switch", {}).get("active"):
                    items.append(NewsfeedItem(
                        id=f"trading:kill_switch_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                        item_type=NewsfeedItemType.TRADING_ALERT,
                        source=NewsfeedItemSource.TRADING,
                        title="Kill Switch Active",
                        body=f"Trading kill switch activated. Reason: {risk_status.get('kill_switch', {}).get('reason', 'Manual')}",
                        timestamp=datetime.now(timezone.utc),
                        priority=NewsfeedItemPriority.HIGH,
                        icon="exclamationmark.triangle.fill",
                        color="#FF6467",
                        action_type="risk",
                        action_id="kill_switch",
                        metadata={"severity": "high"},
                    ))
            except Exception:
                pass  # Risk status may not be available

        except Exception as e:
            logger.warning(
                f"Failed to aggregate trading alerts: {type(e).__name__}",
                component=LogComponent.NEWSFEED,
            )
        return items

    async def _aggregate_sentinel_alerts(self) -> List[NewsfeedItem]:
        """Aggregate recent sentinel security events into newsfeed items."""
        items: List[NewsfeedItem] = []
        try:
            from hestia.sentinel.store import SentinelStore

            # Sentinel DB is at <repo_root>/data/sentinel_events.db
            db_path = Path(__file__).parent.parent.parent / "data" / "sentinel_events.db"
            if not db_path.exists():
                return items

            store = SentinelStore(str(db_path))

            # SentinelStore uses synchronous sqlite3 — run in executor
            loop = asyncio.get_running_loop()
            events = await loop.run_in_executor(None, store.get_recent_events, 20)

            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)

            severity_colors = {
                "CRITICAL": "#FF3B30",
                "HIGH": "#FF6467",
                "MEDIUM": "#FF9500",
                "LOW": "#8E8E93",
            }
            severity_icons = {
                "CRITICAL": "exclamationmark.shield.fill",
                "HIGH": "shield.lefthalf.filled",
                "MEDIUM": "shield",
                "LOW": "shield",
            }
            severity_priority = {
                "CRITICAL": NewsfeedItemPriority.URGENT,
                "HIGH": NewsfeedItemPriority.HIGH,
                "MEDIUM": NewsfeedItemPriority.NORMAL,
                "LOW": NewsfeedItemPriority.LOW,
            }

            for event in events:
                event_ts_str = event.get("timestamp")
                if event_ts_str:
                    try:
                        ts = datetime.fromisoformat(event_ts_str)
                    except (ValueError, TypeError):
                        ts = None
                else:
                    ts = None

                # Skip events older than 48h
                if ts and ts.tzinfo and ts < cutoff:
                    continue

                severity = event.get("severity", "LOW")

                items.append(NewsfeedItem(
                    id=f"sentinel:{event.get('event_id', '')}",
                    item_type=NewsfeedItemType.SECURITY_ALERT,
                    source=NewsfeedItemSource.SENTINEL,
                    title=f"Sentinel {severity}: {event.get('event_type', 'event')}",
                    body=event.get("summary"),
                    timestamp=ts,
                    priority=severity_priority.get(severity, NewsfeedItemPriority.NORMAL),
                    icon=severity_icons.get(severity, "shield"),
                    color=severity_colors.get(severity, "#8E8E93"),
                    action_type="sentinel",
                    action_id=event.get("event_id"),
                    metadata={
                        "source": event.get("source", ""),
                        "severity": severity,
                        "action_taken": event.get("action_taken") or "",
                        "acknowledged": str(event.get("acknowledged", 0)),
                    },
                ))

        except Exception as e:
            logger.warning(
                f"Failed to aggregate sentinel alerts: {type(e).__name__}",
                component=LogComponent.NEWSFEED,
            )
        return items


async def get_newsfeed_manager() -> NewsfeedManager:
    """Singleton factory for NewsfeedManager."""
    global _instance
    if _instance is None:
        _instance = NewsfeedManager()
        await _instance.initialize()
    return _instance


async def close_newsfeed_manager() -> None:
    """Close the singleton newsfeed manager."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
