"""
Files module — secure filesystem CRUD with audit trail.

Provides file browsing, reading, writing, and deletion with:
- Allowlist-first path validation (TOCTOU-safe)
- Per-user configurable ALLOWED_ROOTS
- Full audit trail scoped by user_id + device_id
- .hestia-trash/ soft-delete with undo capability
"""

from .models import FileEntry, FileAuditLog, FileSettings, FileOperation, FileType
from .security import PathValidator, PathValidationError
from .manager import FileManager, get_file_manager, close_file_manager

__all__ = [
    "FileEntry",
    "FileAuditLog",
    "FileSettings",
    "FileOperation",
    "FileType",
    "PathValidator",
    "PathValidationError",
    "FileManager",
    "get_file_manager",
    "close_file_manager",
]
