#!/usr/bin/env python3
"""
Parameter optimization sweep for all 4 trading strategies.

Sprint 27.5 WS1: Find profitable configurations before expanding scope.
Tests parameter combinations against 1yr BTC-USD hourly data with walk-forward validation.
"""

import asyncio
import itertools
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
from hestia.trading.strategies.grid import GridStrategy
from hestia.trading.strategies.signal_dca import SignalDCAStrategy
from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy


async def fetch_data() -> pd.DataFrame:
    loader = DataLoader()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365)
    print(f"Fetching BTC-USD 1yr hourly data...")
    df = await loader.fetch_from_coinbase("BTC-USD", "1h", start, end)
    print(f"Got {len(df)} candles ({len(df)/24:.0f} days)\n")
    return df


def sweep_strategy(engine, strategy_cls, param_grid, data, config, label):
    """Run parameter sweep for a strategy. Returns sorted results."""
    combos = list(itertools.product(*param_grid.values()))
    param_names = list(param_grid.keys())
    results = []

    print(f"{'='*70}")
    print(f"OPTIMIZING: {label} ({len(combos)} combinations)")
    print(f"{'='*70}")

    for i, combo in enumerate(combos):
        params = dict(zip(param_names, combo))
        try:
            strategy = strategy_cls(config=params)
            result = engine.run(strategy, data.copy(), config)
            report = result.report

            if report is None:
                continue

            row = {
                "params": params,
                "return_pct": report.total_return_pct,
                "annualized_pct": report.annualized_return_pct,
                "sharpe": report.sharpe_ratio,
                "sortino": report.sortino_ratio,
                "max_dd": report.max_drawdown_pct,
                "trades": report.total_trades,
                "win_rate": report.win_rate,
                "profit_factor": report.profit_factor,
                "avg_win": report.avg_win,
                "avg_loss": report.avg_loss,
                "warnings": result.warnings,
            }
            results.append(row)

            # Progress indicator
            if (i + 1) % 10 == 0 or i == len(combos) - 1:
                print(f"  [{i+1}/{len(combos)}] Best so far: {max((r['return_pct'] for r in results), default=0):+.1f}%")

        except Exception as e:
            print(f"  SKIP: {params} — {type(e).__name__}: {e}")
            continue

    # Sort by Sharpe (risk-adjusted return, not raw return)
    results.sort(key=lambda x: x["sharpe"], reverse=True)

    # Print top 5
    print(f"\n  TOP 5 by Sharpe:")
    print(f"  {'Return':>8} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8} {'WinRate':>8} | Params")
    print(f"  {'-'*65}")
    for r in results[:5]:
        params_str = ", ".join(f"{k}={v}" for k, v in r["params"].items())
        print(f"  {r['return_pct']:>+7.1f}% {r['sharpe']:>7.2f} {r['max_dd']:>7.1f}% {r['trades']:>7} {r['win_rate']:>7.0%} | {params_str}")
        if r["warnings"]:
            for w in r["warnings"]:
                if "OVERFIT" in w:
                    print(f"  {'':>8} ⚠️  {w[:80]}")

    return results


def walk_forward_top(engine, strategy_cls, results, data, config, label, top_n=3):
    """Run walk-forward validation on top N parameter sets."""
    print(f"\n  Walk-Forward Validation (top {top_n}):")
    validated = []

    for i, r in enumerate(results[:top_n]):
        params = r["params"]
        strategy = strategy_cls(config=params)
        wf = engine.walk_forward(strategy, data.copy(), train_days=30, test_days=7, config=config)

        if not wf.get("valid"):
            print(f"    #{i+1}: INVALID — {wf.get('reason', '?')}")
            continue

        consistent = wf.get("consistent", False)
        avg_ret = wf.get("avg_test_return", 0)
        win_pct = wf.get("window_win_rate", 0)

        status = "PASS" if consistent else "FAIL"
        params_str = ", ".join(f"{k}={v}" for k, v in params.items())
        print(f"    #{i+1}: {status} — avg_ret={avg_ret:+.3f}%, win_windows={win_pct:.0%} | {params_str}")

        r["walk_forward"] = wf
        r["wf_consistent"] = consistent
        validated.append(r)

    return validated


