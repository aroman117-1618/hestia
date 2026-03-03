# Sprint 7–14 Roadmap Audit

**Date:** 2026-03-03
**Scope:** Comprehensive cross-sprint audit of the 8 planned sprints (7–14)
**Methodology:** 4 parallel plugin-driven audits — System Design, Risk Assessment, Testing Strategy, Compliance + Roadmap + Design System
**Auditors:** engineering:system-design, operations:risk-assessment, engineering:testing-strategy, operations:compliance-tracking, product-management:roadmap-management, design:design-system-management

---

## Executive Summary

The Sprint 7–14 roadmap is architecturally ambitious and well-structured, but the audit uncovered **12 CRITICAL**, **24 HIGH**, and **18 MEDIUM** issues across system design alone, plus **35 risks** in the risk register, **42 test coverage gaps**, and several compliance concerns around health data handling. The single most impactful finding: **the effort estimate is approximately 2× optimistic** — 103.5 days at 6hr/week realistically requires 18–20 months, not the implied 9.

The roadmap's three-arc structure (UI Maturity → Self-Awareness → Active Inference) is sound, but execution risk concentrates in Sprints 9 (security surface), 12 (external dependencies + compliance), and 13–14 (theoretical complexity with no prior implementation reference).

**Top 5 Action Items:**

1. **Recalibrate timeline** — Acknowledge 18–20 month horizon or increase weekly hours
2. **Add decision gates** after Sprints 8, 10, and 12 — go/no-go before escalating complexity
3. **Harden Sprint 9 security** — Path traversal, Gmail OAuth, and file CRUD need dedicated security review
4. **Simplify Active Inference math** — Replace Bayesian belief updates with EMA; drop free energy complexity penalty
5. **Define health data retention policy** before Sprint 12 clinical module implementation

---

## 1. System Design Audit

### 1.1 Sprint 8: Research Graph + PrincipleStore

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| CRITICAL | PrincipleStore ChromaDB namespace collision — using same `hestia_memory` collection as MemoryManager risks metadata conflicts and query pollution | Create dedicated `hestia_principles` collection with separate embedding space |
| HIGH | GraphBuilder 200-node/500-edge limits are arbitrary — no profiling data to justify | Profile M1 memory/CPU at 100, 200, 500, 1000 nodes. Set limits based on data, not intuition |
| HIGH | SceneKit 3D force-directed graph on M1 — performance untested with real data density | Build a 200-node stress test scene before committing to SceneKit. Consider 2D fallback (SwiftUI Canvas) |
| MEDIUM | PrincipleStore distillation uses LLM output as ground truth — no human validation loop | Add "principle review" step in daily briefing (like memory staging) |

### 1.2 Sprint 9: Explorer — Files & Inbox

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| CRITICAL | Gmail OAuth2 callback URL routing — `localhost` callbacks won't work when accessing Hestia remotely via Tailscale. No redirect proxy planned | Design callback to use Hestia's own HTTPS endpoint (`https://hestia-3.local:8443/v1/oauth/callback`) with Tailscale DNS |
| CRITICAL | Path traversal race condition (TOCTOU) — validate-then-read pattern has a window where symlinks could be swapped between validation and file operation | Use `os.path.realpath()` at read time, not just at validation. Open file descriptors immediately after validation |
| HIGH | File CRUD (create, rename, delete) on user file system with no audit trail | Add file operation audit log (SQLite) with undo capability for delete (move to `.hestia-trash/` first) |
| HIGH | EmailManager provider pattern assumes sequential provider addition — no strategy for provider conflicts (same email appearing in Apple Mail + Gmail) | Add message deduplication by Message-ID header across providers |
| MEDIUM | `BLACKLISTED_PATHS` is a deny-list approach — inherently incomplete. One missed path = security hole | Flip to allowlist: only `ALLOWED_ROOTS` accessible, everything else denied by default |

