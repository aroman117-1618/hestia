"""
Council manager for orchestrating specialized LLM roles.

Dual-path execution:
  - Cloud active: parallel council calls via asyncio.gather
  - Cloud disabled: fast SLM intent classification only
"""

import asyncio
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from hestia.logging import get_logger, LogComponent
from hestia.inference.client import InferenceClient, InferenceResponse, Message

from .models import (
    CouncilConfig,
    CouncilResult,
    IntentClassification,
    IntentType,
    RoleResult,
    ToolExtraction,
    ValidationReport,
)
from .roles import Coordinator, Analyzer, Validator, Responder


class CouncilManager:
    """
    Orchestrates council roles for enhanced request processing.

    Two execution paths:
    1. Cloud active: All enabled roles run in parallel via cloud API
    2. Cloud disabled: Coordinator runs via SLM, others skipped
    """

    def __init__(
        self,
        config: Optional[CouncilConfig] = None,
        inference_client: Optional[InferenceClient] = None,
    ) -> None:
        if config is not None:
            self.config = config
        else:
            self.config = self._load_config_from_yaml()

        self.logger = get_logger()
        self._inference_client = inference_client

        # Role instances
        self.coordinator = Coordinator()
        self.analyzer = Analyzer()
        self.validator = Validator()
        self.responder = Responder()

    def _load_config_from_yaml(self) -> CouncilConfig:
        """Load council config from inference.yaml."""
        path = Path(__file__).parent.parent / "config" / "inference.yaml"
        if not path.exists():
            return CouncilConfig()

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return CouncilConfig.from_dict(data.get("council", {}))

    @property
    def inference_client(self) -> InferenceClient:
        """Lazy-load inference client."""
        if self._inference_client is None:
            from hestia.inference import get_inference_client
            self._inference_client = get_inference_client()
        return self._inference_client

    def _is_cloud_active(self) -> bool:
        """Check if cloud routing is active."""
        try:
            return self.inference_client.router.cloud_routing.state != "disabled"
        except Exception:
            return False

    # ========================================================================
    # Public API
    # ========================================================================

    async def classify_intent(
        self,
        user_message: str,
        context: Optional[str] = None,
    ) -> IntentClassification:
        """
        Fast intent classification (Coordinator role only).

        Uses cloud LLM when cloud active, SLM when cloud disabled.
        """
        if not self.config.enabled or not self.config.coordinator_enabled:
            return IntentClassification.create(
                primary_intent=IntentType.CHAT,
                confidence=0.5,
                reasoning="Council disabled",
            )

        messages = [Message(role="user", content=user_message)]

        start = time.perf_counter()
        try:
            if self._is_cloud_active():
                response = await self._call_role_cloud(
                    role=self.coordinator,
                    messages=messages,
                    temperature=self.config.coordinator_temperature,
                    max_tokens=self.config.coordinator_max_tokens,
                )
            else:
                response = await self._call_role_slm(
                    role=self.coordinator,
                    messages=messages,
                    temperature=self.config.coordinator_temperature,
                    max_tokens=self.config.coordinator_max_tokens,
                )

            duration_ms = (time.perf_counter() - start) * 1000
            result = self.coordinator.parse_response(response.content)

            self.logger.info(
                f"Intent classified: {result.primary_intent.value} "
                f"(confidence={result.confidence:.2f}, {duration_ms:.0f}ms)",
                component=LogComponent.COUNCIL,
            )
            return result

        except Exception as e:
            duration_ms = (time.perf_counter() - start) * 1000
            self.logger.warning(
                f"Intent classification failed: {type(e).__name__} ({duration_ms:.0f}ms)",
                component=LogComponent.COUNCIL,
            )
            return IntentClassification.create(
                primary_intent=IntentType.UNCLEAR,
                confidence=0.0,
                reasoning=f"Error: {type(e).__name__}",
            )

    async def run_council(
        self,
        user_message: str,
        inference_response: str,
        mode: str = "tia",
        intent: Optional[IntentClassification] = None,
    ) -> CouncilResult:
        """
        Run full council (post-inference roles).

        Dual-path execution:
        - Cloud active: parallel cloud calls for Analyzer + Validator
        - Cloud disabled: returns minimal result (Coordinator only, already done)
        """
        start = time.perf_counter()

        if not self.config.enabled:
            return CouncilResult(fallback_used=True)

        # CHAT optimization: skip post-inference roles for pure conversation
        if (
            intent
            and intent.primary_intent == IntentType.CHAT
            and intent.confidence > 0.8
        ):
            self.logger.info(
                "Council: CHAT intent, skipping post-inference roles",
                component=LogComponent.COUNCIL,
            )
            result = CouncilResult(intent=intent, fallback_used=False)
            result.total_duration_ms = (time.perf_counter() - start) * 1000
            return result

        if self._is_cloud_active():
            result = await self._run_cloud_council(
                user_message, inference_response, mode, intent
            )
        else:
            result = self._make_local_fallback_result(intent)

        result.total_duration_ms = (time.perf_counter() - start) * 1000
        return result

    async def synthesize_response(
        self,
        user_message: str,
        tool_result: str,
        mode: str = "tia",
    ) -> Optional[str]:
        """
        Run Responder role to synthesize tool results with personality.

        Returns synthesized text, or None if Responder is disabled/fails.
        Cloud-only — returns None when cloud is disabled.
        """
        if not self.config.enabled or not self.config.responder_enabled:
            return None

        if not self._is_cloud_active():
            return None

        prompt = (
            f"User message: {user_message}\n\n"
            f"Tool result: {tool_result}\n\n"
            f"Mode: {mode}"
        )
        messages = [Message(role="user", content=prompt)]

        try:
            response = await self._call_role_cloud(
                role=self.responder,
                messages=messages,
                temperature=self.config.responder_temperature,
                max_tokens=self.config.responder_max_tokens,
            )
            return self.responder.parse_response(response.content)
        except Exception as e:
            self.logger.warning(
                f"Responder failed: {type(e).__name__}",
                component=LogComponent.COUNCIL,
            )
            return None

    # ========================================================================
    # Cloud Parallel Execution
    # ========================================================================

    async def _run_cloud_council(
        self,
        user_message: str,
        inference_response: str,
        mode: str,
        intent: Optional[IntentClassification],
    ) -> CouncilResult:
        """Run Analyzer + Validator in parallel via cloud."""
        tasks: List[asyncio.Task] = []
        task_names: List[str] = []

        if self.config.analyzer_enabled:
            tasks.append(
                asyncio.create_task(
                    self._execute_analyzer(inference_response)
                )
            )
            task_names.append("analyzer")

        if self.config.validator_enabled:
            tasks.append(
                asyncio.create_task(
                    self._execute_validator(inference_response)
                )
            )
            task_names.append("validator")

        if not tasks:
            return CouncilResult(intent=intent, fallback_used=True)

        # Run parallel with timeout
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return self._aggregate_results(results, task_names, intent)

    async def _execute_analyzer(
        self, inference_response: str
    ) -> Tuple[str, Any, float]:
        """Execute Analyzer role."""
        start = time.perf_counter()
        messages = [Message(role="user", content=inference_response)]
        response = await self._call_role_cloud(
            role=self.analyzer,
            messages=messages,
            temperature=self.config.analyzer_temperature,
            max_tokens=self.config.analyzer_max_tokens,
        )
        duration = (time.perf_counter() - start) * 1000
        result = self.analyzer.parse_response(response.content)
        return ("analyzer", result, duration)

    async def _execute_validator(
        self, inference_response: str
    ) -> Tuple[str, Any, float]:
        """Execute Validator role."""
        start = time.perf_counter()
        messages = [Message(role="user", content=inference_response)]
        response = await self._call_role_cloud(
            role=self.validator,
            messages=messages,
            temperature=self.config.validator_temperature,
            max_tokens=self.config.validator_max_tokens,
        )
        duration = (time.perf_counter() - start) * 1000
        result = self.validator.parse_response(response.content)
        return ("validator", result, duration)

    def _aggregate_results(
        self,
        results: List[Any],
        task_names: List[str],
        intent: Optional[IntentClassification],
    ) -> CouncilResult:
        """Aggregate parallel results into CouncilResult."""
        council_result = CouncilResult(intent=intent)

        for i, item in enumerate(results):
            name = task_names[i] if i < len(task_names) else f"unknown_{i}"

            if isinstance(item, Exception):
                self.logger.warning(
                    f"Council role '{name}' failed: {type(item).__name__}",
                    component=LogComponent.COUNCIL,
                )
                council_result.roles_failed.append(name)
                council_result.role_results.append(
                    RoleResult(
                        role_name=name,
                        success=False,
                        duration_ms=0.0,
                        error=type(item).__name__,
                    )
                )
                continue

            role_name, data, duration_ms = item
            council_result.roles_executed.append(role_name)
            council_result.role_results.append(
                RoleResult(
                    role_name=role_name,
                    success=True,
                    duration_ms=duration_ms,
                )
            )

            if role_name == "analyzer" and isinstance(data, ToolExtraction):
                council_result.tool_extraction = data
            elif role_name == "validator" and isinstance(data, ValidationReport):
                council_result.validation = data

        return council_result

    def _make_local_fallback_result(
        self, intent: Optional[IntentClassification]
    ) -> CouncilResult:
        """Create fallback result for cloud-disabled path."""
        return CouncilResult(
            intent=intent,
            fallback_used=True,
        )

    # ========================================================================
    # Role Call Methods
    # ========================================================================

    async def _call_role_cloud(
        self,
        role: Any,
        messages: List[Message],
        temperature: float,
        max_tokens: int,
    ) -> InferenceResponse:
        """Call a role via cloud LLM (direct _call_cloud, bypasses router)."""
        # Direct _call_cloud bypasses the router intentionally: council roles
        # need guaranteed cloud execution with per-role system prompts and
        # temperature, which the router's chat() method doesn't support.
        return await asyncio.wait_for(
            self.inference_client._call_cloud(
                messages=messages,
                system=role.system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=self.config.role_timeout,
        )

    async def _call_role_slm(
        self,
        role: Any,
        messages: List[Message],
        temperature: float,
        max_tokens: int,
    ) -> InferenceResponse:
        """Call a role via local SLM (direct _call_ollama, bypasses router)."""
        # Direct _call_ollama bypasses the router: SLM classification uses a
        # dedicated lightweight model (qwen2.5:0.5b), not the primary model.
        return await asyncio.wait_for(
            self.inference_client._call_ollama(
                prompt="",
                model_name=self.config.local_slm_model,
                system=role.system_prompt,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            ),
            timeout=self.config.local_slm_timeout,
        )


# ============================================================================
# Singleton
# ============================================================================

_council_manager: Optional[CouncilManager] = None


def get_council_manager(
    config: Optional[CouncilConfig] = None,
    inference_client: Optional[InferenceClient] = None,
) -> CouncilManager:
    """Get or create council manager singleton."""
    global _council_manager
    if _council_manager is None:
        _council_manager = CouncilManager(
            config=config,
            inference_client=inference_client,
        )
    return _council_manager
