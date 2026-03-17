"""
MemoryPruner — age + importance-gated soft-delete with undo capability.

Archives old, low-importance memory chunks by:
  1. Setting their status to ARCHIVED in SQLite
  2. Removing their embeddings from ChromaDB

Undo restores the SQLite status to ACTIVE, but ChromaDB embeddings are gone —
chunks won't appear in semantic search until re-embedded. The raw data is safe.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.memory.models import ConversationChunk, MemoryStatus

logger = get_logger()


class MemoryPruner:
    """Archives old, low-importance chunks with undo capability."""

    def __init__(
        self,
        memory_db: Any,
        vector_store: Any,
        learning_db: Any,
        config: Dict[str, Any],
    ) -> None:
        self._db = memory_db
        self._vector_store = vector_store
        self._learning_db = learning_db
        self._config = config.get("pruning", {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def find_eligible(self, user_id: str = "default") -> List[ConversationChunk]:
        """Find chunks eligible for pruning.

        Criteria (all must hold):
        - status NOT IN ('superseded', 'archived', 'committed', …protected)
        - chunk_type NOT IN protected_types
        - timestamp older than max_age_days
        - metadata.confidence < importance_threshold
        """
        max_age_days: int = self._config.get("max_age_days", 60)
        importance_threshold: float = self._config.get("importance_threshold", 0.2)
        protected_statuses: List[str] = self._config.get("protected_statuses", ["committed"])
        protected_types: List[str] = self._config.get("protected_types", ["system"])

        # Always exclude superseded and archived regardless of config
        excluded_statuses = list({"superseded", "archived"} | set(protected_statuses))
        excluded_types = list(set(protected_types))

        status_placeholders = ",".join("?" * len(excluded_statuses))
        type_placeholders = ",".join("?" * len(excluded_types))

        sql = f"""
            SELECT * FROM memory_chunks
            WHERE status NOT IN ({status_placeholders})
              AND chunk_type NOT IN ({type_placeholders})
              AND timestamp < datetime('now', '-{max_age_days} days')
              AND json_extract(metadata, '$.confidence') < ?
            ORDER BY timestamp ASC
        """
        params = tuple(excluded_statuses) + tuple(excluded_types) + (importance_threshold,)

        chunks: List[ConversationChunk] = []
        cursor = await self._db._connection.execute(sql, params)
        rows = await cursor.fetchall()
        for row in rows:
            chunks.append(ConversationChunk.from_sqlite_row(dict(row)))

        logger.info(
            f"MemoryPruner.find_eligible: found {len(chunks)} candidates",
            component=LogComponent.MEMORY,
            data={"user_id": user_id, "count": len(chunks)},
        )
        return chunks

    async def preview(self, user_id: str = "default") -> List[Dict[str, Any]]:
        """Dry-run: return eligible chunks as dicts without modifying anything."""
        eligible = await self.find_eligible(user_id=user_id)
        now = datetime.now(timezone.utc)
        return [
            {
                "id": c.id,
                "chunk_type": c.chunk_type.value,
                "importance": c.metadata.confidence,
                "age_days": (now - c.timestamp.replace(tzinfo=timezone.utc) if c.timestamp.tzinfo is None else now - c.timestamp).days,
                "status": c.status.value,
            }
            for c in eligible
        ]

    async def execute(self, user_id: str = "default") -> Dict[str, Any]:
        """Archive eligible chunks and remove them from ChromaDB.

        Steps:
        1. Find eligible chunks
        2. Set each to status=ARCHIVED in SQLite
        3. Batch-delete embeddings from ChromaDB
        4. Log an audit alert to learning_db
        5. Return stats
        """
        eligible = await self.find_eligible(user_id=user_id)

        if not eligible:
            logger.info(
                "MemoryPruner.execute: no eligible chunks to prune",
                component=LogComponent.MEMORY,
                data={"user_id": user_id},
            )
            return {"archived": 0}

        archived_ids: List[str] = []

        for chunk in eligible:
            chunk.status = MemoryStatus.ARCHIVED
            await self._db.update_chunk(chunk)
            archived_ids.append(chunk.id)

        # Batch remove embeddings from ChromaDB
        self._vector_store.delete_chunks(archived_ids)

        # Audit trail — log a trigger alert to the learning module
        try:
            from hestia.learning.models import TriggerAlert
            from uuid import uuid4

            alert = TriggerAlert(
                id=f"prune-{uuid4().hex[:12]}",
                user_id=user_id,
                trigger_name="memory_pruner",
                current_value=float(len(archived_ids)),
                threshold_value=0.0,
                direction="above",
                message=f"MemoryPruner archived {len(archived_ids)} chunks",
                timestamp=datetime.now(timezone.utc),
                acknowledged=False,
                cooldown_until=None,
            )
            await self._learning_db.store_trigger_alert(alert)
        except Exception:
            # Audit logging is best-effort — never block the prune operation
            logger.info(
                "MemoryPruner: audit log skipped (non-critical)",
                component=LogComponent.MEMORY,
            )

        logger.info(
            f"MemoryPruner.execute: archived {len(archived_ids)} chunks",
            component=LogComponent.MEMORY,
            data={"user_id": user_id, "archived": len(archived_ids)},
        )
        return {"archived": len(archived_ids)}

    async def undo(self, chunk_ids: List[str]) -> int:
        """Restore archived chunks to ACTIVE status.

        Note: ChromaDB embeddings were deleted during execute(). Chunks will
        not appear in semantic search until re-embedded, but all data is
        preserved in SQLite.

        Returns:
            Number of chunks successfully restored.
        """
        restored = 0
        for chunk_id in chunk_ids:
            chunk: Optional[ConversationChunk] = await self._db.get_chunk(chunk_id)
            if chunk is None:
                logger.info(
                    f"MemoryPruner.undo: chunk {chunk_id!r} not found, skipping",
                    component=LogComponent.MEMORY,
                )
                continue

            chunk.status = MemoryStatus.ACTIVE
            await self._db.update_chunk(chunk)
            restored += 1

        if restored:
            logger.info(
                f"MemoryPruner.undo: restored {restored} chunks to ACTIVE "
                f"(embeddings absent from ChromaDB — re-embed to restore search)",
                component=LogComponent.MEMORY,
                data={"restored": restored},
            )
        return restored
