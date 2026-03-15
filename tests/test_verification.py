"""Tests for the self-modification verification layer."""
import pytest
from hestia.execution.verification import (
    is_self_modification,
    find_test_file,
    VerificationResult,
)


class TestSelfModificationDetection:
    def test_detects_own_source_code(self):
        assert is_self_modification("/Users/andrewlonati/hestia/hestia/memory/manager.py")

    def test_detects_test_files(self):
        assert is_self_modification("/Users/andrewlonati/hestia/tests/test_memory.py")

    def test_detects_cli_code(self):
        assert is_self_modification("/Users/andrewlonati/hestia/hestia-cli/hestia_cli/app.py")

    def test_detects_scripts(self):
        assert is_self_modification("/Users/andrewlonati/hestia/scripts/deploy.sh")

    def test_ignores_data_files(self):
        assert not is_self_modification("/Users/andrewlonati/hestia/data/user/MEMORY.md")

    def test_ignores_docs(self):
        assert not is_self_modification("/Users/andrewlonati/hestia/docs/api-contract.md")

    def test_ignores_external_files(self):
        assert not is_self_modification("/Users/andrewlonati/Documents/notes.txt")


class TestTestFileMapping:
    def test_memory_module(self):
        result = find_test_file("hestia/memory/manager.py")
        assert result == "tests/test_memory.py"

    def test_research_module(self):
        result = find_test_file("hestia/research/database.py")
        assert result == "tests/test_research.py"

    def test_orchestration_module(self):
        result = find_test_file("hestia/orchestration/handler.py")
        assert result == "tests/test_orchestration.py"

    def test_unknown_module(self):
        result = find_test_file("hestia/nonexistent/module.py")
        assert result is None

    def test_api_routes_no_generic_test(self):
        """Routes don't have a single test file — returns None for unmatched."""
        result = find_test_file("hestia/api/routes/chat.py")
        # test_routes.py doesn't exist — individual route modules have specific test files
        assert result is None


class TestVerificationResult:
    def test_to_dict(self):
        result = VerificationResult(
            is_self_modification=True,
            test_file="tests/test_memory.py",
            post_test_passed=True,
            diff="some diff content",
        )
        d = result.to_dict()
        assert d["is_self_modification"] is True
        assert d["test_file"] == "tests/test_memory.py"
        assert d["post_test_passed"] is True
        assert d["diff_length"] > 0

    def test_non_self_modification(self):
        result = VerificationResult()
        assert result.is_self_modification is False
        assert result.test_file is None
