"""
WebSocket protocol models for the CLI client.

Mirrors the server-side schemas in hestia/api/schemas/ws_chat.py
but as lightweight Pydantic models for client-side use.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ServerEventType(str, Enum):
    """Server-to-client event types."""
    AUTH_RESULT = "auth_result"
    STATUS = "status"
    TOKEN = "token"
    TOOL_REQUEST = "tool_request"
    TOOL_RESULT = "tool_result"
    DONE = "done"
    ERROR = "error"
    PONG = "pong"
    INSIGHT = "insight"
    CLEAR_STREAM = "clear_stream"
    TOOL_START = "tool_start"
    AGENTIC_DONE = "agentic_done"
    VERIFICATION = "verification"


class PipelineStage(str, Enum):
    """Pipeline stages for status display."""
    VALIDATING = "validating"
    MEMORY = "memory"
    BUILDING_PROMPT = "building_prompt"
    COUNCIL = "council"
    INFERENCE = "inference"
    TOOLS = "tools"
    CACHE_HIT = "cache_hit"


STAGE_LABELS: Dict[str, str] = {
    "validating": "Validating",
    "memory": "Searching memory",
    "building_prompt": "Building prompt",
    "council": "Classifying intent",
    "inference": "Generating",
    "tools": "Executing tools",
    "cache_hit": "Cache hit",
}


class AuthResult(BaseModel):
    """Parsed auth result from server."""
    success: bool
    device_id: Optional[str] = None
    error: Optional[str] = None
    trust_tiers: Optional[Dict[str, str]] = None


class ToolRequest(BaseModel):
    """Tool approval request from server."""
    call_id: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    tier: str = "execute"


class DoneMetrics(BaseModel):
    """Metrics from a completed response."""
    tokens_in: int = 0
    tokens_out: int = 0
    duration_ms: float = 0.0
    model: Optional[str] = None
    cached: bool = False
    cancelled: bool = False


class AgentTheme(BaseModel):
    """Agent visual identity for CLI rendering."""
    name: str = "tia"
    color_hex: str = "#FF9500"  # Default amber
    gradient_secondary: Optional[str] = None

    @classmethod
    def for_agent(cls, name: str) -> "AgentTheme":
        """Get default theme for a known agent."""
        themes = {
            "tia": cls(name="tia", color_hex="#FF9500", gradient_secondary="#FF6B00"),
            "olly": cls(name="olly", color_hex="#2D8B73", gradient_secondary="#1E6B56"),
            "mira": cls(name="mira", color_hex="#1C3A5F", gradient_secondary="#2A5A8F"),
        }
        return themes.get(name.lower(), cls(name=name))


# ── Thinking Animation Verbs (Sprint 11.5 B2) ────────────

COMMON_VERBS = [
    "Thinking", "Processing", "Considering", "Analyzing",
    "Contemplating", "Evaluating", "Computing", "Reasoning",
    "Deliberating", "Formulating", "Synthesizing", "Pondering",
    "Reflecting", "Working on it", "Chewing on this", "Piecing it together",
]

TIA_VERBS = [
    "Warming up", "Stoking the fire", "Brewing something", "Tending the hearth",
    "Stirring the pot", "Cooking up a response", "On it, boss",
    "Let me think about that", "One moment", "Almost there",
    "Reading the room", "Pulling threads", "Connecting dots", "Crunching this",
    "Filing through memories", "Working my magic",
]

OLLY_VERBS = [
    "Compiling thoughts", "Running diagnostics", "Parsing input",
    "Building response", "Optimizing", "Debugging the question",
    "Scanning codebase", "Tracing execution path", "Profiling options",
    "Linting the problem", "Refactoring my answer", "Stack unwinding",
    "GC pause", "Hot-loading context", "Resolving dependencies", "Deploying neurons",
]

MIRA_VERBS = [
    "Considering all angles", "Exploring possibilities", "Seeking clarity",
    "Meditating on this", "Questioning assumptions", "Examining the premise",
    "Finding the thread", "Unraveling layers", "Looking deeper",
    "Weighing perspectives", "Tracing the logic", "Mapping the terrain",
    "Searching for insight", "Opening a new door", "Sitting with the question",
    "Drawing connections",
]

FIRE_FRAMES = [
    "[red]🔥[/red]",
    "[bright_red]🔥[/bright_red]",
    "[yellow]🔥[/yellow]",
    "[bright_yellow]🔥[/bright_yellow]",
]

ASCII_FRAMES = ["◠", "◡", "○", "◉", "●", "◎"]


# ── Banner Startup Animation ──────────────────────────────

# Pixel font for "HESTIA" block letters (5 chars wide per letter)
_PIXEL_FONT: Dict[str, List[str]] = {
    "H": ["█   █", "█   █", "█████", "█   █", "█   █"],
    "E": ["█████", "█    ", "████ ", "█    ", "█████"],
    "S": [" ████", "█    ", " ███ ", "    █", "████ "],
    "T": ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    "I": ["█████", "  █  ", "  █  ", "  █  ", "█████"],
    "A": [" ███ ", "█   █", "█████", "█   █", "█   █"],
}


def build_hestia_text_rows() -> List[str]:
    """Assemble 'HESTIA' as 5 rows of pixel-font block text."""
    rows: List[str] = []
    for row_idx in range(5):
        parts = [_PIXEL_FONT[ch][row_idx] for ch in "HESTIA"]
        rows.append("  ".join(parts))
    return rows


# Ember positions per animation frame (each line 14 chars wide)
BANNER_EMBER_FRAMES: List[Tuple[str, str]] = [
    ("      ·  °    ", "       ·      "),
    ("        ° ·   ", "      ·       "),
    ("     °    ·   ", "        ·     "),
    ("       ·   °  ", "      ·       "),
    ("     ·  °     ", "       ·      "),
    ("       °  ·   ", "     ·        "),
]

# Flame tip color cycle (amber flicker)
BANNER_TIP_COLORS: List[str] = [
    "#FEE685", "#FFB900", "#FEE685", "#FF8904", "#FFB900", "#FF8904",
]

# Campfire shape components (14 chars wide each)
BANNER_FIRE_TIP: str = "      /\\      "
BANNER_FIRE_BODY: List[str] = [
    "     /  \\     ",
    "    / /\\ \\    ",
    "   / /  \\ \\   ",
    "  /_/    \\_\\  ",
]

# Campfire body gradient colors (top to bottom)
BANNER_FIRE_COLORS: List[str] = [
    "#FFB900",  # bright amber
    "#FF8904",  # dark amber
    "#E0A050",  # amber accent
    "#B7874A",  # brown base
]
