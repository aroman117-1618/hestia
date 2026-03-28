"""Tests for hestia.dev.architect — ArchitectAgent planning and review."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from hestia.dev.architect import ArchitectAgent
from hestia.dev.models import DevSession, DevSessionSource
from hestia.inference.client import InferenceResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(**kwargs) -> DevSession:
    """Factory for a minimal DevSession."""
    defaults = dict(
        title="Test task",
        description="Do the thing",
        source=DevSessionSource.CLI,
    )
    defaults.update(kwargs)
    return DevSession.create(**defaults)


def _make_plan_payload(**overrides) -> dict:
    base = {
        "steps": ["step1", "step2"],
        "files": ["hestia/dev/architect.py"],
        "risk": "low",
        "estimated_minutes": 15,
        "complexity": "simple",
        "subtasks": [{"title": "Do thing", "files": ["hestia/dev/architect.py"]}],
    }
    base.update(overrides)
    return base


def _mock_cloud(json_payload: dict) -> AsyncMock:
    """Return a cloud client mock whose complete() returns the given JSON."""
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=InferenceResponse(
            content=json.dumps(json_payload),
            model="claude-opus-4-20250514",
            tokens_in=500,
            tokens_out=200,
            duration_ms=1200.0,
        )
    )
    return client


# ---------------------------------------------------------------------------
# create_plan tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_plan_returns_structured_output() -> None:
    """create_plan should return a dict with all required keys."""
    payload = _make_plan_payload()
    agent = ArchitectAgent(cloud_client=_mock_cloud(payload))

    session = _make_session()
    plan = await agent.create_plan(session, task_description="Add feature X")

    assert isinstance(plan, dict)
    assert "steps" in plan
    assert "files" in plan
    assert "risk" in plan
    assert "estimated_minutes" in plan
    assert "complexity" in plan
    assert "subtasks" in plan


@pytest.mark.asyncio
async def test_create_plan_sets_complexity() -> None:
    """create_plan should propagate complexity from the LLM response."""
    payload = _make_plan_payload(complexity="complex", steps=["a", "b", "c"])
    agent = ArchitectAgent(cloud_client=_mock_cloud(payload))

    session = _make_session()
    plan = await agent.create_plan(session, task_description="Refactor module Y")

    assert plan["complexity"] == "complex"


@pytest.mark.asyncio
async def test_create_plan_with_researcher_findings() -> None:
    """create_plan should forward researcher_findings to the context builder without error."""
    payload = _make_plan_payload()
    agent = ArchitectAgent(cloud_client=_mock_cloud(payload))

    session = _make_session()
    plan = await agent.create_plan(
        session,
        task_description="Fix bug Z",
        researcher_findings="Module foo has 3 usages of bar().",
    )

    assert plan["steps"] == ["step1", "step2"]


@pytest.mark.asyncio
async def test_create_plan_accumulates_tokens() -> None:
    """Token counts from the response are added to session.tokens_used."""
    payload = _make_plan_payload()
    agent = ArchitectAgent(cloud_client=_mock_cloud(payload))

    session = _make_session()
    assert session.tokens_used == 0
    await agent.create_plan(session, task_description="Task")

    assert session.tokens_used == 700  # 500 in + 200 out


@pytest.mark.asyncio
async def test_create_plan_passes_correct_model() -> None:
    """create_plan should call complete() with session.architect_model."""
    payload = _make_plan_payload()
    mock_cloud = _mock_cloud(payload)
    agent = ArchitectAgent(cloud_client=mock_cloud)

    session = _make_session()
    await agent.create_plan(session, task_description="Task")

    call_kwargs = mock_cloud.complete.call_args
    assert call_kwargs.kwargs.get("model_id") == session.architect_model


# ---------------------------------------------------------------------------
# review_diff tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_review_diff_returns_approved_flag() -> None:
    """review_diff should return a dict with approved, feedback, and issues."""
    review_payload = {"approved": True, "feedback": "Looks good.", "issues": []}
    agent = ArchitectAgent(cloud_client=_mock_cloud(review_payload))

    session = _make_session()
    result = await agent.review_diff(
        session,
        diff="--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new",
        test_results="1 passed",
    )

    assert result["approved"] is True
    assert result["feedback"] == "Looks good."
    assert result["issues"] == []


@pytest.mark.asyncio
async def test_review_diff_rejected_with_issues() -> None:
    """review_diff should propagate issues list when rejected."""
    review_payload = {
        "approved": False,
        "feedback": "Missing tests.",
        "issues": ["No test for new function", "Type hint missing on line 5"],
    }
    agent = ArchitectAgent(cloud_client=_mock_cloud(review_payload))

    session = _make_session()
    result = await agent.review_diff(session, diff="diff content", test_results="0 passed")

    assert result["approved"] is False
    assert len(result["issues"]) == 2


@pytest.mark.asyncio
async def test_review_diff_accumulates_tokens() -> None:
    """Token counts from review response are added to session.tokens_used."""
    review_payload = {"approved": True, "feedback": "OK", "issues": []}
    agent = ArchitectAgent(cloud_client=_mock_cloud(review_payload))

    session = _make_session()
    await agent.review_diff(session, diff="d", test_results="t")

    assert session.tokens_used == 700


# ---------------------------------------------------------------------------
# _parse_plan tests (unit level)
# ---------------------------------------------------------------------------

def test_parse_plan_direct_json() -> None:
    """_parse_plan should parse a clean JSON string."""
    agent = ArchitectAgent(cloud_client=MagicMock())
    payload = _make_plan_payload()
    result = agent._parse_plan(json.dumps(payload))
    assert result["complexity"] == "simple"
    assert result["steps"] == ["step1", "step2"]


def test_parse_plan_strips_markdown_fences() -> None:
    """_parse_plan should handle ```json ... ``` wrapping."""
    agent = ArchitectAgent(cloud_client=MagicMock())
    payload = _make_plan_payload(risk="high")
    wrapped = f"```json\n{json.dumps(payload)}\n```"
    result = agent._parse_plan(wrapped)
    assert result["risk"] == "high"


def test_parse_plan_returns_defaults_on_garbage() -> None:
    """_parse_plan should return safe defaults when JSON is unparseable."""
    agent = ArchitectAgent(cloud_client=MagicMock())
    result = agent._parse_plan("not json at all")
    assert result["steps"] == []
    assert result["complexity"] == "simple"
    assert result["estimated_minutes"] == 0


def test_parse_plan_handles_empty_string() -> None:
    """_parse_plan should return defaults for empty input."""
    agent = ArchitectAgent(cloud_client=MagicMock())
    result = agent._parse_plan("")
    assert isinstance(result, dict)
    assert "steps" in result


# ---------------------------------------------------------------------------
# _parse_json_response tests (unit level)
# ---------------------------------------------------------------------------

def test_parse_json_response_brace_extraction() -> None:
    """_parse_json_response should find a JSON object embedded in prose."""
    agent = ArchitectAgent(cloud_client=MagicMock())
    content = 'Here is the result: {"approved": true, "feedback": "ok", "issues": []}'
    result = agent._parse_json_response(content, {"approved": False, "feedback": "", "issues": []})
    assert result["approved"] is True


def test_parse_json_response_uses_default_on_failure() -> None:
    """_parse_json_response should return the default dict when nothing parses."""
    agent = ArchitectAgent(cloud_client=MagicMock())
    default = {"approved": False, "feedback": "fallback", "issues": []}
    result = agent._parse_json_response("gibberish }{", default)
    assert result == default


# ---------------------------------------------------------------------------
# _get_provider test
# ---------------------------------------------------------------------------

def test_get_provider_returns_anthropic() -> None:
    """_get_provider should always return CloudProvider.ANTHROPIC."""
    from hestia.cloud.models import CloudProvider
    agent = ArchitectAgent(cloud_client=MagicMock())
    assert agent._get_provider() == CloudProvider.ANTHROPIC


# ---------------------------------------------------------------------------
# Memory bridge test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_plan_with_memory_bridge() -> None:
    """Memory bridge context is fetched and included without error."""
    payload = _make_plan_payload()
    mock_cloud = _mock_cloud(payload)

    memory_bridge = AsyncMock()
    memory_bridge.get_context = AsyncMock(return_value="Previous session learnings here.")

    agent = ArchitectAgent(cloud_client=mock_cloud, memory_bridge=memory_bridge)
    session = _make_session()
    plan = await agent.create_plan(session, task_description="Task with memory")

    memory_bridge.get_context.assert_called_once_with(session.id)
    assert isinstance(plan, dict)


@pytest.mark.asyncio
async def test_create_plan_handles_memory_bridge_failure_gracefully() -> None:
    """A broken memory bridge should not prevent plan creation."""
    payload = _make_plan_payload()
    mock_cloud = _mock_cloud(payload)

    memory_bridge = AsyncMock()
    memory_bridge.get_context = AsyncMock(side_effect=RuntimeError("DB down"))

    agent = ArchitectAgent(cloud_client=mock_cloud, memory_bridge=memory_bridge)
    session = _make_session()
    plan = await agent.create_plan(session, task_description="Task with broken memory")

    # Should succeed despite the memory failure
    assert "steps" in plan
