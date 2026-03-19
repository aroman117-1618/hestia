"""
Trading module data models.

Core dataclasses for bots, trades, tax lots, daily summaries,
and circuit breaker state.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class BotStatus(str, Enum):
    """Trading bot lifecycle states."""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class TradeSide(str, Enum):
    """Trade direction."""
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Order execution type."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class TaxLotMethod(str, Enum):
    """Cost-basis accounting method."""
    HIFO = "hifo"  # Highest In, First Out (tax-optimal)
    FIFO = "fifo"  # First In, First Out


class TaxLotStatus(str, Enum):
    """Tax lot lifecycle."""
    OPEN = "open"
    PARTIAL = "partial"
    CLOSED = "closed"


class CircuitBreakerState(str, Enum):
    """Circuit breaker operational state."""
    ARMED = "armed"       # Normal operation, monitoring
    TRIGGERED = "triggered"  # Breaker fired, trading paused
    COOLDOWN = "cooldown"   # Waiting to re-arm
    DISABLED = "disabled"   # Manually disabled


class CircuitBreakerType(str, Enum):
    """The 5-layer safety architecture breaker types."""
    DRAWDOWN = "drawdown"           # Layer 4: Portfolio drawdown
    DAILY_LOSS = "daily_loss"       # Layer 5: Daily loss limit
    LATENCY = "latency"             # Layer 6: API latency
    PRICE_DIVERGENCE = "price_divergence"  # Layer 7: Price feed mismatch
    WEEKLY_LOSS = "weekly_loss"     # Extended: Weekly loss


class AssetClass(str, Enum):
    """Supported asset classes for multi-asset trading."""
    CRYPTO = "crypto"
    US_EQUITY = "us_equity"


class StrategyType(str, Enum):
    """Available trading strategies."""
    GRID = "grid"
    MEAN_REVERSION = "mean_reversion"
    SIGNAL_DCA = "signal_dca"
    BOLLINGER_BREAKOUT = "bollinger_breakout"


@dataclass
class Bot:
    """A configured trading bot instance."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    strategy: StrategyType = StrategyType.GRID
    pair: str = "BTC-USD"
    status: BotStatus = BotStatus.CREATED
    capital_allocated: float = 0.0
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    asset_class: str = "crypto"
    user_id: str = "user-default"
    exchange: str = "coinbase"  # Exchange adapter name (coinbase, alpaca)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "strategy": self.strategy.value,
            "pair": self.pair,
            "status": self.status.value,
            "capital_allocated": self.capital_allocated,
            "config": self.config,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "asset_class": self.asset_class,
            "user_id": self.user_id,
            "exchange": self.exchange,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Bot":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", ""),
            strategy=StrategyType(data["strategy"]) if "strategy" in data else StrategyType.GRID,
            pair=data.get("pair", "BTC-USD"),
            status=BotStatus(data["status"]) if "status" in data else BotStatus.CREATED,
            capital_allocated=float(data.get("capital_allocated", 0.0)),
            config=data.get("config", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(timezone.utc),
            asset_class=data.get("asset_class", "crypto"),
            user_id=data.get("user_id", "user-default"),
            exchange=data.get("exchange", "coinbase"),
        )


