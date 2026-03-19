# Sprint 28: Alpaca + Stocks Expansion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand Hestia's trading module from crypto-only (Coinbase) to multi-asset (Coinbase + Alpaca) with market hours awareness, multi-exchange orchestration, and equity-ready strategies.

**Architecture:** S28B (Alpaca infrastructure) before S28A (crypto strategies). The `AbstractExchangeAdapter` ABC gains a `get_candles()` method, breaking the Coinbase-specific data path. A per-bot exchange registry replaces the single-adapter orchestrator. Market hours gating prevents equity bots from polling when markets are closed. AlpacaAdapter starts read-only (account, positions, market data); full orders deferred to S29A.

**Tech Stack:** Python 3.12, `alpaca-py` SDK (Apache-2.0), FastAPI, SQLite (aiosqlite), pandas, existing Hestia trading infrastructure.

**References:**
- Discovery: `docs/discoveries/sprint-28-alpaca-stocks-expansion-2026-03-19.md`
- Second opinion: `docs/plans/sprint-28-alpaca-second-opinion-2026-03-19.md`
- Existing adapter: `hestia/trading/exchange/base.py` (135 lines, 11 abstract methods)
- Existing bot runner: `hestia/trading/bot_runner.py` (386 lines)
- Existing orchestrator: `hestia/trading/orchestrator.py` (332 lines)

**Estimated effort:** ~39h across 14 tasks in 3 phases.

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `hestia/trading/exchange/alpaca.py` (~400 lines) | AlpacaAdapter — implements AbstractExchangeAdapter for Alpaca REST API |
| `hestia/trading/market_hours.py` (~120 lines) | MarketHoursScheduler — checks market open/close via Alpaca Calendar/Clock APIs |
| `tests/test_trading_alpaca.py` (~300 lines) | AlpacaAdapter unit tests (mocked SDK) |
| `tests/test_trading_market_hours.py` (~100 lines) | Market hours scheduler tests |

### Modified Files
| File | Changes |
|------|---------|
| `hestia/trading/exchange/base.py` | Add `get_candles()` abstract method to ABC |
| `hestia/trading/exchange/coinbase.py` | Implement `get_candles()` (move from BotRunner._fetch_candles) |
| `hestia/trading/exchange/paper.py` | Implement `get_candles()` stub |
| `hestia/trading/bot_runner.py` | Use `self._exchange.get_candles()` instead of DataLoader. Add market hours check. |
| `hestia/trading/orchestrator.py` | Exchange registry (`Dict[str, AbstractExchangeAdapter]`), per-bot routing |
| `hestia/trading/models.py` | Add `exchange` field to Bot dataclass |
| `hestia/trading/product_info.py` | Add equity product defaults (SPY, AAPL, QQQ, etc.) |
| `hestia/config/trading.yaml` | Add `alpaca` config block under `exchange` |
| `pyproject.toml` | Add `alpaca-py` dependency |
| `tests/test_trading_adapter.py` | Add `get_candles()` tests |
| `tests/test_trading_golive.py` | Add multi-exchange orchestrator tests |

---

## Phase 1: Foundation (~12h)

### Task 1: Add `get_candles()` to AbstractExchangeAdapter ABC

**Why:** The BotRunner currently fetches candles through a Coinbase-specific `DataLoader` path, bypassing the adapter pattern entirely. This must be fixed before Alpaca can slot in.

**Files:**
- Modify: `hestia/trading/exchange/base.py:114` (after `get_order_book`)
- Test: `tests/test_trading_adapter.py`

- [ ] **Step 1: Add abstract method to ABC**

In `hestia/trading/exchange/base.py`, add after the `get_order_book` method (line ~116):

```python
@abstractmethod
async def get_candles(
    self,
    pair: str,
    granularity: str = "1h",
    days: int = 7,
) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candle data from the exchange.

    Args:
        pair: Trading pair (e.g., "BTC-USD" or "SPY").
        granularity: Candle interval ("1m", "5m", "15m", "1h", "1d").
        days: Number of days of history to fetch.

    Returns:
        DataFrame with columns: open, high, low, close, volume, timestamp.
        None if fetch fails.
    """
```

Add `import pandas as pd` and `from typing import Optional` to imports if not present.

- [ ] **Step 2: Add test for interface compliance**

In `tests/test_trading_adapter.py`, add:

```python
@pytest.mark.asyncio
async def test_get_candles_in_abc():
    """Verify get_candles is an abstract method on the ABC."""
    import inspect
    from hestia.trading.exchange.base import AbstractExchangeAdapter
    assert hasattr(AbstractExchangeAdapter, "get_candles")
    assert "get_candles" in AbstractExchangeAdapter.__abstractmethods__
```

- [ ] **Step 3: Run test** — `python -m pytest tests/test_trading_adapter.py -v --timeout=30 -k "get_candles"`

- [ ] **Step 4: Commit** — `git commit -m "feat(trading): add get_candles() to AbstractExchangeAdapter ABC"`

---

### Task 2: Implement `get_candles()` in CoinbaseAdapter

**Why:** Move candle-fetching logic from `BotRunner._fetch_candles()` into the adapter where it belongs.

