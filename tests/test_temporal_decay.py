"""
Tests for Hestia temporal decay module.

Tests cover:
- DecayConfig loading and defaults
- Per-chunk-type decay rate correctness
- Exponential decay math
- Recency boost behavior
- Min score floor enforcement
- MemoryManager integration with decay
"""

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hestia.memory.decay import (
    DEFAULT_DECAY_RATES,
    DecayConfig,
    TemporalDecay,
    get_temporal_decay,
)
from hestia.memory.models import (
    ChunkType,
    ConversationChunk,
    MemorySearchResult,
)


# ─── DecayConfig Tests ───


class TestDecayConfig:
    """Tests for DecayConfig dataclass."""

    def test_default_config(self) -> None:
        config = DecayConfig.default()
        assert config.enabled is True
        assert config.min_score_after_decay == 0.1
        assert config.recency_boost_hours == 24.0
        assert config.recency_boost_factor == 1.2
        assert config.rates["conversation"] == 0.02
        assert config.rates["fact"] == 0.0
        assert config.rates["system"] == 0.0

    def test_default_rates_match_module_constant(self) -> None:
        config = DecayConfig.default()
        assert config.rates == DEFAULT_DECAY_RATES

    def test_from_yaml_missing_file(self, tmp_path: Path) -> None:
        config = DecayConfig.from_yaml(tmp_path / "nonexistent.yaml")
        assert config.enabled is True
        assert config.rates == DEFAULT_DECAY_RATES

    def test_from_yaml_valid_file(self, tmp_path: Path) -> None:
        yaml_content = """
temporal_decay:
  enabled: false
  rates:
    conversation: 0.05
    fact: 0.0
    preference: 0.01
    decision: 0.003
    action_item: 0.02
    research: 0.015
    system: 0.0
  min_score_after_decay: 0.05
  recency_boost_hours: 12
  recency_boost_factor: 1.5
"""
        yaml_path = tmp_path / "memory.yaml"
        yaml_path.write_text(yaml_content)

        config = DecayConfig.from_yaml(yaml_path)
        assert config.enabled is False
        assert config.rates["conversation"] == 0.05
        assert config.min_score_after_decay == 0.05
        assert config.recency_boost_hours == 12.0
        assert config.recency_boost_factor == 1.5

    def test_from_yaml_empty_file(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "memory.yaml"
        yaml_path.write_text("")

        config = DecayConfig.from_yaml(yaml_path)
        assert config.enabled is True
        assert config.rates == DEFAULT_DECAY_RATES

    def test_from_yaml_partial_rates(self, tmp_path: Path) -> None:
        """If YAML provides partial rates, those are used (missing types fall back to get_lambda default)."""
        yaml_content = """
temporal_decay:
  rates:
    conversation: 0.1
"""
        yaml_path = tmp_path / "memory.yaml"
        yaml_path.write_text(yaml_content)

        config = DecayConfig.from_yaml(yaml_path)
        assert config.rates["conversation"] == 0.1
        # Other rates are not in the YAML, so they won't be in the dict
        assert "fact" not in config.rates


# ─── TemporalDecay Core Tests ───


class TestTemporalDecay:
    """Tests for TemporalDecay class."""

    def setup_method(self) -> None:
        self.config = DecayConfig.default()
        self.decay = TemporalDecay(config=self.config)
        self.now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)

    def test_disabled_returns_raw_score(self) -> None:
        config = DecayConfig(enabled=False)
        decay = TemporalDecay(config=config)
        timestamp = self.now - timedelta(days=365)
        result = decay.apply(0.9, ChunkType.CONVERSATION, timestamp, now=self.now)
        assert result == 0.9

    def test_zero_age_no_decay(self) -> None:
        """Memory created right now should have decay_factor = 1.0."""
        result = self.decay.apply(0.8, ChunkType.CONVERSATION, self.now, now=self.now)
        # With recency boost (within 24h): 0.8 * 1.0 * 1.2 = 0.96
        assert result == pytest.approx(0.96, abs=0.01)

    def test_zero_age_no_decay_fact(self) -> None:
        """Fact memory created right now — lambda=0, so factor=1.0, plus recency boost."""
        result = self.decay.apply(0.8, ChunkType.FACT, self.now, now=self.now)
        assert result == pytest.approx(0.96, abs=0.01)

    # ── Facts never decay ──

    def test_fact_no_decay_30_days(self) -> None:
        timestamp = self.now - timedelta(days=30)
        result = self.decay.apply(0.8, ChunkType.FACT, timestamp, now=self.now)
        # lambda=0 → factor=1.0, no recency boost (>24h)
        assert result == pytest.approx(0.8, abs=0.001)

    def test_fact_no_decay_365_days(self) -> None:
        timestamp = self.now - timedelta(days=365)
        result = self.decay.apply(0.8, ChunkType.FACT, timestamp, now=self.now)
        assert result == pytest.approx(0.8, abs=0.001)

    def test_system_no_decay_365_days(self) -> None:
        timestamp = self.now - timedelta(days=365)
        result = self.decay.apply(0.8, ChunkType.SYSTEM, timestamp, now=self.now)
        assert result == pytest.approx(0.8, abs=0.001)

    # ── Conversation decay ──

    def test_conversation_decay_7_days(self) -> None:
        timestamp = self.now - timedelta(days=7)
        result = self.decay.apply(0.8, ChunkType.CONVERSATION, timestamp, now=self.now)
        expected_factor = math.exp(-0.02 * 7)  # ~0.8694
        expected = 0.8 * expected_factor  # ~0.6955
        assert result == pytest.approx(expected, abs=0.01)

    def test_conversation_decay_35_days_half_life(self) -> None:
        """At ~35 days (half-life for conversation), factor should be ~0.5."""
        half_life = math.log(2) / 0.02  # ~34.66 days
        timestamp = self.now - timedelta(days=half_life)
        result = self.decay.apply(1.0, ChunkType.CONVERSATION, timestamp, now=self.now)
        assert result == pytest.approx(0.5, abs=0.01)

    def test_conversation_decay_90_days(self) -> None:
        timestamp = self.now - timedelta(days=90)
        result = self.decay.apply(0.8, ChunkType.CONVERSATION, timestamp, now=self.now)
        expected_factor = math.exp(-0.02 * 90)  # ~0.1653
        expected = max(0.8 * expected_factor, 0.1)  # ~0.1323
        assert result == pytest.approx(expected, abs=0.01)

    def test_conversation_decay_180_days_hits_floor(self) -> None:
        """Very old conversation should hit min_score floor."""
        timestamp = self.now - timedelta(days=180)
        result = self.decay.apply(0.5, ChunkType.CONVERSATION, timestamp, now=self.now)
        # 0.5 * e^(-0.02*180) = 0.5 * 0.0273 = 0.0137 → clamped to 0.1
        assert result == pytest.approx(0.1, abs=0.001)

    # ── Decision slow decay ──

    def test_decision_decay_30_days(self) -> None:
        timestamp = self.now - timedelta(days=30)
        result = self.decay.apply(0.8, ChunkType.DECISION, timestamp, now=self.now)
        expected_factor = math.exp(-0.002 * 30)  # ~0.9418
        expected = 0.8 * expected_factor  # ~0.7534
        assert result == pytest.approx(expected, abs=0.01)

    def test_decision_decay_347_days_half_life(self) -> None:
        half_life = math.log(2) / 0.002  # ~346.57 days
        timestamp = self.now - timedelta(days=half_life)
        result = self.decay.apply(1.0, ChunkType.DECISION, timestamp, now=self.now)
        assert result == pytest.approx(0.5, abs=0.01)

    # ── Preference medium decay ──

    def test_preference_decay_139_days_half_life(self) -> None:
        half_life = math.log(2) / 0.005  # ~138.63 days
        timestamp = self.now - timedelta(days=half_life)
        result = self.decay.apply(1.0, ChunkType.PREFERENCE, timestamp, now=self.now)
        assert result == pytest.approx(0.5, abs=0.01)

    # ── Action item decay ──

    def test_action_item_decay_69_days_half_life(self) -> None:
        half_life = math.log(2) / 0.01  # ~69.31 days
        timestamp = self.now - timedelta(days=half_life)
        result = self.decay.apply(1.0, ChunkType.ACTION_ITEM, timestamp, now=self.now)
        assert result == pytest.approx(0.5, abs=0.01)

    # ── Research decay ──

    def test_research_decay_99_days_half_life(self) -> None:
        half_life = math.log(2) / 0.007  # ~99.02 days
        timestamp = self.now - timedelta(days=half_life)
        result = self.decay.apply(1.0, ChunkType.RESEARCH, timestamp, now=self.now)
        assert result == pytest.approx(0.5, abs=0.01)

    # ── Recency boost ──

    def test_recency_boost_within_window(self) -> None:
        """Memory from 1 hour ago should get 1.2x boost."""
        timestamp = self.now - timedelta(hours=1)
        result = self.decay.apply(0.8, ChunkType.CONVERSATION, timestamp, now=self.now)
        # Decay is negligible for 1 hour, boost = 1.2
        age_days = 1.0 / 24.0
        expected_factor = math.exp(-0.02 * age_days)  # ~0.9992
        expected = 0.8 * expected_factor * 1.2  # ~0.959
        assert result == pytest.approx(expected, abs=0.01)

    def test_no_recency_boost_outside_window(self) -> None:
        """Memory from 48 hours ago should NOT get boost."""
        timestamp = self.now - timedelta(hours=48)
        result = self.decay.apply(0.8, ChunkType.CONVERSATION, timestamp, now=self.now)
        age_days = 2.0
        expected_factor = math.exp(-0.02 * age_days)  # ~0.9608
        expected = 0.8 * expected_factor  # ~0.7686 (no boost)
        assert result == pytest.approx(expected, abs=0.01)

    def test_recency_boost_at_boundary(self) -> None:
        """Memory at exactly 24 hours should still get boost (<=)."""
        timestamp = self.now - timedelta(hours=24)
        result = self.decay.apply(0.8, ChunkType.CONVERSATION, timestamp, now=self.now)
        age_days = 1.0
        expected_factor = math.exp(-0.02 * age_days)  # ~0.9802
        expected = 0.8 * expected_factor * 1.2  # ~0.941
        assert result == pytest.approx(expected, abs=0.01)

    # ── Min score floor ──

    def test_min_score_floor(self) -> None:
        timestamp = self.now - timedelta(days=500)
        result = self.decay.apply(0.3, ChunkType.CONVERSATION, timestamp, now=self.now)
        assert result == pytest.approx(0.1, abs=0.001)

    def test_min_score_floor_low_initial_score(self) -> None:
        timestamp = self.now - timedelta(days=100)
        result = self.decay.apply(0.15, ChunkType.CONVERSATION, timestamp, now=self.now)
        # 0.15 * e^(-0.02*100) = 0.15 * 0.1353 = 0.0203 → clamped to 0.1
        assert result == pytest.approx(0.1, abs=0.001)

    # ── Score capping at 1.0 ──

    def test_score_capped_at_1_with_boost(self) -> None:
        """Even with recency boost, score should not exceed 1.0."""
        timestamp = self.now - timedelta(minutes=5)
        result = self.decay.apply(0.95, ChunkType.FACT, timestamp, now=self.now)
        # 0.95 * 1.0 * 1.2 = 1.14 → capped to 1.0
        assert result == 1.0

    # ── Edge cases ──

    def test_future_timestamp_treated_as_zero_age(self) -> None:
        """If chunk timestamp is in the future (clock skew), treat as zero age."""
        timestamp = self.now + timedelta(hours=1)
        result = self.decay.apply(0.8, ChunkType.CONVERSATION, timestamp, now=self.now)
        # age_seconds = max(negative, 0) = 0 → factor = 1.0, boost = 1.2
        assert result == pytest.approx(0.96, abs=0.01)

    def test_naive_timestamp_treated_as_utc(self) -> None:
        """Naive timestamps should be treated as UTC."""
        naive_ts = datetime(2026, 2, 1, 12, 0, 0)
        naive_now = datetime(2026, 2, 8, 12, 0, 0)
        result = self.decay.apply(0.8, ChunkType.CONVERSATION, naive_ts, now=naive_now)
        age_days = 7.0
        expected_factor = math.exp(-0.02 * age_days)
        expected = 0.8 * expected_factor
        assert result == pytest.approx(expected, abs=0.01)

    def test_zero_initial_score(self) -> None:
        """Zero initial score should return min_score_after_decay."""
        timestamp = self.now - timedelta(days=10)
        result = self.decay.apply(0.0, ChunkType.CONVERSATION, timestamp, now=self.now)
        assert result == pytest.approx(0.1, abs=0.001)


