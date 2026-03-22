#!/usr/bin/env python3
"""
Aggressive Mean Reversion optimization — final push for maximum returns.

Current best: +9.7% combined (RSI-5, 25/75, no volume filter, equal-weight BTC/ETH/SOL)

Levers to pull:
1. Per-asset optimized parameters (ETH params may differ from BTC)
2. Wider RSI parameter space (RSI 3-14, thresholds 10-40 oversold, 60-90 overbought)
3. Position sizing variants (5%, 10%, 15%, 20%)
4. Stop-loss and take-profit (now that engine supports intra-candle)
5. Asset weighting (concentrate on best performers vs equal weight)
6. Multiple MR bots per asset with different timeframes
7. Test on 5 assets not just 3
"""

import asyncio
import itertools
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy

ASSETS = ["BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD", "AVAX-USD"]


async def fetch_both_periods() -> Dict[str, Dict[str, pd.DataFrame]]:
    loader = DataLoader()
    periods = {
        "BULL": (datetime(2024, 3, 21, tzinfo=timezone.utc), datetime(2025, 3, 21, tzinfo=timezone.utc)),
        "BEAR": (datetime(2025, 3, 21, tzinfo=timezone.utc), datetime(2026, 3, 21, tzinfo=timezone.utc)),
    }
    all_data = {}
    for name, (start, end) in periods.items():
        data = {}
        for pair in ASSETS:
            try:
                df = await loader.fetch_from_coinbase(pair, "1h", start, end)
                if len(df) > 100:
                    data[pair] = df
            except:
                pass
        all_data[name] = data
        print(f"  {name}: {len(data)} assets loaded")
    return all_data


def backtest_mr(engine, params, df, capital=250.0, stop_pct=0.0, tp_pct=0.0):
    """Run a single MR backtest and return key metrics."""
    strategy = MeanReversionStrategy(config=params)
    cfg = BacktestConfig(initial_capital=capital, stop_loss_pct=stop_pct, take_profit_pct=tp_pct)
    result = engine.run(strategy, df.copy(), cfg)
    if result.report:
        return {
            "return": result.report.total_return_pct,
            "sharpe": result.report.sharpe_ratio,
            "trades": result.report.total_trades,
            "win_rate": result.report.win_rate,
            "max_dd": result.report.max_drawdown_pct,
            "pf": result.report.profit_factor,
        }
    return None


