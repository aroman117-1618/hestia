---
name: Hestia Development
description: Optimized for Hestia project development. Enforces project conventions, type safety, layer architecture, and the 4-phase workflow (Research > Plan > Execute > Review).
keep-coding-instructions: true
---

# Hestia Development Mode

You are working on Hestia, a locally-hosted personal AI assistant built on Python/FastAPI (backend), SwiftUI (iOS), and Ollama (local inference). Every session follows a disciplined 4-phase workflow.

## 4-Phase Workflow (Mandatory)

Every non-trivial task follows this structure. Do not skip phases.

### Phase 1: Research
- Explore the relevant parts of the codebase before writing any code
- Identify affected files, dependencies, and patterns
- Consider pros, cons, trade-offs, security implications
- Present findings clearly with reasoning

### Phase 2: Plan
- Confirm decisions with Andrew before implementing
- Draft an implementation plan with specific files and changes
- Pressure-test the plan: what could go wrong? What are the edge cases?
- Iterate on the plan at least once before executing

### Phase 3: Execute
- Implement the plan precisely
- Run tests after each significant change (use @hestia-tester sub-agent)
- Fix issues immediately — don't accumulate tech debt
- Verify the build is fully functional before moving on

### Phase 4: Review
- Run @hestia-reviewer sub-agent on all changed files
- Update all affected documentation (CLAUDE.md, api-contract.md, decision log)
- Ensure historical context is preserved in session log
- Confirm the project is primed for the next Claude Code session

## Python Conventions

- **Type hints**: Always. On every function signature, parameter, and return type.
- **Async/await**: For all I/O operations (database, inference, network calls).
- **Layer architecture**: security > logging > inference > memory > orchestration > execution > API. Never import upward.
- **Logging**: Use `get_logger()` from `hestia.logging`, never `print()`. Call with no arguments. Include request ID in context.
- **Error handling**: Specific exception types. No bare `except:`. Always log errors.
- **Config**: Load from YAML. Never hardcode values.
- **File naming**: `snake_case.py`
- **Manager pattern**: Each module follows `models.py` + `database.py` + `manager.py`

## API Conventions

- Pydantic schemas for all request/response validation
- Response envelope: consistent format across all endpoints
- JWT middleware on all authenticated routes
- Rate limiting configuration on all routes
- Route naming: `/v1/{resource}/{action}`
- HTTP verbs match semantics (GET reads, POST creates, PATCH updates, DELETE deletes)

## Swift/iOS Conventions

- MVVM with `ObservableObject` (not `@Observable` — iOS 26.0+ target)
- DesignSystem tokens: `HestiaColors`, `HestiaTypography`, `HestiaSpacing`
- No force-unwraps (`!`) — use `guard let` / `if let`
- `[weak self]` in closures that capture self
- `#if DEBUG` for debug-only code
- iOS 26.0+ minimum deployment target

## Testing Conventions

- pytest with asyncio
- `@pytest.mark.integration` for Ollama-dependent tests
- Mock externals (Ollama, ChromaDB), not internals
- Test file naming: `test_{module}.py`
- Verify with @hestia-tester sub-agent after implementation

## Security Posture

- 3-tier credential partitioning (operational/sensitive/system)
- Double encryption (Fernet + Keychain AES-256)
- External communication gate — nothing leaves without approval
- Audit logging for all sensitive operations
- No secrets in code, comments, configs, or agent files

## Sub-Agent Usage

Use the appropriate specialist sub-agent:
- **@hestia-tester**: Run tests, diagnose failures (Sonnet)
- **@hestia-reviewer**: Code review before commits (Sonnet)
- **@hestia-explorer**: Find code, trace architecture (Haiku — fast & cheap)
- **@hestia-deployer**: Deploy to Mac Mini (Sonnet)

## Strategic Skills (Opt-In)

These are invoked explicitly — not enforced on every task:
- **/discovery [topic]**: Deep research with SWOT, argue/refute, priority matrix. Outputs to `docs/discoveries/`.
- **/plan-audit**: CISO/CTO/CPO critique before building. Outputs to `docs/plans/`.
- **/codebase-audit**: Full-stack executive health assessment. Outputs to `docs/audits/`.
- **/retrospective**: Session learning audit and friction analysis. Outputs to `docs/retrospectives/`.
- **/handoff**: Session wrap-up with doc spot-check and workspace cleanup.

## Sprint Tracking

Check `SPRINT.md` for current sprint status. Skills save their outputs to structured directories. The typical strategic workflow is:

```
/discovery → /plan-audit → /scaffold or manual → /retrospective → /handoff
```

## Andrew's Working Style

- ~6 hours/week, so efficiency matters
- 70% teach-as-we-build, 30% just-make-it-work
- Prefers thorough explanations when learning, concise when executing
- Prefers to focus on planning and leave execution to the agent
- Uses Claude Code (API billing) + Xcode as primary tools
- See `CHEATSHEET.md` for quick reference
