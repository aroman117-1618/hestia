# Sprint 9A: Explorer Files — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add security-hardened file system CRUD to Hestia's Explorer with audit trail, per-user ALLOWED_ROOTS, and a macOS file browser UI.

**Architecture:** New `hestia/files/` module following manager pattern (models + database + security + manager). Separate `routes/files.py` for filesystem endpoints (distinct from `routes/explorer.py` resource aggregation). Path validation uses allowlist-first with TOCTOU-safe reads. Deletes go to `.hestia-trash/` (Python-native, no osascript). File audit table scoped by `user_id` + `device_id`.

**Tech Stack:** Python/FastAPI (backend), aiosqlite (audit DB), pathlib + os (filesystem), SwiftUI (macOS UI), Pydantic (schemas)

**Audit conditions addressed:** E5 (no osascript), E7 (null-byte sanitization), E8 (text-only content), T1 (reuse SandboxRunner patterns), T2 (plural module name), T3 (query param for path), all CISO E1-E4 from prior audit.

---

## Task 1: Infrastructure — LogComponent + auto-test mapping

**Files:**
- Modify: `hestia/logging/structured_logger.py:58` (add FILE to LogComponent enum)
- Modify: `scripts/auto-test.sh` (add files module mapping)
- Modify: `scripts/validate-security-edit.sh` (add files to security file list)

**Step 1: Add LogComponent.FILE**

In `hestia/logging/structured_logger.py`, after line 58 (`RESEARCH = "research"`), add:

```python
    FILE = "file"
```

**Step 2: Add auto-test.sh mapping**

In `scripts/auto-test.sh`, after the `*hestia/research/*)` case (line 133), add:

```bash
        *hestia/files/*)
            echo "tests/test_files.py" ;;
        *hestia/api/routes/files*)
            echo "tests/test_files.py" ;;
```

**Step 3: Add security validation for files module**

In `scripts/validate-security-edit.sh`, add `hestia/files/` and `hestia/api/routes/files.py` to the security file patterns list.

**Step 4: Commit**

```bash
git add hestia/logging/structured_logger.py scripts/auto-test.sh scripts/validate-security-edit.sh
git commit -m "infra: add LogComponent.FILE, auto-test mapping, security validation for files module"
```

---

## Task 2: Models — FileEntry, FileAuditLog, FileSettings

**Files:**
- Create: `hestia/files/__init__.py`
- Create: `hestia/files/models.py`

**Step 1: Create module init**

```python
"""
Files module — secure filesystem CRUD with audit trail.

Provides file browsing, reading, writing, and deletion with:
- Allowlist-first path validation (TOCTOU-safe)
- Per-user configurable ALLOWED_ROOTS
- Full audit trail scoped by user_id + device_id
- .hestia-trash/ soft-delete with undo capability
"""

from .models import FileEntry, FileAuditLog, FileSettings

__all__ = [
    "FileEntry",
    "FileAuditLog",
    "FileSettings",
]
```

**Step 2: Create models**

```python
"""
File system data models.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


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

    def to_dict(self) -> Dict:
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

    def to_dict(self) -> Dict:
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

    def to_dict(self) -> Dict:
        return {
            "allowed_roots": self.allowed_roots,
            "hidden_paths": self.hidden_paths,
            "max_content_size_bytes": self.max_content_size_bytes,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "FileSettings":
        return cls(
            allowed_roots=data.get("allowed_roots", cls().allowed_roots),
            hidden_paths=data.get("hidden_paths", cls().hidden_paths),
            max_content_size_bytes=data.get("max_content_size_bytes", 10 * 1024 * 1024),
        )
```

**Step 3: Commit**

```bash
git add hestia/files/
git commit -m "feat(files): add models — FileEntry, FileAuditLog, FileSettings"
```

---

## Task 3: Security — PathValidator (TOCTOU-safe, allowlist-first)

**Files:**
- Create: `hestia/files/security.py`
- Create: `tests/test_files.py` (security tests first — TDD)

**Step 1: Write the security tests first**