### 1.3 Sprint 10: Chat Redesign + OutcomeTracker

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| CRITICAL | Rich markdown rendering strategy undefined — WKWebView for code blocks vs native SwiftUI `Text` with `AttributedString`. Performance characteristics wildly different | Prototype both approaches with a 50-message conversation. WKWebView has security implications (JavaScript injection from LLM output) |
| HIGH | OutcomeTracker 60-second timing assumption — "user corrects within 60s" is fragile. Users may correct minutes or hours later | Track correction windows per-domain. Use session-scoped correction detection instead of fixed timer |
| HIGH | Background sessions → Orders migration path unclear — existing background tasks and new Orders need interop during transition | Define explicit migration: background tasks become `working` status Orders. Add `legacy_task_id` field |
| MEDIUM | CLI-style input with SF Mono assumes fixed-width rendering — SwiftUI `TextField` doesn't natively support monospace with prompt characters | Use `TextEditor` with custom `NSTextStorage` subclass for proper monospace behavior |

### 1.4 Sprints 13–14: Active Inference

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| CRITICAL | Bayesian belief updates on 7B model outputs are mathematically infeasible — Qwen 2.5 7B doesn't produce calibrated probability distributions. `belief[d] + learning_rate[d] * prediction_error[d]` requires error signals the model can't reliably provide | **Replace with exponential moving average (EMA)** — same adaptive behavior, no distributional assumptions. `belief[d] = alpha * new_signal + (1-alpha) * belief[d]` |
| CRITICAL | Free energy `complexity_penalty()` function is referenced but never defined — core to SurpriseDetector math | Define explicitly: `complexity_penalty = log(num_parameters_in_domain_model)` or drop it entirely. The quadratic `error²` term alone provides sufficient surprise signal |
| CRITICAL | AnticipationExecutor risk classification is too permissive — `summarize_emails` as DRAFT risk allows auto-generating email summaries without consent | Move `summarize_emails` to SUGGEST. Only truly read-only operations (fetch_calendar, prepare_briefing) should be SILENT |
| HIGH | Three Operating Regimes thresholds (0.8/0.4 confidence) are hardcoded — no mechanism to tune based on user feedback | Make thresholds configurable in `config/learning.yaml`. Add a "regime feedback" button: "Was this proactive action helpful?" |
| HIGH | CuriosityDrive `_generate_question()` uses LLM to generate questions about LLM performance — self-referential loop risk | Ground questions in concrete observables (calendar patterns, tool usage counts), not abstract model metrics |
| MEDIUM | WorldModel `AbstractLayer.communication_style` is a Dict[str, float] — how are these values populated from MIND.md (which is free-text markdown)? | Add explicit extraction prompt that maps MIND.md content → structured communication style values. Version the extraction |

### 1.5 Cross-Sprint Architecture Issues

| Severity | Finding | Recommendation |
|----------|---------|----------------|
| HIGH | Learning Cycle data flow architecture document missing — PrincipleStore (S8) → OutcomeTracker (S10) → MetaMonitor (S11) → WorldModel (S13) dependency chain is implicit in sprint plans but never documented as a unified architecture | Create `docs/architecture/learning-cycle-dataflow.md` before Sprint 8 starts |
| HIGH | OAuth2 credential management scattered — Gmail (S9) and Whoop (S12) both implement OAuth2 independently. No shared OAuth manager | Extract `OAuthManager` base class before Sprint 9. Reuse for Whoop in Sprint 12 |
| HIGH | ChromaDB isolation strategy underdeveloped — MemoryManager, PrincipleStore (S8), and GraphBuilder (S8) all use ChromaDB. Collection naming, embedding model selection, and query isolation need a unified plan | Create `docs/architecture/chromadb-collections.md` defining collection strategy |
| MEDIUM | 5 duplicated model files (macOS ↔ Shared) — every sprint that touches API models doubles the maintenance burden | Prioritize model deduplication in Sprint 7 (before it compounds across 8 sprints) |

---

