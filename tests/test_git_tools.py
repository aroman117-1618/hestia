"""Tests for git tools (status, diff, add, commit, log)."""
import asyncio
import subprocess
import pytest
from pathlib import Path

from hestia.execution.tools.git_tools import (
    _run_git,
    git_status_handler,
    git_diff_handler,
    git_log_handler,
    BLOCKED_GIT_OPERATIONS,
)


class TestGitSafetyChecks:
    def test_blocks_force_push(self):
        result = _run_git(["push", "--force", "origin", "main"])
        assert result["success"] is False
        assert "blocked" in result["error"].lower()

    def test_blocks_hard_reset(self):
        result = _run_git(["reset", "--hard"])
        assert result["success"] is False
        assert "blocked" in result["error"].lower()

    def test_blocks_clean_force(self):
        result = _run_git(["clean", "-f"])
        assert result["success"] is False

    def test_blocks_branch_delete_force(self):
        result = _run_git(["branch", "-D", "some-branch"])
        assert result["success"] is False

    def test_allows_safe_operations(self):
        # These should not be blocked (even if they fail due to no repo)
        for args in [["status"], ["log", "-1"], ["diff"]]:
            result = _run_git(args, "/tmp")
            # May fail (not a repo) but should NOT be blocked
            assert "blocked" not in result.get("error", "").lower()


class TestGitToolsOnRealRepo:
    """Tests that run against the actual hestia repo (read-only operations)."""

    def test_git_status(self):
        result = asyncio.get_event_loop().run_until_complete(git_status_handler())
        assert result["success"] is True
        assert "returncode" in result

    def test_git_log(self):
        result = asyncio.get_event_loop().run_until_complete(git_log_handler(count=5))
        assert result["success"] is True
        assert len(result["stdout"]) > 0

    def test_git_diff(self):
        result = asyncio.get_event_loop().run_until_complete(git_diff_handler())
        assert result["success"] is True

    def test_git_log_respects_max(self):
        result = asyncio.get_event_loop().run_until_complete(git_log_handler(count=3))
        assert result["success"] is True
        lines = [l for l in result["stdout"].strip().split("\n") if l]
        assert len(lines) <= 3


class TestGitToolIsolated:
    """Tests using a temporary git repo."""

    @pytest.fixture
    def git_repo(self, tmp_path):
        """Create a temporary git repo."""
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
            capture_output=True,
        )
        # Create initial commit
        (tmp_path / "README.md").write_text("# Test")
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "commit", "-m", "init"],
            capture_output=True,
        )
        return tmp_path

    def test_status_shows_changes(self, git_repo):
        (git_repo / "new_file.py").write_text("x = 1")
        result = _run_git(["status", "--short"], str(git_repo))
        assert result["success"] is True
        assert "new_file.py" in result["stdout"]

    def test_diff_shows_modifications(self, git_repo):
        (git_repo / "README.md").write_text("# Modified")
        result = _run_git(["diff"], str(git_repo))
        assert result["success"] is True
        assert "Modified" in result["stdout"]
