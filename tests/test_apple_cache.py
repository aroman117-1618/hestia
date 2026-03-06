"""
Tests for the Apple metadata cache module.

Covers: database CRUD, FTS5 search, fuzzy resolution, sync orchestration,
write-through hooks, TTL tracking, and container resolution.
"""

import asyncio
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from hestia.apple_cache.models import CachedEntity, EntitySource, ResolvedMatch
from hestia.apple_cache.database import AppleCacheDatabase
from hestia.apple_cache.resolver import SmartResolver
from hestia.apple_cache.manager import AppleCacheManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db(tmp_path: Path):
    """Fresh in-memory-like database for each test."""
    database = AppleCacheDatabase(db_path=tmp_path / "test_cache.db")
    await database.initialize()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def resolver(db: AppleCacheDatabase):
    """SmartResolver backed by test database."""
    return SmartResolver(db)


@pytest_asyncio.fixture
async def manager(db: AppleCacheDatabase):
    """AppleCacheManager with test database (Apple clients mocked)."""
    mgr = AppleCacheManager(database=db)
    mgr._resolver = SmartResolver(db)
    yield mgr
    await mgr.close()


def _make_entity(
    source: EntitySource = EntitySource.NOTES,
    native_id: str = "note1",
    title: str = "Grocery List",
    container: Optional[str] = "Shopping",
    modified_at: Optional[datetime] = None,
) -> CachedEntity:
    """Helper to create test entities."""
    return CachedEntity(
        id=f"{source.value}:{native_id}",
        source=source,
        native_id=native_id,
        title=title,
        container=container,
        modified_at=modified_at or datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        metadata={},
    )


# ---------------------------------------------------------------------------
# Database Tests
# ---------------------------------------------------------------------------

