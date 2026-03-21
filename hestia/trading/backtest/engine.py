"""
Backtesting engine — runs strategies against historical data.

Uses VectorBT for vectorized performance calculations.
Anti-overfit guardrails built in: look-ahead bias prevention,
walk-forward validation, overfit detection.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.backtest.report import BacktestReport, generate_report
from hestia.trading.data.indicators import add_all_indicators
from hestia.trading.strategies.base import BaseStrategy, SignalType

logger = get_logger()

# Fee tiers — Coinbase <$10K monthly volume
DEFAULT_MAKER_FEE = 0.004  # 0.40%
DEFAULT_TAKER_FEE = 0.006  # 0.60%


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""
    pair: str = "BTC-USD"
    initial_capital: float = 250.0
    maker_fee: float = DEFAULT_MAKER_FEE
    taker_fee: float = DEFAULT_TAKER_FEE
    slippage: float = 0.001  # 0.10%
    use_post_only: bool = True  # Maker orders by default
    lookback_shift: int = 1  # Shift signals back N candles (anti look-ahead)
    stop_loss_pct: float = 0.0      # 0 = disabled, 0.03 = 3% stop-loss
    take_profit_pct: float = 0.0    # 0 = disabled, 0.025 = 2.5% take-profit


@dataclass
class BacktestResult:
    """Complete result of a backtest run."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    config: BacktestConfig = field(default_factory=BacktestConfig)
    strategy_name: str = ""
    strategy_type: str = ""
    report: Optional[BacktestReport] = None
    signals: List[Dict[str, Any]] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "strategy_name": self.strategy_name,
            "strategy_type": self.strategy_type,
            "report": self.report.to_dict() if self.report else None,
            "signal_count": len(self.signals),
            "equity_curve_length": len(self.equity_curve),
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat(),
        }


