"""
Apple ecosystem integration for Hestia.

Provides access to Calendar, Reminders, Notes, and Mail via
Swift CLI tools (EventKit/AppleScript) and SQLite.
"""

from .models import (
    Calendar,
    Email,
    Event,
    Mailbox,
    Note,
    NoteFolder,
    Reminder,
    ReminderList,
    ReminderPriority,
)
from .calendar import CalendarClient, CalendarError
from .reminders import RemindersClient, RemindersError
from .notes import NotesClient, NotesError
from .mail import MailClient, MailError
from .tools import (
    get_all_apple_tools,
    get_calendar_tools,
    get_mail_tools,
    get_notes_tools,
    get_reminders_tools,
    register_apple_tools,
)

__all__ = [
    # Models
    "Calendar",
    "Event",
    "ReminderList",
    "Reminder",
    "ReminderPriority",
    "NoteFolder",
    "Note",
    "Mailbox",
    "Email",
    # Clients
    "CalendarClient",
    "RemindersClient",
    "NotesClient",
    "MailClient",
    # Errors
    "CalendarError",
    "RemindersError",
    "NotesError",
    "MailError",
    # Tool registration
    "get_all_apple_tools",
    "get_calendar_tools",
    "get_reminders_tools",
    "get_notes_tools",
    "get_mail_tools",
    "register_apple_tools",
]
