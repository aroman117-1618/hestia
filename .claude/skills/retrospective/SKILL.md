---
name: retrospective
description: Session learning audit — analyze engagement friction, debugging loops, and optimization opportunities
user_invocable: true
context: fork
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Task
  - TaskCreate
  - TaskUpdate
  - TaskList
---

# Retrospective Skill

Run a deep process optimization audit on the current session. This isn't about documenting what happened (that's `/handoff`) — it's about making the NEXT session better by identifying friction, missed delegation opportunities, and configuration gaps.

**Purpose:** Turn session experience into permanent improvements to skills, agents, hooks, and documentation.

## Phase 1: Configuration Gap Analysis

Analyze the session for problems that better configuration would have prevented:

1. Review the conversation history for:
   - Errors that required manual debugging
   - Information that was searched for but should have been in CLAUDE.md or agent definitions
   - Tasks that were done manually but could have been automated with hooks or skills
   - Repetitive patterns that should become skills

2. For each gap identified:
   - **What happened**: The specific friction point
   - **Root cause**: Why existing config didn't prevent it
   - **Fix**: The exact config change (file path, content) that would prevent it next time

## Phase 2: First-Pass Success Analysis

Measure development efficiency:

1. Count tasks attempted and their outcomes:
   - **First-pass success**: Completed correctly on first attempt (no rework)
   - **Rework needed**: Required correction after initial implementation
   - **Failed/abandoned**: Could not be completed

2. For each rework case:
   - What caused the rework? (wrong assumption, missing context, unclear requirements, tool failure)
   - What would have enabled first-pass success? (better planning, reading more code first, asking Andrew)

3. Calculate **first-pass success rate**: `first_pass / total_attempted * 100`

4. Identify the top 3 blockers to first-pass success and propose mitigations.

## Phase 3: Agent Orchestration Review

Evaluate how effectively sub-agents were used:

1. **Delegation audit**:
   - Were @hestia-explorer, @hestia-tester, @hestia-reviewer used when they should have been?
   - Were there missed delegation opportunities? (e.g., manual grep when explorer could have searched)
   - Were agents used for the wrong task? (e.g., explorer for a job that needed tester)

2. **Parallelism audit**:
   - Were independent tasks run in parallel where possible?
   - Were there sequential bottlenecks that could have been parallelized?

3. **Agent effectiveness**:
   - Did agents return useful results, or were their outputs ignored/repeated?
   - Were agent prompts specific enough, or did they waste turns on unfocused exploration?

## Phase 4: Audit Follow-Ups

If any strategic skills were run this session (/discovery, /plan-audit, /codebase-audit):

1. Were the findings accurate?
2. Were recommendations implemented?
3. Were any findings later proven wrong?
4. Are there unresolved follow-up items that need tracking?

## Phase 5: Optimization Recommendations

For each issue identified, propose a concrete fix in one of these categories:

### CLAUDE.md Updates
- What should be added, changed, or removed?
- Write the exact text to add

### Skills/Agents Updates
- Which files need changes?
- What instructions were missing or misleading?
- Should any new skills or hooks be created?

### Hook/Script Changes
- Should new hooks be added?
- Should existing scripts be modified?
- Are there events that should trigger automation?

### Workflow Improvements
- Are there new patterns that should become skills?
- Are there repetitive tasks that should be automated?
- Should the 4-phase workflow be adjusted for certain task types?

## Output Format

Save the retrospective to `docs/retrospectives/retro-[date].md` and present it:

```markdown
# Process Retrospective: [Date]

## Configuration Gaps
| Gap | Friction Caused | Fix (file + change) |
|-----|----------------|---------------------|
| [description] | [what went wrong] | [exact fix] |

## First-Pass Success
- **Rate**: N% (X/Y tasks succeeded first try)
- **Top blockers**:
  1. [blocker] — [mitigation]
  2. [blocker] — [mitigation]
  3. [blocker] — [mitigation]

## Agent Orchestration
| Observation | Category | Recommendation |
|-------------|----------|----------------|
| [what happened] | Missed delegation / Wrong agent / Good use | [fix] |

## Audit Follow-Ups
| Audit | Finding | Status | Next Action |
|-------|---------|--------|-------------|
| [which] | [finding] | Implemented/Pending/Deferred | [action] |

## Optimization Recommendations

### Config Changes (implement now)
| File | Change | Rationale |
|------|--------|-----------|
| [file] | [change] | [why] |

### Workflow Changes (discuss with Andrew)
| What | How | Expected Impact |
|------|-----|-----------------|
| [change] | [approach] | [benefit] |
```

The goal is NOT to document the session — it's to make the NEXT session measurably better. Every recommendation must be specific enough to implement immediately.
