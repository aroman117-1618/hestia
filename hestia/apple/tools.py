"""
Apple ecosystem tools for registration with execution layer.

Provides Tool definitions for Calendar, Reminders, Notes, and Mail.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..execution.models import Tool, ToolParam, ToolParamType
from ..execution.registry import ToolRegistry
from .calendar import CalendarClient, CalendarError
from .reminders import RemindersClient, RemindersError
from .notes import NotesClient, NotesError
from .mail import MailClient, MailError


# Singleton clients (initialized lazily)
_calendar_client: Optional[CalendarClient] = None
_reminders_client: Optional[RemindersClient] = None
_notes_client: Optional[NotesClient] = None
_mail_client: Optional[MailClient] = None


def _get_calendar_client() -> CalendarClient:
    global _calendar_client
    if _calendar_client is None:
        _calendar_client = CalendarClient()
    return _calendar_client


def _get_reminders_client() -> RemindersClient:
    global _reminders_client
    if _reminders_client is None:
        _reminders_client = RemindersClient()
    return _reminders_client


def _get_notes_client() -> NotesClient:
    global _notes_client
    if _notes_client is None:
        _notes_client = NotesClient()
    return _notes_client


def _get_mail_client() -> MailClient:
    global _mail_client
    if _mail_client is None:
        _mail_client = MailClient()
    return _mail_client


# ============================================================================
# Calendar Tool Handlers
# ============================================================================

async def list_calendars() -> Dict[str, Any]:
    """List all calendars."""
    client = _get_calendar_client()
    calendars = await client.list_calendars()
    return {
        "calendars": [
            {"id": c.id, "title": c.title, "source": c.source}
            for c in calendars
        ],
        "count": len(calendars),
    }


async def list_events(
    calendar: Optional[str] = None,
    after: Optional[str] = None,
    before: Optional[str] = None,
    days: int = 7,
) -> Dict[str, Any]:
    """List calendar events."""
    client = _get_calendar_client()

    after_dt = None
    before_dt = None

    if after:
        after_dt = datetime.fromisoformat(after.replace("Z", "+00:00"))
    if before:
        before_dt = datetime.fromisoformat(before.replace("Z", "+00:00"))

    # Default to upcoming events if no dates specified
    if not after_dt and not before_dt:
        events = await client.get_upcoming_events(days=days)
    else:
        events = await client.list_events(
            calendar=calendar,
            after=after_dt,
            before=before_dt,
        )

    return {
        "events": [
            {
                "id": e.id,
                "title": e.title,
                "calendar": e.calendar,
                "start": e.start.isoformat() if e.start else None,
                "end": e.end.isoformat() if e.end else None,
                "location": e.location,
                "isAllDay": e.is_all_day,
            }
            for e in events
        ],
        "count": len(events),
    }


async def create_event(
    title: str,
    start: str,
    end: str,
    calendar: Optional[str] = None,
    location: Optional[str] = None,
    notes: Optional[str] = None,
    all_day: bool = False,
) -> Dict[str, Any]:
    """Create a calendar event."""
    client = _get_calendar_client()

    event = await client.create_event(
        title=title,
        start=datetime.fromisoformat(start.replace("Z", "+00:00")),
        end=datetime.fromisoformat(end.replace("Z", "+00:00")),
        calendar=calendar,
        location=location,
        notes=notes,
        all_day=all_day,
    )

    return {
        "created": True,
        "event": {
            "id": event.id,
            "title": event.title,
            "calendar": event.calendar,
        },
    }


async def get_today_events() -> Dict[str, Any]:
    """Get today's calendar events."""
    client = _get_calendar_client()
    events = await client.get_today_events()

    return {
        "events": [
            {
                "id": e.id,
                "title": e.title,
                "calendar": e.calendar,
                "start": e.start.isoformat() if e.start else None,
                "end": e.end.isoformat() if e.end else None,
                "location": e.location,
            }
            for e in events
        ],
        "count": len(events),
    }


