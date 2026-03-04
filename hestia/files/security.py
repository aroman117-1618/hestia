"""
File system security — PathValidator.

Provides allowlist-first path validation with defense-in-depth:
- Allowlist: paths must resolve under configured allowed_roots
- Denylist: sensitive system/credential paths always rejected
- Symlink resolution: all paths resolved before checks
- Filesystem boundary: rejects cross-device paths (mount point escape)
- TOCTOU-safe reads: fd-level operations to prevent race conditions
- Soft delete: moves to ~/.hestia-trash/ instead of permanent deletion

Security invariant: PathValidationError messages NEVER include actual paths.
"""

import mimetypes
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set, Tuple

from hestia.logging import get_logger

logger = get_logger()


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class PathValidationError(Exception):
    """Raised when a path fails security validation.

    SECURITY: messages must never include the actual path being validated.
    Use generic descriptions only.
    """
    pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BLOCKED_EXTENSIONS: Set[str] = {
    ".app", ".sh", ".command", ".dmg", ".pkg",
    ".dylib", ".so", ".exe", ".bat", ".cmd",
    ".msi", ".dll",
}

DENYLIST_PATHS: List[str] = [
    os.path.expanduser("~/.ssh"),
    os.path.expanduser("~/.gnupg"),
    os.path.expanduser("~/.config/hestia/credentials"),
    "/System",
    "/Library",
    "/private/etc",
    "/private/tty",
    "/usr",
    "/bin",
    "/sbin",
]

TEXT_MIME_PREFIXES: Tuple[str, ...] = (
    "text/",
    "application/json",
    "application/xml",
    "application/javascript",
    "application/yaml",
    "application/x-yaml",
    "application/toml",
)

TRASH_DIR: Path = Path(os.path.expanduser("~/.hestia-trash"))


# ---------------------------------------------------------------------------
# PathValidator
# ---------------------------------------------------------------------------

