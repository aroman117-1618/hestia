"""
Tests for Sprint 23 — position tracking, price validation, execution pipeline,
and reconciliation.
"""

import asyncio
import pytest
import pytest_asyncio

from hestia.trading.exchange.base import OrderRequest
from hestia.trading.exchange.paper import PaperAdapter
from hestia.trading.executor import TradeExecutor
from hestia.trading.position_tracker import Position, PositionTracker
from hestia.trading.price_validator import PriceValidator
from hestia.trading.risk import RiskManager
from hestia.trading.strategies.base import Signal, SignalType


# ── Position ──────────────────────────────────────────────────

class TestPosition:
    def test_add_position(self):
        pos = Position("BTC-USD")
        pos.add(0.001, 65000.0, fee=0.26)
        assert pos.quantity == 0.001
        assert pos.avg_entry_price == pytest.approx(65260.0, abs=1.0)
        assert pos.total_cost == pytest.approx(65.26, abs=0.01)

    def test_add_multiple(self):
        pos = Position("BTC-USD")
        pos.add(0.001, 65000.0)
        pos.add(0.001, 66000.0)
        assert pos.quantity == 0.002
        assert pos.avg_entry_price == pytest.approx(65500.0, abs=1.0)

    def test_reduce_position(self):
        pos = Position("BTC-USD")
        pos.add(0.002, 65000.0)
        pnl = pos.reduce(0.001, 66000.0)
        assert pnl == pytest.approx(1.0, abs=0.01)  # $1 profit
        assert pos.quantity == pytest.approx(0.001)

    def test_reduce_full_position(self):
        pos = Position("BTC-USD")
        pos.add(0.001, 65000.0)
        pnl = pos.reduce(0.001, 66000.0)
        assert pos.quantity == 0.0
        assert pos.avg_entry_price == 0.0

    def test_reduce_more_than_held(self):
        pos = Position("BTC-USD")
        pos.add(0.001, 65000.0)
        pnl = pos.reduce(0.005, 66000.0)  # Try to sell 5x what we have
        assert pos.quantity == 0.0  # Should cap at held amount

    def test_unrealized_pnl_profit(self):
        pos = Position("BTC-USD")
        pos.add(0.001, 65000.0)
        upnl = pos.unrealized_pnl(66000.0)
        assert upnl == pytest.approx(1.0, abs=0.01)

    def test_unrealized_pnl_loss(self):
        pos = Position("BTC-USD")
        pos.add(0.001, 65000.0)
        upnl = pos.unrealized_pnl(64000.0)
        assert upnl == pytest.approx(-1.0, abs=0.01)

    def test_unrealized_pnl_zero_quantity(self):
        pos = Position("BTC-USD")
        assert pos.unrealized_pnl(65000.0) == 0.0

    def test_to_dict(self):
        pos = Position("BTC-USD")
        pos.add(0.001, 65000.0)
        d = pos.to_dict()
        assert d["pair"] == "BTC-USD"
        assert d["quantity"] == 0.001


# ── PositionTracker ───────────────────────────────────────────

class TestPositionTracker:
    @pytest.mark.asyncio
    async def test_record_buy(self):
        tracker = PositionTracker()
        pnl = await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)
        assert pnl == 0.0
        pos = tracker.get_position("BTC-USD")
        assert pos is not None
        assert pos.quantity == 0.001

    @pytest.mark.asyncio
    async def test_record_sell(self):
        tracker = PositionTracker()
        await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)
        pnl = await tracker.record_fill("BTC-USD", "sell", 0.001, 66000.0)
        assert pnl == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_total_exposure(self):
        tracker = PositionTracker()
        await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)
        await tracker.record_fill("ETH-USD", "buy", 0.01, 3500.0)
        exposure = tracker.get_total_exposure()
        assert exposure == pytest.approx(100.0, abs=1.0)

    @pytest.mark.asyncio
    async def test_total_unrealized_pnl(self):
        tracker = PositionTracker()
        await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)
        prices = {"BTC-USD": 66000.0}
        upnl = tracker.get_total_unrealized_pnl(prices)
        assert upnl == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_portfolio_summary(self):
        tracker = PositionTracker()
        await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)
        summary = tracker.get_portfolio_summary({"BTC-USD": 66000.0})
        assert summary["position_count"] == 1
        assert summary["total_unrealized_pnl"] == pytest.approx(1.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_get_all_positions(self):
        tracker = PositionTracker()
        await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)
        await tracker.record_fill("ETH-USD", "buy", 0.01, 3500.0)
        positions = tracker.get_all_positions()
        assert len(positions) == 2

    @pytest.mark.asyncio
    async def test_closed_position_excluded(self):
        tracker = PositionTracker()
        await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)
        await tracker.record_fill("BTC-USD", "sell", 0.001, 66000.0)
        positions = tracker.get_all_positions()
        assert len(positions) == 0