async def main():
    data = await fetch_data()
    if len(data) < 1000:
        print("ERROR: Not enough data")
        sys.exit(1)

    # ── Mean Reversion Sweep ────────────────────────────────────
    mr_config = BacktestConfig(initial_capital=250.0)
    mr_grid = {
        "rsi_period": [5, 7, 9, 14],
        "rsi_oversold": [15, 20, 25, 30, 35],
        "rsi_overbought": [65, 70, 75, 80, 85],
        "volume_confirmation": [1.0, 1.25, 1.5, 2.0],
        "trend_filter_period": [50],
    }
    engine = BacktestEngine()
    mr_results = sweep_strategy(engine, MeanReversionStrategy, mr_grid, data, mr_config, "Mean Reversion")
    mr_validated = walk_forward_top(engine, MeanReversionStrategy, mr_results, data, mr_config, "Mean Reversion")

    # ── Signal DCA Sweep ────────────────────────────────────────
    dca_config = BacktestConfig(initial_capital=250.0)
    dca_grid = {
        "rsi_period": [7, 14, 21],
        "rsi_threshold": [35, 40, 45, 50, 55, 60],
        "ma_period": [20, 50, 100],
        "buy_interval_hours": [12, 24, 48, 72],
    }
    dca_results = sweep_strategy(engine, SignalDCAStrategy, dca_grid, data, dca_config, "Signal DCA")
    dca_validated = walk_forward_top(engine, SignalDCAStrategy, dca_results, data, dca_config, "Signal DCA")

    # ── Bollinger Breakout Sweep ────────────────────────────────
    bb_config = BacktestConfig(initial_capital=250.0)
    bb_grid = {
        "period": [10, 15, 20, 30],
        "std_dev": [1.5, 2.0, 2.5, 3.0],
        "volume_confirmation": [1.0, 1.25, 1.5, 2.0],
    }
    bb_results = sweep_strategy(engine, BollingerBreakoutStrategy, bb_grid, data, bb_config, "Bollinger Breakout")
    bb_validated = walk_forward_top(engine, BollingerBreakoutStrategy, bb_results, data, bb_config, "Bollinger Breakout")

    # ── Grid Trading Sweep (at $5K capital) ─────────────────────
    grid_config = BacktestConfig(initial_capital=5000.0)  # Test at $5K, not $250
    grid_grid = {
        "spacing_type": ["geometric"],
        "num_levels": [5, 8, 10, 15],
        "grid_width_atr_multiple": [1.5, 2.0, 3.0, 4.0],
    }
    grid_results = sweep_strategy(engine, GridStrategy, grid_grid, data, grid_config, "Grid Trading ($5K capital)")
    grid_validated = walk_forward_top(engine, GridStrategy, grid_results, data, grid_config, "Grid Trading")

    # ── Final Summary ───────────────────────────────────────────
    print(f"\n{'='*70}")
    print("OPTIMIZATION SUMMARY")
    print(f"{'='*70}\n")

    all_results = {
        "mean_reversion": {
            "total_combos": len(mr_results),
            "profitable": sum(1 for r in mr_results if r["return_pct"] > 0),
            "top_sharpe": mr_results[0] if mr_results else None,
            "walk_forward_passed": sum(1 for r in mr_validated if r.get("wf_consistent")),
        },
        "signal_dca": {
            "total_combos": len(dca_results),
            "profitable": sum(1 for r in dca_results if r["return_pct"] > 0),
            "top_sharpe": dca_results[0] if dca_results else None,
            "walk_forward_passed": sum(1 for r in dca_validated if r.get("wf_consistent")),
        },
        "bollinger": {
            "total_combos": len(bb_results),
            "profitable": sum(1 for r in bb_results if r["return_pct"] > 0),
            "top_sharpe": bb_results[0] if bb_results else None,
            "walk_forward_passed": sum(1 for r in bb_validated if r.get("wf_consistent")),
        },
        "grid": {
            "total_combos": len(grid_results),
            "profitable": sum(1 for r in grid_results if r["return_pct"] > 0),
            "top_sharpe": grid_results[0] if grid_results else None,
            "walk_forward_passed": sum(1 for r in grid_validated if r.get("wf_consistent")),
            "note": "Tested at $5K capital (non-viable at $250 due to fee drag)",
        },
    }

    for name, summary in all_results.items():
        top = summary["top_sharpe"]
        if top:
            params_str = ", ".join(f"{k}={v}" for k, v in top["params"].items())
            print(f"{name.upper()}: {summary['profitable']}/{summary['total_combos']} profitable | "
                  f"Best: {top['return_pct']:+.1f}% (Sharpe {top['sharpe']:.2f}) | "
                  f"WF passed: {summary['walk_forward_passed']}/3")
            print(f"  Best params: {params_str}")
        else:
            print(f"{name.upper()}: No results")
        if summary.get("note"):
            print(f"  Note: {summary['note']}")
        print()

    # Go/No-Go assessment
    print("GO/NO-GO ASSESSMENT:")
    viable_strategies = []
    for name, summary in all_results.items():
        top = summary["top_sharpe"]
        if top and top["sharpe"] > 0.5 and top["return_pct"] > 0 and summary["walk_forward_passed"] > 0:
            viable_strategies.append(name)
            print(f"  ✅ {name}: VIABLE (Sharpe > 0.5, positive return, walk-forward passed)")
        elif top and top["return_pct"] > 0:
            print(f"  ⚠️  {name}: MARGINAL (positive return but walk-forward inconsistent)")
        else:
            print(f"  ❌ {name}: NOT VIABLE with tested parameters")

    if viable_strategies:
        print(f"\n  VERDICT: PROCEED with {', '.join(viable_strategies)}")
    else:
        print(f"\n  VERDICT: STRATEGY REDESIGN NEEDED — no strategy shows reliable positive expected value")

    # Save full results
    output_path = Path(__file__).parent.parent / "data" / "optimization-results-2026-03-21.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2, default=str)
    print(f"\nFull results saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
