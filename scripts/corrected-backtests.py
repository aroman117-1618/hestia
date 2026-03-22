#!/usr/bin/env python3
"""
CORRECTED BACKTESTS — addressing Gemini's methodology concerns.

Three corrections applied simultaneously:
1. Execute at OPEN[i] instead of CLOSE[i] (fixes potential look-ahead bias)
2. Use 0.5% fee instead of 0.4% (realistic maker fee with rejection overhead)
3. Test uniform RSI-3 25/75 alongside per-asset optimized params

This is the definitive test. If results survive these corrections, the edge is real.
If they collapse, we need a fundamental rethink.
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType

ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "AVAX-USD"]


class CorrectedBacktestEngine(BacktestEngine):
    """BacktestEngine with OPEN-price execution instead of CLOSE-price."""

    def _generate_signals(self, strategy, df, cfg):
        """Same as parent but records OPEN price for execution, not CLOSE."""
        signals = []
        portfolio_value = cfg.initial_capital

        for i in range(cfg.lookback_shift, len(df)):
            window = df.iloc[:i - cfg.lookback_shift + 1]
            if len(window) < 20:
                continue

            ts = None
            if "timestamp" in df.columns:
                ts = df.iloc[i]["timestamp"]
                if hasattr(ts, "to_pydatetime"):
                    ts = ts.to_pydatetime()

            signal = strategy.analyze(window, portfolio_value, timestamp=ts)

            # CORRECTION: Use OPEN price for execution (not CLOSE)
            # This simulates: see signal after candle i-1 closes, execute at candle i's open
            exec_price = float(df.iloc[i]["open"])

            signals.append({
                "index": i,
                "signal_type": signal.signal_type.value,
                "price": exec_price,
                "quantity": signal.quantity,
                "confidence": signal.confidence,
                "reason": signal.reason,
            })

        return signals


async def fetch_both_periods():
    loader = DataLoader()
    bull_start = datetime(2024, 3, 21, tzinfo=timezone.utc)
    bull_end = datetime(2025, 3, 21, tzinfo=timezone.utc)
    bear_start = datetime(2025, 3, 21, tzinfo=timezone.utc)
    bear_end = datetime(2026, 3, 21, tzinfo=timezone.utc)

    all_data = {}
    for name, start, end in [("BULL", bull_start, bull_end), ("BEAR", bear_start, bear_end)]:
        data = {}
        for pair in ASSETS:
            try:
                df = await loader.fetch_from_coinbase(pair, "1h", start, end)
                if len(df) > 100:
                    data[pair] = df
            except:
                pass
        all_data[name] = data
        print(f"  {name}: {len(data)} assets")
    return all_data


def run_test(engine, params, data, fee_rate=0.004):
    """Run a strategy across all assets in both periods."""
    results = {}
    for pair in ASSETS:
        bull_ret = None
        bear_ret = None

        cfg = BacktestConfig(initial_capital=250.0, maker_fee=fee_rate, taker_fee=fee_rate)

        if pair in data["BULL"]:
            strategy = MeanReversionStrategy(config=params)
            result = engine.run(strategy, data["BULL"][pair].copy(), cfg)
            if result.report:
                bull_ret = result.report.total_return_pct

        if pair in data["BEAR"]:
            strategy = MeanReversionStrategy(config=params)
            result = engine.run(strategy, data["BEAR"][pair].copy(), cfg)
            if result.report:
                bear_ret = result.report.total_return_pct

        if bull_ret is not None and bear_ret is not None:
            results[pair] = {"bull": bull_ret, "bear": bear_ret, "combined": (bull_ret + bear_ret) / 2}

    return results


def print_comparison(label, results):
    """Print results table for a test configuration."""
    print(f"\n  {label}")
    print(f"  {'Asset':<10} {'Bull':>8} {'Bear':>8} {'Combined':>10}")
    print(f"  {'-'*38}")

    returns = []
    for pair in ASSETS:
        if pair in results:
            r = results[pair]
            print(f"  {pair:<10} {r['bull']:>+7.1f}% {r['bear']:>+7.1f}% {r['combined']:>+9.1f}%")
            returns.append(r["combined"])

    profitable = [r for r in returns if r > 0]
    avg_all = sum(returns) / len(returns) if returns else 0
    avg_profitable = sum(profitable) / len(profitable) if profitable else 0

    print(f"  {'ALL avg':<10} {'':>8} {'':>8} {avg_all:>+9.1f}%")
    if len(profitable) < len(returns):
        print(f"  {'Profitable':<10} {'':>8} {'':>8} {avg_profitable:>+9.1f}% ({len(profitable)}/{len(returns)} assets)")

    return avg_all, avg_profitable, len(profitable)


async def main():
    print("=" * 80)
    print("  CORRECTED BACKTESTS — Addressing Methodology Biases")
    print("=" * 80)

    all_data = await fetch_both_periods()

    original_engine = BacktestEngine()
    corrected_engine = CorrectedBacktestEngine()

    # Per-asset optimized params (the claimed best)
    per_asset_params = {
        "BTC-USD": {"rsi_period": 3, "rsi_oversold": 15, "rsi_overbought": 85, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "ETH-USD": {"rsi_period": 3, "rsi_oversold": 20, "rsi_overbought": 80, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "SOL-USD": {"rsi_period": 3, "rsi_oversold": 25, "rsi_overbought": 70, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "DOGE-USD": {"rsi_period": 3, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "AVAX-USD": {"rsi_period": 3, "rsi_oversold": 10, "rsi_overbought": 70, "volume_confirmation": 1.0, "trend_filter_period": 50},
    }

    # Uniform params (anti-overfit test)
    uniform_params = {"rsi_period": 3, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50}

    # ══════════════════════════════════════════════════════════════
    # TEST 1: Original (CLOSE price, 0.4% fee) — reproduce baseline
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  TEST 1: ORIGINAL (CLOSE price, 0.4% fee, per-asset params)")
    print(f"{'#'*80}")

    # Run per-asset params individually
    test1_results = {}
    for pair, params in per_asset_params.items():
        cfg = BacktestConfig(initial_capital=250.0, maker_fee=0.004, taker_fee=0.004)
        bull_ret = bear_ret = None
        if pair in all_data["BULL"]:
            r = original_engine.run(MeanReversionStrategy(config=params), all_data["BULL"][pair].copy(), cfg)
            bull_ret = r.report.total_return_pct if r.report else 0
        if pair in all_data["BEAR"]:
            r = original_engine.run(MeanReversionStrategy(config=params), all_data["BEAR"][pair].copy(), cfg)
            bear_ret = r.report.total_return_pct if r.report else 0
        if bull_ret is not None and bear_ret is not None:
            test1_results[pair] = {"bull": bull_ret, "bear": bear_ret, "combined": (bull_ret + bear_ret) / 2}

    t1_all, t1_prof, t1_n = print_comparison("BASELINE: CLOSE price, 0.4% fee, per-asset params", test1_results)

    # ══════════════════════════════════════════════════════════════
    # TEST 2: OPEN price, 0.4% fee (isolate price bias)
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  TEST 2: OPEN PRICE (0.4% fee, per-asset params)")
    print(f"{'#'*80}")

    test2_results = {}
    for pair, params in per_asset_params.items():
        cfg = BacktestConfig(initial_capital=250.0, maker_fee=0.004, taker_fee=0.004)
        bull_ret = bear_ret = None
        if pair in all_data["BULL"]:
            r = corrected_engine.run(MeanReversionStrategy(config=params), all_data["BULL"][pair].copy(), cfg)
            bull_ret = r.report.total_return_pct if r.report else 0
        if pair in all_data["BEAR"]:
            r = corrected_engine.run(MeanReversionStrategy(config=params), all_data["BEAR"][pair].copy(), cfg)
            bear_ret = r.report.total_return_pct if r.report else 0
        if bull_ret is not None and bear_ret is not None:
            test2_results[pair] = {"bull": bull_ret, "bear": bear_ret, "combined": (bull_ret + bear_ret) / 2}

    t2_all, t2_prof, t2_n = print_comparison("CORRECTION 1: OPEN price, 0.4% fee, per-asset params", test2_results)

    # ══════════════════════════════════════════════════════════════
    # TEST 3: OPEN price, 0.5% fee (price + fee correction)
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  TEST 3: OPEN PRICE + 0.5% FEE (per-asset params)")
    print(f"{'#'*80}")

    test3_results = {}
    for pair, params in per_asset_params.items():
        cfg = BacktestConfig(initial_capital=250.0, maker_fee=0.005, taker_fee=0.005)
        bull_ret = bear_ret = None
        if pair in all_data["BULL"]:
            r = corrected_engine.run(MeanReversionStrategy(config=params), all_data["BULL"][pair].copy(), cfg)
            bull_ret = r.report.total_return_pct if r.report else 0
        if pair in all_data["BEAR"]:
            r = corrected_engine.run(MeanReversionStrategy(config=params), all_data["BEAR"][pair].copy(), cfg)
            bear_ret = r.report.total_return_pct if r.report else 0
        if bull_ret is not None and bear_ret is not None:
            test3_results[pair] = {"bull": bull_ret, "bear": bear_ret, "combined": (bull_ret + bear_ret) / 2}

    t3_all, t3_prof, t3_n = print_comparison("CORRECTION 1+2: OPEN price, 0.5% fee, per-asset params", test3_results)

    # ══════════════════════════════════════════════════════════════
    # TEST 4: OPEN price, 0.5% fee, UNIFORM params (full correction)
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  TEST 4: ALL CORRECTIONS (OPEN price, 0.5% fee, UNIFORM RSI-3 25/75)")
    print(f"{'#'*80}")

    test4_results = run_test(corrected_engine, uniform_params, all_data, fee_rate=0.005)
    t4_all, t4_prof, t4_n = print_comparison("FULL CORRECTION: OPEN price, 0.5% fee, uniform params", test4_results)

    # ══════════════════════════════════════════════════════════════
    # TEST 5: OPEN price, 0.5% fee, UNIFORM RSI-3 20/80 (tighter)
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  TEST 5: FULL CORRECTION + TIGHTER BANDS (RSI-3 20/80)")
    print(f"{'#'*80}")

    tight_params = {"rsi_period": 3, "rsi_oversold": 20, "rsi_overbought": 80, "volume_confirmation": 1.0, "trend_filter_period": 50}
    test5_results = run_test(corrected_engine, tight_params, all_data, fee_rate=0.005)
    t5_all, t5_prof, t5_n = print_comparison("FULL CORRECTION: OPEN price, 0.5% fee, uniform RSI-3 20/80", test5_results)

    # ══════════════════════════════════════════════════════════════
    # TEST 6: OPEN price, 0.5% fee, UNIFORM RSI-5 25/75 (slower)
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  TEST 6: FULL CORRECTION + SLOWER RSI (RSI-5 25/75)")
    print(f"{'#'*80}")

    slow_params = {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50}
    test6_results = run_test(corrected_engine, slow_params, all_data, fee_rate=0.005)
    t6_all, t6_prof, t6_n = print_comparison("FULL CORRECTION: OPEN price, 0.5% fee, uniform RSI-5 25/75", test6_results)

    # ══════════════════════════════════════════════════════════════
    # DEGRADATION ANALYSIS
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  DEGRADATION ANALYSIS")
    print(f"{'#'*80}")

    print(f"\n  {'Test':<55} {'All avg':>8} {'Degradation':>12}")
    print(f"  {'-'*75}")
    tests = [
        ("T1: BASELINE (CLOSE, 0.4%, per-asset)", t1_all),
        ("T2: OPEN price only", t2_all),
        ("T3: OPEN + 0.5% fee", t3_all),
        ("T4: OPEN + 0.5% + uniform RSI-3 25/75", t4_all),
        ("T5: OPEN + 0.5% + uniform RSI-3 20/80", t5_all),
        ("T6: OPEN + 0.5% + uniform RSI-5 25/75", t6_all),
    ]

    baseline = tests[0][1]
    for label, avg in tests:
        if baseline != 0:
            deg = (1 - avg / baseline) * 100 if baseline > 0 else 0
            print(f"  {label:<55} {avg:>+7.1f}% {deg:>+10.0f}%")
        else:
            print(f"  {label:<55} {avg:>+7.1f}%")

    # Final verdict
    print(f"\n{'#'*80}")
    print("  FINAL VERDICT")
    print(f"{'#'*80}")

    best_corrected = max(t4_all, t5_all, t6_all)
    best_label = "T4" if best_corrected == t4_all else ("T5" if best_corrected == t5_all else "T6")

    if best_corrected > 5:
        print(f"\n  ✅ EDGE SURVIVES CORRECTIONS — best corrected avg: {best_corrected:+.1f}% ({best_label})")
        print(f"     Degradation from baseline: {(1 - best_corrected / baseline) * 100:.0f}%")
        print(f"     Gemini predicted 70-90% degradation. Actual: {(1 - best_corrected / baseline) * 100:.0f}%")
        print(f"     PROCEED TO LIVE VALIDATION with corrected engine")
    elif best_corrected > 0:
        print(f"\n  ⚠️  MARGINAL EDGE — best corrected avg: {best_corrected:+.1f}% ({best_label})")
        print(f"     Positive but thin. Live trading fees and slippage may erase it.")
        print(f"     PROCEED WITH CAUTION — very small position sizes")
    else:
        print(f"\n  ❌ EDGE DOES NOT SURVIVE — best corrected avg: {best_corrected:+.1f}% ({best_label})")
        print(f"     Gemini was right. The returns were a methodology artifact.")
        print(f"     FUNDAMENTAL RETHINK NEEDED")


if __name__ == "__main__":
    asyncio.run(main())
