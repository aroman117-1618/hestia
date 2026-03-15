"""
Wiki API routes.

Endpoints for browsing architecture documentation,
triggering AI content generation, and refreshing
static content from disk.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field

from hestia.api.etag import etag_response
from hestia.api.middleware.auth import get_device_token
from hestia.api.errors import sanitize_for_log
from hestia.wiki import get_wiki_manager, get_wiki_scheduler
from hestia.logging import get_logger, LogComponent


router = APIRouter(prefix="/v1/wiki", tags=["wiki"])
logger = get_logger()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class WikiArticleResponse(BaseModel):
    """A single wiki article."""
    id: str
    article_type: str
    title: str
    subtitle: str = ""
    content: str = ""
    module_name: Optional[str] = None
    source_hash: Optional[str] = None
    generation_status: str = "pending"
    generated_at: Optional[str] = None
    generation_model: Optional[str] = None
    word_count: int = 0
    estimated_read_time: int = 0


class WikiArticleListResponse(BaseModel):
    """List of wiki articles."""
    articles: List[WikiArticleResponse]
    count: int


class WikiGenerateRequest(BaseModel):
    """Request to generate a single article."""
    article_type: str = Field(..., description="overview, module, or diagram")
    module_name: Optional[str] = Field(None, description="Required for module/diagram types")


class WikiGenerateResponse(BaseModel):
    """Result of a generation request."""
    article: WikiArticleResponse
    status: str


class WikiGenerateAllResponse(BaseModel):
    """Result of full generation."""
    overview: Optional[str] = None
    modules: Dict[str, str] = Field(default_factory=dict)
    diagrams: Dict[str, str] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class WikiRefreshResponse(BaseModel):
    """Result of static content refresh."""
    decisions: int
    roadmap: int


class WikiMilestoneResponse(BaseModel):
    """A single roadmap milestone."""
    id: str
    title: str
    status: str
    scope: str


class WikiMilestoneGroupResponse(BaseModel):
    """A group of milestones (sprint/phase)."""
    id: str
    title: str
    order: int
    milestones: List[WikiMilestoneResponse] = Field(default_factory=list)


class WikiRoadmapResponse(BaseModel):
    """Structured roadmap response."""
    groups: List[WikiMilestoneGroupResponse] = Field(default_factory=list)
    whats_next: str = ""


class WikiStalenessItem(BaseModel):
    """Staleness check result for one article."""
    article_id: str
    title: str
    is_stale: bool


class WikiStalenessResponse(BaseModel):
    """Staleness check results."""
    articles: List[WikiStalenessItem]
    stale_count: int


class WikiRegenerateStaleResponse(BaseModel):
    """Result of selective regeneration."""
    trigger_source: str
    regenerated: List[str] = Field(default_factory=list)
    skipped: List[str] = Field(default_factory=list)
    failed: List[str] = Field(default_factory=list)
    static: Dict[str, Any] = Field(default_factory=dict)
    total_checked: int = 0


class WikiHealthResponse(BaseModel):
    """Wiki system health status."""
    total_articles: int
    stale_count: int
    last_generation: Optional[str] = None
    next_scheduled_sweep: Optional[str] = None
    articles_by_type: Dict[str, int] = Field(default_factory=dict)
    articles_by_status: Dict[str, int] = Field(default_factory=dict)


# =============================================================================
# Routes
# =============================================================================

@router.get(
    "/articles",
    response_model=WikiArticleListResponse,
    summary="List wiki articles",
    description="List all articles, optionally filtered by type.",
)
async def list_articles(
    request: Request,
    response: Response,
    type: Optional[str] = Query(None, description="Filter by article type"),
    device_id: str = Depends(get_device_token),
):
    """List wiki articles."""
    manager = await get_wiki_manager()
    articles = await manager.list_articles(article_type=type)

    # ETag from article metadata (IDs + generation timestamps)
    etag_source = "|".join(
        f"{a.id}:{a.generated_at.isoformat() if a.generated_at else 'none'}"
        for a in articles
    )
    cached = etag_response(request, response, etag_source)
    if cached:
        return cached

    return WikiArticleListResponse(
        articles=[
            WikiArticleResponse(
                id=a.id,
                article_type=a.article_type.value,
                title=a.title,
                subtitle=a.subtitle,
                content=a.content,
                module_name=a.module_name,
                source_hash=a.source_hash,
                generation_status=a.generation_status.value,
                generated_at=a.generated_at.isoformat() if a.generated_at else None,
                generation_model=a.generation_model,
                word_count=a.word_count,
                estimated_read_time=a.estimated_read_time,
            )
            for a in articles
        ],
        count=len(articles),
    )


@router.get(
    "/articles/{article_id}",
    response_model=WikiArticleResponse,
    summary="Get wiki article",
    description="Get a single article by ID.",
)
async def get_article(
    article_id: str,
    request: Request,
    response: Response,
    device_id: str = Depends(get_device_token),
):
    """Get a single wiki article."""
    manager = await get_wiki_manager()
    article = await manager.get_article(article_id)

    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    # ETag from article content hash + generation timestamp
    etag_source = f"{article.source_hash}:{article.generated_at}"
    cached = etag_response(request, response, etag_source)
    if cached:
        return cached

    return WikiArticleResponse(
        id=article.id,
        article_type=article.article_type.value,
        title=article.title,
        subtitle=article.subtitle,
        content=article.content,
        module_name=article.module_name,
        source_hash=article.source_hash,
        generation_status=article.generation_status.value,
        generated_at=article.generated_at.isoformat() if article.generated_at else None,
        generation_model=article.generation_model,
        word_count=article.word_count,
        estimated_read_time=article.estimated_read_time,
    )


@router.post(
    "/generate",
    response_model=WikiGenerateResponse,
    summary="Generate article",
    description="Generate a single wiki article via cloud LLM.",
)
async def generate_article(
    request: WikiGenerateRequest,
    device_id: str = Depends(get_device_token),
):
    """Generate a single wiki article."""
    manager = await get_wiki_manager()

    try:
        article = await manager.generate_article(
            article_type=request.article_type,
            module_name=request.module_name,
        )
    except ValueError as e:
        logger.warning(
            f"Wiki generation validation error: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid article type or module name.",
        )
    except Exception as e:
        logger.error(
            f"Wiki generation failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Content generation failed. Is cloud LLM enabled?",
        )

    logger.info(
        "Wiki article generated via API",
        component=LogComponent.API,
        data={
            "article_id": article.id,
            "status": article.generation_status.value,
        },
    )

    return WikiGenerateResponse(
        article=WikiArticleResponse(
            id=article.id,
            article_type=article.article_type.value,
            title=article.title,
            subtitle=article.subtitle,
            content=article.content,
            module_name=article.module_name,
            source_hash=article.source_hash,
            generation_status=article.generation_status.value,
            generated_at=article.generated_at.isoformat() if article.generated_at else None,
            generation_model=article.generation_model,
            word_count=article.word_count,
            estimated_read_time=article.estimated_read_time,
        ),
        status=article.generation_status.value,
    )


@router.post(
    "/generate-all",
    response_model=WikiGenerateAllResponse,
    summary="Generate all articles",
    description="Full regeneration of all AI content (~$0.80).",
)
async def generate_all(
    device_id: str = Depends(get_device_token),
):
    """Generate all wiki articles."""
    manager = await get_wiki_manager()

    try:
        results = await manager.generate_all()
    except Exception as e:
        logger.error(
            f"Full wiki generation failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Full generation failed. Is cloud LLM enabled?",
        )

    return WikiGenerateAllResponse(**results)


@router.post(
    "/refresh-static",
    response_model=WikiRefreshResponse,
    summary="Refresh static content",
    description="Re-read markdown docs from disk (decisions + roadmap).",
)
async def refresh_static(
    device_id: str = Depends(get_device_token),
):
    """Refresh static content from disk."""
    manager = await get_wiki_manager()

    try:
        counts = await manager.refresh_static()
    except Exception as e:
        logger.error(
            f"Static refresh failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh static content",
        )

    return WikiRefreshResponse(**counts)


@router.get(
    "/roadmap",
    response_model=WikiRoadmapResponse,
    summary="Get structured roadmap",
    description="Structured development timeline with milestone groups.",
)
async def get_roadmap(
    device_id: str = Depends(get_device_token),
):
    """Get structured roadmap data from development plan."""
    manager = await get_wiki_manager()

    try:
        result = await manager.get_roadmap_structured()
    except Exception as e:
        logger.error(
            f"Roadmap retrieval failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load roadmap",
        )

    groups = [
        WikiMilestoneGroupResponse(
            id=g["id"],
            title=g["title"],
            order=g["order"],
            milestones=[
                WikiMilestoneResponse(
                    id=m["id"],
                    title=m["title"],
                    status=m["status"],
                    scope=m["scope"],
                )
                for m in g.get("milestones", [])
            ],
        )
        for g in result.get("groups", [])
    ]

    return WikiRoadmapResponse(
        groups=groups,
        whats_next=result.get("whats_next", ""),
    )


@router.get(
    "/staleness",
    response_model=WikiStalenessResponse,
    summary="Check article staleness",
    description="Check which articles are stale (source has changed since generation).",
)
async def check_staleness(
    device_id: str = Depends(get_device_token),
):
    """Check staleness of all generated articles."""
    manager = await get_wiki_manager()

    try:
        results = await manager.check_staleness()
    except Exception as e:
        logger.error(
            f"Staleness check failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check article staleness",
        )

    stale_count = sum(1 for r in results if r["is_stale"])

    return WikiStalenessResponse(
        articles=[
            WikiStalenessItem(
                article_id=r["article_id"],
                title=r["title"],
                is_stale=r["is_stale"],
            )
            for r in results
        ],
        stale_count=stale_count,
    )


@router.post(
    "/regenerate-stale",
    response_model=WikiRegenerateStaleResponse,
    summary="Regenerate stale articles",
    description="Selectively regenerate only stale articles (~$0.03-0.05 each).",
)
async def regenerate_stale(
    device_id: str = Depends(get_device_token),
):
    """Trigger selective regeneration of stale articles."""
    manager = await get_wiki_manager()

    try:
        result = await manager.regenerate_stale(trigger_source="manual")
    except Exception as e:
        logger.error(
            f"Selective regeneration failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Selective regeneration failed. Is cloud LLM enabled?",
        )

    logger.info(
        "Selective wiki regeneration via API",
        component=LogComponent.API,
        data={
            "regenerated": len(result.get("regenerated", [])),
            "failed": len(result.get("failed", [])),
        },
    )

    return WikiRegenerateStaleResponse(**result)


@router.get(
    "/health",
    response_model=WikiHealthResponse,
    summary="Wiki system health",
    description="Dashboard: total articles, stale count, next sweep, breakdowns.",
)
async def wiki_health(
    device_id: str = Depends(get_device_token),
):
    """Get wiki system health status."""
    manager = await get_wiki_manager()

    try:
        # Get all articles
        articles = await manager.list_articles()
        total = len(articles)

        # Check staleness
        staleness = await manager.check_staleness()
        stale_count = sum(1 for s in staleness if s["is_stale"])

        # Find most recent generation
        last_gen = None
        for a in articles:
            if a.generated_at:
                ts = a.generated_at.isoformat()
                if last_gen is None or ts > last_gen:
                    last_gen = ts

        # Get next scheduled sweep
        next_sweep = None
        try:
            scheduler = await get_wiki_scheduler()
            sweep_time = scheduler.get_next_sweep_time()
            if sweep_time:
                next_sweep = sweep_time.isoformat()
        except Exception:
            pass

        # Breakdowns
        by_type: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        for a in articles:
            t = a.article_type.value
            s = a.generation_status.value
            by_type[t] = by_type.get(t, 0) + 1
            by_status[s] = by_status.get(s, 0) + 1

    except Exception as e:
        logger.error(
            f"Wiki health check failed: {sanitize_for_log(e)}",
            component=LogComponent.API,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check wiki health",
        )

    return WikiHealthResponse(
        total_articles=total,
        stale_count=stale_count,
        last_generation=last_gen,
        next_scheduled_sweep=next_sweep,
        articles_by_type=by_type,
        articles_by_status=by_status,
    )