**Files:**
- Modify: `hestia/trading/exchange/coinbase.py`
- Modify: `hestia/trading/exchange/paper.py`
- Test: `tests/test_trading_adapter.py`

- [ ] **Step 1: Write failing test for CoinbaseAdapter.get_candles()**

```python
@pytest.mark.asyncio
async def test_coinbase_get_candles(mock_coinbase_adapter):
    """CoinbaseAdapter.get_candles returns a DataFrame with OHLCV columns."""
    df = await mock_coinbase_adapter.get_candles("BTC-USD", granularity="1h", days=7)
    assert df is not None
    assert set(["open", "high", "low", "close", "volume"]).issubset(df.columns)
    assert len(df) > 0
```

- [ ] **Step 2: Implement in CoinbaseAdapter**

Port the logic from `bot_runner.py:275-311` (`_fetch_candles`) into `coinbase.py`:

```python
async def get_candles(
    self,
    pair: str,
    granularity: str = "1h",
    days: int = 7,
) -> Optional[pd.DataFrame]:
    """Fetch candles from Coinbase REST API."""
    try:
        from datetime import timedelta
        from hestia.trading.backtest.data_loader import DataLoader
        loader = DataLoader()
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=days)
        df = await loader.fetch_from_coinbase(
            pair=pair,
            granularity=granularity,
            start=start,
            end=end,
        )
        return df
    except Exception as e:
        logger.warning(
            f"Candle fetch failed: {type(e).__name__}",
            component=LogComponent.TRADING,
        )
        return None
```

- [ ] **Step 3: Implement stub in PaperAdapter**

```python
async def get_candles(
    self,
    pair: str,
    granularity: str = "1h",
    days: int = 7,
) -> Optional[pd.DataFrame]:
    """Paper adapter has no live data source — returns None.

    BotRunner falls back to ticker data when candles are unavailable.
    In practice, paper bots are tested against CoinbaseAdapter or
    AlpacaAdapter candle data via the orchestrator's exchange registry.
    """
    return None
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/test_trading_adapter.py -v --timeout=30`
- [ ] **Step 5: Commit** — `git commit -m "feat(trading): implement get_candles() in CoinbaseAdapter + PaperAdapter"`

---

### Task 3: Update BotRunner to use adapter's `get_candles()`

**Why:** Replace the Coinbase-specific DataLoader call with the adapter's unified interface.

**Files:**
- Modify: `hestia/trading/bot_runner.py:275-311` (`_fetch_candles` method)
- Test: `tests/test_trading_pipeline.py`

- [ ] **Step 1: Write test verifying BotRunner uses adapter.get_candles()**

```python
@pytest.mark.asyncio
async def test_bot_runner_uses_adapter_get_candles(bot_runner, mock_exchange):
    """BotRunner._fetch_candles delegates to the exchange adapter."""
    mock_exchange.get_candles = AsyncMock(return_value=sample_ohlcv_df())
    df = await bot_runner._fetch_candles("BTC-USD")
    mock_exchange.get_candles.assert_called_once_with("BTC-USD", granularity="1h", days=7)
    assert df is not None
```

- [ ] **Step 2: Replace `_fetch_candles` in bot_runner.py**

Replace lines 275-311 with:

```python
async def _fetch_candles(self, pair: str) -> Optional[pd.DataFrame]:
    """Fetch candles from the exchange adapter."""
    try:
        df = await self._exchange.get_candles(
            pair=pair,
            granularity="1h",
            days=7,
        )
        if df is not None and not df.empty:
            return df

        # Fallback: single ticker point if candles unavailable
        logger.warning(
            "Candle fetch returned empty — falling back to ticker",
            component=LogComponent.TRADING,
            data={"pair": pair},
        )
        ticker = await self._exchange.get_ticker(pair)
        if ticker and ticker.get("price"):
            price = ticker["price"]
            now = datetime.now(timezone.utc)
            return pd.DataFrame([{
                "timestamp": now, "open": price, "high": price,
                "low": price, "close": price, "volume": 0,
            }])
        return None
    except Exception as e:
        logger.warning(
            f"Candle fetch failed: {type(e).__name__}",
            component=LogComponent.TRADING,
            data={"pair": pair},
        )
        return None
```

- [ ] **Step 3: Remove DataLoader import** from bot_runner.py (no longer needed in this file)
- [ ] **Step 4: Run full trading tests** — `python -m pytest tests/test_trading_pipeline.py tests/test_trading_golive.py -v --timeout=30`
- [ ] **Step 5: Commit** — `git commit -m "refactor(trading): BotRunner uses adapter.get_candles() — removes Coinbase-specific data path"`

---

### Task 4: Add `exchange` field to Bot model + multi-exchange orchestrator

**Why:** Each bot needs to know which exchange it belongs to. The orchestrator needs an exchange registry to route bots to the correct adapter.

**Files:**
- Modify: `hestia/trading/models.py:81-126` (Bot dataclass)
- Modify: `hestia/trading/orchestrator.py:31-42` (constructor)
- Modify: `hestia/trading/database.py` (bots table schema)
- Test: `tests/test_trading_models.py`, `tests/test_trading_golive.py`

- [ ] **Step 1: Add `exchange` field to Bot**

In `models.py`, add to the Bot dataclass (after `asset_class`):

