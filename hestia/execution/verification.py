"""Verification layer for self-modification safety.

When Hestia modifies her own source code, this layer:
1. Detects self-modification (edits under ~/hestia/hestia/ or ~/hestia/tests/)
2. Finds the matching test file for the edited module
3. Runs tests before and after the edit
4. Generates a diff for human review
"""

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from hestia.logging import get_logger

logger = get_logger()

# Paths that constitute "self-modification"
SELF_PATHS = [
    "hestia/hestia/",
    "hestia/tests/",
    "hestia/hestia-cli/",
    "hestia/scripts/",
]

# Test file mapping (module path → test file)
TEST_FILE_MAP = {
    "hestia/memory/": "tests/test_memory.py",
    "hestia/research/": "tests/test_research.py",
    "hestia/orchestration/": "tests/test_orchestration.py",
    "hestia/inference/": "tests/test_inference.py",
    "hestia/council/": "tests/test_council.py",
    "hestia/execution/": "tests/test_tools.py",
    "hestia/api/routes/": "tests/test_routes.py",
    "hestia/apple/": "tests/test_apple.py",
    "hestia/health/": "tests/test_health_data.py",
    "hestia/wiki/": "tests/test_wiki.py",
    "hestia/explorer/": "tests/test_explorer.py",
    "hestia/newsfeed/": "tests/test_newsfeed.py",
    "hestia/cloud/": "tests/test_cloud.py",
    "hestia/voice/": "tests/test_voice_routes.py",
    "hestia/investigate/": "tests/test_investigate.py",
    "hestia/files/": "tests/test_files.py",
    "hestia/inbox/": "tests/test_inbox.py",
    "hestia/outcomes/": "tests/test_outcomes.py",
}

HESTIA_ROOT = str(Path("~/hestia").expanduser())


@dataclass
class VerificationResult:
    """Result of a self-modification verification."""
    is_self_modification: bool = False
    test_file: Optional[str] = None
    pre_test_passed: Optional[bool] = None
    post_test_passed: Optional[bool] = None
    diff: str = ""
    test_output: str = ""
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "is_self_modification": self.is_self_modification,
            "test_file": self.test_file,
            "pre_test_passed": self.pre_test_passed,
            "post_test_passed": self.post_test_passed,
            "diff_length": len(self.diff),
            "errors": self.errors,
        }


def is_self_modification(file_path: str) -> bool:
    """Check whether an edit targets Hestia's own source code."""
    resolved = str(Path(file_path).expanduser().resolve())
    for self_path in SELF_PATHS:
        # Check if the resolved path contains the self-modification marker
        if self_path.rstrip("/") in resolved:
            return True
    return False


def find_test_file(source_path: str) -> Optional[str]:
    """Find the matching test file for a source module.

    Args:
        source_path: Relative path like 'hestia/memory/manager.py'

    Returns:
        Test file path like 'tests/test_memory.py', or None if no match.
    """
    for module_prefix, test_file in TEST_FILE_MAP.items():
        if module_prefix in source_path:
            full_path = os.path.join(HESTIA_ROOT, test_file)
            if os.path.isfile(full_path):
                return test_file
    return None


def run_test_file(test_path: str, timeout: int = 60) -> tuple:
    """Run a test file and return (passed: bool, output: str)."""
    full_path = os.path.join(HESTIA_ROOT, test_path)
    if not os.path.isfile(full_path):
        return False, f"Test file not found: {test_path}"

    try:
        result = subprocess.run(
            ["python", "-m", "pytest", full_path, "-q", "--timeout=30", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=HESTIA_ROOT,
        )
        passed = result.returncode == 0
        output = result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout
        if result.stderr and not passed:
            output += f"\nSTDERR: {result.stderr[-500:]}"
        return passed, output
    except subprocess.TimeoutExpired:
        return False, f"Test timed out after {timeout}s"
    except Exception as e:
        return False, f"Test execution failed: {type(e).__name__}"


async def verify_self_modification(
    file_path: str,
) -> VerificationResult:
    """Run verification checks for a self-modification.

    1. Detect if it's a self-modification
    2. Find matching test file
    3. Run tests (post-edit only — pre-edit state is already committed)
    4. Generate git diff
    """
    result = VerificationResult()
    result.is_self_modification = is_self_modification(file_path)

    if not result.is_self_modification:
        return result

    # Find matching test file
    result.test_file = find_test_file(file_path)

    if result.test_file:
        # Run tests on current state
        passed, output = run_test_file(result.test_file)
        result.post_test_passed = passed
        result.test_output = output

        if not passed:
            result.errors.append(f"Tests failed after edit: {result.test_file}")
    else:
        result.errors.append(f"No matching test file found for {file_path}")

    # Get git diff for the file
    try:
        diff_result = subprocess.run(
            ["git", "-C", HESTIA_ROOT, "diff", "--", file_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        result.diff = diff_result.stdout[:5000]
    except Exception:
        result.diff = "(diff unavailable)"

    return result
