"""Tests for trading risk management — circuit breakers, position sizing, kill switch."""

import pytest
from datetime import datetime, timedelta, timezone

from hestia.trading.models import CircuitBreakerState, CircuitBreakerType
from hestia.trading.risk import RiskManager


@pytest.fixture
def risk_manager():
    """Create a risk manager with default config."""
    return RiskManager()


@pytest.fixture
def configured_risk_manager():
    """Create a risk manager with explicit config."""
    return RiskManager(config={
        "risk": {
            "position_limits": {
                "max_single_trade_pct": 0.25,
                "max_total_deployed_pct": 0.80,
            },
            "position_sizing": {
                "kelly_fraction": 0.25,
                "default_win_rate": 0.55,
                "default_win_loss_ratio": 1.8,
            },
            "circuit_breakers": {
                "drawdown": {"threshold": 0.15, "enabled": True},
                "daily_loss": {"threshold": 0.05, "enabled": True},
                "latency": {"threshold": 2000, "enabled": True},
                "price_divergence": {"threshold": 0.02, "enabled": True},
            },
        }
    })


# ── Kill Switch ───────────────────────────────────────────────

class TestKillSwitch:
    def test_not_active_by_default(self, risk_manager):
        assert risk_manager.is_kill_switch_active is False

    def test_activate(self, risk_manager):
        risk_manager.activate_kill_switch("Emergency")
        assert risk_manager.is_kill_switch_active is True

    def test_deactivate(self, risk_manager):
        risk_manager.activate_kill_switch("Test")
        risk_manager.deactivate_kill_switch()
        assert risk_manager.is_kill_switch_active is False

    def test_blocks_all_orders(self, risk_manager):
        risk_manager.activate_kill_switch("Test halt")
        result = risk_manager.validate_order(
            side="buy",
            quantity=0.001,
            price=65000.0,
            portfolio_value=250.0,
            current_deployed=0.0,
        )
        assert result["approved"] is False
        assert "Kill switch" in result["reasons"][0]

    def test_status_includes_reason(self, risk_manager):
        risk_manager.activate_kill_switch("Flash crash detected")
        status = risk_manager.get_status()
        assert status["kill_switch"]["active"] is True
        assert status["kill_switch"]["reason"] == "Flash crash detected"


# ── Order Validation ──────────────────────────────────────────

class TestOrderValidation:
    def test_approve_valid_order(self, risk_manager):
        result = risk_manager.validate_order(
            side="buy",
            quantity=0.001,
            price=65000.0,
            portfolio_value=1000.0,
            current_deployed=0.0,
        )
        assert result["approved"] is True

    def test_reject_oversized_trade(self, risk_manager):
        """Trade > 25% of portfolio should be adjusted."""
        result = risk_manager.validate_order(
            side="buy",
            quantity=1.0,  # $65,000 trade on $250 portfolio
            price=65000.0,
            portfolio_value=250.0,
            current_deployed=0.0,
        )
        # Should adjust quantity down, not outright reject
        assert result["adjusted_quantity"] < 1.0
        assert any("max single trade" in r.lower() for r in result["reasons"])

    def test_reject_exceeds_max_deployed(self, risk_manager):
        """Can't deploy more than 80% of portfolio."""
        result = risk_manager.validate_order(
            side="buy",
            quantity=0.001,
            price=65000.0,
            portfolio_value=250.0,
            current_deployed=210.0,  # 84% already deployed
        )
        assert result["approved"] is False
        assert any("max deployed" in r.lower() for r in result["reasons"])


# ── Quarter-Kelly Sizing ──────────────────────────────────────

class TestKellySizing:
    def test_quarter_kelly_calculation(self, configured_risk_manager):
        """Quarter-Kelly with 55% win rate, 1.8 W/L ratio."""
        qty = configured_risk_manager.calculate_kelly_size(
            portfolio_value=250.0,
            price=65000.0,
            win_rate=0.55,
            win_loss_ratio=1.8,
        )
        # Kelly% = 0.55 - (0.45/1.8) = 0.55 - 0.25 = 0.30
        # Quarter-Kelly = 0.30 * 0.25 = 0.075
        # Position = 250 * 0.075 / 65000 = 0.000288...
        assert qty > 0
        assert qty < 250.0 / 65000.0  # Less than full portfolio

    def test_negative_kelly(self, risk_manager):
        """Negative edge should return 0 (no trade)."""
        qty = risk_manager.calculate_kelly_size(
            portfolio_value=250.0,
            price=65000.0,
            win_rate=0.30,  # Bad win rate
            win_loss_ratio=0.8,  # Bad payoff
        )
        assert qty == 0.0

    def test_zero_price(self, risk_manager):
        qty = risk_manager.calculate_kelly_size(
            portfolio_value=250.0,
            price=0.0,
        )
        assert qty == 0.0

    def test_edge_cases(self, risk_manager):
        # Win rate near 0 should return 0
        assert risk_manager.calculate_kelly_size(250.0, 65000.0, win_rate=0.005) == 0.0
        # Win rate 1 should return 0 (invalid)
        assert risk_manager.calculate_kelly_size(250.0, 65000.0, win_rate=1.0) == 0.0


# ── Drawdown Circuit Breaker ─────────────────────────────────

