"""
File operation tools for Hestia.

Provides read_file, write_file, list_directory, and search_files tools
with sandbox integration.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from ..models import Tool, ToolParam, ToolParamType
from ..sandbox import get_sandbox_runner

logger = get_logger()


# Common allowed paths for file tools (iCloud Drive, Desktop, Documents, internal)
_ALLOWED_READ_PATHS = [
    "~/hestia/data",
    "~/hestia/logs",
    "~/Documents",
    "~/Desktop",
    "~/Library/Mobile Documents/com~apple~CloudDocs",
    "~/Library/Mobile Documents",
    "/tmp/hestia",
]

_ALLOWED_WRITE_PATHS = [
    "~/hestia/data",
    "~/hestia/logs",
    "~/Desktop",
    "~/Library/Mobile Documents/com~apple~CloudDocs",
    "~/Library/Mobile Documents",
    "/tmp/hestia",
]


async def read_file_handler(
    path: str,
    encoding: str = "utf-8",
    max_lines: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Read contents of a file.

    Args:
        path: Path to file to read
        encoding: File encoding (default: utf-8)
        max_lines: Maximum lines to read (None for all)

    Returns:
        Dict with file contents and metadata
    """
    sandbox = get_sandbox_runner()

    # Validate path
    sandbox.validate_path(path)

    # Expand and resolve path
    full_path = Path(os.path.expanduser(path)).resolve()

    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not full_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    # Read file
    content = full_path.read_text(encoding=encoding)

    # Apply line limit if specified
    lines = content.splitlines()
    total_lines = len(lines)

    if max_lines is not None and max_lines > 0:
        lines = lines[:max_lines]
        truncated = total_lines > max_lines
    else:
        truncated = False

    return {
        "path": str(full_path),
        "content": "\n".join(lines),
        "total_lines": total_lines,
        "lines_returned": len(lines),
        "truncated": truncated,
        "encoding": encoding,
        "size_bytes": full_path.stat().st_size,
    }


async def write_file_handler(
    path: str,
    content: str,
    encoding: str = "utf-8",
    create_dirs: bool = False,
) -> Dict[str, Any]:
    """
    Write content to a file.

    Args:
        path: Path to file to write
        content: Content to write
        encoding: File encoding (default: utf-8)
        create_dirs: Create parent directories if they don't exist

    Returns:
        Dict with write result
    """
    sandbox = get_sandbox_runner()

    # Validate path for writing
    sandbox.validate_path(path, write=True)

    # Expand and resolve path
    full_path = Path(os.path.expanduser(path)).resolve()

    # Check if auto-approved or needs staging
    auto_approved = sandbox.is_write_auto_approved(path)

    if not auto_approved:
        # Return staging info - orchestration layer handles approval
        return {
            "path": str(full_path),
            "status": "staged",
            "requires_approval": True,
            "content_preview": content[:200] + ("..." if len(content) > 200 else ""),
            "content_length": len(content),
            "message": "Write staged for approval. Path is outside auto-approve directories.",
        }

    # Create parent directories if requested
    if create_dirs:
        full_path.parent.mkdir(parents=True, exist_ok=True)

    # Check parent exists
    if not full_path.parent.exists():
        raise FileNotFoundError(f"Parent directory does not exist: {full_path.parent}")

    # Write file
    full_path.write_text(content, encoding=encoding)

    return {
        "path": str(full_path),
        "status": "written",
        "bytes_written": len(content.encode(encoding)),
        "encoding": encoding,
    }


async def list_directory_handler(
    path: str,
    include_hidden: bool = False,
    sort_by: str = "name",
) -> Dict[str, Any]:
    """
    List contents of a directory with metadata.

    Args:
        path: Directory path to list (supports ~ for home)
        include_hidden: Include hidden files (starting with .)
        sort_by: Sort order - "name", "modified", "size"

    Returns:
        Dict with directory listing and metadata
    """
    sandbox = get_sandbox_runner()
    sandbox.validate_path(path)

    full_path = Path(os.path.expanduser(path)).resolve()

    if not full_path.exists():
        logger.warning(
            f"Directory not found: {path}",
            component=LogComponent.EXECUTION,
        )
        raise FileNotFoundError(f"Directory not found: {path}")
    if not full_path.is_dir():
        logger.warning(
            f"Path is not a directory: {path}",
            component=LogComponent.EXECUTION,
        )
        raise ValueError(f"Path is not a directory: {path}")

    entries: List[Dict[str, Any]] = []
    for item in full_path.iterdir():
        if not include_hidden and item.name.startswith("."):
            continue
        try:
            stat = item.stat()
            entries.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size_bytes": stat.st_size if item.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            })
        except (PermissionError, OSError):
            entries.append({
                "name": item.name,
                "path": str(item),
                "is_dir": item.is_dir(),
                "size_bytes": None,
                "modified": None,
                "created": None,
                "error": "permission_denied",
            })

    # Sort
    if sort_by == "modified":
        entries.sort(key=lambda e: e.get("modified") or "", reverse=True)
    elif sort_by == "size":
        entries.sort(key=lambda e: e.get("size_bytes") or 0, reverse=True)
    else:
        # Default: directories first, then alphabetical
        entries.sort(key=lambda e: (not e.get("is_dir", False), e["name"].lower()))

    return {
        "path": str(full_path),
        "entry_count": len(entries),
        "entries": entries,
    }


