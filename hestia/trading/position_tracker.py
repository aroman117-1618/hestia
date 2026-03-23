"""
Position tracker — real-time exposure, unrealized P&L, and reconciliation.

Maintains local position state and periodically reconciles against
exchange balances (60-second loop) to catch phantom fills, missed
orders, and state drift from API glitches.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.trading.event_bus import TradingEvent, TradingEventBus
from hestia.trading.exchange.base import AbstractExchangeAdapter
from hestia.trading.models import ReconciliationResult

logger = get_logger()

# Callback type for kill switch activation
from typing import Callable
KillSwitchCallback = Optional[Callable[[str], None]]


class Position:
    """Tracks a single position in a trading pair."""

    def __init__(self, pair: str = "BTC-USD") -> None:
        self.pair = pair
        self.quantity: float = 0.0
        self.avg_entry_price: float = 0.0
        self.total_cost: float = 0.0
        self.realized_pnl: float = 0.0

    def add(self, quantity: float, price: float, fee: float = 0.0) -> None:
        """Add to position (buy)."""
        cost = quantity * price + fee
        new_total_qty = self.quantity + quantity
        if new_total_qty > 0:
            self.avg_entry_price = (self.total_cost + cost) / new_total_qty
        self.total_cost += cost
        self.quantity = new_total_qty

    def reduce(self, quantity: float, price: float, fee: float = 0.0) -> float:
        """
        Reduce position (sell). Returns realized P&L for this sale.
        """
        if quantity > self.quantity:
            quantity = self.quantity

        proceeds = quantity * price - fee
        cost_basis = quantity * self.avg_entry_price
        pnl = proceeds - cost_basis
        self.realized_pnl += pnl

        self.quantity -= quantity
        self.total_cost = self.quantity * self.avg_entry_price
        if self.quantity < 1e-10:
            self.quantity = 0.0
            self.total_cost = 0.0
            self.avg_entry_price = 0.0

        return pnl

    def unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized P&L at current price."""
        if self.quantity <= 0:
            return 0.0
        market_value = self.quantity * current_price
        return market_value - self.total_cost

    @property
    def market_value(self) -> float:
        """Current market value (needs current price — uses avg_entry as fallback)."""
        return self.quantity * self.avg_entry_price

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pair": self.pair,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "total_cost": self.total_cost,
            "realized_pnl": self.realized_pnl,
        }


