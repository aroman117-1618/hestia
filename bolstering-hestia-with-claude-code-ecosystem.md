# Bolstering Hestia: A Masterclass on Skills, Sub-Agents, Plugins, Output Styles & MCPs

*Presented to a packed auditorium — by request of Andrew, architect of Hestia*

---

## Preface: What We're Working With

Hestia is not a toy project. It's a locally-hosted personal AI assistant — 19,000+ lines of Python backend, a native SwiftUI iOS app, 47 REST endpoints, 362+ passing tests, Pentagon-level security, and full Apple ecosystem integration. It runs on a Mac Mini M1 via Ollama inference, and it's built to be your Jarvis: competent, adaptive, occasionally sardonic.

The question isn't "how do we get started." The question is: **how do we make what's already good significantly better, faster, and more reliable?**

This document is structured around three pillars:

1. **Efficacy** — Does the tool actually improve what we ship?
2. **Velocity** — Does it make us faster without sacrificing quality?
3. **Quality** — Does it reduce bugs, improve consistency, and raise the floor?

For each recommendation, I'll lay out what it is, why it matters for Hestia specifically, the trade-offs, and how to implement it.

---

## Part I: Skills — Teaching Claude How Hestia Works

### What Skills Are

A Skill is a reusable prompt-and-context package stored as a `SKILL.md` file (with optional supporting files) that Claude loads automatically when the conversation matches its description, or manually via `/skill-name`. Skills are portable across Claude on the web, desktop, and Claude Code.

Think of them as **institutional memory in a file.** Instead of re-explaining Hestia's architecture, security model, or API patterns every session, a Skill does it for you.

### Why This Matters for Hestia

Hestia already has an excellent `CLAUDE.md` — 28KB of project context, ADRs, phase history, and conventions. But `CLAUDE.md` has limits: it loads every time regardless of relevance, and it can't be modular. Skills fix both problems. They load contextually, they're composable, and they can be scoped to specific workflows.

### Recommended Skills to Build

**1. `hestia-api-conventions` — The "How We Build Endpoints" Skill**

Hestia has a very specific pattern for API routes: FastAPI with Pydantic schemas, JWT middleware, rate limiting, and a consistent response envelope. Every new endpoint should follow the same structure. This Skill would encode that pattern.

What it contains: route boilerplate, Pydantic schema patterns, middleware configuration, error response format, and the 47-endpoint contract as a reference file.

Efficacy impact: High — eliminates drift between old and new endpoints.
Velocity impact: High — no more re-reading `api-contract.md` every time.
Quality impact: High — consistent validation, error handling, auth patterns.

**2. `hestia-security` — The "Don't Break the Vault" Skill**

Hestia's security model is non-trivial: 3-tier credential partitioning, Fernet encryption with macOS Keychain fallback, biometric auth, tamper-resistant audit logs, and an `ExternalCommunicationGate` approval system. Any change touching security needs this context.

What it contains: credential tier definitions, encryption patterns, Keychain CLI interface, audit log format, and gate approval flow.

Efficacy impact: Critical — security mistakes are the kind you don't get to make twice.
Velocity impact: Medium — security reviews go faster when Claude already knows the model.
Quality impact: Critical — correct by construction rather than by review.

**3. `hestia-memory-system` — The "How Memory Works" Skill**

The memory layer (ChromaDB + SQLite, tag-based schema per ADR-013, semantic search, auto-tagging) is one of Hestia's most architecturally unique components. Any work on memory retrieval, conversation chunking, or tag management needs deep context.

What it contains: ConversationChunk model, tag schema, ChromaDB collection structure, embedding strategy, and query patterns.

Efficacy impact: High — memory bugs are subtle and hard to reproduce.
Velocity impact: Medium — the memory system is complex enough that ramp-up time matters.
Quality impact: High — correct tag propagation and retrieval is foundational.

**4. `hestia-testing` — The "Run the Tests Right" Skill**

Hestia's test suite has specific conventions: pytest with asyncio, 600-second timeouts for Ollama integration tests, `@pytest.mark.integration` markers, and mock patterns for the inference layer.

What it contains: test file naming conventions, fixture patterns, mock strategies for Ollama/ChromaDB/SQLite, marker usage, and the `pytest.ini` configuration.

