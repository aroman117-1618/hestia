"""
Tests for hestia.files.security — PathValidator.

TDD: tests written before implementation.
Covers allowlist enforcement, path traversal attacks, symlink safety,
filesystem boundary checks, MIME/extension filtering, hidden file detection,
safe read, and safe delete.
"""

import os
import shutil
import stat
import tempfile
import time
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest

from hestia.files.security import (
    BLOCKED_EXTENSIONS,
    DENYLIST_PATHS,
    TEXT_MIME_PREFIXES,
    TRASH_DIR,
    PathValidationError,
    PathValidator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    """Create a temporary directory to serve as an allowed root."""
    root = tmp_path / "allowed"
    root.mkdir()
    return root


@pytest.fixture
def tmp_file(tmp_root: Path) -> Path:
    """Create a simple text file inside the allowed root."""
    f = tmp_root / "hello.txt"
    f.write_text("Hello, Hestia!")
    return f


@pytest.fixture
def validator(tmp_root: Path) -> PathValidator:
    """PathValidator configured with the temp root as the only allowed root."""
    return PathValidator(
        allowed_roots=[str(tmp_root)],
        hidden_patterns=[".DS_Store", ".git", "__pycache__", "node_modules"],
    )


@pytest.fixture
def trash_dir(tmp_path: Path) -> Generator[Path, None, None]:
    """Override TRASH_DIR to a temp location so tests don't pollute ~/.hestia-trash."""
    trash = tmp_path / ".hestia-trash"
    with patch("hestia.files.security.TRASH_DIR", trash):
        yield trash


# ===================================================================
# 1. Allowlist enforcement
# ===================================================================

class TestAllowlistEnforcement:
    """Paths must be within an allowed root to pass validation."""

    def test_path_within_allowed_root_passes(
        self, validator: PathValidator, tmp_file: Path
    ) -> None:
        """A path inside an allowed root should resolve successfully."""
        result = validator.validate_path(str(tmp_file))
        assert result == tmp_file.resolve()

    def test_path_outside_all_allowed_roots_raises(
        self, validator: PathValidator, tmp_path: Path
    ) -> None:
        """A path not under any allowed root should raise PathValidationError."""
        outside = tmp_path / "forbidden" / "secret.txt"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("nope")
        with pytest.raises(PathValidationError):
            validator.validate_path(str(outside))

    def test_denylist_always_rejected(self, tmp_path: Path) -> None:
        """Even if a denylist path is somehow under an allowed root, it should be denied.

        We simulate this by creating a directory structure that mirrors a
        denylist entry within the allowed root and pointing the denylist
        to that specific path.
        """
        # Create root that contains a ".ssh" subdirectory
        root = tmp_path / "home"
        root.mkdir()
        ssh_dir = root / ".ssh"
        ssh_dir.mkdir()
        key_file = ssh_dir / "id_rsa"
        key_file.write_text("secret-key-material")

        validator = PathValidator(
            allowed_roots=[str(root)],
            hidden_patterns=[],
        )
        # The denylist should catch ~/.ssh — but since our root isn't ~,
        # we need to also check that the denylist includes the resolved path.
        # The real denylist uses expanduser, so we patch expanduser to map
        # ~/.ssh to our test dir.
        with patch("hestia.files.security.DENYLIST_PATHS", [str(ssh_dir)]):
            with pytest.raises(PathValidationError):
                validator.validate_path(str(key_file))


# ===================================================================
# 2. Path traversal attacks
# ===================================================================

class TestPathTraversalAttacks:
    """Adversarial path strings must be caught."""

    def test_dotdot_traversal_rejected(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """../  sequences that resolve outside the allowed root should be rejected."""
        evil_path = str(tmp_root / ".." / ".." / "etc" / "passwd")
        with pytest.raises(PathValidationError):
            validator.validate_path(evil_path)

    def test_null_byte_injection_rejected(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """Null bytes are never valid in paths — reject immediately."""
        evil_path = str(tmp_root / "safe.txt\x00../../etc/passwd")
        with pytest.raises(PathValidationError):
            validator.validate_path(evil_path)

    def test_empty_string_rejected(self, validator: PathValidator) -> None:
        """An empty path string should be rejected."""
        with pytest.raises(PathValidationError):
            validator.validate_path("")

    def test_whitespace_only_rejected(self, validator: PathValidator) -> None:
        """A whitespace-only path should be rejected."""
        with pytest.raises(PathValidationError):
            validator.validate_path("   \t\n  ")


# ===================================================================
# 3. Symlink safety
# ===================================================================

class TestSymlinkSafety:
    """Symlinks must be resolved before allowlist check."""

    def test_symlink_inside_allowed_root_passes(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """A symlink whose target is inside the allowed root should pass."""
        target = tmp_root / "real_file.txt"
        target.write_text("real content")
        link = tmp_root / "link_to_real"
        link.symlink_to(target)

        result = validator.validate_path(str(link))
        assert result == target.resolve()

    def test_symlink_outside_allowed_root_rejected(
        self, validator: PathValidator, tmp_root: Path, tmp_path: Path
    ) -> None:
        """A symlink that resolves outside the allowed root must be rejected."""
        outside_file = tmp_path / "outside_secret.txt"
        outside_file.write_text("sensitive data")

        link = tmp_root / "sneaky_link"
        link.symlink_to(outside_file)

        with pytest.raises(PathValidationError):
            validator.validate_path(str(link))


# ===================================================================
# 4. Filesystem boundary check
# ===================================================================

class TestFilesystemBoundary:
    """Reject paths on a different filesystem device than the allowed root."""

    def test_different_device_rejected(
        self, validator: PathValidator, tmp_file: Path, tmp_root: Path
    ) -> None:
        """If os.stat().st_dev differs between path and root, reject."""
        real_stat = os.stat

        def fake_stat(p: str) -> os.stat_result:
            result = real_stat(p)
            resolved_path = str(Path(p).resolve())
            resolved_root = str(tmp_root.resolve())
            # Return different device for the file (not the root)
            if resolved_path != resolved_root and not resolved_path.endswith(resolved_root):
                # Create a fake stat result with a different st_dev
                fake = MagicMock(wraps=result)
                fake.st_dev = result.st_dev + 999
                return fake
            return result

        with patch("hestia.files.security.os.stat", side_effect=fake_stat):
            with pytest.raises(PathValidationError):
                validator.validate_path(str(tmp_file))


# ===================================================================
# 5. MIME / extension filtering
# ===================================================================

class TestMimeExtensionFiltering:
    """validate_content_readable blocks executables and binary MIME types."""

    def test_python_file_readable(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """A .py file should be considered content-readable (text/x-python)."""
        py_file = tmp_root / "script.py"
        py_file.write_text("print('hello')")
        resolved, mime = validator.validate_content_readable(str(py_file))
        assert resolved == py_file.resolve()
        assert mime.startswith("text/")

    def test_markdown_file_readable(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """A .md file should be content-readable."""
        md_file = tmp_root / "README.md"
        md_file.write_text("# Title")
        resolved, mime = validator.validate_content_readable(str(md_file))
        assert resolved == md_file.resolve()
        # markdown may register as text/markdown or text/x-markdown
        assert "text" in mime or "markdown" in mime

    def test_shell_script_blocked(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """A .sh file must be blocked (executable extension)."""
        sh_file = tmp_root / "danger.sh"
        sh_file.write_text("#!/bin/bash\nrm -rf /")
        with pytest.raises(PathValidationError):
            validator.validate_content_readable(str(sh_file))

    def test_binary_image_blocked(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """A .png file should be blocked (binary MIME type)."""
        png_file = tmp_root / "image.png"
        # Write minimal PNG header (doesn't need to be valid image)
        png_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        with pytest.raises(PathValidationError):
            validator.validate_content_readable(str(png_file))

    def test_json_file_readable(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """A .json file should be content-readable (application/json is allowed)."""
        json_file = tmp_root / "data.json"
        json_file.write_text('{"key": "value"}')
        resolved, mime = validator.validate_content_readable(str(json_file))
        assert resolved == json_file.resolve()
        assert "json" in mime


# ===================================================================
# 6. Hidden file detection
# ===================================================================

class TestHiddenFiles:
    """is_hidden detects dot-prefixed files and configured hidden patterns."""

    def test_dotfile_is_hidden(self, validator: PathValidator) -> None:
        """Files starting with '.' should be hidden."""
        assert validator.is_hidden(".gitignore") is True

    def test_normal_file_not_hidden(self, validator: PathValidator) -> None:
        """Normal filenames are not hidden."""
        assert validator.is_hidden("readme.md") is False

    def test_configured_pattern_is_hidden(self, validator: PathValidator) -> None:
        """Names matching hidden_patterns should be hidden."""
        assert validator.is_hidden("node_modules") is True

    def test_ds_store_is_hidden(self, validator: PathValidator) -> None:
        """".DS_Store" is in hidden_patterns."""
        assert validator.is_hidden(".DS_Store") is True


# ===================================================================
# 7. Safe read (TOCTOU-safe)
# ===================================================================

class TestSafeRead:
    """safe_read uses fd-level operations to avoid TOCTOU races."""

    def test_safe_read_returns_content(
        self, validator: PathValidator, tmp_file: Path
    ) -> None:
        """safe_read should return the file bytes."""
        data = validator.safe_read(tmp_file, max_size=4096)
        assert data == b"Hello, Hestia!"

    def test_safe_read_respects_max_size(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """safe_read should truncate at max_size bytes."""
        big_file = tmp_root / "big.txt"
        big_file.write_text("A" * 1000)
        data = validator.safe_read(big_file, max_size=10)
        assert len(data) == 10

    def test_safe_read_nonexistent_raises(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """safe_read on a missing file should raise an OS-level error."""
        missing = tmp_root / "no_such_file.txt"
        with pytest.raises(OSError):
            validator.safe_read(missing, max_size=4096)


# ===================================================================
# 8. Safe delete (soft delete to .hestia-trash/)
# ===================================================================

class TestSafeDelete:
    """safe_delete moves files to .hestia-trash/ with a timestamp directory."""

    def test_safe_delete_moves_to_trash(
        self, validator: PathValidator, tmp_file: Path, trash_dir: Path
    ) -> None:
        """File should end up in trash dir with a timestamp-based parent."""
        original_content = tmp_file.read_text()
        result = validator.safe_delete(tmp_file, user_id="test-user")

        # Original file should be gone
        assert not tmp_file.exists()

        # Result path should be inside the trash dir
        assert str(result).startswith(str(trash_dir))

        # Trashed file should contain the original content
        assert result.exists()
        assert result.read_text() == original_content

    def test_safe_delete_original_no_longer_exists(
        self, validator: PathValidator, tmp_file: Path, trash_dir: Path
    ) -> None:
        """After deletion, the original path should not exist."""
        validator.safe_delete(tmp_file, user_id="test-user")
        assert not tmp_file.exists()

    def test_safe_delete_trash_dir_created(
        self, validator: PathValidator, tmp_file: Path, trash_dir: Path
    ) -> None:
        """Trash directory structure should be created even if it doesn't exist."""
        # trash_dir doesn't exist yet (just a Path); safe_delete should create it
        assert not trash_dir.exists()
        validator.safe_delete(tmp_file, user_id="test-user")
        assert trash_dir.exists()


# ===================================================================
# 9. Constants sanity checks
# ===================================================================

class TestConstants:
    """Verify security constants are properly defined."""

    def test_blocked_extensions_contains_executables(self) -> None:
        """BLOCKED_EXTENSIONS should include common executable types."""
        for ext in [".sh", ".app", ".exe", ".dmg", ".pkg"]:
            assert ext in BLOCKED_EXTENSIONS, f"{ext} missing from BLOCKED_EXTENSIONS"

    def test_denylist_paths_not_empty(self) -> None:
        """DENYLIST_PATHS should have entries."""
        assert len(DENYLIST_PATHS) > 0

    def test_text_mime_prefixes_includes_text(self) -> None:
        """TEXT_MIME_PREFIXES should allow text/* at minimum."""
        assert "text/" in TEXT_MIME_PREFIXES

    def test_trash_dir_is_path(self) -> None:
        """TRASH_DIR should be a Path."""
        assert isinstance(TRASH_DIR, Path)


# ===================================================================
# 10. PathValidationError security
# ===================================================================

class TestPathValidationErrorSecurity:
    """PathValidationError should never leak actual paths."""

    def test_error_does_not_contain_actual_path(
        self, validator: PathValidator, tmp_path: Path
    ) -> None:
        """The error message should not include the literal path that was checked."""
        outside = tmp_path / "super_secret_directory" / "file.txt"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_text("secret")
        with pytest.raises(PathValidationError) as exc_info:
            validator.validate_path(str(outside))
        # The actual path should NOT appear in the error message
        assert "super_secret_directory" not in str(exc_info.value)


# ===================================================================
# 11. Directory validation
# ===================================================================

class TestDirectoryValidation:
    """Directories within allowed roots should pass validation too."""

    def test_subdirectory_passes(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """A subdirectory inside the allowed root should pass."""
        subdir = tmp_root / "subdir"
        subdir.mkdir()
        result = validator.validate_path(str(subdir))
        assert result == subdir.resolve()

    def test_allowed_root_itself_passes(
        self, validator: PathValidator, tmp_root: Path
    ) -> None:
        """The allowed root directory itself should pass validation."""
        result = validator.validate_path(str(tmp_root))
        assert result == tmp_root.resolve()


# ===================================================================
# 12. FileAuditDatabase
# ===================================================================

import asyncio
import json
from datetime import datetime, timedelta, timezone

from hestia.files.database import FileAuditDatabase


class TestFileAuditDatabase:
    """Tests for FileAuditDatabase — SQLite audit trail for file operations."""

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        """Provide a temp database path."""
        return tmp_path / "test_file_audit.db"

    @pytest.mark.asyncio
    async def test_log_operation_stores_all_fields(self, db_path: Path) -> None:
        """Insert an audit log and verify all fields round-trip correctly."""
        async with FileAuditDatabase(db_path) as db:
            entry_id = await db.log_operation(
                user_id="user-1",
                device_id="device-1",
                operation="read",
                path="/home/user/docs/file.txt",
                result="success",
            )

            assert entry_id  # non-empty UUID string

            logs = await db.get_logs("user-1")
            assert len(logs) == 1
            log = logs[0]
            assert log["id"] == entry_id
            assert log["user_id"] == "user-1"
            assert log["device_id"] == "device-1"
            assert log["operation"] == "read"
            assert log["path"] == "/home/user/docs/file.txt"
            assert log["result"] == "success"
            assert log["timestamp"]  # non-empty ISO string
            assert log["destination_path"] is None
            assert log["metadata"] == {}

    @pytest.mark.asyncio
    async def test_get_logs_scoped_by_user_id(self, db_path: Path) -> None:
        """Logs for different users must not leak across user boundaries."""
        async with FileAuditDatabase(db_path) as db:
            await db.log_operation("alice", "dev-a", "read", "/a.txt", "success")
            await db.log_operation("bob", "dev-b", "read", "/b.txt", "success")
            await db.log_operation("alice", "dev-a", "list", "/docs", "success")

            alice_logs = await db.get_logs("alice")
            bob_logs = await db.get_logs("bob")

            assert len(alice_logs) == 2
            assert len(bob_logs) == 1
            assert all(l["user_id"] == "alice" for l in alice_logs)
            assert all(l["user_id"] == "bob" for l in bob_logs)

    @pytest.mark.asyncio
    async def test_get_logs_pagination(self, db_path: Path) -> None:
        """Limit and offset should control which entries are returned."""
        async with FileAuditDatabase(db_path) as db:
            for i in range(5):
                await db.log_operation(
                    "user-1", "dev-1", "read", f"/file_{i}.txt", "success"
                )

            # First page: 2 entries
            page1 = await db.get_logs("user-1", limit=2, offset=0)
            assert len(page1) == 2

            # Second page: 2 entries
            page2 = await db.get_logs("user-1", limit=2, offset=2)
            assert len(page2) == 2

            # Third page: 1 entry
            page3 = await db.get_logs("user-1", limit=2, offset=4)
            assert len(page3) == 1

            # No overlap between pages
            all_ids = [l["id"] for l in page1 + page2 + page3]
            assert len(set(all_ids)) == 5

    @pytest.mark.asyncio
    async def test_get_logs_filter_by_operation(self, db_path: Path) -> None:
        """Operation filter should return only matching operation types."""
        async with FileAuditDatabase(db_path) as db:
            await db.log_operation("user-1", "dev-1", "read", "/a.txt", "success")
            await db.log_operation("user-1", "dev-1", "delete", "/b.txt", "success")
            await db.log_operation("user-1", "dev-1", "read", "/c.txt", "denied")

            reads = await db.get_logs("user-1", operation="read")
            assert len(reads) == 2
            assert all(l["operation"] == "read" for l in reads)

            deletes = await db.get_logs("user-1", operation="delete")
            assert len(deletes) == 1
            assert deletes[0]["operation"] == "delete"

    @pytest.mark.asyncio
    async def test_get_logs_ordered_newest_first(self, db_path: Path) -> None:
        """Logs must be returned in timestamp DESC order."""
        async with FileAuditDatabase(db_path) as db:
            # Insert with small delays to ensure distinct timestamps
            ids = []
            for i in range(3):
                eid = await db.log_operation(
                    "user-1", "dev-1", "read", f"/file_{i}.txt", "success"
                )
                ids.append(eid)

            logs = await db.get_logs("user-1")
            timestamps = [l["timestamp"] for l in logs]
            # Newest first: timestamps should be in descending order
            assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_cleanup_old_entries(self, db_path: Path) -> None:
        """Cleanup should remove entries older than retention and keep recent ones."""
        async with FileAuditDatabase(db_path) as db:
            # Insert a "recent" entry via normal log_operation
            await db.log_operation("user-1", "dev-1", "read", "/new.txt", "success")

            # Insert an "old" entry by directly writing an old timestamp
            old_ts = (
                datetime.now(timezone.utc) - timedelta(days=120)
            ).isoformat()
            await db.connection.execute(
                """
                INSERT INTO file_audit
                    (id, user_id, device_id, operation, path, result, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                ("old-entry-id", "user-1", "dev-1", "read", "/old.txt", "success", old_ts),
            )
            await db.connection.commit()

            # Verify both exist
            all_logs = await db.get_logs("user-1")
            assert len(all_logs) == 2

            # Cleanup with 90-day retention
            deleted = await db.cleanup_old_entries(retention_days=90)
            assert deleted == 1

            # Only the recent entry should remain
            remaining = await db.get_logs("user-1")
            assert len(remaining) == 1
            assert remaining[0]["path"] == "/new.txt"

    @pytest.mark.asyncio
    async def test_log_operation_with_destination_path(self, db_path: Path) -> None:
        """Move operations should store destination_path."""
        async with FileAuditDatabase(db_path) as db:
            entry_id = await db.log_operation(
                user_id="user-1",
                device_id="dev-1",
                operation="move",
                path="/docs/old_name.txt",
                result="success",
                destination_path="/docs/new_name.txt",
            )

            logs = await db.get_logs("user-1")
            assert len(logs) == 1
            assert logs[0]["id"] == entry_id
            assert logs[0]["destination_path"] == "/docs/new_name.txt"

    @pytest.mark.asyncio
    async def test_log_operation_with_metadata(self, db_path: Path) -> None:
        """Metadata dict should be stored as JSON and round-trip correctly."""
        async with FileAuditDatabase(db_path) as db:
            meta = {"mime_type": "text/plain", "size_bytes": "1024", "reason": "user request"}
            entry_id = await db.log_operation(
                user_id="user-1",
                device_id="dev-1",
                operation="read",
                path="/docs/report.txt",
                result="success",
                metadata=meta,
            )

            logs = await db.get_logs("user-1")
            assert len(logs) == 1
            assert logs[0]["metadata"] == meta


# ===================================================================
# 13. FileManager
# ===================================================================

from hestia.files.manager import FileManager
from hestia.files.models import FileSettings


class TestFileManager:
    """Tests for FileManager — async CRUD with audit trail."""

    @pytest.fixture
    def allowed_root(self, tmp_path: Path) -> Path:
        """Create a temp directory to serve as the single allowed root."""
        root = tmp_path / "files_root"
        root.mkdir()
        return root

    @pytest.fixture
    def db_path(self, tmp_path: Path) -> Path:
        return tmp_path / "fm_audit.db"

    @pytest.fixture
    def settings(self, allowed_root: Path) -> FileSettings:
        return FileSettings(
            allowed_roots=[str(allowed_root)],
            hidden_paths=[".DS_Store", ".git", "__pycache__", "node_modules", ".hestia-trash"],
        )

    @pytest.fixture
    async def manager(
        self, db_path: Path, settings: FileSettings
    ) -> FileManager:
        """Create an initialized FileManager scoped to the temp root."""
        db = FileAuditDatabase(db_path)
        fm = FileManager(db=db, settings=settings)
        await fm.initialize()
        yield fm
        await fm.close()

    # ---- list_directory ----

    @pytest.mark.asyncio
    async def test_list_directory_returns_entries(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Create 3 files in the root, list, verify count and names."""
        for name in ["alpha.txt", "beta.txt", "gamma.txt"]:
            (allowed_root / name).write_text(f"content of {name}")

        entries, parent = await manager.list_directory(
            str(allowed_root), "u1", "d1"
        )
        assert len(entries) == 3
        names = {e.name for e in entries}
        assert names == {"alpha.txt", "beta.txt", "gamma.txt"}

    @pytest.mark.asyncio
    async def test_list_directory_hides_hidden_files(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Hidden files should be filtered by default."""
        (allowed_root / "visible.txt").write_text("ok")
        (allowed_root / ".hidden").write_text("secret")

        entries, _ = await manager.list_directory(
            str(allowed_root), "u1", "d1"
        )
        names = [e.name for e in entries]
        assert "visible.txt" in names
        assert ".hidden" not in names

    @pytest.mark.asyncio
    async def test_list_directory_show_hidden(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """With show_hidden=True, hidden files should be included."""
        (allowed_root / "visible.txt").write_text("ok")
        (allowed_root / ".hidden").write_text("secret")

        entries, _ = await manager.list_directory(
            str(allowed_root), "u1", "d1", show_hidden=True
        )
        names = [e.name for e in entries]
        assert "visible.txt" in names
        assert ".hidden" in names

    @pytest.mark.asyncio
    async def test_list_directory_sort_by_name(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Entries should be sorted alphabetically (case-insensitive)."""
        for name in ["Charlie.txt", "alpha.txt", "Bravo.txt"]:
            (allowed_root / name).write_text("x")

        entries, _ = await manager.list_directory(
            str(allowed_root), "u1", "d1", sort_by="name"
        )
        assert [e.name for e in entries] == [
            "alpha.txt", "Bravo.txt", "Charlie.txt"
        ]

    @pytest.mark.asyncio
    async def test_list_directory_sort_by_size(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Entries should be sorted by size descending."""
        (allowed_root / "small.txt").write_text("a")
        (allowed_root / "big.txt").write_text("a" * 1000)
        (allowed_root / "medium.txt").write_text("a" * 100)

        entries, _ = await manager.list_directory(
            str(allowed_root), "u1", "d1", sort_by="size"
        )
        sizes = [e.size for e in entries]
        assert sizes == sorted(sizes, reverse=True)

    @pytest.mark.asyncio
    async def test_list_directory_pagination(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Limit/offset should correctly paginate sorted results."""
        for i in range(5):
            (allowed_root / f"file_{i:02d}.txt").write_text(f"{i}")

        page1, _ = await manager.list_directory(
            str(allowed_root), "u1", "d1", limit=2, offset=0
        )
        page2, _ = await manager.list_directory(
            str(allowed_root), "u1", "d1", limit=2, offset=2
        )
        page3, _ = await manager.list_directory(
            str(allowed_root), "u1", "d1", limit=2, offset=4
        )

        assert len(page1) == 2
        assert len(page2) == 2
        assert len(page3) == 1

        all_names = [e.name for e in page1 + page2 + page3]
        assert len(set(all_names)) == 5

    @pytest.mark.asyncio
    async def test_list_directory_rejects_invalid_path(
        self, manager: FileManager, tmp_path: Path
    ) -> None:
        """A path outside allowed roots should raise PathValidationError."""
        outside = tmp_path / "outside_dir"
        outside.mkdir()
        with pytest.raises(PathValidationError):
            await manager.list_directory(str(outside), "u1", "d1")

    # ---- read_content ----

    @pytest.mark.asyncio
    async def test_read_content_text_file(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Reading a text file should return its content."""
        f = allowed_root / "note.txt"
        f.write_text("Hello from Hestia")

        content, mime, size = await manager.read_content(
            str(f), "u1", "d1"
        )
        assert content == "Hello from Hestia"
        assert size == len(b"Hello from Hestia")
        assert "text" in mime

    @pytest.mark.asyncio
    async def test_read_content_rejects_binary(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """A .png binary file should be rejected."""
        f = allowed_root / "image.png"
        f.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with pytest.raises(PathValidationError):
            await manager.read_content(str(f), "u1", "d1")

    # ---- create_file / create_directory ----

    @pytest.mark.asyncio
    async def test_create_file(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Creating a new file should write content and return FileEntry."""
        entry = await manager.create_file(
            str(allowed_root), "new.txt", "u1", "d1", content="new content"
        )
        created = allowed_root / "new.txt"
        assert created.exists()
        assert created.read_text() == "new content"
        assert entry.name == "new.txt"

    @pytest.mark.asyncio
    async def test_create_directory(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Creating a directory should make it exist and return DIRECTORY type."""
        entry = await manager.create_file(
            str(allowed_root), "subdir", "u1", "d1", file_type="directory"
        )
        created = allowed_root / "subdir"
        assert created.exists()
        assert created.is_dir()
        assert entry.type.value == "directory"

    # ---- update_file ----

    @pytest.mark.asyncio
    async def test_update_file(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Updating a file should replace its content."""
        f = allowed_root / "updatable.txt"
        f.write_text("original")

        entry = await manager.update_file(
            str(f), "modified content", "u1", "d1"
        )
        assert f.read_text() == "modified content"
        assert entry.name == "updatable.txt"

    # ---- delete_file ----

    @pytest.mark.asyncio
    async def test_delete_file_moves_to_trash(
        self, manager: FileManager, allowed_root: Path, tmp_path: Path
    ) -> None:
        """Deleting a file should soft-delete it to .hestia-trash/."""
        f = allowed_root / "doomed.txt"
        f.write_text("goodbye")

        trash = tmp_path / ".hestia-trash"
        with patch("hestia.files.security.TRASH_DIR", trash):
            success, trash_path = await manager.delete_file(
                str(f), "u1", "d1"
            )

        assert success is True
        assert not f.exists()
        assert Path(trash_path).exists()
        assert Path(trash_path).read_text() == "goodbye"

    # ---- move_file ----

    @pytest.mark.asyncio
    async def test_move_file(
        self, manager: FileManager, allowed_root: Path
    ) -> None:
        """Moving a file should relocate it and return entry at new path."""
        src = allowed_root / "moveme.txt"
        src.write_text("mobile data")
        dst = allowed_root / "moved.txt"

        entry = await manager.move_file(
            str(src), str(dst), "u1", "d1"
        )
        assert not src.exists()
        assert dst.exists()
        assert dst.read_text() == "mobile data"
        assert entry.name == "moved.txt"

    # ---- audit trail ----

    @pytest.mark.asyncio
    async def test_all_operations_log_audit(
        self, manager: FileManager, allowed_root: Path, tmp_path: Path
    ) -> None:
        """All CRUD operations should create audit log entries."""
        # CREATE
        await manager.create_file(
            str(allowed_root), "audit_test.txt", "u1", "d1", content="x"
        )
        f = allowed_root / "audit_test.txt"

        # READ
        await manager.read_content(str(f), "u1", "d1")

        # UPDATE
        await manager.update_file(str(f), "y", "u1", "d1")

        # LIST
        await manager.list_directory(str(allowed_root), "u1", "d1")

        # DELETE (with trash override)
        trash = tmp_path / ".hestia-trash"
        with patch("hestia.files.security.TRASH_DIR", trash):
            await manager.delete_file(str(f), "u1", "d1")

        logs = await manager.get_audit_logs("u1")
        operations = [l["operation"] for l in logs]

        assert "create" in operations
        assert "read" in operations
        assert "update" in operations
        assert "list" in operations
        assert "delete" in operations

    # ---- security: create outside roots ----

    @pytest.mark.asyncio
    async def test_create_file_outside_roots_rejected(
        self, manager: FileManager, tmp_path: Path
    ) -> None:
        """Attempting to create a file outside allowed roots should fail."""
        outside = tmp_path / "forbidden_dir"
        outside.mkdir()
        with pytest.raises(PathValidationError):
            await manager.create_file(
                str(outside), "evil.txt", "u1", "d1", content="hack"
            )


# ===================================================================
# 14. File API Routes
# ===================================================================

from unittest.mock import AsyncMock, patch as mock_patch
from datetime import datetime, timezone as tz
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hestia.api.routes.files import router as files_router_instance
from hestia.files.models import FileEntry, FileType


def _make_entry(**overrides) -> FileEntry:
    """Helper to create a FileEntry with sensible defaults."""
    defaults = dict(
        name="test.txt",
        path="/home/user/docs/test.txt",
        type=FileType.FILE,
        size=42,
        modified=datetime(2026, 3, 1, 12, 0, 0, tzinfo=tz.utc),
        mime_type="text/plain",
        is_hidden=False,
        extension=".txt",
    )
    defaults.update(overrides)
    return FileEntry(**defaults)


def _build_test_app(mock_manager: AsyncMock) -> TestClient:
    """Build a minimal FastAPI app with the files router and mocked deps."""
    app = FastAPI()
    app.include_router(files_router_instance)

    # Override auth dependency
    from hestia.api.middleware.auth import get_device_token
    app.dependency_overrides[get_device_token] = lambda: "test-device-id"

    return app, mock_manager


class TestFileRoutes:
    """Tests for /v1/files API routes using mocked FileManager."""

    @pytest.fixture
    def mock_mgr(self):
        """Create a mock FileManager."""
        return AsyncMock()

    @pytest.fixture
    def client(self, mock_mgr):
        """Build a TestClient with the files router and mocked manager."""
        app = FastAPI()
        app.include_router(files_router_instance)

        from hestia.api.middleware.auth import get_device_token
        app.dependency_overrides[get_device_token] = lambda: "test-device-id"

        with mock_patch(
            "hestia.api.routes.files.get_file_manager",
            return_value=mock_mgr,
        ):
            yield TestClient(app)

    # ---- 1. List directory ----

    def test_list_directory_success(self, mock_mgr, client):
        """GET /v1/files should return a list of file entries."""
        entries = [
            _make_entry(name="a.txt", path="/docs/a.txt"),
            _make_entry(name="b.txt", path="/docs/b.txt"),
        ]
        mock_mgr.list_directory.return_value = (entries, "/home/user")

        resp = client.get("/v1/files?path=/home/user/docs")
        assert resp.status_code == 200
        body = resp.json()
        assert body["path"] == "/home/user/docs"
        assert body["parent_path"] == "/home/user"
        assert body["total"] == 2
        assert len(body["files"]) == 2
        assert body["files"][0]["name"] == "a.txt"

    def test_list_directory_access_denied(self, mock_mgr, client):
        """GET /v1/files with path outside roots should return 403."""
        mock_mgr.list_directory.side_effect = PathValidationError("denied")

        resp = client.get("/v1/files?path=/etc/secret")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Access denied"

    # ---- 2. Read content ----

    def test_read_content_success(self, mock_mgr, client):
        """GET /v1/files/content should return file text content."""
        mock_mgr.read_content.return_value = (
            "Hello, Hestia!",
            "text/plain",
            14,
        )
        mock_mgr.get_metadata.return_value = _make_entry()

        resp = client.get("/v1/files/content?path=/docs/test.txt")
        assert resp.status_code == 200
        body = resp.json()
        assert body["content"] == "Hello, Hestia!"
        assert body["mime_type"] == "text/plain"
        assert body["size"] == 14
        assert body["encoding"] == "utf-8"
        assert "modified" in body

    def test_read_content_binary_rejected(self, mock_mgr, client):
        """GET /v1/files/content for binary file should return 403."""
        mock_mgr.read_content.side_effect = PathValidationError("binary")

        resp = client.get("/v1/files/content?path=/docs/image.png")
        assert resp.status_code == 403
        assert resp.json()["detail"] == "Access denied"

    # ---- 3. Get metadata ----

    def test_get_metadata_success(self, mock_mgr, client):
        """GET /v1/files/metadata should return file metadata."""
        entry = _make_entry(name="info.md", path="/docs/info.md", size=256)
        mock_mgr.get_metadata.return_value = entry

        resp = client.get("/v1/files/metadata?path=/docs/info.md")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "info.md"
        assert body["size"] == 256
        assert body["type"] == "file"

    # ---- 4. Create file ----

    def test_create_file_success(self, mock_mgr, client):
        """POST /v1/files should create a file and return 201."""
        entry = _make_entry(name="new.txt", path="/docs/new.txt")
        mock_mgr.create_file.return_value = entry

        resp = client.post(
            "/v1/files",
            json={
                "path": "/docs",
                "name": "new.txt",
                "content": "hello",
                "type": "file",
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "new.txt"
        mock_mgr.create_file.assert_called_once()

    # ---- 5. Update file ----

    def test_update_file_success(self, mock_mgr, client):
        """PUT /v1/files should update content and return entry."""
        entry = _make_entry(name="updated.txt", path="/docs/updated.txt")
        mock_mgr.update_file.return_value = entry

        resp = client.put(
            "/v1/files?path=/docs/updated.txt",
            json={"content": "new content"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "updated.txt"
        mock_mgr.update_file.assert_called_once()

    # ---- 6. Delete file ----

    def test_delete_file_success(self, mock_mgr, client):
        """DELETE /v1/files should soft-delete and return response."""
        mock_mgr.delete_file.return_value = (True, "/trash/test.txt")

        resp = client.delete("/v1/files?path=/docs/test.txt")
        assert resp.status_code == 200
        body = resp.json()
        assert body["deleted"] is True
        assert body["moved_to_trash"] is True

    # ---- 7. Move file ----

    def test_move_file_success(self, mock_mgr, client):
        """PUT /v1/files/move should move and return entry at new path."""
        entry = _make_entry(name="moved.txt", path="/docs/moved.txt")
        mock_mgr.move_file.return_value = entry

        resp = client.put(
            "/v1/files/move",
            json={"source": "/docs/old.txt", "destination": "/docs/moved.txt"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "moved.txt"
        mock_mgr.move_file.assert_called_once()

    # ---- 8. Audit log ----

    def test_audit_log_success(self, mock_mgr, client):
        """GET /v1/files/audit-log should return audit log entries."""
        mock_mgr.get_audit_logs.return_value = [
            {
                "id": "abc-123",
                "operation": "read",
                "path": "/docs/test.txt",
                "result": "success",
                "timestamp": "2026-03-01T12:00:00+00:00",
                "destination_path": None,
                "metadata": {},
            },
            {
                "id": "def-456",
                "operation": "delete",
                "path": "/docs/old.txt",
                "result": "success",
                "timestamp": "2026-03-01T11:00:00+00:00",
                "destination_path": None,
                "metadata": {"trash_path": "/trash/old.txt"},
            },
        ]

        resp = client.get("/v1/files/audit-log")
        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 2
        assert len(body["logs"]) == 2
        assert body["logs"][0]["id"] == "abc-123"
        assert body["logs"][1]["operation"] == "delete"
