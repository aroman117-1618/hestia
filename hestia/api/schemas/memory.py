"""
Memory schemas: chunks, staged memory, search.
"""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator

from .common import ChunkTypeEnum, MemoryScopeEnum, MemoryStatusEnum


class ChunkTags(BaseModel):
    """Tag-based metadata for memory chunks."""
    topics: List[str] = Field(default_factory=list, description="Topic tags")
    entities: List[str] = Field(default_factory=list, description="Entity tags")
    people: List[str] = Field(default_factory=list, description="People mentioned")
    mode: Optional[str] = Field(None, description="Mode when created")
    phase: Optional[str] = Field(None, description="Project phase")
    status: List[str] = Field(default_factory=list, description="Status tags")
    custom: Dict[str, str] = Field(default_factory=dict, description="Custom tags")


class ChunkMetadata(BaseModel):
    """Additional metadata for memory chunks."""
    has_code: bool = Field(False, description="Contains code snippets")
    has_decision: bool = Field(False, description="Contains a decision")
    has_action_item: bool = Field(False, description="Contains action items")
    sentiment: Optional[str] = Field(None, description="Sentiment analysis")
    confidence: float = Field(1.0, description="Confidence score 0.0-1.0")
    token_count: int = Field(0, description="Token count of content")
    source: Optional[str] = Field(None, description="Source of the chunk")
    is_sensitive: bool = Field(False, description="Contains PII, health, or financial data")
    sensitive_reason: Optional[str] = Field(None, description="Why flagged: pii_detected, user_flagged, health_data")


class MemoryChunk(BaseModel):
    """A memory chunk."""
    chunk_id: str = Field(description="Unique chunk identifier")
    session_id: str = Field(description="Session this chunk belongs to")
    timestamp: datetime = Field(description="When the chunk was created")
    content: str = Field(description="The chunk content")
    chunk_type: ChunkTypeEnum = Field(description="Type of chunk")
    scope: MemoryScopeEnum = Field(description="Memory scope")
    status: MemoryStatusEnum = Field(description="Chunk status")
    tags: ChunkTags = Field(description="Tag metadata")
    metadata: ChunkMetadata = Field(description="Additional metadata")


class StagedMemoryItem(BaseModel):
    """A staged memory update awaiting review."""
    chunk_id: str = Field(description="Chunk identifier")
    content: str = Field(description="Chunk content")
    chunk_type: ChunkTypeEnum = Field(description="Type of chunk")
    tags: ChunkTags = Field(description="Tag metadata")
    metadata: ChunkMetadata = Field(description="Additional metadata")
    staged_at: datetime = Field(description="When it was staged")


class StagedMemoryResponse(BaseModel):
    """Response listing staged memory updates."""
    pending: List[StagedMemoryItem] = Field(description="Pending reviews")
    count: int = Field(description="Total count")


class MemoryApprovalRequest(BaseModel):
    """Request to approve a staged memory update."""
    reviewer_notes: Optional[str] = Field(
        None,
        description="Optional notes from reviewer"
    )


class MemoryApprovalResponse(BaseModel):
    """Response after approving/rejecting memory."""
    chunk_id: str = Field(description="Chunk identifier")
    status: str = Field(description="New status (committed/rejected)")
    scope: Optional[str] = Field(None, description="New scope if committed")


class MemorySensitiveRequest(BaseModel):
    """Request to mark a memory chunk as sensitive or non-sensitive."""
    is_sensitive: bool = Field(description="Whether the chunk contains sensitive data")
    reason: Optional[str] = Field(None, description="Why flagged: user_flagged, pii_detected, health_data")


class MemorySensitiveResponse(BaseModel):
    """Response after updating memory sensitivity."""
    chunk_id: str = Field(description="Chunk identifier")
    is_sensitive: bool = Field(description="Current sensitivity status")
    reason: Optional[str] = Field(None, description="Flagging reason")


class MemorySearchResult(BaseModel):
    """A single search result."""
    chunk_id: str = Field(description="Chunk identifier")
    content: str = Field(description="Chunk content")
    relevance_score: float = Field(description="Relevance score 0.0-1.0")
    match_type: str = Field(description="How it matched (semantic/tag/etc)")
    decay_adjusted: bool = Field(False, description="Whether temporal decay was applied to the score")
    timestamp: datetime = Field(description="When created")
    tags: ChunkTags = Field(description="Tag metadata")


class MemorySearchResponse(BaseModel):
    """Response from memory search."""
    results: List[MemorySearchResult] = Field(description="Search results")
    count: int = Field(description="Number of results")


class MemoryChunkUpdateRequest(BaseModel):
    """Request body for PUT /v1/memory/chunks/{chunk_id}."""
    content: Optional[str] = None
    chunk_type: Optional[str] = None
    tags: Optional[List[str]] = None

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> "MemoryChunkUpdateRequest":
        if self.content is None and self.chunk_type is None and self.tags is None:
            raise ValueError("At least one of content, chunk_type, or tags must be provided.")
        return self


class MemoryChunkUpdateResponse(BaseModel):
    """Response for PUT /v1/memory/chunks/{chunk_id}."""
    chunk_id: str
    content: str
    chunk_type: str
    tags: List[str]
    updated_at: str