```python
exchange: str = "coinbase"  # Exchange adapter name
```

Update `to_dict()` and `from_dict()` to serialize this field.

- [ ] **Step 2: Add column to database schema**

In `database.py`, add to bots table CREATE statement:

```sql
exchange TEXT DEFAULT 'coinbase'
```

Add ALTER TABLE migration in `_run_migrations()`:

```python
try:
    await self._connection.execute(
        "ALTER TABLE bots ADD COLUMN exchange TEXT DEFAULT 'coinbase'"
    )
except Exception:
    pass  # Column already exists
```

- [ ] **Step 3: Refactor orchestrator to exchange registry**

Replace `orchestrator.py` constructor (lines 31-42):

```python
def __init__(
    self,
    exchanges: Dict[str, AbstractExchangeAdapter],
    risk_manager: RiskManager,
    event_bus: Optional[TradingEventBus] = None,
    default_exchange: str = "coinbase",
) -> None:
    self._exchanges = exchanges
    self._default_exchange = default_exchange
    self._risk = risk_manager
    self._event_bus = event_bus
    self._runners: Dict[str, asyncio.Task] = {}
    self._bot_locks: Dict[str, asyncio.Lock] = {}
    self._running = False

def _get_exchange_for_bot(self, bot: Bot) -> AbstractExchangeAdapter:
    """Route bot to its configured exchange adapter."""
    exchange_name = getattr(bot, "exchange", self._default_exchange)
    adapter = self._exchanges.get(exchange_name)
    if adapter is None:
        raise ValueError(f"No adapter registered for exchange: {exchange_name}")
    return adapter
```

Update `start_runner()` to use `self._get_exchange_for_bot(bot)` instead of `self._exchange`.

- [ ] **Step 4: Update `get_bot_orchestrator()` singleton** to build exchange registry from config:

```python
async def get_bot_orchestrator() -> BotOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        manager = await get_trading_manager()
        exchanges = {"coinbase": manager.exchange}
        # Alpaca adapter added here when available
        _orchestrator = BotOrchestrator(
            exchanges=exchanges,
            risk_manager=manager.risk_manager,
            event_bus=_event_bus,
        )
    return _orchestrator
```

- [ ] **Step 5: Update `stop_runner()` to use per-bot exchange lookup**

`stop_runner()` currently calls `self._exchange.get_open_orders()` and `self._exchange.cancel_order()`. Replace with:

```python
async def stop_runner(self, bot_id: str) -> bool:
    # Look up bot to find its exchange
    manager = await get_trading_manager()
    bot = await manager.get_bot(bot_id)
    if bot:
        exchange = self._get_exchange_for_bot(bot)
        # Cancel open orders on the correct exchange
        open_orders = await exchange.get_open_orders(bot.pair)
        for order in open_orders:
            await exchange.cancel_order(order.order_id)
    # ... rest of existing stop logic (cancel task, update status)
```

- [ ] **Step 5b: Update `_reconcile_exchange_state()` to iterate all exchanges**

```python
async def _reconcile_exchange_state(self) -> None:
    for name, exchange in self._exchanges.items():
        if not exchange.is_connected:
            logger.warning(f"Exchange {name} not connected — skipping reconciliation")
            continue
        try:
            balances = await exchange.get_balances()
            logger.info(f"Reconciled {name}", data={"balances": {k: v.total for k, v in balances.items()}})
        except Exception as e:
            logger.warning(f"Reconciliation failed for {name}: {type(e).__name__}")
```

- [ ] **Step 5c: Preserve `_event_bus` import** — ensure `from hestia.api.routes.trading import _event_bus` is kept in `get_bot_orchestrator()`.

- [ ] **Step 6: Write tests**

```python
def test_bot_exchange_field_defaults_coinbase():
    bot = Bot(name="test")
    assert bot.exchange == "coinbase"

def test_bot_exchange_serialization():
    bot = Bot(name="test", exchange="alpaca")
    d = bot.to_dict()
    assert d["exchange"] == "alpaca"
    restored = Bot.from_dict(d)
    assert restored.exchange == "alpaca"

@pytest.mark.asyncio
async def test_orchestrator_routes_to_correct_exchange():
    mock_coinbase = AsyncMock(spec=AbstractExchangeAdapter)
    mock_alpaca = AsyncMock(spec=AbstractExchangeAdapter)
    orch = BotOrchestrator(
        exchanges={"coinbase": mock_coinbase, "alpaca": mock_alpaca},
        risk_manager=mock_risk,
    )
    bot = Bot(name="spy-dca", exchange="alpaca", pair="SPY")
    adapter = orch._get_exchange_for_bot(bot)
    assert adapter is mock_alpaca
```

- [ ] **Step 7: Run tests** — `python -m pytest tests/test_trading_models.py tests/test_trading_golive.py -v --timeout=30`
- [ ] **Step 8: Commit** — `git commit -m "feat(trading): multi-exchange orchestrator with per-bot routing"`

---

### Task 5: Extend product_info.py for equities

**Files:**
- Modify: `hestia/trading/product_info.py`
- Test: `tests/test_trading_product_info.py`

- [ ] **Step 1: Add equity product defaults**

```python
# Equity defaults — fractional shares, zero commission
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
```

