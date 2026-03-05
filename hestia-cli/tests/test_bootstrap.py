"""Tests for the zero-friction bootstrap module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from rich.console import Console

from hestia_cli.bootstrap import (
    _is_localhost,
    _get_installed_models,
    ensure_server_running,
    ensure_authenticated,
    ensure_models_available,
)


# --- _is_localhost tests ---


class TestIsLocalhost:
    def test_localhost(self):
        assert _is_localhost("https://localhost:8443") is True

    def test_127_0_0_1(self):
        assert _is_localhost("https://127.0.0.1:8443") is True

    def test_ipv6_loopback(self):
        assert _is_localhost("https://[::1]:8443") is True

    def test_remote_hostname(self):
        assert _is_localhost("https://hestia-3.local:8443") is False

    def test_remote_ip(self):
        assert _is_localhost("https://192.168.1.100:8443") is False

    def test_no_port(self):
        assert _is_localhost("https://localhost") is True

    def test_http_scheme(self):
        assert _is_localhost("http://localhost:8443") is True


# --- ensure_server_running tests ---


@pytest.fixture
def console():
    return Console(quiet=True)


class TestEnsureServerRunning:
    def test_server_already_running(self, console):
        """If ping succeeds, no start attempt should be made."""
        with patch("hestia_cli.bootstrap._ping_server", new_callable=AsyncMock, return_value=True):
            result = asyncio.run(
                ensure_server_running("https://localhost:8443", False, console)
            )
        assert result is True

    def test_server_remote_not_running(self, console):
        """Remote server not running — should return False, no start attempt."""
        with patch("hestia_cli.bootstrap._ping_server", new_callable=AsyncMock, return_value=False):
            result = asyncio.run(
                ensure_server_running("https://hestia-3.local:8443", False, console)
            )
        assert result is False

    def test_auto_start_disabled(self, console):
        """Localhost not running + auto_start=False — should return False."""
        with patch("hestia_cli.bootstrap._ping_server", new_callable=AsyncMock, return_value=False):
            result = asyncio.run(
                ensure_server_running("https://localhost:8443", False, console, auto_start=False)
            )
        assert result is False

    def test_server_start_launchd(self, console):
        """Localhost not running — launchd start succeeds, then ping succeeds."""
        ping_results = [False, True]  # First call fails, second succeeds

        async def mock_ping(*args, **kwargs):
            return ping_results.pop(0) if ping_results else True

        with patch("hestia_cli.bootstrap._ping_server", side_effect=mock_ping), \
             patch("hestia_cli.bootstrap._start_server_launchd", return_value=True), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = asyncio.run(
                ensure_server_running("https://localhost:8443", False, console)
            )
        assert result is True

    def test_server_start_subprocess_fallback(self, console):
        """Localhost not running — launchd fails, subprocess succeeds."""
        ping_results = [False, True]

        async def mock_ping(*args, **kwargs):
            return ping_results.pop(0) if ping_results else True

        with patch("hestia_cli.bootstrap._ping_server", side_effect=mock_ping), \
             patch("hestia_cli.bootstrap._start_server_launchd", return_value=False), \
             patch("hestia_cli.bootstrap._start_server_subprocess", return_value=True), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = asyncio.run(
                ensure_server_running("https://localhost:8443", False, console)
            )
        assert result is True

    def test_server_start_timeout(self, console):
        """Server never becomes healthy — should return False after polling."""
        with patch("hestia_cli.bootstrap._ping_server", new_callable=AsyncMock, return_value=False), \
             patch("hestia_cli.bootstrap._start_server_launchd", return_value=True), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            result = asyncio.run(
                ensure_server_running("https://localhost:8443", False, console)
            )
        assert result is False


# --- ensure_authenticated tests ---


class TestEnsureAuthenticated:
    def test_already_authenticated(self, console):
        """If token exists, should return True immediately."""
        with patch("hestia_cli.bootstrap.get_stored_token", return_value="existing-jwt"):
            result = asyncio.run(
                ensure_authenticated("https://localhost:8443", False, console)
            )
        assert result is True

    def test_auto_register_localhost(self, console):
        """No token + localhost — should POST /v1/auth/register and store credentials."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"token": "new-jwt", "device_id": "device-abc123"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("hestia_cli.bootstrap.get_stored_token", return_value=None), \
             patch("hestia_cli.bootstrap.store_credentials") as mock_store, \
             patch("hestia_cli.bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                ensure_authenticated("https://localhost:8443", False, console)
            )

        assert result is True
        mock_store.assert_called_once_with("new-jwt", "device-abc123")

    def test_auto_register_remote_fails(self, console):
        """No token + remote — should return False without attempting register."""
        with patch("hestia_cli.bootstrap.get_stored_token", return_value=None):
            result = asyncio.run(
                ensure_authenticated("https://hestia-3.local:8443", False, console)
            )
        assert result is False

    def test_auto_register_403_invite_required(self, console):
        """POST returns 403 — should print diagnostic and return False."""
        mock_response = MagicMock()
        mock_response.status_code = 403

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("hestia_cli.bootstrap.get_stored_token", return_value=None), \
             patch("hestia_cli.bootstrap.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(
                ensure_authenticated("https://localhost:8443", False, console)
            )
        assert result is False