Efficacy impact: Medium — prevents test anti-patterns.
Velocity impact: High — new tests get written correctly the first time.
Quality impact: High — test coverage stays meaningful.

**5. `hestia-apple-integration` — The "Talk to Apple" Skill**

The Swift CLI tools (`hestia-calendar-cli`, `hestia-reminders-cli`, `hestia-notes-cli`, `hestia-keychain-cli`) bridge Python and the Apple ecosystem via subprocess calls. The interface is specific and non-obvious.

What it contains: CLI tool interfaces, expected input/output formats, error codes, Makefile build process, and deployment path (`~/.hestia/bin/`).

Efficacy impact: Medium — Apple integration is stable but fragile to change.
Velocity impact: Medium — prevents "how does the calendar CLI work again?" loops.
Quality impact: Medium — correct argument formatting prevents silent failures.

### How to Create Them

```
.claude/skills/
├── hestia-api-conventions/
│   ├── SKILL.md          # Core patterns + when to load
│   └── reference.md      # Full 47-endpoint contract
├── hestia-security/
│   ├── SKILL.md          # Security model overview
│   └── credential-tiers.md
├── hestia-memory-system/
│   ├── SKILL.md          # Memory architecture
│   └── tag-schema.md
├── hestia-testing/
│   └── SKILL.md          # Test conventions
└── hestia-apple-integration/
    ├── SKILL.md          # CLI tool interfaces
    └── cli-reference.md
```

Each `SKILL.md` gets YAML frontmatter with a name and description that tells Claude when to load it:

```yaml
---
name: hestia-api-conventions
description: Hestia REST API patterns and conventions. Use when creating, modifying, or reviewing API routes, endpoints, Pydantic schemas, or middleware.
---
```

### Trade-offs and Considerations

The risk with Skills is over-proliferation. If you build 15 Skills that all load for every request, you've just recreated the problem of a bloated `CLAUDE.md` with more complexity. The discipline is: **each Skill should answer one question — "how do we do X in Hestia?"** — and its description should be specific enough that it only loads when that question is relevant.

Security consideration: Skills are stored in `.claude/skills/` and committed to version control. Don't put actual credentials or secrets in them. Reference the credential management patterns, not the credentials.

---

## Part II: Sub-Agents — Specialists On Demand

### What Sub-Agents Are

A Sub-Agent is a specialized autonomous AI worker that runs in its own context window with a custom system prompt, specific tool access, and independent permissions. When Claude encounters a task matching a sub-agent's description, it automatically delegates.

The key insight: sub-agents have **isolated context.** They don't pollute your main conversation with exploration noise, test output, or long diffs. They do their job and return a summary.

### Why This Matters for Hestia

Hestia is a multi-layer system: security, inference, memory, orchestration, execution, Apple integration, REST API, iOS app, CLI tools, deployment scripts. Working on the orchestration layer while simultaneously needing to verify the API contract and run the test suite is exactly the scenario where sub-agents shine. You can parallelize work that would otherwise be sequential.

### Recommended Sub-Agents to Build

**1. `hestia-tester` — The Test Runner**

```yaml
---
name: hestia-tester
description: Runs Hestia's pytest suite and reports results. Use when tests need to be run, test results need analysis, or test failures need diagnosis.
tools: Bash, Read, Grep, Glob
model: sonnet
maxTurns: 15
skills:
  - hestia-testing
---

You are Hestia's test specialist. You run the pytest suite and analyze results.

When invoked:
1. Navigate to the Hestia project root
2. Run `python -m pytest tests/ -v` (or specific test file if indicated)
3. Analyze output for failures
4. For failures: read the relevant source code and test to diagnose root cause
5. Report: total passed/failed, failure analysis, suggested fixes

Important:
- Tests marked @pytest.mark.integration require Ollama running
- Timeout is 600s for inference tests — this is expected, not a failure
- Never modify test files unless explicitly asked to fix tests
```

Efficacy: High — test failures get diagnosed with context, not just stack traces.
Velocity: High — testing runs in the background while you keep coding.
Quality: High — every change gets validated without context-switching.

**2. `hestia-reviewer` — The Code Review Specialist**