class PathValidator:
    """Validates filesystem paths against security policies.

    Uses allowlist-first approach modelled on hestia.execution.sandbox:
    resolve via Path.resolve(), then check relative_to() against allowed roots.
    """

    def __init__(
        self,
        allowed_roots: List[str],
        hidden_patterns: List[str],
    ) -> None:
        """Initialize the validator.

        Args:
            allowed_roots: Directories the user is permitted to access.
                           Paths with ~ are expanded.
            hidden_patterns: Filenames/directory names to treat as hidden
                             (in addition to dot-prefixed names).
        """
        self._allowed_roots: List[Path] = [
            Path(os.path.expanduser(r)).resolve()
            for r in allowed_roots
        ]
        self._hidden_patterns: Set[str] = set(hidden_patterns)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_path(self, path: str) -> Path:
        """Validate that *path* is safe to access.

        Checks (in order):
        1. Null byte injection
        2. Empty / whitespace-only
        3. Symlink resolution (Path.resolve)
        4. Denylist (defense-in-depth)
        5. Allowlist (must be under an allowed root)
        6. Filesystem boundary (same st_dev as root)

        Returns:
            Resolved ``Path`` on success.

        Raises:
            PathValidationError: If the path fails any check.
        """
        # 1. Null byte check
        if "\x00" in path:
            logger.warning("Path validation failed: null byte detected")
            raise PathValidationError("Path contains invalid characters")

        # 2. Empty / whitespace check
        if not path or not path.strip():
            logger.warning("Path validation failed: empty or whitespace path")
            raise PathValidationError("Path must not be empty")

        # 3. Resolve symlinks
        try:
            resolved = Path(os.path.expanduser(path)).resolve()
        except (ValueError, OSError):
            logger.warning("Path validation failed: unable to resolve path")
            raise PathValidationError("Path could not be resolved")

        # 4. Denylist check (defense-in-depth)
        resolved_str = str(resolved)
        for denied in DENYLIST_PATHS:
            denied_resolved = str(Path(denied).resolve())
            if resolved_str == denied_resolved or resolved_str.startswith(
                denied_resolved + os.sep
            ):
                logger.warning("Path validation failed: denylist match")
                raise PathValidationError("Access to this location is not permitted")

        # 5. Allowlist check — path must be under at least one allowed root
        matched_root: Optional[Path] = None
        for root in self._allowed_roots:
            try:
                resolved.relative_to(root)
                matched_root = root
                break
            except ValueError:
                continue

        if matched_root is None:
            logger.warning("Path validation failed: not under any allowed root")
            raise PathValidationError("Path is outside permitted directories")

        # 6. Filesystem boundary check
        try:
            path_dev = os.stat(str(resolved)).st_dev
            root_dev = os.stat(str(matched_root)).st_dev
            if path_dev != root_dev:
                logger.warning(
                    "Path validation failed: filesystem boundary crossed"
                )
                raise PathValidationError(
                    "Path crosses filesystem boundary"
                )
        except PathValidationError:
            raise
        except OSError:
            # If we can't stat (e.g., path doesn't exist yet), skip the
            # device check — the path may be a new file about to be created.
            pass

        return resolved

    def validate_content_readable(self, path: str) -> Tuple[Path, str]:
        """Validate path and check that its content type is readable.

        Runs ``validate_path`` first, then applies extension and MIME checks.

        Returns:
            Tuple of (resolved_path, mime_type).

        Raises:
            PathValidationError: If extension is blocked or MIME type is not text-like.
        """
        resolved = self.validate_path(path)

        # Extension block — defense-in-depth even if MIME detection fails
        ext = resolved.suffix.lower()
        if ext in BLOCKED_EXTENSIONS:
            logger.warning(
                "Content validation failed: blocked extension"
            )
            raise PathValidationError(
                "File type is not permitted for content reading"
            )

        # MIME type check
        mime_type, _ = mimetypes.guess_type(str(resolved))
        if mime_type is None:
            # Unknown MIME — default to text/plain for extensionless files
            mime_type = "text/plain"

        if not mime_type.startswith(TEXT_MIME_PREFIXES):
            logger.warning(
                "Content validation failed: non-text MIME type"
            )
            raise PathValidationError(
                "File content type is not permitted for reading"
            )

        return resolved, mime_type

    def is_hidden(self, name: str) -> bool:
        """Check whether a filename or directory name should be treated as hidden.

        A name is hidden if it starts with ``'.'`` or matches one of the
        configured ``hidden_patterns``.
        """
        if name.startswith("."):
            return True
        return name in self._hidden_patterns

    def safe_read(self, path: Path, max_size: int) -> bytes:
        """Read file content in a TOCTOU-safe manner.

        Opens the file descriptor with ``os.open`` on the *real* path
        (``os.path.realpath``), reads up to *max_size* bytes, and closes
        the fd in a ``finally`` block.

        Args:
            path: Resolved ``Path`` (caller should have validated first).
            max_size: Maximum number of bytes to read.

        Returns:
            File content as bytes (up to *max_size*).

        Raises:
            OSError: If the file cannot be opened or read.
        """
        fd = os.open(os.path.realpath(str(path)), os.O_RDONLY)
        try:
            return os.read(fd, max_size)
        finally:
            os.close(fd)

    def safe_delete(self, path: Path, user_id: str) -> Path:
        """Soft-delete a file by moving it to the trash directory.

        Moves the file to ``TRASH_DIR / {timestamp}_{microseconds} / {filename}``.
        Creates parent directories as needed.

        Args:
            path: Resolved ``Path`` of the file to delete.
            user_id: Identity of the user performing the deletion (for audit).

        Returns:
            ``Path`` of the file in the trash directory.
        """
        now = datetime.now(timezone.utc)
        timestamp_dir = now.strftime("%Y%m%d_%H%M%S") + f"_{now.microsecond}"
        trash_parent = TRASH_DIR / timestamp_dir
        trash_parent.mkdir(parents=True, exist_ok=True)

        destination = trash_parent / path.name
        shutil.move(str(path), str(destination))

        logger.info(
            "File soft-deleted",
            data={
                "user_id": user_id,
                "trash_dir": timestamp_dir,
            },
        )
        return destination
