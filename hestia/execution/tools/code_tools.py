"""Code editing tools for agentic development.

Provides edit_file (surgical string replacement), glob_files (pattern matching),
and grep_files (content search). All operations go through sandbox validation.
"""

import fnmatch
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.execution.models import Tool, ToolParam, ToolParamType
from hestia.execution.sandbox import get_sandbox_runner

# Paths that edit_file must NEVER modify (audit condition #2)
AGENTIC_DENIED_PATHS = [
    "hestia/security/",
    "hestia/config/",
    ".env",
    ".claude/",
]


def _check_agentic_denied(path: str) -> Optional[str]:
    """Check if a path is in the agentic denied list."""
    resolved = str(Path(path).expanduser().resolve())
    for denied in AGENTIC_DENIED_PATHS:
        if denied in resolved:
            return f"Path contains protected segment '{denied}' — not modifiable by agentic tools"
    return None


async def edit_file_handler(
    path: str,
    old_string: str,
    new_string: str,
) -> Dict[str, Any]:
    """Replace old_string with new_string in a file.

    Fails if old_string is not found or is not unique in the file.
    """
    sandbox = get_sandbox_runner()
    sandbox.validate_path(path, write=True)

    # Check agentic denied paths
    denied = _check_agentic_denied(path)
    if denied:
        return {"success": False, "error": denied}

    full_path = Path(path).expanduser().resolve()
    if not full_path.is_file():
        return {"success": False, "error": f"File not found: {path}"}

    content = full_path.read_text(encoding="utf-8")

    # Check uniqueness
    count = content.count(old_string)
    if count == 0:
        return {"success": False, "error": f"old_string not found in {path}"}
    if count > 1:
        return {
            "success": False,
            "error": f"old_string is not unique — found {count} occurrences. Provide more context.",
        }

    # Perform replacement
    new_content = content.replace(old_string, new_string, 1)
    full_path.write_text(new_content, encoding="utf-8")

    return {
        "success": True,
        "path": str(full_path),
        "chars_removed": len(old_string),
        "chars_added": len(new_string),
    }


async def glob_files_handler(
    pattern: str,
    path: str = ".",
) -> Dict[str, Any]:
    """Find files matching a glob pattern."""
    base = Path(path).expanduser().resolve()
    if not base.is_dir():
        return {"files": [], "error": f"Directory not found: {path}"}

    matches = sorted(str(p) for p in base.rglob(pattern) if p.is_file())
    return {
        "files": matches[:200],  # Cap at 200 results
        "count": len(matches),
        "pattern": pattern,
        "base_path": str(base),
    }


async def grep_files_handler(
    pattern: str,
    path: str = ".",
    file_glob: str = "*.py",
    max_results: int = 50,
) -> Dict[str, Any]:
    """Search file contents with regex pattern."""
    base = Path(path).expanduser().resolve()
    if not base.is_dir():
        return {"matches": [], "error": f"Directory not found: {path}"}

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return {"matches": [], "error": f"Invalid regex: {e}"}

    matches = []
    for file_path in base.rglob(file_glob):
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.splitlines(), 1):
                if regex.search(line):
                    matches.append({
                        "file": str(file_path),
                        "line": i,
                        "content": line.strip()[:200],
                    })
                    if len(matches) >= max_results:
                        break
        except (OSError, UnicodeDecodeError):
            continue
        if len(matches) >= max_results:
            break

    return {
        "matches": matches,
        "count": len(matches),
        "pattern": pattern,
        "truncated": len(matches) >= max_results,
    }


# ── Tool Definitions ─────────────────────────────────────

edit_file_tool = Tool(
    name="edit_file",
    description="Replace an exact string in a file with a new string. Fails if the old string is not found or not unique.",
    parameters={
        "path": ToolParam(
            type=ToolParamType.STRING,
            description="Path to the file to edit",
            required=True,
        ),
        "old_string": ToolParam(
            type=ToolParamType.STRING,
            description="The exact text to find and replace (must be unique in the file)",
            required=True,
        ),
        "new_string": ToolParam(
            type=ToolParamType.STRING,
            description="The replacement text",
            required=True,
        ),
    },
    handler=edit_file_handler,
    requires_approval=False,
    timeout=30.0,
    category="code",
)

glob_files_tool = Tool(
    name="glob_files",
    description="Find files matching a glob pattern (e.g., '*.py', 'tests/test_*.py').",
    parameters={
        "pattern": ToolParam(
            type=ToolParamType.STRING,
            description="Glob pattern to match",
            required=True,
        ),
        "path": ToolParam(
            type=ToolParamType.STRING,
            description="Base directory to search from (default: current directory)",
            required=False,
            default=".",
        ),
    },
    handler=glob_files_handler,
    requires_approval=False,
    timeout=30.0,
    category="code",
)

grep_files_tool = Tool(
    name="grep_files",
    description="Search file contents with a regex pattern. Returns matching lines with file paths and line numbers.",
    parameters={
        "pattern": ToolParam(
            type=ToolParamType.STRING,
            description="Regex pattern to search for",
            required=True,
        ),
        "path": ToolParam(
            type=ToolParamType.STRING,
            description="Base directory to search from",
            required=False,
            default=".",
        ),
        "file_glob": ToolParam(
            type=ToolParamType.STRING,
            description="File pattern to search within (e.g., '*.py')",
            required=False,
            default="*.py",
        ),
        "max_results": ToolParam(
            type=ToolParamType.INTEGER,
            description="Maximum number of results to return",
            required=False,
            default=50,
        ),
    },
    handler=grep_files_handler,
    requires_approval=False,
    timeout=60.0,
    category="code",
)


def get_code_tools() -> List[Tool]:
    """Get all code editing tools."""
    return [edit_file_tool, glob_files_tool, grep_files_tool]
