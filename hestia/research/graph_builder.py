"""
Graph builder — constructs a knowledge graph from memory chunks.

Pipeline:
1. Query MemoryManager for all chunks (or filtered subset)
2. Build memory nodes (one per chunk)
3. Extract unique topics/entities → create topic and entity nodes
4. Build edges (shared topics/entities, topic/entity membership)
5. Compute force-directed 3D layout
6. Simple clustering by dominant topic
7. Cache result in SQLite with TTL

Port of the client-side graph logic from MacNeuralNetViewModel.swift,
moved server-side for consistency and performance.
"""

import asyncio
import math
import random
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from hestia.logging import LogComponent, get_logger

from .models import (
    CATEGORY_COLORS,
    EdgeType,
    Entity,
    EpisodicNode,
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

logger = get_logger()

# Limits to prevent runaway computation on M1 16GB
MAX_NODES = 200
MAX_EDGES = 500
LAYOUT_ITERATIONS = 120
COMPUTATION_TIMEOUT_SECONDS = 10


class GraphBuilder:
    """
    Builds a knowledge graph from memory search results.

    The graph contains three node types:
    - Memory nodes (from ConversationChunk)
    - Topic nodes (aggregated from chunk tags)
    - Entity nodes (aggregated from chunk tags)

    Edges represent shared tags or membership relationships.
    """

    def __init__(self) -> None:
        self._memory_manager = None
        self._research_database = None

    async def _get_memory_manager(self) -> Any:
        """Lazy import to avoid circular dependencies."""
        if self._memory_manager is None:
            from hestia.memory import get_memory_manager
            self._memory_manager = await get_memory_manager()
        return self._memory_manager

    async def _get_research_database(self) -> Any:
        """Lazy import to avoid circular dependencies."""
        if self._research_database is None:
            from .database import get_research_database
            self._research_database = await get_research_database()
        return self._research_database

    # ── Fact-Based Graph ────────────────────────────────

    async def build_fact_graph(
        self,
        center_entity: Optional[str] = None,
        max_depth: int = 3,
        point_in_time: Optional[Any] = None,
    ) -> GraphResponse:
        """
        Build a knowledge graph from entities, facts, communities, and episodes.

        This is a separate entry point from build_graph(). Instead of
        memory chunks, it uses the structured entity/fact/community tables.

        Args:
            center_entity: Entity ID to center the graph on (BFS filtering).
            max_depth: Max hops from center_entity to include.
            point_in_time: Optional datetime for bi-temporal fact filtering.

        Returns:
            GraphResponse with entity nodes, relationship edges, community
            clusters, and episodic timeline nodes.
        """
        start_time = time.time()

        try:
            db = await self._get_research_database()
            entities = await db.list_entities(limit=200)
            facts = await db.list_facts(status=FactStatus.ACTIVE, limit=500)
            communities = await db.list_communities(limit=50)
            episodes = await db.get_episodic_nodes(limit=50)
        except Exception as e:
            logger.warning(
                "Fact graph builder: DB query failed, returning empty graph",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return GraphResponse(
                nodes=[], edges=[], clusters=[],
                metadata={"error": type(e).__name__, "query_time_ms": 0},
            )

        if not entities:
            return GraphResponse(
                nodes=[], edges=[], clusters=[],
                metadata={"total_entities": 0, "query_time_ms": 0},
            )

        # Bi-temporal filtering: keep only facts valid at the given point in time
        total_facts_before_filter = len(facts)
        if point_in_time is not None:
            facts = [f for f in facts if f.is_valid_at(point_in_time)]

        # Sprint 20A: Exclude ephemeral facts (durability=0) from graph
        # They remain searchable in Memory tab only (Log-to-Graph architecture)
        facts = [f for f in facts if f.durability_score > 0]

        # ── Build entity nodes ──────────────────────────
        entity_id_set = {e.id for e in entities}
        fact_counts: Counter = Counter()
        for fact in facts:
            if fact.source_entity_id in entity_id_set:
                fact_counts[fact.source_entity_id] += 1
            if fact.target_entity_id in entity_id_set:
                fact_counts[fact.target_entity_id] += 1

        max_fact_count = max(fact_counts.values()) if fact_counts else 1

        # Sprint 20A: Compute max durability per entity for visual weight
        entity_max_durability: Dict[str, int] = {}
        for fact in facts:
            for eid in (fact.source_entity_id, fact.target_entity_id):
                if eid in entity_id_set:
                    current = entity_max_durability.get(eid, 0)
                    entity_max_durability[eid] = max(current, fact.durability_score)

        entity_nodes: List[GraphNode] = []
        for entity in entities:
            count = fact_counts.get(entity.id, 0)
            freq_weight = (count / max_fact_count) if max_fact_count > 0 else 0.7

            # Blend frequency (60%) with durability (40%) for visual weight
            durability_norm = entity_max_durability.get(entity.id, 1) / 3.0
            weight = freq_weight * 0.6 + durability_norm * 0.4
            weight = max(weight, 0.2)  # minimum weight so isolated entities are visible

            entity_nodes.append(GraphNode(
                id=f"entity:{entity.id}",
                content=entity.summary or f"{entity.entity_type.value}: {entity.name}",
                node_type=NodeType.ENTITY,
                category=entity.entity_type.value,
                label=entity.name,
                confidence=1.0,
                weight=weight,
                entities=[entity.name],
                last_active=entity.updated_at,
                metadata={
                    "entity_type": entity.entity_type.value,
                    "canonical_name": entity.canonical_name,
                    "community_id": entity.community_id,
                    "max_durability": entity_max_durability.get(entity.id, 1),
                },
            ))

        node_id_set = {n.id for n in entity_nodes}

        # ── Build RELATIONSHIP edges from facts ─────────
        relationship_edges: List[GraphEdge] = []
        for fact in facts:
            from_id = f"entity:{fact.source_entity_id}"
            to_id = f"entity:{fact.target_entity_id}"
            if from_id in node_id_set and to_id in node_id_set:
                # Blend confidence (60%) with durability (40%) for edge weight
                conf = fact.confidence if fact.confidence else 0.5
                dur_norm = fact.durability_score / 3.0
                edge_weight = conf * 0.6 + dur_norm * 0.4
                relationship_edges.append(GraphEdge(
                    from_id=from_id,
                    to_id=to_id,
                    edge_type=EdgeType.RELATIONSHIP,
                    weight=edge_weight,
                    count=1,
                ))

        # ── Build community nodes and member edges ──────
        community_nodes: List[GraphNode] = []
        member_edges: List[GraphEdge] = []

        for community in communities:
            comm_node_id = f"community:{community.id}"
            community_nodes.append(GraphNode(
                id=comm_node_id,
                content=community.summary or f"Community: {community.label}",
                node_type=NodeType.COMMUNITY,
                category="community",
                label=community.label,
                confidence=1.0,
                weight=0.5,
                metadata={"member_count": len(community.member_entity_ids)},
            ))

            for member_id in community.member_entity_ids:
                entity_graph_id = f"entity:{member_id}"
                if entity_graph_id in node_id_set:
                    member_edges.append(GraphEdge(
                        from_id=entity_graph_id,
                        to_id=comm_node_id,
                        edge_type=EdgeType.COMMUNITY_MEMBER,
                        weight=0.3,
                    ))

        # ── Build episodic nodes and edges ───────────────
        episode_nodes: List[GraphNode] = []
        episode_edges: List[GraphEdge] = []

        for episode in episodes:
            ep_node_id = f"episode:{episode.id}"
            episode_nodes.append(GraphNode(
                id=ep_node_id,
                content=episode.summary[:200] if episode.summary else f"Session {episode.session_id}",
                node_type=NodeType.EPISODE,
                category="episode",
                label=f"Episode: {episode.summary[:40]}..." if len(episode.summary) > 40 else f"Episode: {episode.summary}",
                confidence=1.0,
                weight=0.4,
                entities=[],
                last_active=episode.created_at,
                metadata={
                    "session_id": episode.session_id,
                    "entity_count": len(episode.entity_ids),
                    "fact_count": len(episode.fact_ids),
                },
            ))

            # Link episode to its entities
            for eid in episode.entity_ids:
                entity_graph_id = f"entity:{eid}"
                if entity_graph_id in node_id_set:
                    episode_edges.append(GraphEdge(
                        from_id=ep_node_id,
                        to_id=entity_graph_id,
                        edge_type=EdgeType.SEMANTIC,
                        weight=0.3,
                    ))

        # ── Assemble all nodes and edges ────────────────
        all_nodes = entity_nodes + community_nodes + episode_nodes
        all_edges = relationship_edges + member_edges + episode_edges

        # ── BFS filter by center_entity ─────────────────
        if center_entity:
            all_nodes, all_edges = self._filter_by_center_entity(
                center_entity, max_depth, all_nodes, all_edges, facts
            )

        # ── Enforce limits ──────────────────────────────
        all_nodes = all_nodes[:MAX_NODES]
        all_edges = all_edges[:MAX_EDGES]

        # ── Layout ──────────────────────────────────────
        self._compute_layout(all_nodes, all_edges)

        # ── Clusters from communities ───────────────────
        clusters = self._build_community_clusters(communities, all_nodes)

        # Query earliest fact date for time slider bounding
        earliest = await db.get_earliest_fact_date()

        query_time_ms = int((time.time() - start_time) * 1000)
        pit_str = point_in_time.isoformat() if point_in_time else None

        logger.info(
            "Fact graph built",
            component=LogComponent.RESEARCH,
            data={
                "nodes": len(all_nodes),
                "edges": len(all_edges),
                "clusters": len(clusters),
                "episodes": len(episode_nodes),
                "point_in_time": pit_str,
                "facts_filtered": total_facts_before_filter - len(facts) if point_in_time else 0,
                "query_time_ms": query_time_ms,
            },
        )

        return GraphResponse(
            nodes=all_nodes,
            edges=all_edges,
            clusters=clusters,
            metadata={
                "total_entities": len(entities),
                "total_facts": len(facts),
                "total_facts_unfiltered": total_facts_before_filter,
                "total_communities": len(communities),
                "total_episodes": len(episodes),
                "point_in_time": pit_str,
                "earliest_fact_date": earliest.isoformat() if earliest else None,
                "node_count": len(all_nodes),
                "edge_count": len(all_edges),
                "query_time_ms": query_time_ms,
            },
        )

    def _filter_by_center_entity(
        self,
        center_entity_id: str,
        max_depth: int,
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        facts: List[Fact],
    ) -> Tuple[List[GraphNode], List[GraphEdge]]:
        """BFS from center entity to find reachable nodes within max_depth hops."""
        # Build adjacency from facts (entity ID → set of connected entity IDs)
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for fact in facts:
            adjacency[fact.source_entity_id].add(fact.target_entity_id)
            adjacency[fact.target_entity_id].add(fact.source_entity_id)

        # BFS
        visited: Set[str] = {center_entity_id}
        frontier: Set[str] = {center_entity_id}
        for _ in range(max_depth):
            next_frontier: Set[str] = set()
            for eid in frontier:
                for neighbor in adjacency.get(eid, set()):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.add(neighbor)
            frontier = next_frontier
            if not frontier:
                break

        # Convert to graph node IDs
        reachable_entity_ids = {f"entity:{eid}" for eid in visited}

        # Also include community nodes whose members overlap
        reachable_node_ids = set(reachable_entity_ids)
        for node in nodes:
            if node.node_type == NodeType.COMMUNITY:
                member_ids = {
                    f"entity:{mid}"
                    for mid in node.metadata.get("member_entity_ids", [])
                }
                if member_ids & reachable_entity_ids:
                    reachable_node_ids.add(node.id)

        filtered_nodes = [n for n in nodes if n.id in reachable_node_ids]
        filtered_edges = [
            e for e in edges
            if e.from_id in reachable_node_ids and e.to_id in reachable_node_ids
        ]

        return filtered_nodes, filtered_edges

    def _build_community_clusters(
        self,
        communities: List[Any],
        nodes: List[GraphNode],
    ) -> List[GraphCluster]:
        """Build clusters from community membership (not topic-based)."""
        node_id_set = {n.id for n in nodes}
        clusters: List[GraphCluster] = []
        palette = list(CATEGORY_COLORS.values())

        for i, community in enumerate(communities):
            member_node_ids = [
                f"entity:{mid}" for mid in community.member_entity_ids
                if f"entity:{mid}" in node_id_set
            ]
            comm_node_id = f"community:{community.id}"
            if comm_node_id in node_id_set:
                member_node_ids.append(comm_node_id)

            if len(member_node_ids) >= 2:
                clusters.append(GraphCluster(
                    id=f"cluster:{community.id}",
                    label=community.label,
                    node_ids=member_node_ids,
                    color=palette[i % len(palette)],
                ))

        return clusters

    async def build_graph(
        self,
        limit: int = MAX_NODES,
        node_types: Optional[Set[str]] = None,
        center_topic: Optional[str] = None,
        sources: Optional[List[str]] = None,
    ) -> GraphResponse:
        """
        Build the full knowledge graph.

        Args:
            limit: Max memory chunks to query.
            node_types: Filter to specific node types (memory, topic, entity).
            center_topic: Focus on nodes related to this topic.
            sources: Filter by MemorySource values (e.g., ["conversation", "mail"]).

        Returns:
            GraphResponse with nodes, edges, clusters, and metadata.
        """
        start_time = time.time()

        try:
            memory_mgr = await self._get_memory_manager()
            results = await memory_mgr.search(
                query="*",
                limit=min(limit, MAX_NODES),
                semantic_threshold=0.0,
            )
            # Filter by source if specified
            if sources is not None:
                results = [
                    r for r in results
                    if r.chunk.metadata.source in sources
                ]
        except Exception as e:
            logger.warning(
                "Graph builder: memory search failed, returning empty graph",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return GraphResponse(
                nodes=[], edges=[], clusters=[],
                metadata={"error": type(e).__name__, "query_time_ms": 0},
            )

        if not results:
            return GraphResponse(
                nodes=[], edges=[], clusters=[],
                metadata={"total_chunks": 0, "query_time_ms": 0},
            )

        # Step 1: Build memory nodes
        memory_nodes = self._build_memory_nodes(results)

        # Step 2: Extract topic and entity nodes
        topic_nodes = self._build_topic_nodes(results)
        entity_nodes = self._build_entity_nodes(results)

        # Step 2b: Build principle nodes (approved only)
        principle_nodes = await self._build_principle_nodes()

        # Step 3: Filter by node_types if specified
        all_nodes: List[GraphNode] = []
        include_types = node_types or {"memory", "topic", "entity", "principle"}
        if "memory" in include_types:
            all_nodes.extend(memory_nodes)
        if "topic" in include_types:
            all_nodes.extend(topic_nodes)
        if "entity" in include_types:
            all_nodes.extend(entity_nodes)
        if "principle" in include_types:
            all_nodes.extend(principle_nodes)

        # Step 4: Filter by center_topic
        if center_topic:
            all_nodes = self._filter_by_topic(all_nodes, center_topic)

        # Step 5: Enforce node limit
        all_nodes = all_nodes[:MAX_NODES]

        # Step 6: Build edges
        node_ids = {n.id for n in all_nodes}
        edges = self._build_edges(all_nodes, results, node_ids)
        edges = edges[:MAX_EDGES]

        # Step 7: Compute layout
        self._compute_layout(all_nodes, edges)

        # Step 8: Cluster by dominant topic
        clusters = self._build_clusters(all_nodes)

        query_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            "Graph built",
            component=LogComponent.RESEARCH,
            data={
                "nodes": len(all_nodes),
                "edges": len(edges),
                "clusters": len(clusters),
                "query_time_ms": query_time_ms,
            },
        )

        return GraphResponse(
            nodes=all_nodes,
            edges=edges,
            clusters=clusters,
            metadata={
                "total_chunks": len(results),
                "node_count": len(all_nodes),
                "edge_count": len(edges),
                "query_time_ms": query_time_ms,
            },
        )

    # ── Node Builders ───────────────────────────────────

    def _build_memory_nodes(self, results: List[Any]) -> List[GraphNode]:
        """Build one GraphNode per memory chunk.

        Weight uses the importance score (stored in metadata.confidence since
        Sprint 16) blended with search relevance.  This means higher-importance
        memories render as larger nodes in the graph.
        """
        nodes = []
        for result in results:
            chunk = result.chunk
            importance = chunk.metadata.confidence if chunk.metadata else 0.5
            # Blend importance (70%) with search relevance (30%) for visual weight
            blended_weight = importance * 0.7 + result.relevance_score * 0.3
            nodes.append(GraphNode(
                id=chunk.id,
                content=chunk.content[:200],
                node_type=NodeType.MEMORY,
                category=chunk.chunk_type.value,
                label=chunk.content[:50].replace("\n", " "),
                confidence=importance,
                weight=max(blended_weight, 0.1),
                topics=list(chunk.tags.topics) if chunk.tags else [],
                entities=list(chunk.tags.entities) if chunk.tags else [],
                last_active=chunk.timestamp,
                metadata={
                    "session_id": chunk.session_id,
                    "chunk_type": chunk.chunk_type.value,
                    "scope": chunk.scope.value if chunk.scope else "session",
                    "importance": round(importance, 3),
                },
            ))
        return nodes

    def _build_topic_nodes(self, results: List[Any]) -> List[GraphNode]:
        """Build aggregated topic nodes from all chunks."""
        topic_counts: Counter = Counter()
        topic_chunks: Dict[str, List[str]] = defaultdict(list)

        for result in results:
            chunk = result.chunk
            for topic in (chunk.tags.topics if chunk.tags else []):
                topic_lower = topic.lower().strip()
                if topic_lower:
                    topic_counts[topic_lower] += 1
                    topic_chunks[topic_lower].append(chunk.id)

        nodes = []
        max_count = max(topic_counts.values()) if topic_counts else 1

        for topic, count in topic_counts.most_common(50):
            nodes.append(GraphNode(
                id=f"topic:{topic}",
                content=f"Topic: {topic} ({count} mentions)",
                node_type=NodeType.TOPIC,
                category="topic",
                label=topic.title(),
                confidence=min(count / max_count, 1.0),
                weight=min(count / max_count, 1.0),
                topics=[topic],
                metadata={"mention_count": count, "chunk_ids": topic_chunks[topic][:10]},
            ))
        return nodes

    def _build_entity_nodes(self, results: List[Any]) -> List[GraphNode]:
        """Build aggregated entity nodes from all chunks."""
        entity_counts: Counter = Counter()
        entity_chunks: Dict[str, List[str]] = defaultdict(list)

        for result in results:
            chunk = result.chunk
            for entity in (chunk.tags.entities if chunk.tags else []):
                entity_lower = entity.lower().strip()
                if entity_lower:
                    entity_counts[entity_lower] += 1
                    entity_chunks[entity_lower].append(chunk.id)

        nodes = []
        max_count = max(entity_counts.values()) if entity_counts else 1

        for entity, count in entity_counts.most_common(50):
            nodes.append(GraphNode(
                id=f"entity:{entity}",
                content=f"Entity: {entity} ({count} mentions)",
                node_type=NodeType.ENTITY,
                category="entity",
                label=entity.title(),
                confidence=min(count / max_count, 1.0),
                weight=min(count / max_count, 1.0),
                entities=[entity],
                metadata={"mention_count": count, "chunk_ids": entity_chunks[entity][:10]},
            ))
        return nodes

    async def _build_principle_nodes(self) -> List[GraphNode]:
        """Build graph nodes from approved principles."""
        try:
            from .database import get_research_database
            db = await get_research_database()
            principles = await db.list_principles(
                status=PrincipleStatus.APPROVED, limit=50
            )
        except Exception as e:
            logger.debug(
                "Could not load principles for graph",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__},
            )
            return []

        nodes = []
        for p in principles:
            nodes.append(GraphNode(
                id=f"principle:{p.id}",
                content=p.content,
                node_type=NodeType.PRINCIPLE,
                category="principle",
                label=p.content[:50].replace("\n", " "),
                confidence=p.confidence,
                weight=min(p.confidence + 0.2, 1.0),
                topics=p.topics,
                entities=p.entities,
                last_active=p.updated_at,
                metadata={
                    "domain": p.domain,
                    "status": p.status.value,
                    "source_chunk_ids": p.source_chunk_ids[:5],
                },
            ))
        return nodes

    def _filter_by_topic(self, nodes: List[GraphNode], topic: str) -> List[GraphNode]:
        """Keep nodes that are related to the given topic."""
        topic_lower = topic.lower()
        return [
            n for n in nodes
            if topic_lower in [t.lower() for t in n.topics]
            or topic_lower in n.label.lower()
            or topic_lower in n.content.lower()
        ]

    # ── Edge Builder ────────────────────────────────────

    def _build_edges(
        self,
        nodes: List[GraphNode],
        results: List[Any],
        valid_ids: Set[str],
    ) -> List[GraphEdge]:
        """
        Build edges between nodes.

        Edge types:
        - SHARED_TOPIC: Two memory nodes share a topic
        - SHARED_ENTITY: Two memory nodes share an entity
        - TOPIC_MEMBERSHIP: Memory node → topic node
        - ENTITY_MEMBERSHIP: Memory node → entity node
        """
        edges: List[GraphEdge] = []
        seen: Set[Tuple[str, str]] = set()

        # Memory-to-memory edges (shared topics/entities)
        memory_nodes = [n for n in nodes if n.node_type == NodeType.MEMORY]
        for i, node_a in enumerate(memory_nodes):
            for node_b in memory_nodes[i + 1:]:
                shared_topics = set(t.lower() for t in node_a.topics) & set(t.lower() for t in node_b.topics)
                shared_entities = set(e.lower() for e in node_a.entities) & set(e.lower() for e in node_b.entities)
                shared_count = len(shared_topics) + len(shared_entities)

                if shared_count > 0:
                    pair = (min(node_a.id, node_b.id), max(node_a.id, node_b.id))
                    if pair not in seen:
                        seen.add(pair)
                        weight = min(shared_count / 3.0, 1.0)
                        edge_type = EdgeType.SHARED_TOPIC if shared_topics else EdgeType.SHARED_ENTITY
                        edges.append(GraphEdge(
                            from_id=node_a.id,
                            to_id=node_b.id,
                            edge_type=edge_type,
                            weight=weight,
                            count=shared_count,
                        ))

        # Memory-to-topic membership edges
        topic_id_set = {n.id for n in nodes if n.node_type == NodeType.TOPIC}
        for node in memory_nodes:
            for topic in node.topics:
                topic_id = f"topic:{topic.lower().strip()}"
                if topic_id in topic_id_set and topic_id in valid_ids:
                    pair = (min(node.id, topic_id), max(node.id, topic_id))
                    if pair not in seen:
                        seen.add(pair)
                        edges.append(GraphEdge(
                            from_id=node.id,
                            to_id=topic_id,
                            edge_type=EdgeType.TOPIC_MEMBERSHIP,
                            weight=0.5,
                        ))

        # Memory-to-entity membership edges
        entity_id_set = {n.id for n in nodes if n.node_type == NodeType.ENTITY}
        for node in memory_nodes:
            for entity in node.entities:
                entity_id = f"entity:{entity.lower().strip()}"
                if entity_id in entity_id_set and entity_id in valid_ids:
                    pair = (min(node.id, entity_id), max(node.id, entity_id))
                    if pair not in seen:
                        seen.add(pair)
                        edges.append(GraphEdge(
                            from_id=node.id,
                            to_id=entity_id,
                            edge_type=EdgeType.ENTITY_MEMBERSHIP,
                            weight=0.5,
                        ))

        # Principle-to-source-chunk edges
        principle_nodes_list = [n for n in nodes if n.node_type == NodeType.PRINCIPLE]
        memory_id_set = {n.id for n in memory_nodes}
        for pnode in principle_nodes_list:
            source_ids = pnode.metadata.get("source_chunk_ids", [])
            for src_id in source_ids:
                if src_id in memory_id_set and src_id in valid_ids:
                    pair = (min(pnode.id, src_id), max(pnode.id, src_id))
                    if pair not in seen:
                        seen.add(pair)
                        edges.append(GraphEdge(
                            from_id=pnode.id,
                            to_id=src_id,
                            edge_type=EdgeType.PRINCIPLE_SOURCE,
                            weight=0.7,
                        ))

        return edges

    # ── Force-Directed Layout ───────────────────────────

    def _compute_layout(self, nodes: List[GraphNode], edges: List[GraphEdge]) -> None:
        """
        Force-directed 3D layout.

        Ported from MacNeuralNetViewModel.swift computeLayout().
        Same parameters: center attraction, node repulsion, link springs, damping.
        Modifies nodes in-place (sets position dict).
        """
        count = len(nodes)
        if count == 0:
            return

        # Initialize on random sphere
        positions: List[List[float]] = []
        for _ in range(count):
            theta = random.uniform(0, 2 * math.pi)
            phi = random.uniform(0, math.pi)
            r = 2.0
            positions.append([
                r * math.sin(phi) * math.cos(theta),
                r * math.sin(phi) * math.sin(theta),
                r * math.cos(phi),
            ])

        # Build index map for edge lookups
        node_index = {n.id: i for i, n in enumerate(nodes)}
        edge_pairs = []
        for edge in edges:
            from_idx = node_index.get(edge.from_id)
            to_idx = node_index.get(edge.to_id)
            if from_idx is not None and to_idx is not None and from_idx != to_idx:
                edge_pairs.append((from_idx, to_idx, edge.weight))

        # Simulation parameters (match Swift values)
        center_strength = 0.01
        repulsion_strength = 1.5
        link_strength = 0.05
        link_distance = 2.0
        damping = 0.9
        max_velocity = 2.0  # cap per step to prevent exponential blowup with many nodes

        velocities = [[0.0, 0.0, 0.0] for _ in range(count)]

        for _ in range(LAYOUT_ITERATIONS):
            # Center attraction
            for i in range(count):
                for d in range(3):
                    velocities[i][d] -= positions[i][d] * center_strength

            # Node repulsion (inverse square)
            for i in range(count):
                for j in range(i + 1, count):
                    dx = positions[i][0] - positions[j][0]
                    dy = positions[i][1] - positions[j][1]
                    dz = positions[i][2] - positions[j][2]
                    dist = max(math.sqrt(dx * dx + dy * dy + dz * dz), 0.1)
                    force = repulsion_strength / (dist * dist)
                    fx, fy, fz = dx / dist * force, dy / dist * force, dz / dist * force
                    velocities[i][0] += fx
                    velocities[i][1] += fy
                    velocities[i][2] += fz
                    velocities[j][0] -= fx
                    velocities[j][1] -= fy
                    velocities[j][2] -= fz

            # Link spring forces
            for from_idx, to_idx, weight in edge_pairs:
                dx = positions[to_idx][0] - positions[from_idx][0]
                dy = positions[to_idx][1] - positions[from_idx][1]
                dz = positions[to_idx][2] - positions[from_idx][2]
                dist = max(math.sqrt(dx * dx + dy * dy + dz * dz), 0.1)
                displacement = (dist - link_distance) * link_strength * weight
                fx = dx / dist * displacement
                fy = dy / dist * displacement
                fz = dz / dist * displacement
                velocities[from_idx][0] += fx
                velocities[from_idx][1] += fy
                velocities[from_idx][2] += fz
                velocities[to_idx][0] -= fx
                velocities[to_idx][1] -= fy
                velocities[to_idx][2] -= fz

            # Apply velocity with damping + per-node speed cap
            for i in range(count):
                speed = math.sqrt(sum(v * v for v in velocities[i]))
                if speed > max_velocity:
                    scale = max_velocity / speed
                    velocities[i] = [v * scale for v in velocities[i]]
                for d in range(3):
                    velocities[i][d] *= damping
                    positions[i][d] += velocities[i][d]

        # Normalize positions to target radius so camera always sees the graph.
        # With many nodes the simulation can produce large values even with the cap.
        max_dist = max(
            math.sqrt(p[0] ** 2 + p[1] ** 2 + p[2] ** 2) for p in positions
        ) if positions else 1.0
        target_radius = 6.0
        scale = target_radius / max(max_dist, target_radius)  # only shrink, never expand

        # Write positions back to nodes
        for i, node in enumerate(nodes):
            node.position = {
                "x": round(positions[i][0] * scale, 4),
                "y": round(positions[i][1] * scale, 4),
                "z": round(positions[i][2] * scale, 4),
            }

    # ── Clustering ──────────────────────────────────────

    def _build_clusters(self, nodes: List[GraphNode]) -> List[GraphCluster]:
        """
        Simple clustering by dominant topic.

        Groups memory nodes by their first topic. Topic and entity nodes
        join the cluster of their most-connected memory nodes.
        """
        topic_groups: Dict[str, List[str]] = defaultdict(list)

        for node in nodes:
            if node.topics:
                primary_topic = node.topics[0].lower()
                topic_groups[primary_topic].append(node.id)
            elif node.node_type in (NodeType.TOPIC, NodeType.ENTITY):
                topic_groups[node.label.lower()].append(node.id)

        # Only create clusters with 2+ members
        clusters = []
        palette = list(CATEGORY_COLORS.values())
        for i, (topic, member_ids) in enumerate(topic_groups.items()):
            if len(member_ids) >= 2:
                clusters.append(GraphCluster(
                    id=f"cluster:{topic}",
                    label=topic.title(),
                    node_ids=member_ids,
                    color=palette[i % len(palette)],
                ))

        return clusters
