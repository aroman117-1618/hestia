"""Memory health monitoring — daily cross-system diagnostics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from hestia.logging import get_logger, LogComponent
from hestia.learning.models import MemoryHealthSnapshot


logger = get_logger()


class MemoryHealthMonitor:
    """Collects daily health snapshots across ChromaDB + knowledge graph."""

    def __init__(
        self,
        memory_manager: Any,
        research_db: Any,
        learning_db: Any,
    ) -> None:
        self._memory_manager = memory_manager
        self._research_db = research_db
        self._learning_db = learning_db

    async def collect_snapshot(self, user_id: str) -> MemoryHealthSnapshot:
        """Collect and store a memory health snapshot."""
        logger.info(
            "Collecting memory health snapshot",
            component=LogComponent.LEARNING,
            data={"user_id": user_id},
        )

        # ChromaDB chunk count
        chunk_count = 0
        try:
            chunk_count = self._memory_manager._vector_store.count()
        except Exception:
            pass

        # Chunk count by source
        chunk_count_by_source: Dict[str, int] = {}
        try:
            chunk_count_by_source = await self._get_chunk_counts_by_source()
        except Exception:
            pass

        # Redundancy estimate (placeholder — needs ChromaDB sampling)
        redundancy_pct = 0.0

        # Knowledge graph stats
        entity_count = 0
        fact_count = 0
        stale_entity_count = 0
        contradiction_count = 0
        community_count = 0

        try:
            entity_count = await self._research_db.count_entities()
        except Exception:
            pass

        try:
            fact_count = await self._research_db.count_facts()
        except Exception:
            pass

        try:
            communities = await self._research_db.list_communities(limit=1000, offset=0)
            community_count = len(communities)
        except Exception:
            pass

        try:
            from hestia.research.models import FactStatus
            contradiction_count = await self._research_db.count_facts(
                status=FactStatus.CONTRADICTED
            )
        except Exception:
            pass

        snapshot = MemoryHealthSnapshot(
            id=str(uuid.uuid4()),
            user_id=user_id,
            timestamp=datetime.now(timezone.utc),
            chunk_count=chunk_count,
            chunk_count_by_source=chunk_count_by_source,
            redundancy_estimate_pct=redundancy_pct,
            entity_count=entity_count,
            fact_count=fact_count,
            stale_entity_count=stale_entity_count,
            contradiction_count=contradiction_count,
            community_count=community_count,
        )

        await self._learning_db.store_health_snapshot(snapshot)

        logger.info(
            "Memory health snapshot stored",
            component=LogComponent.LEARNING,
            data={
                "user_id": user_id,
                "chunk_count": chunk_count,
                "entity_count": entity_count,
            },
        )

        return snapshot

    async def _get_chunk_counts_by_source(self) -> Dict[str, int]:
        """Count chunks grouped by source metadata."""
        try:
            db = self._memory_manager._db
            cursor = await db.execute(
                "SELECT json_extract(metadata, '$.source') as source, COUNT(*) "
                "FROM memory_chunks GROUP BY source"
            )
            rows = await cursor.fetchall()
            return {(row[0] or "unknown"): row[1] for row in rows}
        except Exception:
            return {}
