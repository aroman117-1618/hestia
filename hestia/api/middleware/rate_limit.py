"""
Rate limiting middleware for Hestia API.

Implements per-client rate limiting using a sliding window algorithm.
Supports different limits for different endpoint categories.

Security:
- Prevents API abuse and DoS attacks
- Uses device token or IP for client identification
- Returns standard 429 status with Retry-After header
"""

from collections import defaultdict
from time import time
from typing import Dict, List, Optional, Callable

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from hestia.logging import get_logger, LogComponent


logger = get_logger()


# Rate limit configurations by endpoint pattern
# Format: (requests_per_minute, burst_allowance)
RATE_LIMITS: Dict[str, tuple[int, int]] = {
    # Expensive operations - strict limits
    "/v1/proactive/briefing": (5, 2),
    "/v1/proactive/analyze": (2, 1),
    "/v1/proactive/patterns": (5, 2),

    # Chat operations - moderate limits (Ollama is slow anyway)
    "/v1/chat": (20, 5),

    # Memory operations
    "/v1/memory/search": (30, 10),
    "/v1/memory/approve": (60, 20),
    "/v1/memory/reject": (60, 20),

    # Task operations
    "/v1/tasks": (30, 10),

    # Auth - strict to prevent brute force
    "/v1/auth/register": (5, 2),

    # Health checks - generous
    "/v1/health": (120, 30),
    "/v1/ping": (120, 30),
}

# Default limit for unlisted endpoints
DEFAULT_LIMIT = (60, 15)


class RateLimiter:
    """
    Sliding window rate limiter with per-client tracking.

    Uses a simple in-memory store. For production with multiple
    instances, consider Redis-backed implementation.
    """

    def __init__(self, window_seconds: int = 60):
        """
        Initialize rate limiter.

        Args:
            window_seconds: Size of the sliding window in seconds.
        """
        self.window_seconds = window_seconds
        # Structure: {client_id: {endpoint_pattern: [timestamps]}}
        self._requests: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._last_cleanup = time()
        self._cleanup_interval = 300  # Clean up every 5 minutes

    def _get_client_id(self, request: Request) -> str:
        """
        Extract client identifier from request.

        Uses device token if available, falls back to IP address.
        """
        # Prefer device token for authenticated requests
        device_token = request.headers.get("X-Hestia-Device-Token")
        if device_token:
            # Use first 16 chars of token as identifier
            return f"token:{device_token[:16]}"

        # Fall back to IP address
        client_host = request.client.host if request.client else "unknown"

        # Check for forwarded headers (in case of reverse proxy)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Take the first IP in the chain
            client_host = forwarded_for.split(",")[0].strip()

        return f"ip:{client_host}"

    def _get_endpoint_pattern(self, path: str) -> str:
        """
        Match request path to rate limit pattern.

        Handles path parameters by removing specific IDs.
        """
        # Normalize path
        path = path.rstrip("/")

        # Check for exact match first
        if path in RATE_LIMITS:
            return path

        # Check for prefix matches (handles /v1/tasks/{id} -> /v1/tasks)
        for pattern in RATE_LIMITS:
            if path.startswith(pattern):
                return pattern

        return "default"

    def _cleanup_old_requests(self) -> None:
        """Remove expired request timestamps to prevent memory bloat."""
        now = time()

        if now - self._last_cleanup < self._cleanup_interval:
            return

        cutoff = now - self.window_seconds

        for client_id in list(self._requests.keys()):
            client_data = self._requests[client_id]
            for endpoint in list(client_data.keys()):
                client_data[endpoint] = [
                    ts for ts in client_data[endpoint] if ts > cutoff
                ]
                # Remove empty lists
                if not client_data[endpoint]:
                    del client_data[endpoint]
            # Remove empty client entries
            if not client_data:
                del self._requests[client_id]

        self._last_cleanup = now

    def check_rate_limit(
        self,
        request: Request,
    ) -> tuple[bool, Optional[int]]:
        """
        Check if request is within rate limits.

        Args:
            request: The incoming request.

        Returns:
            Tuple of (is_allowed, retry_after_seconds).
            If allowed, retry_after is None.
        """
        self._cleanup_old_requests()

        client_id = self._get_client_id(request)
        endpoint_pattern = self._get_endpoint_pattern(request.url.path)

        # Get limits for this endpoint
        if endpoint_pattern == "default":
            requests_per_minute, burst = DEFAULT_LIMIT
        else:
            requests_per_minute, burst = RATE_LIMITS[endpoint_pattern]

        now = time()
        cutoff = now - self.window_seconds

        # Get request history for this client/endpoint
        history = self._requests[client_id][endpoint_pattern]

        # Remove old requests
        history = [ts for ts in history if ts > cutoff]
        self._requests[client_id][endpoint_pattern] = history

        # Check if over limit
        if len(history) >= requests_per_minute:
            # Calculate retry-after based on oldest request in window
            oldest = min(history) if history else now
            retry_after = int(self.window_seconds - (now - oldest)) + 1
            return False, max(1, retry_after)

        # Allow request and record timestamp
        history.append(now)
        return True, None

    def get_remaining(self, request: Request) -> tuple[int, int]:
        """
        Get remaining requests and reset time for a client/endpoint.

        Returns:
            Tuple of (remaining_requests, seconds_until_reset).
        """
        client_id = self._get_client_id(request)
        endpoint_pattern = self._get_endpoint_pattern(request.url.path)

        if endpoint_pattern == "default":
            requests_per_minute, _ = DEFAULT_LIMIT
        else:
            requests_per_minute, _ = RATE_LIMITS[endpoint_pattern]

        now = time()
        cutoff = now - self.window_seconds

        history = self._requests[client_id][endpoint_pattern]
        active_requests = len([ts for ts in history if ts > cutoff])

        remaining = max(0, requests_per_minute - active_requests)

        # Calculate reset time
        if history:
            oldest = min(ts for ts in history if ts > cutoff)
            reset_in = int(self.window_seconds - (now - oldest))
        else:
            reset_in = self.window_seconds

        return remaining, max(0, reset_in)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Adds rate limit headers to all responses and returns 429
    when limits are exceeded.
    """

    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or RateLimiter()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Check rate limit
        allowed, retry_after = self.rate_limiter.check_rate_limit(request)

        if not allowed:
            # Log rate limit hit
            client_id = self.rate_limiter._get_client_id(request)
            logger.warning(
                f"Rate limit exceeded for {client_id}",
                component=LogComponent.API,
                data={
                    "client_id": client_id,
                    "path": request.url.path,
                    "retry_after": retry_after,
                },
            )

            # Return 429 with Retry-After header
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": str(retry_after)},
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining, reset_in = self.rate_limiter.get_remaining(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_in)

        return response


# Module-level singleton
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the singleton rate limiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter
