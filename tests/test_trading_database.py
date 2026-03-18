"""Tests for trading database — CRUD, WAL mode, tax lot queries."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from hestia.trading.database import TradingDatabase


@pytest_asyncio.fixture
async def db(tmp_path):
    """Create a fresh trading database for each test."""
    db_path = tmp_path / "test_trading.db"
    database = TradingDatabase(db_path=db_path)
    await database.connect()
    yield database
    await database.close()


def _make_bot(bot_id=None, **kwargs):
    """Helper to create bot data dict."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": bot_id or str(uuid.uuid4()),
        "name": kwargs.get("name", "Test Bot"),
        "strategy": kwargs.get("strategy", "grid"),
        "pair": kwargs.get("pair", "BTC-USD"),
        "status": kwargs.get("status", "created"),
        "capital_allocated": kwargs.get("capital_allocated", 87.50),
        "config": kwargs.get("config", {"num_levels": 10}),
        "created_at": kwargs.get("created_at", now),
        "updated_at": kwargs.get("updated_at", now),
        "user_id": kwargs.get("user_id", "user-default"),
    }


def _make_trade(trade_id=None, bot_id="bot-1", **kwargs):
    """Helper to create trade data dict."""
    return {
        "id": trade_id or str(uuid.uuid4()),
        "bot_id": bot_id,
        "side": kwargs.get("side", "buy"),
        "order_type": kwargs.get("order_type", "limit"),
        "price": kwargs.get("price", 65000.0),
        "quantity": kwargs.get("quantity", 0.001),
        "fee": kwargs.get("fee", 0.26),
        "fee_currency": kwargs.get("fee_currency", "USD"),
        "pair": kwargs.get("pair", "BTC-USD"),
        "tax_lot_id": kwargs.get("tax_lot_id"),
        "exchange_order_id": kwargs.get("exchange_order_id"),
        "timestamp": kwargs.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "metadata": kwargs.get("metadata", {}),
        "user_id": kwargs.get("user_id", "user-default"),
    }


