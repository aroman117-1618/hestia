"""
Inbox module — unified inbox aggregating mail, reminders, and calendar.

Wraps existing Apple clients (MailClient, RemindersClient, CalendarClient)
into a single timeline with per-user read/archive state and caching.
"""

from .models import InboxItem, InboxItemType, InboxItemSource, InboxItemPriority

__all__ = [
    "InboxItem",
    "InboxItemType",
    "InboxItemSource",
    "InboxItemPriority",
]