```yaml
---
name: hestia-reviewer
description: Reviews code changes for Hestia quality standards, security, and architectural consistency. Use for code review, PR preparation, or quality checks.
tools: Read, Grep, Glob, Bash
disallowedTools: Write, Edit
model: sonnet
maxTurns: 12
skills:
  - hestia-api-conventions
  - hestia-security
---

You are Hestia's code reviewer. You review for:

1. Security: credential handling follows 3-tier model, no plaintext secrets, audit logging present
2. API consistency: Pydantic schemas, response envelope format, proper middleware
3. Architecture: proper layer boundaries (security → logging → inference → memory → orchestration → execution → API)
4. Error handling: all external calls wrapped, meaningful error messages
5. Type hints: present on all function signatures

Output format:
- CRITICAL: must fix before merge
- WARNING: should fix
- SUGGESTION: consider improving
- APPROVED: no issues found
```

Efficacy: High — systematic review catches what eyes miss.
Velocity: Medium — reviews take time but prevent rework.
Quality: Critical — this is your quality gate.

**3. `hestia-explorer` — The Codebase Navigator**

```yaml
---
name: hestia-explorer
description: Explores the Hestia codebase to answer questions about architecture, find implementations, trace call paths, or understand how components interact. Use for "where is X?" or "how does Y work?" questions.
tools: Read, Grep, Glob
disallowedTools: Write, Edit, Bash
model: haiku
maxTurns: 20
---

You are Hestia's codebase explorer. You find things fast.

When asked about a component:
1. Search for the primary implementation
2. Trace its callers/callees
3. Check for tests
4. Summarize the architecture concisely

Key locations:
- Backend: hestia/ (Python package)
- iOS app: HestiaApp/Shared/
- CLI tools: hestia-cli-tools/
- Tests: tests/
- API routes: hestia/api/routes/
- Config: hestia/config/
```

Efficacy: Medium — answers questions, doesn't change code.
Velocity: High — runs on Haiku (fast, cheap), keeps exploration noise out of main context.
Quality: Medium — better understanding leads to better decisions.

**4. `hestia-deployer` — The Deployment Specialist**

```yaml
---
name: hestia-deployer
description: Handles Hestia deployment to the Mac Mini. Use when deploying, running pre-deploy checks, syncing CLI tools, or managing certificates.
tools: Bash, Read
disallowedTools: Write, Edit
model: sonnet
maxTurns: 10
---

You manage Hestia deployments.

Deployment checklist:
1. Run pre-deploy check: scripts/pre-deploy-check.sh
2. Run test suite: python -m pytest tests/ -v
3. If all pass: scripts/deploy-to-mini.sh
4. For CLI tools: scripts/sync-swift-tools.sh
5. For certificates: scripts/generate-cert.sh

Never deploy if tests fail. Report deployment status clearly.
```

Efficacy: High — deployment becomes repeatable and verifiable.
Velocity: High — one command instead of a manual checklist.
Quality: High — pre-deploy checks prevent broken deployments.

### How to Create Them

```
.claude/agents/
├── hestia-tester.md
├── hestia-reviewer.md
├── hestia-explorer.md
└── hestia-deployer.md
```

Or use the interactive `/agents` command in Claude Code for guided creation.

### Advanced Pattern: Parallel Research

When working on a feature that touches multiple layers, spawn multiple sub-agents simultaneously:

- `hestia-explorer` to find related implementations
- `hestia-tester` to run the current test suite
- `hestia-reviewer` to review recent changes

All three run in parallel, each in its own context, and return summaries. This is dramatically faster than doing each sequentially.

### Trade-offs and Considerations

Sub-agents consume tokens for each invocation — they start fresh (no memory of previous runs unless you enable persistent memory). For Hestia's scale, this is manageable, but be aware that a sub-agent with `maxTurns: 20` on Opus could burn through significant context.

The `model` field matters: use `haiku` for exploration and read-only tasks (fast, cheap), `sonnet` for code review and testing (good balance), and only `opus` for truly complex architectural analysis.

Security note: the `hestia-deployer` has `Bash` access. Consider using `permissionMode: default` so deployment commands still require your approval.

---

## Part III: Plugins — Pre-Built Power Tools

### What Plugins Are

Plugins are packages that bundle skills, agents, hooks, and MCP servers. They're installed from marketplaces (think app stores for Claude Code). The official Anthropic marketplace (`claude-plugins-official`) comes pre-available.

### Recommended Plugins for Hestia

**1. `pyright-lsp` — Python Language Server Integration**

