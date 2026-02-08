"""
FastAPI server for Hestia API.

Main entry point for the REST API.

Supports TLS/HTTPS for secure remote access via Tailscale.

Security features:
- HTTPS required for production (TLS 1.2+)
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Error message sanitization (no stack traces to clients)
- CORS restriction
"""

import os
import ssl
import traceback
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from hestia.logging import get_logger, LogComponent
from hestia.api.middleware.rate_limit import RateLimitMiddleware
from hestia.orchestration.handler import get_request_handler
from hestia.memory import get_memory_manager
from hestia.tasks import get_task_manager
from hestia.orders import get_order_manager, get_order_scheduler
from hestia.agents import get_agent_manager
from hestia.user import get_user_manager
from hestia.cloud import get_cloud_manager

# Import routers
from hestia.api.routes import (
    health_router,
    chat_router,
    mode_router,
    memory_router,
    sessions_router,
    tools_router,
    auth_router,
    tasks_router,
    proactive_router,
    orders_router,
    agents_router,
    user_router,
    cloud_router,
    voice_router,
)

logger = get_logger()


# =============================================================================
# Security Middleware
# =============================================================================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Headers added:
    - Strict-Transport-Security: Enforce HTTPS
    - X-Content-Type-Options: Prevent MIME type sniffing
    - X-Frame-Options: Prevent clickjacking
    - X-XSS-Protection: Enable XSS filtering
    - Content-Security-Policy: Restrict resource loading
    - Referrer-Policy: Control referrer information
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Add security headers
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        return response


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add a unique request ID to each request for tracking.
    """

    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        response = await call_next(request)

        # Add request ID to response headers for debugging
        response.headers["X-Request-ID"] = request_id

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.

    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        "Hestia API starting",
        component=LogComponent.API,
        data={"version": "1.0.0"}
    )

    try:
        # Initialize core components
        handler = await get_request_handler()
        memory = await get_memory_manager()
        task_manager = await get_task_manager()

        # Initialize new Phase 6b components
        order_manager = await get_order_manager()
        order_scheduler = await get_order_scheduler()
        agent_manager = await get_agent_manager()
        user_manager = await get_user_manager()

        # Initialize cloud provider management (WS1)
        cloud_manager = await get_cloud_manager()

        logger.info(
            "Hestia API ready",
            component=LogComponent.API,
            data={
                "tools_registered": len(handler.get_tool_definitions()) > 0,
                "task_manager_ready": task_manager is not None,
                "order_scheduler_ready": order_scheduler is not None,
                "agent_manager_ready": agent_manager is not None,
                "user_manager_ready": user_manager is not None,
                "cloud_manager_ready": cloud_manager is not None,
            }
        )

        yield

    finally:
        # Shutdown
        logger.info(
            "Hestia API shutting down",
            component=LogComponent.API,
        )


# Create FastAPI app
app = FastAPI(
    title="Hestia API",
    description="""
Hestia is a locally-hosted personal AI assistant.

## Features

- **Chat**: Natural language conversation with context-aware responses
- **Modes**: Three persona modes (Tia, Mira, Olly) for different interaction styles
- **Memory**: Semantic search and governed memory persistence (ADR-002)
- **Tools**: 20+ Apple ecosystem integrations (Calendar, Reminders, Notes, Mail)
- **Proactive**: Daily briefings, behavioral patterns, context-aware suggestions (ADR-017)

## Authentication

All endpoints (except `/v1/health`, `/v1/ping`, and `/v1/auth/register`) require
a device token. Register a device first, then include the token in requests:

```
X-Hestia-Device-Token: <your-token>
```

## Modes

- **Tia** (default): Efficient, direct, occasionally sardonic
- **Mira**: Socratic teaching, patient explanations
- **Olly**: Focused project work, minimal tangents
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware - restrict origins for security
# Use HESTIA_CORS_ORIGINS env var to customize (comma-separated)
CORS_ORIGINS = os.environ.get(
    "HESTIA_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8080,http://localhost:8443"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["X-Hestia-Device-Token", "Content-Type", "Accept"],
)

