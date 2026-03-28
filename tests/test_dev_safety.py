"""Tests for hestia.dev.safety — AuthorityMatrix, TokenBudgetTracker, NotificationRateLimiter."""
from __future__ import annotations

import pytest

from hestia.dev.models import AgentTier, ApprovalType
from hestia.dev.safety import AuthorityMatrix, NotificationRateLimiter, TokenBudgetTracker


# ---------------------------------------------------------------------------
# AuthorityMatrix — tool access
# ---------------------------------------------------------------------------

class TestAuthorityMatrixToolAccess:
    """Verify per-tier tool grants."""

    # --- Universal (all tiers) ---

    @pytest.mark.parametrize("tier", list(AgentTier))
    def test_all_tiers_can_read_file(self, tier: AgentTier) -> None:
        assert AuthorityMatrix.can_use_tool(tier, "read_file") is True

    @pytest.mark.parametrize("tier", list(AgentTier))
    def test_all_tiers_can_glob_files(self, tier: AgentTier) -> None:
        assert AuthorityMatrix.can_use_tool(tier, "glob_files") is True

    @pytest.mark.parametrize("tier", list(AgentTier))
    def test_all_tiers_can_grep_files(self, tier: AgentTier) -> None:
        assert AuthorityMatrix.can_use_tool(tier, "grep_files") is True

    @pytest.mark.parametrize("tier", list(AgentTier))
    def test_all_tiers_can_git_status(self, tier: AgentTier) -> None:
        assert AuthorityMatrix.can_use_tool(tier, "git_status") is True

    @pytest.mark.parametrize("tier", list(AgentTier))
    def test_all_tiers_can_git_diff(self, tier: AgentTier) -> None:
        assert AuthorityMatrix.can_use_tool(tier, "git_diff") is True

    @pytest.mark.parametrize("tier", list(AgentTier))
    def test_all_tiers_can_git_log(self, tier: AgentTier) -> None:
        assert AuthorityMatrix.can_use_tool(tier, "git_log") is True

    # --- Engineer-specific ---

    def test_engineer_can_edit_file(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "edit_file") is True

    def test_engineer_can_write_file(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "write_file") is True

    def test_engineer_can_run_command(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "run_command") is True

    def test_researcher_cannot_edit_file(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.RESEARCHER, "edit_file") is False

    def test_validator_cannot_edit_file(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.VALIDATOR, "edit_file") is False

    def test_architect_cannot_edit_file(self) -> None:
        # Architect can orchestrate but does NOT have edit_file
        assert AuthorityMatrix.can_use_tool(AgentTier.ARCHITECT, "edit_file") is False

    # --- Validator-specific ---

    def test_validator_can_run_tests(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.VALIDATOR, "run_tests") is True

    def test_validator_can_pip_audit(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.VALIDATOR, "pip_audit") is True

    def test_validator_cannot_create_github_issue(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.VALIDATOR, "create_github_issue") is False

    def test_validator_cannot_create_github_pr(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.VALIDATOR, "create_github_pr") is False

    # --- Architect-specific ---

    def test_architect_can_create_github_issue(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.ARCHITECT, "create_github_issue") is True

    def test_architect_can_create_github_pr(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.ARCHITECT, "create_github_pr") is True

    def test_architect_can_merge_github_pr(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.ARCHITECT, "merge_github_pr") is True

    def test_engineer_cannot_create_github_pr(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.ENGINEER, "create_github_pr") is False

    def test_researcher_cannot_create_github_issue(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.RESEARCHER, "create_github_issue") is False

    # --- Researcher is strictly read-only ---

    def test_researcher_cannot_git_push(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.RESEARCHER, "git_push") is False

    def test_researcher_cannot_run_tests(self) -> None:
        assert AuthorityMatrix.can_use_tool(AgentTier.RESEARCHER, "run_tests") is False

    # --- Unknown tool ---

    def test_unknown_tool_denied_for_all_tiers(self) -> None:
        for tier in AgentTier:
            assert AuthorityMatrix.can_use_tool(tier, "delete_production_db") is False


# ---------------------------------------------------------------------------
# AuthorityMatrix — protected paths
# ---------------------------------------------------------------------------

class TestProtectedPaths:
    """Verify is_protected_path detection."""

    @pytest.mark.parametrize("path", [
        "security/credentials.py",
        "security/",
        "config/inference.yaml",
        "config/",
        ".env",
        ".env.local",
        ".claude/settings.json",
        ".claude/",
    ])
    def test_protected_paths_detected(self, path: str) -> None:
        assert AuthorityMatrix.is_protected_path(path) is True

    @pytest.mark.parametrize("path", [
        "hestia/trading/manager.py",
        "tests/test_foo.py",
        "README.md",
        "hestia/config_helper.py",  # "config" not as prefix directory
    ])
    def test_non_protected_paths(self, path: str) -> None:
        assert AuthorityMatrix.is_protected_path(path) is False

    def test_leading_slash_normalised(self) -> None:
        assert AuthorityMatrix.is_protected_path("/security/foo.py") is True


# ---------------------------------------------------------------------------
# AuthorityMatrix — approval gates
# ---------------------------------------------------------------------------

