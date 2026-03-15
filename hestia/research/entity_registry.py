"""
Entity Registry — resolution, deduplication, and community detection.

Entity resolution pipeline:
1. Canonical name match (exact, case-insensitive) via SQLite
2. Create new entity if no match

Community detection uses label propagation on the fact adjacency graph.
No graph database required — runs on SQLite fact edges.
"""

from collections import Counter, defaultdict
from typing import Dict, List, Set

from hestia.logging import LogComponent, get_logger

from .database import ResearchDatabase
from .models import Community, Entity, EntityType, FactStatus

logger = get_logger()

MAX_LP_ITERATIONS = 20


class EntityRegistry:
    """Entity resolution and community detection on the fact graph."""

    def __init__(self, database: ResearchDatabase) -> None:
        self._db = database

    async def resolve_entity(
        self,
        name: str,
        entity_type: EntityType = EntityType.CONCEPT,
        user_id: str = "default",
    ) -> Entity:
        """Resolve a name to an existing or new entity.

        Steps:
        1. Canonical name = name.lower().strip()
        2. Look up by canonical name in DB — return if found
        3. Otherwise create and persist a new entity
        """
        canonical = name.lower().strip()

        existing = await self._db.find_entity_by_name(canonical)
        if existing is not None:
            return existing

        entity = Entity.create(
            name=name,
            entity_type=entity_type,
            user_id=user_id,
        )
        await self._db.create_entity(entity)
        logger.debug(
            "Created new entity",
            component=LogComponent.RESEARCH,
            data={"name": name, "type": entity_type.value, "id": entity.id},
        )
        return entity

    async def detect_communities(
        self,
        min_community_size: int = 2,
        user_id: str = "default",
    ) -> List[Community]:
        """Run label propagation on the fact adjacency graph.

        1. Build adjacency list from active facts
        2. Each entity starts with its own label
        3. Iterate: adopt majority label among neighbors
        4. Persist communities that meet min_community_size
        """
        facts = await self._db.list_facts(
            status=FactStatus.ACTIVE, limit=10000
        )

        if not facts:
            await self._db.delete_all_communities()
            return []

        # Build undirected adjacency list
        adjacency: Dict[str, Set[str]] = defaultdict(set)
        for fact in facts:
            adjacency[fact.source_entity_id].add(fact.target_entity_id)
            adjacency[fact.target_entity_id].add(fact.source_entity_id)

        entity_ids = list(adjacency.keys())

        # Initialize: each entity's label is itself
        labels: Dict[str, str] = {eid: eid for eid in entity_ids}

        # Label propagation
        for _ in range(MAX_LP_ITERATIONS):
            changed = False
            for eid in entity_ids:
                neighbor_labels = [labels[n] for n in adjacency[eid]]
                if not neighbor_labels:
                    continue
                counts = Counter(neighbor_labels)
                majority_label = counts.most_common(1)[0][0]
                if labels[eid] != majority_label:
                    labels[eid] = majority_label
                    changed = True
            if not changed:
                break

        # Group entities by label
        groups: Dict[str, List[str]] = defaultdict(list)
        for eid, label in labels.items():
            groups[label].append(eid)

        # Delete existing communities before writing new ones
        await self._db.delete_all_communities()

        # Create communities for groups meeting size threshold
        communities: List[Community] = []
        for label, member_ids in groups.items():
            if len(member_ids) < min_community_size:
                continue
            community = Community.create(
                label=f"community-{len(communities) + 1}",
                member_entity_ids=sorted(member_ids),
                user_id=user_id,
            )
            await self._db.create_community(community)

            # Update entity community references
            for eid in member_ids:
                await self._db.update_entity_community(eid, community.id)

            communities.append(community)

        logger.info(
            "Community detection complete",
            component=LogComponent.RESEARCH,
            data={
                "entity_count": len(entity_ids),
                "community_count": len(communities),
            },
        )
        return communities
