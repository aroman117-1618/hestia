"""
Research API routes.

Endpoints for the knowledge graph, fact extraction, entity management,
community detection, and principle distillation.
Part of the Learning Cycle (Phase A).
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_device_token
from hestia.api.schemas.research import (
    AddReferenceRequest,
    BoardListResponse,
    BoardResponse,
    CommunityListResponse,
    CreateBoardRequest,
    DistillFromSelectionRequest,
    DistillFromSelectionResponse,
    DistillRequest,
    DistillResponse,
    EntityListResponse,
    EntityReferenceListResponse,
    EntityReferenceResponse,
    ExtractFactsRequest,
    ExtractFactsResponse,
    FactListResponse,
    GraphResponse,
    ImportPasteRequest,
    ImportPasteResponse,
    ImportSourceListResponse,
    PrincipleListResponse,
    PrincipleResponse,
    PrincipleUpdateRequest,
    TimelineResponse,
    UpdateBoardRequest,
)
from hestia.logging import LogComponent, get_logger
from hestia.research.boards import ResearchBoard
from hestia.research.manager import get_research_manager
from hestia.research.models import Principle, PrincipleStatus, SourceCategory
from hestia.research.references import EntityReference, ReferenceModule

router = APIRouter(prefix="/v1/research", tags=["research"])
logger = get_logger()


# =============================================================================
# Graph Endpoint
# =============================================================================


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    limit: int = Query(default=200, ge=1, le=500),
    node_types: Optional[str] = Query(default=None, description="Comma-separated: memory,topic,entity,principle,fact,community,episode"),
    center_topic: Optional[str] = Query(default=None, description="Focus graph on this topic"),
    sources: Optional[str] = Query(default=None, description="Comma-separated MemorySource values: conversation,mail,calendar,reminders,notes,health"),
    mode: str = Query(default="legacy", description="Graph mode: 'legacy' (co-occurrence) or 'facts' (entity-fact)"),
    center_entity: Optional[str] = Query(default=None, description="Center entity for mode=facts"),
    point_in_time: Optional[str] = Query(default=None, description="ISO datetime for bi-temporal fact filtering (mode=facts only)"),
    source_categories: Optional[str] = Query(default=None, description="Comma-separated SourceCategory values for mode=facts: conversation,imported,web,tool,user_statement,apple_ecosystem,health,voice"),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get the knowledge graph with nodes, edges, and clusters."""
    try:
        manager = await get_research_manager()

        # Parse optional point-in-time for bi-temporal filtering
        pit: Optional[datetime] = None
        if point_in_time:
            try:
                pit = datetime.fromisoformat(point_in_time)
                if pit.tzinfo is None:
                    pit = pit.replace(tzinfo=timezone.utc)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid point_in_time format. Use ISO 8601.",
                )

        if mode == "facts":
            # Resolve center_entity name to entity ID for BFS filtering
            resolved_center = center_entity
            if center_entity and manager._database:
                entity = await manager._database.find_entity_by_name_like(center_entity)
                if entity:
                    resolved_center = entity.id
                else:
                    logger.warning(
                        "Center entity not found by name, passing as-is",
                        component=LogComponent.RESEARCH,
                        data={"center_entity": center_entity},
                    )

            # Parse source_categories filter
            sc_list: Optional[List[SourceCategory]] = None
            if source_categories:
                try:
                    sc_list = [SourceCategory(s.strip()) for s in source_categories.split(",") if s.strip()]
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid source_categories. Use: {', '.join(sc.value for sc in SourceCategory)}",
                    )

            response = await manager.get_fact_graph(
                center_entity=resolved_center,
                point_in_time=pit,
                source_categories=sc_list,
            )
            return response.to_dict()

        types_set: Optional[Set[str]] = None
        if node_types:
            types_set = set(t.strip() for t in node_types.split(","))

        sources_list: Optional[list] = None
        if sources:
            sources_list = [s.strip() for s in sources.split(",") if s.strip()]

        response = await manager.get_graph(
            limit=limit,
            node_types=types_set,
            center_topic=center_topic,
            sources=sources_list,
        )
        return response.to_dict()

    except Exception as e:
        logger.error(
            "Graph endpoint error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build graph",
        )


# =============================================================================
# Fact Endpoints
# =============================================================================


