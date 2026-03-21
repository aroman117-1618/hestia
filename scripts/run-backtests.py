#!/usr/bin/env python3
"""
Run backtests for all 4 trading strategies against 1 year of BTC-USD hourly data.

Sprint 27.5 WS1: Validate strategy foundation before expanding scope.
"""

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from hestia.trading.backtest.data_loader import DataLoader
from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
from hestia.trading.strategies.mean_reversion import MeanReversionStrategy
from hestia.trading.strategies.grid import GridStrategy
from hestia.trading.strategies.signal_dca import SignalDCAStrategy
from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy


async def fetch_data() -> "pd.DataFrame":
    """Fetch 1 year of BTC-USD hourly candles."""
    loader = DataLoader()
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=365)
    print(f"Fetching BTC-USD hourly candles: {start.date()} to {end.date()}...")
    df = await loader.fetch_from_coinbase("BTC-USD", "1h", start, end)
    print(f"Fetched {len(df)} candles ({len(df)/24:.0f} days)")
    return df


def run_backtest(engine, strategy, data, config):
    """Run a single backtest and print results."""
    print(f"\n{'='*60}")
    print(f"STRATEGY: {strategy.name}")
    print(f"{'='*60}")

    result = engine.run(strategy, data.copy(), config)
    report = result.report

    if report is None:
        print("  ERROR: No report generated")
        return None

    print(f"  Total Return:     {report.total_return_pct:+.2f}%")
    print(f"  Annualized:       {report.annualized_return_pct:+.2f}%")
    print(f"  Sharpe Ratio:     {report.sharpe_ratio:.2f}")
    print(f"  Sortino Ratio:    {report.sortino_ratio:.2f}")
    print(f"  Max Drawdown:     {report.max_drawdown_pct:.2f}%")
    print(f"  Total Trades:     {report.total_trades}")
    print(f"  Win Rate:         {report.win_rate:.1%}")
    print(f"  Profit Factor:    {report.profit_factor:.2f}")
    print(f"  Avg Win:          ${report.avg_win:.2f}")
    print(f"  Avg Loss:         ${report.avg_loss:.2f}")

    if result.warnings:
        print(f"  WARNINGS:")
        for w in result.warnings:
            print(f"    - {w}")

    return result


def run_walk_forward(engine, strategy, data, config):
    """Run walk-forward validation."""
    print(f"\n  Walk-Forward (30d train / 7d test):")
    wf = engine.walk_forward(strategy, data.copy(), train_days=30, test_days=7, config=config)

    if not wf.get("valid"):
        print(f"    {wf.get('reason', 'Unknown error')}")
        return wf

    print(f"    Windows:        {wf['total_windows']}")
    print(f"    Avg Test Return:{wf['avg_test_return']:+.2f}%")
    print(f"    Win Windows:    {wf['win_windows']}/{wf['total_windows']} ({wf['window_win_rate']:.0%})")
    print(f"    Consistent:     {'YES' if wf['consistent'] else 'NO'}")
    return wf


async def main():
    # Fetch data
    data = await fetch_data()
    if len(data) < 100:
        print("ERROR: Not enough data for backtesting")
        sys.exit(1)

    # Config
    config = BacktestConfig(
        pair="BTC-USD",
        initial_capital=250.0,
        maker_fee=0.004,
        taker_fee=0.006,
        slippage=0.001,
        use_post_only=True,
        lookback_shift=1,
    )

    engine = BacktestEngine(config)

    # Strategies
    strategies = [
        MeanReversionStrategy(config={
            "rsi_period": 7,
            "rsi_oversold": 20,
            "rsi_overbought": 80,
            "volume_confirmation": 1.5,
            "trend_filter_period": 50,
        }),
        GridStrategy(config={
            "spacing_type": "geometric",
            "num_levels": 10,
            "grid_width_atr_multiple": 2.0,
        }),
        SignalDCAStrategy(config={
            "rsi_period": 14,
            "rsi_threshold": 40,
            "ma_period": 50,
            "buy_interval_hours": 24,
        }),
        BollingerBreakoutStrategy(config={
            "period": 20,
            "std_dev": 2.0,
            "volume_confirmation": 1.5,
        }),
    ]

    # Run backtests
    results = {}
    for strategy in strategies:
        result = run_backtest(engine, strategy, data, config)
        if result and result.report:
            results[strategy.name] = result.report.to_dict()
            # Walk-forward validation
            wf = run_walk_forward(engine, strategy, data, config)
            results[strategy.name]["walk_forward"] = wf

    # Summary
    print(f"\n{'='*60}")
    print("PORTFOLIO SUMMARY")
    print(f"{'='*60}")
    print(f"{'Strategy':<25} {'Return':>8} {'Sharpe':>8} {'MaxDD':>8} {'Trades':>8} {'WinRate':>8}")
    print("-" * 73)

    for name, r in results.items():
        print(f"{name:<25} {r['total_return_pct']:>+7.1f}% {r['sharpe_ratio']:>7.2f} {r['max_drawdown_pct']:>7.1f}% {r['total_trades']:>7} {r['win_rate']:>7.0%}")

    # Save results
    output_path = Path(__file__).parent.parent / "data" / "backtest-results-2026-03-21.json"
    output_path.parent.mkdir(exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nResults saved to {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
