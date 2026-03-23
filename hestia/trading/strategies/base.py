"""
Base strategy ABC — all strategies implement this interface.

Strategies analyze market data and produce signals. They never
place orders directly — the manager validates through the risk
framework first.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd


class SignalType(str, Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class Signal:
    """A trading signal produced by a strategy."""
    signal_type: SignalType = SignalType.HOLD
    pair: str = "BTC-USD"
    price: float = 0.0
    quantity: float = 0.0
    confidence: float = 0.0  # 0.0 to 1.0
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_actionable(self) -> bool:
        """Whether this signal should be acted on (not HOLD)."""
        return self.signal_type != SignalType.HOLD

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type.value,
            "pair": self.pair,
            "price": self.price,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "reason": self.reason,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    Strategies are stateless analyzers — they receive market data
    and return signals. The manager handles execution.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.pair = self.config.get("pair", "BTC-USD")

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name."""
        ...

    @property
    @abstractmethod
    def strategy_type(self) -> str:
        """Strategy type identifier (matches StrategyType enum)."""
        ...

    @abstractmethod
    def analyze(self, df: pd.DataFrame, portfolio_value: float, timestamp: Optional[datetime] = None) -> Signal:
        """
        Analyze market data and produce a signal.

        Args:
            df: OHLCV DataFrame with indicators already computed.
            portfolio_value: Current portfolio value for position sizing.
            timestamp: Simulation time for the current candle. When provided,
                strategies that use time-based gates (e.g. DCA interval) should
                use this instead of wall-clock time. Live trading passes None,
                which falls back to datetime.now(timezone.utc).

        Returns:
            Signal with buy/sell/hold recommendation.
        """
        ...

    def reset(self) -> None:
        """
        Reset any accumulated instance state between walk-forward windows.

        Called by the backtesting engine before each test window so that
        time-gated or stateful strategies (e.g. DCA interval tracking)
        start each window clean.  The default implementation is a no-op;
        subclasses with mutable state MUST override this.
        """

    def indicator_periods(self) -> Dict[str, int]:
        """
        Return strategy-specific indicator periods for the backtest engine.

        The engine calls add_all_indicators() with these values so
        that pre-computed indicators match what the strategy expects.
        Override in subclasses that use non-default periods.

        Keys: rsi_period, sma_period, bb_period, atr_period, adx_period.
        """
        return {}

    def validate_config(self) -> List[str]:
        """
        Validate strategy configuration. Returns list of warnings.

        Override in subclasses for strategy-specific validation.
        """
        return []