- [ ] **Step 2: Update `get_product_info()` to check both catalogs**

```python
def get_product_info(pair: str) -> ProductInfo:
    if pair in _PRODUCT_DEFAULTS:
        return ProductInfo(pair=pair, **_PRODUCT_DEFAULTS[pair])
    if pair in _EQUITY_DEFAULTS:
        return ProductInfo(pair=pair, **_EQUITY_DEFAULTS[pair])
    # Conservative default for unknown pairs
    return ProductInfo(pair=pair)
```

- [ ] **Step 3: Test**

```python
def test_equity_product_info():
    info = get_product_info("SPY")
    assert info.base_min_size == 0.001  # Fractional shares
    assert info.base_max_size == 100000.0

def test_unknown_pair_returns_default():
    info = get_product_info("UNKNOWN")
    assert info.pair == "UNKNOWN"
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/test_trading_product_info.py -v --timeout=30`
- [ ] **Step 5: Commit** — `git commit -m "feat(trading): add equity product defaults for SPY, QQQ, AAPL, etc."`

---

## Phase 2: Alpaca Integration (~15h)

### Task 6: Add alpaca-py dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add dependency**

```toml
"alpaca-py>=0.30.0,<1.0",
```

- [ ] **Step 2: Install** — `pip install alpaca-py`
- [ ] **Step 3: Verify import** — `python -c "from alpaca.trading.client import TradingClient; print('OK')"`
- [ ] **Step 4: Commit** — `git commit -m "chore: add alpaca-py dependency"`

---

### Task 7: Implement AlpacaAdapter (read-only)

**Why:** Core integration — maps Alpaca SDK to `AbstractExchangeAdapter` interface. Read-only for S28: account info, positions, market data, candles. Order methods raise `NotImplementedError` until S29A.

**Files:**
- Create: `hestia/trading/exchange/alpaca.py`
- Create: `tests/test_trading_alpaca.py`

- [ ] **Step 1: Write comprehensive tests first**

```python
"""Tests for AlpacaAdapter — mocked SDK, no live API calls."""

class TestAlpacaAdapter:
    @pytest.fixture
    def mock_trading_client(self):
        """Mock alpaca TradingClient."""
        client = MagicMock()
        client.get_account.return_value = MagicMock(
            equity="50000.00", buying_power="100000.00",
            cash="25000.00", currency="USD",
            daytrade_count=1, pattern_day_trader=False,
        )
        return client

    @pytest.fixture
    def adapter(self, mock_trading_client):
        adapter = AlpacaAdapter.__new__(AlpacaAdapter)
        adapter._client = mock_trading_client
        adapter._connected = True
        adapter._paper = True
        return adapter

    @pytest.mark.asyncio
    async def test_get_balances(self, adapter):
        balances = await adapter.get_balances()
        assert "USD" in balances
        assert balances["USD"].total == 25000.0

    @pytest.mark.asyncio
    async def test_get_ticker(self, adapter):
        # Mock market data
        adapter._data_client = MagicMock()
        adapter._data_client.get_stock_latest_quote.return_value = {
            "SPY": MagicMock(ask_price=450.50, bid_price=450.45)
        }
        ticker = await adapter.get_ticker("SPY")
        assert ticker["price"] > 0
        assert ticker["bid"] > 0
        assert ticker["ask"] > 0

    @pytest.mark.asyncio
    async def test_get_candles(self, adapter):
        # Mock historical bars
        adapter._data_client = MagicMock()
        mock_bar = MagicMock(open=450.0, high=452.0, low=449.0, close=451.0, volume=1000000)
        adapter._data_client.get_stock_bars.return_value = {"SPY": [mock_bar]}
        df = await adapter.get_candles("SPY", granularity="1h", days=7)
        assert df is not None
        assert "close" in df.columns

    @pytest.mark.asyncio
    async def test_place_order_raises_not_implemented(self, adapter):
        with pytest.raises(NotImplementedError):
            await adapter.place_order(OrderRequest(pair="SPY", side="buy"))

    def test_exchange_name(self, adapter):
        assert adapter.exchange_name == "alpaca"

    def test_is_paper(self, adapter):
        assert adapter.is_paper is True
```

- [ ] **Step 2: Run tests to verify they fail** — `python -m pytest tests/test_trading_alpaca.py -v --timeout=30`

- [ ] **Step 3: Implement AlpacaAdapter**

