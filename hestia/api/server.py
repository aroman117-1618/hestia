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

import asyncio
import os
import signal
import ssl
import time
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
from hestia.memory import get_memory_manager, close_memory_manager
from hestia.tasks import get_task_manager, close_task_manager
from hestia.orders import get_order_manager, get_order_scheduler, close_order_manager, close_order_scheduler
from hestia.agents import get_agent_manager, close_agent_manager
from hestia.user import get_user_manager, close_user_manager
from hestia.cloud import get_cloud_manager, close_cloud_manager
from hestia.health import get_health_manager, close_health_manager
from hestia.wiki import get_wiki_manager, get_wiki_scheduler, close_wiki_scheduler, close_wiki_manager
from hestia.explorer import get_explorer_manager, close_explorer_manager
from hestia.newsfeed import get_newsfeed_manager, close_newsfeed_manager
from hestia.investigate import get_investigate_manager, close_investigate_manager
from hestia.research.manager import get_research_manager, close_research_manager
from hestia.files import get_file_manager, close_file_manager
from hestia.inbox import get_inbox_manager, close_inbox_manager
from hestia.outcomes import get_outcome_manager, close_outcome_manager
from hestia.apple_cache import get_apple_cache_manager, close_apple_cache_manager
from hestia.notifications import get_notification_manager, close_notification_manager
from hestia.orchestration.audit_db import get_routing_audit_db, close_routing_audit_db
from hestia.learning import get_learning_scheduler, close_learning_scheduler
from hestia.trading.manager import close_trading_manager

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
    health_data_router,
    wiki_router,
    user_profile_router,
    explorer_router,
    newsfeed_router,
    investigate_router,
    research_router,
    files_router,
    inbox_router,
    outcomes_router,
    ws_chat_router,
)
from hestia.api.routes.agents_v2 import router as agents_v2_router
from hestia.api.routes.learning import router as learning_router
from hestia.api.routes.trading import router as trading_router
from hestia.api.routes.notifications import router as notifications_router

logger = get_logger()


# =============================================================================
# Security Middleware
# =============================================================================

# Cache-Control policies by path prefix (most specific first)
_CACHE_POLICIES: list[tuple[str, str]] = [
    ("/v1/ping", "max-age=10"),
    ("/v1/tools", "max-age=60"),
    ("/v1/wiki/articles", "max-age=30"),
    # /v1/ready must always be fresh (default no-store applies)
]
_DEFAULT_CACHE_POLICY = "no-store, no-cache"


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
    - Cache-Control: Path-aware caching (read-heavy endpoints cacheable)
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

        # Path-aware Cache-Control
        path = request.url.path
        cache_policy = _DEFAULT_CACHE_POLICY
        for prefix, policy in _CACHE_POLICIES:
            if path.startswith(prefix):
                cache_policy = policy
                break
        response.headers["Cache-Control"] = cache_policy
        if cache_policy == _DEFAULT_CACHE_POLICY:
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


# Paths that bypass the readiness gate (health probes, docs, root)
_READINESS_BYPASS_PATHS = frozenset({
    "/v1/ping", "/v1/ready", "/docs", "/redoc", "/openapi.json", "/",
    "/v1/ws/chat",  # WebSocket bypasses HTTP middleware, listed for completeness
})


class ReadinessMiddleware(BaseHTTPMiddleware):
    """
    Returns 503 Service Unavailable while the server is still initializing.

    Prevents clients from hitting partially-initialized managers during
    the startup window. Bypasses health probes and docs.
    """

    async def dispatch(self, request: Request, call_next):
        if not getattr(request.app.state, "ready", False):
            if request.url.path not in _READINESS_BYPASS_PATHS:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "service_unavailable",
                        "message": "Server is starting up. Please retry shortly.",
                        "ready": False,
                    },
                    headers={"Retry-After": "5"},
                )
        return await call_next(request)


