"""
Hestia Execution Layer.

Provides tool registration, sandboxed execution, and external
communication gating for tool calls.

Main components:
- ToolRegistry: Register and manage available tools
- ToolExecutor: Execute tools with sandboxing and gating
- SandboxRunner: Isolated execution environment
- ExternalCommunicationGate: Approval system for external access

Usage:
    from hestia.execution import (
        get_tool_executor,
        get_tool_registry,
        ToolCall,
    )

    # Get executor singleton
    executor = await get_tool_executor()

    # Execute a tool call
    call = ToolCall.create("read_file", {"path": "~/hestia/data/test.txt"})
    result = await executor.execute(call)

    if result.success:
        print(result.output)
    else:
        print(f"Error: {result.error}")
"""

from .models import (
    Tool,
    ToolCall,
    ToolResult,
    ToolResultStatus,
    ToolParam,
    ToolParamType,
    ToolValidationResult,
    GateDecision,
    GateRequest,
    SandboxConfig,
)

from .registry import (
    ToolRegistry,
    ToolNotFoundError,
    ToolAlreadyRegisteredError,
    get_tool_registry,
    register_tool,
)

from .executor import (
    ToolExecutor,
    get_tool_executor,
)

from .sandbox import (
    SandboxRunner,
    SandboxViolationError,
    SandboxTimeoutError,
    get_sandbox_runner,
)

from .gate import (
    ExternalCommunicationGate,
    get_communication_gate,
)

from .tools import (
    read_file_tool,
    write_file_tool,
    list_directory_tool,
    search_files_tool,
    run_command_tool,
    register_builtin_tools,
)

__all__ = [
    # Models
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolResultStatus",
    "ToolParam",
    "ToolParamType",
    "ToolValidationResult",
    "GateDecision",
    "GateRequest",
    "SandboxConfig",
    # Registry
    "ToolRegistry",
    "ToolNotFoundError",
    "ToolAlreadyRegisteredError",
    "get_tool_registry",
    "register_tool",
    # Executor
    "ToolExecutor",
    "get_tool_executor",
    # Sandbox
    "SandboxRunner",
    "SandboxViolationError",
    "SandboxTimeoutError",
    "get_sandbox_runner",
    # Gate
    "ExternalCommunicationGate",
    "get_communication_gate",
    # Built-in tools
    "read_file_tool",
    "write_file_tool",
    "list_directory_tool",
    "search_files_tool",
    "run_command_tool",
    "register_builtin_tools",
]