# ============================================================================
# Reminders Tool Handlers
# ============================================================================

async def list_reminder_lists() -> Dict[str, Any]:
    """List all reminder lists."""
    client = _get_reminders_client()
    lists = await client.list_lists()

    return {
        "lists": [
            {"id": lst.id, "title": lst.title, "source": lst.source}
            for lst in lists
        ],
        "count": len(lists),
    }


async def list_reminders(
    list_name: Optional[str] = None,
    completed: bool = False,
    incomplete: bool = True,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    """List reminders."""
    client = _get_reminders_client()
    reminders = await client.list_reminders(
        list_name=list_name,
        completed=completed,
        incomplete=incomplete,
    )

    # Apply limit if specified
    if limit and limit > 0:
        reminders = reminders[:limit]

    return {
        "reminders": [
            {
                "id": r.id,
                "title": r.title,
                "list": r.list_name,
                "isCompleted": r.is_completed,
                "due": r.due.isoformat() if r.due else None,
                "priority": r.priority,
            }
            for r in reminders
        ],
        "count": len(reminders),
    }


async def create_reminder(
    title: str,
    list_name: Optional[str] = None,
    due: Optional[str] = None,
    priority: int = 0,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a reminder."""
    client = _get_reminders_client()

    due_dt = datetime.fromisoformat(due.replace("Z", "+00:00")) if due else None

    reminder = await client.create_reminder(
        title=title,
        list_name=list_name,
        due=due_dt,
        priority=priority,
        notes=notes,
    )

    return {
        "created": True,
        "reminder": {
            "id": reminder.id,
            "title": reminder.title,
            "list": reminder.list_name,
        },
    }


async def complete_reminder(reminder_id: str) -> Dict[str, Any]:
    """Mark a reminder as complete."""
    client = _get_reminders_client()
    reminder = await client.complete_reminder(reminder_id)

    return {
        "completed": True,
        "reminder": {
            "id": reminder.id,
            "title": reminder.title,
        },
    }


async def get_due_reminders() -> Dict[str, Any]:
    """Get reminders due today."""
    client = _get_reminders_client()
    reminders = await client.get_due_today()

    return {
        "reminders": [
            {
                "id": r.id,
                "title": r.title,
                "list": r.list_name,
                "due": r.due.isoformat() if r.due else None,
            }
            for r in reminders
        ],
        "count": len(reminders),
    }


async def get_overdue_reminders() -> Dict[str, Any]:
    """Get overdue reminders."""
    client = _get_reminders_client()
    reminders = await client.get_overdue()

    return {
        "reminders": [
            {
                "id": r.id,
                "title": r.title,
                "list": r.list_name,
                "due": r.due.isoformat() if r.due else None,
            }
            for r in reminders
        ],
        "count": len(reminders),
    }


# ============================================================================
# Notes Tool Handlers
# ============================================================================

async def list_note_folders() -> Dict[str, Any]:
    """List all note folders."""
    client = _get_notes_client()
    folders = await client.list_folders()

    return {
        "folders": [{"id": f.id, "name": f.name} for f in folders],
        "count": len(folders),
    }


async def list_notes(folder: Optional[str] = None) -> Dict[str, Any]:
    """List notes, optionally filtered by folder."""
    client = _get_notes_client()
    notes = await client.list_notes(folder=folder)

    return {
        "notes": [
            {
                "id": n.id,
                "title": n.title,
                "folder": n.folder,
                "modifiedAt": n.modified_at,
            }
            for n in notes
        ],
        "count": len(notes),
    }


async def get_note(note_id: str) -> Dict[str, Any]:
    """Get note content."""
    client = _get_notes_client()
    note = await client.get_note(note_id)

    return {
        "note": {
            "id": note.id,
            "title": note.title,
            "folder": note.folder,
            "body": note.body,
            "createdAt": note.created_at,
            "modifiedAt": note.modified_at,
        },
    }


async def create_note(
    title: str,
    body: Optional[str] = None,
    folder: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a note."""
    client = _get_notes_client()
    note = await client.create_note(title=title, body=body, folder=folder)

    return {
        "created": True,
        "note": {
            "id": note.id,
            "title": note.title,
            "folder": note.folder,
        },
    }


async def search_notes(query: str) -> Dict[str, Any]:
    """Search notes by title."""
    client = _get_notes_client()
    notes = await client.search_notes(query)

    return {
        "notes": [
            {"id": n.id, "title": n.title, "folder": n.folder}
            for n in notes
        ],
        "count": len(notes),
    }


# ============================================================================
# Mail Tool Handlers
# ============================================================================

async def list_mailboxes() -> Dict[str, Any]:
    """List all mailboxes."""
    client = _get_mail_client()
    async with client:
        mailboxes = await client.list_mailboxes()

    return {
        "mailboxes": [
            {"id": m.id, "name": m.name, "unreadCount": m.unread_count}
            for m in mailboxes
        ],
        "count": len(mailboxes),
    }


async def search_emails(
    query: str,
    limit: int = 50,
    mailbox: Optional[str] = None,
) -> Dict[str, Any]:
    """Search emails."""
    client = _get_mail_client()
    async with client:
        emails = await client.search_emails(query, limit=limit, mailbox=mailbox)

    return {
        "emails": [
            {
                "messageId": e.message_id,
                "subject": e.subject,
                "sender": e.sender,
                "senderEmail": e.sender_email,
                "date": e.date.isoformat() if e.date else None,
                "snippet": e.snippet,
                "isRead": e.is_read,
                "isFlagged": e.is_flagged,
            }
            for e in emails
        ],
        "count": len(emails),
    }


async def get_recent_emails(
    hours: int = 24,
    limit: int = 100,
    unread_only: bool = False,
) -> Dict[str, Any]:
    """Get recent emails."""
    client = _get_mail_client()
    async with client:
        emails = await client.get_recent_emails(
            hours=hours,
            limit=limit,
            unread_only=unread_only,
        )

    return {
        "emails": [
            {
                "messageId": e.message_id,
                "subject": e.subject,
                "sender": e.sender,
                "senderEmail": e.sender_email,
                "date": e.date.isoformat() if e.date else None,
                "snippet": e.snippet,
                "isRead": e.is_read,
            }
            for e in emails
        ],
        "count": len(emails),
    }


async def get_unread_count(mailbox: Optional[str] = None) -> Dict[str, Any]:
    """Get unread email count."""
    client = _get_mail_client()
    async with client:
        count = await client.get_unread_count(mailbox=mailbox)

    return {"unreadCount": count, "mailbox": mailbox or "all"}


async def get_flagged_emails(limit: int = 50) -> Dict[str, Any]:
    """Get flagged emails."""
    client = _get_mail_client()
    async with client:
        emails = await client.get_flagged_emails(limit=limit)

    return {
        "emails": [
            {
                "messageId": e.message_id,
                "subject": e.subject,
                "sender": e.sender,
                "date": e.date.isoformat() if e.date else None,
            }
            for e in emails
        ],
        "count": len(emails),
    }


# ============================================================================
# Tool Definitions
# ============================================================================

def get_calendar_tools() -> List[Tool]:
    """Get Calendar tool definitions."""
    return [
        Tool(
            name="list_calendars",
            description="List all available calendars",
            parameters={},
            handler=list_calendars,
            category="calendar",
        ),
        Tool(
            name="list_events",
            description="List calendar events. Shows upcoming events by default, or filter by date range and calendar.",
            parameters={
                "calendar": ToolParam(
                    type=ToolParamType.STRING,
                    description="Filter by calendar name",
                ),
                "after": ToolParam(
                    type=ToolParamType.STRING,
                    description="Show events after this date (ISO format)",
                ),
                "before": ToolParam(
                    type=ToolParamType.STRING,
                    description="Show events before this date (ISO format)",
                ),
                "days": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Number of days to look ahead (default: 7)",
                    default=7,
                ),
            },
            handler=list_events,
            category="calendar",
        ),
        Tool(
            name="create_event",
            description="Create a new calendar event",
            parameters={
                "title": ToolParam(
                    type=ToolParamType.STRING,
                    description="Event title",
                    required=True,
                ),
                "start": ToolParam(
                    type=ToolParamType.STRING,
                    description="Start datetime (ISO format)",
                    required=True,
                ),
                "end": ToolParam(
                    type=ToolParamType.STRING,
                    description="End datetime (ISO format)",
                    required=True,
                ),
                "calendar": ToolParam(
                    type=ToolParamType.STRING,
                    description="Calendar name (uses default if not specified)",
                ),
                "location": ToolParam(
                    type=ToolParamType.STRING,
                    description="Event location",
                ),
                "notes": ToolParam(
                    type=ToolParamType.STRING,
                    description="Event notes",
                ),
                "all_day": ToolParam(
                    type=ToolParamType.BOOLEAN,
                    description="Whether this is an all-day event",
                    default=False,
                ),
            },
            handler=create_event,
            requires_approval=True,  # Creating events requires approval
            category="calendar",
        ),
        Tool(
            name="get_today_events",
            description="Get all calendar events scheduled for today",
            parameters={},
            handler=get_today_events,
            category="calendar",
        ),
    ]


def get_reminders_tools() -> List[Tool]:
    """Get Reminders tool definitions."""
    return [
        Tool(
            name="list_reminder_lists",
            description="List all reminder lists",
            parameters={},
            handler=list_reminder_lists,
            category="reminders",
        ),
        Tool(
            name="list_reminders",
            description="List reminders, optionally filtered by list and completion status",
            parameters={
                "list_name": ToolParam(
                    type=ToolParamType.STRING,
                    description="Filter by list name",
                ),
                "completed": ToolParam(
                    type=ToolParamType.BOOLEAN,
                    description="Show completed reminders",
                    default=False,
                ),
                "incomplete": ToolParam(
                    type=ToolParamType.BOOLEAN,
                    description="Show incomplete reminders",
                    default=True,
                ),
                "limit": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Maximum number of reminders to return",
                ),
            },
            handler=list_reminders,
            category="reminders",
        ),
        Tool(
            name="create_reminder",
            description="Create a new reminder",
            parameters={
                "title": ToolParam(
                    type=ToolParamType.STRING,
                    description="Reminder title",
                    required=True,
                ),
                "list_name": ToolParam(
                    type=ToolParamType.STRING,
                    description="List name (uses default if not specified)",
                ),
                "due": ToolParam(
                    type=ToolParamType.STRING,
                    description="Due datetime (ISO format)",
                ),
                "priority": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Priority (0=none, 1-4=high, 5=medium, 6-9=low)",
                    default=0,
                ),
                "notes": ToolParam(
                    type=ToolParamType.STRING,
                    description="Additional notes",
                ),
            },
            handler=create_reminder,
            requires_approval=True,  # Creating reminders requires approval
            category="reminders",
        ),
        Tool(
            name="complete_reminder",
            description="Mark a reminder as complete",
            parameters={
                "reminder_id": ToolParam(
                    type=ToolParamType.STRING,
                    description="ID of the reminder to complete",
                    required=True,
                ),
            },
            handler=complete_reminder,
            requires_approval=True,  # Completing reminders requires approval
            category="reminders",
        ),
        Tool(
            name="get_due_reminders",
            description="Get all reminders due today",
            parameters={},
            handler=get_due_reminders,
            category="reminders",
        ),
        Tool(
            name="get_overdue_reminders",
            description="Get all overdue (past due date) reminders",
            parameters={},
            handler=get_overdue_reminders,
            category="reminders",
        ),
    ]


