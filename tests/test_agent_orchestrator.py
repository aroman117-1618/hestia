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
