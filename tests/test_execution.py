"""
Tests for the execution layer.

Run with: python -m pytest tests/test_execution.py -v
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

from hestia.execution.models import (
    Tool,
    ToolCall,
    ToolResult,
    ToolResultStatus,
    ToolParam,
    ToolParamType,
    ToolValidationResult,
    GateDecision,
    SandboxConfig,
)
from hestia.execution.registry import (
    ToolRegistry,
    ToolNotFoundError,
    ToolAlreadyRegisteredError,
)
from hestia.execution.sandbox import (
    SandboxRunner,
    SandboxViolationError,
    SandboxTimeoutError,
)
from hestia.execution.gate import ExternalCommunicationGate
from hestia.execution.executor import ToolExecutor


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_tool() -> Tool:
    """Create a sample tool for testing."""
    async def handler(message: str, count: int = 1) -> str:
        return message * count

    return Tool(
        name="echo",
        description="Echo a message",
        parameters={
            "message": ToolParam(
                type=ToolParamType.STRING,
                description="Message to echo",
                required=True,
            ),
            "count": ToolParam(
                type=ToolParamType.INTEGER,
                description="Number of times to repeat",
                required=False,
                default=1,
            ),
        },
        handler=handler,
        timeout=10.0,
    )


@pytest.fixture
def registry() -> ToolRegistry:
    """Create a fresh tool registry."""
    return ToolRegistry()


@pytest.fixture
def sandbox_config(temp_dir: Path) -> SandboxConfig:
    """Create sandbox config with temp directory."""
    return SandboxConfig(
        enabled=True,
        mode="subprocess",
        default_timeout=10.0,
        max_timeout=30.0,
        allowed_directories=[str(temp_dir)],
        auto_approve_write_dirs=[str(temp_dir)],
    )


@pytest.fixture
def sandbox(sandbox_config: SandboxConfig) -> SandboxRunner:
    """Create a sandbox runner with test config."""
    return SandboxRunner(sandbox_config)


@pytest_asyncio.fixture
async def gate(temp_dir: Path) -> ExternalCommunicationGate:
    """Create a communication gate with temp database."""
    gate = ExternalCommunicationGate(db_path=temp_dir / "gate.db")
    await gate.connect()
    yield gate
    await gate.close()


# ============================================================================
# Model Tests
# ============================================================================


class TestModels:
    """Tests for data models."""

    def test_tool_param_to_json_schema(self):
        """Test ToolParam JSON schema conversion."""
        param = ToolParam(
            type=ToolParamType.STRING,
            description="A test parameter",
            required=True,
        )
        schema = param.to_json_schema()

        assert schema["type"] == "string"
        assert schema["description"] == "A test parameter"

    def test_tool_param_with_enum(self):
        """Test ToolParam with enum values."""
        param = ToolParam(
            type=ToolParamType.STRING,
            description="A choice",
            enum=["a", "b", "c"],
        )
        schema = param.to_json_schema()

        assert schema["enum"] == ["a", "b", "c"]

    def test_tool_creation(self, sample_tool: Tool):
        """Test Tool creation."""
        assert sample_tool.name == "echo"
        assert sample_tool.description == "Echo a message"
        assert len(sample_tool.parameters) == 2
        assert sample_tool.timeout == 10.0

    def test_tool_required_params(self, sample_tool: Tool):
        """Test getting required parameters."""
        required = sample_tool.get_required_params()
        assert "message" in required
        assert "count" not in required

    def test_tool_to_json_schema(self, sample_tool: Tool):
        """Test Tool JSON schema conversion."""
        schema = sample_tool.to_json_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "echo"
        assert "parameters" in schema["function"]
        assert "message" in schema["function"]["parameters"]["properties"]

    def test_tool_validation_empty_name(self):
        """Test Tool rejects empty name."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            Tool(
                name="",
                description="Test",
                parameters={},
                handler=lambda: None,
            )

    def test_tool_call_create(self):
        """Test ToolCall.create factory method."""
        call = ToolCall.create("test_tool", {"arg1": "value1"})

        assert call.tool_name == "test_tool"
        assert call.arguments == {"arg1": "value1"}
        assert call.id.startswith("tc-")

    def test_tool_call_serialization(self):
        """Test ToolCall serialization/deserialization."""
        call = ToolCall.create("test", {"key": "value"})
        data = call.to_dict()
        restored = ToolCall.from_dict(data)

        assert restored.id == call.id
        assert restored.tool_name == call.tool_name
        assert restored.arguments == call.arguments

    def test_tool_result_success(self):
        """Test successful ToolResult."""
        result = ToolResult(
            call_id="tc-123",
            tool_name="test",
            status=ToolResultStatus.SUCCESS,
            output="hello",
            duration_ms=100.0,
        )

        assert result.success is True
        assert result.output == "hello"

    def test_tool_result_failure(self):
        """Test failed ToolResult."""
        result = ToolResult(
            call_id="tc-123",
            tool_name="test",
            status=ToolResultStatus.ERROR,
            error="Something went wrong",
        )

        assert result.success is False
        assert result.error == "Something went wrong"

    def test_tool_result_message_content(self):
        """Test ToolResult message formatting."""
        success = ToolResult(
            call_id="tc-1",
            tool_name="echo",
            status=ToolResultStatus.SUCCESS,
            output="hello",
        )
        assert "executed successfully" in success.to_message_content()

        failure = ToolResult(
            call_id="tc-2",
            tool_name="echo",
            status=ToolResultStatus.ERROR,
            error="oops",
        )
        assert "failed" in failure.to_message_content()


