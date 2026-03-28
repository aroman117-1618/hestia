import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from hestia.dev.proposal import ProposalDelivery
from hestia.dev.models import DevSession, DevSessionSource, DevPriority


@pytest.fixture
def mock_notifications():
    n = AsyncMock()
    n.create_bump = AsyncMock(return_value={"callback_id": "cb-123", "status": "delivered"})
    return n


@pytest.fixture
def delivery(mock_notifications):
    return ProposalDelivery(notification_manager=mock_notifications)


@pytest.fixture
def session():
    s = DevSession.create(title="Fix bug", description="Fix the memory bug", source=DevSessionSource.SELF_DISCOVERED)
    s.plan = {"steps": ["Read file", "Edit"], "files": ["hestia/memory/manager.py"], "risk": "low", "estimated_minutes": 15}
    s.priority = DevPriority.HIGH
    return s


class TestCreateGitHubIssue:
    @pytest.mark.asyncio
    async def test_creates_issue(self, delivery, session):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/repo/issues/42")
            result = await delivery.create_github_issue(session)
            assert result["success"] is True
            assert "42" in result["url"]

    @pytest.mark.asyncio
    async def test_handles_gh_missing(self, delivery, session):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await delivery.create_github_issue(session)
            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_includes_proposal_label(self, delivery, session):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="url")
            await delivery.create_github_issue(session)
            cmd = mock_run.call_args[0][0]
            assert "hestia-proposal" in str(cmd)


class TestSendNotification:
    @pytest.mark.asyncio
    async def test_sends_for_high_priority(self, delivery, session, mock_notifications):
        result = await delivery.send_notification(session)
        assert result["success"] is True
        mock_notifications.create_bump.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_notification_without_manager(self, session):
        d = ProposalDelivery(notification_manager=None)
        result = await d.send_notification(session)
        assert result["success"] is False


class TestDeliverProposal:
    @pytest.mark.asyncio
    async def test_delivers_to_github_and_notification(self, delivery, session):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="url")
            result = await delivery.deliver_proposal(session)
            assert "github" in result
            assert "notification" in result  # HIGH priority gets notification

    @pytest.mark.asyncio
    async def test_normal_priority_skips_notification(self, delivery):
        s = DevSession.create(title="Low", description="Low", source=DevSessionSource.SELF_DISCOVERED)
        s.priority = DevPriority.NORMAL
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="url")
            result = await delivery.deliver_proposal(s)
            assert "github" in result
            assert "notification" not in result  # NORMAL doesn't get immediate notification


class TestFormatForBriefing:
    def test_formats_proposals(self, delivery, session):
        text = delivery.format_for_briefing([session])
        assert "Fix bug" in text
        assert "hestia/memory/manager.py" not in text  # Brief format, not full file list
        assert "Development Proposals" in text

    def test_empty_returns_empty(self, delivery):
        assert delivery.format_for_briefing([]) == ""


class TestCompletionNotification:
    @pytest.mark.asyncio
    async def test_sends_completion(self, delivery, session, mock_notifications):
        result = await delivery.send_completion_notification(session)
        assert result["success"] is True
