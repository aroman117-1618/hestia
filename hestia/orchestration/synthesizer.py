"""
Result synthesis and byline generation for agent orchestrator.

Lightweight module — pure functions, no state. Combines specialist
outputs into coherent responses with attribution bylines.
"""

from typing import List, Tuple

from hestia.orchestration.agent_models import (
    AgentByline,
    AgentResult,
    AgentRoute,
    AGENT_DISPLAY_NAMES,
)


def generate_bylines(results: List[AgentResult]) -> List[AgentByline]:
    """
    Generate attribution bylines for specialist agent results.

    Hestia-solo results produce no bylines (she IS the interface).
    """
    bylines = []
    for result in results:
        if result.agent_id == AgentRoute.HESTIA_SOLO:
            continue

        contribution = _infer_contribution_type(result)
        summary = _summarize_contribution(result)

        bylines.append(AgentByline(
            agent=result.agent_id,
            contribution_type=contribution,
            summary=summary,
        ))
    return bylines


def synthesize_single_agent(
    result: AgentResult, original_request: str
) -> Tuple[str, List[AgentByline]]:
    """
    Synthesize response from a single specialist agent.

    Returns (content, bylines). For Hestia-solo, bylines is empty.
    """
    bylines = generate_bylines([result])
    return result.content, bylines


def synthesize_multi_agent(
    results: List[AgentResult], original_request: str
) -> Tuple[str, List[AgentByline]]:
    """
    Synthesize response from multiple specialist agents.

    Combines outputs with clear section separation. Returns (content, bylines).
    """
    if not results:
        return "", []

    bylines = generate_bylines(results)

    # Combine outputs with separator
    parts = []
    for result in results:
        if result.content.strip():
            parts.append(result.content.strip())

    content = "\n\n".join(parts)
    return content, bylines


def format_byline_footer(bylines: List[AgentByline]) -> str:
    """Format bylines as a footer appended to response content."""
    if not bylines:
        return ""
    lines = [byline.format() for byline in bylines]
    return "\n\n---\n" + "\n".join(lines)


def _infer_contribution_type(result: AgentResult) -> str:
    """Infer the contribution type from the agent and content."""
    if result.agent_id == AgentRoute.ARTEMIS:
        return "analysis"
    elif result.agent_id == AgentRoute.APOLLO:
        if result.tool_calls:
            return "tool_result"
        return "implementation"
    return "response"


def _summarize_contribution(result: AgentResult) -> str:
    """Generate a one-line summary of the contribution."""
    content_preview = result.content[:80].replace("\n", " ").strip()
    if len(result.content) > 80:
        content_preview += "..."
    if result.agent_id == AgentRoute.ARTEMIS:
        return f"analyzed: {content_preview}"
    elif result.agent_id == AgentRoute.APOLLO:
        return f"executed: {content_preview}"
    return content_preview
