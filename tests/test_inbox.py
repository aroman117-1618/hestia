"""
Tests for hestia.inbox -- InboxDatabase, InboxManager, and API routes.

Covers:
- TestInboxDatabase: SQLite CRUD, user-scoped state, pagination, cleanup
- TestInboxManager: Aggregation from mocked Apple clients, cache TTL, error resilience
- TestInboxRoutes: API endpoints with mocked manager
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch as mock_patch

import pytest

from hestia.inbox.models import (
    InboxItem,
    InboxItemPriority,
    InboxItemSource,
    InboxItemType,
)
from hestia.inbox.database import InboxDatabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    id: str = "mail:test-1",
    item_type: InboxItemType = InboxItemType.EMAIL,
    source: InboxItemSource = InboxItemSource.MAIL,
    title: str = "Test Email",
    body: str = "Hello world",
    timestamp: datetime = None,
    priority: InboxItemPriority = InboxItemPriority.NORMAL,
    sender: str = "Alice",
    sender_detail: str = "alice@example.com",
    has_attachments: bool = False,
    icon: str = "envelope.fill",
    color: str = "#E0A050",
    metadata: dict = None,
) -> InboxItem:
    """Helper to create an InboxItem with sensible defaults."""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc)
    if metadata is None:
        metadata = {}
    return InboxItem(
        id=id,
        item_type=item_type,
        source=source,
        title=title,
        body=body,
        timestamp=timestamp,
        priority=priority,
        sender=sender,
        sender_detail=sender_detail,
        has_attachments=has_attachments,
        icon=icon,
        color=color,
        metadata=metadata,
    )


# ===========================================================================
# TestInboxDatabase
# ===========================================================================

class TestInboxDatabase:
    """Tests for InboxDatabase SQLite operations."""

    @pytest.fixture
    async def db(self, tmp_path: Path):
        """Create an in-memory-like InboxDatabase for testing."""
        db_path = tmp_path / "test_inbox.db"
        database = InboxDatabase(db_path=db_path)
        await database.initialize()
        yield database
        await database.close()

    @pytest.mark.asyncio
    async def test_upsert_and_retrieve(self, db: InboxDatabase):
        """Upserted items should be retrievable."""
        items = [
            _make_item(id="mail:1", title="First"),
            _make_item(id="mail:2", title="Second"),
        ]
        count = await db.upsert_items(items)
        assert count == 2

        result = await db.get_items(user_id="user-1")
        assert len(result) == 2
        titles = {r.title for r in result}
        assert "First" in titles
        assert "Second" in titles

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self, db: InboxDatabase):
        """Upserting with the same ID should replace the item."""
        await db.upsert_items([_make_item(id="mail:1", title="Original")])
        await db.upsert_items([_make_item(id="mail:1", title="Updated")])

        result = await db.get_items(user_id="user-1")
        assert len(result) == 1
        assert result[0].title == "Updated"

    @pytest.mark.asyncio
    async def test_user_scoped_state(self, db: InboxDatabase):
        """Two users should have independent read status."""
        await db.upsert_items([_make_item(id="mail:1")])

        # User A marks read
        await db.mark_read("mail:1", "user-a")

        # User A sees it as read
        item_a = await db.get_item("mail:1", "user-a")
        assert item_a is not None
        assert item_a.is_read is True

        # User B still sees it as unread
        item_b = await db.get_item("mail:1", "user-b")
        assert item_b is not None
        assert item_b.is_read is False

    @pytest.mark.asyncio
    async def test_mark_read(self, db: InboxDatabase):
        """mark_read should set is_read=True."""
        await db.upsert_items([_make_item(id="mail:1")])

        result = await db.mark_read("mail:1", "user-1")
        assert result is True

        item = await db.get_item("mail:1", "user-1")
        assert item.is_read is True

    @pytest.mark.asyncio
    async def test_mark_all_read(self, db: InboxDatabase):
        """mark_all_read should mark all unread items as read."""
        items = [
            _make_item(id="mail:1", source=InboxItemSource.MAIL),
            _make_item(id="mail:2", source=InboxItemSource.MAIL),
            _make_item(
                id="reminders:1",
                source=InboxItemSource.REMINDERS,
                item_type=InboxItemType.REMINDER,
            ),
        ]
        await db.upsert_items(items)

        # Mark all mail as read
        count = await db.mark_all_read("user-1", source=InboxItemSource.MAIL)
        assert count == 2

        # Mail items are read
        unread_mail = await db.get_unread_count("user-1", source=InboxItemSource.MAIL)
        assert unread_mail == 0

        # Reminder is still unread
        unread_reminders = await db.get_unread_count(
            "user-1", source=InboxItemSource.REMINDERS
        )
        assert unread_reminders == 1

    @pytest.mark.asyncio
    async def test_archive_hides_from_default_query(self, db: InboxDatabase):
        """Archived items should not appear in the default (non-archived) query."""
        await db.upsert_items([
            _make_item(id="mail:1"),
            _make_item(id="mail:2"),
        ])

        await db.archive("mail:1", "user-1")

        # Default query excludes archived
        result = await db.get_items(user_id="user-1")
        assert len(result) == 1
        assert result[0].id == "mail:2"

        # include_archived=True shows all
        result_all = await db.get_items(user_id="user-1", include_archived=True)
        assert len(result_all) == 2

    @pytest.mark.asyncio
    async def test_unread_count_accuracy(self, db: InboxDatabase):
        """get_unread_count should accurately reflect unread/non-archived items."""
        items = [
            _make_item(id="mail:1"),
            _make_item(id="mail:2"),
            _make_item(id="mail:3"),
        ]
        await db.upsert_items(items)

        assert await db.get_unread_count("user-1") == 3

        await db.mark_read("mail:1", "user-1")
        assert await db.get_unread_count("user-1") == 2

        await db.archive("mail:2", "user-1")
        assert await db.get_unread_count("user-1") == 1

    @pytest.mark.asyncio
    async def test_unread_by_source(self, db: InboxDatabase):
        """get_unread_by_source should give per-source breakdown."""
        items = [
            _make_item(id="mail:1", source=InboxItemSource.MAIL),
            _make_item(id="mail:2", source=InboxItemSource.MAIL),
            _make_item(
                id="reminders:1",
                source=InboxItemSource.REMINDERS,
                item_type=InboxItemType.REMINDER,
            ),
            _make_item(
                id="calendar:1",
                source=InboxItemSource.CALENDAR,
                item_type=InboxItemType.CALENDAR,
            ),
        ]
        await db.upsert_items(items)

        by_source = await db.get_unread_by_source("user-1")
        assert by_source["mail"] == 2
        assert by_source["reminders"] == 1
        assert by_source["calendar"] == 1

    @pytest.mark.asyncio
    async def test_pagination(self, db: InboxDatabase):
        """Pagination with limit and offset should work correctly."""
        now = datetime.now(timezone.utc)
        items = [
            _make_item(
                id=f"mail:{i}",
                title=f"Item {i}",
                timestamp=now - timedelta(minutes=i),
            )
            for i in range(5)
        ]
        await db.upsert_items(items)

        # First page
        page1 = await db.get_items(user_id="user-1", limit=2, offset=0)
        assert len(page1) == 2
        assert page1[0].title == "Item 0"  # Most recent first

        # Second page
        page2 = await db.get_items(user_id="user-1", limit=2, offset=2)
        assert len(page2) == 2
        assert page2[0].title == "Item 2"

    @pytest.mark.asyncio
    async def test_cleanup_old_items(self, db: InboxDatabase):
        """cleanup_old_items should remove items older than retention period."""
        # Insert items with old cached_at
        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(days=60)).isoformat()
        recent_time = now.isoformat()

        # Manually insert with old cached_at
        await db.connection.execute(
            """INSERT INTO inbox_items
               (id, item_type, source, title, body, timestamp, priority,
                sender, sender_detail, has_attachments, icon, color, metadata, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("old:1", "email", "mail", "Old Item", None, None, "normal",
             None, None, 0, None, None, "{}", old_time),
        )
        await db.connection.execute(
            """INSERT INTO inbox_items
               (id, item_type, source, title, body, timestamp, priority,
                sender, sender_detail, has_attachments, icon, color, metadata, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("new:1", "email", "mail", "New Item", None, None, "normal",
             None, None, 0, None, None, "{}", recent_time),
        )
        await db.connection.commit()

        # Also add state for old item to verify orphan cleanup
        await db.mark_read("old:1", "user-1")

        deleted = await db.cleanup_old_items(retention_days=30)
        assert deleted == 1

        # Only the new item remains
        items = await db.get_items(user_id="user-1")
        assert len(items) == 1
        assert items[0].id == "new:1"

    @pytest.mark.asyncio
    async def test_get_item_not_found(self, db: InboxDatabase):
        """get_item should return None for non-existent items."""
        result = await db.get_item("nonexistent:1", "user-1")
        assert result is None

    @pytest.mark.asyncio
    async def test_source_filter(self, db: InboxDatabase):
        """get_items with source filter should only return matching items."""
        items = [
            _make_item(id="mail:1", source=InboxItemSource.MAIL),
            _make_item(
                id="reminders:1",
                source=InboxItemSource.REMINDERS,
                item_type=InboxItemType.REMINDER,
            ),
        ]
        await db.upsert_items(items)

        result = await db.get_items(
            user_id="user-1", source=InboxItemSource.MAIL
        )
        assert len(result) == 1
        assert result[0].id == "mail:1"

    @pytest.mark.asyncio
    async def test_upsert_empty_list(self, db: InboxDatabase):
        """Upserting empty list should return 0."""
        count = await db.upsert_items([])
        assert count == 0


# ===========================================================================
# TestInboxManager
# ===========================================================================

class TestInboxManager:
    """Tests for InboxManager with mocked Apple clients."""

    @pytest.fixture
    async def db(self, tmp_path: Path):
        """Create a test InboxDatabase."""
        db_path = tmp_path / "test_inbox_mgr.db"
        database = InboxDatabase(db_path=db_path)
        await database.initialize()
        yield database
        await database.close()

    @pytest.fixture
    def mock_mail(self):
        """Create a mock MailClient."""
        client = AsyncMock()
        client.get_recent_emails = AsyncMock(return_value=[])
        client.get_email = AsyncMock(return_value=None)
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def mock_reminders(self):
        """Create a mock RemindersClient."""
        client = AsyncMock()
        client.get_incomplete = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    def mock_calendar(self):
        """Create a mock CalendarClient."""
        client = AsyncMock()
        client.get_upcoming_events = AsyncMock(return_value=[])
        return client

    @pytest.fixture
    async def manager(self, db, mock_mail, mock_reminders, mock_calendar):
        """Create an InboxManager with mocked clients."""
        from hestia.inbox.manager import InboxManager
        mgr = InboxManager(database=db)
        await mgr.initialize()
        mgr._mail_client = mock_mail
        mgr._reminders_client = mock_reminders
        mgr._calendar_client = mock_calendar
        yield mgr
        await mgr.close()

    @pytest.mark.asyncio
    async def test_aggregate_mail(self, manager, mock_mail):
        """Mail aggregation should convert emails to InboxItems."""
        from hestia.apple.models import Email

        mock_mail.get_recent_emails.return_value = [
            Email(
                message_id="msg-001",
                subject="Hello",
                sender="Bob",
                sender_email="bob@example.com",
                recipients=[],
                date=datetime(2026, 3, 4, 10, 0, tzinfo=timezone.utc),
                snippet="Hi there",
                body=None,
                mailbox="INBOX",
                is_read=False,
                is_flagged=True,
                has_attachments=False,
            ),
        ]

        items = await manager._aggregate_mail()
        assert len(items) == 1
        assert items[0].id == "mail:msg-001"
        assert items[0].title == "Hello"
        assert items[0].sender == "Bob"
        assert items[0].sender_detail == "bob@example.com"
        assert items[0].icon == "envelope.fill"
        assert items[0].color == "#E0A050"
        assert items[0].priority == InboxItemPriority.HIGH  # flagged
        assert items[0].metadata["is_flagged"] is True

    @pytest.mark.asyncio
    async def test_aggregate_reminders(self, manager, mock_reminders):
        """Reminder aggregation should convert reminders to InboxItems."""
        from hestia.apple.models import Reminder

        mock_reminders.get_incomplete.return_value = [
            Reminder(
                id="rem-001",
                title="Buy groceries",
                list_name="Shopping",
                list_id="list-1",
                is_completed=False,
                priority=2,  # HIGH (1-4)
                due=datetime(2026, 3, 5, 12, 0, tzinfo=timezone.utc),
                notes="Milk, bread, eggs",
            ),
        ]

        items = await manager._aggregate_reminders()
        assert len(items) == 1
        assert items[0].id == "reminders:rem-001"
        assert items[0].title == "Buy groceries"
        assert items[0].priority == InboxItemPriority.HIGH
        assert items[0].icon == "checklist"
        assert items[0].metadata["list_name"] == "Shopping"

    @pytest.mark.asyncio
    async def test_aggregate_calendar(self, manager, mock_calendar):
        """Calendar aggregation should convert events to InboxItems."""
        from hestia.apple.models import Event

        start = datetime(2026, 3, 5, 14, 0, tzinfo=timezone.utc)
        end = datetime(2026, 3, 5, 15, 0, tzinfo=timezone.utc)

        mock_calendar.get_upcoming_events.return_value = [
            Event(
                id="evt-001",
                title="Team standup",
                calendar="Work",
                calendar_id="cal-1",
                start=start,
                end=end,
                is_all_day=False,
                location="Conference Room A",
                notes="Weekly sync",
            ),
        ]

        items = await manager._aggregate_calendar()
        assert len(items) == 1
        assert items[0].id == "calendar:evt-001"
        assert items[0].title == "Team standup"
        assert items[0].icon == "calendar"
        assert items[0].color == "#007AFF"
        assert items[0].metadata["calendar"] == "Work"
        assert items[0].metadata["location"] == "Conference Room A"

    @pytest.mark.asyncio
    async def test_error_resilience(self, manager, mock_mail, mock_reminders, mock_calendar):
        """One client failing should not block others."""
        from hestia.apple.models import Event

        mock_mail.get_recent_emails.side_effect = Exception("Mail DB offline")
        mock_reminders.get_incomplete.side_effect = Exception("CLI not found")
        mock_calendar.get_upcoming_events.return_value = [
            Event(
                id="evt-001",
                title="Surviving event",
                calendar="Work",
                calendar_id="cal-1",
                start=datetime.now(timezone.utc),
                end=datetime.now(timezone.utc) + timedelta(hours=1),
            ),
        ]

        count = await manager.refresh()
        assert count == 1  # Only calendar items

    @pytest.mark.asyncio
    async def test_cache_ttl(self, manager, mock_mail, mock_calendar, mock_reminders):
        """Second call within TTL should use cache (not re-aggregate)."""
        # First call triggers aggregation
        await manager.get_inbox(user_id="user-1")
        assert mock_mail.get_recent_emails.call_count == 1

        # Second call within TTL should not re-aggregate
        await manager.get_inbox(user_id="user-1")
        assert mock_mail.get_recent_emails.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_stale_triggers_refresh(self, manager, mock_mail, mock_calendar, mock_reminders):
        """Call after cache expires should trigger fresh aggregation."""
        # First call
        await manager.get_inbox(user_id="user-1")
        assert mock_mail.get_recent_emails.call_count == 1

        # Force cache to be stale
        manager._last_refresh = time.time() - 60

        # Should re-aggregate
        await manager.get_inbox(user_id="user-1")
        assert mock_mail.get_recent_emails.call_count == 2

    @pytest.mark.asyncio
    async def test_source_filtering(self, manager, mock_mail, mock_reminders, mock_calendar):
        """Source filter should only return items from that source."""
        from hestia.apple.models import Email, Reminder

        mock_mail.get_recent_emails.return_value = [
            Email(
                message_id="msg-1",
                subject="Email 1",
                sender="Bob",
                sender_email="bob@test.com",
                recipients=[],
                date=datetime.now(timezone.utc),
            ),
        ]
        mock_reminders.get_incomplete.return_value = [
            Reminder(
                id="rem-1",
                title="Reminder 1",
                list_name="Default",
                list_id="list-1",
            ),
        ]

        all_items = await manager.get_inbox(user_id="user-1")
        assert len(all_items) == 2

        mail_only = await manager.get_inbox(
            user_id="user-1", source=InboxItemSource.MAIL
        )
        assert len(mail_only) == 1
        assert mail_only[0].source == InboxItemSource.MAIL

    @pytest.mark.asyncio
    async def test_get_item_with_email_body_lazy_load(self, manager, mock_mail, db):
        """get_item for email should lazy-load body from MailClient."""
        from hestia.apple.models import Email

        # Insert an email item with no body
        item = _make_item(
            id="mail:msg-lazy",
            body=None,
            source=InboxItemSource.MAIL,
        )
        await db.upsert_items([item])

        # Mock get_email to return body
        mock_mail.get_email.return_value = Email(
            message_id="msg-lazy",
            subject="Test",
            sender="Alice",
            sender_email="alice@test.com",
            recipients=[],
            body="Full email body content here",
        )

        result = await manager.get_item("mail:msg-lazy", "user-1")
        assert result is not None
        assert result.body == "Full email body content here"
        mock_mail.get_email.assert_called_once_with("msg-lazy")

    @pytest.mark.asyncio
    async def test_mark_read_delegates_to_database(self, manager, db):
        """mark_read should update the database state."""
        await db.upsert_items([_make_item(id="mail:mr-1")])

        success = await manager.mark_read("mail:mr-1", "user-1")
        assert success is True

        item = await db.get_item("mail:mr-1", "user-1")
        assert item.is_read is True

    @pytest.mark.asyncio
    async def test_refresh_forces_reaggregate(self, manager, mock_mail):
        """refresh() should force re-aggregation regardless of cache state."""
        # Initialize cache
        await manager.refresh()
        initial_count = mock_mail.get_recent_emails.call_count

        # Immediately refresh (within TTL)
        await manager.refresh()
        assert mock_mail.get_recent_emails.call_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_reminder_priority_mapping(self, manager, mock_reminders):
        """Reminder priorities should map correctly from Apple values."""
        from hestia.apple.models import Reminder

        mock_reminders.get_incomplete.return_value = [
            Reminder(id="r1", title="High", list_name="L", list_id="l1", priority=1),
            Reminder(id="r2", title="Normal", list_name="L", list_id="l1", priority=5),
            Reminder(id="r3", title="Low", list_name="L", list_id="l1", priority=7),
            Reminder(id="r4", title="None", list_name="L", list_id="l1", priority=0),
        ]

        items = await manager._aggregate_reminders()
        priority_map = {i.title: i.priority for i in items}
        assert priority_map["High"] == InboxItemPriority.HIGH
        assert priority_map["Normal"] == InboxItemPriority.NORMAL
        assert priority_map["Low"] == InboxItemPriority.LOW
        assert priority_map["None"] == InboxItemPriority.NORMAL

    @pytest.mark.asyncio
    async def test_unread_by_source(self, manager, mock_mail, mock_reminders, mock_calendar, db):
        """get_unread_by_source should return per-source counts."""
        items = [
            _make_item(id="mail:1", source=InboxItemSource.MAIL),
            _make_item(id="mail:2", source=InboxItemSource.MAIL),
            _make_item(
                id="reminders:1",
                source=InboxItemSource.REMINDERS,
                item_type=InboxItemType.REMINDER,
            ),
        ]
        await db.upsert_items(items)

        by_source = await manager.get_unread_by_source("user-1")
        assert by_source["mail"] == 2
        assert by_source["reminders"] == 1


# ===========================================================================
# TestInboxRoutes
# ===========================================================================

from fastapi import FastAPI
from fastapi.testclient import TestClient

from hestia.api.routes.inbox import router as inbox_router_instance


class TestInboxRoutes:
    """Tests for /v1/inbox API routes using mocked InboxManager."""

    @pytest.fixture
    def mock_mgr(self):
        """Create a mock InboxManager."""
        return AsyncMock()

    @pytest.fixture
    def client(self, mock_mgr):
        """Build a TestClient with the inbox router and mocked manager."""
        app = FastAPI()
        app.include_router(inbox_router_instance)

        from hestia.api.middleware.auth import get_device_token
        app.dependency_overrides[get_device_token] = lambda: "test-device-id"

        with mock_patch(
            "hestia.api.routes.inbox.get_inbox_manager",
            return_value=mock_mgr,
        ):
            yield TestClient(app)

    # ---- 1. List inbox ----

    def test_list_inbox_success(self, mock_mgr, client):
        """GET /v1/inbox should return items list."""
        mock_mgr.get_inbox.return_value = [
            _make_item(id="mail:1", title="Email 1"),
            _make_item(id="reminders:1", title="Reminder 1"),
        ]
        mock_mgr.get_unread_count.return_value = 2

        resp = client.get("/v1/inbox")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert body["unread_count"] == 2
        assert len(body["items"]) == 2

    def test_list_inbox_with_source_filter(self, mock_mgr, client):
        """GET /v1/inbox?source=mail should filter by source."""
        mock_mgr.get_inbox.return_value = [
            _make_item(id="mail:1", title="Email 1"),
        ]
        mock_mgr.get_unread_count.return_value = 1

        resp = client.get("/v1/inbox?source=mail")
        assert resp.status_code == 200
        assert resp.json()["count"] == 1

    def test_list_inbox_invalid_source(self, mock_mgr, client):
        """GET /v1/inbox?source=invalid should return 400."""
        resp = client.get("/v1/inbox?source=invalid")
        assert resp.status_code == 400

    # ---- 2. Unread count ----

    def test_unread_count_success(self, mock_mgr, client):
        """GET /v1/inbox/unread-count should return counts."""
        mock_mgr.get_unread_count.return_value = 5
        mock_mgr.get_unread_by_source.return_value = {"mail": 3, "reminders": 2}

        resp = client.get("/v1/inbox/unread-count")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 5
        assert body["by_source"]["mail"] == 3
        assert body["by_source"]["reminders"] == 2

    # ---- 3. Get item ----

    def test_get_item_success(self, mock_mgr, client):
        """GET /v1/inbox/{item_id} should return the item."""
        mock_mgr.get_item.return_value = _make_item(
            id="mail:1", title="Test Email", body="Full body"
        )

        resp = client.get("/v1/inbox/mail:1")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "mail:1"
        assert body["title"] == "Test Email"
        assert body["body"] == "Full body"

    def test_get_item_not_found(self, mock_mgr, client):
        """GET /v1/inbox/{item_id} for non-existent item should return 404."""
        mock_mgr.get_item.return_value = None

        resp = client.get("/v1/inbox/nonexistent:1")
        assert resp.status_code == 404

    # ---- 4. Mark read ----

    def test_mark_read_success(self, mock_mgr, client):
        """POST /v1/inbox/{item_id}/read should mark as read."""
        mock_mgr.mark_read.return_value = True

        resp = client.post("/v1/inbox/mail:1/read")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["item_id"] == "mail:1"

    # ---- 5. Mark all read ----

    def test_mark_all_read_success(self, mock_mgr, client):
        """POST /v1/inbox/mark-all-read should mark all items as read."""
        mock_mgr.mark_all_read.return_value = 5

        resp = client.post("/v1/inbox/mark-all-read")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["count"] == 5

    # ---- 6. Archive ----

    def test_archive_success(self, mock_mgr, client):
        """POST /v1/inbox/{item_id}/archive should archive the item."""
        mock_mgr.archive.return_value = True

        resp = client.post("/v1/inbox/mail:1/archive")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["item_id"] == "mail:1"

    # ---- 7. Refresh ----

    def test_refresh_success(self, mock_mgr, client):
        """POST /v1/inbox/refresh should force re-aggregate."""
        mock_mgr.refresh.return_value = 10

        # Reset rate limit state for tests
        from hestia.api.routes.inbox import _refresh_timestamps
        _refresh_timestamps.clear()

        resp = client.post("/v1/inbox/refresh")
        assert resp.status_code == 200
        body = resp.json()
        assert body["items_refreshed"] == 10

    def test_refresh_rate_limited(self, mock_mgr, client):
        """POST /v1/inbox/refresh twice quickly should be rate limited."""
        mock_mgr.refresh.return_value = 10

        from hestia.api.routes.inbox import _refresh_timestamps
        _refresh_timestamps.clear()

        resp1 = client.post("/v1/inbox/refresh")
        assert resp1.status_code == 200

        resp2 = client.post("/v1/inbox/refresh")
        assert resp2.status_code == 429
