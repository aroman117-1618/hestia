"""Tests for trading module models and tax lot math."""

import pytest
from datetime import datetime, timedelta, timezone

from hestia.trading.models import (
    Bot,
    BotStatus,
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerType,
    DailySummary,
    OrderType,
    ReconciliationResult,
    StrategyType,
    TaxLot,
    TaxLotMethod,
    TaxLotStatus,
    Trade,
    TradeSide,
)


class TestBot:
    def test_create_default(self):
        bot = Bot()
        assert bot.strategy == StrategyType.GRID
        assert bot.pair == "BTC-USD"
        assert bot.status == BotStatus.CREATED
        assert bot.capital_allocated == 0.0
        assert bot.id  # UUID generated

    def test_create_with_params(self):
        bot = Bot(
            name="Test Grid Bot",
            strategy=StrategyType.GRID,
            pair="ETH-USD",
            capital_allocated=87.50,
            config={"num_levels": 10},
        )
        assert bot.name == "Test Grid Bot"
        assert bot.pair == "ETH-USD"
        assert bot.capital_allocated == 87.50
        assert bot.config["num_levels"] == 10

    def test_to_dict_roundtrip(self):
        bot = Bot(
            name="Roundtrip Bot",
            strategy=StrategyType.MEAN_REVERSION,
            capital_allocated=50.0,
        )
        d = bot.to_dict()
        assert d["strategy"] == "mean_reversion"
        assert d["capital_allocated"] == 50.0

        restored = Bot.from_dict(d)
        assert restored.name == "Roundtrip Bot"
        assert restored.strategy == StrategyType.MEAN_REVERSION
        assert restored.id == bot.id

    def test_from_dict_defaults(self):
        bot = Bot.from_dict({"name": "Minimal"})
        assert bot.strategy == StrategyType.GRID
        assert bot.status == BotStatus.CREATED

    def test_all_strategies(self):
        for st in StrategyType:
            bot = Bot(strategy=st)
            assert bot.strategy == st
            assert bot.to_dict()["strategy"] == st.value


class TestTrade:
    def test_total_cost(self):
        trade = Trade(price=65000.0, quantity=0.001, fee=0.26)
        assert trade.total_cost == pytest.approx(65.26, abs=0.01)

    def test_net_value(self):
        trade = Trade(side=TradeSide.SELL, price=65000.0, quantity=0.001, fee=0.26)
        assert trade.net_value == pytest.approx(64.74, abs=0.01)

    def test_to_dict_roundtrip(self):
        trade = Trade(
            bot_id="bot-123",
            side=TradeSide.BUY,
            price=65000.0,
            quantity=0.001,
            fee=0.26,
            pair="BTC-USD",
        )
        d = trade.to_dict()
        restored = Trade.from_dict(d)
        assert restored.side == TradeSide.BUY
        assert restored.price == 65000.0
        assert restored.bot_id == "bot-123"

    def test_order_types(self):
        for ot in OrderType:
            trade = Trade(order_type=ot)
            assert trade.order_type == ot


