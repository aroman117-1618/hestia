# Discovery Report: UI Wiring Audit Methodology

**Date:** 2026-03-19
**Type:** Retrospective — process documentation for future Discovery and Second-Opinion skills
**Confidence:** High
**Decision:** All future UI/wiring audits should follow the 4-layer parallel audit methodology developed in this session, not rely on single-pass surface scans.

## Context

Andrew requested a comprehensive audit of the macOS app to find all unwired, hardcoded, and placeholder UI. The initial audit agent came back claiming the app was "excellent" and "18/21 features fully wired." Andrew sent a screenshot of the actual running app showing obviously broken behavior: fake metrics, dead buttons, empty panels, and "All systems operational" while the server was down. This forced a complete redo with far more skepticism.

## What Went Wrong (First Pass)

The first audit agent made a critical error: **it treated "calls an API" as "fully wired."** The agent checked whether ViewModels called `APIClient` endpoints and reported "yes" as the whole story. It missed:

1. **Data loaded but not displayed** — `systemHealth` was fetched but never bound to the Hero UI
2. **Empty button closures** — buttons rendered beautifully but `{}` on tap
3. **Non-interactive list items** — data displayed but no tap handlers, no drill-down
4. **Hardcoded fake data** — progress rings, timestamps, status badges all static
5. **Missing error handling** — `errorMessage` property declared but never set; errors silently caught
6. **Built components in wrong location** — full `OrderInlineForm` existed in `Shared/` but macOS used a stripped-down `OrdersPanel`

**Root cause:** The audit was checking *plumbing* (does data flow?) but not *behavior* (does the UI actually do what it claims?).

## What Worked (Revised Approach)

### The 4-Layer Parallel Audit

Instead of one monolithic pass, we ran 4 specialized audits concurrently, each looking for a specific CLASS of problem:

#### Layer 1: Hardcoded Values Scan
**Goal:** Find every static value that should be dynamic
**Method:**
- `grep` for string literals in View files that look like real data ("2 min ago", "12 updates", "All systems operational")
- `grep` for numeric constants in Views that aren't spacing/sizing (0.992, 0.87, 0.64)
- `grep` for `Color(hex:)` literals outside of DesignSystem files
- Read each match in context to verify it's truly hardcoded vs. properly computed
**Findings:** 6 HIGH severity, 10 MEDIUM severity

#### Layer 2: Shared Components Cross-Reference
**Goal:** Find components that are built but not connected
**Method:**
- List ALL files in `Shared/Views/`, `Shared/ViewModels/`, `Shared/Services/`
- For each, `grep` whether it's imported/used in `macOS/`
- For unused components, compare completeness vs. the macOS equivalent
- Identify cases where Shared version > macOS version
**Findings:** 12 Shared components more complete than macOS equivalents, most notably `OrderInlineForm` (full wizard) vs `OrdersPanel` (display-only)

#### Layer 3: Error Handling & Offline Behavior
**Goal:** What does the user see when things go wrong?
**Method:**
- Read all ViewModel catch blocks — are errors surfaced or swallowed?
- Check if `errorMessage` / `isLoading` properties are ever displayed in Views
- Check for `NetworkMonitor` usage
- Check if `GlobalErrorBanner` is wired to any View
- Test the "server is down" path end-to-end through the code
**Findings:** Complete absence of error surfacing. All 17 ViewModels silently swallow errors. NetworkMonitor exists but isn't instantiated in macOS. GlobalErrorBanner exists but isn't wired.

#### Layer 4: Backend Endpoint Gap Analysis
**Goal:** What's built server-side but invisible to the user?
**Method:**
- `grep` all `@router.get/post/put/delete` in backend routes
- `grep` all `APIClient.shared.` calls in macOS Swift files
- Cross-reference to find uncalled endpoints
- Filter to endpoints relevant for macOS (exclude iOS-only like HealthKit sync)
**Findings:** 130 of 218 endpoints (59%) have no macOS caller. Entire subsystems hidden: memory CRUD, knowledge graph browser, proactive briefings, background task management.

### Key Principles That Made This Work

1. **Skepticism over trust.** The first agent was too trusting. The revised approach assumed everything was broken until proven otherwise. Andrew's screenshot was the forcing function.

2. **Screenshot validation.** Seeing the actual running app immediately revealed what code review missed. A surface-level code scan said "data loads" but the screenshot showed empty panels. Future audits should ALWAYS include visual validation.

3. **Parallel specialization > serial generalization.** Four agents each looking for one thing found far more than one agent looking for everything. Each specialist had a clear search pattern and couldn't get distracted.

4. **Cross-reference between layers.** Layer 2 (Shared components) found the `OrderInlineForm`. Layer 1 (hardcoded values) found the dead Hero buttons. Together they revealed the fix: wire the existing form to the existing button. Neither layer alone would have produced this insight.

