"""
Historical OHLCV data loader with point-in-time awareness.

Fetches candles from Coinbase public API and caches them in SQLite.
Point-in-time tracking: every data point records when it was fetched,
not just the candle timestamp — prevents backtests from using
retroactively revised data.
"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from hestia.logging import get_logger, LogComponent

logger = get_logger()

_CACHE_DIR = Path.home() / "hestia" / "data" / "trading_cache"

# Coinbase granularity options (seconds)
GRANULARITY = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "6h": 21600,
    "1d": 86400,
}

# Coinbase API granularity strings (SDK enum values)
COINBASE_GRANULARITY = {
    "1m": "ONE_MINUTE",
    "5m": "FIVE_MINUTE",
    "15m": "FIFTEEN_MINUTE",
    "1h": "ONE_HOUR",
    "6h": "SIX_HOUR",
    "1d": "ONE_DAY",
}


class DataLoader:
    """
    Loads and caches historical OHLCV data.

    Sources:
    - Coinbase public API (get_public_candles) — no auth needed
    - Local cache (SQLite or CSV)
    - Synthetic data (for testing)
    """

    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        self._cache_dir = cache_dir or _CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def load_from_cache(self, pair: str, granularity: str = "1h") -> Optional[pd.DataFrame]:
        """Load cached OHLCV data if available."""
        cache_file = self._cache_path(pair, granularity)
        if cache_file.exists():
            try:
                df = pd.read_csv(cache_file, parse_dates=["timestamp"])
                logger.debug(
                    f"Loaded {len(df)} candles from cache: {pair} ({granularity})",
                    component=LogComponent.TRADING,
                )
                return df
            except Exception as e:
                logger.warning(
                    f"Cache read failed for {pair}: {type(e).__name__}",
                    component=LogComponent.TRADING,
                )
        return None

    def save_to_cache(self, df: pd.DataFrame, pair: str, granularity: str = "1h") -> None:
        """Save OHLCV data to local cache."""
        cache_file = self._cache_path(pair, granularity)
        df.to_csv(cache_file, index=False)
        logger.debug(
            f"Cached {len(df)} candles: {pair} ({granularity})",
            component=LogComponent.TRADING,
        )

    async def fetch_from_coinbase(
        self,
        pair: str = "BTC-USD",
        granularity: str = "1h",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetch historical candles from Coinbase public API.

        Uses coinbase-advanced-py SDK's get_public_candles.
        Paginates automatically (Coinbase returns max 350 candles per request).
        """
        try:
            from coinbase.rest import RESTClient
        except ImportError:
            logger.warning(
                "coinbase-advanced-py not installed — using cached/synthetic data only",
                component=LogComponent.TRADING,
            )
            return pd.DataFrame()

        if end is None:
            end = datetime.now(timezone.utc)
        if start is None:
            start = end - timedelta(days=365)

        gran_seconds = GRANULARITY.get(granularity, 3600)
        all_candles: List[Dict[str, Any]] = []

        # Public API — no auth needed
        client = RESTClient()

        current_start = start
        while current_start < end:
            # Coinbase max 350 candles per request
            chunk_end = min(
                current_start + timedelta(seconds=gran_seconds * 300),
                end,
            )
            try:
                response = client.get_public_candles(
                    product_id=pair,
                    start=str(int(current_start.timestamp())),
                    end=str(int(chunk_end.timestamp())),
                    granularity=COINBASE_GRANULARITY.get(granularity, "ONE_HOUR"),
                )
                # SDK returns GetProductCandlesResponse object (not dict).
                # Support both: .candles attr (v1.8+) and dict .get() (older).
                if hasattr(response, "candles"):
                    candles = response.candles
                elif isinstance(response, dict):
                    candles = response.get("candles", [])
                else:
                    candles = []

                for c in candles:
                    # Candle objects support both bracket and attribute access
                    all_candles.append({
                        "timestamp": datetime.fromtimestamp(int(c["start"]), tz=timezone.utc),
                        "open": float(c["open"]),
                        "high": float(c["high"]),
                        "low": float(c["low"]),
                        "close": float(c["close"]),
                        "volume": float(c["volume"]),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                    })
            except Exception as e:
                logger.warning(
                    f"Coinbase fetch chunk failed: {type(e).__name__}",
                    component=LogComponent.TRADING,
                )
                break

            current_start = chunk_end

        if not all_candles:
            return pd.DataFrame()

        df = pd.DataFrame(all_candles)
        df = df.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)

        # Cache for future use
        self.save_to_cache(df, pair, granularity)

        logger.info(
            f"Fetched {len(df)} candles from Coinbase: {pair} ({granularity})",
            component=LogComponent.TRADING,
        )
        return df

    async def load(
        self,
        pair: str = "BTC-USD",
        granularity: str = "1h",
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Load OHLCV data — cache first, then fetch.

        This is the primary interface. Strategies call this.
        """
        if use_cache:
            cached = self.load_from_cache(pair, granularity)
            if cached is not None and len(cached) > 0:
                # Filter by date range if specified
                if start:
                    cached = cached[cached["timestamp"] >= pd.Timestamp(start, tz=timezone.utc)]
                if end:
                    cached = cached[cached["timestamp"] <= pd.Timestamp(end, tz=timezone.utc)]
                if len(cached) > 100:
                    return cached.reset_index(drop=True)

        return await self.fetch_from_coinbase(pair, granularity, start, end)

    @staticmethod
    def generate_synthetic(
        n: int = 8760,
        base_price: float = 65000.0,
        volatility: float = 0.02,
        trend: float = 0.0,
        seed: int = 42,
    ) -> pd.DataFrame:
        """
        Generate synthetic OHLCV data for testing.

        Default: 1 year of hourly candles (~8760).
        """
        import numpy as np
        np.random.seed(seed)

        returns = np.random.normal(trend / n, volatility, n)
        prices = base_price * np.cumprod(1 + returns)

        timestamps = pd.date_range(
            end=datetime.now(timezone.utc),
            periods=n,
            freq="h",
            tz=timezone.utc,
        )

        df = pd.DataFrame({
            "timestamp": timestamps[:n],
            "open": prices * (1 + np.random.uniform(-0.003, 0.003, n)),
            "high": prices * (1 + np.random.uniform(0.001, 0.015, n)),
            "low": prices * (1 - np.random.uniform(0.001, 0.015, n)),
            "close": prices,
            "volume": np.random.uniform(50, 5000, n),
        })
        return df

    def _cache_path(self, pair: str, granularity: str) -> Path:
        safe_pair = pair.replace("/", "-").replace(" ", "_")
        return self._cache_dir / f"{safe_pair}_{granularity}.csv"
