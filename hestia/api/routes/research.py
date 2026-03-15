"""
Research API routes.

Endpoints for the knowledge graph, fact extraction, entity management,
community detection, and principle distillation.
Part of the Learning Cycle (Phase A).
"""

from datetime import datetime
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_device_token
from hestia.api.schemas.research import (
    CommunityListResponse,
    DistillRequest,
    DistillResponse,
    EntityListResponse,
    ExtractFactsRequest,
    ExtractFactsResponse,
    FactListResponse,
    GraphResponse,
    PrincipleListResponse,
    PrincipleResponse,
    PrincipleUpdateRequest,
    TimelineResponse,
)
from hestia.logging import LogComponent, get_logger
from hestia.research.manager import get_research_manager
from hestia.research.models import PrincipleStatus

router = APIRouter(prefix="/v1/research", tags=["research"])
logger = get_logger()


# =============================================================================
# Graph Endpoint
# =============================================================================


@router.get("/graph", response_model=GraphResponse)
async def get_graph(
    limit: int = Query(default=200, ge=1, le=500),
    node_types: Optional[str] = Query(default=None, description="Comma-separated: memory,topic,entity"),
    center_topic: Optional[str] = Query(default=None, description="Focus graph on this topic"),
    sources: Optional[str] = Query(default=None, description="Comma-separated MemorySource values: conversation,mail,calendar,reminders,notes,health"),
    mode: str = Query(default="legacy", description="Graph mode: 'legacy' (co-occurrence) or 'facts' (entity-fact)"),
    center_entity: Optional[str] = Query(default=None, description="Center entity for mode=facts"),
    device_token: str = Depends(get_device_token),
) -> Dict[str, Any]:
    """Get the knowledge graph with nodes, edges, and clusters."""
    try:
        manager = await get_research_manager()

        if mode == "facts":
            response = await manager.get_fact_graph(center_entity=center_entity)
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
        if not manager._database:
            return {"communities": [], "total": 0}

        communities = await manager._database.list_communities(limit=limit, offset=offset)
        return {
            "communities": [c.to_dict() for c in communities],
            "total": len(communities),
        }

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
