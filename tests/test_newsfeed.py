"""
Tests for Hestia Newsfeed module.

Materialized timeline, read/dismiss state, aggregation engine, API routes.

Run with: python -m pytest tests/test_newsfeed.py -v
"""

import asyncio
import json
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from hestia.newsfeed.models import (
    NewsfeedItem,
    NewsfeedItemPriority,
    NewsfeedItemSource,
    NewsfeedItemType,
)
from hestia.newsfeed.database import NewsfeedDatabase
from hestia.newsfeed.manager import NewsfeedManager


# ============== Fixtures ==============


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> NewsfeedDatabase:
    """Create a test database."""
    db = NewsfeedDatabase(db_path=temp_dir / "test_newsfeed.db")
    await db.initialize()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(database: NewsfeedDatabase) -> NewsfeedManager:
    """Create a manager with injected database (no source managers)."""
    mgr = NewsfeedManager(database=database)
    # Skip initialize() which would try to import source managers
    mgr._database = database
    mgr._last_refresh = 0.0
    return mgr


@pytest.fixture
def sample_item() -> NewsfeedItem:
    """Create a sample newsfeed item."""
    return NewsfeedItem(
        id="order_exec:exec-abc123",
        item_type=NewsfeedItemType.ORDER_EXECUTION,
        source=NewsfeedItemSource.ORDERS,
        title="Order: Morning Briefing",
        body="Briefing executed successfully",
        timestamp=datetime(2026, 3, 1, 8, 0, tzinfo=timezone.utc),
        priority=NewsfeedItemPriority.NORMAL,
        icon="checkmark.circle",
        color="#34C759",
        action_type="order",
        action_id="order-abc123",
        metadata={"status": "success", "duration_ms": "1234"},
    )


@pytest.fixture
def sample_items() -> List[NewsfeedItem]:
    """Create multiple sample items for testing."""
    now = datetime.now(timezone.utc)
    return [
        NewsfeedItem(
            id="order_exec:exec-001",
            item_type=NewsfeedItemType.ORDER_EXECUTION,
            source=NewsfeedItemSource.ORDERS,
            title="Order: Morning Briefing",
            body="Success",
            timestamp=now - timedelta(hours=1),
            priority=NewsfeedItemPriority.NORMAL,
            icon="checkmark.circle",
            color="#34C759",
        ),
        NewsfeedItem(
            id="memory:chunk-002",
            item_type=NewsfeedItemType.MEMORY_REVIEW,
            source=NewsfeedItemSource.MEMORY,
            title="Memory pending review",
            body="Important conversation about architecture",
            timestamp=now - timedelta(hours=2),
            priority=NewsfeedItemPriority.NORMAL,
            icon="brain",
            color="#AF52DE",
        ),
        NewsfeedItem(
            id="task:task-003",
            item_type=NewsfeedItemType.TASK_UPDATE,
            source=NewsfeedItemSource.TASKS,
            title="Deploy to production",
            body=None,
            timestamp=now - timedelta(hours=3),
            priority=NewsfeedItemPriority.HIGH,
            icon="exclamationmark.circle",
            color="#FF9500",
        ),
        NewsfeedItem(
            id="health:daily:2026-03-01",
            item_type=NewsfeedItemType.HEALTH_INSIGHT,
            source=NewsfeedItemSource.HEALTH,
            title="Daily health summary",
            body="Steps: 8,432 | Sleep: 7.2h",
            timestamp=now - timedelta(hours=4),
            priority=NewsfeedItemPriority.LOW,
            icon="heart.fill",
            color="#FF2D55",
        ),
    ]


# ============== Model Tests ==============