Create `tests/test_files.py` with path validation tests. These must cover:
- Allowlist enforcement (allowed path passes, disallowed path rejected)
- Symlink escape (symlink pointing outside allowed root → rejected)
- `../` traversal sequences → rejected
- Null byte injection (`path\x00../../etc/passwd`) → rejected
- Filesystem boundary check (same `st_dev`)
- Executable MIME type filtering (`.sh`, `.app`, `.command` → rejected for content reads)
- Non-text MIME type filtering (binary files → metadata only, no content)
- Denylist defense-in-depth (`~/.ssh`, `~/.gnupg` → always rejected even if somehow in allowlist)
- Empty path, root path `/`, relative path without root → rejected

The test file should mock filesystem operations where needed but test the actual validation logic.

**Step 2: Implement PathValidator**

```python
"""
Path validation and security for file system operations.

SECURITY MODEL:
1. Allowlist-first: Only paths under user's ALLOWED_ROOTS are accessible
2. Denylist defense-in-depth: Sensitive paths always blocked even if in allowlist
3. TOCTOU-safe: Resolve symlinks at validation AND operation time via fd
4. Null-byte sanitization: Reject paths containing null bytes
5. Filesystem boundary: Reject paths on different filesystems than their root
6. MIME filtering: Only serve content for text/* types
"""

import mimetypes
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

from hestia.logging import get_logger, LogComponent

logger = get_logger()

# Extensions that are never served as content (defense-in-depth)
BLOCKED_EXTENSIONS: Set[str] = {
    ".app", ".sh", ".command", ".dmg", ".pkg", ".dylib",
    ".so", ".exe", ".bat", ".cmd", ".msi", ".dll",
}

# Paths always denied regardless of allowlist
DENYLIST_PATHS: List[str] = [
    os.path.expanduser("~/.ssh"),
    os.path.expanduser("~/.gnupg"),
    os.path.expanduser("~/.config/hestia/credentials"),
    "/System",
    "/Library",
    "/private",
    "/usr",
    "/bin",
    "/sbin",
]

# MIME types that can have their content served
TEXT_MIME_PREFIXES = ("text/", "application/json", "application/xml",
                      "application/javascript", "application/yaml",
                      "application/x-yaml", "application/toml")

TRASH_DIR = Path.home() / ".hestia-trash"


class PathValidationError(Exception):
    """Raised when path validation fails. Never include the actual path in the message."""
    pass


class PathValidator:
    """
    Validates filesystem paths against per-user allowlist.

    Thread-safe. Stateless except for configuration.
    """

    def __init__(self, allowed_roots: List[str], hidden_patterns: List[str]) -> None:
        self._allowed_roots: List[Path] = [
            Path(os.path.expanduser(r)).resolve() for r in allowed_roots
        ]
        self._hidden_patterns = set(hidden_patterns)
        self._denylist: List[str] = [
            os.path.realpath(p) for p in DENYLIST_PATHS
        ]

    def validate_path(self, path: str) -> Path:
        """
        Validate a path is safe to access. Returns the resolved Path.

        Raises PathValidationError if path is not allowed.
        """
        # Null byte check (E7)
        if "\x00" in path:
            raise PathValidationError("Access denied")

        # Empty/whitespace check
        if not path or not path.strip():
            raise PathValidationError("Access denied")

        try:
            resolved = Path(os.path.expanduser(path)).resolve()
        except (ValueError, OSError):
            raise PathValidationError("Access denied")

        real_path = os.path.realpath(str(resolved))

        # Denylist check (defense-in-depth)
        for denied in self._denylist:
            if real_path == denied or real_path.startswith(denied + os.sep):
                raise PathValidationError("Access denied")

        # Allowlist check (primary defense)
        in_allowed_root = False
        matching_root: Optional[Path] = None
        for root in self._allowed_roots:
            try:
                resolved.relative_to(root)
                in_allowed_root = True
                matching_root = root
                break
            except ValueError:
                continue

        if not in_allowed_root or matching_root is None:
            raise PathValidationError("Access denied")

        # Filesystem boundary check (E1) — same device as allowed root
        try:
            if os.path.exists(real_path):
                path_dev = os.stat(real_path).st_dev
                root_dev = os.stat(str(matching_root)).st_dev
                if path_dev != root_dev:
                    raise PathValidationError("Access denied")
        except OSError:
            raise PathValidationError("Access denied")

        return resolved

    def validate_content_readable(self, path: str) -> Tuple[Path, str]:
        """
        Validate path is safe to read content from. Returns (resolved_path, mime_type).

        Only allows text-like MIME types. Blocks executables and binary files.
        Raises PathValidationError if content read is not allowed.
        """
        resolved = self.validate_path(path)

        # Extension check — block executables (E3)
        ext = resolved.suffix.lower()
        if ext in BLOCKED_EXTENSIONS:
            raise PathValidationError("Access denied")

        # MIME type check (E8) — only serve text-like content
        mime_type, _ = mimetypes.guess_type(str(resolved))
        if mime_type is None:
            mime_type = "application/octet-stream"

        if not any(mime_type.startswith(prefix) for prefix in TEXT_MIME_PREFIXES):
            raise PathValidationError(
                "Binary file — use metadata endpoint instead"
            )

        return resolved, mime_type

    def is_hidden(self, name: str) -> bool:
        """Check if a filename matches hidden patterns."""
        if name.startswith("."):
            return True
        return name in self._hidden_patterns

    @staticmethod
    def safe_read(path: Path, max_size: int) -> bytes:
        """
        TOCTOU-safe file read. Opens fd immediately after resolution.

        The path should already be validated. This provides a second
        layer of protection by re-resolving at read time.
        """
        real_path = os.path.realpath(str(path))
        fd = os.open(real_path, os.O_RDONLY)
        try:
            return os.read(fd, max_size)
        finally:
            os.close(fd)

    @staticmethod
    def safe_delete(path: Path, user_id: str) -> Path:
        """
        Move file to .hestia-trash/ instead of permanent deletion.

        Returns the trash destination path for audit logging.
        Works headless (no Finder/osascript required).
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        trash_dest = TRASH_DIR / timestamp / path.name
        trash_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(trash_dest))
        return trash_dest
```

