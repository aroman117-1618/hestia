"""
MemoryConsolidator — embedding-similarity dedup for Hestia memory lifecycle.

Detects near-duplicate memory chunks via ChromaDB embedding similarity and
marks the lower-importance chunk as SUPERSEDED, pointing it at the survivor.

Design:
- Non-LLM by default (ImportanceBasedMerge) — fast on M1 hardware.
- Pluggable MergeStrategy protocol allows LLM-based merging on M5 Ultra.
- Dry-run first: preview() / execute(dry_run=True) never write to the DB.
- Capped at max_merges_per_run per execution to bound runtime.
"""

from typing import Any, Dict, List, Optional, Tuple

from hestia.logging import get_logger, LogComponent
from hestia.memory.models import ConversationChunk, MemoryStatus


logger = get_logger()


# ---------------------------------------------------------------------------
# Strategy protocol
# ---------------------------------------------------------------------------


class MergeStrategy:
    """Pluggable merge strategy.

    Non-LLM (ImportanceBasedMerge) for M1, LLM-backed for M5 Ultra.
    Implement select_survivor() to swap in a custom strategy.
    """

    def select_survivor(
        self, chunk_a: ConversationChunk, chunk_b: ConversationChunk
    ) -> str:
        """Return the ID of the chunk to keep.

        Args:
            chunk_a: First candidate chunk.
            chunk_b: Second candidate chunk.

        Returns:
            ID of the chunk that should survive consolidation.
        """
        raise NotImplementedError


class ImportanceBasedMerge:
    """Default strategy: keep the higher-confidence (importance) chunk.

    Ties go to chunk_a for deterministic behaviour.
    """

    def select_survivor(
        self, chunk_a: ConversationChunk, chunk_b: ConversationChunk
    ) -> str:
        if chunk_a.metadata.confidence >= chunk_b.metadata.confidence:
            return chunk_a.id
        return chunk_b.id


# ---------------------------------------------------------------------------
# Consolidator
# ---------------------------------------------------------------------------


class MemoryConsolidator:
    """Detects and merges near-duplicate memory chunks.

    Algorithm (find_candidates):
      1. Sample up to sample_size active chunk IDs from SQLite.
      2. For each, fetch its embedding from ChromaDB.
      3. Query ChromaDB for top-5 similar chunks (excluding self).
      4. Filter by similarity threshold and optionally by chunk_type.
      5. Deduplicate pairs (A, B) == (B, A) via frozenset.

    Algorithm (execute):
      For each candidate pair:
        - Load both chunks from SQLite.
        - Select survivor via strategy.
        - Mark loser SUPERSEDED with supersedes = survivor.id.
        - Write loser back to SQLite (survivor unchanged).
    """

    def __init__(
        self,
        memory_db: Any,
        vector_store: Any,
        config: Dict[str, Any],
        strategy: Optional[Any] = None,
    ) -> None:
        self._db = memory_db
        self._vector_store = vector_store
        self._config = config.get("consolidation", {})
        self._strategy: Any = strategy if strategy is not None else ImportanceBasedMerge()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def find_candidates(self) -> List[Tuple[str, str, float]]:
        """Sample active chunks and return near-duplicate pairs.

        Returns:
            List of (id_a, id_b, similarity_score) tuples.
        """
        threshold: float = self._config.get("similarity_threshold", 0.90)
        sample_size: int = self._config.get("sample_size", 50)
        require_same_type: bool = self._config.get("require_same_type", True)

        # 1. Sample random active chunk IDs from SQLite
        sample_sql = (
            f"SELECT id FROM memory_chunks "
            f"WHERE status NOT IN ('superseded', 'archived') "
            f"ORDER BY RANDOM() LIMIT {sample_size}"
        )
        async with self._db._connection.execute(sample_sql) as cursor:
            rows = await cursor.fetchall()

        chunk_ids = [row[0] for row in rows]
        if not chunk_ids:
            return []

        seen_pairs: set = set()
        candidates: List[Tuple[str, str, float]] = []

        for chunk_id in chunk_ids:
            # 2. Get embedding from ChromaDB
            result = self._vector_store.collection.get(
                ids=[chunk_id], include=["embeddings"]
            )
            embeddings = result.get("embeddings") or []
            if not embeddings or embeddings[0] is None:
                continue
            embedding = embeddings[0]

            # 3. Find similar chunks (top-5, score >= threshold)
            similar = self._vector_store.search_by_embedding(
                embedding, n_results=5, min_score=threshold
            )

            for other_id, score in similar:
                if other_id == chunk_id:
                    continue

                # Guard: enforce threshold even if vector store doesn't filter
                if score < threshold:
                    continue

                # 5. Deduplicate pairs
                pair_key = frozenset({chunk_id, other_id})
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # 4. Optionally filter by chunk_type
                if require_same_type:
                    chunk_a = await self._db.get_chunk(chunk_id)
                    chunk_b = await self._db.get_chunk(other_id)
                    if chunk_a is None or chunk_b is None:
                        continue
                    if chunk_a.chunk_type != chunk_b.chunk_type:
                        continue

                candidates.append((chunk_id, other_id, score))

        logger.info(
            f"MemoryConsolidator: found {len(candidates)} candidate pairs from "
            f"{len(chunk_ids)} sampled chunks",
            component=LogComponent.MEMORY,
            data={"candidates": len(candidates), "sampled": len(chunk_ids)},
        )
        return candidates

    async def preview(self) -> Dict[str, Any]:
        """Return candidate pairs without modifying the database.

        Returns:
            Dict with 'candidates' count and 'pairs' list.
        """
        candidates = await self.find_candidates()
        return {
            "mode": "preview",
            "candidates": len(candidates),
            "pairs": [
                {"id_a": a, "id_b": b, "similarity": round(score, 4)}
                for a, b, score in candidates
            ],
        }

    async def execute(self, dry_run: bool = True) -> Dict[str, Any]:
        """Run consolidation, marking losers as SUPERSEDED.

        Args:
            dry_run: If True, compute stats but do not write to the database.

        Returns:
            Dict with 'mode', 'candidates', and 'merged' counts.
        """
        candidates = await self.find_candidates()
        max_merges: int = self._config.get("max_merges_per_run", 100)

        # Cap at max_merges_per_run
        to_process = candidates[:max_merges]

        merged = 0
        for id_a, id_b, _score in to_process:
            chunk_a = await self._db.get_chunk(id_a)
            chunk_b = await self._db.get_chunk(id_b)

            if chunk_a is None or chunk_b is None:
                continue

            survivor_id = self._strategy.select_survivor(chunk_a, chunk_b)
            loser = chunk_a if chunk_b.id == survivor_id else chunk_b

            if not dry_run:
                loser.status = MemoryStatus.SUPERSEDED
                loser.supersedes = survivor_id
                await self._db.update_chunk(loser)
                logger.debug(
                    f"Consolidated chunk {loser.id} → superseded by {survivor_id}",
                    component=LogComponent.MEMORY,
                    data={"loser": loser.id, "survivor": survivor_id},
                )

            merged += 1

        mode = "dry_run" if dry_run else "execute"
        logger.info(
            f"MemoryConsolidator ({mode}): merged={merged} candidates={len(candidates)}",
            component=LogComponent.MEMORY,
            data={"mode": mode, "merged": merged, "candidates": len(candidates)},
        )

        return {
            "mode": mode,
            "candidates": len(candidates),
            "merged": merged,
        }
