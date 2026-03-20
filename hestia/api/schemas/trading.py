"""
Pydantic request/response schemas for trading API endpoints.
"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ── Request Models ────────────────────────────────────────────

class CreateBotRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Bot display name")
    strategy: Literal["grid", "mean_reversion", "signal_dca", "bollinger_breakout"] = Field(
        ..., description="Strategy type"
    )
    pair: str = Field(
        default="BTC-USD",
        pattern=r"^[A-Z]{2,10}-[A-Z]{2,10}$",
        description="Trading pair (e.g. BTC-USD)",
    )
    capital_allocated: float = Field(default=0.0, ge=0, description="Capital allocated in USD")
    config: Dict[str, Any] = Field(default_factory=dict, description="Strategy-specific configuration")


class UpdateBotRequest(BaseModel):
    name: Optional[str] = None
    strategy: Optional[str] = None
    pair: Optional[str] = None
    capital_allocated: Optional[float] = Field(default=None, ge=0)
    config: Optional[Dict[str, Any]] = None


class KillSwitchRequest(BaseModel):
    action: Literal["activate", "deactivate"] = Field(..., description="'activate' or 'deactivate'")
    reason: str = Field(default="Manual activation", description="Reason for kill switch")


# ── Response Models ───────────────────────────────────────────

class BotResponse(BaseModel):
    id: str
    name: str
    strategy: str
    pair: str
    status: str
    capital_allocated: float
    config: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class BotListResponse(BaseModel):
    bots: List[BotResponse]
    total: int


class TradeResponse(BaseModel):
    id: str
    bot_id: str
    side: str
    order_type: str
    price: float
    quantity: float
    fee: float
    pair: str
    tax_lot_id: Optional[str] = None
    timestamp: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TradeListResponse(BaseModel):
    trades: List[TradeResponse]
    total: int


class TaxLotResponse(BaseModel):
    id: str
    trade_id: str
    pair: str
    quantity: float
    remaining_quantity: float
    cost_basis: float
    cost_per_unit: float
    method: str
    status: str
    acquired_at: str
    closed_at: Optional[str] = None
    realized_pnl: float


class TaxLotListResponse(BaseModel):
    lots: List[TaxLotResponse]
    total: int


class DailySummaryResponse(BaseModel):
    id: str
    date: str
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_fees: float
    total_volume: float
    win_rate: float = 0.0
    positions: Dict[str, Any] = Field(default_factory=dict)
    strategy_attribution: Dict[str, Any] = Field(default_factory=dict)


class DailySummaryListResponse(BaseModel):
    summaries: List[DailySummaryResponse]
    total: int


class RiskStatusResponse(BaseModel):
    kill_switch: Dict[str, Any]
    circuit_breakers: Dict[str, Any]
    position_limits: Dict[str, Any]
    sizing: Dict[str, Any]
    tracking: Dict[str, Any]
    any_breaker_active: bool


class KillSwitchResponse(BaseModel):
    success: bool
    active: bool
    reason: Optional[str] = None


# ── Sprint 26: Trail, Watchlist, Feedback ────────────────────

class TradeTrailResponse(BaseModel):
    trade_id: str
    decision_trail: List[Dict[str, Any]]
    confidence_score: Optional[float] = None


class TradeFeedbackRequest(BaseModel):
    rating: Literal["positive", "negative", "neutral"]
    note: str = Field(default="")


class WatchlistItemRequest(BaseModel):
    pair: str = Field(..., pattern=r"^[A-Z]{2,10}-[A-Z]{2,10}$")
    notes: str = Field(default="")
    price_alerts: Dict[str, Any] = Field(default_factory=dict)


class WatchlistItemResponse(BaseModel):
    id: str
    pair: str
    notes: str
    price_alerts: Dict[str, Any] = Field(default_factory=dict)
    added_at: str


class WatchlistResponse(BaseModel):
    items: List[WatchlistItemResponse]
    total: int


# ── Sprint 31: Dashboard Summary ─────────────────────────────

class TradingSummaryResponse(BaseModel):
    """Lightweight summary for macOS Command Center progress rings."""

    active_bots: int = Field(default=0, description="Number of running bots")
    total_pnl: float = Field(default=0.0, description="Today's total P&L in USD")
    win_rate: float = Field(default=0.0, description="Today's win rate (0.0-1.0)")
    total_trades: int = Field(default=0, description="Today's trade count")
    kill_switch_active: bool = Field(default=False, description="Whether kill switch is engaged")