@dataclass
class Trade:
    """A single executed trade (fill)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    bot_id: str = ""
    side: TradeSide = TradeSide.BUY
    order_type: OrderType = OrderType.LIMIT
    price: float = 0.0
    quantity: float = 0.0
    fee: float = 0.0
    fee_currency: str = "USD"
    pair: str = "BTC-USD"
    tax_lot_id: Optional[str] = None
    exchange_order_id: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    asset_class: str = "crypto"
    settlement_date: Optional[str] = None
    user_id: str = "user-default"

    @property
    def total_cost(self) -> float:
        """Total cost including fees."""
        return (self.price * self.quantity) + self.fee

    @property
    def net_value(self) -> float:
        """Net value after fees (for sells)."""
        return (self.price * self.quantity) - self.fee

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "bot_id": self.bot_id,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "price": self.price,
            "quantity": self.quantity,
            "fee": self.fee,
            "fee_currency": self.fee_currency,
            "pair": self.pair,
            "tax_lot_id": self.tax_lot_id,
            "exchange_order_id": self.exchange_order_id,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "asset_class": self.asset_class,
            "settlement_date": self.settlement_date,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Trade":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            bot_id=data.get("bot_id", ""),
            side=TradeSide(data["side"]) if "side" in data else TradeSide.BUY,
            order_type=OrderType(data["order_type"]) if "order_type" in data else OrderType.LIMIT,
            price=float(data.get("price", 0.0)),
            quantity=float(data.get("quantity", 0.0)),
            fee=float(data.get("fee", 0.0)),
            fee_currency=data.get("fee_currency", "USD"),
            pair=data.get("pair", "BTC-USD"),
            tax_lot_id=data.get("tax_lot_id"),
            exchange_order_id=data.get("exchange_order_id"),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(timezone.utc),
            metadata=data.get("metadata", {}),
            asset_class=data.get("asset_class", "crypto"),
            settlement_date=data.get("settlement_date"),
            user_id=data.get("user_id", "user-default"),
        )


@dataclass
class TaxLot:
    """
    A tax lot for cost-basis tracking (1099-DA compliant).

    Each buy creates a new lot. Sells consume lots based on the
    selected method (HIFO or FIFO).
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trade_id: str = ""  # The buy trade that created this lot
    pair: str = "BTC-USD"
    quantity: float = 0.0
    remaining_quantity: float = 0.0  # Decremented as lots are consumed
    cost_basis: float = 0.0  # Total cost including fees
    cost_per_unit: float = 0.0
    method: TaxLotMethod = TaxLotMethod.HIFO
    status: TaxLotStatus = TaxLotStatus.OPEN
    acquired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    closed_at: Optional[datetime] = None
    realized_pnl: float = 0.0  # P&L when lot is sold
    asset_class: str = "crypto"
    user_id: str = "user-default"

    @property
    def is_long_term(self) -> bool:
        """Whether this lot qualifies for long-term capital gains (>1 year)."""
        if self.closed_at is None:
            hold_time = datetime.now(timezone.utc) - self.acquired_at
        else:
            hold_time = self.closed_at - self.acquired_at
        return hold_time.days > 365

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "trade_id": self.trade_id,
            "pair": self.pair,
            "quantity": self.quantity,
            "remaining_quantity": self.remaining_quantity,
            "cost_basis": self.cost_basis,
            "cost_per_unit": self.cost_per_unit,
            "method": self.method.value,
            "status": self.status.value,
            "acquired_at": self.acquired_at.isoformat(),
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "realized_pnl": self.realized_pnl,
            "asset_class": self.asset_class,
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaxLot":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            trade_id=data.get("trade_id", ""),
            pair=data.get("pair", "BTC-USD"),
            quantity=float(data.get("quantity", 0.0)),
            remaining_quantity=float(data.get("remaining_quantity", 0.0)),
            cost_basis=float(data.get("cost_basis", 0.0)),
            cost_per_unit=float(data.get("cost_per_unit", 0.0)),
            method=TaxLotMethod(data["method"]) if "method" in data else TaxLotMethod.HIFO,
            status=TaxLotStatus(data["status"]) if "status" in data else TaxLotStatus.OPEN,
            acquired_at=datetime.fromisoformat(data["acquired_at"]) if "acquired_at" in data else datetime.now(timezone.utc),
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            realized_pnl=float(data.get("realized_pnl", 0.0)),
            asset_class=data.get("asset_class", "crypto"),
            user_id=data.get("user_id", "user-default"),
        )


@dataclass
class DailySummary:
    """Daily trading performance summary."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: str = ""  # YYYY-MM-DD
    total_pnl: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_fees: float = 0.0
    total_volume: float = 0.0
    positions: Dict[str, Any] = field(default_factory=dict)  # {pair: {qty, avg_price}}
    strategy_attribution: Dict[str, Any] = field(default_factory=dict)  # {strategy: pnl}
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: str = "user-default"

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.winning_trades / self.total_trades

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "date": self.date,
            "total_pnl": self.total_pnl,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "total_fees": self.total_fees,
            "total_volume": self.total_volume,
            "positions": self.positions,
            "strategy_attribution": self.strategy_attribution,
            "win_rate": self.win_rate,
            "created_at": self.created_at.isoformat(),
            "user_id": self.user_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DailySummary":
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            date=data.get("date", ""),
            total_pnl=float(data.get("total_pnl", 0.0)),
            realized_pnl=float(data.get("realized_pnl", 0.0)),
            unrealized_pnl=float(data.get("unrealized_pnl", 0.0)),
            total_trades=int(data.get("total_trades", 0)),
            winning_trades=int(data.get("winning_trades", 0)),
            losing_trades=int(data.get("losing_trades", 0)),
            total_fees=float(data.get("total_fees", 0.0)),
            total_volume=float(data.get("total_volume", 0.0)),
            positions=data.get("positions", {}),
            strategy_attribution=data.get("strategy_attribution", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc),
            user_id=data.get("user_id", "user-default"),
        )


@dataclass
class CircuitBreaker:
    """State tracking for a single circuit breaker."""
    breaker_type: CircuitBreakerType = CircuitBreakerType.DRAWDOWN
    state: CircuitBreakerState = CircuitBreakerState.ARMED
    threshold: float = 0.0
    current_value: float = 0.0
    triggered_at: Optional[datetime] = None
    cooldown_until: Optional[datetime] = None
    trigger_count: int = 0

    @property
    def is_blocking(self) -> bool:
        """Whether this breaker is currently preventing trading."""
        return self.state in (CircuitBreakerState.TRIGGERED, CircuitBreakerState.COOLDOWN)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "breaker_type": self.breaker_type.value,
            "state": self.state.value,
            "threshold": self.threshold,
            "current_value": self.current_value,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "cooldown_until": self.cooldown_until.isoformat() if self.cooldown_until else None,
            "trigger_count": self.trigger_count,
            "is_blocking": self.is_blocking,
        }


@dataclass
class ReconciliationResult:
    """Result of an exchange state reconciliation check."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    local_balance: float = 0.0
    exchange_balance: float = 0.0
    discrepancy: float = 0.0
    pair: str = "BTC-USD"
    resolved: bool = False
    notes: str = ""

    @property
    def has_discrepancy(self) -> bool:
        return abs(self.discrepancy) > 1e-8

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "local_balance": self.local_balance,
            "exchange_balance": self.exchange_balance,
            "discrepancy": self.discrepancy,
            "pair": self.pair,
            "resolved": self.resolved,
            "notes": self.notes,
            "has_discrepancy": self.has_discrepancy,
        }
