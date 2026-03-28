"""Tests for hestia.dev.engineer — EngineerAgent tool loop execution."""
from __future__ import annotations

from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hestia.dev.engineer import EngineerAgent, MAX_TOOL_ITERATIONS, MAX_TOKENS_PER_SUBTASK
from hestia.dev.models import AgentTier, DevSession, DevSessionSource
from hestia.dev.safety import AuthorityMatrix
from hestia.inference import InferenceResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def session() -> DevSession:
    return DevSession.create(
        title="Test engineer subtask",
        description="Implement a new feature",
        source=DevSessionSource.CLI,
    )


@pytest.fixture()
def subtask() -> Dict[str, Any]:
    return {
        "title": "Edit handler.py",
        "description": "Add a new route handler",
        "acceptance_criteria": "New endpoint returns 200",
        "target_files": ["hestia/api/routes/handler.py"],
    }


def _make_response(
    content: str = "Done.",
    tokens_in: int = 300,
    tokens_out: int = 100,
    tool_calls=None,
) -> InferenceResponse:
    """Build a minimal InferenceResponse for mocking."""
    return InferenceResponse(
        content=content,
        model="claude-sonnet-4-20250514",
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        duration_ms=250.0,
        tool_calls=tool_calls,
    )


def _make_cloud_client(response: InferenceResponse) -> MagicMock:
    """Return a mock cloud client whose complete() returns *response*."""
    client = MagicMock()
    client.complete = AsyncMock(return_value=response)
    return client


# ---------------------------------------------------------------------------
# Helper: suppress ToolExecutor and ToolRegistry I/O in all tests
# ---------------------------------------------------------------------------

def _patch_execution():
    """Context managers that stub out get_tool_executor and get_tool_registry."""
    mock_registry = MagicMock()
    mock_registry.get_definitions_as_list.return_value = [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Edit a file.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_github_pr",
                "description": "Create a PR.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
    ]

    mock_executor = MagicMock()
    mock_executor.execute = AsyncMock()

    return (
        patch("hestia.dev.engineer.get_tool_registry", return_value=mock_registry),
        patch("hestia.dev.engineer.get_tool_executor", new=AsyncMock(return_value=mock_executor)),
    )


# ---------------------------------------------------------------------------
# Tests: simple path (no tool calls)
# ---------------------------------------------------------------------------

class TestExecuteSubtaskSimplePath:
    """Tests covering the happy-path where the model returns text immediately."""

    @pytest.mark.asyncio
    async def test_returns_content(self, session: DevSession, subtask: Dict[str, Any]) -> None:
        """execute_subtask result contains the model's response text."""
        response = _make_response(content="File edited successfully.")
        client = _make_cloud_client(response)
        agent = EngineerAgent(cloud_client=client)

        p1, p2 = _patch_execution()
        with p1, p2:
            result = await agent.execute_subtask(session, subtask)

        assert result["content"] == "File edited successfully."

    @pytest.mark.asyncio
    async def test_returns_tokens_used(self, session: DevSession, subtask: Dict[str, Any]) -> None:
        """execute_subtask result includes total tokens consumed."""
        response = _make_response(tokens_in=300, tokens_out=100)
        client = _make_cloud_client(response)
        agent = EngineerAgent(cloud_client=client)

        p1, p2 = _patch_execution()
        with p1, p2:
            result = await agent.execute_subtask(session, subtask)

        assert result["tokens_used"] == 400

    @pytest.mark.asyncio
    async def test_returns_zero_iterations_when_no_tools(
        self, session: DevSession, subtask: Dict[str, Any]
    ) -> None:
        """Iterations counter is 0 when the model makes no tool calls."""
        response = _make_response(tool_calls=None)
        client = _make_cloud_client(response)
        agent = EngineerAgent(cloud_client=client)

        p1, p2 = _patch_execution()
        with p1, p2:
            result = await agent.execute_subtask(session, subtask)

        assert result["iterations"] == 0

    @pytest.mark.asyncio
    async def test_returns_files_affected(self, session: DevSession, subtask: Dict[str, Any]) -> None:
        """execute_subtask propagates target_files into files_affected."""
        response = _make_response()
        client = _make_cloud_client(response)
        agent = EngineerAgent(cloud_client=client)

        p1, p2 = _patch_execution()
        with p1, p2:
            result = await agent.execute_subtask(session, subtask)

        assert result["files_affected"] == subtask["target_files"]

    @pytest.mark.asyncio
    async def test_result_has_required_keys(
        self, session: DevSession, subtask: Dict[str, Any]
    ) -> None:
        """Result dict always contains content, tokens_used, iterations, files_affected."""
        response = _make_response()
        client = _make_cloud_client(response)
        agent = EngineerAgent(cloud_client=client)

        p1, p2 = _patch_execution()
        with p1, p2:
            result = await agent.execute_subtask(session, subtask)

        for key in ("content", "tokens_used", "iterations", "files_affected"):
            assert key in result