# ============================================================================
# Registry Tests
# ============================================================================


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_register_tool(self, registry: ToolRegistry, sample_tool: Tool):
        """Test registering a tool."""
        registry.register(sample_tool)

        assert registry.has_tool("echo")
        assert len(registry) == 1

    def test_register_duplicate(self, registry: ToolRegistry, sample_tool: Tool):
        """Test registering duplicate tool raises error."""
        registry.register(sample_tool)

        with pytest.raises(ToolAlreadyRegisteredError):
            registry.register(sample_tool)

    def test_get_tool(self, registry: ToolRegistry, sample_tool: Tool):
        """Test getting a registered tool."""
        registry.register(sample_tool)

        tool = registry.get("echo")
        assert tool is not None
        assert tool.name == "echo"

    def test_get_nonexistent_tool(self, registry: ToolRegistry):
        """Test getting non-existent tool returns None."""
        assert registry.get("nonexistent") is None

    def test_get_required_raises(self, registry: ToolRegistry):
        """Test get_required raises for non-existent tool."""
        with pytest.raises(ToolNotFoundError):
            registry.get_required("nonexistent")

    def test_unregister_tool(self, registry: ToolRegistry, sample_tool: Tool):
        """Test unregistering a tool."""
        registry.register(sample_tool)
        registry.unregister("echo")

        assert not registry.has_tool("echo")

    def test_list_tools(self, registry: ToolRegistry, sample_tool: Tool):
        """Test listing all tools."""
        registry.register(sample_tool)

        tools = registry.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"

    def test_validate_call_success(self, registry: ToolRegistry, sample_tool: Tool):
        """Test successful call validation."""
        registry.register(sample_tool)
        call = ToolCall.create("echo", {"message": "hello"})

        result = registry.validate_call(call)

        assert result.valid is True

    def test_validate_call_missing_param(self, registry: ToolRegistry, sample_tool: Tool):
        """Test validation fails for missing required param."""
        registry.register(sample_tool)
        call = ToolCall.create("echo", {})  # Missing required "message"

        result = registry.validate_call(call)

        assert result.valid is False
        assert result.error_type == "MISSING_PARAM"

    def test_validate_call_unknown_param(self, registry: ToolRegistry, sample_tool: Tool):
        """Test validation fails for unknown param."""
        registry.register(sample_tool)
        call = ToolCall.create("echo", {"message": "hi", "unknown": "param"})

        result = registry.validate_call(call)

        assert result.valid is False
        assert result.error_type == "UNKNOWN_PARAM"

    def test_validate_call_tool_not_found(self, registry: ToolRegistry):
        """Test validation fails for non-existent tool."""
        call = ToolCall.create("nonexistent", {})

        result = registry.validate_call(call)

        assert result.valid is False
        assert result.error_type == "NOT_FOUND"

    def test_get_definitions_for_prompt(self, registry: ToolRegistry, sample_tool: Tool):
        """Test generating prompt definitions."""
        registry.register(sample_tool)

        definitions = registry.get_definitions_for_prompt()

        assert "echo" in definitions
        assert "message" in definitions

    def test_get_tool_descriptions(self, registry: ToolRegistry, sample_tool: Tool):
        """Test generating human-readable descriptions."""
        registry.register(sample_tool)

        descriptions = registry.get_tool_descriptions()

        assert "echo" in descriptions
        assert "Echo a message" in descriptions


# ============================================================================
# Sandbox Tests
# ============================================================================


