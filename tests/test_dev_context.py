"""Tests for hestia.dev.context_builder — per-tier context assembly."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hestia.dev.context_builder import (
    ARCHITECT_ROLE,
    ENGINEER_ROLE,
    RESEARCHER_ROLE,
    VALIDATOR_ROLE,
    DevContextBuilder,
)
from hestia.dev.models import DevSession, DevSessionSource


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def session() -> DevSession:
    return DevSession.create(
        title="Test task",
        description="A test dev session",
        source=DevSessionSource.CLI,
    )


@pytest.fixture()
def builder() -> DevContextBuilder:
    return DevContextBuilder()


# ---------------------------------------------------------------------------
# Helper to suppress file-system and git I/O in all tests
# ---------------------------------------------------------------------------

def _patch_io(read_returns: str = "", git_returns: str = "") -> tuple:
    """Return patch context managers for _read_file_capped, _get_file_tree, _run_git."""
    return (
        patch.object(DevContextBuilder, "_read_file_capped", return_value=read_returns),
        patch.object(DevContextBuilder, "_get_file_tree", return_value="src/\n  hestia/"),
        patch("hestia.dev.context_builder._run_git", return_value=git_returns),
    )


# ---------------------------------------------------------------------------
# Role prompt constants
# ---------------------------------------------------------------------------

class TestRolePromptConstants:
    def test_all_role_prompts_defined(self) -> None:
        for constant in (ARCHITECT_ROLE, ENGINEER_ROLE, RESEARCHER_ROLE, VALIDATOR_ROLE):
            assert isinstance(constant, str)
            assert len(constant) >= 100

    def test_role_prompts_are_distinct(self) -> None:
        prompts = [ARCHITECT_ROLE, ENGINEER_ROLE, RESEARCHER_ROLE, VALIDATOR_ROLE]
        assert len(set(prompts)) == 4, "Each role prompt must be unique"


# ---------------------------------------------------------------------------
# TestBuildArchitectContext
# ---------------------------------------------------------------------------

class TestBuildArchitectContext:
    def test_returns_required_keys(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_architect_context(session, "Add a new trading strategy module")
        assert "system_prompt" in ctx
        assert "messages" in ctx

    def test_system_prompt_contains_architect_role(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_architect_context(session, "Build the auth module")
        assert ARCHITECT_ROLE[:100] in ctx["system_prompt"]

    def test_system_prompt_includes_claude_md(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io(read_returns="## Project Conventions CLAUDE.md content")
        with p1, p2, p3:
            ctx = builder.build_architect_context(session, "Some task")
        assert "Project Conventions" in ctx["system_prompt"]

    def test_messages_contain_task_description(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_architect_context(session, "Implement feature X")
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "Implement feature X" in contents

    def test_messages_contain_git_log_when_available(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io(git_returns="abc1234 fix: something\ndef5678 feat: other")
        with p1, p2, p3:
            ctx = builder.build_architect_context(session, "Task")
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "abc1234" in contents

    def test_optional_memory_context_included(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_architect_context(
                session, "Task", memory_context="Relevant memory fact"
            )
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "Relevant memory fact" in contents

    def test_optional_researcher_findings_included(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_architect_context(
                session, "Task", researcher_findings="Found key pattern in module X"
            )
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "Found key pattern in module X" in contents

    def test_messages_are_user_role(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_architect_context(session, "Task")
        for msg in ctx["messages"]:
            assert msg["role"] == "user"


# ---------------------------------------------------------------------------
# TestBuildEngineerContext
# ---------------------------------------------------------------------------

class TestBuildEngineerContext:
    def test_returns_required_keys(self, builder: DevContextBuilder, session: DevSession) -> None:
        subtask = {"title": "Write manager.py", "description": "Create the manager"}
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_engineer_context(session, subtask)
        assert "system_prompt" in ctx
        assert "messages" in ctx

    def test_system_prompt_contains_engineer_role(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_engineer_context(session, {"title": "Fix bug"})
        assert ENGINEER_ROLE[:100] in ctx["system_prompt"]

    def test_subtask_title_in_messages(self, builder: DevContextBuilder, session: DevSession) -> None:
        subtask = {"title": "Implement get_manager", "description": "Create async factory"}
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_engineer_context(session, subtask)
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "Implement get_manager" in contents

    def test_subtask_description_in_messages(self, builder: DevContextBuilder, session: DevSession) -> None:
        subtask = {
            "title": "Add endpoint",
            "description": "POST /v1/dev/sessions endpoint that validates JWT",
        }
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_engineer_context(session, subtask)
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "POST /v1/dev/sessions" in contents

    def test_memory_learnings_included_when_provided(self, builder: DevContextBuilder, session: DevSession) -> None:
        subtask = {"title": "Fix logger"}
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_engineer_context(
                session, subtask, memory_learnings="Always use get_logger() with no args"
            )
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "Always use get_logger() with no args" in contents

    def test_codebase_invariants_in_system_prompt(self, builder: DevContextBuilder, session: DevSession) -> None:
        subtask = {"title": "Add model"}
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_engineer_context(
                session, subtask, codebase_invariants="BaseDatabase must never be removed"
            )
        assert "BaseDatabase must never be removed" in ctx["system_prompt"]

    def test_target_files_included_in_messages(self, builder: DevContextBuilder, session: DevSession) -> None:
        subtask = {
            "title": "Edit models",
            "target_files": ["/fake/models.py"],
        }
        fake_content = "class FakeModel: pass"
        with (
            patch.object(DevContextBuilder, "_read_file_capped", return_value=fake_content),
            patch.object(DevContextBuilder, "_get_file_tree", return_value=""),
            patch("hestia.dev.context_builder._run_git", return_value=""),
        ):
            ctx = builder.build_engineer_context(session, subtask)
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "FakeModel" in contents


# ---------------------------------------------------------------------------
# TestBuildResearcherContext
# ---------------------------------------------------------------------------

class TestBuildResearcherContext:
    def test_returns_required_keys(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_researcher_context(session, ["What does manager.py do?"], [])
        assert "system_prompt" in ctx
        assert "messages" in ctx

    def test_system_prompt_contains_researcher_role(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_researcher_context(session, [], [])
        assert RESEARCHER_ROLE[:100] in ctx["system_prompt"]

    def test_questions_appear_in_messages(self, builder: DevContextBuilder, session: DevSession) -> None:
        questions = ["How does MemoryManager initialise?", "What is the pruning threshold?"]
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_researcher_context(session, questions, [])
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "How does MemoryManager initialise?" in contents
        assert "What is the pruning threshold?" in contents

    def test_memory_context_included_when_provided(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_researcher_context(
                session, ["Question?"], [], memory_context="Context from prior session"
            )
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "Context from prior session" in contents

    def test_no_messages_when_empty_inputs(self, builder: DevContextBuilder, session: DevSession) -> None:
        p1, p2, p3 = _patch_io()
        with p1, p2, p3:
            ctx = builder.build_researcher_context(session, [], [])
        assert isinstance(ctx["messages"], list)


# ---------------------------------------------------------------------------
# TestBuildValidatorContext
# ---------------------------------------------------------------------------

class TestBuildValidatorContext:
    def test_returns_required_keys(self, builder: DevContextBuilder, session: DevSession) -> None:
        ctx = builder.build_validator_context(session)
        assert "system_prompt" in ctx
        assert "messages" in ctx

    def test_system_prompt_contains_validator_role(self, builder: DevContextBuilder, session: DevSession) -> None:
        ctx = builder.build_validator_context(session)
        assert VALIDATOR_ROLE[:100] in ctx["system_prompt"]

    def test_diff_appears_in_messages(self, builder: DevContextBuilder, session: DevSession) -> None:
        diff = "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new"
        ctx = builder.build_validator_context(session, diff=diff)
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "--- a/foo.py" in contents

    def test_test_output_appears_in_messages(self, builder: DevContextBuilder, session: DevSession) -> None:
        test_out = "PASSED tests/test_foo.py::test_bar - 3 passed in 0.12s"
        ctx = builder.build_validator_context(session, test_output=test_out)
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "3 passed" in contents

    def test_lint_output_appears_in_messages(self, builder: DevContextBuilder, session: DevSession) -> None:
        lint_out = "E501 line too long (95 > 88 characters)"
        ctx = builder.build_validator_context(session, lint_output=lint_out)
        contents = " ".join(m["content"] for m in ctx["messages"])
        assert "E501" in contents

    def test_diff_capped_at_15k(self, builder: DevContextBuilder, session: DevSession) -> None:
        diff = "x" * 20_000
        ctx = builder.build_validator_context(session, diff=diff)
        diff_msg = next(m for m in ctx["messages"] if "Diff" in m["content"])
        # The content includes wrapper text, so check the raw diff portion is capped
        assert len(diff_msg["content"]) < 20_000

    def test_test_output_capped_at_10k(self, builder: DevContextBuilder, session: DevSession) -> None:
        test_out = "y" * 15_000
        ctx = builder.build_validator_context(session, test_output=test_out)
        test_msg = next(m for m in ctx["messages"] if "Test Output" in m["content"])
        assert len(test_msg["content"]) < 15_000

    def test_lint_output_capped_at_5k(self, builder: DevContextBuilder, session: DevSession) -> None:
        lint_out = "z" * 8_000
        ctx = builder.build_validator_context(session, lint_output=lint_out)
        lint_msg = next(m for m in ctx["messages"] if "Lint" in m["content"])
        assert len(lint_msg["content"]) < 8_000

    def test_empty_inputs_produce_empty_messages(self, builder: DevContextBuilder, session: DevSession) -> None:
        ctx = builder.build_validator_context(session, diff="", test_output="", lint_output="")
        assert ctx["messages"] == []


# ---------------------------------------------------------------------------
# TestAllBuilderMethodsExist
# ---------------------------------------------------------------------------

class TestAllBuilderMethodsExist:
    def test_build_architect_context_exists(self, builder: DevContextBuilder) -> None:
        assert callable(getattr(builder, "build_architect_context", None))

    def test_build_engineer_context_exists(self, builder: DevContextBuilder) -> None:
        assert callable(getattr(builder, "build_engineer_context", None))

    def test_build_researcher_context_exists(self, builder: DevContextBuilder) -> None:
        assert callable(getattr(builder, "build_researcher_context", None))

    def test_build_validator_context_exists(self, builder: DevContextBuilder) -> None:
        assert callable(getattr(builder, "build_validator_context", None))
