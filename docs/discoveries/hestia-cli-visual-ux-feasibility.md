# Hestia CLI: Visual UX Feasibility — Can We Match Claude Code?

**Date:** 2026-03-05
**Parent:** [hestia-cli-research.md](hestia-cli-research.md)

---

## TL;DR

**Yes, we can match ~90% of Claude Code's visual UX in Python.** The remaining 10% (cell-level diff rendering, React reconciliation smoothness) is a marginal polish gap, not a capability gap. The key insight: Claude Code uses React + Ink (a React-to-terminal renderer), which is essentially what Textual is for Python — both use constraint-based layouts and smart diffing to minimize terminal flicker.

---

## Claude Code's Rendering Stack (for reference)

Claude Code is TypeScript, built on:
- **Ink** — React components rendered to terminal (ANSI escape sequences)
- **Yoga** — Meta's flexbox layout engine for character-based grids
- **Shiki** — Syntax highlighting with theme-aware colors
- **Cell-level diffing** — Only redraws changed characters (85% flicker reduction)

This is a sophisticated setup. But Python's ecosystem has mature equivalents for every layer.

---

## Feature-by-Feature Feasibility

### Can Match Exactly ✅

| Claude Code Feature | Python Equivalent | Library |
|---|---|---|
| **Streaming text** (char-by-char as LLM generates) | `Rich.Live` or `Textual.RichLog` — both support incremental updates | Rich / Textual |
| **Animated thinking spinner** | `Rich.Status` or `Rich.Spinner` — identical spinning ASCII patterns | Rich |
| **Markdown rendering** (headers, bold, code, lists, tables) | `Rich.Markdown` — full CommonMark support with terminal formatting | Rich |
| **Syntax-highlighted code blocks** | `Rich.Syntax` via Pygments — same language coverage as Shiki | Rich |
| **Tables** (box-drawing chars, columns, padding) | `Rich.Table` — identical visual output to Ink tables | Rich |
| **Colored permission prompts** (y/n with styling) | `Rich.Confirm` or custom `prompt_toolkit` prompts | Rich / prompt_toolkit |
| **6 theme support** (dark/light/colorblind/ANSI-only) | Rich respects terminal theme, supports forced color modes | Rich |
| **Multi-line input** with Shift+Enter | `prompt_toolkit` with `multiline=True` — full Emacs/Vi keybindings | prompt_toolkit |
| **Command history** (up/down, Ctrl+R search) | `prompt_toolkit.FileHistory` — persistent cross-session history | prompt_toolkit |
| **Tab completion** for commands/tools | `prompt_toolkit` completers — custom word, path, fuzzy matching | prompt_toolkit |
| **Vim keybindings** in input | `prompt_toolkit` vi mode — full modal editing | prompt_toolkit |
| **Panel/box borders** around content | `Rich.Panel` — identical box-drawing character rendering | Rich |
| **Tree views** (file trees, memory hierarchy) | `Rich.Tree` — static rendering with guide lines | Rich |
| **Error display** (red ANSI, context info) | `Rich.Console` with `style="red"` — trivial | Rich |
| **Progress bars** (for long operations) | `Rich.Progress` — multi-bar, ETA, transfer speed | Rich |
| **Verbose/debug mode toggle** | Print additional trace info, trivial to implement | Any |

### Can Match With Some Effort ⚠️

| Claude Code Feature | Gap | Mitigation |
|---|---|---|
| **Persistent status bar** (bottom of screen, live updating) | Rich's `Live` isn't a true footer. Textual has `Footer` widget but requires full TUI mode. | **Option A:** Use ANSI escape codes to pin a line at terminal bottom (manual but works). **Option B:** Use Textual in "app mode" for full layout control. **Option C:** Rich `Live` with a custom layout that reserves the bottom row. |
| **Colored diff display** (+ green, - red, context gray) | No built-in diff renderer in Rich/Textual. | Generate unified diff with `difflib`, apply Rich syntax styling per line. ~50 lines of code. Or shell out to `delta`/`diff-so-fancy` for rendering. |
| **Plan mode UI** (read-only indicator, plan display, approval flow) | Not a rendering problem — it's a state machine. | Implement as a mode flag that changes the prompt indicator and restricts tool execution. Visual indicator in status line: `⏸ plan mode`. |
| **External editor integration** (Ctrl+G opens $EDITOR) | prompt_toolkit supports this natively via `open_in_editor` binding. | Configure `prompt_toolkit` with `enable_open_in_editor=True`. Works out of the box. |
| **Auto-complete suggestions** (ghost text below input) | prompt_toolkit supports auto-suggestions (history-based). | `AutoSuggestFromHistory()` provides ghost-text completions. Custom suggesters possible. |

### Cannot Fully Match ❌ (But Acceptable)

| Claude Code Feature | Why | Impact |
|---|---|---|
| **Cell-level terminal diffing** (only redraws changed chars) | Ink's React reconciler + Yoga does character-level diffing. Rich/Textual diff at the line level. | Slightly more flicker on rapid updates. Imperceptible at normal LLM streaming speeds (~50 tokens/sec). Not a real problem. |
| **React component composition** (reusable UI atoms) | Textual has widgets but Python's terminal UI composition is less elegant than JSX. | Functional, just less developer-ergonomic. End-user sees no difference. |
| **Smooth 120fps animations** | Textual claims 5-10x faster than curses but terminal output is inherently frame-limited. | At LLM output speeds, this is irrelevant. Spinner animations are smooth enough in Rich. |

---

## Recommended Stack (Updated)

Based on the feasibility analysis, there are two viable approaches:

