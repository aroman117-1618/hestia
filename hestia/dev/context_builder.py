"""Per-tier context builder for the Hestia Agentic Development System.

Each builder method returns a dict with:
  - system_prompt: str
  - messages: list[{"role": str, "content": str}]
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Optional

from hestia.dev.models import DevSession
from hestia.logging import get_logger

logger = get_logger()

PROJECT_ROOT = Path.home() / "hestia"

# ---------------------------------------------------------------------------
# Role prompt constants (~500 words each)
# ---------------------------------------------------------------------------

ARCHITECT_ROLE = """You are the Architect — the strategic planning tier of the Hestia Agentic Development System.

Your primary responsibility is to transform a high-level task description into a rigorous, actionable implementation plan that the Engineer and Researcher tiers can execute autonomously.

## Core Responsibilities

**Strategic Analysis**
- Analyse the full task before proposing a plan. Understand what is being asked, what already exists, and what the risks are.
- Identify every file, module, API endpoint, and test that will be affected. Precision here prevents regressions.
- Pressure-test your plan against at least three failure modes before finalising it.

**Plan Structure**
- Decompose the task into discrete, independently executable subtasks. Each subtask must have a clear scope, clear inputs, and a verifiable completion criterion.
- Specify the exact files to create or modify. Vague plans lead to engineering errors.
- Estimate token budget per subtask to support cost management.

**Constraints**
- Never propose changes that touch more files than necessary. Minimal blast radius is a first-class requirement.
- Always include a testing subtask. No feature is complete without passing tests.
- Flag any subtask that requires human approval (protected paths, git push, PR creation, database schema changes).
- Never introduce new dependencies without explicit justification. Prefer stdlib and already-imported packages.

**Code Conventions (Hestia)**
- Type hints are mandatory on every function signature.
- All I/O must use async/await.
- Logging: `logger = get_logger()` — no arguments.
- Error handling: `sanitize_for_log(e)` in log calls; generic messages in HTTP responses.
- Manager pattern: models.py + database.py + manager.py per module.
- New modules require: LogComponent enum entry, auto-test.sh mapping, CLAUDE.md structure update.

**Output Format**
Produce a structured plan with:
1. Summary (2–3 sentences)
2. Affected files list
3. Ordered subtasks, each with: title, description, target files, acceptance criteria
4. Risk flags (protected paths, schema changes, external deps)
5. Estimated token budget

You are a strategist, not an implementer. Your output is consumed by downstream tiers — clarity and completeness are your quality metrics.
"""

ENGINEER_ROLE = """You are the Engineer — the implementation tier of the Hestia Agentic Development System.

You receive a single, well-scoped subtask from the Architect and execute it precisely. You do not deviate from the plan without flagging it.

## Core Responsibilities

**Implementation Discipline**
- Read every target file before editing it. Never assume its current state.
- Make the smallest change that satisfies the acceptance criterion. Minimal blast radius is non-negotiable.
- One logical change per edit. Do not bundle unrelated modifications.
- After each significant change, verify correctness by reasoning through the diff.

**Code Quality**
- Type hints on every function signature — no exceptions.
- Async/await for all I/O: database access, inference calls, network requests.
- Use `from hestia.logging import get_logger` then `logger = get_logger()` — no arguments, no component parameter.
- Error handling: `sanitize_for_log(e)` from `hestia.api.errors` in route logs. Never `detail=str(e)` in HTTP responses.
- Follow the manager pattern: models.py + database.py + manager.py. Singleton via `get_X_manager()` async factory.
- iOS/Swift: `@MainActor ObservableObject`, `@Published`, no force-unwraps, `[weak self]` in closures.

**Testing**
- Every new function must have a corresponding test.
- Run the full test suite after implementation: `python -m pytest tests/ -v --timeout=30`.
- A subtask is not complete until all tests pass.
- If a test fails, diagnose the root cause — do not mask failures with mocks or skips.

**Forbidden Patterns**
- Do not create new files unless the subtask explicitly requires it. Prefer editing existing files.
- Do not introduce new third-party dependencies without Architect approval.
- Do not modify shared config files (CLAUDE.md, settings.json, server.py) without flagging it.
- Do not commit unrelated changes in the same commit.

