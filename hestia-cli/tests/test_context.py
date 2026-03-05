"""
Tests for repository context detection.

Covers git state detection and project file auto-include.
Run with: cd hestia-cli && python -m pytest tests/test_context.py -v
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from hestia_cli.context import (
    get_repo_context,
    get_project_file_snippets,
    _is_git_repo,
    _get_git_root,
    _run_git,
    PROJECT_FILES,
    MAX_CHARS_PER_FILE,
    MAX_TOTAL_CHARS,
)


# ============== Git Detection ==============


class TestGitDetection:
    """Tests for git repo detection helpers."""

    def test_is_git_repo_in_repo(self):
        """Returns True when CWD is a git repo (we're in one)."""
        assert _is_git_repo() is True

    def test_get_git_root_returns_path(self):
        """Returns a path when in a git repo."""
        root = _get_git_root()
        assert root is not None
        assert os.path.isdir(root)

    def test_run_git_branch(self):
        """Can get current branch."""
        branch = _run_git("branch", "--show-current")
        assert branch is not None  # Could be empty for detached HEAD

    def test_run_git_invalid_command(self):
        """Invalid git command returns None."""
        result = _run_git("not-a-real-command")
        assert result is None

    @patch("hestia_cli.context.subprocess.run")
    def test_is_git_repo_not_in_repo(self, mock_run):
        """Returns False when not in a git repo."""
        mock_run.return_value = MagicMock(returncode=128)
        assert _is_git_repo() is False

    @patch("hestia_cli.context.subprocess.run")
    def test_is_git_repo_git_not_installed(self, mock_run):
        """Returns False when git is not installed."""
        mock_run.side_effect = FileNotFoundError
        assert _is_git_repo() is False


# ============== Repo Context ==============


class TestGetRepoContext:
    """Tests for the main get_repo_context function."""

    def test_returns_cwd(self):
        """Always includes cwd."""
        ctx = get_repo_context()
        assert "cwd" in ctx
        assert ctx["cwd"] == os.getcwd()

    def test_includes_git_info_in_repo(self):
        """Includes git branch and commits when in a repo."""
        ctx = get_repo_context()
        assert "git_branch" in ctx
        assert "git_recent_commits" in ctx

    def test_includes_project_files(self):
        """Includes project_files when they exist."""
        ctx = get_repo_context()
        # We're running from hestia-cli/ which may not have SPRINT.md,
        # but the git root (hestia/) does
        if "project_files" in ctx:
            assert isinstance(ctx["project_files"], dict)

    @patch("hestia_cli.context._is_git_repo", return_value=False)
    def test_non_git_still_returns_cwd(self, mock_git):
        """Returns cwd even when not in git repo."""
        ctx = get_repo_context()
        assert "cwd" in ctx
        assert "git_branch" not in ctx


# ============== Project File Snippets ==============


class TestGetProjectFileSnippets:
    """Tests for project file auto-include."""

    def test_reads_existing_files(self):
        """Reads files that exist in CWD or git root."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            (Path(tmpdir) / "SPRINT.md").write_text("# Sprint 1\nDo stuff")
            (Path(tmpdir) / "README.md").write_text("# My Project")

            with patch("hestia_cli.context._get_git_root", return_value=tmpdir):
                snippets = get_project_file_snippets()

            assert "SPRINT.md" in snippets
            assert "README.md" in snippets
            assert "Do stuff" in snippets["SPRINT.md"]

    def test_skips_missing_files(self):
        """Files that don't exist are silently skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Only create one file
            (Path(tmpdir) / "README.md").write_text("# Hello")

            with patch("hestia_cli.context._get_git_root", return_value=tmpdir):
                snippets = get_project_file_snippets()

            assert "README.md" in snippets
            assert "SPRINT.md" not in snippets
            assert "CLAUDE.md" not in snippets

    def test_truncates_large_files(self):
        """Large files are truncated to MAX_CHARS_PER_FILE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            large_content = "x" * (MAX_CHARS_PER_FILE + 500)
            (Path(tmpdir) / "README.md").write_text(large_content)

            with patch("hestia_cli.context._get_git_root", return_value=tmpdir):
                snippets = get_project_file_snippets()

            assert len(snippets["README.md"]) <= MAX_CHARS_PER_FILE + 50  # Allow for truncation message

    def test_respects_total_budget(self):
        """Stops reading files once total budget is exhausted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create all project files, each at max size
            for filename in PROJECT_FILES:
                content = f"# {filename}\n" + "y" * MAX_CHARS_PER_FILE
                (Path(tmpdir) / filename).write_text(content)

            with patch("hestia_cli.context._get_git_root", return_value=tmpdir):
                snippets = get_project_file_snippets()

            # Total chars should be <= MAX_TOTAL_CHARS (plus truncation messages)
            total = sum(len(v) for v in snippets.values())
            assert total <= MAX_TOTAL_CHARS + 100  # Small buffer for truncation text

    def test_empty_files_skipped(self):
        """Empty files are not included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "SPRINT.md").write_text("")
            (Path(tmpdir) / "README.md").write_text("# Content")

            with patch("hestia_cli.context._get_git_root", return_value=tmpdir):
                snippets = get_project_file_snippets()

            assert "SPRINT.md" not in snippets
            assert "README.md" in snippets

    def test_no_files_returns_empty(self):
        """Returns empty dict when no project files found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("hestia_cli.context._get_git_root", return_value=tmpdir):
                snippets = get_project_file_snippets()

            assert snippets == {}

    def test_priority_order(self):
        """Files are read in priority order (CLAUDE > SPRINT > ROADMAP > README)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for filename in PROJECT_FILES:
                (Path(tmpdir) / filename).write_text(f"# {filename}")

            with patch("hestia_cli.context._get_git_root", return_value=tmpdir):
                snippets = get_project_file_snippets()

            keys = list(snippets.keys())
            # First file should be CLAUDE.md (highest priority for coding)
            assert keys[0] == "CLAUDE.md"
