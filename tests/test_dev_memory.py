"""Tests for hestia.dev.memory_bridge — DevMemoryBridge and MemoryType."""
from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest

from hestia.dev.memory_bridge import DevMemoryBridge, MemoryType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_memory_manager() -> MagicMock:
    """Return a mock MemoryManager with async store_exchange and build_context."""
    mm = MagicMock()
    mm.store_exchange = AsyncMock(return_value=(MagicMock(), MagicMock()))
    mm.build_context = AsyncMock(return_value="retrieved context")
    return mm


@pytest.fixture
def bridge(mock_memory_manager: MagicMock) -> DevMemoryBridge:
    """Return a DevMemoryBridge wired to a mock MemoryManager."""
    return DevMemoryBridge(mock_memory_manager)


# ---------------------------------------------------------------------------
# TestMemoryType
# ---------------------------------------------------------------------------

class TestMemoryType:
    def test_all_values_defined(self) -> None:
        expected = {
            "dev_session_summary",
            "dev_technical_learning",
            "dev_failure_pattern",
            "dev_codebase_invariant",
        }
        actual = {m.value for m in MemoryType}
        assert actual == expected

    def test_session_summary_value(self) -> None:
        assert MemoryType.SESSION_SUMMARY.value == "dev_session_summary"

    def test_technical_learning_value(self) -> None:
        assert MemoryType.TECHNICAL_LEARNING.value == "dev_technical_learning"

    def test_failure_pattern_value(self) -> None:
        assert MemoryType.FAILURE_PATTERN.value == "dev_failure_pattern"

    def test_codebase_invariant_value(self) -> None:
        assert MemoryType.CODEBASE_INVARIANT.value == "dev_codebase_invariant"


# ---------------------------------------------------------------------------
# TestStoreSessionSummary
# ---------------------------------------------------------------------------