class PositionTracker:
    """
    Tracks positions across all pairs and reconciles with exchange.

    The reconciliation loop runs every 60 seconds (configurable) and
    compares local position state with actual exchange balances. Any
    discrepancy is logged and optionally triggers the risk manager.
    """

    def __init__(
        self,
        exchange: Optional[AbstractExchangeAdapter] = None,
        reconciliation_interval: int = 60,
        max_acceptable_discrepancy: float = 0.001,
        kill_switch_callback: KillSwitchCallback = None,
        event_bus: Optional[TradingEventBus] = None,
    ) -> None:
        self._exchange = exchange
        self._positions: Dict[str, Position] = {}
        self._positions_lock = asyncio.Lock()
        self._reconciliation_interval = reconciliation_interval
        self._max_discrepancy = max_acceptable_discrepancy
        self._kill_switch_callback = kill_switch_callback
        self._event_bus = event_bus
        self._reconciliation_task: Optional[asyncio.Task] = None
        self._running = False
        self._reconciliation_results: List[ReconciliationResult] = []

    async def record_fill(
        self, pair: str, side: str, quantity: float, price: float, fee: float = 0.0
    ) -> float:
        """
        Record a fill and update position. Returns realized P&L (0 for buys).
        """
        async with self._positions_lock:
            if pair not in self._positions:
                self._positions[pair] = Position(pair)

            pos = self._positions[pair]
            if side == "buy":
                pos.add(quantity, price, fee)
                return 0.0
            else:
                return pos.reduce(quantity, price, fee)

    def get_position(self, pair: str) -> Optional[Position]:
        """Get position for a pair."""
        return self._positions.get(pair)

    def get_all_positions(self) -> Dict[str, Position]:
        """Get all open positions."""
        return {k: v for k, v in self._positions.items() if v.quantity > 0}

    def get_total_exposure(self) -> float:
        """Get total deployed capital (sum of all position costs)."""
        return sum(p.total_cost for p in self._positions.values() if p.quantity > 0)

    def get_total_unrealized_pnl(self, prices: Dict[str, float]) -> float:
        """Calculate total unrealized P&L across all positions."""
        total = 0.0
        for pair, pos in self._positions.items():
            if pos.quantity > 0 and pair in prices:
                total += pos.unrealized_pnl(prices[pair])
        return total

    def get_portfolio_summary(self, prices: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Get full portfolio summary."""
        prices = prices or {}
        positions = {}
        total_cost = 0.0
        total_unrealized = 0.0
        total_realized = 0.0

        for pair, pos in self._positions.items():
            if pos.quantity > 0:
                current_price = prices.get(pair, pos.avg_entry_price)
                unrealized = pos.unrealized_pnl(current_price)
                positions[pair] = {
                    **pos.to_dict(),
                    "current_price": current_price,
                    "unrealized_pnl": unrealized,
                    "market_value": pos.quantity * current_price,
                }
                total_cost += pos.total_cost
                total_unrealized += unrealized
            total_realized += pos.realized_pnl

        return {
            "positions": positions,
            "total_cost": total_cost,
            "total_unrealized_pnl": total_unrealized,
            "total_realized_pnl": total_realized,
            "total_pnl": total_unrealized + total_realized,
            "position_count": len(positions),
        }

    # ── Reconciliation ────────────────────────────────────────

    async def reconcile(self) -> List[ReconciliationResult]:
        """
        Compare local positions with exchange balances.

        Returns list of discrepancies found.
        """
        if not self._exchange or not self._exchange.is_connected:
            return []

        results = []
        has_critical_divergence = False
        try:
            balances = await self._exchange.get_balances()

            async with self._positions_lock:
                for pair, pos in self._positions.items():
                    asset = pair.split("-")[0]  # "BTC" from "BTC-USD"
                    exchange_balance = balances.get(asset)
                    exchange_qty = exchange_balance.available + exchange_balance.hold if exchange_balance else 0.0

                    discrepancy = abs(pos.quantity - exchange_qty)
                    result = ReconciliationResult(
                        local_balance=pos.quantity,
                        exchange_balance=exchange_qty,
                        discrepancy=discrepancy,
                        pair=pair,
                        resolved=discrepancy <= self._max_discrepancy,
                        notes="" if discrepancy <= self._max_discrepancy
                        else f"Discrepancy: local={pos.quantity:.8f}, exchange={exchange_qty:.8f}",
                    )
                    results.append(result)

                    if result.has_discrepancy and discrepancy > self._max_discrepancy:
                        logger.warning(
                            f"Position discrepancy detected: {pair} "
                            f"local={pos.quantity:.8f} exchange={exchange_qty:.8f}",
                            component=LogComponent.TRADING,
                            data=result.to_dict(),
                        )
                        has_critical_divergence = True

                # Check for positions on exchange not tracked locally
                # Skip stablecoins and dust balances (< $1 value) to avoid
                # false kill-switch triggers from pre-existing account dust.
                _STABLECOINS = {"USDC", "USDT", "DAI", "BUSD"}
                _DUST_THRESHOLD_USD = 1.0
                for currency, balance in balances.items():
                    if currency == "USD":
                        continue
                    # Skip stablecoin dust (value ≈ quantity for stablecoins)
                    if currency in _STABLECOINS and balance.total < _DUST_THRESHOLD_USD:
                        continue
                    pair = f"{currency}-USD"
                    if pair not in self._positions and balance.total > self._max_discrepancy:
                        result = ReconciliationResult(
                            local_balance=0.0,
                            exchange_balance=balance.total,
                            discrepancy=balance.total,
                            pair=pair,
                            resolved=False,
                            notes=f"Untracked position on exchange: {balance.total:.8f} {currency}",
                        )
                        results.append(result)
                        logger.warning(
                            f"Untracked exchange position: {balance.total:.8f} {currency}",
                            component=LogComponent.TRADING,
                        )
                        has_critical_divergence = True

            # CRITICAL: Trigger kill switch on any divergence above threshold
            if has_critical_divergence:
                reason = (
                    f"Position reconciliation divergence detected: "
                    f"{sum(1 for r in results if not r.resolved)} discrepancies found"
                )
                logger.critical(
                    f"RECONCILIATION HALT: {reason}",
                    component=LogComponent.TRADING,
                )
                if self._kill_switch_callback:
                    self._kill_switch_callback(reason)
                if self._event_bus:
                    self._event_bus.publish(TradingEvent(
                        event_type="kill_switch",
                        data={"reason": reason, "discrepancies": [r.to_dict() for r in results if not r.resolved]},
                        priority=True,
                    ))

        except Exception as e:
            logger.error(
                "Reconciliation failed",
                component=LogComponent.TRADING,
                data={"error": str(type(e).__name__)},
            )

        self._reconciliation_results = results
        return results

    async def start_reconciliation_loop(self) -> None:
        """Start the periodic reconciliation background task."""
        if self._running:
            return
        self._running = True
        self._reconciliation_task = asyncio.create_task(self._reconciliation_loop())
        logger.info(
            f"Reconciliation loop started (interval={self._reconciliation_interval}s)",
            component=LogComponent.TRADING,
        )

    async def stop_reconciliation_loop(self) -> None:
        """Stop the reconciliation loop."""
        self._running = False
        if self._reconciliation_task:
            self._reconciliation_task.cancel()
            try:
                await self._reconciliation_task
            except asyncio.CancelledError:
                pass
            self._reconciliation_task = None

    async def _reconciliation_loop(self) -> None:
        """Background loop that reconciles every N seconds."""
        while self._running:
            try:
                await asyncio.sleep(self._reconciliation_interval)
                await self.reconcile()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"Reconciliation loop error: {type(e).__name__}",
                    component=LogComponent.TRADING,
                )

    @property
    def last_reconciliation(self) -> List[ReconciliationResult]:
        """Get results of the most recent reconciliation."""
        return self._reconciliation_results
