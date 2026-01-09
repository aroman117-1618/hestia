"""
Reminders client - Python wrapper for hestia-reminders-cli.

Provides async interface to Apple Reminders via EventKit.
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .models import Reminder, ReminderList

logger = logging.getLogger(__name__)


class RemindersError(Exception):
    """Reminders operation error."""
    pass


class RemindersClient:
    """Async client for Apple Reminders operations."""

    def __init__(self, cli_path: str = "~/.hestia/bin/hestia-reminders-cli"):
        self.cli_path = Path(cli_path).expanduser()

    async def _run_cli(
        self,
        args: List[str],
        stdin: Optional[str] = None,
        timeout: float = 30.0,
    ) -> dict:
        """Run CLI command and parse JSON response."""
        if not self.cli_path.exists():
            raise RemindersError(f"CLI not found: {self.cli_path}")

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
                raise RemindersError(f"Empty response from CLI. stderr: {stderr_str}")

            try:
                result = json.loads(stdout_str)
            except json.JSONDecodeError as e:
                raise RemindersError(f"Invalid JSON response: {stdout_str[:200]}") from e

            if not result.get("success"):
                error_msg = result.get("error", "Unknown error")
                raise RemindersError(error_msg)

            return result

        except asyncio.TimeoutError:
            raise RemindersError(f"CLI command timed out after {timeout}s")
        except FileNotFoundError:
            raise RemindersError(f"CLI not found: {self.cli_path}")

    async def list_lists(self) -> List[ReminderList]:
        """List all reminder lists."""
        result = await self._run_cli(["list-lists"])
        lists = result.get("data", {}).get("lists", [])
        return [ReminderList.from_dict(lst) for lst in lists]

    async def list_reminders(
        self,
        list_name: Optional[str] = None,
        completed: bool = False,
        incomplete: bool = False,
    ) -> List[Reminder]:
        """
        List reminders with optional filters.

        Args:
            list_name: Filter by list name
            completed: Show only completed reminders
            incomplete: Show only incomplete reminders
        """
        args = ["list-reminders"]

        if list_name:
            args.extend(["--list", list_name])
        if completed:
            args.append("--completed")
        if incomplete:
            args.append("--incomplete")

        result = await self._run_cli(args)
        reminders = result.get("data", {}).get("reminders", [])
        return [Reminder.from_dict(r) for r in reminders]

    async def get_reminder(self, reminder_id: str) -> Reminder:
        """Get reminder details by ID."""
        result = await self._run_cli(["get-reminder", reminder_id])
        reminder_data = result.get("data", {}).get("reminder", {})
        return Reminder.from_dict(reminder_data)

    async def create_reminder(
        self,
        title: str,
        list_name: Optional[str] = None,
        due: Optional[datetime] = None,
        priority: int = 0,
        notes: Optional[str] = None,
    ) -> Reminder:
        """
        Create a new reminder.

        Args:
            title: Reminder title
            list_name: List name (uses default if not specified)
            due: Due date/time
            priority: Priority (0=none, 1-4=high, 5=medium, 6-9=low)
            notes: Additional notes
        """
        reminder_data = {"title": title}

        if list_name:
            reminder_data["list"] = list_name
        if due:
            reminder_data["due"] = due.isoformat()
        if priority:
            reminder_data["priority"] = priority
        if notes:
            reminder_data["notes"] = notes

        result = await self._run_cli(
            ["create-reminder"],
            stdin=json.dumps(reminder_data),
        )

        reminder_dict = result.get("data", {}).get("reminder", {})
        return Reminder.from_dict(reminder_dict)

    async def complete_reminder(self, reminder_id: str) -> Reminder:
        """Mark a reminder as complete."""
        result = await self._run_cli(["complete-reminder", reminder_id])
        reminder_dict = result.get("data", {}).get("reminder", {})
        return Reminder.from_dict(reminder_dict)

    async def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder by ID."""
        result = await self._run_cli(["delete-reminder", reminder_id])
        return result.get("data", {}).get("deleted", False)

    async def get_incomplete(self, list_name: Optional[str] = None) -> List[Reminder]:
        """Get all incomplete reminders."""
        return await self.list_reminders(list_name=list_name, incomplete=True)

    async def get_due_today(self) -> List[Reminder]:
        """Get reminders due today (incomplete only)."""
        reminders = await self.get_incomplete()
        today = datetime.now().date()
        return [r for r in reminders if r.due and r.due.date() == today]

    async def get_overdue(self) -> List[Reminder]:
        """Get overdue reminders (incomplete, past due date)."""
        reminders = await self.get_incomplete()
        now = datetime.now()
        return [r for r in reminders if r.due and r.due < now]
