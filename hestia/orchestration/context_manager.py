"""
Context slicing functions for specialist agents.

Lightweight module — pure functions, no state. Controls what context
each agent sees for efficiency and security.
"""

from typing import Any, Dict, List, Optional


# Apollo gets only the last N messages (recent context, not full history)
_APOLLO_MAX_HISTORY_MESSAGES = 6


def slice_context_for_artemis(
    memory_context: str,
    user_profile: str,
    conversation_history: List[Dict[str, str]],
    tool_instructions: str,
    cloud_safe: bool = False,
) -> Dict[str, Any]:
    """
    Build context slice for Artemis (analysis agent).

    Artemis gets: full history, memory, profile (unless cloud).
    Artemis does NOT get: tool definitions (she analyzes, not executes).
    """
    return {
        "memory": memory_context,
        "profile": "" if cloud_safe else user_profile,
        "history": conversation_history,
    }


def slice_context_for_apollo(
    conversation_history: List[Dict[str, str]],
    tool_instructions: str,
    artemis_output: Optional[str] = None,
    cloud_safe: bool = False,
) -> Dict[str, Any]:
    """
    Build context slice for Apollo (execution agent).

    Apollo gets: recent turns, tool defs, Artemis output (if chained).
    Apollo does NOT get: full history, full user profile.
    """
    recent = conversation_history[-_APOLLO_MAX_HISTORY_MESSAGES:]
    ctx: Dict[str, Any] = {
        "history": recent,
        "tool_instructions": tool_instructions,
    }
    if artemis_output:
        ctx["artemis_analysis"] = artemis_output
    return ctx


def slice_context_for_synthesis(
    agent_results: list,
    original_request: str,
    user_profile: str,
) -> Dict[str, Any]:
    """
    Build context slice for Hestia's synthesis step.

    Gets all agent outputs + original request. Used to combine
    specialist outputs into a coherent response with bylines.
    """
    return {
        "agent_results": agent_results,
        "original_request": original_request,
        "profile": user_profile,
    }
