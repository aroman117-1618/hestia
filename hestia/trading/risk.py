"""
Risk management framework — 8-layer safety architecture.

Layer 1: API key scoping (enforced at Coinbase console level)
Layer 2: Position limits (max % per trade, max total deployed)
Layer 3: Quarter-Kelly position sizing
Layer 4: Drawdown circuit breaker
Layer 5: Daily loss limit
Layer 6: Latency circuit breaker
Layer 7: Price divergence check
Layer 8: Reconciliation loop (in manager.py)

Plus: kill switch for immediate halt of all trading.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.trading.models import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerType,
)

logger = get_logger()


class RiskManager:
    """
    Validates every order against the 8-layer safety architecture.

    No code path can place an order without passing through this manager.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = config or {}
        risk_cfg = cfg.get("risk", {})
        position_cfg = risk_cfg.get("position_limits", {})
        breaker_cfg = risk_cfg.get("circuit_breakers", {})
        sizing_cfg = risk_cfg.get("position_sizing", {})

        # Layer 2: Position limits
        self.max_single_trade_pct: float = position_cfg.get("max_single_trade_pct", 0.25)
        self.max_total_deployed_pct: float = position_cfg.get("max_total_deployed_pct", 0.80)
        self.max_correlated_pct: float = position_cfg.get("max_correlated_pct", 0.50)

        # Layer 3: Quarter-Kelly sizing
        self.kelly_fraction: float = sizing_cfg.get("kelly_fraction", 0.25)
        self.default_win_rate: float = sizing_cfg.get("default_win_rate", 0.50)
        self.default_win_loss_ratio: float = sizing_cfg.get("default_win_loss_ratio", 1.5)

        # Kill switch
        self._kill_switch_active = False
        self._kill_switch_reason: Optional[str] = None
        self._kill_switch_at: Optional[datetime] = None

        # Circuit breakers (Layers 4-7 + extended)
        self._breakers: Dict[CircuitBreakerType, CircuitBreaker] = {}
        self._init_breakers(breaker_cfg)

        # Tracking state
        self._peak_portfolio_value: float = 0.0
        self._daily_pnl: float = 0.0
        self._weekly_pnl: float = 0.0
        self._daily_reset_date: Optional[str] = None

    def _init_breakers(self, cfg: Dict[str, Any]) -> None:
        """Initialize circuit breakers from config."""
        defaults = {
            CircuitBreakerType.DRAWDOWN: 0.15,       # 15% from peak
            CircuitBreakerType.DAILY_LOSS: 0.05,      # 5% daily
            CircuitBreakerType.WEEKLY_LOSS: 0.10,     # 10% weekly
            CircuitBreakerType.LATENCY: 2000.0,       # 2000ms
            CircuitBreakerType.PRICE_DIVERGENCE: 0.02, # 2%
            CircuitBreakerType.SINGLE_TRADE: 0.03,    # 3% single trade
            CircuitBreakerType.VOLATILITY: 2.0,       # 2x normal ATR
            CircuitBreakerType.CONNECTIVITY: 300.0,   # 5 minutes (seconds)
        }

        for breaker_type, default_threshold in defaults.items():
            threshold = cfg.get(breaker_type.value, {}).get("threshold", default_threshold)
            enabled = cfg.get(breaker_type.value, {}).get("enabled", True)
            self._breakers[breaker_type] = CircuitBreaker(
                breaker_type=breaker_type,
                state=CircuitBreakerState.ARMED if enabled else CircuitBreakerState.DISABLED,
                threshold=threshold,
            )

    # ── Kill Switch ───────────────────────────────────────────────

    def activate_kill_switch(self, reason: str = "Manual activation") -> None:
        """Immediately halt ALL trading activity."""
        self._kill_switch_active = True
        self._kill_switch_reason = reason
        self._kill_switch_at = datetime.now(timezone.utc)
        logger.critical(
            f"KILL SWITCH ACTIVATED: {reason}",
            component=LogComponent.TRADING,
        )

    def deactivate_kill_switch(self) -> None:
        """Re-enable trading after kill switch."""
        self._kill_switch_active = False
        self._kill_switch_reason = None
        logger.warning(
            "Kill switch deactivated — trading re-enabled",
            component=LogComponent.TRADING,
        )

    @property
    def is_kill_switch_active(self) -> bool:
        return self._kill_switch_active

    # ── Order Validation (main entry point) ───────────────────────

    def validate_order(
        self,
        side: str,
        quantity: float,
        price: float,
        portfolio_value: float,
        current_deployed: float,
    ) -> Dict[str, Any]:
        """
        Validate an order against all risk layers.

        Returns: {"approved": bool, "reasons": [str], "adjusted_quantity": float}
        """
        reasons: List[str] = []

        # Kill switch check
        if self._kill_switch_active:
            return {
                "approved": False,
                "reasons": [f"Kill switch active: {self._kill_switch_reason}"],
                "adjusted_quantity": 0.0,
            }

        # Check all circuit breakers
        for breaker in self._breakers.values():
            if breaker.is_blocking:
                reasons.append(
                    f"Circuit breaker {breaker.breaker_type.value} triggered "
                    f"(value: {breaker.current_value:.4f}, threshold: {breaker.threshold:.4f})"
                )

        if reasons:
            return {"approved": False, "reasons": reasons, "adjusted_quantity": 0.0}

        trade_value = quantity * price

        # Layer 2: Position limit check
        if portfolio_value > 0:
            trade_pct = trade_value / portfolio_value
            if trade_pct > self.max_single_trade_pct:
                max_value = portfolio_value * self.max_single_trade_pct
                adjusted_qty = max_value / price if price > 0 else 0.0
                reasons.append(
                    f"Trade exceeds max single trade ({trade_pct:.1%} > {self.max_single_trade_pct:.1%}). "
                    f"Adjusted to {adjusted_qty:.8f}"
                )
                quantity = adjusted_qty
                trade_value = quantity * price

            # Total deployed check
            new_deployed = current_deployed + trade_value
            deployed_pct = new_deployed / portfolio_value
            if deployed_pct > self.max_total_deployed_pct:
                reasons.append(
                    f"Would exceed max deployed ({deployed_pct:.1%} > {self.max_total_deployed_pct:.1%})"
                )
                return {"approved": False, "reasons": reasons, "adjusted_quantity": 0.0}

        # Layer 3: Quarter-Kelly position sizing
        kelly_qty = self.calculate_kelly_size(portfolio_value, price)
        if quantity > kelly_qty > 0:
            reasons.append(
                f"Quantity reduced from {quantity:.8f} to {kelly_qty:.8f} (Quarter-Kelly)"
            )
            quantity = kelly_qty

        approved = len([r for r in reasons if "exceeds" in r.lower() or "would exceed" in r.lower()]) == 0
        return {
            "approved": approved,
            "reasons": reasons,
            "adjusted_quantity": quantity,
        }

    # ── Layer 3: Quarter-Kelly Position Sizing ────────────────────

    def calculate_kelly_size(
        self,
        portfolio_value: float,
        price: float,
        win_rate: Optional[float] = None,
        win_loss_ratio: Optional[float] = None,
    ) -> float:
        """
        Calculate position size using Quarter-Kelly criterion.

        Kelly% = W - (1-W)/R where W=win_rate, R=avg_win/avg_loss
        Quarter-Kelly = Kelly% * 0.25 (conservative during parameter estimation)
        """
        w = win_rate or self.default_win_rate
        r = win_loss_ratio or self.default_win_loss_ratio

        if r <= 0 or w < 0.01 or w >= 1:
            return 0.0

        kelly_pct = w - ((1 - w) / r)
        if kelly_pct <= 0:
            return 0.0

        # Apply fraction (quarter-Kelly for months 1-3)
        adjusted_pct = kelly_pct * self.kelly_fraction
        position_value = portfolio_value * adjusted_pct

        if price <= 0:
            return 0.0
        return position_value / price

    # ── Layer 4: Drawdown Circuit Breaker ─────────────────────────

    def update_portfolio_value(self, current_value: float) -> None:
        """Track portfolio value for drawdown calculation."""
        if current_value > self._peak_portfolio_value:
            self._peak_portfolio_value = current_value

        if self._peak_portfolio_value > 0:
            drawdown = (self._peak_portfolio_value - current_value) / self._peak_portfolio_value
            breaker = self._breakers[CircuitBreakerType.DRAWDOWN]
            breaker.current_value = drawdown

            if drawdown >= breaker.threshold and breaker.state == CircuitBreakerState.ARMED:
                self._trigger_breaker(breaker, f"Drawdown {drawdown:.1%} exceeds {breaker.threshold:.1%}")

    # ── Layer 5: Daily Loss Limit ─────────────────────────────────

    def record_trade_pnl(self, pnl: float, portfolio_value: float) -> None:
        """Record trade P&L for daily/weekly loss tracking."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._daily_reset_date != today:
            self._daily_pnl = 0.0
            self._daily_reset_date = today

        self._daily_pnl += pnl
        self._weekly_pnl += pnl

        if portfolio_value > 0:
            # Daily loss check
            daily_loss_pct = abs(self._daily_pnl) / portfolio_value if self._daily_pnl < 0 else 0.0
            breaker = self._breakers[CircuitBreakerType.DAILY_LOSS]
            breaker.current_value = daily_loss_pct
            if daily_loss_pct >= breaker.threshold and breaker.state == CircuitBreakerState.ARMED:
                self._trigger_breaker(
                    breaker,
                    f"Daily loss {daily_loss_pct:.1%} exceeds {breaker.threshold:.1%}",
                    cooldown_hours=24,
                )

            # Weekly loss check
            weekly_loss_pct = abs(self._weekly_pnl) / portfolio_value if self._weekly_pnl < 0 else 0.0
            breaker = self._breakers[CircuitBreakerType.WEEKLY_LOSS]
            breaker.current_value = weekly_loss_pct
            if weekly_loss_pct >= breaker.threshold and breaker.state == CircuitBreakerState.ARMED:
                self._trigger_breaker(
                    breaker,
                    f"Weekly loss {weekly_loss_pct:.1%} exceeds {breaker.threshold:.1%}",
                    cooldown_hours=72,
                )

    # ── Layer 6: Latency Circuit Breaker ──────────────────────────

    def record_api_latency(self, latency_ms: float) -> None:
        """Check API latency against threshold."""
        breaker = self._breakers[CircuitBreakerType.LATENCY]
        breaker.current_value = latency_ms
        if latency_ms >= breaker.threshold and breaker.state == CircuitBreakerState.ARMED:
            self._trigger_breaker(
                breaker,
                f"API latency {latency_ms:.0f}ms exceeds {breaker.threshold:.0f}ms",
            )

    def record_latency_recovery(self, latency_ms: float) -> None:
        """Check if latency has recovered below threshold for 60s."""
        breaker = self._breakers[CircuitBreakerType.LATENCY]
        if breaker.state == CircuitBreakerState.TRIGGERED and latency_ms < 500:
            self._reset_breaker(breaker)

    # ── Layer 7: Price Divergence ─────────────────────────────────

    def check_price_divergence(
        self, primary_price: float, secondary_price: float
    ) -> bool:
        """
        Check if prices from two feeds diverge beyond threshold.

        Returns True if safe (no divergence), False if divergent.
        """
        if primary_price <= 0 or secondary_price <= 0:
            return False

        divergence = abs(primary_price - secondary_price) / primary_price
        breaker = self._breakers[CircuitBreakerType.PRICE_DIVERGENCE]
        breaker.current_value = divergence

        if divergence >= breaker.threshold and breaker.state == CircuitBreakerState.ARMED:
            self._trigger_breaker(
                breaker,
                f"Price divergence {divergence:.2%} exceeds {breaker.threshold:.2%} "
                f"(primary: {primary_price:.2f}, secondary: {secondary_price:.2f})",
            )
            return False
        return True

    # ── Circuit Breaker Internals ─────────────────────────────────

    def _trigger_breaker(
        self,
        breaker: CircuitBreaker,
        reason: str,
        cooldown_hours: Optional[int] = None,
    ) -> None:
        """Trigger a circuit breaker."""
        breaker.state = CircuitBreakerState.TRIGGERED
        breaker.triggered_at = datetime.now(timezone.utc)
        breaker.trigger_count += 1
        if cooldown_hours:
            breaker.cooldown_until = breaker.triggered_at + timedelta(hours=cooldown_hours)

        logger.warning(
            f"Circuit breaker TRIGGERED: {breaker.breaker_type.value} — {reason}",
            component=LogComponent.TRADING,
            data=breaker.to_dict(),
        )

    def _reset_breaker(self, breaker: CircuitBreaker) -> None:
        """Reset a circuit breaker to armed state."""
        breaker.state = CircuitBreakerState.ARMED
        breaker.cooldown_until = None
        logger.info(
            f"Circuit breaker reset: {breaker.breaker_type.value}",
            component=LogComponent.TRADING,
        )

    def check_cooldowns(self) -> None:
        """Check and reset any expired cooldowns."""
        now = datetime.now(timezone.utc)
        for breaker in self._breakers.values():
            if (
                breaker.state == CircuitBreakerState.TRIGGERED
                and breaker.cooldown_until
                and now >= breaker.cooldown_until
            ):
                self._reset_breaker(breaker)

    def reset_breaker(self, breaker_type: CircuitBreakerType) -> bool:
        """Manually reset a specific circuit breaker."""
        breaker = self._breakers.get(breaker_type)
        if breaker and breaker.state in (CircuitBreakerState.TRIGGERED, CircuitBreakerState.COOLDOWN):
            self._reset_breaker(breaker)
            return True
        return False

    # ── Status ────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Get full risk manager status."""
        return {
            "kill_switch": {
                "active": self._kill_switch_active,
                "reason": self._kill_switch_reason,
                "activated_at": self._kill_switch_at.isoformat() if self._kill_switch_at else None,
            },
            "circuit_breakers": {
                bt.value: b.to_dict() for bt, b in self._breakers.items()
            },
            "position_limits": {
                "max_single_trade_pct": self.max_single_trade_pct,
                "max_total_deployed_pct": self.max_total_deployed_pct,
                "max_correlated_pct": self.max_correlated_pct,
            },
            "sizing": {
                "kelly_fraction": self.kelly_fraction,
                "win_rate": self.default_win_rate,
                "win_loss_ratio": self.default_win_loss_ratio,
            },
            "tracking": {
                "peak_portfolio_value": self._peak_portfolio_value,
                "daily_pnl": self._daily_pnl,
                "weekly_pnl": self._weekly_pnl,
            },
            "any_breaker_active": any(b.is_blocking for b in self._breakers.values()),
        }

    def get_breaker(self, breaker_type: CircuitBreakerType) -> Optional[CircuitBreaker]:
        """Get a specific circuit breaker."""
        return self._breakers.get(breaker_type)
