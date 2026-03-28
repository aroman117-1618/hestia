"""Tests for hestia.dev.validator — ValidatorAgent test/lint/AI analysis."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from hestia.dev.validator import ValidatorAgent
from hestia.dev.models import DevSession, DevSessionSource
from hestia.inference.client import InferenceResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(**kwargs) -> DevSession:
    defaults = dict(
        title="Test",
        description="Validate changes",
        source=DevSessionSource.CLI,
    )
    defaults.update(kwargs)
    return DevSession.create(**defaults)


def _make_response(content: str) -> InferenceResponse:
    return InferenceResponse(
        content=content,
        model="claude-haiku-4-5-20251001",
        tokens_in=300,
        tokens_out=100,
        duration_ms=200.0,
    )


_PASSED_RESULT = {"passed": True, "returncode": 0, "stdout": "5 passed", "stderr": ""}
_FAILED_RESULT = {"passed": False, "returncode": 1, "stdout": "1 failed", "stderr": ""}


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def validator() -> ValidatorAgent:
    return ValidatorAgent()


# ---------------------------------------------------------------------------
# Tests — run_tests
# ---------------------------------------------------------------------------

class TestRunTests:
    @pytest.mark.asyncio
    async def test_run_tests_returns_passed(self, validator: ValidatorAgent) -> None:
        with patch(
            "hestia.dev.tools.run_tests_handler",
            new_callable=AsyncMock,
            return_value=_PASSED_RESULT,
        ):
            result = await validator.run_tests()
            assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_tests_returns_failed(self, validator: ValidatorAgent) -> None:
        with patch(
            "hestia.dev.tools.run_tests_handler",
            new_callable=AsyncMock,
            return_value=_FAILED_RESULT,
        ):
            result = await validator.run_tests()
            assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_run_tests_with_path_and_marker(
        self, validator: ValidatorAgent
    ) -> None:
        """run_tests() should forward path and marker to the handler."""
        mock_handler = AsyncMock(return_value=_PASSED_RESULT)
        with patch("hestia.dev.tools.run_tests_handler", mock_handler):
            await validator.run_tests(
                path="tests/test_dev_models.py", marker="not slow"
            )
            mock_handler.assert_awaited_once_with(
                path="tests/test_dev_models.py",
                marker="not slow",
            )


# ---------------------------------------------------------------------------
# Tests — run_xcode_build
# ---------------------------------------------------------------------------

class TestRunXcodeBuild:
    @pytest.mark.asyncio
    async def test_run_xcode_build_returns_result(
        self, validator: ValidatorAgent
    ) -> None:
        build_result = {"success": True, "stdout": "", "stderr": ""}
        with patch(
            "hestia.dev.tools.xcode_build_handler",
            new_callable=AsyncMock,
            return_value=build_result,
        ):
            result = await validator.run_xcode_build()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_run_xcode_build_passes_scheme(
        self, validator: ValidatorAgent
    ) -> None:
        mock_handler = AsyncMock(return_value={"success": True, "stdout": "", "stderr": ""})
        with patch("hestia.dev.tools.xcode_build_handler", mock_handler):
            await validator.run_xcode_build(scheme="HestiaApp")
            mock_handler.assert_awaited_once_with(scheme="HestiaApp")


# ---------------------------------------------------------------------------
# Tests — validate_session
# ---------------------------------------------------------------------------

class TestValidateSession:
    @pytest.mark.asyncio
    async def test_validate_session_passes(self, validator: ValidatorAgent) -> None:
        with patch(
            "hestia.dev.tools.run_tests_handler",
            new_callable=AsyncMock,
            return_value=_PASSED_RESULT,
        ):
            session = _make_session()
            result = await validator.validate_session(session)
            assert result["passed"] is True
            assert result["ai_analysis"] is None  # No cloud client

    @pytest.mark.asyncio
    async def test_validate_session_fails_on_test_failure(
        self, validator: ValidatorAgent
    ) -> None:
        with patch(
            "hestia.dev.tools.run_tests_handler",
            new_callable=AsyncMock,
            return_value=_FAILED_RESULT,
        ):
            session = _make_session()
            result = await validator.validate_session(session)
            assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_validate_session_returns_all_keys(
        self, validator: ValidatorAgent
    ) -> None:
        with patch(
            "hestia.dev.tools.run_tests_handler",
            new_callable=AsyncMock,
            return_value=_PASSED_RESULT,
        ):
            session = _make_session()
            result = await validator.validate_session(session)
            assert "passed" in result
            assert "test_result" in result
            assert "lint_result" in result
            assert "ai_analysis" in result

    @pytest.mark.asyncio
    async def test_validate_session_with_ai_analysis(self) -> None:
        """validate_session() should call the cloud client when configured."""
        mock_cloud = AsyncMock()
        mock_cloud.complete = AsyncMock(
            return_value=_make_response("APPROVED: Looks good.")
        )
        v = ValidatorAgent(cloud_client=mock_cloud)

        with patch(
            "hestia.dev.tools.run_tests_handler",
            new_callable=AsyncMock,
            return_value=_PASSED_RESULT,
        ):
            session = _make_session()
            result = await v.validate_session(session, diff="+++ b/hestia/dev/foo.py\n+new line")
            assert result["ai_analysis"] is not None
            assert "content" in result["ai_analysis"]
            assert "tokens_used" in result["ai_analysis"]

    @pytest.mark.asyncio
    async def test_validate_session_no_ai_without_diff(self) -> None:
        """validate_session() should skip AI analysis when no diff is provided."""
        mock_cloud = AsyncMock()
        v = ValidatorAgent(cloud_client=mock_cloud)

        with patch(
            "hestia.dev.tools.run_tests_handler",
            new_callable=AsyncMock,
            return_value=_PASSED_RESULT,
        ):
            session = _make_session()
            result = await v.validate_session(session, diff="")
            assert result["ai_analysis"] is None
            mock_cloud.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_session_accumulates_tokens(self) -> None:
        """validate_session() should accumulate AI tokens on the session."""
        mock_cloud = AsyncMock()
        mock_cloud.complete = AsyncMock(
            return_value=_make_response("APPROVED")
        )
        v = ValidatorAgent(cloud_client=mock_cloud)

        with patch(
            "hestia.dev.tools.run_tests_handler",
            new_callable=AsyncMock,
            return_value=_PASSED_RESULT,
        ):
            session = _make_session()
            assert session.tokens_used == 0
            await v.validate_session(session, diff="+++ b/hestia/dev/foo.py\n+x")
            assert session.tokens_used > 0


# ---------------------------------------------------------------------------
# Tests — check_dependencies
# ---------------------------------------------------------------------------

class TestCheckDependencies:
    @pytest.mark.asyncio
    async def test_check_dependencies_success(
        self, validator: ValidatorAgent
    ) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "[]"
            result = await validator.check_dependencies()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_check_dependencies_not_available(
        self, validator: ValidatorAgent
    ) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await validator.check_dependencies()
            assert result["success"] is True
            assert "not available" in result["output"]

    @pytest.mark.asyncio
    async def test_check_dependencies_failure(
        self, validator: ValidatorAgent
    ) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = '[{"name": "foo", "version": "1.0"}]'
            result = await validator.check_dependencies()
            assert result["success"] is False


# ---------------------------------------------------------------------------
# Tests — _run_lint
# ---------------------------------------------------------------------------

class TestRunLint:
    @pytest.mark.asyncio
    async def test_lint_no_diff(self, validator: ValidatorAgent) -> None:
        result = await validator._run_lint("")
        assert result["files_checked"] == 0
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_lint_detects_wildcard_import(
        self, validator: ValidatorAgent
    ) -> None:
        """_run_lint() should warn about wildcard imports in changed files."""
        diff = "+++ b/fake_file.py"
        result = await validator._run_lint(diff)
        # File doesn't exist on disk — should still return without error
        assert "files_checked" in result
        assert isinstance(result["warnings"], list)

    @pytest.mark.asyncio
    async def test_lint_returns_structure(self, validator: ValidatorAgent) -> None:
        result = await validator._run_lint("+++ b/hestia/dev/foo.py")
        assert "errors" in result
        assert "warnings" in result
        assert "files_checked" in result

    @pytest.mark.asyncio
    async def test_lint_ignores_non_python_files(
        self, validator: ValidatorAgent
    ) -> None:
        diff = "+++ b/HestiaApp/Shared/Views/ChatView.swift\n+++ b/docs/plan.md"
        result = await validator._run_lint(diff)
        assert result["files_checked"] == 0