```python
"""
Alpaca exchange adapter for US equities.

Sprint 28: Read-only (account, positions, market data, candles).
Sprint 29A: Full order placement + PDT enforcement.
"""

import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from hestia.trading.exchange.base import AbstractExchangeAdapter, OrderRequest, OrderResult, AccountBalance
from hestia.logging import get_logger, LogComponent

logger = get_logger()

KEYCHAIN_API_KEY = "alpaca-api-key"
KEYCHAIN_API_SECRET = "alpaca-api-secret"


class AlpacaAdapter(AbstractExchangeAdapter):
    """Alpaca Markets adapter for US equities trading."""

    def __init__(self, paper: bool = True) -> None:
        self._client = None  # TradingClient
        self._data_client = None  # StockHistoricalDataClient
        self._connected = False
        self._paper = paper

    async def connect(self) -> None:
        from hestia.security.credential_manager import get_credential_manager
        from alpaca.trading.client import TradingClient
        from alpaca.data.historical import StockHistoricalDataClient

        cred_mgr = get_credential_manager()
        api_key = cred_mgr.get_credential(KEYCHAIN_API_KEY)
        api_secret = cred_mgr.get_credential(KEYCHAIN_API_SECRET)

        if not api_key or not api_secret:
            raise ConnectionError("Alpaca API keys not found in Keychain")

        self._client = TradingClient(api_key, api_secret, paper=self._paper)
        self._data_client = StockHistoricalDataClient(api_key, api_secret)
        self._connected = True

        logger.info(
            "Alpaca adapter connected",
            component=LogComponent.TRADING,
            data={"paper": self._paper},
        )

    async def disconnect(self) -> None:
        self._connected = False
        self._client = None
        self._data_client = None

    async def get_balances(self) -> Dict[str, AccountBalance]:
        account = self._client.get_account()
        return {
            "USD": AccountBalance(
                available=float(account.buying_power),
                total=float(account.equity),
                hold=0.0,  # Read-only adapter — no orders, no holds
            ),
        }

    async def get_ticker(self, pair: str = "SPY") -> Dict[str, Any]:
        from alpaca.data.requests import StockLatestQuoteRequest
        quote = self._data_client.get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=pair)
        )
        q = quote.get(pair) or quote.get(pair.upper())
        if q is None:
            return {"price": 0.0, "bid": 0.0, "ask": 0.0}
        mid = (float(q.ask_price) + float(q.bid_price)) / 2
        return {
            "price": mid,
            "bid": float(q.bid_price),
            "ask": float(q.ask_price),
            "pair": pair,
        }

    async def get_candles(
        self,
        pair: str,
        granularity: str = "1h",
        days: int = 7,
    ) -> Optional[pd.DataFrame]:
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        tf_map = {"1m": TimeFrame.Minute, "5m": TimeFrame(5, "Min"),
                   "15m": TimeFrame(15, "Min"), "1h": TimeFrame.Hour, "1d": TimeFrame.Day}
        tf = tf_map.get(granularity, TimeFrame.Hour)

        start = datetime.now(timezone.utc) - timedelta(days=days)
        request = StockBarsRequest(
            symbol_or_symbols=pair,
            timeframe=tf,
            start=start,
        )
        bars = self._data_client.get_stock_bars(request)
        bar_list = bars.get(pair, [])

        if not bar_list:
            return None

        records = [{
            "timestamp": getattr(b, "timestamp", datetime.now(timezone.utc)),
            "open": float(b.open), "high": float(b.high),
            "low": float(b.low), "close": float(b.close),
            "volume": float(b.volume),
        } for b in bar_list]

        return pd.DataFrame(records)

    async def get_order_book(self, pair: str = "SPY", depth: int = 10) -> Dict[str, Any]:
        # Alpaca doesn't provide L2 order book for stocks
        ticker = await self.get_ticker(pair)
        return {"bids": [[ticker["bid"], 0]], "asks": [[ticker["ask"], 0]]}

    # -- Order methods (S29A — not implemented yet) --

    async def place_order(self, request: OrderRequest) -> OrderResult:
        raise NotImplementedError("Alpaca order placement deferred to S29A")

    async def cancel_order(self, order_id: str) -> bool:
        raise NotImplementedError("Alpaca order cancellation deferred to S29A")

    async def get_order(self, order_id: str) -> Optional[OrderResult]:
        raise NotImplementedError("Alpaca order queries deferred to S29A")

    async def get_open_orders(self, pair: Optional[str] = None) -> List[OrderResult]:
        return []  # No orders in read-only mode

    # -- Properties --

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def is_paper(self) -> bool:
        return self._paper

    @property
    def exchange_name(self) -> str:
        return "alpaca"
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/test_trading_alpaca.py -v --timeout=30`
- [ ] **Step 5: Commit** — `git commit -m "feat(trading): AlpacaAdapter read-only — account, positions, market data, candles"`

---

### Task 7b: Corporate actions awareness (second opinion Condition 2)

**Why:** A stock split would halve the price — the strategy would incorrectly see a 50% drop and generate a buy signal. At minimum, log corporate action events so they can be investigated.

**Files:**
- Modify: `hestia/trading/exchange/alpaca.py`
- Test: `tests/test_trading_alpaca.py`

- [ ] **Step 1: Add `get_corporate_actions()` to AlpacaAdapter**

```python
async def get_corporate_actions(self, pair: str, days: int = 30) -> List[Dict[str, Any]]:
    """Check for recent corporate actions (splits, dividends) on a symbol.

    Returns a list of action dicts. Logs warnings for any actions found
    so the user can investigate position adjustments.
    """
    try:
        from alpaca.data.requests import CorporateActionsRequest
        start = datetime.now(timezone.utc) - timedelta(days=days)
        # Alpaca corporate actions API
        actions = self._client.get_corporate_actions(
            CorporateActionsRequest(symbols=[pair], start=start)
        )
        results = []
        for action in actions:
            logger.warning(
                f"Corporate action detected: {action.ca_type} on {pair}",
                component=LogComponent.TRADING,
                data={"symbol": pair, "type": str(action.ca_type), "date": str(action.date)},
            )
            results.append({"symbol": pair, "type": str(action.ca_type), "date": str(action.date)})
        return results
    except Exception as e:
        logger.debug(
            f"Corporate actions check failed: {type(e).__name__}",
            component=LogComponent.TRADING,
        )
        return []
```