class TestSandboxRunner:
    """Tests for SandboxRunner."""

    def test_path_allowed(self, sandbox: SandboxRunner, temp_dir: Path):
        """Test allowed path check."""
        test_file = temp_dir / "test.txt"
        assert sandbox.is_path_allowed(str(test_file)) is True

    def test_path_not_allowed(self, sandbox: SandboxRunner):
        """Test disallowed path check."""
        assert sandbox.is_path_allowed("/etc/passwd") is False

    def test_validate_path_raises(self, sandbox: SandboxRunner):
        """Test validate_path raises for disallowed path."""
        with pytest.raises(SandboxViolationError):
            sandbox.validate_path("/etc/passwd")

    def test_command_blocked(self, sandbox: SandboxRunner):
        """Test blocked command detection."""
        assert sandbox.is_command_blocked("rm -rf /") is True
        assert sandbox.is_command_blocked("sudo apt install") is True
        assert sandbox.is_command_blocked("ls -la") is False

    def test_validate_command_raises(self, sandbox: SandboxRunner):
        """Test validate_command raises for blocked command."""
        with pytest.raises(SandboxViolationError):
            sandbox.validate_command("sudo rm -rf /")

    @pytest.mark.asyncio
    async def test_run_handler(self, sandbox: SandboxRunner):
        """Test running a handler in sandbox."""
        async def handler(x: int, y: int) -> int:
            return x + y

        result = await sandbox.run(handler, {"x": 1, "y": 2}, timeout=5.0)
        assert result == 3

    @pytest.mark.asyncio
    async def test_run_timeout(self, sandbox: SandboxRunner):
        """Test sandbox timeout."""
        async def slow_handler() -> None:
            await asyncio.sleep(10)

        with pytest.raises(SandboxTimeoutError):
            await sandbox.run(slow_handler, {}, timeout=0.1)

    @pytest.mark.asyncio
    async def test_run_shell_command(self, sandbox: SandboxRunner, temp_dir: Path):
        """Test running shell command."""
        result = await sandbox.run_shell_command(
            "echo hello",
            working_dir=str(temp_dir),
            timeout=5.0,
        )

        assert result["returncode"] == 0
        assert "hello" in result["stdout"]

    def test_write_auto_approved(self, sandbox: SandboxRunner, temp_dir: Path):
        """Test write auto-approval check."""
        in_approved = temp_dir / "file.txt"
        assert sandbox.is_write_auto_approved(str(in_approved)) is True

        # Path outside auto-approve dirs
        assert sandbox.is_write_auto_approved("/tmp/other.txt") is False


# ============================================================================
# Gate Tests
# ============================================================================


class TestExternalCommunicationGate:
    """Tests for ExternalCommunicationGate."""

    @pytest.mark.asyncio
    async def test_check_approval_unwhitelisted(self, gate: ExternalCommunicationGate):
        """Test checking approval for unwhitelisted service."""
        decision = await gate.check_approval("unknown_service")
        assert decision == GateDecision.PENDING

    @pytest.mark.asyncio
    async def test_add_to_whitelist(self, gate: ExternalCommunicationGate):
        """Test adding service to whitelist."""
        await gate.add_to_whitelist("test_service", scope="all")

        decision = await gate.check_approval("test_service")
        assert decision == GateDecision.APPROVED

    @pytest.mark.asyncio
    async def test_remove_from_whitelist(self, gate: ExternalCommunicationGate):
        """Test removing service from whitelist."""
        await gate.add_to_whitelist("test_service")
        removed = await gate.remove_from_whitelist("test_service")

        assert removed is True
        decision = await gate.check_approval("test_service")
        assert decision == GateDecision.PENDING

    @pytest.mark.asyncio
    async def test_list_whitelist(self, gate: ExternalCommunicationGate):
        """Test listing whitelisted services."""
        await gate.add_to_whitelist("service1")
        await gate.add_to_whitelist("service2")

        whitelist = await gate.list_whitelist()

        assert len(whitelist) == 2
        services = [w["service"] for w in whitelist]
        assert "service1" in services
        assert "service2" in services

    @pytest.mark.asyncio
    async def test_is_whitelisted(self, gate: ExternalCommunicationGate):
        """Test is_whitelisted helper."""
        await gate.add_to_whitelist("approved_service")

        assert await gate.is_whitelisted("approved_service") is True
        assert await gate.is_whitelisted("other_service") is False

    @pytest.mark.asyncio
    async def test_request_approval_auto(self, gate: ExternalCommunicationGate):
        """Test auto-approval in request_approval."""
        decision = await gate.request_approval(
            service="new_service",
            action="execute",
            tool_name="test_tool",
            reason="Testing",
            auto_approve=True,
        )

        assert decision == GateDecision.APPROVED
        assert await gate.is_whitelisted("new_service") is True

    @pytest.mark.asyncio
    async def test_get_recent_decisions(self, gate: ExternalCommunicationGate):
        """Test retrieving recent gate decisions."""
        await gate.request_approval(
            service="service1",
            action="execute",
            tool_name="tool1",
            reason="Test 1",
        )

        decisions = await gate.get_recent_decisions(limit=10)
        assert len(decisions) >= 1


