"""
Coinbase Advanced Trade adapter — full REST implementation.

Uses coinbase-advanced-py SDK for authenticated API access.
Credentials loaded from macOS Keychain via CredentialManager.

CRITICAL: API keys must be scoped to "Consumer Default Spot" portfolio.
Wrong scope = silent 401 failures.

Order lifecycle: placed → open → partial → filled → settled / cancelled
Partial fills accumulate — each fill creates its own tax lot entry.
"""

import asyncio
import functools
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.exchange.base import (
    AbstractExchangeAdapter,
    AccountBalance,
    OrderRequest,
    OrderResult,
)
from hestia.trading.exchange.health_monitor import HealthMonitor

logger = get_logger()

# Keychain keys for Coinbase credentials
KEYCHAIN_API_KEY = "coinbase-api-key"
KEYCHAIN_API_SECRET = "coinbase-api-secret"

# Key rotation reminder (90 days)
KEY_ROTATION_DAYS = 90

# File-based credentials (survives keychain locks on headless servers)
_CREDENTIALS_DIR = Path.home() / ".hestia"
_CREDENTIALS_FILE = _CREDENTIALS_DIR / "coinbase-credentials"


def save_coinbase_credentials(api_key: str, api_secret: str) -> None:
    """Store Coinbase credentials in ~/.hestia/coinbase-credentials (chmod 600)."""
    _CREDENTIALS_DIR.mkdir(mode=0o700, exist_ok=True)
    _CREDENTIALS_FILE.write_text(f"{api_key}\n{api_secret}")
    _CREDENTIALS_FILE.chmod(0o600)


