"""
Agent router — deterministic intent-to-route heuristic.

Maps council IntentClassification to AgentRoute decisions.
Primary routing mechanism: intent type + keyword analysis.
SLM does intent classification only (proven). This heuristic maps intent to route.
"""

from typing import Optional, Tuple

from hestia.council.models import IntentType
from hestia.orchestration.agent_models import AgentRoute, OrchestratorConfig


# Direct intent -> route mapping (no keyword analysis needed)
INTENT_ROUTE_MAP = {
    IntentType.MEMORY_SEARCH: AgentRoute.ARTEMIS,
    IntentType.CODING: AgentRoute.APOLLO,
    IntentType.CALENDAR_CREATE: AgentRoute.APOLLO,
    IntentType.REMINDER_CREATE: AgentRoute.APOLLO,
    IntentType.NOTE_CREATE: AgentRoute.APOLLO,
    IntentType.CALENDAR_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.REMINDER_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.NOTE_SEARCH: AgentRoute.HESTIA_SOLO,
    IntentType.MAIL_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.WEATHER_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.STOCKS_QUERY: AgentRoute.HESTIA_SOLO,
    IntentType.UNCLEAR: AgentRoute.HESTIA_SOLO,
    IntentType.MULTI_INTENT: AgentRoute.HESTIA_SOLO,
}


class AgentRouter:
    """Deterministic intent-to-route heuristic."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self._config = config

    def resolve(
        self, intent: IntentType, content: str
    ) -> Tuple[AgentRoute, float]:
        """
        Resolve an intent + content to an agent route and confidence.

        Returns:
            (AgentRoute, confidence) tuple.
        """
        if not self._config.enabled:
            return AgentRoute.HESTIA_SOLO, 1.0

        # Direct intent mapping (high confidence)
        if intent in INTENT_ROUTE_MAP:
            route = INTENT_ROUTE_MAP[intent]
            if route != AgentRoute.HESTIA_SOLO:
                return route, 0.9
            # For HESTIA_SOLO intents, only CHAT gets keyword escalation
            if intent != IntentType.CHAT:
                return route, 0.9

        # CHAT intent: keyword analysis
        content_lower = content.lower()
        has_analysis = self._has_keywords(content_lower, self._config.analysis_keywords)
        has_execution = self._has_keywords(content_lower, self._config.execution_keywords)

        if has_analysis and has_execution:
            return AgentRoute.ARTEMIS_THEN_APOLLO, 0.75
        elif has_analysis:
            return AgentRoute.ARTEMIS, 0.8
        elif has_execution:
            return AgentRoute.APOLLO, 0.8
        else:
            return AgentRoute.HESTIA_SOLO, 0.9

    def resolve_with_override(
        self,
        intent: IntentType,
        content: str,
        explicit_agent: Optional[str] = None,
    ) -> Tuple[AgentRoute, float]:
        """
        Resolve with optional explicit @mention override.

        If explicit_agent is set, it takes priority over heuristic.
        """
        if explicit_agent:
            agent_map = {
                "artemis": AgentRoute.ARTEMIS,
                "mira": AgentRoute.ARTEMIS,
                "apollo": AgentRoute.APOLLO,
                "olly": AgentRoute.APOLLO,
            }
            route = agent_map.get(explicit_agent.lower())
            if route:
                return route, 1.0

        return self.resolve(intent, content)

    def _has_keywords(self, content: str, keywords: list) -> bool:
        """Check if content contains any of the keywords."""
        return any(kw in content for kw in keywords)
