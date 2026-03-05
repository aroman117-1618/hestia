"""Tests for auth module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hestia_cli.auth import (
    get_stored_token,
    store_credentials,
    clear_credentials,
    register_with_invite,
    check_connection,
    SERVICE_NAME,
    TOKEN_KEY,
    DEVICE_ID_KEY,
)


class TestCredentialStorage:
    def test_store_and_retrieve(self):
        with patch('hestia_cli.auth.keyring') as mock_kr:
            mock_kr.get_password.return_value = "test-token"
            store_credentials("test-token", "dev-123")
            mock_kr.set_password.assert_any_call(SERVICE_NAME, TOKEN_KEY, "test-token")
            mock_kr.set_password.assert_any_call(SERVICE_NAME, DEVICE_ID_KEY, "dev-123")

            result = get_stored_token()
            assert result == "test-token"

    def test_clear_credentials(self):
        with patch('hestia_cli.auth.keyring') as mock_kr:
            clear_credentials()
            assert mock_kr.delete_password.call_count == 2


class TestRegisterWithInvite:
    @pytest.mark.asyncio
    async def test_register_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "token": "jwt-token-123",
            "device_id": "dev-abc",
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('hestia_cli.auth.httpx.AsyncClient', return_value=mock_client), \
             patch('hestia_cli.auth.store_credentials') as mock_store:
            token, device_id = await register_with_invite(
                "https://localhost:8443", "invite-token-xyz"
            )

        assert token == "jwt-token-123"
        assert device_id == "dev-abc"
        mock_store.assert_called_once_with("jwt-token-123", "dev-abc")


class TestTestConnection:
    @pytest.mark.asyncio
    async def test_server_reachable(self):
        mock_response = MagicMock(status_code=200)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock()

        with patch('hestia_cli.auth.httpx.AsyncClient', return_value=mock_client):
            result = await check_connection("https://localhost:8443")
        assert result is True

    @pytest.mark.asyncio
    async def test_server_unreachable(self):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch('hestia_cli.auth.httpx.AsyncClient', return_value=mock_client):
            result = await check_connection("https://localhost:8443")
        assert result is False