# ============================================================================
# Executor Tests
# ============================================================================


class TestToolExecutor:
    """Tests for ToolExecutor."""

    @pytest_asyncio.fixture
    async def executor(
        self,
        temp_dir: Path,
        sample_tool: Tool,
    ) -> ToolExecutor:
        """Create a tool executor with test setup."""
        registry = ToolRegistry()
        registry.register(sample_tool)

        sandbox_config = SandboxConfig(
            enabled=True,
            allowed_directories=[str(temp_dir)],
            auto_approve_write_dirs=[str(temp_dir)],
        )
        sandbox = SandboxRunner(sandbox_config)

        gate = ExternalCommunicationGate(db_path=temp_dir / "gate.db")
        await gate.connect()

        executor = ToolExecutor(
            registry=registry,
            sandbox=sandbox,
            gate=gate,
        )

        yield executor
        await gate.close()

    @pytest.mark.asyncio
    async def test_execute_success(self, executor: ToolExecutor):
        """Test successful tool execution."""
        call = ToolCall.create("echo", {"message": "hello"})

        result = await executor.execute(call)

        assert result.success is True
        assert result.output == "hello"
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, executor: ToolExecutor):
        """Test execution of non-existent tool."""
        call = ToolCall.create("nonexistent", {})

        result = await executor.execute(call)

        assert result.success is False
        assert result.status == ToolResultStatus.NOT_FOUND

    @pytest.mark.asyncio
    async def test_execute_missing_param(self, executor: ToolExecutor):
        """Test execution with missing required param."""
        call = ToolCall.create("echo", {})  # Missing "message"

        result = await executor.execute(call)

        assert result.success is False
        assert result.status == ToolResultStatus.ERROR

    @pytest.mark.asyncio
    async def test_execute_batch(self, executor: ToolExecutor):
        """Test batch execution."""
        calls = [
            ToolCall.create("echo", {"message": "a"}),
            ToolCall.create("echo", {"message": "b"}),
            ToolCall.create("echo", {"message": "c"}),
        ]

        results = await executor.execute_batch(calls)

        assert len(results) == 3
        assert all(r.success for r in results)
        outputs = [r.output for r in results]
        assert "a" in outputs
        assert "b" in outputs
        assert "c" in outputs

    @pytest.mark.asyncio
    async def test_execute_batch_empty(self, executor: ToolExecutor):
        """Test batch execution with empty list."""
        results = await executor.execute_batch([])
        assert results == []

    @pytest.mark.asyncio
    async def test_get_tool_definitions(self, executor: ToolExecutor):
        """Test getting tool definitions."""
        definitions = executor.get_tool_definitions()

        assert "echo" in definitions
        assert "message" in definitions


# ============================================================================
# Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests for execution layer."""

    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_full_execution_pipeline(self, temp_dir: Path):
        """Test complete execution from registry to result."""
        # Setup
        async def file_reader(path: str) -> str:
            return Path(path).read_text()

        tool = Tool(
            name="read_test",
            description="Read a test file",
            parameters={
                "path": ToolParam(
                    type=ToolParamType.STRING,
                    required=True,
                ),
            },
            handler=file_reader,
            allowed_paths=[str(temp_dir)],
        )

        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("hello world")

        # Setup components
        registry = ToolRegistry()
        registry.register(tool)

        sandbox = SandboxRunner(SandboxConfig(
            allowed_directories=[str(temp_dir)],
        ))

        gate = ExternalCommunicationGate(db_path=temp_dir / "gate.db")
        await gate.connect()

        executor = ToolExecutor(registry=registry, sandbox=sandbox, gate=gate)

        # Execute
        call = ToolCall.create("read_test", {"path": str(test_file)})
        result = await executor.execute(call)

        # Verify
        assert result.success is True
        assert result.output == "hello world"

        await gate.close()


# ============================================================================
# Manual Test Runner
# ============================================================================


if __name__ == "__main__":
    async def main():
        print("Running execution layer tests...")
        print("Use: python -m pytest tests/test_execution.py -v")

    asyncio.run(main())
