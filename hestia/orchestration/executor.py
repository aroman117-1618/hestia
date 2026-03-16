"""
Agent executor — dispatches AgentTasks to inference.

Handles single-agent dispatch, sequential chains, parallel groups,
and fallback on error/low confidence.
"""

import asyncio
import time
from typing import List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.orchestration.agent_models import (
    AgentResult,
    AgentRoute,
    AgentTask,
    ExecutionPlan,
    OrchestratorConfig,
)
from hestia.orchestration.mode import PERSONAS
from hestia.orchestration.models import Mode

logger = get_logger()

# Map AgentRoute to Mode for system prompt lookup
_ROUTE_TO_MODE = {
    AgentRoute.ARTEMIS: Mode.MIRA,
    AgentRoute.APOLLO: Mode.OLLY,
    AgentRoute.HESTIA_SOLO: Mode.TIA,
}


class AgentExecutor:
    """Dispatches agent tasks to inference and collects results."""

    def __init__(
        self,
        config: OrchestratorConfig,
        inference_client: object,
        prompt_builder: object,
    ) -> None:
        self._config = config
        self._inference = inference_client
        self._prompt_builder = prompt_builder

    async def execute(
        self, plan: ExecutionPlan
    ) -> Optional[List[AgentResult]]:
        """
        Execute an orchestration plan.

        Returns None for HESTIA_SOLO plans (handler uses normal pipeline).
        Returns List[AgentResult] for specialist plans.
        """
        if plan.route == AgentRoute.HESTIA_SOLO:
            return None

        results: List[AgentResult] = []

        for i, step in enumerate(plan.steps):
            # If step depends on previous, inject previous output into context
            if step.depends_on is not None and results:
                prev_content = results[-1].content
                for task in step.tasks:
                    task.context_slice["artemis_analysis"] = prev_content

            if len(step.tasks) == 1:
                result = await self._execute_task(step.tasks[0])
                results.append(result)
            else:
                # Parallel group — asyncio.gather
                # On M1: serialized by Ollama. On M5 Ultra: genuine parallel.
                step_results = await asyncio.gather(
                    *[self._execute_task(t) for t in step.tasks],
                    return_exceptions=True,
                )
                for sr in step_results:
                    if isinstance(sr, Exception):
                        results.append(AgentResult(
                            agent_id=AgentRoute.HESTIA_SOLO,
                            content="",
                            confidence=0.0,
                            error=str(sr),
                        ))
                    else:
                        results.append(sr)

        return results

    async def _execute_task(self, task: AgentTask) -> AgentResult:
        """Execute a single agent task via inference."""
        start = time.perf_counter()

        try:
            # Build system prompt from persona
            mode = _ROUTE_TO_MODE.get(task.agent_id, Mode.TIA)
            persona = PERSONAS.get(mode)
            system_prompt = persona.system_prompt if persona else ""

            # Build messages from history
            messages = []
            history = task.context_slice.get("history", [])
            for msg in history:
                messages.append(msg)

            # Enrich system prompt with context
            memory = task.context_slice.get("memory", "")
            profile = task.context_slice.get("profile", "")
            artemis_analysis = task.context_slice.get("artemis_analysis", "")
            persona_hints = task.context_slice.get("persona_hints", "")

            if memory:
                system_prompt += f"\n\n## Relevant Memory\n{memory}"
            if profile:
                system_prompt += f"\n\n## User Profile\n{profile}"
            if artemis_analysis:
                system_prompt += f"\n\n## Analysis from Artemis\n{artemis_analysis}"
            if persona_hints:
                system_prompt += f"\n\n## Approach\n{persona_hints}"

            # Add tool instructions for Apollo
            tool_instructions = task.context_slice.get("tool_instructions", "")
            if tool_instructions and task.agent_id == AgentRoute.APOLLO:
                system_prompt += f"\n\n## Available Tools\n{tool_instructions}"

            messages.append({"role": "user", "content": task.prompt})

            # Call inference
            temperature = persona.temperature if persona else 0.0
            response = await self._inference.chat(
                messages=messages,
                system=system_prompt,
                temperature=temperature,
                max_tokens=2048,
            )

            duration_ms = int((time.perf_counter() - start) * 1000)

            return AgentResult(
                agent_id=task.agent_id,
                content=response.content,
                confidence=0.85,
                tool_calls=response.tool_calls or [],
                tokens_used=(response.tokens_in or 0) + (response.tokens_out or 0),
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            logger.warning(
                f"Agent execution failed: {type(e).__name__}",
                component=LogComponent.ORCHESTRATION,
                data={"agent": task.agent_id.value, "duration_ms": duration_ms},
            )
            return AgentResult(
                agent_id=task.agent_id,
                content="",
                confidence=0.0,
                duration_ms=duration_ms,
                error=f"{type(e).__name__}: agent execution failed",
            )
