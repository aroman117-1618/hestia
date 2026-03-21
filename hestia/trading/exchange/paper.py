"""
Paper trading adapter — simulated fills for backtesting and validation.

Same interface as live adapters but executes against virtual balances
with realistic slippage and fee modeling.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.exchange.base import (
    AbstractExchangeAdapter,
    AccountBalance,
    OrderRequest,
    OrderResult,
)

logger = get_logger()

# Coinbase fee tiers for <$10K monthly volume
DEFAULT_MAKER_FEE = 0.004  # 0.40%
DEFAULT_TAKER_FEE = 0.006  # 0.60%
DEFAULT_SLIPPAGE = 0.001   # 0.10% realistic slippage


class PaperAdapter(AbstractExchangeAdapter):
    """
    Paper trading adapter with realistic simulation.

    Simulates order fills with configurable slippage and fees.
    Maintains virtual balances for P&L tracking.
    """

    def __init__(
        self,
        initial_balance_usd: float = 250.0,
        maker_fee: float = DEFAULT_MAKER_FEE,
        taker_fee: float = DEFAULT_TAKER_FEE,
        slippage: float = DEFAULT_SLIPPAGE,
        market_data_source: Optional[Callable] = None,
    ) -> None:
        self._connected = False
        self._maker_fee = maker_fee
        self._taker_fee = taker_fee
        self._slippage = slippage
        self._market_data_source = market_data_source

        # Virtual balances
        self._balances: Dict[str, AccountBalance] = {
            "USD": AccountBalance(currency="USD", available=initial_balance_usd),
        }

        # Order tracking
        self._orders: Dict[str, OrderResult] = {}
        self._open_orders: Dict[str, OrderRequest] = {}

        # Simulated price (set externally or default)
        self._current_prices: Dict[str, float] = {
            "BTC-USD": 65000.0,
            "ETH-USD": 3500.0,
        }

    async def connect(self) -> None:
        self._connected = True
        logger.info(
            "Paper trading adapter connected",
            component=LogComponent.TRADING,
            data={"balances": {k: v.total for k, v in self._balances.items()}},
        )

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Paper trading adapter disconnected", component=LogComponent.TRADING)

    def set_price(self, pair: str, price: float) -> None:
        """Set simulated price for a pair (for testing)."""
        self._current_prices[pair] = price

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Simulate order placement with realistic fills."""
        order_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        price = request.price or self._current_prices.get(request.pair, 0.0)
        if price <= 0:
            return OrderResult(
                order_id=order_id,
                status="failed",
                pair=request.pair,
                side=request.side,
                timestamp=now,
                raw_response={"error": f"No price available for {request.pair}"},
            )

        # Apply slippage for market orders
        if request.order_type == "market":
            if request.side == "buy":
                filled_price = price * (1 + self._slippage)
            else:
                filled_price = price * (1 - self._slippage)
            fee_rate = self._taker_fee
        else:
            filled_price = price
            fee_rate = self._maker_fee if request.post_only else self._taker_fee

        # Calculate fee
        trade_value = filled_price * request.quantity
        fee = trade_value * fee_rate

        # Check sufficient balance
        if request.side == "buy":
            required = trade_value + fee
            usd_balance = self._balances.get("USD", AccountBalance(currency="USD"))
            if usd_balance.available < required:
                return OrderResult(
                    order_id=order_id,
                    status="failed",
                    pair=request.pair,
                    side=request.side,
                    timestamp=now,
                    raw_response={
                        "error": "Insufficient balance",
                        "required": required,
                        "available": usd_balance.available,
                    },
                )
            # Deduct USD, add asset
            usd_balance.available -= required
            asset = request.pair.split("-")[0]  # "BTC" from "BTC-USD"
            if asset not in self._balances:
                self._balances[asset] = AccountBalance(currency=asset)
            self._balances[asset].available += request.quantity

        else:  # sell
            asset = request.pair.split("-")[0]
            asset_balance = self._balances.get(asset, AccountBalance(currency=asset))
            if asset_balance.available < request.quantity:
                return OrderResult(
                    order_id=order_id,
                    status="failed",
                    pair=request.pair,
                    side=request.side,
                    timestamp=now,
                    raw_response={
                        "error": "Insufficient balance",
                        "required": request.quantity,
                        "available": asset_balance.available,
                    },
                )
            # Deduct asset, add USD
            asset_balance.available -= request.quantity
            proceeds = trade_value - fee
            if "USD" not in self._balances:
                self._balances["USD"] = AccountBalance(currency="USD")
            self._balances["USD"].available += proceeds

        result = OrderResult(
            order_id=order_id,
            client_order_id=request.client_order_id,
            status="filled",
            pair=request.pair,
            side=request.side,
            order_type=request.order_type,
            price=price,
            filled_price=filled_price,
            quantity=request.quantity,
            filled_quantity=request.quantity,
            fee=fee,
            fee_currency="USD",
            timestamp=now,
        )
        self._orders[order_id] = result

        logger.debug(
            f"Paper trade filled: {request.side} {request.quantity} {request.pair} @ {filled_price:.2f}",
            component=LogComponent.TRADING,
            data={"order_id": order_id, "fee": fee},
        )
        return result

    async def cancel_order(self, order_id: str) -> bool:
        if order_id in self._open_orders:
            del self._open_orders[order_id]
            if order_id in self._orders:
                self._orders[order_id].status = "cancelled"
            return True
        return False

    async def get_order(self, order_id: str) -> Optional[OrderResult]:
        return self._orders.get(order_id)

    async def get_open_orders(self, pair: Optional[str] = None) -> List[OrderResult]:
        results = []
        for oid, req in self._open_orders.items():
            if pair and req.pair != pair:
                continue
            if oid in self._orders:
                results.append(self._orders[oid])
        return results

    async def get_balances(self) -> Dict[str, AccountBalance]:
        return dict(self._balances)

    async def get_ticker(self, pair: str = "BTC-USD") -> Dict[str, Any]:
        """Use market data source for live spot price if available."""
        if self._market_data_source:
            try:
                df = await self._market_data_source(pair=pair, granularity="1h", days=1)
                if df is not None and not df.empty:
                    price = float(df.iloc[-1]["close"])
                    self._current_prices[pair] = price
            except Exception:
                pass  # Fall through to cached price

        price = self._current_prices.get(pair, 0.0)
        return {
            "pair": pair,
            "price": price,
            "bid": price * 0.9999,
            "ask": price * 1.0001,
            "volume_24h": 1000000.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_candles(
        self,
        pair: str,
        granularity: str = "1h",
        days: int = 7,
    ) -> Optional[pd.DataFrame]:
        """Delegate to market data source if available."""
        if self._market_data_source:
            try:
                return await self._market_data_source(
                    pair=pair, granularity=granularity, days=days
                )
            except Exception as e:
                logger.warning(
                    f"Market data source failed: {type(e).__name__}",
                    component=LogComponent.TRADING,
                    data={"pair": pair},
                )
        return None

    async def get_order_book(self, pair: str = "BTC-USD", depth: int = 10) -> Dict[str, Any]:
        price = self._current_prices.get(pair, 0.0)
        spread = price * 0.0002  # 0.02% spread
        bids = [
            {"price": price - spread * (i + 1), "quantity": 0.1 * (i + 1)}
            for i in range(depth)
        ]
        asks = [
            {"price": price + spread * (i + 1), "quantity": 0.1 * (i + 1)}
            for i in range(depth)
        ]
        return {"pair": pair, "bids": bids, "asks": asks}

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_paper(self) -> bool:
        return True

    @property
    def exchange_name(self) -> str:
        return "paper"