### Approach A: Rich + prompt_toolkit (REPL-first)

```
┌──────────────────────────────────┐
│  prompt_toolkit                  │  ← Input layer (multi-line, history, completion, vi mode)
├──────────────────────────────────┤
│  Rich                            │  ← Output layer (markdown, code, tables, spinners, streaming)
├──────────────────────────────────┤
│  Custom ANSI status line         │  ← Status bar (mode, cloud state, memory count, server health)
├──────────────────────────────────┤
│  httpx (async)                   │  ← API client (SSE streaming to Hestia backend)
└──────────────────────────────────┘
```

**Pros:** Lightweight (~4 dependencies). Fast startup. Familiar REPL feel. Each library does one thing well.
**Cons:** Status bar requires manual ANSI wrangling. No complex layouts (split panes, dashboards).

### Approach B: Textual (TUI-first)

```
┌──────────────────────────────────┐
│  Textual App                     │  ← Full TUI framework
│  ├── Header (status bar)         │
│  ├── RichLog (streaming output)  │
│  ├── TextArea (multi-line input) │
│  └── Footer (shortcuts, mode)    │
├──────────────────────────────────┤
│  httpx (async)                   │  ← API client
└──────────────────────────────────┘

```

**Pros:** Native async. True persistent status bar. CSS-based theming. Can evolve into dashboard mode (split panes for memory browser, knowledge graph, health data). Widget composition.
**Cons:** Heavier (~10 dependencies). Steeper learning curve. Full-screen app (less "terminal-native" feel than a REPL).

### Recommendation: **Approach A for v1, Approach B for v2/dashboard mode**

Start with Rich + prompt_toolkit for the core REPL experience. It's closer to how Claude Code *feels* (you're still in your terminal, not in a full-screen app). Add Textual later for an optional dashboard/monitoring mode.

---

## What Each Visual Element Looks Like in Python

### Streaming Response (Rich.Live)

```python
from rich.live import Live
from rich.markdown import Markdown

with Live(auto_refresh=True) as live:
    buffer = ""
    async for chunk in stream_response():
        buffer += chunk
        live.update(Markdown(buffer))
```

### Thinking Spinner (Rich.Status)

```python
with console.status("[bold cyan]Thinking...", spinner="dots"):
    response = await hestia_chat(message)
```

### Tool Approval Prompt (Rich.Confirm + Panel)

```
╭─ Tool Execution ──────────────────────────╮
│  🔧 calendar_today                        │
│  Fetches today's calendar events           │
╰────────────────────────────────────────────╯
Execute? [y/N]:
```

### Permission-Gated Tool Output

```
╭─ Result: calendar_today (1.2s) ────────────╮
│  📅 3 events today:                         │
│    • 10:00 AM — Team standup (30min)        │
│    • 1:00 PM — Design review (1hr)          │
│    • 4:00 PM — 1:1 with manager (30min)     │
╰─────────────────────────────────────────────╯
```

### Status Line (ANSI escape)

```
[tia] cloud:smart │ mem:1,247 │ health:2h ago │ ctx:12% │ server:✓
```

### Mode Switch Indicator

```
> @mira explain temporal decay

🦉 Switching to Artemis (teaching mode)...
```

### Plan Mode

```
⏸ PLAN MODE — read-only, no tool execution
> analyze the council system and propose improvements

📋 Plan:
  1. Read council/manager.py to understand current architecture
  2. Review council prompt templates
  3. Check test coverage for dual-path routing
  4. Propose improvements with tradeoffs

Approve plan? [Y/n/edit]:
```

### Diff Display (custom with Rich)

```python
from rich.syntax import Syntax
from rich.text import Text

# Green for additions, red for removals
for line in diff_lines:
    if line.startswith('+'):
        console.print(Text(line, style="green"))
    elif line.startswith('-'):
        console.print(Text(line, style="red"))
    else:
        console.print(Text(line, style="dim"))
```

---

## Gap Analysis: What Hestia CLI Adds Beyond Claude Code

Claude Code is a coding tool. Hestia CLI is a personal AI assistant that also codes. The UX gaps aren't about matching Claude Code — they're about the features Claude Code doesn't have:

| Feature | Claude Code | Hestia CLI |
|---|---|---|
| Persona/mode system | ❌ | ✅ `@tia`, `@mira`, `@olly` with distinct behavior |
| Long-term memory | ❌ (session-only) | ✅ ChromaDB + temporal decay across sessions |
| Proactive briefings | ❌ | ✅ `/briefing` with calendar, health, inbox |
| Health data access | ❌ | ✅ HealthKit metrics, coaching, trends |
| Knowledge graph | ❌ | ✅ Research graph + principle store |
| Apple ecosystem tools | ❌ | ✅ Calendar, Reminders, Notes, Mail |
| URL investigation | ❌ (WebFetch only) | ✅ Full article/YouTube analysis pipeline |
| Multiple inference backends | ❌ (Anthropic only) | ✅ Local Ollama + Anthropic + OpenAI + Google |
| Privacy control | ❌ | ✅ `force_local` flag, cloud routing states |

---

## Bottom Line

The Python terminal ecosystem can reproduce Claude Code's visual UX with high fidelity. The combination of Rich (output) + prompt_toolkit (input) covers every major visual pattern. The 10% gap (cell-level diffing, React composition elegance) is invisible to end users at normal LLM interaction speeds.

The harder engineering work isn't the rendering — it's the **streaming backend** (SSE endpoint), **session persistence**, and **tool approval state machine**. Those are backend/orchestration problems, not UI problems.
