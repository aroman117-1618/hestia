"""
Interruption Policy Manager for Hestia.

Manages when and how Hestia can proactively interrupt the user,
respecting:
- User's policy preference (NEVER, DAILY_ONLY, PROACTIVE)
- macOS/iOS Focus mode
- Calendar busy status
- Quiet hours
- Notification priority

Implements ADR-017: Proactive Intelligence Framework.
"""

import subprocess
from datetime import datetime, timezone
from typing import Optional

from hestia.logging import get_logger, LogComponent
from hestia.proactive.models import (
    InterruptionPolicy,
    InterruptionContext,
    NotificationPriority,
    ProactiveConfig,
)


class InterruptionManager:
    """
    Manages interruption decisions for proactive features.

    Checks multiple factors to determine if an interruption is appropriate:
    1. User's global policy setting
    2. System Focus mode (macOS/iOS)
    3. Calendar busy status
    4. Quiet hours configuration
    5. Notification priority
    """

    def __init__(self, config: Optional[ProactiveConfig] = None):
        """
        Initialize the interruption manager.

        Args:
            config: Proactive configuration. If None, uses defaults.
        """
        self.config = config or ProactiveConfig()
        self.logger = get_logger()

    def get_context(self) -> InterruptionContext:
        """
        Build current interruption context.

        Returns:
            InterruptionContext with current state.
        """
        now = datetime.now(timezone.utc)

        return InterruptionContext(
            current_time=now,
            day_of_week=now.weekday(),
            is_focus_mode=self._check_focus_mode(),
            is_busy_calendar=self._check_calendar_busy(),
            is_quiet_hours=self.config.is_quiet_hours(now.time()),
        )

    def can_interrupt(
        self,
        priority: NotificationPriority = NotificationPriority.MEDIUM,
        context: Optional[InterruptionContext] = None,
    ) -> bool:
        """
        Check if an interruption is allowed.

        Args:
            priority: Notification priority level.
            context: Optional pre-built context. If None, builds fresh.

        Returns:
            True if interruption is allowed.
        """
        if context is None:
            context = self.get_context()

        allowed = context.can_interrupt(self.config.interruption_policy, priority)

        self.logger.debug(
            f"Interruption check: {'allowed' if allowed else 'blocked'}",
            component=LogComponent.ORCHESTRATION,
            data={
                "priority": priority.value,
                "policy": self.config.interruption_policy.value,
                "is_focus_mode": context.is_focus_mode,
                "is_busy_calendar": context.is_busy_calendar,
                "is_quiet_hours": context.is_quiet_hours,
            },
        )

        return allowed

    def _check_focus_mode(self) -> bool:
        """
        Check if macOS Focus mode (Do Not Disturb) is active.

        Uses macOS `defaults` command to check Focus status.
        Returns False if check fails (fail-open approach).

        Security: Validates file paths to prevent symlink attacks.
        """
        try:
            # Check macOS Focus mode via defaults
            result = subprocess.run(
                ["defaults", "read", "com.apple.controlcenter", "NSStatusItem Visible FocusModes"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )

            # If visible (1), Focus is potentially active
            # Additional check for actual DND status
            if result.returncode == 0 and "1" in result.stdout:
                # Security: Validate the path to prevent symlink attacks
                dnd_path = os.path.expanduser("~/Library/DoNotDisturb/DB/Assertions.json")
                expected_prefix = os.path.realpath(os.path.expanduser("~/Library/DoNotDisturb"))

                # Resolve any symlinks and check the real path
                real_path = os.path.realpath(dnd_path)

                # Verify the path stays within the expected directory
                if not real_path.startswith(expected_prefix + os.sep) and real_path != expected_prefix:
                    self.logger.warning(
                        "Focus mode path validation failed - potential symlink attack",
                        component=LogComponent.ORCHESTRATION,
                        data={
                            "expected_prefix": expected_prefix,
                            "actual_path": real_path,
                        },
                    )
                    return False

                # Verify the file exists and is a regular file
                if not os.path.isfile(real_path):
                    return False

                # Check the actual assertion status
                dnd_result = subprocess.run(
                    ["plutil", "-extract", "userPref", "raw", "-o", "-", real_path],
                    capture_output=True,
                    text=True,
                    timeout=2.0,
                )
                return dnd_result.returncode == 0 and len(dnd_result.stdout.strip()) > 2

            return False

        except Exception:
            # Fail open - if we can't check, allow interruption
            return False

    def _check_calendar_busy(self) -> bool:
        """
        Check if user is currently in a calendar event.

        Returns False if check fails (fail-open approach).
        """
        try:
            from hestia.apple.calendar import CalendarClient

            client = CalendarClient()
            now = datetime.now()

            # Get today's events
            events = client.get_today_events()

            # Check if any event is happening now
            for event in events:
                if event.is_all_day:
                    continue

                if event.start_date and event.end_date:
                    if event.start_date <= now <= event.end_date:
                        return True

            return False

        except Exception:
            # Fail open - if we can't check, allow interruption
            return False

    def should_send_briefing(self) -> bool:
        """
        Check if daily briefing should be sent now.

        Returns:
            True if briefing should be sent.
        """
        now = datetime.now(timezone.utc)

        if not self.config.should_send_briefing(now):
            return False

        # Briefings ignore Focus mode and calendar busy
        # But respect NEVER policy
        if self.config.interruption_policy == InterruptionPolicy.NEVER:
            return False

        return True

    def get_next_briefing_time(self) -> Optional[datetime]:
        """
        Get the next scheduled briefing time.

        Returns:
            Next briefing datetime, or None if disabled.
        """
        if not self.config.briefing_enabled:
            return None

        now = datetime.now(timezone.utc)
        today = now.date()

        # Check today
        briefing_today = datetime.combine(
            today,
            self.config.briefing_time,
            tzinfo=timezone.utc,
        )

        if briefing_today > now and now.weekday() in self.config.briefing_days:
            return briefing_today

        # Find next valid day
        for days_ahead in range(1, 8):
            future_date = today + timedelta(days=days_ahead)
            future_weekday = future_date.weekday()

            if future_weekday in self.config.briefing_days:
                return datetime.combine(
                    future_date,
                    self.config.briefing_time,
                    tzinfo=timezone.utc,
                )

        return None


# Import needed for calendar check
import os
from datetime import timedelta


# Module-level singleton
_manager: Optional[InterruptionManager] = None


def get_interruption_manager(config: Optional[ProactiveConfig] = None) -> InterruptionManager:
    """Get or create the singleton interruption manager."""
    global _manager
    if _manager is None or config is not None:
        _manager = InterruptionManager(config)
    return _manager
