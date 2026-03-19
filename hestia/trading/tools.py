"""
Trading chat tools for registration with execution layer.

Provides Tool definitions for controlling autonomous trading via natural
language. Users can enable/disable trading, check status, manage bots,
and trigger the kill switch through conversation.

These tools are the "remote control" layer — the macOS dashboard is the
primary control plane. Both modify the same state (single source of truth).
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.execution.models import Tool, ToolParam, ToolParamType
from hestia.execution.registry import ToolRegistry


# ── Tool Handlers ────────────────────────────────────────────


async def trading_status() -> Dict[str, Any]:
    """Get current trading status — active bots, P&L, risk state."""
    from hestia.trading.manager import get_trading_manager

    manager = await get_trading_manager()
    bots = await manager.list_bots()
    risk = manager.get_risk_status()

    running = [b for b in bots if b.status.value == "running"]
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    summary = await manager.get_daily_summary(today)

    return {
        "autonomous_trading": len(running) > 0,
        "active_bots": len(running),
        "total_bots": len(bots),
        "bots": [
            {"name": b.name, "strategy": b.strategy.value if hasattr(b.strategy, 'value') else b.strategy,
             "pair": b.pair, "status": b.status.value}
            for b in bots
        ],
        "kill_switch_active": risk["kill_switch"]["active"],
        "any_breaker_active": risk["any_breaker_active"],
        "daily_pnl": summary["total_pnl"] if summary else 0.0,
        "daily_trades": summary["total_trades"] if summary else 0,
    }


async def trading_enable(
    strategy: str = "mean_reversion",
    pair: str = "BTC-USD",
    capital: float = 25.0,
) -> Dict[str, Any]:
    """Enable autonomous trading — creates and starts a bot."""
    from hestia.trading.manager import get_trading_manager
    from hestia.trading.orchestrator import get_bot_orchestrator

    manager = await get_trading_manager()

    # Check for existing running bots on the same pair
    bots = await manager.list_bots()
    existing = [b for b in bots if b.pair == pair and b.status.value == "running"]
    if existing:
        return {
            "success": False,
            "message": f"Already have a running bot on {pair}: {existing[0].name}. "
                       f"Stop it first with 'disable trading' or use a different pair.",
        }

    # Create and start bot
    bot = await manager.create_bot(
        name=f"{strategy.replace('_', ' ').title()} — {pair}",
        strategy=strategy,
        pair=pair,
        capital=capital,
    )
    await manager.start_bot(bot.id)

    # Launch the runner
    orchestrator = await get_bot_orchestrator()
    await orchestrator.start_runner(bot)

    return {
        "success": True,
        "bot_id": bot.id,
        "name": bot.name,
        "strategy": strategy,
        "pair": pair,
        "capital": capital,
        "message": f"Autonomous trading enabled! {bot.name} is now running with ${capital:.0f} "
                   f"allocated. Quarter-Kelly sizing, 5% daily loss limit. "
                   f"Say 'trading status' to check progress or 'disable trading' to stop.",
    }


async def trading_disable() -> Dict[str, Any]:
    """Disable all autonomous trading — stops bots, cancels open orders, keeps positions."""
    from hestia.trading.manager import get_trading_manager
    from hestia.trading.orchestrator import get_bot_orchestrator

    manager = await get_trading_manager()
    orchestrator = await get_bot_orchestrator()

    bots = await manager.list_bots()
    running = [b for b in bots if b.status.value == "running"]
    stopped_count = 0

    for bot in running:
        await manager.stop_bot(bot.id)
        await orchestrator.stop_runner(bot.id)
        stopped_count += 1

    return {
        "success": True,
        "stopped_count": stopped_count,
        "message": f"Autonomous trading disabled. Stopped {stopped_count} bot(s). "
                   f"Open orders cancelled, positions kept. "
                   f"Say 'enable trading' to resume.",
    }


async def trading_kill_switch() -> Dict[str, Any]:
    """EMERGENCY: Immediately halt ALL trading activity."""
    from hestia.trading.manager import get_trading_manager
    from hestia.trading.orchestrator import get_bot_orchestrator

    manager = await get_trading_manager()
    orchestrator = await get_bot_orchestrator()

    # Activate kill switch (persisted to DB — survives restarts)
    manager.activate_kill_switch("Emergency kill switch via chat")

    # Stop all runners
    await orchestrator.stop_all()

    # Stop all bots in DB
    bots = await manager.list_bots()
    for bot in bots:
        if bot.status.value == "running":
            await manager.stop_bot(bot.id)

    # Send critical alert
    try:
        from hestia.trading.alerts import get_trading_alerter
        alerter = await get_trading_alerter()
        await alerter.send_kill_switch_alert(active=True, reason="Chat command")
    except Exception:
        pass

    return {
        "success": True,
        "kill_switch_active": True,
        "message": "KILL SWITCH ACTIVATED. All trading halted immediately. "
                   "All bots stopped. All open orders cancelled. "
                   "To re-enable, deactivate the kill switch from the dashboard first.",
    }


async def trading_summary(days: int = 1) -> Dict[str, Any]:
    """Get trading summary for recent days."""
    from hestia.trading.manager import get_trading_manager

    manager = await get_trading_manager()
    summaries = await manager.get_daily_summaries(limit=days)
    trades = await manager.get_trades(limit=20)

    return {
        "summaries": summaries,
        "recent_trades": trades[:10],
        "trade_count": len(trades),
    }


# ── Tool Definitions ─────────────────────────────────────────


def get_trading_tools() -> List[Tool]:
    """Get trading control tools."""
    return [
        Tool(
            name="trading_status",
            description="Get current autonomous trading status — active bots, P&L, risk state, and kill switch status",
            parameters={},
            handler=trading_status,
            category="trading",
        ),
        Tool(
            name="trading_enable",
            description="Enable autonomous trading. Creates and starts a trading bot with the specified strategy and capital allocation. Use 'mean_reversion' for a single-position RSI strategy or 'grid' for geometric grid trading.",
            parameters={
                "strategy": ToolParam(
                    type=ToolParamType.STRING,
                    description="Trading strategy: 'mean_reversion' (recommended for small capital) or 'grid'",
                    required=False,
                    default="mean_reversion",
                    enum=["mean_reversion", "grid"],
                ),
                "pair": ToolParam(
                    type=ToolParamType.STRING,
                    description="Trading pair (default: BTC-USD)",
                    required=False,
                    default="BTC-USD",
                ),
                "capital": ToolParam(
                    type=ToolParamType.NUMBER,
                    description="Capital to allocate in USD (default: 25)",
                    required=False,
                    default=25.0,
                ),
            },
            handler=trading_enable,
            category="trading",
        ),
        Tool(
            name="trading_disable",
            description="Disable all autonomous trading. Stops all running bots, cancels open orders, but keeps existing positions. This is an orderly shutdown, not an emergency.",
            parameters={},
            handler=trading_disable,
            category="trading",
        ),
        Tool(
            name="trading_kill_switch",
            description="EMERGENCY kill switch — immediately halt ALL trading activity. Activates the persistent kill switch (survives server restarts), stops all bots, cancels all orders. Use only in emergencies.",
            parameters={},
            handler=trading_kill_switch,
            category="trading",
        ),
        Tool(
            name="trading_summary",
            description="Get a summary of recent trading activity — daily P&L, trade count, win rate, and recent trade details",
            parameters={
                "days": ToolParam(
                    type=ToolParamType.INTEGER,
                    description="Number of days to summarize (default: 1)",
                    required=False,
                    default=1,
                ),
            },
            handler=trading_summary,
            category="trading",
        ),
    ]


def register_trading_tools(registry: ToolRegistry) -> int:
    """Register trading tools with a tool registry."""
    tools = get_trading_tools()
    for tool in tools:
        registry.register(tool)
    return len(tools)