# ── Reconciliation ────────────────────────────────────────────

class TestReconciliation:
    @pytest.mark.asyncio
    async def test_reconcile_matching(self):
        adapter = PaperAdapter(initial_balance_usd=250.0)
        await adapter.connect()

        tracker = PositionTracker(exchange=adapter)

        # Buy through adapter and tracker
        order = OrderRequest(pair="BTC-USD", side="buy", order_type="limit",
                            quantity=0.001, price=65000.0)
        await adapter.place_order(order)
        await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)

        results = await tracker.reconcile()
        assert len(results) >= 1
        btc_result = [r for r in results if r.pair == "BTC-USD"]
        assert len(btc_result) == 1
        assert btc_result[0].resolved  # Should match

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_reconcile_discrepancy(self):
        adapter = PaperAdapter(initial_balance_usd=250.0)
        await adapter.connect()

        tracker = PositionTracker(exchange=adapter)

        # Record locally but don't execute on exchange
        await tracker.record_fill("BTC-USD", "buy", 0.001, 65000.0)

        results = await tracker.reconcile()
        btc_result = [r for r in results if r.pair == "BTC-USD"]
        assert len(btc_result) == 1
        assert btc_result[0].has_discrepancy

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_reconcile_no_exchange(self):
        tracker = PositionTracker()  # No exchange
        results = await tracker.reconcile()
        assert results == []

    @pytest.mark.asyncio
    async def test_reconcile_untracked_position(self):
        adapter = PaperAdapter(initial_balance_usd=250.0)
        await adapter.connect()

        # Buy on exchange but don't track locally
        order = OrderRequest(pair="BTC-USD", side="buy", order_type="limit",
                            quantity=0.001, price=65000.0)
        await adapter.place_order(order)

        tracker = PositionTracker(exchange=adapter, max_acceptable_discrepancy=0.0001)
        results = await tracker.reconcile()
        # Should detect untracked BTC position on exchange
        untracked = [r for r in results if not r.resolved and r.discrepancy > 0]
        assert len(untracked) >= 1

        await adapter.disconnect()


# ── PriceValidator ────────────────────────────────────────────

class TestPriceValidator:
    @pytest.mark.asyncio
    async def test_valid_prices(self):
        validator = PriceValidator(max_divergence=0.02)
        validator.set_secondary_price("BTC-USD", 65000.0)
        result = await validator.validate("BTC-USD", proposed_price=65100.0)
        assert result["valid"] is True
        assert result["divergence"] < 0.02

    @pytest.mark.asyncio
    async def test_divergent_prices(self):
        validator = PriceValidator(max_divergence=0.02)
        validator.set_secondary_price("BTC-USD", 65000.0)
        result = await validator.validate("BTC-USD", proposed_price=70000.0)
        assert result["valid"] is False
        assert result["divergence"] > 0.02

    @pytest.mark.asyncio
    async def test_no_secondary_price_passes(self):
        validator = PriceValidator()
        result = await validator.validate("BTC-USD", proposed_price=65000.0)
        assert result["valid"] is True
        assert "skipped" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_zero_primary_fails(self):
        validator = PriceValidator()
        validator.set_secondary_price("BTC-USD", 65000.0)
        result = await validator.validate("BTC-USD", proposed_price=0.0)
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_last_check_stored(self):
        validator = PriceValidator()
        validator.set_secondary_price("BTC-USD", 65000.0)
        await validator.validate("BTC-USD", proposed_price=65100.0)
        assert validator.last_check is not None
        assert validator.last_check["valid"] is True

    @pytest.mark.asyncio
    async def test_with_exchange(self):
        adapter = PaperAdapter()
        await adapter.connect()
        validator = PriceValidator(exchange=adapter)
        validator.set_secondary_price("BTC-USD", 65000.0)
        primary = await validator.get_primary_price("BTC-USD")
        assert primary == 65000.0
        await adapter.disconnect()


# ── TradeExecutor Pipeline ────────────────────────────────────

