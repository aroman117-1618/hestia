"""Tests for BotRunner — portfolio value fallback and pair injection."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from hestia.trading.bot_runner import BotRunner
from hestia.trading.exchange.base import AbstractExchangeAdapter
from hestia.trading.models import Bot, StrategyType
from hestia.trading.risk import RiskManager


@pytest.mark.asyncio
async def test_get_portfolio_value_fallback_on_empty_balances():
    """When exchange returns empty balances, fall back to bot.capital_allocated."""
    bot = Bot(name="test", strategy=StrategyType.MEAN_REVERSION, pair="BTC-USD",
              capital_allocated=62.50, config={})
    exchange = AsyncMock(spec=AbstractExchangeAdapter)
    exchange.get_balances = AsyncMock(return_value={})

    runner = BotRunner(bot=bot, exchange=exchange, risk_manager=MagicMock())
    result = await runner._get_portfolio_value()
    assert result == 62.50


def test_strategy_receives_bot_pair():
    """Strategy should use bot.pair, not default to BTC-USD."""
    bot = Bot(name="ETH MR", strategy=StrategyType.MEAN_REVERSION, pair="ETH-USD",
              capital_allocated=62.50, config={"rsi_period": 3, "rsi_oversold": 20, "rsi_overbought": 80})
    exchange = AsyncMock(spec=AbstractExchangeAdapter)

    runner = BotRunner(bot=bot, exchange=exchange, risk_manager=MagicMock())
    assert runner._strategy.pair == "ETH-USD"
