"""
Tests for backtesting engine — data loading, fee modeling, slippage,
look-ahead bias, overfit detection, walk-forward, report generation.
"""

import numpy as np
import pandas as pd
import pytest

from datetime import datetime
from typing import Any, Dict, Optional

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine, BacktestResult
from hestia.trading.backtest.report import BacktestReport, generate_report
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType
from hestia.trading.strategies.grid import GridStrategy
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy


class AlwaysBuyStrategy(BaseStrategy):
    """Test stub: always emits a BUY signal (guarantees open position at train end)."""

    @property
    def name(self) -> str:
        return "AlwaysBuy"

    @property
    def strategy_type(self) -> str:
        return "always_buy"

    def analyze(
        self,
        df: pd.DataFrame,
        portfolio_value: float,
        timestamp: Optional[datetime] = None,
    ) -> Signal:
        if len(df) < 2:
            return Signal()
        price = float(df.iloc[-1]["close"])
        qty = (portfolio_value * 0.10) / price if price > 0 else 0.0
        return Signal(
            signal_type=SignalType.BUY,
            pair=self.pair,
            price=price,
            quantity=qty,
            confidence=1.0,
            reason="always buy",
        )


def _synthetic_data(n: int = 500, trend: float = 0.0, seed: int = 42) -> pd.DataFrame:
    return DataLoader.generate_synthetic(n=n, trend=trend, seed=seed)


def _trending_up(n: int = 500) -> pd.DataFrame:
    return DataLoader.generate_synthetic(n=n, trend=0.15, seed=123)


def _trending_down(n: int = 500) -> pd.DataFrame:
    return DataLoader.generate_synthetic(n=n, trend=-0.15, seed=456)


# ── DataLoader ────────────────────────────────────────────────

class TestDataLoader:
    def test_generate_synthetic(self):
        df = DataLoader.generate_synthetic(n=100)
        assert len(df) == 100
        assert "open" in df.columns
        assert "high" in df.columns
        assert "low" in df.columns
        assert "close" in df.columns
        assert "volume" in df.columns
        assert "timestamp" in df.columns

    def test_synthetic_prices_positive(self):
        df = DataLoader.generate_synthetic(n=1000)
        assert (df["close"] > 0).all()
        assert (df["high"] >= df["low"]).all()

    def test_synthetic_reproducible(self):
        df1 = DataLoader.generate_synthetic(n=50, seed=42)
        df2 = DataLoader.generate_synthetic(n=50, seed=42)
        # Timestamps differ by microseconds (based on now()), compare OHLCV only
        for col in ("open", "high", "low", "close", "volume"):
            pd.testing.assert_series_equal(df1[col], df2[col])

    def test_synthetic_different_seeds(self):
        df1 = DataLoader.generate_synthetic(n=50, seed=1)
        df2 = DataLoader.generate_synthetic(n=50, seed=2)
        assert not df1["close"].equals(df2["close"])

    def test_cache_roundtrip(self, tmp_path):
        loader = DataLoader(cache_dir=tmp_path)
        df = DataLoader.generate_synthetic(n=100)
        loader.save_to_cache(df, "BTC-USD", "1h")

        loaded = loader.load_from_cache("BTC-USD", "1h")
        assert loaded is not None
        assert len(loaded) == 100

    def test_cache_miss(self, tmp_path):
        loader = DataLoader(cache_dir=tmp_path)
        assert loader.load_from_cache("NONEXISTENT", "1h") is None

    def test_synthetic_with_trend(self):
        up = DataLoader.generate_synthetic(n=1000, trend=0.5, seed=42)
        assert up.iloc[-1]["close"] > up.iloc[0]["close"]

        down = DataLoader.generate_synthetic(n=1000, trend=-0.5, seed=42)
        assert down.iloc[-1]["close"] < down.iloc[0]["close"]


# ── BacktestReport ────────────────────────────────────────────

