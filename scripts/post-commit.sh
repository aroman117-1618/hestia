#!/bin/bash
# Post-commit lint + test — run after committing to catch regressions
# Usage: ./scripts/post-commit.sh
#
# Runs Claude in headless mode to:
# 1. Identify files changed in the last commit
# 2. Run pyright on changed Python files
# 3. Run pytest and fix any errors

set -euo pipefail
cd "$(dirname "$0")/.."

claude -p "You are doing a post-commit validation for the Hestia project.

1. Run: git diff --name-only HEAD~1 HEAD
2. For any changed .py files, run pyright on them: source .venv/bin/activate && pyright <files>
3. Run the full test suite: python -m pytest --tb=short -q
4. If there are pyright errors or test failures, fix them and report what you changed.
5. If everything passes, just report the results." \
  --allowedTools "Read,Bash,Edit,Grep"