# Add security middleware (order matters - outermost first)
# 1. Security headers - applied to all responses
# 2. Request ID - for correlation and debugging
# 3. Rate limiting - prevents API abuse
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RateLimitMiddleware)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(
        "Request validation error",
        component=LogComponent.API,
        data={"errors": str(exc.errors())},
    )

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "validation_error",
            "message": "Invalid request format",
            "details": exc.errors(),
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """
    Handle unexpected exceptions with security-conscious error responses.

    Security: Never expose internal paths, stack traces, or implementation
    details to clients. Log full details internally for debugging.
    """
    # Get request ID for correlation (if available)
    request_id = getattr(request.state, "request_id", None)

    # Log full error details internally (for debugging)
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        component=LogComponent.API,
        data={
            "request_id": request_id,
            "exception_type": type(exc).__name__,
            "traceback": traceback.format_exc(),  # Internal logging only
            "path": str(request.url.path),
            "method": request.method,
        },
    )

    # Return sanitized error to client (no internal details)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred. Please try again.",
            "request_id": request_id,  # For support correlation
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        },
    )


# Include routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(mode_router)
app.include_router(memory_router)
app.include_router(sessions_router)
app.include_router(tools_router)
app.include_router(tasks_router)
app.include_router(proactive_router)
app.include_router(orders_router)
app.include_router(agents_router)
app.include_router(user_router)
app.include_router(cloud_router)
app.include_router(voice_router)


# Root endpoint
@app.get("/", include_in_schema=False)
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Hestia API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/v1/health",
    }


def get_ssl_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    """
    Create SSL context for HTTPS.

    Args:
        cert_path: Path to certificate file.
        key_path: Path to private key file.

    Returns:
        Configured SSL context.

    Raises:
        FileNotFoundError: If certificate or key file not found.
    """
    if not os.path.exists(cert_path):
        raise FileNotFoundError(f"SSL certificate not found: {cert_path}")
    if not os.path.exists(key_path):
        raise FileNotFoundError(f"SSL key not found: {key_path}")

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(cert_path, key_path)
    return ssl_context


def run_server(
    host: str = "0.0.0.0",
    port: int = 8443,
    reload: bool = False,
    log_level: str = "info",
    ssl_cert: Optional[str] = None,
    ssl_key: Optional[str] = None,
):
    """
    Run the Hestia API server.

    Args:
        host: Host to bind to.
        port: Port to listen on.
        reload: Enable auto-reload for development.
        log_level: Logging level.
        ssl_cert: Path to SSL certificate (enables HTTPS).
        ssl_key: Path to SSL private key.

    Environment variables:
        HESTIA_SSL_CERT: SSL certificate path (alternative to ssl_cert).
        HESTIA_SSL_KEY: SSL key path (alternative to ssl_key).
    """
    import uvicorn

    # Check environment variables for SSL config
    cert_path = ssl_cert or os.environ.get("HESTIA_SSL_CERT")
    key_path = ssl_key or os.environ.get("HESTIA_SSL_KEY")

    # Default paths for certificates
    if cert_path is None and key_path is None:
        default_cert = Path(__file__).parent.parent.parent / "certs" / "hestia.crt"
        default_key = Path(__file__).parent.parent.parent / "certs" / "hestia.key"
        if default_cert.exists() and default_key.exists():
            cert_path = str(default_cert)
            key_path = str(default_key)
            logger.info(
                "Using default SSL certificates",
                component=LogComponent.API,
                data={"cert": cert_path}
            )

    # Configure uvicorn with or without SSL
    uvicorn_config = {
        "app": "hestia.api.server:app",
        "host": host,
        "port": port,
        "reload": reload,
        "log_level": log_level,
    }

    if cert_path and key_path:
        # Validate certificate files exist
        get_ssl_context(cert_path, key_path)  # Will raise if invalid
        uvicorn_config["ssl_certfile"] = cert_path
        uvicorn_config["ssl_keyfile"] = key_path
        protocol = "https"
    else:
        protocol = "http"
        if not reload:
            logger.warning(
                "Running without TLS - tokens will be transmitted in cleartext",
                component=LogComponent.API,
            )

    print(f"\n🏛  Hestia API starting on {protocol}://{host}:{port}")
    print(f"   API docs: {protocol}://localhost:{port}/docs\n")

    uvicorn.run(**uvicorn_config)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Hestia API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8443, help="Port to listen on")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--ssl-cert", help="Path to SSL certificate")
    parser.add_argument("--ssl-key", help="Path to SSL private key")
    parser.add_argument("--log-level", default="info", help="Logging level")

    args = parser.parse_args()

    run_server(
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
        ssl_cert=args.ssl_cert,
        ssl_key=args.ssl_key,
    )
