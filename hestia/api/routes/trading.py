"""
Trading API routes — bot CRUD, trade history, risk status, kill switch.

NOTE: These routes are NOT registered in server.py yet.
Registration deferred to merge time (concurrent session guardrail).
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from hestia.api.errors import sanitize_for_log
from hestia.api.middleware.auth import get_device_token
from hestia.api.schemas.trading import (
    BotListResponse,
    BotResponse,
    CreateBotRequest,
    DailySummaryListResponse,
    DailySummaryResponse,
    KillSwitchRequest,
    KillSwitchResponse,
    RiskStatusResponse,
    TaxLotListResponse,
    TradeListResponse,
    UpdateBotRequest,
)
from hestia.logging import get_logger, LogComponent
from hestia.trading.manager import get_trading_manager

logger = get_logger()
router = APIRouter(prefix="/v1/trading", tags=["trading"])

DEFAULT_USER_ID = "user-default"


# ── Bot CRUD ──────────────────────────────────────────────────

@router.post(
    "/bots",
    response_model=BotResponse,
    summary="Create trading bot",
    description="Create a new trading bot with strategy and capital allocation.",
)
async def create_bot(
    request: CreateBotRequest,
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        bot = await manager.create_bot(
            name=request.name,
            strategy=request.strategy,
            pair=request.pair,
            capital=request.capital_allocated,
            config=request.config,
        )
        return BotResponse(**bot.to_dict())
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid strategy or configuration")
    except Exception as e:
        logger.error(
            "Failed to create bot",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to create bot")


@router.get(
    "/bots",
    response_model=BotListResponse,
    summary="List trading bots",
)
async def list_bots(
    status: Optional[str] = Query(None, description="Filter by status"),
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        bots = await manager.list_bots(user_id=DEFAULT_USER_ID, status=status)
        return BotListResponse(
            bots=[BotResponse(**b.to_dict()) for b in bots],
            total=len(bots),
        )
    except Exception as e:
        logger.error(
            "Failed to list bots",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to list bots")


@router.get(
    "/bots/{bot_id}",
    response_model=BotResponse,
    summary="Get bot details",
)
async def get_bot(
    bot_id: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    bot = await manager.get_bot(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse(**bot.to_dict())


@router.put(
    "/bots/{bot_id}",
    response_model=BotResponse,
    summary="Update bot configuration",
)
async def update_bot(
    bot_id: str,
    request: UpdateBotRequest,
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    updates = request.model_dump(exclude_none=True)
    bot = await manager.update_bot(bot_id, updates)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse(**bot.to_dict())


@router.delete(
    "/bots/{bot_id}",
    summary="Stop and remove bot",
)
async def delete_bot(
    bot_id: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    success = await manager.delete_bot(bot_id)
    if not success:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"success": True, "bot_id": bot_id}


@router.post(
    "/bots/{bot_id}/start",
    response_model=BotResponse,
    summary="Start a bot",
)
async def start_bot(
    bot_id: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    bot = await manager.start_bot(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse(**bot.to_dict())


@router.post(
    "/bots/{bot_id}/stop",
    response_model=BotResponse,
    summary="Stop a bot",
)
async def stop_bot(
    bot_id: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    bot = await manager.stop_bot(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse(**bot.to_dict())


# ── Trade History ─────────────────────────────────────────────

@router.get(
    "/trades",
    response_model=TradeListResponse,
    summary="Get trade history",
)
async def get_trades(
    bot_id: Optional[str] = Query(None, description="Filter by bot ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    trades = await manager.get_trades(bot_id=bot_id, limit=limit, offset=offset)
    total = await manager.get_trade_count(bot_id=bot_id)
    return TradeListResponse(trades=trades, total=total)


# ── Tax Lots ──────────────────────────────────────────────────

@router.get(
    "/tax/lots",
    response_model=TaxLotListResponse,
    summary="Get tax lot details (1099-DA ready)",
)
async def get_tax_lots(
    status: Optional[str] = Query(None, description="Filter by status: open, partial, closed"),
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    lots = await manager.get_tax_lots(status=status)
    return TaxLotListResponse(lots=lots, total=len(lots))


# ── Daily Summary ─────────────────────────────────────────────

@router.get(
    "/daily-summary",
    response_model=DailySummaryListResponse,
    summary="Get daily trading summaries",
)
async def get_daily_summaries(
    limit: int = Query(30, ge=1, le=365),
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    summaries = await manager.get_daily_summaries(limit=limit)
    return DailySummaryListResponse(summaries=summaries, total=len(summaries))


@router.get(
    "/daily-summary/{date}",
    response_model=DailySummaryResponse,
    summary="Get daily summary for a specific date",
)
async def get_daily_summary(
    date: str,
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    summary = await manager.get_daily_summary(date)
    if summary is None:
        raise HTTPException(status_code=404, detail="No summary for this date")
    return DailySummaryResponse(**summary)


# ── Risk Management ───────────────────────────────────────────

@router.get(
    "/risk/status",
    response_model=RiskStatusResponse,
    summary="Get risk manager status",
    description="Shows circuit breaker states, position limits, and kill switch status.",
)
async def get_risk_status(
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    return RiskStatusResponse(**manager.get_risk_status())


@router.post(
    "/kill-switch",
    response_model=KillSwitchResponse,
    summary="Activate or deactivate kill switch",
    description="Emergency halt (activate) or resume (deactivate) all trading.",
)
async def kill_switch(
    request: KillSwitchRequest,
    device_id: str = Depends(get_device_token),
):
    manager = await get_trading_manager()
    if request.action == "activate":
        manager.activate_kill_switch(request.reason)
        return KillSwitchResponse(success=True, active=True, reason=request.reason)
    elif request.action == "deactivate":
        manager.deactivate_kill_switch()
        return KillSwitchResponse(success=True, active=False)
    else:
        raise HTTPException(status_code=400, detail="Action must be 'activate' or 'deactivate'")


# ── Backtesting ───────────────────────────────────────────────

@router.post(
    "/backtest",
    summary="Run a backtest",
    description="Run a strategy against historical data with realistic fee/slippage modeling.",
)
async def run_backtest(
    strategy: str = Query(..., description="Strategy type: grid, mean_reversion"),
    pair: str = Query("BTC-USD"),
    days: int = Query(365, ge=30, le=730),
    capital: float = Query(250.0, ge=10),
    device_id: str = Depends(get_device_token),
):
    from hestia.trading.backtest.data_loader import DataLoader
    from hestia.trading.backtest.engine import BacktestConfig, BacktestEngine
    from hestia.trading.strategies.grid import GridStrategy
    from hestia.trading.strategies.mean_reversion import MeanReversionStrategy

    strategies_map = {
        "grid": GridStrategy,
        "mean_reversion": MeanReversionStrategy,
    }

    if strategy not in strategies_map:
        raise HTTPException(status_code=400, detail=f"Unknown strategy: {strategy}")

    try:
        loader = DataLoader()
        data = loader.generate_synthetic(n=days * 24)  # Hourly candles

        strat = strategies_map[strategy]()
        engine = BacktestEngine(BacktestConfig(pair=pair, initial_capital=capital))
        result = engine.run(strat, data)

        return result.to_dict()
    except Exception as e:
        logger.error(
            "Backtest failed",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Backtest execution failed")
