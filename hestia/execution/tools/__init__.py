"""
Built-in tools for Hestia execution layer.

Provides core tools: read_file, write_file, run_command, plus Apple ecosystem tools.
"""

from .file_tools import read_file_tool, write_file_tool, get_file_tools
from .shell_tools import run_command_tool, get_shell_tools

__all__ = [
    "read_file_tool",
    "write_file_tool",
    "run_command_tool",
    "get_file_tools",
    "get_shell_tools",
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
