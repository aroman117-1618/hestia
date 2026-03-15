"""
Tests for Apple ecosystem integration.

Tests models, client wrappers, and tool registration.
Note: Integration tests require Mac with Calendar/Reminders/Notes access.
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Import models
from hestia.apple.models import (
    Calendar,
    Event,
    ReminderList,
    Reminder,
    ReminderPriority,
    NoteFolder,
    Note,
    Mailbox,
    Email,
)

# Import clients
from hestia.apple.calendar import CalendarClient, CalendarError
from hestia.apple.reminders import RemindersClient, RemindersError
from hestia.apple.notes import NotesClient, NotesError
from hestia.apple.mail import MailClient, MailError

# Import tools
from hestia.apple.tools import (
    get_all_apple_tools,
    get_calendar_tools,
    get_reminders_tools,
    get_notes_tools,
    get_mail_tools,
    register_apple_tools,
)

from hestia.execution.registry import ToolRegistry


# ============================================================================
# Model Tests
# ============================================================================

class TestCalendarModel:
    """Tests for Calendar model."""

    def test_from_dict(self):
        """Test creating Calendar from dict."""
        data = {
            "id": "cal-123",
            "title": "Work",
            "source": "iCloud",
            "color": [1.0, 0.0, 0.0],
            "allowsModifications": True,
        }
        calendar = Calendar.from_dict(data)

        assert calendar.id == "cal-123"
        assert calendar.title == "Work"
        assert calendar.source == "iCloud"
        assert calendar.color == [1.0, 0.0, 0.0]
        assert calendar.allows_modifications is True

    def test_from_dict_defaults(self):
        """Test Calendar with missing optional fields."""
        data = {"id": "cal-1", "title": "Personal", "source": "Local"}
        calendar = Calendar.from_dict(data)

        assert calendar.color is None
        assert calendar.allows_modifications is True


class TestEventModel:
    """Tests for Event model."""

    def test_from_dict_full(self):
        """Test creating Event from dict with all fields."""
        data = {
            "id": "event-123",
            "title": "Team Meeting",
            "calendar": "Work",
            "calendarId": "cal-1",
            "start": "2025-01-15T10:00:00",
            "end": "2025-01-15T11:00:00",
            "isAllDay": False,
            "location": "Conference Room A",
            "notes": "Discuss Q1 planning",
            "url": "https://meet.example.com",
            "attendees": ["alice@example.com", "bob@example.com"],
        }
        event = Event.from_dict(data)

        assert event.id == "event-123"
        assert event.title == "Team Meeting"
        assert event.start == datetime(2025, 1, 15, 10, 0)
        assert event.end == datetime(2025, 1, 15, 11, 0)
        assert event.location == "Conference Room A"
        assert len(event.attendees) == 2

    def test_from_dict_minimal(self):
        """Test Event with minimal fields."""
        data = {"id": "e1", "title": "Quick chat", "calendar": "Personal", "calendarId": "c1"}
        event = Event.from_dict(data)

        assert event.id == "e1"
        assert event.start is None
        assert event.end is None
        assert event.is_all_day is False

    def test_to_create_dict(self):
        """Test converting Event to create dict."""
        event = Event(
            id="",
            title="New Event",
            calendar="Work",
            calendar_id="",
            start=datetime(2025, 1, 20, 14, 0),
            end=datetime(2025, 1, 20, 15, 0),
            location="Office",
        )

        create_dict = event.to_create_dict()

        assert create_dict["title"] == "New Event"
        assert create_dict["calendar"] == "Work"
        assert "start" in create_dict
        assert create_dict["location"] == "Office"


class TestReminderModel:
    """Tests for Reminder model."""

    def test_from_dict(self):
        """Test creating Reminder from dict."""
        data = {
            "id": "rem-123",
            "title": "Buy groceries",
            "list": "Personal",
            "listId": "list-1",
            "isCompleted": False,
            "priority": 1,
            "due": "2025-01-15T17:00:00",
            "notes": "Milk, eggs, bread",
        }
        reminder = Reminder.from_dict(data)

        assert reminder.id == "rem-123"
        assert reminder.title == "Buy groceries"
        assert reminder.is_completed is False
        assert reminder.priority == 1
        assert reminder.due is not None

    def test_priority_level(self):
        """Test priority level property."""
        high = Reminder(id="1", title="A", list_name="", list_id="", priority=1)
        medium = Reminder(id="2", title="B", list_name="", list_id="", priority=5)
        low = Reminder(id="3", title="C", list_name="", list_id="", priority=9)
        none = Reminder(id="4", title="D", list_name="", list_id="", priority=0)

        assert high.priority_level == ReminderPriority.HIGH
        assert medium.priority_level == ReminderPriority.MEDIUM
        assert low.priority_level == ReminderPriority.LOW
        assert none.priority_level == ReminderPriority.NONE


class TestNoteModel:
    """Tests for Note model."""

    def test_from_dict(self):
        """Test creating Note from dict."""
        data = {
            "id": "note-123",
            "title": "Meeting Notes",
            "folder": "Work",
            "body": "Discussion points...",
            "createdAt": "2025-01-10",
            "modifiedAt": "2025-01-11",
        }
        note = Note.from_dict(data)

        assert note.id == "note-123"
        assert note.title == "Meeting Notes"
        assert note.folder == "Work"
        assert note.body == "Discussion points..."

    def test_to_create_dict(self):
        """Test converting Note to create dict."""
        note = Note(
            id="",
            title="New Note",
            folder="Personal",
            body="Some content",
        )

        create_dict = note.to_create_dict()

        assert create_dict["title"] == "New Note"
        assert create_dict["folder"] == "Personal"
        assert create_dict["body"] == "Some content"


class TestEmailModel:
    """Tests for Email model."""

    def test_from_dict(self):
        """Test creating Email from dict."""
        data = {
            "messageId": "msg-123",
            "subject": "Weekly Report",
            "sender": "Alice",
            "senderEmail": "alice@example.com",
            "recipients": ["bob@example.com"],
            "date": "2025-01-15T09:00:00",
            "snippet": "Here is the weekly report...",
            "isRead": True,
            "isFlagged": False,
        }
        email = Email.from_dict(data)

        assert email.message_id == "msg-123"
        assert email.subject == "Weekly Report"
        assert email.sender == "Alice"
        assert email.is_read is True


# ============================================================================
# Calendar Client Tests
# ============================================================================

class TestCalendarClient:
    """Tests for CalendarClient."""

    def test_init(self):
        """Test client initialization."""
        client = CalendarClient("/custom/path/cli")
        assert client.cli_path == Path("/custom/path/cli")

    def test_init_default_path(self):
        """Test client with default path."""
        client = CalendarClient()
        assert "hestia-calendar-cli" in str(client.cli_path)

    @pytest.mark.asyncio
    async def test_run_cli_not_found(self):
        """Test error when CLI not found."""
        client = CalendarClient("/nonexistent/path/cli")

        with pytest.raises(CalendarError) as exc:
            await client._run_cli(["list-calendars"])

        assert "not found" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_list_calendars_mock(self):
        """Test list_calendars with mocked CLI."""
        client = CalendarClient()

        mock_result = {
            "success": True,
            "data": {
                "calendars": [
                    {"id": "cal-1", "title": "Work", "source": "iCloud"},
                    {"id": "cal-2", "title": "Personal", "source": "iCloud"},
                ],
                "count": 2,
            },
        }

        with patch.object(client, "_run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            calendars = await client.list_calendars()

        assert len(calendars) == 2
        assert calendars[0].title == "Work"

    @pytest.mark.asyncio
    async def test_create_event_mock(self):
        """Test create_event with mocked CLI."""
        client = CalendarClient()

        mock_result = {
            "success": True,
            "data": {
                "created": True,
                "event": {"id": "new-event", "title": "Test Event", "calendar": "Work"},
            },
        }

        with patch.object(client, "_run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            event = await client.create_event(
                title="Test Event",
                start=datetime(2025, 1, 20, 10, 0),
                end=datetime(2025, 1, 20, 11, 0),
                calendar="Work",
            )

        assert event.id == "new-event"
        assert event.title == "Test Event"

        # Verify CLI was called with correct args
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args == ["create-event"]


# ============================================================================
# Reminders Client Tests
# ============================================================================

class TestRemindersClient:
    """Tests for RemindersClient."""

    @pytest.mark.asyncio
    async def test_list_lists_mock(self):
        """Test list_lists with mocked CLI."""
        client = RemindersClient()

        mock_result = {
            "success": True,
            "data": {
                "lists": [
                    {"id": "list-1", "title": "Personal", "source": "iCloud"},
                    {"id": "list-2", "title": "Work", "source": "iCloud"},
                ],
                "count": 2,
            },
        }

        with patch.object(client, "_run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            lists = await client.list_lists()

        assert len(lists) == 2
        assert lists[0].title == "Personal"

    @pytest.mark.asyncio
    async def test_create_reminder_mock(self):
        """Test create_reminder with mocked CLI."""
        client = RemindersClient()

        mock_result = {
            "success": True,
            "data": {
                "created": True,
                "reminder": {"id": "rem-new", "title": "Test Reminder", "list": "Personal"},
            },
        }

        with patch.object(client, "_run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result

            reminder = await client.create_reminder(
                title="Test Reminder",
                list_name="Personal",
                due=datetime(2025, 1, 20, 17, 0),
            )

        assert reminder.id == "rem-new"

    @pytest.mark.asyncio
    async def test_get_incomplete_mock(self):
        """Test get_incomplete filters correctly."""
        client = RemindersClient()

        mock_result = {
            "success": True,
            "data": {
                "reminders": [
                    {"id": "r1", "title": "Task 1", "list": "Work", "listId": "l1", "isCompleted": False},
                    {"id": "r2", "title": "Task 2", "list": "Work", "listId": "l1", "isCompleted": False},
                ],
                "count": 2,
            },
        }

        with patch.object(client, "_run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            reminders = await client.get_incomplete()

        assert len(reminders) == 2
        # Verify --incomplete flag was passed
        call_args = mock_run.call_args[0][0]
        assert "--incomplete" in call_args


# ============================================================================
# Notes Client Tests
# ============================================================================

class TestNotesClient:
    """Tests for NotesClient."""

    @pytest.mark.asyncio
    async def test_list_folders_mock(self):
        """Test list_folders with mocked CLI."""
        client = NotesClient()

        mock_result = {
            "success": True,
            "data": {
                "folders": [
                    {"id": "f1", "name": "Notes"},
                    {"id": "f2", "name": "Work"},
                ],
                "count": 2,
            },
        }

        with patch.object(client, "_run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            folders = await client.list_folders()

        assert len(folders) == 2
        assert folders[1].name == "Work"

    @pytest.mark.asyncio
    async def test_search_notes_mock(self):
        """Test search_notes filters by title."""
        client = NotesClient()

        mock_result = {
            "success": True,
            "data": {
                "notes": [
                    {"id": "n1", "title": "Meeting Notes January", "folder": "Work"},
                    {"id": "n2", "title": "Project Ideas", "folder": "Work"},
                    {"id": "n3", "title": "Meeting Notes February", "folder": "Work"},
                ],
                "count": 3,
            },
        }

        with patch.object(client, "_run_cli", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = mock_result
            notes = await client.search_notes("Meeting")

        # Should only return notes with "Meeting" in title
        assert len(notes) == 2
        assert all("Meeting" in n.title for n in notes)


# ============================================================================
# Mail Client Tests
# ============================================================================

class TestMailClient:
    """Tests for MailClient."""

    def test_apple_timestamp_conversion(self):
        """Test Apple timestamp to datetime conversion."""
        client = MailClient.__new__(MailClient)

        # Apple epoch is 2001-01-01, so 0 seconds = 2001-01-01
        dt = client._apple_timestamp_to_datetime(0)
        assert dt == datetime(2001, 1, 1)

        # 1 day in seconds
        dt = client._apple_timestamp_to_datetime(86400)
        assert dt == datetime(2001, 1, 2)

    def test_apple_timestamp_none(self):
        """Test None timestamp."""
        client = MailClient.__new__(MailClient)
        assert client._apple_timestamp_to_datetime(None) is None


# ============================================================================
# Tool Registration Tests
# ============================================================================

class TestToolRegistration:
    """Tests for Apple tool registration."""

    def test_get_calendar_tools(self):
        """Test getting calendar tools."""
        tools = get_calendar_tools()

        assert len(tools) >= 5
        tool_names = [t.name for t in tools]
        assert "list_calendars" in tool_names
        assert "list_events" in tool_names
        assert "find_event" in tool_names
        assert "create_event" in tool_names
        assert "get_today_events" in tool_names

    def test_get_reminders_tools(self):
        """Test getting reminders tools."""
        tools = get_reminders_tools()

        assert len(tools) >= 5
        tool_names = [t.name for t in tools]
        assert "list_reminder_lists" in tool_names
        assert "create_reminder" in tool_names
        assert "complete_reminder" in tool_names

    def test_get_notes_tools(self):
        """Test getting notes tools."""
        tools = get_notes_tools()

        assert len(tools) >= 6
        tool_names = [t.name for t in tools]
        assert "list_note_folders" in tool_names
        assert "list_notes" in tool_names
        # get_note removed from LLM tool list — read_note supersedes it
        assert "read_note" in tool_names
        assert "find_note" in tool_names
        assert "create_note" in tool_names
        assert "search_notes" in tool_names

    def test_get_mail_tools(self):
        """Test getting mail tools."""
        tools = get_mail_tools()

        assert len(tools) >= 4
        tool_names = [t.name for t in tools]
        assert "search_emails" in tool_names
        assert "get_recent_emails" in tool_names
        assert "get_unread_count" in tool_names

    def test_get_all_apple_tools(self):
        """Test getting all Apple tools."""
        tools = get_all_apple_tools()

        # Should have 20+ tools total (base 17 + find_event + read_note + find_note = 20)
        assert len(tools) >= 20

        # Check categories
        categories = set(t.category for t in tools)
        assert "calendar" in categories
        assert "reminders" in categories
        assert "notes" in categories
        assert "mail" in categories

    def test_register_apple_tools(self):
        """Test registering tools with registry."""
        registry = ToolRegistry()
        count = register_apple_tools(registry)

        assert count >= 20
        assert len(registry) == count

        # Verify specific tools are registered
        assert registry.has_tool("list_calendars")
        assert registry.has_tool("create_reminder")
        assert registry.has_tool("search_notes")
        assert registry.has_tool("get_unread_count")

    def test_tool_requires_approval(self):
        """Test that write operations require approval."""
        tools = get_all_apple_tools()
        tools_by_name = {t.name: t for t in tools}

        # Write operations should require approval
        assert tools_by_name["create_event"].requires_approval is True
        assert tools_by_name["create_reminder"].requires_approval is True
        assert tools_by_name["create_note"].requires_approval is True

        # Read operations should not require approval
        assert tools_by_name["list_calendars"].requires_approval is False
        assert tools_by_name["list_reminders"].requires_approval is False
        assert tools_by_name["search_emails"].requires_approval is False

    def test_tool_categories(self):
        """Test tool categories are correctly set."""
        tools = get_all_apple_tools()

        for tool in tools:
            if "calendar" in tool.name or tool.name in ["list_events", "create_event", "get_today_events", "find_event"]:
                assert tool.category == "calendar", f"{tool.name} should be calendar"
            elif "reminder" in tool.name or tool.name in ["list_reminders", "get_due_reminders", "get_overdue_reminders"]:
                assert tool.category == "reminders", f"{tool.name} should be reminders"
            elif "note" in tool.name or tool.name in ["read_note", "find_note"]:
                assert tool.category == "notes", f"{tool.name} should be notes"
            elif "email" in tool.name or "mail" in tool.name or tool.name in ["get_unread_count", "get_flagged_emails"]:
                assert tool.category == "mail", f"{tool.name} should be mail"


# ============================================================================
# Integration Tests (require actual CLI and system access)
# ============================================================================

@pytest.mark.skip(reason="Integration test - requires CLI tools installed")
class TestIntegration:
    """Integration tests that require actual CLI tools."""

    @pytest.mark.asyncio
    async def test_list_calendars_integration(self):
        """Test listing calendars with real CLI."""
        client = CalendarClient()
        calendars = await client.list_calendars()
        assert isinstance(calendars, list)

    @pytest.mark.asyncio
    async def test_list_reminder_lists_integration(self):
        """Test listing reminder lists with real CLI."""
        client = RemindersClient()
        lists = await client.list_lists()
        assert isinstance(lists, list)

    @pytest.mark.asyncio
    async def test_list_note_folders_integration(self):
        """Test listing note folders with real CLI."""
        client = NotesClient()
        folders = await client.list_folders()
        assert isinstance(folders, list)
