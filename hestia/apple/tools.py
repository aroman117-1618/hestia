"""
Apple ecosystem tools for registration with execution layer.

Provides Tool definitions for Calendar, Reminders, Notes, and Mail.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..execution.models import Tool, ToolParam, ToolParamType
from ..execution.registry import ToolRegistry
from ..logging import get_logger, LogComponent
from .calendar import CalendarClient
from .reminders import RemindersClient
from .notes import NotesClient
from .mail import MailClient


logger = get_logger()

# Singleton clients (initialized lazily)
_calendar_client: Optional[CalendarClient] = None
_reminders_client: Optional[RemindersClient] = None
_notes_client: Optional[NotesClient] = None
_mail_client: Optional[MailClient] = None
_cache_manager = None  # AppleCacheManager, lazy-imported to avoid circular


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


async def _get_cache_manager():
    """Lazy-initialize AppleCacheManager (async singleton)."""
    global _cache_manager
    if _cache_manager is None:
        from ..apple_cache.manager import get_apple_cache_manager
        _cache_manager = await get_apple_cache_manager()
    return _cache_manager


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

    # Write-through to cache
    try:
        from ..apple_cache.models import EntitySource
        cache = await _get_cache_manager()
        await cache.on_entity_created(
            source=EntitySource.CALENDAR,
            native_id=event.id,
            title=event.title,
            container=event.calendar,
        )
    except Exception:
        pass  # Cache is best-effort

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


async def find_event(query: str, days: int = 30) -> Dict[str, Any]:
    """Find calendar events by fuzzy title match using the metadata cache."""
    from ..apple_cache.models import EntitySource

    cache = await _get_cache_manager()
    matches = await cache.resolve(query, source=EntitySource.CALENDAR, limit=5)

    if not matches:
        return {"events": [], "count": 0, "query": query}

    return {
        "events": [
            {
                "id": m.entity.native_id,
                "title": m.entity.title,
                "calendar": m.entity.container,
                "score": round(m.score, 1),
                "start": m.entity.metadata.get("start"),
                "end": m.entity.metadata.get("end"),
                "location": m.entity.metadata.get("location"),
            }
            for m in matches
        ],
        "count": len(matches),
        "query": query,
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

    # Fuzzy-resolve list name via cache if provided
    resolved_list = list_name
    if list_name:
        try:
            from ..apple_cache.models import EntitySource
            cache = await _get_cache_manager()
            exact = await cache.resolve_container(list_name, EntitySource.REMINDERS)
            if exact:
                resolved_list = exact
        except Exception:
            pass  # Fall through to original list_name

    reminders = await client.list_reminders(
        list_name=resolved_list,
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

    # Write-through to cache
    try:
        from ..apple_cache.models import EntitySource
        cache = await _get_cache_manager()
        await cache.on_entity_created(
            source=EntitySource.REMINDERS,
            native_id=reminder.id,
            title=reminder.title,
            container=reminder.list_name,
        )
    except Exception:
        pass

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
    """Get note content by ID or title (auto-resolves fuzzy titles via cache)."""
    client = _get_notes_client()

    # Heuristic: Apple Note IDs look like "x-coredata://..." or long hex strings.
    # If the input doesn't look like an ID, try fuzzy resolution first.
    if not _looks_like_note_id(note_id):
        try:
            from ..apple_cache.models import EntitySource
            cache = await _get_cache_manager()
            match = await cache.resolve_best(note_id, source=EntitySource.NOTES)
            if match and match.score >= 70.0:
                note_id = match.entity.native_id
        except Exception:
            pass  # Fall through to original note_id

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


def _looks_like_note_id(value: str) -> bool:
    """Heuristic: Apple Note IDs contain 'x-coredata' or are very long hex-like strings."""
    if "x-coredata" in value:
        return True
    if len(value) > 30 and "/" in value:
        return True
    return False


async def create_note(
    title: str,
    body: Optional[str] = None,
    folder: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a note."""
    client = _get_notes_client()
    note = await client.create_note(title=title, body=body, folder=folder)

    # Write-through to cache
    try:
        from ..apple_cache.models import EntitySource
        cache = await _get_cache_manager()
        await cache.on_entity_created(
            source=EntitySource.NOTES,
            native_id=note.id,
            title=note.title,
            container=note.folder,
        )
    except Exception:
        pass

    return {
        "created": True,
        "note": {
            "id": note.id,
            "title": note.title,
            "folder": note.folder,
        },
    }


