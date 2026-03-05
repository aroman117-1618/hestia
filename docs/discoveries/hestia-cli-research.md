# Hestia CLI Research: Building an Agentic Terminal Interface

**Date:** 2026-03-05
**Status:** Research / Phase 1
**Vision:** Hestia CLI = Claude Code capabilities + full Hestia backend access + personal AI assistant in the terminal

---

## The Big Picture

The goal is a CLI that lets Andrew interact with Hestia from the terminal the way Claude Code lets developers interact with Claude — but with the added depth of Hestia's memory, personas, tools, health data, knowledge graph, and personal context. Think: Claude Code's agentic UX married to Hestia's 154-endpoint backend.

---

## What Hestia Already Has (That a CLI Can Plug Into)

### Request Flow (already works)

```
User Input → /v1/chat → RequestHandler → Mode Detection → Memory Retrieval
    → Prompt Building → Council Classification → Inference → Tool Execution
    → Memory Storage → Response
```

The orchestration layer (`RequestHandler.handle()`) already supports multiple request sources via `RequestSource` enum — including `CLI` as a value. The entire backend is async Python with singleton managers accessed via `get_X_manager()` factories.

### Two Integration Paths

**Path A — HTTP API Client (simpler, remote-friendly)**
CLI sends requests to `https://localhost:8443/v1/chat` (or via Tailscale). JWT auth. Works from any machine on the Tailnet. Limitation: no streaming (current `/v1/chat` returns a complete response).

**Path B — Direct Manager Access (deeper, same-process)**
CLI imports `hestia.orchestration.handler` directly, bypassing HTTP. Gets access to all 25+ managers in-process. Enables streaming, richer tool integration, lower latency. Limitation: must run on the Mac Mini or wherever the backend is.

**Recommended:** Start with Path A for simplicity, add streaming via SSE endpoint, migrate to Path B for advanced features later.

### Existing Tool System

The `ToolExecutor` + `ToolRegistry` already supports:
- File operations (read, write, list, search)
- Shell command execution (sandboxed, blocked dangerous commands)
- Apple ecosystem (Calendar, Reminders, Notes, Mail via Swift CLI tools)
- HealthKit queries, URL investigation, knowledge graph operations
- Dynamic tool registration — new tools can be added at runtime

A CLI tool could register itself as a new tool source, or expose all existing tools as CLI subcommands.

---

## Claude Code UX Patterns Worth Adopting

### 1. The REPL Loop

Claude Code's core loop: **input → stream thinking → tool approval → execution → feedback**. Three modes:
- **Interactive** (default): conversational turns with approval gates
- **Batch**: single-shot for automation (`hestia "what's my schedule today?"`)
- **Plan mode**: structured task planning before execution

For Hestia, the REPL maps naturally to the existing conversation/session model (30-min TTL, mode persistence).

### 2. Universal Primitives Over Specialized Commands

Claude Code succeeds with just four capabilities: **read, write, execute, connect**. Rather than building 154 CLI subcommands, expose a small set of primitives that compose:

```bash
hestia chat "what's on my calendar today?"          # Natural language (routes through full pipeline)
hestia api GET /v1/health                            # Direct API access
hestia tool calendar_today                           # Direct tool execution
hestia memory search "project deadlines"             # Memory query
```

### 3. Progressive Permission Model

Claude Code is conservative by default — requires approval for writes, bash, MCP tools. For Hestia:

| Tier | Actions | Default |
|------|---------|---------|
| **Read** | Memory search, API GETs, file reads | Auto-approve |
| **Write** | Memory staging, file writes, settings changes | Require approval |
| **Execute** | Tool execution, shell commands, API mutations | Require approval |
| **External** | Cloud inference, URL investigation, mail/calendar writes | Require approval + gate |

Support session-level escalation: `hestia --trust-tools` to auto-approve for a session.

### 4. Slash Commands

Claude Code stores commands as markdown files in `.claude/commands/`. Hestia already has skills (`.claude/skills/`). The CLI should support both:

