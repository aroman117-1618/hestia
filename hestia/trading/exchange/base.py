"""
Abstract exchange adapter — unified interface for all exchanges.

Designed for CCXT-compatible expansion (Kraken, etc.).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass
class OrderRequest:
    """Request to place an order."""
    pair: str = "BTC-USD"
    side: str = "buy"  # buy or sell
    order_type: str = "limit"  # limit, market, stop
    quantity: float = 0.0
    price: Optional[float] = None  # Required for limit orders
    post_only: bool = True  # Default to maker orders (lower fees)
    client_order_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OrderResult:
    """Result of an order placement or query."""
    order_id: str = ""
    client_order_id: Optional[str] = None
    status: str = "pending"  # pending, open, partial, filled, cancelled, failed
    pair: str = "BTC-USD"
    side: str = "buy"
    order_type: str = "limit"
    price: float = 0.0
    filled_price: float = 0.0
    quantity: float = 0.0
    filled_quantity: float = 0.0
    fee: float = 0.0
    fee_currency: str = "USD"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    raw_response: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_filled(self) -> bool:
        return self.status == "filled"

    @property
    def is_open(self) -> bool:
        return self.status in ("pending", "open", "partial")


@dataclass
class AccountBalance:
    """Balance for a single currency."""
    currency: str = "USD"
    available: float = 0.0
    hold: float = 0.0  # Held in open orders

    @property
    def total(self) -> float:
        return self.available + self.hold


class AbstractExchangeAdapter(ABC):
    """
    Base class for all exchange adapters.

    Implementations: CoinbaseAdapter (live), PaperAdapter (simulation).
    Future: KrakenAdapter, etc.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Initialize connection to exchange."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection."""
        ...

    @abstractmethod
    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place an order on the exchange."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if cancelled."""
        ...

    @abstractmethod
    async def get_order(self, order_id: str) -> Optional[OrderResult]:
        """Get order status."""
        ...

    @abstractmethod
    async def get_open_orders(self, pair: Optional[str] = None) -> List[OrderResult]:
        """Get all open orders, optionally filtered by pair."""
        ...

    @abstractmethod
    async def get_balances(self) -> Dict[str, AccountBalance]:
        """Get account balances for all currencies."""
        ...

    @abstractmethod
    async def get_ticker(self, pair: str = "BTC-USD") -> Dict[str, Any]:
        """Get current price ticker for a pair."""
        ...

    @abstractmethod
    async def get_order_book(self, pair: str = "BTC-USD", depth: int = 10) -> Dict[str, Any]:
        """Get order book (bids and asks)."""
        ...

    @abstractmethod
    async def get_candles(
        self,
        pair: str,
        granularity: str = "1h",
        days: int = 7,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV candle data from the exchange.

        Returns DataFrame with columns: open, high, low, close, volume, timestamp.
        None if fetch fails.
        """
        ...

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the adapter is connected to the exchange."""
        ...

    @property
    @abstractmethod
    def is_paper(self) -> bool:
        """Whether this is a paper trading adapter."""
        ...

    @property
    @abstractmethod
    def exchange_name(self) -> str:
        """Name of the exchange."""
        ...