# ─── Half-Life Calculation Tests ───


class TestHalfLifeCalculation:
    """Tests for half-life calculation utility."""

    def setup_method(self) -> None:
        self.decay = TemporalDecay(config=DecayConfig.default())

    def test_conversation_half_life(self) -> None:
        hl = self.decay.calculate_half_life_days(ChunkType.CONVERSATION)
        assert hl is not None
        assert hl == pytest.approx(34.66, abs=0.1)

    def test_fact_half_life_is_none(self) -> None:
        """Facts have lambda=0, so no half-life (infinite)."""
        hl = self.decay.calculate_half_life_days(ChunkType.FACT)
        assert hl is None

    def test_system_half_life_is_none(self) -> None:
        hl = self.decay.calculate_half_life_days(ChunkType.SYSTEM)
        assert hl is None

    def test_decision_half_life(self) -> None:
        hl = self.decay.calculate_half_life_days(ChunkType.DECISION)
        assert hl is not None
        assert hl == pytest.approx(346.57, abs=0.5)

    def test_preference_half_life(self) -> None:
        hl = self.decay.calculate_half_life_days(ChunkType.PREFERENCE)
        assert hl is not None
        assert hl == pytest.approx(138.63, abs=0.5)

    def test_action_item_half_life(self) -> None:
        hl = self.decay.calculate_half_life_days(ChunkType.ACTION_ITEM)
        assert hl is not None
        assert hl == pytest.approx(69.31, abs=0.5)

    def test_research_half_life(self) -> None:
        hl = self.decay.calculate_half_life_days(ChunkType.RESEARCH)
        assert hl is not None
        assert hl == pytest.approx(99.02, abs=0.5)


