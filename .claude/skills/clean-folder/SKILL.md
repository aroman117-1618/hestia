---
name: clean-folder
description: Scan for stray files at repo root (or a given path), propose moves to proper folders, verify no references would break, then execute
user_invocable: true
allowed_tools:
  - Bash
  - Read
  - Edit
  - Grep
  - Glob
---

# Clean Folder Skill

Scan a directory for misplaced files, propose a relocation plan, verify safety, and execute. Default target: repo root.

**Usage:** `/clean-folder` or `/clean-folder path/to/dir`

## Phase 1: Survey

1. List all files at the target path (default: repo root `/Users/andrewlonati/hestia/`).
2. Separate into two groups:
   - **Belongs here** — project-level operational files that should stay (e.g., `CLAUDE.md`, `README.md`, `SPRINT.md`, `SESSION_HANDOFF.md`, `CHEATSHEET.md`, `requirements.txt`, `pytest.ini`, `.gitignore`, `pyproject.toml`).
   - **Candidates for relocation** — docs, reports, analysis files, plans, audits, images, or other files that have a natural home in a subdirectory.
3. Also flag untracked directories that should be `.gitignore`d (runtime state, local exports, OS artifacts).

### Hestia folder conventions

| Content type | Destination |
|-------------|-------------|
| Audit reports | `docs/audits/` |
| Implementation plans | `docs/plans/` |
| Research & discovery | `docs/discoveries/` |
| Reference material (external analysis, exports) | `docs/reference/` |
| Architecture docs | `docs/architecture/` |
| Session retrospectives | `docs/retrospectives/` |
| UI mockups (HTML) | `docs/mockups/` |
| Archived / superseded docs | `docs/archive/` |

## Phase 2: Safety Check

For every file proposed for relocation, verify it is safe to move:

1. **Grep the entire repo** for the filename (without path) to find references.
2. Classify each reference:
   - **Code import / build reference** — BLOCKER. Do not move this file without updating the reference.
   - **Doc cross-reference** — Note it. If the referencing doc moves too, or the reference is informational (e.g., "see also"), it's fine.
   - **Self-reference** (file references itself or a sibling being co-relocated) — Safe.
   - **Handoff / cleanup note** (e.g., "these files need cleanup") — Safe; the move fulfills the note.
3. Check `git ls-files --error-unmatch <file>` to determine tracked vs. untracked status.

**Hard rule:** If any file has a code/build reference that would break, exclude it from the batch and flag it to the user. Never move a file that would break imports, builds, or scripts.

## Phase 3: Present Plan

Show the user a table:

| File | Destination | Tracked? | References found | Safe? |
|------|-------------|----------|-----------------|-------|

Plus a separate table for proposed `.gitignore` additions.

**Wait for user approval before executing.**

## Phase 4: Execute

1. `mv` each file to its destination.
2. For tracked files that moved: `git rm --cached <old_path>` + `git add <new_path>`.
3. Add any new `.gitignore` entries (group by category, add comments).
4. Run `git status --short` to verify the result.
5. List what remains at the target path to confirm it's clean.

Do NOT auto-commit. Let the user decide when to commit (or offer to).

## Edge Cases

- If the target directory doesn't exist, create it.
- If a file with the same name already exists at the destination, flag it and skip (don't overwrite).
- If all files already belong where they are, say so and exit early.
- For non-root paths, adapt the "belongs here" list to context (e.g., `tests/` should have `*.py` and `conftest.py`).