async def search_notes(query: str) -> Dict[str, Any]:
    """Search notes by title using the metadata cache (fast fuzzy search)."""
    # Try cache-based search first (instant, fuzzy)
    try:
        from ..apple_cache.models import EntitySource
        cache = await _get_cache_manager()
        matches = await cache.resolve(query, source=EntitySource.NOTES, limit=10)
        if matches:
            return {
                "notes": [
                    {
                        "id": m.entity.native_id,
                        "title": m.entity.title,
                        "folder": m.entity.container,
                        "score": round(m.score, 1),
                    }
                    for m in matches
                ],
                "count": len(matches),
            }
    except Exception:
        pass

    # Fallback to direct AppleScript search
    client = _get_notes_client()
    notes = await client.search_notes(query)

    return {
        "notes": [
            {"id": n.id, "title": n.title, "folder": n.folder}
            for n in notes
        ],
        "count": len(notes),
    }


async def find_note(query: str) -> Dict[str, Any]:
    """Find notes by fuzzy title match. Returns ranked matches from the metadata cache."""
    from ..apple_cache.models import EntitySource

    cache = await _get_cache_manager()
    matches = await cache.resolve(query, source=EntitySource.NOTES, limit=5)

    if not matches:
        return {"notes": [], "count": 0, "query": query}

    return {
        "notes": [
            {
                "id": m.entity.native_id,
                "title": m.entity.title,
                "folder": m.entity.container,
                "score": round(m.score, 1),
            }
            for m in matches
        ],
        "count": len(matches),
        "query": query,
    }


async def read_note(query: str) -> Dict[str, Any]:
    """
    Find a note by fuzzy title and return its full content in one step.

    This is the primary tool for reading notes — it resolves a natural-language
    reference to the best-matching note and fetches its content, all in a single
    tool call. No need to list notes first, then get by ID.
    """
    from ..apple_cache.models import EntitySource

    cache = await _get_cache_manager()
    match = await cache.resolve_best(query, source=EntitySource.NOTES, min_score=60.0)

    if not match:
        return {
            "error": f"No note found matching '{query}'",
            "suggestion": "Try a different search term or use list_notes to browse all notes.",
        }

    # Fetch full content using the resolved ID
    client = _get_notes_client()
    note = await client.get_note(match.entity.native_id)

    return {
        "note": {
            "id": note.id,
            "title": note.title,
            "folder": note.folder,
            "body": note.body,
            "createdAt": note.created_at,
            "modifiedAt": note.modified_at,
        },
        "match_score": round(match.score, 1),
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
            name="find_event",
            description="Find calendar events by fuzzy title match. Use when user asks about a specific event by name (e.g., 'when is my dentist appointment'). Returns ranked matches.",
            parameters={
                "query": ToolParam(
                    type=ToolParamType.STRING,
                    description="Event title to search for (fuzzy matching)",
                    required=True,
                ),
                "days": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Number of days to search (default: 30)",
                    default=30,
                ),
            },
            handler=find_event,
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
        # get_note removed from LLM tool list — read_note supersedes it.
        # get_note is still available internally (e.g., for direct ID lookups).
        Tool(
            name="read_note",
            description="Read a note by name — the PRIMARY tool for reading notes. Finds the best-matching note by fuzzy title search and returns its full content in one step. Always use this when the user asks to read, show, open, or see a specific note.",
            parameters={
                "query": ToolParam(
                    type=ToolParamType.STRING,
                    description="Note title or topic to search for (fuzzy matching)",
                    required=True,
                ),
            },
            handler=read_note,
            category="notes",
        ),
        Tool(
            name="find_note",
            description="Find notes by fuzzy title match. Returns ranked matches without content. Use when user wants to find or list notes matching a topic.",
            parameters={
                "query": ToolParam(
                    type=ToolParamType.STRING,
                    description="Note title to search for (fuzzy matching)",
                    required=True,
                ),
            },
            handler=find_note,
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
            description="Search notes by title using fuzzy matching. Alias for find_note.",
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
