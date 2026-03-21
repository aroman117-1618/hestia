#!/usr/bin/env python3
"""
Bull market backtest — test strategies against the 2024-2025 BTC bull run.

Context: S27.6 backtests showed all strategies lose money in a bear market
(Mar 2025-Mar 2026). But losing LESS than buy-and-hold IS alpha.
Now we need to verify: do the strategies ALSO capture upside in a bull market?

Period: Mar 2024 - Mar 2025 (BTC went from ~$65K to ~$85K, ~30% gain)
This covers both the pre-halving rally and post-halving consolidation.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy
from hestia.trading.strategies.signal_dca import SignalDCAStrategy
from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy
from hestia.trading.strategies.dual_momentum import DualMomentumStrategy

ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD"]  # Focus on top 3 liquid assets


async def fetch_data(start: datetime, end: datetime) -> Dict[str, pd.DataFrame]:
    loader = DataLoader()
    data = {}
    for pair in ASSETS:
        print(f"  {pair}...", end=" ", flush=True)
        try:
            df = await loader.fetch_from_coinbase(pair, "1h", start, end)
            if len(df) > 100:
                first_close = float(df.iloc[0]["close"])
                last_close = float(df.iloc[-1]["close"])
                bh = (last_close - first_close) / first_close * 100
                data[pair] = df
                print(f"{len(df)} candles (buy-hold: {bh:+.1f}%)")
        except Exception as e:
            print(f"SKIP ({e})")
    return data


def test_strategy(engine, strategy, data, bt_cfg, wf_days=(90, 30)):
    results = {}
    for pair, df in data.items():
        cfg = BacktestConfig(
            pair=pair,
            initial_capital=bt_cfg.get("capital", 250.0),
            stop_loss_pct=bt_cfg.get("stop_loss_pct", 0.0),
            take_profit_pct=bt_cfg.get("take_profit_pct", 0.0),
        )
        result = engine.run(strategy, df.copy(), cfg)
        report = result.report

        strategy.reset()
        wf = engine.walk_forward(strategy, df.copy(), train_days=wf_days[0], test_days=wf_days[1], config=cfg)

        if report:
            results[pair] = {
                "return_pct": report.total_return_pct,
                "sharpe": report.sharpe_ratio,
                "max_dd": report.max_drawdown_pct,
                "trades": report.total_trades,
                "win_rate": report.win_rate,
                "profit_factor": report.profit_factor,
                "wf_consistent": wf.get("consistent", False),
                "wf_win_windows": wf.get("window_win_rate", 0),
            }
    return results


def print_results(name, results, buy_hold):
    print(f"\n{'='*80}")
    print(f"  {name}")
    print(f"{'='*80}")
    print(f"  {'Asset':<10} {'Return':>8} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8} {'WinRate':>8} {'PF':>8} {'WF':>8} {'vs B&H':>8}")
    print(f"  {'-'*78}")

    returns = []
    for pair in ASSETS:
        if pair in results:
            r = results[pair]
            bh = buy_hold.get(pair, 0)
            alpha = r["return_pct"] - bh
            wf_status = "PASS" if r["wf_consistent"] else f"FAIL({r['wf_win_windows']:.0%})"
            print(f"  {pair:<10} {r['return_pct']:>+7.1f}% {r['sharpe']:>7.2f} {r['max_dd']:>7.1f}% {r['trades']:>7} {r['win_rate']:>7.0%} {r['profit_factor']:>7.2f} {wf_status:>8} {alpha:>+7.1f}%")
            returns.append(r["return_pct"])

    avg = sum(returns) / len(returns) if returns else 0
    wf_pass = sum(1 for r in results.values() if r["wf_consistent"])
    print(f"\n  AVG: {avg:+.1f}% | Walk-forward passed: {wf_pass}/{len(results)}")
    return avg, wf_pass


async def main():
    # ── Period 1: Bull Market (Mar 2024 - Mar 2025) ──
    bull_start = datetime(2024, 3, 21, tzinfo=timezone.utc)
    bull_end = datetime(2025, 3, 21, tzinfo=timezone.utc)

    # ── Period 2: Bear Market (Mar 2025 - Mar 2026) — already tested ──
    bear_start = datetime(2025, 3, 21, tzinfo=timezone.utc)
    bear_end = datetime(2026, 3, 21, tzinfo=timezone.utc)

    engine = BacktestEngine()
    all_results = {}

    for period_name, start, end in [("BULL (Mar 2024 - Mar 2025)", bull_start, bull_end),
                                      ("BEAR (Mar 2025 - Mar 2026)", bear_start, bear_end)]:
        print(f"\n{'#'*80}")
        print(f"  PERIOD: {period_name}")
        print(f"{'#'*80}")

        data = await fetch_data(start, end)
        if not data:
            print("  No data available for this period")
            continue

        buy_hold = {}
        for pair, df in data.items():
            first = float(df.iloc[0]["close"])
            last = float(df.iloc[-1]["close"])
            buy_hold[pair] = (last - first) / first * 100

        period_results = {}

        # Strategy configs to test
        strategies = [
            ("MR-fast-moderate", MeanReversionStrategy, {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50}, {"capital": 250.0}),
            ("MR-wide", MeanReversionStrategy, {"rsi_period": 5, "rsi_oversold": 15, "rsi_overbought": 85, "volume_confirmation": 1.0, "trend_filter_period": 50}, {"capital": 250.0}),
            ("DualMom 168h", DualMomentumStrategy, {"lookback_period": 168, "position_pct": 0.15}, {"capital": 250.0}),
            ("DualMom 720h", DualMomentumStrategy, {"lookback_period": 720, "position_pct": 0.15}, {"capital": 250.0}),
            ("DCA RSI<50", SignalDCAStrategy, {"rsi_period": 14, "rsi_threshold": 50, "ma_period": 50, "buy_interval_hours": 24}, {"capital": 250.0}),
            ("Bollinger", BollingerBreakoutStrategy, {"period": 20, "std_dev": 2.0, "volume_confirmation": 1.5}, {"capital": 250.0}),
        ]

        for label, cls, strategy_cfg, bt_cfg in strategies:
            strategy = cls(config=strategy_cfg)
            results = test_strategy(engine, strategy, data, bt_cfg)
            avg, wf = print_results(f"{label}", results, buy_hold)
            period_results[label] = {"results": results, "avg_return": avg, "wf_passed": wf}

        # Period summary
        print(f"\n  Buy & Hold: ", end="")
        bh_avg = sum(buy_hold.values()) / len(buy_hold)
        for p, bh in buy_hold.items():
            print(f"{p}={bh:+.1f}%  ", end="")
        print(f"AVG={bh_avg:+.1f}%")

        all_results[period_name] = {"buy_hold": buy_hold, "bh_avg": bh_avg, "strategies": period_results}

    # ── Cross-Period Comparison ──
    print(f"\n{'#'*80}")
    print(f"  CROSS-PERIOD COMPARISON")
    print(f"{'#'*80}\n")

    period_names = list(all_results.keys())
    if len(period_names) == 2:
        bull_data = all_results[period_names[0]]
        bear_data = all_results[period_names[1]]

        print(f"  {'Strategy':<25} {'BULL avg':>10} {'BEAR avg':>10} {'Combined':>10} {'Bull B&H':>10} {'Bear B&H':>10}")
        print(f"  {'-'*75}")

        combined_scores = []
        strategy_names = list(bull_data["strategies"].keys())
        for name in strategy_names:
            bull_avg = bull_data["strategies"].get(name, {}).get("avg_return", 0)
            bear_avg = bear_data["strategies"].get(name, {}).get("avg_return", 0)
            combined = (bull_avg + bear_avg) / 2
            combined_scores.append((name, bull_avg, bear_avg, combined))

        combined_scores.sort(key=lambda x: x[3], reverse=True)

        bull_bh = bull_data["bh_avg"]
        bear_bh = bear_data["bh_avg"]

        for name, bull_avg, bear_avg, combined in combined_scores:
            print(f"  {name:<25} {bull_avg:>+9.1f}% {bear_avg:>+9.1f}% {combined:>+9.1f}% {bull_bh:>+9.1f}% {bear_bh:>+9.1f}%")

        print(f"\n  {'Buy & Hold':<25} {bull_bh:>+9.1f}% {bear_bh:>+9.1f}% {(bull_bh + bear_bh) / 2:>+9.1f}%")

        # Verdict
        print(f"\n  VERDICT:")
        for name, bull_avg, bear_avg, combined in combined_scores:
            beats_bull = bull_avg > bull_bh * 0.5  # At least half of B&H in bull
            beats_bear = bear_avg > bear_bh  # Better than B&H in bear
            if combined > 0:
                print(f"  ✅ {name}: PROFITABLE across both periods ({combined:+.1f}% avg)")
            elif beats_bear and bull_avg > 0:
                print(f"  ⚠️  {name}: Makes money in bull, loses less in bear ({combined:+.1f}% avg)")
            elif beats_bear:
                print(f"  ⚠️  {name}: Bear-market alpha but no bull capture ({combined:+.1f}% avg)")
            else:
                print(f"  ❌ {name}: Loses in both periods ({combined:+.1f}% avg)")

    # Save
    output = Path(__file__).parent.parent / "data" / "backtest-bull-bear-comparison-2026-03-21.json"
    with open(output, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {output}")


if __name__ == "__main__":
    asyncio.run(main())