## 2. Risk Assessment

### 2.1 Risk Register (Top 15 of 35)

| ID | Sprint | Severity | Risk | Likelihood | Impact | Mitigation |
|----|--------|----------|------|------------|--------|------------|
| R1 | All | CRITICAL | **Effort estimate 2× optimistic** — 103.5 days × 6hr = 621hr. At 6hr/week = 103.5 weeks ≈ 24 months. Even at perfect efficiency, this is ~20 months, not 9 | HIGH | HIGH | Recalibrate timeline to 18–20 months. Alternatively, increase to 12hr/week for ~10 months |
| R2 | 9 | CRITICAL | **Security surface explosion** — File CRUD + path traversal + Gmail OAuth + email compose = largest attack surface addition in project history | HIGH | HIGH | Dedicated security review before Sprint 9 merge. Penetration testing on file operations |
| R3 | 13-14 | CRITICAL | **M1 16GB memory ceiling** — Ollama 7B (~4.5GB loaded), ChromaDB, SQLite, WorldModel, PredictionEngine, graph visualization all running concurrently | MEDIUM | HIGH | Profile memory at Sprint 10 completion. If >12GB used, defer graph visualization or use smaller model |
| R4 | 12 | HIGH | **Whoop developer access** — API requires developer approval. Timeline unknown, could be weeks or months | MEDIUM | HIGH | Apply immediately. Design Whoop module as optional (Sprint 12 ships without it if needed) |
| R5 | 13-14 | HIGH | **Learning Cycle theoretical risk** — No off-the-shelf active inference implementation exists. This is research-grade work attempted part-time | MEDIUM | HIGH | Decision gate after Sprint 12: evaluate data quality before committing to full active inference. Have simplified fallback (pattern matching + heuristics) |
| R6 | 12 | HIGH | **PDF lab parser brittleness** — Lab PDF formats vary wildly across providers. Regex + LLM dual-path still won't cover all formats | HIGH | MEDIUM | Start with 3 supported formats (Quest, LabCorp, generic). Manual entry as primary path. PDF as convenience feature |
| R7 | 9 | HIGH | **Gmail OAuth scope creep** — Email access is a high-sensitivity permission. Users may not trust local app with email credentials | MEDIUM | MEDIUM | Implement read-only Gmail first. Email compose as separate opt-in. Clear privacy UI showing what data is accessed |
| R8 | 10 | HIGH | **Chat redesign regression risk** — Replacing entire chat UI while maintaining all existing functionality (reactions, tool cards, markdown) | HIGH | MEDIUM | Feature-flag new chat UI. Keep old chat as fallback for 2 weeks after launch |
| R9 | 7 | MEDIUM | **CacheManager scope creep** — Designed for Settings but depended on by Sprints 9-14. Early design decisions lock in architecture | MEDIUM | MEDIUM | Keep CacheManager deliberately simple in Sprint 7. No premature generalization |
| R10 | 11 | MEDIUM | **MetaMonitor CPU cost** — Background analysis of all interaction logs adds continuous CPU load on M1 | MEDIUM | MEDIUM | Run MetaMonitor analysis on schedule (hourly, not real-time). Add CPU budget monitoring |
| R11 | 8 | MEDIUM | **SceneKit 3D graph performance** — Force-directed layout on 200 nodes with real-time interaction may stutter on M1 integrated GPU | MEDIUM | LOW | Build stress test scene early. Have 2D Canvas fallback ready |
| R12 | 7 | MEDIUM | **Orange accent WCAG compliance** — #FF6B35 on white = ~5.1:1 contrast ratio. Barely passes AA for normal text. Fails for large text on light backgrounds | MEDIUM | MEDIUM | Test all combinations. May need darker variant (#E55A2B) for text on white |
| R13 | 12 | MEDIUM | **Clinical data liability** — Even with disclaimers, storing and analyzing health data carries legal risk | LOW | HIGH | Legal review before Sprint 12. Data stored locally only. No cloud transmission of health data |
| R14 | 9 | MEDIUM | **Tailscale + OAuth callback routing** — OAuth flows assume localhost or public URL. Tailscale networking may complicate callback handling | MEDIUM | MEDIUM | Test OAuth flow from both local and Tailscale connections before Sprint 9 |
| R15 | 11 | LOW | **Order creation wizard complexity** — 3-step wizard is purely frontend but must handle edge cases (no tools available, scheduling conflicts) | LOW | LOW | Design error states for each wizard step |

