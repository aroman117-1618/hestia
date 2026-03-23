"""
Trading manager — singleton coordinator for the trading module.

Orchestrates database, exchange adapters, risk management,
and tax lot tracking.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

from hestia.logging import get_logger, LogComponent
from hestia.trading.database import TradingDatabase, get_trading_database
from hestia.trading.exchange.base import AbstractExchangeAdapter, OrderRequest
from hestia.trading.exchange.paper import PaperAdapter
from hestia.trading.models import (
    Bot,
    BotStatus,
    DailySummary,
    OrderType,
    StrategyType,
    Trade,
    TradeSide,
)
from hestia.trading.risk import RiskManager
from hestia.trading.tax import TaxLotTracker

logger = get_logger()

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "trading.yaml"

# Module-level singleton
_instance: Optional["TradingManager"] = None


def _load_config() -> Dict[str, Any]:
    """Load trading config from YAML."""
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {}


class TradingManager:
    """
    Central coordinator for all trading operations.

    Follows Hestia's singleton manager pattern with async factory.
    """

    def __init__(
        self,
        database: Optional[TradingDatabase] = None,
        exchange: Optional[AbstractExchangeAdapter] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._database = database
        self._exchange = exchange
        self._config = config or _load_config()
        self._risk_manager = RiskManager(self._config)
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database and exchange connections."""
        if self._initialized:
            return

        # Database
        if self._database is None:
            self._database = await get_trading_database()

        # Wire risk manager to database for state persistence
        self._risk_manager.set_database(self._database)
        await self._risk_manager.restore_state()

        # Exchange adapter (default to paper)
        if self._exchange is None:
            mode = self._config.get("exchange", {}).get("mode", "paper")
            if mode == "paper":
                paper_cfg = self._config.get("exchange", {}).get("paper", {})

                # Wire Coinbase public API as market data source for paper trading
                market_data_source = None
                primary = self._config.get("exchange", {}).get("primary", "")
                if primary == "coinbase":
                    from hestia.trading.backtest.data_loader import DataLoader
                    _loader = DataLoader()

                    async def _fetch_candles(
                        pair: str, granularity: str = "1h", days: int = 7,
                    ) -> Optional[pd.DataFrame]:
                        from datetime import timedelta
                        end = datetime.now(timezone.utc)
                        start = end - timedelta(days=days)
                        return await _loader.fetch_from_coinbase(
                            pair=pair, granularity=granularity, start=start, end=end,
                        )

                    market_data_source = _fetch_candles

                self._exchange = PaperAdapter(
                    initial_balance_usd=paper_cfg.get("initial_balance_usd", 250.0),
                    maker_fee=paper_cfg.get("maker_fee", 0.004),
                    taker_fee=paper_cfg.get("taker_fee", 0.006),
                    slippage=paper_cfg.get("slippage", 0.001),
                    market_data_source=market_data_source,
                )
            else:
                from hestia.trading.exchange.coinbase import CoinbaseAdapter
                self._exchange = CoinbaseAdapter()
            await self._exchange.connect()

        self._initialized = True
        logger.info(
            "Trading manager initialized",
            component=LogComponent.TRADING,
            data={
                "mode": "paper" if self._exchange.is_paper else "live",
                "exchange": self._exchange.exchange_name,
            },
        )

    async def close(self) -> None:
        """Shutdown trading manager."""
        if self._exchange:
            await self._exchange.disconnect()
        logger.debug("Trading manager closed", component=LogComponent.TRADING)

    # ── Bot Management ────────────────────────────────────────────

    async def create_bot(
        self,
        name: str,
        strategy: str,
        pair: str = "BTC-USD",
        capital: float = 0.0,
        config: Optional[Dict[str, Any]] = None,
        user_id: str = "user-default",
    ) -> Bot:
        """Create a new trading bot."""
        bot = Bot(
            name=name,
            strategy=StrategyType(strategy),
            pair=pair,
            capital_allocated=capital,
            config=config or {},
            user_id=user_id,
        )
        await self._database.create_bot(bot.to_dict())
        logger.info(
            f"Bot created: {name} ({strategy})",
            component=LogComponent.TRADING,
            data={"bot_id": bot.id, "pair": pair, "capital": capital},
        )
        return bot

    async def get_bot(self, bot_id: str) -> Optional[Bot]:
        """Get a bot by ID."""
        data = await self._database.get_bot(bot_id)
        if data is None:
            return None
        return Bot.from_dict(data)

    async def list_bots(
        self, user_id: str = "user-default", status: Optional[str] = None
    ) -> List[Bot]:
        """List all bots."""
        rows = await self._database.list_bots(user_id, status)
        return [Bot.from_dict(r) for r in rows]

    async def update_bot(self, bot_id: str, updates: Dict[str, Any]) -> Optional[Bot]:
        """Update bot configuration."""
        data = await self._database.update_bot(bot_id, updates)
        if data is None:
            return None
        return Bot.from_dict(data)

    async def start_bot(self, bot_id: str) -> Optional[Bot]:
        """Start a bot (set status to running)."""
        return await self.update_bot(bot_id, {"status": BotStatus.RUNNING.value})

    async def stop_bot(self, bot_id: str) -> Optional[Bot]:
        """Stop a bot (set status to stopped)."""
        return await self.update_bot(bot_id, {"status": BotStatus.STOPPED.value})

    async def delete_bot(self, bot_id: str) -> bool:
        """Soft-delete a bot."""
        return await self._database.delete_bot(bot_id)

    # ── Trade Recording & Tax Lots ────────────────────────────────

    async def record_trade(
        self,
        bot_id: str,
        side: str,
        price: float,
        quantity: float,
        fee: float = 0.0,
        pair: str = "BTC-USD",
        order_type: str = "limit",
        exchange_order_id: Optional[str] = None,
        user_id: str = "user-default",
    ) -> Trade:
        """
        Record a trade and manage tax lots atomically.

        Buys create new tax lots. Sells consume lots (HIFO or FIFO).
        Trade + tax lot writes happen in a single SQLite transaction —
        if either fails, both roll back (no orphaned records).
        """
        trade = Trade(
            bot_id=bot_id,
            side=TradeSide(side),
            order_type=OrderType(order_type) if isinstance(order_type, str) else order_type,
            price=price,
            quantity=quantity,
            fee=fee,
            pair=pair,
            exchange_order_id=exchange_order_id,
            user_id=user_id,
        )

        tax_method = self._config.get("tax", {}).get("default_method", "hifo")

        pnl = 0.0
        # Pre-compute portfolio value BEFORE entering transaction.
        # _estimate_portfolio_value() makes exchange API calls (network I/O)
        # which would hold the BEGIN IMMEDIATE lock for unbounded time.
        portfolio_value = 0.0
        if trade.side == TradeSide.SELL:
            portfolio_value = await self._estimate_portfolio_value(user_id)

        # Atomic transaction: trade + tax lot(s) written together.
        # Trade is inserted first (tax_lots.trade_id has FK constraint).
        try:
            await self._database.connection.execute("BEGIN IMMEDIATE")

            if trade.side == TradeSide.BUY:
                tax_tracker = TaxLotTracker(method=tax_method)
                lot_dict = tax_tracker.create_lot_from_buy(
                    trade_id=trade.id,
                    pair=pair,
                    quantity=quantity,
                    price=price,
                    fee=fee,
                    acquired_at=trade.timestamp,
                    user_id=user_id,
                )
                trade.tax_lot_id = lot_dict["id"]
                # Insert trade first (FK parent), then tax lot (FK child)
                await self._database.record_trade_no_commit(trade.to_dict())
                await self._database.create_tax_lot_no_commit(lot_dict)

            elif trade.side == TradeSide.SELL:
                pnl = await self._consume_tax_lots_no_commit(
                    pair=pair,
                    sell_quantity=quantity,
                    sell_price=price,
                    sell_fee=fee,
                    method=tax_method,
                    user_id=user_id,
                )
                await self._database.record_trade_no_commit(trade.to_dict())

            else:
                await self._database.record_trade_no_commit(trade.to_dict())

            await self._database.connection.execute("COMMIT")

        except Exception as exc:
            try:
                await self._database.connection.execute("ROLLBACK")
            except Exception:
                pass  # Connection may already be rolled back
            logger.error(
                f"Trade recording ROLLED BACK: {side} {quantity:.8f} {pair} @ {price:.2f}",
                component=LogComponent.TRADING,
                data={"trade_id": trade.id, "bot_id": bot_id, "error": type(exc).__name__},
            )
            raise

        # Record P&L for risk tracking AFTER successful commit.
        # This is in-memory state, not transactional — safe outside the lock.
        if trade.side == TradeSide.SELL:
            self._risk_manager.record_trade_pnl(pnl, portfolio_value)

        logger.info(
            f"Trade recorded: {side} {quantity:.8f} {pair} @ {price:.2f}",
            component=LogComponent.TRADING,
            data={"trade_id": trade.id, "bot_id": bot_id, "fee": fee},
        )
        return trade

    async def _consume_tax_lots(
        self,
        pair: str,
        sell_quantity: float,
        sell_price: float,
        sell_fee: float,
        method: str,
        user_id: str,
    ) -> float:
        """Consume tax lots with auto-commit (standalone use)."""
        pnl = await self._consume_tax_lots_no_commit(
            pair, sell_quantity, sell_price, sell_fee, method, user_id
        )
        await self._database.connection.commit()
        return pnl

    async def _consume_tax_lots_no_commit(
        self,
        pair: str,
        sell_quantity: float,
        sell_price: float,
        sell_fee: float,
        method: str,
        user_id: str,
    ) -> float:
        """
        Consume tax lots for a sell order WITHOUT committing.

        Used inside atomic transactions. Caller is responsible for COMMIT/ROLLBACK.
        Delegates lot selection and P&L math to TaxLotTracker; applies
        the results to the database via update_tax_lot_no_commit.
        """
        lots = await self._database.get_open_tax_lots(pair, method, user_id)

        tax_tracker = TaxLotTracker(method=method)
        result = tax_tracker.match_lots_for_sell(
            open_lots=lots,
            quantity=sell_quantity,
            sell_price=sell_price,
            sell_fee=sell_fee,
        )

        for entry in result["consumed_lots"]:
            updates: Dict[str, Any] = {
                "remaining_quantity": entry["new_remaining"],
                "realized_pnl": entry["prior_realized_pnl"] + entry["realized_pnl_delta"],
                "status": entry["status"],
            }
            if entry.get("closed_at"):
                updates["closed_at"] = entry["closed_at"]

            await self._database.update_tax_lot_no_commit(entry["lot_id"], updates)

        return result["realized_pnl"]

    async def _estimate_portfolio_value(self, user_id: str) -> float:
        """Estimate total portfolio value from exchange balances."""
        _STABLECOINS = {"USDC", "USDT", "DAI", "BUSD"}
        if self._exchange:
            balances = await self._exchange.get_balances()
            total = 0.0
            for currency, balance in balances.items():
                if currency == "USD":
                    total += balance.total
                elif currency in _STABLECOINS:
                    total += balance.total
                elif balance.total > 0:
                    try:
                        ticker = await self._exchange.get_ticker(f"{currency}-USD")
                        total += balance.total * ticker.get("price", 0.0)
                    except Exception:
                        pass
            return total
        return 0.0

    # ── Trade History ─────────────────────────────────────────────

    async def get_trades(
        self,
        bot_id: Optional[str] = None,
        user_id: str = "user-default",
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get trade history."""
        return await self._database.get_trades(bot_id, user_id, limit, offset)

    async def get_trade_count(
        self, bot_id: Optional[str] = None, user_id: str = "user-default"
    ) -> int:
        """Count trades."""
        return await self._database.get_trade_count(bot_id, user_id)

    # ── Tax Lots ──────────────────────────────────────────────────

    async def get_tax_lots(
        self, user_id: str = "user-default", status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all tax lots."""
        return await self._database.get_tax_lots(user_id, status)

    # ── Daily Summary ─────────────────────────────────────────────

    async def get_daily_summary(
        self, date: str, user_id: str = "user-default"
    ) -> Optional[Dict[str, Any]]:
        """Get daily summary for a date."""
        return await self._database.get_daily_summary(date, user_id)

    async def get_daily_summaries(
        self, user_id: str = "user-default", limit: int = 30
    ) -> List[Dict[str, Any]]:
        """Get recent daily summaries."""
        return await self._database.get_daily_summaries(user_id, limit)

    # ── Risk Management ───────────────────────────────────────────

    @property
    def risk_manager(self) -> RiskManager:
        """Access the risk manager."""
        return self._risk_manager

    def activate_kill_switch(self, reason: str = "Manual activation") -> None:
        """Emergency halt all trading."""
        self._risk_manager.activate_kill_switch(reason)

    def deactivate_kill_switch(self) -> None:
        """Re-enable trading."""
        self._risk_manager.deactivate_kill_switch()

    def get_risk_status(self) -> Dict[str, Any]:
        """Get full risk manager status."""
        return self._risk_manager.get_status()

    # ── Exchange ──────────────────────────────────────────────────

    @property
    def exchange(self) -> Optional[AbstractExchangeAdapter]:
        """Access the exchange adapter."""
        return self._exchange


async def get_trading_manager(
    config: Optional[Dict[str, Any]] = None,
) -> TradingManager:
    """Singleton factory for TradingManager."""
    global _instance
    if _instance is None:
        _instance = TradingManager(config=config)
        await _instance.initialize()
    return _instance


async def close_trading_manager() -> None:
    """Shutdown the trading manager singleton."""
    global _instance
    if _instance is not None:
        await _instance.close()
        _instance = None
