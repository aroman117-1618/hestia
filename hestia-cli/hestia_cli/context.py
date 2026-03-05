"""
Repository context detection for agentic coding.

Auto-detects git state in the current working directory and
packages it as context_hints for the WebSocket message.
"""

import os
import subprocess
from typing import Any, Dict, Optional


def get_repo_context() -> Dict[str, Any]:
    """
    Auto-detect git repo context in CWD.

    Returns a dict suitable for the context_hints field.
    Returns empty dict if not in a git repo.
    """
    context: Dict[str, Any] = {
        "cwd": os.getcwd(),
    }

    if not _is_git_repo():
        return context

    context["git_branch"] = _run_git("branch", "--show-current")
    context["git_status_summary"] = _run_git("status", "--short")
    context["git_recent_commits"] = _run_git("log", "--oneline", "-5")

    return context


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
