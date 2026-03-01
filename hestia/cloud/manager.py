"""
Cloud provider manager for Hestia.

Coordinates provider configuration, API key storage via Keychain,
model detection, and usage tracking.
"""

import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.cloud.database import CloudDatabase, get_cloud_database
from hestia.cloud.models import (
    CloudProvider,
    CloudProviderState,
    CloudModel,
    ProviderConfig,
    CloudUsageRecord,
    PROVIDER_DEFAULTS,
    calculate_cost,
)


class CloudManager:
    """
    Manages cloud LLM provider configuration and usage.

    Coordinates:
    - SQLite for provider configs and usage records
    - macOS Keychain (via CredentialManager) for API keys
    - HTTP calls for model detection and health checks
    """

    def __init__(
        self,
        database: Optional[CloudDatabase] = None,
    ) -> None:
        self._database = database
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the cloud manager."""
        if self._database is None:
            self._database = await get_cloud_database()

        providers = await self._database.list_providers()
        self.logger.info(
            "Cloud manager initialized",
            component=LogComponent.INFERENCE,
            data={"provider_count": len(providers)},
        )

    async def close(self) -> None:
        """Close the cloud manager."""
        if self._database:
            await self._database.close()

    @property
    def database(self) -> CloudDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("Cloud manager not initialized")
        return self._database

    # ── Provider CRUD ──────────────────────────────────────────────────

    async def add_provider(
        self,
        provider: CloudProvider,
        api_key: str,
        state: CloudProviderState = CloudProviderState.ENABLED_SMART,
        model_id: Optional[str] = None,
    ) -> ProviderConfig:
        """
        Add a cloud provider.

        Stores API key in Keychain via CredentialManager,
        creates provider config, and attempts model detection.

        Args:
            provider: The cloud provider type.
            api_key: The API key to store.
            state: Initial provider state.
            model_id: Preferred model (auto-selects default if None).

        Returns:
            The created ProviderConfig.
        """
        credential_key = f"cloud_api_key_{provider.value}"

        # Store API key in Keychain
        self._store_api_key(credential_key, api_key)

        # Create provider config
        config = ProviderConfig.create(
            provider=provider,
            credential_key=credential_key,
            state=state,
            active_model_id=model_id,
        )

        # Attempt model detection (non-blocking, use defaults on failure)
        try:
            detected = await self._detect_models_from_api(provider, api_key)
            if detected:
                config.available_models = [m.model_id for m in detected]
                config.health_status = "healthy"
                config.last_health_check = datetime.now(timezone.utc)
        except Exception as e:
            self.logger.warning(
                f"Model detection failed for {provider.value}: {type(e).__name__}",
                component=LogComponent.INFERENCE,
            )
            # Use curated defaults
            defaults = PROVIDER_DEFAULTS.get(provider, {})
            config.available_models = [
                m.model_id for m in defaults.get("models", [])
            ]

        await self.database.store_provider(config)

        self.logger.info(
            f"Added cloud provider: {provider.value}",
            component=LogComponent.INFERENCE,
            data={
                "state": state.value,
                "model": config.active_model_id,
                "models_count": len(config.available_models),
            },
        )

        return config

    async def remove_provider(self, provider: CloudProvider) -> bool:
        """
        Remove a cloud provider and delete its API key.

        Returns:
            True if the provider was found and removed.
        """
        config = await self.database.get_provider(provider)
        if config is None:
            return False

        # Delete API key from Keychain
        self._delete_api_key(config.credential_key)

        # Remove from database
        deleted = await self.database.delete_provider(provider)

        if deleted:
            self.logger.info(
                f"Removed cloud provider: {provider.value}",
                component=LogComponent.INFERENCE,
            )

        return deleted

    async def update_provider_state(
        self,
        provider: CloudProvider,
        state: CloudProviderState,
    ) -> Optional[ProviderConfig]:
        """Update a provider's operational state."""
        config = await self.database.get_provider(provider)
        if config is None:
            return None

        config.state = state
        await self.database.update_provider(config)

        self.logger.info(
            f"Updated provider state: {provider.value} → {state.value}",
            component=LogComponent.INFERENCE,
        )

        return config

    async def select_model(
        self,
        provider: CloudProvider,
        model_id: str,
    ) -> Optional[ProviderConfig]:
        """Select which model to use for a provider."""
        config = await self.database.get_provider(provider)
        if config is None:
            return None

        config.active_model_id = model_id
        await self.database.update_provider(config)

        self.logger.info(
            f"Selected model: {provider.value} → {model_id}",
            component=LogComponent.INFERENCE,
        )

        return config

    async def get_provider(self, provider: CloudProvider) -> Optional[ProviderConfig]:
        """Get a provider configuration."""
        return await self.database.get_provider(provider)

    async def list_providers(self) -> List[ProviderConfig]:
        """List all provider configurations."""
        return await self.database.list_providers()

    async def get_active_provider(self) -> Optional[ProviderConfig]:
        """
        Get the first enabled provider.

        Priority order: Anthropic > OpenAI > Google.
        """
        providers = await self.database.list_providers()
        for config in providers:
            if config.state != CloudProviderState.DISABLED:
                return config

        # Check priority order if no providers are ordered by creation
        for target in [CloudProvider.ANTHROPIC, CloudProvider.OPENAI, CloudProvider.GOOGLE]:
            for config in providers:
                if config.provider == target and config.state != CloudProviderState.DISABLED:
                    return config

        return None

    # ── Model Detection ────────────────────────────────────────────────

    async def detect_models(self, provider: CloudProvider) -> List[CloudModel]:
        """
        Detect available models from a provider's API.

        Falls back to curated defaults on failure.

        Returns:
            List of available CloudModel objects.
        """
        config = await self.database.get_provider(provider)
        if config is None:
            raise ValueError(f"Provider not configured: {provider.value}")

        api_key = self._get_api_key(config.credential_key)
        if not api_key:
            raise ValueError(f"No API key for {provider.value}")

        try:
            models = await self._detect_models_from_api(provider, api_key)
            if models:
                config.available_models = [m.model_id for m in models]
                config.health_status = "healthy"
                config.last_health_check = datetime.now(timezone.utc)
                await self.database.update_provider(config)

                self.logger.info(
                    f"Detected {len(models)} models for {provider.value}",
                    component=LogComponent.INFERENCE,
                )
                return models
        except Exception as e:
            self.logger.warning(
                f"Model detection failed for {provider.value}: {type(e).__name__}",
                component=LogComponent.INFERENCE,
            )

        # Fall back to curated defaults
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        return defaults.get("models", [])

    async def _detect_models_from_api(
        self,
        provider: CloudProvider,
        api_key: str,
    ) -> List[CloudModel]:
        """Call provider API to list available models."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            if provider == CloudProvider.ANTHROPIC:
                return await self._detect_anthropic_models(client, api_key)
            elif provider == CloudProvider.OPENAI:
                return await self._detect_openai_models(client, api_key)
            elif provider == CloudProvider.GOOGLE:
                return await self._detect_google_models(client, api_key)
        return []

    async def _detect_anthropic_models(
        self,
        client: httpx.AsyncClient,
        api_key: str,
    ) -> List[CloudModel]:
        """Detect models from Anthropic API."""
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        response = await client.get(
            "https://api.anthropic.com/v1/models",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        models = []
        for item in data.get("data", []):
            model_id = item.get("id", "")
            # Match against curated models for pricing
            curated = self._find_curated_model(CloudProvider.ANTHROPIC, model_id)
            if curated:
                models.append(curated)
            else:
                models.append(CloudModel(
                    model_id=model_id,
                    provider=CloudProvider.ANTHROPIC,
                    display_name=item.get("display_name", model_id),
                    context_window=200000,
                    max_output_tokens=8192,
                    cost_per_1k_input=0.003,
                    cost_per_1k_output=0.015,
                ))
        return models

    async def _detect_openai_models(
        self,
        client: httpx.AsyncClient,
        api_key: str,
    ) -> List[CloudModel]:
        """Detect models from OpenAI API."""
        headers = {"Authorization": f"Bearer {api_key}"}
        response = await client.get(
            "https://api.openai.com/v1/models",
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

        # Filter to chat models only
        chat_prefixes = ("gpt-4", "gpt-3.5", "o1", "o3")
        models = []
        for item in data.get("data", []):
            model_id = item.get("id", "")
            if any(model_id.startswith(p) for p in chat_prefixes):
                curated = self._find_curated_model(CloudProvider.OPENAI, model_id)
                if curated:
                    models.append(curated)
                else:
                    models.append(CloudModel(
                        model_id=model_id,
                        provider=CloudProvider.OPENAI,
                        display_name=model_id,
                        context_window=128000,
                        max_output_tokens=4096,
                        cost_per_1k_input=0.005,
                        cost_per_1k_output=0.015,
                    ))
        return models

    async def _detect_google_models(
        self,
        client: httpx.AsyncClient,
        api_key: str,
    ) -> List[CloudModel]:
        """Detect models from Google Gemini API."""
        response = await client.get(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
        )
        response.raise_for_status()
        data = response.json()

        models = []
        for item in data.get("models", []):
            model_id = item.get("name", "").replace("models/", "")
            if "gemini" in model_id:
                curated = self._find_curated_model(CloudProvider.GOOGLE, model_id)
                if curated:
                    models.append(curated)
                else:
                    models.append(CloudModel(
                        model_id=model_id,
                        provider=CloudProvider.GOOGLE,
                        display_name=item.get("displayName", model_id),
                        context_window=item.get("inputTokenLimit", 1048576),
                        max_output_tokens=item.get("outputTokenLimit", 8192),
                        cost_per_1k_input=0.00035,
                        cost_per_1k_output=0.0015,
                    ))
        return models

    def _find_curated_model(
        self,
        provider: CloudProvider,
        model_id: str,
    ) -> Optional[CloudModel]:
        """Find a model in the curated defaults list."""
        defaults = PROVIDER_DEFAULTS.get(provider, {})
        for model in defaults.get("models", []):
            if model.model_id == model_id:
                return model
        return None

    # ── Health Checks ──────────────────────────────────────────────────

    async def check_provider_health(self, provider: CloudProvider) -> bool:
        """
        Quick health check for a provider.

        Uses a lightweight API call to verify connectivity and key validity.
        """
        config = await self.database.get_provider(provider)
        if config is None:
            return False

        api_key = self._get_api_key(config.credential_key)
        if not api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if provider == CloudProvider.ANTHROPIC:
                    headers = {
                        "x-api-key": api_key,
                        "anthropic-version": "2023-06-01",
                    }
                    resp = await client.get(
                        "https://api.anthropic.com/v1/models",
                        headers=headers,
                    )
                elif provider == CloudProvider.OPENAI:
                    headers = {"Authorization": f"Bearer {api_key}"}
                    resp = await client.get(
                        "https://api.openai.com/v1/models",
                        headers=headers,
                    )
                elif provider == CloudProvider.GOOGLE:
                    resp = await client.get(
                        f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                    )
                else:
                    return False

                healthy = resp.status_code == 200

            config.health_status = "healthy" if healthy else "unhealthy"
            config.last_health_check = datetime.now(timezone.utc)
            await self.database.update_provider(config)

            return healthy
        except Exception as e:
            self.logger.warning(
                f"Health check failed for {provider.value}: {type(e).__name__}",
                component=LogComponent.INFERENCE,
            )
            config.health_status = "unhealthy"
            config.last_health_check = datetime.now(timezone.utc)
            await self.database.update_provider(config)
            return False

    # ── Usage Tracking ─────────────────────────────────────────────────

    async def record_usage(self, record: CloudUsageRecord) -> None:
        """Record a cloud API usage record."""
        await self.database.store_usage(record)

    async def get_usage_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get usage summary for cost tracking."""
        return await self.database.get_usage_summary(days=days)

    async def get_monthly_cost(self) -> float:
        """Get total cloud cost for the current month."""
        summary = await self.database.get_usage_summary(days=30)
        return summary.get("total_cost_usd", 0.0)

    # ── API Key Management ─────────────────────────────────────────────

    def _store_api_key(self, credential_key: str, api_key: str) -> None:
        """Store an API key in the Keychain via CredentialManager."""
        # Always keep in-memory fallback for environments without Keychain
        if not hasattr(self, "_key_fallback"):
            self._key_fallback: Dict[str, str] = {}
        self._key_fallback[credential_key] = api_key

        try:
            from hestia.security import get_credential_manager
            cm = get_credential_manager()
            cm.store_operational(credential_key, api_key)
        except Exception as e:
            self.logger.warning(
                f"Keychain storage failed, using in-memory fallback: {type(e).__name__}",
                component=LogComponent.INFERENCE,
            )

    def _get_api_key(self, credential_key: str) -> Optional[str]:
        """Retrieve an API key from the Keychain."""
        try:
            from hestia.security import get_credential_manager
            cm = get_credential_manager()
            result = cm.retrieve_operational(credential_key)
            if result is not None:
                return result
        except Exception:
            pass
        # Fallback for testing environments without Keychain
        if hasattr(self, "_key_fallback"):
            return self._key_fallback.get(credential_key)
        return None

    def _delete_api_key(self, credential_key: str) -> None:
        """Delete an API key from the Keychain."""
        # Clear in-memory fallback
        if hasattr(self, "_key_fallback"):
            self._key_fallback.pop(credential_key, None)

        try:
            from hestia.security import get_credential_manager
            cm = get_credential_manager()
            cm.delete_credential(credential_key)
        except Exception as e:
            self.logger.warning(
                f"Keychain deletion failed: {type(e).__name__}",
                component=LogComponent.INFERENCE,
            )

    async def get_api_key(self, provider: CloudProvider) -> Optional[str]:
        """Get the API key for a provider."""
        config = await self.database.get_provider(provider)
        if config is None:
            return None
        return self._get_api_key(config.credential_key)


# Module-level singleton
_cloud_manager: Optional[CloudManager] = None


async def get_cloud_manager() -> CloudManager:
    """Get or create the cloud manager singleton."""
    global _cloud_manager
    if _cloud_manager is None:
        _cloud_manager = CloudManager()
        await _cloud_manager.initialize()
    return _cloud_manager