- [ ] **Step 2: Call from BotRunner on first tick for equity bots**

In `bot_runner.py`, at the start of `run()` for equity bots:

```python
if self.bot.asset_class == "us_equity" and hasattr(self._exchange, "get_corporate_actions"):
    actions = await self._exchange.get_corporate_actions(self.bot.pair, days=7)
    if actions:
        logger.warning(
            f"Corporate actions found for {self.bot.pair} — review positions",
            component=LogComponent.TRADING,
            data={"actions": actions, "bot_id": self.bot.id},
        )
```

- [ ] **Step 3: Test**

```python
@pytest.mark.asyncio
async def test_corporate_actions_logs_splits(self, adapter):
    """Corporate actions check should log split events."""
    mock_action = MagicMock(ca_type="forward_split", date="2026-03-20")
    adapter._client.get_corporate_actions.return_value = [mock_action]
    actions = await adapter.get_corporate_actions("AAPL")
    assert len(actions) == 1
    assert actions[0]["type"] == "forward_split"
```

- [ ] **Step 4: Run tests** — `python -m pytest tests/test_trading_alpaca.py -v --timeout=30`
- [ ] **Step 5: Commit** — `git commit -m "feat(trading): corporate actions awareness — log splits and dividends for equity bots"`

---

### Task 8: Market hours scheduler

**Why:** Equity bots must not poll when markets are closed. Uses Alpaca's Calendar + Clock APIs.

**Files:**
- Create: `hestia/trading/market_hours.py`
- Create: `tests/test_trading_market_hours.py`
- Modify: `hestia/trading/bot_runner.py` (add market hours check to `_tick`)

- [ ] **Step 1: Write tests**

```python
class TestMarketHours:
    @pytest.mark.asyncio
    async def test_market_open_during_trading_hours(self, scheduler):
        """Market should report open during regular NYSE hours."""
        # Mock clock response: market is open
        scheduler._client.get_clock.return_value = MagicMock(is_open=True)
        assert await scheduler.is_market_open() is True

    @pytest.mark.asyncio
    async def test_market_closed_outside_hours(self, scheduler):
        scheduler._client.get_clock.return_value = MagicMock(is_open=False)
        assert await scheduler.is_market_open() is False

    @pytest.mark.asyncio
    async def test_next_open_returns_datetime(self, scheduler):
        scheduler._client.get_clock.return_value = MagicMock(
            is_open=False,
            next_open=datetime(2026, 3, 20, 14, 30, tzinfo=timezone.utc),
        )
        next_open = await scheduler.next_market_open()
        assert next_open is not None

    @pytest.mark.asyncio
    async def test_cache_prevents_excessive_api_calls(self, scheduler):
        scheduler._client.get_clock.return_value = MagicMock(is_open=True)
        await scheduler.is_market_open()
        await scheduler.is_market_open()
        # Should only call API once due to cache
        assert scheduler._client.get_clock.call_count == 1
```

- [ ] **Step 2: Implement MarketHoursScheduler**

```python
"""Market hours scheduler using Alpaca Calendar/Clock APIs."""

from datetime import datetime, timezone
from typing import Optional

from hestia.logging import get_logger, LogComponent

logger = get_logger()

CACHE_TTL_SECONDS = 60  # Re-check market status every 60s


class MarketHoursScheduler:
    """Checks market open/close status via Alpaca APIs."""

    def __init__(self, trading_client) -> None:
        self._client = trading_client
        self._cached_status: Optional[bool] = None
        self._cache_expires: float = 0

    async def is_market_open(self) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        if self._cached_status is not None and now < self._cache_expires:
            return self._cached_status

        try:
            clock = self._client.get_clock()
            self._cached_status = clock.is_open
            self._cache_expires = now + CACHE_TTL_SECONDS
            return clock.is_open
        except Exception as e:
            logger.warning(
                f"Market hours check failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return False  # Fail-closed: assume market closed if check fails

    async def next_market_open(self) -> Optional[datetime]:
        try:
            clock = self._client.get_clock()
            return clock.next_open
        except Exception:
            return None

    async def seconds_until_open(self) -> Optional[float]:
        next_open = await self.next_market_open()
        if next_open is None:
            return None
        delta = next_open - datetime.now(timezone.utc)
        return max(0, delta.total_seconds())
```

- [ ] **Step 3: Add market hours check to BotRunner._tick()**

In `bot_runner.py`, at the top of `_tick()` (before candle fetch):

```python
# Market hours gate for equity bots
if self.bot.asset_class == "us_equity":
    if self._market_hours and not await self._market_hours.is_market_open():
        logger.debug(
            "Market closed — skipping equity tick",
            component=LogComponent.TRADING,
            data={"bot_id": self.bot.id, "pair": self.bot.pair},
        )
        return
```

Add `market_hours: Optional[MarketHoursScheduler] = None` to BotRunner constructor.

