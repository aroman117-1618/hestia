"""
Signal-Enhanced DCA Strategy — accumulation with RSI + MA filter.

BUY when RSI < threshold AND price is below the moving average,
respecting a minimum interval between buys. Never sells —
this is a pure accumulation strategy for long-term holders.

The interval gate prevents overbuying during extended dips.
"""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType

logger = get_logger()


class SignalDCAStrategy(BaseStrategy):
    """
    Signal-enhanced dollar-cost averaging.

    Buys only when technical conditions are favorable (RSI oversold +
    price below MA), with a minimum interval between purchases.
    Never sells — accumulation only.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.rsi_period = self.config.get("rsi_period", 14)
        self.rsi_threshold = self.config.get("rsi_threshold", 40)
        self.ma_period = self.config.get("ma_period", 50)
        self.buy_interval_hours = self.config.get("buy_interval_hours", 24)
        self._last_buy_time: Optional[datetime] = None

    def reset(self) -> None:
        """Clear the interval gate so each walk-forward window starts fresh."""
        self._last_buy_time = None

    @property
    def name(self) -> str:
        return "Signal-Enhanced DCA"

    @property
    def strategy_type(self) -> str:
        return "signal_dca"

    def analyze(self, df: pd.DataFrame, portfolio_value: float, timestamp: Optional[datetime] = None) -> Signal:
        """
        Generate DCA buy signals with RSI + MA confirmation.

        1. RSI below threshold (default 40) — oversold or weakening
        2. Price below MA (default 50-period) — discount zone
        3. Interval gate: min hours since last buy
        4. Never generates SELL signals
        """
        min_rows = max(self.rsi_period, self.ma_period) + 5
        if len(df) < min_rows:
            return Signal(reason=f"Need {min_rows} candles, have {len(df)}")

        current = df.iloc[-1]
        current_price = float(current["close"])
        current_rsi = float(current.get("rsi", 50.0))
        current_sma = float(current.get("sma", current_price))

        # Check RSI condition
        rsi_favorable = current_rsi < self.rsi_threshold
        if not rsi_favorable:
            return Signal(
                reason=f"RSI {current_rsi:.1f} >= threshold {self.rsi_threshold} — waiting for dip",
                metadata={"rsi": current_rsi, "sma": current_sma},
            )

        # Check MA condition
        below_ma = current_price < current_sma
        if not below_ma:
            return Signal(
                reason=f"Price ${current_price:,.2f} above MA ${current_sma:,.2f} — waiting for discount",
                metadata={"rsi": current_rsi, "sma": current_sma, "price": current_price},
            )

        # Check interval gate — use candle timestamp in backtests, wall-clock in live trading
        now = timestamp or datetime.now(timezone.utc)
        if self._last_buy_time is not None:
            min_interval = timedelta(hours=self.buy_interval_hours)
            elapsed = now - self._last_buy_time
            if elapsed < min_interval:
                remaining = min_interval - elapsed
                return Signal(
                    reason=f"Conditions met but interval gate active — "
                           f"{remaining.total_seconds() / 3600:.1f}h remaining",
                    metadata={
                        "rsi": current_rsi,
                        "sma": current_sma,
                        "last_buy": self._last_buy_time.isoformat(),
                        "interval_hours": self.buy_interval_hours,
                    },
                )

        # All conditions met — BUY
        self._last_buy_time = now

        # DCA uses fixed allocation per buy (5% of portfolio)
        per_buy_value = portfolio_value * 0.05
        quantity = per_buy_value / current_price if current_price > 0 else 0.0

        # Confidence based on how oversold + how far below MA
        confidence = self._calculate_confidence(current_rsi, current_price, current_sma)

        return Signal(
            signal_type=SignalType.BUY,
            pair=self.pair,
            price=current_price,
            quantity=quantity,
            confidence=confidence,
            reason=f"DCA buy: RSI={current_rsi:.1f} < {self.rsi_threshold}, "
                   f"price ${current_price:,.2f} below MA ${current_sma:,.2f}",
            metadata={
                "rsi": current_rsi,
                "sma": current_sma,
                "entry_type": "signal_dca",
                "interval_hours": self.buy_interval_hours,
            },
        )

    def _calculate_confidence(
        self, rsi: float, price: float, ma: float
    ) -> float:
        """
        Confidence from RSI depth + MA discount magnitude.

        Lower RSI and further below MA = higher confidence.
        """
        # RSI component: how far below threshold (normalized)
        rsi_depth = max(0, (self.rsi_threshold - rsi) / self.rsi_threshold)

        # MA discount component: how far below MA (capped at 10%)
        if ma > 0:
            discount = (ma - price) / ma
            ma_strength = min(1.0, discount / 0.10)
        else:
            ma_strength = 0.0

        confidence = 0.5 + (rsi_depth * 0.3) + (ma_strength * 0.2)
        return min(1.0, max(0.0, confidence))

    def validate_config(self) -> List[str]:
        warnings = []
        if self.buy_interval_hours < 4:
            warnings.append(
                f"Buy interval {self.buy_interval_hours}h is very short — "
                f"risk of overbuying in extended dips"
            )
        if self.rsi_threshold > 50:
            warnings.append(
                f"RSI threshold {self.rsi_threshold} is above midpoint — "
                f"will trigger too frequently"
            )
        if self.ma_period < 20:
            warnings.append(
                f"MA period {self.ma_period} is short — may not reflect true trend"
            )
        return warnings
