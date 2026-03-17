"""
Orchestration planner — builds execution plans from routing decisions.

Handles confidence gating, chain validation, and plan collapsing.
Plans are data structures that the executor interprets.
"""

from typing import List, Optional

from hestia.orchestration.agent_models import (
    AgentRoute,
    AgentTask,
    ExecutionPlan,
    ExecutionStep,
    OrchestratorConfig,
)
from hestia.orchestration.context_manager import (
    slice_context_for_artemis,
    slice_context_for_apollo,
)


# Persona hints injected into Hestia-solo prompts for medium-confidence routing
_ARTEMIS_HINTS = (
    "Approach this analytically. Consider multiple perspectives, "
    "trade-offs, and provide thorough reasoning."
)
_APOLLO_HINTS = (
    "Focus on execution and concrete deliverables. Be precise, "
    "production-quality, and minimal in tangents."
)


class OrchestrationPlanner:
    """Builds execution plans from agent routing decisions."""

    def __init__(self, config: OrchestratorConfig) -> None:
        self._config = config

    def build_plan(
        self,
        route: AgentRoute,
        route_confidence: float,
        content: str,
        memory_context: str,
        user_profile: str,
        conversation_history: list,
        tool_instructions: str,
        cloud_available: bool,
        cloud_safe: bool = False,
    ) -> ExecutionPlan:
        """
        Build an execution plan from a routing decision.

        Applies confidence gating and chain validation before
        producing the final plan.
        """
        # Confidence gating
        if route.involves_specialist:
            if route_confidence < self._config.enriched_solo_threshold:
                # Low confidence -> pure Hestia solo
                return self._solo_plan(content, "Low routing confidence — Hestia solo")
            elif route_confidence < self._config.full_dispatch_threshold:
                # Medium confidence -> Hestia solo with persona hints
                hints = (
                    _ARTEMIS_HINTS
                    if route in (AgentRoute.ARTEMIS, AgentRoute.ARTEMIS_THEN_APOLLO)
                    else _APOLLO_HINTS
                )
                return self._enriched_solo_plan(content, hints)

        # Chain validation
        if route == AgentRoute.ARTEMIS_THEN_APOLLO:
            route = self._validate_chain(route, content, cloud_available)

        # Build the actual plan
        if route == AgentRoute.HESTIA_SOLO:
            return self._solo_plan(content, "Direct Hestia handling")

        elif route == AgentRoute.ARTEMIS:
            ctx = slice_context_for_artemis(
                memory_context, user_profile, conversation_history,
                tool_instructions, cloud_safe=cloud_safe,
            )
            task = AgentTask(
                agent_id=AgentRoute.ARTEMIS,
                prompt=content,
                context_slice=ctx,
            )
            return ExecutionPlan(
                steps=[ExecutionStep(tasks=[task])],
                rationale="Analysis needed",
                route=AgentRoute.ARTEMIS,
            )

        elif route == AgentRoute.APOLLO:
            ctx = slice_context_for_apollo(
                conversation_history, tool_instructions,
                cloud_safe=cloud_safe,
            )
            task = AgentTask(
                agent_id=AgentRoute.APOLLO,
                prompt=content,
                context_slice=ctx,
                model_preference="coding",
            )
            return ExecutionPlan(
                steps=[ExecutionStep(tasks=[task])],
                rationale="Execution needed",
                route=AgentRoute.APOLLO,
            )

        elif route == AgentRoute.ARTEMIS_THEN_APOLLO:
            artemis_ctx = slice_context_for_artemis(
                memory_context, user_profile, conversation_history,
                tool_instructions, cloud_safe=cloud_safe,
            )
            apollo_ctx = slice_context_for_apollo(
                conversation_history, tool_instructions,
                cloud_safe=cloud_safe,
            )
            s1 = ExecutionStep(tasks=[
                AgentTask(
                    agent_id=AgentRoute.ARTEMIS,
                    prompt=content,
                    context_slice=artemis_ctx,
                ),
            ])
            s2 = ExecutionStep(
                tasks=[
                    AgentTask(
                        agent_id=AgentRoute.APOLLO,
                        prompt=content,
                        context_slice=apollo_ctx,
                        model_preference="coding",
                    ),
                ],
                depends_on=0,
            )
            return ExecutionPlan(
                steps=[s1, s2],
                rationale="Analysis then execution",
                route=AgentRoute.ARTEMIS_THEN_APOLLO,
            )

        return self._solo_plan(content, "Fallback — unknown route")

    def _validate_chain(
        self, route: AgentRoute, content: str, cloud_available: bool
    ) -> AgentRoute:
        """Validate chain viability, collapsing to single agent if needed."""
        word_count = len(content.split())

        # Short requests don't need chains
        if word_count < self._config.min_words_for_chain:
            return AgentRoute.ARTEMIS  # Collapse to analysis only

        # Local-only: respect hop limits
        if not cloud_available:
            if 2 > self._config.max_hops_local:
                return AgentRoute.ARTEMIS  # Collapse

        return route  # Chain is valid

    def _solo_plan(self, content: str, rationale: str) -> ExecutionPlan:
        """Create a Hestia-solo plan (passthrough to normal pipeline)."""
        task = AgentTask(
            agent_id=AgentRoute.HESTIA_SOLO,
            prompt=content,
            context_slice={},
        )
        return ExecutionPlan(
            steps=[ExecutionStep(tasks=[task])],
            rationale=rationale,
            route=AgentRoute.HESTIA_SOLO,
        )

    def _enriched_solo_plan(self, content: str, hints: str) -> ExecutionPlan:
        """Create a Hestia-solo plan with specialist persona hints."""
        task = AgentTask(
            agent_id=AgentRoute.HESTIA_SOLO,
            prompt=content,
            context_slice={"persona_hints": hints},
        )
        return ExecutionPlan(
            steps=[ExecutionStep(tasks=[task])],
            rationale="Medium routing confidence — enriched Hestia solo",
            route=AgentRoute.HESTIA_SOLO,
        )
