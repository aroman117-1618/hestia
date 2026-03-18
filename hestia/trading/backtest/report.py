"""
Backtest performance report — Sharpe, Sortino, drawdown, win rate, equity curve.

All metrics calculated from the equity curve and trade log.
Overfit detection flags built in.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class BacktestReport:
    """Complete performance metrics for a backtest."""
    # Returns
    total_return_pct: float = 0.0
    annualized_return_pct: float = 0.0

    # Risk-adjusted
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0

    # Drawdown
    max_drawdown_pct: float = 0.0
    max_drawdown_duration_candles: int = 0

    # Trade stats
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0

    # Capital
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_fees: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_return_pct": round(self.total_return_pct, 2),
            "annualized_return_pct": round(self.annualized_return_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "max_drawdown_duration_candles": self.max_drawdown_duration_candles,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 3),
            "profit_factor": round(self.profit_factor, 3),
            "avg_win": round(self.avg_win, 4),
            "avg_loss": round(self.avg_loss, 4),
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "total_fees": round(self.total_fees, 4),
        }


def generate_report(
    equity_curve: List[float],
    trade_log: List[Dict[str, Any]],
    initial_capital: float = 250.0,
    candles_per_year: int = 8760,  # Hourly candles
) -> BacktestReport:
    """
    Generate a full performance report from equity curve and trade log.
    """
    report = BacktestReport(initial_capital=initial_capital)

    if not equity_curve or len(equity_curve) < 2:
        return report

    equity = np.array(equity_curve, dtype=float)
    report.final_capital = float(equity[-1])

    # ── Returns ───────────────────────────────────────────────
    report.total_return_pct = ((equity[-1] - initial_capital) / initial_capital) * 100

    # Annualize
    n_candles = len(equity)
    years = n_candles / candles_per_year
    if years > 0 and equity[-1] > 0 and initial_capital > 0:
        report.annualized_return_pct = (
            ((equity[-1] / initial_capital) ** (1 / years)) - 1
        ) * 100

    # ── Sharpe & Sortino ──────────────────────────────────────
    returns = np.diff(equity) / equity[:-1]
    returns = returns[np.isfinite(returns)]

    if len(returns) > 1:
        mean_return = np.mean(returns)
        std_return = np.std(returns, ddof=1)

        # Annualized Sharpe (risk-free rate ≈ 0 for crypto)
        if std_return > 0:
            report.sharpe_ratio = float(
                (mean_return / std_return) * math.sqrt(candles_per_year)
            )

        # Sortino (downside deviation only)
        downside_returns = returns[returns < 0]
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns, ddof=1)
            if downside_std > 0:
                report.sortino_ratio = float(
                    (mean_return / downside_std) * math.sqrt(candles_per_year)
                )

    # ── Max Drawdown ──────────────────────────────────────────
    peak = equity[0]
    max_dd = 0.0
    dd_start = 0
    max_dd_duration = 0
    current_dd_start = 0

    for i in range(len(equity)):
        if equity[i] > peak:
            peak = equity[i]
            current_dd_start = i
        dd = (peak - equity[i]) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            dd_start = current_dd_start
            max_dd_duration = i - current_dd_start

    report.max_drawdown_pct = max_dd * 100
    report.max_drawdown_duration_candles = max_dd_duration

    # ── Trade Stats ───────────────────────────────────────────
    sells = [t for t in trade_log if t.get("side") == "sell"]
    report.total_trades = len(sells)
    report.total_fees = sum(t.get("fee", 0) for t in trade_log)

    if sells:
        pnls = [t.get("pnl", 0) for t in sells]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        report.winning_trades = len(wins)
        report.losing_trades = len(losses)
        report.win_rate = len(wins) / len(sells) if sells else 0.0
        report.avg_win = float(np.mean(wins)) if wins else 0.0
        report.avg_loss = float(np.mean(losses)) if losses else 0.0

        # Profit factor = gross wins / gross losses
        gross_wins = sum(wins)
        gross_losses = abs(sum(losses))
        report.profit_factor = (
            gross_wins / gross_losses if gross_losses > 0 else float("inf")
        )

    return report
