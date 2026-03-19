"""
Trading API routes — bot CRUD, trade history, risk status, kill switch,
SSE streaming, positions, portfolio, watchlist, decision trails, feedback.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

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
    TradeFeedbackRequest,
    TradeListResponse,
    TradeTrailResponse,
    UpdateBotRequest,
    WatchlistItemRequest,
    WatchlistItemResponse,
    WatchlistResponse,
)
from hestia.logging import get_logger, LogComponent
from hestia.trading.event_bus import TradingEvent, TradingEventBus
from hestia.trading.manager import get_trading_manager

logger = get_logger()

# Module-level event bus singleton
_event_bus = TradingEventBus(max_queue_size=100)
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
    try:
        manager = await get_trading_manager()
        bot = await manager.get_bot(bot_id)
        if bot is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        return BotResponse(**bot.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get bot",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e), "bot_id": bot_id},
        )
        raise HTTPException(status_code=500, detail="Failed to get bot")


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
    try:
        manager = await get_trading_manager()
        updates = request.model_dump(exclude_none=True)
        bot = await manager.update_bot(bot_id, updates)
        if bot is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        return BotResponse(**bot.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to update bot",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e), "bot_id": bot_id},
        )
        raise HTTPException(status_code=500, detail="Failed to update bot")


@router.delete(
    "/bots/{bot_id}",
    summary="Stop and remove bot",
)
async def delete_bot(
    bot_id: str,
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        success = await manager.delete_bot(bot_id)
        if not success:
            raise HTTPException(status_code=404, detail="Bot not found")
        return {"success": True, "bot_id": bot_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to delete bot",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e), "bot_id": bot_id},
        )
        raise HTTPException(status_code=500, detail="Failed to delete bot")


@router.post(
    "/bots/{bot_id}/start",
    response_model=BotResponse,
    summary="Start a bot",
)
async def start_bot(
    bot_id: str,
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        bot = await manager.start_bot(bot_id)
        if bot is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        return BotResponse(**bot.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to start bot",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e), "bot_id": bot_id},
        )
        raise HTTPException(status_code=500, detail="Failed to start bot")


@router.post(
    "/bots/{bot_id}/stop",
    response_model=BotResponse,
    summary="Stop a bot",
)
async def stop_bot(
    bot_id: str,
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        bot = await manager.stop_bot(bot_id)
        if bot is None:
            raise HTTPException(status_code=404, detail="Bot not found")
        return BotResponse(**bot.to_dict())
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to stop bot",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e), "bot_id": bot_id},
        )
        raise HTTPException(status_code=500, detail="Failed to stop bot")


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


# ── SSE Streaming (Sprint 26) ────────────────────────────────

@router.get(
    "/stream",
    summary="SSE streaming for real-time trading updates",
    description="Long-lived SSE connection. Events: heartbeat, trade, position_update, risk_alert, portfolio_snapshot, kill_switch.",
)
async def trading_stream(
    device_id: str = Depends(get_device_token),
) -> StreamingResponse:
    async def event_generator():
        queue = _event_bus.subscribe()
        try:
            # Send initial portfolio snapshot
            try:
                manager = await get_trading_manager()
                snapshot = manager.get_risk_status()
                yield TradingEvent(
                    event_type="portfolio_snapshot",
                    data={"risk": snapshot, "kill_switch_active": snapshot["kill_switch"]["active"]},
                ).to_sse()
            except Exception:
                pass  # Non-fatal — snapshot is informational

            heartbeat_interval = 15
            last_heartbeat = asyncio.get_running_loop().time()

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=float(heartbeat_interval))
                    yield event.to_sse()
                except asyncio.TimeoutError:
                    now = asyncio.get_running_loop().time()
                    if now - last_heartbeat >= heartbeat_interval:
                        yield TradingEvent(event_type="heartbeat", data={}).to_sse()
                        last_heartbeat = now
        except asyncio.CancelledError:
            pass
        finally:
            _event_bus.unsubscribe(queue)
            logger.debug("SSE trading client disconnected", component=LogComponent.TRADING)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Positions & Portfolio (Sprint 26) ────────────────────────

@router.get(
    "/positions",
    summary="Get current open positions",
)
async def get_positions(
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        if not manager.exchange:
            return {"positions": {}, "total_exposure": 0.0}
        balances = await manager.exchange.get_balances()
        positions: Dict[str, Any] = {}
        for currency, balance in balances.items():
            if currency != "USD" and balance.total > 0:
                ticker = await manager.exchange.get_ticker(f"{currency}-USD")
                price = ticker.get("price", 0.0)
                positions[f"{currency}-USD"] = {
                    "currency": currency,
                    "quantity": balance.available,
                    "hold": balance.hold,
                    "price": price,
                    "value": balance.total * price,
                }
        total = sum(p["value"] for p in positions.values())
        return {"positions": positions, "total_exposure": total}
    except Exception as e:
        logger.error(
            "Failed to get positions",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get positions")


@router.get(
    "/portfolio",
    summary="Get portfolio overview",
)
async def get_portfolio(
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        if not manager.exchange:
            return {
                "total_value": 0.0, "cash": 0.0,
                "positions_value": 0.0, "daily_pnl": 0.0,
                "risk_status": manager.get_risk_status(),
            }
        balances = await manager.exchange.get_balances()
        cash_bal = balances.get("USD")
        cash_value = (cash_bal.available + cash_bal.hold) if cash_bal else 0.0

        positions_value = 0.0
        for currency, balance in balances.items():
            if currency != "USD" and balance.total > 0:
                ticker = await manager.exchange.get_ticker(f"{currency}-USD")
                positions_value += balance.total * ticker.get("price", 0.0)

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summary = await manager.get_daily_summary(today)
        daily_pnl = summary["total_pnl"] if summary else 0.0

        return {
            "total_value": cash_value + positions_value,
            "cash": cash_value,
            "positions_value": positions_value,
            "daily_pnl": daily_pnl,
            "risk_status": manager.get_risk_status(),
        }
    except Exception as e:
        logger.error(
            "Failed to get portfolio",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get portfolio")


# ── Decision Trail & Feedback (Sprint 26) ────────────────────

@router.get(
    "/trades/{trade_id}/trail",
    response_model=TradeTrailResponse,
    summary="Get decision trail for a trade",
)
async def get_trade_trail(
    trade_id: str,
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        trade = await manager._database.get_trade_by_id(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        return TradeTrailResponse(
            trade_id=trade_id,
            decision_trail=trade.get("decision_trail", []),
            confidence_score=trade.get("confidence_score"),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to get trade trail",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e), "trade_id": trade_id},
        )
        raise HTTPException(status_code=500, detail="Failed to get trade trail")


@router.post(
    "/trades/{trade_id}/feedback",
    summary="Submit user feedback on a trade",
)
async def submit_trade_feedback(
    trade_id: str,
    request: TradeFeedbackRequest,
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        trade = await manager._database.get_trade_by_id(trade_id)
        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")
        metadata = trade.get("metadata", {})
        metadata["user_feedback"] = {"rating": request.rating, "note": request.note}
        await manager._database.update_trade_metadata(trade_id, metadata)
        return {"success": True, "trade_id": trade_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to submit feedback",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e), "trade_id": trade_id},
        )
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


# ── Watchlist (Sprint 26) ────────────────────────────────────

@router.get(
    "/watchlist",
    response_model=WatchlistResponse,
    summary="Get watchlist items",
)
async def get_watchlist(
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        items = await manager._database.get_watchlist()
        return WatchlistResponse(
            items=[WatchlistItemResponse(**{k: v for k, v in i.items() if k != "user_id"}) for i in items],
            total=len(items),
        )
    except Exception as e:
        logger.error(
            "Failed to get watchlist",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to get watchlist")


@router.post(
    "/watchlist",
    response_model=WatchlistItemResponse,
    summary="Add item to watchlist",
)
async def add_to_watchlist(
    request: WatchlistItemRequest,
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        item = {
            "id": str(uuid.uuid4()),
            "pair": request.pair,
            "notes": request.notes,
            "price_alerts": json.dumps(request.price_alerts),
            "added_at": datetime.now(timezone.utc).isoformat(),
            "user_id": DEFAULT_USER_ID,
        }
        await manager._database.create_watchlist_item(item)
        return WatchlistItemResponse(
            id=item["id"], pair=item["pair"], notes=item["notes"],
            price_alerts=request.price_alerts, added_at=item["added_at"],
        )
    except Exception as e:
        logger.error(
            "Failed to add watchlist item",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to add to watchlist")


@router.delete("/watchlist/{item_id}", summary="Remove item from watchlist")
async def remove_from_watchlist(
    item_id: str,
    device_id: str = Depends(get_device_token),
):
    try:
        manager = await get_trading_manager()
        success = await manager._database.delete_watchlist_item(item_id)
        if not success:
            raise HTTPException(status_code=404, detail="Watchlist item not found")
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to remove watchlist item",
            component=LogComponent.TRADING,
            data={"error": sanitize_for_log(e)},
        )
        raise HTTPException(status_code=500, detail="Failed to remove from watchlist")


# POST alias for DELETE /watchlist/{item_id} — iOS/macOS APIClient.delete() is private
@router.post("/watchlist/{item_id}/delete", include_in_schema=False)
async def remove_from_watchlist_post(
    item_id: str,
    device_id: str = Depends(get_device_token),
):
    return await remove_from_watchlist(item_id, device_id=device_id)
