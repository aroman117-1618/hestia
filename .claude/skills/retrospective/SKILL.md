---
name: retrospective
description: Session learning audit — analyze engagement friction, debugging loops, and optimization opportunities
user_invocable: true
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Task
  - TodoWrite
---

# Retrospective Skill

Run a deep learning audit on the current session. This isn't just "what did we do" — it's a critical analysis of HOW we worked, where we got stuck, and what should change to prevent the same friction next time.

**Purpose:** Optimize the development workflow by turning session experience into permanent improvements to CLAUDE.md, skills, agents, and documentation.

## Phase 1: Session Inventory

1. Review the full conversation history for this session
2. Catalog:
   - Tasks attempted (with outcomes: completed / partial / failed / abandoned)
   - Decisions made (with reasoning quality: well-informed / rushed / wrong)
   - Questions asked by Andrew (indicates missing context or unclear docs)
   - Questions asked by Claude (indicates ambiguity in requirements or config)
3. Create a TodoWrite plan tracking audit sections

## Phase 2: Learning Audit

### Key Learnings
- What new information emerged this session?
- What assumptions were validated or invalidated?
- What patterns worked well and should be repeated?
- What approaches failed and should be avoided?

### Engagement Friction Points
Identify every point where the conversation stalled, went in circles, or required course correction:
- **Clarification loops** — where did Andrew have to re-explain something?
- **Wrong assumptions** — where did Claude go down the wrong path?
- **Missing context** — what information was needed but not in CLAUDE.md or skills?
- **Tool/environment issues** — what broke, what was slow, what was confusing?

For each friction point: what caused it, and what documentation or config change would prevent it?

## Phase 3: Debugging & Troubleshooting Loop Analysis

Identify any bug-fixing or troubleshooting sequences in the session:
- How long did each loop take (in conversation turns)?
- What was the root cause vs. what was initially investigated?
- Was the debugging approach efficient, or did it spiral?
- **For each loop:** What would have shortened it? (better error messages, more logging, clearer docs, different diagnostic approach)

Rate each debugging loop:
- **Efficient** — found root cause quickly, fixed cleanly
- **Acceptable** — some exploration needed, but reasonable
- **Spiral** — went in circles, investigated wrong layers, wasted turns

## Phase 4: Deep-Dive Audit Reviews

If any audits were run this session (/discovery, /plan-audit, /codebase-audit), review their outputs:
- Were the findings accurate?
- Were any recommendations implemented?
- Did anything get flagged that was later proven wrong?
- Are there follow-up items that should be tracked?

## Phase 5: Optimization Recommendations

For each issue identified, propose a concrete fix in one of these categories:

### CLAUDE.md Updates
- What should be added, changed, or removed?
- Be specific — write the exact text to add

### Skills/Agents Updates
- Which skill or agent files need changes?
- What instructions were missing or misleading?

### Documentation Updates
- Which docs drifted from reality?
- What new documentation is needed?

### Workflow Improvements
- Are there new patterns that should become skills?
- Are there repetitive tasks that should be automated?
- Should hook scripts be added or modified?

### SPRINT.md Updates
- Update phase markers for any topics worked on
- Add new topics discovered during the session

## Phase 6: Session Metrics

Collect quantitative data:
- Files changed: `git diff --stat` (or from conversation history)
- Tests added or fixed
- Decisions made (list them)
- Skills/agents invoked (and their effectiveness)
- Approximate conversation turns spent on each task
- Ratio: productive turns vs. friction/debugging turns

## Output Format

Save the retrospective to `docs/retrospectives/retro-[date].md` and present it:

```markdown
# Session Retrospective: [Date]

## Session Summary
[2-3 sentence overview of what this session accomplished]

## Key Learnings
1. [Learning with context]
2. [Learning with context]
...

## Engagement Friction Points
| Friction | Cause | Turns Wasted | Prevention |
|----------|-------|-------------|------------|
| [description] | [root cause] | ~N | [specific fix] |

## Debugging Loops
| Issue | Turns | Rating | Root Cause | Faster Path |
|-------|-------|--------|-----------|-------------|
| [bug] | N | Efficient/Acceptable/Spiral | [cause] | [what to do next time] |

## Audit Follow-Ups
| Audit | Finding | Status | Next Action |
|-------|---------|--------|-------------|
| [which audit] | [finding] | Implemented/Pending/Deferred | [action] |

## Optimization Recommendations

### CLAUDE.md Changes
| Section | Change | Rationale |
|---------|--------|-----------|
| [section] | [exact change] | [why] |

### Skills/Agents Changes
| File | Change | Rationale |
|------|--------|-----------|
| [file] | [change] | [why] |

### Documentation Changes
| Doc | Change | Rationale |
|-----|--------|-----------|
| [doc] | [change] | [why] |

### New Automation Opportunities
| What | How | Effort |
|------|-----|--------|
| [task] | [approach] | [estimate] |

## Session Metrics
- Tasks completed: N
- Files changed: N
- Tests: +N added, N fixed
- Decisions made: N
- Productive turns: ~N
- Friction turns: ~N
- Efficiency ratio: N%
```

The goal is not to document the session — it's to make the NEXT session better. Every recommendation should be specific enough to implement immediately.
