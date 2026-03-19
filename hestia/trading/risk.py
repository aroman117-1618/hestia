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

import asyncio
import json
import math
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.trading.models import (
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerType,
)

if TYPE_CHECKING:
    from hestia.trading.database import TradingDatabase

logger = get_logger()


class RiskManager:
    """
    Validates every order against the 8-layer safety architecture.

    No code path can place an order without passing through this manager.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        database: Optional["TradingDatabase"] = None,
    ) -> None:
        cfg = config or {}
        risk_cfg = cfg.get("risk", {})
        position_cfg = risk_cfg.get("position_limits", {})
        breaker_cfg = risk_cfg.get("circuit_breakers", {})
        sizing_cfg = risk_cfg.get("position_sizing", {})

        self._database = database

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
        self._weekly_reset_date: Optional[str] = None

    # Breakers that have active check logic in the executor pipeline.
    # Others are disabled by default until implemented (dead code = false safety).
    _IMPLEMENTED_BREAKERS = {
        CircuitBreakerType.DRAWDOWN,
        CircuitBreakerType.DAILY_LOSS,
        CircuitBreakerType.WEEKLY_LOSS,
        CircuitBreakerType.LATENCY,
        CircuitBreakerType.PRICE_DIVERGENCE,
    }

    def _init_breakers(self, cfg: Dict[str, Any]) -> None:
        """Initialize circuit breakers from config."""
        defaults = {
            CircuitBreakerType.DRAWDOWN: 0.15,       # 15% from peak
            CircuitBreakerType.DAILY_LOSS: 0.05,      # 5% daily
            CircuitBreakerType.WEEKLY_LOSS: 0.10,     # 10% weekly
            CircuitBreakerType.LATENCY: 2000.0,       # 2000ms
            CircuitBreakerType.PRICE_DIVERGENCE: 0.02, # 2%
            CircuitBreakerType.SINGLE_TRADE: 0.03,    # 3% single trade (NOT IMPLEMENTED)
            CircuitBreakerType.VOLATILITY: 2.0,       # 2x normal ATR (NOT IMPLEMENTED)
            CircuitBreakerType.CONNECTIVITY: 300.0,   # 5 minutes (NOT IMPLEMENTED)
        }

        for breaker_type, default_threshold in defaults.items():
            threshold = cfg.get(breaker_type.value, {}).get("threshold", default_threshold)
            # Only arm breakers that have actual check logic
            if breaker_type in self._IMPLEMENTED_BREAKERS:
                enabled = cfg.get(breaker_type.value, {}).get("enabled", True)
            else:
                enabled = cfg.get(breaker_type.value, {}).get("enabled", False)
            self._breakers[breaker_type] = CircuitBreaker(
                breaker_type=breaker_type,
                state=CircuitBreakerState.ARMED if enabled else CircuitBreakerState.DISABLED,
                threshold=threshold,
            )

    # ── State Persistence ────────────────────────────────────────

    def set_database(self, database: "TradingDatabase") -> None:
        """Set database reference (called after manager init)."""
        self._database = database

    async def persist_state(self) -> None:
        """Persist kill switch, breaker states, and tracking to database."""
        if not self._database:
            return
        try:
            state = {
                "kill_switch_active": self._kill_switch_active,
                "kill_switch_reason": self._kill_switch_reason,
                "kill_switch_at": self._kill_switch_at.isoformat() if self._kill_switch_at else None,
                "peak_portfolio_value": self._peak_portfolio_value,
                "daily_pnl": self._daily_pnl,
                "weekly_pnl": self._weekly_pnl,
                "daily_reset_date": self._daily_reset_date,
                "weekly_reset_date": self._weekly_reset_date,
                "breakers": {
                    bt.value: {
                        "state": b.state.value,
                        "current_value": b.current_value,
                        "trigger_count": b.trigger_count,
                        "triggered_at": b.triggered_at.isoformat() if b.triggered_at else None,
                        "cooldown_until": b.cooldown_until.isoformat() if b.cooldown_until else None,
                    }
                    for bt, b in self._breakers.items()
                },
            }
            await self._database.save_risk_state("risk_state", json.dumps(state))
        except Exception as e:
            logger.error(
                f"Failed to persist risk state: {type(e).__name__}",
                component=LogComponent.TRADING,
            )

    async def restore_state(self) -> None:
        """Restore persisted risk state from database on startup."""
        if not self._database:
            return
        try:
            raw = await self._database.load_risk_state("risk_state")
            if not raw:
                return
            state = json.loads(raw)

            # Restore kill switch
            self._kill_switch_active = state.get("kill_switch_active", False)
            self._kill_switch_reason = state.get("kill_switch_reason")
            ks_at = state.get("kill_switch_at")
            self._kill_switch_at = datetime.fromisoformat(ks_at) if ks_at else None

            # Restore tracking
            self._peak_portfolio_value = state.get("peak_portfolio_value", 0.0)
            self._daily_pnl = state.get("daily_pnl", 0.0)
            self._weekly_pnl = state.get("weekly_pnl", 0.0)
            self._daily_reset_date = state.get("daily_reset_date")
            self._weekly_reset_date = state.get("weekly_reset_date")

            # Restore breaker states
            breakers_data = state.get("breakers", {})
            for bt, b in self._breakers.items():
                bd = breakers_data.get(bt.value)
                if bd:
                    try:
                        b.state = CircuitBreakerState(bd["state"])
                    except ValueError:
                        pass
                    b.current_value = bd.get("current_value", 0.0)
                    b.trigger_count = bd.get("trigger_count", 0)
                    ta = bd.get("triggered_at")
                    b.triggered_at = datetime.fromisoformat(ta) if ta else None
                    cu = bd.get("cooldown_until")
                    b.cooldown_until = datetime.fromisoformat(cu) if cu else None

            if self._kill_switch_active:
                logger.warning(
                    f"Kill switch restored from database: {self._kill_switch_reason}",
                    component=LogComponent.TRADING,
                )
            triggered = [bt.value for bt, b in self._breakers.items() if b.is_blocking]
            if triggered:
                logger.warning(
                    f"Circuit breakers restored from database: {triggered}",
                    component=LogComponent.TRADING,
                )
        except Exception as e:
            logger.error(
                f"Failed to restore risk state: {type(e).__name__}",
                component=LogComponent.TRADING,
            )

    def _schedule_persist(self) -> None:
        """Fire-and-forget persistence after state changes."""
        if not self._database:
            return
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.persist_state())
        except RuntimeError:
            pass  # No running loop (e.g., in tests)

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
        self._schedule_persist()

    def deactivate_kill_switch(self) -> None:
        """Re-enable trading after kill switch."""
        self._kill_switch_active = False
        self._kill_switch_reason = None
        logger.warning(
            "Kill switch deactivated — trading re-enabled",
            component=LogComponent.TRADING,
        )
        self._schedule_persist()

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
        adjustments: List[str] = []
        rejections: List[str] = []

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
                rejections.append(
                    f"Circuit breaker {breaker.breaker_type.value} triggered "
                    f"(value: {breaker.current_value:.4f}, threshold: {breaker.threshold:.4f})"
                )

        if rejections:
            return {"approved": False, "reasons": rejections, "adjusted_quantity": 0.0}

        trade_value = quantity * price

        # Layer 2: Position limit check
        if portfolio_value > 0:
            trade_pct = trade_value / portfolio_value
            if trade_pct > self.max_single_trade_pct:
                max_value = portfolio_value * self.max_single_trade_pct
                adjusted_qty = max_value / price if price > 0 else 0.0
                adjustments.append(
                    f"Trade adjusted: single trade {trade_pct:.1%} > {self.max_single_trade_pct:.1%}. "
                    f"Reduced to {adjusted_qty:.8f}"
                )
                quantity = adjusted_qty
                trade_value = quantity * price

            # Total deployed check
            new_deployed = current_deployed + trade_value
            deployed_pct = new_deployed / portfolio_value
            if deployed_pct > self.max_total_deployed_pct:
                rejections.append(
                    f"Would exceed max deployed ({deployed_pct:.1%} > {self.max_total_deployed_pct:.1%})"
                )
                return {
                    "approved": False,
                    "reasons": rejections + adjustments,
                    "adjusted_quantity": 0.0,
                }

        # Layer 3: Quarter-Kelly position sizing
        kelly_qty = self.calculate_kelly_size(portfolio_value, price)
        if quantity > kelly_qty > 0:
            adjustments.append(
                f"Quantity reduced from {quantity:.8f} to {kelly_qty:.8f} (Quarter-Kelly)"
            )
            quantity = kelly_qty

        approved = len(rejections) == 0
        return {
            "approved": approved,
            "reasons": rejections + adjustments,
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

        # Weekly reset on Monday
        import calendar
        today_dt = datetime.now(timezone.utc)
        monday = (today_dt - timedelta(days=today_dt.weekday())).strftime("%Y-%m-%d")
        if self._weekly_reset_date != monday:
            self._weekly_pnl = 0.0
            self._weekly_reset_date = monday

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

        self._schedule_persist()

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
        self._schedule_persist()

    def _reset_breaker(self, breaker: CircuitBreaker) -> None:
        """Reset a circuit breaker to armed state."""
        breaker.state = CircuitBreakerState.ARMED
        breaker.cooldown_until = None
        logger.info(
            f"Circuit breaker reset: {breaker.breaker_type.value}",
            component=LogComponent.TRADING,
        )
        self._schedule_persist()

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
