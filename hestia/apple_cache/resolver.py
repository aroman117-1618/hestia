"""
Smart resolver -- two-phase fuzzy entity resolution.

Phase 1: FTS5 candidate generation (fast, indexed)
Phase 2: rapidfuzz scoring for accurate ranking

Converts fuzzy user queries ("grocery list", "my dentist appt")
into resolved entity IDs without requiring LLM multi-step tool chains.
"""

from typing import List, Optional

from rapidfuzz import fuzz

from .database import AppleCacheDatabase
from .models import CachedEntity, EntitySource, ResolvedMatch


# Minimum score to consider a match valid
DEFAULT_MIN_SCORE = 50.0

# Maximum FTS5 candidates to pass to fuzzy scoring
FTS_CANDIDATE_LIMIT = 30


class SmartResolver:
    """
    Two-phase fuzzy entity resolution.

    1. FTS5 narrows the full dataset to ~30 candidates (indexed, <1ms)
    2. rapidfuzz scores those candidates for accurate ranking (<5ms)

    Falls back to scanning all entities if FTS5 returns nothing
    (handles typos that FTS5 prefix matching can't catch).
    """

    def __init__(self, database: AppleCacheDatabase) -> None:
        self._database = database

    async def resolve(
        self,
        query: str,
        source: Optional[EntitySource] = None,
        min_score: float = DEFAULT_MIN_SCORE,
        limit: int = 5,
    ) -> List[ResolvedMatch]:
        """
        Resolve a fuzzy query to ranked entity matches.

        Args:
            query: User's natural-language reference (e.g., "grocery list")
            source: Restrict to a specific Apple source
            min_score: Minimum fuzzy score (0-100) to include
            limit: Maximum results to return

        Returns:
            Ranked list of ResolvedMatch, best match first.
        """
        if not query or not query.strip():
            return []

        query = query.strip()

        # Phase 1: Check for exact title match first
        exact = await self._exact_match(query, source)
        if exact:
            return [ResolvedMatch(entity=exact, score=100.0, match_method="exact")]

        # Phase 2: FTS5 candidate generation
        candidates = await self._database.search_fts(
            query, source=source, limit=FTS_CANDIDATE_LIMIT
        )

        # Phase 3: If FTS5 found nothing, fall back to full scan
        if not candidates:
            candidates = await self._database.get_all(
                source=source, limit=200
            )

        if not candidates:
            return []

        # Phase 4: Score with rapidfuzz
        scored = self._score_candidates(query, candidates)

        # Filter and limit
        results = [m for m in scored if m.score >= min_score]
        return results[:limit]

    async def resolve_best(
        self,
        query: str,
        source: Optional[EntitySource] = None,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> Optional[ResolvedMatch]:
        """
        Resolve to the single best match, or None if no match above threshold.
        """
        matches = await self.resolve(query, source=source, min_score=min_score, limit=1)
        return matches[0] if matches else None

    async def resolve_container(
        self,
        query: str,
        source: EntitySource,
        min_score: float = DEFAULT_MIN_SCORE,
    ) -> Optional[str]:
        """
        Resolve a fuzzy container name (folder, calendar, list) to exact name.

        Useful for "reminders in my shopping list" -> "Shopping".
        """
        containers = await self._database.get_containers(source)
        if not containers:
            return None

        best_score = 0.0
        best_match = None

        for container in containers:
            score = fuzz.token_set_ratio(query.lower(), container.lower())
            if score > best_score and score >= min_score:
                best_score = score
                best_match = container

        return best_match

    # -- Internal ----------------------------------------------------------

    async def _exact_match(
        self, query: str, source: Optional[EntitySource] = None
    ) -> Optional[CachedEntity]:
        """Check for case-insensitive exact title match."""
        # Use FTS5 for initial candidates, then check exact
        candidates = await self._database.search_fts(
            query, source=source, limit=10
        )
        query_lower = query.lower()
        for c in candidates:
            if c.title.lower() == query_lower:
                return c
        return None

    @staticmethod
    def _score_candidates(
        query: str, candidates: List[CachedEntity]
    ) -> List[ResolvedMatch]:
        """
        Score candidates using rapidfuzz token_set_ratio.

        token_set_ratio is best for this use case because:
        - Handles word reordering: "list grocery" matches "Grocery List"
        - Handles partial matches: "grocery" matches "Grocery Shopping List"
        - Handles extra words: "my grocery" matches "Grocery List"
        """
        query_lower = query.lower()
        scored = []

        for entity in candidates:
            title_lower = entity.title.lower()

            # Use token_set_ratio for flexible matching
            score = fuzz.token_set_ratio(query_lower, title_lower)

            # Boost exact substring matches
            if query_lower in title_lower or title_lower in query_lower:
                score = min(100.0, score + 10.0)

            scored.append(ResolvedMatch(
                entity=entity,
                score=score,
                match_method="fuzzy",
            ))

        # Sort by score descending, then by title length ascending (prefer shorter/more specific)
        scored.sort(key=lambda m: (-m.score, len(m.entity.title)))

        return scored
