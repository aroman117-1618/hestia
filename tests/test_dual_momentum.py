"""Tests for Dual Momentum strategy."""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone

from hestia.trading.strategies.dual_momentum import DualMomentumStrategy
from hestia.trading.strategies.base import SignalType


class TestDualMomentum:
    def _make_data(self, prices, n=200):
        """Create OHLCV DataFrame from a price series."""
        if len(prices) < n:
            # Pad with flat prices at the start
            pad = [prices[0]] * (n - len(prices))
            prices = pad + list(prices)
        timestamps = [datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i) for i in range(len(prices))]
        return pd.DataFrame({
            "timestamp": timestamps,
            "open": prices,
            "high": [p * 1.01 for p in prices],
            "low": [p * 0.99 for p in prices],
            "close": prices,
            "volume": [1000] * len(prices),
        })

    def test_positive_momentum_buys(self):
        """When lookback return is positive, signal is BUY."""
        # Price rising from 100 to 120 over 200 candles
        prices = [100 + i * 0.1 for i in range(200)]
        df = self._make_data(prices)
        strategy = DualMomentumStrategy(config={"lookback_period": 168})
        signal = strategy.analyze(df, 1000.0)
        assert signal.signal_type == SignalType.BUY
        assert signal.confidence > 0.5

    def test_negative_momentum_sells(self):
        """When lookback return is negative, signal is SELL."""
        # Price falling from 120 to 100 over 200 candles
        prices = [120 - i * 0.1 for i in range(200)]
        df = self._make_data(prices)
        strategy = DualMomentumStrategy(config={"lookback_period": 168})
        signal = strategy.analyze(df, 1000.0)
        assert signal.signal_type == SignalType.SELL

    def test_insufficient_data_holds(self):
        """When not enough data for lookback, signal is HOLD."""
        prices = [100 + i for i in range(50)]
        df = self._make_data(prices, n=50)
        strategy = DualMomentumStrategy(config={"lookback_period": 168})
        signal = strategy.analyze(df, 1000.0)
        assert signal.signal_type == SignalType.HOLD

    def test_strong_momentum_high_confidence(self):
        """Strong positive momentum should produce higher confidence."""
        # 30% gain
        prices = [100] * 32 + [130] * 168
        df = self._make_data(prices)
        strategy = DualMomentumStrategy(config={"lookback_period": 168})
        signal = strategy.analyze(df, 1000.0)
        assert signal.signal_type == SignalType.BUY
        assert signal.confidence >= 0.7

    def test_weak_momentum_lower_confidence(self):
        """Weak positive momentum should produce lower confidence."""
        # 1% gain
        prices = [100] * 32 + [101] * 168
        df = self._make_data(prices)
        strategy = DualMomentumStrategy(config={"lookback_period": 168})
        signal = strategy.analyze(df, 1000.0)
        assert signal.signal_type == SignalType.BUY
        assert signal.confidence < 0.7

    def test_configurable_lookback(self):
        """Lookback period should be configurable."""
        strategy = DualMomentumStrategy(config={"lookback_period": 252})
        assert strategy._lookback_period == 252

    def test_position_size(self):
        """BUY signal should include quantity based on position_pct."""
        prices = [100 + i * 0.1 for i in range(200)]
        df = self._make_data(prices)
        strategy = DualMomentumStrategy(config={"lookback_period": 168, "position_pct": 0.15})
        signal = strategy.analyze(df, 10000.0)
        assert signal.signal_type == SignalType.BUY
        # 15% of $10K = $1500 at ~$120 price
        assert signal.quantity > 0

    def test_name_and_type(self):
        """Strategy name and type should be correct."""
        strategy = DualMomentumStrategy(config={"lookback_period": 168})
        assert "Dual Momentum" in strategy.name
        assert strategy.strategy_type == "dual_momentum"

    def test_accepts_timestamp(self):
        """Strategy should accept optional timestamp parameter."""
        prices = [100 + i * 0.1 for i in range(200)]
        df = self._make_data(prices)
        strategy = DualMomentumStrategy(config={"lookback_period": 168})
        ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        signal = strategy.analyze(df, 1000.0, timestamp=ts)
        assert signal.signal_type in (SignalType.BUY, SignalType.SELL, SignalType.HOLD)
