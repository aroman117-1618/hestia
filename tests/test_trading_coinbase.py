"""
Tests for Coinbase integration — mocked SDK responses, WebSocket feed,
health monitoring, order lifecycle, reconnection, live paper mode.

No real API calls — all exchange interactions are mocked.
"""

import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from hestia.trading.exchange.base import AccountBalance, OrderRequest
from hestia.trading.exchange.coinbase_ws import CoinbaseWebSocketFeed
from hestia.trading.exchange.health_monitor import HealthMonitor


# ── HealthMonitor ─────────────────────────────────────────────

class TestHealthMonitor:
    def test_initial_state(self):
        hm = HealthMonitor()
        assert hm.is_healthy is False
        assert hm.avg_latency_ms == 0.0
        assert hm.uptime_seconds == 0.0

    def test_connect_makes_healthy(self):
        hm = HealthMonitor(heartbeat_interval_s=30.0)
        hm.record_connect()
        assert hm.is_healthy is True
        assert hm.uptime_seconds >= 0.0

    def test_heartbeat_keeps_alive(self):
        hm = HealthMonitor(heartbeat_interval_s=30.0)
        hm.record_heartbeat()
        assert hm.is_healthy is True

    def test_latency_tracking(self):
        hm = HealthMonitor()
        hm.record_latency(100.0)
        hm.record_latency(200.0)
        hm.record_latency(300.0)
        assert hm.avg_latency_ms == pytest.approx(200.0)

    def test_p95_latency(self):
        hm = HealthMonitor()
        for i in range(100):
            hm.record_latency(float(i))
        assert hm.p95_latency_ms >= 90.0

    def test_latency_buffer_capped(self):
        hm = HealthMonitor()
        for i in range(200):
            hm.record_latency(float(i))
        assert len(hm._latencies) == 100

    def test_disconnect_count(self):
        hm = HealthMonitor()
        hm.record_disconnect()
        hm.record_disconnect()
        assert hm._disconnect_count == 2

    def test_status_dict(self):
        hm = HealthMonitor()
        hm.record_connect()
        hm.record_latency(150.0)
        status = hm.get_status()
        assert "healthy" in status
        assert "avg_latency_ms" in status
        assert "disconnect_count" in status

    def test_heartbeat_age(self):
        hm = HealthMonitor()
        hm.record_heartbeat()
        age = hm.heartbeat_age_seconds
        assert age is not None
        assert age < 1.0  # Just recorded


# ── WebSocket Feed ────────────────────────────────────────────

class TestWebSocketFeed:
    def test_initial_state(self):
        ws = CoinbaseWebSocketFeed(pairs=["BTC-USD", "ETH-USD"])
        assert ws.is_connected is False
        assert ws.gaps_detected == 0
        assert ws.reconnect_count == 0

    def test_ticker_callback(self):
        ws = CoinbaseWebSocketFeed()
        received = []
        ws.on_ticker(lambda data: received.append(data))

        msg = json.dumps({
            "channel": "ticker",
            "sequence_num": 1,
            "events": [{
                "type": "update",
                "tickers": [{
                    "product_id": "BTC-USD",
                    "price": "65000.00",
                    "volume_24_h": "1234.56",
                }],
            }],
        })
        ws._handle_message(msg)

        assert len(received) == 1
        assert received[0]["pair"] == "BTC-USD"
        assert received[0]["price"] == 65000.0

    def test_candle_callback(self):
        ws = CoinbaseWebSocketFeed()
        received = []
        ws.on_candle(lambda data: received.append(data))

        msg = json.dumps({
            "channel": "candles",
            "sequence_num": 1,
            "events": [{
                "type": "update",
                "candles": [{
                    "product_id": "BTC-USD",
                    "start": "1710700800",
                    "open": "65000",
                    "high": "65500",
                    "low": "64800",
                    "close": "65200",
                    "volume": "100.5",
                }],
            }],
        })
        ws._handle_message(msg)

        assert len(received) == 1
        assert received[0]["close"] == 65200.0
        assert received[0]["volume"] == 100.5

    def test_fill_callback(self):
        ws = CoinbaseWebSocketFeed()
        received = []
        ws.on_fill(lambda data: received.append(data))

        msg = json.dumps({
            "channel": "user",
            "sequence_num": 1,
            "events": [{
                "type": "update",
                "orders": [{
                    "order_id": "order-123",
                    "product_id": "BTC-USD",
                    "order_side": "BUY",
                    "status": "FILLED",
                    "average_filled_price": "65000.00",
                    "filled_size": "0.001",
                    "total_fees": "0.26",
                }],
            }],
        })
        ws._handle_message(msg)

        assert len(received) == 1
        assert received[0]["order_id"] == "order-123"
        assert received[0]["filled_price"] == 65000.0
        assert received[0]["filled_quantity"] == 0.001

    def test_partial_fill(self):
        ws = CoinbaseWebSocketFeed()
        received = []
        ws.on_fill(lambda data: received.append(data))

        msg = json.dumps({
            "channel": "user",
            "sequence_num": 1,
            "events": [{
                "type": "update",
                "orders": [{
                    "order_id": "order-456",
                    "product_id": "BTC-USD",
                    "order_side": "SELL",
                    "status": "PARTIALLY_FILLED",
                    "average_filled_price": "66000.00",
                    "filled_size": "0.0005",
                    "total_fees": "0.13",
                }],
            }],
        })
        ws._handle_message(msg)
        assert len(received) == 1
        assert received[0]["status"] == "partially_filled"

    def test_non_fill_order_ignored(self):
        ws = CoinbaseWebSocketFeed()
        received = []
        ws.on_fill(lambda data: received.append(data))

        msg = json.dumps({
            "channel": "user",
            "sequence_num": 1,
            "events": [{
                "type": "update",
                "orders": [{
                    "order_id": "order-789",
                    "status": "OPEN",
                }],
            }],
        })
        ws._handle_message(msg)
        assert len(received) == 0  # OPEN status should not trigger fill callback

    def test_sequence_gap_detection(self):
        ws = CoinbaseWebSocketFeed()
        ws._on_ticker = lambda d: None

        # Send sequence 1, then skip to 5
        ws._handle_message(json.dumps({
            "channel": "ticker",
            "sequence_num": 1,
            "events": [{"tickers": [{"product_id": "BTC-USD", "price": "65000"}]}],
        }))
        ws._handle_message(json.dumps({
            "channel": "ticker",
            "sequence_num": 5,
            "events": [{"tickers": [{"product_id": "BTC-USD", "price": "65100"}]}],
        }))

        assert ws.gaps_detected == 1
        assert ws._sequences["ticker"] == 5

    def test_no_gap_sequential(self):
        ws = CoinbaseWebSocketFeed()
        ws._on_ticker = lambda d: None

        for seq in range(1, 6):
            ws._handle_message(json.dumps({
                "channel": "ticker",
                "sequence_num": seq,
                "events": [{"tickers": [{"product_id": "BTC-USD", "price": "65000"}]}],
            }))

        assert ws.gaps_detected == 0

    def test_status(self):
        ws = CoinbaseWebSocketFeed(pairs=["BTC-USD"])
        status = ws.get_status()
        assert status["connected"] is False
        assert status["pairs"] == ["BTC-USD"]
        assert status["gaps_detected"] == 0

    def test_invalid_message_handled(self):
        ws = CoinbaseWebSocketFeed()
        # Should not crash on invalid JSON
        ws._handle_message("not valid json{{{")
        ws._handle_message(None)
        ws._handle_message("")

    def test_multiple_tickers_in_one_message(self):
        ws = CoinbaseWebSocketFeed()
        received = []
        ws.on_ticker(lambda data: received.append(data))

        msg = json.dumps({
            "channel": "ticker",
            "sequence_num": 1,
            "events": [{
                "type": "update",
                "tickers": [
                    {"product_id": "BTC-USD", "price": "65000"},
                    {"product_id": "ETH-USD", "price": "3500"},
                ],
            }],
        })
        ws._handle_message(msg)
        assert len(received) == 2