def get_notes_tools() -> List[Tool]:
    """Get Notes tool definitions."""
    return [
        Tool(
            name="list_note_folders",
            description="List all note folders",
            parameters={},
            handler=list_note_folders,
            category="notes",
        ),
        Tool(
            name="list_notes",
            description="List notes, optionally filtered by folder",
            parameters={
                "folder": ToolParam(
                    type=ToolParamType.STRING,
                    description="Filter by folder name",
                ),
            },
            handler=list_notes,
            category="notes",
        ),
        Tool(
            name="get_note",
            description="Get the content of a specific note",
            parameters={
                "note_id": ToolParam(
                    type=ToolParamType.STRING,
                    description="ID of the note to retrieve",
                    required=True,
                ),
            },
            handler=get_note,
            category="notes",
        ),
        Tool(
            name="create_note",
            description="Create a new note",
            parameters={
                "title": ToolParam(
                    type=ToolParamType.STRING,
                    description="Note title",
                    required=True,
                ),
                "body": ToolParam(
                    type=ToolParamType.STRING,
                    description="Note content",
                ),
                "folder": ToolParam(
                    type=ToolParamType.STRING,
                    description="Folder name (uses default if not specified)",
                ),
            },
            handler=create_note,
            requires_approval=True,  # Creating notes requires approval
            category="notes",
        ),
        Tool(
            name="search_notes",
            description="Search notes by title",
            parameters={
                "query": ToolParam(
                    type=ToolParamType.STRING,
                    description="Search query",
                    required=True,
                ),
            },
            handler=search_notes,
            category="notes",
        ),
    ]


