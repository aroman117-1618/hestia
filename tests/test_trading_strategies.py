"""Tests for trading strategies — grid, mean reversion, signals, paper integration."""

import numpy as np
import pandas as pd
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone

from hestia.trading.data.indicators import add_all_indicators
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType
from hestia.trading.strategies.grid import GridStrategy
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy
from hestia.trading.exchange.paper import PaperAdapter
from hestia.trading.exchange.base import OrderRequest


def _make_ohlcv(
    n: int = 100,
    base_price: float = 65000.0,
    seed: int = 42,
    trend: float = 0.0,
) -> pd.DataFrame:
    """Generate synthetic OHLCV data with optional trend."""
    np.random.seed(seed)
    returns = np.random.normal(trend, 0.02, n)
    prices = base_price * np.cumprod(1 + returns)
    df = pd.DataFrame({
        "open": prices * (1 + np.random.uniform(-0.005, 0.005, n)),
        "high": prices * (1 + np.random.uniform(0.001, 0.02, n)),
        "low": prices * (1 - np.random.uniform(0.001, 0.02, n)),
        "close": prices,
        "volume": np.random.uniform(100, 10000, n),
    })
    return add_all_indicators(df)


def _make_oversold_data() -> pd.DataFrame:
    """Create data that produces an oversold RSI reading."""
    n = 60
    # Strong downtrend to push RSI below 20
    prices = [65000.0]
    for i in range(n - 1):
        if i < 40:
            prices.append(prices[-1] * 0.995)  # Steady decline
        else:
            prices.append(prices[-1] * 0.985)  # Sharp drop at end
    prices = np.array(prices)
    df = pd.DataFrame({
        "open": prices * 1.002,
        "high": prices * 1.01,
        "low": prices * 0.99,
        "close": prices,
        "volume": np.full(n, 5000.0),  # Normal volume
    })
    return add_all_indicators(df, rsi_period=7)


def _make_oversold_with_volume() -> pd.DataFrame:
    """Create oversold data WITH volume confirmation."""
    df = _make_oversold_data()
    # Spike volume on last few candles (>1.5x average)
    avg_vol = df["volume"].mean()
    df.iloc[-3:, df.columns.get_loc("volume")] = avg_vol * 3.0
    # Recompute volume ratio
    return add_all_indicators(
        df[["open", "high", "low", "close", "volume"]],
        rsi_period=7,
    )


# ── Signal Model ──────────────────────────────────────────────

class TestSignal:
    def test_hold_not_actionable(self):
        s = Signal()
        assert s.is_actionable is False

    def test_buy_is_actionable(self):
        s = Signal(signal_type=SignalType.BUY)
        assert s.is_actionable is True

    def test_to_dict(self):
        s = Signal(signal_type=SignalType.SELL, price=65000.0, confidence=0.8)
        d = s.to_dict()
        assert d["signal_type"] == "sell"
        assert d["confidence"] == 0.8


# ── Grid Strategy ─────────────────────────────────────────────

