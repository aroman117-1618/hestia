#!/usr/bin/env python3
"""
S27.6 Final Backtest — All strategies with fixed engine across 5 assets.

Engine fixes applied:
- Signal DCA: uses candle timestamp (not wall-clock)
- Walk-forward: fresh capital per test window (no position contamination)
- Intra-candle exits: stop-loss and take-profit check high/low

Strategies tested:
- Mean Reversion (best params from prior sweep + stop/target variants)
- Dual Momentum (NEW — Antonacci absolute momentum)
- Signal DCA (FIXED — was producing 0 trades)
- Bollinger Breakout (baseline — pending redesign)

Walk-forward: 90d train / 30d test (per Gemini recommendation)
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy
from hestia.trading.strategies.signal_dca import SignalDCAStrategy
from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy
from hestia.trading.strategies.dual_momentum import DualMomentumStrategy

ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "AVAX-USD"]


async def fetch_all() -> Dict[str, pd.DataFrame]:
    loader = DataLoader()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365)
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


def test_strategy(engine, strategy, data, config, walk_forward_days=(90, 30)):
    """Test a strategy across all assets with backtest + walk-forward."""
    results = {}
    for pair, df in data.items():
        cfg = BacktestConfig(
            pair=pair,
            initial_capital=config.get("capital", 250.0),
            stop_loss_pct=config.get("stop_loss_pct", 0.0),
            take_profit_pct=config.get("take_profit_pct", 0.0),
        )
        # Full backtest
        result = engine.run(strategy, df.copy(), cfg)
        report = result.report

        # Walk-forward
        strategy.reset()
        wf = engine.walk_forward(
            strategy, df.copy(),
            train_days=walk_forward_days[0],
            test_days=walk_forward_days[1],
            config=cfg,
        )

        if report:
            results[pair] = {
                "return_pct": report.total_return_pct,
                "sharpe": report.sharpe_ratio,
                "sortino": report.sortino_ratio,
                "max_dd": report.max_drawdown_pct,
                "trades": report.total_trades,
                "win_rate": report.win_rate,
                "profit_factor": report.profit_factor,
                "avg_win": report.avg_win,
                "avg_loss": report.avg_loss,
                "wf_consistent": wf.get("consistent", False),
                "wf_avg_return": wf.get("avg_test_return", 0),
                "wf_win_windows": wf.get("window_win_rate", 0),
                "wf_total_windows": wf.get("total_windows", 0),
            }

    return results


def print_strategy_results(name, results, buy_hold):
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
    print(f"\n  AVG: {avg:+.1f}% | Walk-forward passed: {wf_pass}/{len(results)} assets")
    return avg, wf_pass


async def main():
    print("S27.6 FINAL BACKTEST — Fixed Engine + All Strategies\n")
    data = await fetch_all()

    # Buy-and-hold baseline
    buy_hold = {}
    for pair, df in data.items():
        first = float(df.iloc[0]["close"])
        last = float(df.iloc[-1]["close"])
        buy_hold[pair] = (last - first) / first * 100

    engine = BacktestEngine()
    all_results = {}

    # ── Mean Reversion (best config from prior sweep, now with stop/target) ──
    configs = [
        ("MR-fast-moderate (no exits)", {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50}, {"capital": 250.0}),
        ("MR-fast-moderate (2% stop)", {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50}, {"capital": 250.0, "stop_loss_pct": 0.02}),
        ("MR-fast-moderate (2% stop + 3% target)", {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50}, {"capital": 250.0, "stop_loss_pct": 0.02, "take_profit_pct": 0.03}),
        ("MR-wide (no exits)", {"rsi_period": 5, "rsi_oversold": 15, "rsi_overbought": 85, "volume_confirmation": 1.0, "trend_filter_period": 50}, {"capital": 250.0}),
    ]

    for label, strategy_cfg, bt_cfg in configs:
        strategy = MeanReversionStrategy(config=strategy_cfg)
        results = test_strategy(engine, strategy, data, bt_cfg)
        avg, wf = print_strategy_results(f"MEAN REVERSION — {label}", results, buy_hold)
        all_results[label] = {"results": results, "avg_return": avg, "wf_passed": wf}

    # ── Dual Momentum ──
    dm_configs = [
        ("DualMom 168h (7d lookback)", {"lookback_period": 168, "position_pct": 0.15}),
        ("DualMom 720h (30d lookback)", {"lookback_period": 720, "position_pct": 0.15}),
        ("DualMom 2160h (90d lookback)", {"lookback_period": 2160, "position_pct": 0.15}),
        ("DualMom 4320h (180d lookback)", {"lookback_period": 4320, "position_pct": 0.15}),
    ]

    for label, strategy_cfg in dm_configs:
        strategy = DualMomentumStrategy(config=strategy_cfg)
        results = test_strategy(engine, strategy, data, {"capital": 250.0})
        avg, wf = print_strategy_results(f"DUAL MOMENTUM — {label}", results, buy_hold)
        all_results[label] = {"results": results, "avg_return": avg, "wf_passed": wf}

    # ── Signal DCA (FIXED) ──
    dca_configs = [
        ("DCA RSI<50 (24h interval)", {"rsi_period": 14, "rsi_threshold": 50, "ma_period": 50, "buy_interval_hours": 24}),
        ("DCA RSI<55 (12h interval)", {"rsi_period": 14, "rsi_threshold": 55, "ma_period": 20, "buy_interval_hours": 12}),
    ]

    for label, strategy_cfg in dca_configs:
        strategy = SignalDCAStrategy(config=strategy_cfg)
        results = test_strategy(engine, strategy, data, {"capital": 250.0})
        avg, wf = print_strategy_results(f"SIGNAL DCA — {label}", results, buy_hold)
        all_results[label] = {"results": results, "avg_return": avg, "wf_passed": wf}

    # ── Bollinger (baseline) ──
    strategy = BollingerBreakoutStrategy(config={"period": 20, "std_dev": 2.0, "volume_confirmation": 1.5})
    results = test_strategy(engine, strategy, data, {"capital": 250.0})
    avg, wf = print_strategy_results("BOLLINGER BREAKOUT — standard (baseline)", results, buy_hold)
    all_results["Bollinger-standard"] = {"results": results, "avg_return": avg, "wf_passed": wf}

    # ── Summary ──
    print(f"\n{'='*80}")
    print("  GO/NO-GO ASSESSMENT")
    print(f"{'='*80}\n")

    print(f"  Buy & Hold baseline:")
    for pair in ASSETS:
        print(f"    {pair}: {buy_hold[pair]:+.1f}%")
    bh_avg = sum(buy_hold.values()) / len(buy_hold)
    print(f"    AVG: {bh_avg:+.1f}%\n")

    viable = []
    for label, data_dict in sorted(all_results.items(), key=lambda x: x[1]["avg_return"], reverse=True):
        avg = data_dict["avg_return"]
        wf = data_dict["wf_passed"]
        beats_bh = avg > bh_avg

        if avg > 0 and wf >= 2:
            icon = "✅"
            status = "VIABLE"
            viable.append(label)
        elif avg > 0:
            icon = "⚠️ "
            status = "MARGINAL"
        else:
            icon = "❌"
            status = "NOT VIABLE"

        print(f"  {icon} {label:<45} avg: {avg:>+7.1f}%  WF: {wf}/5  {'BEATS B&H' if beats_bh else '':<12} {status}")

    print(f"\n  VIABLE STRATEGIES: {len(viable)}")
    if len(viable) >= 2:
        print(f"  VERDICT: ✅ PROCEED TO S28 — {', '.join(viable)}")
    elif len(viable) == 1:
        print(f"  VERDICT: ⚠️  MARGINAL — only 1 viable strategy. Consider more optimization before S28.")
    else:
        print(f"  VERDICT: ❌ STRATEGY REDESIGN STILL NEEDED — no reliable positive expected value.")

    # Save
    output_path = Path(__file__).parent.parent / "data" / "backtest-results-s27.6.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