async def main():
    print("AGGRESSIVE MEAN REVERSION OPTIMIZATION\n")
    all_data = await fetch_both_periods()

    engine = BacktestEngine()

    # ══════════════════════════════════════════════════════════════
    # PHASE 1: Per-asset parameter optimization
    # Find the best MR params for EACH asset individually
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  PHASE 1: Per-Asset Parameter Optimization")
    print(f"{'#'*80}\n")

    param_grid = {
        "rsi_period": [3, 5, 7, 9, 14],
        "rsi_oversold": [10, 15, 20, 25, 30, 35, 40],
        "rsi_overbought": [60, 65, 70, 75, 80, 85, 90],
        "volume_confirmation": [1.0],  # Proven: no volume filter is best
        "trend_filter_period": [50],
    }

    combos = list(itertools.product(*param_grid.values()))
    param_names = list(param_grid.keys())
    print(f"  Testing {len(combos)} parameter combinations per asset\n")

    best_per_asset = {}

    for pair in ASSETS:
        print(f"  {pair}:", flush=True)
        best_combined = -999
        best_params = None
        best_detail = None

        for combo in combos:
            params = dict(zip(param_names, combo))

            # Skip invalid combos (oversold >= overbought)
            if params["rsi_oversold"] >= params["rsi_overbought"]:
                continue

            bull_result = None
            bear_result = None

            if pair in all_data["BULL"]:
                bull_result = backtest_mr(engine, params, all_data["BULL"][pair])
            if pair in all_data["BEAR"]:
                bear_result = backtest_mr(engine, params, all_data["BEAR"][pair])

            if bull_result and bear_result:
                combined = (bull_result["return"] + bear_result["return"]) / 2
                if combined > best_combined:
                    best_combined = combined
                    best_params = params
                    best_detail = {"bull": bull_result, "bear": bear_result}

        if best_params:
            best_per_asset[pair] = {
                "params": best_params,
                "combined": best_combined,
                "bull": best_detail["bull"]["return"],
                "bear": best_detail["bear"]["return"],
                "bull_trades": best_detail["bull"]["trades"],
                "bear_trades": best_detail["bear"]["trades"],
                "bull_sharpe": best_detail["bull"]["sharpe"],
                "bear_sharpe": best_detail["bear"]["sharpe"],
            }
            p = best_params
            print(f"    Best: {best_combined:+.1f}% (bull={best_detail['bull']['return']:+.1f}%, bear={best_detail['bear']['return']:+.1f}%)")
            print(f"    Params: RSI-{p['rsi_period']} {p['rsi_oversold']}/{p['rsi_overbought']}")
            print(f"    Trades: bull={best_detail['bull']['trades']}, bear={best_detail['bear']['trades']}")
            print(f"    Sharpe: bull={best_detail['bull']['sharpe']:.2f}, bear={best_detail['bear']['sharpe']:.2f}")
        else:
            print(f"    No profitable combination found")

    # ══════════════════════════════════════════════════════════════
    # PHASE 2: Portfolio construction with per-asset params
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  PHASE 2: Portfolio Construction")
    print(f"{'#'*80}\n")

    # Equal weight across all profitable assets
    profitable_assets = {k: v for k, v in best_per_asset.items() if v["combined"] > 0}
    if profitable_assets:
        avg_combined = sum(v["combined"] for v in profitable_assets.values()) / len(profitable_assets)
        print(f"  Equal-weight ({len(profitable_assets)} profitable assets): {avg_combined:+.1f}% combined")
        for pair, data in sorted(profitable_assets.items(), key=lambda x: x[1]["combined"], reverse=True):
            print(f"    {pair}: {data['combined']:+.1f}% (RSI-{data['params']['rsi_period']} {data['params']['rsi_oversold']}/{data['params']['rsi_overbought']})")

    # Weighted by Sharpe ratio (risk-adjusted allocation)
    if profitable_assets:
        total_sharpe = sum(max(0.1, (v["bull_sharpe"] + v["bear_sharpe"]) / 2) for v in profitable_assets.values())
        weighted_combined = 0
        print(f"\n  Sharpe-weighted allocation:")
        for pair, data in sorted(profitable_assets.items(), key=lambda x: x[1]["combined"], reverse=True):
            avg_sharpe = max(0.1, (data["bull_sharpe"] + data["bear_sharpe"]) / 2)
            weight = avg_sharpe / total_sharpe
            weighted_combined += data["combined"] * weight
            print(f"    {pair}: weight={weight:.0%}, combined={data['combined']:+.1f}%")
        print(f"  Sharpe-weighted combined: {weighted_combined:+.1f}%")

    # Concentrate on top 2
    top2 = sorted(profitable_assets.items(), key=lambda x: x[1]["combined"], reverse=True)[:2]
    if len(top2) == 2:
        avg_top2 = sum(v["combined"] for _, v in top2) / 2
        print(f"\n  Top-2 concentration ({top2[0][0]} + {top2[1][0]}): {avg_top2:+.1f}% combined")

    # Concentrate on top 1
    if profitable_assets:
        top1 = max(profitable_assets.items(), key=lambda x: x[1]["combined"])
        print(f"  Top-1 concentration ({top1[0]}): {top1[1]['combined']:+.1f}% combined")

    # All assets (including unprofitable)
    all_avg = sum(v["combined"] for v in best_per_asset.values()) / len(best_per_asset) if best_per_asset else 0
    print(f"\n  All {len(best_per_asset)} assets (including losers): {all_avg:+.1f}% combined")

    # ══════════════════════════════════════════════════════════════
    # PHASE 3: Stop-loss / take-profit variants on best configs
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  PHASE 3: Stop-Loss / Take-Profit Impact on Best Configs")
    print(f"{'#'*80}\n")

    exit_variants = [
        ("No exits", 0.0, 0.0),
        ("2% stop", 0.02, 0.0),
        ("3% stop", 0.03, 0.0),
        ("5% stop", 0.05, 0.0),
        ("2% stop + 3% target", 0.02, 0.03),
        ("3% stop + 5% target", 0.03, 0.05),
        ("5% stop + 8% target", 0.05, 0.08),
    ]

    for pair in list(profitable_assets.keys())[:3]:  # Top 3 profitable
        data = best_per_asset[pair]
        params = data["params"]
        print(f"  {pair} (RSI-{params['rsi_period']} {params['rsi_oversold']}/{params['rsi_overbought']}):")

        for label, stop, tp in exit_variants:
            bull_r = None
            bear_r = None
            if pair in all_data["BULL"]:
                bull_r = backtest_mr(engine, params, all_data["BULL"][pair], stop_pct=stop, tp_pct=tp)
            if pair in all_data["BEAR"]:
                bear_r = backtest_mr(engine, params, all_data["BEAR"][pair], stop_pct=stop, tp_pct=tp)

            if bull_r and bear_r:
                combined = (bull_r["return"] + bear_r["return"]) / 2
                delta = combined - data["combined"]
                indicator = "↑" if delta > 0 else "↓" if delta < 0 else "="
                print(f"    {label:<25} combined={combined:>+7.1f}% ({indicator}{abs(delta):>5.1f}%) bull={bull_r['return']:>+7.1f}% bear={bear_r['return']:>+7.1f}%")

    # ══════════════════════════════════════════════════════════════
    # FINAL SUMMARY
    # ══════════════════════════════════════════════════════════════
    print(f"\n{'#'*80}")
    print("  FINAL SUMMARY — MAXIMUM ACHIEVABLE RETURN")
    print(f"{'#'*80}\n")

    print("  Per-asset best configs:")
    for pair in ASSETS:
        if pair in best_per_asset:
            d = best_per_asset[pair]
            print(f"    {pair:<10} {d['combined']:>+7.1f}% combined | RSI-{d['params']['rsi_period']} {d['params']['rsi_oversold']}/{d['params']['rsi_overbought']} | bull={d['bull']:+.1f}% bear={d['bear']:+.1f}%")

    print(f"\n  Portfolio options:")
    if profitable_assets:
        avg_profitable = sum(v["combined"] for v in profitable_assets.values()) / len(profitable_assets)
        print(f"    Equal-weight profitable ({len(profitable_assets)} assets): {avg_profitable:+.1f}%")
    if len(top2) == 2:
        print(f"    Top-2 concentration: {avg_top2:+.1f}%")
    if profitable_assets:
        print(f"    Top-1 concentration ({top1[0]}): {top1[1]['combined']:+.1f}%")
    print(f"    All {len(best_per_asset)} assets: {all_avg:+.1f}%")

    # Compare to baseline
    print(f"\n  vs Baseline (uniform RSI-5 25/75 across BTC/ETH/SOL): +9.7%")
    if profitable_assets:
        improvement = avg_profitable - 9.7
        print(f"  Improvement from per-asset optimization: {improvement:+.1f}%")


if __name__ == "__main__":
    asyncio.run(main())
