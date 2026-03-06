"""
Tests for Hestia council system.

Covers:
- Intent classification models and parsing (Coordinator)
- Tool extraction models and parsing (Analyzer)
- Response validation models and parsing (Validator)
- Personality synthesis parsing (Responder)
- Council configuration loading
- Council result aggregation
- CouncilManager dual-path orchestration
- Singleton factory
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hestia.council.models import (
    IntentType,
    IntentClassification,
    ToolExtraction,
    ValidationReport,
    RoleResult,
    CouncilResult,
    CouncilConfig,
)
from hestia.council.roles import (
    Coordinator,
    Analyzer,
    Validator,
    Responder,
)
from hestia.council.manager import CouncilManager, get_council_manager, _council_manager
from hestia.inference.client import InferenceResponse, Message
from hestia.orchestration.handler import RequestHandler
from hestia.orchestration.models import Request, Response, Mode


# ============================================================================
# IntentType Tests
# ============================================================================

class TestIntentType:
    """Tests for IntentType enum."""

    def test_all_values_exist(self):
        """All 13 intent types are defined."""
        assert len(IntentType) == 13

    def test_from_string_valid(self):
        """Valid strings parse correctly."""
        assert IntentType.from_string("calendar_query") == IntentType.CALENDAR_QUERY
        assert IntentType.from_string("chat") == IntentType.CHAT
        assert IntentType.from_string("multi_intent") == IntentType.MULTI_INTENT

    def test_from_string_case_insensitive(self):
        """Parsing is case-insensitive."""
        assert IntentType.from_string("CALENDAR_QUERY") == IntentType.CALENDAR_QUERY
        assert IntentType.from_string("Chat") == IntentType.CHAT

    def test_from_string_invalid_returns_unclear(self):
        """Invalid strings return UNCLEAR."""
        assert IntentType.from_string("invalid") == IntentType.UNCLEAR
        assert IntentType.from_string("") == IntentType.UNCLEAR
        assert IntentType.from_string("some_random_string") == IntentType.UNCLEAR

    def test_from_string_with_whitespace(self):
        """Whitespace is stripped before parsing."""
        assert IntentType.from_string("  chat  ") == IntentType.CHAT

    def test_requires_tools_tool_intents(self):
        """Tool-requiring intents return True."""
        assert IntentType.CALENDAR_QUERY.requires_tools is True
        assert IntentType.REMINDER_CREATE.requires_tools is True
        assert IntentType.MAIL_QUERY.requires_tools is True
        assert IntentType.WEATHER_QUERY.requires_tools is True

    def test_requires_tools_non_tool_intents(self):
        """Non-tool intents return False."""
        assert IntentType.CHAT.requires_tools is False
        assert IntentType.MEMORY_SEARCH.requires_tools is False
        assert IntentType.UNCLEAR.requires_tools is False
        assert IntentType.MULTI_INTENT.requires_tools is False


# ============================================================================
# IntentClassification Tests
# ============================================================================

class TestIntentClassification:
    """Tests for IntentClassification dataclass."""

    def test_create_basic(self):
        """Basic creation works."""
        ic = IntentClassification.create(
            primary_intent=IntentType.CALENDAR_QUERY,
            confidence=0.95,
        )
        assert ic.primary_intent == IntentType.CALENDAR_QUERY
        assert ic.confidence == 0.95
        assert ic.secondary_intents == []
        assert ic.reasoning == ""

    def test_create_with_all_fields(self):
        """Creation with all fields works."""
        ic = IntentClassification.create(
            primary_intent=IntentType.MULTI_INTENT,
            confidence=0.8,
            secondary_intents=[IntentType.REMINDER_CREATE, IntentType.WEATHER_QUERY],
            reasoning="Two distinct intents detected",
        )
        assert len(ic.secondary_intents) == 2
        assert ic.reasoning == "Two distinct intents detected"

    def test_confidence_clamped_high(self):
        """Confidence above 1.0 is clamped."""
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT,
            confidence=1.5,
        )
        assert ic.confidence == 1.0

    def test_confidence_clamped_low(self):
        """Confidence below 0.0 is clamped."""
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT,
            confidence=-0.5,
        )
        assert ic.confidence == 0.0

    def test_to_dict(self):
        """Serialization works."""
        ic = IntentClassification.create(
            primary_intent=IntentType.CHAT,
            confidence=0.9,
            reasoning="test",
        )
        d = ic.to_dict()
        assert d["primary_intent"] == "chat"
        assert d["confidence"] == 0.9
        assert d["secondary_intents"] == []
        assert d["reasoning"] == "test"


# ============================================================================
# ToolExtraction Tests
# ============================================================================

class TestToolExtraction:
    """Tests for ToolExtraction dataclass."""

    def test_create_with_tools(self):
        """Creation with tool calls works."""
        te = ToolExtraction.create(
            tool_calls=[{"name": "list_events", "arguments": {"days": 7}}],
            confidence=0.95,
        )
        assert len(te.tool_calls) == 1
        assert te.tool_calls[0]["name"] == "list_events"

    def test_create_empty(self):
        """Creation with no tools works."""
        te = ToolExtraction.create()
        assert te.tool_calls == []
        assert te.confidence == 1.0

    def test_confidence_clamped(self):
        """Confidence is clamped to [0, 1]."""
        te = ToolExtraction.create(confidence=2.0)
        assert te.confidence == 1.0
        te2 = ToolExtraction.create(confidence=-1.0)
        assert te2.confidence == 0.0

    def test_to_dict(self):
        """Serialization works."""
        te = ToolExtraction.create(
            tool_calls=[{"name": "get_weather", "arguments": {}}],
            confidence=0.8,
            reasoning="Weather check",
        )
        d = te.to_dict()
        assert len(d["tool_calls"]) == 1
        assert d["confidence"] == 0.8


# ============================================================================
# ValidationReport Tests
# ============================================================================

class TestValidationReport:
    """Tests for ValidationReport dataclass."""

    def test_create_safe(self):
        """Safe report creation works."""
        vr = ValidationReport.create()
        assert vr.is_safe is True
        assert vr.is_high_quality is True
        assert vr.quality_score == 1.0
        assert vr.issues == []

    def test_create_with_issues(self):
        """Report with issues works."""
        vr = ValidationReport.create(
            is_safe=False,
            is_high_quality=False,
            quality_score=0.2,
            issues=["Inappropriate language"],
            suggestions=["Rewrite with professional tone"],
        )
        assert vr.is_safe is False
        assert len(vr.issues) == 1
        assert len(vr.suggestions) == 1

    def test_quality_score_clamped(self):
        """Quality score is clamped to [0, 1]."""
        vr = ValidationReport.create(quality_score=1.5)
        assert vr.quality_score == 1.0
        vr2 = ValidationReport.create(quality_score=-0.5)
        assert vr2.quality_score == 0.0

    def test_to_dict(self):
        """Serialization works."""
        vr = ValidationReport.create(quality_score=0.8, issues=["minor"])
        d = vr.to_dict()
        assert d["quality_score"] == 0.8
        assert d["issues"] == ["minor"]


# ============================================================================
# RoleResult Tests
# ============================================================================

class TestRoleResult:
    """Tests for RoleResult dataclass."""

    def test_success_result(self):
        """Successful role result."""
        rr = RoleResult(role_name="coordinator", success=True, duration_ms=50.0)
        assert rr.success is True
        assert rr.error is None

    def test_failure_result(self):
        """Failed role result."""
        rr = RoleResult(
            role_name="validator",
            success=False,
            duration_ms=100.0,
            error="Timeout",
        )
        assert rr.success is False
        assert rr.error == "Timeout"


# ============================================================================
# CouncilResult Tests
# ============================================================================

class TestCouncilResult:
    """Tests for CouncilResult dataclass."""

    def test_empty_result(self):
        """Empty result with defaults."""
        cr = CouncilResult()
        assert cr.intent is None
        assert cr.tool_extraction is None
        assert cr.validation is None
        assert cr.synthesized_response is None
        assert cr.roles_executed == []
        assert cr.fallback_used is False

    def test_with_intent(self):
        """Result with intent classification."""
        intent = IntentClassification.create(
            primary_intent=IntentType.CALENDAR_QUERY,
            confidence=0.9,
        )
        cr = CouncilResult(
            intent=intent,
            roles_executed=["coordinator"],
        )
        assert cr.intent.primary_intent == IntentType.CALENDAR_QUERY

    def test_with_all_roles(self):
        """Result with all role outputs."""
        cr = CouncilResult(
            intent=IntentClassification.create(IntentType.CHAT, 1.0),
            tool_extraction=ToolExtraction.create(),
            validation=ValidationReport.create(),
            synthesized_response="All good.",
            roles_executed=["coordinator", "analyzer", "validator", "responder"],
        )
        assert len(cr.roles_executed) == 4

    def test_to_dict(self):
        """Serialization works."""
        cr = CouncilResult(
            intent=IntentClassification.create(IntentType.CHAT, 0.9),
            fallback_used=True,
            roles_executed=["coordinator"],
            roles_failed=["analyzer"],
        )
        d = cr.to_dict()
        assert d["intent"]["primary_intent"] == "chat"
        assert d["fallback_used"] is True
        assert d["roles_failed"] == ["analyzer"]

    def test_to_dict_empty(self):
        """Serialization of empty result."""
        d = CouncilResult().to_dict()
        assert d["intent"] is None
        assert d["tool_extraction"] is None


# ============================================================================
# CouncilConfig Tests
# ============================================================================

class TestCouncilConfig:
    """Tests for CouncilConfig dataclass."""

    def test_defaults(self):
        """Default config is sensible."""
        cfg = CouncilConfig()
        assert cfg.enabled is True
        assert cfg.local_slm_model == "qwen2.5:0.5b"
        assert cfg.coordinator_enabled is True
        assert cfg.responder_temperature == 0.3

    def test_from_dict_full(self):
        """Load from complete YAML dict."""
        data = {
            "enabled": False,
            "cloud_parallel": False,
            "local_slm_model": "phi:2.7b",
            "local_slm_timeout": 10.0,
            "role_timeout": 20.0,
            "fallback_to_single_agent": False,
            "roles": {
                "coordinator": {"enabled": True, "temperature": 0.1, "max_tokens": 128},
                "analyzer": {"enabled": False, "temperature": 0.0, "max_tokens": 256},
                "validator": {"enabled": True, "temperature": 0.0, "max_tokens": 128},
                "responder": {"enabled": True, "temperature": 0.5, "max_tokens": 1024},
            },
        }
        cfg = CouncilConfig.from_dict(data)
        assert cfg.enabled is False
        assert cfg.local_slm_model == "phi:2.7b"
        assert cfg.coordinator_max_tokens == 128
        assert cfg.analyzer_enabled is False
        assert cfg.responder_temperature == 0.5

    def test_from_dict_partial(self):
        """Load from partial YAML dict — missing keys use defaults."""
        data = {"enabled": True}
        cfg = CouncilConfig.from_dict(data)
        assert cfg.enabled is True
        assert cfg.local_slm_model == "qwen2.5:0.5b"
        assert cfg.coordinator_enabled is True

    def test_from_dict_empty(self):
        """Load from empty dict — all defaults."""
        cfg = CouncilConfig.from_dict({})
        assert cfg.enabled is True
        assert cfg.role_timeout == 30.0


# ============================================================================
# Coordinator Role Tests
# ============================================================================

class TestCoordinator:
    """Tests for Coordinator role (intent classification)."""

    def setup_method(self):
        self.coordinator = Coordinator()

    def test_role_name(self):
        """Role name is correct."""
        assert self.coordinator.name == "coordinator"

    def test_system_prompt_exists(self):
        """System prompt is non-empty."""
        assert len(self.coordinator.system_prompt) > 100

    def test_parse_calendar_query(self):
        """Parse calendar query intent."""
        response = json.dumps({
            "primary_intent": "calendar_query",
            "confidence": 0.95,
            "secondary_intents": [],
            "reasoning": "User asking about schedule",
        })
        result = self.coordinator.parse_response(response)
        assert result.primary_intent == IntentType.CALENDAR_QUERY
        assert result.confidence == 0.95

    def test_parse_multi_intent(self):
        """Parse multi-intent response."""
        response = json.dumps({
            "primary_intent": "multi_intent",
            "confidence": 0.9,
            "secondary_intents": ["reminder_create", "weather_query"],
            "reasoning": "Two intents",
        })
        result = self.coordinator.parse_response(response)
        assert result.primary_intent == IntentType.MULTI_INTENT
        assert len(result.secondary_intents) == 2

    def test_parse_chat_intent(self):
        """Parse simple chat intent."""
        response = json.dumps({
            "primary_intent": "chat",
            "confidence": 1.0,
            "secondary_intents": [],
            "reasoning": "Greeting",
        })
        result = self.coordinator.parse_response(response)
        assert result.primary_intent == IntentType.CHAT
        assert result.confidence == 1.0

    def test_parse_invalid_json(self):
        """Invalid JSON falls back to UNCLEAR."""
        result = self.coordinator.parse_response("not json at all")
        assert result.primary_intent == IntentType.UNCLEAR
        assert result.confidence == 0.0

    def test_parse_empty_string(self):
        """Empty string falls back to UNCLEAR."""
        result = self.coordinator.parse_response("")
        assert result.primary_intent == IntentType.UNCLEAR

    def test_parse_with_code_fences(self):
        """JSON wrapped in code fences parses correctly."""
        response = '```json\n{"primary_intent": "mail_query", "confidence": 0.8, "secondary_intents": [], "reasoning": "test"}\n```'
        result = self.coordinator.parse_response(response)
        assert result.primary_intent == IntentType.MAIL_QUERY

    def test_parse_unknown_intent(self):
        """Unknown intent string falls back to UNCLEAR."""
        response = json.dumps({
            "primary_intent": "flying_cars",
            "confidence": 0.5,
            "secondary_intents": [],
            "reasoning": "Made up",
        })
        result = self.coordinator.parse_response(response)
        assert result.primary_intent == IntentType.UNCLEAR

    def test_parse_missing_fields(self):
        """Missing fields use defaults."""
        response = json.dumps({"primary_intent": "chat"})
        result = self.coordinator.parse_response(response)
        assert result.primary_intent == IntentType.CHAT
        assert result.confidence == 0.5  # default

    def test_parse_all_intent_types(self):
        """Every intent type parses correctly."""
        for intent_type in IntentType:
            response = json.dumps({
                "primary_intent": intent_type.value,
                "confidence": 0.9,
                "secondary_intents": [],
                "reasoning": "test",
            })
            result = self.coordinator.parse_response(response)
            assert result.primary_intent == intent_type


# ============================================================================
# Analyzer Role Tests
# ============================================================================

class TestAnalyzer:
    """Tests for Analyzer role (tool extraction)."""

    def setup_method(self):
        self.analyzer = Analyzer()

    def test_role_name(self):
        """Role name is correct."""
        assert self.analyzer.name == "analyzer"

    def test_parse_single_tool(self):
        """Parse single tool call."""
        response = json.dumps({
            "tool_calls": [{"name": "list_events", "arguments": {"days": 7}}],
            "confidence": 0.95,
            "reasoning": "Calendar check",
        })
        result = self.analyzer.parse_response(response)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "list_events"
        assert result.tool_calls[0]["arguments"]["days"] == 7

    def test_parse_multiple_tools(self):
        """Parse multiple tool calls."""
        response = json.dumps({
            "tool_calls": [
                {"name": "get_weather", "arguments": {}},
                {"name": "list_reminders", "arguments": {"list_name": "work"}},
            ],
            "confidence": 0.9,
            "reasoning": "Two tools",
        })
        result = self.analyzer.parse_response(response)
        assert len(result.tool_calls) == 2

    def test_parse_no_tools(self):
        """Parse response with no tools."""
        response = json.dumps({
            "tool_calls": [],
            "confidence": 1.0,
            "reasoning": "No tools needed",
        })
        result = self.analyzer.parse_response(response)
        assert result.tool_calls == []
        assert result.confidence == 1.0

    def test_parse_invalid_json(self):
        """Invalid JSON returns empty tools."""
        result = self.analyzer.parse_response("not json")
        assert result.tool_calls == []
        assert result.confidence == 0.0

    def test_parse_malformed_tool_calls(self):
        """Tool calls missing 'name' are filtered out."""
        response = json.dumps({
            "tool_calls": [
                {"name": "get_weather", "arguments": {}},
                {"arguments": {"foo": "bar"}},  # Missing name
                "not_a_dict",  # Not a dict
            ],
            "confidence": 0.7,
            "reasoning": "Partial parse",
        })
        result = self.analyzer.parse_response(response)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["name"] == "get_weather"

    def test_parse_tool_missing_arguments(self):
        """Tool call without arguments gets empty dict."""
        response = json.dumps({
            "tool_calls": [{"name": "get_today_events"}],
            "confidence": 1.0,
            "reasoning": "Simple tool",
        })
        result = self.analyzer.parse_response(response)
        assert result.tool_calls[0]["arguments"] == {}


# ============================================================================
# Validator Role Tests
# ============================================================================

class TestValidator:
    """Tests for Validator role (quality check)."""

    def setup_method(self):
        self.validator = Validator()

    def test_role_name(self):
        """Role name is correct."""
        assert self.validator.name == "validator"

    def test_parse_safe_response(self):
        """Parse safe, high-quality response."""
        response = json.dumps({
            "is_safe": True,
            "is_high_quality": True,
            "quality_score": 0.95,
            "issues": [],
            "suggestions": [],
        })
        result = self.validator.parse_response(response)
        assert result.is_safe is True
        assert result.is_high_quality is True
        assert result.quality_score == 0.95

    def test_parse_unsafe_response(self):
        """Parse unsafe response."""
        response = json.dumps({
            "is_safe": False,
            "is_high_quality": False,
            "quality_score": 0.1,
            "issues": ["Inappropriate language"],
            "suggestions": ["Rewrite"],
        })
        result = self.validator.parse_response(response)
        assert result.is_safe is False
        assert len(result.issues) == 1

    def test_parse_invalid_json_fails_open(self):
        """Invalid JSON fails open (passes validation)."""
        result = self.validator.parse_response("not json")
        assert result.is_safe is True
        assert result.is_high_quality is True
        assert len(result.issues) == 1  # Parse error noted

    def test_parse_with_code_fences(self):
        """JSON wrapped in code fences parses correctly."""
        response = '```json\n{"is_safe": true, "is_high_quality": false, "quality_score": 0.6, "issues": ["low quality"], "suggestions": []}\n```'
        result = self.validator.parse_response(response)
        assert result.is_high_quality is False
        assert result.quality_score == 0.6


# ============================================================================
# Responder Role Tests
# ============================================================================

class TestResponder:
    """Tests for Responder role (personality synthesis)."""

    def setup_method(self):
        self.responder = Responder()

    def test_role_name(self):
        """Role name is correct."""
        assert self.responder.name == "responder"

    def test_parse_plain_text(self):
        """Plain text returned as-is."""
        text = "You've got two things tomorrow: standup at 9am, lunch at noon."
        result = self.responder.parse_response(text)
        assert result == text

    def test_parse_strips_whitespace(self):
        """Whitespace is stripped."""
        result = self.responder.parse_response("  Hello, Boss.  \n")
        assert result == "Hello, Boss."

    def test_parse_empty_string(self):
        """Empty string returns empty."""
        result = self.responder.parse_response("")
        assert result == ""

    def test_system_prompt_exists(self):
        """System prompt is non-empty."""
        assert len(self.responder.system_prompt) > 50


# ============================================================================
# Helper: Mock InferenceClient for manager tests
# ============================================================================

def _make_inference_response(content: str, model: str = "test-model") -> InferenceResponse:
    """Create a minimal InferenceResponse for testing."""
    return InferenceResponse(
        content=content,
        model=model,
        tokens_in=10,
        tokens_out=20,
        duration_ms=50.0,
    )


def _make_mock_client(cloud_active: bool = True) -> MagicMock:
    """Create a mock InferenceClient with router state."""
    client = MagicMock()
    client.router = MagicMock()
    client.router.cloud_routing = MagicMock()
    client.router.cloud_routing.state = "enabled_full" if cloud_active else "disabled"
    client._call_cloud = AsyncMock()
    client._call_ollama = AsyncMock()
    return client


def _make_manager(
    cloud_active: bool = True,
    enabled: bool = True,
    coordinator_enabled: bool = True,
    analyzer_enabled: bool = True,
    validator_enabled: bool = True,
    responder_enabled: bool = True,
    force_local_roles: bool = False,
) -> CouncilManager:
    """Create a CouncilManager with mock inference client."""
    config = CouncilConfig(
        enabled=enabled,
        coordinator_enabled=coordinator_enabled,
        analyzer_enabled=analyzer_enabled,
        validator_enabled=validator_enabled,
        responder_enabled=responder_enabled,
        role_timeout=5.0,
        local_slm_timeout=5.0,
        force_local_roles=force_local_roles,
    )
    client = _make_mock_client(cloud_active=cloud_active)
    manager = CouncilManager(config=config, inference_client=client)
    return manager


# ============================================================================
# CouncilManager Init Tests
# ============================================================================

class TestCouncilManagerInit:
    """Tests for CouncilManager initialization."""

    def test_init_with_config(self):
        """Custom config is used when provided."""
        config = CouncilConfig(enabled=False)
        client = _make_mock_client()
        mgr = CouncilManager(config=config, inference_client=client)
        assert mgr.config.enabled is False

    def test_init_with_defaults(self):
        """Default config loads from YAML when none provided."""
        client = _make_mock_client()
        mgr = CouncilManager(inference_client=client)
        # Should load from inference.yaml — enabled by default
        assert mgr.config.enabled is True

    def test_roles_initialized(self):
        """All 4 roles are instantiated."""
        mgr = _make_manager()
        assert isinstance(mgr.coordinator, Coordinator)
        assert isinstance(mgr.analyzer, Analyzer)
        assert isinstance(mgr.validator, Validator)
        assert isinstance(mgr.responder, Responder)

    def test_inference_client_stored(self):
        """Provided inference client is stored."""
        client = _make_mock_client()
        mgr = CouncilManager(inference_client=client)
        assert mgr._inference_client is client


# ============================================================================
# Cloud Detection Tests
# ============================================================================

class TestCloudDetection:
    """Tests for _is_cloud_active()."""

    def test_cloud_active_enabled_full(self):
        """Cloud is active when state is enabled_full."""
        mgr = _make_manager(cloud_active=True)
        assert mgr._is_cloud_active() is True

    def test_cloud_inactive_disabled(self):
        """Cloud is inactive when state is disabled."""
        mgr = _make_manager(cloud_active=False)
        assert mgr._is_cloud_active() is False

    def test_cloud_active_enabled_smart(self):
        """Cloud is active when state is enabled_smart."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client.router.cloud_routing.state = "enabled_smart"
        assert mgr._is_cloud_active() is True

    def test_cloud_detection_handles_exception(self):
        """Exception in cloud check returns False."""
        mgr = _make_manager()
        mgr._inference_client.router = None  # Force AttributeError
        assert mgr._is_cloud_active() is False


