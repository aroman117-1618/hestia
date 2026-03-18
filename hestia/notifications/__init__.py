"""Intelligent Notification Relay — context-aware bumps to macOS or iPhone."""

from hestia.notifications.manager import (
    get_notification_manager,
    close_notification_manager,
)

__all__ = ["get_notification_manager", "close_notification_manager"]