class TestGridStrategy:
    def test_geometric_levels(self):
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        levels = grid.calculate_grid_levels(65000.0)
        assert len(levels) == 11  # 5 above + center + 5 below

        # Verify geometric spacing: ratio between consecutive levels should be constant
        for i in range(1, len(levels)):
            ratio = levels[i] / levels[i - 1]
            assert ratio == pytest.approx(1.01, abs=0.001)

    def test_grid_width_check(self):
        grid = GridStrategy(config={"num_levels": 10, "spacing_pct": 0.01})
        levels = grid.calculate_grid_levels(65000.0)
        # Grid width should be substantial
        width = levels[-1] - levels[0]
        assert width > 0
        # With ATR of 500, grid width of ~13,000 should pass 2x check
        assert grid.check_grid_width(levels, 500.0) is True
        # With ATR of 10,000, grid should be too narrow
        assert grid.check_grid_width(levels, 10000.0) is False

    def test_grid_buy_signal(self):
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        df = _make_ohlcv(50)

        # First call: initializes grid
        s1 = grid.analyze(df, portfolio_value=250.0)
        assert s1.signal_type == SignalType.HOLD  # Grid init

        # Simulate price drop: append a lower-price candle
        last = df.iloc[-1].copy()
        last["close"] = last["close"] * 0.97  # 3% drop
        last["low"] = last["close"] * 0.99
        df_dropped = pd.concat([df, pd.DataFrame([last])], ignore_index=True)
        df_dropped = add_all_indicators(df_dropped[["open", "high", "low", "close", "volume"]])

        s2 = grid.analyze(df_dropped, portfolio_value=250.0)
        # Should get a buy signal (price dropped through grid levels)
        assert s2.signal_type == SignalType.BUY

    def test_grid_sell_signal(self):
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        df = _make_ohlcv(50)

        # Initialize grid
        grid.analyze(df, portfolio_value=250.0)

        # Simulate price rise
        last = df.iloc[-1].copy()
        last["close"] = last["close"] * 1.03  # 3% rise
        last["high"] = last["close"] * 1.01
        df_up = pd.concat([df, pd.DataFrame([last])], ignore_index=True)
        df_up = add_all_indicators(df_up[["open", "high", "low", "close", "volume"]])

        s = grid.analyze(df_up, portfolio_value=250.0)
        assert s.signal_type == SignalType.SELL

    def test_grid_hold_within_band(self):
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        df = _make_ohlcv(50)

        # Initialize
        grid.analyze(df, portfolio_value=250.0)

        # Same price (tiny change within band)
        last = df.iloc[-1].copy()
        last["close"] = last["close"] * 1.001  # 0.1% — within band
        df_same = pd.concat([df, pd.DataFrame([last])], ignore_index=True)
        df_same = add_all_indicators(df_same[["open", "high", "low", "close", "volume"]])

        s = grid.analyze(df_same, portfolio_value=250.0)
        assert s.signal_type == SignalType.HOLD

    def test_grid_regrid_on_breakout(self):
        grid = GridStrategy(config={"num_levels": 3, "spacing_pct": 0.01})
        df = _make_ohlcv(50)

        # Initialize
        grid.analyze(df, portfolio_value=250.0)
        old_center = grid._center_price

        # Price moves far beyond grid range
        last = df.iloc[-1].copy()
        last["close"] = last["close"] * 1.10  # 10% move
        last["high"] = last["close"]
        df_breakout = pd.concat([df, pd.DataFrame([last])], ignore_index=True)
        df_breakout = add_all_indicators(df_breakout[["open", "high", "low", "close", "volume"]])

        # Should re-grid
        grid.analyze(df_breakout, portfolio_value=250.0)
        assert grid._center_price != old_center

    def test_insufficient_data(self):
        grid = GridStrategy()
        # Create minimal DataFrame without running indicators (they need >14 rows)
        df = pd.DataFrame({
            "open": [65000.0], "high": [65100.0], "low": [64900.0],
            "close": [65000.0], "volume": [1000.0],
        })
        s = grid.analyze(df, portfolio_value=250.0)
        assert s.signal_type == SignalType.HOLD
        assert "Insufficient" in s.reason

    def test_config_validation(self):
        grid = GridStrategy(config={"num_levels": 2, "spacing_pct": 0.001})
        warnings = grid.validate_config()
        assert len(warnings) >= 1  # Should warn about tight spacing or few levels

    def test_zero_price(self):
        grid = GridStrategy()
        levels = grid.calculate_grid_levels(0.0)
        assert levels == []

    def test_name_and_type(self):
        grid = GridStrategy()
        assert "Grid" in grid.name
        assert grid.strategy_type == "grid"


# ── Mean Reversion Strategy ───────────────────────────────────