class TestBacktestReport:
    def test_generate_from_equity_curve(self):
        equity = [250.0, 252.0, 248.0, 255.0, 260.0, 258.0, 265.0]
        trades = [
            {"side": "sell", "pnl": 2.0, "fee": 0.1},
            {"side": "sell", "pnl": -4.0, "fee": 0.1},
            {"side": "sell", "pnl": 7.0, "fee": 0.1},
        ]
        report = generate_report(equity, trades, initial_capital=250.0)
        assert report.total_return_pct == pytest.approx(6.0, abs=0.1)
        assert report.total_trades == 3
        assert report.winning_trades == 2
        assert report.losing_trades == 1
        assert report.win_rate == pytest.approx(2 / 3, abs=0.01)
        assert report.total_fees == pytest.approx(0.3, abs=0.01)

    def test_empty_equity_curve(self):
        report = generate_report([], [])
        assert report.total_return_pct == 0.0
        assert report.sharpe_ratio == 0.0

    def test_single_point_curve(self):
        report = generate_report([250.0], [])
        assert report.total_return_pct == 0.0

    def test_max_drawdown(self):
        # Peak at 300, drops to 240 = 20% drawdown
        equity = [250.0, 280.0, 300.0, 270.0, 240.0, 260.0, 280.0]
        report = generate_report(equity, [], initial_capital=250.0)
        assert report.max_drawdown_pct == pytest.approx(20.0, abs=0.5)

    def test_no_drawdown(self):
        equity = [250.0, 260.0, 270.0, 280.0]
        report = generate_report(equity, [], initial_capital=250.0)
        assert report.max_drawdown_pct == 0.0

    def test_profit_factor(self):
        trades = [
            {"side": "sell", "pnl": 10.0},
            {"side": "sell", "pnl": -5.0},
        ]
        report = generate_report([250.0, 260.0, 255.0], trades)
        assert report.profit_factor == pytest.approx(2.0, abs=0.01)

    def test_to_dict(self):
        report = generate_report([250.0, 260.0], [])
        d = report.to_dict()
        assert "sharpe_ratio" in d
        assert "max_drawdown_pct" in d
        assert "win_rate" in d

    def test_sharpe_positive_for_gains(self):
        # Steadily increasing equity
        equity = [250.0 + i * 0.5 for i in range(200)]
        report = generate_report(equity, [], initial_capital=250.0)
        assert report.sharpe_ratio > 0

    def test_sharpe_negative_for_losses(self):
        # Steadily decreasing equity
        equity = [250.0 - i * 0.3 for i in range(200)]
        report = generate_report(equity, [], initial_capital=250.0)
        assert report.sharpe_ratio < 0


# ── BacktestEngine ────────────────────────────────────────────

class TestBacktestEngine:
    def test_run_grid_strategy(self):
        data = _synthetic_data(500)
        engine = BacktestEngine(BacktestConfig(initial_capital=250.0))
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        result = engine.run(grid, data)

        assert result.report is not None
        assert result.strategy_name == grid.name
        assert len(result.equity_curve) > 0
        assert result.equity_curve[0] == pytest.approx(250.0, abs=1.0)

    def test_run_mean_reversion(self):
        data = _synthetic_data(500)
        engine = BacktestEngine()
        mr = MeanReversionStrategy(config={"rsi_period": 7})
        result = engine.run(mr, data)
        assert result.report is not None

    def test_fee_impact(self):
        """Higher fees should result in lower returns."""
        data = _synthetic_data(500)
        low_fee = BacktestConfig(maker_fee=0.001, taker_fee=0.002)
        high_fee = BacktestConfig(maker_fee=0.01, taker_fee=0.02)

        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})

        result_low = BacktestEngine(low_fee).run(grid, data)
        result_high = BacktestEngine(high_fee).run(grid, data)

        # Higher fees should eat more returns
        if result_low.report.total_trades > 0 and result_high.report.total_trades > 0:
            assert result_high.report.total_fees >= result_low.report.total_fees

    def test_slippage_impact(self):
        """Higher slippage should reduce returns."""
        data = _synthetic_data(500)
        no_slip = BacktestConfig(slippage=0.0)
        high_slip = BacktestConfig(slippage=0.01)

        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})

        result_none = BacktestEngine(no_slip).run(grid, data)
        result_high = BacktestEngine(high_slip).run(grid, data)

        # With trades, slippage should matter
        if result_none.report.total_trades > 0:
            assert result_high.report.total_return_pct <= result_none.report.total_return_pct + 1.0

    def test_look_ahead_bias_prevention(self):
        """Signals should be shifted back to prevent look-ahead bias."""
        data = _synthetic_data(200)
        engine = BacktestEngine(BacktestConfig(lookback_shift=1))
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        result = engine.run(grid, data)

        # Signals should reference candle indices >= lookback_shift
        for sig in result.signals:
            assert sig["index"] >= 1

    def test_short_data_warning(self):
        data = _synthetic_data(30)
        engine = BacktestEngine()
        grid = GridStrategy()
        result = engine.run(grid, data)
        assert any("unreliable" in w.lower() for w in result.warnings)

    def test_result_to_dict(self):
        data = _synthetic_data(200)
        engine = BacktestEngine()
        grid = GridStrategy()
        result = engine.run(grid, data)
        d = result.to_dict()
        assert "id" in d
        assert "report" in d
        assert "warnings" in d

    def test_equity_curve_starts_at_capital(self):
        data = _synthetic_data(200)
        engine = BacktestEngine(BacktestConfig(initial_capital=500.0))
        grid = GridStrategy()
        result = engine.run(grid, data)
        assert result.equity_curve[0] == pytest.approx(500.0, abs=1.0)


