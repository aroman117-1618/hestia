"""
Tests for ETag conditional GET support.

Tests the etag utility functions and their integration with wiki/tools routes.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hestia.api.etag import compute_etag, check_not_modified, etag_response


class TestComputeEtag:
    """Tests for ETag computation."""

    def test_deterministic(self):
        """Same input produces same ETag."""
        assert compute_etag("hello") == compute_etag("hello")

    def test_different_inputs(self):
        """Different inputs produce different ETags."""
        assert compute_etag("hello") != compute_etag("world")

    def test_returns_16_chars(self):
        """ETag is 16 hex characters."""
        etag = compute_etag("test data")
        assert len(etag) == 16
        assert all(c in "0123456789abcdef" for c in etag)


class TestCheckNotModified:
    """Tests for If-None-Match checking."""

    def test_matching_etag(self):
        """Matching ETag returns True (304 should be sent)."""
        request = MagicMock()
        request.headers = {"if-none-match": '"abc123"'}
        assert check_not_modified(request, "abc123") is True

    def test_non_matching_etag(self):
        """Non-matching ETag returns False."""
        request = MagicMock()
        request.headers = {"if-none-match": '"old-etag"'}
        assert check_not_modified(request, "new-etag") is False

    def test_no_header(self):
        """Missing If-None-Match returns False."""
        request = MagicMock()
        request.headers = {}
        assert check_not_modified(request, "abc123") is False

    def test_unquoted_etag(self):
        """Unquoted If-None-Match still matches."""
        request = MagicMock()
        request.headers = {"if-none-match": "abc123"}
        assert check_not_modified(request, "abc123") is True


class TestEtagResponse:
    """Tests for the combined etag_response helper."""

    def test_returns_304_on_match(self):
        """Returns 304 Response when ETag matches."""
        request = MagicMock()
        request.headers = {"if-none-match": f'"{compute_etag("test")}"'}
        response = MagicMock()
        response.headers = {}

        result = etag_response(request, response, "test")
        assert result is not None
        assert result.status_code == 304

    def test_returns_none_on_mismatch(self):
        """Returns None when ETag doesn't match (caller returns full body)."""
        request = MagicMock()
        request.headers = {"if-none-match": '"stale-etag"'}
        response = MagicMock()
        response.headers = {}

        result = etag_response(request, response, "test")
        assert result is None

    def test_sets_etag_header(self):
        """Sets ETag header on the response object."""
        request = MagicMock()
        request.headers = {}
        mock_headers = MagicMock()
        response = MagicMock()
        response.headers = mock_headers

        etag_response(request, response, "test")
        etag = compute_etag("test")
        mock_headers.__setitem__.assert_called_with("ETag", f'"{etag}"')

    def test_returns_none_on_first_request(self):
        """First request (no If-None-Match) returns None."""
        request = MagicMock()
        request.headers = {}
        response = MagicMock()
        response.headers = {}

        result = etag_response(request, response, "anything")
        assert result is None