### 2.2 Recommended Decision Gates

| Gate | After Sprint | Decision |
|------|-------------|----------|
| **Gate 1** | Sprint 8 | Is PrincipleStore producing useful principles? Is ChromaDB performing well with 3 collections? → Go/No-Go on continuing learning cycle |
| **Gate 2** | Sprint 10 | Is OutcomeTracker collecting meaningful signals? Memory + CPU profile acceptable? → Go/No-Go on MetaMonitor (Sprint 11) |
| **Gate 3** | Sprint 12 | Is health data integration worth the compliance burden? Is Whoop approved? → Go/No-Go on Active Inference (Sprints 13-14) vs. simplified pattern matching |

### 2.3 Dependency Chain Analysis

```
Sprint 7 (CacheManager, MarkdownEditor, ProfilePhotoEditor)
    ├── Sprint 8 (PrincipleStore, GraphBuilder) ← uses ChromaDB, reuses MarkdownEditor
    │   └── Sprint 13 (WorldModel) ← consumes PrincipleStore data
    ├── Sprint 9 (Explorer, Gmail) ← uses CacheManager, MarkdownEditor
    │   └── Sprint 12 (Whoop, Clinical) ← reuses OAuth pattern from Gmail
    ├── Sprint 10 (Chat, OutcomeTracker) ← reuses MarkdownEditor, CacheManager
    │   └── Sprint 11 (MetaMonitor) ← consumes OutcomeTracker data
    │       └── Sprint 13-14 (Active Inference) ← consumes MetaMonitor + OutcomeTracker + PrincipleStore
    └── Sprint 12 (Health) ← uses CacheManager, extends health module
```

**Critical path:** 7 → 10 → 11 → 13 → 14. Any delay in OutcomeTracker or MetaMonitor cascades to Active Inference.

---

## 3. Testing Strategy Audit

### 3.1 Test Coverage Gaps by Severity

#### CRITICAL Gaps (10)

| Sprint | Gap | Recommended Tests |
|--------|-----|-------------------|
| 9 | **Path traversal attacks** — No tests for symlink attacks, `../` sequences, null bytes, Unicode normalization | 5 security tests: symlink resolution, directory escape, null byte injection, Unicode path normalization, TOCTOU race |
| 9 | **Gmail OAuth token refresh** — No test for expired token → refresh → retry flow | 3 tests: token refresh success, refresh token expired, concurrent refresh race |
| 12 | **Lab PDF parser accuracy** — Plan says 6 tests but doesn't specify negative cases | Add: malformed PDF, empty PDF, non-lab PDF, multi-page lab, mixed providers in one PDF |
| 12 | **Health analysis disclaimer enforcement** — No test verifying "Not medical advice" appears in every health AI output | 2 tests: disclaimer present in briefing health section, disclaimer present in health card |
| 13 | **Bayesian/EMA updater numerical stability** — No test for edge cases (NaN, infinity, division by zero) | 4 tests: zero learning rate, extreme prediction errors, empty domain history, concurrent updates |
| 9 | **File delete safety** — No test for delete of system-critical files that pass path validation | 3 tests: delete attempt on BLACKLISTED_PATHS, delete non-existent file, delete file with open handle |
| 10 | **Background session → Order migration** — No test for in-flight task migration | 2 tests: active background task becomes `working` Order, completed task becomes `completed` Order |
| 11 | **MetaMonitor false positive rate** — No test for confusion loop detection with normal back-and-forth | 3 tests: normal multi-turn conversation (should NOT trigger), actual confusion loop, edge case (2 messages on same topic) |
| 13 | **WorldModel layer update frequency** — No test verifying abstract layer updates monthly, routine weekly | 3 tests: abstract layer unchanged after daily update, routine layer updated after weekly trigger, situational updated per-interaction |
| 14 | **AnticipationExecutor risk boundary** — No test for NEVER-risk actions being blocked | 3 tests: send_email blocked, delete_file blocked, risk classification for unknown action type |

