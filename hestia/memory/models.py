"""
Memory models for Hestia.

Based on ADR-013: Tag-based memory schema with hybrid storage.
ChromaDB for vector embeddings, SQLite for structured metadata.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class MemoryScope(Enum):
    """Memory scope levels."""
    SESSION = "session"      # Current conversation only
    SHORT_TERM = "short_term"  # Last 7 days
    LONG_TERM = "long_term"   # Persistent, reviewed


class MemoryStatus(Enum):
    """Memory chunk status."""
    ACTIVE = "active"        # Current, relevant
    STAGED = "staged"        # Awaiting human review for long-term
    COMMITTED = "committed"  # Reviewed and committed to long-term
    SUPERSEDED = "superseded"  # Replaced by newer information
    ARCHIVED = "archived"    # Old but preserved


class ChunkType(Enum):
    """Type of memory chunk."""
    CONVERSATION = "conversation"  # User-assistant exchange
    FACT = "fact"                  # Extracted factual information
    PREFERENCE = "preference"       # User preference
    DECISION = "decision"           # Architectural or user decision
    ACTION_ITEM = "action_item"     # Task to be done
    RESEARCH = "research"           # Research findings
    SYSTEM = "system"               # System-generated notes


@dataclass
class ChunkTags:
    """
    Tag-based metadata for memory chunks.

    Inspired by Datadog's observability model.
    Enables multi-dimensional queries.
    """
    topics: List[str] = field(default_factory=list)      # ["security", "encryption"]
    entities: List[str] = field(default_factory=list)    # ["Face ID", "Secure Enclave"]
    people: List[str] = field(default_factory=list)      # ["andrew"]
    mode: Optional[str] = None                            # "Tia", "Mira", "Olly"
    phase: Optional[str] = None                           # "design", "implementation"
    status: List[str] = field(default_factory=list)      # ["active", "unresolved"]
    custom: Dict[str, str] = field(default_factory=dict)  # User-defined tags

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "topics": self.topics,
            "entities": self.entities,
            "people": self.people,
            "mode": self.mode,
            "phase": self.phase,
            "status": self.status,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkTags":
        """Create from dictionary."""
        return cls(
            topics=data.get("topics", []),
            entities=data.get("entities", []),
            people=data.get("people", []),
            mode=data.get("mode"),
            phase=data.get("phase"),
            status=data.get("status", []),
            custom=data.get("custom", {}),
        )


@dataclass
class ChunkMetadata:
    """
    Additional metadata for memory chunks.
    """
    has_code: bool = False
    has_decision: bool = False
    has_action_item: bool = False
    sentiment: Optional[str] = None     # "positive", "neutral", "negative"
    confidence: float = 1.0             # 0.0 - 1.0
    token_count: int = 0
    source: Optional[str] = None        # "conversation", "import", "background_task"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "has_code": self.has_code,
            "has_decision": self.has_decision,
            "has_action_item": self.has_action_item,
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "token_count": self.token_count,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkMetadata":
        """Create from dictionary."""
        return cls(
            has_code=data.get("has_code", False),
            has_decision=data.get("has_decision", False),
            has_action_item=data.get("has_action_item", False),
            sentiment=data.get("sentiment"),
            confidence=data.get("confidence", 1.0),
            token_count=data.get("token_count", 0),
            source=data.get("source"),
        )


@dataclass
class ConversationChunk:
    """
    Core memory unit for Hestia.

    Represents a piece of conversation or extracted information
    with rich metadata for multi-dimensional querying.
    """
    id: str
    session_id: str
    timestamp: datetime
    content: str

    # Classification
    chunk_type: ChunkType = ChunkType.CONVERSATION
    scope: MemoryScope = MemoryScope.SESSION
    status: MemoryStatus = MemoryStatus.ACTIVE

    # Tag-based metadata (SQLite)
    tags: ChunkTags = field(default_factory=ChunkTags)
    metadata: ChunkMetadata = field(default_factory=ChunkMetadata)

    # Relationships
    references: List[str] = field(default_factory=list)  # Links to other chunks
    supersedes: Optional[str] = None  # If this updates old info
    parent_id: Optional[str] = None   # For threaded conversations

    # Embedding (stored in ChromaDB, not SQLite)
    embedding: Optional[List[float]] = None

    @classmethod
    def create(
        cls,
        content: str,
        session_id: str,
        chunk_type: ChunkType = ChunkType.CONVERSATION,
        **kwargs
    ) -> "ConversationChunk":
        """Factory method to create a new chunk with auto-generated ID."""
        return cls(
            id=f"chunk-{uuid4().hex[:12]}",
            session_id=session_id,
            timestamp=datetime.now(timezone.utc),
            content=content,
            chunk_type=chunk_type,
            **kwargs
        )

    def to_sqlite_row(self) -> Dict[str, Any]:
        """Convert to SQLite row format."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "chunk_type": self.chunk_type.value,
            "scope": self.scope.value,
            "status": self.status.value,
            "tags": json.dumps(self.tags.to_dict()),
            "metadata": json.dumps(self.metadata.to_dict()),
            "chunk_refs": json.dumps(self.references),
            "supersedes": self.supersedes,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_sqlite_row(cls, row: Dict[str, Any]) -> "ConversationChunk":
        """Create from SQLite row."""
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            content=row["content"],
            chunk_type=ChunkType(row["chunk_type"]),
            scope=MemoryScope(row["scope"]),
            status=MemoryStatus(row["status"]),
            tags=ChunkTags.from_dict(json.loads(row["tags"])),
            metadata=ChunkMetadata.from_dict(json.loads(row["metadata"])),
            references=json.loads(row["chunk_refs"]),
            supersedes=row["supersedes"],
            parent_id=row["parent_id"],
        )


@dataclass
class MemorySearchResult:
    """Result from memory search."""
    chunk: ConversationChunk
    relevance_score: float  # 0.0 - 1.0, higher is more relevant
    match_type: str         # "semantic", "tag", "temporal", "exact"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "chunk_id": self.chunk.id,
            "content": self.chunk.content,
            "relevance_score": self.relevance_score,
            "match_type": self.match_type,
            "timestamp": self.chunk.timestamp.isoformat(),
            "tags": self.chunk.tags.to_dict(),
        }


@dataclass
class MemoryQuery:
    """
    Query parameters for memory search.

    Supports multi-dimensional filtering:
    - Semantic: Vector similarity search
    - Tags: Filter by metadata tags
    - Temporal: Date range filtering
    - Relational: Follow references
    """
    # Semantic search
    semantic_query: Optional[str] = None
    semantic_threshold: float = 0.7  # Minimum similarity score

    # Tag filters
    topics: Optional[List[str]] = None
    entities: Optional[List[str]] = None
    people: Optional[List[str]] = None
    mode: Optional[str] = None
    status: Optional[List[str]] = None
    chunk_types: Optional[List[ChunkType]] = None

    # Metadata filters
    has_code: Optional[bool] = None
    has_decision: Optional[bool] = None
    has_action_item: Optional[bool] = None

    # Temporal filters
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    session_id: Optional[str] = None

    # Relational
    references: Optional[List[str]] = None  # Chunks that reference these IDs

    # Pagination
    limit: int = 10
    offset: int = 0

    # Scope filter
    scopes: Optional[List[MemoryScope]] = None