# ── Overfit Detection ─────────────────────────────────────────

class TestOverfitDetection:
    def test_high_sharpe_warning(self):
        engine = BacktestEngine()
        warnings = engine._check_overfit(BacktestReport(sharpe_ratio=4.0))
        assert any("OVERFIT" in w for w in warnings)

    def test_high_win_rate_warning(self):
        engine = BacktestEngine()
        warnings = engine._check_overfit(BacktestReport(win_rate=0.85))
        assert any("OVERFIT" in w for w in warnings)

    def test_high_profit_factor_warning(self):
        engine = BacktestEngine()
        warnings = engine._check_overfit(BacktestReport(profit_factor=4.0))
        assert any("OVERFIT" in w for w in warnings)

    def test_normal_metrics_no_warning(self):
        engine = BacktestEngine()
        warnings = engine._check_overfit(BacktestReport(
            sharpe_ratio=1.5, win_rate=0.55, profit_factor=1.5,
        ))
        assert len(warnings) == 0


# ── Walk-Forward Validation ───────────────────────────────────

class TestWalkForward:
    def test_walk_forward_basic(self):
        data = _synthetic_data(2000)
        engine = BacktestEngine()
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        result = engine.walk_forward(grid, data, train_days=30, test_days=7)

        assert result["valid"] is True
        assert result["total_windows"] >= 1
        assert "avg_test_return" in result
        assert "window_win_rate" in result

    def test_walk_forward_insufficient_data(self):
        data = _synthetic_data(100)
        engine = BacktestEngine()
        grid = GridStrategy()
        result = engine.walk_forward(grid, data, train_days=30, test_days=7)
        assert result["valid"] is False

    def test_walk_forward_consistency_flag(self):
        data = _synthetic_data(2000)
        engine = BacktestEngine()
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        result = engine.walk_forward(grid, data, train_days=30, test_days=7)
        assert "consistent" in result

    def test_walk_forward_test_windows_start_with_fresh_capital(self):
        """
        Each test window must begin with initial_capital equity.

        If training ends with an open position, the old (broken) approach carries
        that position's unrealized P&L into the test slice.  The fixed approach
        runs each test window as an independent backtest so the first equity
        point always equals initial_capital.
        """
        # Need enough candles: train=5d*24 + test=2d*24 + one slide = 504 candles
        data = _synthetic_data(1200)
        cfg = BacktestConfig(initial_capital=250.0)
        engine = BacktestEngine(cfg)
        # AlwaysBuyStrategy guarantees training ends with an open position
        strategy = AlwaysBuyStrategy()
        result = engine.walk_forward(
            strategy, data, train_days=5, test_days=2, config=cfg
        )

        assert result["valid"] is True
        assert result["total_windows"] >= 1

        # Every test window's reported first equity == initial_capital
        for window in result["windows"]:
            first_equity = window.get("test_first_equity")
            assert first_equity is not None, "walk_forward must expose test_first_equity per window"
            assert first_equity == pytest.approx(cfg.initial_capital, abs=1.0), (
                f"Window {window['window']}: test started at {first_equity:.2f}, "
                f"expected {cfg.initial_capital:.2f} — position state leaked from training"
            )


# ── Train/Test Split ──────────────────────────────────────────