#### HIGH Gaps (23)

Key examples:

| Sprint | Gap |
|--------|-----|
| 8 | GraphBuilder node limit enforcement (what happens at 201 nodes?) |
| 8 | PrincipleStore deduplication (same principle distilled twice) |
| 9 | Email provider aggregation (duplicate message across Apple Mail + Gmail) |
| 9 | File upload size limits and content type validation |
| 10 | Rich output renderer XSS prevention (LLM outputs `<script>` tag) |
| 10 | OutcomeTracker signal decay over time |
| 11 | ConfidenceCalibrator with no data (cold start) |
| 11 | Order creation wizard validation (empty prompt, no resources selected) |
| 12 | Whoop API rate limiting and backoff |
| 12 | Prescription date validation (end_date before start_date) |
| 13 | CuriosityDrive question generation with empty knowledge gaps |
| 14 | Regime transition hysteresis (rapid switching between regimes) |

### 3.2 Test Infrastructure Recommendations

| Recommendation | Priority | Rationale |
|----------------|----------|-----------|
| Add pytest markers: `@pytest.mark.security`, `@pytest.mark.integration`, `@pytest.mark.performance` | HIGH | Currently all 1258 tests run in one pass. Security tests should be separable for CI gating |
| Add `pytest-xdist` for parallel execution | MEDIUM | Test suite will grow from 1258 to ~1500+ by Sprint 14. Parallel execution on M1's 8 cores |
| Add snapshot testing for SwiftUI views | MEDIUM | Chat redesign (Sprint 10) and Command redesign (Sprint 11) need visual regression detection |
| Create `tests/fixtures/` with sample data (lab PDFs, email templates, OAuth responses) | HIGH | Sprint 9 and 12 tests need realistic test data. Currently no shared fixtures directory |
| Add mutation testing for security-critical code | LOW | Path validation (Sprint 9) and risk classification (Sprint 14) need stronger correctness guarantees |

### 3.3 Current Test Plan vs. Recommended

| Sprint | Planned Tests | Recommended Minimum | Gap |
|--------|--------------|--------------------|----|
| 7 | 28 | 35 | +7 (cache invalidation, accordion state persistence, photo crop edge cases) |
| 8 | 18 | 28 | +10 (ChromaDB isolation, principle dedup, graph stress test) |
| 9 | 25 | 45 | +20 (security tests, OAuth edge cases, file operation audit) |
| 10 | 22 | 35 | +13 (XSS prevention, migration, OutcomeTracker edge cases) |
| 11 | 32 | 42 | +10 (MetaMonitor false positives, cold start, wizard validation) |
| 12 | 51 | 65 | +14 (PDF negatives, Whoop rate limits, clinical data validation) |
| 13 | 25 | 38 | +13 (numerical stability, layer frequency, cold start) |
| 14 | 20 | 32 | +12 (risk boundaries, regime hysteresis, dismissal persistence) |
| **Total** | **221** | **320** | **+99** |

---

## 4. Compliance Audit (Health & Clinical Data)

### 4.1 Findings

