"""Tests for Sprint 26 — trading dashboard features.

Covers: database schema changes, confidence scoring, event bus,
watchlist CRUD, decision trail persistence.
"""

import asyncio
import json
from pathlib import Path

import pytest
import pytest_asyncio

from hestia.trading.database import TradingDatabase
from hestia.trading.event_bus import TradingEvent, TradingEventBus
from hestia.trading.scoring import ConfidenceScorer


# ── Database Schema Tests ────────────────────────────────────


class TestDecisionTrailSchema:
    @pytest_asyncio.fixture
    async def db(self, tmp_path: Path):
        db = TradingDatabase(tmp_path / "test_trading.db")
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_trade_with_decision_trail(self, db: TradingDatabase) -> None:
        """Trades table should accept decision_trail JSON column."""
        # FK constraint — need a bot first
        await db.create_bot({
            "id": "b1", "name": "test", "strategy": "grid",
            "pair": "BTC-USD", "status": "running",
            "capital_allocated": 250.0, "config": {},
            "created_at": "2026-03-18T12:00:00Z",
            "updated_at": "2026-03-18T12:00:00Z",
            "user_id": "user-default",
        })
        trail = [
            {"step": "risk_validation", "result": {"approved": True}},
            {"step": "price_validation", "result": {"valid": True}},
        ]
        trade_data = {
            "id": "t1", "bot_id": "b1", "side": "buy", "order_type": "limit",
            "price": 65000.0, "quantity": 0.001, "fee": 0.26,
            "pair": "BTC-USD", "timestamp": "2026-03-18T12:00:00Z",
            "user_id": "user-default",
            "decision_trail": json.dumps(trail),
            "confidence_score": 0.82,
        }
        result = await db.record_trade(trade_data)
        assert result["decision_trail"] is not None

        trades = await db.get_trades(user_id="user-default", limit=1)
        assert len(trades) == 1
        assert len(trades[0]["decision_trail"]) == 2
        assert trades[0].get("confidence_score") == 0.82

    @pytest.mark.asyncio
    async def test_trade_without_trail_defaults(self, db: TradingDatabase) -> None:
        """Trades without trail should default to empty list."""
        await db.create_bot({
            "id": "b2", "name": "test2", "strategy": "grid",
            "pair": "BTC-USD", "status": "running",
            "capital_allocated": 250.0, "config": {},
            "created_at": "2026-03-18T12:00:00Z",
            "updated_at": "2026-03-18T12:00:00Z",
        })
        trade_data = {
            "id": "t2", "bot_id": "b2", "side": "buy", "order_type": "limit",
            "price": 65000.0, "quantity": 0.001, "fee": 0.0,
            "pair": "BTC-USD", "timestamp": "2026-03-18T12:00:00Z",
        }
        await db.record_trade(trade_data)
        trades = await db.get_trades(limit=10)
        t = [t for t in trades if t["id"] == "t2"][0]
        assert t["decision_trail"] == []
        assert t.get("confidence_score") is None

    @pytest.mark.asyncio
    async def test_get_trade_by_id(self, db: TradingDatabase) -> None:
        """Should retrieve a single trade by ID."""
        await db.create_bot({
            "id": "b3", "name": "test3", "strategy": "grid",
            "pair": "BTC-USD", "status": "running",
            "capital_allocated": 250.0, "config": {},
            "created_at": "2026-03-18T12:00:00Z",
            "updated_at": "2026-03-18T12:00:00Z",
        })
        await db.record_trade({
            "id": "t3", "bot_id": "b3", "side": "sell", "order_type": "limit",
            "price": 66000.0, "quantity": 0.001, "fee": 0.26,
            "pair": "BTC-USD", "timestamp": "2026-03-18T12:00:00Z",
            "confidence_score": 0.75,
        })
        trade = await db.get_trade_by_id("t3")
        assert trade is not None
        assert trade["side"] == "sell"
        assert trade["confidence_score"] == 0.75

        missing = await db.get_trade_by_id("nonexistent")
        assert missing is None

    @pytest.mark.asyncio
    async def test_update_trade_metadata(self, db: TradingDatabase) -> None:
        """Should update trade metadata JSON."""
        await db.create_bot({
            "id": "b4", "name": "test4", "strategy": "grid",
            "pair": "BTC-USD", "status": "running",
            "capital_allocated": 250.0, "config": {},
            "created_at": "2026-03-18T12:00:00Z",
            "updated_at": "2026-03-18T12:00:00Z",
        })
        await db.record_trade({
            "id": "t4", "bot_id": "b4", "side": "buy", "order_type": "limit",
            "price": 65000.0, "quantity": 0.001, "fee": 0.0,
            "pair": "BTC-USD", "timestamp": "2026-03-18T12:00:00Z",
        })
        success = await db.update_trade_metadata("t4", {"user_feedback": {"rating": "positive"}})
        assert success is True
        trade = await db.get_trade_by_id("t4")
        assert trade["metadata"]["user_feedback"]["rating"] == "positive"


