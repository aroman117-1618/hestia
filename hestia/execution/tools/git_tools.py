"""Git tools for agentic development.

Provides safe git operations (status, diff, add, commit, log).
No force operations allowed. Automated commits use [hestia-auto] prefix.
"""

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.execution.models import Tool, ToolParam, ToolParamType
from hestia.logging import get_logger

logger = get_logger()

# Operations that are NEVER allowed
BLOCKED_GIT_OPERATIONS = {
    "push --force", "push -f",
    "reset --hard",
    "clean -f", "clean -fd",
    "branch -D",
    "checkout -- .",
    "restore .",
}

# Default repo path
DEFAULT_REPO = str(Path("~/hestia").expanduser())


def _run_git(args: List[str], repo_path: str = DEFAULT_REPO) -> Dict[str, Any]:
    """Run a git command and return structured result."""
    cmd = ["git", "-C", repo_path] + args
    cmd_str = " ".join(args)

    # Safety check
    for blocked in BLOCKED_GIT_OPERATIONS:
        if blocked in cmd_str:
            return {
                "success": False,
                "error": f"Blocked operation: '{blocked}' is not allowed for safety.",
            }

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000],  # Cap output
            "stderr": result.stderr[:2000] if result.returncode != 0 else "",
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Git command timed out (30s)"}
    except Exception as e:
        return {"success": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}


async def git_status_handler() -> Dict[str, Any]:
    """Get current git status."""
    return _run_git(["status", "--short"])


async def git_diff_handler(staged: bool = False) -> Dict[str, Any]:
    """Get git diff (staged or unstaged)."""
    args = ["diff", "--stat"]
    if staged:
        args.append("--cached")
    result = _run_git(args)

    # Also get the actual diff content (capped)
    detail_args = ["diff"]
    if staged:
        detail_args.append("--cached")
    detail = _run_git(detail_args)
    if detail["success"]:
        result["diff_content"] = detail["stdout"][:10000]

    return result


async def git_add_handler(files: str) -> Dict[str, Any]:
    """Stage files for commit. Accepts space-separated file paths."""
    file_list = files.split()
    if not file_list:
        return {"success": False, "error": "No files specified"}
    return _run_git(["add"] + file_list)


async def git_commit_handler(message: str) -> Dict[str, Any]:
    """Create a git commit with [hestia-auto] prefix (audit condition #5)."""
    prefixed = f"[hestia-auto] {message}"
    return _run_git(["commit", "-m", prefixed])


async def git_log_handler(count: int = 10) -> Dict[str, Any]:
    """Show recent commit log."""
    return _run_git(["log", f"--oneline", f"-{min(count, 50)}"])


# ── Tool Definitions ─────────────────────────────────────

git_status_tool = Tool(
    name="git_status",
    description="Show the current git status (modified, staged, untracked files).",
    parameters={},
    handler=git_status_handler,
    requires_approval=False,
    timeout=10.0,
    category="git",
)

git_diff_tool = Tool(
    name="git_diff",
    description="Show git diff. Set staged=true for staged changes.",
    parameters={
        "staged": ToolParam(
            type=ToolParamType.BOOLEAN,
            description="Show staged changes (default: unstaged)",
            required=False,
            default=False,
        ),
    },
    handler=git_diff_handler,
    requires_approval=False,
    timeout=15.0,
    category="git",
)

git_add_tool = Tool(
    name="git_add",
    description="Stage files for commit. Provide space-separated file paths.",
    parameters={
        "files": ToolParam(
            type=ToolParamType.STRING,
            description="Space-separated file paths to stage",
            required=True,
        ),
    },
    handler=git_add_handler,
    requires_approval=True,  # Staging requires approval
    timeout=10.0,
    category="git",
)

git_commit_tool = Tool(
    name="git_commit",
    description="Create a git commit. Message is automatically prefixed with [hestia-auto].",
    parameters={
        "message": ToolParam(
            type=ToolParamType.STRING,
            description="Commit message (will be prefixed with [hestia-auto])",
            required=True,
        ),
    },
    handler=git_commit_handler,
    requires_approval=True,  # Commits require approval
    timeout=15.0,
    category="git",
)

git_log_tool = Tool(
    name="git_log",
    description="Show recent git commits.",
    parameters={
        "count": ToolParam(
            type=ToolParamType.INTEGER,
            description="Number of commits to show (default: 10, max: 50)",
            required=False,
            default=10,
        ),
    },
    handler=git_log_handler,
    requires_approval=False,
    timeout=10.0,
    category="git",
)


def get_git_tools() -> List[Tool]:
    """Get all git tools."""
    return [git_status_tool, git_diff_tool, git_add_tool, git_commit_tool, git_log_tool]
