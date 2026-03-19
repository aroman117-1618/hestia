"""Tests for paper trading adapter — fills, order lifecycle, balance tracking."""

import pytest
import pytest_asyncio

from hestia.trading.exchange.base import AbstractExchangeAdapter, AccountBalance, OrderRequest, OrderResult
from hestia.trading.exchange.paper import PaperAdapter


@pytest_asyncio.fixture
async def paper():
    """Create and connect a paper trading adapter."""
    adapter = PaperAdapter(initial_balance_usd=250.0)
    await adapter.connect()
    yield adapter
    await adapter.disconnect()


# ── Connection ────────────────────────────────────────────────

class TestConnection:
    @pytest.mark.asyncio
    async def test_connect(self, paper):
        assert paper.is_connected is True
        assert paper.is_paper is True
        assert paper.exchange_name == "paper"

    @pytest.mark.asyncio
    async def test_disconnect(self):
        adapter = PaperAdapter()
        await adapter.connect()
        assert adapter.is_connected is True
        await adapter.disconnect()
        assert adapter.is_connected is False


# ── Buy Orders ────────────────────────────────────────────────

class TestBuyOrders:
    @pytest.mark.asyncio
    async def test_limit_buy(self, paper):
        request = OrderRequest(
            pair="BTC-USD",
            side="buy",
            order_type="limit",
            quantity=0.001,
            price=65000.0,
            post_only=True,
        )
        result = await paper.place_order(request)
        assert result.is_filled
        assert result.filled_price == 65000.0
        assert result.fee > 0  # Maker fee applied
        assert result.fee == pytest.approx(65000.0 * 0.001 * 0.004, abs=0.01)

    @pytest.mark.asyncio
    async def test_market_buy_has_slippage(self, paper):
        request = OrderRequest(
            pair="BTC-USD",
            side="buy",
            order_type="market",
            quantity=0.001,
            price=65000.0,
        )
        result = await paper.place_order(request)
        assert result.is_filled
        assert result.filled_price > 65000.0  # Slippage up for buys
        assert result.fee > 0  # Taker fee (higher)

    @pytest.mark.asyncio
    async def test_buy_deducts_usd(self, paper):
        initial_usd = (await paper.get_balances())["USD"].available
        request = OrderRequest(
            pair="BTC-USD",
            side="buy",
            order_type="limit",
            quantity=0.001,
            price=65000.0,
        )
        result = await paper.place_order(request)
        balances = await paper.get_balances()
        assert balances["USD"].available < initial_usd
        assert "BTC" in balances
        assert balances["BTC"].available == 0.001

    @pytest.mark.asyncio
    async def test_buy_insufficient_balance(self, paper):
        """Can't buy more than available USD."""
        request = OrderRequest(
            pair="BTC-USD",
            side="buy",
            order_type="limit",
            quantity=1.0,  # $65,000 on $250 balance
            price=65000.0,
        )
        result = await paper.place_order(request)
        assert result.status == "failed"
        assert "Insufficient" in result.raw_response.get("error", "")


# ── Sell Orders ───────────────────────────────────────────────

class TestSellOrders:
    @pytest.mark.asyncio
    async def test_sell_after_buy(self, paper):
        # Buy first
        buy = OrderRequest(pair="BTC-USD", side="buy", order_type="limit",
                          quantity=0.001, price=65000.0)
        await paper.place_order(buy)

        # Then sell
        sell = OrderRequest(pair="BTC-USD", side="sell", order_type="limit",
                          quantity=0.001, price=66000.0)
        result = await paper.place_order(sell)
        assert result.is_filled
        assert result.filled_price == 66000.0

    @pytest.mark.asyncio
    async def test_sell_updates_balances(self, paper):
        # Buy
        buy = OrderRequest(pair="BTC-USD", side="buy", order_type="limit",
                          quantity=0.001, price=65000.0)
        await paper.place_order(buy)

        # Sell at profit
        sell = OrderRequest(pair="BTC-USD", side="sell", order_type="limit",
                          quantity=0.001, price=66000.0)
        await paper.place_order(sell)

        balances = await paper.get_balances()
        assert balances["BTC"].available == pytest.approx(0.0, abs=1e-10)
        # USD should be roughly initial + profit - fees
        assert balances["USD"].available > 0

    @pytest.mark.asyncio
    async def test_sell_insufficient_asset(self, paper):
        """Can't sell what you don't have."""
        request = OrderRequest(pair="BTC-USD", side="sell", order_type="limit",
                              quantity=1.0, price=65000.0)
        result = await paper.place_order(request)
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_market_sell_has_slippage(self, paper):
        # Buy first
        buy = OrderRequest(pair="BTC-USD", side="buy", order_type="limit",
                          quantity=0.001, price=65000.0)
        await paper.place_order(buy)

        # Market sell
        sell = OrderRequest(pair="BTC-USD", side="sell", order_type="market",
                          quantity=0.001, price=65000.0)
        result = await paper.place_order(sell)
        assert result.filled_price < 65000.0  # Slippage down for sells


