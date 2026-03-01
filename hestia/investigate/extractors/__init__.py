"""
Content extractors for the Investigate module.

Classifies URLs by content type and dispatches to the appropriate extractor.
"""

import re
from typing import Optional

from ..models import ContentType

# Compiled URL patterns for classification
_YOUTUBE_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+", re.IGNORECASE),
    re.compile(r"(?:https?://)?youtu\.be/[\w-]+", re.IGNORECASE),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+", re.IGNORECASE),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/[\w-]+", re.IGNORECASE),
    re.compile(r"(?:https?://)?m\.youtube\.com/watch\?v=[\w-]+", re.IGNORECASE),
]

_TIKTOK_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+", re.IGNORECASE),
    re.compile(r"(?:https?://)?vm\.tiktok\.com/[\w-]+", re.IGNORECASE),
    re.compile(r"(?:https?://)?(?:www\.)?tiktok\.com/t/[\w-]+", re.IGNORECASE),
]


def classify_url(url: str) -> ContentType:
    """
    Classify a URL into a content type based on regex patterns.

    Args:
        url: The URL to classify.

    Returns:
        ContentType enum value.
    """
    url = url.strip()

    for pattern in _YOUTUBE_PATTERNS:
        if pattern.search(url):
            return ContentType.YOUTUBE

    for pattern in _TIKTOK_PATTERNS:
        if pattern.search(url):
            return ContentType.TIKTOK

    # Default: treat as web article
    return ContentType.WEB_ARTICLE


def get_extractor(content_type: ContentType) -> Optional["BaseExtractor"]:
    """
    Get the appropriate extractor for a content type.

    Lazy imports to avoid loading unused dependencies.

    Args:
        content_type: The type of content to extract.

    Returns:
        Extractor instance or None if not available.
    """
    if content_type == ContentType.YOUTUBE:
        from .youtube import YouTubeExtractor
        return YouTubeExtractor()

    if content_type == ContentType.TIKTOK:
        # Phase 2 — not yet implemented
        return None

    if content_type == ContentType.WEB_ARTICLE:
        from .web import WebArticleExtractor
        return WebArticleExtractor()

    return None
