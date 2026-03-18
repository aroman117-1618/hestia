"""
Coinbase Advanced Trade adapter.

Uses coinbase-advanced-py SDK for authenticated REST API access.
Credentials loaded from macOS Keychain via CredentialManager.

CRITICAL: API keys must be scoped to "Consumer Default Spot" portfolio.
Wrong scope = silent 401 failures.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.trading.exchange.base import (
    AbstractExchangeAdapter,
    AccountBalance,
    OrderRequest,
    OrderResult,
)

logger = get_logger()

# Keychain keys for Coinbase credentials
KEYCHAIN_API_KEY = "coinbase-api-key"
KEYCHAIN_API_SECRET = "coinbase-api-secret"


class CoinbaseAdapter(AbstractExchangeAdapter):
    """
    Coinbase Advanced Trade adapter.

    Sprint 21: Skeleton with credential loading.
    Sprint 25: Full REST + WebSocket implementation.
    """

    def __init__(self) -> None:
        self._connected = False
        self._client = None  # coinbase.rest.RESTClient (Sprint 25)
        self._api_key: Optional[str] = None
        self._api_secret: Optional[str] = None

    async def connect(self) -> None:
        """Load credentials from Keychain and initialize SDK client."""
        try:
            from hestia.security.credential_manager import get_credential_manager

            cred_mgr = await get_credential_manager()
            self._api_key = await cred_mgr.get_credential(KEYCHAIN_API_KEY)
            self._api_secret = await cred_mgr.get_credential(KEYCHAIN_API_SECRET)

            if not self._api_key or not self._api_secret:
                logger.warning(
                    "Coinbase API credentials not found in Keychain. "
                    "Use paper trading mode until credentials are configured.",
                    component=LogComponent.TRADING,
                )
                return

            # SDK client initialization deferred to Sprint 25
            # from coinbase.rest import RESTClient
            # self._client = RESTClient(api_key=self._api_key, api_secret=self._api_secret)

            self._connected = True
            logger.info(
                "Coinbase adapter connected (credentials loaded)",
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
        logger.info("Coinbase adapter disconnected", component=LogComponent.TRADING)

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Place order via Coinbase API (Sprint 25 implementation)."""
        raise NotImplementedError("Live Coinbase orders are Sprint 25 scope")

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("Live Coinbase orders are Sprint 25 scope")

    async def get_order(self, order_id: str) -> Optional[OrderResult]:
        raise NotImplementedError("Live Coinbase orders are Sprint 25 scope")

    async def get_open_orders(self, pair: Optional[str] = None) -> List[OrderResult]:
        raise NotImplementedError("Live Coinbase orders are Sprint 25 scope")

    async def get_balances(self) -> Dict[str, AccountBalance]:
        raise NotImplementedError("Live Coinbase balances are Sprint 25 scope")

    async def get_ticker(self, pair: str = "BTC-USD") -> Dict[str, Any]:
        raise NotImplementedError("Live Coinbase market data is Sprint 25 scope")

    async def get_order_book(self, pair: str = "BTC-USD", depth: int = 10) -> Dict[str, Any]:
        raise NotImplementedError("Live Coinbase order book is Sprint 25 scope")

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_paper(self) -> bool:
        return False

    @property
    def exchange_name(self) -> str:
        return "coinbase"
