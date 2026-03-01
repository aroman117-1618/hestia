"""
Wiki manager for orchestrating wiki operations.

Coordinates article retrieval, static content loading,
AI generation, and staleness detection.
"""

import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

from .models import WikiArticle, ArticleType, GenerationStatus
from .database import WikiDatabase, get_wiki_database
from .scanner import WikiScanner
from .generator import WikiGenerator


class WikiManager:
    """
    Manages wiki article lifecycle.

    Handles static content parsing (decisions, roadmap),
    AI-generated content (overview, modules, diagrams),
    and staleness detection.
    """

    def __init__(
        self,
        database: Optional[WikiDatabase] = None,
        scanner: Optional[WikiScanner] = None,
        generator: Optional[WikiGenerator] = None,
    ):
        """
        Initialize wiki manager.

        Args:
            database: WikiDatabase instance. If None, uses singleton.
            scanner: WikiScanner instance.
            generator: WikiGenerator instance.
        """
        self._database = database
        self._scanner = scanner
        self._generator = generator
        self._config: Optional[Dict[str, Any]] = None
        self.logger = get_logger()

    async def initialize(self) -> None:
        """Initialize the wiki manager and its dependencies."""
        if self._database is None:
            self._database = await get_wiki_database()
        if self._scanner is None:
            self._scanner = WikiScanner()
        if self._generator is None:
            self._generator = WikiGenerator(scanner=self._scanner)

        self._config = self._load_config()

        self.logger.info(
            "Wiki manager initialized",
            component=LogComponent.WIKI,
        )

    async def close(self) -> None:
        """Close wiki manager resources."""
        self.logger.debug(
            "Wiki manager closed",
            component=LogComponent.WIKI,
        )

    @property
    def database(self) -> WikiDatabase:
        """Get database instance."""
        if self._database is None:
            raise RuntimeError("Wiki manager not initialized. Call initialize() first.")
        return self._database

    @property
    def scanner(self) -> WikiScanner:
        """Get scanner instance."""
        if self._scanner is None:
            raise RuntimeError("Wiki manager not initialized. Call initialize() first.")
        return self._scanner

    @property
    def generator(self) -> WikiGenerator:
        """Get generator instance."""
        if self._generator is None:
            raise RuntimeError("Wiki manager not initialized. Call initialize() first.")
        return self._generator

    @property
    def config(self) -> Dict[str, Any]:
        """Get wiki config."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    # =========================================================================
    # Article Retrieval
    # =========================================================================

    async def get_article(self, article_id: str) -> Optional[WikiArticle]:
        """Get a single article by ID."""
        return await self.database.get_article(article_id)

    async def list_articles(
        self,
        article_type: Optional[str] = None,
    ) -> List[WikiArticle]:
        """
        List articles, optionally filtered by type.

        Args:
            article_type: Filter string (e.g., "module", "decision").

        Returns:
            List of WikiArticle objects.
        """
        if article_type:
            try:
                atype = ArticleType(article_type)
            except ValueError:
                return []
            return await self.database.list_articles(atype)
        return await self.database.list_articles()

    # =========================================================================
    # Static Content Loading
    # =========================================================================

    async def refresh_static(self) -> Dict[str, int]:
        """
        Re-read static docs from disk and update database.

        Parses decision log and development plan into articles.

        Returns:
            Dict with counts: decisions, roadmap.
        """
        counts = {"decisions": 0, "roadmap": 0}

        # Parse decisions
        decisions = self.scanner.parse_decisions()
        for adr in decisions:
            article = WikiArticle.create(
                article_type=ArticleType.DECISION,
                title=f"{adr['number']}: {adr['title']}",
                subtitle=adr.get("status", "Accepted"),
                content=self._format_decision_content(adr),
                module_name=adr["number"].lower(),
                generation_status=GenerationStatus.STATIC,
            )
            await self.database.upsert_article(article)
            counts["decisions"] += 1

        # Parse roadmap
        roadmap = self.scanner.parse_roadmap()
        if roadmap.get("content"):
            article = WikiArticle.create(
                article_type=ArticleType.ROADMAP,
                title="Development Roadmap",
                subtitle="Completed milestones and what's next",
                content=roadmap["content"],
                generation_status=GenerationStatus.STATIC,
            )
            await self.database.upsert_article(article)
            counts["roadmap"] = 1

        self.logger.info(
            "Static wiki content refreshed",
            component=LogComponent.WIKI,
            data=counts,
        )

        return counts

    # =========================================================================
    # AI Content Generation
    # =========================================================================

    async def generate_article(
        self,
        article_type: str,
        module_name: Optional[str] = None,
    ) -> WikiArticle:
        """
        Generate a single article via cloud LLM.

        Args:
            article_type: "overview", "module", or "diagram".
            module_name: Required for module and diagram types.

        Returns:
            Generated WikiArticle (also cached in database).
        """
        atype = ArticleType(article_type)

        if atype == ArticleType.OVERVIEW:
            article = await self.generator.generate_overview()

        elif atype == ArticleType.MODULE:
            if not module_name:
                raise ValueError("module_name required for module articles")
            module_config = self.config.get("modules", {}).get(module_name, {})
            display_name = module_config.get("display_name", module_name.title())
            subtitle = module_config.get("subtitle", "")
            article = await self.generator.generate_module(module_name, display_name, subtitle)

        elif atype == ArticleType.DIAGRAM:
            if not module_name:
                raise ValueError("module_name (diagram type) required for diagram articles")
            article = await self.generator.generate_diagram(module_name)

        else:
            raise ValueError(f"Cannot generate {article_type} articles — use refresh_static()")

        # Cache in database
        await self.database.upsert_article(article)

        self.logger.info(
            f"Wiki article generated: {article.id}",
            component=LogComponent.WIKI,
            data={
                "article_type": article_type,
                "word_count": article.word_count,
                "status": article.generation_status.value,
            },
        )

        return article

    async def generate_all(self) -> Dict[str, Any]:
        """
        Generate all AI content (overview + all modules + diagrams).

        Returns:
            Summary with counts and any errors.
        """
        results: Dict[str, Any] = {
            "overview": None,
            "modules": {},
            "diagrams": {},
            "errors": [],
        }

        # Generate overview
        try:
            overview = await self.generate_article("overview")
            results["overview"] = overview.generation_status.value
        except Exception as e:
            results["errors"].append(f"overview: {type(e).__name__}")

        # Generate module deep dives
        modules_config = self.config.get("modules", {})
        for module_name in modules_config:
            try:
                article = await self.generate_article("module", module_name)
                results["modules"][module_name] = article.generation_status.value
            except Exception as e:
                results["errors"].append(f"module-{module_name}: {type(e).__name__}")

        # Generate diagrams
        diagrams_config = self.config.get("diagrams", [])
        for diagram in diagrams_config:
            dtype = diagram["type"]
            try:
                article = await self.generate_article("diagram", dtype)
                results["diagrams"][dtype] = article.generation_status.value
            except Exception as e:
                results["errors"].append(f"diagram-{dtype}: {type(e).__name__}")

        self.logger.info(
            "Full wiki generation complete",
            component=LogComponent.WIKI,
            data={
                "modules_generated": len(results["modules"]),
                "diagrams_generated": len(results["diagrams"]),
                "errors": len(results["errors"]),
            },
        )

        return results

    # =========================================================================
    # Staleness Detection
    # =========================================================================

    async def check_staleness(self) -> List[Dict[str, Any]]:
        """
        Check all generated articles for staleness.

        Returns:
            List of dicts with article_id and is_stale for each checked article.
        """
        articles = await self.database.get_stale_articles()
        results = []

        for article in articles:
            is_stale = self.scanner.check_staleness(article.id, article.source_hash)
            results.append({
                "article_id": article.id,
                "title": article.title,
                "is_stale": is_stale,
            })

        return results

    # =========================================================================
    # Selective Regeneration
    # =========================================================================

    async def regenerate_stale(
        self,
        trigger_source: str = "manual",
    ) -> Dict[str, Any]:
        """
        Selectively regenerate stale articles.

        Always refreshes static content (free), then checks each
        generated article for staleness and regenerates only those
        that have changed.

        Args:
            trigger_source: What triggered this (deploy, scheduled, manual).

        Returns:
            Summary dict with counts.
        """
        result: Dict[str, Any] = {
            "trigger_source": trigger_source,
            "regenerated": [],
            "skipped": [],
            "failed": [],
            "static": {},
            "total_checked": 0,
        }

        # 1. Always refresh static content (free, ~500ms)
        try:
            static_counts = await self.refresh_static()
            result["static"] = static_counts
        except Exception as e:
            self.logger.error(
                f"Static refresh failed during regenerate_stale: {type(e).__name__}",
                component=LogComponent.WIKI,
            )
            result["static"] = {"error": type(e).__name__}

        # 2. Check staleness of all generated articles
        staleness_results = await self.check_staleness()
        result["total_checked"] = len(staleness_results)

        # 3. Regenerate stale articles (individually try/excepted)
        for item in staleness_results:
            article_id = item["article_id"]

            if not item["is_stale"]:
                result["skipped"].append(article_id)
                continue

            try:
                # Determine article type and module from ID
                if article_id == "overview":
                    article_type = "overview"
                    module_name = None
                elif article_id.startswith("module-"):
                    article_type = "module"
                    module_name = article_id.replace("module-", "")
                elif article_id.startswith("diagram-"):
                    article_type = "diagram"
                    module_name = article_id.replace("diagram-", "")
                else:
                    result["skipped"].append(article_id)
                    continue

                # Get existing article to increment regeneration_count
                existing = await self.get_article(article_id)
                prev_count = existing.regeneration_count if existing else 0

                article = await self.generate_article(
                    article_type=article_type,
                    module_name=module_name,
                )

                # Update audit fields
                article.last_trigger_source = trigger_source
                article.regeneration_count = prev_count + 1
                await self.database.upsert_article(article)

                result["regenerated"].append(article_id)

                self.logger.info(
                    f"Regenerated stale article: {article_id}",
                    component=LogComponent.WIKI,
                    data={
                        "trigger": trigger_source,
                        "regeneration_count": article.regeneration_count,
                    },
                )

            except Exception as e:
                result["failed"].append(article_id)
                self.logger.error(
                    f"Failed to regenerate {article_id}: {type(e).__name__}",
                    component=LogComponent.WIKI,
                )

        self.logger.info(
            "Selective wiki regeneration complete",
            component=LogComponent.WIKI,
            data={
                "trigger": trigger_source,
                "regenerated": len(result["regenerated"]),
                "skipped": len(result["skipped"]),
                "failed": len(result["failed"]),
                "total_checked": result["total_checked"],
            },
        )

        return result

    # =========================================================================
    # Helpers
    # =========================================================================

    def _load_config(self) -> Dict[str, Any]:
        """Load wiki.yaml config."""
        config_path = Path(__file__).parent.parent / "config" / "wiki.yaml"
        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as e:
            self.logger.warning(
                f"Failed to load wiki config: {type(e).__name__}",
                component=LogComponent.WIKI,
            )
            return {}

    def _format_decision_content(self, adr: Dict[str, Any]) -> str:
        """Format an ADR dict into readable markdown content."""
        parts = []

        parts.append(f"**Date**: {adr.get('date', 'Unknown')}")
        parts.append(f"**Status**: {adr.get('status', 'Accepted')}")
        parts.append("")

        if adr.get("context"):
            parts.append("### Context")
            parts.append(adr["context"])
            parts.append("")

        if adr.get("decision"):
            parts.append("### Decision")
            parts.append(adr["decision"])
            parts.append("")

        if adr.get("alternatives"):
            parts.append("### Alternatives Considered")
            parts.append(adr["alternatives"])
            parts.append("")

        if adr.get("consequences"):
            parts.append("### Consequences")
            parts.append(adr["consequences"])
            parts.append("")

        if adr.get("notes"):
            parts.append("### Notes")
            parts.append(adr["notes"])

        return "\n".join(parts)


# Module-level singleton
_wiki_manager: Optional[WikiManager] = None


async def get_wiki_manager() -> WikiManager:
    """Get or create singleton wiki manager."""
    global _wiki_manager
    if _wiki_manager is None:
        _wiki_manager = WikiManager()
        await _wiki_manager.initialize()
    return _wiki_manager


async def close_wiki_manager() -> None:
    """Close the singleton wiki manager."""
    global _wiki_manager
    if _wiki_manager is not None:
        await _wiki_manager.close()
        _wiki_manager = None
