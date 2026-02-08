"""
Cloud LLM provider management routes for Hestia API.

WS1: Cloud LLM Support — Session 3
Provides REST endpoints for managing cloud providers, routing state,
model selection, usage tracking, and health checks.

Security: API keys are accepted via POST but never returned in responses.
Keys are stored in macOS Keychain via CredentialManager.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.schemas import (
    CloudProviderEnum,
    CloudProviderStateEnum,
    CloudProviderAddRequest,
    CloudProviderStateUpdateRequest,
    CloudProviderModelUpdateRequest,
    CloudProviderResponse,
    CloudProviderListResponse,
    CloudProviderDeleteResponse,
    CloudUsageSummaryResponse,
    CloudHealthCheckResponse,
    ErrorResponse,
)
from hestia.api.middleware.auth import get_device_token
from hestia.cloud import (
    CloudProvider,
    CloudProviderState,
    ProviderConfig,
    get_cloud_manager,
)
from hestia.inference.router import get_router
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/cloud", tags=["cloud"])
logger = get_logger()


def _config_to_response(config: ProviderConfig) -> CloudProviderResponse:
    """Convert a ProviderConfig to API response (never exposes API key)."""
    return CloudProviderResponse(
        id=config.id,
        provider=CloudProviderEnum(config.provider.value),
        state=CloudProviderStateEnum(config.state.value),
        active_model_id=config.active_model_id,
        available_models=config.available_models,
        has_api_key=bool(config.credential_key),
        health_status=config.health_status,
        last_health_check=config.last_health_check,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _compute_effective_cloud_state(providers: list) -> str:
    """
    Compute the effective cloud routing state from all providers.

    Priority: enabled_full > enabled_smart > disabled.
    If any provider is enabled_full, the system is in full cloud mode.
    If any provider is enabled_smart, the system is in smart mode.
    Otherwise, cloud is disabled.
    """
    has_full = False
    has_smart = False
    for config in providers:
        if config.state == CloudProviderState.ENABLED_FULL:
            has_full = True
        elif config.state == CloudProviderState.ENABLED_SMART:
            has_smart = True

    if has_full:
        return "enabled_full"
    elif has_smart:
        return "enabled_smart"
    return "disabled"


def _sync_router_state(providers: list) -> str:
    """Compute effective state and push it to the inference router."""
    effective = _compute_effective_cloud_state(providers)
    try:
        inference_router = get_router()
        inference_router.set_cloud_state(effective)
    except Exception as e:
        logger.warning(
            f"Failed to sync cloud state to inference router: {sanitize_for_log(e)}",
            component=LogComponent.INFERENCE,
        )
    return effective


# ── GET /v1/cloud/providers ─────────────────────────────────────────

@router.get(
    "/providers",
    response_model=CloudProviderListResponse,
    summary="List cloud providers",
    description="List all configured cloud LLM providers.",
)
async def list_providers(
    device_id: str = Depends(get_device_token),
) -> CloudProviderListResponse:
    """List all configured cloud providers."""
    try:
        manager = await get_cloud_manager()
        providers = await manager.list_providers()

        effective_state = _compute_effective_cloud_state(providers)

        logger.info(
            "Cloud providers listed",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "count": len(providers),
                "effective_state": effective_state,
            },
        )

        return CloudProviderListResponse(
            providers=[_config_to_response(p) for p in providers],
            count=len(providers),
            cloud_state=effective_state,
        )

    except Exception as e:
        logger.error(
            f"Failed to list cloud providers: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to list cloud providers.",
            },
        )


# ── POST /v1/cloud/providers ────────────────────────────────────────

@router.post(
    "/providers",
    response_model=CloudProviderResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        409: {"model": ErrorResponse, "description": "Provider already configured"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Add cloud provider",
    description="Add a cloud provider with API key. Key is stored in Keychain.",
)
async def add_provider(
    provider: CloudProviderEnum,
    request: CloudProviderAddRequest,
    device_id: str = Depends(get_device_token),
) -> CloudProviderResponse:
    """
    Add a new cloud provider.

    The API key is stored securely in macOS Keychain and never returned
    in API responses.
    """
    try:
        # Validate API key is not obviously malformed
        if len(request.api_key.strip()) < 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "invalid_api_key",
                    "message": "API key appears to be malformed (too short).",
                },
            )

        manager = await get_cloud_manager()

        # Check if provider already exists
        existing = await manager.get_provider(CloudProvider(provider.value))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "provider_exists",
                    "message": f"Provider '{provider.value}' is already configured. Remove it first to reconfigure.",
                },
            )

        config = await manager.add_provider(
            provider=CloudProvider(provider.value),
            api_key=request.api_key,
            state=CloudProviderState(request.state.value),
            model_id=request.model_id,
        )

        # Sync routing state
        providers = await manager.list_providers()
        _sync_router_state(providers)

        logger.info(
            f"Cloud provider added: {provider.value}",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "provider": provider.value,
                "state": request.state.value,
                "model_id": config.active_model_id,
            },
        )

        return _config_to_response(config)

    except HTTPException:
        raise

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_request",
                "message": "Invalid request parameters.",
            },
        )

    except Exception as e:
        logger.error(
            f"Failed to add cloud provider: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to add cloud provider.",
            },
        )


# ── DELETE /v1/cloud/providers/{provider} ───────────────────────────

@router.delete(
    "/providers/{provider}",
    response_model=CloudProviderDeleteResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Provider not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Remove cloud provider",
    description="Remove a cloud provider and delete its API key from Keychain.",
)
async def remove_provider(
    provider: CloudProviderEnum,
    device_id: str = Depends(get_device_token),
) -> CloudProviderDeleteResponse:
    """Remove a cloud provider and delete its stored API key."""
    try:
        manager = await get_cloud_manager()
        deleted = await manager.remove_provider(CloudProvider(provider.value))

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "provider_not_found",
                    "message": f"Provider '{provider.value}' is not configured.",
                },
            )

        # Sync routing state after removal
        providers = await manager.list_providers()
        _sync_router_state(providers)

        logger.info(
            f"Cloud provider removed: {provider.value}",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "provider": provider.value,
            },
        )

        return CloudProviderDeleteResponse(
            provider=CloudProviderEnum(provider.value),
            deleted=True,
            message=f"Provider '{provider.value}' removed and API key deleted.",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to remove cloud provider: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to remove cloud provider.",
            },
        )


# ── PATCH /v1/cloud/providers/{provider}/state ──────────────────────

@router.patch(
    "/providers/{provider}/state",
    response_model=CloudProviderResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Provider not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Update provider state",
    description="Update a provider's routing state (disabled, enabled_full, enabled_smart).",
)
async def update_provider_state(
    provider: CloudProviderEnum,
    request: CloudProviderStateUpdateRequest,
    device_id: str = Depends(get_device_token),
) -> CloudProviderResponse:
    """Update a provider's operational routing state."""
    try:
        manager = await get_cloud_manager()
        config = await manager.update_provider_state(
            provider=CloudProvider(provider.value),
            state=CloudProviderState(request.state.value),
        )

        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "provider_not_found",
                    "message": f"Provider '{provider.value}' is not configured.",
                },
            )

        # Sync routing state
        providers = await manager.list_providers()
        _sync_router_state(providers)

        logger.info(
            f"Cloud provider state updated: {provider.value} → {request.state.value}",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "provider": provider.value,
                "new_state": request.state.value,
            },
        )

        return _config_to_response(config)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to update provider state: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to update provider state.",
            },
        )


