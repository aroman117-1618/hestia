# Hestia Master Roadmap: Sprints 7–14

**Created:** 2026-03-03
**Status:** APPROVED (Discovery Complete)
**Owner:** Andrew Lonati
**Architect:** Claude (Discovery Agent)

---

## Vision

Transform Hestia from a functional backend with partial UI wiring into a fully live, real-time, editable, persistent application — and simultaneously weave in the Neural Net Learning Cycle so that every interaction makes Hestia smarter, quieter, and more anticipatory.

## Key Decisions (from Discovery Session)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| MIND.md / BODY.md format | Freeform markdown editor | Maximum flexibility, developer-oriented |
| Agent API version | V2 only (.md-based) | Cleaner, more flexible, supports custom files |
| Agent customization depth | Identity + Personality tabs | Power-user friendly without overwhelming |
| Settings layout | Accordion (4 sections) | Profile, Agents, Resources, Field Guide |
| Resources strategy | Replace/consolidate Cloud+Integrations+Devices | Eliminate duplication |
| Graph data model | Hybrid knowledge + activity | Richest visualization, foundation for Learning Cycle |
| File browser scope | Full Finder + configurable hide-list | Maximum power with privacy controls |
| Email scope | Apple Mail (read-only) + Gmail (read-only) first | Covers 90% of use cases. Compose/send deferred to 9C. Outlook deferred. |
| File CRUD scope | Full CRUD on supported types | Read all, create/edit/delete with JWT auth |
| Chat input style | CLI hybrid (terminal input, rich output) | Claude Code-inspired input, Cowork-level output |
| Avatar design | Floating header with swap animation | Personality-forward, clean |
| Background sessions | Continue if bandwidth allows, else park | Adaptive concurrency |
| Session management location | Inside Orders (Scheduled section) | Unified task management |
| Order statuses | drafted → scheduled → working → completed | Clear lifecycle |
| Metrics display | Contextual auto-switch (Personal ↔ System) | Smart, saves space |
| Calendar layout | Week grid (7-day overview) | Planning-oriented |
| Order creation | Multi-step wizard (sheet/modal) | Guided flow for complex orders |
| Health data priority | HealthKit first, nutrition later | Ship what exists, add incrementally |
| Whoop integration | Scope it in (confirmed: Strain/Recovery/5-stage sleep NOT in HealthKit) | Unique data value |
| Labs & prescriptions | Manual + Apple Health Records (FHIR) | Practical start + automated future |
| Health AI analysis | Daily briefing integration | Part of existing proactive system |
| Command scroll | Full scroll with sticky sections | Maximum content space |
| Delete auth level | JWT sufficient (no biometric for destructive ops) | Consistent with current API |
| Data persistence | Local cache + server sync | Better UX, offline viewing |
| Accent color | Amber globally (existing MacColors palette) | Brand consistency, Figma-derived, already in codebase |

## Sprint Overview

| Sprint | Focus | Backend | macOS Views | Tests | Days |
|--------|-------|---------|-------------|-------|------|
| **7** | Profile & Settings Restructure | 0 new endpoints | ~12 | ~42 | ~14.5 |
| **8** | Research & Graph + PrincipleStore | ~1 module, ~5 routes | ~4 | ~52 | ~13 |
| **9A** | Explorer: Files | ~1 module (routes/files.py), ~8 endpoints | ~6 | ~43 | ~8 |
| **9B** | Explorer: Inbox | ~1 module (email), ~9 endpoints | ~5 | ~35 | ~11 |
| **10** | Chat Redesign + OutcomeTracker | ~3 endpoint changes | ~5 | ~35 | ~11 |
| **11A** | Model Swap + Coding Specialist | config + routing changes | ~0 | ~18 | ~2 |
| **11.5** | Memory Pipeline + CLI Polish | ~1 module (bridge), ~3 endpoint changes | ~8 | ~136 | ~6 |
| **11B** | Command Center + MetaMonitor + Self-Healing Foundation | ~3 endpoints + bg manager + settings tools + pipeline | ~6 | ~54 | ~16 |
| **12** | Health Dashboard & Whoop | ~2 modules, ~10 endpoints | ~9 | ~65 | ~17 |
| **13** | Active Inference Foundation + Write Settings | ~1 module, ~4 endpoints + settings write tools | ~2 | ~45 | ~13 |
| **14** | Anticipatory Execution | ~3 endpoints | ~3 | ~30 | ~10 |
| **Total** | | **~9 modules, ~48 endpoints** | **~60** | **~533** | **~119.5** |

