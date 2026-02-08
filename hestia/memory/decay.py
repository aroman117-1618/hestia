"""
Temporal decay for Hestia memory relevance scores.

Applies exponential decay to memory search results based on age,
with configurable per-chunk-type decay rates. Facts and system
memories never decay; conversations decay normally.

Formula: adjusted_score = raw_score * e^(-lambda * age_days) * recency_boost
Clamped to [min_score_after_decay, 1.0].

Based on ADR-013 extension for temporal awareness.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

import yaml

from hestia.logging import get_logger, LogComponent
from hestia.memory.models import ChunkType


# Default decay rates per chunk type
DEFAULT_DECAY_RATES: Dict[str, float] = {
    "conversation": 0.02,
    "fact": 0.0,
    "preference": 0.005,
    "decision": 0.002,
    "action_item": 0.01,
    "research": 0.007,
    "system": 0.0,
}


@dataclass
class DecayConfig:
    """Configuration for temporal decay."""

    enabled: bool = True
    rates: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_DECAY_RATES))
    min_score_after_decay: float = 0.1
    recency_boost_hours: float = 24.0
    recency_boost_factor: float = 1.2

    @classmethod
    def from_yaml(cls, path: Path) -> "DecayConfig":
        """Load config from YAML file."""
        if not path.exists():
            return cls.default()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        decay_data = data.get("temporal_decay", {})
        return cls(
            enabled=decay_data.get("enabled", True),
            rates=decay_data.get("rates", dict(DEFAULT_DECAY_RATES)),
            min_score_after_decay=decay_data.get("min_score_after_decay", 0.1),
            recency_boost_hours=decay_data.get("recency_boost_hours", 24.0),
            recency_boost_factor=decay_data.get("recency_boost_factor", 1.2),
        )

    @classmethod
    def default(cls) -> "DecayConfig":
        """Create config with default values."""
        return cls()


class TemporalDecay:
    """
    Applies temporal decay to memory relevance scores.

    Each ChunkType has its own decay rate (lambda). A lambda of 0 means
    no decay (facts, system memories). Higher lambda means faster decay.

    The decay function is exponential: factor = e^(-lambda * age_days)

    Memories within the recency window get a boost multiplier.
    A minimum score floor prevents useful memories from disappearing entirely.
    """

    def __init__(self, config: Optional[DecayConfig] = None) -> None:
        """
        Initialize temporal decay.

        Args:
            config: Decay configuration. If None, loads from default path.
        """
        if config is None:
            config_path = Path(__file__).parent.parent / "config" / "memory.yaml"
            config = DecayConfig.from_yaml(config_path)

        self._config = config
        self._logger = get_logger()

    @property
    def enabled(self) -> bool:
        """Whether temporal decay is enabled."""
        return self._config.enabled

    def get_lambda(self, chunk_type: ChunkType) -> float:
        """
        Get the decay rate (lambda) for a chunk type.

        Args:
            chunk_type: The type of memory chunk.

        Returns:
            Decay rate. 0.0 means no decay.
        """
        return self._config.rates.get(chunk_type.value, 0.02)

    def calculate_half_life_days(self, chunk_type: ChunkType) -> Optional[float]:
        """
        Calculate the half-life in days for a given chunk type.

        Half-life is the number of days until the decay factor reaches 0.5.
        Formula: half_life = ln(2) / lambda

        Args:
            chunk_type: The type of memory chunk.

        Returns:
            Half-life in days, or None if lambda is 0 (no decay).
        """
        lam = self.get_lambda(chunk_type)
        if lam <= 0:
            return None
        return math.log(2) / lam

    def apply(
        self,
        relevance_score: float,
        chunk_type: ChunkType,
        chunk_timestamp: datetime,
        now: Optional[datetime] = None,
    ) -> float:
        """
        Apply temporal decay to a relevance score.

        Args:
            relevance_score: Raw relevance score from vector search (0.0-1.0).
            chunk_type: Type of the memory chunk.
            chunk_timestamp: When the memory was created.
            now: Current time. Defaults to UTC now.

        Returns:
            Decay-adjusted relevance score, clamped to
            [min_score_after_decay, 1.0].
        """
        if not self._config.enabled:
            return relevance_score

        if now is None:
            now = datetime.now(timezone.utc)

        # Ensure both timestamps are timezone-aware for comparison
        if chunk_timestamp.tzinfo is None:
            chunk_timestamp = chunk_timestamp.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Calculate age in days (fractional)
        age_seconds = max((now - chunk_timestamp).total_seconds(), 0.0)
        age_days = age_seconds / 86400.0

        # Get decay rate for this chunk type
        lam = self.get_lambda(chunk_type)

        # Exponential decay: factor = e^(-lambda * age_days)
        decay_factor = math.exp(-lam * age_days)

        # Recency boost for very recent memories
        age_hours = age_seconds / 3600.0
        if age_hours <= self._config.recency_boost_hours:
            boost = self._config.recency_boost_factor
        else:
            boost = 1.0

        # Apply decay and boost
        adjusted = relevance_score * decay_factor * boost

        # Clamp to [min_score, 1.0]
        adjusted = max(adjusted, self._config.min_score_after_decay)
        adjusted = min(adjusted, 1.0)

        return adjusted


# Module-level singleton
_temporal_decay: Optional[TemporalDecay] = None


def get_temporal_decay() -> TemporalDecay:
    """Get or create the default temporal decay instance."""
    global _temporal_decay
    if _temporal_decay is None:
        _temporal_decay = TemporalDecay()
    return _temporal_decay