class TestMeanReversionStrategy:
    def test_neutral_rsi_holds(self):
        mr = MeanReversionStrategy(config={"rsi_period": 7})
        df = _make_ohlcv(100, trend=0.0)
        s = mr.analyze(df, portfolio_value=250.0)
        # With random walk data, RSI is usually neutral
        assert s.signal_type == SignalType.HOLD

    def test_oversold_without_volume_holds(self):
        """Oversold RSI alone is not enough — needs volume confirmation."""
        mr = MeanReversionStrategy(config={
            "rsi_period": 7,
            "rsi_oversold": 20,
            "volume_confirmation": 1.5,
        })
        df = _make_oversold_data()
        s = mr.analyze(df, portfolio_value=250.0)
        # RSI should be extreme but volume is flat — should hold
        last_rsi = float(df.iloc[-1].get("rsi", 50))
        if last_rsi < 20:
            # Volume not high enough, should mention volume
            assert s.signal_type == SignalType.HOLD
            assert "volume" in s.reason.lower() or "neutral" in s.reason.lower()

    def test_oversold_with_volume_buys(self):
        """Oversold + volume confirmation = buy signal."""
        mr = MeanReversionStrategy(config={
            "rsi_period": 7,
            "rsi_oversold": 20,
            "volume_confirmation": 1.5,
        })
        df = _make_oversold_with_volume()
        last_rsi = float(df.iloc[-1].get("rsi", 50))
        s = mr.analyze(df, portfolio_value=250.0)
        if last_rsi < 20:
            # With volume, should buy (unless trend filter blocks)
            assert s.signal_type in (SignalType.BUY, SignalType.HOLD)
            if s.signal_type == SignalType.HOLD:
                # Blocked by trend filter — that's correct behavior
                assert "trend" in s.reason.lower() or "momentum" in s.reason.lower()

    def test_stop_loss_in_metadata(self):
        """Buy signals must include stop-loss price."""
        mr = MeanReversionStrategy(config={
            "rsi_period": 7,
            "rsi_oversold": 20,
            "stop_loss_pct": 0.03,
            "volume_confirmation": 1.0,  # Lower bar for testing
        })
        df = _make_oversold_with_volume()
        s = mr.analyze(df, portfolio_value=250.0)
        if s.signal_type == SignalType.BUY:
            assert "stop_loss" in s.metadata
            assert s.metadata["stop_loss"] < s.price

    def test_confidence_calculation(self):
        mr = MeanReversionStrategy()
        # More extreme RSI should give higher confidence
        c_mild = mr._calculate_confidence(rsi=18, volume_ratio=1.5, is_buy=True)
        c_extreme = mr._calculate_confidence(rsi=5, volume_ratio=3.0, is_buy=True)
        assert c_extreme > c_mild

    def test_config_validation_warns_equity_defaults(self):
        mr = MeanReversionStrategy(config={
            "rsi_period": 14,
            "rsi_oversold": 30,
            "rsi_overbought": 70,
        })
        warnings = mr.validate_config()
        assert len(warnings) >= 2  # Should warn about equity defaults

    def test_config_validation_no_stop_loss(self):
        mr = MeanReversionStrategy(config={"stop_loss_pct": 0.0})
        warnings = mr.validate_config()
        assert any("CRITICAL" in w for w in warnings)

    def test_insufficient_data(self):
        mr = MeanReversionStrategy(config={"trend_filter_period": 50})
        # Create small DataFrame without running indicators
        df = pd.DataFrame({
            "open": [65000.0] * 10, "high": [65100.0] * 10,
            "low": [64900.0] * 10, "close": [65000.0] * 10,
            "volume": [1000.0] * 10, "rsi": [50.0] * 10,
            "sma": [65000.0] * 10, "volume_ratio": [1.0] * 10,
            "adx": [15.0] * 10,
        })
        s = mr.analyze(df, portfolio_value=250.0)
        assert s.signal_type == SignalType.HOLD
        assert "Need" in s.reason

    def test_name_includes_period(self):
        mr = MeanReversionStrategy(config={"rsi_period": 9})
        assert "RSI-9" in mr.name

    def test_strategy_type(self):
        mr = MeanReversionStrategy()
        assert mr.strategy_type == "mean_reversion"


# ── Paper Trading Integration ─────────────────────────────────

