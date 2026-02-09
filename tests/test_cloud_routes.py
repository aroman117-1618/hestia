"""
Tests for Hestia cloud LLM API routes.

WS1: Cloud LLM Support — Session 3
Tests all 7 cloud endpoints and state propagation to inference router.
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.cloud.models import (
    CloudProvider,
    CloudProviderState,
    ProviderConfig,
)
from hestia.cloud.database import CloudDatabase
from hestia.cloud.manager import CloudManager
from hestia.api.routes.cloud import (
    _config_to_response,
    _compute_effective_cloud_state,
    _sync_router_state,
)
from hestia.api.schemas import (
    CloudProviderEnum,
    CloudProviderStateEnum,
)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test databases."""
    return tmp_path


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> CloudDatabase:
    """Provide a connected test database."""
    db = CloudDatabase(db_path=temp_dir / "test_cloud_routes.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(temp_dir: Path) -> CloudManager:
    """Provide a CloudManager with test database."""
    db = CloudDatabase(db_path=temp_dir / "test_cloud_routes.db")
    await db.connect()
    mgr = CloudManager(database=db)
    await mgr.initialize()
    yield mgr
    await mgr.close()


def _make_provider_config(
    provider: CloudProvider = CloudProvider.ANTHROPIC,
    state: CloudProviderState = CloudProviderState.ENABLED_SMART,
    model_id: str = "claude-sonnet-4-20250514",
) -> ProviderConfig:
    """Create a test ProviderConfig."""
    return ProviderConfig(
        id="prov-test123456",
        provider=provider,
        state=state,
        credential_key=f"cloud_api_key_{provider.value}",
        active_model_id=model_id,
        available_models=[model_id],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        health_status="unknown",
    )


# ── Test: Config to Response Conversion ───────────────────────────────


class TestConfigToResponse:
    """Tests for ProviderConfig → API response conversion."""

    def test_basic_conversion(self) -> None:
        """Config converts to response with correct fields."""
        config = _make_provider_config()
        response = _config_to_response(config)

        assert response.id == "prov-test123456"
        assert response.provider == CloudProviderEnum.ANTHROPIC
        assert response.state == CloudProviderStateEnum.ENABLED_SMART
        assert response.active_model_id == "claude-sonnet-4-20250514"
        assert response.available_models == ["claude-sonnet-4-20250514"]
        assert response.has_api_key is True
        assert response.health_status == "unknown"

    def test_no_credential_key(self) -> None:
        """Config with empty credential_key shows has_api_key=False."""
        config = _make_provider_config()
        config.credential_key = ""
        response = _config_to_response(config)
        assert response.has_api_key is False

    def test_all_providers(self) -> None:
        """All provider types convert correctly."""
        for cloud_provider in CloudProvider:
            config = _make_provider_config(provider=cloud_provider)
            response = _config_to_response(config)
            assert response.provider.value == cloud_provider.value

    def test_all_states(self) -> None:
        """All state types convert correctly."""
        for cloud_state in CloudProviderState:
            config = _make_provider_config(state=cloud_state)
            response = _config_to_response(config)
            assert response.state.value == cloud_state.value


# ── Test: Effective Cloud State Computation ───────────────────────────


class TestEffectiveCloudState:
    """Tests for _compute_effective_cloud_state."""

    def test_no_providers_returns_disabled(self) -> None:
        """No providers → disabled."""
        assert _compute_effective_cloud_state([]) == "disabled"

    def test_all_disabled_returns_disabled(self) -> None:
        """All disabled providers → disabled."""
        providers = [
            _make_provider_config(state=CloudProviderState.DISABLED),
            _make_provider_config(
                provider=CloudProvider.OPENAI,
                state=CloudProviderState.DISABLED,
            ),
        ]
        assert _compute_effective_cloud_state(providers) == "disabled"

    def test_smart_provider_returns_smart(self) -> None:
        """One smart provider → enabled_smart."""
        providers = [
            _make_provider_config(state=CloudProviderState.ENABLED_SMART),
        ]
        assert _compute_effective_cloud_state(providers) == "enabled_smart"

    def test_full_provider_returns_full(self) -> None:
        """One full provider → enabled_full."""
        providers = [
            _make_provider_config(state=CloudProviderState.ENABLED_FULL),
        ]
        assert _compute_effective_cloud_state(providers) == "enabled_full"

    def test_full_takes_priority_over_smart(self) -> None:
        """Full takes priority: one full + one smart → enabled_full."""
        providers = [
            _make_provider_config(state=CloudProviderState.ENABLED_SMART),
            _make_provider_config(
                provider=CloudProvider.OPENAI,
                state=CloudProviderState.ENABLED_FULL,
            ),
        ]
        assert _compute_effective_cloud_state(providers) == "enabled_full"

    def test_smart_with_disabled_returns_smart(self) -> None:
        """Smart + disabled → enabled_smart."""
        providers = [
            _make_provider_config(state=CloudProviderState.DISABLED),
            _make_provider_config(
                provider=CloudProvider.OPENAI,
                state=CloudProviderState.ENABLED_SMART,
            ),
        ]
        assert _compute_effective_cloud_state(providers) == "enabled_smart"


# ── Test: Router State Sync ───────────────────────────────────────────


class TestRouterStateSync:
    """Tests for _sync_router_state propagation to inference router."""

    @patch("hestia.api.routes.cloud.get_router")
    def test_sync_calls_set_cloud_state(self, mock_get_router: MagicMock) -> None:
        """Syncing pushes state to inference router."""
        mock_router = MagicMock()
        mock_get_router.return_value = mock_router

        providers = [
            _make_provider_config(state=CloudProviderState.ENABLED_SMART),
        ]
        result = _sync_router_state(providers)

        assert result == "enabled_smart"
        mock_router.set_cloud_state.assert_called_once_with("enabled_smart")

    @patch("hestia.api.routes.cloud.get_router")
    def test_sync_disabled_when_no_providers(self, mock_get_router: MagicMock) -> None:
        """Empty providers → router set to disabled."""
        mock_router = MagicMock()
        mock_get_router.return_value = mock_router

        result = _sync_router_state([])
        assert result == "disabled"
        mock_router.set_cloud_state.assert_called_once_with("disabled")

    @patch("hestia.api.routes.cloud.get_router")
    def test_sync_survives_router_error(self, mock_get_router: MagicMock) -> None:
        """Router errors don't crash the sync."""
        mock_get_router.side_effect = RuntimeError("Router not initialized")
        result = _sync_router_state([
            _make_provider_config(state=CloudProviderState.ENABLED_FULL),
        ])
        assert result == "enabled_full"


# ── Test: List Providers Endpoint ─────────────────────────────────────


class TestListProvidersEndpoint:
    """Tests for GET /v1/cloud/providers."""

    @pytest.mark.asyncio
    async def test_list_empty(self, manager: CloudManager) -> None:
        """Empty provider list returns correctly."""
        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            from hestia.api.routes.cloud import list_providers
            response = await list_providers(device_id="test-device")

        assert response.count == 0
        assert response.providers == []
        assert response.cloud_state == "disabled"

    @pytest.mark.asyncio
    async def test_list_with_provider(self, manager: CloudManager) -> None:
        """List returns configured providers."""
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-test-key-12345",
            state=CloudProviderState.ENABLED_SMART,
        )

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            from hestia.api.routes.cloud import list_providers
            response = await list_providers(device_id="test-device")

        assert response.count == 1
        assert response.providers[0].provider == CloudProviderEnum.ANTHROPIC
        assert response.providers[0].state == CloudProviderStateEnum.ENABLED_SMART
        assert response.providers[0].has_api_key is True
        assert response.cloud_state == "enabled_smart"

    @pytest.mark.asyncio
    async def test_list_multiple_providers(self, manager: CloudManager) -> None:
        """List with multiple providers returns all."""
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-12345",
            state=CloudProviderState.ENABLED_SMART,
        )
        await manager.add_provider(
            provider=CloudProvider.OPENAI,
            api_key="sk-oai-12345",
            state=CloudProviderState.DISABLED,
        )

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            from hestia.api.routes.cloud import list_providers
            response = await list_providers(device_id="test-device")

        assert response.count == 2
        assert response.cloud_state == "enabled_smart"


