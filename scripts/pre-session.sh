#!/bin/bash
# Pre-session health check — run before starting a Claude Code session
# Usage: ./scripts/pre-session.sh
#
# Runs Claude in headless mode to:
# 1. Check what was last worked on (git log + docs)
# 2. Verify the test suite passes
# 3. Summarize what to tackle next

set -euo pipefail
cd "$(dirname "$0")/.."

claude -p "You are doing a pre-session health check for the Hestia project.

1. Read CLAUDE.md — note the Current Status and Context Continuity sections
2. Run: git log --oneline -10
3. Run: lsof -i :8443 | grep LISTEN || echo 'No server running'
4. Run: source .venv/bin/activate && python -m pytest --tb=short -q
5. Check for any uncommitted changes: git status --short

Summarize in this format:
- **Last active**: What was the most recent work (from git log)
- **Server**: Running or not
- **Tests**: X passing, Y failing (list any failures)
- **Uncommitted changes**: Yes/no (list files if yes)
- **Next up**: What should be tackled next (from CLAUDE.md roadmap)" \
  --allowedTools "Read,Bash,Grep"
