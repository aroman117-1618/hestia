"""
Investigation manager for orchestrating URL content analysis.

Coordinates the extract → analyze → store pipeline using the
extractor framework and InferenceClient for LLM analysis.
"""

import asyncio
import ipaddress
import re
import socket
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from hestia.logging import get_logger, LogComponent

from .models import (
    AnalysisDepth,
    ContentType,
    ExtractionResult,
    Investigation,
    InvestigationStatus,
    DEPTH_CONTENT_LIMITS,
    DEPTH_TOKEN_TARGETS,
)
from .database import InvestigateDatabase, get_investigate_database, close_investigate_database
from .extractors import classify_url, get_extractor


# Analysis system prompts by depth
_ANALYSIS_PROMPTS: Dict[AnalysisDepth, str] = {
    AnalysisDepth.QUICK: (
        "You are a research analyst. Provide a concise 2-3 paragraph summary of "
        "the following content. Focus on the main thesis, key facts, and conclusions. "
        "Be direct and factual."
    ),
    AnalysisDepth.STANDARD: (
        "You are a research analyst. Analyze the following content and provide:\n"
        "1. **Summary**: 2-3 paragraph overview of the main thesis and arguments\n"
        "2. **Key Points**: 5-8 bullet points of the most important facts/claims\n"
        "3. **Source Assessment**: Brief evaluation of the source's credibility and perspective\n"
        "4. **Notable Quotes**: 2-3 direct quotes that capture the core message\n\n"
        "Be thorough but concise. Distinguish facts from opinions."
    ),
    AnalysisDepth.DEEP: (
        "You are a senior research analyst. Perform a comprehensive analysis of the "
        "following content:\n"
        "1. **Summary**: Detailed overview of thesis, arguments, and conclusions\n"
        "2. **Key Points**: All significant facts, claims, and data points\n"
        "3. **Source Assessment**: Credibility evaluation — who wrote this, what's their angle?\n"
        "4. **Bias Detection**: Identify any framing, omissions, or loaded language\n"
        "5. **Missing Context**: What important context or counterarguments are absent?\n"
        "6. **Cross-Reference Suggestions**: What related topics should be investigated next?\n"
        "7. **Notable Quotes**: Key passages with brief commentary\n\n"
        "Be rigorous. Flag uncertainty. Distinguish established facts from claims."
    ),
}

# Allowed URL schemes
_ALLOWED_SCHEMES = {"http", "https"}

# Max extracted text stored in DB (chars) — prevents DB bloat
_MAX_STORED_TEXT_CHARS = 100_000


def _load_config() -> Dict[str, Any]:
    """Load investigate config from YAML."""
    config_path = Path(__file__).parent.parent / "config" / "investigate.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _is_dangerous_ip(ip_str: str) -> Optional[str]:
    """Check if an IP address is private, loopback, link-local, or otherwise dangerous."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return None  # Not an IP literal, will be resolved via DNS

    if addr.is_loopback:
        return "Cannot investigate localhost URLs"
    if addr.is_private:
        return "Cannot investigate private network URLs"
    if addr.is_link_local:
        return "Cannot investigate private network URLs"
    if addr.is_multicast:
        return "Cannot investigate multicast URLs"
    if addr.is_reserved:
        return "Cannot investigate reserved network URLs"
    # Explicit cloud metadata endpoint (link-local covers it, but belt-and-suspenders)
    if ip_str in ("169.254.169.254", "fd00::ec2"):
        return "Cannot investigate private network URLs"
    return None


async def _validate_url(url: str) -> Optional[str]:
    """
    Validate a URL for safety. Returns error message or None if valid.

    Checks scheme, hostname presence, and resolves DNS to block private/internal
    addresses. Uses ipaddress module to catch DNS rebinding, decimal IP encoding,
    IPv6-mapped IPv4, link-local, and multicast addresses.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return "Invalid URL format"

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return f"URL scheme must be http or https, got: {parsed.scheme or 'none'}"

    if not parsed.hostname:
        return "URL must have a hostname"

    hostname = parsed.hostname.lower()

    # Block "localhost" by name before DNS resolution
    if hostname == "localhost":
        return "Cannot investigate localhost URLs"

    # Check if hostname is an IP literal (v4 or v6)
    ip_error = _is_dangerous_ip(hostname)
    if ip_error:
        return ip_error

    # DNS resolution: resolve hostname and check ALL resolved IPs
    # Uses run_in_executor because socket.getaddrinfo is blocking
    try:
        loop = asyncio.get_event_loop()
        addrinfo = await loop.run_in_executor(
            None, socket.getaddrinfo, hostname, None
        )
        for family, _type, _proto, _canonname, sockaddr in addrinfo:
            resolved_ip = sockaddr[0]
            ip_error = _is_dangerous_ip(resolved_ip)
            if ip_error:
                return "Cannot investigate private network URLs"
    except socket.gaierror:
        return "Cannot resolve hostname"

    return None