# --- ensure_models_available tests ---


class TestGetInstalledModels:
    def test_parses_ollama_list(self):
        """Parses model names from ollama list output."""
        mock_output = "NAME              ID           SIZE    MODIFIED\nqwen3.5:9b        abc123       6.0 GB  2 days ago\nqwen2.5:0.5b      def456       394 MB  3 days ago\n"
        mock_result = MagicMock(returncode=0, stdout=mock_output)
        with patch("hestia_cli.bootstrap.subprocess.run", return_value=mock_result):
            models = _get_installed_models()
        assert "qwen3.5:9b" in models
        assert "qwen2.5:0.5b" in models

    def test_ollama_not_found(self):
        """Returns empty set if ollama binary not found."""
        with patch("hestia_cli.bootstrap.subprocess.run", side_effect=FileNotFoundError):
            models = _get_installed_models()
        assert models == set()


class TestEnsureModelsAvailable:
    def test_all_models_present(self, console):
        """All models installed — returns True, no pulls."""
        with patch("hestia_cli.bootstrap.subprocess.run") as mock_run, \
             patch("hestia_cli.bootstrap._get_required_models", return_value=["qwen3.5:9b"]), \
             patch("hestia_cli.bootstrap._get_installed_models", return_value={"qwen3.5:9b"}):
            result = asyncio.run(ensure_models_available(console))
        assert result is True

    def test_missing_model_pulled(self, console):
        """Missing model triggers ollama pull."""
        pull_result = MagicMock(returncode=0)
        with patch("hestia_cli.bootstrap.subprocess.run", return_value=pull_result), \
             patch("hestia_cli.bootstrap._get_required_models", return_value=["qwen3.5:9b"]), \
             patch("hestia_cli.bootstrap._get_installed_models", return_value=set()):
            result = asyncio.run(ensure_models_available(console))
        assert result is True

    def test_ollama_not_installed(self, console):
        """Returns False if ollama binary not found."""
        with patch("hestia_cli.bootstrap.subprocess.run", side_effect=FileNotFoundError):
            result = asyncio.run(ensure_models_available(console))
        assert result is False

    def test_pull_failure(self, console):
        """Returns False if pull fails."""
        version_result = MagicMock(returncode=0)
        pull_result = MagicMock(returncode=1, stderr="connection error")

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return version_result  # ollama --version
            return pull_result  # ollama pull

        with patch("hestia_cli.bootstrap.subprocess.run", side_effect=side_effect), \
             patch("hestia_cli.bootstrap._get_required_models", return_value=["qwen3.5:9b"]), \
             patch("hestia_cli.bootstrap._get_installed_models", return_value=set()):
            result = asyncio.run(ensure_models_available(console))
        assert result is False
