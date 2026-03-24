"""Tests for DELAY node executor."""
import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from hestia.workflows.models import NodeType
from hestia.workflows.nodes import execute_delay, NODE_EXECUTORS


class TestDelayNode:
    """Tests for the DELAY node executor."""

    @pytest.mark.asyncio
    async def test_delay_returns_elapsed(self):
        """DELAY node should sleep and report elapsed time."""
        config = {"delay_seconds": 0.1}
        result = await execute_delay(config, {"input": "data"})
        assert result["delayed"] is True
        assert result["delay_seconds"] == 0.1
        assert "elapsed_ms" in result

    @pytest.mark.asyncio
    async def test_delay_zero_seconds(self):
        """Zero delay should complete immediately."""
        config = {"delay_seconds": 0}
        result = await execute_delay(config, {})
        assert result["delayed"] is True
        assert result["delay_seconds"] == 0

    @pytest.mark.asyncio
    async def test_delay_missing_config(self):
        """Missing delay_seconds should default to 0."""
        result = await execute_delay({}, {})
        assert result["delayed"] is True
        assert result["delay_seconds"] == 0

    @pytest.mark.asyncio
    async def test_delay_max_capped(self):
        """Delay should be capped at 180 days (15552000 seconds)."""
        config = {"delay_seconds": 99999999}
        max_delay = 180 * 86400  # 15552000
        with patch("hestia.workflows.nodes.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await execute_delay(config, {})
        assert result["delay_seconds"] == max_delay
        mock_sleep.assert_awaited_once_with(float(max_delay))

    @pytest.mark.asyncio
    async def test_delay_passes_input_through(self):
        """DELAY should pass input_data through as output (transparent pipe)."""
        config = {"delay_seconds": 0}
        input_data = {"response": "hello", "tokens": 42}
        result = await execute_delay(config, input_data)
        assert result["input_data"] == input_data

    def test_delay_registered_in_executors(self):
        """DELAY should be registered in NODE_EXECUTORS."""
        assert NodeType.DELAY in NODE_EXECUTORS

    def test_delay_in_node_type_enum(self):
        """DELAY should be a valid NodeType."""
        assert NodeType.DELAY.value == "delay"
