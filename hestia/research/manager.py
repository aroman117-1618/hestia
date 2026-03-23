"""
Research Manager — singleton orchestrating graph building and principle distillation.

Follows the standard Hestia manager pattern:
- Singleton via get_research_manager() / close_research_manager()
- Async initialize() for database and ChromaDB setup
- Combines GraphBuilder + PrincipleStore + ResearchDatabase
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from hestia.logging import LogComponent, get_logger

from .database import ResearchDatabase, get_research_database, close_research_database
from .entity_registry import EntityRegistry
from .fact_extractor import FactExtractor
from .graph_builder import GraphBuilder
from .models import GraphCluster, GraphEdge, GraphNode, GraphResponse, ImportSource, Principle, PrincipleStatus, SourceCategory
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
        self._entity_registry: Optional[EntityRegistry] = None
        self._fact_extractor: Optional[FactExtractor] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database, graph builder, and principle store."""
        if self._initialized:
            return

        self._database = await get_research_database()
        self._graph_builder = GraphBuilder()
        self._principle_store = PrincipleStore(self._database)
        self._entity_registry = EntityRegistry(self._database)
        self._fact_extractor = FactExtractor(self._database, self._entity_registry)

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
                nodes=[GraphNode.from_dict(n) for n in cached.get("nodes", [])],
                edges=[GraphEdge.from_dict(e) for e in cached.get("edges", [])],
                clusters=[GraphCluster.from_dict(c) for c in cached.get("clusters", [])],
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

    # ── Fact Operations ──────────────────────────────────

    async def extract_facts(self, time_range_days: int = 7) -> Dict[str, Any]:
        """Extract facts from recent memory chunks via LLM."""
        if not self._fact_extractor:
            return {"error": "not_initialized", "facts_created": 0}

        # Get recent memory chunks (same pattern as distill_principles)
        try:
            from hestia.memory import get_memory_manager
            memory_mgr = await get_memory_manager()
            results = await memory_mgr.search(query="*", limit=15, semantic_threshold=0.0)
        except Exception as e:
            logger.warning(
                f"Cannot search memory for fact extraction: {type(e).__name__}",
                component=LogComponent.RESEARCH,
            )
            return {
                "error": type(e).__name__,
                "facts_created": 0,
                "chunks_processed": 0,
                "entities_created": 0,
            }

        # Extract facts from each chunk
        total_facts = 0
        for result in results:
            chunk = result.chunk
            facts = await self._fact_extractor.extract_from_text(
                text=chunk.content,
                source_chunk_id=chunk.id,
            )
            total_facts += len(facts)

        # Invalidate graph cache
        if self._database:
            await self._database.invalidate_cache()

        entities_count = await self._database.count_entities() if self._database else 0

        return {
            "facts_created": total_facts,
            "chunks_processed": len(results),
            "entities_created": entities_count,
        }

    async def get_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List entities with optional type filter."""
        if not self._database:
            return {"entities": [], "total": 0}

        from .models import EntityType
        etype = EntityType(entity_type) if entity_type else None
        entities = await self._database.list_entities(entity_type=etype, limit=limit, offset=offset)
        total = await self._database.count_entities(entity_type=etype)

        return {
            "entities": [e.to_dict() for e in entities],
            "total": total,
        }

    async def set_entity_rejected(
        self, entity_id: str, rejected: bool
    ) -> Optional[Dict[str, Any]]:
        """Mark an entity as rejected or un-rejected."""
        if not self._database:
            return None
        entity = await self._database.set_entity_rejected(entity_id, rejected)
        return entity.to_dict() if entity else None

    async def get_facts(
        self,
        status: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List facts with optional filters."""
        if not self._database:
            return {"facts": [], "total": 0}

        from .models import FactStatus
        fstatus = FactStatus(status) if status else None
        facts = await self._database.list_facts(
            status=fstatus, source_entity_id=entity_id, limit=limit, offset=offset,
        )
        total = await self._database.count_facts(status=fstatus)

        return {
            "facts": [f.to_dict() for f in facts],
            "total": total,
        }

    async def get_timeline(
        self,
        point_in_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Get facts and entities valid at a point in time."""
        if not self._database:
            return {"facts": [], "entities": [], "point_in_time": None}

        from datetime import datetime as dt, timezone
        pit = point_in_time or dt.now(timezone.utc)

        facts = await self._database.get_facts_valid_at(pit)
        entities = await self._database.list_entities(limit=200)

        return {
            "facts": [f.to_dict() for f in facts],
            "entities": [e.to_dict() for e in entities],
            "point_in_time": pit.isoformat(),
        }

    async def get_fact_graph(
        self,
        center_entity: Optional[str] = None,
        point_in_time: Optional[datetime] = None,
        source_categories: Optional[List[SourceCategory]] = None,
    ) -> GraphResponse:
        """Get the fact-based knowledge graph, optionally filtered to a point in time or source."""
        if not self._graph_builder:
            return GraphResponse(nodes=[], edges=[], clusters=[], metadata={"error": "not_initialized"})

        return await self._graph_builder.build_fact_graph(
            center_entity=center_entity,
            point_in_time=point_in_time,
            source_categories=source_categories,
        )

    async def list_communities(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List entity communities."""
        if not self._database:
            return {"communities": [], "total": 0}

        communities = await self._database.list_communities(limit=limit, offset=offset)
        return {
            "communities": [c.to_dict() for c in communities],
            "total": len(communities),
        }

    async def detect_communities(self) -> Dict[str, Any]:
        """Run community detection on the entity-fact graph."""
        if not self._entity_registry:
            return {"communities": 0}

        communities = await self._entity_registry.detect_communities()

        # Invalidate graph cache
        if self._database:
            await self._database.invalidate_cache()

        return {
            "communities": len(communities),
            "details": [c.to_dict() for c in communities],
        }


    # ── Import Source Operations ──────────────────────────

    async def import_paste(
        self,
        text: str,
        provider: str = "paste",
        description: Optional[str] = None,
        source_category: SourceCategory = SourceCategory.IMPORTED,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """Import facts from pasted text.

        Creates an ImportSource record, extracts facts from the text,
        and links all created facts/entities to the import source.
        """
        if not self._database or not self._fact_extractor:
            return {"error": "not_initialized", "facts_created": 0}

        # Create import source record
        import_source = ImportSource.create(
            user_id=user_id,
            provider=provider,
            import_type="paste",
            description=description,
            source_category=source_category,
        )
        await self._database.create_import_source(import_source)

        # Count entities before extraction to compute delta
        entities_before = await self._database.count_entities()

        # Extract facts from the pasted text
        facts = await self._fact_extractor.extract_from_text(
            text=text,
            source_chunk_id=None,
            source_category=source_category,
            import_source_id=import_source.id,
        )

        # Count entities created during this import
        entities_after = await self._database.count_entities()
        entity_count = entities_after - entities_before

        # Update import source counts
        await self._database.update_import_source_counts(
            source_id=import_source.id,
            chunk_count=1,
            fact_count=len(facts),
            entity_count=entity_count,
        )

        # Invalidate graph cache
        await self._database.invalidate_cache()

        return {
            "import_source_id": import_source.id,
            "facts_created": len(facts),
            "entities_created": entity_count,
            "source_category": source_category.value,
        }

    async def list_import_sources(
        self,
        user_id: str = "default",
        provider: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List import source records."""
        if not self._database:
            return {"sources": [], "total": 0}

        sources = await self._database.list_import_sources(
            user_id=user_id, provider=provider, limit=limit, offset=offset,
        )
        return {
            "sources": [s.to_dict() for s in sources],
            "total": len(sources),
        }


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
