---
name: bugfix
description: Autonomous test-driven bug fix pipeline — diagnose failures, fix one at a time, verify each fix in isolation
user_invocable: true
argument-hint: "<test name or bug description>"
disable-model-invocation: true
allowed_tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Agent
  - TaskCreate
  - TaskUpdate
  - TaskList
---

# Autonomous Bug Fix Skill

Run an autonomous test-driven bug fix pipeline. Diagnose all failures, then fix them ONE AT A TIME with isolated verification.

## Phase 1: Diagnose

1. Run `source .venv/bin/activate && python -m pytest -x --tb=short --timeout=30 2>&1` to find the first failure
2. Run the full suite with `python -m pytest --tb=line -q --timeout=30` to get a complete failure inventory
3. Create a TaskCreate plan categorizing each failure by root cause
4. Group related failures (e.g., multiple tests failing from the same bug)

## Phase 2: Fix (strict one-at-a-time cycle)

For EACH failure group, follow this exact cycle. Do NOT batch fixes:

1. **Investigate**: Use @hestia-explorer (Agent with subagent_type=hestia-explorer) to read all relevant source files and trace the bug
2. **Fix**: Apply the minimal fix — do not refactor surrounding code
3. **Verify**: Run ONLY the affected test(s) to confirm the fix: `python -m pytest tests/test_X.py::test_name -v --timeout=30`
4. **Regression check**: Run the full suite: `python -m pytest --tb=short -q --timeout=30`
5. **Record**: Mark the TaskCreate item as completed
6. **Next**: Only move to the next failure group after the full suite passes with no new failures

If a fix introduces a NEW failure, revert the fix and investigate further. Do not accumulate tech debt.

## Phase 3: Report

After all failures are resolved (or if you're blocked), summarize:

```
## Bug Fix Results

| Bug | Root Cause | Fix | Files Changed |
|-----|-----------|-----|---------------|
| test_name | Description | What was done | file.py:line |

**Before**: X passing, Y failing
**After**: X passing, 0 failing
**New issues**: None / [describe blockers]
```

## Important Rules

- NEVER skip the isolated verification step
- NEVER batch multiple unrelated fixes before testing
- If stuck on a bug after 2 attempts, flag it for Andrew rather than guessing
- Consider the FULL stack (server state, permissions, simulator) per the Debugging Approach in CLAUDE.md
- Use `sanitize_for_log(e)` in any new error handling, never raw exceptions