# ── Test: Add Provider Endpoint ───────────────────────────────────────


class TestAddProviderEndpoint:
    """Tests for POST /v1/cloud/providers."""

    @pytest.mark.asyncio
    async def test_add_provider_success(self, manager: CloudManager) -> None:
        """Successfully add a new provider."""
        from hestia.api.routes.cloud import add_provider
        from hestia.api.schemas import CloudProviderAddRequest

        request = CloudProviderAddRequest(
            provider=CloudProviderEnum.ANTHROPIC,
            api_key="sk-test-key-12345",
            state=CloudProviderStateEnum.ENABLED_SMART,
        )

        with (
            patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager),
            patch("hestia.api.routes.cloud.get_router") as mock_router,
        ):
            mock_router.return_value = MagicMock()
            response = await add_provider(
                request=request,
                device_id="test-device",
            )

        assert response.provider == CloudProviderEnum.ANTHROPIC
        assert response.state == CloudProviderStateEnum.ENABLED_SMART
        assert response.has_api_key is True

    @pytest.mark.asyncio
    async def test_add_duplicate_provider_409(self, manager: CloudManager) -> None:
        """Adding an already-configured provider returns 409."""
        from hestia.api.routes.cloud import add_provider
        from hestia.api.schemas import CloudProviderAddRequest
        from fastapi import HTTPException

        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-existing-key",
        )

        request = CloudProviderAddRequest(
            provider=CloudProviderEnum.ANTHROPIC,
            api_key="sk-new-key",
        )

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            with pytest.raises(HTTPException) as exc_info:
                await add_provider(
                    request=request,
                    device_id="test-device",
                )
            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_add_provider_with_model(self, manager: CloudManager) -> None:
        """Adding a provider with explicit model_id sets it."""
        from hestia.api.routes.cloud import add_provider
        from hestia.api.schemas import CloudProviderAddRequest

        request = CloudProviderAddRequest(
            provider=CloudProviderEnum.ANTHROPIC,
            api_key="sk-test-key",
            model_id="claude-haiku-3-5-20241022",
        )

        with (
            patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager),
            patch("hestia.api.routes.cloud.get_router") as mock_router,
        ):
            mock_router.return_value = MagicMock()
            response = await add_provider(
                request=request,
                device_id="test-device",
            )

        assert response.active_model_id == "claude-haiku-3-5-20241022"