# ── CoinbaseAdapter (mocked SDK) ─────────────────────────────

class TestCoinbaseAdapterMocked:
    @pytest.mark.asyncio
    async def test_connect_without_credentials(self):
        """Adapter should warn but not crash without Keychain credentials."""
        from hestia.trading.exchange.coinbase import CoinbaseAdapter

        adapter = CoinbaseAdapter()
        # Mock the security module import inside connect()
        mock_mgr = AsyncMock()
        mock_mgr.get_credential = AsyncMock(return_value=None)

        with patch("hestia.security.credential_manager.get_credential_manager", return_value=mock_mgr):
            await adapter.connect()
            assert adapter.is_connected is False  # No credentials

    @pytest.mark.asyncio
    async def test_place_order_without_connection(self):
        from hestia.trading.exchange.coinbase import CoinbaseAdapter

        adapter = CoinbaseAdapter()
        request = OrderRequest(pair="BTC-USD", side="buy", quantity=0.001, price=65000.0)
        result = await adapter.place_order(request)
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_get_balances_without_connection(self):
        from hestia.trading.exchange.coinbase import CoinbaseAdapter

        adapter = CoinbaseAdapter()
        balances = await adapter.get_balances()
        assert balances == {}

    @pytest.mark.asyncio
    async def test_cancel_order_without_connection(self):
        from hestia.trading.exchange.coinbase import CoinbaseAdapter

        adapter = CoinbaseAdapter()
        result = await adapter.cancel_order("some-id")
        assert result is False

    def test_properties(self):
        from hestia.trading.exchange.coinbase import CoinbaseAdapter

        adapter = CoinbaseAdapter()
        assert adapter.is_paper is False
        assert adapter.exchange_name == "coinbase"
        assert adapter.is_connected is False


# ── Live Paper Mode ───────────────────────────────────────────

class TestLivePaperMode:
    @pytest.mark.asyncio
    async def test_live_paper_concept(self):
        """
        Live paper mode: real prices from WebSocket, virtual fills from PaperAdapter.
        This test validates the concept works.
        """
        from hestia.trading.exchange.paper import PaperAdapter

        adapter = PaperAdapter(initial_balance_usd=250.0)
        await adapter.connect()

        # Simulate receiving a real price from WebSocket
        real_price = 65432.10  # "Real" market price
        adapter.set_price("BTC-USD", real_price)

        # Execute with PaperAdapter using the real price
        request = OrderRequest(
            pair="BTC-USD",
            side="buy",
            order_type="limit",
            quantity=0.001,
            price=real_price,
            post_only=True,
        )
        result = await adapter.place_order(request)

        assert result.is_filled
        assert result.filled_price == real_price
        assert result.fee > 0  # Maker fee applied

        await adapter.disconnect()
