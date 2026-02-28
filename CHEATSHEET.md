# Hestia Cheat Sheet

## Session Lifecycle

| Command | What it does |
|---------|-------------|
| `cd ~/hestia && claude` | Start a local session (API billing) |
| `hestia-remote` | Start a Remote Control session (Max plan, accessible from iPhone/iPad) |
| `/preflight` | Full environment validation — server, tests, permissions, connectivity |
| `/restart` | Kill stale server, restart, health check, run tests |
| `/handoff` | Wrap up session — write handoff notes, spot-check docs, clean workspace |

## Strategic Workflow (opt-in)

| Command | When to use |
|---------|------------|
| `/discovery [topic]` | Deep research with SWOT, argue/refute, priority matrix |
| `/plan-audit` | Before building — CISO/CTO/CPO critique of your plan |
| `/codebase-audit` | Periodic health check — full-stack executive review |
| `/retrospective` | End of session — learning audit, friction analysis, optimization |

## Development Workflow

| Command | What it does |
|---------|-------------|
| `/scaffold [feature]` | Decompose feature into slices, build with parallel agents |
| `/bugfix` | Autonomous test-driven fix pipeline (one bug at a time) |
| `python -m pytest tests/ -v` | Run full test suite locally |
| `git push origin main` | Triggers CI → deploy to Mac Mini automatically |

## Quick Fixes

| Problem | Fix |
|---------|-----|
| Server stuck | `lsof -i :8443 \| grep LISTEN` → `kill -9 [PID]` |
| Tests timing out | Check Ollama: `curl http://localhost:11434/api/tags` |
| Auth broken | Re-register: `curl -sk -X POST https://localhost:8443/v1/auth/register -H "Content-Type: application/json" -d '{"device_name":"macbook"}'` |
| Stale tokens | Restart server: `/restart` |
| Mac Mini unreachable | Check Tailscale: `tailscale status` |

## Key Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Project context — conventions, architecture, status |
| `SESSION_HANDOFF.md` | Last session's handoff notes |
| `SPRINT.md` | Current sprint tracker — topics and phases |
| `CHEATSHEET.md` | This file |
| `docs/api-contract.md` | Full API documentation (77 endpoints) |
| `docs/hestia-decision-log.md` | Architecture Decision Records |

## Sprint Workflow

```
/discovery [topic-1]     Research
/discovery [topic-2]     Research
/discovery [topic-3]     Research
  ↓ review all discoveries, synthesize
/plan-audit              Validate unified plan
  ↓ execute
/scaffold or manual      Build
  ↓ review
/retrospective           Learn
/handoff                 Wrap up
```

## Output Directories

| Directory | Contents |
|-----------|----------|
| `docs/discoveries/` | /discovery output files |
| `docs/plans/` | /plan-audit output files |
| `docs/audits/` | /codebase-audit output files |
| `docs/retrospectives/` | /retrospective output files |

## Remote Access

```bash
# From MacBook — start remote session
hestia-remote

# From iPhone/iPad — scan QR code or find session in Claude app

# SSH fallback (API key billing)
ssh andrewroman117@hestia-3.local
tmux attach -t claude
```

## Aliases (add to ~/.zshrc)

```bash
alias hestia='cd ~/hestia && claude'
alias hestia-remote='cd ~/hestia && unset ANTHROPIC_API_KEY && claude remote-control'
alias hestia-test='cd ~/hestia && source .venv/bin/activate && python -m pytest tests/ -v'
alias hestia-server='cd ~/hestia && source .venv/bin/activate && python -m hestia.api.server'
```
