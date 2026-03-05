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
from .cloud import router as cloud_router
from .voice import router as voice_router
from .health_data import router as health_data_router
from .wiki import router as wiki_router
from .user_profile import router as user_profile_router
from .explorer import router as explorer_router
from .newsfeed import router as newsfeed_router
from .investigate import router as investigate_router
from .research import router as research_router
from .files import router as files_router
from .inbox import router as inbox_router
from .outcomes import router as outcomes_router
from .ws_chat import router as ws_chat_router

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
    "cloud_router",
    "voice_router",
    "health_data_router",
    "wiki_router",
    "user_profile_router",
    "explorer_router",
    "newsfeed_router",
    "investigate_router",
    "research_router",
    "files_router",
    "inbox_router",
    "outcomes_router",
    "ws_chat_router",
]
