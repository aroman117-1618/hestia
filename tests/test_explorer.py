"""
Tests for Hestia Explorer module.

Resource aggregation, draft CRUD, caching, filtering, and deduplication.

Run with: python -m pytest tests/test_explorer.py -v
"""

import asyncio
import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from hestia.explorer.models import (
    ExplorerResource,
    ResourceFlag,
    ResourceSource,
    ResourceType,
)
from hestia.explorer.database import ExplorerDatabase
from hestia.explorer.manager import ExplorerManager


# ============== Fixtures ==============


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> ExplorerDatabase:
    """Create a test database."""
    db = ExplorerDatabase(db_path=temp_dir / "test_explorer.db")
    await db.initialize()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(database: ExplorerDatabase) -> ExplorerManager:
    """Create a manager with mocked Apple clients."""
    mgr = ExplorerManager(database=database)
    # Don't call initialize() — we set up mock clients manually
    mgr._mail_client = None
    mgr._notes_client = None
    mgr._reminders_client = None
    mgr._calendar_client = None
    return mgr


@pytest.fixture
def sample_resource() -> ExplorerResource:
    """Create a sample resource."""
    return ExplorerResource(
        id="mail:abc123",
        type=ResourceType.MAIL,
        title="Test Email",
        source=ResourceSource.MAIL,
        created_at=datetime(2026, 3, 1, 10, 0),
        modified_at=datetime(2026, 3, 1, 10, 0),
        preview="This is a test email preview...",
        flags=[ResourceFlag.UNREAD],
        metadata={"sender": "alice@example.com"},
    )


# ============== Model Tests ==============


class TestExplorerResource:
    """Tests for ExplorerResource model."""

    def test_to_dict(self, sample_resource: ExplorerResource):
        """Resource serializes to dict correctly."""
        d = sample_resource.to_dict()
        assert d["id"] == "mail:abc123"
        assert d["type"] == "mail"
        assert d["title"] == "Test Email"
        assert d["source"] == "mail"
        assert d["flags"] == ["unread"]
        assert d["metadata"]["sender"] == "alice@example.com"

    def test_from_dict_roundtrip(self, sample_resource: ExplorerResource):
        """Resource survives dict roundtrip."""
        d = sample_resource.to_dict()
        restored = ExplorerResource.from_dict(d)
        assert restored.id == sample_resource.id
        assert restored.type == sample_resource.type
        assert restored.title == sample_resource.title
        assert restored.flags == sample_resource.flags

    def test_from_dict_missing_optional(self):
        """Resource handles missing optional fields."""
        d = {
            "id": "notes:xyz",
            "type": "note",
            "title": "A Note",
            "source": "notes",
        }
        r = ExplorerResource.from_dict(d)
        assert r.preview is None
        assert r.flags == []
        assert r.color is None
        assert r.metadata == {}

    def test_resource_types(self):
        """All resource types are valid."""
        assert ResourceType.DRAFT.value == "draft"
        assert ResourceType.MAIL.value == "mail"
        assert ResourceType.TASK.value == "task"
        assert ResourceType.NOTE.value == "note"
        assert ResourceType.FILE.value == "file"

    def test_resource_sources(self):
        """All resource sources are valid."""
        assert ResourceSource.HESTIA.value == "hestia"
        assert ResourceSource.MAIL.value == "mail"
        assert ResourceSource.NOTES.value == "notes"
        assert ResourceSource.REMINDERS.value == "reminders"
        assert ResourceSource.FILES.value == "files"


# ============== Database Tests ==============


