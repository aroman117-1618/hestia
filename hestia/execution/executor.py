"""
Tool executor for running tools with sandboxing and gating.

Main entry point for tool execution in the Hestia system.
"""

import asyncio
import time
from typing import List, Optional

from .models import (
    GateDecision,
    GateRequest,
    ToolCall,
    ToolResult,
    ToolResultStatus,
    ToolValidationResult,
)
from .registry import ToolRegistry, get_tool_registry
from .sandbox import SandboxRunner, SandboxTimeoutError, SandboxViolationError, get_sandbox_runner
from .gate import ExternalCommunicationGate, get_communication_gate


class ToolExecutor:
    """
    Executes tools with validation, sandboxing, and gating.

    Orchestrates the full tool execution pipeline:
    1. Validate tool call
    2. Check external communication gate (if required)
    3. Execute in sandbox
    4. Return result
    """

    MAX_CONCURRENT_TOOLS = 3  # Max parallel tool executions

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        sandbox: Optional[SandboxRunner] = None,
        gate: Optional[ExternalCommunicationGate] = None,
    ):
        """
        Initialize the tool executor.

        Args:
            registry: Tool registry (uses singleton if not provided)
            sandbox: Sandbox runner (uses singleton if not provided)
            gate: Communication gate (uses singleton if not provided)
        """
        self.registry = registry or get_tool_registry()
        self.sandbox = sandbox or get_sandbox_runner()
        self._gate = gate
        self._gate_initialized = False

    async def _get_gate(self) -> ExternalCommunicationGate:
        """Get the communication gate, initializing if needed."""
        if self._gate is None:
            self._gate = await get_communication_gate()
            self._gate_initialized = True
        return self._gate

    async def execute(
        self,
        call: ToolCall,
        request_id: Optional[str] = None,
    ) -> ToolResult:
        """
        Execute a single tool call.

        Args:
            call: Tool call to execute
            request_id: Request ID for logging/tracing

        Returns:
            ToolResult with execution outcome
        """
        start_time = time.time()

        # 1. Validate the call
        validation = self.registry.validate_call(call)
        if not validation.valid:
            return ToolResult(
                call_id=call.id,
                tool_name=call.tool_name,
                status=ToolResultStatus.NOT_FOUND if validation.error_type == "NOT_FOUND" else ToolResultStatus.ERROR,
                error=validation.message,
                duration_ms=(time.time() - start_time) * 1000,
            )

        # 2. Get the tool
        tool = self.registry.get_required(call.tool_name)

        # 3. Check external communication gate
        if tool.requires_approval:
            gate = await self._get_gate()
            decision = await gate.check_approval(
                service=call.tool_name,
                action="execute",
            )

            if decision != GateDecision.APPROVED:
                # Record the pending request
                gate_request = GateRequest.create(
                    service=call.tool_name,
                    action="execute",
                    tool_name=call.tool_name,
                    reason=f"Tool execution requested with args: {list(call.arguments.keys())}",
                )
                await gate.record_decision(gate_request, decision)

                return ToolResult(
                    call_id=call.id,
                    tool_name=call.tool_name,
                    status=ToolResultStatus.DENIED,
                    error=f"Tool '{call.tool_name}' requires approval. Status: {decision.value}",
                    duration_ms=(time.time() - start_time) * 1000,
                )

        # 4. Execute in sandbox
        try:
            output = await self.sandbox.run(
                handler=tool.handler,
                args=call.arguments,
                timeout=tool.timeout,
                allowed_paths=tool.allowed_paths,
            )

            return ToolResult(
                call_id=call.id,
                tool_name=call.tool_name,
                status=ToolResultStatus.SUCCESS,
                output=output,
                duration_ms=(time.time() - start_time) * 1000,
            )

        except SandboxTimeoutError as e:
            return ToolResult(
                call_id=call.id,
                tool_name=call.tool_name,
                status=ToolResultStatus.TIMEOUT,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except SandboxViolationError as e:
            return ToolResult(
                call_id=call.id,
                tool_name=call.tool_name,
                status=ToolResultStatus.DENIED,
                error=str(e),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return ToolResult(
                call_id=call.id,
                tool_name=call.tool_name,
                status=ToolResultStatus.ERROR,
                error=f"{type(e).__name__}: {str(e)}",
                duration_ms=(time.time() - start_time) * 1000,
            )

    async def execute_batch(
        self,
        calls: List[ToolCall],
        request_id: Optional[str] = None,
    ) -> List[ToolResult]:
        """
        Execute multiple tool calls.

        Executes tools in parallel with concurrency limit.

        Args:
            calls: List of tool calls to execute
            request_id: Request ID for logging/tracing

        Returns:
            List of ToolResults in same order as calls
        """
        if not calls:
            return []

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_TOOLS)

        async def execute_with_semaphore(call: ToolCall) -> ToolResult:
            async with semaphore:
                return await self.execute(call, request_id)

        # Execute all calls with concurrency limit
        tasks = [execute_with_semaphore(call) for call in calls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert any exceptions to ToolResults
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(ToolResult(
                    call_id=calls[i].id,
                    tool_name=calls[i].tool_name,
                    status=ToolResultStatus.ERROR,
                    error=f"Unexpected error: {type(result).__name__}: {str(result)}",
                ))
            else:
                final_results.append(result)

        return final_results

    async def validate_call(self, call: ToolCall) -> ToolValidationResult:
        """
        Validate a tool call without executing.

        Args:
            call: Tool call to validate

        Returns:
            Validation result
        """
        return self.registry.validate_call(call)

    async def check_gate(
        self,
        tool_name: str,
        action: str = "execute",
    ) -> GateDecision:
        """
        Check if a tool can be executed through the gate.

        Args:
            tool_name: Name of the tool
            action: Action to check

        Returns:
            GateDecision
        """
        tool = self.registry.get(tool_name)
        if tool is None:
            return GateDecision.DENIED

        if not tool.requires_approval:
            return GateDecision.APPROVED

        gate = await self._get_gate()
        return await gate.check_approval(tool_name, action)

    async def approve_tool(
        self,
        tool_name: str,
        scope: str = "all",
        notes: Optional[str] = None,
    ) -> None:
        """
        Pre-approve a tool for execution.

        Args:
            tool_name: Name of the tool to approve
            scope: Approval scope
            notes: Optional notes
        """
        gate = await self._get_gate()
        await gate.add_to_whitelist(tool_name, scope, notes)

    def get_tool_definitions(self) -> str:
        """
        Get tool definitions for prompt injection.

        Returns:
            JSON string of tool definitions
        """
        return self.registry.get_definitions_for_prompt()

    def get_tool_descriptions(self) -> str:
        """
        Get human-readable tool descriptions.

        Returns:
            Formatted string of tool descriptions
        """
        return self.registry.get_tool_descriptions()


# Module-level singleton
_executor: Optional[ToolExecutor] = None


async def get_tool_executor() -> ToolExecutor:
    """
    Get the global tool executor singleton.

    Returns:
        Shared ToolExecutor instance
    """
    global _executor
    if _executor is None:
        _executor = ToolExecutor()
    return _executor
