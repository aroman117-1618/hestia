"""Tests for TradingManager initialization — market data source wiring."""

import pytest
import pytest_asyncio

from hestia.trading.manager import TradingManager


class TestTradingManagerPaperWithMarketData:
    """Verify TradingManager wires market data source in paper mode."""

    @pytest.mark.asyncio
    async def test_paper_mode_has_market_data_source(self):
        """Paper adapter gets market_data_source when primary is coinbase."""
        config = {
            "exchange": {
                "primary": "coinbase",
                "mode": "paper",
                "paper": {"initial_balance_usd": 100.0},
            }
        }
        mgr = TradingManager(config=config)
        await mgr.initialize()
        assert mgr.exchange is not None
        assert mgr.exchange.is_paper is True
        assert mgr.exchange._market_data_source is not None
        await mgr.close()

    @pytest.mark.asyncio
    async def test_paper_mode_no_source_without_coinbase_primary(self):
        """Paper adapter has no market_data_source when primary != coinbase."""
        config = {
            "exchange": {
                "primary": "alpaca",
                "mode": "paper",
                "paper": {"initial_balance_usd": 100.0},
            }
        }
        mgr = TradingManager(config=config)
        await mgr.initialize()
        assert mgr.exchange is not None
        assert mgr.exchange.is_paper is True
        assert mgr.exchange._market_data_source is None
        await mgr.close()
