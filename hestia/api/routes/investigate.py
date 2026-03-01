"""Investigation API routes."""

from typing import Dict, List, Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from hestia.api.middleware.auth import get_device_token
from hestia.api.errors import sanitize_for_log
from hestia.investigate import get_investigate_manager
from hestia.logging import get_logger, LogComponent

router = APIRouter(prefix="/v1/investigate", tags=["investigate"])
logger = get_logger()


# =============================================================================
# Request/Response Schemas
# =============================================================================

class InvestigateURLRequest(BaseModel):
    """Request to investigate a single URL."""
    url: str = Field(..., min_length=5, max_length=2048)
    depth: str = Field("standard", pattern=r"^(quick|standard|deep)$")

    @field_validator("url")
    @classmethod
    def validate_url_scheme(cls, v: str) -> str:
        """Ensure URL has http/https scheme."""
        parsed = urlparse(v.strip())
        if parsed.scheme not in ("http", "https"):
            raise ValueError("URL must use http or https scheme")
        if not parsed.hostname:
            raise ValueError("URL must have a valid hostname")
        return v.strip()


class InvestigateCompareRequest(BaseModel):
    """Request to compare multiple URLs."""
    urls: List[str] = Field(..., min_length=2, max_length=5)
    focus: Optional[str] = Field(None, max_length=500)


class InvestigationResponse(BaseModel):
    """A single investigation result."""
    id: str
    url: str
    content_type: str
    depth: str
    status: str
    title: Optional[str] = None
    source_author: Optional[str] = None
    source_date: Optional[str] = None
    analysis: str = ""
    key_points: List[str] = Field(default_factory=list)
    model_used: Optional[str] = None
    tokens_used: int = 0
    word_count: int = 0
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class InvestigationListResponse(BaseModel):
    """List of investigations."""
    investigations: List[InvestigationResponse]
    count: int
    total: int


class ComparisonResponse(BaseModel):
    """Comparison of multiple investigations."""
    investigations: List[Dict]
    comparison: str = ""
    urls_compared: int = 0
    urls_failed: int = 0
    error: Optional[str] = None


# =============================================================================
# Routes — static paths BEFORE dynamic {id} paths
# =============================================================================

@router.post(
    "/url",
    response_model=InvestigationResponse,
    summary="Investigate a URL",
    description="Extract content from a URL and analyze it with LLM.",
)
async def investigate_url(
    request: InvestigateURLRequest,
    device_id: str = Depends(get_device_token),
):
    """Investigate a single URL."""
    manager = await get_investigate_manager()

    try:
        result = await manager.investigate(
            url=request.url,
            depth=request.depth,
            user_id=device_id,
        )
    except Exception as e:
        logger.error(
            f"Investigation failed: {sanitize_for_log(e)}",
            component=LogComponent.INVESTIGATE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Investigation failed",
        )

    return InvestigationResponse(**result)


@router.get(
    "/history",
    response_model=InvestigationListResponse,
    summary="List investigations",
    description="List past investigations with optional filtering.",
)
async def list_investigations(
    content_type: Optional[str] = Query(None, description="Filter by content type"),
    investigation_status: Optional[str] = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_device_token),
):
    """List investigation history."""
    manager = await get_investigate_manager()

    try:
        result = await manager.list_investigations(
            user_id=device_id,
            content_type=content_type,
            status=investigation_status,
            limit=limit,
            offset=offset,
        )
    except Exception as e:
        logger.error(
            f"Investigation list failed: {sanitize_for_log(e)}",
            component=LogComponent.INVESTIGATE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list investigations",
        )

    return InvestigationListResponse(**result)


@router.post(
    "/compare",
    response_model=ComparisonResponse,
    summary="Compare URLs",
    description="Investigate and compare content from 2-5 URLs.",
)
async def compare_urls(
    request: InvestigateCompareRequest,
    device_id: str = Depends(get_device_token),
):
    """Compare content from multiple URLs."""
    manager = await get_investigate_manager()

    try:
        result = await manager.compare(
            urls=request.urls,
            focus=request.focus,
            user_id=device_id,
        )
    except Exception as e:
        logger.error(
            f"Comparison failed: {sanitize_for_log(e)}",
            component=LogComponent.INVESTIGATE,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Comparison failed",
        )

    return ComparisonResponse(**result)


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
    summary="Get investigation",
    description="Retrieve a completed investigation by ID.",
)
async def get_investigation(
    investigation_id: str,
    device_id: str = Depends(get_device_token),
):
    """Get an investigation by ID."""
    manager = await get_investigate_manager()

    result = await manager.get_investigation(investigation_id, user_id=device_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    return InvestigationResponse(**result)


@router.delete(
    "/{investigation_id}",
    summary="Delete investigation",
    description="Delete an investigation by ID.",
)
async def delete_investigation(
    investigation_id: str,
    device_id: str = Depends(get_device_token),
):
    """Delete an investigation."""
    manager = await get_investigate_manager()

    deleted = await manager.delete_investigation(investigation_id, user_id=device_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    return {"deleted": True, "id": investigation_id}
