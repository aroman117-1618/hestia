import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from hestia.dev.discovery import WorkDiscoveryScheduler
from hestia.dev.models import DevSessionSource, DevPriority


@pytest.fixture
def mock_manager():
    m = AsyncMock()
    m.create_session = AsyncMock()
    m.list_sessions = AsyncMock(return_value=[])
    return m


@pytest.fixture
def scheduler(mock_manager):
    return WorkDiscoveryScheduler(manager=mock_manager, interval_seconds=60)


class TestWorkDiscoveryScheduler:
    def test_init(self, scheduler):
        assert scheduler.is_running is False
        assert scheduler._interval == 60

    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler):
        await scheduler.start()
        assert scheduler.is_running is True
        await scheduler.stop()
        assert scheduler.is_running is False

    @pytest.mark.asyncio
    async def test_check_tests_passing(self, scheduler):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="5 passed", stderr="")
            findings = await scheduler.check_tests()
            assert len(findings) == 0

    @pytest.mark.asyncio
    async def test_check_tests_failing(self, scheduler):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="FAILED tests/test_foo.py::test_bar", stderr="")
            findings = await scheduler.check_tests()
            assert len(findings) == 1
            assert findings[0]["type"] == "test_failure"
            assert findings[0]["priority"] == DevPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_check_github_issues(self, scheduler):
        with patch("subprocess.run") as mock_run:
            import json
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([{"number": 42, "title": "Fix bug", "body": "Details", "labels": []}]),
            )
            findings = await scheduler.check_github_issues()
            assert len(findings) == 1
            assert findings[0]["source_ref"] == "#42"

    @pytest.mark.asyncio
    async def test_check_github_skips_existing(self, scheduler, mock_manager):
        """Don't create duplicate sessions for the same issue."""
        from hestia.dev.models import DevSession
        existing = DevSession.create(title="Existing", description="", source=DevSessionSource.GITHUB, source_ref="#42")
        mock_manager.list_sessions = AsyncMock(return_value=[existing])

        with patch("subprocess.run") as mock_run:
            import json
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps([{"number": 42, "title": "Fix bug", "body": "", "labels": []}]),
            )
            findings = await scheduler.check_github_issues()
            assert len(findings) == 0  # Skipped because #42 already exists

    @pytest.mark.asyncio
    async def test_create_session_from_finding(self, scheduler, mock_manager):
        finding = {"type": "test_failure", "title": "Tests broken", "description": "1 failed", "priority": DevPriority.CRITICAL}
        await scheduler._create_session_from_finding(finding)
        mock_manager.create_session.assert_called_once()
        call_args = mock_manager.create_session.call_args
        assert call_args.kwargs["source"] == DevSessionSource.SELF_DISCOVERED
        assert call_args.kwargs["priority"] == DevPriority.CRITICAL

    @pytest.mark.asyncio
    async def test_run_discovery_cycle(self, scheduler):
        with patch.object(scheduler, "check_tests", return_value=[]):
            with patch.object(scheduler, "check_github_issues", return_value=[]):
                findings = await scheduler.run_discovery_cycle()
                assert findings == []

    @pytest.mark.asyncio
    async def test_code_quality_check(self, scheduler):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="hestia/foo.py:10: # TODO 2025-01-01 fix this")
            findings = await scheduler.check_code_quality()
            # Only reports if >5 TODOs
            assert len(findings) == 0
