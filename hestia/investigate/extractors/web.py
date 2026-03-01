"""
Web article extractor using trafilatura.

Extracts article text, title, author, and date from web pages.
Uses asyncio.to_thread() since trafilatura is synchronous.
"""

import asyncio
import json

from hestia.logging import get_logger, LogComponent

from ..models import ContentType, ExtractionResult
from .base import BaseExtractor


def _extract_sync(url: str) -> dict:
    """Synchronous extraction — runs in thread pool."""
    try:
        import trafilatura
    except ImportError:
        return {"error": "trafilatura not installed. Run: pip install trafilatura"}

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"error": f"Failed to download: {url}"}

        # Single extraction call with JSON output — includes both text and metadata
        json_result = trafilatura.extract(
            downloaded,
            output_format="json",
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )

        if not json_result:
            return {"error": "Extraction produced no content"}

        try:
            meta_dict = json.loads(json_result)
        except (json.JSONDecodeError, ValueError):
            return {"error": "Failed to parse extraction result"}

        return {
            "text": meta_dict.get("text", ""),
            "title": meta_dict.get("title"),
            "author": meta_dict.get("author"),
            "date": meta_dict.get("date"),
            "hostname": meta_dict.get("hostname"),
            "sitename": meta_dict.get("sitename"),
        }

    except Exception as e:
        return {"error": f"Extraction failed: {type(e).__name__}"}


class WebArticleExtractor(BaseExtractor):
    """Extracts article content from web pages using trafilatura."""

    @property
    def content_type(self) -> ContentType:
        return ContentType.WEB_ARTICLE

    async def extract(self, url: str) -> ExtractionResult:
        """Extract article content from a web URL."""
        logger = get_logger()
        logger.info(
            f"Extracting web article: {url}",
            component=LogComponent.INVESTIGATE,
        )

        result = await asyncio.to_thread(_extract_sync, url)

        if "error" in result and result["error"]:
            logger.warning(
                f"Web extraction failed for {url}: {result['error']}",
                component=LogComponent.INVESTIGATE,
            )
            return ExtractionResult(
                content_type=ContentType.WEB_ARTICLE,
                url=url,
                error=result["error"],
            )

        metadata = {}
        if result.get("hostname"):
            metadata["hostname"] = result["hostname"]
        if result.get("sitename"):
            metadata["sitename"] = result["sitename"]

        return ExtractionResult(
            content_type=ContentType.WEB_ARTICLE,
            url=url,
            title=result.get("title"),
            author=result.get("author"),
            date=result.get("date"),
            text=result.get("text", ""),
            metadata=metadata,
        )
