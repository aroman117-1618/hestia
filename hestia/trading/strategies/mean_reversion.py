"""
Mean Reversion Strategy — crypto-optimized RSI with filters.

Uses RSI-7/9 with 20/80 thresholds (NOT the standard 14-period 30/70
equity defaults — those produce delayed signals in crypto markets).

Entry requires:
1. RSI below 20 (oversold) or above 80 (overbought)
2. Volume confirmation: >= 1.5x 20-period average
3. Trend filter: 50-period SMA direction check (avoid momentum traps)
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType

logger = get_logger()


class MeanReversionStrategy(BaseStrategy):
    """
    Crypto-optimized mean reversion with multi-filter confirmation.

    Profits from temporary price extremes that revert to the mean.
    CRITICAL: Hard stop-losses are non-negotiable — without them,
    "falling knife" entries can be catastrophic in breakout markets.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.rsi_period = self.config.get("rsi_period", 7)
        self.rsi_oversold = self.config.get("rsi_oversold", 20)
        self.rsi_overbought = self.config.get("rsi_overbought", 80)
        self.rsi_exit_buy = self.config.get("rsi_exit_buy", 70)  # Take profit after BUY
        self.rsi_exit_sell = self.config.get("rsi_exit_sell", 30)  # Take profit after SELL
        self.volume_confirmation = self.config.get("volume_confirmation", 1.5)
        self.trend_filter_period = self.config.get("trend_filter_period", 50)
        self.stop_loss_pct = self.config.get("stop_loss_pct", 0.03)  # 3% hard stop
        # Track open position for exit logic
        self._last_entry: Optional[Dict[str, Any]] = None  # {side, price, quantity}

    def reset(self) -> None:
        """Clear open position state for walk-forward windows."""
        self._last_entry = None

    def indicator_periods(self) -> Dict[str, int]:
        """Expose RSI and SMA periods for the backtest engine."""
        return {"rsi_period": self.rsi_period, "sma_period": self.trend_filter_period}

    @property
    def name(self) -> str:
        return f"Mean Reversion (RSI-{self.rsi_period})"

    @property
    def strategy_type(self) -> str:
        return "mean_reversion"

    def analyze(self, df: pd.DataFrame, portfolio_value: float, timestamp: Optional[datetime] = None) -> Signal:
        """
        Generate mean reversion signals with triple confirmation.

        1. RSI extreme (< oversold or > overbought)
        2. Volume surge (> 1.5x average)
        3. Trend alignment (SMA direction supports entry)
        """
        min_rows = max(self.rsi_period, self.trend_filter_period) + 5
        if len(df) < min_rows:
            return Signal(reason=f"Need {min_rows} candles, have {len(df)}")

        current = df.iloc[-1]
        current_price = float(current["close"])

        # Get indicators (expect them pre-computed)
        current_rsi = float(current.get("rsi", 50.0))
        current_volume_ratio = float(current.get("volume_ratio", 1.0))
        current_sma = float(current.get("sma", current_price))

        # ── Exit logic: check open position first ────────────
        if self._last_entry is not None:
            entry = self._last_entry

            if entry["side"] == "buy":
                # Stop-loss: hard exit if price drops below entry - stop_loss_pct
                stop_price = entry["price"] * (1 - self.stop_loss_pct)
                if current_price <= stop_price:
                    self._last_entry = None
                    return Signal(
                        signal_type=SignalType.SELL,
                        pair=self.pair,
                        price=current_price,
                        quantity=entry["quantity"],
                        confidence=0.9,
                        reason=f"Stop-loss hit: price ${current_price:,.2f} <= "
                               f"stop ${stop_price:,.2f} ({self.stop_loss_pct:.0%} from entry)",
                        metadata={"exit_type": "stop_loss", "entry_price": entry["price"]},
                    )

                # Profit exit: RSI reverted above exit threshold
                if current_rsi > self.rsi_exit_buy:
                    self._last_entry = None
                    pnl_pct = (current_price - entry["price"]) / entry["price"]
                    return Signal(
                        signal_type=SignalType.SELL,
                        pair=self.pair,
                        price=current_price,
                        quantity=entry["quantity"],
                        confidence=0.8,
                        reason=f"Mean reverted: RSI={current_rsi:.1f} > {self.rsi_exit_buy}, "
                               f"P&L={pnl_pct:+.1%}",
                        metadata={
                            "exit_type": "mean_reversion_profit",
                            "entry_price": entry["price"],
                            "pnl_pct": pnl_pct,
                        },
                    )

            elif entry["side"] == "sell":
                # Stop-loss for short: price rises above entry + stop_loss_pct
                stop_price = entry["price"] * (1 + self.stop_loss_pct)
                if current_price >= stop_price:
                    self._last_entry = None
                    return Signal(
                        signal_type=SignalType.BUY,
                        pair=self.pair,
                        price=current_price,
                        quantity=entry["quantity"],
                        confidence=0.9,
                        reason=f"Stop-loss hit: price ${current_price:,.2f} >= "
                               f"stop ${stop_price:,.2f} ({self.stop_loss_pct:.0%} from entry)",
                        metadata={"exit_type": "stop_loss", "entry_price": entry["price"]},
                    )

                # Profit exit: RSI reverted below exit threshold
                if current_rsi < self.rsi_exit_sell:
                    self._last_entry = None
                    pnl_pct = (entry["price"] - current_price) / entry["price"]
                    return Signal(
                        signal_type=SignalType.BUY,
                        pair=self.pair,
                        price=current_price,
                        quantity=entry["quantity"],
                        confidence=0.8,
                        reason=f"Mean reverted: RSI={current_rsi:.1f} < {self.rsi_exit_sell}, "
                               f"P&L={pnl_pct:+.1%}",
                        metadata={
                            "exit_type": "mean_reversion_profit",
                            "entry_price": entry["price"],
                            "pnl_pct": pnl_pct,
                        },
                    )

            # Still in position, no exit triggered
            return Signal(
                reason=f"Holding {entry['side']} from ${entry['price']:,.2f} — "
                       f"RSI={current_rsi:.1f}, waiting for exit",
                metadata={"holding": entry["side"], "entry_price": entry["price"]},
            )

        # ── Filter 1: RSI extreme ──────────────────────────────
        is_oversold = current_rsi < self.rsi_oversold
        is_overbought = current_rsi > self.rsi_overbought

        if not is_oversold and not is_overbought:
            return Signal(
                reason=f"RSI {current_rsi:.1f} — neutral zone ({self.rsi_oversold}-{self.rsi_overbought})",
                metadata={"rsi": current_rsi},
            )

        # ── Filter 2: Volume confirmation ──────────────────────
        has_volume = current_volume_ratio >= self.volume_confirmation

        if not has_volume:
            return Signal(
                reason=f"RSI extreme ({current_rsi:.1f}) but insufficient volume "
                       f"({current_volume_ratio:.2f}x < {self.volume_confirmation}x required)",
                metadata={"rsi": current_rsi, "volume_ratio": current_volume_ratio},
            )

        # ── Filter 3: Trend alignment ─────────────────────────
        # For oversold buys: price should be near/above SMA (mean reversion context)
        # For overbought sells: price should be near/below SMA
        # Avoid buying in strong downtrends ("falling knife")
        trend_up = current_price > current_sma
        trend_down = current_price < current_sma

        if is_oversold:
            # Check ADX to avoid momentum traps
            current_adx = float(current.get("adx", 0.0))
            if current_adx > 25 and trend_down:
                return Signal(
                    reason=f"RSI oversold ({current_rsi:.1f}) but strong downtrend "
                           f"(ADX={current_adx:.1f}, price below SMA) — momentum trap risk",
                    metadata={"rsi": current_rsi, "adx": current_adx, "filter": "trend"},
                )

            # BUY signal — oversold with volume and no momentum trap
            confidence = self._calculate_confidence(current_rsi, current_volume_ratio, is_buy=True)
            per_trade_value = portfolio_value * 0.10  # 10% per mean reversion trade
            quantity = per_trade_value / current_price if current_price > 0 else 0.0

            # Track entry for exit logic
            self._last_entry = {"side": "buy", "price": current_price, "quantity": quantity}

            return Signal(
                signal_type=SignalType.BUY,
                pair=self.pair,
                price=current_price,
                quantity=quantity,
                confidence=confidence,
                reason=f"Oversold: RSI={current_rsi:.1f}, volume={current_volume_ratio:.2f}x, "
                       f"stop-loss at {current_price * (1 - self.stop_loss_pct):.2f}",
                metadata={
                    "rsi": current_rsi,
                    "volume_ratio": current_volume_ratio,
                    "sma": current_sma,
                    "stop_loss": current_price * (1 - self.stop_loss_pct),
                    "entry_type": "oversold_reversal",
                },
            )

        if is_overbought:
            current_adx = float(current.get("adx", 0.0))
            if current_adx > 25 and trend_up:
                return Signal(
                    reason=f"RSI overbought ({current_rsi:.1f}) but strong uptrend "
                           f"(ADX={current_adx:.1f}, price above SMA) — momentum continuation likely",
                    metadata={"rsi": current_rsi, "adx": current_adx, "filter": "trend"},
                )

            # SELL signal — overbought with volume
            confidence = self._calculate_confidence(current_rsi, current_volume_ratio, is_buy=False)
            per_trade_value = portfolio_value * 0.10
            quantity = per_trade_value / current_price if current_price > 0 else 0.0

            # Track entry for exit logic
            self._last_entry = {"side": "sell", "price": current_price, "quantity": quantity}

            return Signal(
                signal_type=SignalType.SELL,
                pair=self.pair,
                price=current_price,
                quantity=quantity,
                confidence=confidence,
                reason=f"Overbought: RSI={current_rsi:.1f}, volume={current_volume_ratio:.2f}x",
                metadata={
                    "rsi": current_rsi,
                    "volume_ratio": current_volume_ratio,
                    "sma": current_sma,
                    "entry_type": "overbought_reversal",
                },
            )

        return Signal(reason="No signal")

    def _calculate_confidence(
        self, rsi: float, volume_ratio: float, is_buy: bool
    ) -> float:
        """
        Calculate signal confidence from indicator strength.

        More extreme RSI + higher volume = higher confidence.
        """
        if is_buy:
            rsi_strength = max(0, (self.rsi_oversold - rsi) / self.rsi_oversold)
        else:
            rsi_strength = max(0, (rsi - self.rsi_overbought) / (100 - self.rsi_overbought))

        volume_strength = min(1.0, (volume_ratio - 1.0) / 2.0)
        confidence = 0.5 + (rsi_strength * 0.3) + (volume_strength * 0.2)
        return min(1.0, max(0.0, confidence))

    def validate_config(self) -> List[str]:
        warnings = []
        if self.rsi_period == 14:
            warnings.append(
                "RSI-14 is the equity default — crypto markets respond better to RSI-7 or RSI-9"
            )
        if self.rsi_oversold >= 30:
            warnings.append(
                f"Oversold threshold {self.rsi_oversold} is conservative for crypto — consider 20"
            )
        if self.rsi_overbought <= 70:
            warnings.append(
                f"Overbought threshold {self.rsi_overbought} is conservative for crypto — consider 80"
            )
        if self.stop_loss_pct <= 0:
            warnings.append("CRITICAL: Mean reversion without stop-loss is extremely dangerous")
        return warnings
