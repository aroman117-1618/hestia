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


# =============================================================================
# Fact / Entity / Community Schemas
# =============================================================================


class FactResponse(BaseModel):
    """A single knowledge graph fact."""
    id: str
    sourceEntityId: str
    relation: str
    targetEntityId: str
    factText: str
    status: str
    validAt: Optional[str] = None
    invalidAt: Optional[str] = None
    expiredAt: Optional[str] = None
    sourceChunkId: Optional[str] = None
    confidence: float = 0.5
    durabilityScore: int = 1
    temporalType: str = "dynamic"
    sourceCategory: str = "conversation"
    importSourceId: Optional[str] = None
    createdAt: Optional[str] = None


class FactListResponse(BaseModel):
    """List of facts with total count."""
    facts: List[FactResponse]
    total: int


class EntityResponse(BaseModel):
    """A single knowledge graph entity."""
    id: str
    name: str
    entityType: str
    canonicalName: str
    summary: Optional[str] = None
    communityId: Optional[str] = None
    firstSeenSource: str = "conversation"
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class EntityListResponse(BaseModel):
    """List of entities with total count."""
    entities: List[EntityResponse]
    total: int


class CommunityResponse(BaseModel):
    """A community of related entities."""
    id: str
    name: str
    memberEntityIds: List[str] = Field(default_factory=list)
    summary: Optional[str] = None
    createdAt: Optional[str] = None


class CommunityListResponse(BaseModel):
    """List of communities with total count."""
    communities: List[CommunityResponse]
    total: int


class ExtractFactsRequest(BaseModel):
    """Request to trigger fact extraction."""
    time_range_days: int = Field(default=7, ge=1, le=90)


class ExtractFactsResponse(BaseModel):
    """Result of fact extraction."""
    facts_created: int
    chunks_processed: int
    entities_created: int


class TimelineResponse(BaseModel):
    """Timeline snapshot: facts and entities valid at a point in time."""
    facts: List[FactResponse]
    entities: List[EntityResponse]
    point_in_time: Optional[str] = None


# =============================================================================
# Import Source Schemas (Sprint 20B)
# =============================================================================


class ImportPasteRequest(BaseModel):
    """Request to import facts from pasted text."""
    text: str = Field(..., min_length=10, max_length=50000, description="Text to extract facts from")
    provider: str = Field(default="paste", max_length=50, description="Source provider name")
    description: Optional[str] = Field(default=None, max_length=500)
    source_category: str = Field(default="imported", description="Source category: conversation, imported, web, etc.")


class ImportPasteResponse(BaseModel):
    """Result of a paste import."""
    import_source_id: str
    facts_created: int
    entities_created: int
    source_category: str


class ImportSourceResponse(BaseModel):
    """A single import source record."""
    id: str
    userId: str
    provider: str
    importType: str
    filename: Optional[str] = None
    description: Optional[str] = None
    chunkCount: int = 0
    factCount: int = 0
    entityCount: int = 0
    sourceCategory: str = "imported"
    createdAt: Optional[str] = None


class ImportSourceListResponse(BaseModel):
    """List of import sources."""
    sources: List[ImportSourceResponse]
    total: int


# =============================================================================
# Entity Reference Schemas
# =============================================================================


class EntityReferenceResponse(BaseModel):
    """A single cross-module entity reference."""

    id: str
    entityId: str
    module: str
    itemId: str
    context: str = ""
    userId: str = ""
    createdAt: Optional[str] = None


class EntityReferenceListResponse(BaseModel):
    """List of entity references with pagination metadata."""

    references: List[EntityReferenceResponse]
    total: int
    entityId: str


class AddReferenceRequest(BaseModel):
    """Request body for adding a cross-module entity reference."""

    module: str = Field(..., description="Module that references the entity: workflow, chat, command, research_canvas, memory")
    item_id: str = Field(..., min_length=1, description="ID of the item in the source module")
    context: str = Field(default="", description="Human-readable description of the reference")
    user_id: str = Field(default="default", description="User that owns this reference")
