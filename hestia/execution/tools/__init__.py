"""
Built-in tools for Hestia execution layer.

Provides core tools: read_file, write_file, run_command, plus Apple ecosystem tools.
"""

from .file_tools import (
    read_file_tool,
    write_file_tool,
    list_directory_tool,
    search_files_tool,
    get_file_tools,
)
from .shell_tools import run_command_tool, get_shell_tools
from .code_tools import edit_file_tool, glob_files_tool, grep_files_tool, get_code_tools
from .git_tools import git_status_tool, git_diff_tool, git_add_tool, git_commit_tool, git_log_tool, get_git_tools

__all__ = [
    "read_file_tool",
    "write_file_tool",
    "list_directory_tool",
    "search_files_tool",
    "run_command_tool",
    "get_file_tools",
    "get_shell_tools",
    "edit_file_tool",
    "glob_files_tool",
    "grep_files_tool",
    "get_code_tools",
    "git_status_tool",
    "git_diff_tool",
    "git_add_tool",
    "git_commit_tool",
    "git_log_tool",
    "get_git_tools",
]


def register_builtin_tools(registry) -> None:
    """
    Register all built-in tools with a registry.

    Args:
        registry: ToolRegistry to register tools with
    """
    # Core file and shell tools
    for tool in get_file_tools():
        registry.register(tool)

    for tool in get_shell_tools():
        registry.register(tool)

    # Code editing tools (edit_file, glob, grep)
    for tool in get_code_tools():
        registry.register(tool)

    # Git tools (status, diff, add, commit, log)
    for tool in get_git_tools():
        registry.register(tool)

    # Apple ecosystem tools (Calendar, Reminders, Notes, Mail)
    try:
        from hestia.apple.tools import register_apple_tools
        count = register_apple_tools(registry)
        # Log will be handled by the caller
    except ImportError as e:
        # Apple tools not available (e.g., missing dependencies)
        pass
    except Exception as e:
        # Don't fail tool registration if Apple tools fail
        pass

    # Health analysis tools (query HealthKit data synced from iOS)
    try:
        from hestia.health.tools import register_health_tools
        count = register_health_tools(registry)
    except ImportError:
        pass
    except Exception:
        pass

    # Investigation tools (URL content analysis)
    try:
        from hestia.investigate.tools import register_investigate_tools
        count = register_investigate_tools(registry)
    except ImportError:
        pass
    except Exception:
        pass