# ─── Lambda Lookup Tests ───


class TestGetLambda:
    """Tests for get_lambda method."""

    def setup_method(self) -> None:
        self.decay = TemporalDecay(config=DecayConfig.default())

    def test_all_chunk_types_have_lambda(self) -> None:
        for chunk_type in ChunkType:
            lam = self.decay.get_lambda(chunk_type)
            assert isinstance(lam, float)
            assert lam >= 0.0

    def test_unknown_chunk_type_defaults(self) -> None:
        """If a chunk type isn't in config rates, default to 0.02."""
        config = DecayConfig(rates={})
        decay = TemporalDecay(config=config)
        lam = decay.get_lambda(ChunkType.CONVERSATION)
        assert lam == 0.02


# ─── Integration: Decay Applied to Search Results ───


class TestDecayIntegration:
    """Tests verifying decay changes result ordering."""

    def setup_method(self) -> None:
        self.decay = TemporalDecay(config=DecayConfig.default())
        self.now = datetime(2026, 2, 8, 12, 0, 0, tzinfo=timezone.utc)

    def _make_chunk(
        self,
        chunk_id: str,
        chunk_type: ChunkType,
        age_days: float,
    ) -> ConversationChunk:
        """Helper to create a chunk with a specific age."""
        return ConversationChunk(
            id=chunk_id,
            session_id="session-test",
            timestamp=self.now - timedelta(days=age_days),
            content=f"Test content for {chunk_id}",
            chunk_type=chunk_type,
        )

    def test_recent_conversation_beats_old_conversation(self) -> None:
        """With equal raw scores, a recent conversation ranks higher."""
        recent = self._make_chunk("recent", ChunkType.CONVERSATION, age_days=1)
        old = self._make_chunk("old", ChunkType.CONVERSATION, age_days=60)

        score_recent = self.decay.apply(0.8, recent.chunk_type, recent.timestamp, now=self.now)
        score_old = self.decay.apply(0.8, old.chunk_type, old.timestamp, now=self.now)

        assert score_recent > score_old

    def test_fact_resists_old_conversation_with_higher_raw_score(self) -> None:
        """A fact from 6 months ago still beats a conversation from 6 months ago."""
        fact = self._make_chunk("fact", ChunkType.FACT, age_days=180)
        conv = self._make_chunk("conv", ChunkType.CONVERSATION, age_days=180)

        score_fact = self.decay.apply(0.8, fact.chunk_type, fact.timestamp, now=self.now)
        score_conv = self.decay.apply(0.8, conv.chunk_type, conv.timestamp, now=self.now)

        assert score_fact > score_conv

    def test_old_decision_still_relevant(self) -> None:
        """A decision from 100 days ago should still have meaningful score."""
        decision = self._make_chunk("dec", ChunkType.DECISION, age_days=100)
        score = self.decay.apply(0.9, decision.chunk_type, decision.timestamp, now=self.now)
        # e^(-0.002 * 100) = 0.8187 → 0.9 * 0.8187 = 0.737
        assert score > 0.7

    def test_decay_reorders_results(self) -> None:
        """Verify that decay actually changes the ordering of results."""
        # Old conversation has higher raw score
        old_high = self._make_chunk("old_high", ChunkType.CONVERSATION, age_days=90)
        # Recent conversation has slightly lower raw score
        recent_low = self._make_chunk("recent_low", ChunkType.CONVERSATION, age_days=1)

        # Raw scores: old_high > recent_low
        raw_old = 0.85
        raw_recent = 0.75

        score_old = self.decay.apply(raw_old, old_high.chunk_type, old_high.timestamp, now=self.now)
        score_recent = self.decay.apply(raw_recent, recent_low.chunk_type, recent_low.timestamp, now=self.now)

        # After decay, recent should win despite lower raw score
        # Old: 0.85 * e^(-0.02*90) = 0.85 * 0.165 = 0.140
        # Recent: 0.75 * e^(-0.02*1) * 1.2 = 0.75 * 0.980 * 1.2 = 0.882
        assert score_recent > score_old

    def test_mixed_types_decay_correctly(self) -> None:
        """Different chunk types with same age and raw score produce different adjusted scores."""
        age_days = 60.0
        raw_score = 0.8

        scores: Dict[str, float] = {}
        for chunk_type in [ChunkType.CONVERSATION, ChunkType.FACT, ChunkType.DECISION, ChunkType.PREFERENCE]:
            chunk = self._make_chunk(chunk_type.value, chunk_type, age_days)
            scores[chunk_type.value] = self.decay.apply(
                raw_score, chunk.chunk_type, chunk.timestamp, now=self.now
            )

        # Fact should have highest score (no decay)
        assert scores["fact"] == pytest.approx(0.8, abs=0.001)
        # Decision should be next (slowest decay)
        assert scores["decision"] > scores["preference"]
        # Preference should beat conversation
        assert scores["preference"] > scores["conversation"]


# ─── Singleton Tests ───


class TestSingleton:
    """Tests for module-level singleton."""

    def test_get_temporal_decay_returns_instance(self) -> None:
        import hestia.memory.decay as decay_module
        # Reset singleton
        decay_module._temporal_decay = None
        instance = get_temporal_decay()
        assert isinstance(instance, TemporalDecay)
        # Calling again returns same instance
        assert get_temporal_decay() is instance
        # Reset to not affect other tests
        decay_module._temporal_decay = None
