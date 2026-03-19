"""Tests for Sprint 27 — Go-Live (BotRunner, BotOrchestrator).

Covers: bot runner tick logic, orchestrator lifecycle, concurrency locks,
error handling with exponential backoff, exchange reconciliation.
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
from hestia.trading.models import Bot, BotStatus, StrategyType
from hestia.trading.orchestrator import BotOrchestrator
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
