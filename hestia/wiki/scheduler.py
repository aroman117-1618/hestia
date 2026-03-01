"""
Wiki scheduler for automatic article regeneration.

Manages a weekly sweep that detects stale articles and
regenerates them via cloud LLM. Uses APScheduler with
CronTrigger, following the same pattern as orders/scheduler.py.
"""

import yaml
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from hestia.logging import get_logger, LogComponent

from .manager import WikiManager, get_wiki_manager


class WikiScheduler:
    """
    Schedules weekly wiki staleness sweeps.

    Reads schedule config from wiki.yaml and runs
    regenerate_stale() on a CronTrigger.
    """

    def __init__(self, manager: Optional[WikiManager] = None):
        """
        Initialize wiki scheduler.

        Args:
            manager: WikiManager instance. If None, uses singleton.
        """
        self._manager = manager
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._config: Optional[Dict[str, Any]] = None
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the scheduler and register the weekly sweep job."""
        if self._manager is None:
            self._manager = await get_wiki_manager()

        self._config = self._load_config()
        schedule = self._config.get("schedule", {})

        self._scheduler = AsyncIOScheduler(
            timezone="UTC",
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 60 * 60 * 4,  # 4 hour grace period
            },
        )

        # Register weekly sweep job
        day_of_week = schedule.get("day_of_week", "sun")
        hour = schedule.get("hour", 3)
        minute = schedule.get("minute", 0)

        self._scheduler.add_job(
            self._weekly_sweep,
            trigger=CronTrigger(
                day_of_week=day_of_week,
                hour=hour,
                minute=minute,
            ),
            id="wiki-weekly-sweep",
            name="Wiki weekly staleness sweep",
            replace_existing=True,
        )

        self._scheduler.start()

        self.logger.info(
            "Wiki scheduler initialized",
            component=LogComponent.WIKI,
            data={
                "day_of_week": day_of_week,
                "hour": hour,
                "minute": minute,
                "next_sweep": str(self.get_next_sweep_time()),
            },
        )

    async def close(self) -> None:
        """Shutdown the scheduler."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

        self.logger.debug(
            "Wiki scheduler closed",
            component=LogComponent.WIKI,
        )

    @property
    def manager(self) -> WikiManager:
        """Get wiki manager."""
        if self._manager is None:
            raise RuntimeError("Wiki scheduler not initialized. Call initialize() first.")
        return self._manager

    @property
    def scheduler(self) -> AsyncIOScheduler:
        """Get APScheduler instance."""
        if self._scheduler is None:
            raise RuntimeError("Wiki scheduler not initialized. Call initialize() first.")
        return self._scheduler

    @property
    def config(self) -> Dict[str, Any]:
        """Get wiki config."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    async def _weekly_sweep(self) -> None:
        """Execute the weekly staleness sweep."""
        try:
            result = await self.manager.regenerate_stale(trigger_source="scheduled")

            self.logger.info(
                "Weekly wiki sweep complete",
                component=LogComponent.WIKI,
                data={
                    "regenerated": len(result.get("regenerated", [])),
                    "skipped": len(result.get("skipped", [])),
                    "failed": len(result.get("failed", [])),
                },
            )
        except Exception as e:
            self.logger.error(
                f"Weekly wiki sweep failed: {type(e).__name__}",
                component=LogComponent.WIKI,
            )

    def get_next_sweep_time(self) -> Optional[datetime]:
        """Get the next scheduled sweep time."""
        try:
            job = self.scheduler.get_job("wiki-weekly-sweep")
            if job:
                return job.next_run_time
        except Exception:
            pass
        return None

    def is_post_deploy_enabled(self) -> bool:
        """Check if post-deploy auto-refresh is enabled."""
        schedule = self.config.get("schedule", {})
        return schedule.get("post_deploy_enabled", True)

    def get_post_deploy_delay(self) -> int:
        """Get post-deploy delay in seconds."""
        schedule = self.config.get("schedule", {})
        return schedule.get("post_deploy_delay_seconds", 5)

    def _load_config(self) -> Dict[str, Any]:
        """Load wiki.yaml config."""
        config_path = Path(__file__).parent.parent / "config" / "wiki.yaml"
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            self.logger.warning(
                f"Failed to load wiki config: {type(e).__name__}",
                component=LogComponent.WIKI,
            )
            return {}


# Module-level singleton
_wiki_scheduler: Optional[WikiScheduler] = None


async def get_wiki_scheduler() -> WikiScheduler:
    """Get or create singleton wiki scheduler."""
    global _wiki_scheduler
    if _wiki_scheduler is None:
        _wiki_scheduler = WikiScheduler()
        await _wiki_scheduler.initialize()
    return _wiki_scheduler


async def close_wiki_scheduler() -> None:
    """Close the singleton wiki scheduler."""
    global _wiki_scheduler
    if _wiki_scheduler is not None:
        await _wiki_scheduler.close()
        _wiki_scheduler = None
