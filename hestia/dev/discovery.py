"""Background work discovery for the Hestia Agentic Dev System.

Periodically checks for: failing tests, new GitHub issues, code quality signals,
dependency vulnerabilities. Creates dev sessions in QUEUED state for the Architect to assess.
"""
from __future__ import annotations

import asyncio
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hestia.logging import get_logger, LogComponent
from hestia.dev.models import DevSessionSource, DevPriority

logger = get_logger()

PROJECT_ROOT = Path.home() / "hestia"


class WorkDiscoveryScheduler:
    """Periodically discovers work opportunities and feeds the dev session queue."""

    def __init__(self, manager: Any, interval_seconds: int = 1800) -> None:
        self._manager = manager
        self._interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Work discovery started (interval: {self._interval}s)", component=LogComponent.DEV)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Work discovery stopped", component=LogComponent.DEV)

    @property
    def is_running(self) -> bool:
        return self._running

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.run_discovery_cycle()
            except Exception as e:
                logger.error(f"Discovery cycle error: {type(e).__name__}", component=LogComponent.DEV)
            await asyncio.sleep(self._interval)

    async def run_discovery_cycle(self) -> List[Dict[str, Any]]:
        """Run all discovery checks. Returns list of findings."""
        findings = []

        # Check for test failures
        test_findings = await self.check_tests()
        findings.extend(test_findings)

        # Check for GitHub issues
        gh_findings = await self.check_github_issues()
        findings.extend(gh_findings)

        # Create sessions for findings
        for finding in findings:
            await self._create_session_from_finding(finding)

        return findings

    async def check_tests(self) -> List[Dict[str, Any]]:
        """Run pytest and report any failures as findings."""
        try:
            result = subprocess.run(
                [str(Path.home() / "hestia" / ".venv" / "bin" / "python"), "-m", "pytest", "tests/", "-q", "--timeout=60", "--tb=line"],
                cwd=str(PROJECT_ROOT),
                capture_output=True, text=True, timeout=180,
            )
            if result.returncode != 0:
                # Extract failure info
                failed_lines = [l for l in result.stdout.split("\n") if "FAILED" in l]
                return [{
                    "type": "test_failure",
                    "title": f"Test failures detected ({len(failed_lines)} tests)",
                    "description": f"pytest returned exit code {result.returncode}.\n\nFailed tests:\n" + "\n".join(failed_lines[:10]),
                    "priority": DevPriority.CRITICAL,
                }]
        except subprocess.TimeoutExpired:
            return [{
                "type": "test_timeout",
                "title": "Test suite timed out",
                "description": "pytest did not complete within 180 seconds",
                "priority": DevPriority.HIGH,
            }]
        except Exception:
            pass
        return []

    async def check_github_issues(self) -> List[Dict[str, Any]]:
        """Check for new GitHub issues assigned to the project."""
        try:
            result = subprocess.run(
                ["gh", "issue", "list", "--state=open", "--assignee=@me", "--json=number,title,body,labels", "--limit=5"],
                cwd=str(PROJECT_ROOT),
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                import json
                issues = json.loads(result.stdout)
                findings = []
                for issue in issues:
                    # Check if we already have a session for this issue
                    existing = await self._manager.list_sessions()
                    source_refs = {s.source_ref for s in existing if s.source_ref}
                    ref = f"#{issue['number']}"
                    if ref not in source_refs:
                        findings.append({
                            "type": "github_issue",
                            "title": issue["title"],
                            "description": issue.get("body", "")[:2000],
                            "priority": DevPriority.HIGH,
                            "source_ref": ref,
                        })
                return findings
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        except Exception:
            pass
        return []

    async def check_code_quality(self) -> List[Dict[str, Any]]:
        """Lightweight code quality scan. Returns findings for weekly summary."""
        findings = []
        # Check for TODO comments with dates
        try:
            result = subprocess.run(
                ["grep", "-rn", "TODO.*20[0-9][0-9]", "hestia/", "--include=*.py"],
                cwd=str(PROJECT_ROOT),
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip():
                todos = result.stdout.strip().split("\n")
                if len(todos) > 5:
                    findings.append({
                        "type": "code_quality",
                        "title": f"Dated TODOs found ({len(todos)} items)",
                        "description": "TODOs with dates:\n" + "\n".join(todos[:10]),
                        "priority": DevPriority.BACKGROUND,
                    })
        except Exception:
            pass
        return findings

    async def _create_session_from_finding(self, finding: Dict[str, Any]) -> None:
        """Create a QUEUED dev session from a discovery finding."""
        source = DevSessionSource.SELF_DISCOVERED
        if finding.get("type") == "github_issue":
            source = DevSessionSource.GITHUB

        await self._manager.create_session(
            title=finding["title"],
            description=finding.get("description", ""),
            source=source,
            source_ref=finding.get("source_ref"),
            priority=finding.get("priority", DevPriority.NORMAL),
        )
        logger.info(f"Created session from discovery: {finding['title']}", component=LogComponent.DEV)
