"""Bot runner — the core trading loop.

One runner per bot. Polls candles → computes indicators → generates signals
→ executes through risk pipeline → records trades → publishes events.

Error handling: exponential backoff with max 3 crashes before ERROR state.
"""

import asyncio
import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent
from hestia.trading.data.indicators import add_all_indicators
from hestia.trading.event_bus import TradingEvent, TradingEventBus
from hestia.trading.exchange.base import AbstractExchangeAdapter
from hestia.trading.executor import TradeExecutor
from hestia.trading.models import Bot, BotStatus, StrategyType
from hestia.trading.position_tracker import PositionTracker
from hestia.trading.price_validator import PriceValidator
from hestia.trading.risk import RiskManager
from hestia.trading.scoring import ConfidenceScorer
from hestia.trading.strategies.base import BaseStrategy, Signal

logger = get_logger()

# Error handling constants
MAX_CONSECUTIVE_ERRORS = 3
BACKOFF_INITIAL_S = 10.0
BACKOFF_MAX_S = 60.0

# Default poll interval (seconds) — 15 min for 1h candle strategies
DEFAULT_POLL_INTERVAL = 900


def _create_strategy(strategy_type: StrategyType, config: Dict[str, Any]) -> BaseStrategy:
    """Factory for strategy instances."""
    if strategy_type == StrategyType.GRID:
        from hestia.trading.strategies.grid import GridStrategy
        return GridStrategy(config)
    elif strategy_type == StrategyType.MEAN_REVERSION:
        from hestia.trading.strategies.mean_reversion import MeanReversionStrategy
        return MeanReversionStrategy(config)
    else:
        raise ValueError(f"Unsupported strategy type: {strategy_type}")


