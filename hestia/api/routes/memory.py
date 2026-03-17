"""
Memory management routes for Hestia API.

Handles memory search, staging, and approval (ADR-002).
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from hestia.api.schemas import (
    StagedMemoryResponse,
    StagedMemoryItem,
    MemoryApprovalRequest,
    MemoryApprovalResponse,
    MemorySensitiveRequest,
    MemorySensitiveResponse,
    MemorySearchResponse,
    MemorySearchResult,
    ChunkTags,
    ChunkMetadata,
    ChunkTypeEnum,
    MemoryScopeEnum,
    MemoryStatusEnum,
    ErrorResponse,
)
from hestia.api.middleware.auth import get_device_token
from hestia.memory import get_memory_manager
from hestia.memory.models import ConversationChunk
from hestia.api.errors import sanitize_for_log
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/memory", tags=["memory"])
logger = get_logger()


def _chunk_to_staged_item(chunk: ConversationChunk, staged_at: datetime = None) -> StagedMemoryItem:
    """Convert a ConversationChunk to StagedMemoryItem."""
    return StagedMemoryItem(
        chunk_id=chunk.id,
        content=chunk.content,
        chunk_type=ChunkTypeEnum(chunk.chunk_type.value),
        tags=ChunkTags(
            topics=chunk.tags.topics,
            entities=chunk.tags.entities,
            people=chunk.tags.people,
            mode=chunk.tags.mode,
            phase=chunk.tags.phase,
            status=chunk.tags.status,
            custom=chunk.tags.custom,
        ),
        metadata=ChunkMetadata(
            has_code=chunk.metadata.has_code,
            has_decision=chunk.metadata.has_decision,
            has_action_item=chunk.metadata.has_action_item,
            sentiment=chunk.metadata.sentiment,
            confidence=chunk.metadata.confidence,
            token_count=chunk.metadata.token_count,
            source=chunk.metadata.source,
            is_sensitive=chunk.metadata.is_sensitive,
            sensitive_reason=chunk.metadata.sensitive_reason,
        ),
        staged_at=staged_at or chunk.timestamp,
    )


def _chunk_to_search_result(
    chunk: ConversationChunk,
    relevance_score: float,
    match_type: str
) -> MemorySearchResult:
    """Convert a ConversationChunk to MemorySearchResult."""
    return MemorySearchResult(
        chunk_id=chunk.id,
        content=chunk.content,
        relevance_score=relevance_score,
        match_type=match_type,
        timestamp=chunk.timestamp,
        tags=ChunkTags(
            topics=chunk.tags.topics,
            entities=chunk.tags.entities,
            people=chunk.tags.people,
            mode=chunk.tags.mode,
            phase=chunk.tags.phase,
            status=chunk.tags.status,
            custom=chunk.tags.custom,
        ),
    )


@router.get(
    "/chunks",
    summary="List memory chunks",
    description="Paginated list of memory chunks with sort and filter options.",
)
async def list_memory_chunks(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    sort_by: str = Query(default="importance", description="importance, created, or updated"),
    sort_order: str = Query(default="desc", description="asc or desc"),
    chunk_type: Optional[str] = Query(default=None),
    chunk_status: Optional[str] = Query(default=None, alias="status", description="active, archived, superseded"),
    source: Optional[str] = Query(default=None, description="conversation, mail, calendar, etc."),
    device_id: str = Depends(get_device_token),
):
    """List memory chunks with pagination, sorting, and filtering."""
    try:
        memory = await get_memory_manager()
        chunks, total = await memory.database.list_chunks(
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            chunk_type=chunk_type,
            status=chunk_status,
            source=source,
        )

        chunk_dicts = []
        for chunk in chunks:
            chunk_dicts.append({
                "id": chunk.id,
                "content": chunk.content[:200],
                "chunk_type": chunk.chunk_type.value,
                "importance": chunk.metadata.confidence,
                "status": chunk.status.value,
                "source": chunk.metadata.source,
                "topics": chunk.tags.topics,
                "entities": chunk.tags.entities,
                "created_at": chunk.timestamp.isoformat(),
                "updated_at": None,
            })

        logger.info(
            "Memory chunks listed",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "total": total,
                "returned": len(chunk_dicts),
            }
        )

        return {
            "chunks": chunk_dicts,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except Exception as e:
        logger.error(
            f"Failed to list memory chunks: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to list memory chunks.",
            }
        )


@router.get(
    "/staged",
    response_model=StagedMemoryResponse,
    summary="Get staged memory updates",
    description="List memory updates pending human review (ADR-002)."
)
async def get_staged_memory(
    device_id: str = Depends(get_device_token),
) -> StagedMemoryResponse:
    """
    Get memory chunks staged for review.

    These are chunks that have been flagged for human review before
    being committed to long-term memory (ADR-002: Governed Memory).
    """
    try:
        memory = await get_memory_manager()
        pending = await memory.get_pending_reviews()

        items = [_chunk_to_staged_item(chunk) for chunk in pending]

        logger.info(
            "Staged memory retrieved",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "pending_count": len(items),
            }
        )

        return StagedMemoryResponse(
            pending=items,
            count=len(items),
        )

    except Exception as e:
        logger.error(
            f"Failed to get staged memory: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to retrieve staged memory.",
            }
        )


@router.post(
    "/approve/{chunk_id}",
    response_model=MemoryApprovalResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Chunk not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Approve staged memory",
    description="Approve a staged memory update for long-term storage."
)
async def approve_memory(
    chunk_id: str,
    request: MemoryApprovalRequest = None,
    device_id: str = Depends(get_device_token),
) -> MemoryApprovalResponse:
    """
    Approve a staged memory chunk.

    This commits the chunk to long-term memory storage.

    Args:
        chunk_id: ID of the chunk to approve.
        request: Optional reviewer notes.
        device_id: Device ID from authentication token.

    Returns:
        MemoryApprovalResponse with new status.
    """
    try:
        memory = await get_memory_manager()

        reviewer_notes = request.reviewer_notes if request else None
        await memory.commit_to_long_term(chunk_id, reviewer_notes)

        logger.info(
            "Memory chunk approved",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "chunk_id": chunk_id,
                "has_notes": reviewer_notes is not None,
            }
        )

        return MemoryApprovalResponse(
            chunk_id=chunk_id,
            status="committed",
            scope="long_term",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "chunk_not_found",
                "message": f"Chunk '{chunk_id}' not found.",
            }
        )

    except Exception as e:
        logger.error(
            f"Failed to approve memory: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"chunk_id": chunk_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to approve memory chunk.",
            }
        )


@router.post(
    "/reject/{chunk_id}",
    response_model=MemoryApprovalResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Chunk not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Reject staged memory",
    description="Reject a staged memory update."
)
async def reject_memory(
    chunk_id: str,
    device_id: str = Depends(get_device_token),
) -> MemoryApprovalResponse:
    """
    Reject a staged memory chunk.

    This removes the chunk from the staging queue without committing it.

    Args:
        chunk_id: ID of the chunk to reject.
        device_id: Device ID from authentication token.

    Returns:
        MemoryApprovalResponse with rejected status.
    """
    try:
        memory = await get_memory_manager()

        # Get the chunk to verify it exists
        chunk = await memory.database.get_chunk(chunk_id)
        if not chunk:
            raise ValueError("Chunk not found")

        # Update status to archived (rejected)
        from hestia.memory.models import MemoryStatus
        chunk.status = MemoryStatus.ARCHIVED
        await memory.database.update_chunk(chunk)

        logger.info(
            "Memory chunk rejected",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "chunk_id": chunk_id,
            }
        )

        return MemoryApprovalResponse(
            chunk_id=chunk_id,
            status="rejected",
            scope=None,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "chunk_not_found",
                "message": f"Chunk '{chunk_id}' not found.",
            }
        )

    except Exception as e:
        logger.error(
            f"Failed to reject memory: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"chunk_id": chunk_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to reject memory chunk.",
            }
        )


@router.get(
    "/search",
    response_model=MemorySearchResponse,
    summary="Search memory",
    description="Search memory with semantic and filter queries."
)
async def search_memory(
    q: str = Query(..., description="Search query"),
    topics: Optional[List[str]] = Query(None, description="Filter by topics"),
    entities: Optional[List[str]] = Query(None, description="Filter by entities"),
    limit: int = Query(10, ge=1, le=100, description="Maximum results"),
    session_id: Optional[str] = Query(None, description="Filter by session"),
    device_id: str = Depends(get_device_token),
) -> MemorySearchResponse:
    """
    Search memory with semantic and filter queries.

    Performs semantic search using vector embeddings and optionally
    filters by tags.

    Args:
        q: The search query for semantic matching.
        topics: Optional topic tags to filter by.
        entities: Optional entity tags to filter by.
        limit: Maximum number of results (1-100).
        session_id: Optional session ID to filter by.
        device_id: Device ID from authentication token.

    Returns:
        MemorySearchResponse with matching results.
    """
    try:
        memory = await get_memory_manager()

        # Build filter kwargs
        filters = {}
        if topics:
            filters["topics"] = topics
        if entities:
            filters["entities"] = entities
        if session_id:
            filters["session_id"] = session_id

        # Perform search
        results = await memory.search(
            query=q,
            limit=limit,
            **filters
        )

        # Convert to API response
        search_results = [
            _chunk_to_search_result(
                result.chunk,
                result.relevance_score,
                result.match_type,
            )
            for result in results
        ]

        logger.info(
            "Memory search completed",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "query_preview": q[:50],
                "result_count": len(search_results),
            }
        )

        return MemorySearchResponse(
            results=search_results,
            count=len(search_results),
        )

    except Exception as e:
        logger.error(
            f"Memory search failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Memory search failed.",
            }
        )


@router.patch(
    "/{chunk_id}/sensitive",
    response_model=MemorySensitiveResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Chunk not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Set memory sensitivity",
    description="Mark a memory chunk as sensitive or non-sensitive."
)
async def set_memory_sensitivity(
    chunk_id: str,
    request: MemorySensitiveRequest,
    device_id: str = Depends(get_device_token),
) -> MemorySensitiveResponse:
    """
    Manually mark a memory chunk as sensitive or non-sensitive.

    Sensitive chunks are excluded from cloud-safe context windows,
    ensuring PII, health data, and financial info stay local.
    """
    try:
        memory = await get_memory_manager()
        chunk = await memory.flag_sensitive(
            chunk_id=chunk_id,
            is_sensitive=request.is_sensitive,
            reason=request.reason or "user_flagged",
        )

        if chunk is None:
            raise ValueError("Chunk not found")

        logger.info(
            "Memory sensitivity updated",
            component=LogComponent.API,
            data={
                "device_id": device_id,
                "chunk_id": chunk_id,
                "is_sensitive": request.is_sensitive,
            }
        )

        return MemorySensitiveResponse(
            chunk_id=chunk_id,
            is_sensitive=chunk.metadata.is_sensitive,
            reason=chunk.metadata.sensitive_reason,
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "chunk_not_found",
                "message": f"Chunk '{chunk_id}' not found.",
            }
        )

    except Exception as e:
        logger.error(
            f"Failed to update sensitivity: {sanitize_for_log(e)}",
            component=LogComponent.API,
            data={"chunk_id": chunk_id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_error",
                "message": "Failed to update memory sensitivity.",
            }
        )


# =============================================================================
# Ingestion Endpoint (Sprint 11.5)
# =============================================================================


@router.post("/ingest")
async def trigger_ingestion(
    source: Optional[str] = Query(default=None, description="Filter: mail, calendar, reminders"),
    device_token: str = Depends(get_device_token),
):
    """
    Trigger memory ingestion from Apple inbox sources.

    Ingests mail, calendar, and/or reminder items into the memory system
    with deduplication, preprocessing, and source tagging.
    """
    try:
        from hestia.inbox import get_inbox_manager
        from hestia.inbox.bridge import InboxMemoryBridge

        memory_mgr = await get_memory_manager()
        inbox_mgr = await get_inbox_manager()

        bridge = InboxMemoryBridge(
            inbox_manager=inbox_mgr,
            memory_manager=memory_mgr,
        )

        # Use device_token as user_id (single-user for now)
        result = await bridge.ingest(
            user_id=device_token,
            source_filter=source,
        )

        return {
            "batch_id": result.batch_id,
            "source": result.source,
            "items_processed": result.items_processed,
            "items_stored": result.items_stored,
            "items_skipped": result.items_skipped,
            "items_failed": result.items_failed,
            "errors": result.errors[:10],  # Cap error list
        }

    except Exception as e:
        logger.error(
            f"Ingestion failed: {sanitize_for_log(e)}",
            component=LogComponent.MEMORY,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "ingestion_failed",
                "message": "Memory ingestion failed.",
            }
        )


# =============================================================================
# Claude History Import (Sprint 13)
# =============================================================================


@router.post("/import/claude")
async def import_claude_history(
    conversations_path: str = Query(..., description="Path to conversations.json"),
    memories_path: Optional[str] = Query(default=None, description="Path to memories.json"),
    projects_path: Optional[str] = Query(default=None, description="Path to projects.json"),
    device_token: str = Depends(get_device_token),
):
    """
    Import Claude.ai conversation history into Hestia memory.

    Parses exported conversations (including thinking blocks, summaries,
    and tool patterns), deduplicates against previous imports, and stores
    through the full memory pipeline (SQLite + ChromaDB).

    Credentials found in imported text are automatically redacted.
    """
    import os
    from hestia.memory.importers.pipeline import ImportPipeline

    # Validate paths exist
    if not os.path.isfile(conversations_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "file_not_found", "message": f"Conversations file not found."},
        )

    try:
        memory_mgr = await get_memory_manager()
        pipeline = ImportPipeline(
            memory_manager=memory_mgr,
            memory_database=memory_mgr.database,
        )

        result = await pipeline.import_claude_history(
            conversations_path=conversations_path,
            memories_path=memories_path,
            projects_path=projects_path,
        )

        return result.to_dict()

    except Exception as e:
        logger.error(
            f"Claude import failed: {sanitize_for_log(e)}",
            component=LogComponent.MEMORY,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "import_failed",
                "message": "Claude history import failed.",
            }
        )


# ── Memory Lifecycle (Sprint 16) ──────────────────────────────────


def _load_memory_config() -> dict:
    """Load memory config from YAML."""
    from pathlib import Path
    import yaml
    config_path = Path(__file__).parent.parent.parent / "config" / "memory.yaml"
    try:
        with open(config_path) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


@router.get(
    "/importance-stats",
    summary="Get importance score distribution",
    description="Run importance scoring on all active chunks and return statistics.",
)
async def get_importance_stats(
    device_id: str = Depends(get_device_token),
):
    """Score all active chunks and return importance distribution stats."""
    try:
        from hestia.memory.importance import ImportanceScorer
        from hestia.outcomes import get_outcome_manager

        memory = await get_memory_manager()
        outcome_mgr = await get_outcome_manager()
        config = _load_memory_config()

        scorer = ImportanceScorer(
            memory_db=memory.database,
            outcome_db=outcome_mgr,
            config=config,
        )
        stats = await scorer.score_all(user_id="default")

        return {"data": stats}

    except Exception as e:
        logger.error(
            f"Importance scoring failed: {sanitize_for_log(e)}",
            component=LogComponent.MEMORY,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Importance scoring failed."},
        )


@router.post(
    "/consolidation/preview",
    summary="Preview consolidation candidates",
    description="Dry-run: find near-duplicate chunk pairs without modifying anything.",
)
async def consolidation_preview(
    device_id: str = Depends(get_device_token),
):
    """Find near-duplicate chunks above similarity threshold."""
    try:
        from hestia.memory.consolidator import MemoryConsolidator

        memory = await get_memory_manager()
        config = _load_memory_config()

        consolidator = MemoryConsolidator(
            memory_db=memory.database,
            vector_store=memory.vector_store,
            config=config,
        )
        result = await consolidator.preview()

        return {"data": result}

    except Exception as e:
        logger.error(
            f"Consolidation preview failed: {sanitize_for_log(e)}",
            component=LogComponent.MEMORY,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Consolidation preview failed."},
        )


@router.post(
    "/consolidation/execute",
    summary="Execute consolidation",
    description="Merge near-duplicate chunks. Lower-importance duplicate gets SUPERSEDED.",
)
async def consolidation_execute(
    dry_run: bool = Query(True, description="If true, preview only without modifying."),
    device_id: str = Depends(get_device_token),
):
    """Run consolidation. Set dry_run=false to actually merge."""
    try:
        from hestia.memory.consolidator import MemoryConsolidator

        memory = await get_memory_manager()
        config = _load_memory_config()

        consolidator = MemoryConsolidator(
            memory_db=memory.database,
            vector_store=memory.vector_store,
            config=config,
        )
        result = await consolidator.execute(dry_run=dry_run)

        return {"data": result}

    except Exception as e:
        logger.error(
            f"Consolidation execute failed: {sanitize_for_log(e)}",
            component=LogComponent.MEMORY,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Consolidation failed."},
        )


@router.get(
    "/pruning/preview",
    summary="Preview pruning candidates",
    description="List chunks eligible for pruning (old + low importance).",
)
async def pruning_preview(
    device_id: str = Depends(get_device_token),
):
    """Find chunks eligible for archival."""
    try:
        from hestia.memory.pruner import MemoryPruner

        memory = await get_memory_manager()
        config = _load_memory_config()

        pruner = MemoryPruner(
            memory_db=memory.database,
            vector_store=memory.vector_store,
            learning_db=None,  # Audit logging optional
            config=config,
        )
        result = await pruner.preview()

        return {"data": result}

    except Exception as e:
        logger.error(
            f"Pruning preview failed: {sanitize_for_log(e)}",
            component=LogComponent.MEMORY,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Pruning preview failed."},
        )


@router.post(
    "/pruning/execute",
    summary="Execute pruning",
    description="Archive eligible chunks and remove from search index.",
)
async def pruning_execute(
    device_id: str = Depends(get_device_token),
):
    """Run pruning. Archives old low-importance chunks."""
    try:
        from hestia.memory.pruner import MemoryPruner

        memory = await get_memory_manager()
        config = _load_memory_config()

        pruner = MemoryPruner(
            memory_db=memory.database,
            vector_store=memory.vector_store,
            learning_db=None,
            config=config,
        )
        result = await pruner.execute()

        return {"data": result}

    except Exception as e:
        logger.error(
            f"Pruning execute failed: {sanitize_for_log(e)}",
            component=LogComponent.MEMORY,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Pruning failed."},
        )
