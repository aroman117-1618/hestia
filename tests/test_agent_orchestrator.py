"""Tests for agent orchestrator models, routing, planning, and execution."""

import pytest
from hestia.orchestration.agent_models import (
    AgentRoute,
    AgentTask,
    AgentResult,
    ExecutionPlan,
    ExecutionStep,
    AgentByline,
    RoutingAuditEntry,
    OrchestratorConfig,
)
from hestia.orchestration.router import AgentRouter
from hestia.council.models import IntentClassification, IntentType


# ── AgentRoute ───────────────────────────────────────────────────────────────


class TestAgentRoute:
    """AgentRoute enum behavior."""

    def test_enum_values(self):
        assert AgentRoute.HESTIA_SOLO.value == "hestia_solo"
        assert AgentRoute.ARTEMIS.value == "artemis"
        assert AgentRoute.APOLLO.value == "apollo"
        assert AgentRoute.ARTEMIS_THEN_APOLLO.value == "artemis_apollo"

    def test_is_multi_agent(self):
        assert not AgentRoute.HESTIA_SOLO.is_multi_agent
        assert not AgentRoute.ARTEMIS.is_multi_agent
        assert not AgentRoute.APOLLO.is_multi_agent
        assert AgentRoute.ARTEMIS_THEN_APOLLO.is_multi_agent

    def test_involves_specialist(self):
        assert not AgentRoute.HESTIA_SOLO.involves_specialist
        assert AgentRoute.ARTEMIS.involves_specialist
        assert AgentRoute.APOLLO.involves_specialist
        assert AgentRoute.ARTEMIS_THEN_APOLLO.involves_specialist


# ── AgentTask ────────────────────────────────────────────────────────────────


class TestAgentTask:
    """AgentTask construction."""

    def test_create_task(self):
        task = AgentTask(
            agent_id=AgentRoute.ARTEMIS,
            prompt="Analyze trade-offs between A and B",
            context_slice={"memory": "some context", "profile": "user prefs"},
        )
        assert task.agent_id == AgentRoute.ARTEMIS
        assert task.model_preference is None

    def test_create_task_with_model(self):
        task = AgentTask(
            agent_id=AgentRoute.APOLLO,
            prompt="Write the migration",
            context_slice={},
            model_preference="coding",
        )
        assert task.model_preference == "coding"


# ── AgentResult ──────────────────────────────────────────────────────────────


class TestAgentResult:
    """AgentResult creation."""

    def test_create_result(self):
        result = AgentResult(
            agent_id=AgentRoute.ARTEMIS,
            content="SSE is better because...",
            confidence=0.92,
        )
        assert result.confidence == 0.92
        assert result.tool_calls == []
        assert result.tokens_used == 0

    def test_is_low_confidence(self):
        low = AgentResult(agent_id=AgentRoute.ARTEMIS, content="maybe", confidence=0.3)
        high = AgentResult(agent_id=AgentRoute.ARTEMIS, content="yes", confidence=0.8)
        assert low.is_low_confidence(threshold=0.4)
        assert not high.is_low_confidence(threshold=0.4)


# ── ExecutionPlan ────────────────────────────────────────────────────────────


class TestExecutionPlan:
    """ExecutionPlan construction."""

    def test_single_step(self):
        task = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze", context_slice={})
        step = ExecutionStep(tasks=[task])
        plan = ExecutionPlan(steps=[step], rationale="Analysis needed")
        assert plan.estimated_hops == 1
        assert not plan.has_parallel_steps

    def test_chain(self):
        t1 = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze", context_slice={})
        t2 = AgentTask(agent_id=AgentRoute.APOLLO, prompt="build", context_slice={})
        s1 = ExecutionStep(tasks=[t1])
        s2 = ExecutionStep(tasks=[t2], depends_on=0)
        plan = ExecutionPlan(steps=[s1, s2], rationale="Analyze then build")
        assert plan.estimated_hops == 2

    def test_parallel_group(self):
        t1 = AgentTask(agent_id=AgentRoute.ARTEMIS, prompt="analyze", context_slice={})
        t2 = AgentTask(agent_id=AgentRoute.APOLLO, prompt="build", context_slice={})
        step = ExecutionStep(tasks=[t1, t2])
        plan = ExecutionPlan(steps=[step], rationale="Parallel work")
        assert plan.has_parallel_steps


# ── AgentByline ──────────────────────────────────────────────────────────────


class TestAgentByline:
    """AgentByline formatting."""

    def test_format_artemis(self):
        byline = AgentByline(
            agent=AgentRoute.ARTEMIS,
            contribution_type="analysis",
            summary="Analyzed WebSocket vs SSE trade-offs",
        )
        formatted = byline.format()
        assert "Artemis" in formatted
        assert "\U0001f4d0" in formatted

    def test_format_apollo(self):
        byline = AgentByline(
            agent=AgentRoute.APOLLO,
            contribution_type="implementation",
            summary="Scaffolded SSE implementation",
        )
        formatted = byline.format()
        assert "Apollo" in formatted
        assert "\u26a1" in formatted

    def test_to_dict(self):
        byline = AgentByline(
            agent=AgentRoute.ARTEMIS,
            contribution_type="analysis",
            summary="Analyzed trade-offs",
        )
        d = byline.to_dict()
        assert d["agent"] == "artemis"
        assert d["contribution"] == "analysis"
        assert d["summary"] == "Analyzed trade-offs"


# ── OrchestratorConfig ───────────────────────────────────────────────────────


class TestOrchestratorConfig:
    """OrchestratorConfig loading from YAML."""

    def test_defaults(self):
        config = OrchestratorConfig()
        assert config.enabled is True
        assert config.full_dispatch_threshold == 0.8
        assert config.enriched_solo_threshold == 0.5
        assert config.min_specialist_confidence == 0.4
        assert config.min_words_for_chain == 15
        assert config.max_hops_local == 2
        assert config.max_hops_cloud == 4

    def test_from_dict(self):
        data = {
            "enabled": False,
            "confidence_thresholds": {
                "full_dispatch": 0.9,
                "enriched_solo": 0.6,
            },
        }
        config = OrchestratorConfig.from_dict(data)
        assert config.enabled is False
        assert config.full_dispatch_threshold == 0.9
        assert config.enriched_solo_threshold == 0.6


# ── RoutingAuditEntry ────────────────────────────────────────────────────────


class TestRoutingAuditEntry:
    """RoutingAuditEntry factory."""

    def test_create(self):
        entry = RoutingAuditEntry.create(
            user_id="user-1",
            request_id="req-abc",
            intent="chat",
            route_chosen="artemis",
            route_confidence=0.85,
        )
        assert entry.user_id == "user-1"
        assert entry.route_chosen == "artemis"
        assert entry.id.startswith("raud-")
        assert entry.actual_agents == []


# ── AgentRouter ──────────────────────────────────────────────────────────────