# ── PATCH /v1/cloud/providers/{provider}/model ──────────────────────

@router.patch(
    "/providers/{provider}/model",
    response_model=CloudProviderResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Provider not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Select active model",
    description="Select which model to use for a cloud provider.",
)
async def update_provider_model(
    provider: CloudProviderEnum,
    request: CloudProviderModelUpdateRequest,
    device_id: str = Depends(get_device_token),
) -> CloudProviderResponse:
    """Select the active model for a cloud provider."""
    try:
        manager = await get_cloud_manager()
        config = await manager.select_model(
            provider=CloudProvider(provider.value),
            model_id=request.model_id,
        )

        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "provider_not_found",
                    "message": f"Provider '{provider.value}' is not configured.",
                },
            )

        logger.info(
            f"Cloud provider model updated: {provider.value} → {request.model_id}",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "provider": provider.value,
                "model_id": request.model_id,
            },
        )

        return _config_to_response(config)

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to update provider model: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to update provider model.",
            },
        )


# ── GET /v1/cloud/usage ─────────────────────────────────────────────

@router.get(
    "/usage",
    response_model=CloudUsageSummaryResponse,
    summary="Get usage summary",
    description="Get cloud API usage and cost summary.",
)
async def get_usage_summary(
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    device_id: str = Depends(get_device_token),
) -> CloudUsageSummaryResponse:
    """Get cloud API usage and cost summary for the specified period."""
    try:
        manager = await get_cloud_manager()
        summary = await manager.get_usage_summary(days=days)

        # Transform database format (list of rows grouped by provider+model)
        # into API format (dicts keyed by provider and model)
        raw_entries = summary.get("by_provider", [])
        by_provider: Dict[str, Any] = {}
        by_model: Dict[str, Any] = {}
        total_tokens_in = 0
        total_tokens_out = 0

        if isinstance(raw_entries, list):
            for entry in raw_entries:
                prov = entry.get("provider", "unknown")
                model = entry.get("model_id", "unknown")
                # SQL SUM() returns NULL when no rows match; `or 0` handles that
                tokens_in = entry.get("total_tokens_in", 0) or 0
                tokens_out = entry.get("total_tokens_out", 0) or 0
                cost = entry.get("total_cost_usd", 0.0) or 0.0
                reqs = entry.get("total_requests", 0) or 0

                total_tokens_in += tokens_in
                total_tokens_out += tokens_out

                # Aggregate by provider
                if prov not in by_provider:
                    by_provider[prov] = {"requests": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
                by_provider[prov]["requests"] += reqs
                by_provider[prov]["tokens_in"] += tokens_in
                by_provider[prov]["tokens_out"] += tokens_out
                by_provider[prov]["cost_usd"] += cost

                # Aggregate by model
                if model not in by_model:
                    by_model[model] = {"requests": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}
                by_model[model]["requests"] += reqs
                by_model[model]["tokens_in"] += tokens_in
                by_model[model]["tokens_out"] += tokens_out
                by_model[model]["cost_usd"] += cost

        logger.info(
            "Cloud usage summary retrieved",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "period_days": days,
                "total_cost": summary.get("total_cost_usd", 0.0),
            },
        )

        return CloudUsageSummaryResponse(
            period_days=days,
            total_requests=summary.get("total_requests", 0),
            total_tokens_in=total_tokens_in,
            total_tokens_out=total_tokens_out,
            total_cost_usd=summary.get("total_cost_usd", 0.0),
            by_provider=by_provider,
            by_model=by_model,
        )

    except Exception as e:
        logger.error(
            f"Failed to get usage summary: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to get usage summary.",
            },
        )


