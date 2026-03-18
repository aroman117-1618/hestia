"""
Notification routing engine.

Decides how to deliver a bump notification based on:
  - macOS idle time (active → macOS, idle → APNs to iPhone)
  - Rate limiting (max 1 per session per 5 min)
  - Quiet hours (suppress non-urgent during sleep)
  - Focus mode (defer non-urgent)
  - Session cooldown (suppress after recent response)
  - Batch consolidation (3+ in 60s → single summary)
"""

from datetime import datetime, time, timezone
from typing import Optional, Tuple

from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent
from hestia.notifications.database import NotificationDatabase
from hestia.notifications.idle_detector import get_idle_seconds, is_focus_mode_active
from hestia.notifications.models import (
    BumpRequest,
    BumpStatus,
    NotificationRoute,
    NotificationSettings,
)

logger = get_logger()


class NotificationRouter:
    """Routes bump requests to the appropriate delivery channel."""

    def __init__(self, database: NotificationDatabase) -> None:
        self._database = database

    async def route(
        self, bump: BumpRequest, settings: NotificationSettings
    ) -> Tuple[NotificationRoute, Optional[str]]:
        """Determine delivery route for a bump request.

        Returns:
            (route, reason) — route decision and human-readable reason.
        """
        # 1. Rate limit: max 1 bump per session per rate_limit_seconds
        if bump.session_id:
            recent = await self._database.get_recent_bump_for_session(
                bump.session_id, settings.rate_limit_seconds
            )
            if recent and recent.id != bump.id:
                return NotificationRoute.SUPPRESSED, "rate_limited"

        # 2. Session cooldown: suppress after recent response
        if bump.session_id:
            last_response = await self._database.get_last_response_for_session(
                bump.session_id
            )
            if last_response and last_response.responded_at:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                responded = last_response.responded_at
                if responded.tzinfo is not None:
                    responded = responded.replace(tzinfo=None)
                elapsed = (now - responded).total_seconds()
                if elapsed < settings.session_cooldown_seconds:
                    return NotificationRoute.SUPPRESSED, "session_cooldown"

        # 3. Quiet hours (urgent overrides)
        if settings.quiet_hours_enabled and bump.priority != "urgent":
            if self._is_quiet_hours(settings):
                return NotificationRoute.SUPPRESSED, "quiet_hours"

        # 4. Focus mode (urgent overrides)
        if settings.focus_mode_respect and bump.priority != "urgent":
            if await is_focus_mode_active():
                return NotificationRoute.SUPPRESSED, "focus_mode"

        # 5. Idle detection: macOS active → local, idle → APNs
        idle_seconds = await get_idle_seconds()
        if idle_seconds >= settings.idle_threshold_seconds:
            return NotificationRoute.APNS, "idle"
        else:
            return NotificationRoute.MACOS, "active"

    def _is_quiet_hours(self, settings: NotificationSettings) -> bool:
        """Check if current local time is within quiet hours."""
        now = datetime.now().time()
        try:
            start = time.fromisoformat(settings.quiet_hours_start)
            end = time.fromisoformat(settings.quiet_hours_end)
        except ValueError:
            return False

        # Handle overnight ranges (e.g., 22:00 - 08:00)
        if start > end:
            return now >= start or now < end
        return start <= now < end

    async def should_batch(
        self, bump: BumpRequest, settings: NotificationSettings
    ) -> bool:
        """Check if this bump should be batched with recent pending bumps."""
        pending = await self._database.get_pending_bumps_in_window(
            bump.user_id, settings.batch_window_seconds
        )
        # Batch if 3+ pending bumps in the window (excluding this one)
        other_pending = [b for b in pending if b.id != bump.id]
        return len(other_pending) >= 2
