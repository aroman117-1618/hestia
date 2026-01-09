"""
Apple ecosystem data models.

Dataclasses for Calendar events, Reminders, Notes, and Mail.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class ReminderPriority(Enum):
    """Reminder priority levels (matches Apple's EKReminderPriority)."""
    NONE = 0
    HIGH = 1  # 1-4 are high
    MEDIUM = 5
    LOW = 9  # 6-9 are low


@dataclass
class Calendar:
    """Represents an Apple Calendar."""
    id: str
    title: str
    source: str
    color: Optional[List[float]] = None
    allows_modifications: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "Calendar":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            source=data.get("source", ""),
            color=data.get("color"),
            allows_modifications=data.get("allowsModifications", True),
        )


@dataclass
class Event:
    """Represents a Calendar event."""
    id: str
    title: str
    calendar: str
    calendar_id: str
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    is_all_day: bool = False
    location: Optional[str] = None
    notes: Optional[str] = None
    url: Optional[str] = None
    attendees: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "Event":
        start = None
        end = None
        if data.get("start"):
            try:
                start = datetime.fromisoformat(data["start"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        if data.get("end"):
            try:
                end = datetime.fromisoformat(data["end"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            calendar=data.get("calendar", ""),
            calendar_id=data.get("calendarId", ""),
            start=start,
            end=end,
            is_all_day=data.get("isAllDay", False),
            location=data.get("location"),
            notes=data.get("notes"),
            url=data.get("url"),
            attendees=data.get("attendees", []),
        )

    def to_create_dict(self) -> dict:
        """Convert to dict for create/update operations."""
        result = {"title": self.title}
        if self.calendar:
            result["calendar"] = self.calendar
        if self.start:
            result["start"] = self.start.isoformat()
        if self.end:
            result["end"] = self.end.isoformat()
        if self.is_all_day:
            result["allDay"] = True
        if self.location:
            result["location"] = self.location
        if self.notes:
            result["notes"] = self.notes
        return result


@dataclass
class ReminderList:
    """Represents a Reminders list."""
    id: str
    title: str
    source: str
    color: Optional[List[float]] = None
    allows_modifications: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "ReminderList":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            source=data.get("source", ""),
            color=data.get("color"),
            allows_modifications=data.get("allowsModifications", True),
        )


@dataclass
class Reminder:
    """Represents a Reminder."""
    id: str
    title: str
    list_name: str
    list_id: str
    is_completed: bool = False
    priority: int = 0
    due: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None
    url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Reminder":
        due = None
        completed_at = None
        if data.get("due"):
            try:
                due = datetime.fromisoformat(data["due"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        if data.get("completedAt"):
            try:
                completed_at = datetime.fromisoformat(data["completedAt"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            list_name=data.get("list", ""),
            list_id=data.get("listId", ""),
            is_completed=data.get("isCompleted", False),
            priority=data.get("priority", 0),
            due=due,
            completed_at=completed_at,
            notes=data.get("notes"),
            url=data.get("url"),
        )

    def to_create_dict(self) -> dict:
        """Convert to dict for create operations."""
        result = {"title": self.title}
        if self.list_name:
            result["list"] = self.list_name
        if self.due:
            result["due"] = self.due.isoformat()
        if self.priority:
            result["priority"] = self.priority
        if self.notes:
            result["notes"] = self.notes
        return result

    @property
    def priority_level(self) -> ReminderPriority:
        """Get priority as enum."""
        if self.priority == 0:
            return ReminderPriority.NONE
        elif 1 <= self.priority <= 4:
            return ReminderPriority.HIGH
        elif self.priority == 5:
            return ReminderPriority.MEDIUM
        else:
            return ReminderPriority.LOW


@dataclass
class NoteFolder:
    """Represents a Notes folder."""
    id: str
    name: str

    @classmethod
    def from_dict(cls, data: dict) -> "NoteFolder":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
        )


@dataclass
class Note:
    """Represents a Note."""
    id: str
    title: str
    folder: str
    body: Optional[str] = None
    created_at: Optional[str] = None  # String from AppleScript
    modified_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Note":
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            folder=data.get("folder", ""),
            body=data.get("body"),
            created_at=data.get("createdAt"),
            modified_at=data.get("modifiedAt"),
        )

    def to_create_dict(self) -> dict:
        """Convert to dict for create/update operations."""
        result = {"title": self.title}
        if self.body:
            result["body"] = self.body
        if self.folder:
            result["folder"] = self.folder
        return result


@dataclass
class Mailbox:
    """Represents a Mail mailbox."""
    id: str
    name: str
    url: str
    unread_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "Mailbox":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            url=data.get("url", ""),
            unread_count=data.get("unreadCount", 0),
        )


@dataclass
class Email:
    """Represents an email message."""
    message_id: str
    subject: str
    sender: str
    sender_email: str
    recipients: List[str]
    date: Optional[datetime] = None
    snippet: Optional[str] = None
    body: Optional[str] = None
    mailbox: Optional[str] = None
    is_read: bool = True
    is_flagged: bool = False
    has_attachments: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "Email":
        date = None
        if data.get("date"):
            try:
                date = datetime.fromisoformat(data["date"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return cls(
            message_id=data.get("messageId", ""),
            subject=data.get("subject", ""),
            sender=data.get("sender", ""),
            sender_email=data.get("senderEmail", ""),
            recipients=data.get("recipients", []),
            date=date,
            snippet=data.get("snippet"),
            body=data.get("body"),
            mailbox=data.get("mailbox"),
            is_read=data.get("isRead", True),
            is_flagged=data.get("isFlagged", False),
            has_attachments=data.get("hasAttachments", False),
        )
