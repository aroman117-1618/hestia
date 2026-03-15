"""
ETag utilities for conditional GET support.

Computes lightweight ETags from metadata (not full response bodies)
and checks If-None-Match headers for 304 responses.
"""

import hashlib
from typing import Optional

from fastapi import Request, Response


def compute_etag(data: str) -> str:
    """Compute a short ETag from a string (e.g. concatenated metadata)."""
    return hashlib.md5(data.encode()).hexdigest()[:16]


def add_etag(response: Response, etag: str) -> None:
    """Set the ETag header on a response."""
    response.headers["ETag"] = f'"{etag}"'


def check_not_modified(request: Request, etag: str) -> bool:
    """Check If-None-Match header against computed ETag.

    Returns True if the client's cached version matches (304 should be sent).
    """
    if_none_match = request.headers.get("if-none-match", "")
    # Strip quotes and compare
    return if_none_match.strip('"') == etag


def etag_response(
    request: Request,
    response: Response,
    etag_source: str,
) -> Optional[Response]:
    """Compute ETag, check If-None-Match, set header.

    Returns a 304 Response if the client cache is fresh, or None if
    the caller should return the full response body.

    Usage:
        cached = etag_response(request, response, etag_source)
        if cached:
            return cached
        return MyResponseModel(...)
    """
    etag = compute_etag(etag_source)
    add_etag(response, etag)

    if check_not_modified(request, etag):
        return Response(status_code=304, headers={"ETag": f'"{etag}"'})

    return None