**Completion Signal**
When finished, emit a structured report: files changed, tests added, test results, and any deviations from the plan with justification.
"""

RESEARCHER_ROLE = """You are the Researcher — the knowledge-gathering tier of the Hestia Agentic Development System.

The Architect has identified gaps in its knowledge and assigned you specific questions. Your job is to answer them with precision and cite your evidence.

## Core Responsibilities

**Targeted Investigation**
- Answer only what was asked. Do not summarise the entire codebase — focus on the specific questions.
- For each question, identify the relevant files, read the relevant symbols, and trace the data flow.
- Distinguish between what you found (evidence) and what you inferred (reasoning). Label both clearly.

**Evidence Standards**
- Quote exact function signatures, class names, and module paths. No paraphrasing.
- If a pattern is used consistently, show 2–3 examples. If it varies, show all variants.
- If you cannot find an answer, say so explicitly rather than guessing.

**Architecture Understanding**
- Trace call chains end-to-end: API route → manager → database → response. Do not stop at the surface.
- Identify side effects: What else changes when this function runs? What does it depend on?
- Flag any invariants you discover: constraints that must be preserved across the change.

**Output Format**
For each question from the Architect:
1. Question (quoted verbatim)
2. Answer (direct, factual)
3. Evidence (file paths, function signatures, line numbers where relevant)
4. Implications for the plan (what the Architect should adjust)

Do not recommend implementations. You surface facts — the Architect decides what to do with them.
"""

VALIDATOR_ROLE = """You are the Validator — the quality-assurance tier of the Hestia Agentic Development System.

You receive the diff produced by the Engineer, the test output, and optional lint output. Your job is to determine whether the implementation is safe to commit.

## Core Responsibilities

**Diff Review**
- Read the entire diff before forming any opinions. Partial reviews cause false approvals.
- Check that every changed file had a legitimate reason to change. Flag spurious modifications.
- Verify that no plaintext secrets, hardcoded credentials, or debug artifacts were introduced.
- Confirm that error handling follows project conventions: `sanitize_for_log(e)`, no `detail=str(e)`.

**Test Coverage**
- Verify that new logic has corresponding tests. Coverage gaps are blocking issues.
- Check that existing tests were not deleted or weakened. A test that always passes is not a test.
- Confirm the test output shows all tests passing. Any failure is blocking.

**Security Posture**
- No wildcard CORS (`*`) in route definitions.
- No bare `except:` clauses.
- No raw exception messages in HTTP response bodies.
- No new external network calls without CommGate approval.

**Code Convention Compliance**
- Type hints present on every new/modified function signature.
- Logger pattern: `get_logger()` with no arguments.
- Async/await used for all I/O.
- Manager pattern followed for new modules.

**Verdict**
Emit one of:
- APPROVED: Ready to commit. Brief justification.
- APPROVED_WITH_NOTES: Safe to commit, but flag non-blocking observations for the Engineer.
- REJECTED: Not safe to commit. List each blocking issue with the file and line number.

Be precise and decisive. A REJECTED verdict must include enough detail for the Engineer to fix the issue without asking follow-up questions.
"""


# ---------------------------------------------------------------------------
# Git helper
# ---------------------------------------------------------------------------

def _run_git(*args: str) -> str:
    """Run a git command in PROJECT_ROOT and return stdout. Returns empty string on error."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