```
/mode tia                    # Switch persona
/memory search [query]       # Search memory
/memory approve              # Approve staged memories
/research graph              # View knowledge graph
/investigate [url]           # Analyze URL
/briefing                    # Get proactive briefing
/health summary              # Health data summary
/sync                        # Refresh all data sources
/status                      # Server health + sync age + mode
```

### 5. Streaming Output

Claude Code streams everything — thinking, tool execution, diffs. Critical for a good terminal UX. Current Hestia `/v1/chat` is request/response. **Action needed:** Add SSE or WebSocket streaming endpoint.

### 6. Status Line

Claude Code shows: git branch, PR state, cost, MCP health. Hestia CLI status line should show:

```
[tia] cloud:smart | mem:1.2k chunks | health:synced 2h ago | server:healthy
```

### 7. Context Management

Claude Code uses auto-compression to handle long conversations. Hestia already has:
- Memory manager (ChromaDB + temporal decay) for long-term context
- Session-based conversation history (30-min TTL)
- Token budgeting (32K context window)

For the CLI: leverage existing memory for cross-session continuity, add CLI-specific session notes that persist to `~/.hestia/sessions/`.

---

## Key Architecture Decision: Build vs. Extend

### Option 1: Build on Claude Agent SDK

The Agent SDK provides: REPL loop, tool approval, streaming, subagents, slash commands, auto-compression.

**Pros:** Inherit battle-tested UX patterns. Subagent support for parallel research. Streaming and permission model built in.

**Cons:** Opinionated about system prompts. Requires wrapping Hestia backend as Agent SDK tools. Ties inference to Anthropic API (Hestia uses local Ollama + multi-cloud). May conflict with Hestia's own orchestration layer.

### Option 2: Standalone Python CLI

Build a custom CLI using `prompt_toolkit` or `textual` for the TUI, calling Hestia's API or managers directly.

**Pros:** Full control over system prompts, inference routing, persona system. Can use local Ollama or any cloud provider. Tighter integration with Hestia's 25+ managers. No dependency on Anthropic SDK.

**Cons:** Must build REPL, streaming, permissions, slash commands from scratch. More engineering effort.

### Option 3: Hybrid — Agent SDK Shell + Hestia Backend

Use Agent SDK for the REPL/TUI layer but route inference through Hestia's `InferenceClient` (which already handles local/cloud routing). Register Hestia's tools as Agent SDK custom tools.

**Pros:** Best of both worlds — polished UX + Hestia's full stack. Agent SDK handles the hard UX problems (streaming, compression, permissions).

**Cons:** Complex integration layer. Two orchestration systems to reconcile. Agent SDK may not support non-Anthropic models cleanly.

**Recommendation:** Option 2 (Standalone) for v1. Hestia's existing architecture is too rich and opinionated to fit cleanly into Agent SDK's model. The CLI should be a thin terminal layer over Hestia's existing orchestration, not a parallel agent system. Agent SDK patterns can be adopted without the SDK itself.

---

## What Needs to Be Built

### Must-Have (v1)

| Component | Description | Effort |
|-----------|-------------|--------|
| **REPL core** | Turn-based conversation loop with session persistence | Medium |
| **Auth flow** | JWT token acquisition + refresh (reuse existing auth endpoints) | Small |
| **Chat command** | Send messages through `/v1/chat`, display responses | Small |
| **Streaming endpoint** | SSE or WebSocket on backend for real-time output | Medium |
| **Mode switching** | `@tia`, `@mira`, `@olly` prefix detection (already in backend) | Small |
| **Tool approval** | Interactive y/n prompts for tool execution | Small |
| **Slash commands** | `/status`, `/mode`, `/memory`, `/briefing` | Medium |
| **Rich output** | Markdown rendering, colored text, spinners | Medium |
| **Config file** | `~/.hestia/config.yaml` for server URL, default mode, preferences | Small |

### Should-Have (v2)

| Component | Description | Effort |
|-----------|-------------|--------|
| **Batch mode** | `hestia "query"` for single-shot use + piping | Small |
| **Direct API access** | `hestia api GET /v1/endpoint` for power users | Small |
| **Memory browser** | Interactive memory search + staging approval | Medium |
| **File operations** | Read/write/search files through Hestia's file manager | Medium |
| **Shell integration** | `hestia exec "command"` through sandbox | Medium |
| **Tab completion** | Commands, tools, memory tags | Medium |
| **Session history** | Browse/resume previous sessions | Small |

