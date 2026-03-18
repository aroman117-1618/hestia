"""
Price validator — redundant price feed verification.

Cross-checks the primary exchange price against a secondary source
(CoinGecko API in production, configurable in paper mode). Prevents
trading on data glitches — a single bad tick can trigger false signals.

Layer 7 of the 8-layer safety architecture.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from hestia.logging import get_logger, LogComponent
from hestia.trading.exchange.base import AbstractExchangeAdapter

logger = get_logger()


class PriceValidator:
    """
    Validates prices against a secondary feed before execution.

    In paper mode: uses a configurable secondary price (for testing).
    In live mode: will query CoinGecko API (Sprint 25).
    """

    def __init__(
        self,
        max_divergence: float = 0.02,  # 2% threshold
        exchange: Optional[AbstractExchangeAdapter] = None,
    ) -> None:
        self._max_divergence = max_divergence
        self._exchange = exchange
        self._secondary_prices: Dict[str, float] = {}
        self._last_check: Optional[Dict[str, Any]] = None

    def set_secondary_price(self, pair: str, price: float) -> None:
        """Set secondary price for a pair (testing/paper mode)."""
        self._secondary_prices[pair] = price

    async def get_primary_price(self, pair: str) -> float:
        """Get price from primary exchange."""
        if self._exchange and self._exchange.is_connected:
            ticker = await self._exchange.get_ticker(pair)
            return ticker.get("price", 0.0)
        return 0.0

    def get_secondary_price(self, pair: str) -> float:
        """
        Get price from secondary source.

        Paper mode: returns pre-set price.
        Live mode: will query CoinGecko (Sprint 25).
        """
        return self._secondary_prices.get(pair, 0.0)

    async def validate(self, pair: str, proposed_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Validate that primary and secondary price feeds agree.

        Returns:
            {
                "valid": bool,
                "primary_price": float,
                "secondary_price": float,
                "divergence": float,
                "reason": str,
            }
        """
        primary = proposed_price or await self.get_primary_price(pair)
        secondary = self.get_secondary_price(pair)

        # If no secondary price available, pass validation with warning
        if secondary <= 0:
            result = {
                "valid": True,
                "primary_price": primary,
                "secondary_price": 0.0,
                "divergence": 0.0,
                "reason": "No secondary price feed available — validation skipped",
            }
            self._last_check = result
            return result

        if primary <= 0:
            result = {
                "valid": False,
                "primary_price": 0.0,
                "secondary_price": secondary,
                "divergence": 1.0,
                "reason": "Primary price is zero or unavailable",
            }
            self._last_check = result
            return result

        divergence = abs(primary - secondary) / primary

        if divergence > self._max_divergence:
            result = {
                "valid": False,
                "primary_price": primary,
                "secondary_price": secondary,
                "divergence": divergence,
                "reason": f"Price divergence {divergence:.2%} exceeds {self._max_divergence:.2%} "
                         f"(primary={primary:.2f}, secondary={secondary:.2f})",
            }
            logger.warning(
                f"Price validation FAILED: {pair} divergence={divergence:.2%}",
                component=LogComponent.TRADING,
                data=result,
            )
        else:
            result = {
                "valid": True,
                "primary_price": primary,
                "secondary_price": secondary,
                "divergence": divergence,
                "reason": "Prices within acceptable range",
            }

        self._last_check = result
        return result

    @property
    def last_check(self) -> Optional[Dict[str, Any]]:
        """Get the most recent validation result."""
        return self._last_check
