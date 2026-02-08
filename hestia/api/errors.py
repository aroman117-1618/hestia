"""
Standardized error handling for Hestia API routes.

Provides consistent error sanitization for both logging and HTTP responses.
Prevents internal error details (file paths, database schemas, stack traces)
from leaking to clients or appearing unsanitized in logs.
"""

from typing import Any, Dict


def sanitize_for_log(e: Exception) -> str:
    """Return a safe string for logging: exception type only, no internals.

    Use this in logger.error() calls instead of raw f"{e}".

    Example:
        logger.error(
            f"Failed to create order: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
    """
    return type(e).__name__


def safe_error_detail(operation: str) -> Dict[str, Any]:
    """Return a generic error detail dict for HTTPException responses.

    Use this instead of detail=str(e) to prevent leaking internals.

    Args:
        operation: Human-readable description of the failed operation.

    Example:
        raise HTTPException(
            status_code=500,
            detail=safe_error_detail("list cloud providers"),
        )
    """
    return {
        "error": "internal_error",
        "message": f"Failed to {operation}.",
    }
