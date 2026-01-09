"""
Orders module for scheduled recurring prompts.

Provides CRUD operations for orders and execution tracking.
Uses APScheduler for recurring execution scheduling.
"""

from .models import (
    Order,
    OrderExecution,
    OrderStatus,
    ExecutionStatus,
    OrderFrequency,
    FrequencyType,
    MCPResource,
)
from .database import OrderDatabase, get_order_database, close_order_database
from .manager import OrderManager, get_order_manager, close_order_manager
from .scheduler import OrderScheduler, get_order_scheduler, close_order_scheduler

__all__ = [
    # Models
    "Order",
    "OrderExecution",
    "OrderStatus",
    "ExecutionStatus",
    "OrderFrequency",
    "FrequencyType",
    "MCPResource",
    # Database
    "OrderDatabase",
    "get_order_database",
    "close_order_database",
    # Manager
    "OrderManager",
    "get_order_manager",
    "close_order_manager",
    # Scheduler
    "OrderScheduler",
    "get_order_scheduler",
    "close_order_scheduler",
]
