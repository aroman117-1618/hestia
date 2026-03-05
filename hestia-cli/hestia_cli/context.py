"""
Repository context detection for agentic coding.

Auto-detects git state in the current working directory and
packages it as context_hints for the WebSocket message.
Also reads key project files (SPRINT.md, README.md, CLAUDE.md)
for ambient project knowledge.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

# Project files to auto-include, in priority order.
# We stop adding files once we hit the token budget.
PROJECT_FILES: List[str] = [
    "CLAUDE.md",
    "SPRINT.md",
    "ROADMAP.md",
    "README.md",
]

# Max characters per file and total budget
MAX_CHARS_PER_FILE = 4000
MAX_TOTAL_CHARS = 16000


def get_repo_context() -> Dict[str, Any]:
    """
    Auto-detect git repo context in CWD.

    Includes git state and key project file contents.
    Returns a dict suitable for the context_hints field.
    Returns empty dict if not in a git repo.
    """
    context: Dict[str, Any] = {
        "cwd": os.getcwd(),
    }

    if not _is_git_repo():
        # Still try to read project files even outside git
        project_files = get_project_file_snippets()
        if project_files:
            context["project_files"] = project_files
        return context

    context["git_branch"] = _run_git("branch", "--show-current")
    context["git_status_summary"] = _run_git("status", "--short")
    context["git_recent_commits"] = _run_git("log", "--oneline", "-5")

    # Auto-include project files for ambient context
    project_files = get_project_file_snippets()
    if project_files:
        context["project_files"] = project_files

    return context


def get_project_file_snippets() -> Dict[str, str]:
    """
    Read key project files for context injection.

    Auto-detects which files exist in CWD or git root.
    Truncates to MAX_CHARS_PER_FILE each, stops at MAX_TOTAL_CHARS.
    Returns {filename: content} dict.

    Priority order (stops at budget):
    1. CLAUDE.md — conventions & architecture (highest value for coding)
    2. SPRINT.md / ROADMAP.md — current work context
    3. README.md — project overview
    """
    root = _get_git_root() or os.getcwd()
    snippets: Dict[str, str] = {}
    total_chars = 0

    for filename in PROJECT_FILES:
        if total_chars >= MAX_TOTAL_CHARS:
            break

        filepath = Path(root) / filename
        if not filepath.is_file():
            continue

        try:
            content = filepath.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            continue

        if not content.strip():
            continue

        # Budget-aware truncation
        remaining = MAX_TOTAL_CHARS - total_chars
        max_for_this = min(MAX_CHARS_PER_FILE, remaining)

        if len(content) > max_for_this:
            content = content[:max_for_this] + "\n... (truncated)"

        snippets[filename] = content
        total_chars += len(content)

    return snippets


def _get_git_root() -> Optional[str]:
    """Get the root directory of the current git repo, or None."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _is_git_repo() -> bool:
    """Check if CWD is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _run_git(*args: str) -> Optional[str]:
    """Run a git command and return stdout, or None on failure."""
    try:
        result = subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None