# ── Test: Remove Provider Endpoint ────────────────────────────────────


class TestRemoveProviderEndpoint:
    """Tests for DELETE /v1/cloud/providers/{provider}."""

    @pytest.mark.asyncio
    async def test_remove_existing(self, manager: CloudManager) -> None:
        """Remove an existing provider succeeds."""
        from hestia.api.routes.cloud import remove_provider

        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-test",
        )

        with (
            patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager),
            patch("hestia.api.routes.cloud.get_router") as mock_router,
        ):
            mock_router.return_value = MagicMock()
            response = await remove_provider(
                provider=CloudProviderEnum.ANTHROPIC,
                device_id="test-device",
            )

        assert response.deleted is True
        assert response.provider == CloudProviderEnum.ANTHROPIC

    @pytest.mark.asyncio
    async def test_remove_nonexistent_404(self, manager: CloudManager) -> None:
        """Removing a non-configured provider returns 404."""
        from hestia.api.routes.cloud import remove_provider
        from fastapi import HTTPException

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            with pytest.raises(HTTPException) as exc_info:
                await remove_provider(
                    provider=CloudProviderEnum.GOOGLE,
                    device_id="test-device",
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_remove_syncs_router(self, manager: CloudManager) -> None:
        """Removing a provider syncs the router to disabled."""
        from hestia.api.routes.cloud import remove_provider

        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-test",
            state=CloudProviderState.ENABLED_SMART,
        )

        with (
            patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager),
            patch("hestia.api.routes.cloud.get_router") as mock_get_router,
        ):
            mock_router = MagicMock()
            mock_get_router.return_value = mock_router
            await remove_provider(
                provider=CloudProviderEnum.ANTHROPIC,
                device_id="test-device",
            )

        mock_router.set_cloud_state.assert_called_once_with("disabled")


# ── Test: Update Provider State Endpoint ──────────────────────────────


