from __future__ import annotations
"""Safety primitives for the Hestia Agentic Development System.

Provides:
- AuthorityMatrix: per-tier tool access control and approval gate
- TokenBudgetTracker: cumulative token budget enforcement
- NotificationRateLimiter: per-priority hourly send limits
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from hestia.dev.models import AgentTier, ApprovalType

# ---------------------------------------------------------------------------
# Authority Matrix
# ---------------------------------------------------------------------------

# Tools every tier may use
_UNIVERSAL_TOOLS: frozenset[str] = frozenset({
    "read_file",
    "glob_files",
    "grep_files",
    "git_status",
    "git_diff",
    "git_log",
})

# Additional tools granted per tier (on top of universal)
_TIER_EXTRA_TOOLS: dict[AgentTier, frozenset[str]] = {
    AgentTier.RESEARCHER: frozenset(),  # read-only — universal only
    AgentTier.ARCHITECT: frozenset({
        "git_branch",
        "run_tests",
        "server_restart",
        "create_github_issue",
        "create_github_pr",
        "merge_github_pr",
        "git_push",
        "notify_andrew",
    }),
    AgentTier.ENGINEER: frozenset({
        "edit_file",
        "write_file",
        "git_add",
        "git_commit",
        "git_branch",
        "run_tests",
        "xcode_build",
        "run_command",
        "server_restart",
        "git_push",
        "notify_andrew",
    }),
    AgentTier.VALIDATOR: frozenset({
        "run_tests",
        "xcode_build",
        "pip_audit",
        "notify_andrew",
    }),
}

# Paths that require PROTECTED_PATH approval on edit_file / write_file
_PROTECTED_PATH_PREFIXES: tuple[str, ...] = (
    "security/",
    "config/",
    ".env",
    ".claude/",
)


class AuthorityMatrix:
    """Static authority matrix — no instances needed; all methods are class-level."""

    @classmethod
    def _allowed_tools(cls, tier: AgentTier) -> frozenset[str]:
        """Return the full set of tools allowed for *tier*."""
        return _UNIVERSAL_TOOLS | _TIER_EXTRA_TOOLS.get(tier, frozenset())

    @classmethod
    def can_use_tool(cls, tier: AgentTier, tool_name: str) -> bool:
        """Return True if *tier* is authorised to invoke *tool_name*."""
        return tool_name in cls._allowed_tools(tier)

    @classmethod
    def is_protected_path(cls, path: str) -> bool:
        """Return True if *path* matches any protected-path prefix."""
        # Normalise: strip leading slashes / spaces so relative paths match too
        normalised = path.lstrip("/").lstrip()
        for prefix in _PROTECTED_PATH_PREFIXES:
            if normalised.startswith(prefix) or normalised == prefix.rstrip("/"):
                return True
        # Also catch bare .env file (no directory component)
        if normalised == ".env":
            return True
        return False

    @classmethod
    def requires_approval(
        cls,
        tier: AgentTier,
        tool_name: str,
        path: Optional[str] = None,
    ) -> Optional[ApprovalType]:
        """Return the ApprovalType required, or None if no approval is needed.

        Precedence:
        1. edit_file / write_file on a protected path → PROTECTED_PATH
        2. git_push → GIT_PUSH
        3. create_github_pr → PR_CREATE
        4. merge_github_pr → PR_MERGE
        5. run_command → GIT_PUSH (reuse type for shell-escape risk)
        """
        if tool_name in {"edit_file", "write_file"} and path is not None:
            if cls.is_protected_path(path):
                return ApprovalType.PROTECTED_PATH

        if tool_name == "git_push":
            return ApprovalType.GIT_PUSH

        if tool_name == "create_github_pr":
            return ApprovalType.PR_CREATE

        if tool_name == "merge_github_pr":
            return ApprovalType.PR_MERGE

        if tool_name == "run_command":
            return ApprovalType.GIT_PUSH  # reuse type as specified

        return None


# ---------------------------------------------------------------------------
# Token Budget Tracker
# ---------------------------------------------------------------------------

_NEAR_LIMIT_THRESHOLD: float = 0.85


class TokenBudgetTracker:
    """Tracks cumulative token usage against a fixed budget."""

    def __init__(self, budget: int = 500_000) -> None:
        self._budget: int = budget
        self._used: int = 0

    def add(self, tokens: int) -> None:
        """Record *tokens* as consumed."""
        self._used += tokens

    def remaining(self) -> int:
        """Return tokens remaining in the budget (may be negative if over)."""
        return self._budget - self._used

    def within_budget(self) -> bool:
        """Return True if tokens consumed are strictly within the budget."""
        return self._used < self._budget

    def near_limit(self) -> bool:
        """Return True when >= 85 % of the budget has been consumed."""
        return self._used >= self._budget * _NEAR_LIMIT_THRESHOLD


# ---------------------------------------------------------------------------
# Notification Rate Limiter
# ---------------------------------------------------------------------------

# Max sends per hour per priority level. None = unlimited.
_HOURLY_LIMITS: dict[str, Optional[int]] = {
    "critical": None,   # unlimited
    "high": 10,
    "normal": 10,
    "background": 2,
}


class NotificationRateLimiter:
    """Enforces per-priority hourly send limits for notifications."""

    def __init__(self) -> None:
        # Maps priority → list of send timestamps (ISO strings) in the current window
        self._sends: dict[str, list[datetime]] = defaultdict(list)

    def _current_hour_count(self, priority: str) -> int:
        """Return the number of sends recorded in the current rolling hour."""
        now = datetime.now(tz=timezone.utc)
        return sum(
            1
            for ts in self._sends[priority]
            if (now - ts).total_seconds() < 3600
        )

    def can_send(self, priority: str) -> bool:
        """Return True if another notification at *priority* is permitted right now."""
        limit = _HOURLY_LIMITS.get(priority)
        if limit is None:
            return True  # unlimited
        return self._current_hour_count(priority) < limit

    def record(self, priority: str) -> None:
        """Record a notification send at *priority* (call after actually sending)."""
        self._sends[priority].append(datetime.now(tz=timezone.utc))