@router.post("/facts/extract", response_model=ExtractFactsResponse)
async def extract_facts(
    request: ExtractFactsRequest = ExtractFactsRequest(),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Trigger fact extraction from recent memory."""
    try:
        manager = await get_research_manager()
        result = await manager.extract_facts(
            time_range_days=request.time_range_days,
        )
        return result

    except Exception as e:
        logger.error(
            "Fact extraction endpoint error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fact extraction failed",
        )


@router.get("/facts", response_model=FactListResponse)
async def list_facts(
    status_filter: Optional[str] = Query(default=None, alias="status", description="active, expired, or contradicted"),
    entity_id: Optional[str] = Query(default=None, description="Filter by source entity ID"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List knowledge graph facts."""
    try:
        manager = await get_research_manager()
        result = await manager.get_facts(
            status=status_filter,
            entity_id=entity_id,
            limit=limit,
            offset=offset,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "List facts error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list facts",
        )


@router.get("/facts/timeline", response_model=TimelineResponse)
async def get_timeline(
    point_in_time: Optional[str] = Query(default=None, description="ISO 8601 datetime"),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get facts valid at a specific point in time."""
    try:
        manager = await get_research_manager()

        pit = datetime.fromisoformat(point_in_time) if point_in_time else None

        result = await manager.get_timeline(point_in_time=pit)
        return result

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid datetime format. Use ISO 8601.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Timeline endpoint error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get timeline",
        )


# =============================================================================
# Entity Endpoints
# =============================================================================


@router.get("/entities", response_model=EntityListResponse)
async def list_entities(
    entity_type: Optional[str] = Query(default=None, description="Filter by entity type"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List knowledge graph entities."""
    try:
        manager = await get_research_manager()
        result = await manager.get_entities(
            entity_type=entity_type,
            limit=limit,
            offset=offset,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "List entities error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list entities",
        )


@router.post("/entities/{entity_id}/reject")
async def reject_entity(
    entity_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Reject an entity — marks it as low-quality for extraction feedback."""
    try:
        manager = await get_research_manager()
        entity = await manager.set_entity_rejected(entity_id, rejected=True)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return entity
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Reject entity error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to reject entity")


@router.post("/entities/{entity_id}/unreject")
async def unreject_entity(
    entity_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Un-reject an entity."""
    try:
        manager = await get_research_manager()
        entity = await manager.set_entity_rejected(entity_id, rejected=False)
        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")
        return entity
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Unreject entity error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to unreject entity")


# =============================================================================
# Community Endpoints
# =============================================================================


@router.post("/entities/communities")
async def detect_communities(
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Run community detection on entity-fact graph."""
    try:
        manager = await get_research_manager()
        result = await manager.detect_communities()
        return result

    except Exception as e:
        logger.error(
            "Community detection error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Community detection failed",
        )


@router.get("/communities", response_model=CommunityListResponse)
async def list_communities(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List entity communities."""
    try:
        manager = await get_research_manager()
        return await manager.list_communities(limit=limit, offset=offset)

    except Exception as e:
        logger.error(
            "List communities error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list communities",
        )


# =============================================================================
# Principle Endpoints
# =============================================================================


@router.post("/principles/distill", response_model=DistillResponse)
async def distill_principles(
    request: DistillRequest = DistillRequest(),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Trigger principle distillation from recent memory chunks."""
    try:
        manager = await get_research_manager()
        result = await manager.distill_principles(
            time_range_days=request.time_range_days,
        )
        return result

    except Exception as e:
        logger.error(
            "Distillation endpoint error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Principle distillation failed",
        )


@router.get("/principles", response_model=PrincipleListResponse)
async def list_principles(
    status_filter: Optional[str] = Query(default=None, alias="status", description="pending, approved, or rejected"),
    domain: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List principles with optional status and domain filters."""
    try:
        manager = await get_research_manager()

        principle_status = None
        if status_filter:
            try:
                principle_status = PrincipleStatus(status_filter)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. Use pending, approved, or rejected.",
                )

        result = await manager.list_principles(
            status=principle_status,
            domain=domain,
            limit=limit,
            offset=offset,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "List principles error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list principles",
        )


@router.post("/principles/{principle_id}/approve", response_model=PrincipleResponse)
async def approve_principle(
    principle_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Approve a pending principle (makes it active for downstream systems)."""
    try:
        manager = await get_research_manager()
        result = await manager.approve_principle(principle_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Principle not found",
            )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Approve principle error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "principle_id": principle_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve principle",
        )


@router.post("/principles/{principle_id}/reject", response_model=PrincipleResponse)
async def reject_principle(
    principle_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Reject a pending principle."""
    try:
        manager = await get_research_manager()
        result = await manager.reject_principle(principle_id)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Principle not found",
            )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Reject principle error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "principle_id": principle_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject principle",
        )


@router.put("/principles/{principle_id}", response_model=PrincipleResponse)
async def update_principle(
    principle_id: str,
    request: PrincipleUpdateRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Update a principle's content."""
    try:
        manager = await get_research_manager()
        result = await manager.update_principle(principle_id, request.content)
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Principle not found",
            )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Update principle error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "principle_id": principle_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update principle",
        )


# =============================================================================
# Entity Search + Fact Invalidation + Temporal Queries (Sprint 13 WS1)
# =============================================================================


@router.get("/entities/search")
async def search_entities(
    q: str = Query(..., min_length=1, description="Entity name to search"),
    limit: int = Query(default=20, ge=1, le=100),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Search entities by name (fuzzy match via canonical name)."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            return {"entities": [], "count": 0}

        entities = await manager._database.search_entities_by_name(q, limit=limit)

        return {
            "entities": [e.to_dict() for e in entities],
            "count": len(entities),
            "query": q,
        }

    except Exception as e:
        logger.error(
            "Entity search error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "query": q},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Entity search failed",
        )


@router.post("/facts/{fact_id}/invalidate")
async def invalidate_fact(
    fact_id: str,
    reason: Optional[str] = Query(default=None),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Mark a fact as invalidated (set invalid_at to now)."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(status_code=503, detail="Database not available")

        now = datetime.now(timezone.utc).isoformat()
        await manager._database._connection.execute(
            "UPDATE facts SET invalid_at = ?, status = 'superseded' WHERE id = ?",
            (now, fact_id),
        )
        await manager._database._connection.commit()

        # Invalidate graph cache
        await manager._database.invalidate_cache()

        return {
            "fact_id": fact_id,
            "status": "invalidated",
            "invalid_at": now,
            "reason": reason,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Fact invalidation error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "fact_id": fact_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Fact invalidation failed",
        )


@router.get("/facts/at-time")
async def get_facts_at_time(
    point_in_time: str = Query(..., description="ISO datetime for temporal query"),
    subject: Optional[str] = Query(default=None, description="Filter by entity name"),
    limit: int = Query(default=100, ge=1, le=500),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get facts that were valid at a specific point in time."""
    try:
        pit = datetime.fromisoformat(point_in_time.replace("Z", "+00:00"))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid datetime format. Use ISO 8601.",
        )

    try:
        manager = await get_research_manager()
        if not manager._database:
            return {"facts": [], "count": 0}

        facts = await manager._database.get_facts_at_time(
            point_in_time=pit,
            subject=subject,
            limit=limit,
        )

        return {
            "facts": [f.to_dict() for f in facts],
            "count": len(facts),
            "point_in_time": pit.isoformat(),
            "subject": subject,
        }

    except Exception as e:
        logger.error(
            "Temporal fact query error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Temporal fact query failed",
        )


@router.get("/episodes")
async def list_episodic_nodes(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List episodic memory nodes (conversation summaries in the knowledge graph)."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            return {"episodes": [], "count": 0}

        nodes = await manager._database.get_episodic_nodes(limit=limit, offset=offset)
        return {
            "episodes": [n.to_dict() for n in nodes],
            "count": len(nodes),
        }

    except Exception as e:
        logger.error(
            "Episodic nodes error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list episodic nodes",
        )


@router.get("/episodes/for-entity/{entity_id}")
async def get_episodes_for_entity(
    entity_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Find episodes that mention a specific entity."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            return {"episodes": [], "count": 0}

        nodes = await manager._database.get_episodic_nodes_for_entity(entity_id)
        return {
            "episodes": [n.to_dict() for n in nodes],
            "count": len(nodes),
            "entity_id": entity_id,
        }

    except Exception as e:
        logger.error(
            "Episodes for entity error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "entity_id": entity_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find episodes for entity",
        )


# =============================================================================
# Import Source Endpoints (Sprint 20B)
# =============================================================================


@router.post("/import/paste", response_model=ImportPasteResponse)
async def import_paste(
    request: ImportPasteRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Import facts from pasted text. Creates an import source record and extracts facts."""
    try:
        # Validate source_category
        try:
            source_cat = SourceCategory(request.source_category)
        except ValueError:
            valid = ", ".join(c.value for c in SourceCategory)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid source_category. Use: {valid}",
            )

        manager = await get_research_manager()
        result = await manager.import_paste(
            text=request.text,
            provider=request.provider,
            description=request.description,
            source_category=source_cat,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Import paste error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to import pasted text",
        )


@router.get("/import/sources", response_model=ImportSourceListResponse)
async def list_import_sources(
    provider: Optional[str] = Query(default=None, description="Filter by provider name"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List import source records."""
    try:
        manager = await get_research_manager()
        result = await manager.list_import_sources(
            provider=provider,
            limit=limit,
            offset=offset,
        )
        return result

    except Exception as e:
        logger.error(
            "List import sources error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list import sources",
        )


# =============================================================================
# Entity Reference Endpoints
# =============================================================================


@router.get("/entities/{entity_id}/references", response_model=EntityReferenceListResponse)
async def get_entity_references(
    entity_id: str,
    module: Optional[str] = Query(default=None, description="Filter by module: workflow, chat, command, research_canvas, memory"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get all cross-module references for an entity."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            return {"references": [], "total": 0, "entityId": entity_id}

        module_filter: Optional[ReferenceModule] = None
        if module:
            try:
                module_filter = ReferenceModule(module)
            except ValueError:
                valid = ", ".join(m.value for m in ReferenceModule)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid module. Use: {valid}",
                )

        refs = await manager._database.get_entity_references(
            entity_id=entity_id,
            module=module_filter,
            limit=limit,
            offset=offset,
        )
        return {
            "references": [r.to_dict() for r in refs],
            "total": len(refs),
            "entityId": entity_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Get entity references error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "entity_id": entity_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get entity references",
        )


@router.post("/entities/{entity_id}/references", response_model=EntityReferenceResponse)
async def add_entity_reference(
    entity_id: str,
    request: AddReferenceRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Manually add a cross-module reference to an entity."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available",
            )

        try:
            ref_module = ReferenceModule(request.module)
        except ValueError:
            valid = ", ".join(m.value for m in ReferenceModule)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid module. Use: {valid}",
            )

        ref = EntityReference(
            entity_id=entity_id,
            module=ref_module,
            item_id=request.item_id,
            context=request.context,
            user_id=request.user_id,
        )
        saved = await manager._database.add_entity_reference(ref)
        return saved.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Add entity reference error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "entity_id": entity_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add entity reference",
        )


@router.delete("/entities/{entity_id}/references/{reference_id}")
async def delete_entity_reference(
    entity_id: str,
    reference_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Delete a specific cross-module reference by its ID."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available",
            )

        deleted = await manager._database.delete_entity_reference(reference_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reference not found",
            )
        return {"deleted": True, "referenceId": reference_id, "entityId": entity_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Delete entity reference error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "reference_id": reference_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete entity reference",
        )


# =============================================================================
# Research Board Endpoints
# =============================================================================


@router.post("/boards", response_model=BoardResponse, status_code=status.HTTP_201_CREATED)
async def create_board(
    request: CreateBoardRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Create a new research canvas board."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available",
            )
        board = ResearchBoard(name=request.name)
        saved = await manager._database.create_board(board)
        return saved.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Create board error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create board",
        )


@router.get("/boards", response_model=BoardListResponse)
async def list_boards(
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """List all research canvas boards."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            return {"boards": [], "total": 0}
        boards = await manager._database.list_boards()
        return {"boards": [b.to_dict() for b in boards], "total": len(boards)}

    except Exception as e:
        logger.error(
            "List boards error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list boards",
        )


@router.get("/boards/{board_id}", response_model=BoardResponse)
async def get_board(
    board_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get a single research canvas board by ID."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available",
            )
        board = await manager._database.get_board(board_id)
        if board is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )
        return board.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Get board error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "board_id": board_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get board",
        )


@router.put("/boards/{board_id}", response_model=BoardResponse)
async def update_board(
    board_id: str,
    request: UpdateBoardRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Update a research canvas board's name or layout."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available",
            )
        board = await manager._database.update_board(
            board_id,
            name=request.name,
            layout_json=request.layout_json,
        )
        if board is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )
        return board.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Update board error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "board_id": board_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update board",
        )


@router.delete("/boards/{board_id}")
async def delete_board(
    board_id: str,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Delete a research canvas board."""
    try:
        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available",
            )
        deleted = await manager._database.delete_board(board_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Board not found",
            )
        return {"deleted": True, "boardId": board_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Delete board error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e), "board_id": board_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete board",
        )


# =============================================================================
# Distill from Selection Endpoint
# =============================================================================


@router.post("/principles/distill-from-selection", response_model=DistillFromSelectionResponse)
async def distill_from_selection(
    request: DistillFromSelectionRequest,
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Distill a principle from a canvas entity selection.

    Loads the selected entities, builds a prompt, calls inference to propose
    a principle, and stores it with status='pending'.
    Falls back to a stub principle if inference is unavailable.
    """
    try:
        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database not available",
            )

        # Load entities
        entity_rows = []
        for entity_id in request.entity_ids:
            entity = await manager._database.find_entity_by_id(entity_id)
            if entity:
                entity_rows.append(entity)

        if not entity_rows:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No matching entities found",
            )

        entity_names = [e.name for e in entity_rows]
        entity_summary = ", ".join(entity_names)

        # Build inference prompt
        prompt = (
            f"The following knowledge graph entities are selected on the research canvas: {entity_summary}. "
            "Based on the relationships between these concepts, propose one concise behavioral or "
            "conceptual principle that captures a key insight. "
            "Respond with a single principle statement prefixed with [domain] — e.g. [reasoning] ..."
        )

        principle_content: str
        domain: str = "canvas"

        # Attempt inference
        try:
            from hestia.inference import Message, get_inference_client
            inference_client = get_inference_client()
            messages = [
                Message(role="system", content="You are a research assistant that distills knowledge graph insights into reusable principles."),
                Message(role="user", content=prompt),
            ]
            response = await inference_client.chat(messages=messages)
            raw = response.content.strip()

            # Parse [domain] prefix if present
            if raw.startswith("[") and "]" in raw:
                bracket_end = raw.index("]")
                domain = raw[1:bracket_end].strip() or "canvas"
                principle_content = raw[bracket_end + 1:].strip()
            else:
                principle_content = raw

        except Exception as infer_err:
            logger.warning(
                "Inference unavailable for distill-from-selection, creating stub",
                component=LogComponent.RESEARCH,
                data={"error": type(infer_err).__name__},
            )
            principle_content = (
                f"Principle derived from: {entity_summary}. "
                "(Inference will enhance this when available.)"
            )

        # Create principle with status=pending
        now = datetime.now(timezone.utc)
        principle = Principle(
            id=str(uuid.uuid4()),
            content=principle_content,
            domain=domain,
            confidence=0.5,
            entities=entity_names,
            created_at=now,
            updated_at=now,
        )

        if manager._principle_store:
            try:
                await manager._principle_store.ensure_initialized()
                await manager._principle_store.store_principle(principle)
            except Exception as store_err:
                logger.warning(
                    "PrincipleStore unavailable, storing in SQLite only",
                    component=LogComponent.RESEARCH,
                    data={"error": type(store_err).__name__},
                )
                await manager._database.create_principle(principle)
        else:
            await manager._database.create_principle(principle)

        logger.info(
            "Distilled principle from canvas selection",
            component=LogComponent.RESEARCH,
            data={
                "principle_id": principle.id,
                "entity_count": len(entity_rows),
                "board_id": request.board_id,
            },
        )

        return {"principle": principle.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Distill from selection error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to distill principle from selection",
        )


# =============================================================================
# Reference Indexer Endpoint
# =============================================================================


@router.post("/references/reindex")
async def trigger_reindex(
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Trigger batch entity reference indexing across all modules.

    Scans workflow steps and research canvas boards for entity mentions,
    then upserts cross-links into entity_references.  Idempotent — safe to
    call multiple times.
    """
    try:
        from hestia.research.indexer import run_batch_index
        from hestia.workflows.database import get_workflow_database

        manager = await get_research_manager()
        if not manager._database:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Research database not available",
            )

        # Workflow database is optional — if it fails to connect we skip it
        workflow_db = None
        try:
            workflow_db = await get_workflow_database()
        except Exception as wf_err:
            logger.warning(
                "Reindex: workflow database unavailable, skipping workflow scan",
                component=LogComponent.RESEARCH,
                data={"error": sanitize_for_log(wf_err)},
            )

        counts = await run_batch_index(
            research_db=manager._database,
            workflow_db=workflow_db,
        )
        return {"status": "ok", "counts": counts}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Reindex error",
            component=LogComponent.RESEARCH,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Reference reindex failed",
        )