class TestAgentRouter:
    """Intent-to-route heuristic tests."""

    def setup_method(self):
        self.config = OrchestratorConfig()
        self.router = AgentRouter(self.config)

    # -- Direct intent mapping --

    def test_coding_intent_routes_to_apollo(self):
        route, conf = self.router.resolve(IntentType.CODING, "write a function")
        assert route == AgentRoute.APOLLO

    def test_memory_search_routes_to_artemis(self):
        route, conf = self.router.resolve(IntentType.MEMORY_SEARCH, "what do I know about X")
        assert route == AgentRoute.ARTEMIS

    def test_calendar_query_routes_to_solo(self):
        route, conf = self.router.resolve(IntentType.CALENDAR_QUERY, "what's on my calendar")
        assert route == AgentRoute.HESTIA_SOLO

    def test_chat_simple_routes_to_solo(self):
        route, conf = self.router.resolve(IntentType.CHAT, "hey")
        assert route == AgentRoute.HESTIA_SOLO

    # -- Keyword escalation for CHAT intent --

    def test_chat_with_analysis_keywords_routes_to_artemis(self):
        route, conf = self.router.resolve(
            IntentType.CHAT, "help me think through the database architecture"
        )
        assert route == AgentRoute.ARTEMIS

    def test_chat_with_execution_keywords_routes_to_apollo(self):
        route, conf = self.router.resolve(
            IntentType.CHAT, "write the migration script for the users table"
        )
        assert route == AgentRoute.APOLLO

    def test_chat_with_both_keywords_routes_to_chain(self):
        route, conf = self.router.resolve(
            IntentType.CHAT,
            "research how HealthKit handles background sync then implement it"
        )
        assert route == AgentRoute.ARTEMIS_THEN_APOLLO

    def test_chat_no_keywords_routes_to_solo(self):
        route, conf = self.router.resolve(
            IntentType.CHAT, "thanks that was helpful"
        )
        assert route == AgentRoute.HESTIA_SOLO

    # -- Confidence scoring --

    def test_direct_intent_has_high_confidence(self):
        route, conf = self.router.resolve(IntentType.CODING, "write code")
        assert conf >= 0.85

    def test_keyword_match_has_moderate_confidence(self):
        route, conf = self.router.resolve(
            IntentType.CHAT, "compare SQLite vs Postgres"
        )
        assert 0.6 <= conf <= 0.9

    def test_no_match_has_high_solo_confidence(self):
        route, conf = self.router.resolve(IntentType.CHAT, "hi there")
        assert conf >= 0.8

    # -- @mention override --

    def test_explicit_override(self):
        route, conf = self.router.resolve_with_override(
            IntentType.CHAT, "how are you", explicit_agent="artemis"
        )
        assert route == AgentRoute.ARTEMIS
        assert conf == 1.0

    # -- Disabled orchestrator --

    def test_disabled_always_returns_solo(self):
        config = OrchestratorConfig(enabled=False)
        router = AgentRouter(config)
        route, conf = router.resolve(IntentType.CODING, "write code")
        assert route == AgentRoute.HESTIA_SOLO


# ── IntentClassification Extension ───────────────────────────────────────────


class TestIntentClassificationExtension:
    """Verify IntentClassification agent_route fields."""

    def test_default_values_backward_compat(self):
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT, confidence=0.9
        )
        assert ic.agent_route is None
        assert ic.route_confidence == 0.0

    def test_with_routing_fields(self):
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT,
            confidence=0.9,
            agent_route="artemis",
            route_confidence=0.85,
        )
        assert ic.agent_route == "artemis"
        assert ic.route_confidence == 0.85

    def test_to_dict_includes_routing(self):
        ic = IntentClassification.create(
            primary_intent=IntentType.CODING,
            confidence=0.95,
            agent_route="apollo",
            route_confidence=0.9,
        )
        d = ic.to_dict()
        assert d["agent_route"] == "apollo"
        assert d["route_confidence"] == 0.9

    def test_to_dict_backward_compat_no_routing(self):
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT, confidence=0.9
        )
        d = ic.to_dict()
        assert d["agent_route"] is None
        assert d["route_confidence"] == 0.0


# ── Context Manager ──────────────────────────────────────────────────────────

from hestia.orchestration.context_manager import (
    slice_context_for_artemis,
    slice_context_for_apollo,
    slice_context_for_synthesis,
)


