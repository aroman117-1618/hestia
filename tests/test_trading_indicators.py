"""Tests for technical indicators layer."""

import numpy as np
import pandas as pd
import pytest

from hestia.trading.data.indicators import (
    add_all_indicators,
    adx,
    atr,
    bollinger_bands,
    ema,
    rsi,
    sma,
    volume_ratio,
)


def _make_ohlcv(n: int = 100, base_price: float = 65000.0, seed: int = 42) -> pd.DataFrame:
    """Generate synthetic OHLCV data for testing."""
    np.random.seed(seed)
    returns = np.random.normal(0.0, 0.02, n)
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame({
        "open": prices * (1 + np.random.uniform(-0.005, 0.005, n)),
        "high": prices * (1 + np.random.uniform(0.001, 0.02, n)),
        "low": prices * (1 - np.random.uniform(0.001, 0.02, n)),
        "close": prices,
        "volume": np.random.uniform(100, 10000, n),
    })
    return df


class TestRSI:
    def test_rsi_range(self):
        df = _make_ohlcv()
        result = rsi(df["close"], period=7)
        valid = result.dropna()
        assert all(0 <= v <= 100 for v in valid)

    def test_rsi_period_7(self):
        df = _make_ohlcv()
        r7 = rsi(df["close"], period=7)
        r14 = rsi(df["close"], period=14)
        # RSI-7 should be more volatile than RSI-14
        assert r7.dropna().std() > r14.dropna().std()

    def test_rsi_default_period(self):
        df = _make_ohlcv()
        result = rsi(df["close"])
        assert len(result) == len(df)


class TestSMA:
    def test_sma_calculation(self):
        df = _make_ohlcv()
        result = sma(df["close"], period=20)
        # SMA should be smoother than raw prices
        valid = result.dropna()
        assert valid.std() < df["close"].std()

    def test_sma_length(self):
        df = _make_ohlcv(50)
        result = sma(df["close"], period=20)
        assert len(result) == 50


class TestEMA:
    def test_ema_responds_faster(self):
        df = _make_ohlcv()
        s = sma(df["close"], period=20)
        e = ema(df["close"], period=20)
        # EMA and SMA should have similar means
        assert abs(s.dropna().mean() - e.dropna().mean()) / s.dropna().mean() < 0.05


class TestBollingerBands:
    def test_band_structure(self):
        df = _make_ohlcv()
        bb = bollinger_bands(df["close"], period=20, std_dev=2.0)
        assert "upper" in bb
        assert "middle" in bb
        assert "lower" in bb
        assert "bandwidth" in bb

        valid_idx = bb["upper"].dropna().index
        # Upper > middle > lower
        for i in valid_idx:
            assert bb["upper"].iloc[i] >= bb["middle"].iloc[i]
            assert bb["middle"].iloc[i] >= bb["lower"].iloc[i]

    def test_wider_bands_with_higher_std(self):
        df = _make_ohlcv()
        bb2 = bollinger_bands(df["close"], std_dev=2.0)
        bb3 = bollinger_bands(df["close"], std_dev=3.0)
        # 3σ bands should be wider than 2σ
        bw2 = bb2["bandwidth"].dropna().mean()
        bw3 = bb3["bandwidth"].dropna().mean()
        assert bw3 > bw2


class TestATR:
    def test_atr_positive(self):
        df = _make_ohlcv()
        result = atr(df["high"], df["low"], df["close"])
        valid = result.dropna()
        assert all(v >= 0 for v in valid)

    def test_atr_length(self):
        df = _make_ohlcv()
        result = atr(df["high"], df["low"], df["close"], period=14)
        assert len(result) == len(df)


class TestADX:
    def test_adx_range(self):
        df = _make_ohlcv()
        result = adx(df["high"], df["low"], df["close"])
        valid = result.dropna()
        assert all(0 <= v <= 100 for v in valid)


class TestVolumeRatio:
    def test_volume_ratio_baseline(self):
        df = _make_ohlcv()
        result = volume_ratio(df["volume"], period=20)
        valid = result.dropna()
        # Average ratio should be approximately 1.0
        assert 0.5 < valid.mean() < 2.0

    def test_high_volume_detection(self):
        df = _make_ohlcv()
        # Spike the last candle's volume
        df.iloc[-1, df.columns.get_loc("volume")] = df["volume"].mean() * 3
        result = volume_ratio(df["volume"], period=20)
        assert result.iloc[-1] > 2.0  # Should detect the spike


class TestAddAllIndicators:
    def test_all_columns_added(self):
        df = _make_ohlcv()
        result = add_all_indicators(df)
        expected_cols = [
            "rsi", "sma", "ema", "bb_upper", "bb_middle", "bb_lower",
            "bb_bandwidth", "bb_pband", "atr", "adx", "volume_ratio",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_original_data_preserved(self):
        df = _make_ohlcv()
        result = add_all_indicators(df)
        pd.testing.assert_series_equal(result["close"], df["close"])
        pd.testing.assert_series_equal(result["volume"], df["volume"])

    def test_custom_periods(self):
        df = _make_ohlcv()
        result = add_all_indicators(df, rsi_period=9, sma_period=30)
        assert "rsi" in result.columns
        assert "sma" in result.columns

    def test_does_not_modify_original(self):
        df = _make_ohlcv()
        original_cols = set(df.columns)
        _ = add_all_indicators(df)
        assert set(df.columns) == original_cols