class TestTrainTestSplit:
    def test_split_basic(self):
        data = _synthetic_data(1000)
        engine = BacktestEngine()
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        result = engine.train_test_split(grid, data, train_pct=0.7)

        assert "train" in result
        assert "test" in result
        assert "overfit_risk" in result
        assert result["train"]["candles"] == 700
        assert result["test"]["candles"] == 300

    def test_split_reports_generated(self):
        data = _synthetic_data(1000)
        engine = BacktestEngine()
        grid = GridStrategy(config={"num_levels": 5, "spacing_pct": 0.01})
        result = engine.train_test_split(grid, data)

        assert result["train"]["report"] is not None
        assert result["test"]["report"] is not None

    def test_overfit_assessment(self):
        engine = BacktestEngine()
        # Simulate big train/test gap
        risk = engine._assess_overfit_risk(
            BacktestReport(sharpe_ratio=3.0, total_return_pct=50.0),
            BacktestReport(sharpe_ratio=0.5, total_return_pct=-5.0),
        )
        assert "high" in risk.lower()

    def test_consistent_assessment(self):
        engine = BacktestEngine()
        risk = engine._assess_overfit_risk(
            BacktestReport(sharpe_ratio=1.5, total_return_pct=20.0),
            BacktestReport(sharpe_ratio=1.2, total_return_pct=15.0),
        )
        assert "low" in risk.lower()


# ── Intra-Candle Exits ────────────────────────────────────────

class _OnceOnlyBuyStrategy(BaseStrategy):
    """Buys on the first signal opportunity, then holds (no sell signals)."""

    def __init__(self) -> None:
        super().__init__()
        self._bought = False

    @property
    def name(self) -> str:
        return "OnceOnlyBuy"

    @property
    def strategy_type(self) -> str:
        return "once_only_buy"

    def reset(self) -> None:
        self._bought = False

    def analyze(
        self,
        df: pd.DataFrame,
        portfolio_value: float,
        timestamp: Optional[datetime] = None,
    ) -> Signal:
        if self._bought or len(df) < 2:
            return Signal()
        price = float(df.iloc[-1]["close"])
        qty = portfolio_value / price if price > 0 else 0.0
        self._bought = True
        return Signal(
            signal_type=SignalType.BUY,
            pair=self.pair,
            price=price,
            quantity=qty,
            confidence=1.0,
            reason="once-only buy",
        )


def _make_ohlcv_df(
    prefix_price: float,
    prefix_n: int,
    test_rows: list,
    suffix_n: int = 40,
) -> pd.DataFrame:
    """
    Build an OHLCV DataFrame for intra-candle exit tests.

    Structure:
      - `prefix_n` flat candles at `prefix_price` (warm-up: builds indicator history,
        lets the strategy generate exactly one BUY on the last warm-up candle)
      - `test_rows`: list of (open, high, low, close, volume) — the candles under test
      - `suffix_n` flat candles at `prefix_price` (pad to meet engine's 60-candle minimum)

    The _OnceOnlyBuyStrategy buys on the very first signal opportunity.  With
    lookback_shift=1 and len(window)<20 guard, that first opportunity falls at
    candle index 20.  By making prefix_n=21 the buy occurs at index 20 (price =
    prefix_price), and test_rows[0] is the first candle AFTER the buy where
    intra-candle checks can trigger.
    """
    flat = [prefix_price, prefix_price, prefix_price, prefix_price, 1.0]
    rows = [flat] * prefix_n
    rows += list(test_rows)
    rows += [flat] * suffix_n
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.date_range("2024-01-01", periods=len(df), freq="h")
    return df