class TestContextManager:
    """Context slicing for specialist agents."""

    def test_artemis_gets_full_history(self):
        ctx = slice_context_for_artemis(
            memory_context="memories here",
            user_profile="profile here",
            conversation_history=[
                {"role": "user", "content": "msg1"},
                {"role": "assistant", "content": "resp1"},
                {"role": "user", "content": "msg2"},
                {"role": "assistant", "content": "resp2"},
            ],
            tool_instructions="tool defs",
        )
        assert "memories here" in ctx["memory"]
        assert "profile here" in ctx["profile"]
        assert len(ctx["history"]) == 4
        assert "tool_instructions" not in ctx

    def test_apollo_gets_recent_turns_only(self):
        history = [{"role": "user", "content": f"msg{i}"} for i in range(20)]
        ctx = slice_context_for_apollo(
            conversation_history=history,
            tool_instructions="tool defs",
            artemis_output=None,
        )
        assert len(ctx["history"]) <= 6
        assert ctx["tool_instructions"] == "tool defs"

    def test_apollo_gets_artemis_output_when_chained(self):
        ctx = slice_context_for_apollo(
            conversation_history=[],
            tool_instructions="tool defs",
            artemis_output="SSE is better because...",
        )
        assert ctx["artemis_analysis"] == "SSE is better because..."

    def test_synthesis_gets_all_results(self):
        results = [
            AgentResult(agent_id=AgentRoute.ARTEMIS, content="analysis", confidence=0.9),
            AgentResult(agent_id=AgentRoute.APOLLO, content="code", confidence=0.85),
        ]
        ctx = slice_context_for_synthesis(
            agent_results=results,
            original_request="research and implement X",
            user_profile="profile",
        )
        assert len(ctx["agent_results"]) == 2
        assert ctx["original_request"] == "research and implement X"

    def test_artemis_excludes_pii_when_cloud(self):
        ctx = slice_context_for_artemis(
            memory_context="memories",
            user_profile="SENSITIVE: SSN 123-45-6789",
            conversation_history=[],
            tool_instructions="",
            cloud_safe=True,
        )
        assert ctx["profile"] == ""


# ── Synthesizer ──────────────────────────────────────────────────────────────

from hestia.orchestration.synthesizer import (
    generate_bylines,
    synthesize_single_agent,
    synthesize_multi_agent,
    format_byline_footer,
)


class TestSynthesizer:
    """Result synthesis and byline generation."""

    def test_single_agent_returns_content_with_byline(self):
        result = AgentResult(
            agent_id=AgentRoute.ARTEMIS,
            content="SSE is better for unidirectional data flow.",
            confidence=0.9,
        )
        content, bylines = synthesize_single_agent(result, "analyze SSE vs WS")
        assert "SSE is better" in content
        assert len(bylines) == 1
        assert bylines[0].agent == AgentRoute.ARTEMIS

    def test_multi_agent_combines_outputs(self):
        r1 = AgentResult(
            agent_id=AgentRoute.ARTEMIS,
            content="SSE is better because...",
            confidence=0.9,
        )
        r2 = AgentResult(
            agent_id=AgentRoute.APOLLO,
            content="```python\nclass SSEHandler:\n    pass\n```",
            confidence=0.85,
        )
        content, bylines = synthesize_multi_agent([r1, r2], "research and build SSE")
        assert "SSE is better" in content
        assert "SSEHandler" in content
        assert len(bylines) == 2

    def test_byline_format(self):
        bylines = generate_bylines([
            AgentResult(agent_id=AgentRoute.ARTEMIS, content="analysis", confidence=0.9),
        ])
        assert len(bylines) == 1
        formatted = bylines[0].format()
        assert "\U0001f4d0" in formatted
        assert "Artemis" in formatted

    def test_hestia_solo_no_byline(self):
        result = AgentResult(
            agent_id=AgentRoute.HESTIA_SOLO,
            content="Your calendar is clear today.",
            confidence=1.0,
        )
        content, bylines = synthesize_single_agent(result, "calendar check")
        assert len(bylines) == 0

    def test_empty_results(self):
        content, bylines = synthesize_multi_agent([], "something")
        assert content == ""
        assert bylines == []

    def test_format_byline_footer(self):
        bylines = [
            AgentByline(agent=AgentRoute.ARTEMIS, contribution_type="analysis", summary="analyzed X"),
        ]
        footer = format_byline_footer(bylines)
        assert "---" in footer
        assert "Artemis" in footer

    def test_format_byline_footer_empty(self):
        assert format_byline_footer([]) == ""


