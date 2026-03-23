"""Trading alerts — Discord webhook + push notification integration.

Discord webhook URL stored in Keychain (per second-opinion review).
Rate limiting: max 1 msg/min per event type, batch consolidation.
Fully optional — fails silent if webhook not configured.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from hestia.logging import get_logger, LogComponent

logger = get_logger()

# Rate limiting: per event type, max 1 message per 60 seconds
RATE_LIMIT_SECONDS = 60.0


class TradingAlerter:
    """Delivers trading alerts via Discord webhook and push notifications.

    Webhook URL loaded from Keychain (key: discord-trading-webhook).
    Falls back silently if not configured.
    """

    def __init__(self) -> None:
        self._webhook_url: Optional[str] = None
        self._initialized = False
        self._last_sent: Dict[str, float] = {}  # event_type -> timestamp

    async def initialize(self) -> None:
        """Load Discord webhook URL from Keychain."""
        if self._initialized:
            return
        try:
            from hestia.security.credential_manager import get_credential_manager
            cred_mgr = get_credential_manager()
            self._webhook_url = cred_mgr.retrieve_operational("discord-trading-webhook")
            if self._webhook_url:
                logger.info(
                    "Discord trading webhook configured",
                    component=LogComponent.TRADING,
                )
            else:
                logger.debug(
                    "Discord webhook not configured — alerts will use push only",
                    component=LogComponent.TRADING,
                )
        except Exception as e:
            logger.debug(
                f"Discord webhook init skipped: {type(e).__name__}",
                component=LogComponent.TRADING,
            )
        self._initialized = True

    def _is_rate_limited(self, event_type: str) -> bool:
        """Check if this event type was sent recently."""
        last = self._last_sent.get(event_type, 0)
        return (time.time() - last) < RATE_LIMIT_SECONDS

    def _record_send(self, event_type: str) -> None:
        self._last_sent[event_type] = time.time()

    async def send_trade_alert(self, trade_data: Dict[str, Any]) -> None:
        """Alert on trade execution."""
        if self._is_rate_limited("trade"):
            return

        side = trade_data.get("side", "?").upper()
        pair = trade_data.get("pair", "?")
        qty = trade_data.get("quantity", 0)
        price = trade_data.get("price", 0)
        score = trade_data.get("confidence_score")

        title = f"Trade Executed: {side} {pair}"
        body = f"{qty:.6f} @ ${price:,.2f}"
        if score is not None:
            body += f" | Confidence: {score:.0%}"

        await self._send_discord(title, body, color=0x30D158 if side == "BUY" else 0xFF3B30)
        await self._send_push(title, body, priority="low")
        self._record_send("trade")

    async def send_risk_alert(self, breaker_type: str, reason: str) -> None:
        """Alert on circuit breaker trigger."""
        if self._is_rate_limited("risk_alert"):
            return

        title = f"Circuit Breaker: {breaker_type}"
        await self._send_discord(title, reason, color=0xFF9500)
        await self._send_push(title, reason, priority="high")
        self._record_send("risk_alert")

    async def send_kill_switch_alert(self, active: bool, reason: str = "") -> None:
        """Alert on kill switch change — always delivered (bypasses rate limit)."""
        action = "ACTIVATED" if active else "DEACTIVATED"
        title = f"Kill Switch {action}"
        body = reason or "No reason provided"

        await self._send_discord(title, body, color=0xFF3B30 if active else 0x30D158)
        await self._send_push(title, body, priority="critical")
        # Kill switch bypasses rate limiting

    async def send_daily_summary(self, summary: Dict[str, Any]) -> None:
        """Send daily trading summary."""
        pnl = summary.get("total_pnl", 0)
        trades = summary.get("total_trades", 0)
        win_rate = summary.get("win_rate", 0)

        title = "Daily Trading Summary"
        body = (
            f"P&L: ${pnl:+,.2f} | Trades: {trades} | "
            f"Win Rate: {win_rate:.0%}"
        )
        color = 0x30D158 if pnl >= 0 else 0xFF3B30

        await self._send_discord(title, body, color=color)
        await self._send_push(title, body, priority="low")

    # ── Discord Webhook ──────────────────────────────────────

    async def _send_discord(
        self, title: str, body: str, color: int = 0xFFD60A
    ) -> None:
        """Send a Discord embed via webhook. Fails silent."""
        if not self._webhook_url:
            return
        try:
            import aiohttp
            payload = {
                "embeds": [{
                    "title": title,
                    "description": body,
                    "color": color,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "footer": {"text": "Hestia Trading"},
                }],
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self._webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status >= 400:
                        logger.warning(
                            f"Discord webhook returned {resp.status}",
                            component=LogComponent.TRADING,
                        )
        except ImportError:
            logger.debug("aiohttp not installed — Discord alerts unavailable",
                        component=LogComponent.TRADING)
        except Exception as e:
            logger.debug(
                f"Discord alert failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )

    # ── Push Notifications ───────────────────────────────────

    async def _send_push(
        self, title: str, body: str, priority: str = "medium"
    ) -> None:
        """Send push notification via Hestia's notification system. Fails silent."""
        try:
            from hestia.notifications import get_notification_manager
            mgr = await get_notification_manager()
            await mgr.create_bump(
                title=title,
                body=body,
                priority=priority,
                context={"source": "trading"},
            )
        except Exception as e:
            logger.debug(
                f"Push notification failed: {type(e).__name__}",
                component=LogComponent.TRADING,
            )


# Module-level singleton
_instance: Optional[TradingAlerter] = None


async def get_trading_alerter() -> TradingAlerter:
    """Singleton factory for TradingAlerter."""
    global _instance
    if _instance is None:
        _instance = TradingAlerter()
        await _instance.initialize()
    return _instance