# ── Watchlist Tests ──────────────────────────────────────────


class TestWatchlist:
    @pytest_asyncio.fixture
    async def db(self, tmp_path: Path):
        db = TradingDatabase(tmp_path / "test_trading.db")
        await db.connect()
        yield db
        await db.close()

    @pytest.mark.asyncio
    async def test_create_and_list(self, db: TradingDatabase) -> None:
        await db.create_watchlist_item({
            "id": "w1", "pair": "ETH-USD", "notes": "Watching for breakout",
            "price_alerts": json.dumps({"above": 4000}),
            "added_at": "2026-03-18T12:00:00Z", "user_id": "user-default",
        })
        items = await db.get_watchlist("user-default")
        assert len(items) == 1
        assert items[0]["pair"] == "ETH-USD"
        assert items[0]["price_alerts"]["above"] == 4000

    @pytest.mark.asyncio
    async def test_update(self, db: TradingDatabase) -> None:
        await db.create_watchlist_item({
            "id": "w2", "pair": "SOL-USD", "notes": "",
            "price_alerts": "{}", "added_at": "2026-03-18T12:00:00Z",
        })
        updated = await db.update_watchlist_item("w2", {"notes": "Updated note"})
        assert updated is not None
        assert updated["notes"] == "Updated note"

    @pytest.mark.asyncio
    async def test_delete(self, db: TradingDatabase) -> None:
        await db.create_watchlist_item({
            "id": "w3", "pair": "DOGE-USD", "notes": "",
            "price_alerts": "{}", "added_at": "2026-03-18T12:00:00Z",
        })
        assert await db.delete_watchlist_item("w3") is True
        assert await db.delete_watchlist_item("w3") is False  # Already deleted
        items = await db.get_watchlist()
        assert len(items) == 0


# ── Confidence Scorer Tests ──────────────────────────────────