class TestNewsfeedItem:
    """Tests for NewsfeedItem model."""

    def test_to_dict(self, sample_item: NewsfeedItem):
        """Item serializes to dict correctly."""
        d = sample_item.to_dict()
        assert d["id"] == "order_exec:exec-abc123"
        assert d["item_type"] == "order_execution"
        assert d["source"] == "orders"
        assert d["title"] == "Order: Morning Briefing"
        assert d["priority"] == "normal"
        assert d["icon"] == "checkmark.circle"
        assert d["action_type"] == "order"
        assert d["action_id"] == "order-abc123"
        assert d["metadata"]["status"] == "success"
        assert d["is_read"] is False
        assert d["is_dismissed"] is False

    def test_from_dict_roundtrip(self, sample_item: NewsfeedItem):
        """Item survives dict roundtrip."""
        d = sample_item.to_dict()
        restored = NewsfeedItem.from_dict(d)
        assert restored.id == sample_item.id
        assert restored.item_type == sample_item.item_type
        assert restored.source == sample_item.source
        assert restored.title == sample_item.title
        assert restored.priority == sample_item.priority
        assert restored.metadata == sample_item.metadata

    def test_from_dict_missing_optional(self):
        """Item handles missing optional fields."""
        d = {
            "id": "test:001",
            "item_type": "system_alert",
            "source": "system",
            "title": "System message",
        }
        item = NewsfeedItem.from_dict(d)
        assert item.body is None
        assert item.timestamp is None
        assert item.priority == NewsfeedItemPriority.NORMAL
        assert item.icon is None
        assert item.metadata == {}
        assert item.is_read is False
        assert item.is_dismissed is False

    def test_from_dict_with_read_dismissed(self):
        """Item preserves read/dismissed state from dict."""
        d = {
            "id": "test:002",
            "item_type": "task_update",
            "source": "tasks",
            "title": "Task done",
            "is_read": True,
            "is_dismissed": True,
        }
        item = NewsfeedItem.from_dict(d)
        assert item.is_read is True
        assert item.is_dismissed is True

    def test_item_types(self):
        """All item types are valid."""
        assert NewsfeedItemType.ORDER_EXECUTION.value == "order_execution"
        assert NewsfeedItemType.MEMORY_REVIEW.value == "memory_review"
        assert NewsfeedItemType.TASK_UPDATE.value == "task_update"
        assert NewsfeedItemType.HEALTH_INSIGHT.value == "health_insight"
        assert NewsfeedItemType.CALENDAR_EVENT.value == "calendar_event"
        assert NewsfeedItemType.SYSTEM_ALERT.value == "system_alert"

    def test_item_sources(self):
        """All item sources are valid."""
        assert NewsfeedItemSource.ORDERS.value == "orders"
        assert NewsfeedItemSource.MEMORY.value == "memory"
        assert NewsfeedItemSource.TASKS.value == "tasks"
        assert NewsfeedItemSource.HEALTH.value == "health"
        assert NewsfeedItemSource.CALENDAR.value == "calendar"
        assert NewsfeedItemSource.SYSTEM.value == "system"

    def test_priorities(self):
        """All priority levels are valid."""
        assert NewsfeedItemPriority.LOW.value == "low"
        assert NewsfeedItemPriority.NORMAL.value == "normal"
        assert NewsfeedItemPriority.HIGH.value == "high"
        assert NewsfeedItemPriority.URGENT.value == "urgent"

    def test_default_values(self):
        """Item has correct defaults."""
        item = NewsfeedItem(
            id="test:defaults",
            item_type=NewsfeedItemType.SYSTEM_ALERT,
            source=NewsfeedItemSource.SYSTEM,
            title="Test",
        )
        assert item.priority == NewsfeedItemPriority.NORMAL
        assert item.metadata == {}
        assert item.is_read is False
        assert item.is_dismissed is False
        assert item.body is None
        assert item.timestamp is None


# ============== Database Tests ==============


