"""
Apple cache manager -- sync orchestration and public API.

Syncs metadata from Apple ecosystem clients (Notes, Calendar, Reminders)
into the FTS5-backed cache. Uses TTL-based refresh (like Inbox module)
with write-through on create/update operations.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .database import AppleCacheDatabase, get_apple_cache_database
from .models import CachedEntity, EntitySource, ResolvedMatch
from .resolver import SmartResolver

logger = get_logger()

# Default TTL per source (seconds)
_TTL = {
    EntitySource.NOTES: 6 * 3600,       # 6 hours
    EntitySource.CALENDAR: 2 * 3600,     # 2 hours
    EntitySource.REMINDERS: 4 * 3600,    # 4 hours
}

_instance: Optional["AppleCacheManager"] = None


class AppleCacheManager:
    """
    Orchestrates Apple metadata caching with fuzzy resolution.

    - Lazy-syncs each source on first access (TTL-based)
    - Provides fuzzy title resolution via SmartResolver
    - Write-through hooks keep cache fresh after mutations
    """

    def __init__(self, database: Optional[AppleCacheDatabase] = None) -> None:
        self._database = database
        self._resolver: Optional[SmartResolver] = None
        self._last_sync: Dict[EntitySource, float] = {}
        # Lazy-initialized Apple clients
        self._notes_client = None
        self._calendar_client = None
        self._reminders_client = None

    async def initialize(self) -> None:
        """Initialize database and resolver."""
        if self._database is None:
            self._database = await get_apple_cache_database()

        self._resolver = SmartResolver(self._database)

        logger.info(
            "Apple cache manager initialized",
            component=LogComponent.APPLE_CACHE,
        )

    async def close(self) -> None:
        """Close manager resources."""
        logger.debug(
            "Apple cache manager closed",
            component=LogComponent.APPLE_CACHE,
        )

    # -- Apple Client Lazy Init -------------------------------------------

    def _get_notes_client(self):
        """Lazy-initialize NotesClient."""
        if self._notes_client is None:
            from hestia.apple.notes import NotesClient
            self._notes_client = NotesClient()
        return self._notes_client

    def _get_calendar_client(self):
        """Lazy-initialize CalendarClient."""
        if self._calendar_client is None:
            from hestia.apple.calendar import CalendarClient
            self._calendar_client = CalendarClient()
        return self._calendar_client

    def _get_reminders_client(self):
        """Lazy-initialize RemindersClient."""
        if self._reminders_client is None:
            from hestia.apple.reminders import RemindersClient
            self._reminders_client = RemindersClient()
        return self._reminders_client

    # -- Public API: Resolution -------------------------------------------

    async def resolve(
        self,
        query: str,
        source: Optional[EntitySource] = None,
        min_score: float = 50.0,
        limit: int = 5,
    ) -> List[ResolvedMatch]:
        """
        Fuzzy-resolve a query to cached Apple entities.

        Auto-syncs stale sources before resolving.
        """
        await self._ensure_fresh(source)
        return await self._resolver.resolve(
            query, source=source, min_score=min_score, limit=limit
        )

    async def resolve_best(
        self,
        query: str,
        source: Optional[EntitySource] = None,
        min_score: float = 50.0,
    ) -> Optional[ResolvedMatch]:
        """Resolve to the single best match."""
        await self._ensure_fresh(source)
        return await self._resolver.resolve_best(
            query, source=source, min_score=min_score
        )

    async def resolve_container(
        self,
        query: str,
        source: EntitySource,
        min_score: float = 50.0,
    ) -> Optional[str]:
        """Resolve a fuzzy container name to exact name."""
        await self._ensure_fresh(source)
        return await self._resolver.resolve_container(
            query, source=source, min_score=min_score
        )

    # -- Public API: Cache Management -------------------------------------

    async def sync_all(self) -> Dict[str, int]:
        """Force sync all sources. Returns {source: count}."""
        results = await asyncio.gather(
            self._sync_notes(),
            self._sync_calendar(),
            self._sync_reminders(),
            return_exceptions=True,
        )

        counts: Dict[str, int] = {}
        source_names = [EntitySource.NOTES, EntitySource.CALENDAR, EntitySource.REMINDERS]
        for i, result in enumerate(results):
            source = source_names[i]
            if isinstance(result, Exception):
                logger.warning(
                    f"Apple cache sync failed for {source.value}: {type(result).__name__}",
                    component=LogComponent.APPLE_CACHE,
                )
                counts[source.value] = 0
            else:
                counts[source.value] = result

        return counts

    async def sync_source(self, source: EntitySource) -> int:
        """Sync a specific source. Returns entity count."""
        sync_fn = {
            EntitySource.NOTES: self._sync_notes,
            EntitySource.CALENDAR: self._sync_calendar,
            EntitySource.REMINDERS: self._sync_reminders,
        }
        return await sync_fn[source]()

    async def get_status(self) -> Dict[str, Any]:
        """Get cache status (sync times, counts)."""
        db_status = await self._database.get_sync_status()
        total = await self._database.get_entity_count()

        return {
            "total_entities": total,
            "sources": db_status,
            "ttl_seconds": {s.value: t for s, t in _TTL.items()},
        }

    async def get_entities(
        self,
        source: Optional[EntitySource] = None,
        container: Optional[str] = None,
        limit: int = 500,
    ) -> List[CachedEntity]:
        """Get cached entities with optional filtering."""
        return await self._database.get_all(
            source=source, container=container, limit=limit
        )

    # -- Write-Through Hooks ----------------------------------------------

    async def on_entity_created(
        self, source: EntitySource, native_id: str, title: str,
        container: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write-through: called after creating an Apple entity."""
        entity = CachedEntity(
            id=f"{source.value}:{native_id}",
            source=source,
            native_id=native_id,
            title=title,
            container=container,
            modified_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            metadata=metadata or {},
        )
        await self._database.upsert_single(entity)
        logger.debug(
            f"Cache write-through: created {source.value}:{native_id}",
            component=LogComponent.APPLE_CACHE,
        )

    async def on_entity_updated(
        self, source: EntitySource, native_id: str, title: str,
        container: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write-through: called after updating an Apple entity."""
        entity_id = f"{source.value}:{native_id}"
        existing = await self._database.get_by_id(entity_id)

        entity = CachedEntity(
            id=entity_id,
            source=source,
            native_id=native_id,
            title=title,
            container=container or (existing.container if existing else None),
            modified_at=datetime.now(timezone.utc),
            created_at=existing.created_at if existing else None,
            metadata=metadata or (existing.metadata if existing else {}),
        )
        await self._database.upsert_single(entity)
        logger.debug(
            f"Cache write-through: updated {entity_id}",
            component=LogComponent.APPLE_CACHE,
        )

    async def on_entity_deleted(
        self, source: EntitySource, native_id: str
    ) -> None:
        """Write-through: called after deleting an Apple entity."""
        entity_id = f"{source.value}:{native_id}"
        await self._database.delete_entity(entity_id)
        logger.debug(
            f"Cache write-through: deleted {entity_id}",
            component=LogComponent.APPLE_CACHE,
        )

    # -- Internal: Sync Logic ---------------------------------------------

    def _is_stale(self, source: EntitySource) -> bool:
        """Check if a source needs refresh based on TTL."""
        last = self._last_sync.get(source, 0.0)
        ttl = _TTL.get(source, 3600)
        return (time.time() - last) > ttl

    async def _ensure_fresh(self, source: Optional[EntitySource] = None) -> None:
        """Sync stale sources before a resolve operation."""
        if source:
            if self._is_stale(source):
                try:
                    await self.sync_source(source)
                except Exception as e:
                    logger.warning(
                        f"Auto-sync failed for {source.value}: {type(e).__name__}",
                        component=LogComponent.APPLE_CACHE,
                    )
        else:
            # Sync all stale sources in parallel
            tasks = []
            for s in EntitySource:
                if self._is_stale(s):
                    tasks.append(self._safe_sync(s))
            if tasks:
                await asyncio.gather(*tasks)

    async def _safe_sync(self, source: EntitySource) -> None:
        """Sync with error suppression (for parallel sync)."""
        try:
            await self.sync_source(source)
        except Exception as e:
            logger.warning(
                f"Auto-sync failed for {source.value}: {type(e).__name__}",
                component=LogComponent.APPLE_CACHE,
            )

    async def _sync_notes(self) -> int:
        """Sync notes metadata from Apple Notes."""
        client = self._get_notes_client()
        notes = await client.list_notes()

        entities = []
        for note in notes:
            entities.append(CachedEntity(
                id=f"notes:{note.id}",
                source=EntitySource.NOTES,
                native_id=note.id,
                title=note.title,
                container=note.folder,
                modified_at=_parse_apple_date(note.modified_at),
                created_at=_parse_apple_date(note.created_at),
                metadata={},
            ))

        count = await self._database.upsert_entities(entities, EntitySource.NOTES)
        self._last_sync[EntitySource.NOTES] = time.time()

        logger.info(
            f"Notes cache synced: {count} notes",
            component=LogComponent.APPLE_CACHE,
        )
        return count

    async def _sync_calendar(self) -> int:
        """Sync calendar event metadata."""
        client = self._get_calendar_client()
        events = await client.get_upcoming_events(days=30)

        entities = []
        for event in events:
            entities.append(CachedEntity(
                id=f"calendar:{event.id}",
                source=EntitySource.CALENDAR,
                native_id=event.id,
                title=event.title,
                container=event.calendar,
                modified_at=event.start,  # Use start time as proxy
                created_at=None,
                metadata={
                    "location": event.location,
                    "is_all_day": event.is_all_day,
                    "start": event.start.isoformat() if event.start else None,
                    "end": event.end.isoformat() if event.end else None,
                },
            ))

        count = await self._database.upsert_entities(entities, EntitySource.CALENDAR)
        self._last_sync[EntitySource.CALENDAR] = time.time()

        logger.info(
            f"Calendar cache synced: {count} events",
            component=LogComponent.APPLE_CACHE,
        )
        return count

    async def _sync_reminders(self) -> int:
        """Sync incomplete reminders metadata."""
        client = self._get_reminders_client()
        reminders = await client.get_incomplete()

        entities = []
        for reminder in reminders:
            entities.append(CachedEntity(
                id=f"reminders:{reminder.id}",
                source=EntitySource.REMINDERS,
                native_id=reminder.id,
                title=reminder.title,
                container=reminder.list_name,
                modified_at=reminder.due,
                created_at=None,
                metadata={
                    "due": reminder.due.isoformat() if reminder.due else None,
                    "priority": reminder.priority,
                },
            ))

        count = await self._database.upsert_entities(entities, EntitySource.REMINDERS)
        self._last_sync[EntitySource.REMINDERS] = time.time()

        logger.info(
            f"Reminders cache synced: {count} reminders",
            component=LogComponent.APPLE_CACHE,
        )
        return count


def _parse_apple_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse Apple date strings (various formats from AppleScript/EventKit)."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError, AttributeError):
        return None


async def get_apple_cache_manager() -> AppleCacheManager:
    """Singleton factory for AppleCacheManager."""
    global _instance
    if _instance is None:
        _instance = AppleCacheManager()
        await _instance.initialize()
    return _instance


async def close_apple_cache_manager() -> None:
    """Close the singleton apple cache manager."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