def _extract_key_points(analysis_text: str) -> List[str]:
    """Extract key points from analysis text (simple heuristic)."""
    points = []
    in_key_points = False
    for line in analysis_text.split("\n"):
        stripped = line.strip()
        # Look for key points section header (must be a heading, not a bullet)
        if not in_key_points and not stripped.startswith(("- ", "* ", "• ")):
            lower = stripped.lower()
            if "key point" in lower or "key finding" in lower:
                in_key_points = True
                continue
        # Stop at next section header
        if in_key_points and stripped.startswith("**") and not stripped.startswith(("- ", "* ", "• ")):
            if ":" in stripped or stripped.endswith("**"):
                break
        # Capture numbered items (1., 2., etc.) and bullet points
        if in_key_points:
            if stripped.startswith(("- ", "* ", "• ")):
                point = stripped.lstrip("-*• ").strip()
                if point:
                    points.append(point)
            elif re.match(r"^\d+[\.\)]\s+", stripped):
                point = re.sub(r"^\d+[\.\)]\s+", "", stripped).strip()
                if point:
                    points.append(point)

    # Fallback: grab bullet points from anywhere
    if not points:
        for line in analysis_text.split("\n"):
            stripped = line.strip()
            if stripped.startswith(("- ", "* ", "• ")) and len(stripped) > 10:
                point = stripped.lstrip("-*• ").strip()
                if point:
                    points.append(point)
                if len(points) >= 8:
                    break

    return points