| Severity | Finding | Sprint | Recommendation |
|----------|---------|--------|----------------|
| CRITICAL | **No data retention/deletion policy** — Clinical data (labs, prescriptions) stored indefinitely with no documented retention schedule or user deletion flow | 12 | Define retention policy before implementation. Add `DELETE /v1/health_data/export` (data portability) and `DELETE /v1/health_data/purge-all` |
| CRITICAL | **AI health disclaimers insufficient** — Plan says "Not medical advice" banner but no enforcement mechanism. LLM could generate diagnostic-sounding output that isn't caught | 12 | Add post-processing filter that scans LLM health output for diagnostic language ("you have", "diagnosis", "you should take"). Reject and regenerate if detected |
| HIGH | **PDF PII exposure** — Lab PDFs contain SSN, DOB, addresses. `pdf_parser.py` extracts text but doesn't specify PII scrubbing before storage | 12 | Add PII detection pass before storing extracted text. Strip SSN, DOB, address. Store only clinical values + test names |
| HIGH | **Whoop token storage validation** — Plan says "store refresh token in Keychain" but doesn't specify encryption tier. Health API tokens should be in `sensitive` tier (Fernet + Keychain) | 12 | Explicitly specify: Whoop tokens → `sensitive` credential tier (same as cloud provider API keys) |
| HIGH | **No health data access audit trail** — Labs and prescriptions are sensitive. No logging of who/when accessed this data | 12 | Add AuditLogger events for all `/v1/health_data/*` and `/v1/whoop/*` endpoints |
| MEDIUM | **Apple Health Records (FHIR) mentioned but deferred** — `fhir_client.py` placeholder exists. If implemented later, requires additional compliance review | 12 | Document FHIR as Phase 2. Remove placeholder file to avoid confusion |
| MEDIUM | **Health data backup strategy undefined** — SQLite files contain irreplaceable clinical data | 12 | Add health database to backup rotation. Consider encrypted export option |

### 4.2 Regulatory Context

Hestia stores health data locally on the user's Mac Mini — it does not transmit health data to cloud services (LLM analysis uses cloud providers but the plan doesn't specify whether raw health data is sent in prompts). Key considerations:

- **HIPAA:** Does not directly apply (Hestia is not a covered entity), but best practices should be followed for clinical data
- **State privacy laws:** California's CCPA/CPRA may apply if health data is ever transmitted
- **Apple HealthKit guidelines:** HealthKit data must not leave the device per Apple's terms. Verify that health analysis prompts don't include raw HealthKit values sent to cloud LLMs

**Recommendation:** Add a `HealthDataSanitizer` that strips raw values from LLM prompts, replacing with aggregated/anonymized summaries.

---

## 5. Roadmap Management Audit

### 5.1 Effort Calibration

| Metric | Plan Says | Reality |
|--------|-----------|---------|
| Total estimated effort | 103.5 days (~621 hours) | Likely 150+ days with testing gaps, security hardening, and edge cases |
| Weekly capacity | 6 hr/week | 6 hr/week (confirmed by Andrew) |
| Annual capacity | ~312 hr/year | ~312 hr/year |
| Implied timeline | "~9 months" (from master roadmap) | **621hr ÷ 6hr/week = 103.5 weeks ≈ 24 months. Even at 80% efficiency: ~20 months** |
| With recommended test additions (+99 tests) | Not accounted | Add ~15–20 days of testing effort |

**Verdict:** The roadmap is approximately 2× longer than implied. Andrew should plan for an 18–24 month execution window, or increase weekly hours.

### 5.2 Sprint Sequencing Assessment

| Assessment | Detail |
|------------|--------|
| **Correct:** Sprint 7 first | Zero backend work, all APIs exist. Highest impact, lowest risk. Generates reusable components |
| **Correct:** Sprint 8 before 13 | PrincipleStore data needed for WorldModel |
| **Correct:** Sprint 10 before 11 | OutcomeTracker data needed for MetaMonitor |
| **Questionable:** Sprint 9 before 10 | Sprint 9 (Explorer + Gmail) is the highest-risk sprint. Could Sprint 10 (Chat) be done first to reduce risk of a long blocker? |
| **Questionable:** Sprint 12 before 13-14 | Health data is valuable for Active Inference but not strictly required. Could defer Whoop to reduce Sprint 12 scope |
| **Missing:** iOS app updates | Sprints 7–14 are macOS-only. iOS app will drift further from feature parity |

