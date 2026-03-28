"""
Development tools for the agentic dev system.

Provides run_tests, git_push, git_branch, server_restart, and xcode_build tools.
"""

import os
import signal
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.execution.models import Tool, ToolParam, ToolParamType
from hestia.logging import get_logger

logger = get_logger()

PROJECT_ROOT = Path.home() / "hestia"


# ── Handlers ─────────────────────────────────────────────────────────────────

async def run_tests_handler(
    path: Optional[str] = None,
    marker: Optional[str] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Run pytest with optional path, marker, and verbose flags."""
    cmd = ["python", "-m", "pytest"]

    if path:
        cmd.append(path)
    if marker:
        cmd.extend(["-m", marker])
    if verbose:
        cmd.append("-v")

    # Always capture output; add timeout flag
    cmd.extend(["--timeout=30", "--tb=short"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(PROJECT_ROOT),
        )
        # Parse passed/failed counts from pytest summary line
        passed = 0
        lines = result.stdout.splitlines()
        for line in reversed(lines):
            if "passed" in line or "failed" in line or "error" in line:
                summary_line = line
                break

        return {
            "passed": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout[-8000:],   # last 8k chars
            "stderr": result.stderr[-2000:],
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": "pytest timed out after 300 seconds",
        }
    except Exception as e:
        return {
            "passed": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"{type(e).__name__}: {str(e)[:200]}",
        }


async def git_push_handler(branch: Optional[str] = None) -> Dict[str, Any]:
    """Push current branch to origin. Refuses to push main/master."""
    # Determine current branch if not specified
    try:
        current = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        current_branch = current.stdout.strip()
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": f"Could not determine branch: {type(e).__name__}"}

    target_branch = branch or current_branch

    # Safety: refuse to push to main or master
    if target_branch in ("main", "master"):
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Refusing to push to protected branch '{target_branch}'. Switch to a feature branch first.",
        }

    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "push", "origin", target_branch],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "git push timed out after 60 seconds"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": f"{type(e).__name__}: {str(e)[:200]}"}


async def git_branch_handler(name: str, checkout: bool = True) -> Dict[str, Any]:
    """Create a new git branch and optionally check it out."""
    try:
        if checkout:
            result = subprocess.run(
                ["git", "-C", str(PROJECT_ROOT), "checkout", "-b", name],
                capture_output=True,
                text=True,
                timeout=15,
            )
        else:
            result = subprocess.run(
                ["git", "-C", str(PROJECT_ROOT), "branch", name],
                capture_output=True,
                text=True,
                timeout=15,
            )
        return {
            "success": result.returncode == 0,
            "branch": name,
            "stdout": result.stdout[:2000],
            "stderr": result.stderr[:1000],
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "branch": name, "stdout": "", "stderr": "git branch timed out"}
    except Exception as e:
        return {"success": False, "branch": name, "stdout": "", "stderr": f"{type(e).__name__}: {str(e)[:200]}"}


async def server_restart_handler() -> Dict[str, Any]:
    """Kill stale processes on port 8443 then report killed PIDs."""
    killed_pids: List[int] = []
    errors: List[str] = []

    try:
        # Find PIDs listening on 8443
        lsof_result = subprocess.run(
            ["lsof", "-i", ":8443", "-t"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        raw_pids = lsof_result.stdout.strip().splitlines()
        pids = [int(p) for p in raw_pids if p.strip().isdigit()]

        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
                killed_pids.append(pid)
            except ProcessLookupError:
                pass  # Already gone
            except PermissionError as e:
                errors.append(f"PID {pid}: permission denied")
            except Exception as e:
                errors.append(f"PID {pid}: {type(e).__name__}")

        return {
            "success": True,
            "killed_pids": killed_pids,
            "errors": errors if errors else None,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "killed_pids": [], "errors": ["lsof timed out"]}
    except Exception as e:
        return {"success": False, "killed_pids": [], "errors": [f"{type(e).__name__}: {str(e)[:200]}"]}


async def xcode_build_handler(
    scheme: str,
    destination: str = "platform=macOS",
) -> Dict[str, Any]:
    """Run xcodebuild for the given scheme and destination."""
    project_path = PROJECT_ROOT / "HestiaApp"
    cmd = [
        "xcodebuild",
        "-scheme", scheme,
        "-destination", destination,
        "build",
        "-quiet",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(project_path),
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "xcodebuild timed out after 300 seconds"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": f"{type(e).__name__}: {str(e)[:200]}"}


# ── Tool Definitions ──────────────────────────────────────────────────────────

run_tests_tool = Tool(
    name="run_tests",
    description=(
        "Run the pytest test suite. Optionally target a specific path or marker. "
        "Returns pass/fail status, returncode, stdout, and stderr."
    ),
    parameters={
        "path": ToolParam(
            type=ToolParamType.STRING,
            description="Path to a test file or directory (e.g. tests/test_foo.py). Omit to run all tests.",
            required=False,
        ),
        "marker": ToolParam(
            type=ToolParamType.STRING,
            description="pytest marker expression to filter tests (e.g. 'not slow').",
            required=False,
        ),
        "verbose": ToolParam(
            type=ToolParamType.BOOLEAN,
            description="Run with -v for verbose output (default: false).",
            required=False,
            default=False,
        ),
    },
    handler=run_tests_handler,
    requires_approval=False,
    timeout=320.0,
    category="development",
)

git_push_tool = Tool(
    name="git_push",
    description=(
        "Push a branch to origin. Refuses to push main or master for safety. "
        "Returns success, stdout, and stderr."
    ),
    parameters={
        "branch": ToolParam(
            type=ToolParamType.STRING,
            description="Branch name to push. Defaults to the current branch.",
            required=False,
        ),
    },
    handler=git_push_handler,
    requires_approval=True,
    timeout=75.0,
    category="development",
)

git_branch_tool = Tool(
    name="git_branch",
    description=(
        "Create a new git branch and optionally check it out. "
        "Returns success, branch name, stdout, and stderr."
    ),
    parameters={
        "name": ToolParam(
            type=ToolParamType.STRING,
            description="Name of the new branch to create.",
            required=True,
        ),
        "checkout": ToolParam(
            type=ToolParamType.BOOLEAN,
            description="Check out the new branch immediately (default: true).",
            required=False,
            default=True,
        ),
    },
    handler=git_branch_handler,
    requires_approval=False,
    timeout=20.0,
    category="development",
)

server_restart_tool = Tool(
    name="server_restart",
    description=(
        "Kill all processes listening on port 8443 (stale Hestia server instances). "
        "Returns success and a list of killed PIDs."
    ),
    parameters={},
    handler=server_restart_handler,
    requires_approval=False,
    timeout=20.0,
    category="development",
)

xcode_build_tool = Tool(
    name="xcode_build",
    description=(
        "Build an Xcode scheme with xcodebuild -quiet. "
        "Returns success, stdout, and stderr."
    ),
    parameters={
        "scheme": ToolParam(
            type=ToolParamType.STRING,
            description="Xcode scheme to build (e.g. 'HestiaApp' or 'HestiaWorkspace').",
            required=True,
        ),
        "destination": ToolParam(
            type=ToolParamType.STRING,
            description="Build destination string (default: 'platform=macOS').",
            required=False,
            default="platform=macOS",
        ),
    },
    handler=xcode_build_handler,
    requires_approval=False,
    timeout=320.0,
    category="development",
)


def get_dev_tools() -> List[Tool]:
    """Return all development tools."""
    return [
        run_tests_tool,
        git_push_tool,
        git_branch_tool,
        server_restart_tool,
        xcode_build_tool,
    ]