class InvestigateManager:
    """
    Orchestrates the URL investigation pipeline.

    URL → classify → extract → analyze (LLM) → store
    """

    def __init__(self, database: Optional[InvestigateDatabase] = None):
        """
        Initialize investigation manager.

        Args:
            database: InvestigateDatabase instance. If None, uses singleton.
        """
        self._database = database
        self._config = _load_config()
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the manager and its dependencies."""
        if self._database is None:
            self._database = await get_investigate_database()

        self.logger.info(
            "Investigate manager initialized",
            component=LogComponent.INVESTIGATE,
        )

    async def close(self) -> None:
        """Close manager resources including database."""
        await close_investigate_database()
        self.logger.debug(
            "Investigate manager closed",
            component=LogComponent.INVESTIGATE,
        )

    async def __aenter__(self) -> "InvestigateManager":
        await self.initialize()
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    @property
    def database(self) -> InvestigateDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("Investigate manager not initialized. Call initialize() first.")
        return self._database

    def _is_extractor_enabled(self, content_type: ContentType) -> bool:
        """Check if an extractor is enabled in config.

        Returns True for unknown types (they'll fail at extractor dispatch instead).
        """
        extractors_config = self._config.get("extractors", {})
        type_key = {
            ContentType.WEB_ARTICLE: "web",
            ContentType.YOUTUBE: "youtube",
            ContentType.TIKTOK: "tiktok",
            ContentType.AUDIO: "audio",
            ContentType.VIDEO: "video",
        }.get(content_type)
        if type_key is None:
            # Unknown types pass through — they'll fail at extractor dispatch
            return True
        return extractors_config.get(type_key, {}).get("enabled", True)

    def _get_content_limit(self, depth: AnalysisDepth) -> int:
        """Get content character limit from config, falling back to defaults."""
        config_limits = self._config.get("analysis", {}).get("content_limits", {})
        config_val = config_limits.get(depth.value)
        if config_val is not None:
            return int(config_val)
        return DEPTH_CONTENT_LIMITS.get(depth, 32_000)

    def _get_token_target(self, depth: AnalysisDepth) -> int:
        """Get token target from config, falling back to defaults."""
        config_targets = self._config.get("analysis", {}).get("token_targets", {})
        config_val = config_targets.get(depth.value)
        if config_val is not None:
            return int(config_val)
        return DEPTH_TOKEN_TARGETS.get(depth, 2_000)

    # =========================================================================
    # Core Pipeline
    # =========================================================================

    async def investigate(
        self,
        url: str,
        depth: str = "standard",
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Investigate a URL: extract content, analyze with LLM, store result.

        Args:
            url: URL to investigate.
            depth: Analysis depth (quick/standard/deep).
            user_id: User ID for scoping.

        Returns:
            Investigation result as dict.
        """
        # Validate URL (async — resolves DNS to prevent SSRF)
        url_error = await _validate_url(url)
        if url_error:
            return {
                "id": "",
                "url": url,
                "content_type": "unknown",
                "depth": depth,
                "status": "failed",
                "title": None,
                "source_author": None,
                "source_date": None,
                "analysis": "",
                "key_points": [],
                "model_used": None,
                "tokens_used": 0,
                "word_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": url_error,
            }

        # Parse depth
        try:
            analysis_depth = AnalysisDepth(depth)
        except ValueError:
            analysis_depth = AnalysisDepth.STANDARD

        # Classify URL
        content_type = classify_url(url)

        # Check if extractor is enabled in config
        if not self._is_extractor_enabled(content_type):
            return {
                "id": "",
                "url": url,
                "content_type": content_type.value,
                "depth": depth,
                "status": "failed",
                "title": None,
                "source_author": None,
                "source_date": None,
                "analysis": "",
                "key_points": [],
                "model_used": None,
                "tokens_used": 0,
                "word_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "error": f"Extractor for {content_type.value} is disabled in config",
            }

        # Check for recent duplicate
        existing = await self.database.find_by_url(url, user_id)
        if existing:
            # If investigated within last 6 hours, return cached
            age_hours = (datetime.now(timezone.utc) - existing.created_at).total_seconds() / 3600
            if age_hours < 6:
                self.logger.info(
                    f"Returning cached investigation for {url} (age={age_hours:.1f}h)",
                    component=LogComponent.INVESTIGATE,
                )
                return existing.to_dict()

        # Create investigation record
        investigation = Investigation.create(
            url=url,
            user_id=user_id,
            content_type=content_type,
            depth=analysis_depth,
        )

        self.logger.info(
            f"Starting investigation: {url} (type={content_type.value}, depth={depth})",
            component=LogComponent.INVESTIGATE,
            data={"investigation_id": investigation.id},
        )

        try:
            # Step 1: Extract
            investigation.status = InvestigationStatus.EXTRACTING
            extraction = await self._extract(url, content_type)

            if not extraction.success:
                investigation.status = InvestigationStatus.FAILED
                investigation.error = extraction.error or "Extraction produced no content"
                investigation.completed_at = datetime.now(timezone.utc)
                await self.database.store(investigation)
                return investigation.to_dict()

            # Populate extraction data (truncate stored text to prevent DB bloat)
            investigation.title = extraction.title
            investigation.source_author = extraction.author
            investigation.source_date = extraction.date
            investigation.extracted_text = extraction.text[:_MAX_STORED_TEXT_CHARS]
            investigation.extraction_metadata = extraction.metadata

            # Step 2: Analyze with LLM
            investigation.status = InvestigationStatus.ANALYZING
            analysis_result = await self._analyze(extraction, analysis_depth)

            investigation.analysis = analysis_result.get("analysis", "")
            investigation.key_points = analysis_result.get("key_points", [])
            investigation.model_used = analysis_result.get("model")
            investigation.tokens_used = analysis_result.get("tokens_used", 0)

            # Step 3: Mark complete
            investigation.status = InvestigationStatus.COMPLETE
            investigation.completed_at = datetime.now(timezone.utc)

        except Exception as e:
            investigation.status = InvestigationStatus.FAILED
            investigation.error = f"Investigation failed: {type(e).__name__}"
            investigation.completed_at = datetime.now(timezone.utc)

            self.logger.error(
                f"Investigation failed for {url}: {type(e).__name__}",
                component=LogComponent.INVESTIGATE,
            )

        # Store result
        await self.database.store(investigation)

        self.logger.info(
            f"Investigation complete: {investigation.id} (status={investigation.status.value})",
            component=LogComponent.INVESTIGATE,
        )

        return investigation.to_dict()

    async def compare(
        self,
        urls: List[str],
        focus: Optional[str] = None,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Compare content from multiple URLs.

        Args:
            urls: List of 2-5 URLs to compare.
            focus: Optional focus area for comparison.
            user_id: User ID for scoping.

        Returns:
            Comparison result with individual analyses and synthesis.
        """
        if len(urls) < 2:
            return {"error": "At least 2 URLs required for comparison"}
        if len(urls) > 5:
            return {"error": "Maximum 5 URLs for comparison"}

        # Investigate all URLs concurrently
        tasks = [
            self.investigate(url, depth="standard", user_id=user_id)
            for url in urls
        ]
        investigations = await asyncio.gather(*tasks)

        # Build comparison prompt
        successful = [inv for inv in investigations if inv.get("status") == "complete"]
        if len(successful) < 2:
            return {
                "error": "Need at least 2 successful extractions to compare",
                "investigations": list(investigations),
            }

        comparison_analysis = await self._compare_analyses(successful, focus)

        return {
            "investigations": list(investigations),
            "comparison": comparison_analysis,
            "urls_compared": len(successful),
            "urls_failed": len(investigations) - len(successful),
        }

    # =========================================================================
    # Retrieval
    # =========================================================================

    async def get_investigation(
        self, investigation_id: str, user_id: str = "default"
    ) -> Optional[Dict[str, Any]]:
        """Get a single investigation by ID."""
        inv = await self.database.get(investigation_id, user_id)
        return inv.to_dict() if inv else None

    async def list_investigations(
        self,
        user_id: str = "default",
        content_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List investigation history."""
        investigations = await self.database.list_history(
            user_id=user_id,
            content_type=content_type,
            status=status,
            limit=limit,
            offset=offset,
        )
        total = await self.database.count(user_id)
        return {
            "investigations": [inv.to_dict() for inv in investigations],
            "count": len(investigations),
            "total": total,
        }

    async def delete_investigation(
        self, investigation_id: str, user_id: str = "default"
    ) -> bool:
        """Delete an investigation."""
        return await self.database.delete(investigation_id, user_id)

    # =========================================================================
    # Internal Pipeline Steps
    # =========================================================================

    async def _extract(self, url: str, content_type: ContentType) -> ExtractionResult:
        """Run the appropriate extractor for the content type."""
        extractor = get_extractor(content_type)

        if extractor is None:
            return ExtractionResult(
                content_type=content_type,
                url=url,
                error=f"No extractor available for content type: {content_type.value}",
            )

        return await extractor.extract(url)

    async def _analyze(
        self, extraction: ExtractionResult, depth: AnalysisDepth
    ) -> Dict[str, Any]:
        """Analyze extracted content using InferenceClient."""
        from hestia.inference.client import get_inference_client

        client = get_inference_client()

        system_prompt = _ANALYSIS_PROMPTS.get(depth, _ANALYSIS_PROMPTS[AnalysisDepth.STANDARD])

        # Use config-driven content limit for truncation
        content_limit = self._get_content_limit(depth)
        truncated_text = extraction.text[:content_limit]
        if len(extraction.text) > content_limit:
            truncated_text += "\n\n[Content truncated...]"

        max_tokens = self._get_token_target(depth)

        # Build the user prompt with metadata context
        user_prompt_parts = []
        if extraction.title:
            user_prompt_parts.append(f"Title: {extraction.title}")
        if extraction.author:
            user_prompt_parts.append(f"Author: {extraction.author}")
        if extraction.date:
            user_prompt_parts.append(f"Date: {extraction.date}")
        user_prompt_parts.append(f"Source: {extraction.url}")
        user_prompt_parts.append(f"Content Type: {extraction.content_type.value}")
        user_prompt_parts.append(f"\n---\n\n{truncated_text}")

        user_prompt = "\n".join(user_prompt_parts)

        try:
            response = await client.complete(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=max_tokens,
            )

            analysis_text = response.content
            key_points = _extract_key_points(analysis_text)

            return {
                "analysis": analysis_text,
                "key_points": key_points,
                "model": response.model,
                "tokens_used": response.tokens_in + response.tokens_out,
            }

        except Exception as e:
            self.logger.warning(
                f"LLM analysis failed: {type(e).__name__}",
                component=LogComponent.INVESTIGATE,
            )
            return {
                "analysis": f"Analysis unavailable: {type(e).__name__}",
                "key_points": [],
                "model": None,
                "tokens_used": 0,
            }

    async def _compare_analyses(
        self,
        investigations: List[Dict[str, Any]],
        focus: Optional[str] = None,
    ) -> str:
        """Generate a comparison analysis across multiple investigations."""
        from hestia.inference.client import get_inference_client

        client = get_inference_client()

        system_prompt = (
            "You are a research analyst. Compare and synthesize the following "
            "content analyses. Identify:\n"
            "1. **Points of Agreement**: Where sources align\n"
            "2. **Points of Disagreement**: Where sources diverge and why\n"
            "3. **Unique Contributions**: What each source adds that others miss\n"
            "4. **Overall Assessment**: Synthesized understanding from all sources\n\n"
            "Be specific. Reference sources by their title or URL."
        )

        if focus:
            system_prompt += f"\n\nFocus your comparison on: {focus}"

        # Build comparison prompt
        parts = []
        for i, inv in enumerate(investigations, 1):
            title = inv.get("title") or inv.get("url", "Unknown")
            analysis = inv.get("analysis", "No analysis available")
            parts.append(f"### Source {i}: {title}\n{analysis}\n")

        user_prompt = "\n".join(parts)

        try:
            response = await client.complete(
                prompt=user_prompt,
                system=system_prompt,
                max_tokens=3_000,
            )
            return response.content
        except Exception as e:
            self.logger.warning(
                f"Comparison analysis failed: {type(e).__name__}",
                component=LogComponent.INVESTIGATE,
            )
            return f"Comparison unavailable: {type(e).__name__}"


# Module-level singleton
_investigate_manager: Optional[InvestigateManager] = None


async def get_investigate_manager() -> InvestigateManager:
    """Get or create singleton investigation manager."""
    global _investigate_manager
    if _investigate_manager is None:
        _investigate_manager = InvestigateManager()
        await _investigate_manager.initialize()
    return _investigate_manager


async def close_investigate_manager() -> None:
    """Close the singleton investigation manager."""
    global _investigate_manager
    if _investigate_manager is not None:
        await _investigate_manager.close()
        _investigate_manager = None
