"""
NotificationManager — singleton orchestrator for the notification relay.

Coordinates routing decisions, macOS/APNs delivery, rate limiting,
and bump lifecycle management.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger
from hestia.logging.structured_logger import LogComponent
from hestia.notifications.apns_client import APNsClient, create_apns_client_from_keychain
from hestia.notifications.database import NotificationDatabase
from hestia.notifications.macos_notifier import send_macos_notification
from hestia.notifications.models import (
    BumpRequest,
    BumpStatus,
    NotificationRoute,
    NotificationSettings,
)
from hestia.notifications.router import NotificationRouter

logger = get_logger()


class NotificationManager:
    """Manages the intelligent notification relay system."""

    def __init__(self) -> None:
        self._database: Optional[NotificationDatabase] = None
        self._router: Optional[NotificationRouter] = None
        self._apns_client: Optional[APNsClient] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize database, router, and APNs client."""
        self._database = NotificationDatabase()
        await self._database.connect()
        self._router = NotificationRouter(self._database)

        # Try to initialize APNs (optional — works without it)
        try:
            self._apns_client = await create_apns_client_from_keychain()
        except Exception as e:
            logger.warning(
                "APNs client init failed, iPhone push disabled",
                component=LogComponent.NOTIFICATION,
                data={"error": type(e).__name__},
            )

        self._initialized = True
        logger.info(
            "NotificationManager initialized",
            component=LogComponent.NOTIFICATION,
            data={"apns_available": self._apns_client is not None},
        )

    async def close(self) -> None:
        """Shut down the notification manager."""
        if self._database:
            await self._database.close()
            self._database = None
        self._router = None
        self._apns_client = None
        self._initialized = False

    @property
    def database(self) -> NotificationDatabase:
        """Get the database, raising if not initialized."""
        if self._database is None:
            raise RuntimeError("NotificationManager not initialized")
        return self._database

    # ── Bump Lifecycle ─────────────────────────────────────────

    async def create_bump(
        self,
        title: str,
        body: Optional[str] = None,
        priority: str = "medium",
        actions: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        user_id: str = "default",
    ) -> Dict[str, Any]:
        """Create, route, and deliver a bump notification.

        Returns dict with callback_id, status, and route.
        """
        if not self._database or not self._router:
            return {"error": "not_initialized"}

        # Expire stale bumps first
        settings = await self._database.get_settings(user_id)
        expired_count = await self._database.expire_old_bumps(
            settings.bump_expiry_seconds
        )
        if expired_count:
            logger.info(
                "Expired stale bumps",
                component=LogComponent.NOTIFICATION,
                data={"count": expired_count},
            )

        # Create the bump request
        bump = BumpRequest.create(
            title=title,
            body=body,
            priority=priority,
            actions=actions,
            context=context,
            session_id=session_id,
            user_id=user_id,
        )
        await self._database.create_bump(bump)

        # Route the notification
        route, reason = await self._router.route(bump, settings)
        bump.route = route
        await self._database.update_bump_route(bump.callback_id, route)

        logger.info(
            "Bump routed",
            component=LogComponent.NOTIFICATION,
            data={
                "callback_id": bump.callback_id,
                "route": route.value,
                "reason": reason,
                "priority": priority,
            },
        )

        # Deliver based on route
        delivered = False
        if route == NotificationRoute.MACOS:
            delivered = await self._deliver_macos(bump, settings)
        elif route == NotificationRoute.APNS:
            delivered = await self._deliver_apns(bump, user_id)
            # Fallback to macOS if APNs fails
            if not delivered:
                delivered = await self._deliver_macos(bump, settings)
                if delivered:
                    await self._database.update_bump_route(
                        bump.callback_id, NotificationRoute.MACOS
                    )
        elif route == NotificationRoute.SUPPRESSED:
            # Mark as expired since it won't be delivered
            await self._database.update_bump_status(
                bump.callback_id, BumpStatus.EXPIRED
            )

        return {
            "callbackId": bump.callback_id,
            "status": bump.status.value,
            "route": route.value,
            "reason": reason,
            "delivered": delivered,
        }

    async def get_bump_status(self, callback_id: str) -> Optional[Dict[str, Any]]:
        """Get current status of a bump request."""
        if not self._database:
            return None

        bump = await self._database.get_bump_by_callback(callback_id)
        if not bump:
            return None

        return {
            "callbackId": bump.callback_id,
            "status": bump.status.value,
            "route": bump.route.value if bump.route else None,
            "responseAction": bump.response_action,
            "createdAt": bump.created_at.isoformat(),
            "respondedAt": bump.responded_at.isoformat() if bump.responded_at else None,
        }

    async def respond_to_bump(
        self,
        callback_id: str,
        action: str,
    ) -> Optional[Dict[str, Any]]:
        """Record a user response to a bump request.

        Args:
            callback_id: The bump callback ID.
            action: The chosen action (e.g., "approve", "deny").

        Returns:
            Updated bump status dict, or None if not found.
        """
        if not self._database:
            return None

        bump = await self._database.get_bump_by_callback(callback_id)
        if not bump:
            return None

        if bump.status != BumpStatus.PENDING:
            return {
                "callbackId": callback_id,
                "status": bump.status.value,
                "error": "already_responded",
            }

        # Validate action against bump's declared actions
        if action not in bump.actions:
            return {
                "callbackId": callback_id,
                "status": bump.status.value,
                "error": "invalid_action",
            }

        # Map action to status
        status = BumpStatus.APPROVED if action == "approve" else BumpStatus.DENIED
        await self._database.update_bump_status(
            callback_id, status, response_action=action
        )

        logger.info(
            "Bump responded",
            component=LogComponent.NOTIFICATION,
            data={
                "callback_id": callback_id,
                "action": action,
                "status": status.value,
            },
        )

        return {
            "callbackId": callback_id,
            "status": status.value,
            "responseAction": action,
        }

    async def list_bumps(
        self,
        user_id: str = "default",
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List bump requests with optional status filter."""
        if not self._database:
            return {"bumps": [], "total": 0}

        bump_status = BumpStatus(status) if status else None
        bumps = await self._database.list_bumps(
            user_id=user_id, status=bump_status, limit=limit, offset=offset
        )
        total = await self._database.count_bumps(
            user_id=user_id, status=bump_status
        )

        return {
            "bumps": [b.to_dict() for b in bumps],
            "total": total,
        }

    # ── Settings ───────────────────────────────────────────────

    async def get_settings(self, user_id: str = "default") -> Dict[str, Any]:
        """Get notification settings."""
        if not self._database:
            return NotificationSettings().to_dict()
        settings = await self._database.get_settings(user_id)
        return settings.to_dict()

    async def update_settings(
        self, user_id: str, updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update notification settings."""
        if not self._database:
            return {"error": "not_initialized"}

        settings = await self._database.get_settings(user_id)

        # Apply updates
        field_map = {
            "idleThresholdSeconds": "idle_threshold_seconds",
            "rateLimitSeconds": "rate_limit_seconds",
            "batchWindowSeconds": "batch_window_seconds",
            "bumpExpirySeconds": "bump_expiry_seconds",
            "quietHoursEnabled": "quiet_hours_enabled",
            "quietHoursStart": "quiet_hours_start",
            "quietHoursEnd": "quiet_hours_end",
            "focusModeRespect": "focus_mode_respect",
            "sessionCooldownSeconds": "session_cooldown_seconds",
        }
        for camel_key, snake_key in field_map.items():
            if camel_key in updates:
                setattr(settings, snake_key, updates[camel_key])

        await self._database.save_settings(settings)
        return settings.to_dict()

    # ── Delivery Helpers ───────────────────────────────────────

    async def _deliver_macos(
        self, bump: BumpRequest, settings: NotificationSettings
    ) -> bool:
        """Deliver a bump via macOS notification center."""
        # Check if we should batch
        if self._router and await self._router.should_batch(bump, settings):
            pending = await self._database.get_pending_bumps_in_window(
                bump.user_id, settings.batch_window_seconds
            )
            count = len(pending)
            return await send_macos_notification(
                title="Hestia",
                body=f"{count} items need your attention",
                subtitle="Multiple requests pending",
            )

        return await send_macos_notification(
            title=f"Hestia: {bump.title}",
            body=bump.body or "",
            subtitle=bump.session_id or "",
        )

    async def _deliver_apns(self, bump: BumpRequest, user_id: str) -> bool:
        """Deliver a bump via APNs push to iPhone."""
        if not self._apns_client:
            logger.info(
                "APNs not available, skipping iPhone push",
                component=LogComponent.NOTIFICATION,
            )
            return False

        # Get the user's push token
        try:
            from hestia.user.manager import get_user_manager
            user_manager = await get_user_manager()
            # Get all push tokens for this user's devices
            tokens = await user_manager.database.list_push_tokens()
            if not tokens:
                logger.info(
                    "No push tokens registered, skipping APNs",
                    component=LogComponent.NOTIFICATION,
                )
                return False

            # Send to the most recently used token
            token = sorted(tokens, key=lambda t: t.last_used_at or "", reverse=True)[0]
            return await self._apns_client.send_actionable_bump(
                device_token=token.push_token,
                callback_id=bump.callback_id,
                title=bump.title,
                body=bump.body or "",
                actions=bump.actions,
            )

        except Exception as e:
            logger.warning(
                "APNs delivery failed",
                component=LogComponent.NOTIFICATION,
                data={"error": type(e).__name__},
            )
            return False


# ── Singleton Factory ──────────────────────────────────────────

_notification_manager: Optional[NotificationManager] = None


async def get_notification_manager() -> NotificationManager:
    """Get or create the NotificationManager singleton."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
        await _notification_manager.initialize()
    return _notification_manager


async def close_notification_manager() -> None:
    """Shut down the NotificationManager singleton."""
    global _notification_manager
    if _notification_manager:
        await _notification_manager.close()
        _notification_manager = None