class TestNewsfeedDatabase:
    """Tests for NewsfeedDatabase CRUD and state management."""

    @pytest.mark.asyncio
    async def test_upsert_items(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Upsert stores items correctly."""
        count = await database.upsert_items(sample_items)
        assert count == 4

    @pytest.mark.asyncio
    async def test_upsert_empty_list(self, database: NewsfeedDatabase):
        """Upsert with empty list returns 0."""
        count = await database.upsert_items([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_upsert_replaces_existing(self, database: NewsfeedDatabase):
        """Upsert replaces items with same ID."""
        item = NewsfeedItem(
            id="test:replace",
            item_type=NewsfeedItemType.SYSTEM_ALERT,
            source=NewsfeedItemSource.SYSTEM,
            title="Original title",
            timestamp=datetime.now(timezone.utc),
        )
        await database.upsert_items([item])

        item.title = "Updated title"
        await database.upsert_items([item])

        items = await database.get_items(user_id="user-default")
        assert len(items) == 1
        assert items[0].title == "Updated title"

    @pytest.mark.asyncio
    async def test_get_items_basic(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Get items returns all items ordered by timestamp DESC."""
        await database.upsert_items(sample_items)
        items = await database.get_items(user_id="user-default")
        assert len(items) == 4
        # Most recent first
        assert items[0].id == "order_exec:exec-001"

    @pytest.mark.asyncio
    async def test_get_items_filter_by_type(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Get items filters by item_type."""
        await database.upsert_items(sample_items)
        items = await database.get_items(
            user_id="user-default",
            item_type=NewsfeedItemType.ORDER_EXECUTION,
        )
        assert len(items) == 1
        assert items[0].item_type == NewsfeedItemType.ORDER_EXECUTION

    @pytest.mark.asyncio
    async def test_get_items_filter_by_source(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Get items filters by source."""
        await database.upsert_items(sample_items)
        items = await database.get_items(
            user_id="user-default",
            source=NewsfeedItemSource.HEALTH,
        )
        assert len(items) == 1
        assert items[0].source == NewsfeedItemSource.HEALTH

    @pytest.mark.asyncio
    async def test_get_items_pagination(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Get items respects limit and offset."""
        await database.upsert_items(sample_items)

        page1 = await database.get_items(user_id="user-default", limit=2, offset=0)
        assert len(page1) == 2

        page2 = await database.get_items(user_id="user-default", limit=2, offset=2)
        assert len(page2) == 2

        page3 = await database.get_items(user_id="user-default", limit=2, offset=4)
        assert len(page3) == 0

    @pytest.mark.asyncio
    async def test_mark_read(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Mark read sets is_read on retrieval."""
        await database.upsert_items(sample_items)
        await database.mark_read("order_exec:exec-001", "user-default", "device-1")

        items = await database.get_items(user_id="user-default")
        read_item = next(i for i in items if i.id == "order_exec:exec-001")
        assert read_item.is_read is True

        # Others remain unread
        unread = [i for i in items if not i.is_read]
        assert len(unread) == 3

    @pytest.mark.asyncio
    async def test_mark_dismissed(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Dismissed items hidden by default, shown with include_dismissed."""
        await database.upsert_items(sample_items)
        await database.mark_dismissed("task:task-003", "user-default")

        # Default: dismissed items hidden
        items = await database.get_items(user_id="user-default")
        ids = [i.id for i in items]
        assert "task:task-003" not in ids

        # With include_dismissed
        items_all = await database.get_items(
            user_id="user-default",
            include_dismissed=True,
        )
        ids_all = [i.id for i in items_all]
        assert "task:task-003" in ids_all
        dismissed = next(i for i in items_all if i.id == "task:task-003")
        assert dismissed.is_dismissed is True

    @pytest.mark.asyncio
    async def test_get_unread_count(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Unread count reflects read/dismiss state."""
        await database.upsert_items(sample_items)

        # All 4 are unread initially
        count = await database.get_unread_count("user-default")
        assert count == 4

        # Mark one read — still counts as unread? No: read items are no longer unread
        await database.mark_read("order_exec:exec-001", "user-default")
        count = await database.get_unread_count("user-default")
        assert count == 3

        # Dismiss one
        await database.mark_dismissed("task:task-003", "user-default")
        count = await database.get_unread_count("user-default")
        assert count == 2

    @pytest.mark.asyncio
    async def test_get_unread_count_by_type(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Unread count can be filtered by type."""
        await database.upsert_items(sample_items)

        order_count = await database.get_unread_count(
            "user-default",
            item_type=NewsfeedItemType.ORDER_EXECUTION,
        )
        assert order_count == 1

        health_count = await database.get_unread_count(
            "user-default",
            item_type=NewsfeedItemType.HEALTH_INSIGHT,
        )
        assert health_count == 1

    @pytest.mark.asyncio
    async def test_multi_user_state(self, database: NewsfeedDatabase, sample_items: List[NewsfeedItem]):
        """Read state is per-user — user A reading doesn't affect user B."""
        await database.upsert_items(sample_items)

        await database.mark_read("order_exec:exec-001", "user-A")

        # User A sees it as read
        items_a = await database.get_items(user_id="user-A")
        read_a = next(i for i in items_a if i.id == "order_exec:exec-001")
        assert read_a.is_read is True

        # User B still sees it as unread
        items_b = await database.get_items(user_id="user-B")
        read_b = next(i for i in items_b if i.id == "order_exec:exec-001")
        assert read_b.is_read is False

    @pytest.mark.asyncio
    async def test_cleanup_old_items(self, database: NewsfeedDatabase):
        """Cleanup removes items older than threshold."""
        assert database._connection is not None

        # Insert an old item directly with old cached_at
        old_cached_at = time.time() - (31 * 86400)  # 31 days ago
        await database._connection.execute(
            """INSERT INTO newsfeed_items
               (id, item_type, source, title, timestamp, priority, metadata, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("old:item", "system_alert", "system", "Old alert",
             "2026-01-01T00:00:00", "low", "{}", old_cached_at),
        )

        # Insert a recent item
        recent_cached_at = time.time()
        await database._connection.execute(
            """INSERT INTO newsfeed_items
               (id, item_type, source, title, timestamp, priority, metadata, cached_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("new:item", "system_alert", "system", "New alert",
             "2026-03-01T00:00:00", "low", "{}", recent_cached_at),
        )
        await database._connection.commit()

        deleted = await database.cleanup_old_items(days=30)
        assert deleted == 1

        items = await database.get_items(user_id="user-default")
        assert len(items) == 1
        assert items[0].id == "new:item"


# ============== Manager Tests ==============


class TestNewsfeedManager:
    """Tests for NewsfeedManager aggregation and state operations."""

    @pytest.mark.asyncio
    async def test_get_timeline_empty(self, manager: NewsfeedManager):
        """Empty timeline returns empty list."""
        # Force refresh to avoid stale check trying to import source managers
        manager._last_refresh = time.time()
        items = await manager.get_timeline(user_id="user-default")
        assert items == []

    @pytest.mark.asyncio
    async def test_mark_read_and_retrieve(
        self, manager: NewsfeedManager, sample_items: List[NewsfeedItem]
    ):
        """Mark read propagates through get_timeline."""
        await manager._database.upsert_items(sample_items)
        manager._last_refresh = time.time()  # Skip aggregation

        await manager.mark_read("order_exec:exec-001", "user-default", "dev-1")

        items = await manager.get_timeline(user_id="user-default")
        read_item = next(i for i in items if i.id == "order_exec:exec-001")
        assert read_item.is_read is True

    @pytest.mark.asyncio
    async def test_mark_dismissed_hides_item(
        self, manager: NewsfeedManager, sample_items: List[NewsfeedItem]
    ):
        """Dismissed items are hidden from default timeline."""
        await manager._database.upsert_items(sample_items)
        manager._last_refresh = time.time()

        await manager.mark_dismissed("task:task-003", "user-default")

        items = await manager.get_timeline(user_id="user-default")
        ids = [i.id for i in items]
        assert "task:task-003" not in ids

    @pytest.mark.asyncio
    async def test_get_unread_count(
        self, manager: NewsfeedManager, sample_items: List[NewsfeedItem]
    ):
        """Unread count works through manager."""
        await manager._database.upsert_items(sample_items)

        count = await manager.get_unread_count("user-default")
        assert count == 4

    @pytest.mark.asyncio
    async def test_cache_staleness(self, manager: NewsfeedManager):
        """Manager detects stale cache correctly."""
        manager._last_refresh = 0.0
        assert manager._is_cache_stale() is True

        manager._last_refresh = time.time()
        assert manager._is_cache_stale() is False

        manager._last_refresh = time.time() - 31
        assert manager._is_cache_stale() is True

    @pytest.mark.asyncio
    async def test_aggregate_order_executions(self, manager: NewsfeedManager):
        """Order execution aggregator produces correct items."""
        mock_order_mgr = AsyncMock()
        mock_order_mgr.list_recent_executions = AsyncMock(return_value=[
            {
                "id": "exec-test1",
                "order_id": "order-123",
                "order_name": "Morning Briefing",
                "timestamp": "2026-03-01T08:00:00+00:00",
                "status": "success",
                "hestia_read": "Briefing delivered",
                "duration_ms": 1234,
            },
            {
                "id": "exec-test2",
                "order_id": "order-456",
                "order_name": "News Digest",
                "timestamp": "2026-03-01T09:00:00+00:00",
                "status": "failed",
                "error_message": "Timeout",
                "duration_ms": 5000,
            },
        ])

        with patch("hestia.newsfeed.manager.get_order_manager", new_callable=AsyncMock, return_value=mock_order_mgr):
            items = await manager._aggregate_order_executions()

        assert len(items) == 2

        success = next(i for i in items if "exec-test1" in i.id)
        assert success.priority == NewsfeedItemPriority.NORMAL
        assert success.color == "#34C759"
        assert "Morning Briefing" in success.title

        failed = next(i for i in items if "exec-test2" in i.id)
        assert failed.priority == NewsfeedItemPriority.HIGH
        assert failed.color == "#FF3B30"
        assert failed.body == "Timeout"

    @pytest.mark.asyncio
    async def test_aggregate_memory_reviews(self, manager: NewsfeedManager):
        """Memory review aggregator produces correct items."""
        mock_chunk = MagicMock()
        mock_chunk.id = "chunk-abc"
        mock_chunk.content = "User discussed Python async patterns"
        mock_chunk.tags = ["python", "async"]
        mock_chunk.to_dict = MagicMock(return_value={
            "id": "chunk-abc",
            "content": "User discussed Python async patterns",
            "tags": ["python", "async"],
        })

        mock_memory_mgr = AsyncMock()
        mock_memory_mgr.get_pending_reviews = AsyncMock(return_value=[mock_chunk])

        with patch("hestia.newsfeed.manager.get_memory_manager", new_callable=AsyncMock, return_value=mock_memory_mgr):
            items = await manager._aggregate_memory_reviews()

        assert len(items) == 1
        assert items[0].item_type == NewsfeedItemType.MEMORY_REVIEW
        assert "chunk-abc" in items[0].id
        assert items[0].icon == "brain"

    @pytest.mark.asyncio
    async def test_aggregate_task_updates(self, manager: NewsfeedManager):
        """Task aggregator produces correct items and skips terminal tasks."""
        mock_task_pending = MagicMock()
        mock_task_pending.to_dict = MagicMock(return_value={
            "id": "task-001",
            "description": "Pending deploy",
            "status": "pending_approval",
            "requires_approval": True,
            "created_at": "2026-03-01T10:00:00",
            "result": None,
        })

        mock_task_completed = MagicMock()
        mock_task_completed.to_dict = MagicMock(return_value={
            "id": "task-002",
            "description": "Done task",
            "status": "completed",
            "requires_approval": False,
            "created_at": "2026-03-01T09:00:00",
            "result": "Done",
        })

        mock_task_mgr = AsyncMock()
        mock_task_mgr.list_tasks = AsyncMock(return_value=[mock_task_pending, mock_task_completed])

        with patch("hestia.newsfeed.manager.get_task_manager", new_callable=AsyncMock, return_value=mock_task_mgr):
            items = await manager._aggregate_task_updates()

        # Only the pending task should appear (completed is filtered)
        assert len(items) == 1
        assert items[0].action_id == "task-001"
        assert items[0].priority == NewsfeedItemPriority.HIGH

    @pytest.mark.asyncio
    async def test_aggregate_health_insights(self, manager: NewsfeedManager):
        """Health aggregator produces daily summary item."""
        mock_health_mgr = AsyncMock()
        mock_health_mgr.get_daily_summary = AsyncMock(return_value={
            "summary": "Steps: 8,432 | Sleep: 7.2h",
            "date": "2026-03-01",
        })

        with patch("hestia.newsfeed.manager.get_health_manager", new_callable=AsyncMock, return_value=mock_health_mgr):
            items = await manager._aggregate_health_insights()

        assert len(items) == 1
        assert items[0].item_type == NewsfeedItemType.HEALTH_INSIGHT
        assert items[0].icon == "heart.fill"

    @pytest.mark.asyncio
    async def test_aggregate_all_resilience(self, manager: NewsfeedManager):
        """One aggregator failing doesn't block others."""
        # Orders fails
        mock_order_mgr = AsyncMock()
        mock_order_mgr.list_recent_executions = AsyncMock(
            side_effect=Exception("DB connection lost")
        )

        # Memory succeeds
        mock_memory_mgr = AsyncMock()
        mock_memory_mgr.get_pending_reviews = AsyncMock(return_value=[])

        # Tasks succeeds
        mock_task_mgr = AsyncMock()
        mock_task_mgr.list_tasks = AsyncMock(return_value=[])

        # Health succeeds
        mock_health_mgr = AsyncMock()
        mock_health_mgr.get_daily_summary = AsyncMock(return_value=None)

        with patch("hestia.newsfeed.manager.get_order_manager", new_callable=AsyncMock, return_value=mock_order_mgr), \
             patch("hestia.newsfeed.manager.get_memory_manager", new_callable=AsyncMock, return_value=mock_memory_mgr), \
             patch("hestia.newsfeed.manager.get_task_manager", new_callable=AsyncMock, return_value=mock_task_mgr), \
             patch("hestia.newsfeed.manager.get_health_manager", new_callable=AsyncMock, return_value=mock_health_mgr):
            count = await manager._aggregate_all()

        # Should succeed despite orders failure
        assert count == 0  # No items from any source
        assert manager._last_refresh > 0

    @pytest.mark.asyncio
    async def test_refresh_updates_cache(self, manager: NewsfeedManager):
        """Refresh forces re-aggregation and updates timestamp."""
        mock_order_mgr = AsyncMock()
        mock_order_mgr.list_recent_executions = AsyncMock(return_value=[])
        mock_memory_mgr = AsyncMock()
        mock_memory_mgr.get_pending_reviews = AsyncMock(return_value=[])
        mock_task_mgr = AsyncMock()
        mock_task_mgr.list_tasks = AsyncMock(return_value=[])
        mock_health_mgr = AsyncMock()
        mock_health_mgr.get_daily_summary = AsyncMock(return_value=None)

        with patch("hestia.newsfeed.manager.get_order_manager", new_callable=AsyncMock, return_value=mock_order_mgr), \
             patch("hestia.newsfeed.manager.get_memory_manager", new_callable=AsyncMock, return_value=mock_memory_mgr), \
             patch("hestia.newsfeed.manager.get_task_manager", new_callable=AsyncMock, return_value=mock_task_mgr), \
             patch("hestia.newsfeed.manager.get_health_manager", new_callable=AsyncMock, return_value=mock_health_mgr):
            before = manager._last_refresh
            await manager.refresh()
            assert manager._last_refresh > before

    @pytest.mark.asyncio
    async def test_timeline_filter_by_type(
        self, manager: NewsfeedManager, sample_items: List[NewsfeedItem]
    ):
        """Timeline filters by item_type."""
        await manager._database.upsert_items(sample_items)
        manager._last_refresh = time.time()

        items = await manager.get_timeline(
            user_id="user-default",
            item_type=NewsfeedItemType.HEALTH_INSIGHT,
        )
        assert len(items) == 1
        assert items[0].item_type == NewsfeedItemType.HEALTH_INSIGHT

    @pytest.mark.asyncio
    async def test_timeline_filter_by_source(
        self, manager: NewsfeedManager, sample_items: List[NewsfeedItem]
    ):
        """Timeline filters by source."""
        await manager._database.upsert_items(sample_items)
        manager._last_refresh = time.time()

        items = await manager.get_timeline(
            user_id="user-default",
            source=NewsfeedItemSource.ORDERS,
        )
        assert len(items) == 1
        assert items[0].source == NewsfeedItemSource.ORDERS


# ============== Route Tests ==============


class TestNewsfeedRoutes:
    """Tests for newsfeed API endpoints."""

    def _make_app(self, mock_manager):
        """Create a test FastAPI app with auth override and mocked manager."""
        from fastapi import FastAPI
        from hestia.api.routes.newsfeed import router
        from hestia.api.middleware.auth import get_device_token

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_device_token] = lambda: "test-device-123"

        return app, mock_manager

    @pytest.fixture
    def mock_manager(self):
        """Mock newsfeed manager."""
        mock_mgr = AsyncMock()
        mock_mgr.get_timeline = AsyncMock(return_value=[])
        mock_mgr.get_unread_count = AsyncMock(return_value=0)
        mock_mgr.mark_read = AsyncMock(return_value=True)
        mock_mgr.mark_dismissed = AsyncMock(return_value=True)
        mock_mgr.refresh = AsyncMock(return_value=5)
        return mock_mgr

    @pytest.mark.asyncio
    async def test_timeline_endpoint(self, mock_manager):
        """GET /v1/newsfeed/timeline returns items."""
        from fastapi.testclient import TestClient
        app, _ = self._make_app(mock_manager)

        with patch("hestia.api.routes.newsfeed.get_newsfeed_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/newsfeed/timeline")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "count" in data
        assert "unread_count" in data

    @pytest.mark.asyncio
    async def test_timeline_invalid_type(self, mock_manager):
        """GET /v1/newsfeed/timeline rejects invalid type filter."""
        from fastapi.testclient import TestClient
        app, _ = self._make_app(mock_manager)

        with patch("hestia.api.routes.newsfeed.get_newsfeed_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/newsfeed/timeline?type=invalid_type")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_unread_count_endpoint(self, mock_manager):
        """GET /v1/newsfeed/unread-count returns counts."""
        from fastapi.testclient import TestClient
        app, _ = self._make_app(mock_manager)

        with patch("hestia.api.routes.newsfeed.get_newsfeed_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/newsfeed/unread-count")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_type" in data

    @pytest.mark.asyncio
    async def test_mark_read_endpoint(self, mock_manager):
        """POST /v1/newsfeed/items/{id}/read marks item."""
        from fastapi.testclient import TestClient
        app, _ = self._make_app(mock_manager)

        with patch("hestia.api.routes.newsfeed.get_newsfeed_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.post("/v1/newsfeed/items/test-item-1/read")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["item_id"] == "test-item-1"

    @pytest.mark.asyncio
    async def test_dismiss_endpoint(self, mock_manager):
        """POST /v1/newsfeed/items/{id}/dismiss dismisses item."""
        from fastapi.testclient import TestClient
        app, _ = self._make_app(mock_manager)

        with patch("hestia.api.routes.newsfeed.get_newsfeed_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.post("/v1/newsfeed/items/test-item-2/dismiss")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_refresh_endpoint(self, mock_manager):
        """POST /v1/newsfeed/refresh triggers re-aggregation."""
        from fastapi.testclient import TestClient
        from hestia.api.routes.newsfeed import _refresh_timestamps

        app, _ = self._make_app(mock_manager)
        _refresh_timestamps.clear()

        with patch("hestia.api.routes.newsfeed.get_newsfeed_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.post("/v1/newsfeed/refresh")

        assert response.status_code == 200
        data = response.json()
        assert data["items_refreshed"] == 5

    @pytest.mark.asyncio
    async def test_refresh_rate_limit(self, mock_manager):
        """POST /v1/newsfeed/refresh rate-limited to 1/10s."""
        from fastapi.testclient import TestClient
        from hestia.api.routes.newsfeed import _refresh_timestamps

        app, _ = self._make_app(mock_manager)
        _refresh_timestamps.clear()

        with patch("hestia.api.routes.newsfeed.get_newsfeed_manager", return_value=mock_manager):
            client = TestClient(app)

            # First request succeeds
            r1 = client.post("/v1/newsfeed/refresh")
            assert r1.status_code == 200

            # Second request within 10s should be rate-limited
            r2 = client.post("/v1/newsfeed/refresh")
            assert r2.status_code == 429

    @pytest.mark.asyncio
    async def test_timeline_with_items(self):
        """Timeline returns properly formatted items."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from hestia.api.routes.newsfeed import router
        from hestia.api.middleware.auth import get_device_token

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_device_token] = lambda: "test-device-123"

        mock_item = NewsfeedItem(
            id="test:formatted",
            item_type=NewsfeedItemType.SYSTEM_ALERT,
            source=NewsfeedItemSource.SYSTEM,
            title="Test Alert",
            body="Alert body",
            timestamp=datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc),
            priority=NewsfeedItemPriority.HIGH,
        )

        mock_mgr = AsyncMock()
        mock_mgr.get_timeline = AsyncMock(return_value=[mock_item])
        mock_mgr.get_unread_count = AsyncMock(return_value=1)

        with patch("hestia.api.routes.newsfeed.get_newsfeed_manager", return_value=mock_mgr):
            client = TestClient(app)
            response = client.get("/v1/newsfeed/timeline")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["unread_count"] == 1
        assert data["items"][0]["title"] == "Test Alert"
        assert data["items"][0]["priority"] == "high"
