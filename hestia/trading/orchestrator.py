"""Bot orchestrator — manages BotRunner lifecycle.

Spawns runners on bot start, cancels on stop, resumes RUNNING bots
on server restart. Reconciles exchange state before resuming.

Concurrency: asyncio.Lock per bot_id prevents duplicate runners.
"""

import asyncio
from typing import Any, Dict, Optional

from hestia.logging import get_logger, LogComponent
from hestia.trading.bot_runner import BotRunner
from hestia.trading.event_bus import TradingEvent, TradingEventBus
from hestia.trading.exchange.base import AbstractExchangeAdapter
from hestia.trading.models import Bot, BotStatus
from hestia.trading.risk import RiskManager

logger = get_logger()


class BotOrchestrator:
    """Manages the lifecycle of all BotRunners.

    - Spawns one BotRunner per active bot as an asyncio.Task
    - Cancels runners on bot stop (cancels open orders, keeps positions)
    - Resumes all RUNNING bots on server startup after reconciliation
    - Prevents duplicate runners via per-bot locks
    """

    def __init__(
        self,
        exchange: AbstractExchangeAdapter,
        risk_manager: RiskManager,
        event_bus: Optional[TradingEventBus] = None,
    ) -> None:
        self._exchange = exchange
        self._risk = risk_manager
        self._event_bus = event_bus
        self._runners: Dict[str, asyncio.Task] = {}
        self._bot_locks: Dict[str, asyncio.Lock] = {}
        self._running = False

    def _get_lock(self, bot_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific bot."""
        if bot_id not in self._bot_locks:
            self._bot_locks[bot_id] = asyncio.Lock()
        return self._bot_locks[bot_id]

    async def start_runner(self, bot: Bot) -> bool:
        """Spawn a BotRunner for the given bot.

        Returns True if runner was started, False if already running.
        """
        async with self._get_lock(bot.id):
            if bot.id in self._runners and not self._runners[bot.id].done():
                logger.warning(
                    f"Runner already active for bot {bot.id}",
                    component=LogComponent.TRADING,
                )
                return False

            runner = BotRunner(
                bot=bot,
                exchange=self._exchange,
                risk_manager=self._risk,
                event_bus=self._event_bus,
            )
            task = asyncio.create_task(
                runner.run(),
                name=f"bot-runner-{bot.id[:8]}",
            )
            self._runners[bot.id] = task

            # Monitor for unexpected completion
            task.add_done_callback(
                lambda t, bid=bot.id: self._on_runner_done(bid, t)
            )

            logger.info(
                f"Bot runner started: {bot.name} ({bot.id[:8]})",
                component=LogComponent.TRADING,
                data={"bot_id": bot.id, "strategy": bot.strategy},
            )

            if self._event_bus:
                self._event_bus.publish(TradingEvent(
                    event_type="position_update",
                    data={"bot_id": bot.id, "action": "started", "name": bot.name},
                ))

            return True

    async def stop_runner(self, bot_id: str) -> bool:
        """Stop a BotRunner and cancel open orders (keep positions).

        Returns True if runner was stopped, False if not found.
        """
        async with self._get_lock(bot_id):
            task = self._runners.pop(bot_id, None)
            if task is None or task.done():
                return False

            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

            # Cancel open orders for this bot's pair (don't flatten positions)
            try:
                open_orders = await self._exchange.get_open_orders()
                for order in open_orders:
                    await self._exchange.cancel_order(order.order_id)
                    logger.info(
                        f"Cancelled open order {order.order_id} on bot stop",
                        component=LogComponent.TRADING,
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to cancel open orders on stop: {type(e).__name__}",
                    component=LogComponent.TRADING,
                )

            logger.info(
                f"Bot runner stopped: {bot_id[:8]}",
                component=LogComponent.TRADING,
            )

            if self._event_bus:
                self._event_bus.publish(TradingEvent(
                    event_type="position_update",
                    data={"bot_id": bot_id, "action": "stopped"},
                ))

            return True

    async def resume_running_bots(self) -> int:
        """Resume all bots with status=RUNNING on server startup.

        Performs exchange reconciliation first (Gemini condition #1).
        Returns number of bots resumed.
        """
        self._running = True

        # Step 1: Reconcile exchange state
        await self._reconcile_exchange_state()

        # Step 2: Load all RUNNING bots
        from hestia.trading.manager import get_trading_manager
        manager = await get_trading_manager()
        bots = await manager.list_bots(status=BotStatus.RUNNING.value)

        if not bots:
            logger.info(
                "No RUNNING bots to resume",
                component=LogComponent.TRADING,
            )
            return 0

        resumed = 0
        for bot in bots:
            try:
                started = await self.start_runner(bot)
                if started:
                    resumed += 1
            except Exception as e:
                logger.error(
                    f"Failed to resume bot {bot.id[:8]}: {type(e).__name__}",
                    component=LogComponent.TRADING,
                )

        logger.info(
            f"Resumed {resumed}/{len(bots)} RUNNING bots",
            component=LogComponent.TRADING,
        )
        return resumed

    async def stop_all(self) -> None:
        """Stop all active runners (server shutdown)."""
        self._running = False
        bot_ids = list(self._runners.keys())
        for bot_id in bot_ids:
            try:
                await self.stop_runner(bot_id)
            except Exception as e:
                logger.warning(
                    f"Error stopping runner {bot_id[:8]}: {type(e).__name__}",
                    component=LogComponent.TRADING,
                )

    async def _reconcile_exchange_state(self) -> None:
        """Reconcile local state with exchange on startup (Gemini condition #1).

        Queries Coinbase for actual positions and open orders.
        Logs discrepancies. Does NOT auto-correct — logs for human review.
        """
        if not self._exchange or not self._exchange.is_connected:
            logger.debug(
                "Exchange not connected, skipping reconciliation",
                component=LogComponent.TRADING,
            )
            return

        try:
            # Check actual balances
            balances = await self._exchange.get_balances()
            non_usd = {
                k: v for k, v in balances.items()
                if k != "USD" and v.total > 0.001
            }
            if non_usd:
                logger.info(
                    f"Exchange positions on startup: {list(non_usd.keys())}",
                    component=LogComponent.TRADING,
                    data={k: {"available": v.available, "hold": v.hold} for k, v in non_usd.items()},
                )

            # Check open orders
            open_orders = await self._exchange.get_open_orders()
            if open_orders:
                logger.info(
                    f"Open orders on startup: {len(open_orders)}",
                    component=LogComponent.TRADING,
                    data=[{"id": o.order_id, "pair": o.pair, "side": o.side} for o in open_orders],
                )

        except Exception as e:
            logger.warning(
                f"Exchange reconciliation failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )

    def _on_runner_done(self, bot_id: str, task: asyncio.Task) -> None:
        """Callback when a runner task completes (normally or with error)."""
        self._runners.pop(bot_id, None)
        if task.cancelled():
            return

        exc = task.exception()
        if exc:
            logger.error(
                f"Bot runner {bot_id[:8]} crashed: {type(exc).__name__}",
                component=LogComponent.TRADING,
            )
            # Mark bot as ERROR
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._mark_bot_error(bot_id))
            except RuntimeError:
                pass

    async def _mark_bot_error(self, bot_id: str) -> None:
        """Set bot status to ERROR after runner crash."""
        try:
            from hestia.trading.manager import get_trading_manager
            manager = await get_trading_manager()
            await manager.update_bot(bot_id, {"status": BotStatus.ERROR.value})

            if self._event_bus:
                self._event_bus.publish(TradingEvent(
                    event_type="risk_alert",
                    data={"bot_id": bot_id, "reason": "Bot entered ERROR state after crash"},
                    priority=True,
                ))

            # Send critical alert
            try:
                from hestia.trading.alerts import get_trading_alerter
                alerter = await get_trading_alerter()
                await alerter.send_risk_alert("bot_crash", f"Bot {bot_id[:8]} crashed and entered ERROR state")
            except Exception:
                pass
        except Exception as e:
            logger.error(
                f"Failed to mark bot as ERROR: {type(e).__name__}",
                component=LogComponent.TRADING,
            )

    @property
    def active_count(self) -> int:
        """Number of currently running bot tasks."""
        return len([t for t in self._runners.values() if not t.done()])

    @property
    def active_bot_ids(self) -> list:
        """IDs of bots with active runners."""
        return [bid for bid, t in self._runners.items() if not t.done()]


# Module-level singleton
_orchestrator: Optional[BotOrchestrator] = None


async def get_bot_orchestrator() -> BotOrchestrator:
    """Get or create the bot orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        from hestia.trading.manager import get_trading_manager
        from hestia.api.routes.trading import _event_bus

        manager = await get_trading_manager()
        _orchestrator = BotOrchestrator(
            exchange=manager.exchange,
            risk_manager=manager.risk_manager,
            event_bus=_event_bus,
        )
    return _orchestrator


async def close_bot_orchestrator() -> None:
    """Shutdown the orchestrator (server shutdown)."""
    global _orchestrator
    if _orchestrator is not None:
        await _orchestrator.stop_all()
        _orchestrator = None
