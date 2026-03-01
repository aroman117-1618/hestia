"""
YouTube transcript extractor using youtube-transcript-api.

Extracts video transcripts with language cascade:
English manual → any manual → auto-generated.
Uses asyncio.to_thread() since the library is synchronous.
"""

import asyncio
import re
from typing import Optional

from hestia.logging import get_logger, LogComponent

from ..models import ContentType, ExtractionResult
from .base import BaseExtractor

# Regex to extract video ID from various YouTube URL formats
_VIDEO_ID_PATTERNS = [
    re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})"),
]


def _extract_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from a URL."""
    for pattern in _VIDEO_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _fetch_transcript_sync(video_id: str) -> dict:
    """Synchronous transcript fetch — runs in thread pool."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return {"error": "youtube-transcript-api not installed. Run: pip install youtube-transcript-api"}

    try:
        # Try English manual first, then any manual, then auto-generated
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        transcript = None
        language = None

        # Priority 1: English manual transcript
        try:
            transcript = transcript_list.find_manually_created_transcript(["en"])
            language = "en (manual)"
        except Exception:
            pass

        # Priority 2: Any manual transcript (translated to English)
        if transcript is None:
            try:
                for t in transcript_list:
                    if not t.is_generated:
                        transcript = t
                        language = f"{t.language_code} (manual)"
                        break
            except Exception:
                pass

        # Priority 3: Auto-generated (any language)
        if transcript is None:
            try:
                for t in transcript_list:
                    if t.is_generated:
                        transcript = t
                        language = f"{t.language_code} (auto)"
                        break
            except Exception:
                pass

        if transcript is None:
            return {"error": "No transcript available for this video"}

        # Fetch the actual transcript entries
        entries = transcript.fetch()

        # Combine entries into full text
        text_parts = []
        for entry in entries:
            text_parts.append(entry.get("text", entry.text if hasattr(entry, "text") else str(entry)))

        full_text = " ".join(text_parts)

        return {
            "text": full_text,
            "language": language,
            "entry_count": len(entries),
            "video_id": video_id,
        }

    except Exception as e:
        error_type = type(e).__name__
        if "TranscriptsDisabled" in error_type:
            return {"error": "Transcripts are disabled for this video"}
        if "NoTranscriptFound" in error_type:
            return {"error": "No transcript found for this video"}
        if "VideoUnavailable" in error_type:
            return {"error": "Video is unavailable"}
        return {"error": f"Transcript fetch failed: {error_type}"}


def _fetch_video_title_sync(video_id: str) -> Optional[str]:
    """Best-effort title fetch from YouTube page HTML."""
    try:
        import re as _re
        from urllib.request import urlopen, Request

        url = f"https://www.youtube.com/watch?v={video_id}"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=10) as resp:
            # Read just the first 100KB to find the title tag
            html = resp.read(100_000).decode("utf-8", errors="ignore")
            match = _re.search(r"<title>(.*?)</title>", html)
            if match:
                title = match.group(1).strip()
                # YouTube titles end with " - YouTube"
                if title.endswith(" - YouTube"):
                    title = title[:-10].strip()
                return title if title else None
    except Exception:
        pass
    return None


class YouTubeExtractor(BaseExtractor):
    """Extracts transcripts from YouTube videos."""

    @property
    def content_type(self) -> ContentType:
        return ContentType.YOUTUBE

    async def extract(self, url: str) -> ExtractionResult:
        """Extract transcript from a YouTube video URL."""
        logger = get_logger()

        video_id = _extract_video_id(url)
        if not video_id:
            return ExtractionResult(
                content_type=ContentType.YOUTUBE,
                url=url,
                error="Could not extract video ID from URL",
            )

        logger.info(
            f"Extracting YouTube transcript: {video_id}",
            component=LogComponent.INVESTIGATE,
        )

        result = await asyncio.to_thread(_fetch_transcript_sync, video_id)

        if "error" in result and result["error"]:
            logger.warning(
                f"YouTube extraction failed for {video_id}: {result['error']}",
                component=LogComponent.INVESTIGATE,
            )
            return ExtractionResult(
                content_type=ContentType.YOUTUBE,
                url=url,
                error=result["error"],
            )

        # Best-effort title fetch (lightweight HTML scrape)
        title = await asyncio.to_thread(_fetch_video_title_sync, video_id)

        metadata = {
            "video_id": video_id,
            "language": result.get("language", "unknown"),
            "entry_count": result.get("entry_count", 0),
        }

        return ExtractionResult(
            content_type=ContentType.YOUTUBE,
            url=url,
            title=title,
            text=result.get("text", ""),
            metadata=metadata,
        )