> **Revision (2026-03-05):** Sprint 11 split into 11A (Model Swap, COMPLETE) + 11.5 (Memory Pipeline + CLI Polish, INSERTED) + 11B (Command Center, deferred). Sprint 11.5 fills the missing Inbox→Memory pipeline and adds 136 tests. Total: +8 days, +154 tests over previous revision.

> **Audit revision (2026-03-03):** Sprint 9 split into 9A (Files) + 9B (Inbox). Effort estimates revised upward across all sprints based on codebase verification. Test counts increased per audit recommendations. Total: +8 days over original, +118 tests.

## Neural Net Learning Cycle Threading

The Learning Cycle isn't a separate workstream — it's woven into the sprint fabric:

```
Sprint 7:   Profile & Settings               ← Foundation (settings for all future config)
Sprint 8:   Research & Graph + PrincipleStore ← Learning Cycle Phase A (part 1)
Sprint 9A:  Explorer: Files                   ← Data breadth (file behavioral signals)
Sprint 9B:  Explorer: Inbox                   ← Data breadth (email behavioral signals)
Sprint 10:  Chat Redesign + OutcomeTracker    ← Learning Cycle Phase A (part 2)
        ↳ Phase 0: Timezone fix (pre-11)      ← Bug fix: timezone-aware datetime throughout
Sprint 11A: Model Swap + Coding Specialist    ← Dual model (qwen3.5:9b + qwen2.5-coder:7b), ADR-040
Sprint 11.5A: Memory Pipeline + Research Wire ← INSERTED: Inbox→Memory ingestion (fills 9B→8 gap)
        ↳ InboxMemoryBridge (encrypted, deduped, sanitized)
        ↳ DataSource filters wired to real source data
        ↳ Principles auto-distill + daily background task
Sprint 11.5B: CLI + Agent Polish              ← INSERTED: Agent theming, fire animation, device wizard
Sprint 11B: Command + MetaMonitor             ← Learning Cycle Phase B + Self-Healing Foundation
        ↳ +11.8a: Read settings tools          ← Tia can diagnose her own config
        ↳ +11.8b: Outcome→Principle pipeline   ← Corrections become knowledge (hybrid threshold)
        ↳ +11.8c: Correction classification    ← Categorize mistake types
Sprint 12:  Health & Whoop                    ← Personal state data for world model
Sprint 13:  Active Inference Foundation       ← Learning Cycle Phase C (part 1)
        ↳ +13.4: Write settings tools          ← Tia can apply corrections (SUGGEST gate)
        ↳ +13.4: CorrectionConfidence scoring  ← Future auto-apply framework
Sprint 14:  Anticipatory Execution            ← Learning Cycle Phase C (part 2)
        ↳ Granular ActionRisk tiering          ← Replace blanket NEVER with per-category risk
```

## Timeline

**Realistic estimate** at ~6 hours/week (per audit 2026-03-03):
- **Total effort:** ~111.5 working days (~669 hours)
- **At 6hr/week:** 669hr ÷ 6hr = 111.5 weeks ≈ **26 calendar months**
- **At 80% efficiency:** ~21 calendar months
- **At 12hr/week (stretch):** ~11 calendar months

> ⚠️ **Audit finding (2026-03-03):** The original "~9 months" estimate assumed ~6.7 working days/week. With the Sprint 9 split (9A + 9B) and revised effort estimates, the corrected math yields 21–26 months at current capacity. Plan accordingly — either accept longer timeline or increase weekly hours.

**Recommended pace:** 2-week sprint cycles with demo/review between each.

### Decision Gates (Go/No-Go Checkpoints)

| Gate | After Sprint | Decision |
|------|-------------|----------|
| **Gate 1** | Sprint 8 | Is PrincipleStore producing useful principles? Is ChromaDB performing well with 3 collections? → Go/No-Go on continuing learning cycle |
| **Gate 2** | Sprint 10 | Is OutcomeTracker collecting meaningful signals? Memory + CPU profile acceptable on M1? → Go/No-Go on MetaMonitor (Sprint 11) |
| **Gate 3** | Sprint 12 | Is health data integration worth the compliance burden? Is Whoop approved? → Go/No-Go on Active Inference (Sprints 13-14) vs. simplified pattern matching |

