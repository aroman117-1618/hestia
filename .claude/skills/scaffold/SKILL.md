---
name: scaffold
description: Parallel multi-agent feature scaffold — decompose a feature into vertical slices and build them with sub-agents
user_invocable: true
argument-hint: "<feature description>"
disable-model-invocation: true
allowed_tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Task
  - TaskCreate
  - TaskUpdate
  - TaskList
---

# Parallel Feature Scaffold Skill

Decompose a new feature into independent vertical slices and build them using parallel sub-agents, then integrate and test.

The user should provide a feature description when invoking this skill. If not provided, ask for one.

## Phase 1: Research & Design

1. Read `CLAUDE.md` to understand project conventions (manager pattern, logging, error handling, etc.)
2. Use @hestia-explorer (Task with subagent_type=hestia-explorer) to find similar existing modules for reference
3. Identify the vertical slices needed. For a typical Hestia module, this is:
   - **Models**: `models.py` — Pydantic/dataclass definitions
   - **Database**: `database.py` — SQLite/ChromaDB persistence
   - **Manager**: `manager.py` — Business logic singleton with `get_X_manager()` factory
   - **Routes**: `routes/X.py` — FastAPI endpoints with Pydantic schemas
   - **Tests**: `tests/test_X.py` — pytest suite
   - **iOS** (if applicable): Model, ViewModel, View files

4. Define **interface contracts** first — the shared types, function signatures, and data shapes that all slices depend on. Write these to a scratch file or directly to `models.py`.

5. Create a TaskCreate plan with one item per slice.

## Phase 2: Parallel Build

Launch parallel Task sub-agents for independent slices:

- **Agent 1** (hestia-explorer or general-purpose): Build models + database layer with unit tests
- **Agent 2** (general-purpose): Build manager layer with unit tests
- **Agent 3** (general-purpose): Build route layer with integration tests
- **Agent 4** (general-purpose): Build iOS files if applicable

Each agent MUST:
- Follow Hestia conventions from CLAUDE.md (type hints, async/await, get_logger(), sanitize_for_log)
- Import from the shared interface contracts
- Write tests that pass independently
- Use the correct `LogComponent` for the new module

Slices that depend on each other (e.g., routes depend on manager) should be built sequentially, not in parallel.

## Phase 3: Integrate & Test

1. Run the full test suite: `python -m pytest --tb=short -q`
2. Fix any integration issues (import errors, type mismatches, missing dependencies)
3. Run @hestia-reviewer (Task with subagent_type=hestia-reviewer) on all new files
4. Verify the new module checklist from CLAUDE.md:
   - [ ] `LogComponent` enum updated
   - [ ] `auto-test.sh` mapping added
   - [ ] `validate-security-edit.sh` updated if credentials involved
   - [ ] Sub-agent definitions updated if needed
   - [ ] CLAUDE.md project structure updated

## Phase 4: Report

```
## Feature Scaffold Results

**Feature**: [name]
**Files created**: [count]

| Slice | Files | Tests | Status |
|-------|-------|-------|--------|
| Models | models.py | 5 tests | Passing |
| Database | database.py | 8 tests | Passing |
| Manager | manager.py | 12 tests | Passing |
| Routes | routes/X.py | 10 tests | Passing |
| iOS | [files] | N/A | Built |

**Total tests**: X new, all passing
**Checklist**: All items complete
```
