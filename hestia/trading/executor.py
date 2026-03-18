"""
Trade executor — Strategy → Risk → Price Validation → Exchange pipeline.

No order can reach the exchange without passing through this pipeline.
This is the single entry point for all trade execution.
"""

from typing import Any, Dict, Optional

from hestia.logging import get_logger, LogComponent
from hestia.trading.exchange.base import AbstractExchangeAdapter, OrderRequest, OrderResult
from hestia.trading.position_tracker import PositionTracker
from hestia.trading.price_validator import PriceValidator
from hestia.trading.risk import RiskManager
from hestia.trading.strategies.base import Signal, SignalType

logger = get_logger()


class TradeExecutor:
    """
    Executes trades through the full safety pipeline.

    Pipeline: Signal → Risk Validation → Price Validation → Exchange → Position Update

    Every decision is logged with full reasoning for audit trail.
    """

    def __init__(
        self,
        exchange: AbstractExchangeAdapter,
        risk_manager: RiskManager,
        position_tracker: PositionTracker,
        price_validator: PriceValidator,
    ) -> None:
        self._exchange = exchange
        self._risk = risk_manager
        self._positions = position_tracker
        self._price_validator = price_validator
        self._execution_count = 0
        self._rejected_count = 0

    async def execute_signal(
        self,
        signal: Signal,
        portfolio_value: float,
    ) -> Dict[str, Any]:
        """
        Execute a strategy signal through the full safety pipeline.

        Returns execution result with full audit trail.
        """
        audit: Dict[str, Any] = {
            "signal": signal.to_dict(),
            "portfolio_value": portfolio_value,
            "pipeline_steps": [],
        }

        # Step 0: Check if signal is actionable
        if not signal.is_actionable:
            audit["result"] = "skipped"
            audit["reason"] = "Signal is HOLD — no action needed"
            return audit

        # Step 1: Risk validation
        current_deployed = self._positions.get_total_exposure()
        risk_result = self._risk.validate_order(
            side=signal.signal_type.value,
            quantity=signal.quantity,
            price=signal.price,
            portfolio_value=portfolio_value,
            current_deployed=current_deployed,
        )
        audit["pipeline_steps"].append({
            "step": "risk_validation",
            "result": risk_result,
        })

        if not risk_result["approved"]:
            self._rejected_count += 1
            audit["result"] = "rejected"
            audit["reason"] = f"Risk rejected: {'; '.join(risk_result['reasons'])}"
            logger.info(
                f"Order rejected by risk manager: {signal.signal_type.value} "
                f"{signal.quantity:.8f} {signal.pair}",
                component=LogComponent.TRADING,
                data={"reasons": risk_result["reasons"]},
            )
            return audit

        # Use adjusted quantity from risk manager
        quantity = risk_result["adjusted_quantity"]
        if quantity <= 0:
            audit["result"] = "rejected"
            audit["reason"] = "Adjusted quantity is zero after risk limits"
            return audit

        # Step 2: Price validation
        price_check = await self._price_validator.validate(signal.pair, signal.price)
        audit["pipeline_steps"].append({
            "step": "price_validation",
            "result": price_check,
        })

        if not price_check["valid"]:
            self._rejected_count += 1
            audit["result"] = "rejected"
            audit["reason"] = f"Price validation failed: {price_check['reason']}"
            logger.warning(
                f"Order rejected by price validator: {signal.pair}",
                component=LogComponent.TRADING,
                data=price_check,
            )
            return audit

        # Step 3: Execute on exchange
        order = OrderRequest(
            pair=signal.pair,
            side=signal.signal_type.value,
            order_type="limit",
            quantity=quantity,
            price=signal.price,
            post_only=signal.metadata.get("post_only", True),
        )

        try:
            result = await self._exchange.place_order(order)
        except Exception as e:
            audit["result"] = "error"
            audit["reason"] = f"Exchange error: {type(e).__name__}"
            logger.error(
                f"Exchange execution failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return audit

        audit["pipeline_steps"].append({
            "step": "exchange_execution",
            "result": {
                "order_id": result.order_id,
                "status": result.status,
                "filled_price": result.filled_price,
                "filled_quantity": result.filled_quantity,
                "fee": result.fee,
            },
        })

        # Step 4: Update position tracker
        if result.is_filled:
            pnl = self._positions.record_fill(
                pair=signal.pair,
                side=signal.signal_type.value,
                quantity=result.filled_quantity,
                price=result.filled_price,
                fee=result.fee,
            )

            # Update risk manager with P&L (for sells)
            if signal.signal_type == SignalType.SELL and pnl != 0:
                self._risk.record_trade_pnl(pnl, portfolio_value)

            # Update portfolio value tracking
            self._risk.update_portfolio_value(
                portfolio_value + pnl if signal.signal_type == SignalType.SELL else portfolio_value
            )

            self._execution_count += 1
            audit["result"] = "filled"
            audit["fill"] = {
                "price": result.filled_price,
                "quantity": result.filled_quantity,
                "fee": result.fee,
                "pnl": pnl,
            }

            logger.info(
                f"Trade executed: {signal.signal_type.value} {result.filled_quantity:.8f} "
                f"{signal.pair} @ {result.filled_price:.2f} (fee: {result.fee:.4f})",
                component=LogComponent.TRADING,
                data={"order_id": result.order_id, "pnl": pnl},
            )
        else:
            audit["result"] = result.status
            audit["reason"] = result.raw_response.get("error", "Order not filled")

        return audit

    @property
    def stats(self) -> Dict[str, Any]:
        """Execution statistics."""
        total = self._execution_count + self._rejected_count
        return {
            "total_signals_processed": total,
            "executions": self._execution_count,
            "rejections": self._rejected_count,
            "rejection_rate": self._rejected_count / total if total > 0 else 0.0,
        }