class TestExplorerDatabase:
    """Tests for ExplorerDatabase draft CRUD and caching."""

    @pytest.mark.asyncio
    async def test_create_draft(self, database: ExplorerDatabase):
        """Create a draft and verify fields."""
        draft = await database.create_draft(
            title="My Draft",
            body="Some content here",
            color="#FF5733",
            flags=[ResourceFlag.FLAGGED],
            metadata={"priority": "high"},
        )
        assert draft.id.startswith("drafts:")
        assert draft.title == "My Draft"
        assert draft.type == ResourceType.DRAFT
        assert draft.source == ResourceSource.HESTIA
        assert draft.preview == "Some content here"
        assert ResourceFlag.FLAGGED in draft.flags
        assert draft.color == "#FF5733"
        assert draft.metadata["priority"] == "high"

    @pytest.mark.asyncio
    async def test_get_draft(self, database: ExplorerDatabase):
        """Get a draft by ID."""
        created = await database.create_draft(title="Findable Draft", body="Find me")
        found = await database.get_draft(created.id)
        assert found is not None
        assert found.id == created.id
        assert found.title == "Findable Draft"

    @pytest.mark.asyncio
    async def test_get_draft_not_found(self, database: ExplorerDatabase):
        """Get non-existent draft returns None."""
        result = await database.get_draft("drafts:nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_update_draft(self, database: ExplorerDatabase):
        """Update a draft's fields."""
        created = await database.create_draft(title="Original", body="Old body")
        updated = await database.update_draft(
            created.id, title="Updated", body="New body"
        )
        assert updated is not None
        assert updated.title == "Updated"
        assert updated.preview == "New body"
        assert updated.modified_at > created.modified_at

    @pytest.mark.asyncio
    async def test_update_draft_partial(self, database: ExplorerDatabase):
        """Partial update preserves unchanged fields."""
        created = await database.create_draft(
            title="Keep Me", body="Keep this too", color="#123456"
        )
        updated = await database.update_draft(created.id, body="Only this changes")
        assert updated is not None
        assert updated.title == "Keep Me"
        assert updated.color == "#123456"
        assert updated.preview == "Only this changes"

    @pytest.mark.asyncio
    async def test_update_draft_not_found(self, database: ExplorerDatabase):
        """Update non-existent draft returns None."""
        result = await database.update_draft("drafts:nonexistent", title="Nope")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_draft(self, database: ExplorerDatabase):
        """Delete a draft."""
        created = await database.create_draft(title="Delete Me")
        deleted = await database.delete_draft(created.id)
        assert deleted is True
        found = await database.get_draft(created.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_delete_draft_not_found(self, database: ExplorerDatabase):
        """Delete non-existent draft returns False."""
        result = await database.delete_draft("drafts:nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_drafts_ordered(self, database: ExplorerDatabase):
        """List drafts returns most recent first."""
        await database.create_draft(title="First")
        await database.create_draft(title="Second")
        await database.create_draft(title="Third")
        drafts = await database.list_drafts()
        assert len(drafts) == 3
        assert drafts[0].title == "Third"

    @pytest.mark.asyncio
    async def test_cache_set_and_get(
        self, database: ExplorerDatabase, sample_resource: ExplorerResource
    ):
        """Cache stores and retrieves resources."""
        await database.set_cached_resources(
            ResourceSource.MAIL, [sample_resource]
        )
        cached = await database.get_cached_resources(ResourceSource.MAIL)
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].id == "mail:abc123"

    @pytest.mark.asyncio
    async def test_cache_miss(self, database: ExplorerDatabase):
        """Cache returns None for uncached source."""
        result = await database.get_cached_resources(ResourceSource.NOTES)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_ttl_expired(
        self, database: ExplorerDatabase, sample_resource: ExplorerResource
    ):
        """Cache returns None when TTL has expired."""
        # Write cache entry with very short TTL by manipulating cached_at
        assert database._connection is not None
        await database._connection.execute(
            """INSERT OR REPLACE INTO resource_cache (source, data_json, cached_at, ttl_seconds)
               VALUES (?, ?, ?, ?)""",
            (
                ResourceSource.MAIL.value,
                json.dumps([sample_resource.to_dict()]),
                time.time() - 1000,  # Cached 1000 seconds ago
                300,  # TTL is 300 seconds
            ),
        )
        await database._connection.commit()

        result = await database.get_cached_resources(ResourceSource.MAIL)
        assert result is None  # Expired

    @pytest.mark.asyncio
    async def test_clear_cache_specific(
        self, database: ExplorerDatabase, sample_resource: ExplorerResource
    ):
        """Clear cache for specific source."""
        await database.set_cached_resources(
            ResourceSource.MAIL, [sample_resource]
        )
        await database.clear_cache(ResourceSource.MAIL)
        result = await database.get_cached_resources(ResourceSource.MAIL)
        assert result is None

    @pytest.mark.asyncio
    async def test_clear_cache_all(
        self, database: ExplorerDatabase, sample_resource: ExplorerResource
    ):
        """Clear all caches."""
        await database.set_cached_resources(
            ResourceSource.MAIL, [sample_resource]
        )
        note_resource = ExplorerResource(
            id="notes:xyz",
            type=ResourceType.NOTE,
            title="A Note",
            source=ResourceSource.NOTES,
        )
        await database.set_cached_resources(
            ResourceSource.NOTES, [note_resource]
        )
        await database.clear_cache()
        assert await database.get_cached_resources(ResourceSource.MAIL) is None
        assert await database.get_cached_resources(ResourceSource.NOTES) is None


# ============== Manager Tests ==============


class TestExplorerManager:
    """Tests for ExplorerManager aggregation and draft operations."""

    @pytest.mark.asyncio
    async def test_create_and_list_drafts(self, manager: ExplorerManager):
        """Create drafts via manager and list them."""
        await manager.create_draft(title="Draft 1", body="Body 1")
        await manager.create_draft(title="Draft 2", body="Body 2")

        resources = await manager.get_resources(resource_type=ResourceType.DRAFT)
        assert len(resources) == 2
        titles = {r.title for r in resources}
        assert "Draft 1" in titles
        assert "Draft 2" in titles

    @pytest.mark.asyncio
    async def test_update_draft_via_manager(self, manager: ExplorerManager):
        """Update a draft through the manager."""
        draft = await manager.create_draft(title="Original")
        updated = await manager.update_draft(draft.id, title="Modified")
        assert updated is not None
        assert updated.title == "Modified"

    @pytest.mark.asyncio
    async def test_delete_draft_via_manager(self, manager: ExplorerManager):
        """Delete a draft through the manager."""
        draft = await manager.create_draft(title="Temporary")
        deleted = await manager.delete_draft(draft.id)
        assert deleted is True
        resources = await manager.get_resources(resource_type=ResourceType.DRAFT)
        assert len(resources) == 0

    @pytest.mark.asyncio
    async def test_get_resource_by_id(self, manager: ExplorerManager):
        """Get a specific draft by ID."""
        draft = await manager.create_draft(title="Specific Draft")
        found = await manager.get_resource(draft.id)
        assert found is not None
        assert found.id == draft.id

    @pytest.mark.asyncio
    async def test_search_filter(self, manager: ExplorerManager):
        """Search filters resources by title."""
        await manager.create_draft(title="Important meeting notes")
        await manager.create_draft(title="Grocery list")
        await manager.create_draft(title="Meeting agenda")

        results = await manager.get_resources(search="meeting")
        assert len(results) == 2
        titles = {r.title for r in results}
        assert "Important meeting notes" in titles
        assert "Meeting agenda" in titles

    @pytest.mark.asyncio
    async def test_search_by_preview(self, manager: ExplorerManager):
        """Search finds resources by preview text too."""
        await manager.create_draft(title="Draft A", body="Contains the keyword search")
        await manager.create_draft(title="Draft B", body="No match here")

        results = await manager.get_resources(search="keyword")
        assert len(results) == 1
        assert results[0].title == "Draft A"

    @pytest.mark.asyncio
    async def test_type_filter(self, manager: ExplorerManager):
        """Type filter returns only matching resources."""
        await manager.create_draft(title="A Draft")

        draft_results = await manager.get_resources(resource_type=ResourceType.DRAFT)
        assert len(draft_results) == 1

        mail_results = await manager.get_resources(resource_type=ResourceType.MAIL)
        assert len(mail_results) == 0

    @pytest.mark.asyncio
    async def test_source_filter(self, manager: ExplorerManager):
        """Source filter returns only matching resources."""
        await manager.create_draft(title="Hestia Draft")

        hestia_results = await manager.get_resources(source=ResourceSource.HESTIA)
        assert len(hestia_results) == 1

        mail_results = await manager.get_resources(source=ResourceSource.MAIL)
        assert len(mail_results) == 0

    @pytest.mark.asyncio
    async def test_pagination(self, manager: ExplorerManager):
        """Pagination limits and offsets results."""
        for i in range(5):
            await manager.create_draft(title=f"Draft {i}")

        page1 = await manager.get_resources(limit=2, offset=0)
        assert len(page1) == 2

        page2 = await manager.get_resources(limit=2, offset=2)
        assert len(page2) == 2

        page3 = await manager.get_resources(limit=2, offset=4)
        assert len(page3) == 1

    @pytest.mark.asyncio
    async def test_aggregation_with_mocked_mail(self, manager: ExplorerManager):
        """Manager aggregates mail alongside drafts."""
        # Mock mail client
        mock_mail = AsyncMock()
        mock_email = MagicMock()
        mock_email.message_id = "msg123"
        mock_email.subject = "Hello"
        mock_email.date = datetime(2026, 3, 1, 12, 0)
        mock_email.snippet = "Preview text"
        mock_email.sender = "alice"
        mock_email.sender_email = "alice@example.com"
        mock_email.mailbox = "INBOX"
        mock_email.is_read = False
        mock_email.is_flagged = True
        mock_mail.get_recent_emails = AsyncMock(return_value=[mock_email])
        manager._mail_client = mock_mail

        await manager.create_draft(title="My Draft")

        resources = await manager.get_resources()
        assert len(resources) == 2

        types = {r.type for r in resources}
        assert ResourceType.DRAFT in types
        assert ResourceType.MAIL in types

    @pytest.mark.asyncio
    async def test_aggregation_with_mocked_notes(self, manager: ExplorerManager):
        """Manager aggregates notes."""
        mock_notes = AsyncMock()
        mock_note = MagicMock()
        mock_note.id = "note456"
        mock_note.title = "My Note"
        mock_note.folder = "Personal"
        mock_note.body = "Note content here"
        mock_note.created_at = "2026-03-01T10:00:00"
        mock_note.modified_at = "2026-03-01T11:00:00"
        mock_notes.list_notes = AsyncMock(return_value=[mock_note])
        manager._notes_client = mock_notes

        resources = await manager.get_resources(source=ResourceSource.NOTES)
        assert len(resources) == 1
        assert resources[0].id == "notes:note456"
        assert resources[0].type == ResourceType.NOTE

    @pytest.mark.asyncio
    async def test_aggregation_with_mocked_reminders(self, manager: ExplorerManager):
        """Manager aggregates reminders as tasks."""
        mock_reminders = AsyncMock()
        mock_reminder = MagicMock()
        mock_reminder.id = "rem789"
        mock_reminder.title = "Buy groceries"
        mock_reminder.list_name = "Shopping"
        mock_reminder.notes = "Get milk and bread"
        mock_reminder.due = None
        mock_reminder.priority = 0
        mock_reminder.priority_level = MagicMock()
        mock_reminder.priority_level.value = 0
        mock_reminders.get_incomplete = AsyncMock(return_value=[mock_reminder])
        manager._reminders_client = mock_reminders

        resources = await manager.get_resources(source=ResourceSource.REMINDERS)
        assert len(resources) == 1
        assert resources[0].id == "reminders:rem789"
        assert resources[0].type == ResourceType.TASK
        assert resources[0].metadata["list"] == "Shopping"

    @pytest.mark.asyncio
    async def test_source_failure_graceful(self, manager: ExplorerManager):
        """If one source fails, others still return."""
        # Mail client that raises
        mock_mail = AsyncMock()
        mock_mail.get_recent_emails = AsyncMock(side_effect=Exception("DB error"))
        manager._mail_client = mock_mail

        await manager.create_draft(title="Surviving Draft")

        # Should still get the draft despite mail failure
        resources = await manager.get_resources()
        assert len(resources) == 1
        assert resources[0].title == "Surviving Draft"

    @pytest.mark.asyncio
    async def test_cache_serves_stale(self, manager: ExplorerManager):
        """Cached resources are served without re-fetching."""
        mock_mail = AsyncMock()
        mock_email = MagicMock()
        mock_email.message_id = "cached1"
        mock_email.subject = "Cached Email"
        mock_email.date = datetime(2026, 3, 1)
        mock_email.snippet = "Preview"
        mock_email.sender = "bob"
        mock_email.sender_email = "bob@example.com"
        mock_email.mailbox = "INBOX"
        mock_email.is_read = True
        mock_email.is_flagged = False
        mock_mail.get_recent_emails = AsyncMock(return_value=[mock_email])
        manager._mail_client = mock_mail

        # First call populates cache
        r1 = await manager.get_resources(source=ResourceSource.MAIL)
        assert len(r1) == 1

        # Second call should use cache (mail client not called again)
        mock_mail.get_recent_emails.reset_mock()
        r2 = await manager.get_resources(source=ResourceSource.MAIL)
        assert len(r2) == 1
        mock_mail.get_recent_emails.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_source_bypasses_cache(self, manager: ExplorerManager):
        """refresh_source() forces a fresh fetch."""
        mock_mail = AsyncMock()
        mock_email = MagicMock()
        mock_email.message_id = "fresh1"
        mock_email.subject = "Fresh Email"
        mock_email.date = datetime(2026, 3, 1)
        mock_email.snippet = "Preview"
        mock_email.sender = "carol"
        mock_email.sender_email = "carol@example.com"
        mock_email.mailbox = "INBOX"
        mock_email.is_read = True
        mock_email.is_flagged = False
        mock_mail.get_recent_emails = AsyncMock(return_value=[mock_email])
        manager._mail_client = mock_mail

        # Populate cache
        await manager.get_resources(source=ResourceSource.MAIL)
        call_count = mock_mail.get_recent_emails.call_count

        # Force refresh
        await manager.refresh_source(ResourceSource.MAIL)
        assert mock_mail.get_recent_emails.call_count > call_count

    @pytest.mark.asyncio
    async def test_get_resource_content_draft(self, manager: ExplorerManager):
        """Get content for a draft returns body from metadata."""
        draft = await manager.create_draft(
            title="Content Draft",
            body="Full body content here",
            metadata={"body": "Full body content here"},
        )
        content = await manager.get_resource_content(draft.id)
        assert content == "Full body content here"

    @pytest.mark.asyncio
    async def test_get_resource_content_mail(self, manager: ExplorerManager):
        """Get content for mail delegates to mail client."""
        mock_mail = AsyncMock()
        mock_email = MagicMock()
        mock_email.body = "Full email body content"
        mock_mail.get_email = AsyncMock(return_value=mock_email)
        manager._mail_client = mock_mail

        content = await manager.get_resource_content("mail:msg123")
        assert content == "Full email body content"
        mock_mail.get_email.assert_called_once_with("msg123")

    @pytest.mark.asyncio
    async def test_get_resource_content_notes(self, manager: ExplorerManager):
        """Get content for note delegates to notes client."""
        mock_notes = AsyncMock()
        mock_note = MagicMock()
        mock_note.body = "Full note body"
        mock_notes.get_note = AsyncMock(return_value=mock_note)
        manager._notes_client = mock_notes

        content = await manager.get_resource_content("notes:note456")
        assert content == "Full note body"


# ============== ID Format Tests ==============


class TestResourceIDFormats:
    """Verify ID generation follows plan rules."""

    @pytest.mark.asyncio
    async def test_draft_id_format(self, manager: ExplorerManager):
        """Draft IDs follow drafts:{uuid} format."""
        draft = await manager.create_draft(title="Test")
        assert draft.id.startswith("drafts:")
        assert len(draft.id) > len("drafts:")

    @pytest.mark.asyncio
    async def test_mail_id_format(self, manager: ExplorerManager):
        """Mail IDs follow mail:{message_id} format."""
        mock_mail = AsyncMock()
        mock_email = MagicMock()
        mock_email.message_id = "abc-123-def"
        mock_email.subject = "Test"
        mock_email.date = datetime(2026, 3, 1)
        mock_email.snippet = ""
        mock_email.sender = "x"
        mock_email.sender_email = "x@y.com"
        mock_email.mailbox = "INBOX"
        mock_email.is_read = True
        mock_email.is_flagged = False
        mock_mail.get_recent_emails = AsyncMock(return_value=[mock_email])
        manager._mail_client = mock_mail

        resources = await manager.get_resources(source=ResourceSource.MAIL)
        assert resources[0].id == "mail:abc-123-def"

    @pytest.mark.asyncio
    async def test_notes_id_format(self, manager: ExplorerManager):
        """Notes IDs follow notes:{note_id} format."""
        mock_notes = AsyncMock()
        mock_note = MagicMock()
        mock_note.id = "x-AppleNote-12345"
        mock_note.title = "Test"
        mock_note.folder = "Notes"
        mock_note.body = None
        mock_note.created_at = None
        mock_note.modified_at = None
        mock_notes.list_notes = AsyncMock(return_value=[mock_note])
        manager._notes_client = mock_notes

        resources = await manager.get_resources(source=ResourceSource.NOTES)
        assert resources[0].id == "notes:x-AppleNote-12345"

    @pytest.mark.asyncio
    async def test_reminders_id_format(self, manager: ExplorerManager):
        """Reminder IDs follow reminders:{reminder_id} format."""
        mock_reminders = AsyncMock()
        mock_reminder = MagicMock()
        mock_reminder.id = "EK-REM-789"
        mock_reminder.title = "Test"
        mock_reminder.list_name = "Default"
        mock_reminder.notes = None
        mock_reminder.due = None
        mock_reminder.priority = 0
        mock_reminder.priority_level = MagicMock()
        mock_reminder.priority_level.value = 0
        mock_reminders.get_incomplete = AsyncMock(return_value=[mock_reminder])
        manager._reminders_client = mock_reminders

        resources = await manager.get_resources(source=ResourceSource.REMINDERS)
        assert resources[0].id == "reminders:EK-REM-789"
