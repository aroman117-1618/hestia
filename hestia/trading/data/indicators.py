"""
Technical indicator layer — wraps the `ta` library.

Provides RSI, SMA, EMA, Bollinger Bands, ATR, ADX, and volume
analysis. All indicators accept pandas DataFrames with OHLCV columns.

Strategies import from here, never from `ta` directly — allows
swapping the underlying library without touching strategy code.
"""

from typing import Optional

import pandas as pd
import ta.momentum
import ta.trend
import ta.volatility
import ta.volume


def rsi(close: pd.Series, period: int = 7) -> pd.Series:
    """
    Relative Strength Index.

    Crypto-optimized default: 7-period (not 14-period equity default).
    """
    return ta.momentum.RSIIndicator(close=close, window=period).rsi()


def sma(close: pd.Series, period: int = 50) -> pd.Series:
    """Simple Moving Average."""
    return ta.trend.SMAIndicator(close=close, window=period).sma_indicator()


def ema(close: pd.Series, period: int = 20) -> pd.Series:
    """Exponential Moving Average."""
    return ta.trend.EMAIndicator(close=close, window=period).ema_indicator()


def bollinger_bands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> dict:
    """
    Bollinger Bands (upper, middle, lower).

    Returns dict with keys: 'upper', 'middle', 'lower', 'bandwidth', 'pband'.
    """
    bb = ta.volatility.BollingerBands(
        close=close, window=period, window_dev=std_dev
    )
    return {
        "upper": bb.bollinger_hband(),
        "middle": bb.bollinger_mavg(),
        "lower": bb.bollinger_lband(),
        "bandwidth": bb.bollinger_wband(),
        "pband": bb.bollinger_pband(),
    }


def atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Average True Range — volatility measure."""
    return ta.volatility.AverageTrueRange(
        high=high, low=low, close=close, window=period
    ).average_true_range()


def adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """
    Average Directional Index — trend strength.

    ADX > 25 indicates a strong trend.
    """
    return ta.trend.ADXIndicator(
        high=high, low=low, close=close, window=period
    ).adx()


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """
    Volume relative to N-period average.

    Values > 1.5 indicate significant volume (confirmation signal).
    """
    avg = volume.rolling(window=period).mean()
    return volume / avg


def add_all_indicators(
    df: pd.DataFrame,
    rsi_period: int = 7,
    sma_period: int = 50,
    bb_period: int = 20,
    bb_std: float = 2.0,
    atr_period: int = 14,
    adx_period: int = 14,
    volume_period: int = 20,
) -> pd.DataFrame:
    """
    Add all standard indicators to an OHLCV DataFrame.

    Expects columns: open, high, low, close, volume.
    Returns DataFrame with additional indicator columns.
    """
    df = df.copy()

    # Momentum
    df["rsi"] = rsi(df["close"], rsi_period)

    # Trend
    df["sma"] = sma(df["close"], sma_period)
    df["ema"] = ema(df["close"], bb_period)

    # Volatility
    bb = bollinger_bands(df["close"], bb_period, bb_std)
    df["bb_upper"] = bb["upper"]
    df["bb_middle"] = bb["middle"]
    df["bb_lower"] = bb["lower"]
    df["bb_bandwidth"] = bb["bandwidth"]
    df["bb_pband"] = bb["pband"]
    df["atr"] = atr(df["high"], df["low"], df["close"], atr_period)

    # Trend strength
    df["adx"] = adx(df["high"], df["low"], df["close"], adx_period)

    # Volume
    df["volume_ratio"] = volume_ratio(df["volume"], volume_period)

    return df
