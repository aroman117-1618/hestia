"""
Entity Registry — resolution, deduplication, and community detection.

Entity resolution pipeline:
1. Normalize name (lowercase, strip, remove underscores/parentheticals)
2. Exact canonical match via SQLite
3. Fuzzy match (Jaro-Winkler >= 0.88) against same-type entities
4. Create new entity if no match

Community detection uses label propagation on the fact adjacency graph.
No graph database required — runs on SQLite fact edges.
"""

import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set

from hestia.logging import LogComponent, get_logger

from .database import ResearchDatabase
from .models import Community, Entity, EntityType, FactStatus, SourceCategory

logger = get_logger()

MAX_LP_ITERATIONS = 20
FUZZY_MATCH_THRESHOLD = 0.93


def _normalize_name(name: str) -> str:
    """Normalize entity name for matching.

    Strips whitespace, lowercases, replaces underscores with spaces,
    and removes parenthetical suffixes like "(Head of CS)".
    """
    result = name.lower().strip()
    result = result.replace("_", " ")
    result = re.sub(r"\s*\([^)]*\)\s*$", "", result)
    result = re.sub(r"\s+", " ", result).strip()
    return result


def _jaro_winkler_similarity(s1: str, s2: str, winkler_prefix_weight: float = 0.1) -> float:
    """Compute Jaro-Winkler similarity between two strings.

    Returns a value between 0.0 (no similarity) and 1.0 (identical).
    Gives extra weight to common prefixes, making it ideal for name matching.
    """
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    match_window = max(len1, len2) // 2 - 1
    if match_window < 0:
        match_window = 0

    s1_matches = [False] * len1
    s2_matches = [False] * len2
    matches = 0
    transpositions = 0

    for i in range(len1):
        start = max(0, i - match_window)
        end = min(i + match_window + 1, len2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break

    if matches == 0:
        return 0.0

    k = 0
    for i in range(len1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1

    jaro = (matches / len1 + matches / len2 + (matches - transpositions / 2) / matches) / 3.0

    # Winkler modification: boost for common prefix (up to 4 chars)
    prefix_len = 0
    for i in range(min(4, len1, len2)):
        if s1[i] == s2[i]:
            prefix_len += 1
        else:
            break

    return jaro + prefix_len * winkler_prefix_weight * (1.0 - jaro)


class EntityRegistry:
    """Entity resolution and community detection on the fact graph."""

    def __init__(self, database: ResearchDatabase) -> None:
        self._db = database

    async def resolve_entity(
        self,
        name: str,
        entity_type: EntityType = EntityType.CONCEPT,
        source_category: SourceCategory = SourceCategory.CONVERSATION,
        user_id: str = "default",
    ) -> Entity:
        """Resolve a name to an existing or new entity.

        Steps:
        1. Normalize name (lowercase, strip, underscores, parentheticals)
        2. Exact canonical match in DB — return if found
        3. Fuzzy match (Jaro-Winkler >= 0.88) against same-type entities
        4. Create new entity if no match
        """
        canonical = name.lower().strip()
        normalized = _normalize_name(name)

        # 1. Exact match on canonical name
        existing = await self._db.find_entity_by_name(canonical)
        if existing is not None:
            return existing

        # 1b. Exact match on normalized name (catches underscore/parenthetical variants)
        if normalized != canonical:
            existing = await self._db.find_entity_by_name(normalized)
            if existing is not None:
                return existing

        # 2. Fuzzy match against same-type entities
        candidates = await self._db.list_entities(entity_type=entity_type, limit=500)
        best_match: Optional[Entity] = None
        best_score = 0.0
        for candidate in candidates:
            candidate_normalized = _normalize_name(candidate.name)
            score = _jaro_winkler_similarity(normalized, candidate_normalized)
            if score > best_score:
                best_match, best_score = candidate, score

        if best_match and best_score >= FUZZY_MATCH_THRESHOLD:
            logger.debug(
                "Fuzzy matched entity",
                component=LogComponent.RESEARCH,
                data={
                    "input": name,
                    "matched": best_match.name,
                    "score": round(best_score, 3),
                },
            )
            return best_match

        # 3. Create new entity
        entity = Entity.create(
            name=name,
            entity_type=entity_type,
            first_seen_source=source_category,
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
        5. Generate descriptive labels via LLM
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

            # Resolve member entity names for labeling
            member_names = await self._get_entity_names(member_ids)
            community_label = await self._generate_community_label(
                member_names, len(communities) + 1
            )

            community = Community.create(
                label=community_label,
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

    async def _get_entity_names(self, entity_ids: List[str]) -> List[str]:
        """Look up entity names by IDs."""
        names: List[str] = []
        for eid in entity_ids:
            entity = await self._db.find_entity_by_id(eid)
            if entity:
                names.append(entity.name)
        return names

    async def _generate_community_label(
        self, member_names: List[str], fallback_number: int
    ) -> str:
        """Generate a descriptive community label via LLM.

        Falls back to 'community-N' if LLM is unavailable or fails.
        """
        fallback = f"community-{fallback_number}"
        if not member_names:
            return fallback

        try:
            from hestia.inference import get_inference_client

            client = get_inference_client()
            names_str = ", ".join(member_names[:10])
            response = await client.complete(
                prompt=f"Entities in this cluster: {names_str}",
                system=(
                    "Generate a 2-4 word descriptive label that captures the common theme "
                    "of these related entities. Return JSON: {\"label\": \"...\"}\n\n"
                    "Examples:\n"
                    "Entities: Andrew, Sarah, Mike -> {\"label\": \"Social Circle\"}\n"
                    "Entities: Python, FastAPI, SQLite -> {\"label\": \"Tech Stack\"}\n"
                    "Entities: Apple, Google, Anthropic -> {\"label\": \"Tech Companies\"}\n"
                    "Entities: Running, Cycling, Swimming -> {\"label\": \"Fitness Activities\"}\n"
                    "Entities: Bitcoin, Ethereum, Coinbase -> {\"label\": \"Crypto Ecosystem\"}"
                ),
                think=False,
                force_tier="primary",
                format="json",
            )
            import json
            data = json.loads(response.content)
            label = data.get("label", "").strip()
            if label and len(label) <= 50:
                return label
        except Exception as e:
            logger.debug(
                "Community label generation failed, using fallback",
                component=LogComponent.RESEARCH,
                data={"error": type(e).__name__, "fallback": fallback},
            )

        return fallback
