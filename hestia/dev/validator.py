from __future__ import annotations
"""ValidatorAgent — quality-assurance tier for the Hestia Agentic Dev System.

Calls Claude Haiku via the cloud client for AI-assisted diff analysis.
Also runs pytest and xcodebuild directly for objective test/build verification.
"""

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.cloud.models import CloudProvider
from hestia.dev.context_builder import DevContextBuilder
from hestia.dev.models import DevSession
from hestia.inference.client import Message
from hestia.logging import get_logger

logger = get_logger()

PROJECT_ROOT = Path.home() / "hestia"


class ValidatorAgent:
    """Quality-assurance agent backed by Claude Haiku.

    Runs tests and lint checks directly, then optionally uses Haiku for
    AI-assisted diff analysis when a cloud client is provided.
    """

    def __init__(self, cloud_client: Optional[Any] = None) -> None:
        self._cloud = cloud_client
        self._context_builder = DevContextBuilder()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_tests(
        self,
        path: str = "",
        marker: str = "",
    ) -> Dict[str, Any]:
        """Run pytest and return structured results.

        Args:
            path: Optional path to a test file or directory.
            marker: Optional pytest marker expression.

        Returns:
            {"passed": bool, "returncode": int, "stdout": str, "stderr": str}
        """
        from hestia.dev.tools import run_tests_handler
        return await run_tests_handler(path=path or None, marker=marker or None)

    async def run_xcode_build(self, scheme: str = "HestiaWorkspace") -> Dict[str, Any]:
        """Run xcodebuild and return results.

        Args:
            scheme: Xcode scheme to build (default: HestiaWorkspace).

        Returns:
            {"success": bool, "stdout": str, "stderr": str}
        """
        from hestia.dev.tools import xcode_build_handler
        return await xcode_build_handler(scheme=scheme)

    async def validate_session(
        self,
        session: DevSession,
        diff: str = "",
    ) -> Dict[str, Any]:
        """Full validation: tests + lint + optional AI analysis.

        Runs the test suite and a basic lint pass on changed Python files.
        If a cloud client is configured and a diff is provided, also calls
        Haiku for an AI-assisted review of the diff.

        Args:
            session: The active dev session.
            diff: Optional unified diff string for lint extraction and AI review.

        Returns:
            {
                "passed": bool,
                "test_result": dict,
                "lint_result": dict,
                "ai_analysis": dict | None,
            }
        """
        # Run test suite
        test_result = await self.run_tests()

        # Basic lint pass on files referenced in the diff
        lint_result = await self._run_lint(diff)

        passed = test_result.get("passed", False) and not lint_result.get("errors", [])

        # Optional AI analysis (Haiku) — only when cloud client and diff are present
        ai_analysis: Optional[Dict[str, Any]] = None
        if self._cloud is not None and diff:
            try:
                ctx = self._context_builder.build_validator_context(
                    session=session,
                    diff=diff,
                    test_output=test_result.get("stdout", ""),
                    lint_output=str(lint_result),
                )
                messages = [
                    Message(role=m["role"], content=m["content"])
                    for m in ctx["messages"]
                ]
                api_key = await self._get_api_key()
                response = await self._cloud.complete(
                    provider=CloudProvider.ANTHROPIC,
                    model_id=session.validator_model,
                    api_key=api_key,
                    messages=messages,
                    system=ctx["system_prompt"],
                    max_tokens=2048,
                    temperature=0.0,
                )
                tokens_used = response.tokens_in + response.tokens_out
                session.tokens_used += tokens_used
                ai_analysis = {
                    "content": response.content,
                    "tokens_used": tokens_used,
                }
            except Exception as exc:
                logger.warning(f"ValidatorAgent AI analysis failed: {type(exc).__name__}")

        logger.info(
            f"Validator session check for {session.id!r}: passed={passed}, "
            f"ai_analysis={'yes' if ai_analysis else 'no'}"
        )

        return {
            "passed": passed,
            "test_result": test_result,
            "lint_result": lint_result,
            "ai_analysis": ai_analysis,
        }

    async def check_dependencies(self) -> Dict[str, Any]:
        """Run pip-audit to detect known-vulnerable dependencies.

        Returns:
            {"success": bool, "output": str}
        """
        try:
            result = subprocess.run(
                ["pip-audit", "--format=json", "--progress-spinner=off"],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(PROJECT_ROOT),
            )
            return {
                "success": result.returncode == 0,
                "output": result.stdout[:5000],
            }
        except FileNotFoundError:
            return {"success": True, "output": "pip-audit not available"}
        except subprocess.TimeoutExpired:
            return {"success": False, "output": "pip-audit timed out after 60 seconds"}
        except Exception as exc:
            return {"success": False, "output": f"{type(exc).__name__}"}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _run_lint(self, diff: str) -> Dict[str, Any]:
        """Basic lint check on Python files referenced in the diff.

        Detects wildcard imports and tab indentation in function definitions.
        Intentionally lightweight — not a replacement for a full linter.

        Returns:
            {"errors": list[str], "warnings": list[str], "files_checked": int}
        """
        files: List[str] = re.findall(r'\+\+\+ b/(.+)', diff)
        py_files = [f for f in files if f.endswith(".py")]

        errors: List[str] = []
        warnings: List[str] = []

        for rel_path in py_files[:10]:
            full_path = PROJECT_ROOT / rel_path
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="replace")
                    if "import *" in content:
                        warnings.append(f"{rel_path}: wildcard import")
                    if "\tdef " in content:
                        warnings.append(f"{rel_path}: tab indentation in function def")
                except Exception as exc:
                    logger.warning(
                        f"ValidatorAgent lint read failed for {rel_path}: {type(exc).__name__}"
                    )

        return {
            "errors": errors,
            "warnings": warnings,
            "files_checked": len(py_files),
        }

    async def _get_api_key(self) -> Optional[str]:
        """Retrieve the Anthropic API key from CloudManager."""
        try:
            from hestia.cloud.manager import get_cloud_manager
            manager = await get_cloud_manager()
            return await manager.get_api_key(CloudProvider.ANTHROPIC)
        except Exception as exc:
            logger.warning(
                f"ValidatorAgent: could not retrieve Anthropic API key: {type(exc).__name__}"
            )
            return None