_shutdown_event: asyncio.Event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.

    Handles startup and shutdown events with graceful shutdown support.
    SIGTERM/SIGINT set the shutdown event, giving in-flight requests
    up to 15 seconds to complete before the process exits.
    """
    # Startup
    logger.info(
        "Hestia API starting",
        component=LogComponent.API,
        data={"version": "1.0.0"}
    )

    # Register signal handlers for graceful shutdown
    loop = asyncio.get_running_loop()

    def _signal_handler(sig: int) -> None:
        sig_name = signal.Signals(sig).name
        logger.info(
            f"Received {sig_name} — initiating graceful shutdown",
            component=LogComponent.API,
        )
        _shutdown_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler, sig)

    try:
        startup_start = time.monotonic()

        # ── Phase 1: Sequential foundations ──────────────────────────
        # request_handler and memory_manager are dependencies for other managers
        handler = await get_request_handler()
        memory = await get_memory_manager()

        # ── Phase 2: Parallel independent managers ───────────────────
        # These managers don't depend on each other at init time.
        # Uses return_exceptions=True so one failure doesn't cancel others.
        from hestia.agents.config_loader import get_config_loader
        from hestia.api.invite_store import get_invite_store

        phase2_names = [
            "task_manager", "order_manager", "agent_manager", "user_manager",
            "cloud_manager", "health_manager", "wiki_manager", "config_loader",
            "invite_store", "explorer_manager", "newsfeed_manager",
            "investigate_manager", "research_manager", "file_manager",
            "inbox_manager", "outcome_manager", "apple_cache_manager",
            "notification_manager",
        ]
        phase2_coroutines = [
            get_task_manager(), get_order_manager(), get_agent_manager(),
            get_user_manager(), get_cloud_manager(), get_health_manager(),
            get_wiki_manager(), get_config_loader(), get_invite_store(),
            get_explorer_manager(), get_newsfeed_manager(),
            get_investigate_manager(), get_research_manager(),
            get_file_manager(), get_inbox_manager(),
            get_outcome_manager(), get_apple_cache_manager(),
            get_notification_manager(),
        ]

        try:
            phase2_start = time.monotonic()
            results = await asyncio.gather(*phase2_coroutines, return_exceptions=True)
            phase2_ms = round((time.monotonic() - phase2_start) * 1000)

            # Check for failures and retry sequentially
            failures = [
                (name, res) for name, res in zip(phase2_names, results)
                if isinstance(res, Exception)
            ]
            if failures:
                failed_names = [f[0] for f in failures]
                logger.warning(
                    f"Parallel init failed for {failed_names}, retrying sequentially",
                    component=LogComponent.API,
                    data={"failed": failed_names, "parallel_ms": phase2_ms},
                )
                # Retry failed managers sequentially
                retry_map = {
                    "task_manager": get_task_manager,
                    "order_manager": get_order_manager,
                    "agent_manager": get_agent_manager,
                    "user_manager": get_user_manager,
                    "cloud_manager": get_cloud_manager,
                    "health_manager": get_health_manager,
                    "wiki_manager": get_wiki_manager,
                    "config_loader": get_config_loader,
                    "invite_store": get_invite_store,
                    "explorer_manager": get_explorer_manager,
                    "newsfeed_manager": get_newsfeed_manager,
                    "investigate_manager": get_investigate_manager,
                    "research_manager": get_research_manager,
                    "file_manager": get_file_manager,
                    "inbox_manager": get_inbox_manager,
                    "outcome_manager": get_outcome_manager,
                    "apple_cache_manager": get_apple_cache_manager,
                }
                for name, _ in failures:
                    await retry_map[name]()

            logger.info(
                "Phase 2 init complete",
                component=LogComponent.API,
                data={
                    "parallel_ms": phase2_ms,
                    "managers": len(phase2_names),
                    "failures_retried": len(failures) if failures else 0,
                },
            )

        except Exception as e:
            # Total parallel failure — fall back to full sequential init
            logger.warning(
                f"Parallel init failed entirely ({type(e).__name__}), using sequential fallback",
                component=LogComponent.API,
            )
            await get_task_manager()
            await get_order_manager()
            await get_agent_manager()
            await get_user_manager()
            await get_cloud_manager()
            await get_health_manager()
            await get_wiki_manager()
            await get_config_loader()
            await get_invite_store()
            await get_explorer_manager()
            await get_newsfeed_manager()
            await get_investigate_manager()
            await get_research_manager()
            await get_file_manager()
            await get_inbox_manager()
            await get_outcome_manager()
            await get_apple_cache_manager()
            await get_notification_manager()
            await get_routing_audit_db()

        # ── Phase 3: Sequential dependents ───────────────────────────
        # Schedulers depend on their managers from Phase 2
        order_scheduler = await get_order_scheduler()
        wiki_scheduler = await get_wiki_scheduler()
        learning_scheduler = await get_learning_scheduler()

        # ── Phase 4: Fire-and-forget background tasks ────────────────
        async def _post_deploy_wiki_refresh() -> None:
            """Refresh stale wiki articles after server restart."""
            try:
                delay = wiki_scheduler.get_post_deploy_delay()
                if not wiki_scheduler.is_post_deploy_enabled():
                    return
                await asyncio.sleep(delay)
                wiki_mgr = await get_wiki_manager()
                result = await wiki_mgr.regenerate_stale("deploy")
                logger.info(
                    "Post-deploy wiki refresh complete",
                    component=LogComponent.WIKI,
                    data={
                        "regenerated": len(result.get("regenerated", [])),
                        "skipped": len(result.get("skipped", [])),
                        "failed": len(result.get("failed", [])),
                    },
                )
            except Exception as e:
                logger.warning(
                    f"Post-deploy wiki refresh failed: {type(e).__name__}",
                    component=LogComponent.WIKI,
                )

        asyncio.create_task(_post_deploy_wiki_refresh())

        startup_ms = round((time.monotonic() - startup_start) * 1000)

        logger.info(
            "Hestia API ready",
            component=LogComponent.API,
            data={
                "startup_ms": startup_ms,
                "managers_initialized": 19,
            }
        )

        # Mark server as ready — ReadinessMiddleware starts allowing traffic
        app.state.ready = True
        app.state.started_at = time.monotonic()

        yield

    finally:
        # Graceful shutdown: Uvicorn handles request draining.
        # Close all managers in reverse initialization order.
        # Each in its own try/except so one failure doesn't block others.
        logger.info(
            "Hestia API shutting down — cleaning up connections",
            component=LogComponent.API,
        )

        shutdown_errors = 0

        # 22. learning_scheduler (newest -> first closed)
        try:
            await close_learning_scheduler()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Learning scheduler cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 22. notification_manager
        try:
            await close_notification_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Notification manager cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 22. trading_manager
        try:
            await close_trading_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Trading manager cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 21. routing_audit_db
        try:
            await close_routing_audit_db()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Routing audit DB cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 20. outcome_manager
        try:
            await close_outcome_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Outcome manager cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 20. apple_cache_manager
        try:
            await close_apple_cache_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Apple cache manager cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 19. inbox_manager
        try:
            await close_inbox_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Inbox manager cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 18. file_manager
        try:
            await close_file_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"File manager cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 17. research_manager
        try:
            await close_research_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Research cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 16. investigate_manager
        try:
            await close_investigate_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Investigate cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 15. newsfeed_manager
        try:
            await close_newsfeed_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Newsfeed cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 14. explorer_manager
        try:
            await close_explorer_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Explorer cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 13. invite_store
        try:
            invite_store = await get_invite_store()
            await invite_store.close()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Invite store cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 12. config_loader/writer
        try:
            from hestia.agents.config_loader import close_config_loader
            from hestia.agents.config_writer import close_config_writer
            await close_config_loader()
            await close_config_writer()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Config cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 11. wiki_scheduler
        try:
            await close_wiki_scheduler()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Wiki scheduler cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 10. wiki_manager
        try:
            await close_wiki_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Wiki cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 9. health_manager
        try:
            await close_health_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Health cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 8. cloud_manager
        try:
            await close_cloud_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Cloud cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 7. user_manager
        try:
            await close_user_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"User cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 6. agent_manager
        try:
            await close_agent_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Agent cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 5. order_scheduler (before order_manager — scheduler uses manager)
        try:
            await close_order_scheduler()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Order scheduler cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 4. order_manager
        try:
            await close_order_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Order cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 3. task_manager
        try:
            await close_task_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Task cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 2. memory_manager (foundation — closed last of the managers)
        try:
            await close_memory_manager()
        except Exception as e:
            shutdown_errors += 1
            logger.warning(
                f"Memory cleanup error: {type(e).__name__}",
                component=LogComponent.API,
            )

        # 1. request_handler — no close() needed (delegates to managers above)

        logger.info(
            "Hestia API shutdown complete",
            component=LogComponent.API,
            data={"shutdown_errors": shutdown_errors},
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

# Initialize readiness state (set True after all managers init in lifespan)
app.state.ready = False
app.state.started_at = 0.0

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

# Add middleware (Starlette executes in reverse registration order)
# Last registered = first to execute on request
# 1. Security headers - applied to all responses
# 2. Request ID - for correlation and debugging
# 3. Rate limiting - prevents API abuse
# 4. Readiness gate - 503 during startup (registered LAST → executes FIRST)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(ReadinessMiddleware)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    logger.warning(
        "Request validation error",
        component=LogComponent.API,
        data={"errors": str(exc.errors())},
    )

    # Strip Pydantic internals — only expose field names and messages
    safe_details = [
        {"field": " -> ".join(str(loc) for loc in err.get("loc", [])), "message": err.get("msg", "Invalid value")}
        for err in exc.errors()
    ]

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": "validation_error",
            "message": "Invalid request format",
            "details": safe_details,
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
app.include_router(health_data_router)
app.include_router(wiki_router)
app.include_router(agents_v2_router)
app.include_router(user_profile_router)
app.include_router(explorer_router)
app.include_router(newsfeed_router)
app.include_router(investigate_router)
app.include_router(research_router)
app.include_router(files_router)
app.include_router(inbox_router)
app.include_router(outcomes_router)
app.include_router(learning_router)
app.include_router(trading_router)
app.include_router(notifications_router)
app.include_router(ws_chat_router)


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
        # Recycle worker after ~5000 requests to prevent memory leak accumulation.
        # launchd KeepAlive restarts the process automatically.
        "limit_max_requests": 5000,
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
