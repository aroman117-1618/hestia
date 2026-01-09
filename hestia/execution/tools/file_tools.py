"""
File operation tools for Hestia.

Provides read_file and write_file tools with sandbox integration.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import Tool, ToolParam, ToolParamType
from ..sandbox import get_sandbox_runner


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
    allowed_paths=["~/hestia/data", "~/hestia/logs", "~/Documents", "/tmp/hestia"],
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
    allowed_paths=["~/hestia/data", "~/hestia/logs", "/tmp/hestia"],
    category="file",
)


def get_file_tools() -> List[Tool]:
    """Get all file-related tools."""
    return [read_file_tool, write_file_tool]
