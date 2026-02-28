# Current Sprint: Claude Code Config Refresh

**Started:** 2026-02-28
**Target:** 2026-03-07

## Topics

### Direct API Configuration
- **Phase:** Done
- **Discovery:** N/A — straightforward setup
- **Key files:** `~/.zshrc` (ANTHROPIC_API_KEY export)
- **Notes:** API billing active. Max plan kept for Remote Control sessions.

### Remote Control (iPhone/iPad)
- **Phase:** Execute
- **Discovery:** N/A
- **Key files:** `~/.zshrc` (hestia-remote alias)
- **Blockers:** Requires Max plan (can't use with API key)
- **Notes:** Use `unset ANTHROPIC_API_KEY` in Remote Control terminal only

### Figma MCP Integration
- **Phase:** Pending
- **Discovery:** N/A — single command setup
- **Key files:** MCP config (after `claude mcp add`)
- **Next action:** Run `claude mcp add --transport http figma https://mcp.figma.com/mcp`

### Skill Redesign
- **Phase:** Execute
- **Discovery:** N/A — requirements defined in plan
- **Key files:** `.claude/skills/discovery/`, `plan-audit/`, `codebase-audit/`, `retrospective/`, `handoff/`
- **Notes:** Old /audit and /pickup archived to `_archive_*` directories

### CI/CD Pipeline
- **Phase:** Plan
- **Discovery:** N/A
- **Key files:** `.github/workflows/ci.yml`, `deploy.yml`, `claude.yml`
- **Blockers:** Need GitHub repo created, secrets added (ANTHROPIC_API_KEY, MAC_MINI_SSH_KEY, MAC_MINI_HOST)
- **Next action:** `gh repo create hestia --private --source=.`

### Fireproof (Server Reliability)
- **Phase:** Research
- **Discovery:** Pending — need to investigate actual failure patterns
- **Key files:** TBD
- **Blockers:** Need monitoring data before building solutions
- **Next action:** Add `/v1/health/detailed` endpoint + watchdog script

### Onboarding Cheat Sheet
- **Phase:** Done
- **Key files:** `CHEATSHEET.md`