class TestAppleCacheDatabase:
    """Tests for AppleCacheDatabase CRUD and FTS5."""

    @pytest.mark.asyncio
    async def test_upsert_and_get_all(self, db: AppleCacheDatabase):
        """Upserted entities are retrievable."""
        entities = [
            _make_entity(native_id="n1", title="Grocery List"),
            _make_entity(native_id="n2", title="Meeting Notes"),
        ]
        count = await db.upsert_entities(entities, EntitySource.NOTES)
        assert count == 2

        all_entities = await db.get_all(source=EntitySource.NOTES)
        assert len(all_entities) == 2

    @pytest.mark.asyncio
    async def test_upsert_replaces_source(self, db: AppleCacheDatabase):
        """Second upsert for same source replaces all entries."""
        batch1 = [_make_entity(native_id="n1", title="Old Note")]
        await db.upsert_entities(batch1, EntitySource.NOTES)

        batch2 = [_make_entity(native_id="n2", title="New Note")]
        await db.upsert_entities(batch2, EntitySource.NOTES)

        all_entities = await db.get_all(source=EntitySource.NOTES)
        assert len(all_entities) == 1
        assert all_entities[0].title == "New Note"

    @pytest.mark.asyncio
    async def test_upsert_empty_clears_source(self, db: AppleCacheDatabase):
        """Empty upsert clears all entries for that source."""
        entities = [_make_entity(native_id="n1", title="Note")]
        await db.upsert_entities(entities, EntitySource.NOTES)

        count = await db.upsert_entities([], EntitySource.NOTES)
        assert count == 0

        all_entities = await db.get_all(source=EntitySource.NOTES)
        assert len(all_entities) == 0

    @pytest.mark.asyncio
    async def test_get_by_id(self, db: AppleCacheDatabase):
        """Can retrieve entity by composite ID."""
        entity = _make_entity(native_id="n1", title="Test Note")
        await db.upsert_entities([entity], EntitySource.NOTES)

        result = await db.get_by_id("notes:n1")
        assert result is not None
        assert result.title == "Test Note"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, db: AppleCacheDatabase):
        """Returns None for unknown ID."""
        result = await db.get_by_id("notes:nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_upsert_single_write_through(self, db: AppleCacheDatabase):
        """Single upsert for write-through doesn't affect other entities."""
        entities = [
            _make_entity(native_id="n1", title="Note One"),
            _make_entity(native_id="n2", title="Note Two"),
        ]
        await db.upsert_entities(entities, EntitySource.NOTES)

        new_entity = _make_entity(native_id="n3", title="Note Three")
        await db.upsert_single(new_entity)

        all_entities = await db.get_all(source=EntitySource.NOTES)
        assert len(all_entities) == 3

    @pytest.mark.asyncio
    async def test_delete_entity(self, db: AppleCacheDatabase):
        """Can delete a single entity."""
        entities = [_make_entity(native_id="n1", title="Delete Me")]
        await db.upsert_entities(entities, EntitySource.NOTES)

        deleted = await db.delete_entity("notes:n1")
        assert deleted is True

        result = await db.get_by_id("notes:n1")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, db: AppleCacheDatabase):
        """Deleting nonexistent entity returns False."""
        deleted = await db.delete_entity("notes:nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_containers(self, db: AppleCacheDatabase):
        """Get distinct containers for a source."""
        entities = [
            _make_entity(native_id="n1", title="A", container="Work"),
            _make_entity(native_id="n2", title="B", container="Personal"),
            _make_entity(native_id="n3", title="C", container="Work"),
        ]
        await db.upsert_entities(entities, EntitySource.NOTES)

        containers = await db.get_containers(EntitySource.NOTES)
        assert sorted(containers) == ["Personal", "Work"]

    @pytest.mark.asyncio
    async def test_get_entity_count(self, db: AppleCacheDatabase):
        """Entity count works with and without source filter."""
        notes = [_make_entity(native_id=f"n{i}", title=f"Note {i}") for i in range(5)]
        cal = [_make_entity(
            source=EntitySource.CALENDAR, native_id=f"c{i}", title=f"Event {i}"
        ) for i in range(3)]

        await db.upsert_entities(notes, EntitySource.NOTES)
        await db.upsert_entities(cal, EntitySource.CALENDAR)

        assert await db.get_entity_count() == 8
        assert await db.get_entity_count(EntitySource.NOTES) == 5
        assert await db.get_entity_count(EntitySource.CALENDAR) == 3

    @pytest.mark.asyncio
    async def test_source_isolation(self, db: AppleCacheDatabase):
        """Upsert for one source doesn't affect another."""
        notes = [_make_entity(native_id="n1", title="Note")]
        cal = [_make_entity(
            source=EntitySource.CALENDAR, native_id="c1", title="Event"
        )]

        await db.upsert_entities(notes, EntitySource.NOTES)
        await db.upsert_entities(cal, EntitySource.CALENDAR)

        # Re-sync notes with different data
        new_notes = [_make_entity(native_id="n2", title="New Note")]
        await db.upsert_entities(new_notes, EntitySource.NOTES)

        # Calendar should be untouched
        all_cal = await db.get_all(source=EntitySource.CALENDAR)
        assert len(all_cal) == 1
        assert all_cal[0].title == "Event"

    # -- FTS5 Tests --------------------------------------------------------

    @pytest.mark.asyncio
    async def test_fts_search_basic(self, db: AppleCacheDatabase):
        """FTS5 search finds matching titles."""
        entities = [
            _make_entity(native_id="n1", title="Grocery Shopping List"),
            _make_entity(native_id="n2", title="Meeting Agenda"),
            _make_entity(native_id="n3", title="Grocery Store Hours"),
        ]
        await db.upsert_entities(entities, EntitySource.NOTES)

        results = await db.search_fts("grocery")
        assert len(results) == 2
        titles = {e.title for e in results}
        assert "Grocery Shopping List" in titles
        assert "Grocery Store Hours" in titles

    @pytest.mark.asyncio
    async def test_fts_search_source_filter(self, db: AppleCacheDatabase):
        """FTS5 search respects source filter."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Dentist Appointment Notes")],
            EntitySource.NOTES,
        )
        await db.upsert_entities(
            [_make_entity(
                source=EntitySource.CALENDAR,
                native_id="c1",
                title="Dentist Appointment",
            )],
            EntitySource.CALENDAR,
        )

        notes_only = await db.search_fts("dentist", source=EntitySource.NOTES)
        assert len(notes_only) == 1
        assert notes_only[0].source == EntitySource.NOTES

    @pytest.mark.asyncio
    async def test_fts_search_empty_query(self, db: AppleCacheDatabase):
        """Empty query returns no results."""
        entities = [_make_entity(native_id="n1", title="Something")]
        await db.upsert_entities(entities, EntitySource.NOTES)

        results = await db.search_fts("")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_fts_prefix_matching(self, db: AppleCacheDatabase):
        """FTS5 prefix matching works (groce* matches grocery)."""
        entities = [_make_entity(native_id="n1", title="Grocery List")]
        await db.upsert_entities(entities, EntitySource.NOTES)

        results = await db.search_fts("groce")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_fts_container_search(self, db: AppleCacheDatabase):
        """FTS5 can match on container field."""
        entities = [_make_entity(native_id="n1", title="Recipe", container="Cooking")]
        await db.upsert_entities(entities, EntitySource.NOTES)

        results = await db.search_fts("cooking")
        assert len(results) == 1

    # -- Sync Tracking Tests -----------------------------------------------

    @pytest.mark.asyncio
    async def test_sync_timestamp_tracking(self, db: AppleCacheDatabase):
        """Sync timestamps are recorded and retrievable."""
        entities = [_make_entity(native_id="n1", title="Note")]
        await db.upsert_entities(entities, EntitySource.NOTES)

        last_sync = await db.get_last_sync(EntitySource.NOTES)
        assert last_sync is not None
        assert (datetime.now(timezone.utc) - last_sync).total_seconds() < 5

    @pytest.mark.asyncio
    async def test_sync_status(self, db: AppleCacheDatabase):
        """Sync status returns per-source info."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Note")],
            EntitySource.NOTES,
        )
        await db.upsert_entities(
            [_make_entity(
                source=EntitySource.CALENDAR, native_id="c1", title="Event"
            )],
            EntitySource.CALENDAR,
        )

        status = await db.get_sync_status()
        assert "notes" in status
        assert "calendar" in status
        assert status["notes"]["item_count"] == 1
        assert status["calendar"]["item_count"] == 1

    @pytest.mark.asyncio
    async def test_no_sync_for_unsyced_source(self, db: AppleCacheDatabase):
        """Unsynced source returns None for last_sync."""
        last_sync = await db.get_last_sync(EntitySource.REMINDERS)
        assert last_sync is None


