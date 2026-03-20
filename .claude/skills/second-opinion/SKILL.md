---
name: second-opinion
description: Cross-model plan validation — 9-phase internal audit + Gemini CLI external critique, replaces /plan-audit
user_invocable: true
argument-hint: "<plan to audit, file path, or 'current sprint'>"
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Write
  - Agent
  - TaskCreate
  - TaskUpdate
  - TaskList
---

# /second-opinion — Cross-Model Plan Validation

Run a rigorous, multi-perspective audit of a proposed plan or sprint, then cross-validate with Gemini for an independent second opinion. This is the gate between planning and building.

**Supersedes /plan-audit** — all 9 internal phases carried over, plus Phase 10 (Gemini cross-model validation).

The user should provide the plan to audit (or point to relevant files/context). If not provided, read `SPRINT.md`, recent conversation history, and any plan documents in `docs/plans/`.

**Mode detection:** If Andrew says "just make it work", "operate mode", or passes `--mode operate`, compress the workflow: combine Phases 2-7 into a rapid risk assessment, run Phases 8-8.6 as a single pass, skip Phase 9 (Devil's Advocate), and deliver a concise verdict without interactive gates. Default is **Collaborate mode** (full multi-phase review with explanations and approval gates).

---

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

- **Design system compliance**: Does the plan use HestiaColors, HestiaTypography, HestiaSpacing? Grep for `Color(hex:)` literals in View files — these should be design tokens.
- **Interaction model**: Are user flows clear? Any dead ends or confusing states?
- **Platform divergences**: Does iOS behavior match macOS behavior where appropriate?
- **Accessibility**: Is the plan accessible? VoiceOver, Dynamic Type?
- **Empty states**: What does the user see before there's data?

### 6.1 Wiring Verification (CRITICAL — do not skip)
Past audits revealed that plans can claim features are "built" when they're actually facade-only. Run these checks on any UI the plan touches or claims is already done:

1. **Button audit**: For every button in relevant views, verify the closure body isn't `{ }` or `{ // TODO }`. Use: `grep -n "Button {}" <file>` and `grep -n "// TODO" <file>`
2. **Data binding check**: For every displayed value, trace it back to the ViewModel. Is it bound to `@Published` state from an API call, or hardcoded? Key pattern: progress rings, status badges, and timestamps are frequent offenders.
3. **Error path validation**: What happens when the API call fails? Is `errorMessage` set and displayed, or caught-and-swallowed with `#if DEBUG print()`?
4. **Shared component cross-check**: Before recommending "build X", check if it already exists in `Shared/Views/` or `Shared/ViewModels/`. Previous audits found full components (OrderInlineForm, BriefingCard, MemoryWidget) already built but unused by the target platform.
5. **Endpoint coverage**: For the feature area, list backend endpoints and verify the client calls them. Flag uncalled endpoints that should be wired.

See `docs/discoveries/ui-wiring-audit-methodology-2026-03-19.md` for the full 4-layer methodology.

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

## Phase 8.4: CFO Review

Think like the CFO:
- **Build cost**: Engineer-hours and cloud spend to implement this plan
- **Maintenance cost**: Ongoing compute, monitoring, support burden
- **ROI**: Time saved, capability gained, risk reduced — is this worth it?
- **Resource allocation**: Are we putting resources on the highest-value work?
- **Opportunity cost**: What's the dollar-equivalent cost of NOT building something else?
- **Verdict:** Acceptable / Needs Remediation / Reject

## Phase 8.5: Legal Review

Think like the Legal counsel:
- **Data handling**: Does this touch PII? GDPR/CCPA implications?
- **Third-party dependencies**: License compatibility (GPL contamination)? Vendor lock-in risk?
- **API usage**: Terms of service compliance for any external APIs (Coinbase, Ollama, cloud providers)?
- **IP exposure**: Any open-source risk for proprietary logic?
- **Regulatory**: Industry-specific compliance concerns (crypto regulations for trading module)?
- **Verdict:** Acceptable / Needs Remediation / Reject

## Phase 8.6: Key Principles Filter

Rate the plan against Hestia's core principles (1-5 each):
- **Security**: Does this reduce (or at least not increase) the attack surface?
- **Empathy**: Does this genuinely serve the user well?
- **Simplicity**: Is this the simplest approach that works?
- **Joy**: Will building and using this bring satisfaction?

If any principle scores 1-2, flag it as a concern in the executive summary.

## Phase 9: Sustained Devil's Advocate

This is not a checklist — it's a sustained adversarial argument against the plan. Build the strongest possible case for NOT doing this plan.

**Before starting Phase 9**, dispatch @hestia-critic (Agent with subagent_type=hestia-critic) with the plan summary and top findings from Phases 1-8. The critic agent runs independently and returns adversarial strategic critique. Incorporate its findings into sections 9.1-9.4 below — use its strongest arguments, don't duplicate weaker ones.

### 9.1 The Counter-Plan

Construct a coherent alternative approach that achieves the same goals differently:
- What would you build instead?
- Why is the alternative better on the dimensions that matter most?
- What does the alternative sacrifice? Is that sacrifice acceptable?

If you can't build a credible counter-plan, the plan is probably strong. Say so.

### 9.2 Future Regret Analysis

Project forward and identify what the team will regret:
- **3 months**: What daily friction will this plan create?
- **6 months**: What will be expensive to change because of choices made here?
- **12 months**: Will this approach survive the next era of the roadmap? (Check `SPRINT.md` and roadmap context)

### 9.3 The Uncomfortable Questions

Ask the questions nobody wants to hear:
- **"Do we actually need this?"** — Is the problem real, or are we building for a hypothetical?
- **"Are we building this because it's valuable, or because it's interesting?"** — Distinguish engineering curiosity from user value
- **"What's the cost of doing nothing?"** — Sometimes the best plan is no plan
- **"Who benefits?"** — If the answer is only "future us, maybe" — that's a warning sign

### 9.4 Final Stress Tests

Three targeted critiques:

1. **Most likely failure**: What single thing is most likely to go wrong? What's the mitigation?
2. **Critical assumption**: What assumption, if wrong, would invalidate the entire plan? How do we validate it early?
3. **Half-time cut list**: If we had half the time, what would we cut? (reveals true priorities)

---

## Phase 10: Cross-Model Validation (Gemini)

This phase sends the plan and all internal findings to Gemini for an independent second opinion. The goal is to surface blind spots that Claude's reasoning may share systematically.

### 10.1 Prompt Construction

Build a structured prompt containing:
1. The plan summary (2-3 paragraphs)
2. Key architectural decisions and their rationale
3. The internal audit's top 5 findings (risks, gaps, concerns)
4. Specific questions where a second opinion would be most valuable
5. The codebase context that matters (stack, constraints, patterns)

**Prompt template:**

```
You are a senior software architect reviewing a development plan for a second opinion.

## Project Context
[Stack: Python/FastAPI backend, SwiftUI iOS/macOS, SQLite + ChromaDB, local Ollama inference]
[Scale: Single-user personal AI assistant on Mac Mini M1]

## Plan Under Review
[Plan summary — what is being built, why, estimated effort]

## Key Decisions
[Numbered list of architectural decisions with rationale]

## Internal Audit Findings
[Top 5 concerns from Phases 1-9]

## Specific Questions
[2-3 targeted questions where a fresh perspective would be most valuable]

Please provide:
1. Your independent assessment of the plan's strengths and weaknesses
2. Any risks or blind spots the internal audit missed
3. Alternative approaches worth considering
4. Your verdict: APPROVE, APPROVE WITH CONDITIONS, or REJECT
```

### 10.2 Gemini Dispatch

Shell out to the Gemini CLI and capture the response:

```bash
# Write prompt to temp file (avoids shell escaping issues)
PROMPT_FILE=$(mktemp /tmp/gemini-prompt-XXXXX.md)
# [prompt content written to $PROMPT_FILE]

# Dispatch to Gemini — non-interactive mode with prompt from file
RESPONSE=$(cat "$PROMPT_FILE" | gemini --model gemini-2.5-pro 2>/dev/null)

# Clean up
rm -f "$PROMPT_FILE"
```

**If Gemini CLI fails** (not authenticated, network error, rate limit):
- Log the error
- Skip Phase 10 gracefully — the internal audit (Phases 1-9) is still valid
- Note in the output: "Cross-model validation unavailable — Gemini CLI returned [error]"

**If Gemini returns empty or garbled response:**
- Retry once with a shorter prompt (just plan summary + top 3 questions)
- If still fails, skip with a note

### 10.3 Response Parsing

Extract from Gemini's response:
- **Agreements**: Where Gemini aligns with the internal audit
- **Disagreements**: Where Gemini has a different assessment
- **Novel insights**: Risks or suggestions NOT present in the internal audit
- **Gemini's verdict**: Their overall recommendation

### 10.4 Reconciliation Report

Produce a side-by-side comparison:

```markdown
## Cross-Model Reconciliation

### Where Both Models Agree
[Bullet list of shared findings — these are high-confidence signals]

### Where Models Diverge
| Topic | Claude's View | Gemini's View | Resolution |
|-------|--------------|---------------|------------|
| ... | ... | ... | [which is right and why] |

### Novel Insights from Gemini
[Findings that Claude's audit did not surface]

### Synthesis
[2-3 paragraph unified assessment incorporating both perspectives]
```

### 10.5 Final Verdict

Render a unified verdict that weighs both models' assessments:
- If both agree: high confidence in that direction
- If they disagree: examine the disagreement, explain which perspective is more applicable to Hestia's context, and recommend accordingly
- The final verdict is always Claude's to make — Gemini informs but doesn't override

---

## Output Format

Save the audit to `docs/plans/[plan-name]-second-opinion-[date].md` and present it:

```markdown
# Second Opinion: [Plan Name]
**Date:** [date]
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
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
- **CFO:** [verdict] — [one-line summary]
- **Legal:** [verdict] — [one-line summary]

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | X | ... |
| Empathy | X | ... |
| Simplicity | X | ... |
| Joy | X | ... |

## Final Critiques
1. **Most likely failure:** [what and mitigation]
2. **Critical assumption:** [what and validation approach]
3. **Half-time cut list:** [what gets cut]

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment
[Summary of Gemini's response]

### Where Both Models Agree
[High-confidence shared findings]

### Where Models Diverge
| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| ... | ... | ... | ... |

### Novel Insights from Gemini
[Findings not present in internal audit]

### Reconciliation
[Unified assessment incorporating both perspectives]

## Conditions for Approval
[If APPROVE WITH CONDITIONS — list the specific conditions]
```

Be decisive. The plan either passes or it doesn't. Don't hedge with "it depends" — state what it depends ON and recommend accordingly.

## Phase 11: Roadmap Sync

After delivering the verdict, sync with the GitHub Project board.

**If verdict is APPROVE or APPROVE WITH CONDITIONS:**

1. Check if a GitHub issue already exists for this plan: `scripts/roadmap-sync.sh list`
2. If **no issue exists**, proactively ask: "This plan is approved. Want me to create a GitHub issue and add it to the board?"
3. When creating:
   ```bash
   scripts/roadmap-sync.sh issue "<Sprint/WS title>" \
     --labels "sprint-XX,backend" \
     --hours <estimate from plan> \
     --plan "docs/plans/<plan-file>.md"
   ```
4. Adapt labels based on plan content (add `macos`, `ios`, `trading`, etc. as appropriate).

**If verdict is REJECT:**
- If an issue already exists on the board for this plan, flag it: "This plan was rejected — should I remove issue #X from the board?"

After any board changes, verify with `scripts/roadmap-sync.sh list`.
