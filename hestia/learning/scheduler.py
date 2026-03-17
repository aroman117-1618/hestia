"""Learning module scheduler — periodic background analysis.

Runs three monitors on independent schedules:
- MetaMonitor: hourly behavioral analysis (outcomes + routing quality)
- MemoryHealthMonitor: daily cross-system diagnostics (ChromaDB + knowledge graph)
- TriggerMonitor: periodic threshold checking (configurable via triggers.yaml)
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from hestia.logging import get_logger, LogComponent
from hestia.learning.database import LearningDatabase
from hestia.learning.meta_monitor import MetaMonitorManager
from hestia.learning.memory_health import MemoryHealthMonitor
from hestia.learning.trigger_monitor import TriggerMonitor


logger = get_logger()

DEFAULT_USER_ID = "default"


class LearningScheduler:
    """Schedules periodic learning analysis tasks as async background loops."""

    def __init__(self) -> None:
        self._db: Optional[LearningDatabase] = None
        self._meta_monitor: Optional[MetaMonitorManager] = None
        self._memory_health: Optional[MemoryHealthMonitor] = None
        self._trigger_monitor: Optional[TriggerMonitor] = None
        self._tasks: List[asyncio.Task] = []
        self._running = False

    async def initialize(self) -> None:
        """Initialize monitors with dependencies and start background loops."""
        # Initialize learning database
        self._db = LearningDatabase()
        await self._db.connect()

        # Load triggers config
        config = self._load_triggers_config()

        # Get dependencies from existing singletons (all initialized in Phase 2)
        from hestia.outcomes import get_outcome_manager
        from hestia.orchestration.audit_db import get_routing_audit_db
        from hestia.memory import get_memory_manager
        from hestia.research.manager import get_research_manager

        outcome_mgr = await get_outcome_manager()
        routing_db = await get_routing_audit_db()
        memory_mgr = await get_memory_manager()
        research_mgr = await get_research_manager()

        # Create monitors
        self._meta_monitor = MetaMonitorManager(
            outcome_db=outcome_mgr,
            routing_audit_db=routing_db,
            learning_db=self._db,
        )
        self._memory_health = MemoryHealthMonitor(
            memory_manager=memory_mgr,
            research_db=research_mgr._database,
            learning_db=self._db,
        )
        self._trigger_monitor = TriggerMonitor(
            learning_db=self._db,
            config=config,
        )

        # Start background loops
        self._running = True
        self._tasks.append(asyncio.create_task(self._meta_monitor_loop()))
        self._tasks.append(asyncio.create_task(self._memory_health_loop()))
        self._tasks.append(asyncio.create_task(self._trigger_check_loop(config)))

        logger.info(
            "Learning scheduler started",
            component=LogComponent.LEARNING,
            data={"monitors": 3},
        )

    async def close(self) -> None:
        """Stop all background tasks and close database."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

        if self._db:
            await self._db.close()

        logger.info("Learning scheduler stopped", component=LogComponent.LEARNING)

    def _load_triggers_config(self) -> Dict[str, Any]:
        """Load triggers configuration from YAML."""
        config_path = Path(__file__).parent.parent / "config" / "triggers.yaml"
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(
                "triggers.yaml not found, triggers disabled",
                component=LogComponent.LEARNING,
            )
            return {}

    async def _meta_monitor_loop(self) -> None:
        """Run MetaMonitor analysis every hour."""
        await asyncio.sleep(60)  # Initial delay — let server stabilize
        while self._running:
            try:
                await self._meta_monitor.analyze(DEFAULT_USER_ID)
            except Exception as e:
                logger.warning(
                    f"MetaMonitor analysis failed: {type(e).__name__}",
                    component=LogComponent.LEARNING,
                )
            await asyncio.sleep(3600)  # 1 hour

    async def _memory_health_loop(self) -> None:
        """Collect memory health snapshots daily."""
        await asyncio.sleep(120)  # Stagger startup (2 min after server start)
        while self._running:
            try:
                await self._memory_health.collect_snapshot(DEFAULT_USER_ID)
            except Exception as e:
                logger.warning(
                    f"MemoryHealth snapshot failed: {type(e).__name__}",
                    component=LogComponent.LEARNING,
                )
            await asyncio.sleep(86400)  # 24 hours

    async def _trigger_check_loop(self, config: Dict[str, Any]) -> None:
        """Check trigger thresholds periodically."""
        interval_hours = config.get("triggers", {}).get("check_interval_hours", 24)
        await asyncio.sleep(180)  # Stagger startup (3 min, after first health snapshot)
        while self._running:
            try:
                metrics = await self._gather_metrics()
                if metrics:
                    await self._trigger_monitor.check_thresholds(DEFAULT_USER_ID, metrics)
            except Exception as e:
                logger.warning(
                    f"TriggerMonitor check failed: {type(e).__name__}",
                    component=LogComponent.LEARNING,
                )
            await asyncio.sleep(interval_hours * 3600)

    async def _gather_metrics(self) -> Dict[str, float]:
        """Gather current system metrics from latest snapshots for trigger checking."""
        metrics: Dict[str, float] = {}

        try:
            snapshot = await self._db.get_latest_health_snapshot(DEFAULT_USER_ID)
            if snapshot:
                metrics["memory_total_chunks"] = float(snapshot.chunk_count)
                metrics["memory_redundancy_pct"] = float(snapshot.redundancy_estimate_pct)
                metrics["knowledge_entity_count"] = float(snapshot.entity_count)
        except Exception:
            pass

        try:
            report = await self._db.get_latest_report(DEFAULT_USER_ID)
            if report and report.avg_latency_ms is not None:
                metrics["inference_avg_latency_ms"] = float(report.avg_latency_ms)
        except Exception:
            pass

        return metrics


# ── Singleton ──────────────────────────────────────────────

_scheduler: Optional[LearningScheduler] = None


async def get_learning_scheduler() -> LearningScheduler:
    """Get or create the learning scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = LearningScheduler()
        await _scheduler.initialize()
    return _scheduler


async def close_learning_scheduler() -> None:
    """Shut down the learning scheduler."""
    global _scheduler
    if _scheduler is not None:
        await _scheduler.close()
        _scheduler = None