class TestConfidenceScorer:
    def test_perfect_trade(self) -> None:
        score = ConfidenceScorer.compute(
            signal_confidence=0.9,
            requested_quantity=0.001,
            adjusted_quantity=0.001,
            expected_price=65000.0,
            filled_price=65000.0,
            volume_confirmed=True,
            trend_aligned=True,
        )
        assert score >= 0.85

    def test_risk_adjusted_trade(self) -> None:
        score = ConfidenceScorer.compute(
            signal_confidence=0.8,
            requested_quantity=0.01,
            adjusted_quantity=0.005,
            expected_price=65000.0,
            filled_price=65050.0,
            volume_confirmed=True,
            trend_aligned=False,
        )
        assert 0.4 < score < 0.75

    def test_poor_execution(self) -> None:
        score = ConfidenceScorer.compute(
            signal_confidence=0.5,
            requested_quantity=0.01,
            adjusted_quantity=0.002,
            expected_price=65000.0,
            filled_price=66000.0,
            volume_confirmed=False,
            trend_aligned=False,
        )
        assert score < 0.4

    def test_clamped_0_to_1(self) -> None:
        score = ConfidenceScorer.compute(
            signal_confidence=1.0,
            requested_quantity=0.001,
            adjusted_quantity=0.001,
            expected_price=65000.0,
            filled_price=65000.0,
            volume_confirmed=True,
            trend_aligned=True,
        )
        assert 0.0 <= score <= 1.0

    def test_zero_quantity_safe(self) -> None:
        score = ConfidenceScorer.compute(
            signal_confidence=0.8,
            requested_quantity=0.0,
            adjusted_quantity=0.0,
        )
        assert 0.0 <= score <= 1.0

    def test_zero_price_safe(self) -> None:
        score = ConfidenceScorer.compute(
            signal_confidence=0.8,
            expected_price=0.0,
            filled_price=65000.0,
        )
        assert 0.0 <= score <= 1.0


# ── Event Bus Tests ──────────────────────────────────────────


class TestTradingEventBus:
    @pytest.mark.asyncio
    async def test_subscribe_receive(self) -> None:
        bus = TradingEventBus(max_queue_size=10)
        queue = bus.subscribe()
        bus.publish(TradingEvent(event_type="trade", data={"pair": "BTC-USD"}))
        event = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert event.event_type == "trade"
        assert event.data["pair"] == "BTC-USD"
        bus.unsubscribe(queue)

    @pytest.mark.asyncio
    async def test_bounded_queue_drops_oldest(self) -> None:
        bus = TradingEventBus(max_queue_size=3)
        queue = bus.subscribe()
        for i in range(5):
            bus.publish(TradingEvent(event_type="trade", data={"i": i}))
        events = []
        while not queue.empty():
            events.append(await queue.get())
        assert len(events) == 3
        assert events[0].data["i"] == 2  # 0 and 1 were dropped

    @pytest.mark.asyncio
    async def test_critical_events_always_delivered(self) -> None:
        bus = TradingEventBus(max_queue_size=2)
        queue = bus.subscribe()
        bus.publish(TradingEvent(event_type="trade", data={"i": 0}))
        bus.publish(TradingEvent(event_type="trade", data={"i": 1}))
        bus.publish(TradingEvent(
            event_type="kill_switch", data={"active": True}, priority=True,
        ))
        events = []
        while not queue.empty():
            events.append(await queue.get())
        assert any(e.event_type == "kill_switch" for e in events)

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_queue(self) -> None:
        bus = TradingEventBus()
        queue = bus.subscribe()
        assert bus.subscriber_count == 1
        bus.unsubscribe(queue)
        assert bus.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_sequence_numbers_increment(self) -> None:
        bus = TradingEventBus()
        queue = bus.subscribe()
        bus.publish(TradingEvent(event_type="trade", data={}))
        bus.publish(TradingEvent(event_type="trade", data={}))
        e1 = await asyncio.wait_for(queue.get(), timeout=1.0)
        e2 = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert e2.sequence == e1.sequence + 1
        bus.unsubscribe(queue)

    def test_to_sse_format(self) -> None:
        event = TradingEvent(event_type="trade", data={"pair": "BTC-USD"})
        event.sequence = 42
        sse = event.to_sse()
        assert "id: 42" in sse
        assert "event: trade" in sse
        assert '"pair": "BTC-USD"' in sse

    @pytest.mark.asyncio
    async def test_multiple_subscribers(self) -> None:
        bus = TradingEventBus()
        q1 = bus.subscribe()
        q2 = bus.subscribe()
        bus.publish(TradingEvent(event_type="trade", data={"pair": "ETH-USD"}))
        e1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        e2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert e1.data["pair"] == "ETH-USD"
        assert e2.data["pair"] == "ETH-USD"
        bus.unsubscribe(q1)
        bus.unsubscribe(q2)
