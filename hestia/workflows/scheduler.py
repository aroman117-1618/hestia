"""
Workflow scheduler — APScheduler integration for scheduled workflows.

Mirrors the OrderScheduler pattern. Manages cron/interval/one-time
triggers for active workflows.
"""

from datetime import datetime, timezone
from typing import Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from hestia.logging import get_logger, LogComponent
from hestia.workflows.models import TriggerType, Workflow, WorkflowStatus

logger = get_logger()

# Module-level singleton
_instance: Optional["WorkflowScheduler"] = None


class WorkflowScheduler:
    """Schedules workflow execution via APScheduler."""

    def __init__(self) -> None:
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._scheduled_jobs: Dict[str, str] = {}  # workflow_id -> job_id

    async def initialize(self) -> None:
        """Initialize APScheduler and load active scheduled workflows."""
        from hestia.user.config_loader import get_user_timezone
        scheduler_tz = get_user_timezone()

        self._scheduler = AsyncIOScheduler(
            timezone=scheduler_tz,
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 3600,
            },
        )
        self._scheduler.start()

        # Load active scheduled workflows
        await self._load_active_workflows()

        logger.info(
            "Workflow scheduler initialized",
            component=LogComponent.WORKFLOW,
            data={"scheduled_workflows": len(self._scheduled_jobs)},
        )

    async def close(self) -> None:
        """Shutdown the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
        self._scheduled_jobs.clear()

    async def _load_active_workflows(self) -> None:
        """Load and schedule all active workflows with schedule triggers."""
        from hestia.workflows.manager import get_workflow_manager

        try:
            manager = await get_workflow_manager()
            workflows, _ = await manager.list_workflows(status="active")
            for wf in workflows:
                if wf.trigger_type == TriggerType.SCHEDULE:
                    self.schedule_workflow(wf)
        except Exception as e:
            logger.warning(
                f"Failed to load active workflows: {type(e).__name__}",
                component=LogComponent.WORKFLOW,
            )

    def schedule_workflow(self, workflow: Workflow) -> None:
        """Schedule a workflow based on its trigger_config."""
        if not self._scheduler:
            return
        if workflow.trigger_type != TriggerType.SCHEDULE:
            return

        trigger = self._create_trigger(workflow.trigger_config)
        if trigger is None:
            logger.warning(
                f"Cannot create trigger for workflow {workflow.id}",
                component=LogComponent.WORKFLOW,
            )
            return

        job_id = f"wf-{workflow.id}"
        self._scheduler.add_job(
            self._execute_workflow,
            trigger=trigger,
            id=job_id,
            args=[workflow.id],
            replace_existing=True,
        )
        self._scheduled_jobs[workflow.id] = job_id

        logger.info(
            f"Scheduled workflow: {workflow.id} ({workflow.name})",
            component=LogComponent.WORKFLOW,
        )

    def unschedule_workflow(self, workflow_id: str) -> None:
        """Remove a workflow from the scheduler."""
        job_id = self._scheduled_jobs.pop(workflow_id, None)
        if job_id and self._scheduler:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass

    def reschedule_workflow(self, workflow: Workflow) -> None:
        """Unschedule and re-schedule a workflow."""
        self.unschedule_workflow(workflow.id)
        if workflow.status == WorkflowStatus.ACTIVE:
            self.schedule_workflow(workflow)

    def _create_trigger(self, trigger_config: Dict) -> Optional[object]:
        """Create an APScheduler trigger from config.

        Supported config keys:
            cron: "0 7 * * *" (cron expression: minute hour day month day_of_week)
            interval_minutes: 60 (interval in minutes, min 15)
        """
        if "cron" in trigger_config:
            parts = trigger_config["cron"].split()
            if len(parts) >= 5:
                return CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                )

        if "interval_minutes" in trigger_config:
            minutes = max(15, int(trigger_config["interval_minutes"]))
            return IntervalTrigger(minutes=minutes)

        return None

    async def _execute_workflow(self, workflow_id: str) -> None:
        """APScheduler callback — triggers workflow execution."""
        from hestia.workflows.manager import get_workflow_manager

        try:
            manager = await get_workflow_manager()
            wf = await manager.get_workflow(workflow_id)
            if not wf or wf.status != WorkflowStatus.ACTIVE:
                return
            await manager.trigger(workflow_id, trigger_source="schedule")
        except Exception as e:
            logger.error(
                f"Scheduled workflow execution failed: {type(e).__name__}",
                component=LogComponent.WORKFLOW,
                data={"workflow_id": workflow_id},
            )

    def get_next_run_time(self, workflow_id: str) -> Optional[datetime]:
        """Get the next scheduled run time for a workflow."""
        job_id = self._scheduled_jobs.get(workflow_id)
        if not job_id or not self._scheduler:
            return None
        job = self._scheduler.get_job(job_id)
        return job.next_run_time if job else None

    def is_scheduled(self, workflow_id: str) -> bool:
        """Check if a workflow is currently scheduled."""
        return workflow_id in self._scheduled_jobs


async def get_workflow_scheduler() -> WorkflowScheduler:
    """Get or create the singleton workflow scheduler."""
    global _instance
    if _instance is None:
        _instance = WorkflowScheduler()
        await _instance.initialize()
    return _instance


async def close_workflow_scheduler() -> None:
    """Close the singleton workflow scheduler."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