class CoinbaseAdapter(AbstractExchangeAdapter):
    """
    Coinbase Advanced Trade adapter — REST API.

    All order placement defaults to Post-Only (maker fees: 0.40%).
    Portfolio explicitly scoped to "Consumer Default Spot".
    """

    def __init__(self) -> None:
        self._connected = False
        self._client = None
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None
        self._health = HealthMonitor()
        self._key_loaded_at: Optional[datetime] = None

    @staticmethod
    def _load_from_file() -> Tuple[Optional[str], Optional[str]]:
        """Load credentials from ~/.hestia/coinbase-credentials."""
        if not _CREDENTIALS_FILE.exists():
            return None, None
        try:
            lines = _CREDENTIALS_FILE.read_text().strip().split("\n")
            if len(lines) >= 2:
                return lines[0].strip(), "\n".join(lines[1:]).strip()
        except Exception:
            pass
        return None, None

    async def _run_sync(self, func, *args, **kwargs):
        """Run a synchronous SDK call in a thread pool to avoid blocking the event loop.

        Coinbase SDK returns typed response objects (not dicts). Convert via
        to_dict() so downstream code can use .get() safely.
        """
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))
        if hasattr(result, "to_dict"):
            return result.to_dict()
        return result

    async def connect(self) -> None:
        """Load credentials from credentials file or Keychain."""
        try:
            # Primary: file-based credentials (survives keychain locks on headless servers)
            self._api_key, self._api_secret = self._load_from_file()

            # Fallback: Keychain (works in interactive sessions)
            if not self._api_key or not self._api_secret:
                try:
                    from hestia.security.credential_manager import get_credential_manager
                    cred_mgr = get_credential_manager()
                    self._api_key = self._api_key or cred_mgr.retrieve_operational(KEYCHAIN_API_KEY)
                    self._api_secret = self._api_secret or cred_mgr.retrieve_operational(KEYCHAIN_API_SECRET)
                except Exception:
                    pass  # Keychain unavailable (locked, launchd context)

            if not self._api_key or not self._api_secret:
                logger.warning(
                    "Coinbase API credentials not found in Keychain. "
                    "Use paper trading mode until credentials are configured.",
                    component=LogComponent.TRADING,
                )
                return

            from coinbase.rest import RESTClient
            self._client = RESTClient(
                api_key=self._api_key,
                api_secret=self._api_secret,
            )

            self._connected = True
            self._key_loaded_at = datetime.now(timezone.utc)
            self._health.record_connect()

            # Check key age for rotation reminder
            self._check_key_rotation()

            logger.info(
                "Coinbase adapter connected",
                component=LogComponent.TRADING,
            )
        except ImportError:
            logger.error(
                "coinbase-advanced-py not installed",
                component=LogComponent.TRADING,
            )
        except Exception as e:
            logger.error(
                "Failed to initialize Coinbase adapter",
                component=LogComponent.TRADING,
                data={"error": str(type(e).__name__)},
            )

    async def disconnect(self) -> None:
        self._connected = False
        self._client = None
        self._api_key = None
        self._api_secret = None
        self._health.record_disconnect()
        logger.info("Coinbase adapter disconnected", component=LogComponent.TRADING)

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """
        Place an order via Coinbase REST API.

        Defaults to Post-Only limit orders (maker fees).
        """
        if not self._client:
            return OrderResult(status="failed", raw_response={"error": "Not connected"})

        client_oid = request.client_order_id or str(uuid.uuid4())
        start = time.monotonic()

        try:
            if request.order_type == "market":
                if request.side == "buy":
                    response = await self._run_sync(
                        self._client.market_order_buy,
                        client_order_id=client_oid,
                        product_id=request.pair,
                        base_size=str(request.quantity),
                    )
                else:
                    response = await self._run_sync(
                        self._client.market_order_sell,
                        client_order_id=client_oid,
                        product_id=request.pair,
                        base_size=str(request.quantity),
                    )
            else:
                # Limit order — GTC (Good Till Cancelled), Post-Only default
                if request.side == "buy":
                    response = await self._run_sync(
                        self._client.limit_order_gtc_buy,
                        client_order_id=client_oid,
                        product_id=request.pair,
                        base_size=str(request.quantity),
                        limit_price=str(request.price),
                        post_only=request.post_only,
                    )
                else:
                    response = await self._run_sync(
                        self._client.limit_order_gtc_sell,
                        client_order_id=client_oid,
                        product_id=request.pair,
                        base_size=str(request.quantity),
                        limit_price=str(request.price),
                        post_only=request.post_only,
                    )

            latency = (time.monotonic() - start) * 1000
            self._health.record_latency(latency)
            self._health.record_heartbeat()

            # Parse response
            order_data = response if isinstance(response, dict) else {}
            success_resp = order_data.get("success_response", {})
            error_resp = order_data.get("error_response", {})

            if error_resp:
                return OrderResult(
                    order_id=success_resp.get("order_id", ""),
                    client_order_id=client_oid,
                    status="failed",
                    pair=request.pair,
                    side=request.side,
                    raw_response=order_data,
                )

            return OrderResult(
                order_id=success_resp.get("order_id", ""),
                client_order_id=client_oid,
                status="pending",
                pair=request.pair,
                side=request.side,
                order_type=request.order_type,
                price=request.price or 0.0,
                quantity=request.quantity,
                timestamp=datetime.now(timezone.utc),
                raw_response=order_data,
            )

        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            self._health.record_latency(latency)
            logger.error(
                f"Order placement failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return OrderResult(
                status="failed",
                pair=request.pair,
                side=request.side,
                raw_response={"error": str(type(e).__name__)},
            )

    async def cancel_order(self, order_id: str) -> bool:
        if not self._client:
            return False
        try:
            start = time.monotonic()
            await self._run_sync(self._client.cancel_orders, order_ids=[order_id])
            self._health.record_latency((time.monotonic() - start) * 1000)
            self._health.record_heartbeat()
            return True
        except Exception as e:
            logger.error(
                f"Cancel order failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return False

    async def get_order(self, order_id: str) -> Optional[OrderResult]:
        if not self._client:
            return None
        try:
            start = time.monotonic()
            response = await self._run_sync(self._client.get_order, order_id=order_id)
            self._health.record_latency((time.monotonic() - start) * 1000)
            self._health.record_heartbeat()

            order = response.get("order", {})
            return OrderResult(
                order_id=order.get("order_id", ""),
                client_order_id=order.get("client_order_id"),
                status=order.get("status", "unknown").lower(),
                pair=order.get("product_id", ""),
                side=order.get("side", "").lower(),
                order_type=order.get("order_type", "").lower(),
                price=float(order.get("average_filled_price", 0) or 0),
                filled_price=float(order.get("average_filled_price", 0) or 0),
                quantity=float(order.get("base_size", 0) or 0),
                filled_quantity=float(order.get("filled_size", 0) or 0),
                fee=float(order.get("total_fees", 0) or 0),
                raw_response=response,
            )
        except Exception as e:
            logger.error(
                f"Get order failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return None

    async def get_open_orders(self, pair: Optional[str] = None) -> List[OrderResult]:
        if not self._client:
            return []
        try:
            start = time.monotonic()
            kwargs = {"product_id": pair} if pair else {}
            response = await self._run_sync(
                self._client.list_orders,
                order_status=["OPEN", "PENDING"],
                **kwargs,
            )
            self._health.record_latency((time.monotonic() - start) * 1000)
            self._health.record_heartbeat()

            orders = response.get("orders", [])
            return [
                OrderResult(
                    order_id=o.get("order_id", ""),
                    status=o.get("status", "").lower(),
                    pair=o.get("product_id", ""),
                    side=o.get("side", "").lower(),
                    price=float(o.get("average_filled_price", 0) or 0),
                    quantity=float(o.get("base_size", 0) or 0),
                    filled_quantity=float(o.get("filled_size", 0) or 0),
                )
                for o in orders
            ]
        except Exception as e:
            logger.error(
                f"List orders failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return []

    async def get_balances(self) -> Dict[str, AccountBalance]:
        if not self._client:
            return {}
        try:
            start = time.monotonic()
            response = await self._run_sync(self._client.get_accounts)
            self._health.record_latency((time.monotonic() - start) * 1000)
            self._health.record_heartbeat()

            balances = {}
            for account in response.get("accounts", []):
                currency = account.get("currency", "")
                available = float(account.get("available_balance", {}).get("value", 0) or 0)
                hold = float(account.get("hold", {}).get("value", 0) or 0)
                if available > 0 or hold > 0:
                    balances[currency] = AccountBalance(
                        currency=currency,
                        available=available,
                        hold=hold,
                    )
            return balances
        except Exception as e:
            logger.error(
                f"Get balances failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return {}

    async def get_ticker(self, pair: str = "BTC-USD") -> Dict[str, Any]:
        if not self._client:
            return {}
        try:
            start = time.monotonic()
            response = await self._run_sync(self._client.get_best_bid_ask, product_ids=[pair])
            self._health.record_latency((time.monotonic() - start) * 1000)
            self._health.record_heartbeat()

            pricebooks = response.get("pricebooks", [])
            if pricebooks:
                pb = pricebooks[0]
                bids = pb.get("bids", [])
                asks = pb.get("asks", [])
                bid = float(bids[0].get("price", 0)) if bids else 0.0
                ask = float(asks[0].get("price", 0)) if asks else 0.0
                return {
                    "pair": pair,
                    "price": (bid + ask) / 2 if bid and ask else 0.0,
                    "bid": bid,
                    "ask": ask,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            return {"pair": pair, "price": 0.0}
        except Exception as e:
            logger.error(
                f"Get ticker failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return {"pair": pair, "price": 0.0}

    async def get_candles(
        self,
        pair: str,
        granularity: str = "1h",
        days: int = 7,
    ) -> Optional[pd.DataFrame]:
        """Fetch OHLCV candles via DataLoader (Coinbase REST API)."""
        try:
            from hestia.trading.backtest.data_loader import DataLoader

            loader = DataLoader()
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days)
            df = await loader.fetch_from_coinbase(
                pair=pair, granularity=granularity, start=start, end=end
            )
            return df
        except Exception as e:
            logger.warning(
                f"Candle fetch failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return None

    async def get_order_book(self, pair: str = "BTC-USD", depth: int = 10) -> Dict[str, Any]:
        if not self._client:
            return {"pair": pair, "bids": [], "asks": []}
        try:
            start = time.monotonic()
            response = await self._run_sync(
                self._client.get_product_book,
                product_id=pair, limit=depth,
            )
            self._health.record_latency((time.monotonic() - start) * 1000)
            self._health.record_heartbeat()

            pricebook = response.get("pricebook", {})
            return {
                "pair": pair,
                "bids": [
                    {"price": float(b.get("price", 0)), "quantity": float(b.get("size", 0))}
                    for b in pricebook.get("bids", [])
                ],
                "asks": [
                    {"price": float(a.get("price", 0)), "quantity": float(a.get("size", 0))}
                    for a in pricebook.get("asks", [])
                ],
            }
        except Exception as e:
            logger.error(
                f"Get order book failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return {"pair": pair, "bids": [], "asks": []}

    def _check_key_rotation(self) -> None:
        """Warn if API key is approaching rotation age."""
        if self._key_loaded_at:
            # We don't know when the key was created, but we can remind
            # on every connect to check key age in Coinbase console
            logger.debug(
                f"API key rotation reminder: verify key age < {KEY_ROTATION_DAYS} days "
                "in Coinbase Developer console",
                component=LogComponent.TRADING,
            )

    @property
    def health(self) -> HealthMonitor:
        return self._health

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_paper(self) -> bool:
        return False

    @property
    def exchange_name(self) -> str:
        return "coinbase"