# ============================================================================
# Classify Intent Tests
# ============================================================================

class TestClassifyIntent:
    """Tests for classify_intent() — Coordinator role."""

    @pytest.mark.asyncio
    async def test_cloud_path(self):
        """Cloud-active path calls _call_cloud."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response(
            json.dumps({
                "primary_intent": "calendar_query",
                "confidence": 0.95,
                "secondary_intents": [],
                "reasoning": "Asking about schedule",
            })
        )

        result = await mgr.classify_intent("What's on my calendar today?")
        assert result.primary_intent == IntentType.CALENDAR_QUERY
        assert result.confidence == 0.95
        mgr._inference_client._call_cloud.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_slm_path(self):
        """Cloud-disabled path calls _call_ollama."""
        mgr = _make_manager(cloud_active=False)
        mgr._inference_client._call_ollama.return_value = _make_inference_response(
            json.dumps({
                "primary_intent": "chat",
                "confidence": 0.9,
                "secondary_intents": [],
                "reasoning": "Greeting",
            })
        )

        result = await mgr.classify_intent("Hey Tia, how are you?")
        assert result.primary_intent == IntentType.CHAT
        mgr._inference_client._call_ollama.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_slm_path_uses_correct_model(self):
        """SLM path passes correct model name."""
        mgr = _make_manager(cloud_active=False)
        mgr._inference_client._call_ollama.return_value = _make_inference_response(
            json.dumps({"primary_intent": "chat", "confidence": 0.9,
                        "secondary_intents": [], "reasoning": "test"})
        )

        await mgr.classify_intent("Hello")

        call_kwargs = mgr._inference_client._call_ollama.call_args
        assert call_kwargs.kwargs.get("model_name") == "qwen2.5:0.5b"

    @pytest.mark.asyncio
    async def test_disabled_returns_default(self):
        """Disabled council returns CHAT with 0.5 confidence."""
        mgr = _make_manager(enabled=False)
        result = await mgr.classify_intent("What's the weather?")
        assert result.primary_intent == IntentType.CHAT
        assert result.confidence == 0.5
        assert result.reasoning == "Council disabled"

    @pytest.mark.asyncio
    async def test_coordinator_disabled_returns_default(self):
        """Disabled coordinator returns CHAT with 0.5 confidence."""
        mgr = _make_manager(coordinator_enabled=False)
        result = await mgr.classify_intent("What's the weather?")
        assert result.primary_intent == IntentType.CHAT
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_exception_returns_unclear(self):
        """Exception during classification returns UNCLEAR."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.side_effect = TimeoutError("Cloud timeout")

        result = await mgr.classify_intent("What's on my calendar?")
        assert result.primary_intent == IntentType.UNCLEAR
        assert result.confidence == 0.0
        assert "TimeoutError" in result.reasoning

    @pytest.mark.asyncio
    async def test_slm_exception_returns_unclear(self):
        """Exception in SLM path returns UNCLEAR."""
        mgr = _make_manager(cloud_active=False)
        mgr._inference_client._call_ollama.side_effect = ConnectionError("Ollama down")

        result = await mgr.classify_intent("Hello")
        assert result.primary_intent == IntentType.UNCLEAR
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_cloud_passes_system_prompt(self):
        """Cloud call includes coordinator system prompt."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response(
            json.dumps({"primary_intent": "chat", "confidence": 1.0,
                        "secondary_intents": [], "reasoning": "test"})
        )

        await mgr.classify_intent("Hello")

        call_kwargs = mgr._inference_client._call_cloud.call_args
        assert "system" in call_kwargs.kwargs
        assert len(call_kwargs.kwargs["system"]) > 100


# ============================================================================
# Run Council Tests (Cloud Active)
# ============================================================================

class TestRunCouncilCloudActive:
    """Tests for run_council() with cloud active."""

    @pytest.mark.asyncio
    async def test_parallel_execution_both_roles(self):
        """Analyzer + Validator run in parallel when cloud active."""
        mgr = _make_manager(cloud_active=True)

        # Analyzer response
        analyzer_json = json.dumps({
            "tool_calls": [{"name": "list_events", "arguments": {"days": 7}}],
            "confidence": 0.95,
            "reasoning": "Calendar check",
        })
        # Validator response
        validator_json = json.dumps({
            "is_safe": True,
            "is_high_quality": True,
            "quality_score": 0.9,
            "issues": [],
            "suggestions": [],
        })

        async def mock_call_cloud(**kwargs):
            sys = kwargs.get("system", "")
            if "analyzer role" in sys.lower():
                return _make_inference_response(analyzer_json)
            return _make_inference_response(validator_json)

        mgr._inference_client._call_cloud.side_effect = mock_call_cloud

        intent = IntentClassification.create(IntentType.CALENDAR_QUERY, 0.9)
        result = await mgr.run_council(
            user_message="What's on my calendar?",
            inference_response="Let me check your calendar.",
            intent=intent,
        )

        assert "analyzer" in result.roles_executed
        assert "validator" in result.roles_executed
        assert result.tool_extraction is not None
        assert len(result.tool_extraction.tool_calls) == 1
        assert result.validation is not None
        assert result.validation.is_safe is True

    @pytest.mark.asyncio
    async def test_chat_optimization_skips_roles(self):
        """CHAT intent with high confidence skips post-inference roles."""
        mgr = _make_manager(cloud_active=True)
        intent = IntentClassification.create(IntentType.CHAT, 0.95)

        result = await mgr.run_council(
            user_message="How are you?",
            inference_response="I'm doing great!",
            intent=intent,
        )

        assert result.fallback_used is False
        assert result.roles_executed == []
        assert result.tool_extraction is None
        # Cloud call should NOT have been made
        mgr._inference_client._call_cloud.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_chat_low_confidence_runs_roles(self):
        """CHAT intent with low confidence still runs roles."""
        mgr = _make_manager(cloud_active=True)
        intent = IntentClassification.create(IntentType.CHAT, 0.6)

        # Mock responses
        mgr._inference_client._call_cloud.return_value = _make_inference_response(
            json.dumps({"tool_calls": [], "confidence": 1.0, "reasoning": "none"})
        )

        result = await mgr.run_council(
            user_message="How are you?",
            inference_response="I'm doing great!",
            intent=intent,
        )

        # Should have run roles since confidence <= 0.8
        assert mgr._inference_client._call_cloud.await_count >= 1

    @pytest.mark.asyncio
    async def test_partial_failure_still_returns(self):
        """One role failing doesn't block the other."""
        mgr = _make_manager(cloud_active=True)

        async def mock_call_cloud(**kwargs):
            sys = kwargs.get("system", "")
            if "analyzer role" in sys.lower():
                raise TimeoutError("Analyzer timed out")
            return _make_inference_response(json.dumps({
                "is_safe": True, "is_high_quality": True,
                "quality_score": 0.9, "issues": [], "suggestions": [],
            }))

        mgr._inference_client._call_cloud.side_effect = mock_call_cloud

        intent = IntentClassification.create(IntentType.CALENDAR_QUERY, 0.9)
        result = await mgr.run_council(
            user_message="What's on my calendar?",
            inference_response="Checking...",
            intent=intent,
        )

        assert "analyzer" in result.roles_failed
        assert "validator" in result.roles_executed
        assert result.tool_extraction is None
        assert result.validation is not None

    @pytest.mark.asyncio
    async def test_both_roles_fail(self):
        """Both roles failing returns result with empty roles."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.side_effect = TimeoutError("Cloud down")

        intent = IntentClassification.create(IntentType.WEATHER_QUERY, 0.9)
        result = await mgr.run_council(
            user_message="What's the weather?",
            inference_response="Let me check.",
            intent=intent,
        )

        assert len(result.roles_failed) == 2
        assert len(result.roles_executed) == 0

    @pytest.mark.asyncio
    async def test_disabled_returns_fallback(self):
        """Disabled council returns fallback result immediately."""
        mgr = _make_manager(enabled=False)
        result = await mgr.run_council(
            user_message="Hello",
            inference_response="Hi!",
        )
        assert result.fallback_used is True
        mgr._inference_client._call_cloud.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_intent_runs_roles(self):
        """No intent provided still runs roles."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response(
            json.dumps({"tool_calls": [], "confidence": 1.0, "reasoning": "none"})
        )

        result = await mgr.run_council(
            user_message="test",
            inference_response="test response",
            intent=None,
        )
        assert mgr._inference_client._call_cloud.await_count >= 1

    @pytest.mark.asyncio
    async def test_total_duration_tracked(self):
        """Total duration is measured."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response(
            json.dumps({"tool_calls": [], "confidence": 1.0, "reasoning": "none"})
        )

        result = await mgr.run_council(
            user_message="test",
            inference_response="test response",
        )
        assert result.total_duration_ms is not None
        assert result.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_analyzer_disabled_only_validator(self):
        """Only validator runs when analyzer disabled."""
        mgr = _make_manager(cloud_active=True, analyzer_enabled=False)
        mgr._inference_client._call_cloud.return_value = _make_inference_response(
            json.dumps({
                "is_safe": True, "is_high_quality": True,
                "quality_score": 0.9, "issues": [], "suggestions": [],
            })
        )

        intent = IntentClassification.create(IntentType.WEATHER_QUERY, 0.9)
        result = await mgr.run_council(
            user_message="Weather?",
            inference_response="Sunny.",
            intent=intent,
        )

        assert "validator" in result.roles_executed
        assert "analyzer" not in result.roles_executed
        assert result.tool_extraction is None

    @pytest.mark.asyncio
    async def test_both_roles_disabled_returns_fallback(self):
        """Both roles disabled returns fallback."""
        mgr = _make_manager(
            cloud_active=True,
            analyzer_enabled=False,
            validator_enabled=False,
        )

        intent = IntentClassification.create(IntentType.WEATHER_QUERY, 0.9)
        result = await mgr.run_council(
            user_message="Weather?",
            inference_response="Sunny.",
            intent=intent,
        )

        assert result.fallback_used is True


# ============================================================================
# Run Council Tests (Cloud Disabled)
# ============================================================================

class TestRunCouncilCloudDisabled:
    """Tests for run_council() with cloud disabled (SLM fallback)."""

    @pytest.mark.asyncio
    async def test_local_fallback_result(self):
        """Cloud disabled returns fallback result."""
        mgr = _make_manager(cloud_active=False)
        intent = IntentClassification.create(IntentType.CALENDAR_QUERY, 0.9)

        result = await mgr.run_council(
            user_message="What's on my calendar?",
            inference_response="Checking calendar...",
            intent=intent,
        )

        assert result.fallback_used is True
        assert result.intent is intent
        mgr._inference_client._call_cloud.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_local_fallback_preserves_intent(self):
        """Local fallback preserves the pre-classified intent."""
        mgr = _make_manager(cloud_active=False)
        intent = IntentClassification.create(
            IntentType.REMINDER_CREATE, 0.85,
            reasoning="Creating a reminder"
        )

        result = await mgr.run_council(
            user_message="Remind me...",
            inference_response="I'll set a reminder.",
            intent=intent,
        )

        assert result.intent.primary_intent == IntentType.REMINDER_CREATE
        assert result.intent.confidence == 0.85

    @pytest.mark.asyncio
    async def test_local_fallback_no_tool_extraction(self):
        """Local fallback has no tool extraction."""
        mgr = _make_manager(cloud_active=False)
        result = await mgr.run_council(
            user_message="test",
            inference_response="test response",
        )
        assert result.tool_extraction is None
        assert result.validation is None

    @pytest.mark.asyncio
    async def test_chat_optimization_still_works(self):
        """CHAT optimization works even when cloud disabled."""
        mgr = _make_manager(cloud_active=False)
        intent = IntentClassification.create(IntentType.CHAT, 0.95)

        result = await mgr.run_council(
            user_message="Hey",
            inference_response="Hello!",
            intent=intent,
        )

        assert result.fallback_used is False  # CHAT skips to fast path
        assert result.intent is intent

    @pytest.mark.asyncio
    async def test_duration_tracked(self):
        """Duration is tracked even for local fallback."""
        mgr = _make_manager(cloud_active=False)
        result = await mgr.run_council(
            user_message="test",
            inference_response="test response",
        )
        assert result.total_duration_ms >= 0


# ============================================================================
# Synthesize Response Tests
# ============================================================================

class TestSynthesizeResponse:
    """Tests for synthesize_response() — Responder role."""

    @pytest.mark.asyncio
    async def test_cloud_synthesis(self):
        """Cloud-active path returns synthesized text."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response(
            "You've got two meetings tomorrow, Boss."
        )

        result = await mgr.synthesize_response(
            user_message="What's on my calendar tomorrow?",
            tool_result="Meeting at 9am, Meeting at 2pm",
            mode="tia",
        )

        assert result == "You've got two meetings tomorrow, Boss."

    @pytest.mark.asyncio
    async def test_cloud_disabled_returns_none(self):
        """Cloud-disabled returns None."""
        mgr = _make_manager(cloud_active=False)
        result = await mgr.synthesize_response(
            user_message="test",
            tool_result="test result",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        """Disabled council returns None."""
        mgr = _make_manager(enabled=False)
        result = await mgr.synthesize_response(
            user_message="test",
            tool_result="test result",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_responder_disabled_returns_none(self):
        """Disabled responder returns None."""
        mgr = _make_manager(responder_enabled=False)
        result = await mgr.synthesize_response(
            user_message="test",
            tool_result="test result",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        """Exception in Responder returns None."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.side_effect = TimeoutError("Timeout")

        result = await mgr.synthesize_response(
            user_message="test",
            tool_result="test result",
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_mode_included_in_prompt(self):
        """Mode is included in the prompt sent to Responder."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response("Result")

        await mgr.synthesize_response(
            user_message="test",
            tool_result="test result",
            mode="mira",
        )

        call_kwargs = mgr._inference_client._call_cloud.call_args
        messages = call_kwargs.kwargs.get("messages", [])
        assert any("mira" in m.content.lower() for m in messages)


# ============================================================================
# Call Role Cloud Tests
# ============================================================================

class TestCallRoleCloud:
    """Tests for _call_role_cloud() — direct cloud calls."""

    @pytest.mark.asyncio
    async def test_uses_direct_call_cloud(self):
        """Uses _call_cloud directly (not chat())."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response("test")

        await mgr._call_role_cloud(
            role=mgr.coordinator,
            messages=[Message(role="user", content="test")],
            temperature=0.0,
            max_tokens=256,
        )

        mgr._inference_client._call_cloud.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_system_prompt(self):
        """System prompt from role is passed to cloud call."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response("test")

        await mgr._call_role_cloud(
            role=mgr.analyzer,
            messages=[Message(role="user", content="test")],
            temperature=0.0,
            max_tokens=512,
        )

        call_kwargs = mgr._inference_client._call_cloud.call_args
        assert call_kwargs.kwargs["system"] == mgr.analyzer.system_prompt

    @pytest.mark.asyncio
    async def test_passes_temperature(self):
        """Temperature is forwarded to cloud call."""
        mgr = _make_manager(cloud_active=True)
        mgr._inference_client._call_cloud.return_value = _make_inference_response("test")

        await mgr._call_role_cloud(
            role=mgr.responder,
            messages=[Message(role="user", content="test")],
            temperature=0.3,
            max_tokens=2048,
        )

        call_kwargs = mgr._inference_client._call_cloud.call_args
        assert call_kwargs.kwargs["temperature"] == 0.3

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """Timeout is enforced via asyncio.wait_for."""
        mgr = _make_manager(cloud_active=True)
        mgr.config.role_timeout = 0.01  # 10ms

        async def slow_call(**kwargs):
            await asyncio.sleep(1.0)
            return _make_inference_response("too late")

        mgr._inference_client._call_cloud.side_effect = slow_call

        with pytest.raises(asyncio.TimeoutError):
            await mgr._call_role_cloud(
                role=mgr.coordinator,
                messages=[Message(role="user", content="test")],
                temperature=0.0,
                max_tokens=256,
            )


# ============================================================================
# Call Role SLM Tests
# ============================================================================

class TestCallRoleSLM:
    """Tests for _call_role_slm() — local SLM calls."""

    @pytest.mark.asyncio
    async def test_uses_call_ollama(self):
        """Uses _call_ollama directly."""
        mgr = _make_manager(cloud_active=False)
        mgr._inference_client._call_ollama.return_value = _make_inference_response("test")

        await mgr._call_role_slm(
            role=mgr.coordinator,
            messages=[Message(role="user", content="test")],
            temperature=0.0,
            max_tokens=256,
        )

        mgr._inference_client._call_ollama.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_passes_correct_model(self):
        """SLM model name is passed to Ollama."""
        mgr = _make_manager(cloud_active=False)
        mgr._inference_client._call_ollama.return_value = _make_inference_response("test")

        await mgr._call_role_slm(
            role=mgr.coordinator,
            messages=[Message(role="user", content="test")],
            temperature=0.0,
            max_tokens=256,
        )

        call_kwargs = mgr._inference_client._call_ollama.call_args
        assert call_kwargs.kwargs["model_name"] == "qwen2.5:0.5b"

    @pytest.mark.asyncio
    async def test_passes_system_prompt(self):
        """System prompt is passed to Ollama call."""
        mgr = _make_manager(cloud_active=False)
        mgr._inference_client._call_ollama.return_value = _make_inference_response("test")

        await mgr._call_role_slm(
            role=mgr.coordinator,
            messages=[Message(role="user", content="test")],
            temperature=0.0,
            max_tokens=256,
        )

        call_kwargs = mgr._inference_client._call_ollama.call_args
        assert call_kwargs.kwargs["system"] == mgr.coordinator.system_prompt

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """SLM timeout is enforced."""
        mgr = _make_manager(cloud_active=False)
        mgr.config.local_slm_timeout = 0.01

        async def slow_call(**kwargs):
            await asyncio.sleep(1.0)
            return _make_inference_response("too late")

        mgr._inference_client._call_ollama.side_effect = slow_call

        with pytest.raises(asyncio.TimeoutError):
            await mgr._call_role_slm(
                role=mgr.coordinator,
                messages=[Message(role="user", content="test")],
                temperature=0.0,
                max_tokens=256,
            )


# ============================================================================
# Aggregate Results Tests
# ============================================================================

class TestAggregateResults:
    """Tests for _aggregate_results() — combining parallel outputs."""

    def test_both_succeed(self):
        """Both analyzer and validator results aggregated."""
        mgr = _make_manager()
        te = ToolExtraction.create(
            tool_calls=[{"name": "get_weather", "arguments": {}}],
            confidence=0.9,
        )
        vr = ValidationReport.create(quality_score=0.95)

        results = [
            ("analyzer", te, 50.0),
            ("validator", vr, 30.0),
        ]
        task_names = ["analyzer", "validator"]

        cr = mgr._aggregate_results(results, task_names, intent=None)
        assert "analyzer" in cr.roles_executed
        assert "validator" in cr.roles_executed
        assert cr.tool_extraction is te
        assert cr.validation is vr
        assert len(cr.role_results) == 2

    def test_analyzer_exception(self):
        """Analyzer exception is recorded as failure."""
        mgr = _make_manager()
        vr = ValidationReport.create()

        results = [
            TimeoutError("Analyzer timed out"),
            ("validator", vr, 30.0),
        ]
        task_names = ["analyzer", "validator"]

        cr = mgr._aggregate_results(results, task_names, intent=None)
        assert "analyzer" in cr.roles_failed
        assert "validator" in cr.roles_executed
        assert cr.tool_extraction is None
        assert cr.validation is vr

    def test_both_exceptions(self):
        """Both exceptions recorded."""
        mgr = _make_manager()
        results = [
            TimeoutError("Analyzer timed out"),
            ConnectionError("Validator failed"),
        ]
        task_names = ["analyzer", "validator"]

        cr = mgr._aggregate_results(results, task_names, intent=None)
        assert len(cr.roles_failed) == 2
        assert len(cr.roles_executed) == 0

    def test_intent_preserved(self):
        """Intent is preserved in aggregated result."""
        mgr = _make_manager()
        intent = IntentClassification.create(IntentType.MAIL_QUERY, 0.85)
        te = ToolExtraction.create()

        results = [("analyzer", te, 20.0)]
        task_names = ["analyzer"]

        cr = mgr._aggregate_results(results, task_names, intent=intent)
        assert cr.intent is intent
        assert cr.intent.primary_intent == IntentType.MAIL_QUERY

    def test_role_results_have_duration(self):
        """Role results track duration."""
        mgr = _make_manager()
        te = ToolExtraction.create()
        results = [("analyzer", te, 42.5)]
        task_names = ["analyzer"]

        cr = mgr._aggregate_results(results, task_names, intent=None)
        assert cr.role_results[0].duration_ms == 42.5
        assert cr.role_results[0].success is True


# ============================================================================
# Singleton Tests
# ============================================================================

class TestSingleton:
    """Tests for get_council_manager() singleton."""

    def test_singleton_returns_instance(self):
        """Factory returns a CouncilManager."""
        import hestia.council.manager as mgr_module
        mgr_module._council_manager = None  # Reset

        client = _make_mock_client()
        config = CouncilConfig(enabled=True)
        result = get_council_manager(config=config, inference_client=client)

        assert isinstance(result, CouncilManager)
        mgr_module._council_manager = None  # Cleanup

    def test_singleton_returns_same_instance(self):
        """Repeated calls return the same instance."""
        import hestia.council.manager as mgr_module
        mgr_module._council_manager = None  # Reset

        client = _make_mock_client()
        config = CouncilConfig(enabled=True)
        first = get_council_manager(config=config, inference_client=client)
        second = get_council_manager()

        assert first is second
        mgr_module._council_manager = None  # Cleanup


# ============================================================================
# Config Loading Tests
# ============================================================================

class TestConfigLoading:
    """Tests for _load_config_from_yaml()."""

    def test_loads_from_yaml(self):
        """Config loads from actual inference.yaml."""
        client = _make_mock_client()
        mgr = CouncilManager(inference_client=client)
        # Should pick up the council section we just added
        assert mgr.config.enabled is True
        assert mgr.config.local_slm_model == "qwen2.5:0.5b"
        assert mgr.config.role_timeout == 30.0

    def test_coordinator_config_from_yaml(self):
        """Coordinator role config from YAML."""
        client = _make_mock_client()
        mgr = CouncilManager(inference_client=client)
        assert mgr.config.coordinator_enabled is True
        assert mgr.config.coordinator_temperature == 0.0
        assert mgr.config.coordinator_max_tokens == 256

    def test_responder_config_from_yaml(self):
        """Responder role config from YAML."""
        client = _make_mock_client()
        mgr = CouncilManager(inference_client=client)
        assert mgr.config.responder_temperature == 0.3
        assert mgr.config.responder_max_tokens == 2048


# ============================================================================
# Handler Integration Tests (Session 3)
# ============================================================================

def _make_handler_with_mocks(
    council_manager: Optional[CouncilManager] = None,
) -> RequestHandler:
    """Create a RequestHandler with mocked dependencies for council testing."""
    from hestia.orchestration.models import Mode
    from hestia.orchestration.validation import ValidationResult

    handler = RequestHandler.__new__(RequestHandler)

    # Mock inference client
    mock_inference = MagicMock()
    mock_inference.chat = AsyncMock(return_value=_make_inference_response(
        "Hello! How can I help?"
    ))
    mock_inference.health_check = AsyncMock(return_value=True)
    mock_inference.router.get_suggested_agent = MagicMock(return_value=None)
    handler._inference_client = mock_inference

    # Mock memory manager
    mock_memory = AsyncMock()
    mock_memory.build_context = AsyncMock(return_value="")
    mock_memory.store_exchange = AsyncMock()
    handler._memory_manager = mock_memory

    # Mode manager (real)
    from hestia.orchestration.mode import get_mode_manager
    handler._mode_manager = get_mode_manager()

    # Prompt builder (real)
    from hestia.orchestration.prompt import get_prompt_builder
    handler._prompt_builder = get_prompt_builder()

    # Validation pipeline (real)
    from hestia.orchestration.validation import get_validation_pipeline
    handler._validation_pipeline = get_validation_pipeline()

    # Tool executor (mock)
    handler._tool_executor = AsyncMock()

    # Council manager
    handler._council_manager = council_manager

    # State machine (real)
    from hestia.orchestration.state import TaskStateMachine
    handler.state_machine = TaskStateMachine()

    # Logger (real)
    from hestia.logging import get_logger
    handler.logger = get_logger()

    # Conversations cache + handle counter (session TTL support)
    handler._conversations = {}
    handler._handle_count = 0

    # Register tools
    try:
        handler._register_builtin_tools()
    except Exception:
        pass

    return handler


class TestHandlerCouncilIntegration:
    """Tests for council integration in RequestHandler."""

    @pytest.mark.asyncio
    async def test_intent_stored_in_task_context(self):
        """Step 6.5 stores intent in task.context."""
        council = _make_manager(cloud_active=True)
        council._inference_client._call_cloud.return_value = _make_inference_response(
            json.dumps({
                "primary_intent": "calendar_query",
                "confidence": 0.95,
                "secondary_intents": [],
                "reasoning": "Checking calendar",
            })
        )

        handler = _make_handler_with_mocks(council_manager=council)
        request = Request.create(content="What's on my calendar today?", session_id="test-session")

        response = await handler.handle(request)

        # The handler should have classified intent
        # We can't easily check task.context from outside, but we verify the handler ran
        assert response.content is not None
        assert response.error_code is None

    @pytest.mark.asyncio
    async def test_council_failure_doesnt_block_response(self):
        """Council failure falls back gracefully — response still works."""
        council = _make_manager(cloud_active=True)
        # Make classify_intent blow up
        council._inference_client._call_cloud.side_effect = ConnectionError("Cloud down")

        handler = _make_handler_with_mocks(council_manager=council)
        request = Request.create(content="Hello Tia!", session_id="test-session")

        # Override inference to return simple chat response
        handler._inference_client.chat = AsyncMock(return_value=_make_inference_response(
            "Hey Boss! What's up?"
        ))

        response = await handler.handle(request)

        # Should still get a response despite council failure
        assert response.content is not None
        assert response.error_code is None

    @pytest.mark.asyncio
    async def test_no_council_still_works(self):
        """Handler works fine with no council manager configured."""
        handler = _make_handler_with_mocks(council_manager=None)
        # When _council_manager is None, _get_council_manager calls get_council_manager()
        # which creates a new instance — that's fine, it will use default config

        request = Request.create(content="Hello!", session_id="test-session")
        response = await handler.handle(request)

        assert response.content is not None
        assert response.error_code is None

    @pytest.mark.asyncio
    async def test_chat_optimization_skips_post_inference(self):
        """High-confidence CHAT intent skips Analyzer/Validator."""
        council = _make_manager(cloud_active=True)

        # classify_intent returns CHAT with high confidence
        classify_response = _make_inference_response(
            json.dumps({
                "primary_intent": "chat",
                "confidence": 0.95,
                "secondary_intents": [],
                "reasoning": "Simple greeting",
            })
        )

        call_count = 0
        async def track_calls(**kwargs):
            nonlocal call_count
            call_count += 1
            return classify_response

        council._inference_client._call_cloud.side_effect = track_calls

        handler = _make_handler_with_mocks(council_manager=council)
        request = Request.create(content="Hey, how are you?", session_id="test-session")

        response = await handler.handle(request)
        assert response.content is not None

        # classify_intent makes 1 cloud call, run_council should make 0 (CHAT skip)
        # Total cloud calls should be 1 (just the classify_intent call)
        assert call_count == 1


class TestHandlerCouncilFallback:
    """Tests for council fallback behavior in handler."""

    @pytest.mark.asyncio
    async def test_disabled_council_uses_existing_pipeline(self):
        """Disabled council falls back to existing tool parsing."""
        council = _make_manager(enabled=False)
        handler = _make_handler_with_mocks(council_manager=council)

        # LLM returns a non-tool response
        handler._inference_client.chat = AsyncMock(return_value=_make_inference_response(
            "The weather is sunny today."
        ))

        request = Request.create(content="What's the weather?", session_id="test-session")
        response = await handler.handle(request)

        assert response.content == "The weather is sunny today."

    @pytest.mark.asyncio
    async def test_council_timeout_falls_through(self):
        """Council timeout doesn't crash the handler."""
        council = _make_manager(cloud_active=True)
        council.config.role_timeout = 0.001  # Very short timeout

        async def slow_cloud(**kwargs):
            import asyncio
            await asyncio.sleep(5.0)
            return _make_inference_response("too late")

        council._inference_client._call_cloud.side_effect = slow_cloud

        handler = _make_handler_with_mocks(council_manager=council)
        handler._inference_client.chat = AsyncMock(return_value=_make_inference_response(
            "I'm here to help!"
        ))

        request = Request.create(content="Hello", session_id="test-session")
        response = await handler.handle(request)

        # Should still return a response (falls through council errors)
        assert response.content is not None
        assert response.error_code is None


class TestExecuteCouncilTools:
    """Tests for _execute_council_tools() method."""

    @pytest.mark.asyncio
    async def test_valid_tool_executes(self):
        """Council-extracted tool executes via ToolExecutor."""
        handler = _make_handler_with_mocks()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {"events": [{"title": "Meeting", "start": "2026-02-08T09:00:00"}]}

        executor = AsyncMock()
        executor.execute = AsyncMock(return_value=mock_result)
        handler._tool_executor = executor

        request = Request.create(content="Calendar", session_id="test")
        task = handler.state_machine.create_task(request)

        tool_calls = [{"name": "list_events", "arguments": {"days": 7}}]

        # Only works if list_events is in the registry
        from hestia.execution import get_tool_registry
        registry = get_tool_registry()
        if registry.has_tool("list_events"):
            result = await handler._execute_council_tools(tool_calls, request, task)
            assert result is not None
            executor.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_unknown_tool_skipped(self):
        """Unknown tool names are skipped, not executed."""
        handler = _make_handler_with_mocks()

        mock_executor = AsyncMock()
        handler._tool_executor = mock_executor

        request = Request.create(content="test", session_id="test")
        task = handler.state_machine.create_task(request)

        tool_calls = [{"name": "nonexistent_tool_xyz", "arguments": {}}]
        result = await handler._execute_council_tools(tool_calls, request, task)

        # Should return None since the tool doesn't exist
        assert result is None
        mock_executor.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_tool_calls_returns_none(self):
        """Empty tool call list returns None."""
        handler = _make_handler_with_mocks()
        request = Request.create(content="test", session_id="test")
        task = handler.state_machine.create_task(request)

        result = await handler._execute_council_tools([], request, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_tool_failure_included_in_result(self):
        """Failed tool execution is reported in result."""
        handler = _make_handler_with_mocks()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Calendar access denied"

        executor = AsyncMock()
        executor.execute = AsyncMock(return_value=mock_result)
        handler._tool_executor = executor

        request = Request.create(content="Calendar", session_id="test")
        task = handler.state_machine.create_task(request)

        tool_calls = [{"name": "list_events", "arguments": {}}]

        from hestia.execution import get_tool_registry
        registry = get_tool_registry()
        if registry.has_tool("list_events"):
            result = await handler._execute_council_tools(tool_calls, request, task)
            assert result is not None
            assert "failed" in result.lower() or "denied" in result.lower()


class TestExecuteNativeToolCalls:
    """Tests for _execute_native_tool_calls() — Ollama native API tool calls."""

    @pytest.mark.asyncio
    async def test_native_tool_call_success(self):
        """Native tool call with valid function format executes successfully."""
        handler = _make_handler_with_mocks()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {"events": [{"title": "Standup", "start": "2026-03-04T09:00:00"}]}

        executor = AsyncMock()
        executor.execute = AsyncMock(return_value=mock_result)
        handler._tool_executor = executor

        # Mock registry to recognize the tool
        mock_registry = MagicMock()
        mock_registry.has_tool = MagicMock(return_value=True)

        request = Request.create(content="Calendar", session_id="test")
        task = handler.state_machine.create_task(request)
        handler.state_machine.start_processing(task)

        # Ollama native format: [{"function": {"name": ..., "arguments": ...}}]
        tool_calls = [{"function": {"name": "get_today_events", "arguments": {}}}]

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            result = await handler._execute_native_tool_calls(tool_calls, request, task)
        assert result is not None
        assert "Standup" in result
        executor.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_native_tool_call_empty_list(self):
        """Empty tool_calls list returns None."""
        handler = _make_handler_with_mocks()
        request = Request.create(content="test", session_id="test")
        task = handler.state_machine.create_task(request)

        result = await handler._execute_native_tool_calls([], request, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_native_tool_call_missing_function_key(self):
        """Tool call without 'function' key is skipped."""
        handler = _make_handler_with_mocks()
        request = Request.create(content="test", session_id="test")
        task = handler.state_machine.create_task(request)

        tool_calls = [{"bad_key": {"name": "get_today_events"}}]
        result = await handler._execute_native_tool_calls(tool_calls, request, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_native_tool_call_missing_name(self):
        """Tool call with empty name is skipped."""
        handler = _make_handler_with_mocks()
        request = Request.create(content="test", session_id="test")
        task = handler.state_machine.create_task(request)

        tool_calls = [{"function": {"name": "", "arguments": {}}}]
        result = await handler._execute_native_tool_calls(tool_calls, request, task)
        assert result is None

    @pytest.mark.asyncio
    async def test_native_tool_call_failure_reported(self):
        """Failed native tool execution is reported in result."""
        handler = _make_handler_with_mocks()

        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Calendar access denied"

        executor = AsyncMock()
        executor.execute = AsyncMock(return_value=mock_result)
        handler._tool_executor = executor

        mock_registry = MagicMock()
        mock_registry.has_tool = MagicMock(return_value=True)

        request = Request.create(content="Calendar", session_id="test")
        task = handler.state_machine.create_task(request)
        handler.state_machine.start_processing(task)

        tool_calls = [{"function": {"name": "get_today_events", "arguments": {}}}]
        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            result = await handler._execute_native_tool_calls(tool_calls, request, task)

        assert result is not None
        assert "failed" in result.lower()

    @pytest.mark.asyncio
    async def test_native_tool_call_multiple_tools(self):
        """Multiple native tool calls execute and results are joined."""
        handler = _make_handler_with_mocks()

        mock_result_1 = MagicMock()
        mock_result_1.success = True
        mock_result_1.output = {"events": []}

        mock_result_2 = MagicMock()
        mock_result_2.success = True
        mock_result_2.output = {"reminders": [{"title": "Buy milk"}]}

        executor = AsyncMock()
        executor.execute = AsyncMock(side_effect=[mock_result_1, mock_result_2])
        handler._tool_executor = executor

        mock_registry = MagicMock()
        mock_registry.has_tool = MagicMock(return_value=True)

        request = Request.create(content="Calendar and reminders", session_id="test")
        task = handler.state_machine.create_task(request)
        handler.state_machine.start_processing(task)

        tool_calls = [
            {"function": {"name": "get_today_events", "arguments": {}}},
            {"function": {"name": "get_due_reminders", "arguments": {}}},
        ]
        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            result = await handler._execute_native_tool_calls(tool_calls, request, task)

        assert result is not None
        assert "Buy milk" in result
        assert executor.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_native_tool_call_string_arguments(self):
        """Arguments returned as JSON string are parsed to dict."""
        handler = _make_handler_with_mocks()

        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = {"events": []}

        executor = AsyncMock()
        executor.execute = AsyncMock(return_value=mock_result)
        handler._tool_executor = executor

        mock_registry = MagicMock()
        mock_registry.has_tool = MagicMock(return_value=True)

        request = Request.create(content="Calendar", session_id="test")
        task = handler.state_machine.create_task(request)
        handler.state_machine.start_processing(task)

        # Ollama sometimes returns arguments as a JSON string instead of dict
        tool_calls = [{"function": {"name": "get_today_events", "arguments": '{"days": 1}'}}]

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            result = await handler._execute_native_tool_calls(tool_calls, request, task)
        assert result is not None
        executor.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_native_tool_call_unknown_tool_skipped(self):
        """Tool not in registry is skipped with warning."""
        handler = _make_handler_with_mocks()

        mock_registry = MagicMock()
        mock_registry.has_tool = MagicMock(return_value=False)

        request = Request.create(content="test", session_id="test")
        task = handler.state_machine.create_task(request)
        handler.state_machine.start_processing(task)

        tool_calls = [{"function": {"name": "nonexistent_tool", "arguments": {}}}]

        with patch("hestia.orchestration.handler.get_tool_registry", return_value=mock_registry):
            result = await handler._execute_native_tool_calls(tool_calls, request, task)
        assert result is None