class TestUpdateStateEndpoint:
    """Tests for PATCH /v1/cloud/providers/{provider}/state."""

    @pytest.mark.asyncio
    async def test_update_state_success(self, manager: CloudManager) -> None:
        """Successfully update a provider's state."""
        from hestia.api.routes.cloud import update_provider_state
        from hestia.api.schemas import CloudProviderStateUpdateRequest

        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-test",
            state=CloudProviderState.ENABLED_SMART,
        )

        request = CloudProviderStateUpdateRequest(
            state=CloudProviderStateEnum.ENABLED_FULL,
        )

        with (
            patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager),
            patch("hestia.api.routes.cloud.get_router") as mock_get_router,
        ):
            mock_get_router.return_value = MagicMock()
            response = await update_provider_state(
                provider=CloudProviderEnum.ANTHROPIC,
                request=request,
                device_id="test-device",
            )

        assert response.state == CloudProviderStateEnum.ENABLED_FULL

    @pytest.mark.asyncio
    async def test_update_state_not_found(self, manager: CloudManager) -> None:
        """Updating state for non-configured provider returns 404."""
        from hestia.api.routes.cloud import update_provider_state
        from hestia.api.schemas import CloudProviderStateUpdateRequest
        from fastapi import HTTPException

        request = CloudProviderStateUpdateRequest(
            state=CloudProviderStateEnum.DISABLED,
        )

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            with pytest.raises(HTTPException) as exc_info:
                await update_provider_state(
                    provider=CloudProviderEnum.OPENAI,
                    request=request,
                    device_id="test-device",
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_to_disabled_syncs_router(self, manager: CloudManager) -> None:
        """Disabling the only provider syncs router to disabled."""
        from hestia.api.routes.cloud import update_provider_state
        from hestia.api.schemas import CloudProviderStateUpdateRequest

        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-test",
            state=CloudProviderState.ENABLED_SMART,
        )

        request = CloudProviderStateUpdateRequest(
            state=CloudProviderStateEnum.DISABLED,
        )

        with (
            patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager),
            patch("hestia.api.routes.cloud.get_router") as mock_get_router,
        ):
            mock_router = MagicMock()
            mock_get_router.return_value = mock_router
            await update_provider_state(
                provider=CloudProviderEnum.ANTHROPIC,
                request=request,
                device_id="test-device",
            )

        mock_router.set_cloud_state.assert_called_once_with("disabled")


# ── Test: Update Provider Model Endpoint ──────────────────────────────


class TestUpdateModelEndpoint:
    """Tests for PATCH /v1/cloud/providers/{provider}/model."""

    @pytest.mark.asyncio
    async def test_update_model_success(self, manager: CloudManager) -> None:
        """Successfully update a provider's active model."""
        from hestia.api.routes.cloud import update_provider_model
        from hestia.api.schemas import CloudProviderModelUpdateRequest

        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-test",
        )

        request = CloudProviderModelUpdateRequest(
            model_id="claude-haiku-3-5-20241022",
        )

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            response = await update_provider_model(
                provider=CloudProviderEnum.ANTHROPIC,
                request=request,
                device_id="test-device",
            )

        assert response.active_model_id == "claude-haiku-3-5-20241022"

    @pytest.mark.asyncio
    async def test_update_model_not_found(self, manager: CloudManager) -> None:
        """Updating model for non-configured provider returns 404."""
        from hestia.api.routes.cloud import update_provider_model
        from hestia.api.schemas import CloudProviderModelUpdateRequest
        from fastapi import HTTPException

        request = CloudProviderModelUpdateRequest(model_id="gpt-4o")

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            with pytest.raises(HTTPException) as exc_info:
                await update_provider_model(
                    provider=CloudProviderEnum.OPENAI,
                    request=request,
                    device_id="test-device",
                )
            assert exc_info.value.status_code == 404


# ── Test: Usage Summary Endpoint ──────────────────────────────────────


