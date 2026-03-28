"""Tests for hestia.dev.researcher — ResearcherAgent analysis and review."""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock

from hestia.dev.researcher import ResearcherAgent
from hestia.dev.models import DevSession, DevSessionSource
from hestia.inference.client import InferenceResponse


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_response(content: str) -> InferenceResponse:
    """Build an InferenceResponse with required fields."""
    return InferenceResponse(
        content=content,
        model="gemini-2.0-pro",
        tokens_in=1000,
        tokens_out=500,
        duration_ms=800.0,
    )


@pytest.fixture
def mock_cloud() -> AsyncMock:
    client = AsyncMock()
    client.complete = AsyncMock(
        return_value=_make_response(
            "The module uses a singleton pattern with async factory."
        )
    )
    return client


@pytest.fixture
def researcher(mock_cloud: AsyncMock) -> ResearcherAgent:
    return ResearcherAgent(cloud_client=mock_cloud)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestResearcherAgent:
    @pytest.mark.asyncio
    async def test_analyze_returns_findings(self, researcher: ResearcherAgent) -> None:
        """analyze() should return a findings string and positive token count."""
        session = DevSession.create(
            title="Research",
            description="Analyze routing module",
            source=DevSessionSource.CLI,
        )
        result = await researcher.analyze(session, "How does routing work?", [])

        assert "findings" in result
        assert isinstance(result["findings"], str)
        assert len(result["findings"]) > 0
        assert result["tokens_used"] > 0

    @pytest.mark.asyncio
    async def test_analyze_accumulates_tokens_on_session(
        self, researcher: ResearcherAgent
    ) -> None:
        """analyze() should accumulate token usage on the session."""
        session = DevSession.create(
            title="Research",
            description="Check patterns",
            source=DevSessionSource.CLI,
        )
        assert session.tokens_used == 0
        await researcher.analyze(session, "What patterns are used?", [])
        assert session.tokens_used > 0

    @pytest.mark.asyncio
    async def test_analyze_converts_string_questions_to_list(
        self, mock_cloud: AsyncMock
    ) -> None:
        """analyze() should handle multi-line question strings without error."""
        researcher = ResearcherAgent(cloud_client=mock_cloud)
        session = DevSession.create(
            title="Research",
            description="Multi-question",
            source=DevSessionSource.CLI,
        )
        questions = "How does auth work?\nWhat is the logging pattern?\nWhere is the DB?"
        result = await researcher.analyze(session, questions, [])
        assert "findings" in result

    @pytest.mark.asyncio
    async def test_review_code_returns_structure(self, mock_cloud: AsyncMock) -> None:
        """review_code() should return approved, issues, feedback, and tokens_used."""
        mock_cloud.complete = AsyncMock(
            return_value=_make_response(
                json.dumps({"approved": True, "issues": [], "feedback": "Clean diff."})
            )
        )
        researcher = ResearcherAgent(cloud_client=mock_cloud)
        session = DevSession.create(
            title="Review",
            description="Review a diff",
            source=DevSessionSource.CLI,
        )
        result = await researcher.review_code(session, diff="+new line\n-old line")

        assert result["approved"] is True
        assert isinstance(result["issues"], list)
        assert isinstance(result["feedback"], str)
        assert "tokens_used" in result
        assert result["tokens_used"] > 0

    @pytest.mark.asyncio
    async def test_review_code_handles_json_in_fences(self, mock_cloud: AsyncMock) -> None:
        """review_code() should parse JSON wrapped in markdown fences."""
        fenced = (
            "```json\n"
            '{"approved": false, "issues": ["missing type hint"], "feedback": "Fix it"}\n'
            "```"
        )
        mock_cloud.complete = AsyncMock(
            return_value=_make_response(fenced)
        )
        researcher = ResearcherAgent(cloud_client=mock_cloud)
        session = DevSession.create(
            title="Review",
            description="Fenced JSON test",
            source=DevSessionSource.CLI,
        )
        result = await researcher.review_code(session, diff="+foo")

        assert result["approved"] is False
        assert result["issues"] == ["missing type hint"]

    @pytest.mark.asyncio
    async def test_review_code_handles_malformed_json(self, mock_cloud: AsyncMock) -> None:
        """review_code() should fall back to default dict on malformed JSON."""
        mock_cloud.complete = AsyncMock(
            return_value=_make_response("This is not JSON at all.")
        )
        researcher = ResearcherAgent(cloud_client=mock_cloud)
        session = DevSession.create(
            title="Review",
            description="Bad JSON test",
            source=DevSessionSource.CLI,
        )
        result = await researcher.review_code(session, diff="+bar")

        assert isinstance(result.get("approved"), bool)
        assert isinstance(result.get("issues"), list)
        assert isinstance(result.get("feedback"), str)

    @pytest.mark.asyncio
    async def test_review_code_normalises_approved_type(
        self, mock_cloud: AsyncMock
    ) -> None:
        """review_code() should coerce 'approved' to bool even if LLM returns a string."""
        mock_cloud.complete = AsyncMock(
            return_value=_make_response(
                json.dumps({"approved": "true", "issues": [], "feedback": "ok"})
            )
        )
        researcher = ResearcherAgent(cloud_client=mock_cloud)
        session = DevSession.create(
            title="Review",
            description="Type normalisation",
            source=DevSessionSource.CLI,
        )
        result = await researcher.review_code(session, diff="+baz")
        assert isinstance(result["approved"], bool)
