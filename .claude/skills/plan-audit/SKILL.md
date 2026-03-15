---
name: plan-audit
description: Sprint/plan SWOT analysis with bottom-up review chain and executive critiques — validate before you build
user_invocable: true
argument-hint: "<plan to audit or 'current sprint'>"
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

# Plan Audit Skill

Run a rigorous, multi-perspective audit of a proposed plan or sprint before execution begins. This is the gate between planning and building — catch the problems here, not in production.

The review chain is bottom-up: front-line engineers first, then leads, then executives. Each layer builds on findings from the previous.

The user should provide the plan to audit (or point to relevant files/context). If not provided, read `SPRINT.md`, recent conversation history, and any plan documents in `docs/plans/`.

## Phase 1: Consume the Plan

1. Read all plan context — CLAUDE.md, SPRINT.md, the plan itself, any referenced discovery reports
2. Use @hestia-explorer (Agent with subagent_type=hestia-explorer) to validate technical assumptions in the plan
3. Create a TaskCreate plan to track the audit phases

## Phase 2: Scale Assumptions Check

Assess the plan's assumptions about scale:

- **Current state**: Single user (Andrew), single device, personal assistant
- **Near-term**: Family scale (2-5 users, multiple devices per user)
- **Medium-term**: Community scale (small group, shared resources)
- **Long-term**: Multi-tenant (if ever relevant)

For each scale level:
- Does the plan work? What breaks?
- What would need to change to support it?
- Is the plan building toward scale or creating technical debt?

Flag anything that assumes single-user and would be expensive to change later.

## Phase 3: Front-Line Engineering Review

Think like the developer who will implement this:

- **Feasibility**: Can this actually be built as described? Are there hidden prerequisites?
- **Complexity**: Is the estimated effort realistic? What's underestimated?
- **Hidden prerequisites**: What needs to exist before this can start? (migrations, dependencies, config changes)
- **Testing strategy**: How will this be tested? Are the test scenarios comprehensive? What's hard to test?
- **Developer experience**: Will this be pleasant to implement, or will it fight the existing codebase?

## Phase 4: Backend Engineering Lead Review

Think like the tech lead reviewing the architecture:

- **Architecture fit**: Does this follow Hestia's layer boundaries and manager pattern?
- **API design**: Are endpoints well-designed? Consistent naming? Proper HTTP semantics?
- **Data model**: Is the data model right? Will it need migration later?
- **Multi-tenancy readiness**: Does the plan use `user_id` scoping? Device-aware?
- **Integration points**: What existing code will this touch? What will break?
- **Dependency risk**: Any new dependencies? Version conflicts? License issues?

## Phase 5: Product Management Review

Think like the product manager:

- **User value**: Does this deliver real value, or is it infrastructure for infrastructure's sake?
- **Edge cases**: What happens with empty data, first-time users, offline scenarios?
- **Multi-device**: Does the feature work across iOS and macOS? Are there platform divergences?
- **Opportunity cost**: What are we NOT building while we build this?
- **Scope**: Is this the right size? Too big (should be split)? Too small (should be combined)?

## Phase 6: Design/UX Review (if UI involved)

Skip this phase if the plan has no UI component. Otherwise:

- **Design system compliance**: Does the plan use HestiaColors, HestiaTypography, HestiaSpacing?
- **Interaction model**: Are user flows clear? Any dead ends or confusing states?
- **Platform divergences**: Does iOS behavior match macOS behavior where appropriate?
- **Accessibility**: Is the plan accessible? VoiceOver, Dynamic Type?
- **Empty states**: What does the user see before there's data?

## Phase 7: Infrastructure/SRE Review

Think like the ops engineer:

- **Deployment impact**: Does this require server restart? Database migration? Config change?
- **New dependencies**: Any new Python packages, Swift packages, system libraries?
- **Monitoring**: How will we know if this breaks in production? Logging? Health checks?
- **Rollback strategy**: If this fails after deploy, can we revert cleanly?
- **Resource implications**: Memory, CPU, storage impact on Mac Mini M1 (16GB)?

## Phase 8: Executive Panel

Three executives render verdicts based on all previous findings:

### CISO Review
- Does this change the attack surface?
- Any new credential handling, data exposure, or communication paths?
- Are error handling and sanitization patterns maintained?
- **Verdict:** Acceptable / Needs Remediation / Reject

### CTO Review
- Does this fit the existing architecture?
- What technical debt does this introduce or resolve?
- Are there simpler alternatives?
- **Verdict:** Acceptable / Needs Remediation / Reject

### CPO Review
- Does this deliver the right user value at the right scope?
- Is the priority ordering correct?
- **Verdict:** Acceptable / Needs Remediation / Reject

## Phase 9: Final Critiques

Three targeted stress-tests:

1. **Most likely failure**: What single thing is most likely to go wrong? What's the mitigation?
2. **Critical assumption**: What assumption, if wrong, would invalidate the entire plan? How do we validate it early?
3. **Half-time cut list**: If we had half the time, what would we cut? (reveals true priorities)

## Output Format

Save the audit to `docs/plans/[plan-name]-audit-[date].md` and present it:

```markdown
# Plan Audit: [Plan Name]
**Date:** [date]
**Verdict:** APPROVE | APPROVE WITH CONDITIONS | REJECT

## Plan Summary
[2-3 sentence summary of what's being audited]

## Scale Assessment
| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes/No | ... | ... |
| Family | Yes/No | ... | ... |
| Community | Yes/No | ... | ... |

## Front-Line Engineering
- **Feasibility:** [assessment]
- **Hidden prerequisites:** [list]
- **Testing gaps:** [what's hard to test]

## Architecture Review
- **Fit:** [assessment]
- **Data model:** [assessment]
- **Integration risk:** [assessment]

## Product Review
- **User value:** [assessment]
- **Scope:** [right-sized / too big / too small]
- **Opportunity cost:** [what we're not building]

## UX Review (if applicable)
[Design system compliance, interaction model, platform parity]

## Infrastructure Review
- **Deployment impact:** [assessment]
- **Rollback strategy:** [defined / missing]
- **Resource impact:** [acceptable / concerning]

## Executive Verdicts
- **CISO:** [verdict] — [one-line summary]
- **CTO:** [verdict] — [one-line summary]
- **CPO:** [verdict] — [one-line summary]

## Final Critiques
1. **Most likely failure:** [what and mitigation]
2. **Critical assumption:** [what and validation approach]
3. **Half-time cut list:** [what gets cut]

## Conditions for Approval
[If APPROVE WITH CONDITIONS — list the specific conditions]
```

Be decisive. The plan either passes or it doesn't. Don't hedge with "it depends" — state what it depends ON and recommend accordingly.
