"""
Exchange product metadata — minimum order sizes and increments.

Validates that orders meet exchange minimums before submission.
Supports crypto pairs (Coinbase) and equity symbols (Alpaca).
Future: fetch live product specs from exchange API.
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from hestia.logging import get_logger, LogComponent

logger = get_logger()

# Default product catalog — hardcoded for now, fetched from exchange later
_PRODUCT_DEFAULTS: Dict[str, Dict[str, float]] = {
    "BTC-USD": {
        "base_min_size": 0.0001,
        "base_increment": 0.00000001,
        "quote_increment": 0.01,
        "base_max_size": 1000.0,
    },
    "ETH-USD": {
        "base_min_size": 0.001,
        "base_increment": 0.0000001,
        "quote_increment": 0.01,
        "base_max_size": 10000.0,
    },
}

# Equity defaults — fractional shares, zero commission via Alpaca
_EQUITY_DEFAULTS: Dict[str, Dict[str, float]] = {
    "SPY": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "QQQ": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "AAPL": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "MSFT": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "GOOGL": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "AMZN": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "NVDA": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "TSLA": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "VOO": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
    "VTI": {"base_min_size": 0.001, "base_increment": 0.001, "quote_increment": 0.01, "base_max_size": 100000.0},
}


@dataclass
class ProductInfo:
    """Exchange product metadata for a trading pair."""

    pair: str = "BTC-USD"
    base_min_size: float = 0.0001
    base_increment: float = 0.00000001
    quote_increment: float = 0.01
    base_max_size: float = 1000.0

    def min_quote_value(self, price: float) -> float:
        """Minimum USD order value at the given price."""
        return self.base_min_size * price

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair": self.pair,
            "base_min_size": self.base_min_size,
            "base_increment": self.base_increment,
            "quote_increment": self.quote_increment,
            "base_max_size": self.base_max_size,
        }


def validate_order_size(
    info: ProductInfo,
    quantity: float,
    price: float,
) -> Dict[str, Any]:
    """
    Validate an order against exchange product constraints.

    Returns dict with 'valid' (bool) and 'reason' (str).
    """
    if quantity < info.base_min_size:
        return {
            "valid": False,
            "reason": (
                f"Quantity {quantity:.8f} below minimum {info.base_min_size:.8f} "
                f"for {info.pair} (min USD value: ${info.min_quote_value(price):.2f})"
            ),
        }

    if quantity > info.base_max_size:
        return {
            "valid": False,
            "reason": (
                f"Quantity {quantity:.8f} exceeds maximum {info.base_max_size:.8f} "
                f"for {info.pair}"
            ),
        }

    return {"valid": True, "reason": "Order meets product constraints"}


def get_product_info(pair: str) -> ProductInfo:
    """
    Get product metadata for a trading pair or equity symbol.

    Checks crypto catalog first, then equity catalog.
    Falls back to conservative BTC-USD defaults for unknown pairs.
    Future: fetch from exchange API and cache.
    """
    if pair in _PRODUCT_DEFAULTS:
        return ProductInfo(pair=pair, **_PRODUCT_DEFAULTS[pair])
    if pair in _EQUITY_DEFAULTS:
        return ProductInfo(pair=pair, **_EQUITY_DEFAULTS[pair])

    logger.warning(
        f"No product info for {pair}, using BTC-USD defaults",
        component=LogComponent.TRADING,
    )
    btc_defaults = _PRODUCT_DEFAULTS["BTC-USD"]
    return ProductInfo(pair=pair, **btc_defaults)