**Step 3: Run tests to verify they pass**

```bash
python -m pytest tests/test_files.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add hestia/files/security.py tests/test_files.py
git commit -m "feat(files): add PathValidator with TOCTOU-safe reads, allowlist, null-byte protection"
```

---

## Task 4: Database — FileAuditDatabase

**Files:**
- Create: `hestia/files/database.py`
- Add to: `tests/test_files.py` (database tests)

**Step 1: Write database tests**

Add tests to `tests/test_files.py` for:
- Audit log insertion (all fields stored correctly)
- Audit log query by user_id (only returns matching user's logs)
- Audit log query with limit/offset pagination
- Audit log query by operation type
- Retention cleanup (entries older than N days deleted)

**Step 2: Implement FileAuditDatabase**

```python
"""
File audit database — SQLite storage for file operation audit trail.

Follows BaseDatabase pattern. All queries scoped by user_id.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from hestia.database import BaseDatabase
from hestia.logging import get_logger

logger = get_logger()

_instance: Optional["FileAuditDatabase"] = None
_DB_PATH = Path.home() / "hestia" / "data" / "file_audit.db"


class FileAuditDatabase(BaseDatabase):
    """SQLite storage for file operation audit logs."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__("file_audit", db_path or _DB_PATH)

    async def _init_schema(self) -> None:
        await self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS file_audit (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                device_id TEXT NOT NULL,
                operation TEXT NOT NULL,
                path TEXT NOT NULL,
                result TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                destination_path TEXT,
                metadata TEXT DEFAULT '{}'
            );

            CREATE INDEX IF NOT EXISTS idx_file_audit_user_ts
                ON file_audit(user_id, timestamp DESC);

            CREATE INDEX IF NOT EXISTS idx_file_audit_operation
                ON file_audit(operation, timestamp DESC);
        """)
        await self.connection.commit()

    async def log_operation(
        self,
        user_id: str,
        device_id: str,
        operation: str,
        path: str,
        result: str,
        destination_path: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Log a file operation. Returns the log entry ID."""
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await self.connection.execute(
            """INSERT INTO file_audit
               (id, user_id, device_id, operation, path, result, timestamp,
                destination_path, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                log_id, user_id, device_id, operation, path, result, now,
                destination_path, json.dumps(metadata or {}),
            ),
        )
        await self.connection.commit()
        return log_id

    async def get_logs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        operation: Optional[str] = None,
    ) -> List[Dict]:
        """Get audit logs for a user, newest first."""
        if operation:
            cursor = await self.connection.execute(
                """SELECT * FROM file_audit
                   WHERE user_id = ? AND operation = ?
                   ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (user_id, operation, limit, offset),
            )
        else:
            cursor = await self.connection.execute(
                """SELECT * FROM file_audit
                   WHERE user_id = ?
                   ORDER BY timestamp DESC LIMIT ? OFFSET ?""",
                (user_id, limit, offset),
            )
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "device_id": r["device_id"],
                "operation": r["operation"],
                "path": r["path"],
                "result": r["result"],
                "timestamp": r["timestamp"],
                "destination_path": r["destination_path"],
                "metadata": json.loads(r["metadata"]) if r["metadata"] else {},
            }
            for r in rows
        ]

    async def cleanup_old_entries(self, retention_days: int = 90) -> int:
        """Delete audit entries older than retention period. Returns count deleted."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
        cursor = await self.connection.execute(
            "DELETE FROM file_audit WHERE timestamp < ?", (cutoff,)
        )
        await self.connection.commit()
        return cursor.rowcount


async def get_file_audit_database(db_path: Optional[Path] = None) -> FileAuditDatabase:
    """Singleton factory."""
    global _instance
    if _instance is None:
        _instance = FileAuditDatabase(db_path)
        await _instance.connect()
    return _instance


async def close_file_audit_database() -> None:
    """Close singleton."""
    global _instance
    if _instance:
        await _instance.close()
        _instance = None
```

**Step 3: Run tests**

```bash
python -m pytest tests/test_files.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add hestia/files/database.py tests/test_files.py
git commit -m "feat(files): add FileAuditDatabase with user-scoped audit trail"
```

---

## Task 5: Manager — FileManager

**Files:**
- Create: `hestia/files/manager.py`
- Update: `hestia/files/__init__.py` (export manager)
- Add to: `tests/test_files.py` (manager tests)

**Step 1: Write manager tests**

Add tests for:
- `list_directory()` — returns FileEntry list, respects hidden patterns, pagination
- `read_content()` — returns text content, rejects binary, respects size limit
- `create_file()` — creates file, logs audit event
- `update_file()` — writes content, logs audit
- `delete_file()` — moves to trash, logs audit, returns trash path
- `move_file()` — moves file, logs audit with destination
- `get_hidden_paths()` / `update_hidden_paths()` — settings CRUD
- All operations reject invalid paths (validation errors)
- All operations log to audit trail with correct user_id/device_id

**Step 2: Implement FileManager**

The manager:
- Takes FileSettings (from UserSettings) at construction
- Creates PathValidator from settings
- Delegates all validation to PathValidator
- Logs all operations to FileAuditDatabase
- Uses `os.scandir()` for efficient directory listing
- Uses `mimetypes.guess_type()` for MIME detection (T7)

Key methods:
```
async list_directory(path, user_id, device_id, show_hidden, sort_by, limit, offset) -> (List[FileEntry], str parent_path)
async read_content(path, user_id, device_id) -> (str content, str mime_type, int size)
async get_metadata(path, user_id, device_id) -> FileEntry
async create_file(path, name, content, file_type, user_id, device_id) -> FileEntry
async update_file(path, content, user_id, device_id) -> FileEntry
async delete_file(path, user_id, device_id) -> (bool deleted, str trash_path)
async move_file(source, destination, user_id, device_id) -> FileEntry
async get_audit_logs(user_id, limit, offset, operation) -> List[Dict]
```

**Step 3: Update `__init__.py` exports**

Add `FileManager`, `get_file_manager`, `close_file_manager` to exports.

**Step 4: Run tests**

```bash
python -m pytest tests/test_files.py -v --timeout=30
```

**Step 5: Commit**

```bash
git add hestia/files/
git commit -m "feat(files): add FileManager with CRUD, audit logging, path validation"
```

---

## Task 6: UserSettings — Add FileSettings field

**Files:**
- Modify: `hestia/user/models.py` (add file_settings to UserSettings)
- Add to: `tests/test_files.py` or `tests/test_user.py` (settings serialization test)

**Step 1: Add `file_settings` to UserSettings dataclass**

In `hestia/user/models.py`, add to `UserSettings`:

```python
from hestia.files.models import FileSettings

@dataclass
class UserSettings:
    push_notifications: PushNotificationSettings = field(default_factory=PushNotificationSettings)
    default_mode: str = "tia"
    auto_lock_timeout_minutes: int = 5
    file_settings: FileSettings = field(default_factory=FileSettings)
```

Update `to_dict()` and `from_dict()` to include `file_settings`.

**Step 2: Test round-trip serialization**

Verify `UserSettings.to_dict()` → `UserSettings.from_dict()` preserves `file_settings` including custom `allowed_roots`.

**Step 3: Run existing user tests to verify no regressions**

```bash
python -m pytest tests/test_user.py -v --timeout=30
```

**Step 4: Commit**

```bash
git add hestia/user/models.py hestia/files/models.py tests/
git commit -m "feat(files): add FileSettings to UserSettings for per-user allowed roots"
```

---

## Task 7: API Routes — routes/files.py (8 endpoints)

**Files:**
- Create: `hestia/api/routes/files.py`
- Modify: `hestia/api/routes/__init__.py` (register)
- Modify: `hestia/api/server.py` (import, init, shutdown)
- Add to: `tests/test_files.py` (route tests)

**Step 1: Write route tests**

Add API-level tests using FastAPI TestClient for all 8 endpoints:
- `GET /v1/files?path=...` — list directory
- `GET /v1/files/content?path=...` — read file content (text only)
- `GET /v1/files/metadata?path=...` — get file metadata (any type)
- `POST /v1/files` — create file/directory
- `PUT /v1/files?path=...` — update file content (path in query, content in body)
- `DELETE /v1/files?path=...` — delete (move to trash)
- `PUT /v1/files/move` — move/rename
- `GET /v1/files/audit-log` — get audit trail

Plus security tests:
- Path traversal via `../` → 403
- Null byte in path → 403
- Path outside allowed roots → 403
- Binary file content read → 403 with "use metadata endpoint"
- Executable extension → 403
- Missing auth header → 401

**Step 2: Implement routes**

Key design decisions:
- All endpoints use `Depends(get_device_token)` for auth
- Path always passed as `?path=` query parameter (GET, DELETE, PUT update) or in body (POST create, PUT move)
- Error responses use `safe_error_detail()` pattern — never leak filesystem paths
- All operations logged via manager audit trail
- `LogComponent.FILE` for all route logging

Endpoint schemas:

```python
class FileListResponse(BaseModel):
    files: List[FileEntryResponse]
    path: str
    parent_path: Optional[str] = None
    total: int

class FileContentResponse(BaseModel):
    content: str
    mime_type: str
    size: int
    modified: str
    encoding: str = "utf-8"

class FileCreateRequest(BaseModel):
    path: str = Field(..., description="Parent directory path")
    name: str = Field(..., min_length=1, max_length=255)
    content: Optional[str] = None
    type: str = Field(default="file", pattern=r"^(file|directory)$")

class FileMoveRequest(BaseModel):
    source: str
    destination: str

class FileDeleteResponse(BaseModel):
    deleted: bool
    moved_to_trash: bool
```

**Step 3: Register routes**

Add to `hestia/api/routes/__init__.py`:
```python
from .files import router as files_router
# Add to __all__
```

Add to `hestia/api/server.py`:
- Import: `from hestia.files import get_file_manager, close_file_manager`
- Phase 2 init: Add `get_file_manager()` to `phase2_coroutines` and `phase2_names`
- Shutdown: Add `close_file_manager()` block (after research_manager, before investigate_manager)
- Router: `app.include_router(files_router)` after `research_router`

**Step 4: Run all tests**

```bash
python -m pytest tests/test_files.py -v --timeout=30
python -m pytest tests/ -v --timeout=30  # Full suite — verify no regressions
```

**Step 5: Commit**

```bash
git add hestia/api/routes/files.py hestia/api/routes/__init__.py hestia/api/server.py tests/test_files.py
git commit -m "feat(files): add 8 API endpoints with security hardening and audit trail"
```

---

## Task 8: macOS UI — APIClient+Files extension

**Files:**
- Create: `HestiaApp/macOS/Services/APIClient+Files.swift`

**Step 1: Implement API client extension**

Methods matching all 8 endpoints:
```swift
extension APIClient {
    func listFiles(path: String, showHidden: Bool = false, sortBy: String = "name", limit: Int = 100, offset: Int = 0) async throws -> FileListResponse
    func readFileContent(path: String) async throws -> FileContentResponse
    func getFileMetadata(path: String) async throws -> FileEntryResponse
    func createFile(parentPath: String, name: String, content: String?, type: String) async throws -> FileEntryResponse
    func updateFile(path: String, content: String) async throws -> FileEntryResponse
    func deleteFile(path: String) async throws -> FileDeleteResponse
    func moveFile(source: String, destination: String) async throws -> FileEntryResponse
    func getFileAuditLog(limit: Int, offset: Int) async throws -> FileAuditLogResponse
}
```

**Step 2: Add response models**

Create `HestiaApp/macOS/Models/FileModels.swift` with Swift structs matching the Pydantic schemas.

**Step 3: Commit**

```bash
git add HestiaApp/macOS/Services/APIClient+Files.swift HestiaApp/macOS/Models/FileModels.swift
git commit -m "feat(macOS): add APIClient+Files extension and FileModels"
```

---

## Task 9: macOS UI — ExplorerFilesView + ViewModel

**Files:**
- Create: `HestiaApp/macOS/ViewModels/MacExplorerFilesViewModel.swift`
- Create: `HestiaApp/macOS/Views/Explorer/ExplorerFilesView.swift`
- Create: `HestiaApp/macOS/Views/Explorer/FileRowView.swift`
- Modify: `HestiaApp/macOS/Views/Explorer/ExplorerView.swift` (add Files segment)

**Step 1: Implement ViewModel**

```swift
@MainActor
class MacExplorerFilesViewModel: ObservableObject {
    @Published var files: [FileEntry] = []
    @Published var currentPath: String = "~/Documents"
    @Published var parentPath: String? = nil
    @Published var breadcrumbs: [PathSegment] = []
    @Published var isLoading = false
    @Published var error: String? = nil
    @Published var sortBy: String = "name"
    @Published var showHidden = false
    @Published var searchText = ""

    func loadDirectory(_ path: String? = nil) async { ... }
    func navigateUp() async { ... }
    func createFile(name: String, content: String?, type: String) async { ... }
    func deleteFile(_ file: FileEntry) async { ... }
    func moveFile(from: String, to: String) async { ... }
}
```

**Step 2: Implement ExplorerFilesView**

Layout from plan:
- Breadcrumb navigation bar (clickable segments)
- Search bar + sort controls
- File list with FileRowView rows (icon + name + size + modified)
- Context menu on each row (Open, Edit, Rename, Move, Delete)
- New File / New Folder buttons at bottom
- Empty state: "No files in this directory"

**Step 3: Integrate into ExplorerView**

The existing ExplorerView has a segmented control (Files/Resources). Wire the "Files" segment to show `ExplorerFilesView`.

**Step 4: Build and verify**

```bash
xcodebuild -scheme Hestia -destination 'platform=macOS' build 2>&1 | tail -5
```

**Step 5: Commit**

```bash
git add HestiaApp/macOS/ViewModels/MacExplorerFilesViewModel.swift HestiaApp/macOS/Views/Explorer/
git commit -m "feat(macOS): add file browser with breadcrumb nav, CRUD, and context menus"
```

---

## Task 10: macOS UI — FilePreviewSheet + FileEditorView

**Files:**
- Create: `HestiaApp/macOS/Views/Explorer/FilePreviewSheet.swift`
- Create: `HestiaApp/macOS/Views/Explorer/FileEditorView.swift`
- Create: `HestiaApp/macOS/Views/Explorer/HiddenPathsSheet.swift`

**Step 1: FilePreviewSheet**

Quick Look-style preview for files. For text files, shows content with syntax highlighting. For images, shows the image. For other types, shows metadata (size, type, modified) with an "Open in Finder" button.

**Step 2: FileEditorView**

Wraps/reuses the MarkdownEditorView (from Sprint 7) for inline text editing. Save button calls `updateFile()`.

**Step 3: HiddenPathsSheet**

Simple list editor for hidden path patterns. Add/remove patterns. Save calls user settings update endpoint.

**Step 4: Build and verify**

```bash
xcodebuild -scheme Hestia -destination 'platform=macOS' build 2>&1 | tail -5
```

**Step 5: Commit**

```bash
git add HestiaApp/macOS/Views/Explorer/
git commit -m "feat(macOS): add file preview, inline editor, and hidden paths configuration"
```

---

## Task 11: Config + xcodegen + full test suite

**Files:**
- Create: `hestia/config/files.yaml`
- Modify: `HestiaApp/project.yml` (add new Swift files to macOS target)
- Modify: `CLAUDE.md` (update project structure, endpoint count, test count)

**Step 1: Create files.yaml config**

```yaml
# File system access configuration
file_access:
  # Default allowed roots (overridden by per-user settings)
  default_allowed_roots:
    - ~/Documents
    - ~/Desktop
    - ~/Downloads
    - ~/Projects

  # Maximum file content size for reads (bytes)
  max_content_size: 10485760  # 10MB

  # Audit log retention (days)
  audit_retention_days: 90

  # Default hidden patterns
  default_hidden_patterns:
    - .DS_Store
    - .git
    - __pycache__
    - node_modules
    - .hestia-trash

  # Trash directory
  trash_dir: ~/.hestia-trash
```

**Step 2: Update project.yml**

Add new Swift files to macOS target sources.

**Step 3: Run full test suite**

```bash
python -m pytest tests/ -v --timeout=30
```

Verify all existing tests still pass + new tests pass. Target: ~43 new tests → ~1355 total.

**Step 4: Update CLAUDE.md**

- Project structure: add `hestia/files/` module description
- Endpoint count: 132 → 140 (8 new file endpoints)
- Route modules: 22 → 23
- Module count: 23 → 24
- Test count: update to actual passing count

**Step 5: Commit**

```bash
git add hestia/config/files.yaml HestiaApp/project.yml CLAUDE.md
git commit -m "feat(files): add config, update xcodegen, update CLAUDE.md — Sprint 9A complete"
```

---

## Task 12: Review + Documentation

**Step 1: Run @hestia-reviewer on all changed files**

Code audit mode. Verify:
- All security patterns correct (PathValidator, TOCTOU, null-byte)
- All routes use `get_device_token`, `sanitize_for_log`, `LogComponent.FILE`
- All database queries scoped by `user_id`
- No raw exception strings in HTTP responses
- No hardcoded paths (all from config/settings)

**Step 2: Run @hestia-tester — full suite**

Verify 0 failures, note skip count.

**Step 3: Update docs**

- `docs/api-contract.md`: Add all 8 file endpoints
- `docs/hestia-decision-log.md`: Add ADR-040 (File System Access — Allowlist-First)
- `SPRINT.md`: Update Sprint 9A status

**Step 4: Final commit**

```bash
git add docs/ SPRINT.md
git commit -m "docs: Sprint 9A API contract, ADR-040 file access, sprint tracker"
```

---

## Summary

| Task | Description | Est. Time |
|------|-------------|-----------|
| 1 | Infrastructure (LogComponent, auto-test, security hook) | 15 min |
| 2 | Models (FileEntry, FileAuditLog, FileSettings) | 30 min |
| 3 | Security (PathValidator — TDD) | 2 hours |
| 4 | Database (FileAuditDatabase — TDD) | 1 hour |
| 5 | Manager (FileManager — TDD) | 2 hours |
| 6 | UserSettings integration | 30 min |
| 7 | API Routes (8 endpoints — TDD) | 3 hours |
| 8 | macOS APIClient+Files + Models | 1 hour |
| 9 | macOS FileBrowser UI + ViewModel | 3 hours |
| 10 | macOS Preview/Editor/HiddenPaths | 2 hours |
| 11 | Config + xcodegen + full test suite | 1 hour |
| 12 | Review + documentation | 1 hour |
| **Total** | | **~17 hours (~3 sessions)** |

## Audit Conditions Tracker

| Audit ID | Description | Addressed In |
|----------|-------------|-------------|
| E1 | Filesystem boundary check (`st_dev`) | Task 3 — PathValidator |
| E2 | AppleScript injection | Task 3 — eliminated (no osascript) |
| E3 | Executable MIME filtering | Task 3 — BLOCKED_EXTENSIONS set |
| E4 | ALLOWED_ROOTS per-user | Task 6 — FileSettings in UserSettings |
| E5 | No osascript (headless safe) | Task 3 — shutil.move to .hestia-trash |
| E7 | Null-byte sanitization | Task 3 — explicit check in validate_path |
| E8 | Text-only content serving | Task 3 — TEXT_MIME_PREFIXES check |
| T1 | Reuse SandboxRunner patterns | Task 3 — PathValidator follows same design |
| T2 | Plural module name | Task 2 — `hestia/files/` |
| T3 | Query param for path | Task 7 — all GET/DELETE/PUT use `?path=` |
| T7 | mimetypes.guess_type() | Task 3/5 — stdlib MIME detection |
