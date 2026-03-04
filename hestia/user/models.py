"""
Data models for User Settings.

User profile, notification preferences, and push token management.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4


class PushEnvironment(Enum):
    """APNS environment."""
    PRODUCTION = "production"
    SANDBOX = "sandbox"


@dataclass
class QuietHours:
    """
    Quiet hours configuration.

    Notifications are suppressed during quiet hours.
    """
    enabled: bool = False
    start: time = field(default_factory=lambda: time(22, 0))  # 10 PM
    end: time = field(default_factory=lambda: time(7, 0))  # 7 AM

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "start": self.start.strftime("%H:%M"),
            "end": self.end.strftime("%H:%M"),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "QuietHours":
        """Create from dictionary."""
        start_time = time(22, 0)
        end_time = time(7, 0)

        if data.get("start"):
            h, m = map(int, data["start"].split(":"))
            start_time = time(h, m)
        if data.get("end"):
            h, m = map(int, data["end"].split(":"))
            end_time = time(h, m)

        return cls(
            enabled=data.get("enabled", False),
            start=start_time,
            end=end_time,
        )


@dataclass
class PushNotificationSettings:
    """
    Push notification preferences.
    """
    enabled: bool = True
    order_executions: bool = True
    order_failures: bool = True
    proactive_briefings: bool = True
    quiet_hours: QuietHours = field(default_factory=QuietHours)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "enabled": self.enabled,
            "order_executions": self.order_executions,
            "order_failures": self.order_failures,
            "proactive_briefings": self.proactive_briefings,
            "quiet_hours": self.quiet_hours.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PushNotificationSettings":
        """Create from dictionary."""
        quiet_hours = QuietHours()
        if data.get("quiet_hours"):
            quiet_hours = QuietHours.from_dict(data["quiet_hours"])

        return cls(
            enabled=data.get("enabled", True),
            order_executions=data.get("order_executions", True),
            order_failures=data.get("order_failures", True),
            proactive_briefings=data.get("proactive_briefings", True),
            quiet_hours=quiet_hours,
        )


@dataclass
class UserSettings:
    """
    User preference settings.
    """
    push_notifications: PushNotificationSettings = field(
        default_factory=PushNotificationSettings
    )
    default_mode: str = "tia"
    auto_lock_timeout_minutes: int = 5
    file_settings: Optional[Dict[str, Any]] = None  # FileSettings stored as dict to avoid circular import

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result: Dict[str, Any] = {
            "push_notifications": self.push_notifications.to_dict(),
            "default_mode": self.default_mode,
            "auto_lock_timeout_minutes": self.auto_lock_timeout_minutes,
        }
        if self.file_settings is not None:
            result["file_settings"] = self.file_settings
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSettings":
        """Create from dictionary."""
        push_settings = PushNotificationSettings()
        if data.get("push_notifications"):
            push_settings = PushNotificationSettings.from_dict(data["push_notifications"])

        return cls(
            push_notifications=push_settings,
            default_mode=data.get("default_mode", "tia"),
            auto_lock_timeout_minutes=data.get("auto_lock_timeout_minutes", 5),
            file_settings=data.get("file_settings"),
        )

    def get_file_settings(self) -> "FileSettings":
        """Get FileSettings, lazily importing to avoid circular dependency."""
        from hestia.files.models import FileSettings
        if self.file_settings is not None:
            return FileSettings.from_dict(self.file_settings)
        return FileSettings()

    def set_file_settings(self, settings: "FileSettings") -> None:
        """Store FileSettings as dict."""
        self.file_settings = settings.to_dict()


@dataclass
class UserProfile:
    """
    User profile information.
    """
    id: str
    name: str
    description: Optional[str] = None
    photo_path: Optional[str] = None
    settings: UserSettings = field(default_factory=UserSettings)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def create(cls, name: str = "User") -> "UserProfile":
        """Create a new user profile."""
        now = datetime.now(timezone.utc)
        return cls(
            id=f"user-{uuid4().hex[:12]}",
            name=name,
            created_at=now,
            updated_at=now,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "photo_path": self.photo_path,
            "settings": self.settings.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserProfile":
        """Create from dictionary."""
        settings = UserSettings()
        if data.get("settings"):
            settings = UserSettings.from_dict(data["settings"])

        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            photo_path=data.get("photo_path"),
            settings=settings,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.name,
            self.description,
            self.photo_path,
            json.dumps(self.settings.to_dict()),
            self.created_at.isoformat(),
            self.updated_at.isoformat(),
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "UserProfile":
        """Create from SQLite row."""
        settings = UserSettings()
        if row.get("settings"):
            try:
                settings = UserSettings.from_dict(json.loads(row["settings"]))
            except (json.JSONDecodeError, TypeError):
                pass

        return cls(
            id=row["id"],
            name=row["name"],
            description=row.get("description"),
            photo_path=row.get("photo_path"),
            settings=settings,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


@dataclass
class PushToken:
    """
    Registered push notification token for a device.
    """
    id: str
    device_id: str
    push_token: str
    environment: PushEnvironment
    registered_at: datetime
    last_used_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        device_id: str,
        push_token: str,
        environment: PushEnvironment = PushEnvironment.PRODUCTION,
    ) -> "PushToken":
        """Create a new push token record."""
        return cls(
            id=f"pt-{uuid4().hex[:12]}",
            device_id=device_id,
            push_token=push_token,
            environment=environment,
            registered_at=datetime.now(timezone.utc),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "device_id": self.device_id,
            "push_token": self.push_token,
            "environment": self.environment.value,
            "registered_at": self.registered_at.isoformat(),
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PushToken":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            device_id=data["device_id"],
            push_token=data["push_token"],
            environment=PushEnvironment(data["environment"]),
            registered_at=datetime.fromisoformat(data["registered_at"]),
            last_used_at=datetime.fromisoformat(data["last_used_at"]) if data.get("last_used_at") else None,
        )

    def to_sqlite_row(self) -> tuple:
        """Convert to SQLite row tuple."""
        return (
            self.id,
            self.device_id,
            self.push_token,
            self.environment.value,
            self.registered_at.isoformat(),
            self.last_used_at.isoformat() if self.last_used_at else None,
        )

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "PushToken":
        """Create from SQLite row."""
        return cls(
            id=row["id"],
            device_id=row["device_id"],
            push_token=row["push_token"],
            environment=PushEnvironment(row["environment"]),
            registered_at=datetime.fromisoformat(row["registered_at"]),
            last_used_at=datetime.fromisoformat(row["last_used_at"]) if row.get("last_used_at") else None,
        )