# ---------------------------------------------------------------------------
# Tests: AuthorityMatrix tool filtering
# ---------------------------------------------------------------------------

class TestAuthorityMatrixFiltering:
    """Tests that verify the Engineer tier's tool access boundaries."""

    def test_engineer_can_use_edit_file(self) -> None:
        """edit_file is in the Engineer's allowed tool set."""
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "edit_file") is True

    def test_engineer_can_use_read_file(self) -> None:
        """read_file is a universal tool available to all tiers."""
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "read_file") is True

    def test_engineer_cannot_use_create_github_pr(self) -> None:
        """create_github_pr is reserved for the Architect tier only."""
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "create_github_pr") is False

    def test_engineer_cannot_use_merge_github_pr(self) -> None:
        """merge_github_pr is not in the Engineer's allowed set."""
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "merge_github_pr") is False

    @pytest.mark.asyncio
    async def test_tool_filtering_excludes_unauthorized(
        self, session: DevSession, subtask: Dict[str, Any]
    ) -> None:
        """get_definitions_as_list result is filtered so create_github_pr is absent."""
        response = _make_response()
        client = _make_cloud_client(response)
        agent = EngineerAgent(cloud_client=client)

        # Capture what tools are passed to cloud_client.complete
        captured_tools: Dict[str, Any] = {}

        async def capturing_complete(**kwargs: Any) -> InferenceResponse:
            captured_tools["tools"] = kwargs.get("tools", [])
            return response

        client.complete = capturing_complete

        p1, p2 = _patch_execution()
        with p1, p2:
            await agent.execute_subtask(session, subtask)

        tool_names = [t["function"]["name"] for t in (captured_tools.get("tools") or [])]
        assert "create_github_pr" not in tool_names
        # edit_file and read_file should be present
        assert "edit_file" in tool_names
        assert "read_file" in tool_names


# ---------------------------------------------------------------------------
# Tests: memory_bridge integration
# ---------------------------------------------------------------------------

class TestMemoryBridgeIntegration:
    """Tests that verify memory_bridge is called and failures are silenced."""

    @pytest.mark.asyncio
    async def test_executes_without_memory_bridge(
        self, session: DevSession, subtask: Dict[str, Any]
    ) -> None:
        """Agent runs normally when no memory_bridge is provided."""
        response = _make_response()
        client = _make_cloud_client(response)
        agent = EngineerAgent(cloud_client=client, memory_bridge=None)

        p1, p2 = _patch_execution()
        with p1, p2:
            result = await agent.execute_subtask(session, subtask)

        assert "content" in result

    @pytest.mark.asyncio
    async def test_memory_bridge_failure_is_silenced(
        self, session: DevSession, subtask: Dict[str, Any]
    ) -> None:
        """A failing memory_bridge does not propagate an exception."""
        response = _make_response()
        client = _make_cloud_client(response)

        bridge = MagicMock()
        bridge.retrieve_for_engineer = AsyncMock(side_effect=RuntimeError("DB unavailable"))
        bridge.retrieve_invariants = AsyncMock(side_effect=RuntimeError("DB unavailable"))

        agent = EngineerAgent(cloud_client=client, memory_bridge=bridge)

        p1, p2 = _patch_execution()
        with p1, p2:
            result = await agent.execute_subtask(session, subtask)

        assert "content" in result
