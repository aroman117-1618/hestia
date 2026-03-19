"""Tests for hestia.trading.tax — TaxLotTracker."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from hestia.trading.tax import TaxLotTracker


class TestCreateLotFromBuy:
    """Tax lot creation from buy trades."""

    def test_buy_creates_tax_lot(self) -> None:
        """Cost basis includes fees: cost_basis = (price * qty) + fee."""
        tracker = TaxLotTracker(method="hifo")
        lot = tracker.create_lot_from_buy(
            trade_id="trade-1",
            pair="BTC-USD",
            quantity=0.5,
            price=60000.0,
            fee=10.0,
            acquired_at=datetime(2026, 1, 15, tzinfo=timezone.utc),
            user_id="user-1",
        )

        assert lot["trade_id"] == "trade-1"
        assert lot["pair"] == "BTC-USD"
        assert lot["quantity"] == 0.5
        assert lot["remaining_quantity"] == 0.5
        # cost_basis = (60000 * 0.5) + 10 = 30010
        assert lot["cost_basis"] == pytest.approx(30010.0)
        # cost_per_unit = 30010 / 0.5 = 60020
        assert lot["cost_per_unit"] == pytest.approx(60020.0)
        assert lot["method"] == "hifo"
        assert lot["status"] == "open"
        assert lot["user_id"] == "user-1"
        assert lot["realized_pnl"] == 0.0
        assert lot["id"]  # UUID was generated

    def test_buy_zero_quantity(self) -> None:
        """Zero quantity should produce zero cost_per_unit, not division error."""
        tracker = TaxLotTracker(method="fifo")
        lot = tracker.create_lot_from_buy(
            trade_id="t-zero",
            pair="ETH-USD",
            quantity=0.0,
            price=3000.0,
            fee=1.0,
            acquired_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert lot["cost_per_unit"] == 0.0


class TestMatchLotsForSell:
    """HIFO/FIFO lot matching and P&L calculation."""

    @staticmethod
    def _make_lot(
        lot_id: str,
        cost_per_unit: float,
        remaining: float,
        acquired_at: str = "2026-01-01T00:00:00+00:00",
    ) -> dict:
        return {
            "id": lot_id,
            "cost_per_unit": cost_per_unit,
            "remaining_quantity": remaining,
            "acquired_at": acquired_at,
            "realized_pnl": 0.0,
        }

    def test_sell_consumes_hifo_lot(self) -> None:
        """HIFO picks the highest cost_per_unit lot first."""
        tracker = TaxLotTracker(method="hifo")
        lots = [
            self._make_lot("cheap", 50000.0, 1.0),
            self._make_lot("expensive", 70000.0, 1.0),
        ]
        result = tracker.match_lots_for_sell(lots, quantity=0.5, sell_price=65000.0)

        consumed = result["consumed_lots"]
        assert len(consumed) == 1
        assert consumed[0]["lot_id"] == "expensive"
        assert consumed[0]["consumed_qty"] == pytest.approx(0.5)

        # P&L = (0.5 * 65000) - (0.5 * 70000) = 32500 - 35000 = -2500
        assert result["realized_pnl"] == pytest.approx(-2500.0)
        assert result["unmatched_quantity"] == pytest.approx(0.0)

    def test_hifo_sorts_internally(self) -> None:
        """Even if caller passes lots in wrong order, HIFO picks highest cost first."""
        tracker = TaxLotTracker(method="hifo")
        # Deliberately pass cheap lot first
        lots = [
            self._make_lot("cheap", 40000.0, 1.0),
            self._make_lot("mid", 55000.0, 1.0),
            self._make_lot("expensive", 70000.0, 1.0),
        ]
        result = tracker.match_lots_for_sell(lots, quantity=0.5, sell_price=60000.0)

        consumed = result["consumed_lots"]
        assert len(consumed) == 1
        assert consumed[0]["lot_id"] == "expensive"  # Most expensive consumed first

    def test_fifo_sorts_by_acquired_at(self) -> None:
        """FIFO picks the oldest lot first, regardless of cost."""
        tracker = TaxLotTracker(method="fifo")
        lots = [
            self._make_lot("new-expensive", 70000.0, 1.0, "2026-03-01T00:00:00+00:00"),
            self._make_lot("old-cheap", 40000.0, 1.0, "2026-01-01T00:00:00+00:00"),
        ]
        result = tracker.match_lots_for_sell(lots, quantity=0.5, sell_price=60000.0)

        consumed = result["consumed_lots"]
        assert len(consumed) == 1
        assert consumed[0]["lot_id"] == "old-cheap"

    def test_sell_spans_multiple_lots(self) -> None:
        """Sell quantity larger than one lot consumes multiple."""
        tracker = TaxLotTracker(method="hifo")
        lots = [
            self._make_lot("a", 60000.0, 0.3),
            self._make_lot("b", 50000.0, 0.5),
        ]
        result = tracker.match_lots_for_sell(lots, quantity=0.6, sell_price=55000.0)

        consumed = result["consumed_lots"]
        assert len(consumed) == 2
        # HIFO: lot "a" (60k) consumed fully, then lot "b" (50k) partially
        assert consumed[0]["lot_id"] == "a"
        assert consumed[0]["consumed_qty"] == pytest.approx(0.3)
        assert consumed[0]["status"] == "closed"
        assert consumed[1]["lot_id"] == "b"
        assert consumed[1]["consumed_qty"] == pytest.approx(0.3)
        assert consumed[1]["status"] == "partial"
        assert result["unmatched_quantity"] == pytest.approx(0.0)

    def test_insufficient_lots(self) -> None:
        """Unmatched quantity reported when lots are insufficient."""
        tracker = TaxLotTracker(method="hifo")
        lots = [self._make_lot("only", 50000.0, 0.1)]
        result = tracker.match_lots_for_sell(lots, quantity=1.0, sell_price=55000.0)

        assert result["unmatched_quantity"] == pytest.approx(0.9)
        assert len(result["consumed_lots"]) == 1

    def test_sell_fee_allocated_proportionally(self) -> None:
        """Sell fee is split across consumed lots by proportion."""
        tracker = TaxLotTracker(method="hifo")
        lots = [self._make_lot("x", 50000.0, 1.0)]
        result = tracker.match_lots_for_sell(
            lots, quantity=1.0, sell_price=55000.0, sell_fee=100.0
        )
        # P&L = (1 * 55000) - (1 * 50000) - 100 = 4900
        assert result["realized_pnl"] == pytest.approx(4900.0)


class TestExportTradesCsv:
    """CSV trade export."""

    def test_csv_export(self) -> None:
        """Correct header and row count."""
        trades = [
            {
                "timestamp": "2026-01-15T12:00:00",
                "side": "buy",
                "pair": "BTC-USD",
                "quantity": 0.5,
                "price": 60000.0,
                "fee": 10.0,
                "exchange": "coinbase",
            },
            {
                "timestamp": "2026-02-01T09:30:00",
                "side": "sell",
                "pair": "BTC-USD",
                "quantity": 0.25,
                "price": 65000.0,
                "fee": 8.0,
                "exchange": "coinbase",
            },
        ]
        csv_str = TaxLotTracker.export_trades_csv(trades)
        lines = [line.strip() for line in csv_str.strip().splitlines()]

        # Header + 2 data rows
        assert len(lines) == 3
        assert lines[0] == "Date,Type,Asset,Quantity,Price,Fee,Total,Exchange"

        # Buy total = (60000 * 0.5) + 10 = 30010
        assert "30010.00" in lines[1]
        # Sell total = (65000 * 0.25) - 8 = 16242
        assert "16242.00" in lines[2]

    def test_csv_empty(self) -> None:
        """Empty trade list produces header only."""
        csv_str = TaxLotTracker.export_trades_csv([])
        lines = csv_str.strip().split("\n")
        assert len(lines) == 1
        assert "Date" in lines[0]


class TestInvalidMethod:
    """Reject unknown tax lot methods."""

    def test_invalid_method_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tax lot method"):
            TaxLotTracker(method="lifo")


class TestExportCsvEndpoint:
    """API endpoint tests for GET /v1/trading/export/csv."""

    @staticmethod
    def _make_app():
        from fastapi import FastAPI
        from hestia.api.middleware.auth import get_device_token
        from hestia.api.routes.trading import router

        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_device_token] = lambda: "test-device-123"
        return app

    def test_csv_export_endpoint_returns_csv(self) -> None:
        """GET /v1/trading/export/csv returns 200 with text/csv content type."""
        from fastapi.testclient import TestClient

        mock_manager = AsyncMock()
        mock_manager.get_trades = AsyncMock(return_value=[
            {
                "timestamp": "2026-01-15T12:00:00",
                "side": "buy",
                "pair": "BTC-USD",
                "quantity": 0.5,
                "price": 60000.0,
                "fee": 10.0,
                "exchange": "coinbase",
            },
        ])

        app = self._make_app()
        with patch("hestia.api.routes.trading.get_trading_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/trading/export/csv")

        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        assert "attachment" in response.headers["content-disposition"]
        assert "hestia-trades-all.csv" in response.headers["content-disposition"]
        # Verify CSV content
        lines = response.text.strip().splitlines()
        assert len(lines) == 2  # header + 1 trade
        assert lines[0] == "Date,Type,Asset,Quantity,Price,Fee,Total,Exchange"

    def test_csv_export_with_year_filter(self) -> None:
        """Year parameter filters trades and sets filename."""
        from fastapi.testclient import TestClient

        mock_manager = AsyncMock()
        mock_manager.get_trades = AsyncMock(return_value=[
            {
                "timestamp": "2026-01-15T12:00:00",
                "side": "buy",
                "pair": "BTC-USD",
                "quantity": 0.5,
                "price": 60000.0,
                "fee": 10.0,
                "exchange": "coinbase",
            },
            {
                "timestamp": "2025-06-01T09:00:00",
                "side": "sell",
                "pair": "ETH-USD",
                "quantity": 1.0,
                "price": 3000.0,
                "fee": 5.0,
                "exchange": "coinbase",
            },
        ])

        app = self._make_app()
        with patch("hestia.api.routes.trading.get_trading_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/trading/export/csv?year=2026")

        assert response.status_code == 200
        assert "hestia-trades-2026.csv" in response.headers["content-disposition"]
        lines = response.text.strip().splitlines()
        assert len(lines) == 2  # header + 1 trade (2025 trade filtered out)

    def test_csv_export_empty(self) -> None:
        """No trades returns header-only CSV."""
        from fastapi.testclient import TestClient

        mock_manager = AsyncMock()
        mock_manager.get_trades = AsyncMock(return_value=[])

        app = self._make_app()
        with patch("hestia.api.routes.trading.get_trading_manager", return_value=mock_manager):
            client = TestClient(app)
            response = client.get("/v1/trading/export/csv")

        assert response.status_code == 200
        lines = response.text.strip().splitlines()
        assert len(lines) == 1  # header only
