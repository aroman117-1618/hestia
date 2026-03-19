"""
Bollinger Breakout Strategy — momentum breakout with volume confirmation.

BUY when price closes above the upper Bollinger band (2 sigma) with
volume >= 1.5x average. SELL when price closes below the lower band
with volume. HOLD otherwise.

This is a momentum/trend-following strategy — the opposite of mean
reversion. It profits from sustained directional moves after volatility
contraction (the "squeeze").
"""

from typing import Any, Dict, List, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType

logger = get_logger()


class BollingerBreakoutStrategy(BaseStrategy):
    """
    Bollinger Band breakout strategy with volume confirmation.

    Enters on band breaks with volume surge — exits on opposite band
    break or stop-loss. Works best in trending/breakout regimes.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.period = self.config.get("period", 20)
        self.std_dev = self.config.get("std_dev", 2.0)
        self.volume_confirmation = self.config.get("volume_confirmation", 1.5)

    @property
    def name(self) -> str:
        return "Bollinger Breakout"

    @property
    def strategy_type(self) -> str:
        return "bollinger_breakout"

    def analyze(self, df: pd.DataFrame, portfolio_value: float) -> Signal:
        """
        Generate breakout signals from Bollinger Band violations.

        1. Price above upper band + volume surge -> BUY (bullish breakout)
        2. Price below lower band + volume surge -> SELL (bearish breakout)
        3. Otherwise -> HOLD
        """
        min_rows = self.period + 5
        if len(df) < min_rows:
            return Signal(reason=f"Need {min_rows} candles, have {len(df)}")

        current = df.iloc[-1]
        current_price = float(current["close"])

        # Get pre-computed Bollinger indicators
        bb_upper = float(current.get("bb_upper", 0.0))
        bb_lower = float(current.get("bb_lower", 0.0))
        bb_middle = float(current.get("bb_middle", current_price))
        current_volume_ratio = float(current.get("volume_ratio", 1.0))

        # No valid bands -> hold
        if bb_upper == 0.0 or bb_lower == 0.0:
            return Signal(
                reason="Bollinger bands not computed",
                metadata={"bb_upper": bb_upper, "bb_lower": bb_lower},
            )

        # Check breakout conditions
        above_upper = current_price > bb_upper
        below_lower = current_price < bb_lower
        has_volume = current_volume_ratio >= self.volume_confirmation

        if not above_upper and not below_lower:
            return Signal(
                reason=f"Price ${current_price:,.2f} within bands "
                       f"(${bb_lower:,.2f} - ${bb_upper:,.2f})",
                metadata={
                    "price": current_price,
                    "bb_upper": bb_upper,
                    "bb_lower": bb_lower,
                    "volume_ratio": current_volume_ratio,
                },
            )

        if not has_volume:
            direction = "above upper" if above_upper else "below lower"
            return Signal(
                reason=f"Price {direction} band but insufficient volume "
                       f"({current_volume_ratio:.2f}x < {self.volume_confirmation}x required)",
                metadata={
                    "price": current_price,
                    "bb_upper": bb_upper,
                    "bb_lower": bb_lower,
                    "volume_ratio": current_volume_ratio,
                },
            )

        # Bullish breakout: price above upper band with volume
        if above_upper and has_volume:
            confidence = self._calculate_confidence(
                current_price, bb_upper, bb_middle, current_volume_ratio, is_buy=True
            )
            per_trade_value = portfolio_value * 0.10  # 10% per breakout trade
            quantity = per_trade_value / current_price if current_price > 0 else 0.0

            return Signal(
                signal_type=SignalType.BUY,
                pair=self.pair,
                price=current_price,
                quantity=quantity,
                confidence=confidence,
                reason=f"Bullish breakout: price ${current_price:,.2f} > upper band "
                       f"${bb_upper:,.2f}, volume={current_volume_ratio:.2f}x",
                metadata={
                    "bb_upper": bb_upper,
                    "bb_lower": bb_lower,
                    "bb_middle": bb_middle,
                    "volume_ratio": current_volume_ratio,
                    "entry_type": "bullish_breakout",
                },
            )

        # Bearish breakout: price below lower band with volume
        if below_lower and has_volume:
            confidence = self._calculate_confidence(
                current_price, bb_lower, bb_middle, current_volume_ratio, is_buy=False
            )
            per_trade_value = portfolio_value * 0.10
            quantity = per_trade_value / current_price if current_price > 0 else 0.0

            return Signal(
                signal_type=SignalType.SELL,
                pair=self.pair,
                price=current_price,
                quantity=quantity,
                confidence=confidence,
                reason=f"Bearish breakout: price ${current_price:,.2f} < lower band "
                       f"${bb_lower:,.2f}, volume={current_volume_ratio:.2f}x",
                metadata={
                    "bb_upper": bb_upper,
                    "bb_lower": bb_lower,
                    "bb_middle": bb_middle,
                    "volume_ratio": current_volume_ratio,
                    "entry_type": "bearish_breakout",
                },
            )

        return Signal(reason="No signal")

    def _calculate_confidence(
        self,
        price: float,
        band: float,
        middle: float,
        volume_ratio: float,
        is_buy: bool,
    ) -> float:
        """
        Confidence from breakout magnitude + volume strength.

        Bigger break beyond the band + higher volume = higher confidence.
        """
        # How far past the band (as fraction of band width)
        band_width = abs(band - middle) if middle != 0 else 1.0
        if band_width == 0:
            band_width = 1.0
        breakout_magnitude = abs(price - band) / band_width
        breakout_strength = min(1.0, breakout_magnitude)

        volume_strength = min(1.0, (volume_ratio - 1.0) / 2.0)
        confidence = 0.5 + (breakout_strength * 0.3) + (volume_strength * 0.2)
        return min(1.0, max(0.0, confidence))

    def validate_config(self) -> List[str]:
        warnings = []
        if self.period < 10:
            warnings.append(f"BB period {self.period} is very short — may produce noisy signals")
        if self.std_dev < 1.5:
            warnings.append(f"Std dev {self.std_dev} is tight — frequent false breakouts likely")
        if self.std_dev > 3.0:
            warnings.append(f"Std dev {self.std_dev} is wide — may miss valid breakouts")
        return warnings