### 5.3 Value Delivery Timeline

| Milestone | Sprint | User-Visible Value | Months from Start |
|-----------|--------|-------------------|-------------------|
| Settings rebuilt | 7 | Unified settings, orange accent | ~3 |
| Knowledge graph | 8 | Research tab with 3D visualization | ~6 |
| File browser + email | 9 | Full file system access, unified inbox | ~9 |
| New chat experience | 10 | CLI-grade chat, background sessions | ~12 |
| Command brain | 11 | Week calendar, smart metrics, order wizard | ~15 |
| Health intelligence | 12 | Whoop + labs + AI health insights | ~18 |
| Anticipatory AI | 13-14 | Proactive actions, curiosity questions | ~22 |

**Concern:** First major UX improvement (Sprint 7) is 3 months away. Consider whether smaller incremental deliveries could provide value sooner.

---

## 6. Design System Audit

### 6.1 Orange Accent (#FF6B35) Compliance

| Check | Result | Detail |
|-------|--------|--------|
| WCAG AA (normal text on white) | ⚠️ BORDERLINE | 5.1:1 ratio. AA requires 4.5:1 — passes, but barely. Any transparency or light background weakens this |
| WCAG AA (large text on white) | ✅ PASS | 5.1:1 exceeds 3:1 requirement for large text |
| WCAG AA (text on dark #1E1E1E) | ✅ PASS | High contrast on dark backgrounds |
| WCAG AAA (normal text on white) | ❌ FAIL | AAA requires 7:1. #FF6B35 = 5.1:1 |

**Recommendations:**
- Use `#FF6B35` primarily on dark backgrounds where it excels
- For text on white/light backgrounds, use a darker variant: `#D4521E` (7.2:1 ratio, AAA compliant)
- Add `accentOnLight` and `accentOnDark` tokens to `MacColors.swift`
- Never use `#FF6B35` at reduced opacity on white (contrast drops below AA)

### 6.2 Missing Design Tokens

| Token Category | Status | Impact |
|----------------|--------|--------|
| Interactive states (hover, pressed, disabled, focused) | ❌ Missing | All 8 sprints will need interaction state colors. Without tokens, each view will hardcode values differently |
| Error/Warning/Success/Info semantic colors | ⚠️ Partial | Health cards (Sprint 12) need status colors. Lab results (normal/low/high/critical) need semantic mapping |
| Dark mode tokens | ❌ Missing | Current design assumes dark theme. No light mode tokens defined. Future accessibility concern |
| Animation tokens (duration, easing) | ❌ Missing | Accordion animation (Sprint 7), crossfade (Sprint 10), pulse (Sprint 11) each define their own timing |
| Spacing scale | ⚠️ Partial | `MacSpacing` exists but may not cover all new layouts |

**Recommendation:** Expand `MacColors.swift` and `MacSpacing.swift` in Sprint 7 before other sprints depend on them:

```swift
// Proposed additions to MacColors.swift
static let accentOnDark = Color(hex: "#FF6B35")    // Primary on dark backgrounds
static let accentOnLight = Color(hex: "#D4521E")    // AAA-compliant on light backgrounds

// Interactive states
static let hoverBackground = accentPrimary.opacity(0.08)
static let pressedBackground = accentPrimary.opacity(0.20)
static let disabledForeground = Color.white.opacity(0.3)
static let focusRing = accentPrimary.opacity(0.5)

// Semantic status
static let statusNormal = Color(hex: "#4CAF50")
static let statusWarning = Color(hex: "#FF9800")
static let statusError = Color(hex: "#F44336")
static let statusCritical = Color(hex: "#D32F2F")
static let statusInfo = accentPrimary

// Animation
static let animationFast: Double = 0.15
static let animationNormal: Double = 0.25
static let animationSlow: Double = 0.4
```

### 6.3 System-Level UI Elements

| Element | Covered in Plan? | Risk |
|---------|-----------------|------|
| macOS menu bar | ❌ No | Standard menu items may still show blue focus rings |
| Window chrome (title bar, close/minimize/zoom) | ❌ No | Cannot be themed — system-controlled |
| System alerts/sheets | ❌ No | `NSAlert` and system sheets use system accent color, not app-defined |
| Context menus | ❌ No | Right-click menus use system highlight color |
| Scroll indicators | ❌ No | System-managed, may not respect app accent |

**Recommendation:** Document which elements can vs. cannot be themed. Set system accent color via `NSApp.appearance` where possible. Accept system controls as-is for elements outside app control.

---

## 7. Consolidated Recommendations

### Immediate (Before Sprint 7 Starts)

1. **Recalibrate timeline** in master roadmap — update from "~9 months" to "18–24 months at 6hr/week"
2. **Expand design tokens** in Sprint 7 scope — add interaction states, semantic colors, animation constants
3. **Create `docs/architecture/learning-cycle-dataflow.md`** — document the PrincipleStore → OutcomeTracker → MetaMonitor → WorldModel pipeline
4. **Create `docs/architecture/chromadb-collections.md`** — plan collection strategy before Sprint 8 adds more collections
5. **Prioritize model deduplication** (5 duplicated files) in Sprint 7 to prevent compounding maintenance burden

### Sprint-Specific

| Sprint | Key Action |
|--------|------------|
| 7 | Add WCAG-compliant `accentOnLight` token. Test all color combinations. Expand design system tokens |
| 8 | Use separate ChromaDB collection for PrincipleStore. Add principle review step |
| 9 | **Security review required.** Flip to allowlist file access. Design OAuth callback for Tailscale. Add file operation audit log |
| 10 | Feature-flag new chat UI. Prototype WKWebView vs native rendering. Add XSS prevention |
| 11 | Schedule MetaMonitor hourly (not real-time). Add false positive tests for confusion detection |
| 12 | Define data retention policy. Add PII scrubbing to PDF parser. Audit trail for all health endpoints. Sanitize LLM health prompts |
| 13 | **Replace Bayesian updates with EMA.** Drop free energy complexity penalty. Ground curiosity questions in observables |
| 14 | Make regime thresholds configurable. Move `summarize_emails` from DRAFT to SUGGEST risk. Add regime transition hysteresis |

### Structural

1. **Add decision gates** after Sprints 8, 10, and 12
2. **Create `tests/fixtures/` directory** with sample data before Sprint 9
3. **Add pytest markers** (`security`, `integration`, `performance`) before test count exceeds 1500
4. **Consider Sprint 9/10 swap** — Chat (Sprint 10) is lower-risk than Explorer+Gmail (Sprint 9) and could provide value sooner
5. **Plan iOS catch-up sprint** — 8 macOS-only sprints will create significant feature drift

---

## Appendix: Audit Coverage Matrix

| Plugin Skill Used | Sprint Coverage | Findings |
|-------------------|----------------|----------|
| engineering:system-design | 8, 9, 10, 13-14 | 12 CRITICAL, 10 HIGH, 4 MEDIUM |
| operations:risk-assessment | All (7-14) | 35 risks (3 CRITICAL, 5 HIGH, 7 MEDIUM) |
| engineering:testing-strategy | All (7-14) | 42 gaps (10 CRITICAL, 23 HIGH, 9 MEDIUM) |
| operations:compliance-tracking | 12 | 7 findings (2 CRITICAL, 3 HIGH, 2 MEDIUM) |
| product-management:roadmap-management | All (7-14) | 6 findings (1 CRITICAL, 2 HIGH, 3 MEDIUM) |
| design:design-system-management | 7 (global impact) | 5 findings (1 CRITICAL, 2 HIGH, 2 MEDIUM) |