async def _ensure_bot_and_trade(db, bot_id="bot-1", trade_id="trade-1"):
    """Create parent bot + trade so FK constraints are satisfied."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.create_bot(_make_bot(bot_id=bot_id))
    except Exception:
        pass  # Already exists
    try:
        await db.record_trade({
            "id": trade_id, "bot_id": bot_id, "side": "buy",
            "order_type": "limit", "price": 65000.0, "quantity": 0.001,
            "fee": 0.26, "fee_currency": "USD", "pair": "BTC-USD",
            "tax_lot_id": None, "exchange_order_id": None,
            "timestamp": now, "metadata": {}, "user_id": "user-default",
        })
    except Exception:
        pass  # Already exists


def _make_tax_lot(lot_id=None, trade_id=None, **kwargs):
    """Helper to create tax lot data dict."""
    return {
        "id": lot_id or str(uuid.uuid4()),
        "trade_id": trade_id or str(uuid.uuid4()),
        "pair": kwargs.get("pair", "BTC-USD"),
        "quantity": kwargs.get("quantity", 0.001),
        "remaining_quantity": kwargs.get("remaining_quantity", 0.001),
        "cost_basis": kwargs.get("cost_basis", 65.26),
        "cost_per_unit": kwargs.get("cost_per_unit", 65260.0),
        "method": kwargs.get("method", "hifo"),
        "status": kwargs.get("status", "open"),
        "acquired_at": kwargs.get("acquired_at", datetime.now(timezone.utc).isoformat()),
        "closed_at": kwargs.get("closed_at"),
        "realized_pnl": kwargs.get("realized_pnl", 0.0),
        "user_id": kwargs.get("user_id", "user-default"),
    }


# ── WAL Mode ──────────────────────────────────────────────────

class TestWALMode:
    @pytest.mark.asyncio
    async def test_wal_mode_enabled(self, db):
        """Verify WAL mode is active."""
        cursor = await db.connection.execute("PRAGMA journal_mode")
        row = await cursor.fetchone()
        assert row[0] == "wal"

    @pytest.mark.asyncio
    async def test_mmap_enabled(self, db):
        """Verify memory-mapped I/O is enabled."""
        cursor = await db.connection.execute("PRAGMA mmap_size")
        row = await cursor.fetchone()
        assert row[0] > 0

    @pytest.mark.asyncio
    async def test_foreign_keys_enabled(self, db):
        """Verify foreign keys are on."""
        cursor = await db.connection.execute("PRAGMA foreign_keys")
        row = await cursor.fetchone()
        assert row[0] == 1


# ── Bot CRUD ──────────────────────────────────────────────────

class TestBotCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get_bot(self, db):
        bot = _make_bot(name="Grid Alpha")
        await db.create_bot(bot)
        result = await db.get_bot(bot["id"])
        assert result is not None
        assert result["name"] == "Grid Alpha"
        assert result["strategy"] == "grid"
        assert result["config"]["num_levels"] == 10

    @pytest.mark.asyncio
    async def test_list_bots(self, db):
        await db.create_bot(_make_bot(name="Bot A"))
        await db.create_bot(_make_bot(name="Bot B"))
        bots = await db.list_bots()
        assert len(bots) == 2

    @pytest.mark.asyncio
    async def test_list_bots_by_status(self, db):
        await db.create_bot(_make_bot(name="Running", status="running"))
        await db.create_bot(_make_bot(name="Stopped", status="stopped"))
        running = await db.list_bots(status="running")
        assert len(running) == 1
        assert running[0]["name"] == "Running"

    @pytest.mark.asyncio
    async def test_update_bot(self, db):
        bot = _make_bot()
        await db.create_bot(bot)
        result = await db.update_bot(bot["id"], {"name": "Updated", "status": "running"})
        assert result["name"] == "Updated"
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_delete_bot(self, db):
        bot = _make_bot()
        await db.create_bot(bot)
        success = await db.delete_bot(bot["id"])
        assert success
        result = await db.get_bot(bot["id"])
        assert result["status"] == "stopped"

    @pytest.mark.asyncio
    async def test_get_nonexistent_bot(self, db):
        result = await db.get_bot("nonexistent")
        assert result is None


# ── Trade CRUD ────────────────────────────────────────────────

class TestTradeCRUD:
    @pytest.mark.asyncio
    async def test_record_and_get_trade(self, db):
        bot = _make_bot(bot_id="bot-1")
        await db.create_bot(bot)
        trade = _make_trade(bot_id="bot-1", price=65000.0, quantity=0.001)
        await db.record_trade(trade)
        trades = await db.get_trades(bot_id="bot-1")
        assert len(trades) == 1
        assert trades[0]["price"] == 65000.0

    @pytest.mark.asyncio
    async def test_trade_count(self, db):
        bot = _make_bot(bot_id="bot-1")
        await db.create_bot(bot)
        for i in range(5):
            await db.record_trade(_make_trade(bot_id="bot-1"))
        count = await db.get_trade_count(bot_id="bot-1")
        assert count == 5

    @pytest.mark.asyncio
    async def test_trade_pagination(self, db):
        bot = _make_bot(bot_id="bot-1")
        await db.create_bot(bot)
        for i in range(10):
            await db.record_trade(_make_trade(bot_id="bot-1"))
        page1 = await db.get_trades(bot_id="bot-1", limit=5, offset=0)
        page2 = await db.get_trades(bot_id="bot-1", limit=5, offset=5)
        assert len(page1) == 5
        assert len(page2) == 5
        # Different trades
        ids1 = {t["id"] for t in page1}
        ids2 = {t["id"] for t in page2}
        assert ids1.isdisjoint(ids2)

    @pytest.mark.asyncio
    async def test_trade_metadata_preserved(self, db):
        bot = _make_bot(bot_id="bot-1")
        await db.create_bot(bot)
        trade = _make_trade(
            bot_id="bot-1",
            metadata={"strategy": "grid", "signal_strength": 0.85},
        )
        await db.record_trade(trade)
        trades = await db.get_trades(bot_id="bot-1")
        assert trades[0]["metadata"]["signal_strength"] == 0.85


# ── Tax Lot CRUD ──────────────────────────────────────────────

class TestTaxLotCRUD:
    @pytest.mark.asyncio
    async def test_create_and_get_tax_lot(self, db):
        await _ensure_bot_and_trade(db, trade_id="t1")
        lot = _make_tax_lot(cost_per_unit=65260.0, trade_id="t1")
        await db.create_tax_lot(lot)
        lots = await db.get_tax_lots()
        assert len(lots) == 1
        assert lots[0]["cost_per_unit"] == 65260.0

    @pytest.mark.asyncio
    async def test_hifo_ordering(self, db):
        """HIFO should return highest cost-per-unit first."""
        await _ensure_bot_and_trade(db, trade_id="t1")
        await _ensure_bot_and_trade(db, trade_id="t2")
        await _ensure_bot_and_trade(db, trade_id="t3")
        await db.create_tax_lot(_make_tax_lot(cost_per_unit=60000.0, method="hifo", trade_id="t1"))
        await db.create_tax_lot(_make_tax_lot(cost_per_unit=70000.0, method="hifo", trade_id="t2"))
        await db.create_tax_lot(_make_tax_lot(cost_per_unit=65000.0, method="hifo", trade_id="t3"))
        lots = await db.get_open_tax_lots(method="hifo")
        costs = [l["cost_per_unit"] for l in lots]
        assert costs == [70000.0, 65000.0, 60000.0]

    @pytest.mark.asyncio
    async def test_fifo_ordering(self, db):
        """FIFO should return oldest first."""
        await _ensure_bot_and_trade(db, trade_id="t1")
        await _ensure_bot_and_trade(db, trade_id="t2")
        await _ensure_bot_and_trade(db, trade_id="t3")
        await db.create_tax_lot(_make_tax_lot(
            cost_per_unit=60000.0, method="fifo", trade_id="t1",
            acquired_at="2026-01-01T00:00:00+00:00",
        ))
        await db.create_tax_lot(_make_tax_lot(
            cost_per_unit=70000.0, method="fifo", trade_id="t2",
            acquired_at="2026-03-01T00:00:00+00:00",
        ))
        await db.create_tax_lot(_make_tax_lot(
            cost_per_unit=65000.0, method="fifo", trade_id="t3",
            acquired_at="2026-02-01T00:00:00+00:00",
        ))
        lots = await db.get_open_tax_lots(method="fifo")
        dates = [l["acquired_at"] for l in lots]
        assert dates[0] < dates[1] < dates[2]

    @pytest.mark.asyncio
    async def test_update_tax_lot(self, db):
        await _ensure_bot_and_trade(db, trade_id="t1")
        lot = _make_tax_lot(trade_id="t1")
        await db.create_tax_lot(lot)
        await db.update_tax_lot(lot["id"], {
            "remaining_quantity": 0.0005,
            "status": "partial",
            "realized_pnl": 5.0,
        })
        lots = await db.get_tax_lots()
        assert lots[0]["remaining_quantity"] == 0.0005
        assert lots[0]["status"] == "partial"
        assert lots[0]["realized_pnl"] == 5.0

    @pytest.mark.asyncio
    async def test_closed_lots_excluded_from_open(self, db):
        await _ensure_bot_and_trade(db, trade_id="t1")
        await _ensure_bot_and_trade(db, trade_id="t2")
        await db.create_tax_lot(_make_tax_lot(status="open", trade_id="t1"))
        await db.create_tax_lot(_make_tax_lot(status="closed", trade_id="t2"))
        open_lots = await db.get_open_tax_lots()
        assert len(open_lots) == 1

    @pytest.mark.asyncio
    async def test_filter_by_status(self, db):
        await _ensure_bot_and_trade(db, trade_id="t1")
        await _ensure_bot_and_trade(db, trade_id="t2")
        await db.create_tax_lot(_make_tax_lot(status="open", trade_id="t1"))
        await db.create_tax_lot(_make_tax_lot(status="closed", trade_id="t2"))
        closed = await db.get_tax_lots(status="closed")
        assert len(closed) == 1
        assert closed[0]["status"] == "closed"


# ── Daily Summary ─────────────────────────────────────────────

class TestDailySummary:
    @pytest.mark.asyncio
    async def test_upsert_and_get(self, db):
        summary = {
            "id": str(uuid.uuid4()),
            "date": "2026-03-18",
            "total_pnl": 25.50,
            "realized_pnl": 20.0,
            "unrealized_pnl": 5.50,
            "total_trades": 10,
            "winning_trades": 6,
            "losing_trades": 4,
            "total_fees": 2.60,
            "total_volume": 650.0,
            "positions": {"BTC-USD": {"qty": 0.01}},
            "strategy_attribution": {"grid": 15.0, "mean_reversion": 10.50},
            "user_id": "user-default",
        }
        await db.upsert_daily_summary(summary)
        result = await db.get_daily_summary("2026-03-18")
        assert result is not None
        assert result["total_pnl"] == 25.50
        assert result["positions"]["BTC-USD"]["qty"] == 0.01

    @pytest.mark.asyncio
    async def test_upsert_overwrites(self, db):
        s1 = {
            "id": str(uuid.uuid4()),
            "date": "2026-03-18",
            "total_pnl": 10.0,
            "user_id": "user-default",
        }
        s2 = {
            "id": str(uuid.uuid4()),
            "date": "2026-03-18",
            "total_pnl": 25.0,
            "user_id": "user-default",
        }
        await db.upsert_daily_summary(s1)
        await db.upsert_daily_summary(s2)
        result = await db.get_daily_summary("2026-03-18")
        assert result["total_pnl"] == 25.0

    @pytest.mark.asyncio
    async def test_list_daily_summaries(self, db):
        for i in range(5):
            await db.upsert_daily_summary({
                "id": str(uuid.uuid4()),
                "date": f"2026-03-{18-i:02d}",
                "total_pnl": float(i * 10),
                "user_id": "user-default",
            })
        summaries = await db.get_daily_summaries(limit=3)
        assert len(summaries) == 3


# ── Reconciliation ────────────────────────────────────────────

class TestReconciliation:
    @pytest.mark.asyncio
    async def test_log_and_retrieve(self, db):
        result = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "local_balance": 0.01,
            "exchange_balance": 0.01,
            "discrepancy": 0.0,
            "pair": "BTC-USD",
            "resolved": True,
            "notes": "Match",
        }
        await db.log_reconciliation(result)
        results = await db.get_recent_reconciliations()
        assert len(results) == 1
        assert results[0]["pair"] == "BTC-USD"