# ── POST /v1/cloud/providers/{provider}/health ──────────────────────

@router.post(
    "/providers/{provider}/health",
    response_model=CloudHealthCheckResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Provider not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Check provider health",
    description="Run a health check against a cloud provider's API.",
)
async def check_provider_health(
    provider: CloudProviderEnum,
    device_id: str = Depends(get_device_token),
) -> CloudHealthCheckResponse:
    """Run a health check for a cloud provider."""
    try:
        manager = await get_cloud_manager()

        # Verify provider exists
        config = await manager.get_provider(CloudProvider(provider.value))
        if config is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "provider_not_found",
                    "message": f"Provider '{provider.value}' is not configured.",
                },
            )

        healthy = await manager.check_provider_health(CloudProvider(provider.value))

        # Re-fetch config to get updated health status
        config = await manager.get_provider(CloudProvider(provider.value))
        health_status = config.health_status if config else "unknown"

        logger.info(
            f"Cloud health check: {provider.value} → {health_status}",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "provider": provider.value,
                "healthy": healthy,
            },
        )

        return CloudHealthCheckResponse(
            provider=CloudProviderEnum(provider.value),
            healthy=healthy,
            health_status=health_status,
            message=f"Provider '{provider.value}' is {'healthy' if healthy else 'unhealthy'}.",
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Failed to check provider health: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to check provider health.",
            },
        )