# ── Fees ──────────────────────────────────────────────────────

class TestFees:
    @pytest.mark.asyncio
    async def test_maker_fee(self, paper):
        """Post-Only limit orders get maker fee (0.40%)."""
        request = OrderRequest(
            pair="BTC-USD", side="buy", order_type="limit",
            quantity=0.001, price=65000.0, post_only=True,
        )
        result = await paper.place_order(request)
        expected_fee = 65000.0 * 0.001 * 0.004
        assert result.fee == pytest.approx(expected_fee, abs=0.001)

    @pytest.mark.asyncio
    async def test_taker_fee(self, paper):
        """Market orders get taker fee (0.60%)."""
        request = OrderRequest(
            pair="BTC-USD", side="buy", order_type="market",
            quantity=0.001, price=65000.0,
        )
        result = await paper.place_order(request)
        # Taker fee on slippage-adjusted price
        assert result.fee > 65000.0 * 0.001 * 0.004  # More than maker


# ── Price & Order Book ────────────────────────────────────────

class TestMarketData:
    @pytest.mark.asyncio
    async def test_get_ticker(self, paper):
        ticker = await paper.get_ticker("BTC-USD")
        assert ticker["pair"] == "BTC-USD"
        assert ticker["price"] == 65000.0
        assert "bid" in ticker
        assert "ask" in ticker

    @pytest.mark.asyncio
    async def test_get_order_book(self, paper):
        book = await paper.get_order_book("BTC-USD", depth=5)
        assert len(book["bids"]) == 5
        assert len(book["asks"]) == 5
        # Bids should be below price, asks above
        assert book["bids"][0]["price"] < 65000.0
        assert book["asks"][0]["price"] > 65000.0

    @pytest.mark.asyncio
    async def test_set_price(self, paper):
        paper.set_price("BTC-USD", 70000.0)
        ticker = await paper.get_ticker("BTC-USD")
        assert ticker["price"] == 70000.0


# ── Order Tracking ────────────────────────────────────────────

class TestOrderTracking:
    @pytest.mark.asyncio
    async def test_get_order(self, paper):
        request = OrderRequest(
            pair="BTC-USD", side="buy", order_type="limit",
            quantity=0.001, price=65000.0,
        )
        result = await paper.place_order(request)
        retrieved = await paper.get_order(result.order_id)
        assert retrieved is not None
        assert retrieved.order_id == result.order_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_order(self, paper):
        result = await paper.get_order("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_no_price_fails(self, paper):
        paper.set_price("XYZ-USD", 0.0)
        request = OrderRequest(pair="XYZ-USD", side="buy", quantity=1.0)
        result = await paper.place_order(request)
        assert result.status == "failed"


# ── Custom Config ─────────────────────────────────────────────

class TestCustomConfig:
    @pytest.mark.asyncio
    async def test_custom_fees(self):
        adapter = PaperAdapter(
            initial_balance_usd=1000.0,
            maker_fee=0.001,
            taker_fee=0.002,
            slippage=0.0,
        )
        await adapter.connect()
        request = OrderRequest(
            pair="BTC-USD", side="buy", order_type="limit",
            quantity=0.001, price=65000.0, post_only=True,
        )
        result = await adapter.place_order(request)
        expected_fee = 65000.0 * 0.001 * 0.001
        assert result.fee == pytest.approx(expected_fee, abs=0.001)
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_zero_slippage(self):
        adapter = PaperAdapter(slippage=0.0)
        await adapter.connect()
        request = OrderRequest(
            pair="BTC-USD", side="buy", order_type="market",
            quantity=0.001, price=65000.0,
        )
        result = await adapter.place_order(request)
        assert result.filled_price == 65000.0  # No slippage
        await adapter.disconnect()


# ── ABC Interface ────────────────────────────────────────────

class TestABCInterface:
    @pytest.mark.asyncio
    async def test_get_candles_in_abc(self):
        """get_candles is declared as an abstract method on the ABC."""
        assert hasattr(AbstractExchangeAdapter, "get_candles")
        assert "get_candles" in AbstractExchangeAdapter.__abstractmethods__

    @pytest.mark.asyncio
    async def test_paper_adapter_get_candles_returns_none(self, paper):
        """Paper adapter stub returns None (no live data source)."""
        result = await paper.get_candles("BTC-USD")
        assert result is None