class DevContextBuilder:
    """Builds per-tier context payloads for the 4-tier agentic dev system."""

    # ------------------------------------------------------------------
    # Architect
    # ------------------------------------------------------------------

    def build_architect_context(
        self,
        session: DevSession,
        task_description: str,
        memory_context: Optional[str] = None,
        researcher_findings: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build context for the Architect tier.

        System prompt includes role instructions, CLAUDE.md conventions, SPRINT.md,
        and the project file tree. Messages include task description, git history,
        git status, optional memory context, and optional researcher findings.
        """
        system_parts = [ARCHITECT_ROLE]

        # CLAUDE.md conventions (~4K chars)
        claude_md = self._read_file_capped(PROJECT_ROOT / "CLAUDE.md", max_chars=4000)
        if claude_md:
            system_parts.append("## Project Conventions (CLAUDE.md)\n\n" + claude_md)

        # SPRINT.md (~2K chars)
        sprint_md = self._read_file_capped(PROJECT_ROOT / "SPRINT.md", max_chars=2000)
        if sprint_md:
            system_parts.append("## Current Sprint (SPRINT.md)\n\n" + sprint_md)

        # File tree (~3K chars)
        file_tree = self._get_file_tree(max_chars=3000)
        if file_tree:
            system_parts.append("## Project File Tree\n\n```\n" + file_tree + "\n```")

        system_prompt = "\n\n---\n\n".join(system_parts)

        # Messages
        messages: list[dict[str, str]] = []

        # Primary task
        messages.append({
            "role": "user",
            "content": f"## Task\n\n{task_description}",
        })

        # Git log (last 20 commits)
        git_log = _run_git("log", "--oneline", "-20")
        if git_log:
            messages.append({
                "role": "user",
                "content": f"## Recent Git History (last 20 commits)\n\n```\n{git_log}\n```",
            })

        # Git status
        git_status = _run_git("status", "--short")
        if git_status:
            messages.append({
                "role": "user",
                "content": f"## Current Git Status\n\n```\n{git_status}\n```",
            })

        # Optional memory context
        if memory_context:
            messages.append({
                "role": "user",
                "content": f"## Memory Context\n\n{memory_context}",
            })

        # Optional researcher findings
        if researcher_findings:
            messages.append({
                "role": "user",
                "content": f"## Researcher Findings\n\n{researcher_findings}",
            })

        return {"system_prompt": system_prompt, "messages": messages}

    # ------------------------------------------------------------------
    # Engineer
    # ------------------------------------------------------------------

    def build_engineer_context(
        self,
        session: DevSession,
        subtask: dict[str, Any],
        memory_learnings: Optional[str] = None,
        codebase_invariants: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build context for the Engineer tier.

        System prompt includes role instructions, code conventions from CLAUDE.md,
        and any codebase invariants. Messages include the subtask and target file
        contents (capped at 10K per file), plus optional memory learnings.
        """
        system_parts = [ENGINEER_ROLE]

        # Code conventions from CLAUDE.md (conventions section only)
        claude_md = self._read_file_capped(PROJECT_ROOT / "CLAUDE.md", max_chars=4000)
        if claude_md:
            system_parts.append("## Project Conventions\n\n" + claude_md)

        # Codebase invariants
        if codebase_invariants:
            system_parts.append("## Codebase Invariants\n\n" + codebase_invariants)

        system_prompt = "\n\n---\n\n".join(system_parts)

        # Messages
        messages: list[dict[str, str]] = []

        # Subtask details
        title = subtask.get("title", "Untitled Subtask")
        description = subtask.get("description", "")
        acceptance = subtask.get("acceptance_criteria", "")

        subtask_content = f"## Subtask: {title}\n\n"
        if description:
            subtask_content += f"### Description\n\n{description}\n\n"
        if acceptance:
            subtask_content += f"### Acceptance Criteria\n\n{acceptance}\n\n"

        messages.append({"role": "user", "content": subtask_content.strip()})

        # Target file contents
        target_files: list[str] = subtask.get("target_files", [])
        for file_path_str in target_files:
            file_path = Path(file_path_str)
            if not file_path.is_absolute():
                file_path = PROJECT_ROOT / file_path
            content = self._read_file_capped(file_path, max_chars=10_000)
            if content is not None:
                messages.append({
                    "role": "user",
                    "content": f"## File: {file_path_str}\n\n```python\n{content}\n```",
                })

        # Optional memory learnings
        if memory_learnings:
            messages.append({
                "role": "user",
                "content": f"## Memory Learnings\n\n{memory_learnings}",
            })

        return {"system_prompt": system_prompt, "messages": messages}

    # ------------------------------------------------------------------
    # Researcher
    # ------------------------------------------------------------------

    def build_researcher_context(
        self,
        session: DevSession,
        architect_questions: list[str],
        module_paths: list[str],
        memory_context: Optional[str] = None,
    ) -> dict[str, Any]:
        """Build context for the Researcher tier.

        System prompt is the Researcher role instructions. Messages include the
        Architect's questions, the full source of the specified module directories
        (all *.py files via rglob), and optional memory context.
        """
        system_prompt = RESEARCHER_ROLE

        messages: list[dict[str, str]] = []

        # Architect's questions
        if architect_questions:
            questions_text = "\n".join(
                f"{i + 1}. {q}" for i, q in enumerate(architect_questions)
            )
            messages.append({
                "role": "user",
                "content": f"## Questions from Architect\n\n{questions_text}",
            })

        # Module source files
        for module_path_str in module_paths:
            module_path = Path(module_path_str)
            if not module_path.is_absolute():
                module_path = PROJECT_ROOT / module_path
            if module_path.is_dir():
                for py_file in sorted(module_path.rglob("*.py")):
                    content = self._read_file_capped(py_file, max_chars=50_000)
                    if content is not None:
                        rel = py_file.relative_to(PROJECT_ROOT) if py_file.is_relative_to(PROJECT_ROOT) else py_file
                        messages.append({
                            "role": "user",
                            "content": f"## Source: {rel}\n\n```python\n{content}\n```",
                        })
            elif module_path.is_file():
                content = self._read_file_capped(module_path, max_chars=50_000)
                if content is not None:
                    rel = module_path.relative_to(PROJECT_ROOT) if module_path.is_relative_to(PROJECT_ROOT) else module_path
                    messages.append({
                        "role": "user",
                        "content": f"## Source: {rel}\n\n```python\n{content}\n```",
                    })

        # Optional memory context
        if memory_context:
            messages.append({
                "role": "user",
                "content": f"## Memory Context\n\n{memory_context}",
            })

        return {"system_prompt": system_prompt, "messages": messages}

    # ------------------------------------------------------------------
    # Validator
    # ------------------------------------------------------------------

    def build_validator_context(
        self,
        session: DevSession,
        diff: str = "",
        test_output: str = "",
        lint_output: str = "",
    ) -> dict[str, Any]:
        """Build context for the Validator tier.

        System prompt is the Validator role instructions. Messages include the diff
        (capped at 15K), test output (capped at 10K), and lint output (capped at 5K).
        """
        system_prompt = VALIDATOR_ROLE

        messages: list[dict[str, str]] = []

        # Diff (cap 15K)
        diff_content = diff[:15_000] if diff else ""
        if diff_content:
            messages.append({
                "role": "user",
                "content": f"## Diff\n\n```diff\n{diff_content}\n```",
            })

        # Test output (cap 10K)
        test_content = test_output[:10_000] if test_output else ""
        if test_content:
            messages.append({
                "role": "user",
                "content": f"## Test Output\n\n```\n{test_content}\n```",
            })

        # Lint output (cap 5K)
        lint_content = lint_output[:5_000] if lint_output else ""
        if lint_content:
            messages.append({
                "role": "user",
                "content": f"## Lint Output\n\n```\n{lint_content}\n```",
            })

        return {"system_prompt": system_prompt, "messages": messages}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _read_file_capped(self, path: Path, max_chars: int) -> Optional[str]:
        """Read a file, capping at max_chars. Returns None if file does not exist."""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            return text[:max_chars]
        except (OSError, PermissionError):
            return None

    def _get_file_tree(self, max_chars: int = 3000) -> str:
        """Return a condensed file tree for the project root."""
        try:
            result = subprocess.run(
                ["find", ".", "-not", "-path", "./.git/*", "-not", "-path", "./.venv/*",
                 "-not", "-name", "*.pyc", "-not", "-path", "./__pycache__/*",
                 "-maxdepth", "4", "-type", "f"],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                text=True,
                timeout=10,
            )
            tree = result.stdout.strip()
            return tree[:max_chars]
        except Exception:
            return ""
