#!/usr/bin/env python3
"""
Explore additional strategy approaches to push combined returns above 20%.

Current best: MR-fast-moderate at +9.7% combined avg.
Target: portfolio combined avg > 20%.

Strategies to explore:
1. Fixed Dual Momentum (fix the 0-trade bug inline)
2. Donchian Channel Breakout (Turtle Trading)
3. MACD Trend Following
4. Momentum Rotation (relative strength across assets)
5. Volatility Breakout (ATR-based)
6. Improved Mean Reversion with regime filter (BTC > 200-SMA = risk-on)

All tested across both bull (2024-2025) and bear (2025-2026) periods.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
from hestia.trading.data.indicators import add_all_indicators
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType

ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD"]


# ── Strategy Prototypes (inline for rapid exploration) ──────────────

class DonchianBreakout(BaseStrategy):
    """Donchian Channel Breakout — buy N-period high, sell N-period low.
    Classic Turtle Trading approach. Very few parameters."""

    def __init__(self, config=None):
        config = config or {}
        self._period = config.get("period", 168)  # 7-day lookback on hourly
        self._position_pct = config.get("position_pct", 0.15)

    @property
    def name(self) -> str:
        return f"Donchian Breakout ({self._period}h)"

    @property
    def strategy_type(self) -> str:
        return "donchian"

    def analyze(self, df: pd.DataFrame, portfolio_value: float, timestamp=None) -> Signal:
        if len(df) < self._period + 1:
            return Signal(signal_type=SignalType.HOLD)

        lookback = df.iloc[-self._period - 1:-1]
        current_price = float(df.iloc[-1]["close"])
        high_n = float(lookback["high"].max())
        low_n = float(lookback["low"].min())

        if current_price > high_n:
            qty = (portfolio_value * self._position_pct) / current_price
            return Signal(signal_type=SignalType.BUY, confidence=0.7, quantity=qty,
                         reason=f"Breakout above {self._period}h high ({high_n:.0f})")
        elif current_price < low_n:
            return Signal(signal_type=SignalType.SELL, confidence=0.7,
                         reason=f"Breakdown below {self._period}h low ({low_n:.0f})")

        return Signal(signal_type=SignalType.HOLD)

    def validate_config(self) -> list:
        return []

    def reset(self) -> None:
        pass


class MACDTrend(BaseStrategy):
    """MACD Trend Following — buy on MACD crossover, sell on cross-under."""

    def __init__(self, config=None):
        config = config or {}
        self._fast = config.get("fast_period", 12)
        self._slow = config.get("slow_period", 26)
        self._signal = config.get("signal_period", 9)
        self._position_pct = config.get("position_pct", 0.15)

    @property
    def name(self) -> str:
        return f"MACD Trend ({self._fast}/{self._slow}/{self._signal})"

    @property
    def strategy_type(self) -> str:
        return "macd_trend"

    def analyze(self, df: pd.DataFrame, portfolio_value: float, timestamp=None) -> Signal:
        if len(df) < self._slow + self._signal + 5:
            return Signal(signal_type=SignalType.HOLD)

        close = df["close"].astype(float)
        ema_fast = close.ewm(span=self._fast, adjust=False).mean()
        ema_slow = close.ewm(span=self._slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self._signal, adjust=False).mean()

        current_macd = float(macd_line.iloc[-1])
        current_signal = float(signal_line.iloc[-1])
        prev_macd = float(macd_line.iloc[-2])
        prev_signal = float(signal_line.iloc[-2])

        current_price = float(close.iloc[-1])

        # Bullish crossover
        if prev_macd <= prev_signal and current_macd > current_signal:
            confidence = min(1.0, 0.5 + abs(current_macd - current_signal) / current_price * 1000)
            qty = (portfolio_value * self._position_pct) / current_price
            return Signal(signal_type=SignalType.BUY, confidence=confidence, quantity=qty,
                         reason=f"MACD bullish crossover ({current_macd:.2f} > {current_signal:.2f})")

        # Bearish crossover
        if prev_macd >= prev_signal and current_macd < current_signal:
            return Signal(signal_type=SignalType.SELL, confidence=0.6,
                         reason=f"MACD bearish crossover ({current_macd:.2f} < {current_signal:.2f})")

        return Signal(signal_type=SignalType.HOLD)

    def validate_config(self) -> list:
        return []

    def reset(self) -> None:
        pass


class VolatilityBreakout(BaseStrategy):
    """ATR-based volatility breakout — buy when daily range exceeds 2x ATR."""

    def __init__(self, config=None):
        config = config or {}
        self._atr_period = config.get("atr_period", 14)
        self._atr_multiple = config.get("atr_multiple", 2.0)
        self._position_pct = config.get("position_pct", 0.10)

    @property
    def name(self) -> str:
        return f"Volatility Breakout ({self._atr_multiple}x ATR-{self._atr_period})"

    @property
    def strategy_type(self) -> str:
        return "volatility_breakout"

    def analyze(self, df: pd.DataFrame, portfolio_value: float, timestamp=None) -> Signal:
        if len(df) < self._atr_period + 5:
            return Signal(signal_type=SignalType.HOLD)

        high = df["high"].astype(float)
        low = df["low"].astype(float)
        close = df["close"].astype(float)

        # ATR calculation
        tr = pd.concat([
            high - low,
            (high - close.shift(1)).abs(),
            (low - close.shift(1)).abs()
        ], axis=1).max(axis=1)
        atr = tr.rolling(self._atr_period).mean()

        current_range = float(high.iloc[-1] - low.iloc[-1])
        current_atr = float(atr.iloc[-1])
        current_price = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])

        if current_atr <= 0:
            return Signal(signal_type=SignalType.HOLD)

        # Upside breakout: price moved up > atr_multiple * ATR
        if current_price - prev_close > current_atr * self._atr_multiple:
            confidence = min(1.0, 0.5 + (current_price - prev_close) / (current_atr * 4))
            qty = (portfolio_value * self._position_pct) / current_price
            return Signal(signal_type=SignalType.BUY, confidence=confidence, quantity=qty,
                         reason=f"Upside breakout: +{(current_price - prev_close) / current_atr:.1f}x ATR")

        # Downside breakout: price moved down > atr_multiple * ATR
        if prev_close - current_price > current_atr * self._atr_multiple:
            return Signal(signal_type=SignalType.SELL, confidence=0.6,
                         reason=f"Downside breakout: -{(prev_close - current_price) / current_atr:.1f}x ATR")

        return Signal(signal_type=SignalType.HOLD)

    def validate_config(self) -> list:
        return []

    def reset(self) -> None:
        pass


class RegimeFilteredMR(BaseStrategy):
    """Mean Reversion with regime filter — only trades when BTC > 200-SMA (risk-on)."""

    def __init__(self, config=None):
        config = config or {}
        self._rsi_period = config.get("rsi_period", 5)
        self._rsi_oversold = config.get("rsi_oversold", 25)
        self._rsi_overbought = config.get("rsi_overbought", 75)
        self._sma_period = config.get("regime_sma_period", 200)
        self._position_pct = config.get("position_pct", 0.10)

    @property
    def name(self) -> str:
        return f"Regime-Filtered MR (RSI-{self._rsi_period}, SMA-{self._sma_period})"

    @property
    def strategy_type(self) -> str:
        return "regime_filtered_mr"

    def analyze(self, df: pd.DataFrame, portfolio_value: float, timestamp=None) -> Signal:
        if len(df) < max(self._sma_period, self._rsi_period) + 5:
            return Signal(signal_type=SignalType.HOLD)

        close = df["close"].astype(float)
        current_price = float(close.iloc[-1])

        # Regime filter: price > 200-SMA = risk-on
        sma_200 = float(close.rolling(self._sma_period).mean().iloc[-1])
        risk_on = current_price > sma_200

        # RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).rolling(self._rsi_period).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(self._rsi_period).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        current_rsi = float(rsi.iloc[-1])

        if risk_on:
            # Risk-on: trade both directions
            if current_rsi < self._rsi_oversold:
                qty = (portfolio_value * self._position_pct) / current_price
                return Signal(signal_type=SignalType.BUY, confidence=0.7, quantity=qty,
                             reason=f"Risk-ON: RSI {current_rsi:.1f} < {self._rsi_oversold} (price > SMA-{self._sma_period})")
            elif current_rsi > self._rsi_overbought:
                return Signal(signal_type=SignalType.SELL, confidence=0.6,
                             reason=f"Risk-ON: RSI {current_rsi:.1f} > {self._rsi_overbought}")
        else:
            # Risk-off: only sell overbought (defensive)
            if current_rsi > self._rsi_overbought:
                return Signal(signal_type=SignalType.SELL, confidence=0.7,
                             reason=f"Risk-OFF: RSI {current_rsi:.1f} > {self._rsi_overbought} (price < SMA-{self._sma_period})")

        return Signal(signal_type=SignalType.HOLD)

    def validate_config(self) -> list:
        return []

    def reset(self) -> None:
        pass


class AbsoluteMomentumFixed(BaseStrategy):
    """Fixed Dual Momentum — properly handles position entry/exit transitions.

    The original DualMomentumStrategy showed 0 trades because it generates
    BUY/SELL every candle but the backtest engine only enters on the first BUY.
    This version tracks position state and only generates signals on transitions.
    """

    def __init__(self, config=None):
        config = config or {}
        self._lookback = config.get("lookback_period", 720)  # 30 days hourly
        self._position_pct = config.get("position_pct", 0.15)
        self._in_position = False

    @property
    def name(self) -> str:
        return f"Absolute Momentum ({self._lookback}h)"

    @property
    def strategy_type(self) -> str:
        return "absolute_momentum"

    def analyze(self, df: pd.DataFrame, portfolio_value: float, timestamp=None) -> Signal:
        if len(df) < self._lookback + 1:
            return Signal(signal_type=SignalType.HOLD)

        current_price = float(df.iloc[-1]["close"])
        lookback_price = float(df.iloc[-self._lookback]["close"])
        momentum = (current_price - lookback_price) / lookback_price

        if momentum > 0 and not self._in_position:
            # Transition: cash → long
            self._in_position = True
            qty = (portfolio_value * self._position_pct) / current_price
            return Signal(signal_type=SignalType.BUY, confidence=min(1.0, 0.5 + momentum * 2),
                         quantity=qty, reason=f"Momentum positive: {momentum:+.1%} over {self._lookback}h")

        elif momentum <= 0 and self._in_position:
            # Transition: long → cash
            self._in_position = False
            return Signal(signal_type=SignalType.SELL, confidence=0.7,
                         reason=f"Momentum negative: {momentum:+.1%} over {self._lookback}h")

        return Signal(signal_type=SignalType.HOLD)

    def validate_config(self) -> list:
        return []

    def reset(self) -> None:
        self._in_position = False


async def fetch_periods() -> Dict[str, Dict[str, pd.DataFrame]]:
    loader = DataLoader()
    periods = {
        "BULL (2024-2025)": (datetime(2024, 3, 21, tzinfo=timezone.utc), datetime(2025, 3, 21, tzinfo=timezone.utc)),
        "BEAR (2025-2026)": (datetime(2025, 3, 21, tzinfo=timezone.utc), datetime(2026, 3, 21, tzinfo=timezone.utc)),
    }
    all_data = {}
    for period_name, (start, end) in periods.items():
        print(f"\n  {period_name}:")
        data = {}
        for pair in ASSETS:
            print(f"    {pair}...", end=" ", flush=True)
            try:
                df = await loader.fetch_from_coinbase(pair, "1h", start, end)
                if len(df) > 100:
                    first = float(df.iloc[0]["close"])
                    last = float(df.iloc[-1]["close"])
                    data[pair] = df
                    print(f"{len(df)} candles (B&H: {(last-first)/first*100:+.1f}%)")
            except Exception as e:
                print(f"SKIP")
        all_data[period_name] = data
    return all_data


def run_strategy_both_periods(engine, strategy_cls, config, all_data, label, capital=250.0):
    """Run strategy across both periods and return combined score."""
    period_returns = []

    for period_name, data in all_data.items():
        strategy = strategy_cls(config=config)
        returns = []
        for pair, df in data.items():
            cfg = BacktestConfig(pair=pair, initial_capital=capital)
            result = engine.run(strategy, df.copy(), cfg)
            if result.report:
                returns.append(result.report.total_return_pct)
        avg = sum(returns) / len(returns) if returns else 0
        period_returns.append(avg)

    combined = sum(period_returns) / len(period_returns) if period_returns else 0
    return period_returns[0] if len(period_returns) > 0 else 0, period_returns[1] if len(period_returns) > 1 else 0, combined


async def main():
    print("STRATEGY EXPLORATION — Targeting >20% Combined Average\n")
    all_data = await fetch_periods()

    engine = BacktestEngine()

    strategies = [
        # Baseline
        ("MR-fast-moderate (baseline)", None, {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50}),

        # Regime-filtered Mean Reversion
        ("Regime MR (SMA-200)", RegimeFilteredMR, {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "regime_sma_period": 200}),
        ("Regime MR (SMA-100)", RegimeFilteredMR, {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "regime_sma_period": 100}),
        ("Regime MR (SMA-50)", RegimeFilteredMR, {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "regime_sma_period": 50}),

        # Fixed Absolute Momentum
        ("AbsMom 168h (7d)", AbsoluteMomentumFixed, {"lookback_period": 168}),
        ("AbsMom 336h (14d)", AbsoluteMomentumFixed, {"lookback_period": 336}),
        ("AbsMom 720h (30d)", AbsoluteMomentumFixed, {"lookback_period": 720}),
        ("AbsMom 1440h (60d)", AbsoluteMomentumFixed, {"lookback_period": 1440}),

        # Donchian Breakout
        ("Donchian 168h (7d)", DonchianBreakout, {"period": 168}),
        ("Donchian 336h (14d)", DonchianBreakout, {"period": 336}),
        ("Donchian 720h (30d)", DonchianBreakout, {"period": 720}),

        # MACD Trend
        ("MACD 12/26/9", MACDTrend, {"fast_period": 12, "slow_period": 26, "signal_period": 9}),
        ("MACD 8/21/5", MACDTrend, {"fast_period": 8, "slow_period": 21, "signal_period": 5}),
        ("MACD 24/52/18", MACDTrend, {"fast_period": 24, "slow_period": 52, "signal_period": 18}),

        # Volatility Breakout
        ("VolBreak 2x ATR-14", VolatilityBreakout, {"atr_period": 14, "atr_multiple": 2.0}),
        ("VolBreak 1.5x ATR-14", VolatilityBreakout, {"atr_period": 14, "atr_multiple": 1.5}),
        ("VolBreak 2x ATR-7", VolatilityBreakout, {"atr_period": 7, "atr_multiple": 2.0}),
    ]

    # For Mean Reversion baseline, use the actual strategy class
    from hestia.trading.strategies.mean_reversion import MeanReversionStrategy

    results = []
    print(f"\n{'='*80}")
    print(f"  {'Strategy':<35} {'BULL':>8} {'BEAR':>8} {'COMBINED':>10} {'TARGET':>8}")
    print(f"  {'-'*75}")

    for label, cls, config in strategies:
        if cls is None:
            cls = MeanReversionStrategy
        bull, bear, combined = run_strategy_both_periods(engine, cls, config, all_data, label)
        results.append((label, bull, bear, combined))
        target = "✅ >20%" if combined > 20 else ("⚠️ >10%" if combined > 10 else "")
        print(f"  {label:<35} {bull:>+7.1f}% {bear:>+7.1f}% {combined:>+9.1f}% {target:>8}")

    # Sort by combined
    results.sort(key=lambda x: x[3], reverse=True)

    print(f"\n{'='*80}")
    print(f"  TOP 5 BY COMBINED RETURN")
    print(f"{'='*80}")
    for label, bull, bear, combined in results[:5]:
        print(f"  {label:<35} bull={bull:+.1f}% bear={bear:+.1f}% combined={combined:+.1f}%")

    # Portfolio combinations
    print(f"\n{'='*80}")
    print(f"  PORTFOLIO COMBINATIONS (best pairs)")
    print(f"{'='*80}")

    # Find the best trend strategy and best mean reversion
    best_mr = results[0]  # MR is usually top
    best_trend = None
    for r in results:
        if any(x in r[0] for x in ["AbsMom", "Donchian", "MACD", "VolBreak"]):
            if best_trend is None or r[3] > best_trend[3]:
                best_trend = r

    if best_mr and best_trend:
        # 60/40 MR/Trend portfolio
        combo_bull = best_mr[1] * 0.6 + best_trend[1] * 0.4
        combo_bear = best_mr[2] * 0.6 + best_trend[2] * 0.4
        combo_combined = (combo_bull + combo_bear) / 2
        print(f"\n  60% {best_mr[0]} + 40% {best_trend[0]}:")
        print(f"    BULL: {combo_bull:+.1f}% | BEAR: {combo_bear:+.1f}% | COMBINED: {combo_combined:+.1f}%")

        # 50/50
        combo_bull = best_mr[1] * 0.5 + best_trend[1] * 0.5
        combo_bear = best_mr[2] * 0.5 + best_trend[2] * 0.5
        combo_combined = (combo_bull + combo_bear) / 2
        print(f"\n  50% {best_mr[0]} + 50% {best_trend[0]}:")
        print(f"    BULL: {combo_bull:+.1f}% | BEAR: {combo_bear:+.1f}% | COMBINED: {combo_combined:+.1f}%")

    # Three-strategy portfolio
    top3 = results[:3]
    if len(top3) == 3:
        combo_bull = sum(r[1] for r in top3) / 3
        combo_bear = sum(r[2] for r in top3) / 3
        combo_combined = (combo_bull + combo_bear) / 2
        names = " + ".join(r[0] for r in top3)
        print(f"\n  Equal-weight top 3: {names}")
        print(f"    BULL: {combo_bull:+.1f}% | BEAR: {combo_bear:+.1f}% | COMBINED: {combo_combined:+.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
