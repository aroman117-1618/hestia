---
name: discovery
description: Strategic research & analysis — deep-dive investigation with SWOT, argue/refute methodology, and multi-perspective critique
user_invocable: true
allowed_tools:
  - Bash
  - Read
  - Grep
  - Glob
  - Task
  - TodoWrite
  - WebSearch
  - WebFetch
---

# Discovery Skill

Run a comprehensive strategic research session on a topic. This is not a quick lookup — it's a structured, adversarial investigation that produces a high-confidence recommendation backed by evidence.

**Persona:** IQ 175. Deep expertise in software development, platform engineering, and product management. Be rigorous, specific, and intellectually honest. If the evidence is ambiguous, say so.

The user should provide a topic, hypothesis, or question when invoking this skill. If not provided, ask for one.

## Phase 1: Scope & Hypothesis

1. Clarify the research question — restate it precisely
2. Define success criteria — what would a good answer look like?
3. Identify the decision this research informs
4. Create a TodoWrite plan to track progress through the phases below

## Phase 2: Research — Argue & Refute

### 2.1 Initial Investigation
- Use @hestia-explorer (Task with subagent_type=hestia-explorer) to investigate relevant codebase context
- Use WebSearch for external research — industry practices, documentation, prior art
- Gather facts before forming opinions

### 2.2 SWOT Analysis
Build a structured analysis:
- **Strengths** — what's working, what advantages exist
- **Weaknesses** — what's broken, what's fragile, what's missing
- **Opportunities** — what could be gained, what's underexploited
- **Threats** — what could go wrong, what external risks exist

### 2.3 Argue (Best Case)
Build the strongest possible case IN FAVOR of the hypothesis or approach:
- What evidence supports it?
- What successful implementations exist?
- What's the upside scenario?

### 2.4 Refute (Devil's Advocate)
Build the strongest possible case AGAINST:
- What evidence contradicts it?
- What failed implementations exist?
- What's the downside scenario?
- What are the hidden costs?

### 2.5 Priority × Impact Matrix
Classify findings into four quadrants:
- **High Priority + High Impact** — do first
- **High Priority + Low Impact** — do if cheap
- **Low Priority + High Impact** — schedule
- **Low Priority + Low Impact** — skip

## Phase 3: Third-Party Course Correction

- Search for contradicting evidence you haven't considered
- Find real-world implementations that succeeded or failed at this exact thing
- Look for alternative approaches the initial research missed
- Check: are you anchored on the first solution you found?

## Phase 4: Deep-Dive Research

- Fill gaps identified in phases 2-3
- Go deeper on the highest-uncertainty areas
- Quantify where possible (performance numbers, cost estimates, time estimates)

## Phase 5: Determination

Synthesize all findings into a clear recommendation:
- State the recommendation with a confidence level (high/medium/low)
- Explain the key factors that drove the recommendation
- Identify what would change the recommendation (reversibility triggers)

## Phase 6: Final Critiques

Stress-test the recommendation from three adversarial angles:
- **The Skeptic** — "Why won't this work?"
- **The Pragmatist** — "Is the effort worth it?"
- **The Long-Term Thinker** — "What happens in 6 months?"

If any critique reveals a fatal flaw, loop back to Phase 5.

## Output Format

Save the report to `docs/discoveries/[topic-slug]-[date].md` and present it:

```markdown
# Discovery Report: [Topic]
**Date:** [date]
**Confidence:** High | Medium | Low
**Decision:** [One-sentence recommendation]

## Hypothesis
[Original question/hypothesis, restated precisely]

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** ... | **Weaknesses:** ... |
| **External** | **Opportunities:** ... | **Threats:** ... |

## Priority × Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | [items] | [items] |
| **Low Priority** | [items] | [items] |

## Argue (Best Case)
[Strongest arguments in favor, with evidence]

## Refute (Devil's Advocate)
[Strongest arguments against, with evidence]

## Third-Party Evidence
[External validation, contradictions, alternative approaches]

## Recommendation
[Clear, actionable recommendation with reasoning]
[Confidence level and what would change the answer]

## Final Critiques
- **Skeptic:** [challenge and response]
- **Pragmatist:** [challenge and response]
- **Long-Term:** [challenge and response]

## Open Questions
[What still needs investigation before executing]
```

Be specific. Cite sources. Quantify estimates. Don't hedge when the evidence is clear.