5. **Verify claims by reading code, not trusting summaries.** The first agent claimed "28 missing implementations that will crash." Spot-checking with `grep` revealed all 28 ViewBuilder properties actually existed. The agent was hallucinating crashes. Always verify with direct file reads.

## Methodology Template for Future UI Audits

### When to Use This
- Before any "wiring sprint" that connects UI to backend
- After building a new UI module (verify it's actually connected)
- As part of `/codebase-audit` when UI coverage is in scope
- When Andrew says "this doesn't seem to work" or "nothing is real"

### The Process

```
Phase 1: Visual Validation (5 min)
├── Take screenshots of every screen
├── Click every button, note what happens
├── Identify what LOOKS broken to a user
└── This is the ground truth — code review serves this, not vice versa

Phase 2: Parallel Specialized Audits (run concurrently)
├── Agent A: Hardcoded Values Scan
│   ├── grep for string literals that look like data
│   ├── grep for numeric constants in Views
│   ├── grep for color literals outside DesignSystem
│   └── Verify each in context
├── Agent B: Component Cross-Reference
│   ├── List all Shared/ components
│   ├── Check which are used by target platform
│   ├── Compare completeness of duplicates
│   └── Flag "built but not connected"
├── Agent C: Error & Offline Behavior
│   ├── Read all ViewModel catch blocks
│   ├── Check if error states are displayed
│   ├── Check connectivity monitoring
│   └── Trace the "server down" path
└── Agent D: Backend Endpoint Gap Analysis
    ├── List all backend endpoints
    ├── List all client-side API calls
    ├── Cross-reference for gaps
    └── Filter to platform-relevant gaps

Phase 3: Synthesis
├── Merge findings from all 4 agents
├── De-duplicate (same issue found by multiple agents)
├── Verify claims with direct file reads (spot-check at least 30%)
├── Categorize: hardcoded / empty closure / missing component / silent error / unused endpoint
└── Estimate effort per fix (S/M/L/XL)

Phase 4: Sprint Planning
├── Group fixes into coherent workstreams
├── Order by user impact (what's most visibly broken?)
├── Identify reusable components (Shared/ items that can be ported)
├── Flag decisions needed from Andrew
└── Output: sprint plan with workstream-level estimates
```

### Anti-Patterns to Avoid

1. **"It calls an API so it's wired"** — Check if the response is actually DISPLAYED, not just fetched
2. **Trusting the first agent's summary** — Always spot-check with grep/read
3. **Serial auditing** — Run agents in parallel; they're looking for different things
4. **Confusing "compiles" with "works"** — A View can compile perfectly while showing hardcoded fake data
5. **Ignoring empty closures** — `Button { }` compiles and renders but does nothing
6. **Missing the Shared/ goldmine** — Components may already be built, just in the wrong target

### Integration Points

**For `/discovery`:** When the discovery topic is a UI feature, add Layer 1 (hardcoded scan) and Layer 2 (component cross-reference) to Phase 2. The Discovery skill currently does SWOT on architecture/approach — this extends it to verify the UI is actually connected.

**For `/second-opinion`:** Add a "UI Wiring Verification" phase (after Phase 8's UX Assessment) that runs Layer 3 (error handling) and Layer 4 (endpoint gaps) to validate that the plan covers all the gaps. The second-opinion currently checks if the plan is sound — this checks if the plan is complete.

**For `/codebase-audit`:** Add all 4 layers as a "Frontend Wiring Health" section under the CPO audit (Phase 5). The codebase-audit currently assesses code quality — this adds functional completeness.

## Resolved Decisions (Andrew 2026-03-19)

### ✅ Automated Scripts
Built and committed:
- `scripts/audit-hardcoded.sh [macos|ios|all]` — Layer 1 automation. Scans for suspicious string literals, hardcoded numeric values, color literals outside DesignSystem, empty button closures, and TODO markers. Run as part of every sprint review.
- `scripts/audit-endpoint-gaps.sh [macos|ios|all]` — Layer 4 automation. Cross-references all backend route definitions against Swift APIClient calls. Reports uncalled endpoints grouped by module with coverage percentages.

### ✅ Sub-Agent
Formalized as `@hestia-ui-auditor` (`.claude/agents/hestia-ui-auditor.md`). Sonnet model, read-only, 40-turn max. Runs all 4 layers including the automated scripts, then classifies findings by severity. Use via `@hestia-ui-auditor` in any session.

### ✅ Screenshot Cadence: Every Sprint
Visual validation screenshots should be captured at the end of every UI sprint, before marking the sprint done. This is the ground truth that catches what code review misses:
- Navigate to every screen the sprint touched
- Click every button, note what happens
- Screenshot anything that looks wrong or empty
- Compare against previous sprint's screenshots to catch regressions

Add to the Phase 4 (Review) checklist in CLAUDE.md:
> **REQUIRED: Run `@hestia-ui-auditor` and capture visual validation screenshots before marking any UI sprint done.**