class BotRunner:
    """Runs a single trading bot in a continuous async loop.

    Lifecycle:
    - Created by BotOrchestrator when a bot starts
    - Polls candles, generates signals, executes trades
    - Stops when bot status != RUNNING or cancelled
    - On repeated crashes: exponential backoff → ERROR state
    """

    def __init__(
        self,
        bot: Bot,
        exchange: AbstractExchangeAdapter,
        risk_manager: RiskManager,
        event_bus: Optional[TradingEventBus] = None,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.bot = bot
        self._exchange = exchange
        self._risk = risk_manager
        self._event_bus = event_bus
        self._poll_interval = poll_interval

        # Build execution pipeline
        self._position_tracker = PositionTracker(
            exchange=exchange,
            reconciliation_interval=60,
        )
        self._price_validator = PriceValidator(exchange=exchange)
        self._executor = TradeExecutor(
            exchange=exchange,
            risk_manager=risk_manager,
            position_tracker=self._position_tracker,
            price_validator=self._price_validator,
        )

        # Strategy
        self._strategy = _create_strategy(
            StrategyType(bot.strategy) if isinstance(bot.strategy, str) else bot.strategy,
            bot.config,
        )

        # Error tracking
        self._consecutive_errors = 0
        self._current_backoff = BACKOFF_INITIAL_S
        self._running = False

    async def run(self) -> None:
        """Main trading loop. Runs until cancelled or bot enters ERROR state."""
        self._running = True
        bot_id = self.bot.id
        pair = self.bot.pair

        logger.info(
            f"BotRunner started: {self.bot.name} ({self._strategy.name}) on {pair}",
            component=LogComponent.TRADING,
            data={"bot_id": bot_id, "strategy": self._strategy.strategy_type},
        )

        # Start reconciliation loop
        await self._position_tracker.start_reconciliation_loop()

        try:
            while self._running:
                try:
                    await self._tick(pair)
                    # Success — reset error state
                    self._consecutive_errors = 0
                    self._current_backoff = BACKOFF_INITIAL_S
                    await asyncio.sleep(self._poll_interval)

                except asyncio.CancelledError:
                    raise  # Propagate cancellation
                except Exception as e:
                    self._consecutive_errors += 1
                    logger.error(
                        f"BotRunner tick error ({self._consecutive_errors}/{MAX_CONSECUTIVE_ERRORS}): "
                        f"{type(e).__name__}",
                        component=LogComponent.TRADING,
                        data={"bot_id": bot_id, "error": type(e).__name__},
                    )

                    if self._consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        logger.critical(
                            f"BotRunner entering ERROR state after {MAX_CONSECUTIVE_ERRORS} consecutive failures",
                            component=LogComponent.TRADING,
                            data={"bot_id": bot_id},
                        )
                        # Publish error event
                        if self._event_bus:
                            self._event_bus.publish(TradingEvent(
                                event_type="risk_alert",
                                data={"bot_id": bot_id, "reason": f"Bot entering ERROR state: {type(e).__name__}"},
                                priority=True,
                            ))
                        self._running = False
                        break

                    # Exponential backoff
                    logger.info(
                        f"Backing off {self._current_backoff:.0f}s before retry",
                        component=LogComponent.TRADING,
                    )
                    await asyncio.sleep(self._current_backoff)
                    self._current_backoff = min(
                        self._current_backoff * 2, BACKOFF_MAX_S
                    )
        finally:
            await self._position_tracker.stop_reconciliation_loop()
            self._running = False
            logger.info(
                f"BotRunner stopped: {self.bot.name}",
                component=LogComponent.TRADING,
                data={"bot_id": bot_id},
            )

    async def _tick(self, pair: str) -> None:
        """Single iteration of the trading loop."""
        # 1. Fetch candles from exchange
        candles = await self._fetch_candles(pair)
        if candles is None or len(candles) < 30:
            logger.debug(
                f"Insufficient candle data ({len(candles) if candles is not None else 0} candles), skipping tick",
                component=LogComponent.TRADING,
            )
            return

        # 2. Compute indicators
        df = candles.copy()
        try:
            df = add_all_indicators(df)
        except Exception as e:
            logger.warning(
                f"Indicator computation failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
            return

        # 3. Get portfolio value
        portfolio_value = await self._get_portfolio_value()
        if portfolio_value <= 0:
            logger.debug("Portfolio value is 0, skipping tick", component=LogComponent.TRADING)
            return

        # 4. Generate signal
        signal = self._strategy.analyze(df, portfolio_value)

        # 5. Execute if actionable
        if signal.is_actionable:
            result = await self._executor.execute_signal(signal, portfolio_value)

            # 6. Record trade if filled
            if result.get("result") == "filled":
                await self._record_trade(result, signal)

            # 7. Publish event
            if self._event_bus:
                self._event_bus.publish(TradingEvent(
                    event_type="trade",
                    data={
                        "bot_id": self.bot.id,
                        "result": result.get("result"),
                        "pair": pair,
                        "side": signal.signal_type.value,
                        "confidence": signal.confidence,
                    },
                ))

    async def _fetch_candles(self, pair: str) -> Optional[pd.DataFrame]:
        """Fetch OHLCV candles from exchange REST API."""
        try:
            from hestia.trading.backtest.data_loader import DataLoader
            loader = DataLoader()
            df = await loader.fetch_from_coinbase(
                pair=pair,
                granularity="1h",
            )
            if df is not None and len(df) > 0:
                return df
        except Exception as e:
            logger.warning(
                f"Coinbase candle fetch failed: {type(e).__name__}, trying ticker fallback",
                component=LogComponent.TRADING,
            )

        # Fallback: use ticker for latest price (minimal data)
        try:
            ticker = await self._exchange.get_ticker(pair)
            price = ticker.get("price", 0.0)
            if price > 0:
                now = datetime.now(timezone.utc)
                return pd.DataFrame([{
                    "timestamp": now, "open": price, "high": price,
                    "low": price, "close": price, "volume": 0,
                }])
        except Exception:
            pass
        return None

    async def _get_portfolio_value(self) -> float:
        """Estimate current portfolio value from exchange balances."""
        try:
            balances = await self._exchange.get_balances()
            total = 0.0
            for currency, balance in balances.items():
                if currency == "USD":
                    total += balance.total
                elif balance.total > 0:
                    ticker = await self._exchange.get_ticker(f"{currency}-USD")
                    total += balance.total * ticker.get("price", 0.0)
            return total
        except Exception:
            return 0.0

    async def _record_trade(self, result: Dict[str, Any], signal: Signal) -> None:
        """Record a filled trade via the trading manager."""
        try:
            from hestia.trading.manager import get_trading_manager
            manager = await get_trading_manager()

            fill = result.get("fill", {})
            trail = json.dumps(result.get("pipeline_steps", []))
            score = result.get("confidence_score")

            if score is None:
                score = ConfidenceScorer.compute(
                    signal_confidence=signal.confidence,
                    requested_quantity=signal.quantity,
                    adjusted_quantity=fill.get("quantity", signal.quantity),
                    expected_price=signal.price,
                    filled_price=fill.get("price", signal.price),
                    volume_confirmed=signal.metadata.get("volume_confirmed", False),
                    trend_aligned=signal.metadata.get("trend_aligned", False),
                )

            await manager.record_trade(
                bot_id=self.bot.id,
                side=signal.signal_type.value,
                price=fill.get("price", signal.price),
                quantity=fill.get("quantity", signal.quantity),
                fee=fill.get("fee", 0.0),
                pair=self.bot.pair,
                user_id=self.bot.user_id,
            )

            # Send alert
            try:
                from hestia.trading.alerts import get_trading_alerter
                alerter = await get_trading_alerter()
                await alerter.send_trade_alert({
                    "side": signal.signal_type.value,
                    "pair": self.bot.pair,
                    "quantity": fill.get("quantity", 0),
                    "price": fill.get("price", 0),
                    "confidence_score": score,
                })
            except Exception:
                pass  # Alerts are non-critical

        except Exception as e:
            logger.error(
                f"Failed to record trade: {type(e).__name__}",
                component=LogComponent.TRADING,
            )

    def stop(self) -> None:
        """Signal the runner to stop."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running
