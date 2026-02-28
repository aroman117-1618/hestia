# Claude Code Configuration Refresh — Implementation Plan

**Date:** 2026-02-28
**Author:** Claude (for Andrew's review)
**Scope:** Full overhaul of Claude Code configuration, CI/CD pipeline, skills, and workflow

---

## Executive Summary

This plan covers 7 workstreams to modernize your Claude Code setup. The guiding principles: maximum privacy (direct API), mobile accessibility (Remote Control), automated deployment (GitHub Actions → Mac Mini), and sharper development workflows (redesigned skills with strategic analysis capabilities).

**Estimated effort:** 3–4 focused sessions (~18–24 hours total)
**Risk level:** Low-to-medium (most changes are additive, not destructive)

---

## Current State Assessment

**What's working well:**
- 4-phase workflow is well-enforced via output style + CLAUDE.md
- Sub-agents (explorer, tester, reviewer, deployer) are well-scoped with correct model assignments
- Hook system (security validation + auto-test) is solid and battle-tested
- 892 tests with 886 passing — strong foundation

**What needs work:**
- No CI/CD pipeline (all manual rsync + SSH)
- No remote access (can't manage from iPhone/iPad)
- Skills are functional but lack strategic depth (no SWOT, no multi-perspective critique)
- No Figma integration despite having a detailed design spec ready
- Deployment reliability is fragile (permissions resets, stale tokens, unclear failure modes)
- No onboarding quick-reference — session startup friction
- Using Claude Code via subscription instead of direct API

---

## Workstream 1: Direct API Configuration

**Goal:** Switch from subscription-based to direct Anthropic API key usage for maximum privacy and cost control.

### Steps

1. **Get API key** from [console.anthropic.com](https://console.anthropic.com) → API Keys section
2. **Set environment variable** in `~/.zshrc` on both MacBook and Mac Mini:
   ```bash
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```
3. **Remove subscription login** — run `claude /logout` to disconnect from subscription billing
4. **Verify** — launch `claude` and confirm it's using the API key (it will show "API key" in the status, not your email)
5. **Update `.env`** in Hestia project — your existing `.env` already has an `ANTHROPIC_API_KEY`; ensure it matches
6. **Set up usage monitoring** — configure spend alerts on console.anthropic.com to avoid surprise bills
7. **Optional: `apiKeyHelper`** — if you want key rotation, create a helper script that pulls from macOS Keychain:
   ```bash
   # ~/.claude/api-key-helper.sh
   security find-generic-password -s "anthropic-api-key" -w
   ```
   Then set in Claude Code config: `"apiKeyHelper": "~/.claude/api-key-helper.sh"`

### Testing
- Run `claude -p "echo test" --output-format json` and verify response includes model info
- Confirm billing shows up on console.anthropic.com, not on claude.ai subscription

### Risks
- **Cost visibility** — API billing is per-token, not flat rate. Sub-agents (especially Sonnet-class) can add up during scaffold/audit operations. Recommendation: set a monthly budget alert at $50 and $100.
- **Rate limits** — API tier limits may throttle heavy parallel agent usage. Monitor 429 responses.

---

## Workstream 2: Remote Control (iPhone/iPad Access)

**Goal:** Run and manage Claude Code sessions from iPhone and iPad via Remote Control.

### Prerequisites
- Remote Control currently requires a **Max plan** subscription (not API key alone). This creates a conflict with WS1.
- **Resolution options:**
  - **(A) Keep Max plan + API key** — use Max plan for interactive sessions (Remote Control), API key for CI/CD automation. Claude Code handles the conflict by preferring the API key when set; you'd need to unset it for Remote Control sessions.
  - **(B) Wait for API key support** — Anthropic is rolling out API key support for Remote Control. Timeline unclear.
  - **(C) Tailscale + Termius fallback** — Use your existing Tailscale setup + Termius (iOS SSH app) + tmux for SSH-based remote access. Less polished but works today with API key.

### Steps (Option A — Recommended for now)

1. **Ensure Max plan is active** on claude.ai
2. **Start Remote Control** from your MacBook:
   ```bash
   cd ~/hestia
   claude remote-control
   ```
3. **Connect from iPhone/iPad:**
   - Scan QR code displayed in terminal, OR
   - Open Claude iOS app → find session in session list (green dot = online)
4. **Enable auto-start** (optional):
   ```
   /config → "Enable Remote Control for all sessions" → true
   ```
5. **Keep session alive** — terminal must stay open. Recommendation: run inside `tmux` session so it survives terminal close:
   ```bash
   tmux new -s hestia-remote
   cd ~/hestia && claude remote-control
   # Ctrl+B, D to detach
   ```

### Steps (Option C — Tailscale + SSH fallback)

1. Install **Termius** on iPhone/iPad (free tier works)
2. Add host: `andrewroman117@hestia-3.local` (Mac Mini via Tailscale) or your MacBook's Tailscale hostname
3. On Mac, set up persistent tmux:
   ```bash
   tmux new -s claude
   cd ~/hestia && claude
   # Detach: Ctrl+B, D
   ```
4. From Termius: SSH in → `tmux attach -t claude`

### Recommendation
Start with **Option A** (Max plan + Remote Control) for the best mobile experience. Use the API key for CI/CD (WS5) where Remote Control isn't needed. Revisit when API key support for Remote Control ships.

---

## Workstream 3: Figma MCP Integration

**Goal:** Full bidirectional Figma integration — pull designs for code generation, push annotations back.

### Steps

1. **Add Figma MCP server:**
   ```bash
   claude mcp add --transport http figma https://mcp.figma.com/mcp
   ```
2. **Authenticate** — Figma will prompt OAuth flow on first use
3. **Verify connection:**
   ```
   /mcp
   ```
   Should show `figma` as connected
4. **Test read access** — paste a Figma component link in a Claude Code prompt and ask it to describe the design
5. **Test code generation** — paste a Figma frame link and ask for SwiftUI or HTML output
6. **Update `.claude/settings.json`** — if MCP config needs to be project-scoped, add to settings
7. **Update CLAUDE.md** — add Figma integration to the Technical Stack table and document the workflow

### Design-to-Code Workflow
Your `docs/figma-make-prompt.md` already has detailed specs for the Hestia Workspace macOS app. The workflow would be:
1. Design component in Figma
2. Copy component/frame link
3. In Claude Code: `"Generate SwiftUI view from this Figma design: [link]"`
4. Claude reads design tokens, layout, colors via MCP
5. Generates code matching your DesignSystem tokens (HestiaColors, HestiaTypography, HestiaSpacing)

### Risks
- **Bidirectional writes** — Figma MCP's write capabilities may be limited to annotations/comments, not full design modification. Need to verify actual write API surface.
- **Design token mapping** — Figma variables → SwiftUI DesignSystem tokens requires a mapping layer. May need a custom translation script or prompt template.

---

## Workstream 4: Skill Redesign (Commands)

**Goal:** Replace existing skills with a new set aligned to your strategic workflow. Existing operational skills (/restart, /preflight) that are still useful get folded into the new structure.

### New Skill Architecture

| Skill | Replaces | Purpose |
|-------|----------|---------|
| `/discovery` | (new) | Deep research with argue/refute SWOT analysis |
| `/plan-audit` | `/audit` (plan mode) | Sprint/plan-focused SWOT + CISO/CTO/CPO critiques |
| `/codebase-audit` | `/audit` (code mode) | Full-stack SWOT + CISO/CTO/CPO analysis |
| `/retrospective` | `/audit` (retro mode) | Learning audit, session review, optimization |
| `/handoff` | `/handoff` (upgraded) | Session wrap-up, documentation spot-check, workspace cleanup |
| `/pickup` | `/pickup` (folded in) | Merged into handoff's counterpart — session startup |
| `/restart` | `/restart` (kept) | Operational — no changes needed |
| `/preflight` | `/preflight` (kept) | Operational — no changes needed |
| `/bugfix` | `/bugfix` (kept) | Operational — no changes needed |
| `/scaffold` | `/scaffold` (kept) | Operational — no changes needed |

### Skill Designs

#### `/discovery` — Strategic Research & Analysis

**Trigger:** "I need to research X" or explicit `/discovery`
**Model:** Opus (deep reasoning required)
**Persona:** IQ 175, expertise in software development, platform engineering, product management

**Workflow:**
1. **Receive hypothesis or prompt** — clarify scope and success criteria
2. **Research phase:**
   - Deep-dive investigation using @hestia-explorer + web search
   - Argue & Refute: build the strongest case FOR and AGAINST
   - SWOT matrix: Strengths, Weaknesses, Opportunities, Threats
   - Offense/Defense framing: Good vs Bad × High vs Low priority × Impact
3. **Third-party course correction:**
   - Search for contradicting evidence, alternative approaches
   - Find real-world implementations that succeeded or failed
4. **Deep-dive research** — fill gaps identified in steps 2-3
5. **Determination** — synthesize findings into clear recommendation
6. **Final critiques** — stress-test the recommendation from adversarial angles

**Output format:**
```
## Discovery Report: [Topic]

### Hypothesis
[Original question/hypothesis]

### SWOT Analysis
| | Positive | Negative |
|---|---------|----------|
| Internal | Strengths: ... | Weaknesses: ... |
| External | Opportunities: ... | Threats: ... |

### Priority × Impact Matrix
| | High Impact | Low Impact |
|---|-----------|-----------|
| High Priority | [items] | [items] |
| Low Priority | [items] | [items] |

### Argue (Best Case)
[Strongest arguments in favor]

### Refute (Devil's Advocate)
[Strongest arguments against]

### Third-Party Evidence
[External validation or contradiction]

### Recommendation
[Clear, actionable recommendation with confidence level]

### Open Questions
[What still needs investigation]
```

#### `/plan-audit` — Sprint/Plan SWOT + Executive Critique

**Trigger:** After planning, before execution. Or explicit `/plan-audit`
**Model:** Sonnet (strong reasoning, faster than Opus)
**Persona:** Panel of three executives — CISO, CTO, CPO

**Workflow:**
1. **Read the plan** — consume all context (CLAUDE.md, relevant docs, the plan itself)
2. **SWOT analysis** of the plan
3. **Executive critiques:**
   - **CISO perspective:** Security implications, attack surface changes, credential handling, data exposure
   - **CTO perspective:** Architecture fit, technical debt, scalability, maintenance burden, dependency risk
   - **CPO perspective:** User value, scope creep, priority alignment, opportunity cost
4. **Sequencing assessment** — is the execution order optimal? Dependencies mapped correctly?
5. **Standards & testing** — are quality gates defined? What's the test strategy?
6. **Unilateral redundancies** — single points of failure in the plan?
7. **Final critiques** — what's the one thing most likely to go wrong?

**Output format:**
```
## Plan Audit: [Plan Name]

### SWOT
[Matrix]

### CISO Review
- Critical: [items]
- Acceptable: [items]
- Recommendation: [summary]

### CTO Review
- Critical: [items]
- Acceptable: [items]
- Recommendation: [summary]

### CPO Review
- Critical: [items]
- Acceptable: [items]
- Recommendation: [summary]

### Sequencing Issues
[Any ordering problems]

### Quality Gates
[Are they sufficient?]

### Single Points of Failure
[Redundancy gaps]

### Verdict: [APPROVE / APPROVE WITH CONDITIONS / REJECT]
[One-paragraph summary with conditions if applicable]
```

#### `/codebase-audit` — Full-Stack Technical Audit

**Trigger:** Periodic health check or explicit `/codebase-audit`
**Model:** Sonnet
**Persona:** Same CISO/CTO/CPO panel, IQ 175

**Workflow:**
1. **Scan** — use @hestia-explorer to map current state
2. **SWOT analysis** of the codebase as a whole
3. **CISO audit:** OWASP top 10, credential handling, error sanitization, JWT security, communication gate, prompt injection risks
4. **CTO audit:** Layer boundaries, dead code, manager pattern consistency, dependency hygiene, performance bottlenecks, LLM/ML architecture robustness
5. **CPO audit:** Feature completeness vs roadmap, API usability, documentation quality, onboarding friction
6. **Simplification opportunities** — consolidation, dead code removal, config cleanup
7. **Cohesion & consistency** — naming, patterns, error handling uniformity

**Output:** Same executive panel format as plan-audit, plus file-level specifics (paths, line numbers, concrete fix proposals).

#### `/retrospective` — Session Learning Audit

**Trigger:** End of session (before /handoff) or explicit `/retrospective`
**Model:** Sonnet

**Workflow:**
1. **Learning audit** — what was learned this session? What assumptions were wrong?
2. **Deep-dive audit reviews** — review any audit outputs from this session
3. **Chat engagement analysis** — where did the conversation get stuck? What questions needed pre-answering?
4. **Bug/troubleshooting loop analysis** — any debugging spirals? What caused them? How to prevent?
5. **Optimization recommendations:**
   - What should be added to CLAUDE.md to prevent repeat issues?
   - What skills/agents need updating?
   - What documentation drifted?
6. **Session metrics** — files changed, tests added/fixed, decisions made

**Output:**
```
## Session Retrospective: [Date]

### Key Learnings
[Numbered list]

### Engagement Friction Points
[Where did we get stuck and why]

### Debugging Loops
[Any spirals, root causes, prevention strategies]

### Documentation Updates Needed
| File | What Changed | Status |
|------|-------------|--------|

### Skills/Agents Updates Needed
[Specific improvements]

### Metrics
- Files changed: X
- Tests: +Y added, Z fixed
- Decisions: [list]
```

#### `/handoff` — Session Wrap-Up (Upgraded)

**Trigger:** End of session or explicit `/handoff`
**Model:** Sonnet

**Upgrades from current version:**
1. Everything the current /handoff does, PLUS:
2. **Documentation spot-check** — verify CLAUDE.md, api-contract.md, decision-log are current
3. **Workspace cleanup** — identify stale files, uncommitted changes, orphaned branches
4. **"Prepare for night shift"** framing — write handoff notes as if briefing a fresh colleague:
   - What was the mission today?
   - What got done?
   - What's the exact next action (not vague — specific file, specific function, specific test)?
   - What landmines exist (things that look fine but aren't)?
5. **Merge /pickup into the handoff cycle** — /handoff writes SESSION_HANDOFF.md, next session reads it automatically (via CLAUDE.md instruction or output style)

---

## Workstream 5: CI/CD Pipeline

**Goal:** Local validate → push to GitHub → automated production tests → deploy to Mac Mini → apps auto-update.

### Architecture

```
MacBook (dev)                    GitHub                       Mac Mini (prod)
┌─────────────┐     git push    ┌──────────────┐   SSH/rsync  ┌─────────────┐
│ Local dev    │───────────────→│ GitHub repo   │────────────→│ Production  │
│ - edit code  │                │ - CI tests    │             │ - FastAPI   │
│ - run tests  │                │ - lint        │             │ - Ollama    │
│ - validate   │                │ - deploy job  │             │ - CLI tools │
└─────────────┘                └──────────────┘             └─────────────┘
                                       │
                                       │ claude-code-action
                                       │ (PR reviews, issue triage)
                                       ▼
                                 Claude Code AI
```

### Steps

#### Phase 1: GitHub Repository Setup
1. **Create GitHub repo** (if not already): `gh repo create hestia --private --source=.`
2. **Add secrets:**
   - `ANTHROPIC_API_KEY` — for Claude Code Action
   - `MAC_MINI_SSH_KEY` — private key for `andrewroman117@hestia-3.local`
   - `MAC_MINI_HOST` — `hestia-3.local` (or Tailscale IP as fallback)
3. **Push initial codebase** — ensure `.gitignore` covers all sensitive files

#### Phase 2: CI Workflow (Test + Lint)
Create `.github/workflows/ci.yml`:
```yaml
name: Hestia CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m pytest tests/ -v --timeout=60
        # Note: Ollama integration tests will be skipped (no Ollama on GH runner)
        # Mark them with @pytest.mark.integration and exclude:
        # python -m pytest tests/ -v --timeout=60 -m "not integration"
```

#### Phase 3: Deploy Workflow
Create `.github/workflows/deploy.yml`:
```yaml
name: Hestia Deploy
on:
  push:
    branches: [main]
  workflow_dispatch:  # manual trigger option

jobs:
  deploy:
    runs-on: ubuntu-latest
    needs: [test]  # only deploy if tests pass
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Mac Mini
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.MAC_MINI_HOST }}
          username: andrewroman117
          key: ${{ secrets.MAC_MINI_SSH_KEY }}
          script: |
            cd ~/hestia
            git pull origin main
            source .venv/bin/activate
            pip install -r requirements.txt
            python -m pytest tests/ -v --timeout=120
            # Restart server
            lsof -i :8443 | grep LISTEN | awk '{print $2}' | xargs kill -9 2>/dev/null || true
            nohup python -m hestia.api.server > /dev/null 2>&1 &
            sleep 5
            curl -sk https://localhost:8443/v1/ping
```

#### Phase 4: Claude Code Action (PR Reviews)
Create `.github/workflows/claude.yml`:
```yaml
name: Claude Code
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
  pull_request:
    types: [opened, synchronize]

jobs:
  claude:
    if: contains(github.event.comment.body, '@claude') || github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

#### Phase 5: iOS Auto-Update
- **Xcode Cloud** or **Fastlane** can auto-build when the repo updates
- For TestFlight distribution: push to main → GitHub Action triggers → Xcode Cloud picks up → builds → pushes to TestFlight → devices auto-update
- **Simpler alternative:** Since this is a personal project, just trigger a build from Xcode when you want to update the app. Full Xcode Cloud setup is a separate workstream.

### Fireproof: Server Reliability

This is an investigation-first item. Before building solutions, we need to diagnose what actually breaks.

**Investigation plan:**
1. **Add structured health logging** — create a `/v1/health/detailed` endpoint that reports:
   - JWT token validity for registered devices
   - TLS cert expiry date
   - macOS TCC permission status (calendar, reminders, notes access)
   - Ollama process status and model availability
   - Launchd service status
   - Disk space and memory usage
2. **Add a watchdog script** that runs every 5 minutes via launchd:
   - Hit `/v1/health/detailed`
   - If any check fails, attempt auto-recovery (restart server, reload launchd, etc.)
   - Log all failures to `logs/watchdog.log`
3. **Monitor for 1-2 weeks** to identify the actual failure patterns
4. **Then build targeted fixes** based on real data

### Network Accessibility
- **Tailscale** already handles VPN connectivity
- **Self-signed cert** is the likely source of mobile trust issues. Consider:
  - Let's Encrypt via Tailscale's built-in HTTPS (`tailscale cert`)
  - Or a Tailscale funnel for public HTTPS
  - Or just document the cert trust process clearly for iOS

---

## Workstream 6: Onboarding Cheat Sheet

**Goal:** Quick-reference card for Andrew — commands, workflows, common operations, gotchas.

### Deliverable
A single-page `CHEATSHEET.md` in the project root, covering:

1. **Session Lifecycle:**
   ```
   Start:     cd ~/hestia && claude          (or: claude remote-control)
   Pickup:    /pickup                        (reads SESSION_HANDOFF.md, shows status)
   Preflight: /preflight                     (full environment validation)
   Restart:   /restart                       (kill server, restart, health check)
   Handoff:   /handoff                       (write handoff notes, clean up)
   ```

2. **Strategic Workflow (opt-in):**
   ```
   Research:  /discovery [topic]             (SWOT, argue/refute, deep dive)
   Plan:      /plan-audit                    (CISO/CTO/CPO critique of plan)
   Audit:     /codebase-audit                (full-stack health check)
   Review:    /retrospective                 (session learning audit)
   ```

3. **Development Workflow:**
   ```
   Build:     /scaffold [feature]            (parallel multi-agent buildout)
   Fix:       /bugfix                        (autonomous test-driven fix pipeline)
   Test:      python -m pytest tests/ -v     (full suite)
   Deploy:    git push origin main           (triggers CI/CD → Mac Mini)
   ```

4. **Quick Fixes:**
   ```
   Server stuck:     lsof -i :8443 | grep LISTEN → kill -9 [PID]
   Tests timing out: Check Ollama: curl http://localhost:11434/api/tags
   Auth broken:      Re-register device: curl -X POST .../v1/auth/register
   ```

5. **Key Files:**
   ```
   Config:    CLAUDE.md, .claude/settings.json
   Handoff:   SESSION_HANDOFF.md
   API docs:  docs/api-contract.md
   Decisions: docs/hestia-decision-log.md
   ```

---

## Workstream 7: Workflow Optimization (Modality Tracking)

**Goal:** Optimize for your preferred pattern — plan through research across multiple topics, then audit and execute cohesively.

### The Problem
Your workflow spans multiple topics/modules per sprint. You need easy tracking of where each topic is in the pipeline (Research → Plan → Execute → Review) without losing coordination across them.

### Solution: Sprint Tracker Pattern

Add a `SPRINT.md` file that acts as a lightweight kanban:

```markdown
# Current Sprint: [Name]
**Started:** [date]  |  **Target:** [date]

## Topics

### [Topic 1 Name]
- **Phase:** Research | Plan | Execute | Review | Done
- **Discovery:** [link to discovery output or "pending"]
- **Plan:** [link to plan or "pending"]
- **Key files:** [list]
- **Blockers:** [any]

### [Topic 2 Name]
- **Phase:** Research | Plan | Execute | Review | Done
- ...
```

### Integration with Skills
- `/discovery` outputs get saved to `docs/discoveries/[topic]-[date].md`
- `/plan-audit` outputs get saved to `docs/plans/[topic]-[date].md`
- `/retrospective` references SPRINT.md to assess progress
- `/handoff` updates SPRINT.md phase markers

### Workflow Sequence
```
1. /discovery [topic-1]     → Research report saved
2. /discovery [topic-2]     → Research report saved
3. /discovery [topic-3]     → Research report saved
4. Review all discoveries, synthesize cross-cutting concerns
5. /plan-audit              → Unified implementation plan audited
6. /scaffold or manual      → Execute
7. /retrospective           → Learning capture
8. /handoff                 → Session wrap-up
```

---

## Implementation Sequence

| Order | Workstream | Effort | Dependencies | Session |
|-------|-----------|--------|-------------|---------|
| 1 | WS1: Direct API | 30 min | None | Session 1 |
| 2 | WS3: Figma MCP | 30 min | None | Session 1 |
| 3 | WS4: Skill Redesign | 3-4 hrs | None | Session 1-2 |
| 4 | WS6: Cheat Sheet | 30 min | WS4 (reference new skills) | Session 2 |
| 5 | WS7: Workflow/Sprint Tracker | 1 hr | WS4 (skills save to tracker) | Session 2 |
| 6 | WS2: Remote Control | 1 hr | WS1 (API key decision) | Session 2 |
| 7 | WS5: CI/CD Pipeline | 3-4 hrs | GitHub repo setup | Session 3 |
| 7b | WS5: Fireproof (investigation) | 2 hrs | WS5 CI/CD (deploy first) | Session 3 |

### Rationale
- API key and Figma MCP are quick wins — do them first
- Skills are the highest-value change and inform everything else
- CI/CD requires GitHub repo setup and is more infrastructure-heavy — save for dedicated session
- Fireproof is investigation-first — deploy the monitoring, then fix what breaks

---

## Open Questions for Andrew

1. **Max plan vs API-only:** Remote Control requires Max plan today. Are you willing to keep Max plan alongside API key, or prefer to wait for API key support?
2. **GitHub repo:** Is Hestia already on GitHub, or do we need to create the repo? Private vs public?
3. **iOS auto-deploy:** How important is automatic TestFlight distribution vs manual Xcode builds? Full Xcode Cloud is a significant setup.
4. **Skill model selection:** Discovery is proposed as Opus (deepest reasoning). Is cost a concern, or is quality the priority for strategic analysis?
5. **Sprint cadence:** How long are your typical sprints? Weekly? Bi-weekly? This affects SPRINT.md structure.