async def search_files_handler(
    pattern: str,
    directory: str = "~",
    max_results: int = 50,
) -> Dict[str, Any]:
    """
    Search for files by name pattern within allowed directories.

    Args:
        pattern: Glob pattern to match (e.g., "*.pdf", "project*")
        directory: Root directory to search from (supports ~)
        max_results: Maximum number of results to return

    Returns:
        Dict with matching files and metadata
    """
    sandbox = get_sandbox_runner()
    sandbox.validate_path(directory)

    root = Path(os.path.expanduser(directory)).resolve()

    if not root.exists():
        logger.warning(
            f"Search directory not found: {directory}",
            component=LogComponent.EXECUTION,
        )
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not root.is_dir():
        logger.warning(
            f"Search path is not a directory: {directory}",
            component=LogComponent.EXECUTION,
        )
        raise ValueError(f"Path is not a directory: {directory}")

    matches: List[Dict[str, Any]] = []
    try:
        for item in root.rglob(pattern):
            # Validate each result is within allowed paths
            if not sandbox.is_path_allowed(str(item)):
                logger.debug(
                    f"Search skipping file outside allowed paths: {item}",
                    component=LogComponent.EXECUTION,
                )
                continue
            # Skip hidden directories and files
            try:
                rel_parts = item.relative_to(root).parts
            except ValueError:
                continue
            if any(part.startswith(".") for part in rel_parts):
                continue
            try:
                stat = item.stat()
                matches.append({
                    "name": item.name,
                    "path": str(item),
                    "relative_path": str(item.relative_to(root)),
                    "is_dir": item.is_dir(),
                    "size_bytes": stat.st_size if item.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                })
            except (PermissionError, OSError):
                continue

            if len(matches) >= max_results:
                break
    except PermissionError:
        pass

    return {
        "search_directory": str(root),
        "pattern": pattern,
        "result_count": len(matches),
        "truncated": len(matches) >= max_results,
        "results": matches,
    }


# Tool definitions
read_file_tool = Tool(
    name="read_file",
    description="Read the contents of a file. Returns file content and metadata.",
    parameters={
        "path": ToolParam(
            type=ToolParamType.STRING,
            description="Path to the file to read (supports ~ for home directory)",
            required=True,
        ),
        "encoding": ToolParam(
            type=ToolParamType.STRING,
            description="File encoding",
            required=False,
            default="utf-8",
        ),
        "max_lines": ToolParam(
            type=ToolParamType.INTEGER,
            description="Maximum number of lines to read (omit for all)",
            required=False,
        ),
    },
    handler=read_file_handler,
    requires_approval=False,
    timeout=30.0,
    allowed_paths=_ALLOWED_READ_PATHS,
    category="file",
)

write_file_tool = Tool(
    name="write_file",
    description="Write content to a file. Writes to ~/hestia/data are auto-approved; other paths are staged for review.",
    parameters={
        "path": ToolParam(
            type=ToolParamType.STRING,
            description="Path to the file to write (supports ~ for home directory)",
            required=True,
        ),
        "content": ToolParam(
            type=ToolParamType.STRING,
            description="Content to write to the file",
            required=True,
        ),
        "encoding": ToolParam(
            type=ToolParamType.STRING,
            description="File encoding",
            required=False,
            default="utf-8",
        ),
        "create_dirs": ToolParam(
            type=ToolParamType.BOOLEAN,
            description="Create parent directories if they don't exist",
            required=False,
            default=False,
        ),
    },
    handler=write_file_handler,
    requires_approval=False,  # Handled internally via staging
    timeout=30.0,
    allowed_paths=_ALLOWED_WRITE_PATHS,
    category="file",
)

list_directory_tool = Tool(
    name="list_directory",
    description=(
        "List files and folders in a directory with metadata "
        "(size, modified date). Includes iCloud Drive and Desktop."
    ),
    parameters={
        "path": ToolParam(
            type=ToolParamType.STRING,
            description="Directory path to list (supports ~ for home directory)",
            required=True,
        ),
        "include_hidden": ToolParam(
            type=ToolParamType.BOOLEAN,
            description="Include hidden files (starting with .)",
            required=False,
            default=False,
        ),
        "sort_by": ToolParam(
            type=ToolParamType.STRING,
            description="Sort order: name, modified, or size",
            required=False,
            default="name",
            enum=["name", "modified", "size"],
        ),
    },
    handler=list_directory_handler,
    requires_approval=False,
    timeout=30.0,
    allowed_paths=_ALLOWED_READ_PATHS,
    category="file",
)

search_files_tool = Tool(
    name="search_files",
    description=(
        "Search for files by name pattern (glob) within allowed directories. "
        "Recursively searches subdirectories including iCloud Drive."
    ),
    parameters={
        "pattern": ToolParam(
            type=ToolParamType.STRING,
            description="Glob pattern to match file names (e.g., '*.pdf', 'report*', '*.docx')",
            required=True,
        ),
        "directory": ToolParam(
            type=ToolParamType.STRING,
            description="Root directory to search from (supports ~ for home directory)",
            required=False,
            default="~",
        ),
        "max_results": ToolParam(
            type=ToolParamType.INTEGER,
            description="Maximum number of results to return",
            required=False,
            default=50,
        ),
    },
    handler=search_files_handler,
    requires_approval=False,
    timeout=60.0,
    allowed_paths=_ALLOWED_READ_PATHS,
    category="file",
)


def get_file_tools() -> List[Tool]:
    """Get all file-related tools."""
    return [read_file_tool, write_file_tool, list_directory_tool, search_files_tool]