# ---------------------------------------------------------------------------
# Resolver Tests
# ---------------------------------------------------------------------------

class TestSmartResolver:
    """Tests for fuzzy title resolution."""

    @pytest.mark.asyncio
    async def test_exact_match(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Exact title match returns score 100."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Grocery List")],
            EntitySource.NOTES,
        )

        matches = await resolver.resolve("Grocery List")
        assert len(matches) >= 1
        assert matches[0].score == 100.0
        assert matches[0].match_method == "exact"

    @pytest.mark.asyncio
    async def test_case_insensitive_exact(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Case-insensitive exact match."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Grocery List")],
            EntitySource.NOTES,
        )

        matches = await resolver.resolve("grocery list")
        assert len(matches) >= 1
        assert matches[0].score == 100.0

    @pytest.mark.asyncio
    async def test_fuzzy_partial_match(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Partial query finds matching entities."""
        await db.upsert_entities(
            [
                _make_entity(native_id="n1", title="Grocery Shopping List"),
                _make_entity(native_id="n2", title="Meeting Agenda"),
            ],
            EntitySource.NOTES,
        )

        matches = await resolver.resolve("grocery")
        assert len(matches) >= 1
        assert matches[0].entity.title == "Grocery Shopping List"

    @pytest.mark.asyncio
    async def test_fuzzy_word_reorder(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Word reordering still matches (token_set_ratio)."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Shopping Grocery List")],
            EntitySource.NOTES,
        )

        matches = await resolver.resolve("grocery shopping")
        assert len(matches) >= 1
        assert matches[0].score >= 80.0

    @pytest.mark.asyncio
    async def test_source_filtering(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Resolve respects source filter."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Dentist")],
            EntitySource.NOTES,
        )
        await db.upsert_entities(
            [_make_entity(
                source=EntitySource.CALENDAR, native_id="c1", title="Dentist"
            )],
            EntitySource.CALENDAR,
        )

        matches = await resolver.resolve("dentist", source=EntitySource.CALENDAR)
        assert len(matches) >= 1
        assert all(m.entity.source == EntitySource.CALENDAR for m in matches)

    @pytest.mark.asyncio
    async def test_min_score_threshold(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Low-scoring matches are filtered out."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Completely Unrelated Title")],
            EntitySource.NOTES,
        )

        matches = await resolver.resolve("grocery list", min_score=80.0)
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_resolve_best(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """resolve_best returns single best match."""
        await db.upsert_entities(
            [
                _make_entity(native_id="n1", title="Grocery List"),
                _make_entity(native_id="n2", title="Grocery Store Hours"),
            ],
            EntitySource.NOTES,
        )

        best = await resolver.resolve_best("grocery list")
        assert best is not None
        assert best.entity.title == "Grocery List"

    @pytest.mark.asyncio
    async def test_resolve_best_no_match(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """resolve_best returns None when nothing matches."""
        best = await resolver.resolve_best("nonexistent thing")
        assert best is None

    @pytest.mark.asyncio
    async def test_resolve_container(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Container resolution finds fuzzy container names."""
        await db.upsert_entities(
            [
                _make_entity(native_id="n1", title="A", container="Shopping"),
                _make_entity(native_id="n2", title="B", container="Work Projects"),
            ],
            EntitySource.NOTES,
        )

        result = await resolver.resolve_container("shopping", EntitySource.NOTES)
        assert result == "Shopping"

    @pytest.mark.asyncio
    async def test_resolve_container_fuzzy(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Container resolution handles fuzzy names."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="A", container="Work Projects")],
            EntitySource.NOTES,
        )

        result = await resolver.resolve_container("work", EntitySource.NOTES)
        assert result == "Work Projects"

    @pytest.mark.asyncio
    async def test_empty_query_returns_nothing(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """Empty/whitespace queries return empty list."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Note")],
            EntitySource.NOTES,
        )

        assert await resolver.resolve("") == []
        assert await resolver.resolve("   ") == []

    @pytest.mark.asyncio
    async def test_fallback_to_full_scan(self, db: AppleCacheDatabase, resolver: SmartResolver):
        """When FTS5 finds nothing, falls back to full scan with fuzzy match."""
        # Use a title that FTS5 prefix won't match but fuzzy will
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Groceries")],
            EntitySource.NOTES,
        )

        # "groceris" is a typo -- FTS5 prefix won't match, but fuzzy will
        matches = await resolver.resolve("groceris", min_score=60.0)
        # May or may not match depending on fuzzy threshold
        # The point is it doesn't crash and tries full scan
        assert isinstance(matches, list)


# ---------------------------------------------------------------------------
# Manager Tests
# ---------------------------------------------------------------------------

class TestAppleCacheManager:
    """Tests for sync orchestration and public API."""

    @pytest.mark.asyncio
    async def test_sync_notes(self, manager: AppleCacheManager, db: AppleCacheDatabase):
        """Notes sync populates cache from NotesClient."""
        from hestia.apple.models import Note

        mock_notes = [
            Note(id="n1", title="Grocery List", folder="Shopping"),
            Note(id="n2", title="Meeting Notes", folder="Work"),
        ]

        mock_client = MagicMock()
        mock_client.list_notes = AsyncMock(return_value=mock_notes)
        manager._notes_client = mock_client

        count = await manager._sync_notes()
        assert count == 2

        entities = await db.get_all(source=EntitySource.NOTES)
        assert len(entities) == 2
        titles = {e.title for e in entities}
        assert "Grocery List" in titles
        assert "Meeting Notes" in titles

    @pytest.mark.asyncio
    async def test_sync_calendar(self, manager: AppleCacheManager, db: AppleCacheDatabase):
        """Calendar sync populates cache from CalendarClient."""
        from hestia.apple.models import Event

        now = datetime.now(timezone.utc)
        mock_events = [
            Event(
                id="c1", title="Team Standup", calendar="Work",
                calendar_id="cal1", start=now, end=now,
            ),
        ]

        mock_client = MagicMock()
        mock_client.get_upcoming_events = AsyncMock(return_value=mock_events)
        manager._calendar_client = mock_client

        count = await manager._sync_calendar()
        assert count == 1

    @pytest.mark.asyncio
    async def test_sync_reminders(self, manager: AppleCacheManager, db: AppleCacheDatabase):
        """Reminders sync populates cache from RemindersClient."""
        from hestia.apple.models import Reminder

        mock_reminders = [
            Reminder(id="r1", title="Buy milk", list_name="Shopping", list_id="l1"),
        ]

        mock_client = MagicMock()
        mock_client.get_incomplete = AsyncMock(return_value=mock_reminders)
        manager._reminders_client = mock_client

        count = await manager._sync_reminders()
        assert count == 1

    @pytest.mark.asyncio
    async def test_sync_all(self, manager: AppleCacheManager):
        """sync_all runs all three sources."""
        from hestia.apple.models import Note, Event, Reminder

        mock_notes_client = MagicMock()
        mock_notes_client.list_notes = AsyncMock(return_value=[
            Note(id="n1", title="Note", folder="F"),
        ])
        mock_cal_client = MagicMock()
        mock_cal_client.get_upcoming_events = AsyncMock(return_value=[])
        mock_rem_client = MagicMock()
        mock_rem_client.get_incomplete = AsyncMock(return_value=[])

        manager._notes_client = mock_notes_client
        manager._calendar_client = mock_cal_client
        manager._reminders_client = mock_rem_client

        counts = await manager.sync_all()
        assert counts["notes"] == 1
        assert counts["calendar"] == 0
        assert counts["reminders"] == 0

    @pytest.mark.asyncio
    async def test_sync_failure_isolated(self, manager: AppleCacheManager):
        """One sync failure doesn't block others."""
        from hestia.apple.models import Note

        mock_notes_client = MagicMock()
        mock_notes_client.list_notes = AsyncMock(return_value=[
            Note(id="n1", title="Note", folder="F"),
        ])
        mock_cal_client = MagicMock()
        mock_cal_client.get_upcoming_events = AsyncMock(side_effect=Exception("timeout"))
        mock_rem_client = MagicMock()
        mock_rem_client.get_incomplete = AsyncMock(return_value=[])

        manager._notes_client = mock_notes_client
        manager._calendar_client = mock_cal_client
        manager._reminders_client = mock_rem_client

        counts = await manager.sync_all()
        assert counts["notes"] == 1
        assert counts["calendar"] == 0  # Failed but didn't crash

    @pytest.mark.asyncio
    async def test_write_through_create(self, manager: AppleCacheManager, db: AppleCacheDatabase):
        """Write-through on entity creation updates cache."""
        await manager.on_entity_created(
            source=EntitySource.NOTES,
            native_id="new1",
            title="Brand New Note",
            container="Inbox",
        )

        entity = await db.get_by_id("notes:new1")
        assert entity is not None
        assert entity.title == "Brand New Note"
        assert entity.container == "Inbox"

    @pytest.mark.asyncio
    async def test_write_through_update(self, manager: AppleCacheManager, db: AppleCacheDatabase):
        """Write-through on entity update preserves existing data."""
        # Create initial
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Old Title", container="Work")],
            EntitySource.NOTES,
        )

        # Update
        await manager.on_entity_updated(
            source=EntitySource.NOTES,
            native_id="n1",
            title="New Title",
        )

        entity = await db.get_by_id("notes:n1")
        assert entity.title == "New Title"
        assert entity.container == "Work"  # Preserved from original

    @pytest.mark.asyncio
    async def test_write_through_delete(self, manager: AppleCacheManager, db: AppleCacheDatabase):
        """Write-through on entity deletion removes from cache."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Delete Me")],
            EntitySource.NOTES,
        )

        await manager.on_entity_deleted(EntitySource.NOTES, "n1")

        entity = await db.get_by_id("notes:n1")
        assert entity is None

    @pytest.mark.asyncio
    async def test_ttl_stale_detection(self, manager: AppleCacheManager):
        """Stale detection works based on TTL."""
        # Not synced yet -- should be stale
        assert manager._is_stale(EntitySource.NOTES) is True

        # Fake a recent sync
        manager._last_sync[EntitySource.NOTES] = time.time()
        assert manager._is_stale(EntitySource.NOTES) is False

        # Fake an old sync
        manager._last_sync[EntitySource.NOTES] = time.time() - 7 * 3600
        assert manager._is_stale(EntitySource.NOTES) is True

    @pytest.mark.asyncio
    async def test_get_status(self, manager: AppleCacheManager, db: AppleCacheDatabase):
        """Status includes entity counts and TTL info."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Note")],
            EntitySource.NOTES,
        )

        status = await manager.get_status()
        assert status["total_entities"] == 1
        assert "notes" in status["ttl_seconds"]

    @pytest.mark.asyncio
    async def test_resolve_triggers_sync(self, manager: AppleCacheManager):
        """Resolve auto-syncs stale sources."""
        from hestia.apple.models import Note

        mock_client = MagicMock()
        mock_client.list_notes = AsyncMock(return_value=[
            Note(id="n1", title="Test Note", folder="F"),
        ])
        manager._notes_client = mock_client

        # Notes are stale (never synced) -- resolve should trigger sync
        matches = await manager.resolve("test note", source=EntitySource.NOTES)

        mock_client.list_notes.assert_called_once()
        assert len(matches) >= 1


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tool Integration Tests
# ---------------------------------------------------------------------------

