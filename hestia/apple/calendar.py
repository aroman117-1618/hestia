"""
Calendar client - Python wrapper for hestia-calendar-cli.

Provides async interface to Apple Calendar via EventKit.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import List, Optional

from .models import Calendar, Event

logger = logging.getLogger(__name__)


class CalendarError(Exception):
    """Calendar operation error."""
    pass


class CalendarClient:
    """Async client for Apple Calendar operations."""

    def __init__(self, cli_path: str = "~/.hestia/bin/hestia-calendar-cli"):
        self.cli_path = Path(cli_path).expanduser()

    async def _run_cli(
        self,
        args: List[str],
        stdin: Optional[str] = None,
        timeout: float = 30.0,
    ) -> dict:
        """Run CLI command and parse JSON response."""
        if not self.cli_path.exists():
            raise CalendarError(f"CLI not found: {self.cli_path}")

        try:
            proc = await asyncio.create_subprocess_exec(
                str(self.cli_path),
                *args,
                stdin=asyncio.subprocess.PIPE if stdin else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(stdin.encode() if stdin else None),
                timeout=timeout,
            )

            stdout_str = stdout.decode().strip()
            stderr_str = stderr.decode().strip()

            if not stdout_str:
                raise CalendarError(f"Empty response from CLI. stderr: {stderr_str}")

            try:
                result = json.loads(stdout_str)
            except json.JSONDecodeError as e:
                raise CalendarError(f"Invalid JSON response: {stdout_str[:200]}") from e

            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                raise CalendarError(error_msg)

            return result

        except asyncio.TimeoutError:
            raise CalendarError(f"CLI command timed out after {timeout}s")
        except FileNotFoundError:
            raise CalendarError(f"CLI not found: {self.cli_path}")

    async def list_calendars(self) -> List[Calendar]:
        """List all calendars."""
        result = await self._run_cli(["list-calendars"])
        calendars = result.get("data", {}).get("calendars", [])
        return [Calendar.from_dict(c) for c in calendars]

    async def list_events(
        self,
        calendar: Optional[str] = None,
        after: Optional[datetime] = None,
        before: Optional[datetime] = None,
    ) -> List[Event]:
        """
        List events with optional filters.

        Args:
            calendar: Filter by calendar name
            after: Only events starting after this date
            before: Only events starting before this date
        """
        args = ["list-events"]

        if calendar:
            args.extend(["--calendar", calendar])
        if after:
            args.extend(["--after", after.strftime("%Y-%m-%d")])
        if before:
            args.extend(["--before", before.strftime("%Y-%m-%d")])

        result = await self._run_cli(args)
        events = result.get("data", {}).get("events", [])
        return [Event.from_dict(e) for e in events]

    async def get_event(self, event_id: str) -> Event:
        """Get event details by ID."""
        result = await self._run_cli(["get-event", event_id])
        event_data = result.get("data", {}).get("event", {})
        return Event.from_dict(event_data)

    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        calendar: Optional[str] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
        all_day: bool = False,
    ) -> Event:
        """
        Create a new calendar event.

        Args:
            title: Event title
            start: Start datetime
            end: End datetime
            calendar: Calendar name (uses default if not specified)
            location: Event location
            notes: Event notes
            all_day: Whether this is an all-day event
        """
        event_data = {
            "title": title,
            "start": start.isoformat(),
            "end": end.isoformat(),
        }

        if calendar:
            event_data["calendar"] = calendar
        if location:
            event_data["location"] = location
        if notes:
            event_data["notes"] = notes
        if all_day:
            event_data["allDay"] = True

        result = await self._run_cli(
            ["create-event"],
            stdin=json.dumps(event_data),
        )

        event_dict = result.get("data", {}).get("event", {})
        return Event.from_dict(event_dict)

    async def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        location: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Event:
        """
        Update an existing event.

        Only specified fields will be updated.
        """
        update_data = {}

        if title is not None:
            update_data["title"] = title
        if start is not None:
            update_data["start"] = start.isoformat()
        if end is not None:
            update_data["end"] = end.isoformat()
        if location is not None:
            update_data["location"] = location
        if notes is not None:
            update_data["notes"] = notes

        if not update_data:
            raise CalendarError("No fields to update")

        result = await self._run_cli(
            ["update-event", event_id],
            stdin=json.dumps(update_data),
        )

        event_dict = result.get("data", {}).get("event", {})
        return Event.from_dict(event_dict)

    async def delete_event(self, event_id: str) -> bool:
        """Delete an event by ID."""
        result = await self._run_cli(["delete-event", event_id])
        return result.get("data", {}).get("deleted", False)

    async def get_today_events(self) -> List[Event]:
        """Get all events for today in the user's local timezone."""
        from hestia.user.config_loader import get_user_timezone
        tz = ZoneInfo(get_user_timezone())
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)
        return await self.list_events(after=today, before=tomorrow)

    async def get_upcoming_events(self, days: int = 7) -> List[Event]:
        """Get events for the next N days in the user's local timezone."""
        from hestia.user.config_loader import get_user_timezone
        tz = ZoneInfo(get_user_timezone())
        today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today + timedelta(days=days)
        return await self.list_events(after=today, before=end_date)