### Could-Have (v3)

| Component | Description | Effort |
|-----------|-------------|--------|
| **Subagents** | Parallel research/investigation tasks | Large |
| **Knowledge graph viz** | ASCII/terminal graph rendering | Medium |
| **Voice input** | Microphone → transcription → chat pipeline | Large |
| **Plugin system** | Custom commands, tools, hooks | Large |
| **TUI dashboard** | `textual`-based full-screen interface | Large |

---

## Technical Decisions to Make

1. **Python framework:** `click` (simple) vs `typer` (modern, type hints) vs `prompt_toolkit` (rich TUI) vs `textual` (full TUI framework)
2. **Output rendering:** `rich` library (markdown, tables, syntax highlighting, spinners) — strong candidate
3. **Streaming protocol:** SSE (simpler, HTTP) vs WebSocket (bidirectional, richer) for backend
4. **Package distribution:** `pip install hestia-cli` vs bundled with backend vs standalone binary (PyInstaller)
5. **Auth storage:** macOS Keychain (via existing `hestia-keychain-cli`) vs `~/.hestia/auth.json` (encrypted)

---

## Proposed Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| CLI framework | `typer` + `prompt_toolkit` | Type-hint driven, rich prompts, async support |
| Output rendering | `rich` | Markdown, tables, syntax highlighting, spinners, live displays |
| HTTP client | `httpx` | Async, streaming support, HTTP/2 |
| Config | `pyyaml` | Consistent with Hestia's existing config pattern |
| Auth | macOS Keychain | Consistent with Hestia's security posture |
| Streaming | SSE (server-sent events) | Simpler than WebSocket, sufficient for output streaming |

---

## Example Session (Vision)

```
$ hestia
🏛️ Hestia CLI v0.1 — connected to hestia-3.local:8443
[tia] cloud:smart | 1,247 memories | server:healthy

> what's on my calendar today?

📅 You have 3 events today:
  • 10:00 AM — Team standup (30min)
  • 1:00 PM — Design review with Sarah (1hr)
  • 4:00 PM — 1:1 with manager (30min)

Your next event is in 47 minutes.

> @mira explain how the council system works in hestia

🦉 The council system is Hestia's multi-perspective decision layer.
When cloud inference is active, it runs four specialized roles in
parallel...

[streams explanation with code references]

> /investigate https://arxiv.org/abs/2403.12345

🔍 Investigating URL...
⚙️  Tool: investigate_url — Approve? [Y/n] y

[streams analysis results]

> /memory search "architecture decisions"

Found 8 relevant memories (sorted by relevance × recency):
  1. [0.94] ADR-032: Newsfeed materialized cache (2026-02-15)
  2. [0.91] ADR-036: macOS health redesign (2026-03-01)
  ...

> /briefing

📋 Morning Briefing — Thursday, March 5
  • 3 calendar events today
  • 2 unread inbox items
  • Health: sleep 7.2h (↑), steps on track
  • Newsfeed: 5 new items since yesterday

> exit
Session saved. 12 turns, 3 tool calls. Goodbye! 🏛️
```

---

## Next Steps

1. **Decide:** Option 2 (standalone) vs Option 3 (hybrid Agent SDK)?
2. **Prototype:** Minimal REPL with `/v1/chat` integration + `rich` output
3. **Backend prep:** Add SSE streaming endpoint to FastAPI
4. **Scaffold:** `hestia-cli/` module structure within the monorepo
5. **Sprint planning:** Size the work, slot into sprint cadence

---

## References

- [Claude Code Architecture (Reverse Engineered)](https://vrungta.substack.com/p/claude-code-architecture-reverse)
- [How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works)
- [Claude Agent SDK overview](https://platform.claude.com/docs/en/agent-sdk/overview)
- [Building agents with Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Designing for Agentic AI — Smashing Magazine](https://www.smashingmagazine.com/2026/02/designing-agentic-ai-practical-ux-patterns/)