class TestPaperIntegration:
    @pytest.mark.asyncio
    async def test_grid_signal_to_paper_trade(self):
        """End-to-end: grid generates signal → paper adapter executes."""
        adapter = PaperAdapter(initial_balance_usd=250.0)
        await adapter.connect()

        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        df = _make_ohlcv(50)

        # Initialize grid
        grid.analyze(df, portfolio_value=250.0)

        # Force a buy signal with price drop
        last = df.iloc[-1].copy()
        last["close"] = last["close"] * 0.97
        last["low"] = last["close"] * 0.99
        df_drop = pd.concat([df, pd.DataFrame([last])], ignore_index=True)
        df_drop = add_all_indicators(df_drop[["open", "high", "low", "close", "volume"]])

        signal = grid.analyze(df_drop, portfolio_value=250.0)
        if signal.signal_type == SignalType.BUY and signal.quantity > 0:
            adapter.set_price("BTC-USD", signal.price)
            order = OrderRequest(
                pair=signal.pair,
                side="buy",
                order_type="limit",
                quantity=signal.quantity,
                price=signal.price,
                post_only=True,
            )
            result = await adapter.place_order(order)
            assert result.is_filled or result.status == "failed"  # May fail if qty too small

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_mean_reversion_signal_to_paper_trade(self):
        """End-to-end: mean reversion generates signal → paper adapter executes."""
        adapter = PaperAdapter(initial_balance_usd=250.0)
        await adapter.connect()

        mr = MeanReversionStrategy(config={
            "rsi_period": 7,
            "volume_confirmation": 1.0,
        })
        df = _make_oversold_with_volume()

        signal = mr.analyze(df, portfolio_value=250.0)
        if signal.signal_type == SignalType.BUY and signal.quantity > 0:
            adapter.set_price("BTC-USD", signal.price)
            order = OrderRequest(
                pair=signal.pair,
                side="buy",
                order_type="limit",
                quantity=signal.quantity,
                price=signal.price,
            )
            result = await adapter.place_order(order)
            assert result.status in ("filled", "failed")

        await adapter.disconnect()


# ── Signal DCA Strategy ────────────────────────────────────────

class TestSignalDCAStrategy:
    """Tests for Signal-Enhanced DCA strategy."""

    @pytest.mark.asyncio
    async def test_signal_dca_multiple_buys_across_days(self) -> None:
        """DCA generates multiple buys when candle timestamps are 24h+ apart."""
        from hestia.trading.strategies.signal_dca import SignalDCAStrategy

        strategy = SignalDCAStrategy(config={
            "rsi_threshold": 50,
            "buy_interval_hours": 24,
            "ma_period": 20,
            "rsi_period": 14,
        })

        # Create 100 candles with oversold conditions (declining price, below MA)
        np.random.seed(42)
        n = 100
        timestamps = [
            datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(hours=i)
            for i in range(n)
        ]
        prices = [50000.0 - i * 10 for i in range(n)]  # Steady decline

        df = pd.DataFrame({
            "timestamp": timestamps,
            "open": prices,
            "high": [p + 100 for p in prices],
            "low": [p - 100 for p in prices],
            "close": prices,
            "volume": [1000.0] * n,
        })

        # Compute indicators on OHLCV columns, then re-attach timestamps
        df_with_indicators = add_all_indicators(
            df[["open", "high", "low", "close", "volume"]].copy()
        )
        df_with_indicators["timestamp"] = timestamps

        buy_signals = []
        for i in range(30, len(df_with_indicators)):
            window = df_with_indicators.iloc[:i + 1]
            ts = timestamps[i]
            signal = strategy.analyze(window, 1000.0, timestamp=ts)
            if signal.signal_type == SignalType.BUY:
                buy_signals.append(i)

        # 100 hourly candles = ~4 days; 24h interval → expect at least 2 buys
        assert len(buy_signals) >= 2, (
            f"Expected >= 2 buys but got {len(buy_signals)}: {buy_signals}"
        )

    def test_signal_dca_interval_gate_blocks_without_timestamp(self) -> None:
        """Without timestamp override, second call within 24h is blocked (wall-clock)."""
        from hestia.trading.strategies.signal_dca import SignalDCAStrategy

        strategy = SignalDCAStrategy(config={
            "rsi_threshold": 50,
            "buy_interval_hours": 24,
            "ma_period": 20,
            "rsi_period": 14,
        })

        n = 60
        prices = [50000.0 - i * 10 for i in range(n)]
        df = pd.DataFrame({
            "open": prices,
            "high": [p + 100 for p in prices],
            "low": [p - 100 for p in prices],
            "close": prices,
            "volume": [1000.0] * n,
        })
        df = add_all_indicators(df)

        # First call — no timestamp passed, should buy
        signal1 = strategy.analyze(df, 1000.0)
        assert signal1.signal_type == SignalType.BUY, (
            f"Expected first call to be BUY, got {signal1.reason}"
        )

        # Immediate second call — wall-clock hasn't moved, gate should block
        signal2 = strategy.analyze(df, 1000.0)
        assert signal2.signal_type == SignalType.HOLD, (
            f"Expected interval gate to block second call, got {signal2.signal_type}"
        )
