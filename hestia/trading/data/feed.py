"""
Market data feed — REST polling for MVP, WebSocket in Sprint 25.

Fetches OHLCV candles from the exchange adapter and maintains
an in-memory DataFrame for strategy consumption.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.exchange.base import AbstractExchangeAdapter

logger = get_logger()


class MarketDataFeed:
    """
    Provides OHLCV data to strategies.

    MVP: Accepts data programmatically (set_candles / add_candle).
    Sprint 25: Will pull from exchange WebSocket.
    """

    def __init__(self, pair: str = "BTC-USD") -> None:
        self.pair = pair
        self._candles: pd.DataFrame = pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

    def set_candles(self, candles: List[Dict[str, Any]]) -> None:
        """
        Load historical candle data.

        Each candle: {timestamp, open, high, low, close, volume}
        """
        self._candles = pd.DataFrame(candles)
        if "timestamp" in self._candles.columns:
            self._candles["timestamp"] = pd.to_datetime(self._candles["timestamp"])
            self._candles = self._candles.sort_values("timestamp").reset_index(drop=True)

    def add_candle(self, candle: Dict[str, Any]) -> None:
        """Add a single candle (real-time update)."""
        new_row = pd.DataFrame([candle])
        if "timestamp" in new_row.columns:
            new_row["timestamp"] = pd.to_datetime(new_row["timestamp"])
        self._candles = pd.concat([self._candles, new_row], ignore_index=True)

    def get_candles(self, limit: Optional[int] = None) -> pd.DataFrame:
        """Get candle data, optionally limited to recent N candles."""
        if limit and len(self._candles) > limit:
            return self._candles.tail(limit).reset_index(drop=True)
        return self._candles.copy()

    @property
    def latest_price(self) -> float:
        """Get the most recent close price."""
        if len(self._candles) == 0:
            return 0.0
        return float(self._candles.iloc[-1]["close"])

    @property
    def candle_count(self) -> int:
        return len(self._candles)

    def get_price_range(self, lookback: int = 20) -> Dict[str, float]:
        """Get high/low range over recent candles."""
        recent = self._candles.tail(lookback)
        if len(recent) == 0:
            return {"high": 0.0, "low": 0.0, "range": 0.0}
        high = float(recent["high"].max())
        low = float(recent["low"].min())
        return {"high": high, "low": low, "range": high - low}