What it does: gives Claude real-time diagnostics from Pyright (Python's type checker). After every edit, Claude sees type errors, unresolved imports, and schema violations before you even run tests.

Why it matters for Hestia: Hestia has type hints throughout but no enforced type checking (no `mypy` or `pyright` config). This plugin makes type checking automatic and contextual.

Installation:
```bash
# Install Pyright first
pip install pyright --break-system-packages

# Then install the plugin
/plugin install pyright-lsp@claude-plugins-official
```

Efficacy: High — catches type errors at write time, not test time.
Velocity: High — errors surface immediately, no round-trip to pytest.
Quality: Critical — type safety is the highest-leverage quality improvement for a 19K LOC Python project.

Trade-off: Pyright can be memory-hungry on large projects. Monitor resource usage on the Mac Mini.

**2. `github` — GitHub Integration**

What it does: gives Claude native access to GitHub issues, PRs, branches, and actions via MCP.

Why it matters for Hestia: Hestia uses Git + GitHub but has no CI/CD pipeline. With the GitHub plugin, Claude can create issues, manage PRs, and interact with the repository programmatically.

Installation:
```bash
/plugin install github@claude-plugins-official
```

Efficacy: Medium — streamlines SCM workflows.
Velocity: High — no context-switching to the GitHub UI for routine operations.
Quality: Medium — PR-based workflows improve code review discipline.

**3. `commit-commands` — Git Workflow Skills**

What it does: provides slash commands for common Git workflows — commits, branch management, changelog generation.

Why it matters for Hestia: currently, commits are manual and ad-hoc. Standardized commit workflows improve history readability and make deployment tracking easier.

Installation:
```bash
/plugin marketplace add anthropics/claude-code
/plugin install commit-commands@anthropics-claude-code
```

Efficacy: Medium — better commit hygiene.
Velocity: Medium — saves a few minutes per commit, compounds over time.
Quality: High — consistent commit messages make `git log` actually useful.

**4. `pr-review-toolkit` — Pull Request Review Agents**

What it does: specialized sub-agents for reviewing pull requests — security review, performance review, test coverage analysis.

Why it matters for Hestia: when Hestia eventually gets collaborators (or when you want Claude to systematically review your own PRs before merge), this toolkit provides structured review.

Installation:
```bash
/plugin install pr-review-toolkit@anthropics-claude-code
```

Efficacy: High — structured review catches more issues than ad-hoc review.
Velocity: Medium — adds a review step but prevents rework.
Quality: High — multi-dimensional review (security, performance, coverage).

### Plugins to Watch (Not Install Yet)

- **`sentry`** — Error monitoring integration. Worth installing once Hestia is in sustained production and generating error telemetry.
- **`linear`/`asana`/`notion`** — Project management integrations. Overkill for a solo project, valuable if Hestia becomes a team effort.
- **`slack`** — Communication integration. Potentially useful if Hestia eventually mediates communications.

### Trade-offs and Considerations

Plugins run code on your machine. Every plugin you install is code you're trusting. For Hestia's security-conscious architecture, this matters. Recommended approach: install from the official Anthropic marketplace first, audit third-party plugins before adding, and use project-scoped installation (`.claude/settings.json`) rather than user-scoped (`~/.claude/plugins/`) so plugins are explicit and version-controlled.

---

## Part IV: Output Styles — Matching Claude to the Task

### What Output Styles Are

Output Styles replace Claude Code's system prompt to adapt its behavior for different workflows. Three built-in options exist (Default, Explanatory, Learning), and you can create custom styles.

### When to Switch Styles for Hestia

**Default** — Use for active development. The default style is optimized for efficient coding: less explanation, more action. When you're implementing a new endpoint or fixing a bug, this is what you want.

**Explanatory** — Use when onboarding or learning. If you're diving into a part of the codebase you haven't touched in weeks (like the proactive intelligence system), switch to Explanatory. Claude will include "Insights" blocks explaining why it made certain choices, what patterns it's following, and what trade-offs exist.

**Learning** — Use for skill development. If you're learning a new technique (say, advanced ChromaDB query patterns or APScheduler cron syntax), Learning mode generates `TODO(human)` blocks where you implement the code yourself with Claude's guidance.

### Custom Output Style: `hestia-development`

For Hestia specifically, a custom output style could enforce project conventions without needing Skills loaded for every interaction:

```
.claude/output-styles/hestia-development.md
```

```yaml
---
name: Hestia Development
description: Optimized for Hestia project development with convention enforcement
keep-coding-instructions: true
---

You are working on Hestia, a locally-hosted personal AI assistant.

When writing Python code:
- Always include type hints on function signatures
- Use async/await for database and inference operations
- Follow the existing layer architecture: security → logging → inference → memory → orchestration → execution → API
- Log with HestiaLogger, never print()
- Handle errors with specific exception types, not bare except

When writing API routes:
- Use Pydantic schemas for request/response validation
- Follow the existing response envelope format
- Include proper JWT middleware
- Add rate limiting configuration

When writing tests:
- Use pytest with asyncio
- Mark Ollama-dependent tests with @pytest.mark.integration
- Mock external services (Ollama, ChromaDB) in unit tests
- Follow the naming convention: test_<module>.py

When writing Swift code:
- Follow MVVM with ObservableObject
- Use the existing DesignSystem tokens (colors, typography, spacing)
- Support iOS 16+ minimum
```

### Trade-offs

Output styles are session-persistent but not project-persistent by default — they're stored in `.claude/settings.local.json`, which typically isn't committed (it's local). For team settings, use `.claude/output-styles/` directory (which is committed) and team members select the style they want.

The `keep-coding-instructions: true` flag is critical for code-focused custom styles. Without it, Claude loses its built-in software engineering system prompt, which includes important behaviors around git safety, file handling, and tool usage.

---

## Part V: MCP Servers — Connecting Hestia to the World

### What MCPs Are

Model Context Protocol (MCP) servers are standardized interfaces that give Claude access to external tools and data sources. Think of them as API adapters that Claude can call natively.

### Hestia's MCP Readiness

Hestia already has an `MCPResource` enum designed for future MCP integration:

```python
class MCPResource(str, Enum):
    FIRECRAWL = "firecrawl"
    GITHUB = "github"
    APPLE_NEWS = "apple_news"
    FIDELITY = "fidelity"
    CALENDAR = "calendar"
    EMAIL = "email"
    REMINDER = "reminder"
    NOTE = "note"
    SHORTCUT = "shortcut"
```

The Orders system can already associate scheduled prompts with specific MCP resources. The infrastructure is waiting for the connections.

### Recommended MCP Servers

**1. GitHub MCP — Source Control Integration**

What it provides: issue management, PR workflows, branch operations, actions monitoring.

Why it matters: Hestia's deployment is script-based (`deploy-to-mini.sh`). GitHub MCP enables Claude to check deployment status, create release notes, and manage the repository without leaving the conversation.

Configuration:
```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-github"],
      "env": { "GITHUB_TOKEN": "..." }
    }
  }
}
```

Security note: use a fine-grained GitHub PAT with minimum required permissions. Store it via Hestia's own credential manager, not in plaintext config.

**2. Filesystem MCP — Structured File Access**

What it provides: controlled read/write access to specific directory trees.

Why it matters: Claude Code already has file access, but MCP provides a more structured, auditable interface. For Hestia's security model (which includes tamper-resistant audit logs), routing file operations through MCP means better logging.

**3. Firecrawl MCP — Web Research**

What it provides: web scraping and content extraction.

Why it matters: Hestia's Orders system already defines `FIRECRAWL` as an MCP resource. If Hestia needs to pull web data for briefings, news digests, or research tasks, Firecrawl provides clean, structured extraction.

Trade-off: Firecrawl requires an API key and external network access. This conflicts with Hestia's "local-only" philosophy for inference. Recommendation: use it for development workflows (researching APIs, checking documentation) rather than for Hestia's production inference pipeline.

### MCP in Sub-Agents

MCPs can be scoped to specific sub-agents via the `mcpServers` field in agent configuration. This is powerful for Hestia:

- Give `hestia-deployer` access to GitHub MCP for deployment tracking
- Give a research sub-agent access to Firecrawl for documentation lookup
- Keep production sub-agents (tester, reviewer) isolated from external services

---

## Part VI: Hooks — Automated Quality Gates

### What Hooks Are

Hooks are lifecycle event activators that fire before or after tool use, or when a sub-agent stops. They're like git hooks but for Claude's tool calls.

### Recommended Hooks for Hestia

**1. Pre-Edit Security Check**

Before any file edit in `hestia/security/`, run a validation script:

```yaml
hooks:
  PreToolUse:
    - matcher: "Edit"
      hooks:
        - type: command
          command: "./scripts/validate-security-edit.sh $FILE_PATH"
```

This prevents accidental credential exposure or security model violations.

**2. Post-Edit Test Runner**

After any Python file edit, automatically run the relevant test file:

```yaml
hooks:
  PostToolUse:
    - matcher: "Edit"
      hooks:
        - type: command
          command: "./scripts/auto-test.sh $FILE_PATH"
```

**3. TDD Guard**

Available as a community hook (`TDD Guard`): prevents implementation changes that don't have corresponding tests. For Hestia's 362+ test suite, this maintains coverage discipline.

### Trade-offs and Considerations

Hooks execute synchronously — a slow hook blocks Claude's next action. Keep hook scripts fast (under 5 seconds). For longer validations (full test suite), use a sub-agent instead of a hook.

Hooks can't be overridden per-session; they're defined in agent or project config. If a hook is too aggressive (blocking valid edits), you'll need to edit the config, not just tell Claude to ignore it. Design hooks for conditions that are *always* wrong (security violations, missing tests), not for conditions that are *usually* wrong (long functions, complex logic).

Security consideration: hook commands run with the same permissions as Claude Code itself. A hook script that writes to disk or makes network calls introduces a side-channel. For Hestia, keep hook scripts in the `scripts/` directory, version-controlled and auditable.

---

## Part VII: The Compound Strategy — Putting It All Together

Here's how all five categories work together for a real Hestia workflow:

### Scenario: Adding a New API Endpoint

1. **Output Style** (`hestia-development`) enforces type hints, async patterns, and Pydantic schemas from the start.

2. **Skill** (`hestia-api-conventions`) auto-loads because the description matches "creating an API route." Claude has the endpoint pattern, schema format, and middleware config in context.

3. **Sub-Agent** (`hestia-explorer`) runs in the background on Haiku to find similar endpoints and their test files for reference.

4. **Hook** (Post-Edit) triggers the test runner after each file edit, catching regressions immediately.

5. **Plugin** (`pyright-lsp`) provides real-time type checking as the code is written.

6. **Sub-Agent** (`hestia-reviewer`) does a final quality pass before commit.

7. **Plugin** (`commit-commands`) standardizes the commit message.

8. **Sub-Agent** (`hestia-tester`) runs the full test suite.

9. **Sub-Agent** (`hestia-deployer`) deploys to the Mac Mini if tests pass.

This entire chain can execute with minimal manual intervention. The developer's job shifts from "write everything carefully" to "guide the architecture and approve the results."

---

## Part VIII: Priority Roadmap

Given where Hestia is today (Phase 6b complete, enhancement phases in progress), here's the recommended implementation order:

### Week 1: Foundation (High Impact, Low Effort)

- Create `hestia-api-conventions` Skill (pull from existing CLAUDE.md and api-contract.md)
- Create `hestia-testing` Skill (extract from pytest.ini and CLAUDE.md conventions)
- Install `pyright-lsp` plugin (immediate type-checking gains)
- Create `hestia-tester` sub-agent

### Week 2: Quality Gates

- Create `hestia-security` Skill
- Create `hestia-reviewer` sub-agent
- Set up Post-Edit test hook
- Install `commit-commands` plugin
- Create custom `hestia-development` output style

### Week 3: Ecosystem

- Create `hestia-memory-system` Skill
- Create `hestia-apple-integration` Skill
- Create `hestia-explorer` sub-agent (Haiku-powered)
- Install `github` plugin
- Create `hestia-deployer` sub-agent

### Week 4: Optimization

- Add persistent memory to `hestia-reviewer` (learns project patterns over time)
- Configure MCP servers for GitHub and Filesystem
- Create Pre-Edit security hook
- Audit and tune Skill descriptions (check for over-triggering or under-triggering)
- Measure token usage across sub-agents and optimize model assignments

---

## Part IX: What Not to Do

This section is as important as the recommendations.

**Don't over-engineer the Skill library.** Start with 5 Skills. If you find yourself wanting a 6th, ask whether an existing Skill could be expanded or whether a sub-agent would be more appropriate. Skills are for knowledge; sub-agents are for actions.

**Don't give sub-agents more tools than they need.** The `hestia-reviewer` should never have `Write` or `Edit` — it reviews, it doesn't change. The principle of least privilege applies to AI agents just as it applies to human users.

**Don't install plugins you don't actively use.** Every plugin consumes resources and adds to Claude's context. The `sentry` plugin is great, but if Hestia doesn't use Sentry yet, don't install it "just in case."

**Don't bypass permission modes for convenience.** It's tempting to set `permissionMode: bypassPermissions` on the deployer agent. Don't. Deployment is exactly the kind of action that should require confirmation.

**Don't commit secrets to Skill or Agent files.** Reference credential patterns, not credentials. Reference environment variable names, not values. Hestia's 3-tier security model exists for a reason.

**Don't use Opus for everything.** Haiku is 10-20x cheaper and faster for exploration tasks. Sonnet is the right balance for most code work. Reserve Opus for truly complex architectural decisions.

---

## Appendix A: File Structure Summary

```
hestia/
├── .claude/
│   ├── settings.local.json        # Permissions, output style
│   ├── agents/                     # Sub-agent definitions
│   │   ├── hestia-tester.md
│   │   ├── hestia-reviewer.md
│   │   ├── hestia-explorer.md
│   │   └── hestia-deployer.md
│   ├── skills/                     # Skill definitions
│   │   ├── hestia-api-conventions/
│   │   │   ├── SKILL.md
│   │   │   └── reference.md
│   │   ├── hestia-security/
│   │   │   ├── SKILL.md
│   │   │   └── credential-tiers.md
│   │   ├── hestia-memory-system/
│   │   │   ├── SKILL.md
│   │   │   └── tag-schema.md
│   │   ├── hestia-testing/
│   │   │   └── SKILL.md
│   │   └── hestia-apple-integration/
│   │       ├── SKILL.md
│   │       └── cli-reference.md
│   └── output-styles/
│       └── hestia-development.md
├── CLAUDE.md                       # Existing project context (keep as-is)
└── CLAUDE-CODE-PROMPT.md           # Enhancement roadmap (keep as-is)
```

## Appendix B: Quick Reference — When to Use What

| I need to... | Use a... | Why |
|---|---|---|
| Teach Claude about Hestia patterns | **Skill** | Reusable, context-aware, loads automatically |
| Run tests in the background | **Sub-Agent** | Isolated context, parallel execution |
| Get real-time type errors | **Plugin** (pyright-lsp) | Instant feedback without running tests |
| Standardize commit messages | **Plugin** (commit-commands) | Consistent git history |
| Enforce coding conventions | **Output Style** | Session-wide behavior change |
| Connect to GitHub/Firecrawl | **MCP Server** | Structured external tool access |
| Auto-validate security edits | **Hook** | Fires automatically, zero friction |
| Block edits that break invariants | **Hook** | PreToolUse catches errors before they land |
| Review code before commit | **Sub-Agent** | Read-only, systematic, comprehensive |
| Explore "how does X work?" | **Sub-Agent** (Haiku) | Fast, cheap, doesn't pollute main context |
| Deploy to Mac Mini safely | **Sub-Agent** | Pre-checks, tests, then deploys with approval |

## Appendix C: Sources and Further Reading

- Anthropic Engineering: Claude Code Best Practices — https://www.anthropic.com/engineering/claude-code-best-practices
- Official Docs: Sub-Agents — https://code.claude.com/docs/en/sub-agents
- Official Docs: Skills — https://code.claude.com/docs/en/skills
- Official Docs: Plugins — https://code.claude.com/docs/en/discover-plugins
- Official Docs: Output Styles — https://code.claude.com/docs/en/output-styles
- Awesome Claude Code (Community) — https://github.com/hesreallyhim/awesome-claude-code
- Awesome Claude Plugins (Community) — https://github.com/quemsah/awesome-claude-plugins
- Awesome Claude Skills (Community) — https://github.com/travisvn/awesome-claude-skills
- Awesome Claude Code Sub-Agents (Community) — https://github.com/VoltAgent/awesome-claude-code-subagents
- Skills vs Sub-Agents Deep Dive — https://dev.to/nunc/claude-code-skills-vs-subagents-when-to-use-what-4d12
- OpCode (Visual Claude Code Manager) — https://github.com/winfunc/opcode

---

*End of presentation. The auditorium lights come up.*
