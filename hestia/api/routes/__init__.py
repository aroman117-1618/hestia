"""API routes package."""

from .health import router as health_router
from .chat import router as chat_router
from .mode import router as mode_router
from .memory import router as memory_router
from .sessions import router as sessions_router
from .tools import router as tools_router
from .auth import router as auth_router
from .tasks import router as tasks_router
from .proactive import router as proactive_router
from .orders import router as orders_router
from .agents import router as agents_router
from .user import router as user_router

__all__ = [
    "health_router",
    "chat_router",
    "mode_router",
    "memory_router",
    "sessions_router",
    "tools_router",
    "auth_router",
    "tasks_router",
    "proactive_router",
    "orders_router",
    "agents_router",
    "user_router",
]
