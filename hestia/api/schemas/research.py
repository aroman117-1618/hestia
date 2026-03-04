"""
Research schemas: graph responses and principle models.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Graph Schemas
# =============================================================================


class GraphNodeResponse(BaseModel):
    """A single node in the knowledge graph."""
    id: str
    content: str
    nodeType: str
    category: str
    label: str
    confidence: float
    weight: float
    topics: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    position: Dict[str, float] = Field(default_factory=dict)
    radius: float = 0.15
    color: str = "#8E8E93"
    lastActive: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdgeResponse(BaseModel):
    """An edge connecting two graph nodes."""
    id: str
    fromId: str
    toId: str
    edgeType: str
    weight: float
    count: int = 1


class GraphClusterResponse(BaseModel):
    """A cluster of related nodes."""
    id: str
    label: str
    nodeIds: List[str] = Field(default_factory=list)
    color: str = "#8E8E93"


class GraphResponse(BaseModel):
    """Full graph response with nodes, edges, and clusters."""
    nodes: List[GraphNodeResponse]
    edges: List[GraphEdgeResponse]
    clusters: List[GraphClusterResponse]
    nodeCount: int
    edgeCount: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Principle Schemas
# =============================================================================


class PrincipleResponse(BaseModel):
    """A single distilled principle."""
    id: str
    content: str
    domain: str
    confidence: float
    status: str
    sourceChunkIds: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    validationCount: int = 0
    contradictionCount: int = 0
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class PrincipleListResponse(BaseModel):
    """List of principles with total count."""
    principles: List[PrincipleResponse]
    total: int


class DistillRequest(BaseModel):
    """Request to trigger principle distillation."""
    time_range_days: int = Field(default=7, ge=1, le=90)


class DistillResponse(BaseModel):
    """Result of principle distillation."""
    principles_extracted: int
    new: int
    input_chunks: int = 0


class PrincipleUpdateRequest(BaseModel):
    """Request to update a principle's content."""
    content: str = Field(..., min_length=1, max_length=2000)
