"""
Investigation chat tools for registration with execution layer.

Provides Tool definitions for investigating URLs via chat.
These tools let the user say "investigate this: [url]" in conversation.
"""

from typing import Any, Dict, List, Optional

from ..execution.models import Tool, ToolParam, ToolParamType
from ..execution.registry import ToolRegistry


# ============================================================================
# Investigation Tool Handlers
# ============================================================================
# NOTE: Chat tools use user_id="default" because the execution layer doesn't
# propagate JWT claims into tool handlers. This is consistent with all other
# tools (health, etc.). API routes use device_id from JWT as user_id.
# A systemic fix would require changes to the execution framework.
# ============================================================================

async def investigate_url(
    url: str,
    depth: str = "standard",
) -> Dict[str, Any]:
    """Investigate a URL and return content analysis."""
    from .manager import get_investigate_manager

    manager = await get_investigate_manager()
    return await manager.investigate(url=url, depth=depth)


async def investigate_compare(
    urls: List[str],
    focus: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare content from multiple URLs."""
    from .manager import get_investigate_manager

    # Handle urls passed as various types
    if isinstance(urls, str):
        urls = [u.strip() for u in urls.split(",") if u.strip()]

    manager = await get_investigate_manager()
    return await manager.compare(urls=urls, focus=focus)


# ============================================================================
# Tool Definitions
# ============================================================================

def get_investigate_tools() -> List[Tool]:
    """Get investigation tools for chat."""
    return [
        Tool(
            name="investigate_url",
            description=(
                "Investigate a URL (article, YouTube video, or web page) — "
                "extracts content and provides research-quality analysis"
            ),
            parameters={
                "url": ToolParam(
                    type=ToolParamType.STRING,
                    description="The URL to investigate",
                    required=True,
                ),
                "depth": ToolParam(
                    type=ToolParamType.STRING,
                    description="Analysis depth: quick (summary), standard (full analysis), or deep (comprehensive with bias detection)",
                    required=False,
                    default="standard",
                    enum=["quick", "standard", "deep"],
                ),
            },
            handler=investigate_url,
            category="investigate",
            timeout=120.0,
        ),
        Tool(
            name="investigate_compare",
            description=(
                "Compare content from 2-5 URLs — investigates each and "
                "synthesizes a cross-source comparison"
            ),
            parameters={
                "urls": ToolParam(
                    type=ToolParamType.ARRAY,
                    description="List of 2-5 URLs to compare",
                    required=True,
                ),
                "focus": ToolParam(
                    type=ToolParamType.STRING,
                    description="Optional focus area for the comparison (e.g., 'economic impact', 'methodology')",
                    required=False,
                ),
            },
            handler=investigate_compare,
            category="investigate",
            timeout=300.0,
        ),
    ]


def register_investigate_tools(registry: ToolRegistry) -> int:
    """
    Register investigation tools with a tool registry.

    Args:
        registry: ToolRegistry to register tools with.

    Returns:
        Number of tools registered.
    """
    tools = get_investigate_tools()
    count = 0
    for tool in tools:
        registry.register(tool)
        count += 1
    return count