# ── Orchestration Planner ────────────────────────────────────────────────────

from hestia.orchestration.planner import OrchestrationPlanner


class TestOrchestrationPlanner:
    """Orchestration planner — builds execution plans from routing decisions."""

    def setup_method(self):
        self.config = OrchestratorConfig()
        self.planner = OrchestrationPlanner(self.config)

    def test_high_confidence_full_dispatch(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS, route_confidence=0.9,
            content="analyze the trade-offs",
            memory_context="mem", user_profile="profile",
            conversation_history=[], tool_instructions="tools",
            cloud_available=True,
        )
        assert plan.route == AgentRoute.ARTEMIS
        assert len(plan.steps) == 1
        assert plan.steps[0].tasks[0].agent_id == AgentRoute.ARTEMIS

    def test_medium_confidence_enriched_solo(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS, route_confidence=0.6,
            content="maybe analyze this",
            memory_context="", user_profile="",
            conversation_history=[], tool_instructions="",
            cloud_available=False,
        )
        assert plan.route == AgentRoute.HESTIA_SOLO
        assert len(plan.steps) == 1
        assert plan.steps[0].tasks[0].agent_id == AgentRoute.HESTIA_SOLO

    def test_low_confidence_pure_solo(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS, route_confidence=0.3,
            content="something unclear",
            memory_context="", user_profile="",
            conversation_history=[], tool_instructions="",
            cloud_available=False,
        )
        assert plan.route == AgentRoute.HESTIA_SOLO

    def test_chain_collapsed_for_short_request(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS_THEN_APOLLO, route_confidence=0.9,
            content="do it",
            memory_context="", user_profile="",
            conversation_history=[], tool_instructions="",
            cloud_available=True,
        )
        assert plan.estimated_hops == 1

    def test_chain_collapsed_when_no_cloud_and_low_max_hops(self):
        self.config.max_hops_local = 1
        planner = OrchestrationPlanner(self.config)
        plan = planner.build_plan(
            route=AgentRoute.ARTEMIS_THEN_APOLLO, route_confidence=0.9,
            content="research how HealthKit handles background sync then implement the full solution with tests",
            memory_context="", user_profile="",
            conversation_history=[], tool_instructions="",
            cloud_available=False,
        )
        assert plan.estimated_hops <= 1

    def test_chain_preserved_with_cloud(self):
        plan = self.planner.build_plan(
            route=AgentRoute.ARTEMIS_THEN_APOLLO, route_confidence=0.9,
            content="research how HealthKit handles background sync and data permissions then implement the full solution with comprehensive tests and error handling",
            memory_context="mem", user_profile="profile",
            conversation_history=[], tool_instructions="tools",
            cloud_available=True,
        )
        assert plan.estimated_hops == 2
        assert plan.steps[0].tasks[0].agent_id == AgentRoute.ARTEMIS
        assert plan.steps[1].tasks[0].agent_id == AgentRoute.APOLLO

    def test_solo_produces_single_step(self):
        plan = self.planner.build_plan(
            route=AgentRoute.HESTIA_SOLO, route_confidence=0.9,
            content="what time is it",
            memory_context="", user_profile="",
            conversation_history=[], tool_instructions="",
            cloud_available=False,
        )
        assert plan.route == AgentRoute.HESTIA_SOLO
        assert plan.estimated_hops == 1

    def test_apollo_gets_coding_model_preference(self):
        plan = self.planner.build_plan(
            route=AgentRoute.APOLLO, route_confidence=0.9,
            content="write the migration script",
            memory_context="", user_profile="",
            conversation_history=[], tool_instructions="tools",
            cloud_available=False,
        )
        assert plan.steps[0].tasks[0].model_preference == "coding"


