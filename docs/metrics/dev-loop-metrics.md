# Development Loop Metrics

Rolling log of per-session development efficiency metrics. Appended by `/handoff` Phase 3f.

---

<!-- Each session appends a new entry below this line -->

## 2026-03-20 — Sprint 31 + Caching + Server HA
- **First-pass success**: 8/10 tasks (80%)
- **Rework causes**: Swift 6 @Sendable closure, `body` variable name collision
- **Top blocker**: Sub-agents touching files outside scope
- **Hook catches**: 0 (issues caught at build time)
- **Config proposals**: 4 generated, 0 applied (deferred)
- **Releases**: 4 (v1.1.0, v1.1.1, v1.1.2, HA infra push)
- **Second opinions**: 3 (macOS wiring, caching, server HA)
- **Sub-agents dispatched**: ~20

## 2026-03-20 (continued) — SystemHealth bugfix + Command Center wiring audit
- **First-pass success**: 4/6 tasks (67%)
- **Rework causes**: CodingKeys + convertFromSnakeCase double-conversion (2 rounds to find real root cause), Swift 6 Sendable conformance
- **Top blocker**: Silent JSON decode failures — CacheFetcher catches all errors, making it impossible to see what's failing without temporary debug logging
- **Hook catches**: 0
- **Config proposals**: 1 (CLAUDE.MD: document convertFromSnakeCase + CodingKeys incompatibility)
- **Key learning**: Never use explicit CodingKeys with snake_case raw values when the decoder uses convertFromSnakeCase — they conflict. This wasted ~30 min of debugging.
