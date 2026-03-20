"""
Standalone trading bot service — runs BotOrchestrator independently of the web server.

Designed to run as a separate launchd service (com.hestia.trading-bots).
Communicates with the API server via the bot_commands table in trading.db.

Usage:
    python -m hestia.trading.bot_service

Lifecycle:
    1. Connect to trading database
    2. Initialize exchange adapters + risk manager
    3. Resume all RUNNING bots
    4. Poll bot_commands table every 1s for start/stop commands
    5. On SIGTERM/SIGINT: gracefully stop all bots, then exit
"""

import asyncio
import signal
import sys
from typing import Dict, Optional

from hestia.logging import get_logger, LogComponent
from hestia.trading.bot_runner import BotRunner
from hestia.trading.database import get_trading_database
from hestia.trading.event_bus import TradingEvent, TradingEventBus
from hestia.trading.exchange.base import AbstractExchangeAdapter
from hestia.trading.manager import get_trading_manager
from hestia.trading.models import Bot, BotStatus
from hestia.trading.orchestrator import BotOrchestrator
from hestia.trading.risk import RiskManager

logger = get_logger()

COMMAND_POLL_INTERVAL = 1.0  # seconds


class BotService:
    """Standalone bot service with command queue polling."""

    def __init__(self) -> None:
        self._orchestrator: Optional[BotOrchestrator] = None
        self._shutdown_event = asyncio.Event()
        self._poll_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Initialize and run the bot service."""
        logger.info(
            "Bot service starting",
            component=LogComponent.TRADING,
        )

        # Initialize trading manager (creates DB, exchange adapters, risk manager)
        manager = await get_trading_manager()

        exchanges: Dict[str, AbstractExchangeAdapter] = {}
        if manager.exchange:
            exchanges["coinbase"] = manager.exchange

        event_bus = TradingEventBus(max_queue_size=100)

        self._orchestrator = BotOrchestrator(
            exchanges=exchanges,
            risk_manager=manager.risk_manager,
            event_bus=event_bus,
        )

        # Resume RUNNING bots
        resumed = await self._orchestrator.resume_running_bots()
        logger.info(
            f"Bot service ready — resumed {resumed} bot(s)",
            component=LogComponent.TRADING,
        )

        # Start command polling loop
        self._poll_task = asyncio.create_task(self._poll_commands())

        # Wait for shutdown signal
        await self._shutdown_event.wait()

        # Graceful shutdown
        logger.info(
            "Bot service shutting down",
            component=LogComponent.TRADING,
        )
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass

        if self._orchestrator:
            await self._orchestrator.stop_all()

        logger.info(
            "Bot service stopped",
            component=LogComponent.TRADING,
        )

    async def _poll_commands(self) -> None:
        """Poll the bot_commands table for pending start/stop commands."""
        db = await get_trading_database()

        while not self._shutdown_event.is_set():
            try:
                commands = await db.get_pending_commands()
                for cmd in commands:
                    await self._handle_command(cmd)
                    await db.mark_command_processed(cmd["id"])

                # Periodic cleanup of old processed commands
                await db.cleanup_old_commands(max_age_hours=24)

            except Exception as e:
                logger.error(
                    f"Command poll error: {type(e).__name__}",
                    component=LogComponent.TRADING,
                )

            await asyncio.sleep(COMMAND_POLL_INTERVAL)

    async def _handle_command(self, cmd: dict) -> None:
        """Execute a bot command."""
        bot_id = cmd["bot_id"]
        command = cmd["command"]

        logger.info(
            f"Processing command: {command} for bot {bot_id[:8]}",
            component=LogComponent.TRADING,
        )

        if command == "start":
            manager = await get_trading_manager()
            bot = await manager.get_bot(bot_id)
            if bot and self._orchestrator:
                await self._orchestrator.start_runner(bot)
        elif command == "stop":
            if self._orchestrator:
                await self._orchestrator.stop_runner(bot_id)
        else:
            logger.warning(
                f"Unknown bot command: {command}",
                component=LogComponent.TRADING,
            )

    def _signal_handler(self, sig: signal.Signals) -> None:
        """Handle SIGTERM/SIGINT — trigger graceful shutdown."""
        logger.info(
            f"Received {sig.name} — shutting down bot service",
            component=LogComponent.TRADING,
        )
        self._shutdown_event.set()


async def main() -> None:
    """Entry point for the bot service."""
    service = BotService()

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, service._signal_handler, sig)

    await service.start()


if __name__ == "__main__":
    print("Trading bot service starting...")
    asyncio.run(main())