## Cross-Cutting Concerns

### Data Flow (All Modules)
```
macOS UI → Local Cache → FastAPI (8443) → SQLite/ChromaDB/Keychain
```
Cache strategy: local for reads, server-first for writes, ETag invalidation.

### Design System: Amber Accent
Extend existing Figma-derived amber palette in `MacColors.swift` (`amberAccent` E0A050, `amberBright` FFB900, `amberDark` FF8904):

**Existing tokens (no change needed):** `amberAccent`, `amberBright`, `amberDark`, `accentColor(for mode:)` (mode-dependent).

**Audit additions (2026-03-03):**
- `amberOnLight` (#B8860B) — WCAG AAA-compliant variant for text on light backgrounds (7.0:1 ratio). Use for body text and labels.
- Interactive state tokens: `hoverBackground` (amberAccent at 12% opacity), `pressedBackground` (amberAccent at 20% opacity), `disabledForeground` (0.38 opacity), `focusRing` (amberBright)
- Semantic status colors: Reuse existing `healthGreen` (success), `healthRed` (error), `healthGold`/`healthAmber` (info). Add `statusWarning` (#FF9800) and `statusCritical` (#D32F2F) only.
- Animation timing tokens: `animationFast` (0.15s), `animationNormal` (0.25s), `animationSlow` (0.4s)

> ⚠️ E0A050 on white ≈ 3.0:1 contrast. Use `amberOnLight` (#B8860B) for text. `amberAccent` is for decorative/interactive elements only.

### Security
- JWT auth sufficient for all CRUD (including deletes)
- Path traversal protection on file system endpoints — **allowlist-first approach** (only `ALLOWED_ROOTS` accessible, deny everything else)
- Path validation uses `os.path.realpath()` at read time (not just validation time) to prevent TOCTOU race conditions
- Gmail/Whoop OAuth2 tokens in Keychain — **`sensitive` credential tier** (Fernet + Keychain)
- Clinical data carries "not medical advice" disclaimers — **enforced via post-processing filter**
- File delete operations logged to audit trail with undo capability (`.hestia-trash/`)
- Shared `OAuthManager` base class for Gmail (Sprint 9B) and Whoop (S12) — extract before Sprint 9B

### Health Data Compliance
- Data retention policy required before Sprint 12 (define max retention, user deletion flow)
- PII scrubbing on lab PDF extraction (strip SSN, DOB, address — store only clinical values)
- AuditLogger events for all `/v1/health_data/*` and `/v1/whoop/*` endpoints
- HealthKit data must not leave device — health analysis prompts use aggregated summaries, not raw values
- `HealthDataSanitizer` strips raw values from LLM prompts

### Architecture Documentation (Pre-Sprint 8)
- `docs/architecture/learning-cycle-dataflow.md` — PrincipleStore → OutcomeTracker → MetaMonitor → WorldModel pipeline
- `docs/architecture/chromadb-collections.md` — Collection naming, embedding model selection, query isolation strategy

## Testing Strategy (Audit Additions)

**Recommended test count increase:** 221 planned → 379 minimum (+158 tests across all sprints).

| Sprint | Planned Tests | Recommended Minimum | Key Additions |
|--------|--------------|--------------------|----|
| 7 | 28 | 42 | Cache invalidation, accordion state, photo crop edges, empty states, undo/redo |
| 8 | 35 | 52 | ChromaDB isolation, principle dedup, graph stress, review lifecycle, empty graph |
| 9A | 30 | 43 | Security (symlink, escape, TOCTOU, null byte), file audit, executable MIME |
| 9B | 25 | 35 | OAuth edge cases, token rotation, read-only scope, provider health |
| 10 | 24 | 37 | XSS prevention, migration, OutcomeTracker edges |
| 11 | 32 | 42 | MetaMonitor false positives, cold start, wizard validation |
| 12 | 51 | 65 | PDF negatives, Whoop rate limits, clinical validation, disclaimers |
| 13 | 25 | 38 | Numerical stability, layer frequency, cold start |
| 14 | 20 | 32 | Risk boundaries, regime hysteresis, dismissal persistence |

**Infrastructure:**
- Add pytest markers: `@pytest.mark.security`, `@pytest.mark.integration`, `@pytest.mark.performance`
- Create `tests/fixtures/` directory with sample data (lab PDFs, email templates, OAuth responses) before Sprint 9
- Consider `pytest-xdist` for parallel execution when test count exceeds 1500

## Dependency Chain

```
Sprint 7 (CacheManager, MarkdownEditor, Design Tokens)
    ├── Sprint 8 (PrincipleStore, GraphBuilder) ← uses ChromaDB, reuses MarkdownEditor
    │   └── Sprint 11.5A (Memory Pipeline) ← enriches graph with multi-source data
    │       └── Sprint 13 (WorldModel) ← consumes PrincipleStore + multi-source memory
    ├── Sprint 9A (Explorer: Files) ← uses CacheManager, routes/files.py
    │   └── Sprint 9B (Explorer: Inbox) ← uses CacheManager, OAuthManager base class
    │       ├── Sprint 11.5A (InboxMemoryBridge) ← bridges inbox → memory pipeline
    │       └── Sprint 12 (Whoop, Clinical) ← reuses OAuthManager from 9B
    ├── Sprint 10 (Chat, OutcomeTracker) ← reuses MarkdownEditor, CacheManager
    │   └── Sprint 11B (MetaMonitor) ← consumes OutcomeTracker data + multi-source memory
    │       └── Sprint 13-14 (Active Inference) ← consumes MetaMonitor + OutcomeTracker + PrincipleStore
    └── Sprint 12 (Health) ← uses CacheManager, extends health module
```

**Critical path:** 7 → 10 → 11.5A → 11B → 13 → 14. Sprint 11.5A enriches the data landscape for all downstream Learning Cycle phases. Any delay in OutcomeTracker or MetaMonitor cascades to Active Inference.

## Known Risks (Top 5)

1. **Effort estimate ~2× optimistic** — Plan for 18–24 months, not 9
2. **Sprint 9A/9B security surface** — File CRUD (9A) + OAuth (9B) = largest attack surface. Dedicated security review required at 9A completion gate
3. **M1 16GB memory ceiling** — Profile at Sprint 10 completion. Defer graph viz if >12GB used
4. **Whoop developer access** — Apply immediately; design module as optional
5. **Active Inference theoretical risk** — Decision gate after Sprint 12; have simplified fallback (heuristics)

## Detailed Plans

Each sprint has its own detailed plan document:

| Sprint | Plan Document |
|--------|---------------|
| 7 | [sprint-7-profile-settings-plan.md](sprint-7-profile-settings-plan.md) |
| 8 | [sprint-8-research-graph-plan.md](sprint-8-research-graph-plan.md) |
| 9A + 9B | [sprint-9-explorer-files-inbox-plan.md](sprint-9-explorer-files-inbox-plan.md) |
| 10 | [sprint-10-chat-redesign-plan.md](sprint-10-chat-redesign-plan.md) |
| 11A | [2026-03-05-sprint-11a-model-swap.md](2026-03-05-sprint-11a-model-swap.md) |
| 11.5 | [sprint-12-plan-audit-2026-03-05.md](sprint-12-plan-audit-2026-03-05.md) |
| 11B | [sprint-11-command-center-plan.md](sprint-11-command-center-plan.md) |
| 12 | [sprint-12-health-whoop-plan.md](sprint-12-health-whoop-plan.md) |
| 13–14 | [sprint-13-14-learning-cycle-plan.md](sprint-13-14-learning-cycle-plan.md) |

## Related Documents

| Document | Location |
|----------|----------|
| Discovery (full analysis + SWOT) | `docs/discoveries/ui-wiring-discovery-roadmap.md` |
| Neural Net Learning Cycle Research | `docs/discoveries/neural-net-learning-cycle-research.md` |
| API Contract | `docs/api-contract.md` |
| Decision Log | `docs/hestia-decision-log.md` |
| Sprint Tracker | `SPRINT.md` |
| Sprint 7–9 Audit | `docs/plans/sprint-7-9-audit-2026-03-03.md` |
