"""Tests for trading product metadata validation."""

import pytest

from hestia.trading.product_info import (
    ProductInfo,
    get_product_info,
    validate_order_size,
)


class TestProductInfo:
    """ProductInfo dataclass and min_quote_value."""

    def test_btc_usd_minimum(self) -> None:
        """BTC-USD min order at ~$87K should be ~$8.70."""
        info = ProductInfo(pair="BTC-USD", base_min_size=0.0001)
        min_usd = info.min_quote_value(87000.0)
        assert abs(min_usd - 8.70) < 0.01

    def test_min_quote_value_scales_with_price(self) -> None:
        info = ProductInfo(pair="BTC-USD", base_min_size=0.0001)
        assert info.min_quote_value(100000.0) == pytest.approx(10.0)
        assert info.min_quote_value(50000.0) == pytest.approx(5.0)

    def test_default_values(self) -> None:
        info = ProductInfo()
        assert info.pair == "BTC-USD"
        assert info.base_min_size == 0.0001
        assert info.base_increment == 0.00000001
        assert info.quote_increment == 0.01
        assert info.base_max_size == 1000.0

    def test_to_dict(self) -> None:
        info = ProductInfo(pair="ETH-USD", base_min_size=0.001)
        d = info.to_dict()
        assert d["pair"] == "ETH-USD"
        assert d["base_min_size"] == 0.001


class TestValidateOrderSize:
    """Order size validation against product constraints."""

    def test_order_below_minimum_rejected(self) -> None:
        info = ProductInfo(pair="BTC-USD", base_min_size=0.0001)
        result = validate_order_size(info, quantity=0.00001, price=87000.0)
        assert result["valid"] is False
        assert "below minimum" in result["reason"]

    def test_order_above_minimum_accepted(self) -> None:
        info = ProductInfo(pair="BTC-USD", base_min_size=0.0001)
        result = validate_order_size(info, quantity=0.001, price=87000.0)
        assert result["valid"] is True

    def test_order_at_exact_minimum_accepted(self) -> None:
        info = ProductInfo(pair="BTC-USD", base_min_size=0.0001)
        result = validate_order_size(info, quantity=0.0001, price=87000.0)
        assert result["valid"] is True

    def test_order_above_maximum_rejected(self) -> None:
        info = ProductInfo(pair="BTC-USD", base_max_size=1000.0)
        result = validate_order_size(info, quantity=1500.0, price=87000.0)
        assert result["valid"] is False
        assert "exceeds maximum" in result["reason"]

    def test_zero_quantity_rejected(self) -> None:
        info = ProductInfo(pair="BTC-USD", base_min_size=0.0001)
        result = validate_order_size(info, quantity=0.0, price=87000.0)
        assert result["valid"] is False


class TestGetProductInfo:
    """Product catalog lookup."""

    def test_known_pair(self) -> None:
        info = get_product_info("BTC-USD")
        assert info.pair == "BTC-USD"
        assert info.base_min_size == 0.0001

    def test_eth_pair(self) -> None:
        info = get_product_info("ETH-USD")
        assert info.pair == "ETH-USD"
        assert info.base_min_size == 0.001

    def test_unknown_pair_falls_back(self) -> None:
        info = get_product_info("DOGE-USD")
        assert info.pair == "DOGE-USD"
        # Falls back to BTC-USD defaults
        assert info.base_min_size == 0.0001


class TestEquityProducts:
    """Equity product catalog (Sprint 28)."""

    def test_equity_product_info(self) -> None:
        info = get_product_info("SPY")
        assert info.base_min_size == 0.001
        assert info.base_max_size == 100000.0

    def test_crypto_product_info_unchanged(self) -> None:
        info = get_product_info("BTC-USD")
        assert info.base_min_size == 0.0001

    def test_unknown_pair_returns_default(self) -> None:
        info = get_product_info("UNKNOWN-PAIR")
        assert info.pair == "UNKNOWN-PAIR"

    def test_equity_all_symbols_present(self) -> None:
        """Verify all 10 equity symbols are in the catalog."""
        symbols = ["SPY", "QQQ", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "VOO", "VTI"]
        for sym in symbols:
            info = get_product_info(sym)
            assert info.pair == sym
            assert info.base_min_size == 0.001

    def test_equity_fractional_shares(self) -> None:
        """Equity products support fractional shares (0.001 increment)."""
        info = get_product_info("AAPL")
        assert info.base_increment == 0.001

    def test_equity_does_not_fall_back_to_btc(self) -> None:
        """Equity symbols should use equity defaults, not BTC fallback."""
        info = get_product_info("NVDA")
        assert info.base_max_size == 100000.0
        assert info.base_min_size != 0.0001  # Not BTC default