class TestTaxLot:
    def test_create_from_buy(self):
        lot = TaxLot(
            quantity=0.001,
            remaining_quantity=0.001,
            cost_basis=65.26,  # price * qty + fee
            cost_per_unit=65260.0,
        )
        assert lot.status == TaxLotStatus.OPEN
        assert lot.method == TaxLotMethod.HIFO
        assert lot.remaining_quantity == 0.001

    def test_is_long_term_false(self):
        lot = TaxLot(acquired_at=datetime.now(timezone.utc) - timedelta(days=30))
        assert lot.is_long_term is False

    def test_is_long_term_true(self):
        lot = TaxLot(
            acquired_at=datetime.now(timezone.utc) - timedelta(days=400),
            closed_at=datetime.now(timezone.utc),
        )
        assert lot.is_long_term is True

    def test_is_long_term_exactly_365(self):
        lot = TaxLot(
            acquired_at=datetime.now(timezone.utc) - timedelta(days=365),
        )
        # 365 days is NOT > 365, so should be False
        assert lot.is_long_term is False

    def test_is_long_term_366(self):
        lot = TaxLot(
            acquired_at=datetime.now(timezone.utc) - timedelta(days=366),
        )
        assert lot.is_long_term is True

    def test_to_dict_roundtrip(self):
        lot = TaxLot(
            quantity=0.5,
            remaining_quantity=0.3,
            cost_basis=32500.0,
            cost_per_unit=65000.0,
            method=TaxLotMethod.FIFO,
            status=TaxLotStatus.PARTIAL,
            realized_pnl=150.0,
        )
        d = lot.to_dict()
        restored = TaxLot.from_dict(d)
        assert restored.method == TaxLotMethod.FIFO
        assert restored.status == TaxLotStatus.PARTIAL
        assert restored.realized_pnl == 150.0

    def test_hifo_vs_fifo_method(self):
        hifo = TaxLot(method=TaxLotMethod.HIFO)
        fifo = TaxLot(method=TaxLotMethod.FIFO)
        assert hifo.method.value == "hifo"
        assert fifo.method.value == "fifo"


class TestDailySummary:
    def test_win_rate_calculation(self):
        summary = DailySummary(
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
        )
        assert summary.win_rate == pytest.approx(0.6)

    def test_win_rate_zero_trades(self):
        summary = DailySummary(total_trades=0)
        assert summary.win_rate == 0.0

    def test_to_dict_includes_win_rate(self):
        summary = DailySummary(
            date="2026-03-18",
            total_trades=5,
            winning_trades=3,
            total_pnl=25.50,
        )
        d = summary.to_dict()
        assert d["win_rate"] == pytest.approx(0.6)
        assert d["date"] == "2026-03-18"
        assert d["total_pnl"] == 25.50

    def test_strategy_attribution(self):
        summary = DailySummary(
            strategy_attribution={"grid": 15.0, "mean_reversion": 10.50},
        )
        d = summary.to_dict()
        assert d["strategy_attribution"]["grid"] == 15.0


class TestCircuitBreaker:
    def test_armed_not_blocking(self):
        cb = CircuitBreaker(state=CircuitBreakerState.ARMED)
        assert cb.is_blocking is False

    def test_triggered_is_blocking(self):
        cb = CircuitBreaker(state=CircuitBreakerState.TRIGGERED)
        assert cb.is_blocking is True

    def test_cooldown_is_blocking(self):
        cb = CircuitBreaker(state=CircuitBreakerState.COOLDOWN)
        assert cb.is_blocking is True

    def test_disabled_not_blocking(self):
        cb = CircuitBreaker(state=CircuitBreakerState.DISABLED)
        assert cb.is_blocking is False

    def test_to_dict(self):
        cb = CircuitBreaker(
            breaker_type=CircuitBreakerType.DRAWDOWN,
            threshold=0.15,
            current_value=0.10,
        )
        d = cb.to_dict()
        assert d["breaker_type"] == "drawdown"
        assert d["threshold"] == 0.15
        assert d["is_blocking"] is False

    def test_all_breaker_types(self):
        for bt in CircuitBreakerType:
            cb = CircuitBreaker(breaker_type=bt)
            assert cb.breaker_type == bt


class TestReconciliationResult:
    def test_no_discrepancy(self):
        r = ReconciliationResult(
            local_balance=1.0,
            exchange_balance=1.0,
            discrepancy=0.0,
        )
        assert r.has_discrepancy is False

    def test_has_discrepancy(self):
        r = ReconciliationResult(
            local_balance=1.0,
            exchange_balance=0.999,
            discrepancy=0.001,
        )
        assert r.has_discrepancy is True

    def test_to_dict(self):
        r = ReconciliationResult(pair="ETH-USD")
        d = r.to_dict()
        assert d["pair"] == "ETH-USD"
        assert "has_discrepancy" in d
