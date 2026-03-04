"""
File system data models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class FileOperation(str, Enum):
    """Types of file operations tracked in audit log."""
    LIST = "list"
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    MOVE = "move"


class FileType(str, Enum):
    """File entry types."""
    FILE = "file"
    DIRECTORY = "directory"


@dataclass
class FileEntry:
    """A single file or directory entry."""
    name: str
    path: str
    type: FileType
    size: int
    modified: datetime
    mime_type: Optional[str] = None
    is_hidden: bool = False
    extension: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response."""
        return {
            "name": self.name,
            "path": self.path,
            "type": self.type.value,
            "size": self.size,
            "modified": self.modified.isoformat(),
            "mime_type": self.mime_type,
            "is_hidden": self.is_hidden,
            "extension": self.extension,
        }


@dataclass
class FileAuditLog:
    """Record of a file operation for audit trail."""
    id: str
    user_id: str
    device_id: str
    operation: FileOperation
    path: str
    result: str  # "success", "denied", "error"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    destination_path: Optional[str] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "device_id": self.device_id,
            "operation": self.operation.value,
            "path": self.path,
            "result": self.result,
            "timestamp": self.timestamp.isoformat(),
            "destination_path": self.destination_path,
            "metadata": self.metadata,
        }


@dataclass
class FileSettings:
    """Per-user file access settings. Stored in UserSettings JSON blob."""
    allowed_roots: List[str] = field(default_factory=lambda: [
        "~/Documents",
        "~/Desktop",
        "~/Downloads",
        "~/Projects",
    ])
    hidden_paths: List[str] = field(default_factory=lambda: [
        ".DS_Store",
        ".git",
        "__pycache__",
        "node_modules",
        ".hestia-trash",
    ])
    max_content_size_bytes: int = 10 * 1024 * 1024  # 10MB

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage."""
        return {
            "allowed_roots": self.allowed_roots,
            "hidden_paths": self.hidden_paths,
            "max_content_size_bytes": self.max_content_size_bytes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileSettings":
        """Deserialize from storage."""
        defaults = cls()
        return cls(
            allowed_roots=data.get("allowed_roots", defaults.allowed_roots),
            hidden_paths=data.get("hidden_paths", defaults.hidden_paths),
            max_content_size_bytes=data.get(
                "max_content_size_bytes", defaults.max_content_size_bytes
            ),
        )
