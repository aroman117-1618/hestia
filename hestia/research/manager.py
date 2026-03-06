"""
Research Manager — singleton orchestrating graph building and principle distillation.

Follows the standard Hestia manager pattern:
- Singleton via get_research_manager() / close_research_manager()
- Async initialize() for database and ChromaDB setup
- Combines GraphBuilder + PrincipleStore + ResearchDatabase
"""

from typing import Any, Dict, List, Optional, Set

from hestia.logging import LogComponent, get_logger

from .database import ResearchDatabase, get_research_database, close_research_database
from .graph_builder import GraphBuilder
from .models import GraphResponse, Principle, PrincipleStatus
from .principle_store import PrincipleStore

logger = get_logger()

_instance: Optional["ResearchManager"] = None


class ResearchManager:
    """
    Orchestrates research operations: graph building and principle distillation.

    Thread-safe for async (single event loop). Uses singleton pattern.
    """

    def __init__(self) -> None:
        self._database: Optional[ResearchDatabase] = None
        self._graph_builder: Optional[GraphBuilder] = None
        self._principle_store: Optional[PrincipleStore] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database, graph builder, and principle store."""
        if self._initialized:
            return

        self._database = await get_research_database()
        self._graph_builder = GraphBuilder()
        self._principle_store = PrincipleStore(self._database)

        # Initialize ChromaDB collection for principles (async-safe)
        try:
            await self._principle_store.ensure_initialized()
        except Exception as e:
            logger.warning(
                f"PrincipleStore ChromaDB init failed: {type(e).__name__}",
                component=LogComponent.RESEARCH,
            )

        self._initialized = True
        logger.info(
            "ResearchManager initialized",
            component=LogComponent.RESEARCH,
        )

    async def close(self) -> None:
        """Clean up resources."""
        self._initialized = False
        # Database closed via close_research_database() in server shutdown

    # ── Graph Operations ────────────────────────────────

    async def get_graph(
        self,
        limit: int = 200,
        node_types: Optional[Set[str]] = None,
        center_topic: Optional[str] = None,
        sources: Optional[list] = None,
    ) -> GraphResponse:
        """
        Get the knowledge graph, using cache if available.

        Args:
            limit: Max memory chunks to query.
            node_types: Filter to specific node types.
            center_topic: Focus on nodes related to this topic.
            sources: Filter by MemorySource values (e.g., ["conversation", "mail"]).

        Returns:
            GraphResponse with nodes, edges, clusters.
        """
        if not self._graph_builder or not self._database:
            return GraphResponse(nodes=[], edges=[], clusters=[], metadata={"error": "not_initialized"})

        # Build cache key from parameters
        type_key = ",".join(sorted(node_types)) if node_types else "all"
        source_key = ",".join(sorted(sources)) if sources else "all"
        cache_key = f"graph:{limit}:{type_key}:{center_topic or 'none'}:{source_key}"

        # Check cache
        cached = await self._database.get_cached_graph(cache_key)
        if cached:
            return GraphResponse(
                nodes=[],  # Cached response is already serialized
                edges=[],
                clusters=[],
                metadata={"cached": True, **cached.get("metadata", {})},
            )

        # Build fresh graph
        response = await self._graph_builder.build_graph(
            limit=limit,
            node_types=node_types,
            center_topic=center_topic,
            sources=sources,
        )

        # Cache the result
        await self._database.set_cached_graph(cache_key, response.to_dict(), ttl_seconds=300)

        return response

    # ── Principle Operations ────────────────────────────

    async def distill_principles(
        self, time_range_days: int = 7
    ) -> Dict[str, Any]:
        """
        Trigger principle distillation from recent memory.

        Args:
            time_range_days: How many days of memory to analyze.

        Returns:
            Dict with extraction stats.
        """
        if not self._principle_store:
            return {"error": "not_initialized", "principles_extracted": 0}

        # Get recent memory chunks
        try:
            from hestia.memory import get_memory_manager
            memory_mgr = await get_memory_manager()
            results = await memory_mgr.search(
                query="*",
                limit=50,
                semantic_threshold=0.0,
            )
        except Exception as e:
            logger.warning(
                f"Cannot search memory for distillation: {type(e).__name__}",
                component=LogComponent.RESEARCH,
            )
            return {"error": type(e).__name__, "principles_extracted": 0}

        # Distill
        principles = await self._principle_store.distill_principles(results)

        # Invalidate graph cache (new principles may affect graph)
        if self._database:
            await self._database.invalidate_cache()

        return {
            "principles_extracted": len(principles),
            "new": len(principles),
            "input_chunks": len(results),
        }

    async def list_principles(
        self,
        status: Optional[PrincipleStatus] = None,
        domain: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List principles with optional filters."""
        if not self._database:
            return {"principles": [], "total": 0}

        principles = await self._database.list_principles(
            status=status, domain=domain, limit=limit, offset=offset,
        )
        total = await self._database.count_principles(status=status)

        return {
            "principles": [p.to_dict() for p in principles],
            "total": total,
        }

    async def approve_principle(self, principle_id: str) -> Optional[Dict[str, Any]]:
        """Approve a pending principle."""
        if not self._database:
            return None
        p = await self._database.update_principle_status(principle_id, PrincipleStatus.APPROVED)
        return p.to_dict() if p else None

    async def reject_principle(self, principle_id: str) -> Optional[Dict[str, Any]]:
        """Reject a pending principle."""
        if not self._database:
            return None
        p = await self._database.update_principle_status(principle_id, PrincipleStatus.REJECTED)
        return p.to_dict() if p else None

    async def update_principle(self, principle_id: str, content: str) -> Optional[Dict[str, Any]]:
        """Update a principle's content."""
        if not self._database:
            return None
        p = await self._database.update_principle_content(principle_id, content)
        return p.to_dict() if p else None


async def get_research_manager() -> ResearchManager:
    """Get or create the singleton ResearchManager instance."""
    global _instance
    if _instance is None:
        _instance = ResearchManager()
        await _instance.initialize()
    return _instance


async def close_research_manager() -> None:
    """Close the singleton ResearchManager."""
    global _instance
    if _instance:
        await _instance.close()
        _instance = None
    await close_research_database()
