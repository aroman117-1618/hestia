"""
Dual Momentum strategy — absolute + relative momentum (Antonacci).

Absolute momentum: is the asset's N-period return positive?
  - YES → BUY (trend is up, participate)
  - NO → SELL/HOLD (trend is down, go to cash)

This provides built-in regime detection: automatically exits in bear markets
and participates in bull markets. Trades ~12 times/year at daily timeframe.

Designed for daily candles but works on hourly (adjust lookback_period accordingly).
Default lookback: 168 candles (7 days on hourly, ~7 months on daily).
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType

logger = get_logger()

# Cap for momentum magnitude → confidence mapping (30% return → max momentum confidence)
_MOMENTUM_CAP = 0.30


class DualMomentumStrategy(BaseStrategy):
    """
    Antonacci Dual Momentum — absolute momentum with built-in regime filter.

    Core logic:
    - Compute the N-period return: (current_price - lookback_price) / lookback_price
    - Positive return → BUY; negative return → SELL (go to cash)

    Confidence scoring (0.5 base):
    - Up to +0.30 from momentum magnitude (capped at _MOMENTUM_CAP = 30%)
    - Up to +0.20 from sub-period consistency (last 5 quarter-periods all positive?)
    - Optional +0.05 boost when recent momentum (last 1/4 lookback) > full lookback momentum

    Position sizing: position_pct of portfolio_value / current_price (default 15%).
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self._lookback_period: int = int(self.config.get("lookback_period", 168))
        self._position_pct: float = float(self.config.get("position_pct", 0.15))

    # ── BaseStrategy interface ────────────────────────────────────────────────

    @property
    def name(self) -> str:
        return f"Dual Momentum (lookback={self._lookback_period})"

    @property
    def strategy_type(self) -> str:
        return "dual_momentum"

    def analyze(
        self,
        df: pd.DataFrame,
        portfolio_value: float,
        timestamp: Optional[datetime] = None,
    ) -> Signal:
        """
        Analyze absolute momentum and return a BUY, SELL, or HOLD signal.

        Args:
            df: OHLCV DataFrame (must have a 'close' column).
            portfolio_value: Current portfolio value for position sizing.
            timestamp: Simulation time; accepted but not used by this strategy.

        Returns:
            Signal with BUY (positive momentum), SELL (negative momentum),
            or HOLD (insufficient data).
        """
        if len(df) <= self._lookback_period:
            return Signal(
                signal_type=SignalType.HOLD,
                pair=self.pair,
                reason=(
                    f"Insufficient data: need >{self._lookback_period} candles, "
                    f"have {len(df)}"
                ),
                metadata={"lookback_period": self._lookback_period, "rows": len(df)},
            )

        close: pd.Series = df["close"].astype(float)
        current_price = float(close.iloc[-1])
        lookback_price = float(close.iloc[-(self._lookback_period + 1)])

        if lookback_price <= 0:
            return Signal(
                signal_type=SignalType.HOLD,
                pair=self.pair,
                reason="Lookback price is zero or negative — cannot compute return",
            )

        momentum_return = (current_price - lookback_price) / lookback_price

        # ── Confidence: base + magnitude + consistency ───────────────────────
        confidence = self._compute_confidence(close, momentum_return)

        # ── Signal decision ───────────────────────────────────────────────────
        if momentum_return > 0:
            per_trade_value = portfolio_value * self._position_pct
            quantity = per_trade_value / current_price if current_price > 0 else 0.0

            logger.info(
                f"Dual Momentum BUY: return={momentum_return:.2%}, "
                f"confidence={confidence:.2f}",
                component=LogComponent.TRADING,
                data={
                    "pair": self.pair,
                    "momentum_return": round(momentum_return, 4),
                    "confidence": round(confidence, 3),
                    "lookback_period": self._lookback_period,
                },
            )

            return Signal(
                signal_type=SignalType.BUY,
                pair=self.pair,
                price=current_price,
                quantity=quantity,
                confidence=confidence,
                reason=(
                    f"Positive absolute momentum: {momentum_return:.2%} over "
                    f"{self._lookback_period} candles"
                ),
                metadata={
                    "momentum_return": round(momentum_return, 4),
                    "lookback_period": self._lookback_period,
                    "current_price": current_price,
                    "lookback_price": lookback_price,
                },
            )

        # momentum_return <= 0 → go to cash
        logger.info(
            f"Dual Momentum SELL: return={momentum_return:.2%}, regime=bearish",
            component=LogComponent.TRADING,
            data={
                "pair": self.pair,
                "momentum_return": round(momentum_return, 4),
                "lookback_period": self._lookback_period,
            },
        )

        return Signal(
            signal_type=SignalType.SELL,
            pair=self.pair,
            price=current_price,
            quantity=0.0,  # Sell full position — sized by executor
            confidence=confidence,
            reason=(
                f"Negative absolute momentum: {momentum_return:.2%} over "
                f"{self._lookback_period} candles — go to cash"
            ),
            metadata={
                "momentum_return": round(momentum_return, 4),
                "lookback_period": self._lookback_period,
                "current_price": current_price,
                "lookback_price": lookback_price,
            },
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _compute_confidence(self, close: pd.Series, momentum_return: float) -> float:
        """
        Score confidence in the momentum signal.

        Components:
        - Base: 0.5
        - Magnitude (+0.0 to +0.30): proportional to |return|, capped at _MOMENTUM_CAP
        - Consistency (+0.0 to +0.20): fraction of last 5 sub-periods with positive return
        - Acceleration (+0.05 optional): recent quarter stronger than full lookback
        """
        # 1. Magnitude component
        magnitude_score = min(abs(momentum_return) / _MOMENTUM_CAP, 1.0) * 0.30

        # 2. Sub-period consistency (last 5 quarter-periods of the lookback window)
        sub_period = max(1, self._lookback_period // 4)
        window_start = max(0, len(close) - self._lookback_period - 1)
        sub_window = close.iloc[window_start:]

        positive_sub_periods = 0
        num_checks = 5
        chunk = max(1, len(sub_window) // num_checks)

        for i in range(num_checks):
            start_idx = i * chunk
            end_idx = min((i + 1) * chunk, len(sub_window) - 1)
            if end_idx > start_idx and end_idx < len(sub_window):
                p_start = float(sub_window.iloc[start_idx])
                p_end = float(sub_window.iloc[end_idx])
                if p_start > 0 and p_end > p_start:
                    positive_sub_periods += 1

        consistency_score = (positive_sub_periods / num_checks) * 0.20

        # 3. Acceleration bonus: recent 1/4 lookback vs full lookback
        acceleration_bonus = 0.0
        if len(close) > sub_period + 1:
            recent_start = float(close.iloc[-(sub_period + 1)])
            recent_end = float(close.iloc[-1])
            if recent_start > 0:
                recent_return = (recent_end - recent_start) / recent_start
                full_per_period = momentum_return / max(self._lookback_period, 1)
                # Recent momentum accelerating means recent_return > full momentum rate
                if recent_return > full_per_period * sub_period:
                    acceleration_bonus = 0.05

        confidence = 0.5 + magnitude_score + consistency_score + acceleration_bonus
        return min(1.0, max(0.0, confidence))

    def validate_config(self) -> List[str]:
        warnings: List[str] = []
        if self._lookback_period < 20:
            warnings.append(
                f"lookback_period={self._lookback_period} is very short — "
                "Dual Momentum is designed for medium-to-long lookbacks (168+ candles)"
            )
        if self._position_pct <= 0 or self._position_pct > 1.0:
            warnings.append(
                f"position_pct={self._position_pct} is out of range (0, 1.0]"
            )
        return warnings