class TestStoreSessionSummary:
    @pytest.mark.asyncio
    async def test_calls_store_exchange(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_session_summary(
            session_id="dev-abc123",
            title="Add memory bridge",
            description="Implemented DevMemoryBridge for 4 memory types.",
            files_changed=["hestia/dev/memory_bridge.py"],
            key_decisions=["Use store_exchange as the single write path"],
        )
        mock_memory_manager.store_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_message_contains_type_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_session_summary(
            session_id="s1",
            title="T",
            description="D",
            files_changed=[],
            key_decisions=[],
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert "[DEV SESSION SUMMARY]" in call_kwargs["user_message"]

    @pytest.mark.asyncio
    async def test_assistant_message_contains_type_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_session_summary(
            session_id="s1",
            title="T",
            description="D",
            files_changed=[],
            key_decisions=[],
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert "[DEV SESSION SUMMARY]" in call_kwargs["assistant_message"]

    @pytest.mark.asyncio
    async def test_metadata_contains_memory_type(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_session_summary(
            session_id="s1",
            title="T",
            description="D",
            files_changed=[],
            key_decisions=[],
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["memory_type"] == MemoryType.SESSION_SUMMARY.value

    @pytest.mark.asyncio
    async def test_metadata_contains_session_id(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_session_summary(
            session_id="dev-xyz",
            title="T",
            description="D",
            files_changed=[],
            key_decisions=[],
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["session_id"] == "dev-xyz"


# ---------------------------------------------------------------------------
# TestStoreTechnicalLearning
# ---------------------------------------------------------------------------

class TestStoreTechnicalLearning:
    @pytest.mark.asyncio
    async def test_calls_store_exchange(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_technical_learning(
            session_id="s1",
            file_path="hestia/memory/manager.py",
            learning="store_exchange accepts metadata kwarg",
            file_content_hash="abc123def456789a",
        )
        mock_memory_manager.store_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_message_contains_type_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_technical_learning(
            session_id="s1",
            file_path="f.py",
            learning="learning text",
            file_content_hash="hash",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert "[DEV TECHNICAL LEARNING]" in call_kwargs["user_message"]

    @pytest.mark.asyncio
    async def test_assistant_message_contains_type_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_technical_learning(
            session_id="s1",
            file_path="f.py",
            learning="learning text",
            file_content_hash="hash",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert "[DEV TECHNICAL LEARNING]" in call_kwargs["assistant_message"]

    @pytest.mark.asyncio
    async def test_metadata_contains_file_path(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_technical_learning(
            session_id="s1",
            file_path="hestia/dev/memory_bridge.py",
            learning="some learning",
            file_content_hash="aabbccdd11223344",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["file_path"] == "hestia/dev/memory_bridge.py"

    @pytest.mark.asyncio
    async def test_metadata_contains_file_hash(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_technical_learning(
            session_id="s1",
            file_path="f.py",
            learning="some learning",
            file_content_hash="deadbeef12345678",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["file_hash"] == "deadbeef12345678"

    @pytest.mark.asyncio
    async def test_metadata_contains_memory_type(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_technical_learning(
            session_id="s1",
            file_path="f.py",
            learning="learning",
            file_content_hash="h",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["memory_type"] == MemoryType.TECHNICAL_LEARNING.value


# ---------------------------------------------------------------------------
# TestStoreFailurePattern
# ---------------------------------------------------------------------------

class TestStoreFailurePattern:
    @pytest.mark.asyncio
    async def test_calls_store_exchange(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_failure_pattern(
            session_id="s1",
            approach="Direct DB write without transaction",
            failure_reason="Race condition under concurrent load",
            resolution="Wrap writes in an explicit transaction",
        )
        mock_memory_manager.store_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_message_contains_type_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_failure_pattern(
            session_id="s1",
            approach="approach",
            failure_reason="reason",
            resolution="resolution",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert "[DEV FAILURE PATTERN]" in call_kwargs["user_message"]

    @pytest.mark.asyncio
    async def test_assistant_message_contains_type_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_failure_pattern(
            session_id="s1",
            approach="approach",
            failure_reason="reason",
            resolution="resolution",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert "[DEV FAILURE PATTERN]" in call_kwargs["assistant_message"]

    @pytest.mark.asyncio
    async def test_metadata_contains_memory_type(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_failure_pattern(
            session_id="s1",
            approach="a",
            failure_reason="r",
            resolution="res",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["memory_type"] == MemoryType.FAILURE_PATTERN.value

    @pytest.mark.asyncio
    async def test_metadata_contains_session_id(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_failure_pattern(
            session_id="dev-fail-01",
            approach="a",
            failure_reason="r",
            resolution="res",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["session_id"] == "dev-fail-01"


# ---------------------------------------------------------------------------
# TestStoreCodebaseInvariant
# ---------------------------------------------------------------------------

class TestStoreCodebaseInvariant:
    @pytest.mark.asyncio
    async def test_calls_store_exchange(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_codebase_invariant(
            invariant="Always use get_logger() with no arguments",
            discovered_in="dev-session-001",
        )
        mock_memory_manager.store_exchange.assert_called_once()

    @pytest.mark.asyncio
    async def test_user_message_contains_type_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_codebase_invariant(
            invariant="Rule",
            discovered_in="ctx",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert "[DEV CODEBASE INVARIANT]" in call_kwargs["user_message"]

    @pytest.mark.asyncio
    async def test_assistant_message_contains_type_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_codebase_invariant(
            invariant="Rule",
            discovered_in="ctx",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert "[DEV CODEBASE INVARIANT]" in call_kwargs["assistant_message"]

    @pytest.mark.asyncio
    async def test_metadata_contains_memory_type(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_codebase_invariant(invariant="Rule", discovered_in="ctx")
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["memory_type"] == MemoryType.CODEBASE_INVARIANT.value

    @pytest.mark.asyncio
    async def test_metadata_contains_discovered_in(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.store_codebase_invariant(
            invariant="Rule",
            discovered_in="dev-session-xyz",
        )
        call_kwargs = mock_memory_manager.store_exchange.call_args.kwargs
        assert call_kwargs["metadata"]["discovered_in"] == "dev-session-xyz"


# ---------------------------------------------------------------------------
# TestRetrieveMethods
# ---------------------------------------------------------------------------

class TestRetrieveMethods:
    @pytest.mark.asyncio
    async def test_retrieve_for_architect_calls_build_context(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        result = await bridge.retrieve_for_architect("Add a new trading strategy")
        mock_memory_manager.build_context.assert_called_once()
        assert result == "retrieved context"

    @pytest.mark.asyncio
    async def test_retrieve_for_architect_includes_task_in_query(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.retrieve_for_architect("my task description")
        call_kwargs = mock_memory_manager.build_context.call_args.kwargs
        assert "my task description" in call_kwargs["query"]

    @pytest.mark.asyncio
    async def test_retrieve_for_engineer_calls_build_context(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        result = await bridge.retrieve_for_engineer(["hestia/memory/manager.py"])
        mock_memory_manager.build_context.assert_called_once()
        assert result == "retrieved context"

    @pytest.mark.asyncio
    async def test_retrieve_for_engineer_includes_file_path_in_query(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.retrieve_for_engineer(["hestia/dev/memory_bridge.py", "tests/test_dev_memory.py"])
        call_kwargs = mock_memory_manager.build_context.call_args.kwargs
        assert "hestia/dev/memory_bridge.py" in call_kwargs["query"]

    @pytest.mark.asyncio
    async def test_retrieve_for_researcher_calls_build_context(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        result = await bridge.retrieve_for_researcher("memory architecture")
        mock_memory_manager.build_context.assert_called_once()
        assert result == "retrieved context"

    @pytest.mark.asyncio
    async def test_retrieve_for_researcher_includes_topic_in_query(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.retrieve_for_researcher("ChromaDB embedding dedup")
        call_kwargs = mock_memory_manager.build_context.call_args.kwargs
        assert "ChromaDB embedding dedup" in call_kwargs["query"]

    @pytest.mark.asyncio
    async def test_retrieve_invariants_calls_build_context(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        result = await bridge.retrieve_invariants()
        mock_memory_manager.build_context.assert_called_once()
        assert result == "retrieved context"

    @pytest.mark.asyncio
    async def test_retrieve_invariants_query_targets_invariant_tag(
        self, bridge: DevMemoryBridge, mock_memory_manager: MagicMock
    ) -> None:
        await bridge.retrieve_invariants()
        call_kwargs = mock_memory_manager.build_context.call_args.kwargs
        assert "INVARIANT" in call_kwargs["query"].upper()


# ---------------------------------------------------------------------------
# TestComputeFileHash
# ---------------------------------------------------------------------------

class TestComputeFileHash:
    def test_returns_16_char_hex_string(self) -> None:
        result = DevMemoryBridge.compute_file_hash("hello world")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def test_matches_sha256_first_16_chars(self) -> None:
        content = "def foo(): pass\n"
        expected = hashlib.sha256(content.encode()).hexdigest()[:16]
        assert DevMemoryBridge.compute_file_hash(content) == expected

    def test_empty_string(self) -> None:
        result = DevMemoryBridge.compute_file_hash("")
        expected = hashlib.sha256(b"").hexdigest()[:16]
        assert result == expected

    def test_different_content_produces_different_hash(self) -> None:
        h1 = DevMemoryBridge.compute_file_hash("version 1")
        h2 = DevMemoryBridge.compute_file_hash("version 2")
        assert h1 != h2

    def test_same_content_produces_same_hash(self) -> None:
        content = "stable content"
        assert DevMemoryBridge.compute_file_hash(content) == DevMemoryBridge.compute_file_hash(content)
