"""
User Settings module for profile and notification preferences.

Provides user profile management, settings, and push token registration.
"""

from .models import (
    UserProfile,
    UserSettings,
    PushNotificationSettings,
    QuietHours,
    PushToken,
    PushEnvironment,
)
from .database import UserDatabase, get_user_database, close_user_database
from .manager import UserManager, get_user_manager, close_user_manager

__all__ = [
    # Models
    "UserProfile",
    "UserSettings",
    "PushNotificationSettings",
    "QuietHours",
    "PushToken",
    "PushEnvironment",
    # Database
    "UserDatabase",
    "get_user_database",
    "close_user_database",
    # Manager
    "UserManager",
    "get_user_manager",
    "close_user_manager",
]
