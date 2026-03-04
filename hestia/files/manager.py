"""
FileManager — async CRUD for user files with audit trail.

Provides directory listing, content reading/writing, move, delete (soft),
and metadata retrieval. All operations are validated via PathValidator
and logged to FileAuditDatabase.

Singleton via ``get_file_manager()`` / ``close_file_manager()``.
"""

import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hestia.logging import get_logger

from .database import FileAuditDatabase
from .models import FileEntry, FileOperation, FileSettings, FileType
from .security import PathValidationError, PathValidator

logger = get_logger()


class FileManager:
    """Async file manager with allowlist security and audit trail."""

    def __init__(
        self,
        db: Optional[FileAuditDatabase] = None,
        settings: Optional[FileSettings] = None,
    ) -> None:
        self._db: Optional[FileAuditDatabase] = db
        self._settings: Optional[FileSettings] = settings
        self._validator: Optional[PathValidator] = None
        self._initialized: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(
        self, settings: Optional[FileSettings] = None
    ) -> None:
        """Create PathValidator, connect audit DB, mark ready.

        Args:
            settings: Optional override; falls back to constructor value
                      or ``FileSettings()`` defaults.
        """
        if settings is not None:
            self._settings = settings
        if self._settings is None:
            self._settings = FileSettings()

        self._validator = PathValidator(
            allowed_roots=self._settings.allowed_roots,
            hidden_patterns=self._settings.hidden_paths,
        )

        if self._db is None:
            self._db = FileAuditDatabase()
        if not self._db._connection:
            await self._db.connect()

        self._initialized = True
        logger.info("FileManager initialized")

    async def close(self) -> None:
        """Close the audit database."""
        if self._db is not None:
            await self._db.close()
            self._db = None
        self._initialized = False
        logger.info("FileManager closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("FileManager is not initialized")

    def _build_entry(self, path: Path) -> FileEntry:
        """Build a ``FileEntry`` from an on-disk path."""
        try:
            st = path.stat()
        except OSError:
            st = None

        is_dir = path.is_dir()
        ext = path.suffix.lower() if not is_dir else None
        mime, _ = mimetypes.guess_type(str(path))

        return FileEntry(
            name=path.name,
            path=str(path),
            type=FileType.DIRECTORY if is_dir else FileType.FILE,
            size=st.st_size if st else 0,
            modified=datetime.fromtimestamp(
                st.st_mtime, tz=timezone.utc
            )
            if st
            else datetime.now(timezone.utc),
            mime_type=mime if not is_dir else None,
            is_hidden=self._validator.is_hidden(path.name)
            if self._validator
            else False,
            extension=ext if ext else None,
        )

    async def _log(
        self,
        user_id: str,
        device_id: str,
        operation: FileOperation,
        path: str,
        result: str = "success",
        destination_path: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Write an audit entry (best-effort — never raises)."""
        try:
            if self._db is not None:
                await self._db.log_operation(
                    user_id=user_id,
                    device_id=device_id,
                    operation=operation.value,
                    path=path,
                    result=result,
                    destination_path=destination_path,
                    metadata=metadata,
                )
        except Exception:
            logger.warning("Failed to write audit log entry")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def list_directory(
        self,
        path: str,
        user_id: str,
        device_id: str,
        show_hidden: bool = False,
        sort_by: str = "name",
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[FileEntry], Optional[str]]:
        """List directory contents with filtering, sorting and pagination.

        Args:
            path: Directory to list (must be under an allowed root).
            user_id: Authenticated user.
            device_id: Device performing the request.
            show_hidden: Include hidden files/dirs.
            sort_by: ``"name"`` | ``"date"`` | ``"size"`` | ``"type"``.
            limit: Max entries per page.
            offset: Number of entries to skip.

        Returns:
            Tuple of (entries, parent_path). ``parent_path`` is ``None``
            when *path* equals one of the allowed roots.
        """
        self._ensure_initialized()
        assert self._validator is not None

        resolved = self._validator.validate_path(path)

        entries: List[FileEntry] = []
        try:
            with os.scandir(str(resolved)) as it:
                for de in it:
                    entry_path = Path(de.path)
                    if not show_hidden and self._validator.is_hidden(de.name):
                        continue
                    entries.append(self._build_entry(entry_path))
        except PermissionError:
            logger.warning("Permission denied listing directory")
            raise PathValidationError("Permission denied")

        # Sort
        if sort_by == "name":
            entries.sort(key=lambda e: e.name.lower())
        elif sort_by == "date":
            entries.sort(key=lambda e: e.modified, reverse=True)
        elif sort_by == "size":
            entries.sort(key=lambda e: e.size, reverse=True)
        elif sort_by == "type":
            entries.sort(
                key=lambda e: (
                    0 if e.type == FileType.DIRECTORY else 1,
                    e.name.lower(),
                )
            )

        # Pagination
        paginated = entries[offset: offset + limit]

        # Parent path
        parent = Path(resolved).parent
        parent_path: Optional[str] = None
        # Only return parent if it's not the path itself (i.e. not at root)
        if parent != resolved:
            parent_path = str(parent)

        await self._log(user_id, device_id, FileOperation.LIST, path)

        return paginated, parent_path

    async def read_content(
        self,
        path: str,
        user_id: str,
        device_id: str,
    ) -> Tuple[str, str, int]:
        """Read text file content.

        Returns:
            Tuple of (content_string, mime_type, size_bytes).

        Raises:
            PathValidationError: If the path is invalid or content is not text.
        """
        self._ensure_initialized()
        assert self._validator is not None
        assert self._settings is not None

        resolved, mime_type = self._validator.validate_content_readable(path)

        raw = self._validator.safe_read(
            resolved, self._settings.max_content_size_bytes
        )
        content = raw.decode("utf-8", errors="replace")
        size = len(raw)

        await self._log(user_id, device_id, FileOperation.READ, path)

        return content, mime_type, size

    async def get_metadata(
        self,
        path: str,
        user_id: str,
        device_id: str,
    ) -> FileEntry:
        """Get file/directory metadata without reading content.

        Returns:
            ``FileEntry`` with stat-based fields populated.
        """
        self._ensure_initialized()
        assert self._validator is not None

        resolved = self._validator.validate_path(path)
        entry = self._build_entry(resolved)
        return entry

    async def create_file(
        self,
        parent_path: str,
        name: str,
        user_id: str,
        device_id: str,
        content: Optional[str] = None,
        file_type: str = "file",
    ) -> FileEntry:
        """Create a new file or directory.

        Args:
            parent_path: Parent directory (must be under allowed root).
            name: Name of the new file/directory.
            user_id: Authenticated user.
            device_id: Device performing the request.
            content: Optional content (for files).
            file_type: ``"file"`` or ``"directory"``.

        Returns:
            ``FileEntry`` for the newly created item.
        """
        self._ensure_initialized()
        assert self._validator is not None

        # Validate parent
        resolved_parent = self._validator.validate_path(parent_path)

        # Build full path and also validate it
        full_path = resolved_parent / name
        self._validator.validate_path(str(full_path))

        if file_type == "directory":
            os.makedirs(str(full_path), exist_ok=True)
        else:
            full_path.write_text(content or "", encoding="utf-8")

        entry = self._build_entry(full_path)

        await self._log(
            user_id, device_id, FileOperation.CREATE, str(full_path)
        )

        return entry

    async def update_file(
        self,
        path: str,
        content: str,
        user_id: str,
        device_id: str,
    ) -> FileEntry:
        """Update an existing file's content.

        Args:
            path: File to update (must exist and be a file, not directory).
            content: New content.
            user_id: Authenticated user.
            device_id: Device performing the request.

        Returns:
            ``FileEntry`` with updated metadata.
        """
        self._ensure_initialized()
        assert self._validator is not None

        resolved = self._validator.validate_path(path)

        if resolved.is_dir():
            raise PathValidationError("Cannot update content of a directory")

        resolved.write_text(content, encoding="utf-8")

        entry = self._build_entry(resolved)

        await self._log(
            user_id, device_id, FileOperation.UPDATE, path
        )

        return entry

    async def delete_file(
        self,
        path: str,
        user_id: str,
        device_id: str,
    ) -> Tuple[bool, str]:
        """Soft-delete a file (moves to .hestia-trash/).

        Returns:
            Tuple of (success, trash_path_string).
        """
        self._ensure_initialized()
        assert self._validator is not None

        resolved = self._validator.validate_path(path)
        trash_path = self._validator.safe_delete(resolved, user_id)

        await self._log(
            user_id,
            device_id,
            FileOperation.DELETE,
            path,
            metadata={"trash_path": str(trash_path)},
        )

        return True, str(trash_path)

    async def move_file(
        self,
        source: str,
        destination: str,
        user_id: str,
        device_id: str,
    ) -> FileEntry:
        """Move a file or directory to a new location.

        Both source and destination must be under allowed roots.

        Returns:
            ``FileEntry`` for the file at its new location.
        """
        self._ensure_initialized()
        assert self._validator is not None

        resolved_src = self._validator.validate_path(source)
        resolved_dst = self._validator.validate_path(destination)

        shutil.move(str(resolved_src), str(resolved_dst))

        # If destination is a directory, file lands inside it
        final_path = resolved_dst
        if resolved_dst.is_dir():
            final_path = resolved_dst / resolved_src.name

        entry = self._build_entry(final_path)

        await self._log(
            user_id,
            device_id,
            FileOperation.MOVE,
            source,
            destination_path=destination,
        )

        return entry

    async def get_audit_logs(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
        operation: Optional[str] = None,
    ) -> List[Dict]:
        """Retrieve audit log entries for a user.

        Delegates to ``FileAuditDatabase.get_logs()``.
        """
        self._ensure_initialized()
        if self._db is None:
            return []
        return await self._db.get_logs(
            user_id=user_id,
            limit=limit,
            offset=offset,
            operation=operation,
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_instance: Optional[FileManager] = None


async def get_file_manager(
    settings: Optional[FileSettings] = None,
) -> FileManager:
    """Get or create the singleton FileManager instance."""
    global _instance
    if _instance is None:
        _instance = FileManager()
        await _instance.initialize(settings)
    return _instance


async def close_file_manager() -> None:
    """Close and discard the singleton FileManager instance."""
    global _instance
    if _instance:
        await _instance.close()
        _instance = None