class TestDrawdownBreaker:
    def test_no_trigger_below_threshold(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.update_portfolio_value(1000.0)  # Set peak
        rm.update_portfolio_value(900.0)   # 10% drawdown, threshold is 15%
        breaker = rm.get_breaker(CircuitBreakerType.DRAWDOWN)
        assert breaker.state == CircuitBreakerState.ARMED

    def test_trigger_at_threshold(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.update_portfolio_value(1000.0)
        rm.update_portfolio_value(849.0)  # 15.1% drawdown
        breaker = rm.get_breaker(CircuitBreakerType.DRAWDOWN)
        assert breaker.state == CircuitBreakerState.TRIGGERED

    def test_blocks_orders_when_triggered(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.update_portfolio_value(1000.0)
        rm.update_portfolio_value(840.0)  # 16% drawdown
        result = rm.validate_order("buy", 0.001, 65000.0, 840.0, 0.0)
        assert result["approved"] is False
        assert any("drawdown" in r.lower() for r in result["reasons"])

    def test_peak_tracking(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.update_portfolio_value(1000.0)
        rm.update_portfolio_value(1100.0)  # New peak
        rm.update_portfolio_value(1000.0)  # Only 9% from new peak
        breaker = rm.get_breaker(CircuitBreakerType.DRAWDOWN)
        assert breaker.state == CircuitBreakerState.ARMED


# ── Daily Loss Breaker ────────────────────────────────────────

class TestDailyLossBreaker:
    def test_no_trigger_within_limit(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.record_trade_pnl(-10.0, 250.0)  # 4% loss
        breaker = rm.get_breaker(CircuitBreakerType.DAILY_LOSS)
        assert breaker.state == CircuitBreakerState.ARMED

    def test_trigger_exceeds_limit(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.record_trade_pnl(-13.0, 250.0)  # 5.2% loss
        breaker = rm.get_breaker(CircuitBreakerType.DAILY_LOSS)
        assert breaker.state == CircuitBreakerState.TRIGGERED

    def test_cumulative_losses(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.record_trade_pnl(-5.0, 250.0)   # 2%
        rm.record_trade_pnl(-5.0, 250.0)   # 4% cumulative
        breaker = rm.get_breaker(CircuitBreakerType.DAILY_LOSS)
        assert breaker.state == CircuitBreakerState.ARMED
        rm.record_trade_pnl(-4.0, 250.0)   # 5.6% cumulative
        breaker = rm.get_breaker(CircuitBreakerType.DAILY_LOSS)
        assert breaker.state == CircuitBreakerState.TRIGGERED


# ── Latency Breaker ──────────────────────────────────────────

class TestLatencyBreaker:
    def test_normal_latency(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.record_api_latency(200.0)  # Normal
        breaker = rm.get_breaker(CircuitBreakerType.LATENCY)
        assert breaker.state == CircuitBreakerState.ARMED

    def test_high_latency_triggers(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.record_api_latency(2500.0)
        breaker = rm.get_breaker(CircuitBreakerType.LATENCY)
        assert breaker.state == CircuitBreakerState.TRIGGERED

    def test_recovery(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.record_api_latency(2500.0)
        breaker = rm.get_breaker(CircuitBreakerType.LATENCY)
        assert breaker.state == CircuitBreakerState.TRIGGERED
        rm.record_latency_recovery(300.0)
        assert breaker.state == CircuitBreakerState.ARMED


# ── Price Divergence ─────────────────────────────────────────

class TestPriceDivergence:
    def test_no_divergence(self, configured_risk_manager):
        rm = configured_risk_manager
        safe = rm.check_price_divergence(65000.0, 64990.0)
        assert safe is True

    def test_significant_divergence(self, configured_risk_manager):
        rm = configured_risk_manager
        safe = rm.check_price_divergence(65000.0, 63000.0)  # ~3%
        assert safe is False
        breaker = rm.get_breaker(CircuitBreakerType.PRICE_DIVERGENCE)
        assert breaker.state == CircuitBreakerState.TRIGGERED

    def test_zero_price(self, configured_risk_manager):
        rm = configured_risk_manager
        safe = rm.check_price_divergence(0.0, 65000.0)
        assert safe is False


# ── Manual Reset ─────────────────────────────────────────────

class TestManualReset:
    def test_reset_triggered_breaker(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.record_api_latency(3000.0)
        assert rm.get_breaker(CircuitBreakerType.LATENCY).state == CircuitBreakerState.TRIGGERED
        rm.reset_breaker(CircuitBreakerType.LATENCY)
        assert rm.get_breaker(CircuitBreakerType.LATENCY).state == CircuitBreakerState.ARMED

    def test_reset_armed_breaker_noop(self, configured_risk_manager):
        rm = configured_risk_manager
        result = rm.reset_breaker(CircuitBreakerType.LATENCY)
        assert result is False


# ── Status ────────────────────────────────────────────────────

class TestStatus:
    def test_full_status(self, risk_manager):
        status = risk_manager.get_status()
        assert "kill_switch" in status
        assert "circuit_breakers" in status
        assert "position_limits" in status
        assert "sizing" in status
        assert "tracking" in status
        assert "any_breaker_active" in status

    def test_any_breaker_active_false(self, risk_manager):
        status = risk_manager.get_status()
        assert status["any_breaker_active"] is False

    def test_any_breaker_active_true(self, risk_manager):
        risk_manager.record_api_latency(5000.0)
        status = risk_manager.get_status()
        assert status["any_breaker_active"] is True


# ── Cooldown ─────────────────────────────────────────────────

class TestCooldown:
    def test_check_cooldowns(self, configured_risk_manager):
        rm = configured_risk_manager
        rm.record_trade_pnl(-15.0, 250.0)  # Triggers daily loss
        breaker = rm.get_breaker(CircuitBreakerType.DAILY_LOSS)
        assert breaker.state == CircuitBreakerState.TRIGGERED
        # Manually set cooldown to past
        breaker.cooldown_until = datetime.now(timezone.utc) - timedelta(hours=1)
        rm.check_cooldowns()
        assert breaker.state == CircuitBreakerState.ARMED
