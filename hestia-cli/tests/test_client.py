"""Tests for WebSocket client."""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hestia_cli.client import (
    HestiaWSClient,
    ConnectionError,
    AuthenticationError,
)


class TestHestiaWSClient:
    def test_ws_url_from_https(self):
        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }):
            client = HestiaWSClient(server_url="https://localhost:8443")
        assert client.ws_url == "wss://localhost:8443/v1/ws/chat"

    def test_ws_url_from_http(self):
        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "http://localhost:8080", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }):
            client = HestiaWSClient(server_url="http://localhost:8080")
        assert client.ws_url == "ws://localhost:8080/v1/ws/chat"

    def test_initial_state(self):
        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }):
            client = HestiaWSClient()
        assert not client.connected
        assert client.mode == "tia"
        assert client.device_id is None


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_no_token_raises(self):
        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }), \
        patch('hestia_cli.client.get_stored_token', return_value=None):
            client = HestiaWSClient()
            with pytest.raises(AuthenticationError, match="No stored token"):
                await client.connect()

    @pytest.mark.asyncio
    async def test_connect_success(self):
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({
            "type": "auth_result",
            "success": True,
            "device_id": "dev-123",
        }))

        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }), \
        patch('hestia_cli.client.get_stored_token', return_value="jwt-token"), \
        patch('hestia_cli.client.get_stored_device_id', return_value="dev-123"), \
        patch('hestia_cli.client.websockets.connect', new_callable=AsyncMock, return_value=mock_ws):
            client = HestiaWSClient()
            result = await client.connect()

        assert result.success is True
        assert result.device_id == "dev-123"
        assert client.connected

    @pytest.mark.asyncio
    async def test_connect_auth_failure(self):
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(return_value=json.dumps({
            "type": "auth_result",
            "success": False,
            "error": "Invalid token",
        }))

        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }), \
        patch('hestia_cli.client.get_stored_token', return_value="bad-token"), \
        patch('hestia_cli.client.websockets.connect', new_callable=AsyncMock, return_value=mock_ws):
            client = HestiaWSClient()
            with pytest.raises(AuthenticationError, match="Invalid token"):
                await client.connect()


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_send_message_yields_events(self):
        events = [
            {"type": "status", "stage": "inference"},
            {"type": "token", "content": "Hello", "request_id": "req-1"},
            {"type": "done", "request_id": "req-1", "metrics": {}, "mode": "tia"},
        ]

        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(side_effect=[json.dumps(e) for e in events])

        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }):
            client = HestiaWSClient()
            client._ws = mock_ws
            client._connected = True

            received = [event async for event in client.send_message("Hello")]

        assert len(received) == 3
        assert received[0]["type"] == "status"
        assert received[1]["type"] == "token"
        assert received[2]["type"] == "done"

    @pytest.mark.asyncio
    async def test_send_message_not_connected_raises(self):
        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }):
            client = HestiaWSClient()
            with pytest.raises(ConnectionError, match="Not connected"):
                async for _ in client.send_message("Hello"):
                    pass


class TestToolApproval:
    @pytest.mark.asyncio
    async def test_send_tool_approval(self):
        mock_ws = AsyncMock()

        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }):
            client = HestiaWSClient()
            client._ws = mock_ws
            client._connected = True

            await client.send_tool_approval("tc-001", approved=True)

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["type"] == "tool_approval"
        assert sent["call_id"] == "tc-001"
        assert sent["approved"] is True


class TestCancel:
    @pytest.mark.asyncio
    async def test_send_cancel(self):
        mock_ws = AsyncMock()

        with patch('hestia_cli.client.load_config', return_value={
            "server": {"url": "https://localhost:8443", "verify_ssl": False},
            "preferences": {"default_mode": "tia"},
        }):
            client = HestiaWSClient()
            client._ws = mock_ws
            client._connected = True

            await client.send_cancel()

        sent = json.loads(mock_ws.send.call_args[0][0])
        assert sent["type"] == "cancel"
