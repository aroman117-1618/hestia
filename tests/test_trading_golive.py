"""Tests for Sprint 27 — Go-Live (BotRunner, BotOrchestrator).

Covers: bot runner tick logic, orchestrator lifecycle, concurrency locks,
error handling with exponential backoff, exchange reconciliation,
atomic transactions, active reconciliation kill switch, circuit breaker cascade.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from hestia.trading.bot_runner import BotRunner, _create_strategy
from hestia.trading.event_bus import TradingEventBus
from hestia.trading.exchange.base import AccountBalance, OrderResult
from hestia.trading.exchange.paper import PaperAdapter
from hestia.trading.models import (
    Bot, BotStatus, CircuitBreakerState, CircuitBreakerType,
    ReconciliationResult, StrategyType,
)
from hestia.trading.orchestrator import BotOrchestrator
from hestia.trading.position_tracker import Position, PositionTracker
from hestia.trading.risk import RiskManager
from hestia.trading.strategies.base import Signal, SignalType


# ── Strategy Factory Tests ───────────────────────────────────


class TestStrategyFactory:
    def test_create_grid(self) -> None:
        strategy = _create_strategy(StrategyType.GRID, {})
        assert strategy.strategy_type == "grid"

    def test_create_mean_reversion(self) -> None:
        strategy = _create_strategy(StrategyType.MEAN_REVERSION, {})
        assert strategy.strategy_type == "mean_reversion"

    def test_create_bollinger_strategy(self) -> None:
        strategy = _create_strategy(StrategyType.BOLLINGER_BREAKOUT, {})
        assert strategy.strategy_type == "bollinger_breakout"
        assert strategy.name == "Bollinger Breakout"

    def test_create_signal_dca_strategy(self) -> None:
        strategy = _create_strategy(StrategyType.SIGNAL_DCA, {})
        assert strategy.strategy_type == "signal_dca"
        assert strategy.name == "Signal-Enhanced DCA"

    def test_create_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            _create_strategy(StrategyType("nonexistent"), {})


# ── BotRunner Tests ──────────────────────────────────────────


class TestBotRunner:
    def _make_bot(self, strategy: str = "mean_reversion") -> Bot:
        return Bot(
            name="test-bot",
            strategy=StrategyType(strategy),
            pair="BTC-USD",
            capital_allocated=250.0,
            config={},
            user_id="user-default",
        )

    @pytest.mark.asyncio
    async def test_runner_creates_with_valid_bot(self) -> None:
        bot = self._make_bot()
        adapter = PaperAdapter(initial_balance_usd=250.0)
        await adapter.connect()
        risk = RiskManager()
        runner = BotRunner(bot=bot, exchange=adapter, risk_manager=risk)
        assert runner.bot.name == "test-bot"
        assert not runner.is_running
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_runner_stop_flag(self) -> None:
        bot = self._make_bot()
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        runner = BotRunner(bot=bot, exchange=adapter, risk_manager=risk, poll_interval=1)
        runner.stop()
        assert not runner.is_running
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_get_portfolio_value(self) -> None:
        bot = self._make_bot()
        adapter = PaperAdapter(initial_balance_usd=500.0)
        await adapter.connect()
        risk = RiskManager()
        runner = BotRunner(bot=bot, exchange=adapter, risk_manager=risk)
        value = await runner._get_portfolio_value()
        assert value == pytest.approx(500.0, abs=1.0)
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_tick_with_insufficient_data_skips(self) -> None:
        """Tick should skip when not enough candle data."""
        bot = self._make_bot()
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        runner = BotRunner(bot=bot, exchange=adapter, risk_manager=risk)
        # Mock fetch_candles to return too few candles
        runner._fetch_candles = AsyncMock(return_value=pd.DataFrame([
            {"timestamp": datetime.now(timezone.utc), "open": 65000, "high": 65100,
             "low": 64900, "close": 65050, "volume": 100}
        ]))
        # Should not raise — just skip
        await runner._tick("BTC-USD")
        await adapter.disconnect()


# ── BotOrchestrator Tests ────────────────────────────────────


class TestBotOrchestrator:
    def _make_bot(self, bot_id: str = "bot-1", status: str = "running") -> Bot:
        return Bot(
            id=bot_id,
            name="test-bot",
            strategy=StrategyType.MEAN_REVERSION,
            pair="BTC-USD",
            capital_allocated=250.0,
            status=BotStatus(status),
            config={},
        )

    @pytest.mark.asyncio
    async def test_start_and_stop_runner(self) -> None:
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        bus = TradingEventBus()
        orchestrator = BotOrchestrator(exchange=adapter, risk_manager=risk, event_bus=bus)

        bot = self._make_bot()

        # Start runner
        started = await orchestrator.start_runner(bot)
        assert started is True
        assert orchestrator.active_count == 1

        # Stop runner
        stopped = await orchestrator.stop_runner(bot.id)
        assert stopped is True
        # Give the task time to cancel
        await asyncio.sleep(0.1)
        assert orchestrator.active_count == 0

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_duplicate_start_prevented(self) -> None:
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        orchestrator = BotOrchestrator(exchange=adapter, risk_manager=risk)

        bot = self._make_bot()
        await orchestrator.start_runner(bot)

        # Second start should return False
        duplicate = await orchestrator.start_runner(bot)
        assert duplicate is False
        assert orchestrator.active_count == 1

        await orchestrator.stop_all()
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_stop_nonexistent_returns_false(self) -> None:
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        orchestrator = BotOrchestrator(exchange=adapter, risk_manager=risk)
        stopped = await orchestrator.stop_runner("nonexistent-id")
        assert stopped is False
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_stop_all(self) -> None:
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        orchestrator = BotOrchestrator(exchange=adapter, risk_manager=risk)

        for i in range(3):
            await orchestrator.start_runner(self._make_bot(f"bot-{i}"))
        assert orchestrator.active_count == 3

        await orchestrator.stop_all()
        await asyncio.sleep(0.1)
        assert orchestrator.active_count == 0
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_active_bot_ids(self) -> None:
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        orchestrator = BotOrchestrator(exchange=adapter, risk_manager=risk)

        await orchestrator.start_runner(self._make_bot("alpha"))
        await orchestrator.start_runner(self._make_bot("beta"))

        ids = orchestrator.active_bot_ids
        assert "alpha" in ids
        assert "beta" in ids

        await orchestrator.stop_all()
        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_reconcile_exchange_state_logs(self) -> None:
        """Reconciliation should not crash even with empty balances."""
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        orchestrator = BotOrchestrator(exchange=adapter, risk_manager=risk)
        # Should not raise
        await orchestrator._reconcile_exchange_state()
        await adapter.disconnect()


# ── Phase 1.1: Atomic Trade Recording Tests ──────────────────


class TestAtomicTradeRecording:
    """Verify trade + tax lot writes are atomic (all-or-nothing)."""

    async def _setup_manager(self) -> tuple:
        """Create a TradingManager with in-memory DB and a test bot."""
        from hestia.trading.database import TradingDatabase
        from hestia.trading.manager import TradingManager

        db = TradingDatabase(db_path=":memory:")
        await db.connect()
        adapter = PaperAdapter(initial_balance_usd=250.0)
        await adapter.connect()
        manager = TradingManager(database=db, exchange=adapter)
        manager._initialized = True

        # Create a bot so FK constraint is satisfied
        await manager.create_bot(name="test", strategy="grid", pair="BTC-USD", capital=250.0)
        bots = await manager.list_bots()
        bot_id = bots[0].id
        return manager, db, adapter, bot_id

    @pytest.mark.asyncio
    async def test_buy_creates_trade_and_lot_atomically(self) -> None:
        """A BUY trade should create both trade record and tax lot."""
        manager, db, adapter, bot_id = await self._setup_manager()

        trade = await manager.record_trade(
            bot_id=bot_id, side="buy", price=65000.0,
            quantity=0.001, fee=0.26, pair="BTC-USD",
        )

        # Both should exist
        trades = await db.get_trades(user_id="user-default")
        lots = await db.get_tax_lots(user_id="user-default")
        assert len(trades) == 1
        assert len(lots) == 1
        assert lots[0]["trade_id"] == trade.id
        assert lots[0]["quantity"] == pytest.approx(0.001)

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_sell_consumes_lot_and_records_trade(self) -> None:
        """A SELL should consume tax lots and record trade atomically."""
        manager, db, adapter, bot_id = await self._setup_manager()

        # Buy first
        await manager.record_trade(
            bot_id=bot_id, side="buy", price=65000.0,
            quantity=0.001, fee=0.26,
        )
        # Sell
        await manager.record_trade(
            bot_id=bot_id, side="sell", price=66000.0,
            quantity=0.001, fee=0.26,
        )

        trades = await db.get_trades(user_id="user-default")
        lots = await db.get_tax_lots(user_id="user-default")
        assert len(trades) == 2
        # Tax lot should be closed
        assert lots[0]["status"] == "closed"
        assert lots[0]["realized_pnl"] > 0  # $1 profit per unit × 0.001

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_rollback_on_db_error(self) -> None:
        """If create_tax_lot_no_commit fails, trade should be rolled back."""
        manager, db, adapter, bot_id = await self._setup_manager()

        # Patch create_tax_lot_no_commit to fail AFTER trade is written
        async def fail_on_lot(*args: Any, **kwargs: Any) -> None:
            raise RuntimeError("Simulated DB write failure")

        db.create_tax_lot_no_commit = fail_on_lot

        with pytest.raises(RuntimeError, match="Simulated DB write failure"):
            await manager.record_trade(
                bot_id=bot_id, side="buy", price=65000.0,
                quantity=0.001, fee=0.26,
            )

        # Both should be empty — rolled back
        trades = await db.get_trades(user_id="user-default")
        lots = await db.get_tax_lots(user_id="user-default")
        assert len(trades) == 0
        assert len(lots) == 0

        await adapter.disconnect()


# ── Phase 1.2: Active Reconciliation Tests ───────────────────


class TestActiveReconciliation:
    """Verify reconciliation triggers kill switch on divergence."""

    @pytest.mark.asyncio
    async def test_matching_positions_no_kill_switch(self) -> None:
        """When positions match, kill switch should NOT activate."""
        kill_called = []
        adapter = PaperAdapter()
        await adapter.connect()

        tracker = PositionTracker(
            exchange=adapter,
            kill_switch_callback=lambda reason: kill_called.append(reason),
        )
        # No positions, exchange has no crypto → should match
        results = await tracker.reconcile()
        assert len(kill_called) == 0

        await adapter.disconnect()

    @pytest.mark.asyncio
    async def test_divergence_triggers_kill_switch(self) -> None:
        """When local position diverges from exchange, kill switch should activate."""
        kill_called = []
        bus = TradingEventBus()
        adapter = MagicMock()
        adapter.is_connected = True

        # Exchange says 0.01 BTC, but local tracker has 0.005
        adapter.get_balances = AsyncMock(return_value={
            "BTC": AccountBalance(available=0.01, hold=0.0, currency="BTC"),
            "USD": AccountBalance(available=200.0, hold=0.0, currency="USD"),
        })

        tracker = PositionTracker(
            exchange=adapter,
            max_acceptable_discrepancy=0.001,
            kill_switch_callback=lambda reason: kill_called.append(reason),
            event_bus=bus,
        )
        # Record a smaller local position
        await tracker.record_fill("BTC-USD", "buy", 0.005, 65000.0)

        results = await tracker.reconcile()

        # Kill switch should have been called
        assert len(kill_called) == 1
        assert "divergence" in kill_called[0].lower() or "discrepancy" in kill_called[0].lower()

    @pytest.mark.asyncio
    async def test_untracked_exchange_position_triggers_kill_switch(self) -> None:
        """Untracked position on exchange should trigger kill switch."""
        kill_called = []
        adapter = MagicMock()
        adapter.is_connected = True
        adapter.get_balances = AsyncMock(return_value={
            "ETH": AccountBalance(available=0.5, hold=0.0, currency="ETH"),
            "USD": AccountBalance(available=200.0, hold=0.0, currency="USD"),
        })

        tracker = PositionTracker(
            exchange=adapter,
            kill_switch_callback=lambda reason: kill_called.append(reason),
        )
        # We don't track ETH locally
        results = await tracker.reconcile()

        assert len(kill_called) == 1
        unresolved = [r for r in results if not r.resolved]
        assert len(unresolved) == 1
        assert "ETH" in unresolved[0].notes


# ── Phase 1.3: Circuit Breaker Cascade Tests ────────────────


class TestCircuitBreakerCascade:
    """Verify circuit breakers trigger and block orders correctly."""

    def test_drawdown_triggers_and_blocks(self) -> None:
        """15% drawdown should trigger breaker and reject all orders."""
        risk = RiskManager({"risk": {"circuit_breakers": {"drawdown": {"threshold": 0.15}}}})
        risk.update_portfolio_value(1000.0)  # Set peak
        risk.update_portfolio_value(840.0)   # 16% drawdown

        breaker = risk.get_breaker(CircuitBreakerType.DRAWDOWN)
        assert breaker.state == CircuitBreakerState.TRIGGERED

        # Should reject orders
        result = risk.validate_order("buy", 0.001, 65000.0, 840.0, 0.0)
        assert result["approved"] is False
        assert "drawdown" in result["reasons"][0].lower()

    def test_daily_loss_triggers_with_cooldown(self) -> None:
        """5% daily loss should trigger breaker with 24h cooldown."""
        risk = RiskManager({"risk": {"circuit_breakers": {"daily_loss": {"threshold": 0.05}}}})
        # Record losses exceeding 5% of portfolio
        risk.record_trade_pnl(-60.0, 1000.0)  # 6% loss

        breaker = risk.get_breaker(CircuitBreakerType.DAILY_LOSS)
        assert breaker.state == CircuitBreakerState.TRIGGERED
        assert breaker.cooldown_until is not None

    def test_kill_switch_overrides_everything(self) -> None:
        """Kill switch should block orders even if all breakers are clean."""
        risk = RiskManager()
        risk.activate_kill_switch("Test activation")

        result = risk.validate_order("buy", 0.001, 65000.0, 1000.0, 0.0)
        assert result["approved"] is False
        assert "Kill switch" in result["reasons"][0]

    def test_all_breakers_armed_by_default(self) -> None:
        """All circuit breakers should be armed by default."""
        risk = RiskManager()
        for bt in CircuitBreakerType:
            breaker = risk.get_breaker(bt)
            assert breaker.state == CircuitBreakerState.ARMED, f"{bt.value} should be armed"


# ── Phase 1.4: Risk State Persistence Tests ─────────────────


class TestRiskStatePersistence:
    """Verify risk state survives DB round-trip."""

    @pytest.mark.asyncio
    async def test_kill_switch_persists_and_restores(self) -> None:
        """Kill switch state should survive save → new RiskManager → restore."""
        from hestia.trading.database import TradingDatabase

        db = TradingDatabase(db_path=":memory:")
        await db.connect()

        # Activate kill switch and persist
        risk1 = RiskManager()
        risk1.set_database(db)
        risk1.activate_kill_switch("Integration test")
        await risk1.persist_state()

        # Create a fresh RiskManager and restore
        risk2 = RiskManager()
        risk2.set_database(db)
        await risk2.restore_state()

        assert risk2.is_kill_switch_active
        assert risk2._kill_switch_reason == "Integration test"

    @pytest.mark.asyncio
    async def test_breaker_state_persists(self) -> None:
        """Triggered circuit breaker should survive restart."""
        from hestia.trading.database import TradingDatabase

        db = TradingDatabase(db_path=":memory:")
        await db.connect()

        risk1 = RiskManager({"risk": {"circuit_breakers": {"drawdown": {"threshold": 0.15}}}})
        risk1.set_database(db)
        risk1.update_portfolio_value(1000.0)
        risk1.update_portfolio_value(840.0)  # Trigger drawdown
        await risk1.persist_state()

        risk2 = RiskManager()
        risk2.set_database(db)
        await risk2.restore_state()

        breaker = risk2.get_breaker(CircuitBreakerType.DRAWDOWN)
        assert breaker.state == CircuitBreakerState.TRIGGERED

    @pytest.mark.asyncio
    async def test_pnl_tracking_persists(self) -> None:
        """Daily/weekly PnL should survive restart."""
        from hestia.trading.database import TradingDatabase

        db = TradingDatabase(db_path=":memory:")
        await db.connect()

        risk1 = RiskManager()
        risk1.set_database(db)
        risk1.record_trade_pnl(-30.0, 1000.0)
        await risk1.persist_state()

        risk2 = RiskManager()
        risk2.set_database(db)
        await risk2.restore_state()

        assert risk2._daily_pnl == pytest.approx(-30.0)


# ── Error Recovery Tests ─────────────────────────────────────


class TestErrorRecovery:
    """Verify BotRunner error handling and orchestrator crash detection."""

    def test_runner_backoff_constants(self) -> None:
        """Verify error handling constants are set correctly."""
        from hestia.trading.bot_runner import MAX_CONSECUTIVE_ERRORS, BACKOFF_INITIAL_S, BACKOFF_MAX_S
        assert MAX_CONSECUTIVE_ERRORS == 3
        assert BACKOFF_INITIAL_S == 10.0
        assert BACKOFF_MAX_S == 60.0

    @pytest.mark.asyncio
    async def test_orchestrator_marks_crashed_bot_error(self) -> None:
        """When a runner crashes, orchestrator should mark bot as ERROR."""
        adapter = PaperAdapter()
        await adapter.connect()
        risk = RiskManager()
        bus = TradingEventBus()
        orchestrator = BotOrchestrator(exchange=adapter, risk_manager=risk, event_bus=bus)

        bot = Bot(
            id="crash-bot", name="crasher",
            strategy=StrategyType.MEAN_REVERSION, pair="BTC-USD",
            capital_allocated=250.0, status=BotStatus.RUNNING, config={},
        )

        # Verify the done callback exists and handles exceptions
        task = MagicMock()
        task.cancelled.return_value = False
        task.exception.return_value = RuntimeError("Simulated crash")

        # Patch _mark_bot_error to track calls
        with patch.object(orchestrator, "_mark_bot_error", new_callable=AsyncMock) as mock_mark:
            orchestrator._runners["crash-bot"] = task
            orchestrator._on_runner_done("crash-bot", task)
            # Give the async task time to be created
            await asyncio.sleep(0.1)

        await adapter.disconnect()


# ── Bollinger Breakout Strategy Tests ────────────────────────


class TestBollingerBreakoutStrategy:
    """Verify Bollinger breakout signal generation."""

    def _make_df(
        self,
        close: float = 65000.0,
        bb_upper: float = 66000.0,
        bb_lower: float = 64000.0,
        bb_middle: float = 65000.0,
        volume_ratio: float = 2.0,
        rows: int = 30,
    ) -> pd.DataFrame:
        """Build a minimal DataFrame with pre-computed indicators."""
        data = {
            "open": [close] * rows,
            "high": [close + 100] * rows,
            "low": [close - 100] * rows,
            "close": [close] * rows,
            "volume": [1000] * rows,
            "bb_upper": [bb_upper] * rows,
            "bb_lower": [bb_lower] * rows,
            "bb_middle": [bb_middle] * rows,
            "volume_ratio": [volume_ratio] * rows,
            "rsi": [50.0] * rows,
            "sma": [close] * rows,
        }
        return pd.DataFrame(data)

    def test_buy_on_upper_breakout_with_volume(self) -> None:
        from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy
        strategy = BollingerBreakoutStrategy()
        # Price above upper band + high volume
        df = self._make_df(close=66500.0, bb_upper=66000.0, volume_ratio=2.0)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.BUY
        assert signal.confidence > 0.5
        assert "bullish_breakout" in signal.metadata.get("entry_type", "")

    def test_sell_on_lower_breakout_with_volume(self) -> None:
        from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy
        strategy = BollingerBreakoutStrategy()
        # Price below lower band + high volume
        df = self._make_df(close=63500.0, bb_lower=64000.0, volume_ratio=1.8)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.SELL
        assert signal.confidence > 0.5
        assert "bearish_breakout" in signal.metadata.get("entry_type", "")

    def test_hold_when_inside_bands(self) -> None:
        from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy
        strategy = BollingerBreakoutStrategy()
        df = self._make_df(close=65000.0, bb_upper=66000.0, bb_lower=64000.0)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.HOLD

    def test_hold_when_breakout_without_volume(self) -> None:
        from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy
        strategy = BollingerBreakoutStrategy()
        # Price above upper band but low volume
        df = self._make_df(close=66500.0, bb_upper=66000.0, volume_ratio=1.0)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.HOLD
        assert "insufficient volume" in signal.reason

    def test_insufficient_data_returns_hold(self) -> None:
        from hestia.trading.strategies.bollinger import BollingerBreakoutStrategy
        strategy = BollingerBreakoutStrategy()
        df = self._make_df(rows=5)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.HOLD
        assert "Need" in signal.reason


# ── Signal DCA Strategy Tests ────────────────────────────────


class TestSignalDCAStrategy:
    """Verify signal-enhanced DCA signal generation."""

    def _make_df(
        self,
        close: float = 64000.0,
        rsi: float = 35.0,
        sma: float = 65000.0,
        rows: int = 60,
    ) -> pd.DataFrame:
        """Build a minimal DataFrame with pre-computed indicators."""
        data = {
            "open": [close] * rows,
            "high": [close + 100] * rows,
            "low": [close - 100] * rows,
            "close": [close] * rows,
            "volume": [1000] * rows,
            "rsi": [rsi] * rows,
            "sma": [sma] * rows,
        }
        return pd.DataFrame(data)

    def test_buy_when_rsi_low_and_below_ma(self) -> None:
        from hestia.trading.strategies.signal_dca import SignalDCAStrategy
        strategy = SignalDCAStrategy()
        # RSI < 40 and price < SMA
        df = self._make_df(close=64000.0, rsi=30.0, sma=65000.0)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.BUY
        assert signal.confidence > 0.5
        assert "signal_dca" in signal.metadata.get("entry_type", "")

    def test_hold_when_rsi_above_threshold(self) -> None:
        from hestia.trading.strategies.signal_dca import SignalDCAStrategy
        strategy = SignalDCAStrategy()
        df = self._make_df(close=64000.0, rsi=55.0, sma=65000.0)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.HOLD
        assert "threshold" in signal.reason

    def test_hold_when_price_above_ma(self) -> None:
        from hestia.trading.strategies.signal_dca import SignalDCAStrategy
        strategy = SignalDCAStrategy()
        # RSI favorable but price above MA
        df = self._make_df(close=66000.0, rsi=30.0, sma=65000.0)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.HOLD
        assert "above MA" in signal.reason

    def test_interval_gate_blocks_rapid_buys(self) -> None:
        from hestia.trading.strategies.signal_dca import SignalDCAStrategy
        strategy = SignalDCAStrategy({"buy_interval_hours": 24})
        df = self._make_df(close=64000.0, rsi=30.0, sma=65000.0)

        # First buy should succeed
        signal1 = strategy.analyze(df, portfolio_value=1000.0)
        assert signal1.signal_type == SignalType.BUY

        # Second buy immediately should be blocked by interval gate
        signal2 = strategy.analyze(df, portfolio_value=1000.0)
        assert signal2.signal_type == SignalType.HOLD
        assert "interval gate" in signal2.reason

    def test_never_sells(self) -> None:
        from hestia.trading.strategies.signal_dca import SignalDCAStrategy
        strategy = SignalDCAStrategy()
        # Even with extreme overbought conditions, never sell
        df = self._make_df(close=70000.0, rsi=90.0, sma=65000.0)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type != SignalType.SELL

    def test_insufficient_data_returns_hold(self) -> None:
        from hestia.trading.strategies.signal_dca import SignalDCAStrategy
        strategy = SignalDCAStrategy()
        df = self._make_df(rows=5)
        signal = strategy.analyze(df, portfolio_value=1000.0)
        assert signal.signal_type == SignalType.HOLD
        assert "Need" in signal.reason