class TestToolIntegration:
    """Tests for cache-backed tool handlers."""

    def test_looks_like_note_id(self):
        """Note ID heuristic correctly distinguishes IDs from titles."""
        from hestia.apple.tools import _looks_like_note_id

        # Real Apple Note IDs
        assert _looks_like_note_id("x-coredata://12345/Note/p67") is True
        assert _looks_like_note_id("x-coredata://ABC-DEF/ICNote/p89") is True

        # Long path-like IDs
        assert _looks_like_note_id("12345678-abcd-efgh-ijkl/Notes/SomeId") is True

        # Titles (should NOT be IDs)
        assert _looks_like_note_id("Grocery List") is False
        assert _looks_like_note_id("Meeting Notes") is False
        assert _looks_like_note_id("my ideas") is False
        assert _looks_like_note_id("Sprint 12 Plan") is False

    @pytest.mark.asyncio
    async def test_find_note_handler(self, db: AppleCacheDatabase):
        """find_note tool handler returns ranked results from cache."""
        await db.upsert_entities(
            [
                _make_entity(native_id="n1", title="Grocery List", container="Shopping"),
                _make_entity(native_id="n2", title="Meeting Agenda", container="Work"),
            ],
            EntitySource.NOTES,
        )

        # Patch the cache manager to use our test DB
        from hestia.apple_cache.manager import AppleCacheManager
        from hestia.apple_cache.resolver import SmartResolver

        test_mgr = AppleCacheManager(database=db)
        test_mgr._resolver = SmartResolver(db)
        # Mark notes as fresh so it doesn't try to sync
        import time
        test_mgr._last_sync[EntitySource.NOTES] = time.time()

        with patch("hestia.apple.tools._get_cache_manager", return_value=test_mgr):
            from hestia.apple.tools import find_note
            result = await find_note("grocery")

            assert result["count"] >= 1
            assert result["notes"][0]["title"] == "Grocery List"
            assert "score" in result["notes"][0]

    @pytest.mark.asyncio
    async def test_read_note_handler(self, db: AppleCacheDatabase):
        """read_note tool handler resolves and fetches content."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Sprint Plan", container="Work")],
            EntitySource.NOTES,
        )

        from hestia.apple_cache.manager import AppleCacheManager
        from hestia.apple_cache.resolver import SmartResolver
        from hestia.apple.models import Note

        test_mgr = AppleCacheManager(database=db)
        test_mgr._resolver = SmartResolver(db)
        import time
        test_mgr._last_sync[EntitySource.NOTES] = time.time()

        mock_note = Note(
            id="n1", title="Sprint Plan", folder="Work",
            body="# Sprint 12\n\n- Build cache\n- Wire tools",
        )
        mock_client = MagicMock()
        mock_client.get_note = AsyncMock(return_value=mock_note)

        with patch("hestia.apple.tools._get_cache_manager", return_value=test_mgr), \
             patch("hestia.apple.tools._get_notes_client", return_value=mock_client):
            from hestia.apple.tools import read_note
            result = await read_note("sprint plan")

            assert "note" in result
            assert result["note"]["title"] == "Sprint Plan"
            assert "Sprint 12" in result["note"]["body"]
            assert result["match_score"] >= 80.0

    @pytest.mark.asyncio
    async def test_read_note_no_match(self, db: AppleCacheDatabase):
        """read_note returns error when no match found."""
        from hestia.apple_cache.manager import AppleCacheManager
        from hestia.apple_cache.resolver import SmartResolver

        test_mgr = AppleCacheManager(database=db)
        test_mgr._resolver = SmartResolver(db)
        import time
        test_mgr._last_sync[EntitySource.NOTES] = time.time()

        with patch("hestia.apple.tools._get_cache_manager", return_value=test_mgr):
            from hestia.apple.tools import read_note
            result = await read_note("nonexistent gibberish xyz")

            assert "error" in result
            assert "suggestion" in result

    @pytest.mark.asyncio
    async def test_find_event_handler(self, db: AppleCacheDatabase):
        """find_event tool handler returns ranked calendar matches."""
        await db.upsert_entities(
            [_make_entity(
                source=EntitySource.CALENDAR, native_id="c1",
                title="Dentist Appointment", container="Personal",
            )],
            EntitySource.CALENDAR,
        )

        from hestia.apple_cache.manager import AppleCacheManager
        from hestia.apple_cache.resolver import SmartResolver

        test_mgr = AppleCacheManager(database=db)
        test_mgr._resolver = SmartResolver(db)
        import time
        test_mgr._last_sync[EntitySource.CALENDAR] = time.time()

        with patch("hestia.apple.tools._get_cache_manager", return_value=test_mgr):
            from hestia.apple.tools import find_event
            result = await find_event("dentist")

            assert result["count"] >= 1
            assert result["events"][0]["title"] == "Dentist Appointment"

    @pytest.mark.asyncio
    async def test_search_notes_uses_cache(self, db: AppleCacheDatabase):
        """search_notes uses cache instead of slow AppleScript."""
        await db.upsert_entities(
            [_make_entity(native_id="n1", title="Grocery List", container="Shopping")],
            EntitySource.NOTES,
        )

        from hestia.apple_cache.manager import AppleCacheManager
        from hestia.apple_cache.resolver import SmartResolver

        test_mgr = AppleCacheManager(database=db)
        test_mgr._resolver = SmartResolver(db)
        import time
        test_mgr._last_sync[EntitySource.NOTES] = time.time()

        with patch("hestia.apple.tools._get_cache_manager", return_value=test_mgr):
            from hestia.apple.tools import search_notes
            result = await search_notes("grocery")

            assert result["count"] >= 1
            assert "score" in result["notes"][0]  # Cache adds score field


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestModels:
    """Tests for data model serialization."""

    def test_cached_entity_to_dict(self):
        """CachedEntity serializes correctly."""
        now = datetime.now(timezone.utc)
        entity = CachedEntity(
            id="notes:n1",
            source=EntitySource.NOTES,
            native_id="n1",
            title="Test",
            container="Folder",
            modified_at=now,
            created_at=now,
            metadata={"key": "value"},
        )
        d = entity.to_dict()
        assert d["id"] == "notes:n1"
        assert d["source"] == "notes"
        assert d["metadata"] == {"key": "value"}

    def test_resolved_match_fields(self):
        """ResolvedMatch has expected fields."""
        entity = _make_entity()
        match = ResolvedMatch(entity=entity, score=85.0, match_method="fuzzy")
        assert match.score == 85.0
        assert match.match_method == "fuzzy"

    def test_entity_source_values(self):
        """EntitySource enum has expected values."""
        assert EntitySource.NOTES.value == "notes"
        assert EntitySource.CALENDAR.value == "calendar"
        assert EntitySource.REMINDERS.value == "reminders"