def get_mail_tools() -> List[Tool]:
    """Get Mail tool definitions (read-only)."""
    return [
        Tool(
            name="list_mailboxes",
            description="List all email mailboxes",
            parameters={},
            handler=list_mailboxes,
            category="mail",
        ),
        Tool(
            name="search_emails",
            description="Search emails by subject or sender",
            parameters={
                "query": ToolParam(
                    type=ToolParamType.STRING,
                    description="Search query",
                    required=True,
                ),
                "limit": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Maximum results (default: 50)",
                    default=50,
                ),
                "mailbox": ToolParam(
                    type=ToolParamType.STRING,
                    description="Filter by mailbox name",
                ),
            },
            handler=search_emails,
            category="mail",
        ),
        Tool(
            name="get_recent_emails",
            description="Get recent emails",
            parameters={
                "hours": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="How many hours back to look (default: 24)",
                    default=24,
                ),
                "limit": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Maximum results (default: 100)",
                    default=100,
                ),
                "unread_only": ToolParam(
                    type=ToolParamType.BOOLEAN,
                    description="Only return unread emails",
                    default=False,
                ),
            },
            handler=get_recent_emails,
            category="mail",
        ),
        Tool(
            name="get_unread_count",
            description="Get count of unread emails",
            parameters={
                "mailbox": ToolParam(
                    type=ToolParamType.STRING,
                    description="Filter by mailbox name (all mailboxes if not specified)",
                ),
            },
            handler=get_unread_count,
            category="mail",
        ),
        Tool(
            name="get_flagged_emails",
            description="Get flagged/starred emails",
            parameters={
                "limit": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Maximum results (default: 50)",
                    default=50,
                ),
            },
            handler=get_flagged_emails,
            category="mail",
        ),
    ]


def get_all_apple_tools() -> List[Tool]:
    """Get all Apple ecosystem tools."""
    return (
        get_calendar_tools()
        + get_reminders_tools()
        + get_notes_tools()
        + get_mail_tools()
    )


def register_apple_tools(registry: ToolRegistry) -> int:
    """
    Register all Apple ecosystem tools with a registry.

    Args:
        registry: ToolRegistry to register tools with

    Returns:
        Number of tools registered
    """
    tools = get_all_apple_tools()
    for tool in tools:
        registry.register(tool)
    return len(tools)
