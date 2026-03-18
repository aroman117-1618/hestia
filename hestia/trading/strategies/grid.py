"""
Grid Trading Strategy — geometric spacing with Post-Only maker orders.

Places buy/sell orders at percentage-based intervals within a price range.
CRITICAL: Uses geometric (not arithmetic) spacing to maintain constant
fee-to-profit ratio at every price level.

Grid width must be >= 2x ATR to prevent being "gapped" by volatility.
"""

import math
from typing import Any, Dict, List, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.strategies.base import BaseStrategy, Signal, SignalType

logger = get_logger()


class GridStrategy(BaseStrategy):
    """
    Geometric grid trading strategy.

    Places buy orders below current price and sell orders above,
    at geometrically-spaced intervals. Profits from range-bound markets.

    Key parameters:
    - num_levels: Number of grid levels above and below price
    - spacing_pct: Percentage between grid levels (geometric)
    - grid_width_atr_multiple: Minimum grid width as ATR multiple
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self.num_levels = self.config.get("num_levels", 10)
        self.spacing_pct = self.config.get("spacing_pct", 0.005)  # 0.5% default
        self.grid_width_atr_multiple = self.config.get("grid_width_atr_multiple", 2.0)
        self.post_only = self.config.get("post_only", True)

        # Grid state
        self._grid_levels: List[float] = []
        self._center_price: float = 0.0
        self._last_signal_level: Optional[int] = None

    @property
    def name(self) -> str:
        return "Grid Trading (Geometric)"

    @property
    def strategy_type(self) -> str:
        return "grid"

    def calculate_grid_levels(self, center_price: float) -> List[float]:
        """
        Calculate geometric grid levels around a center price.

        Geometric spacing: each level is (1 + spacing_pct) * previous.
        This maintains a constant fee-to-profit ratio at every level.
        """
        if center_price <= 0:
            return []

        levels = [center_price]
        price = center_price

        # Levels above (sell zone)
        for _ in range(self.num_levels):
            price *= (1 + self.spacing_pct)
            levels.append(round(price, 2))

        # Levels below (buy zone)
        price = center_price
        for _ in range(self.num_levels):
            price /= (1 + self.spacing_pct)
            levels.insert(0, round(price, 2))

        return levels

    def check_grid_width(self, grid_levels: List[float], current_atr: float) -> bool:
        """
        Verify grid width >= 2x ATR.

        If the grid is too narrow relative to volatility, it will get
        "gapped" — price jumps past multiple levels without fills.
        """
        if not grid_levels or current_atr <= 0:
            return False

        grid_width = grid_levels[-1] - grid_levels[0]
        min_width = current_atr * self.grid_width_atr_multiple
        return grid_width >= min_width

    def analyze(self, df: pd.DataFrame, portfolio_value: float) -> Signal:
        """
        Analyze price position relative to grid and generate signals.

        Buy signal: price drops to a grid level below center.
        Sell signal: price rises to a grid level above center.
        Hold: price between grid levels.
        """
        if len(df) < 2:
            return Signal(reason="Insufficient data")

        current_price = float(df.iloc[-1]["close"])
        current_atr = float(df.iloc[-1].get("atr", 0.0))

        # Initialize or re-grid if needed
        if not self._grid_levels or self._needs_regrid(current_price):
            self._center_price = current_price
            self._grid_levels = self.calculate_grid_levels(current_price)
            self._last_signal_level = self._find_nearest_level(current_price)

            if current_atr > 0 and not self.check_grid_width(self._grid_levels, current_atr):
                # Widen spacing to satisfy ATR requirement
                min_spacing = (current_atr * self.grid_width_atr_multiple) / (
                    current_price * 2 * self.num_levels
                )
                self.spacing_pct = max(self.spacing_pct, min_spacing)
                self._grid_levels = self.calculate_grid_levels(current_price)

            logger.debug(
                f"Grid initialized: {len(self._grid_levels)} levels, "
                f"spacing={self.spacing_pct:.3%}, center={current_price:.2f}",
                component=LogComponent.TRADING,
            )
            return Signal(reason="Grid initialized, waiting for price movement")

        # Find current grid position
        current_level = self._find_nearest_level(current_price)

        if self._last_signal_level is None:
            self._last_signal_level = current_level
            return Signal(reason="Tracking price position")

        # Price moved down through a grid level → BUY
        if current_level < self._last_signal_level:
            level_price = self._grid_levels[current_level]
            # Position size: divide allocated capital equally across levels
            per_level_value = portfolio_value / (self.num_levels * 2)
            quantity = per_level_value / current_price if current_price > 0 else 0.0

            self._last_signal_level = current_level
            return Signal(
                signal_type=SignalType.BUY,
                pair=self.pair,
                price=level_price,
                quantity=quantity,
                confidence=0.7,
                reason=f"Price dropped to grid level {current_level} ({level_price:.2f})",
                metadata={
                    "grid_level": current_level,
                    "center_price": self._center_price,
                    "post_only": self.post_only,
                    "spacing_pct": self.spacing_pct,
                },
            )

        # Price moved up through a grid level → SELL
        if current_level > self._last_signal_level:
            level_price = self._grid_levels[current_level]
            per_level_value = portfolio_value / (self.num_levels * 2)
            quantity = per_level_value / current_price if current_price > 0 else 0.0

            self._last_signal_level = current_level
            return Signal(
                signal_type=SignalType.SELL,
                pair=self.pair,
                price=level_price,
                quantity=quantity,
                confidence=0.7,
                reason=f"Price rose to grid level {current_level} ({level_price:.2f})",
                metadata={
                    "grid_level": current_level,
                    "center_price": self._center_price,
                    "post_only": self.post_only,
                    "spacing_pct": self.spacing_pct,
                },
            )

        return Signal(reason="Price within current grid band")

    def _find_nearest_level(self, price: float) -> int:
        """Find the index of the nearest grid level to the given price."""
        if not self._grid_levels:
            return 0
        min_dist = float("inf")
        best_idx = 0
        for i, level in enumerate(self._grid_levels):
            dist = abs(price - level)
            if dist < min_dist:
                min_dist = dist
                best_idx = i
        return best_idx

    def _needs_regrid(self, current_price: float) -> bool:
        """Check if price has moved far enough from center to require re-gridding."""
        if self._center_price <= 0:
            return True
        # Re-grid if price is beyond the outermost grid levels
        if not self._grid_levels:
            return True
        return current_price < self._grid_levels[0] or current_price > self._grid_levels[-1]

    def validate_config(self) -> List[str]:
        warnings = []
        if self.num_levels < 3:
            warnings.append("Grid with < 3 levels provides limited trading opportunities")
        if self.spacing_pct < 0.002:
            warnings.append(f"Spacing {self.spacing_pct:.3%} is very tight — fees may erode profits")
        if self.spacing_pct > 0.05:
            warnings.append(f"Spacing {self.spacing_pct:.3%} is very wide — may miss opportunities")
        return warnings
