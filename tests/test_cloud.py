"""
Tests for Hestia cloud LLM provider support.

Session 1: Cloud module foundation (models, database, manager).
"""

import json
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.cloud.models import (
    CloudProvider,
    CloudProviderState,
    CloudModel,
    ProviderConfig,
    CloudUsageRecord,
    PROVIDER_DEFAULTS,
    calculate_cost,
)
from hestia.cloud.database import CloudDatabase
from hestia.cloud.manager import CloudManager


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test databases."""
    return tmp_path


@pytest_asyncio.fixture
async def database(temp_dir: Path) -> CloudDatabase:
    """Provide a connected test database."""
    db = CloudDatabase(db_path=temp_dir / "test_cloud.db")
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def manager(temp_dir: Path) -> CloudManager:
    """Provide a CloudManager with test database."""
    db = CloudDatabase(db_path=temp_dir / "test_cloud.db")
    await db.connect()
    mgr = CloudManager(database=db)
    await mgr.initialize()
    yield mgr
    await mgr.close()


# ── Test: Cloud Models ─────────────────────────────────────────────────


class TestCloudModels:
    """Tests for cloud model data structures."""

    def test_cloud_provider_enum_values(self) -> None:
        assert CloudProvider.ANTHROPIC.value == "anthropic"
        assert CloudProvider.OPENAI.value == "openai"
        assert CloudProvider.GOOGLE.value == "google"

    def test_cloud_provider_state_enum_values(self) -> None:
        assert CloudProviderState.DISABLED.value == "disabled"
        assert CloudProviderState.ENABLED_FULL.value == "enabled_full"
        assert CloudProviderState.ENABLED_SMART.value == "enabled_smart"

    def test_cloud_model_to_dict(self) -> None:
        model = CloudModel(
            model_id="claude-sonnet-4-20250514",
            provider=CloudProvider.ANTHROPIC,
            display_name="Claude Sonnet 4",
            context_window=200000,
            max_output_tokens=8192,
            cost_per_1k_input=0.003,
            cost_per_1k_output=0.015,
        )
        d = model.to_dict()
        assert d["model_id"] == "claude-sonnet-4-20250514"
        assert d["provider"] == "anthropic"
        assert d["context_window"] == 200000

    def test_cloud_model_from_dict(self) -> None:
        d = {
            "model_id": "gpt-4o",
            "provider": "openai",
            "display_name": "GPT-4o",
            "context_window": 128000,
            "max_output_tokens": 4096,
            "cost_per_1k_input": 0.005,
            "cost_per_1k_output": 0.015,
        }
        model = CloudModel.from_dict(d)
        assert model.provider == CloudProvider.OPENAI
        assert model.cost_per_1k_input == 0.005

    def test_provider_config_create(self) -> None:
        config = ProviderConfig.create(
            provider=CloudProvider.ANTHROPIC,
            credential_key="cloud_api_key_anthropic",
        )
        assert config.id.startswith("prov-")
        assert config.provider == CloudProvider.ANTHROPIC
        assert config.state == CloudProviderState.ENABLED_SMART
        assert config.active_model_id == "claude-sonnet-4-20250514"
        assert config.base_url == "https://api.anthropic.com"

    def test_provider_config_create_with_model(self) -> None:
        config = ProviderConfig.create(
            provider=CloudProvider.OPENAI,
            credential_key="cloud_api_key_openai",
            active_model_id="gpt-4o-mini",
        )
        assert config.active_model_id == "gpt-4o-mini"

    def test_provider_config_to_dict_hides_key(self) -> None:
        config = ProviderConfig.create(
            provider=CloudProvider.ANTHROPIC,
            credential_key="cloud_api_key_anthropic",
        )
        d = config.to_dict()
        assert "credential_key" not in d
        assert d["has_api_key"] is True

    def test_provider_config_sqlite_roundtrip(self) -> None:
        config = ProviderConfig.create(
            provider=CloudProvider.GOOGLE,
            credential_key="cloud_api_key_google",
            state=CloudProviderState.ENABLED_FULL,
        )
        config.available_models = ["gemini-2.0-flash", "gemini-2.0-pro"]
        row = config.to_sqlite_row()
        restored = ProviderConfig.from_sqlite_row(row)
        assert restored.provider == CloudProvider.GOOGLE
        assert restored.state == CloudProviderState.ENABLED_FULL
        assert restored.available_models == ["gemini-2.0-flash", "gemini-2.0-pro"]

    def test_usage_record_create(self) -> None:
        record = CloudUsageRecord.create(
            provider=CloudProvider.ANTHROPIC,
            model_id="claude-sonnet-4-20250514",
            tokens_in=1000,
            tokens_out=500,
            cost_usd=0.0105,
            duration_ms=1500.0,
            request_id="req-abc123",
        )
        assert record.id.startswith("usage-")
        assert record.cost_usd == 0.0105

    def test_usage_record_sqlite_roundtrip(self) -> None:
        record = CloudUsageRecord.create(
            provider=CloudProvider.OPENAI,
            model_id="gpt-4o",
            tokens_in=2000,
            tokens_out=800,
            cost_usd=0.022,
            duration_ms=2300.0,
            request_id="req-def456",
            mode="mira",
        )
        row = record.to_sqlite_row()
        restored = CloudUsageRecord.from_sqlite_row(row)
        assert restored.provider == CloudProvider.OPENAI
        assert restored.mode == "mira"
        assert restored.tokens_in == 2000

    def test_provider_defaults_exist_for_all_providers(self) -> None:
        for provider in CloudProvider:
            assert provider in PROVIDER_DEFAULTS
            defaults = PROVIDER_DEFAULTS[provider]
            assert "base_url" in defaults
            assert "default_model" in defaults
            assert "models" in defaults
            assert len(defaults["models"]) >= 2

    def test_calculate_cost_known_model(self) -> None:
        cost = calculate_cost(
            CloudProvider.ANTHROPIC,
            "claude-sonnet-4-20250514",
            tokens_in=1000,
            tokens_out=500,
        )
        expected = (1000 / 1000) * 0.003 + (500 / 1000) * 0.015
        assert cost == round(expected, 6)

    def test_calculate_cost_unknown_model(self) -> None:
        cost = calculate_cost(
            CloudProvider.ANTHROPIC,
            "unknown-model",
            tokens_in=1000,
            tokens_out=500,
        )
        assert cost > 0


# ── Test: Cloud Database ───────────────────────────────────────────────


class TestCloudDatabase:
    """Tests for cloud database persistence."""

    @pytest.mark.asyncio
    async def test_store_and_get_provider(self, database: CloudDatabase) -> None:
        config = ProviderConfig.create(
            provider=CloudProvider.ANTHROPIC,
            credential_key="cloud_api_key_anthropic",
        )
        await database.store_provider(config)
        result = await database.get_provider(CloudProvider.ANTHROPIC)
        assert result is not None
        assert result.provider == CloudProvider.ANTHROPIC

    @pytest.mark.asyncio
    async def test_get_nonexistent_provider(self, database: CloudDatabase) -> None:
        result = await database.get_provider(CloudProvider.GOOGLE)
        assert result is None

    @pytest.mark.asyncio
    async def test_update_provider(self, database: CloudDatabase) -> None:
        config = ProviderConfig.create(
            provider=CloudProvider.OPENAI,
            credential_key="cloud_api_key_openai",
        )
        await database.store_provider(config)

        config.state = CloudProviderState.ENABLED_FULL
        config.active_model_id = "gpt-4o-mini"
        await database.update_provider(config)

        result = await database.get_provider(CloudProvider.OPENAI)
        assert result.state == CloudProviderState.ENABLED_FULL
        assert result.active_model_id == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_delete_provider(self, database: CloudDatabase) -> None:
        config = ProviderConfig.create(
            provider=CloudProvider.GOOGLE,
            credential_key="cloud_api_key_google",
        )
        await database.store_provider(config)
        deleted = await database.delete_provider(CloudProvider.GOOGLE)
        assert deleted is True

        result = await database.get_provider(CloudProvider.GOOGLE)
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_provider(self, database: CloudDatabase) -> None:
        deleted = await database.delete_provider(CloudProvider.GOOGLE)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_list_providers(self, database: CloudDatabase) -> None:
        for provider in [CloudProvider.ANTHROPIC, CloudProvider.OPENAI]:
            config = ProviderConfig.create(
                provider=provider,
                credential_key=f"cloud_api_key_{provider.value}",
            )
            await database.store_provider(config)

        providers = await database.list_providers()
        assert len(providers) == 2

    @pytest.mark.asyncio
    async def test_store_usage(self, database: CloudDatabase) -> None:
        record = CloudUsageRecord.create(
            provider=CloudProvider.ANTHROPIC,
            model_id="claude-sonnet-4-20250514",
            tokens_in=1000,
            tokens_out=500,
            cost_usd=0.0105,
            duration_ms=1500.0,
            request_id="req-test1",
        )
        await database.store_usage(record)

        records = await database.get_usage_records(limit=10)
        assert len(records) == 1
        assert records[0].request_id == "req-test1"

    @pytest.mark.asyncio
    async def test_usage_summary(self, database: CloudDatabase) -> None:
        for i in range(5):
            record = CloudUsageRecord.create(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                tokens_in=1000,
                tokens_out=500,
                cost_usd=0.01,
                duration_ms=1000.0,
                request_id=f"req-{i}",
            )
            await database.store_usage(record)

        summary = await database.get_usage_summary(days=30)
        assert summary["total_requests"] == 5
        assert summary["total_cost_usd"] == pytest.approx(0.05, abs=0.001)
        assert len(summary["by_provider"]) == 1

    @pytest.mark.asyncio
    async def test_usage_summary_by_provider(self, database: CloudDatabase) -> None:
        for provider in [CloudProvider.ANTHROPIC, CloudProvider.OPENAI]:
            record = CloudUsageRecord.create(
                provider=provider,
                model_id="model",
                tokens_in=100,
                tokens_out=50,
                cost_usd=0.005,
                duration_ms=500.0,
                request_id=f"req-{provider.value}",
            )
            await database.store_usage(record)

        summary = await database.get_usage_summary(
            days=30, provider=CloudProvider.ANTHROPIC
        )
        assert summary["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_usage_summary_empty(self, database: CloudDatabase) -> None:
        summary = await database.get_usage_summary(days=30)
        assert summary["total_requests"] == 0
        assert summary["total_cost_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_provider_unique_constraint(self, database: CloudDatabase) -> None:
        """Storing same provider twice should replace (INSERT OR REPLACE)."""
        config1 = ProviderConfig.create(
            provider=CloudProvider.ANTHROPIC,
            credential_key="key1",
        )
        config1.active_model_id = "model-v1"
        await database.store_provider(config1)

        config2 = ProviderConfig.create(
            provider=CloudProvider.ANTHROPIC,
            credential_key="key2",
        )
        config2.active_model_id = "model-v2"
        await database.store_provider(config2)

        providers = await database.list_providers()
        assert len(providers) == 1
        assert providers[0].active_model_id == "model-v2"


# ── Test: Cloud Manager ────────────────────────────────────────────────


class TestCloudManager:
    """Tests for the CloudManager."""

    @pytest.mark.asyncio
    async def test_add_provider(self, manager: CloudManager) -> None:
        config = await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-test-key-123",
        )
        assert config.provider == CloudProvider.ANTHROPIC
        assert config.state == CloudProviderState.ENABLED_SMART
        assert config.active_model_id == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_add_provider_with_state(self, manager: CloudManager) -> None:
        config = await manager.add_provider(
            provider=CloudProvider.OPENAI,
            api_key="sk-openai-test-key",
            state=CloudProviderState.ENABLED_FULL,
        )
        assert config.state == CloudProviderState.ENABLED_FULL

    @pytest.mark.asyncio
    async def test_add_provider_with_model(self, manager: CloudManager) -> None:
        config = await manager.add_provider(
            provider=CloudProvider.OPENAI,
            api_key="sk-openai-test-key",
            model_id="gpt-4o-mini",
        )
        assert config.active_model_id == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_remove_provider(self, manager: CloudManager) -> None:
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-test-key",
        )
        removed = await manager.remove_provider(CloudProvider.ANTHROPIC)
        assert removed is True

        config = await manager.get_provider(CloudProvider.ANTHROPIC)
        assert config is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent_provider(self, manager: CloudManager) -> None:
        removed = await manager.remove_provider(CloudProvider.GOOGLE)
        assert removed is False

    @pytest.mark.asyncio
    async def test_update_provider_state(self, manager: CloudManager) -> None:
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-test-key",
        )
        config = await manager.update_provider_state(
            CloudProvider.ANTHROPIC,
            CloudProviderState.ENABLED_FULL,
        )
        assert config.state == CloudProviderState.ENABLED_FULL

    @pytest.mark.asyncio
    async def test_update_nonexistent_provider_state(self, manager: CloudManager) -> None:
        result = await manager.update_provider_state(
            CloudProvider.GOOGLE,
            CloudProviderState.DISABLED,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_select_model(self, manager: CloudManager) -> None:
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-test-key",
        )
        config = await manager.select_model(
            CloudProvider.ANTHROPIC,
            "claude-haiku-3-5-20241022",
        )
        assert config.active_model_id == "claude-haiku-3-5-20241022"

    @pytest.mark.asyncio
    async def test_list_providers(self, manager: CloudManager) -> None:
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-key",
        )
        await manager.add_provider(
            provider=CloudProvider.OPENAI,
            api_key="sk-oai-key",
        )
        providers = await manager.list_providers()
        assert len(providers) == 2

    @pytest.mark.asyncio
    async def test_get_active_provider(self, manager: CloudManager) -> None:
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-key",
            state=CloudProviderState.ENABLED_SMART,
        )
        active = await manager.get_active_provider()
        assert active is not None
        assert active.provider == CloudProvider.ANTHROPIC

    @pytest.mark.asyncio
    async def test_get_active_provider_skips_disabled(self, manager: CloudManager) -> None:
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-key",
            state=CloudProviderState.DISABLED,
        )
        await manager.add_provider(
            provider=CloudProvider.OPENAI,
            api_key="sk-oai-key",
            state=CloudProviderState.ENABLED_SMART,
        )
        active = await manager.get_active_provider()
        assert active is not None
        assert active.provider == CloudProvider.OPENAI

    @pytest.mark.asyncio
    async def test_get_active_provider_none_when_all_disabled(self, manager: CloudManager) -> None:
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-key",
            state=CloudProviderState.DISABLED,
        )
        active = await manager.get_active_provider()
        assert active is None

    @pytest.mark.asyncio
    async def test_get_active_provider_empty(self, manager: CloudManager) -> None:
        active = await manager.get_active_provider()
        assert active is None

    @pytest.mark.asyncio
    async def test_record_usage(self, manager: CloudManager) -> None:
        record = CloudUsageRecord.create(
            provider=CloudProvider.ANTHROPIC,
            model_id="claude-sonnet-4-20250514",
            tokens_in=1000,
            tokens_out=500,
            cost_usd=0.0105,
            duration_ms=1500.0,
            request_id="req-test",
        )
        await manager.record_usage(record)

        summary = await manager.get_usage_summary(days=30)
        assert summary["total_requests"] == 1

    @pytest.mark.asyncio
    async def test_get_monthly_cost(self, manager: CloudManager) -> None:
        for i in range(3):
            record = CloudUsageRecord.create(
                provider=CloudProvider.ANTHROPIC,
                model_id="claude-sonnet-4-20250514",
                tokens_in=1000,
                tokens_out=500,
                cost_usd=0.01,
                duration_ms=1000.0,
                request_id=f"req-{i}",
            )
            await manager.record_usage(record)

        cost = await manager.get_monthly_cost()
        assert cost == pytest.approx(0.03, abs=0.001)

    @pytest.mark.asyncio
    async def test_get_api_key_returns_none_no_provider(self, manager: CloudManager) -> None:
        key = await manager.get_api_key(CloudProvider.GOOGLE)
        assert key is None


# ── Test: Cloud Manager Edge Cases ─────────────────────────────────────


class TestCloudManagerEdgeCases:
    """Edge case tests for the CloudManager."""

    @pytest.mark.asyncio
    async def test_add_provider_fallback_models_on_detection_failure(
        self, manager: CloudManager
    ) -> None:
        """When model detection fails, curated defaults should be used."""
        config = await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-test-key",
        )
        # Should have curated defaults since detection was mocked/fails
        assert len(config.available_models) >= 2

    @pytest.mark.asyncio
    async def test_detect_models_no_provider(self, manager: CloudManager) -> None:
        """Detecting models for unconfigured provider should raise."""
        with pytest.raises(ValueError, match="not configured"):
            await manager.detect_models(CloudProvider.GOOGLE)

    @pytest.mark.asyncio
    async def test_provider_config_defaults_per_provider(self) -> None:
        """Each provider should have correct default URLs."""
        for provider in CloudProvider:
            config = ProviderConfig.create(
                provider=provider,
                credential_key=f"key_{provider.value}",
            )
            defaults = PROVIDER_DEFAULTS[provider]
            assert config.base_url == defaults["base_url"]
            assert config.active_model_id == defaults["default_model"]

    @pytest.mark.asyncio
    async def test_usage_cost_calculation_all_providers(self) -> None:
        """Cost calculation should work for all known models."""
        for provider, defaults in PROVIDER_DEFAULTS.items():
            for model in defaults["models"]:
                cost = calculate_cost(
                    provider=provider,
                    model_id=model.model_id,
                    tokens_in=1000,
                    tokens_out=500,
                )
                assert cost >= 0
                assert cost < 1.0  # Sanity check: 1.5K tokens shouldn't cost $1+

    @pytest.mark.asyncio
    async def test_provider_config_empty_available_models(self) -> None:
        """ProviderConfig should handle empty models list."""
        config = ProviderConfig.create(
            provider=CloudProvider.ANTHROPIC,
            credential_key="key",
        )
        config.available_models = []
        row = config.to_sqlite_row()
        restored = ProviderConfig.from_sqlite_row(row)
        assert restored.available_models == []

    @pytest.mark.asyncio
    async def test_manager_api_key_fallback(self, manager: CloudManager) -> None:
        """Manager should use in-memory fallback when Keychain unavailable."""
        # The test environment won't have Keychain, so fallback should work
        await manager.add_provider(
            provider=CloudProvider.ANTHROPIC,
            api_key="sk-ant-test-fallback",
        )
        # Key should be retrievable via fallback
        key = await manager.get_api_key(CloudProvider.ANTHROPIC)
        assert key == "sk-ant-test-fallback"


# ── Test: Database Context Manager ─────────────────────────────────────


class TestDatabaseContextManager:
    """Tests for database lifecycle management."""

    @pytest.mark.asyncio
    async def test_context_manager(self, temp_dir: Path) -> None:
        async with CloudDatabase(db_path=temp_dir / "ctx_test.db") as db:
            config = ProviderConfig.create(
                provider=CloudProvider.ANTHROPIC,
                credential_key="key",
            )
            await db.store_provider(config)
            result = await db.get_provider(CloudProvider.ANTHROPIC)
            assert result is not None

    @pytest.mark.asyncio
    async def test_connection_required(self, temp_dir: Path) -> None:
        db = CloudDatabase(db_path=temp_dir / "no_connect.db")
        with pytest.raises(RuntimeError, match="not connected"):
            _ = db.connection
