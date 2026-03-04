"""
Research data models.

Defines the graph and principle types used by the Research module.
Graph models match the frontend contract in MacNeuralNetViewModel.swift.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeType(str, Enum):
    """Types of nodes in the knowledge graph."""
    MEMORY = "memory"
    TOPIC = "topic"
    ENTITY = "entity"
    PRINCIPLE = "principle"


class EdgeType(str, Enum):
    """Types of edges connecting graph nodes."""
    SHARED_TOPIC = "shared_topic"
    SHARED_ENTITY = "shared_entity"
    TOPIC_MEMBERSHIP = "topic_membership"
    ENTITY_MEMBERSHIP = "entity_membership"
    SEMANTIC = "semantic"


class PrincipleStatus(str, Enum):
    """Status lifecycle for distilled principles."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# Category-to-color mapping for frontend rendering.
# Matches ChunkType.nodeColor in MacNeuralNetViewModel.swift.
CATEGORY_COLORS: Dict[str, str] = {
    "conversation": "#5AC8FA",
    "fact": "#4CD964",
    "preference": "#FF9500",
    "decision": "#FF3B30",
    "action_item": "#AF52DE",
    "research": "#007AFF",
    "system": "#8E8E93",
    "topic": "#FFD60A",
    "entity": "#30D158",
    "principle": "#BF5AF2",
}


@dataclass
class GraphNode:
    """
    A node in the knowledge graph.

    Frontend contract (MacNeuralNetViewModel.swift):
        id, content, chunkType (mapped from category), confidence,
        topics, entities, position {x,y,z}, color (from category).
        radius is computed from weight on the frontend.
    """
    id: str
    content: str
    node_type: NodeType
    category: str
    label: str
    confidence: float
    weight: float
    topics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    position: Optional[Dict[str, float]] = None
    last_active: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def color(self) -> str:
        """Hex color for frontend rendering, based on category."""
        return CATEGORY_COLORS.get(self.category, "#8E8E93")

    @property
    def radius(self) -> float:
        """Node size, proportional to weight. Range: 0.15–0.30."""
        return 0.15 + self.weight * 0.15

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response. Keys match Swift Codable expectations."""
        return {
            "id": self.id,
            "content": self.content,
            "nodeType": self.node_type.value,
            "category": self.category,
            "label": self.label,
            "confidence": self.confidence,
            "weight": self.weight,
            "topics": self.topics,
            "entities": self.entities,
            "position": self.position or {"x": 0.0, "y": 0.0, "z": 0.0},
            "radius": self.radius,
            "color": self.color,
            "lastActive": self.last_active.isoformat() if self.last_active else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphNode":
        """Deserialize from dict."""
        last_active = None
        if data.get("lastActive"):
            try:
                last_active = datetime.fromisoformat(data["lastActive"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=data["id"],
            content=data["content"],
            node_type=NodeType(data["nodeType"]),
            category=data["category"],
            label=data["label"],
            confidence=data["confidence"],
            weight=data["weight"],
            topics=data.get("topics", []),
            entities=data.get("entities", []),
            position=data.get("position"),
            last_active=last_active,
            metadata=data.get("metadata", {}),
        )


@dataclass
class GraphEdge:
    """
    An edge connecting two graph nodes.

    Frontend contract: fromId, toId, weight (camelCase).
    id is auto-generated as "{fromId}-{toId}".
    """
    from_id: str
    to_id: str
    edge_type: EdgeType
    weight: float
    count: int = 1

    @property
    def id(self) -> str:
        return f"{self.from_id}-{self.to_id}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response. camelCase to match Swift."""
        return {
            "id": self.id,
            "fromId": self.from_id,
            "toId": self.to_id,
            "edgeType": self.edge_type.value,
            "weight": self.weight,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphEdge":
        """Deserialize from dict."""
        return cls(
            from_id=data["fromId"],
            to_id=data["toId"],
            edge_type=EdgeType(data["edgeType"]),
            weight=data["weight"],
            count=data.get("count", 1),
        )


@dataclass
class GraphCluster:
    """A group of related nodes in the graph."""
    id: str
    label: str
    node_ids: List[str] = field(default_factory=list)
    color: str = "#8E8E93"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "label": self.label,
            "nodeIds": self.node_ids,
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphCluster":
        return cls(
            id=data["id"],
            label=data["label"],
            node_ids=data.get("nodeIds", []),
            color=data.get("color", "#8E8E93"),
        )


@dataclass
class GraphResponse:
    """Full graph response returned by the API."""
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    clusters: List[GraphCluster]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "clusters": [c.to_dict() for c in self.clusters],
            "nodeCount": len(self.nodes),
            "edgeCount": len(self.edges),
            "metadata": self.metadata,
        }


@dataclass
class Principle:
    """
    A distilled behavioral principle extracted from interactions.

    Principles start as 'pending' and require user approval before
    influencing downstream systems (audit requirement).
    """
    id: str
    content: str
    domain: str
    confidence: float
    status: PrincipleStatus = PrincipleStatus.PENDING
    source_chunk_ids: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)
    validation_count: int = 0
    contradiction_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "domain": self.domain,
            "confidence": self.confidence,
            "status": self.status.value,
            "sourceChunkIds": self.source_chunk_ids,
            "topics": self.topics,
            "entities": self.entities,
            "validationCount": self.validation_count,
            "contradictionCount": self.contradiction_count,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Principle":
        created_at = None
        updated_at = None
        if data.get("createdAt"):
            try:
                created_at = datetime.fromisoformat(data["createdAt"])
            except (ValueError, TypeError):
                pass
        if data.get("updatedAt"):
            try:
                updated_at = datetime.fromisoformat(data["updatedAt"])
            except (ValueError, TypeError):
                pass

        return cls(
            id=data["id"],
            content=data["content"],
            domain=data["domain"],
            confidence=data["confidence"],
            status=PrincipleStatus(data.get("status", "pending")),
            source_chunk_ids=data.get("sourceChunkIds", []),
            topics=data.get("topics", []),
            entities=data.get("entities", []),
            validation_count=data.get("validationCount", 0),
            contradiction_count=data.get("contradictionCount", 0),
            created_at=created_at,
            updated_at=updated_at,
        )

    @classmethod
    def create(cls, content: str, domain: str, confidence: float = 0.5,
               source_chunk_ids: Optional[List[str]] = None,
               topics: Optional[List[str]] = None,
               entities: Optional[List[str]] = None) -> "Principle":
        """Factory method with auto-generated ID and timestamps."""
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            content=content,
            domain=domain,
            confidence=confidence,
            source_chunk_ids=source_chunk_ids or [],
            topics=topics or [],
            entities=entities or [],
            created_at=now,
            updated_at=now,
        )
