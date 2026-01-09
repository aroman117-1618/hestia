"""
Tool registry for managing available tools.

Provides registration, lookup, and schema generation for tools.
"""

import json
from typing import Any, Dict, List, Optional

from .models import Tool, ToolCall, ToolValidationResult


class ToolNotFoundError(Exception):
    """Raised when a tool is not found in the registry."""
    pass


class ToolAlreadyRegisteredError(Exception):
    """Raised when attempting to register a tool with an existing name."""
    pass


class ToolRegistry:
    """
    Registry for tool management.

    Handles registration, lookup, and validation of tools.
    Also generates JSON schemas for prompt injection.
    """

    def __init__(self):
        """Initialize empty registry."""
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """
        Register a tool.

        Args:
            tool: Tool definition to register

        Raises:
            ToolAlreadyRegisteredError: If tool name already exists
        """
        if tool.name in self._tools:
            raise ToolAlreadyRegisteredError(
                f"Tool '{tool.name}' is already registered"
            )
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> None:
        """
        Unregister a tool by name.

        Args:
            name: Name of tool to unregister

        Raises:
            ToolNotFoundError: If tool doesn't exist
        """
        if name not in self._tools:
            raise ToolNotFoundError(f"Tool '{name}' not found")
        del self._tools[name]

    def get(self, name: str) -> Optional[Tool]:
        """
        Get a tool by name.

        Args:
            name: Name of tool to retrieve

        Returns:
            Tool if found, None otherwise
        """
        return self._tools.get(name)

    def get_required(self, name: str) -> Tool:
        """
        Get a tool by name, raising if not found.

        Args:
            name: Name of tool to retrieve

        Returns:
            Tool definition

        Raises:
            ToolNotFoundError: If tool doesn't exist
        """
        tool = self.get(name)
        if tool is None:
            raise ToolNotFoundError(f"Tool '{name}' not found")
        return tool

    def list_tools(self) -> List[Tool]:
        """
        Get all registered tools.

        Returns:
            List of all registered tools
        """
        return list(self._tools.values())

    def list_tool_names(self) -> List[str]:
        """
        Get names of all registered tools.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def has_tool(self, name: str) -> bool:
        """
        Check if a tool is registered.

        Args:
            name: Tool name to check

        Returns:
            True if tool exists
        """
        return name in self._tools

    def get_tools_by_category(self, category: str) -> List[Tool]:
        """
        Get all tools in a category.

        Args:
            category: Category to filter by

        Returns:
            List of tools in category
        """
        return [t for t in self._tools.values() if t.category == category]

    def validate_call(self, call: ToolCall) -> ToolValidationResult:
        """
        Validate a tool call before execution.

        Checks:
        - Tool exists
        - Required parameters are present
        - Parameter types are correct

        Args:
            call: ToolCall to validate

        Returns:
            ToolValidationResult with validation status
        """
        # Check tool exists
        tool = self.get(call.tool_name)
        if tool is None:
            return ToolValidationResult.failure(
                "NOT_FOUND",
                f"Tool '{call.tool_name}' not found"
            )

        # Check required parameters
        required_params = tool.get_required_params()
        for param_name in required_params:
            if param_name not in call.arguments:
                return ToolValidationResult.failure(
                    "MISSING_PARAM",
                    f"Required parameter '{param_name}' not provided for tool '{call.tool_name}'"
                )

        # Check for unknown parameters
        valid_params = set(tool.parameters.keys())
        provided_params = set(call.arguments.keys())
        unknown_params = provided_params - valid_params

        if unknown_params:
            return ToolValidationResult.failure(
                "UNKNOWN_PARAM",
                f"Unknown parameters for tool '{call.tool_name}': {unknown_params}"
            )

        # Type validation would go here in a more complete implementation
        # For now, we trust the model's output

        return ToolValidationResult.success()

    def get_definitions_for_prompt(self) -> str:
        """
        Generate tool definitions for inclusion in model prompts.

        Returns JSON-formatted tool schemas that can be injected
        into the system prompt.

        Returns:
            JSON string of tool definitions
        """
        if not self._tools:
            return ""

        schemas = [tool.to_json_schema() for tool in self._tools.values()]
        return json.dumps(schemas, indent=2)

    def get_definitions_as_list(self) -> List[Dict[str, Any]]:
        """
        Get tool definitions as a list of dictionaries.

        Returns:
            List of tool schemas
        """
        return [tool.to_json_schema() for tool in self._tools.values()]

    def get_tool_descriptions(self) -> str:
        """
        Generate human-readable tool descriptions.

        Used for system prompt injection in a more readable format.

        Returns:
            Formatted string of tool descriptions
        """
        if not self._tools:
            return "No tools available."

        lines = ["Available tools:"]
        for tool in self._tools.values():
            params = ", ".join(
                f"{name}: {param.type.value}"
                for name, param in tool.parameters.items()
            )
            lines.append(f"- {tool.name}({params}): {tool.description}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Remove all registered tools."""
        self._tools.clear()

    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        """Check if tool is registered."""
        return name in self._tools


# Module-level singleton
_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """
    Get the global tool registry singleton.

    Returns:
        Shared ToolRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


def register_tool(tool: Tool) -> None:
    """
    Convenience function to register a tool with the global registry.

    Args:
        tool: Tool to register
    """
    get_tool_registry().register(tool)
