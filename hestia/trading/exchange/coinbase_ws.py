"""
Coinbase WebSocket feed — real-time market data and order updates.

Uses coinbase-advanced-py WSClient for:
- Candles (OHLCV updates)
- Ticker (price updates)
- User channel (order fills, cancellations)

Sequence number checking detects missed messages during disconnects.
Exponential backoff reconnection prevents IP bans.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from hestia.logging import get_logger, LogComponent

logger = get_logger()

# Reconnection constants
INITIAL_BACKOFF_S = 1.0
MAX_BACKOFF_S = 60.0
BACKOFF_MULTIPLIER = 2.0


class CoinbaseWebSocketFeed:
    """
    Real-time market data feed via Coinbase WebSocket.

    Handles:
    - Subscription management (candles, ticker, user)
    - Sequence number tracking (gap detection)
    - Exponential backoff reconnection
    - Callback dispatch for incoming messages
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        pairs: Optional[List[str]] = None,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._pairs = pairs or ["BTC-USD"]
        self._client = None
        self._connected = False
        self._running = False

        # Sequence tracking per channel
        self._sequences: Dict[str, int] = {}
        self._gaps_detected = 0

        # Reconnection state
        self._reconnect_count = 0
        self._current_backoff = INITIAL_BACKOFF_S

        # Callbacks
        self._on_ticker: Optional[Callable] = None
        self._on_candle: Optional[Callable] = None
        self._on_fill: Optional[Callable] = None
        self._on_error: Optional[Callable] = None

        # Latency tracking (feeds into Layer 6 circuit breaker)
        self._last_message_at: Optional[float] = None
        self._latencies: List[float] = []

        # Event loop reference for cross-thread scheduling
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def on_ticker(self, callback: Callable) -> None:
        """Register callback for ticker updates."""
        self._on_ticker = callback

    def on_candle(self, callback: Callable) -> None:
        """Register callback for candle updates."""
        self._on_candle = callback

    def on_fill(self, callback: Callable) -> None:
        """Register callback for order fill events."""
        self._on_fill = callback

    def on_error(self, callback: Callable) -> None:
        """Register callback for errors."""
        self._on_error = callback

    async def connect(self) -> bool:
        """
        Initialize WebSocket connection with the Coinbase SDK.

        Returns True if connected successfully.
        """
        try:
            from coinbase.websocket import WSClient

            # Capture event loop for cross-thread callback scheduling
            self._loop = asyncio.get_running_loop()

            self._client = WSClient(
                api_key=self._api_key or "",
                api_secret=self._api_secret or "",
                on_message=self._handle_message,
                on_close=self._handle_close,
            )
            self._client.open()

            # Subscribe to channels
            self._client.ticker(product_ids=self._pairs)
            self._client.candles(product_ids=self._pairs)

            # User channel requires auth (order fills)
            if self._api_key and self._api_secret:
                self._client.user(product_ids=self._pairs)

            self._connected = True
            self._running = True
            self._reconnect_count = 0
            self._current_backoff = INITIAL_BACKOFF_S

            logger.info(
                f"Coinbase WebSocket connected, subscribed to {self._pairs}",
                component=LogComponent.TRADING,
            )
            return True

        except ImportError:
            logger.warning(
                "coinbase-advanced-py not installed — WebSocket unavailable",
                component=LogComponent.TRADING,
            )
            return False
        except Exception as e:
            logger.error(
                f"WebSocket connection failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            if self._on_error:
                self._on_error({"type": "connection_error", "error": type(e).__name__})
            return False

    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._running = False
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None
        self._connected = False
        logger.info("Coinbase WebSocket disconnected", component=LogComponent.TRADING)

    def _handle_message(self, msg: str) -> None:
        """
        Process incoming WebSocket message.

        Checks sequence numbers and dispatches to registered callbacks.
        """
        import json
        try:
            data = json.loads(msg) if isinstance(msg, str) else msg
        except (json.JSONDecodeError, TypeError):
            return

        if not isinstance(data, dict):
            return

        now = time.monotonic()
        self._last_message_at = now

        channel = data.get("channel", "")
        sequence = data.get("sequence_num")

        # Sequence gap detection
        if sequence is not None:
            expected = self._sequences.get(channel, 0) + 1
            if expected > 1 and sequence != expected:
                gap = sequence - expected
                self._gaps_detected += 1
                logger.warning(
                    f"WebSocket sequence gap: channel={channel}, "
                    f"expected={expected}, got={sequence}, gap={gap}",
                    component=LogComponent.TRADING,
                )
            self._sequences[channel] = sequence

        # Dispatch to callbacks
        events = data.get("events", [])
        for event in events:
            event_type = event.get("type", "")

            if channel == "ticker" and self._on_ticker:
                for ticker in event.get("tickers", []):
                    self._on_ticker({
                        "pair": ticker.get("product_id", ""),
                        "price": float(ticker.get("price", 0)),
                        "volume_24h": float(ticker.get("volume_24_h", 0)),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

            elif channel == "candles" and self._on_candle:
                for candle in event.get("candles", []):
                    self._on_candle({
                        "pair": candle.get("product_id", ""),
                        "timestamp": candle.get("start", ""),
                        "open": float(candle.get("open", 0)),
                        "high": float(candle.get("high", 0)),
                        "low": float(candle.get("low", 0)),
                        "close": float(candle.get("close", 0)),
                        "volume": float(candle.get("volume", 0)),
                    })

            elif channel == "user" and self._on_fill:
                for order in event.get("orders", []):
                    if order.get("status") in ("FILLED", "PARTIALLY_FILLED"):
                        self._on_fill({
                            "order_id": order.get("order_id", ""),
                            "pair": order.get("product_id", ""),
                            "side": order.get("order_side", "").lower(),
                            "status": order.get("status", "").lower(),
                            "filled_price": float(order.get("average_filled_price", 0)),
                            "filled_quantity": float(order.get("filled_size", 0)),
                            "total_fees": float(order.get("total_fees", 0)),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        })

    def _handle_close(self) -> None:
        """Handle WebSocket disconnect — trigger reconnection.

        Called from the WSClient's background thread, not the asyncio event loop.
        Uses call_soon_threadsafe to schedule reconnection on the correct loop.
        """
        self._connected = False
        logger.warning(
            "Coinbase WebSocket disconnected",
            component=LogComponent.TRADING,
        )
        if self._running and self._loop and not self._loop.is_closed():
            self._loop.call_soon_threadsafe(
                self._loop.create_task, self._reconnect()
            )

    async def _reconnect(self) -> None:
        """
        Exponential backoff reconnection.

        1s → 2s → 4s → 8s → ... → 60s max.
        Prevents IP bans from rapid reconnection attempts.
        """
        while self._running and not self._connected:
            self._reconnect_count += 1
            logger.info(
                f"Reconnecting (attempt {self._reconnect_count}, "
                f"backoff {self._current_backoff:.1f}s)",
                component=LogComponent.TRADING,
            )
            await asyncio.sleep(self._current_backoff)

            success = await self.connect()
            if success:
                logger.info(
                    f"Reconnected after {self._reconnect_count} attempts",
                    component=LogComponent.TRADING,
                )
                return

            # Exponential backoff
            self._current_backoff = min(
                self._current_backoff * BACKOFF_MULTIPLIER,
                MAX_BACKOFF_S,
            )

    # ── Status ────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def gaps_detected(self) -> int:
        return self._gaps_detected

    @property
    def reconnect_count(self) -> int:
        return self._reconnect_count

    def get_status(self) -> Dict[str, Any]:
        return {
            "connected": self._connected,
            "pairs": self._pairs,
            "gaps_detected": self._gaps_detected,
            "reconnect_count": self._reconnect_count,
            "sequences": dict(self._sequences),
            "last_message_age_s": (
                time.monotonic() - self._last_message_at
                if self._last_message_at else None
            ),
        }
