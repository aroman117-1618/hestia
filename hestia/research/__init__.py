"""
Research module — knowledge graph and principle distillation.

Builds a hybrid knowledge + activity graph from memory chunks and tool
execution logs. Distills recurring interaction patterns into reusable
principles via LLM analysis (Learning Cycle Phase A).
"""

from .models import (
    CATEGORY_COLORS,
    Community,
    EdgeType,
    Entity,
    EntityType,
    Fact,
    FactStatus,
    GraphCluster,
    GraphEdge,
    GraphNode,
    GraphResponse,
    NodeType,
    Principle,
    PrincipleStatus,
)

__all__ = [
    "CATEGORY_COLORS",
    "Community",
    "EdgeType",
    "Entity",
    "EntityType",
    "Fact",
    "FactStatus",
    "GraphCluster",
    "GraphEdge",
    "GraphNode",
    "GraphResponse",
    "NodeType",
    "Principle",
    "PrincipleStatus",
]
