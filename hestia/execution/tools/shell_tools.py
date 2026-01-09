"""
Shell command tools for Hestia.

Provides run_command tool with sandbox integration.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import Tool, ToolParam, ToolParamType
from ..sandbox import get_sandbox_runner


async def run_command_handler(
    command: str,
    working_dir: Optional[str] = None,
    timeout: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Execute a shell command.

    Args:
        command: Shell command to execute
        working_dir: Working directory for command
        timeout: Command timeout in seconds

    Returns:
        Dict with command output
    """
    sandbox = get_sandbox_runner()

    # Validate command
    sandbox.validate_command(command)

    # Validate working directory if specified
    if working_dir:
        sandbox.validate_path(working_dir)

    # Execute command
    result = await sandbox.run_shell_command(
        command=command,
        working_dir=working_dir,
        timeout=timeout or 60.0,
        capture_output=True,
    )

    return {
        "command": command,
        "working_dir": working_dir or str(Path.home()),
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "success": result["returncode"] == 0,
    }


# Tool definition
run_command_tool = Tool(
    name="run_command",
    description="Execute a shell command and return the output. Dangerous commands are blocked.",
    parameters={
        "command": ToolParam(
            type=ToolParamType.STRING,
            description="Shell command to execute",
            required=True,
        ),
        "working_dir": ToolParam(
            type=ToolParamType.STRING,
            description="Working directory for command execution",
            required=False,
        ),
        "timeout": ToolParam(
            type=ToolParamType.NUMBER,
            description="Command timeout in seconds (default: 60)",
            required=False,
            default=60.0,
        ),
    },
    handler=run_command_handler,
    requires_approval=True,  # Shell commands require approval
    timeout=60.0,
    category="shell",
)


def get_shell_tools() -> List[Tool]:
    """Get all shell-related tools."""
    return [run_command_tool]
