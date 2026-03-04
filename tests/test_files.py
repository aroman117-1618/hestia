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