class TestRequiresApproval:
    """Verify approval-gate logic."""

    def test_git_push_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(AgentTier.ENGINEER, "git_push")
        assert result == ApprovalType.GIT_PUSH

    def test_architect_git_push_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(AgentTier.ARCHITECT, "git_push")
        assert result == ApprovalType.GIT_PUSH

    def test_create_github_pr_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(AgentTier.ARCHITECT, "create_github_pr")
        assert result == ApprovalType.PR_CREATE

    def test_merge_github_pr_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(AgentTier.ARCHITECT, "merge_github_pr")
        assert result == ApprovalType.PR_MERGE

    def test_run_command_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(AgentTier.ENGINEER, "run_command")
        assert result == ApprovalType.GIT_PUSH

    def test_edit_file_protected_path_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(
            AgentTier.ENGINEER, "edit_file", path="security/auth.py"
        )
        assert result == ApprovalType.PROTECTED_PATH

    def test_edit_file_config_path_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(
            AgentTier.ENGINEER, "edit_file", path="config/inference.yaml"
        )
        assert result == ApprovalType.PROTECTED_PATH

    def test_edit_file_safe_path_no_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(
            AgentTier.ENGINEER, "edit_file", path="hestia/trading/manager.py"
        )
        assert result is None

    def test_edit_file_no_path_no_approval(self) -> None:
        # path=None → skip protected-path check
        result = AuthorityMatrix.requires_approval(AgentTier.ENGINEER, "edit_file", path=None)
        assert result is None

    def test_read_file_never_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(
            AgentTier.ENGINEER, "read_file", path="security/auth.py"
        )
        assert result is None

    def test_run_tests_no_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(AgentTier.VALIDATOR, "run_tests")
        assert result is None

    def test_write_file_env_requires_approval(self) -> None:
        result = AuthorityMatrix.requires_approval(
            AgentTier.ENGINEER, "write_file", path=".env"
        )
        assert result == ApprovalType.PROTECTED_PATH


# ---------------------------------------------------------------------------
# TokenBudgetTracker
# ---------------------------------------------------------------------------

class TestTokenBudgetTracker:
    """Verify budget tracking and threshold detection."""

    def test_starts_within_budget(self) -> None:
        tracker = TokenBudgetTracker(budget=500_000)
        assert tracker.within_budget() is True

    def test_remaining_equals_budget_initially(self) -> None:
        tracker = TokenBudgetTracker(budget=100_000)
        assert tracker.remaining() == 100_000

    def test_add_reduces_remaining(self) -> None:
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(30_000)
        assert tracker.remaining() == 70_000

    def test_multiple_adds_accumulate(self) -> None:
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(20_000)
        tracker.add(20_000)
        assert tracker.remaining() == 60_000

    def test_within_budget_false_when_exceeded(self) -> None:
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(100_000)
        assert tracker.within_budget() is False

    def test_remaining_negative_when_exceeded(self) -> None:
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(110_000)
        assert tracker.remaining() == -10_000

    def test_not_near_limit_below_threshold(self) -> None:
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(84_999)
        assert tracker.near_limit() is False

    def test_near_limit_at_exactly_85_percent(self) -> None:
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(85_000)
        assert tracker.near_limit() is True

    def test_near_limit_above_threshold(self) -> None:
        tracker = TokenBudgetTracker(budget=100_000)
        tracker.add(90_000)
        assert tracker.near_limit() is True

    def test_custom_budget(self) -> None:
        tracker = TokenBudgetTracker(budget=200_000)
        tracker.add(100_000)
        assert tracker.within_budget() is True
        assert tracker.remaining() == 100_000

    def test_default_budget_is_500k(self) -> None:
        tracker = TokenBudgetTracker()
        assert tracker.remaining() == 500_000


# ---------------------------------------------------------------------------
# NotificationRateLimiter
# ---------------------------------------------------------------------------

class TestNotificationRateLimiter:
    """Verify per-priority hourly send limits."""

    def test_can_send_initially_for_all_priorities(self) -> None:
        limiter = NotificationRateLimiter()
        for priority in ("critical", "high", "normal", "background"):
            assert limiter.can_send(priority) is True

    def test_critical_always_allowed(self) -> None:
        limiter = NotificationRateLimiter()
        # Record well past any reasonable limit
        for _ in range(100):
            limiter.record("critical")
        assert limiter.can_send("critical") is True

    def test_normal_hits_limit_at_10(self) -> None:
        limiter = NotificationRateLimiter()
        for _ in range(10):
            limiter.record("normal")
        assert limiter.can_send("normal") is False

    def test_normal_allowed_until_limit(self) -> None:
        limiter = NotificationRateLimiter()
        for _ in range(9):
            limiter.record("normal")
        assert limiter.can_send("normal") is True

    def test_high_hits_limit_at_10(self) -> None:
        limiter = NotificationRateLimiter()
        for _ in range(10):
            limiter.record("high")
        assert limiter.can_send("high") is False

    def test_background_hits_limit_at_2(self) -> None:
        limiter = NotificationRateLimiter()
        limiter.record("background")
        limiter.record("background")
        assert limiter.can_send("background") is False

    def test_background_allowed_for_first_send(self) -> None:
        limiter = NotificationRateLimiter()
        assert limiter.can_send("background") is True

    def test_background_allowed_for_second_send(self) -> None:
        limiter = NotificationRateLimiter()
        limiter.record("background")
        assert limiter.can_send("background") is True

    def test_limits_are_independent_per_priority(self) -> None:
        limiter = NotificationRateLimiter()
        for _ in range(10):
            limiter.record("normal")
        # high and background should be unaffected
        assert limiter.can_send("high") is True
        assert limiter.can_send("critical") is True

    def test_unknown_priority_denied(self) -> None:
        limiter = NotificationRateLimiter()
        # Unknown priorities have no limit entry → None limit → can_send returns True
        # (graceful: unknown = unlimited to avoid false blocks on new priorities)
        assert limiter.can_send("unknown_tier") is True