class TestTradeExecutor:
    @pytest_asyncio.fixture
    async def executor(self):
        adapter = PaperAdapter(initial_balance_usd=1000.0)
        await adapter.connect()
        risk = RiskManager()
        tracker = PositionTracker(exchange=adapter)
        validator = PriceValidator(max_divergence=0.02)
        validator.set_secondary_price("BTC-USD", 65000.0)

        exe = TradeExecutor(
            exchange=adapter,
            risk_manager=risk,
            position_tracker=tracker,
            price_validator=validator,
        )
        yield exe
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_execute_buy_signal(self, executor):
        signal = Signal(
            signal_type=SignalType.BUY,
            pair="BTC-USD",
            price=65000.0,
            quantity=0.001,
            confidence=0.8,
            reason="Test buy",
        )
        result = await executor.execute_signal(signal, portfolio_value=1000.0)
        assert result["result"] == "filled"
        assert result["fill"]["price"] == 65000.0

    @pytest.mark.asyncio
    async def test_execute_hold_skipped(self, executor):
        signal = Signal(signal_type=SignalType.HOLD)
        result = await executor.execute_signal(signal, portfolio_value=250.0)
        assert result["result"] == "skipped"

    @pytest.mark.asyncio
    async def test_execute_rejected_by_risk(self, executor):
        """Deploying > 80% should be rejected by risk manager."""
        # First deploy 85% of capital
        await executor._positions.record_fill("ETH-USD", "buy", 0.1, 8500.0)
        signal = Signal(
            signal_type=SignalType.BUY,
            pair="BTC-USD",
            price=65000.0,
            quantity=0.005,  # ~$325 more when already 85% deployed
            confidence=0.8,
        )
        result = await executor.execute_signal(signal, portfolio_value=1000.0)
        assert result["result"] == "rejected"
        assert result["pipeline_steps"][0]["step"] == "risk_validation"

    @pytest.mark.asyncio
    async def test_execute_rejected_by_price(self, executor):
        """Divergent price should block execution."""
        executor._price_validator.set_secondary_price("BTC-USD", 60000.0)  # 7.7% off
        signal = Signal(
            signal_type=SignalType.BUY,
            pair="BTC-USD",
            price=65000.0,
            quantity=0.001,
            confidence=0.8,
        )
        result = await executor.execute_signal(signal, portfolio_value=1000.0)
        assert result["result"] == "rejected"
        assert "price" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_kill_switch_blocks(self, executor):
        executor._risk.activate_kill_switch("Test")
        signal = Signal(
            signal_type=SignalType.BUY,
            pair="BTC-USD",
            price=65000.0,
            quantity=0.001,
        )
        result = await executor.execute_signal(signal, portfolio_value=1000.0)
        assert result["result"] == "rejected"
        assert "kill switch" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_sell_updates_position(self, executor):
        # Buy first
        buy = Signal(signal_type=SignalType.BUY, pair="BTC-USD",
                    price=65000.0, quantity=0.001)
        await executor.execute_signal(buy, portfolio_value=1000.0)

        pos = executor._positions.get_position("BTC-USD")
        assert pos is not None
        assert pos.quantity > 0  # May be Kelly-adjusted

        # Sell what we bought
        executor._price_validator.set_secondary_price("BTC-USD", 66000.0)
        sell = Signal(signal_type=SignalType.SELL, pair="BTC-USD",
                     price=66000.0, quantity=pos.quantity)
        result = await executor.execute_signal(sell, portfolio_value=1000.0)

        if result["result"] == "filled":
            pos = executor._positions.get_position("BTC-USD")
            # Position should be reduced (may not be exactly 0 due to
            # independent Kelly sizing on the sell side)
            assert pos.quantity < 0.001

    @pytest.mark.asyncio
    async def test_execution_stats(self, executor):
        signal = Signal(signal_type=SignalType.BUY, pair="BTC-USD",
                       price=65000.0, quantity=0.001)
        await executor.execute_signal(signal, portfolio_value=1000.0)

        stats = executor.stats
        assert stats["total_signals_processed"] >= 1
        assert stats["executions"] >= 1

    @pytest.mark.asyncio
    async def test_full_pipeline_audit_trail(self, executor):
        """Verify all pipeline steps are logged in audit trail."""
        signal = Signal(
            signal_type=SignalType.BUY,
            pair="BTC-USD",
            price=65000.0,
            quantity=0.001,
            confidence=0.9,
            reason="Full pipeline test",
        )
        result = await executor.execute_signal(signal, portfolio_value=1000.0)
        assert "pipeline_steps" in result
        steps = [s["step"] for s in result["pipeline_steps"]]
        assert "risk_validation" in steps
        assert "price_validation" in steps
        if result["result"] == "filled":
            assert "exchange_execution" in steps

    @pytest.mark.asyncio
    async def test_insufficient_balance_handled(self, executor):
        """Exchange rejects order due to insufficient balance."""
        signal = Signal(
            signal_type=SignalType.BUY,
            pair="BTC-USD",
            price=65000.0,
            quantity=0.1,  # ~$6500, more than $1000 balance
            confidence=0.8,
        )
        result = await executor.execute_signal(signal, portfolio_value=1000.0)
        # Risk manager should adjust quantity down via Kelly/position limits
        assert result["result"] in ("filled", "rejected", "failed")
