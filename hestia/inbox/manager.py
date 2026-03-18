"""
Inbox manager -- aggregation engine for the unified inbox.

Materializes items from Apple clients (Mail, Reminders, Calendar) into a
SQLite cache with 30-second TTL. Read/archive state is per-user for
multi-device continuity.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .database import InboxDatabase, get_inbox_database
from .models import (
    InboxItem,
    InboxItemPriority,
    InboxItemSource,
    InboxItemType,
)

logger = get_logger()

CACHE_TTL_SECONDS = 30

_instance: Optional["InboxManager"] = None


class InboxManager:
    """
    Aggregates inbox items from Apple Mail, Reminders, and Calendar.

    Serves from materialized cache, refreshes when stale (30s TTL).
    Each aggregator is wrapped in try/except so one failure doesn't
    block the others.
    """

    def __init__(self, database: Optional[InboxDatabase] = None):
        self._database = database
        self._last_refresh: float = 0.0
        # Lazy-initialized Apple clients
        self._mail_client = None
        self._reminders_client = None
        self._calendar_client = None

    async def initialize(self) -> None:
        """Initialize database and run initial cleanup."""
        if self._database is None:
            self._database = await get_inbox_database()

        # Clean up old items on startup
        deleted = await self._database.cleanup_old_items(retention_days=30)
        if deleted > 0:
            logger.info(
                f"Cleaned up {deleted} old inbox items",
                component=LogComponent.INBOX,
            )

        logger.info(
            "Inbox manager initialized",
            component=LogComponent.INBOX,
        )

    async def close(self) -> None:
        """Close manager resources."""
        # Close Apple clients if initialized
        if self._mail_client is not None:
            try:
                await self._mail_client.close()
            except Exception:
                pass
        logger.debug(
            "Inbox manager closed",
            component=LogComponent.INBOX,
        )

    # -- Apple Client Lazy Init -------------------------------------------

    def _get_mail_client(self):
        """Lazy-initialize MailClient."""
        if self._mail_client is None:
            from hestia.apple.mail import MailClient
            self._mail_client = MailClient()
        return self._mail_client

    def _get_reminders_client(self):
        """Lazy-initialize RemindersClient."""
        if self._reminders_client is None:
            from hestia.apple.reminders import RemindersClient
            self._reminders_client = RemindersClient()
        return self._reminders_client

    def _get_calendar_client(self):
        """Lazy-initialize CalendarClient."""
        if self._calendar_client is None:
            from hestia.apple.calendar import CalendarClient
            self._calendar_client = CalendarClient()
        return self._calendar_client

    def _get_notes_client(self):
        """Lazy-initialize NotesClient."""
        if not hasattr(self, "_notes_client") or self._notes_client is None:
            from hestia.apple.notes import NotesClient
            self._notes_client = NotesClient()
        return self._notes_client

    # -- Public API -------------------------------------------------------

    async def get_inbox(
        self,
        user_id: str,
        source: Optional[InboxItemSource] = None,
        item_type: Optional[InboxItemType] = None,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[InboxItem]:
        """
        Get inbox items, refreshing cache if stale.

        Args:
            user_id: User ID for read/archive state.
            source: Filter by source.
            item_type: Filter by item type.
            include_archived: Include archived items.
            limit: Max items to return.
            offset: Pagination offset.
        """
        if self._is_cache_stale():
            await self._aggregate_all()

        return await self._database.get_items(
            user_id=user_id,
            source=source,
            item_type=item_type,
            include_archived=include_archived,
            limit=limit,
            offset=offset,
        )

    async def get_item(
        self, item_id: str, user_id: str
    ) -> Optional[InboxItem]:
        """
        Get a single inbox item with user state.

        For email items, lazy-loads the full body via MailClient.get_email().
        """
        item = await self._database.get_item(item_id, user_id)
        if item is None:
            return None

        # Lazy-load full email body for mail items
        if (
            item.source == InboxItemSource.MAIL
            and item.body is None
            and item.id.startswith("mail:")
        ):
            native_id = item.id[len("mail:"):]
            try:
                mail_client = self._get_mail_client()
                email = await mail_client.get_email(native_id)
                if email and email.body:
                    item.body = email.body
                elif email and email.snippet:
                    item.body = email.snippet
            except Exception as e:
                logger.warning(
                    f"Failed to load email body: {type(e).__name__}",
                    component=LogComponent.INBOX,
                )

        return item

    async def mark_read(
        self, item_id: str, user_id: str, device_id: Optional[str] = None
    ) -> bool:
        """Mark an item as read."""
        return await self._database.mark_read(item_id, user_id)

    async def mark_all_read(
        self,
        user_id: str,
        source: Optional[InboxItemSource] = None,
        device_id: Optional[str] = None,
    ) -> int:
        """Mark all items as read. Returns count of items marked."""
        source_enum = None
        if source is not None:
            source_enum = source
        return await self._database.mark_all_read(user_id, source=source_enum)

    async def archive(
        self, item_id: str, user_id: str, device_id: Optional[str] = None
    ) -> bool:
        """Archive an item."""
        return await self._database.archive(item_id, user_id)

    async def get_unread_count(
        self, user_id: str, source: Optional[InboxItemSource] = None
    ) -> int:
        """Get unread count for a user."""
        return await self._database.get_unread_count(user_id, source=source)

    async def get_unread_by_source(self, user_id: str) -> Dict[str, int]:
        """Get unread counts broken down by source."""
        return await self._database.get_unread_by_source(user_id)

    async def refresh(self) -> int:
        """Force re-aggregate from all sources. Returns item count."""
        return await self._aggregate_all()

    # -- Internal ---------------------------------------------------------

    def _is_cache_stale(self) -> bool:
        """Check if cache needs refresh."""
        return (time.time() - self._last_refresh) > CACHE_TTL_SECONDS

    async def _aggregate_all(self) -> int:
        """
        Aggregate items from all Apple clients.

        Each aggregator is independent -- one failure doesn't block others.
        Returns total number of items cached.
        """
        results = await asyncio.gather(
            self._aggregate_mail(),
            self._aggregate_reminders(),
            self._aggregate_calendar(),
            self._aggregate_notes(),
            return_exceptions=True,
        )

        all_items: List[InboxItem] = []
        source_names = ["mail", "reminders", "calendar", "notes"]
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(
                    f"Inbox aggregation failed for {source_names[i]}: {type(result).__name__}",
                    component=LogComponent.INBOX,
                )
                continue
            all_items.extend(result)

        count = await self._database.upsert_items(all_items)
        self._last_refresh = time.time()

        logger.debug(
            f"Inbox refreshed: {count} items from {len(all_items)} aggregated",
            component=LogComponent.INBOX,
        )

        return count

    async def _aggregate_mail(self) -> List[InboxItem]:
        """Aggregate recent emails from Apple Mail."""
        mail_client = self._get_mail_client()
        emails = await mail_client.get_recent_emails(hours=48, limit=200)

        items = []
        for email in emails:
            items.append(InboxItem(
                id=f"mail:{email.message_id}",
                item_type=InboxItemType.EMAIL,
                source=InboxItemSource.MAIL,
                title=email.subject,
                body=email.snippet,
                timestamp=email.date,
                priority=InboxItemPriority.HIGH if email.is_flagged else InboxItemPriority.NORMAL,
                sender=email.sender,
                sender_detail=email.sender_email,
                has_attachments=email.has_attachments,
                icon="envelope.fill",
                color="#E0A050",
                metadata={
                    "mailbox": email.mailbox or "",
                    "is_flagged": email.is_flagged,
                    "is_read": email.is_read,
                },
            ))
        return items

    async def _aggregate_reminders(self) -> List[InboxItem]:
        """Aggregate incomplete reminders."""
        reminders_client = self._get_reminders_client()
        reminders = await reminders_client.get_incomplete()

        items = []
        for reminder in reminders:
            # Map Apple priority (1-4=HIGH, 5=NORMAL, 6-9=LOW, 0=NORMAL)
            if 1 <= reminder.priority <= 4:
                priority = InboxItemPriority.HIGH
            elif 6 <= reminder.priority <= 9:
                priority = InboxItemPriority.LOW
            else:
                priority = InboxItemPriority.NORMAL

            # Color based on priority
            if priority == InboxItemPriority.HIGH:
                color = "#FF3B30"
            elif priority == InboxItemPriority.LOW:
                color = "#8E8E93"
            else:
                color = "#FF9500"

            items.append(InboxItem(
                id=f"reminders:{reminder.id}",
                item_type=InboxItemType.REMINDER,
                source=InboxItemSource.REMINDERS,
                title=reminder.title,
                body=reminder.notes,
                timestamp=reminder.due,
                priority=priority,
                sender=None,
                sender_detail=None,
                has_attachments=False,
                icon="checklist",
                color=color,
                metadata={
                    "list_name": reminder.list_name,
                    "due": reminder.due.isoformat() if reminder.due else None,
                },
            ))
        return items

    async def _aggregate_calendar(self) -> List[InboxItem]:
        """Aggregate upcoming calendar events (next 7 days)."""
        calendar_client = self._get_calendar_client()
        events = await calendar_client.get_upcoming_events(days=7)

        items = []
        for event in events:
            items.append(InboxItem(
                id=f"calendar:{event.id}",
                item_type=InboxItemType.CALENDAR,
                source=InboxItemSource.CALENDAR,
                title=event.title,
                body=event.notes,
                timestamp=event.start,
                priority=InboxItemPriority.NORMAL,
                sender=None,
                sender_detail=None,
                has_attachments=False,
                icon="calendar",
                color="#007AFF",
                metadata={
                    "calendar": event.calendar,
                    "location": event.location,
                    "is_all_day": event.is_all_day,
                    "start": event.start.isoformat() if event.start else None,
                    "end": event.end.isoformat() if event.end else None,
                },
            ))
        return items

    async def _aggregate_notes(self) -> List[InboxItem]:
        """Aggregate recent notes (modified in last 30 days)."""
        notes_client = self._get_notes_client()
        notes = await notes_client.list_notes()

        items = []
        for note in notes:
            # Skip empty/stub notes
            if not note.title or len(note.title.strip()) < 3:
                continue
            items.append(InboxItem(
                id=f"notes:{note.id}",
                item_type=InboxItemType.NOTE,
                source=InboxItemSource.NOTES,
                title=note.title,
                body=note.body[:200] if note.body else None,
                timestamp=datetime.fromisoformat(note.modified_at.replace("Z", "+00:00")) if note.modified_at else None,
                priority=InboxItemPriority.NORMAL,
                sender=None,
                sender_detail=None,
                has_attachments=False,
                icon="note.text",
                color="#FFD60A",
                metadata={
                    "folder": note.folder,
                    "created_at": note.created_at,
                    "modified_at": note.modified_at,
                },
            ))
        return items


async def get_inbox_manager() -> InboxManager:
    """Singleton factory for InboxManager."""
    global _instance
    if _instance is None:
        _instance = InboxManager()
        await _instance.initialize()
    return _instance


async def close_inbox_manager() -> None:
    """Close the singleton inbox manager."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