class TestUsageSummaryEndpoint:
    """Tests for GET /v1/cloud/usage."""

    @pytest.mark.asyncio
    async def test_usage_empty(self, manager: CloudManager) -> None:
        """Usage summary with no records returns zeros."""
        from hestia.api.routes.cloud import get_usage_summary

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            response = await get_usage_summary(
                days=30,
                device_id="test-device",
            )

        assert response.period_days == 30
        assert response.total_requests == 0
        assert response.total_cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_usage_custom_period(self, manager: CloudManager) -> None:
        """Usage summary respects the days parameter."""
        from hestia.api.routes.cloud import get_usage_summary

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            response = await get_usage_summary(
                days=7,
                device_id="test-device",
            )

        assert response.period_days == 7


# ── Test: Health Check Endpoint ───────────────────────────────────────


class TestHealthCheckEndpoint:
    """Tests for POST /v1/cloud/providers/{provider}/health."""

    @pytest.mark.asyncio
    async def test_health_check_not_found(self, manager: CloudManager) -> None:
        """Health check for non-configured provider returns 404."""
        from hestia.api.routes.cloud import check_provider_health
        from fastapi import HTTPException

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            with pytest.raises(HTTPException) as exc_info:
                await check_provider_health(
                    provider=CloudProviderEnum.GOOGLE,
                    device_id="test-device",
                )
            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, manager: CloudManager) -> None:
        """Health check for provider with bad key returns unhealthy."""
        from hestia.api.routes.cloud import check_provider_health

        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-invalid-key",
        )

        with patch("hestia.api.routes.cloud.get_cloud_manager", return_value=manager):
            response = await check_provider_health(
                provider=CloudProviderEnum.ANTHROPIC,
                device_id="test-device",
            )

        # Unhealthy because the key is fake and no API is reachable in tests
        assert response.provider == CloudProviderEnum.ANTHROPIC
        assert response.healthy is False
        assert response.health_status == "unhealthy"


# ── Test: Pydantic Schema Validation ──────────────────────────────────


class TestSchemaValidation:
    """Tests for Pydantic schema constraints."""

    def test_add_request_requires_api_key(self) -> None:
        """CloudProviderAddRequest requires non-empty api_key."""
        from hestia.api.schemas import CloudProviderAddRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CloudProviderAddRequest(api_key="")

    def test_add_request_default_state(self) -> None:
        """CloudProviderAddRequest defaults to enabled_smart."""
        from hestia.api.schemas import CloudProviderAddRequest

        req = CloudProviderAddRequest(provider=CloudProviderEnum.ANTHROPIC, api_key="sk-test")
        assert req.state == CloudProviderStateEnum.ENABLED_SMART

    def test_model_update_requires_model_id(self) -> None:
        """CloudProviderModelUpdateRequest requires non-empty model_id."""
        from hestia.api.schemas import CloudProviderModelUpdateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CloudProviderModelUpdateRequest(model_id="")

    def test_state_update_validates_enum(self) -> None:
        """CloudProviderStateUpdateRequest validates state enum."""
        from hestia.api.schemas import CloudProviderStateUpdateRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CloudProviderStateUpdateRequest(state="invalid_state")

    def test_provider_response_never_has_raw_key(self) -> None:
        """CloudProviderResponse has has_api_key but no raw key field."""
        from hestia.api.schemas import CloudProviderResponse

        fields = CloudProviderResponse.model_fields
        assert "api_key" not in fields
        assert "credential_key" not in fields
        assert "has_api_key" in fields

    def test_usage_summary_defaults(self) -> None:
        """CloudUsageSummaryResponse has sensible defaults."""
        from hestia.api.schemas import CloudUsageSummaryResponse

        summary = CloudUsageSummaryResponse(period_days=30)
        assert summary.total_requests == 0
        assert summary.total_cost_usd == 0.0
        assert summary.total_tokens_in == 0
        assert summary.total_tokens_out == 0

    def test_cloud_provider_enum_values(self) -> None:
        """CloudProviderEnum has correct values."""
        assert CloudProviderEnum.ANTHROPIC.value == "anthropic"
        assert CloudProviderEnum.OPENAI.value == "openai"
        assert CloudProviderEnum.GOOGLE.value == "google"

    def test_cloud_state_enum_values(self) -> None:
        """CloudProviderStateEnum has correct values."""
        assert CloudProviderStateEnum.DISABLED.value == "disabled"
        assert CloudProviderStateEnum.ENABLED_FULL.value == "enabled_full"
        assert CloudProviderStateEnum.ENABLED_SMART.value == "enabled_smart"
