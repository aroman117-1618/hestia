"""Tests for code editing tools (edit_file, glob_files, grep_files)."""
import asyncio
import pytest
from pathlib import Path
from unittest.mock import patch

from hestia.execution.tools.code_tools import (
    edit_file_handler,
    glob_files_handler,
    grep_files_handler,
    _check_agentic_denied,
)


def _mock_sandbox_validate(path, write=False):
    """No-op sandbox validator for tests."""
    pass


class TestEditFileTool:
    @pytest.fixture(autouse=True)
    def mock_sandbox(self):
        """Bypass sandbox validation for test tmp_path files."""
        with patch("hestia.execution.tools.code_tools.get_sandbox_runner") as mock:
            mock.return_value.validate_path = _mock_sandbox_validate
            yield

    def test_edit_replaces_exact_match(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 'world'\n")
        result = asyncio.get_event_loop().run_until_complete(
            edit_file_handler(str(f), "return 'world'", "return 'hello world'")
        )
        assert result["success"] is True
        assert "return 'hello world'" in f.read_text()

    def test_edit_fails_if_old_string_not_found(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def hello():\n    return 'world'\n")
        result = asyncio.get_event_loop().run_until_complete(
            edit_file_handler(str(f), "nonexistent string", "replacement")
        )
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_edit_fails_if_old_string_not_unique(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\nx = 1\n")
        result = asyncio.get_event_loop().run_until_complete(
            edit_file_handler(str(f), "x = 1", "x = 2")
        )
        assert result["success"] is False
        assert "not unique" in result["error"].lower()

    def test_edit_preserves_file_on_failure(self, tmp_path):
        f = tmp_path / "test.py"
        original = "def foo():\n    pass\n"
        f.write_text(original)
        asyncio.get_event_loop().run_until_complete(
            edit_file_handler(str(f), "nonexistent", "replacement")
        )
        assert f.read_text() == original

    def test_edit_reports_char_counts(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello world\n")
        result = asyncio.get_event_loop().run_until_complete(
            edit_file_handler(str(f), "hello", "hi")
        )
        assert result["success"] is True
        assert result["chars_removed"] == 5
        assert result["chars_added"] == 2


class TestAgenticDeniedPaths:
    def test_blocks_security_module(self):
        result = _check_agentic_denied("/Users/test/hestia/hestia/security/creds.py")
        assert result is not None
        assert "security" in result.lower()

    def test_blocks_config_module(self):
        result = _check_agentic_denied("/Users/test/hestia/hestia/config/execution.yaml")
        assert result is not None

    def test_blocks_env_files(self):
        result = _check_agentic_denied("/Users/test/hestia/.env")
        assert result is not None

    def test_allows_normal_code(self):
        result = _check_agentic_denied("/Users/test/hestia/hestia/memory/manager.py")
        assert result is None

    def test_allows_tests(self):
        result = _check_agentic_denied("/Users/test/hestia/tests/test_memory.py")
        assert result is None


class TestGlobFilesTool:
    def test_glob_finds_files(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")
        (tmp_path / "c.txt").write_text("text")
        result = asyncio.get_event_loop().run_until_complete(
            glob_files_handler("*.py", str(tmp_path))
        )
        assert result["count"] == 2
        assert all(".py" in f for f in result["files"])

    def test_glob_empty_dir(self, tmp_path):
        result = asyncio.get_event_loop().run_until_complete(
            glob_files_handler("*.py", str(tmp_path))
        )
        assert result["count"] == 0


class TestGrepFilesTool:
    def test_grep_finds_matches(self, tmp_path):
        (tmp_path / "a.py").write_text("def hello():\n    return 42\n")
        (tmp_path / "b.py").write_text("def world():\n    return 0\n")
        result = asyncio.get_event_loop().run_until_complete(
            grep_files_handler("return 42", str(tmp_path))
        )
        assert result["count"] == 1
        assert result["matches"][0]["line"] == 2

    def test_grep_regex(self, tmp_path):
        (tmp_path / "a.py").write_text("class Foo:\n    pass\nclass Bar:\n    pass\n")
        result = asyncio.get_event_loop().run_until_complete(
            grep_files_handler(r"class \w+:", str(tmp_path))
        )
        assert result["count"] == 2

    def test_grep_invalid_regex(self, tmp_path):
        result = asyncio.get_event_loop().run_until_complete(
            grep_files_handler("[invalid", str(tmp_path))
        )
        assert "error" in result
