"""
Wiki API routes.

Endpoints for browsing architecture documentation,
triggering AI content generation, and refreshing
static content from disk.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from hestia.api.middleware.auth import get_current_device
from hestia.api.errors import sanitize_for_log
from hestia.wiki import get_wiki_manager
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


class WikiStalenessItem(BaseModel):
    """Staleness check result for one article."""
    article_id: str
    title: str
    is_stale: bool


class WikiStalenessResponse(BaseModel):
    """Staleness check results."""
    articles: List[WikiStalenessItem]
    stale_count: int


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
    type: Optional[str] = Query(None, description="Filter by article type"),
    device_id: str = Depends(get_current_device),
):
    """List wiki articles."""
    manager = await get_wiki_manager()
    articles = await manager.list_articles(article_type=type)

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
    device_id: str = Depends(get_current_device),
):
    """Get a single wiki article."""
    manager = await get_wiki_manager()
    article = await manager.get_article(article_id)

    if article is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

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
    device_id: str = Depends(get_current_device),
):
    """Generate a single wiki article."""
    manager = await get_wiki_manager()

    try:
        article = await manager.generate_article(
            article_type=request.article_type,
            module_name=request.module_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
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
    device_id: str = Depends(get_current_device),
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
    device_id: str = Depends(get_current_device),
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
