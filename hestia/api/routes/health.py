"""
Health check routes for Hestia API.

Provides system health status and component checks.
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from hestia.api.schemas import (
    HealthResponse,
    HealthStatusEnum,
    HealthComponents,
    InferenceHealth,
    MemoryHealth,
    StateMachineHealth,
    ToolsHealth,
)
from hestia.orchestration.handler import get_request_handler
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1", tags=["health"])
logger = get_logger()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System health check",
    description="Check the health status of all Hestia components."
)
async def health_check() -> HealthResponse:
    """
    Check system health.

    Returns the health status of all components:
    - inference: Ollama/model availability
    - memory: Vector store and database status
    - state_machine: Task processing status
    - tools: Tool registry status

    Does not require authentication.
    """
    timestamp = datetime.now(timezone.utc)

    try:
        handler = await get_request_handler()
        health_data = await handler.health_check()

        # Parse inference health
        inference_data = health_data.get("components", {}).get("inference", {})
        inference_status = HealthStatusEnum(inference_data.get("status", "unhealthy"))
        inference_health = InferenceHealth(
            status=inference_status,
            ollama_available=inference_data.get("ollama_available"),
            primary_model_available=inference_data.get("primary_model_available"),
            error=inference_data.get("error"),
        )

        # Parse memory health
        memory_data = health_data.get("components", {}).get("memory", {})
        memory_status = HealthStatusEnum(memory_data.get("status", "unhealthy"))
        memory_health = MemoryHealth(
            status=memory_status,
            vector_count=memory_data.get("vector_count"),
            error=memory_data.get("error"),
        )

        # Parse state machine health
        sm_data = health_data.get("components", {}).get("state_machine", {})
        sm_status = HealthStatusEnum(sm_data.get("status", "unhealthy"))
        state_machine_health = StateMachineHealth(
            status=sm_status,
            active_tasks=sm_data.get("active_tasks", 0),
            state_summary=sm_data.get("state_summary"),
        )

        # Parse tools health
        tools_data = health_data.get("components", {}).get("tools", {})
        tools_status = HealthStatusEnum(tools_data.get("status", "unhealthy"))
        tools_health = ToolsHealth(
            status=tools_status,
            registered_tools=tools_data.get("registered_tools", 0),
            tool_names=tools_data.get("tool_names"),
            error=tools_data.get("error"),
        )

        # Determine overall status
        component_statuses = [
            inference_status,
            memory_status,
            sm_status,
            tools_status,
        ]

        if HealthStatusEnum.UNHEALTHY in component_statuses:
            overall_status = HealthStatusEnum.DEGRADED
        elif HealthStatusEnum.DEGRADED in component_statuses:
            overall_status = HealthStatusEnum.DEGRADED
        else:
            overall_status = HealthStatusEnum.HEALTHY

        return HealthResponse(
            status=overall_status,
            timestamp=timestamp,
            components=HealthComponents(
                inference=inference_health,
                memory=memory_health,
                state_machine=state_machine_health,
                tools=tools_health,
            ),
        )

    except Exception as e:
        logger.error(
            f"Health check failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )

        # Return degraded status if we can't check components
        return HealthResponse(
            status=HealthStatusEnum.UNHEALTHY,
            timestamp=timestamp,
            components=HealthComponents(
                inference=InferenceHealth(
                    status=HealthStatusEnum.UNHEALTHY,
                    error=sanitize_for_log(e),
                ),
                memory=MemoryHealth(
                    status=HealthStatusEnum.UNHEALTHY,
                    error=sanitize_for_log(e),
                ),
                state_machine=StateMachineHealth(
                    status=HealthStatusEnum.UNHEALTHY,
                ),
                tools=ToolsHealth(
                    status=HealthStatusEnum.UNHEALTHY,
                    error=sanitize_for_log(e),
                ),
            ),
        )


@router.get(
    "/ready",
    summary="Readiness probe",
    description="Returns 200 when all managers are initialized, 503 during startup."
)
async def readiness_check(request: Request) -> JSONResponse:
    """
    Readiness probe for monitoring and watchdog.

    Returns 200 with uptime when ready, 503 when still initializing.
    Unlike /ping (connectivity) or /health (component status), this
    proves the full manager stack is initialized and serving traffic.

    Does not require authentication.
    """
    is_ready = getattr(request.app.state, "ready", False)
    started_at = getattr(request.app.state, "started_at", 0.0)
    uptime = round(time.monotonic() - started_at, 1) if started_at > 0 else 0.0

    if is_ready:
        return JSONResponse(
            status_code=200,
            content={"ready": True, "uptime_seconds": uptime},
        )
    else:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "uptime_seconds": 0.0},
            headers={"Retry-After": "5"},
        )


@router.get(
    "/ping",
    summary="Simple ping endpoint",
    description="Returns 'pong' - useful for basic connectivity checks."
)
async def ping() -> dict:
    """Simple ping endpoint for basic connectivity checks."""
    return {"status": "ok", "message": "pong"}
