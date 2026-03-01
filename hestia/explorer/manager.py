"""
Explorer manager — aggregates resources from Apple ecosystem sources.

Uses the existing Apple CLI clients (calendar, reminders, notes, mail) to
fetch resources, converts them to the unified ExplorerResource format,
and serves them through a TTL cache for fast responses.
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .database import ExplorerDatabase, get_explorer_database
from .models import (
    ExplorerResource,
    ResourceFlag,
    ResourceSource,
    ResourceType,
)

logger = get_logger()

_instance: Optional["ExplorerManager"] = None


class ExplorerManager:
    """
    Aggregates resources from mail, notes, reminders, files, and Hestia drafts.

    Serves cached data immediately, triggers background refresh when stale.
    """

    def __init__(self, database: Optional[ExplorerDatabase] = None):
        self._database = database
        self._mail_client = None
        self._notes_client = None
        self._reminders_client = None
        self._calendar_client = None

    async def initialize(self) -> None:
        """Lazy-initialize database and Apple clients."""
        if self._database is None:
            self._database = await get_explorer_database()

        # Import Apple clients lazily to avoid circular imports
        try:
            from hestia.apple.mail import MailClient
            self._mail_client = MailClient()
        except Exception:
            logger.warning("Mail client unavailable")

        try:
            from hestia.apple.notes import NotesClient
            self._notes_client = NotesClient()
        except Exception:
            logger.warning("Notes client unavailable")

        try:
            from hestia.apple.reminders import RemindersClient
            self._reminders_client = RemindersClient()
        except Exception:
            logger.warning("Reminders client unavailable")

        try:
            from hestia.apple.calendar import CalendarClient
            self._calendar_client = CalendarClient()
        except Exception:
            logger.warning("Calendar client unavailable")

        logger.info("Explorer manager initialized")

    # ── Public API ──────────────────────────────────────────

    async def get_resources(
        self,
        resource_type: Optional[ResourceType] = None,
        source: Optional[ResourceSource] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ExplorerResource]:
        """
        Get aggregated resources, optionally filtered.

        Serves from cache when available, fetches fresh data in background.
        """
        all_resources: List[ExplorerResource] = []

        # Determine which sources to query
        sources_to_query = self._resolve_sources(resource_type, source)

        # Fetch from each source (cache-first, parallel)
        tasks = []
        for src in sources_to_query:
            tasks.append(self._get_source_resources(src))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Source fetch failed: {type(result).__name__}")
                continue
            all_resources.extend(result)

        # Apply filters
        if resource_type:
            all_resources = [r for r in all_resources if r.type == resource_type]

        if search:
            query = search.lower()
            all_resources = [
                r for r in all_resources
                if query in r.title.lower()
                or (r.preview and query in r.preview.lower())
            ]

        # Sort by modification time (most recent first), then creation time
        all_resources.sort(
            key=lambda r: (r.modified_at or r.created_at or datetime.min),
            reverse=True,
        )

        # Paginate
        return all_resources[offset:offset + limit]

    async def get_resource(self, resource_id: str) -> Optional[ExplorerResource]:
        """Get a single resource by ID."""
        # Check drafts first
        if resource_id.startswith("drafts:"):
            return await self._database.get_draft(resource_id)

        # Search across cached resources
        all_resources = await self.get_resources(limit=500)
        for resource in all_resources:
            if resource.id == resource_id:
                return resource
        return None

    async def get_resource_content(self, resource_id: str) -> Optional[str]:
        """Get full content for a resource (not just preview)."""
        parts = resource_id.split(":", 1)
        if len(parts) != 2:
            return None

        source_prefix, native_id = parts

        if source_prefix == "drafts":
            draft = await self._database.get_draft(resource_id)
            return draft.metadata.get("body") if draft else None

        if source_prefix == "mail" and self._mail_client:
            try:
                email = await self._mail_client.get_email(native_id)
                return email.body if email else None
            except Exception:
                return None

        if source_prefix == "notes" and self._notes_client:
            try:
                note = await self._notes_client.get_note(native_id)
                return note.body if note else None
            except Exception:
                return None

        if source_prefix == "reminders" and self._reminders_client:
            try:
                reminder = await self._reminders_client.get_reminder(native_id)
                return reminder.notes if reminder else None
            except Exception:
                return None

        return None

    # ── Draft CRUD ──────────────────────────────────────────

    async def create_draft(
        self,
        title: str,
        body: Optional[str] = None,
        color: Optional[str] = None,
        flags: Optional[List[ResourceFlag]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> ExplorerResource:
        """Create a new Hestia draft."""
        return await self._database.create_draft(
            title=title, body=body, color=color, flags=flags, metadata=metadata,
        )

    async def update_draft(
        self,
        draft_id: str,
        title: Optional[str] = None,
        body: Optional[str] = None,
        color: Optional[str] = None,
        flags: Optional[List[ResourceFlag]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> Optional[ExplorerResource]:
        """Update an existing draft."""
        return await self._database.update_draft(
            draft_id=draft_id,
            title=title,
            body=body,
            color=color,
            flags=flags,
            metadata=metadata,
        )

    async def delete_draft(self, draft_id: str) -> bool:
        """Delete a draft."""
        return await self._database.delete_draft(draft_id)

    # ── Cache Management ────────────────────────────────────

    async def refresh_source(self, source: ResourceSource) -> List[ExplorerResource]:
        """Force-refresh a specific source (bypasses cache)."""
        resources = await self._fetch_fresh(source)
        await self._database.set_cached_resources(source, resources)
        return resources

    async def clear_cache(self, source: Optional[ResourceSource] = None) -> None:
        """Clear the resource cache."""
        await self._database.clear_cache(source)

    # ── Internal ────────────────────────────────────────────

    def _resolve_sources(
        self,
        resource_type: Optional[ResourceType],
        source: Optional[ResourceSource],
    ) -> List[ResourceSource]:
        """Determine which sources to query based on filters."""
        if source:
            return [source]

        # Map resource types to sources
        type_source_map = {
            ResourceType.DRAFT: [ResourceSource.HESTIA],
            ResourceType.MAIL: [ResourceSource.MAIL],
            ResourceType.TASK: [ResourceSource.REMINDERS],
            ResourceType.NOTE: [ResourceSource.NOTES],
            ResourceType.FILE: [ResourceSource.FILES],
        }

        if resource_type:
            return type_source_map.get(resource_type, [])

        # All sources
        return [
            ResourceSource.HESTIA,
            ResourceSource.MAIL,
            ResourceSource.NOTES,
            ResourceSource.REMINDERS,
        ]

    async def _get_source_resources(
        self, source: ResourceSource
    ) -> List[ExplorerResource]:
        """Get resources for a source, using cache when available."""
        if source == ResourceSource.HESTIA:
            return await self._database.list_drafts()

        # Try cache first
        cached = await self._database.get_cached_resources(source)
        if cached is not None:
            return cached

        # Cache miss — fetch fresh
        resources = await self._fetch_fresh(source)
        await self._database.set_cached_resources(source, resources)
        return resources

    async def _fetch_fresh(self, source: ResourceSource) -> List[ExplorerResource]:
        """Fetch fresh resources from an external source."""
        try:
            if source == ResourceSource.MAIL:
                return await self._fetch_mail()
            elif source == ResourceSource.NOTES:
                return await self._fetch_notes()
            elif source == ResourceSource.REMINDERS:
                return await self._fetch_reminders()
            elif source == ResourceSource.FILES:
                return []  # File browsing deferred to macOS local explorer
            else:
                return []
        except Exception as e:
            logger.warning(f"Failed to fetch {source.value}: {type(e).__name__}")
            return []

    async def _fetch_mail(self) -> List[ExplorerResource]:
        """Fetch recent emails as ExplorerResources."""
        if not self._mail_client:
            return []

        emails = await self._mail_client.get_recent_emails(hours=48, limit=50)
        resources = []
        for email in emails:
            flags = []
            if not email.is_read:
                flags.append(ResourceFlag.UNREAD)
            if email.is_flagged:
                flags.append(ResourceFlag.FLAGGED)

            resources.append(ExplorerResource(
                id=f"mail:{email.message_id}",
                type=ResourceType.MAIL,
                title=email.subject or "(No Subject)",
                source=ResourceSource.MAIL,
                created_at=email.date,
                modified_at=email.date,
                preview=email.snippet[:200] if email.snippet else None,
                flags=flags,
                metadata={
                    "sender": email.sender,
                    "sender_email": email.sender_email,
                    "mailbox": email.mailbox or "",
                },
            ))
        return resources

    async def _fetch_notes(self) -> List[ExplorerResource]:
        """Fetch notes as ExplorerResources."""
        if not self._notes_client:
            return []

        notes = await self._notes_client.list_notes()
        resources = []
        for note in notes:
            created_at = None
            modified_at = None
            if note.created_at:
                try:
                    created_at = datetime.fromisoformat(note.created_at)
                except (ValueError, TypeError):
                    pass
            if note.modified_at:
                try:
                    modified_at = datetime.fromisoformat(note.modified_at)
                except (ValueError, TypeError):
                    pass

            resources.append(ExplorerResource(
                id=f"notes:{note.id}",
                type=ResourceType.NOTE,
                title=note.title,
                source=ResourceSource.NOTES,
                created_at=created_at,
                modified_at=modified_at,
                preview=note.body[:200] if note.body else None,
                metadata={"folder": note.folder},
            ))
        return resources

    async def _fetch_reminders(self) -> List[ExplorerResource]:
        """Fetch incomplete reminders as ExplorerResources."""
        if not self._reminders_client:
            return []

        reminders = await self._reminders_client.get_incomplete()
        resources = []
        for reminder in reminders:
            flags = []
            if reminder.priority_level.value <= 4 and reminder.priority > 0:
                flags.append(ResourceFlag.URGENT)
            if reminder.due and reminder.due < datetime.now(reminder.due.tzinfo):
                flags.append(ResourceFlag.FLAGGED)

            resources.append(ExplorerResource(
                id=f"reminders:{reminder.id}",
                type=ResourceType.TASK,
                title=reminder.title,
                source=ResourceSource.REMINDERS,
                created_at=None,
                modified_at=None,
                preview=reminder.notes[:200] if reminder.notes else None,
                flags=flags,
                metadata={
                    "list": reminder.list_name,
                    "due": reminder.due.isoformat() if reminder.due else "",
                    "priority": str(reminder.priority),
                },
            ))
        return resources


async def get_explorer_manager() -> ExplorerManager:
    """Singleton factory for ExplorerManager."""
    global _instance
    if _instance is None:
        _instance = ExplorerManager()
        await _instance.initialize()
    return _instance
