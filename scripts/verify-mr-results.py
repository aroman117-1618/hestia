#!/usr/bin/env python3
"""
VERIFICATION SCRIPT — independently re-run the claimed best configs
and verify every number matches. No optimization, no sweeps — just
run the exact params and print detailed results.

This exists to catch:
1. Bugs in the optimization script (wrong params reported)
2. Non-deterministic behavior (different results on re-run)
3. Data issues (stale cache, missing candles)
4. Look-ahead bias in the backtest engine
"""

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy

# EXACT configs claimed by the optimization script
CLAIMED_RESULTS = {
    "BTC-USD": {
        "params": {"rsi_period": 3, "rsi_oversold": 15, "rsi_overbought": 85, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "claimed_bull": 28.9,
        "claimed_bear": 7.7,
        "claimed_combined": 18.3,
    },
    "ETH-USD": {
        "params": {"rsi_period": 3, "rsi_oversold": 20, "rsi_overbought": 80, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "claimed_bull": 29.3,
        "claimed_bear": 38.5,
        "claimed_combined": 33.9,
    },
    "SOL-USD": {
        "params": {"rsi_period": 3, "rsi_oversold": 25, "rsi_overbought": 70, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "claimed_bull": 27.6,
        "claimed_bear": 11.1,
        "claimed_combined": 19.4,
    },
    "DOGE-USD": {
        "params": {"rsi_period": 3, "rsi_oversold": 25, "rsi_overbought": 75, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "claimed_bull": 46.9,
        "claimed_bear": -7.8,
        "claimed_combined": 19.6,
    },
    "AVAX-USD": {
        "params": {"rsi_period": 3, "rsi_oversold": 10, "rsi_overbought": 70, "volume_confirmation": 1.0, "trend_filter_period": 50},
        "claimed_bull": -4.9,
        "claimed_bear": 0.1,
        "claimed_combined": -2.4,
    },
}

TOLERANCE = 0.5  # Allow 0.5% tolerance for floating-point/rounding


async def main():
    print("=" * 80)
    print("  INDEPENDENT VERIFICATION OF OPTIMIZATION RESULTS")
    print("  Re-running exact claimed configs from scratch")
    print("=" * 80)

    loader = DataLoader()
    engine = BacktestEngine()

    bull_start = datetime(2024, 3, 21, tzinfo=timezone.utc)
    bull_end = datetime(2025, 3, 21, tzinfo=timezone.utc)
    bear_start = datetime(2025, 3, 21, tzinfo=timezone.utc)
    bear_end = datetime(2026, 3, 21, tzinfo=timezone.utc)

    # Fetch fresh data (don't use cached)
    print("\n  Fetching fresh data...")
    all_pass = True
    verified_results = {}

    for pair, claimed in CLAIMED_RESULTS.items():
        print(f"\n{'─'*60}")
        print(f"  {pair}")
        print(f"{'─'*60}")
        print(f"  Params: RSI-{claimed['params']['rsi_period']} {claimed['params']['rsi_oversold']}/{claimed['params']['rsi_overbought']}")

        # Fetch data
        bull_df = await loader.fetch_from_coinbase(pair, "1h", bull_start, bull_end)
        bear_df = await loader.fetch_from_coinbase(pair, "1h", bear_start, bear_end)

        print(f"  Data: bull={len(bull_df)} candles, bear={len(bear_df)} candles")

        # Verify data integrity
        if len(bull_df) < 8000:
            print(f"  ⚠️  Bull data incomplete: {len(bull_df)} < 8000 expected")
        if len(bear_df) < 8000:
            print(f"  ⚠️  Bear data incomplete: {len(bear_df)} < 8000 expected")

        # Print price range for sanity check
        bull_first = float(bull_df.iloc[0]["close"])
        bull_last = float(bull_df.iloc[-1]["close"])
        bear_first = float(bear_df.iloc[0]["close"])
        bear_last = float(bear_df.iloc[-1]["close"])
        print(f"  Bull price: ${bull_first:,.2f} → ${bull_last:,.2f} (B&H: {(bull_last-bull_first)/bull_first*100:+.1f}%)")
        print(f"  Bear price: ${bear_first:,.2f} → ${bear_last:,.2f} (B&H: {(bear_last-bear_first)/bear_first*100:+.1f}%)")

        # Run backtests
        strategy = MeanReversionStrategy(config=claimed["params"])
        cfg = BacktestConfig(initial_capital=250.0)

        bull_result = engine.run(strategy, bull_df.copy(), cfg)
        bear_result = engine.run(strategy, bear_df.copy(), cfg)

        bull_return = bull_result.report.total_return_pct if bull_result.report else 0
        bear_return = bear_result.report.total_return_pct if bear_result.report else 0
        combined = (bull_return + bear_return) / 2

        # Walk-forward validation
        strategy.reset()
        bull_wf = engine.walk_forward(strategy, bull_df.copy(), train_days=90, test_days=30, config=cfg)
        strategy.reset()
        bear_wf = engine.walk_forward(strategy, bear_df.copy(), train_days=90, test_days=30, config=cfg)

        # Verify against claimed
        bull_match = abs(bull_return - claimed["claimed_bull"]) < TOLERANCE
        bear_match = abs(bear_return - claimed["claimed_bear"]) < TOLERANCE
        combined_match = abs(combined - claimed["claimed_combined"]) < TOLERANCE

        bull_icon = "✅" if bull_match else "❌"
        bear_icon = "✅" if bear_match else "❌"
        combined_icon = "✅" if combined_match else "❌"

        print(f"\n  BULL:     claimed={claimed['claimed_bull']:>+7.1f}%  actual={bull_return:>+7.1f}%  {bull_icon} {'MATCH' if bull_match else 'MISMATCH'}")
        print(f"  BEAR:     claimed={claimed['claimed_bear']:>+7.1f}%  actual={bear_return:>+7.1f}%  {bear_icon} {'MATCH' if bear_match else 'MISMATCH'}")
        print(f"  COMBINED: claimed={claimed['claimed_combined']:>+7.1f}%  actual={combined:>+7.1f}%  {combined_icon} {'MATCH' if combined_match else 'MISMATCH'}")

        # Detailed metrics
        if bull_result.report:
            r = bull_result.report
            print(f"\n  Bull detail: trades={r.total_trades}, win_rate={r.win_rate:.0%}, sharpe={r.sharpe_ratio:.2f}, max_dd={r.max_drawdown_pct:.1f}%, PF={r.profit_factor:.2f}")
            print(f"    avg_win=${r.avg_win:.2f}, avg_loss=${r.avg_loss:.2f}, equity_start=$250, equity_end=${250*(1+r.total_return_pct/100):.2f}")
        if bear_result.report:
            r = bear_result.report
            print(f"  Bear detail: trades={r.total_trades}, win_rate={r.win_rate:.0%}, sharpe={r.sharpe_ratio:.2f}, max_dd={r.max_drawdown_pct:.1f}%, PF={r.profit_factor:.2f}")
            print(f"    avg_win=${r.avg_win:.2f}, avg_loss=${r.avg_loss:.2f}, equity_start=$250, equity_end=${250*(1+r.total_return_pct/100):.2f}")

        # Walk-forward
        bull_wf_status = "PASS" if bull_wf.get("consistent") else f"FAIL ({bull_wf.get('window_win_rate', 0):.0%} win windows)"
        bear_wf_status = "PASS" if bear_wf.get("consistent") else f"FAIL ({bear_wf.get('window_win_rate', 0):.0%} win windows)"
        print(f"\n  Walk-Forward (90d/30d): bull={bull_wf_status}, bear={bear_wf_status}")

        if not (bull_match and bear_match and combined_match):
            all_pass = False

        verified_results[pair] = {
            "bull_return": bull_return,
            "bear_return": bear_return,
            "combined": combined,
            "bull_wf": bull_wf.get("consistent", False),
            "bear_wf": bear_wf.get("consistent", False),
            "bull_wf_win_rate": bull_wf.get("window_win_rate", 0),
            "bear_wf_win_rate": bear_wf.get("window_win_rate", 0),
        }

    # Portfolio verification
    print(f"\n{'='*80}")
    print("  PORTFOLIO VERIFICATION")
    print(f"{'='*80}")

    profitable = {k: v for k, v in verified_results.items() if v["combined"] > 0}
    if profitable:
        eq_avg = sum(v["combined"] for v in profitable.values()) / len(profitable)
        print(f"\n  Equal-weight ({len(profitable)} profitable assets): {eq_avg:+.1f}%")
        print(f"  Claimed: +22.8%")
        print(f"  {'✅ MATCH' if abs(eq_avg - 22.8) < 1.0 else '❌ MISMATCH'}")

    for pair, v in sorted(verified_results.items(), key=lambda x: x[1]["combined"], reverse=True):
        wf_bull = "✅" if v["bull_wf"] else f"❌({v['bull_wf_win_rate']:.0%})"
        wf_bear = "✅" if v["bear_wf"] else f"❌({v['bear_wf_win_rate']:.0%})"
        print(f"    {pair:<10} combined={v['combined']:>+7.1f}%  WF bull={wf_bull:<12} WF bear={wf_bear}")

    # Final verdict
    print(f"\n{'='*80}")
    if all_pass:
        print("  ✅ ALL RESULTS VERIFIED — numbers match claimed values")
    else:
        print("  ❌ SOME RESULTS DO NOT MATCH — investigate discrepancies")
    print(f"{'='*80}")


if __name__ == "__main__":
    asyncio.run(main())