- [ ] **Step 4: Run tests** — `python -m pytest tests/test_trading_market_hours.py -v --timeout=30`
- [ ] **Step 5: Commit** — `git commit -m "feat(trading): market hours scheduler — gate equity bots on NYSE open/close"`

---

### Task 9: Alpaca config in trading.yaml

**Files:**
- Modify: `hestia/config/trading.yaml`

- [ ] **Step 1: Add Alpaca config block**

```yaml
exchange:
  primary: "coinbase"
  mode: "paper"
  coinbase:
    keychain_api_key: "coinbase-api-key"
    keychain_api_secret: "coinbase-api-secret"
    portfolio: "Consumer Default Spot"
    post_only: true
  alpaca:
    keychain_api_key: "alpaca-api-key"
    keychain_api_secret: "alpaca-api-secret"
    paper: true
    market_hours_only: true  # Only poll during regular NYSE hours
  paper:
    initial_balance_usd: 250.0
    maker_fee: 0.004
    taker_fee: 0.006
    slippage: 0.001
```

- [ ] **Step 2: Add equity strategy defaults**

```yaml
strategies:
  # ... existing crypto strategies ...
  signal_dca_equity:
    rsi_period: 14
    rsi_threshold: 30        # More conservative for equities (vs 40 for crypto)
    ma_period: 50
    buy_interval_hours: 24
  mean_reversion_equity:
    rsi_period: 14            # Standard for equities (vs 7 for crypto)
    rsi_oversold: 30          # Wider band (vs 20 for crypto)
    rsi_overbought: 70        # Wider band (vs 80 for crypto)
    volume_confirmation: 1.5
    trend_filter_period: 50
```

- [ ] **Step 3: Commit** — `git commit -m "feat(trading): add Alpaca config + equity strategy defaults to trading.yaml"`

---

### Task 10: Wire AlpacaAdapter into orchestrator startup

**Why:** Connect all the pieces — when the server starts, register the Alpaca adapter alongside Coinbase.

**Files:**
- Modify: `hestia/trading/orchestrator.py` (`get_bot_orchestrator()`)
- Modify: `hestia/trading/manager.py` (if adapter initialization lives here)
- Test: `tests/test_trading_golive.py`

- [ ] **Step 1: Update `get_bot_orchestrator()` to build exchange registry from config**

```python
async def get_bot_orchestrator() -> BotOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        manager = await get_trading_manager()
        exchanges: Dict[str, AbstractExchangeAdapter] = {
            "coinbase": manager.exchange,
        }

        # Register Alpaca if configured
        config = manager.config
        alpaca_cfg = config.get("exchange", {}).get("alpaca", {})
        if alpaca_cfg:
            try:
                from hestia.trading.exchange.alpaca import AlpacaAdapter
                alpaca = AlpacaAdapter(paper=alpaca_cfg.get("paper", True))
                await alpaca.connect()
                exchanges["alpaca"] = alpaca
                logger.info(
                    "Alpaca adapter registered",
                    component=LogComponent.TRADING,
                    data={"paper": alpaca_cfg.get("paper", True)},
                )
            except Exception as e:
                logger.warning(
                    f"Alpaca adapter failed to connect: {type(e).__name__}",
                    component=LogComponent.TRADING,
                )
                # Continue without Alpaca — crypto bots still work

        _orchestrator = BotOrchestrator(
            exchanges=exchanges,
            risk_manager=manager.risk_manager,
            event_bus=_event_bus,
        )
    return _orchestrator
```

- [ ] **Step 2: Test that orchestrator starts without Alpaca keys**

```python
@pytest.mark.asyncio
async def test_orchestrator_starts_without_alpaca(mocker):
    """Orchestrator should start even if Alpaca keys are missing."""
    mock_manager = AsyncMock()
    mock_manager.exchange = AsyncMock(spec=AbstractExchangeAdapter)
    mock_manager.risk_manager = MagicMock()
    mock_manager.config = {"exchange": {}}  # No alpaca config
    mocker.patch("hestia.trading.orchestrator.get_trading_manager", return_value=mock_manager)

    # Reset singleton
    import hestia.trading.orchestrator as orch_mod
    orch_mod._orchestrator = None

    orch = await get_bot_orchestrator()
    assert "coinbase" in orch._exchanges
    assert "alpaca" not in orch._exchanges
```

- [ ] **Step 3: Run full test suite** — `python -m pytest tests/ --timeout=30 -q`
- [ ] **Step 4: Commit** — `git commit -m "feat(trading): wire AlpacaAdapter into orchestrator startup — graceful degradation if keys missing"`

---

## Phase 3: Crypto Strategy Expansion (~12h)

### Task 11: Backtest Signal DCA on historical data

**Files:**
- Modify: `hestia/trading/backtest/` (existing backtest infrastructure)
- Test: `tests/test_trading_backtest.py`

- [ ] **Step 0: Verify BacktestEngine API** — Read `hestia/trading/backtest/engine.py` and confirm constructor signature accepts `strategy_type`, `pair`, `days`, `initial_capital`, `config`. Adapt test code below if the interface differs.

- [ ] **Step 1: Write backtest for Signal DCA on BTC-USD 90 days**

Using existing backtest infrastructure, create a backtest configuration:

