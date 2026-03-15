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
    FACT = "fact"
    COMMUNITY = "community"


class EdgeType(str, Enum):
    """Types of edges connecting graph nodes."""
    SHARED_TOPIC = "shared_topic"
    SHARED_ENTITY = "shared_entity"
    TOPIC_MEMBERSHIP = "topic_membership"
    ENTITY_MEMBERSHIP = "entity_membership"
    SEMANTIC = "semantic"
    PRINCIPLE_SOURCE = "principle_source"
    RELATIONSHIP = "relationship"
    SUPERSEDES = "supersedes"
    COMMUNITY_MEMBER = "community_member"


class PrincipleStatus(str, Enum):
    """Status lifecycle for distilled principles."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EntityType(str, Enum):
    """Types of entities in the knowledge graph."""
    PERSON = "person"
    TOOL = "tool"
    CONCEPT = "concept"
    PLACE = "place"
    PROJECT = "project"
    ORGANIZATION = "organization"


class FactStatus(str, Enum):
    """Lifecycle status for knowledge graph facts."""
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    RETRACTED = "retracted"


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
    "community": "#FF375F",
    "fact_node": "#64D2FF",
    # Entity type colors (for fact-based graph)
    "person": "#FF9F0A",
    "tool": "#30D158",
    "project": "#5AC8FA",
    "organization": "#BF5AF2",
    "place": "#FF375F",
    "concept": "#64D2FF",
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
class Fact:
    """
    A temporal fact (edge between two entities) in the knowledge graph.

    Bi-temporal design:
        valid_at   — when the fact became true in the real world
        invalid_at — when the fact was superseded (real-world end)
        expired_at — when the system detected the change
    """
    id: str
    source_entity_id: str
    relation: str
    target_entity_id: str
    fact_text: str
    status: FactStatus = FactStatus.ACTIVE
    valid_at: Optional[datetime] = None
    invalid_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    source_chunk_id: Optional[str] = None
    confidence: float = 0.5
    user_id: str = "default"
    created_at: Optional[datetime] = None

    def is_valid_at(self, point_in_time: datetime) -> bool:
        """Check whether this fact was valid at a given point in time."""
        if self.valid_at and point_in_time < self.valid_at:
            return False
        if self.invalid_at and point_in_time >= self.invalid_at:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response. camelCase keys for Swift frontend."""
        return {
            "id": self.id,
            "sourceEntityId": self.source_entity_id,
            "relation": self.relation,
            "targetEntityId": self.target_entity_id,
            "factText": self.fact_text,
            "status": self.status.value,
            "validAt": self.valid_at.isoformat() if self.valid_at else None,
            "invalidAt": self.invalid_at.isoformat() if self.invalid_at else None,
            "expiredAt": self.expired_at.isoformat() if self.expired_at else None,
            "sourceChunkId": self.source_chunk_id,
            "confidence": self.confidence,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Fact":
        """Deserialize from camelCase dict."""
        def _parse_dt(key: str) -> Optional[datetime]:
            val = data.get(key)
            if val:
                try:
                    return datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    pass
            return None

        return cls(
            id=data["id"],
            source_entity_id=data["sourceEntityId"],
            relation=data.get("relation", "RELATED_TO"),
            target_entity_id=data["targetEntityId"],
            fact_text=data["factText"],
            status=FactStatus(data.get("status", "active")),
            valid_at=_parse_dt("validAt"),
            invalid_at=_parse_dt("invalidAt"),
            expired_at=_parse_dt("expiredAt"),
            source_chunk_id=data.get("sourceChunkId"),
            confidence=data.get("confidence", 0.5),
            created_at=_parse_dt("createdAt"),
        )

    @classmethod
    def create(
        cls,
        source_entity_id: str,
        relation: str,
        target_entity_id: str,
        fact_text: str,
        source_chunk_id: Optional[str] = None,
        confidence: float = 0.5,
        valid_at: Optional[datetime] = None,
        user_id: str = "default",
    ) -> "Fact":
        """Factory method with auto-generated UUID and timestamps."""
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            source_entity_id=source_entity_id,
            relation=relation,
            target_entity_id=target_entity_id,
            fact_text=fact_text,
            source_chunk_id=source_chunk_id,
            confidence=confidence,
            valid_at=valid_at or now,
            user_id=user_id,
            created_at=now,
        )


@dataclass
class Entity:
    """
    A node in the knowledge graph (person, tool, concept, etc.).

    canonical_name is the lowercase version of name, used for deduplication.
    """
    id: str
    name: str
    canonical_name: str
    entity_type: EntityType
    summary: Optional[str] = None
    community_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user_id: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response. camelCase keys for Swift frontend."""
        return {
            "id": self.id,
            "name": self.name,
            "canonicalName": self.canonical_name,
            "entityType": self.entity_type.value,
            "summary": self.summary,
            "communityId": self.community_id,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "userId": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Entity":
        """Deserialize from camelCase dict."""
        def _parse_dt(key: str) -> Optional[datetime]:
            val = data.get(key)
            if val:
                try:
                    return datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    pass
            return None

        return cls(
            id=data["id"],
            name=data["name"],
            canonical_name=data["canonicalName"],
            entity_type=EntityType(data["entityType"]),
            summary=data.get("summary"),
            community_id=data.get("communityId"),
            created_at=_parse_dt("createdAt"),
            updated_at=_parse_dt("updatedAt"),
            user_id=data.get("userId", "default"),
        )

    @classmethod
    def create(
        cls,
        name: str,
        entity_type: EntityType,
        summary: Optional[str] = None,
        community_id: Optional[str] = None,
        user_id: str = "default",
    ) -> "Entity":
        """Factory method with auto-generated UUID and timestamps."""
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            canonical_name=name.lower(),
            entity_type=entity_type,
            summary=summary,
            community_id=community_id,
            created_at=now,
            updated_at=now,
            user_id=user_id,
        )


@dataclass
class Community:
    """
    A cluster of related entities with optional LLM-generated summary.
    """
    id: str
    label: str
    summary: Optional[str] = None
    member_entity_ids: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    user_id: str = "default"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response. camelCase keys for Swift frontend."""
        return {
            "id": self.id,
            "label": self.label,
            "summary": self.summary,
            "memberEntityIds": self.member_entity_ids,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
            "userId": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Community":
        """Deserialize from camelCase dict."""
        def _parse_dt(key: str) -> Optional[datetime]:
            val = data.get(key)
            if val:
                try:
                    return datetime.fromisoformat(val)
                except (ValueError, TypeError):
                    pass
            return None

        return cls(
            id=data["id"],
            label=data["label"],
            summary=data.get("summary"),
            member_entity_ids=data.get("memberEntityIds", []),
            created_at=_parse_dt("createdAt"),
            updated_at=_parse_dt("updatedAt"),
            user_id=data.get("userId", "default"),
        )

    @classmethod
    def create(
        cls,
        label: str,
        member_entity_ids: Optional[List[str]] = None,
        summary: Optional[str] = None,
        user_id: str = "default",
    ) -> "Community":
        """Factory method with auto-generated UUID and timestamps."""
        now = datetime.now(timezone.utc)
        return cls(
            id=str(uuid.uuid4()),
            label=label,
            summary=summary,
            member_entity_ids=member_entity_ids or [],
            created_at=now,
            updated_at=now,
            user_id=user_id,
        )


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
