#!/usr/bin/env python3
"""
Multi-asset parameter optimization — test strategies across diverse market profiles.

BTC alone is insufficient: it was in a strong uptrend for most of 2025-2026,
which specifically punishes mean reversion and grid strategies. We need to test
across coins with different volatility profiles and market regimes.

Asset selection rationale:
- BTC-USD: Large-cap, trending, moderate volatility
- ETH-USD: Large-cap, higher beta than BTC, more volatile
- SOL-USD: Mid-cap, high volatility, strong trends
- DOGE-USD: Meme/speculative, extreme volatility, range-bound periods
- AVAX-USD: Mid-cap, mixed trending/ranging

This gives us: trending + ranging + high-vol + low-vol + large + mid + speculative
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy
from hestia.trading.strategies.grid import GridStrategy
from hestia.trading.strategies.signal_dca import SignalDCAStrategy
from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy


ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "AVAX-USD"]

# Best Mean Reversion params from BTC sweep + a few variants
MR_CONFIGS = [
    {"rsi_period": 5, "rsi_oversold": 15, "rsi_overbought": 85, "volume_confirmation": 1.0, "trend_filter_period": 50, "label": "MR-wide-no-vol"},
    {"rsi_period": 7, "rsi_oversold": 20, "rsi_overbought": 80, "volume_confirmation": 1.5, "trend_filter_period": 50, "label": "MR-original"},
    {"rsi_period": 7, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50, "label": "MR-moderate"},
    {"rsi_period": 14, "rsi_oversold": 30, "rsi_overbought": 70, "volume_confirmation": 1.0, "trend_filter_period": 50, "label": "MR-equity-style"},
    {"rsi_period": 5, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.25, "trend_filter_period": 50, "label": "MR-fast-moderate"},
]

BB_CONFIGS = [
    {"period": 20, "std_dev": 2.0, "volume_confirmation": 1.5, "label": "BB-standard"},
    {"period": 20, "std_dev": 1.5, "volume_confirmation": 1.0, "label": "BB-tight-no-vol"},
    {"period": 10, "std_dev": 2.0, "volume_confirmation": 1.0, "label": "BB-fast"},
    {"period": 30, "std_dev": 2.5, "volume_confirmation": 1.5, "label": "BB-wide-slow"},
]

DCA_CONFIGS = [
    {"rsi_period": 14, "rsi_threshold": 40, "ma_period": 50, "buy_interval_hours": 24, "label": "DCA-original"},
    {"rsi_period": 14, "rsi_threshold": 50, "ma_period": 50, "buy_interval_hours": 24, "label": "DCA-loose"},
    {"rsi_period": 14, "rsi_threshold": 55, "ma_period": 20, "buy_interval_hours": 12, "label": "DCA-aggressive"},
    {"rsi_period": 7, "rsi_threshold": 60, "ma_period": 50, "buy_interval_hours": 24, "label": "DCA-very-loose"},
]

GRID_CONFIGS = [
    {"spacing_type": "geometric", "num_levels": 5, "grid_width_atr_multiple": 3.0, "label": "Grid-wide-5lev"},
    {"spacing_type": "geometric", "num_levels": 10, "grid_width_atr_multiple": 2.0, "label": "Grid-standard"},
]


async def fetch_all_data() -> Dict[str, pd.DataFrame]:
    """Fetch 1yr hourly data for all assets."""
    loader = DataLoader()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365)
    data = {}

    for pair in ASSETS:
        print(f"  Fetching {pair}...", end=" ", flush=True)
        try:
            df = await loader.fetch_from_coinbase(pair, "1h", start, end)
            if len(df) > 100:
                data[pair] = df
                # Calculate basic stats
                first_close = float(df.iloc[0]["close"])
                last_close = float(df.iloc[-1]["close"])
                buy_hold_return = (last_close - first_close) / first_close * 100
                print(f"{len(df)} candles, buy-hold: {buy_hold_return:+.1f}%")
            else:
                print(f"SKIP (only {len(df)} candles)")
        except Exception as e:
            print(f"SKIP ({type(e).__name__})")

    return data


def run_strategy_across_assets(engine, strategy_cls, configs, all_data, capital):
    """Run strategy configs across all assets."""
    results = []

    for cfg_dict in configs:
        label = cfg_dict.pop("label", "?")
        strategy = strategy_cls(config=cfg_dict)

        for pair, data in all_data.items():
            bt_config = BacktestConfig(pair=pair, initial_capital=capital)
            try:
                result = engine.run(strategy, data.copy(), bt_config)
                report = result.report
                if report:
                    results.append({
                        "label": label,
                        "pair": pair,
                        "return_pct": report.total_return_pct,
                        "sharpe": report.sharpe_ratio,
                        "max_dd": report.max_drawdown_pct,
                        "trades": report.total_trades,
                        "win_rate": report.win_rate,
                        "profit_factor": report.profit_factor,
                        "avg_win": report.avg_win,
                        "avg_loss": report.avg_loss,
                        "params": dict(cfg_dict),
                    })
            except Exception as e:
                results.append({
                    "label": label, "pair": pair,
                    "return_pct": 0, "sharpe": 0, "error": str(e),
                })

        # Restore label for next iteration
        cfg_dict["label"] = label

    return results


def print_results_table(strategy_name, results):
    """Print a cross-asset results table."""
    print(f"\n{'='*80}")
    print(f"  {strategy_name}")
    print(f"{'='*80}")

    # Group by label
    labels = sorted(set(r["label"] for r in results))
    pairs = sorted(set(r["pair"] for r in results if "error" not in r))

    # Header
    print(f"  {'Config':<20}", end="")
    for p in pairs:
        print(f" {p:>10}", end="")
    print(f" {'AVG':>10} {'Sharpe':>8}")
    print(f"  {'-'*20}", end="")
    for _ in pairs:
        print(f" {'-'*10}", end="")
    print(f" {'-'*10} {'-'*8}")

    best_label = None
    best_avg = -999

    for label in labels:
        label_results = [r for r in results if r["label"] == label and "error" not in r]
        print(f"  {label:<20}", end="")

        returns = []
        sharpes = []
        for p in pairs:
            match = [r for r in label_results if r["pair"] == p]
            if match:
                ret = match[0]["return_pct"]
                returns.append(ret)
                sharpes.append(match[0]["sharpe"])
                print(f" {ret:>+9.1f}%", end="")
            else:
                print(f" {'N/A':>10}", end="")

        avg_ret = sum(returns) / len(returns) if returns else 0
        avg_sharpe = sum(sharpes) / len(sharpes) if sharpes else 0
        print(f" {avg_ret:>+9.1f}% {avg_sharpe:>7.2f}")

        if avg_ret > best_avg:
            best_avg = avg_ret
            best_label = label

    if best_label:
        print(f"\n  BEST: {best_label} (avg return: {best_avg:+.1f}%)")

    # Detailed view of best config
    best_results = [r for r in results if r.get("label") == best_label and "error" not in r]
    if best_results:
        print(f"\n  Detailed — {best_label}:")
        print(f"  {'Pair':<10} {'Return':>8} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8} {'WinRate':>8} {'PF':>8}")
        for r in sorted(best_results, key=lambda x: x["pair"]):
            print(f"  {r['pair']:<10} {r['return_pct']:>+7.1f}% {r['sharpe']:>7.2f} {r['max_dd']:>7.1f}% {r['trades']:>7} {r['win_rate']:>7.0%} {r['profit_factor']:>7.2f}")

    return best_label, best_avg, best_results


async def main():
    print("MULTI-ASSET STRATEGY OPTIMIZATION")
    print("Testing across diverse market profiles\n")

    all_data = await fetch_all_data()
    if not all_data:
        print("ERROR: No data fetched")
        sys.exit(1)

    engine = BacktestEngine()
    all_strategy_results = {}

    # Mean Reversion
    mr_results = run_strategy_across_assets(engine, MeanReversionStrategy, MR_CONFIGS, all_data, 250.0)
    mr_best_label, mr_best_avg, mr_best = print_results_table("MEAN REVERSION", mr_results)
    all_strategy_results["mean_reversion"] = {"results": mr_results, "best_label": mr_best_label, "best_avg": mr_best_avg}

    # Bollinger Breakout
    bb_results = run_strategy_across_assets(engine, BollingerBreakoutStrategy, BB_CONFIGS, all_data, 250.0)
    bb_best_label, bb_best_avg, bb_best = print_results_table("BOLLINGER BREAKOUT", bb_results)
    all_strategy_results["bollinger"] = {"results": bb_results, "best_label": bb_best_label, "best_avg": bb_best_avg}

    # Signal DCA
    dca_results = run_strategy_across_assets(engine, SignalDCAStrategy, DCA_CONFIGS, all_data, 250.0)
    dca_best_label, dca_best_avg, dca_best = print_results_table("SIGNAL DCA", dca_results)
    all_strategy_results["signal_dca"] = {"results": dca_results, "best_label": dca_best_label, "best_avg": dca_best_avg}

    # Grid (at $5K)
    grid_results = run_strategy_across_assets(engine, GridStrategy, GRID_CONFIGS, all_data, 5000.0)
    grid_best_label, grid_best_avg, grid_best = print_results_table("GRID TRADING ($5K)", grid_results)
    all_strategy_results["grid"] = {"results": grid_results, "best_label": grid_best_label, "best_avg": grid_best_avg}

    # ── Buy & Hold Baseline ────────────────────────────────────
    print(f"\n{'='*80}")
    print(f"  BUY & HOLD BASELINE (for comparison)")
    print(f"{'='*80}")
    for pair, df in sorted(all_data.items()):
        first = float(df.iloc[0]["close"])
        last = float(df.iloc[-1]["close"])
        ret = (last - first) / first * 100
        print(f"  {pair:<10} {ret:>+7.1f}%")

    # ── Final Verdict ──────────────────────────────────────────
    print(f"\n{'='*80}")
    print("  CROSS-ASSET VERDICT")
    print(f"{'='*80}\n")

    for name, data in all_strategy_results.items():
        label = data.get("best_label", "?")
        avg = data.get("best_avg", 0)
        status = "VIABLE" if avg > 0 else "NOT VIABLE"
        icon = "✅" if avg > 0 else "❌"
        print(f"  {icon} {name.upper():<20} Best avg: {avg:>+7.1f}% ({label}) — {status}")

    # Save
    output_path = Path(__file__).parent.parent / "data" / "multi-asset-optimization-2026-03-21.json"
    with open(output_path, "w") as f:
        json.dump(all_strategy_results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