class TestIntraCandleExits:
    def test_stop_loss_triggers_on_candle_low(self) -> None:
        """Stop-loss exits at stop level when candle low breaches it."""
        # 21 flat candles at 100 → buy at index 20 (price=100)
        # Next candle: close=99, low=95 (5% dip) → 3% stop triggers at 97
        # Without intra-candle check: position would be held (close=99, only 1% down)
        test_rows = [
            # open,  high,   low, close, volume
            (100.0, 100.0,  95.0,  99.0, 10.0),   # low hits 3% stop (97)
        ]
        df = _make_ohlcv_df(prefix_price=100.0, prefix_n=21, test_rows=test_rows)

        engine = BacktestEngine()
        strategy = _OnceOnlyBuyStrategy()
        cfg = BacktestConfig(
            initial_capital=100.0,
            slippage=0.0,
            maker_fee=0.0,
            taker_fee=0.0,
            stop_loss_pct=0.03,
            take_profit_pct=0.0,
        )
        _, trade_log = engine._simulate_trades(
            engine._generate_signals(strategy, df, cfg), df, cfg
        )

        stop_exits = [t for t in trade_log if t.get("exit_type") == "stop_loss"]
        assert len(stop_exits) == 1, f"Expected 1 stop-loss exit, got {len(stop_exits)}"
        # Fill price should be at 97 (100 * 0.97), not 99 (close)
        assert stop_exits[0]["price"] == pytest.approx(97.0, abs=0.5)

    def test_take_profit_triggers_on_candle_high(self) -> None:
        """Take-profit exits at target when candle high reaches it."""
        # Buy at 100, next candle: close=101, high=105 (5% spike)
        # 2.5% take-profit → should exit at 102.5
        test_rows = [
            (100.0, 105.0,  99.0, 101.0, 10.0),   # high hits 2.5% target (102.5)
        ]
        df = _make_ohlcv_df(prefix_price=100.0, prefix_n=21, test_rows=test_rows)

        engine = BacktestEngine()
        strategy = _OnceOnlyBuyStrategy()
        cfg = BacktestConfig(
            initial_capital=100.0,
            slippage=0.0,
            maker_fee=0.0,
            taker_fee=0.0,
            stop_loss_pct=0.0,
            take_profit_pct=0.025,
        )
        _, trade_log = engine._simulate_trades(
            engine._generate_signals(strategy, df, cfg), df, cfg
        )

        tp_exits = [t for t in trade_log if t.get("exit_type") == "take_profit"]
        assert len(tp_exits) == 1, f"Expected 1 take-profit exit, got {len(tp_exits)}"
        assert tp_exits[0]["price"] == pytest.approx(102.5, abs=0.5)

    def test_stop_loss_before_take_profit_on_same_candle(self) -> None:
        """If same candle triggers both, stop-loss takes priority."""
        # Buy at 100. Candle with low=95 AND high=106:
        # 3% stop = 97, 5% target = 105 — both breached; stop wins.
        test_rows = [
            (100.0, 106.0,  95.0, 100.0, 10.0),   # both stop(97) and target(105) breached
        ]
        df = _make_ohlcv_df(prefix_price=100.0, prefix_n=21, test_rows=test_rows)

        engine = BacktestEngine()
        strategy = _OnceOnlyBuyStrategy()
        cfg = BacktestConfig(
            initial_capital=100.0,
            slippage=0.0,
            maker_fee=0.0,
            taker_fee=0.0,
            stop_loss_pct=0.03,
            take_profit_pct=0.05,
        )
        _, trade_log = engine._simulate_trades(
            engine._generate_signals(strategy, df, cfg), df, cfg
        )

        exits = [t for t in trade_log if t.get("exit_type") in ("stop_loss", "take_profit")]
        assert len(exits) == 1, f"Expected exactly 1 intra-candle exit, got {len(exits)}"
        assert exits[0]["exit_type"] == "stop_loss", (
            f"Stop-loss should take priority, got {exits[0]['exit_type']}"
        )
        assert exits[0]["price"] == pytest.approx(97.0, abs=0.5)

    def test_disabled_when_pct_is_zero(self) -> None:
        """No intra-candle exits when both pcts are 0 (default behaviour unchanged)."""
        # Extreme candle that would trigger any active stop/target — but both disabled
        test_rows = [
            (100.0, 120.0,  70.0,  80.0, 10.0),   # 20% spike and 30% dip — would trigger anything
        ]
        df = _make_ohlcv_df(prefix_price=100.0, prefix_n=21, test_rows=test_rows)

        engine = BacktestEngine()
        strategy = _OnceOnlyBuyStrategy()
        cfg = BacktestConfig(
            initial_capital=100.0,
            slippage=0.0,
            maker_fee=0.0,
            taker_fee=0.0,
            stop_loss_pct=0.0,
            take_profit_pct=0.0,
        )
        _, trade_log = engine._simulate_trades(
            engine._generate_signals(strategy, df, cfg), df, cfg
        )

        intra_exits = [t for t in trade_log if t.get("exit_type") in ("stop_loss", "take_profit")]
        assert len(intra_exits) == 0, (
            f"Expected no intra-candle exits with pct=0, got {len(intra_exits)}"
        )