class BacktestEngine:
    """
    Runs strategies against historical data with realistic conditions.

    Key features:
    - Maker/taker fee modeling (not flat fee)
    - Slippage simulation
    - Look-ahead bias prevention (signal shift)
    - Walk-forward validation
    - Overfit detection
    """

    def __init__(self, config: Optional[BacktestConfig] = None) -> None:
        self.config = config or BacktestConfig()

    def run(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        config: Optional[BacktestConfig] = None,
    ) -> BacktestResult:
        """
        Run a backtest for a single strategy on historical data.

        Args:
            strategy: Strategy instance to test
            data: OHLCV DataFrame (raw — indicators will be computed)
            config: Override config for this run
        """
        cfg = config or self.config
        result = BacktestResult(
            config=cfg,
            strategy_name=strategy.name,
            strategy_type=strategy.strategy_type,
        )

        # Validate strategy config
        warnings = strategy.validate_config()
        result.warnings.extend(warnings)

        if len(data) < 60:
            result.warnings.append(f"Only {len(data)} candles — results may be unreliable")

        # Compute indicators
        df = add_all_indicators(data[["open", "high", "low", "close", "volume"]].copy())

        # Generate signals with look-ahead bias prevention
        signals = self._generate_signals(strategy, df, cfg)
        result.signals = signals

        # Simulate trades
        equity_curve, trade_log = self._simulate_trades(signals, df, cfg)
        result.equity_curve = equity_curve

        # Generate performance report
        result.report = generate_report(
            equity_curve=equity_curve,
            trade_log=trade_log,
            initial_capital=cfg.initial_capital,
        )

        # Overfit detection
        overfit_warnings = self._check_overfit(result.report)
        result.warnings.extend(overfit_warnings)

        logger.info(
            f"Backtest complete: {strategy.name} — "
            f"return={result.report.total_return_pct:.1f}%, "
            f"sharpe={result.report.sharpe_ratio:.2f}, "
            f"max_dd={result.report.max_drawdown_pct:.1f}%",
            component=LogComponent.TRADING,
            data={"id": result.id, "trades": result.report.total_trades},
        )
        return result

    def walk_forward(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        train_days: int = 30,
        test_days: int = 7,
        config: Optional[BacktestConfig] = None,
    ) -> Dict[str, Any]:
        """
        Walk-forward validation: train on N days, test on M days, slide forward.

        This is the gold standard for strategy validation. If a strategy
        works in-sample but fails out-of-sample across multiple windows,
        it's overfit.
        """
        cfg = config or self.config

        if "timestamp" not in data.columns:
            # Assume hourly candles, create synthetic timestamps
            data = data.copy()
            data["timestamp"] = pd.date_range(
                end=datetime.now(timezone.utc), periods=len(data), freq="h"
            )

        candles_per_day = 24  # Assuming hourly
        train_size = train_days * candles_per_day
        test_size = test_days * candles_per_day
        window_size = train_size + test_size

        if len(data) < window_size:
            return {
                "valid": False,
                "reason": f"Need {window_size} candles for walk-forward, have {len(data)}",
                "windows": [],
            }

        # 200 candles covers any indicator lookback (RSI-14, SMA-200, etc.)
        warmup_size = 200

        windows = []
        start = 0

        while start + window_size <= len(data):
            train_data = data.iloc[start:start + train_size].reset_index(drop=True)
            test_data = data.iloc[start + train_size:start + window_size].reset_index(drop=True)

            # Reset any accumulated strategy state (e.g. DCA interval gate) so
            # each test window begins as if the strategy were freshly instantiated.
            strategy.reset()

            # Prepend the tail of training data as warmup so indicators (RSI, SMA,
            # Bollinger, etc.) are fully primed when the test period starts.
            # Warmup candles are used for indicator calculation only — we generate
            # signals across the full warmup+test frame but only execute the signals
            # that fall within the test portion.  This gives each window a fresh
            # initial_capital baseline free of any training-period position state.
            actual_warmup = min(warmup_size, len(train_data))
            warmup_data = train_data.iloc[-actual_warmup:] if actual_warmup > 0 else pd.DataFrame()
            test_with_warmup = pd.concat([warmup_data, test_data], ignore_index=True)

            # Compute indicators once for the full warmup+test frame.
            df_combined = add_all_indicators(
                test_with_warmup[["open", "high", "low", "close", "volume"]].copy()
            )

            # Generate signals across the combined frame (indicators are valid throughout).
            all_signals = self._generate_signals(strategy, df_combined, cfg)

            # Only execute signals from the test portion — warmup signals are discarded.
            # Re-index signals so that candle index 0 maps to the start of the test slice.
            test_signals = [
                {**s, "index": s["index"] - actual_warmup}
                for s in all_signals
                if s["index"] >= actual_warmup
            ]

            # Simulate trades on the test candles only, starting with fresh capital.
            test_df = df_combined.iloc[actual_warmup:].reset_index(drop=True)
            test_equity, _ = self._simulate_trades(test_signals, test_df, cfg)

            if len(test_equity) >= 2:
                test_return = (test_equity[-1] - test_equity[0]) / test_equity[0] if test_equity[0] > 0 else 0.0
            else:
                test_return = 0.0

            windows.append({
                "window": len(windows) + 1,
                "train_start": start,
                "test_start": start + train_size,
                "test_end": start + window_size,
                "test_return": test_return,
                "test_first_equity": test_equity[0] if test_equity else None,
                "test_trades": len([s for s in test_signals if s.get("signal_type") != "hold"]),
            })

            start += test_size  # Slide forward by test_size

        # Aggregate
        test_returns = [w["test_return"] for w in windows]
        avg_return = np.mean(test_returns) if test_returns else 0.0
        win_windows = sum(1 for r in test_returns if r > 0)

        return {
            "valid": True,
            "windows": windows,
            "total_windows": len(windows),
            "avg_test_return": float(avg_return),
            "win_windows": win_windows,
            "loss_windows": len(windows) - win_windows,
            "window_win_rate": win_windows / len(windows) if windows else 0.0,
            "consistent": avg_return > 0 and win_windows / len(windows) > 0.5 if windows else False,
        }

    def train_test_split(
        self,
        strategy: BaseStrategy,
        data: pd.DataFrame,
        train_pct: float = 0.7,
        config: Optional[BacktestConfig] = None,
    ) -> Dict[str, Any]:
        """
        Simple 70/30 train/test split validation.

        Run strategy on full data, report in-sample vs out-of-sample performance.
        """
        cfg = config or self.config
        split_idx = int(len(data) * train_pct)

        train_result = self.run(strategy, data.iloc[:split_idx].reset_index(drop=True), cfg)
        test_result = self.run(strategy, data.iloc[split_idx:].reset_index(drop=True), cfg)

        return {
            "train": {
                "candles": split_idx,
                "report": train_result.report.to_dict() if train_result.report else None,
                "warnings": train_result.warnings,
            },
            "test": {
                "candles": len(data) - split_idx,
                "report": test_result.report.to_dict() if test_result.report else None,
                "warnings": test_result.warnings,
            },
            "overfit_risk": self._assess_overfit_risk(train_result.report, test_result.report),
        }

    # ── Internal ──────────────────────────────────────────────

    def _generate_signals(
        self, strategy: BaseStrategy, df: pd.DataFrame, cfg: BacktestConfig
    ) -> List[Dict[str, Any]]:
        """Generate signals with look-ahead bias prevention."""
        signals = []
        portfolio_value = cfg.initial_capital

        for i in range(cfg.lookback_shift, len(df)):
            # Strategy sees data up to i - lookback_shift (can't see current candle close)
            window = df.iloc[:i - cfg.lookback_shift + 1]
            if len(window) < 20:
                continue

            # Pass candle timestamp so time-gated strategies (e.g. DCA) use simulation time
            ts: Optional[datetime] = None
            if "timestamp" in df.columns:
                ts = df.iloc[i]["timestamp"]
                if hasattr(ts, "to_pydatetime"):
                    ts = ts.to_pydatetime()

            signal = strategy.analyze(window, portfolio_value, timestamp=ts)
            signals.append({
                "index": i,
                "signal_type": signal.signal_type.value,
                "price": float(df.iloc[i]["close"]),  # Execute at current candle
                "quantity": signal.quantity,
                "confidence": signal.confidence,
                "reason": signal.reason,
            })

        return signals

    def _simulate_trades(
        self,
        signals: List[Dict[str, Any]],
        df: pd.DataFrame,
        cfg: BacktestConfig,
    ) -> Tuple[List[float], List[Dict[str, Any]]]:
        """Simulate trade execution with fees and slippage."""
        cash = cfg.initial_capital
        position_qty = 0.0
        position_cost = 0.0
        equity_curve = []
        trade_log = []

        fee_rate = cfg.maker_fee if cfg.use_post_only else cfg.taker_fee

        for i in range(len(df)):
            current_price = float(df.iloc[i]["close"])

            # Check if there's a signal for this candle
            matching = [s for s in signals if s["index"] == i and s["signal_type"] != "hold"]

            for sig in matching:
                qty = sig["quantity"]
                if qty <= 0:
                    continue

                if sig["signal_type"] == "buy" and cash > 0:
                    # Apply slippage (price moves up for buys)
                    fill_price = current_price * (1 + cfg.slippage)
                    trade_value = fill_price * qty
                    fee = trade_value * fee_rate
                    total_cost = trade_value + fee

                    if total_cost > cash:
                        qty = (cash * 0.95) / (fill_price * (1 + fee_rate))
                        if qty <= 0:
                            continue
                        trade_value = fill_price * qty
                        fee = trade_value * fee_rate
                        total_cost = trade_value + fee

                    cash -= total_cost
                    position_qty += qty
                    position_cost += total_cost

                    trade_log.append({
                        "index": i,
                        "side": "buy",
                        "price": fill_price,
                        "quantity": qty,
                        "fee": fee,
                        "cash_after": cash,
                    })

                elif sig["signal_type"] == "sell" and position_qty > 0:
                    sell_qty = min(qty, position_qty)
                    fill_price = current_price * (1 - cfg.slippage)
                    proceeds = fill_price * sell_qty
                    fee = proceeds * fee_rate
                    net_proceeds = proceeds - fee

                    # P&L
                    avg_cost = position_cost / position_qty if position_qty > 0 else 0
                    cost_of_sold = avg_cost * sell_qty
                    pnl = net_proceeds - cost_of_sold

                    cash += net_proceeds
                    position_qty -= sell_qty
                    position_cost -= cost_of_sold
                    if position_qty < 1e-10:
                        position_qty = 0.0
                        position_cost = 0.0

                    trade_log.append({
                        "index": i,
                        "side": "sell",
                        "price": fill_price,
                        "quantity": sell_qty,
                        "fee": fee,
                        "pnl": pnl,
                        "cash_after": cash,
                    })

            # After signal processing, check intra-candle exits for open positions
            if position_qty > 0 and (cfg.stop_loss_pct > 0 or cfg.take_profit_pct > 0):
                candle_low = float(df.iloc[i]["low"])
                candle_high = float(df.iloc[i]["high"])
                avg_entry = position_cost / position_qty

                # Stop-loss: check first (conservative assumption when both trigger same candle)
                if cfg.stop_loss_pct > 0:
                    stop_level = avg_entry * (1 - cfg.stop_loss_pct)
                    if candle_low <= stop_level:
                        fill_price = stop_level * (1 - cfg.slippage)
                        proceeds = fill_price * position_qty
                        fee = proceeds * fee_rate
                        net_proceeds = proceeds - fee
                        pnl = net_proceeds - position_cost

                        cash += net_proceeds
                        trade_log.append({
                            "index": i,
                            "side": "sell",
                            "price": fill_price,
                            "quantity": position_qty,
                            "fee": fee,
                            "pnl": pnl,
                            "cash_after": cash,
                            "exit_type": "stop_loss",
                        })
                        position_qty = 0.0
                        position_cost = 0.0

                # Profit target: only check if position still open (stop may have triggered first)
                if position_qty > 0 and cfg.take_profit_pct > 0:
                    target_level = avg_entry * (1 + cfg.take_profit_pct)
                    if candle_high >= target_level:
                        fill_price = target_level * (1 - cfg.slippage)
                        proceeds = fill_price * position_qty
                        fee = proceeds * fee_rate
                        net_proceeds = proceeds - fee
                        pnl = net_proceeds - position_cost

                        cash += net_proceeds
                        trade_log.append({
                            "index": i,
                            "side": "sell",
                            "price": fill_price,
                            "quantity": position_qty,
                            "fee": fee,
                            "pnl": pnl,
                            "cash_after": cash,
                            "exit_type": "take_profit",
                        })
                        position_qty = 0.0
                        position_cost = 0.0

            # Equity = cash + position market value
            equity = cash + (position_qty * current_price)
            equity_curve.append(equity)

        return equity_curve, trade_log

    def _check_overfit(self, report: Optional[BacktestReport]) -> List[str]:
        """Flag potential overfitting indicators."""
        if report is None:
            return []
        warnings = []
        if report.sharpe_ratio > 3.0:
            warnings.append(
                f"OVERFIT WARNING: Sharpe ratio {report.sharpe_ratio:.2f} > 3.0 — "
                "likely curve-fitted to historical data"
            )
        if report.win_rate > 0.70:
            warnings.append(
                f"OVERFIT WARNING: Win rate {report.win_rate:.0%} > 70% — "
                "suspiciously high, verify with walk-forward"
            )
        if report.profit_factor > 3.0:
            warnings.append(
                f"OVERFIT WARNING: Profit factor {report.profit_factor:.2f} > 3.0 — "
                "may not hold out-of-sample"
            )
        return warnings

    def _assess_overfit_risk(
        self,
        train_report: Optional[BacktestReport],
        test_report: Optional[BacktestReport],
    ) -> str:
        """Compare train vs test performance to assess overfit risk."""
        if not train_report or not test_report:
            return "unknown"

        # If test Sharpe is less than half of train Sharpe → likely overfit
        if train_report.sharpe_ratio > 0 and test_report.sharpe_ratio > 0:
            ratio = test_report.sharpe_ratio / train_report.sharpe_ratio
            if ratio < 0.3:
                return "high — test Sharpe is <30% of train Sharpe"
            elif ratio < 0.6:
                return "moderate — test performance degrades significantly"
            else:
                return "low — consistent performance across train/test"

        if test_report.total_return_pct < 0 and train_report.total_return_pct > 0:
            return "high — profitable in-sample but losing out-of-sample"

        return "low"