```python
@pytest.mark.asyncio
async def test_signal_dca_backtest_90d():
    """Signal DCA backtest on 90 days of BTC-USD data."""
    from hestia.trading.backtest.engine import BacktestEngine
    engine = BacktestEngine(
        strategy_type="signal_dca",
        pair="BTC-USD",
        days=90,
        initial_capital=250.0,
        config={"rsi_period": 14, "rsi_threshold": 40, "buy_interval_hours": 24},
    )
    result = await engine.run()
    assert result is not None
    assert result.get("total_trades", 0) > 0
    assert "final_value" in result
```

- [ ] **Step 2: Write backtest for Signal DCA on SPY 365 days** (equity validation per second-opinion condition 5)

```python
@pytest.mark.asyncio
async def test_signal_dca_backtest_spy_365d():
    """Signal DCA backtest on 1 year of SPY data — validates equity strategy."""
    engine = BacktestEngine(
        strategy_type="signal_dca",
        pair="SPY",
        days=365,
        initial_capital=1000.0,
        config={"rsi_period": 14, "rsi_threshold": 30, "buy_interval_hours": 24},
    )
    result = await engine.run()
    assert result is not None
    assert result.get("total_trades", 0) > 0
```

- [ ] **Step 3: Run backtests** — `python -m pytest tests/test_trading_backtest.py -v --timeout=120 -k "signal_dca"`
- [ ] **Step 4: Commit** — `git commit -m "feat(trading): Signal DCA backtests — 90d BTC-USD + 365d SPY"`

---

### Task 12: Backtest Bollinger Breakout on crypto

**Files:**
- Test: `tests/test_trading_backtest.py`

- [ ] **Step 0: Verify BacktestEngine supports `bollinger_breakout` strategy type** — grep for strategy type handling in `engine.py`.

- [ ] **Step 1: Write Bollinger Breakout backtest for BTC-USD 90 days**

```python
@pytest.mark.asyncio
async def test_bollinger_breakout_backtest_90d():
    """Bollinger Breakout backtest on 90 days of BTC-USD."""
    engine = BacktestEngine(
        strategy_type="bollinger_breakout",
        pair="BTC-USD",
        days=90,
        initial_capital=250.0,
        config={"period": 20, "std_dev": 2.0, "volume_confirmation": 1.5},
    )
    result = await engine.run()
    assert result is not None
    assert "sharpe_ratio" in result
```

- [ ] **Step 2: Run backtest** — `python -m pytest tests/test_trading_backtest.py -v --timeout=120 -k "bollinger"`
- [ ] **Step 3: Commit** — `git commit -m "feat(trading): Bollinger Breakout backtest — 90d BTC-USD"`

---

### Task 13: CSV export for backtest results

**Files:**
- Modify: `hestia/api/routes/trading.py` (existing CSV export endpoint)

- [ ] **Step 1: Verify existing CSV export handles backtest results**

Check if the existing `GET /v1/trading/export/csv` endpoint can export backtest trade history. If not, extend it.

- [ ] **Step 2: Test CSV export with backtest data**

```python
@pytest.mark.asyncio
async def test_csv_export_includes_asset_class(client):
    """CSV export should include asset_class column."""
    response = await client.get("/v1/trading/export/csv")
    assert response.status_code == 200
    assert "asset_class" in response.text
```

- [ ] **Step 3: Commit** — `git commit -m "feat(trading): CSV export includes asset_class for multi-asset reporting"`

---

### Task 14: Update CLAUDE.md and documentation

**Files:**
- Modify: `CLAUDE.md` (project structure, endpoint counts, test counts)
- Modify: `SPRINT.md` (Sprint 28 status)

- [ ] **Step 1: Update CLAUDE.md**
  - Add AlpacaAdapter to project structure
  - Update endpoint count if any new routes added
  - Update test count
  - Update Sprint 28 status in roadmap table

- [ ] **Step 2: Update SPRINT.md**
  - Add Sprint 28 entry with completed workstreams
  - Key commits
  - Test results

- [ ] **Step 3: Commit** — `git commit -m "docs: update CLAUDE.md + SPRINT.md for Sprint 28"`

---

## Verification Checklist

Before marking Sprint 28 complete:

- [ ] All existing tests pass (2552+ backend)
- [ ] New tests pass (AlpacaAdapter, market hours, multi-exchange orchestrator)
- [ ] `get_candles()` works through both CoinbaseAdapter and AlpacaAdapter
- [ ] Orchestrator starts with Coinbase-only (no Alpaca keys) — graceful degradation
- [ ] BotRunner skips ticks for equity bots when market is closed
- [ ] Backtests produce results for Signal DCA (BTC + SPY) and Bollinger (BTC)
- [ ] iOS + macOS builds compile
- [ ] No regressions in Sprint 27 paper soak bots

## What's NOT in Sprint 28

Deferred to **S29A** (per second opinion conditions):
- [ ] Alpaca order placement (full `place_order()` implementation)
- [ ] PDT enforcement (`PDTTracker` in risk manager)
- [ ] Automated capital gates (performance-gated tier-up state machine)
- [ ] Trading alert push notifications to iOS
- [ ] Corporate action handling (stock splits, dividends)
- [ ] Alpaca paper soak
