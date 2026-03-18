"""
Importance scoring for Hestia memory chunks.

Computes a composite importance score for each chunk using three signals:
  - Recency: linear decay from 1.0 (today) to min_importance at recency_max_days
  - Retrieval frequency: how often the chunk was returned in recent outcomes
  - Type bonus: configurable per-chunk-type boost

Formula: importance = w_r * recency + w_t * retrieval + w_b * type_bonus

The score is stored in ChunkMetadata.confidence (repurposed as importance score).
System and fact chunks are floored at system_floor to prevent critical memory pruning.

Config lives in hestia/config/memory.yaml under the `importance` key (Sprint 16).
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from hestia.logging import get_logger, LogComponent
from hestia.memory.models import ConversationChunk

logger = get_logger()

# Path to memory config, relative to repo root
_CONFIG_PATH = Path(__file__).parent.parent / "config" / "memory.yaml"

# Types that receive the system_floor guarantee
_FLOORED_TYPES = {"system", "fact"}


class ImportanceScorer:
    """
    Computes importance scores for memory chunks using retrieval feedback.

    Formula: importance = w_r * recency + w_t * retrieval + w_b * type_bonus + w_d * durability
    Where weights come from config/memory.yaml under the `importance` key.

    Sprint 20A adds a 4th signal — durability (from knowledge graph fact scoring).
    The durability weight defaults to 0.0 for backward compat (chunks without facts).
    When durability data is available, weights rebalance to 0.2R + 0.2F + 0.3T + 0.3D.
    """

    def __init__(
        self,
        memory_db: Any,
        outcome_db: Any,
        config: Dict[str, Any],
    ) -> None:
        self._memory_db = memory_db
        self._outcome_db = outcome_db

        imp = config.get("importance", {})
        weights = imp.get("weights", {})
        self._w_recency: float = float(weights.get("recency", 0.3))
        self._w_retrieval: float = float(weights.get("retrieval", 0.4))
        self._w_type: float = float(weights.get("type_bonus", 0.3))
        self._w_durability: float = float(weights.get("durability", 0.0))

        self._type_bonuses: Dict[str, float] = {
            k: float(v) for k, v in imp.get("type_bonuses", {}).items()
        }
        self._recency_max_days: int = int(imp.get("recency_max_days", 90))
        self._min_importance: float = float(imp.get("min_importance", 0.05))
        self._system_floor: float = float(imp.get("system_floor", 0.5))

    # ── Public API ──────────────────────────────────────────────────────────

    async def score_all(self, user_id: str = "default") -> Dict[str, Any]:
        """
        Batch-score all active chunks.

        Fetches active chunks from SQLite, computes retrieval scores from
        recent outcome metadata, updates ChunkMetadata.confidence in-place,
        and persists each chunk.

        Returns a stats dict:
          {
            "scored": int,
            "avg_importance": float,
            "below_threshold": int,
            "distribution": {"low": int, "mid": int, "high": int},
          }
        """
        chunks = await self._get_active_chunks()
        if not chunks:
            logger.info(
                "ImportanceScorer: no active chunks to score",
                component=LogComponent.MEMORY,
                data={"user_id": user_id},
            )
            return {
                "scored": 0,
                "avg_importance": 0.0,
                "below_threshold": 0,
                "distribution": {"low": 0, "mid": 0, "high": 0},
            }

        chunk_ids = [c.id for c in chunks]
        retrieval_scores = await self._compute_retrieval_scores(chunk_ids, user_id)

        now = datetime.now(timezone.utc)
        scores: List[float] = []

        # Pre-load durability scores from research DB if weight is configured
        durability_map: Dict[str, float] = {}
        if self._w_durability > 0:
            durability_map = await self._get_durability_scores(chunk_ids)

        for chunk in chunks:
            recency = self._compute_recency_score(chunk.timestamp)
            retrieval = retrieval_scores.get(chunk.id, 0.0)
            type_bonus = self._get_type_bonus(chunk.chunk_type.value)
            durability = durability_map.get(chunk.id, 0.0)
            importance = self._compute_importance(recency, retrieval, type_bonus, durability)

            # Apply floor for system/fact chunks
            if chunk.chunk_type.value in _FLOORED_TYPES:
                importance = max(importance, self._system_floor)

            chunk.metadata.confidence = importance
            scores.append(importance)

            await self._memory_db.update_chunk(chunk)

        n = len(scores)
        avg = sum(scores) / n
        threshold = 0.2
        below = sum(1 for s in scores if s < threshold)
        distribution = {
            "low": sum(1 for s in scores if s < 0.33),
            "mid": sum(1 for s in scores if 0.33 <= s < 0.66),
            "high": sum(1 for s in scores if s >= 0.66),
        }

        logger.info(
            f"ImportanceScorer: scored {n} chunks, avg={avg:.3f}",
            component=LogComponent.MEMORY,
            data={"user_id": user_id, "scored": n, "avg_importance": avg},
        )

        return {
            "scored": n,
            "avg_importance": avg,
            "below_threshold": below,
            "distribution": distribution,
        }

    # ── Core Scoring Helpers ────────────────────────────────────────────────

    def _compute_recency_score(self, chunk_timestamp: datetime) -> float:
        """
        Linear decay from 1.0 (today) to min_importance at recency_max_days.

        Chunks older than recency_max_days are clamped to min_importance.
        Future timestamps are treated as age=0.
        """
        now = datetime.now(timezone.utc)

        # Normalise to UTC-aware
        ts = chunk_timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        age_days = max(0.0, (now - ts).total_seconds() / 86400.0)

        if age_days >= self._recency_max_days:
            return self._min_importance

        # Linear interpolation: 1.0 at age=0, min_importance at age=recency_max_days
        score = 1.0 - (age_days / self._recency_max_days) * (1.0 - self._min_importance)
        return max(self._min_importance, min(1.0, score))

    async def _compute_retrieval_scores(
        self,
        chunk_ids: List[str],
        user_id: str,
    ) -> Dict[str, float]:
        """
        Aggregate retrieval frequency + outcome signals from outcome metadata.

        Queries outcomes for the last 30 days, parses `retrieved_chunk_ids`
        from each outcome's metadata JSON, tallies how often each chunk was
        retrieved, normalises to [0, 1], then applies signal bonuses/penalties:
          +0.3 if positive signal ratio > 0.6
          -0.2 if negative signal ratio > 0.6
        Both normalisation and bonuses are clamped to [0, 1].
        """
        outcomes = await self._outcome_db.get_outcomes(user_id=user_id, days=30)

        # Build per-chunk-id count and signal lists
        counts: Dict[str, int] = {cid: 0 for cid in chunk_ids}
        positive_counts: Dict[str, int] = {cid: 0 for cid in chunk_ids}
        negative_counts: Dict[str, int] = {cid: 0 for cid in chunk_ids}

        POSITIVE_SIGNALS = {"accepted", "long_gap", "session_end"}
        NEGATIVE_SIGNALS = {"quick_followup"}

        for outcome in outcomes:
            # metadata may be a dict or a JSON string
            raw_meta = outcome.get("metadata", {})
            if isinstance(raw_meta, str):
                try:
                    meta = json.loads(raw_meta)
                except (json.JSONDecodeError, TypeError):
                    meta = {}
            else:
                meta = raw_meta or {}

            retrieved = meta.get("retrieved_chunk_ids", [])
            signal = outcome.get("implicit_signal", "")

            for cid in retrieved:
                if cid not in counts:
                    continue
                counts[cid] += 1
                if signal in POSITIVE_SIGNALS:
                    positive_counts[cid] += 1
                elif signal in NEGATIVE_SIGNALS:
                    negative_counts[cid] += 1

        # Normalise counts
        all_counts = list(counts.values())
        non_zero = [c for c in all_counts if c > 0]

        if not non_zero:
            return {cid: 0.0 for cid in chunk_ids}

        # 95th-percentile normalisation when >20 data points, otherwise max
        if len(non_zero) > 20:
            sorted_counts = sorted(non_zero)
            p95_idx = int(len(sorted_counts) * 0.95)
            normaliser = sorted_counts[min(p95_idx, len(sorted_counts) - 1)]
        else:
            normaliser = max(non_zero)

        normaliser = max(normaliser, 1)  # guard against zero-division

        scores: Dict[str, float] = {}
        for cid in chunk_ids:
            raw = counts[cid]
            base = min(1.0, raw / normaliser)

            total = positive_counts[cid] + negative_counts[cid]
            if total > 0:
                pos_ratio = positive_counts[cid] / total
                neg_ratio = negative_counts[cid] / total
                if pos_ratio > 0.6:
                    base = min(1.0, base + 0.3)
                elif neg_ratio > 0.6:
                    base = max(0.0, base - 0.2)

            scores[cid] = base

        return scores

    def _get_type_bonus(self, chunk_type: str) -> float:
        """Look up type bonus from config. Defaults to 0.3 for unknown types."""
        return self._type_bonuses.get(chunk_type, 0.3)

    def _compute_importance(
        self,
        recency: float,
        retrieval: float,
        type_bonus: float,
        durability: float = 0.0,
    ) -> float:
        """
        Weighted composite score, clamped to [min_importance, 1.0].

        Formula (Sprint 20A): w_r*R + w_f*F + w_t*T + w_d*D
        Default weights: 0.2R + 0.2F + 0.3T + 0.3D (when durability enabled)
        Legacy weights: 0.3R + 0.4F + 0.3T + 0.0D (durability weight = 0)
        """
        raw = (
            self._w_recency * recency
            + self._w_retrieval * retrieval
            + self._w_type * type_bonus
            + self._w_durability * durability
        )
        return max(self._min_importance, min(1.0, raw))

    async def _get_durability_scores(
        self, chunk_ids: List[str]
    ) -> Dict[str, float]:
        """
        Look up max durability_score from facts linked to each chunk.

        Returns normalized 0-1 score (raw 0-3 / 3.0) per chunk ID.
        Chunks with no linked facts get 0.0.
        """
        try:
            from hestia.research.database import get_research_database
            db = await get_research_database()
            if not db._connection:
                return {}

            # Batch query: get max durability per source_chunk_id
            placeholders = ",".join("?" for _ in chunk_ids)
            cursor = await db._connection.execute(
                f"""SELECT source_chunk_id, MAX(durability_score)
                    FROM facts
                    WHERE source_chunk_id IN ({placeholders})
                      AND status = 'active'
                    GROUP BY source_chunk_id""",
                chunk_ids,
            )
            rows = await cursor.fetchall()
            return {
                row[0]: (row[1] or 0) / 3.0
                for row in rows
                if row[0]
            }
        except Exception:
            return {}

    # ── Internal Helpers ────────────────────────────────────────────────────

    async def _get_active_chunks(self) -> List[ConversationChunk]:
        """
        Fetch all non-superseded, non-archived chunks via direct SQL.

        Falls back gracefully to an empty list on errors.
        """
        try:
            # Access the underlying aiosqlite connection on MemoryDatabase
            conn = self._memory_db._connection
            chunks: List[ConversationChunk] = []
            async with conn.execute(
                "SELECT * FROM memory_chunks WHERE status NOT IN ('superseded', 'archived')"
            ) as cursor:
                async for row in cursor:
                    chunks.append(ConversationChunk.from_sqlite_row(dict(row)))
            return chunks
        except Exception as exc:
            logger.warning(
                "ImportanceScorer: failed to fetch active chunks",
                component=LogComponent.MEMORY,
                data={"error": type(exc).__name__},
            )
            return []


def load_importance_config(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load the importance section from memory.yaml. Returns empty dict on failure."""
    cfg_path = path or _CONFIG_PATH
    try:
        with open(cfg_path) as fh:
            data = yaml.safe_load(fh) or {}
        return data
    except (FileNotFoundError, yaml.YAMLError):
        return {}