# ── Agent Executor ───────────────────────────────────────────────────────────

from unittest.mock import AsyncMock, MagicMock
from hestia.orchestration.executor import AgentExecutor


class TestAgentExecutor:
    """Agent executor — dispatches tasks to inference."""

    def setup_method(self):
        self.config = OrchestratorConfig()
        self.mock_inference = AsyncMock()
        self.mock_prompt_builder = MagicMock()

    def _make_executor(self):
        return AgentExecutor(
            config=self.config,
            inference_client=self.mock_inference,
            prompt_builder=self.mock_prompt_builder,
        )

    @pytest.mark.asyncio
    async def test_execute_solo_returns_none(self):
        executor = self._make_executor()
        task = AgentTask(agent_id=AgentRoute.HESTIA_SOLO, prompt="hi", context_slice={})
        plan = ExecutionPlan(
            steps=[ExecutionStep(tasks=[task])],
            rationale="solo",
            route=AgentRoute.HESTIA_SOLO,
        )
        result = await executor.execute(plan)
        assert result is None

    @pytest.mark.asyncio
    async def test_execute_single_specialist(self):
        executor = self._make_executor()
        mock_response = MagicMock()
        mock_response.content = "Analysis: SSE is better."
        mock_response.tokens_in = 100
        mock_response.tokens_out = 50
        mock_response.duration_ms = 2000
        mock_response.tool_calls = None
        self.mock_inference.chat = AsyncMock(return_value=mock_response)

        task = AgentTask(
            agent_id=AgentRoute.ARTEMIS, prompt="analyze SSE vs WS",
            context_slice={"memory": "ctx", "profile": "prof", "history": []},
        )
        plan = ExecutionPlan(
            steps=[ExecutionStep(tasks=[task])],
            rationale="analysis",
            route=AgentRoute.ARTEMIS,
        )
        results = await executor.execute(plan)
        assert results is not None
        assert len(results) == 1
        assert results[0].agent_id == AgentRoute.ARTEMIS
        assert "SSE is better" in results[0].content

    @pytest.mark.asyncio
    async def test_execute_chain(self):
        executor = self._make_executor()
        responses = [
            MagicMock(content="Analysis output", tokens_in=100, tokens_out=50, duration_ms=2000, tool_calls=None),
            MagicMock(content="Code output", tokens_in=80, tokens_out=120, duration_ms=3000, tool_calls=None),
        ]
        self.mock_inference.chat = AsyncMock(side_effect=responses)

        t1 = AgentTask(
            agent_id=AgentRoute.ARTEMIS, prompt="analyze",
            context_slice={"memory": "", "profile": "", "history": []},
        )
        t2 = AgentTask(
            agent_id=AgentRoute.APOLLO, prompt="build",
            context_slice={"history": [], "tool_instructions": ""},
            model_preference="coding",
        )
        plan = ExecutionPlan(
            steps=[ExecutionStep(tasks=[t1]), ExecutionStep(tasks=[t2], depends_on=0)],
            rationale="chain",
            route=AgentRoute.ARTEMIS_THEN_APOLLO,
        )
        results = await executor.execute(plan)
        assert len(results) == 2
        assert results[0].agent_id == AgentRoute.ARTEMIS
        assert results[1].agent_id == AgentRoute.APOLLO

    @pytest.mark.asyncio
    async def test_error_handling(self):
        executor = self._make_executor()
        self.mock_inference.chat = AsyncMock(side_effect=Exception("Ollama down"))

        task = AgentTask(
            agent_id=AgentRoute.ARTEMIS, prompt="analyze",
            context_slice={"memory": "", "profile": "", "history": []},
        )
        plan = ExecutionPlan(
            steps=[ExecutionStep(tasks=[task])],
            rationale="test",
            route=AgentRoute.ARTEMIS,
        )
        results = await executor.execute(plan)
        assert results is not None
        assert results[0].error is not None
