"""Learning module scheduler — periodic background analysis.

Runs 8 monitors on independent schedules:
- MetaMonitor: hourly behavioral analysis (outcomes + routing quality)
- MemoryHealthMonitor: daily cross-system diagnostics (ChromaDB + knowledge graph)
- TriggerMonitor: periodic threshold checking (configurable via triggers.yaml)
- ImportanceScorer: nightly importance scoring (Sprint 16)
- MemoryConsolidator: weekly dedup (Sprint 16)
- MemoryPruner: weekly archive (Sprint 16)
- CorrectionClassifier: 6-hourly correction classification (Sprint 17)
- OutcomeDistiller: weekly principle distillation (Sprint 17)
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
from hestia.memory.importance import ImportanceScorer
from hestia.memory.consolidator import MemoryConsolidator
from hestia.memory.pruner import MemoryPruner
from hestia.learning.correction_classifier import CorrectionClassifier
from hestia.learning.outcome_distiller import OutcomeDistiller


logger = get_logger()

DEFAULT_USER_ID = "default"


class LearningScheduler:
    """Schedules periodic learning analysis tasks as async background loops."""

    def __init__(self) -> None:
        self._db: Optional[LearningDatabase] = None
        self._meta_monitor: Optional[MetaMonitorManager] = None
        self._memory_health: Optional[MemoryHealthMonitor] = None
        self._trigger_monitor: Optional[TriggerMonitor] = None
        self._importance_scorer: Optional[ImportanceScorer] = None
        self._consolidator: Optional[MemoryConsolidator] = None
        self._pruner: Optional[MemoryPruner] = None
        self._correction_classifier: Optional[CorrectionClassifier] = None
        self._outcome_distiller: Optional[OutcomeDistiller] = None
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

        # Memory lifecycle components (Sprint 16)
        memory_config = self._load_memory_config()
        self._importance_scorer = ImportanceScorer(
            memory_db=memory_mgr.database,
            outcome_db=outcome_mgr,
            config=memory_config,
        )
        self._consolidator = MemoryConsolidator(
            memory_db=memory_mgr.database,
            vector_store=memory_mgr.vector_store,
            config=memory_config,
        )
        self._pruner = MemoryPruner(
            memory_db=memory_mgr.database,
            vector_store=memory_mgr.vector_store,
            learning_db=self._db,
            config=memory_config,
        )

        # Sprint 17: Learning closure components
        # inference_client is required for LLM distillation — without it the
        # weekly distillation loop runs but always no-ops (Gap 1 fix).
        from hestia.inference import get_inference_client
        inference_client = await get_inference_client()

        self._correction_classifier = CorrectionClassifier(
            learning_db=self._db,
            outcome_db=outcome_mgr._database,
        )
        self._outcome_distiller = OutcomeDistiller(
            learning_db=self._db,
            outcome_db=outcome_mgr._database,
            principle_store=research_mgr._principle_store,
            inference_client=inference_client,
        )

        # Start background loops
        self._running = True
        self._tasks.append(asyncio.create_task(self._meta_monitor_loop()))
        self._tasks.append(asyncio.create_task(self._memory_health_loop()))
        self._tasks.append(asyncio.create_task(self._trigger_check_loop(config)))
        self._tasks.append(asyncio.create_task(self._importance_scorer_loop()))
        self._tasks.append(asyncio.create_task(self._consolidation_loop()))
        self._tasks.append(asyncio.create_task(self._pruning_loop()))
        self._tasks.append(asyncio.create_task(self._correction_loop()))
        self._tasks.append(asyncio.create_task(self._distillation_loop()))

        logger.info(
            "Learning scheduler started",
            component=LogComponent.LEARNING,
            data={"monitors": 8},
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

    def _load_memory_config(self) -> Dict[str, Any]:
        """Load memory configuration from YAML (for lifecycle components)."""
        config_path = Path(__file__).parent.parent / "config" / "memory.yaml"
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            return {}

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

    # ── Memory Lifecycle Loops (Sprint 16) ─────────────────────

    async def _importance_scorer_loop(self) -> None:
        """Run importance scoring nightly."""
        await asyncio.sleep(240)  # 4 min after startup
        while self._running:
            try:
                stats = await self._importance_scorer.score_all(DEFAULT_USER_ID)
                logger.info(
                    "Importance scoring complete",
                    component=LogComponent.MEMORY,
                    data=stats,
                )
            except Exception as e:
                logger.warning(
                    f"Importance scoring failed: {type(e).__name__}",
                    component=LogComponent.MEMORY,
                )
            await asyncio.sleep(86400)  # 24 hours

    async def _consolidation_loop(self) -> None:
        """Run consolidation weekly."""
        await asyncio.sleep(300)  # 5 min after startup
        while self._running:
            try:
                result = await self._consolidator.execute(dry_run=False)
                logger.info(
                    "Consolidation complete",
                    component=LogComponent.MEMORY,
                    data=result,
                )
            except Exception as e:
                logger.warning(
                    f"Consolidation failed: {type(e).__name__}",
                    component=LogComponent.MEMORY,
                )
            await asyncio.sleep(604800)  # 7 days

    async def _pruning_loop(self) -> None:
        """Run pruning weekly (1 hour after consolidation)."""
        await asyncio.sleep(3900)  # 65 min after startup (after first consolidation)
        while self._running:
            try:
                result = await self._pruner.execute()
                logger.info(
                    "Pruning complete",
                    component=LogComponent.MEMORY,
                    data=result,
                )
            except Exception as e:
                logger.warning(
                    f"Pruning failed: {type(e).__name__}",
                    component=LogComponent.MEMORY,
                )
            await asyncio.sleep(604800)  # 7 days

    # ── Learning Closure Loops (Sprint 17) ─────────────────────

    async def _correction_loop(self) -> None:
        """Classify pending corrections every 6 hours."""
        await asyncio.sleep(360)  # 6 min after startup
        while self._running:
            try:
                stats = await self._correction_classifier.classify_all_pending(DEFAULT_USER_ID)
                if stats.get("classified", 0) > 0:
                    logger.info(
                        "Correction classification complete",
                        component=LogComponent.LEARNING,
                        data=stats,
                    )
            except Exception as e:
                logger.warning(
                    f"Correction classification failed: {type(e).__name__}",
                    component=LogComponent.LEARNING,
                )
            await asyncio.sleep(21600)  # 6 hours

    async def _distillation_loop(self) -> None:
        """Distill principles from outcomes and corrections weekly."""
        await asyncio.sleep(420)  # 7 min after startup
        while self._running:
            try:
                result = await self._outcome_distiller.distill_from_outcomes(DEFAULT_USER_ID)
                logger.info(
                    "Outcome distillation complete",
                    component=LogComponent.LEARNING,
                    data=result,
                )
            except Exception as e:
                logger.warning(
                    f"Outcome distillation failed: {type(e).__name__}",
                    component=LogComponent.LEARNING,
                )

            # Gap 2: also distill from classified corrections (Sprint 19)
            try:
                corr_result = await self._outcome_distiller.distill_from_corrections(DEFAULT_USER_ID)
                if corr_result.get("corrections_processed", 0) > 0:
                    logger.info(
                        "Correction distillation complete",
                        component=LogComponent.LEARNING,
                        data=corr_result,
                    )
            except Exception as e:
                logger.warning(
                    f"Correction distillation failed: {type(e).__name__}",
                    component=LogComponent.LEARNING,
                )

            await asyncio.sleep(604800)  # 7 days


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
