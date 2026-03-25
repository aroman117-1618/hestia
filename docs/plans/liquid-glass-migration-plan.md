# Liquid Glass Design System — Migration Plan (v2, Post-Review)

**Date:** 2026-03-25
**Spec:** `docs/superpowers/specs/2026-03-25-hestia-liquid-glass-design-system.md` v1.0
**Second Opinion:** `docs/plans/liquid-glass-migration-second-opinion-2026-03-25.md`
**Verdict:** APPROVED WITH CONDITIONS (all 5 conditions incorporated below)
**Approach:** Hybrid — fix token values first (immediate visual improvement), then build Glass components, then migrate screens + remove agent colors per-screen, then cleanup.

---

## Changes from v1 (Second Opinion Conditions)

1. **Incremental spacing** — iOS `Spacing` values left untouched. New `GlassSpacing` tokens created. Views migrate one-by-one in Phase 4.
2. **No GlassTokens helper** — Dropped cross-platform abstraction. Platform token systems stay separate. Glass components use `#if os(macOS)` guards.
3. **Agent color removal merged into Phase 4** — No separate Phase 2. Agent colors removed per-screen during migration. Each file touched once.
4. **Contrast validation in Phase 1** — WCAG AA check runs immediately when amber changes.
5. **WorkflowCanvas CSS added** — React Flow canvas colors updated in Phase 4.

---

## Scope Summary

| Category | Count | Description |
|----------|-------|-------------|
| Token value fixes | 15 | Wrong hex values, opacities, base colors in MacColors + Colors+iOS |
| Typography token fixes | 11 | Wrong sizes/weights in MacTypography, missing tokens |
| New GlassSpacing tokens | 7 | Correct spacing scale for incremental migration |
| New Glass components | 6 | HestiaGlassCard, GlassInput, GlassPill, GlassBadge, GlassSettingsBlock, GlassDetailPane |
| Existing component updates | 9 | Panel border, DetailPane spinner, SidebarSection, ContentRow, CrossLinkBadge, ButtonStyle |
| Agent color removal | 20+ files | Merged into screen migration — HestiaMode UI, agentTeal/Purple, accentColor(for:) |
| Navigation restructuring | 3 files | Tab names, health removal, sidebar specs |
| Hardcoded colors in views | 83 files | Direct Color(hex:), Color.orange, Color.white, etc. |
| Hardcoded fonts in views | 128 files | .system(size:) without tokens |
| Glass materials | 5 | New material modifier (sidebar, chatPanel, toolbar, card, input) |
| Layout zone adjustments | 5 values | Sidebar width, chat panel, file sidebar, top bar, logo/icon sizes |
| Animation curve fixes | 3 | Spring response/damping params |
| WorkflowCanvas CSS | 1 | React Flow theme colors |
| iOS typography system | 1 | New centralized token file |

**Total estimated effort:** 47-64 hours across 5 phases

---

## Phase 1: Token Foundation (5-7h)

**Goal:** Fix every color, typography, and layout *value* in existing token files. Create new GlassSpacing tokens (but don't change existing iOS Spacing values). Validate contrast. No new component files.

**Principle:** After this phase, every macOS view already using design tokens automatically looks correct. iOS views won't change yet (spacing migrates per-file in Phase 4).

### WS1.1: macOS Color Token Fixes (MacColors.swift) — 2h

All changes in `HestiaApp/macOS/DesignSystem/MacColors.swift`:

| Line | Token | Current | New | Notes |
|------|-------|---------|-----|-------|
| 27 | `amberAccent` | `#E0A050` | `#FF9F0A` | **Primary accent — cascades to 40+ usages** |
| 67 | `textPrimary` | `#E4DFD7` | `#E8E2D9` | Warm beige shift |
| 68 | `textPrimaryAlt` | `#EBDFD1` | `#E8E2D9` | Unify with textPrimary |
| 69 | `textSender` base | `#EBDFD1` | `#E8E2D9` | Same base color, keep 62% opacity |
| 70 | `textSecondary` | `#EBDFD1 @ 50%` | `#E8E2D9 @ 55%` | Fix base AND opacity |
| 71 | `textPlaceholder` | `@ 40%` | `@ 35%` | Lighter placeholders |
| 11 | `chatInputBackground` | `#261302` | `#1E1308` | bg.input |
| 15-24 | All border base | `254/155/0` | `255/159/10` | Fix RGB to match #FF9F0A |
| 16 | `primaryBorder` | `#E2A45C @ 80%` | `#FF9F0A @ 40%` | border.accent |
| 99 | `statusInfo` | `= amberAccent` | `Color(hex: "0A84FF")` | Apple system blue |
| 43-57 | `logoGradient` | `#E17100 → #F54900` | `#FFB900 → #FF8904` | Spec amber gradient |

**Add new tokens** (append to MacColors):
```swift
// MARK: - Liquid Glass Amber Spectrum
static let amber400 = Color(hex: "FF9F0A")
static let amber300 = Color(hex: "FFB347")
static let amber500 = Color(hex: "E08A00")
static let amber700 = Color(hex: "8B5500")
```

**Contrast validation (Condition 4):**
After changing amber, immediately verify WCAG 2.1 AA (4.5:1 body, 3:1 large text):
- `#FF9F0A` on `#080503` (bg.base) — expect ~8.2:1 ✅
- `#FF9F0A` on `#0D0802` (bg.surface) — expect ~7.5:1 ✅
- `#FF9F0A` on `#110B03` (bg.elevated) — expect ~6.8:1 ✅
- `#E8E2D9` on `#080503` — expect ~14:1 ✅
- `#E8E2D9` on `#110B03` — expect ~12:1 ✅

### WS1.2: iOS Color Token Fixes (Colors+iOS.swift) — 1h

All changes in `HestiaApp/Shared/DesignSystem/Colors+iOS.swift`:

| Token | Current | New | Notes |
|-------|---------|-----|-------|
| `iosCardBackground` | `#1C1C1E` (gray) | `#110B03` | bg.elevated (warm brown) |
| `iosCardBorder` | `#2C2C2E` (gray) | `Color(hex: "FF9F0A").opacity(0.06)` | border.subtle |

**Add new tokens:**
```swift
// MARK: - Liquid Glass Text Tokens
static let textPrimary = Color(hex: "E8E2D9")
static let textSecondary = Color(hex: "E8E2D9").opacity(0.55)
static let textTertiary = Color(hex: "E8E2D9").opacity(0.35)
static let textInverse = Color(hex: "1A1005")
static let textLink = Color(hex: "FF9F0A")

// MARK: - Liquid Glass Background Tiers
static let bgBase = Color(hex: "080503")
static let bgSurface = Color(hex: "0D0802")
static let bgElevated = Color(hex: "110B03")
static let bgOverlay = Color(hex: "1A1005")
static let bgInput = Color(hex: "1E1308")

// MARK: - Liquid Glass Status
static let statusHealthy = Color(hex: "34C759")
static let statusWarning = Color(hex: "FF9F0A")
static let statusError = Color(hex: "FF453A")
static let statusInfo = Color(hex: "0A84FF")
static let statusNeutral = Color(hex: "8E8E93")
```

### WS1.3: macOS Typography Token Fixes (MacTypography.swift) — 1.5h

| Token | Current | New | Spec Token |
|-------|---------|-----|------------|
| `heroNumber` | 48pt | 32pt Semibold | type.hero |
| `sectionTitle` | 16pt | 15pt Medium | type.subheading |
| `label` | 13pt | 12pt Regular | type.caption |
| `labelMedium` | 13pt Medium | 12pt Medium | type.captionMedium |
| `caption` | 11pt | 12pt Regular | type.caption |
| `captionMedium` | 11pt Medium | 12pt Medium | type.captionMedium |
| `micro` | 9pt | 10pt Medium | type.micro |
| `axis` | 8pt | 10pt Medium | type.micro |

**Add missing token:**
```swift
static let sectionLabel: Font = .system(size: 11, weight: .semibold)
// Usage: .tracking(0.8).textCase(.uppercase)
```

**Alias non-spec tokens:**
- `heroHeading` (28pt) → alias to `brand` or remove if unused
- `cardSubtitle` (13pt Medium) → alias to `senderLabel`

### WS1.4: Create GlassSpacing Tokens (NEW — Condition 1) — 0.5h

**DO NOT change existing `Spacing` values in HestiaShared.** Instead, create new tokens.

Create `HestiaApp/Shared/DesignSystem/GlassSpacing.swift`:
```swift
import SwiftUI

/// Liquid Glass Design System spacing tokens.
/// Use these for new/migrated views. Old `Spacing` tokens remain for unmigrated views.
enum GlassSpacing {
    static let xs: CGFloat = 4
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let xxl: CGFloat = 24
    static let xxxl: CGFloat = 32
}

/// Liquid Glass corner radii.
enum GlassRadius {
    static let sm: CGFloat = 8      // badges, pills, input fields
    static let md: CGFloat = 12     // buttons, list items
    static let lg: CGFloat = 16     // cards, panels, popovers
    static let xl: CGFloat = 20     // modals, large containers
    static let pill: CGFloat = 9999 // capsule shapes
}
```

Also fix `CornerRadius` in HestiaShared (these are safe — 25pt values are clearly wrong):
| Token | Current | New |
|-------|---------|-----|
| `standard` | 25pt | 16pt |
| `button` | 25pt | 12pt |
| `card` | 25pt | 16pt |
| `small` | 12pt | 8pt |

### WS1.5: macOS Layout Zone Adjustments — 0.5h

File: `HestiaApp/macOS/DesignSystem/MacSpacing.swift`

| Token | Current | New | Spec |
|-------|---------|-----|------|
| `MacSize.iconSidebarWidth` | 68pt | 64pt | §4.3 |
| `MacSize.chatPanelWidth` | 520pt | 480pt | §4.3 |
| `MacSize.chatWindowWidth` | 515pt | 480pt | Align |
| `MacSize.fileSidebarWidth` | 280pt | 260pt | §4.3 |
| `MacSize.topNavHeight` | 46pt | 44pt | §4.3 |
| `MacSize.logoSize` | 36pt | 28pt | §5.2 |
| `MacSize.navIconButton` | 40pt | 36pt | §5.2 |
| `MacSize.navIcon` | 18pt | 20pt | §5.2 |
| `MacSize.activeIndicatorHeight` | 16pt | 14pt | §5.2 |

**Add missing:**
```swift
static let commandPaletteWidth: CGFloat = 520
static let commandPaletteHeight: CGFloat = 400
```

**Add to MacCornerRadius:**
```swift
static let md: CGFloat = 12
static let xl: CGFloat = 20
```

### WS1.6: macOS Animation Curve Fixes — 0.5h

File: `HestiaApp/macOS/DesignSystem/MacSpacing.swift` (MacAnimation enum)

Update spring parameters to match spec:
```swift
static var fastSpring: Animation {
    .spring(response: 0.2, dampingFraction: 0.85)
}
static var normalSpring: Animation {
    .spring(response: 0.3, dampingFraction: 0.8)
}
static var slowSpring: Animation {
    .spring(response: 0.45, dampingFraction: 0.75)
}
```

Add new tokens:
```swift
static let gentle: Double = 0.6
static let orb: Double = 4.0
static var gentleEase: Animation { .easeInOut(duration: gentle) }
```

### Phase 1 Verification
- [ ] macOS builds clean
- [ ] iOS builds clean
- [ ] HestiaShared package builds
- [ ] macOS: amber accent visibly more vivid (#FF9F0A vs #E0A050)
- [ ] macOS: text colors slightly warmer
- [ ] iOS: cards shift from gray to warm brown
- [ ] macOS: sidebar narrower, chat panel narrower
- [ ] WCAG AA contrast verified for amber on all bg tiers
- [ ] No regressions

---

## Phase 2: Glass Components (7-9h)

**Goal:** Build the 6 new `HestiaGlass*` components + GlassMaterial modifier. Components use `#if os(macOS)` for platform-specific token resolution (no GlassTokens abstraction). Old components stay as deprecated aliases.

### WS2.1: HestiaGlassCard — 1.5h

Create `HestiaApp/Shared/DesignSystem/Components/HestiaGlassCard.swift`

**Spec §6.1:**
- Background: bg.elevated (#110B03)
- Border: 0.5pt, border.subtle (amber @ 6%) → border.default (amber @ 12%) on hover
- Corner radius: 16pt
- Padding: 12pt inner
- Hover: border glow (4px blur), scale 1.005x
- Variants: `.default`, `.accent` (2pt left amber border), `.interactive` (press scale 0.98x)
- Optional section label (11pt semibold uppercase, text.tertiary)

Platform token resolution via `#if os(macOS)` / `#else`.

### WS2.2: HestiaGlassInput — 1h

Create `HestiaApp/Shared/DesignSystem/Components/HestiaGlassInput.swift`

**Spec §6.2:** Capsule, bg.input, 0.5pt border, 44pt height, focus glow.

### WS2.3: HestiaGlassPill — 1h

Create `HestiaApp/Shared/DesignSystem/Components/HestiaGlassPill.swift`

**Spec §6.3:** Tint @ 12% bg, tint @ 20% border, 8pt radius, press scale 0.96x + opacity 0.8.

### WS2.4: HestiaGlassBadge — 0.5h

Create `HestiaApp/Shared/DesignSystem/Components/HestiaGlassBadge.swift`

**Spec §6.4:** 8pt dot with 2px glow, status color @ 8% bg.

### WS2.5: HestiaGlassSettingsBlock — 1h

Create `HestiaApp/Shared/DesignSystem/Components/HestiaGlassSettingsBlock.swift`

**Spec §6.5:** 20pt icon in 36pt frame, bg.elevated, 16pt radius, hover state.

### WS2.6: HestiaGlassDetailPane — 1.5h

Create `HestiaApp/Shared/DesignSystem/Components/HestiaGlassDetailPane.swift`

**Spec §6.6:** Sticky header, amber spinner, error retry pill, scrollable content.

### WS2.7: Glass Material Modifier — 0.5h

Create `HestiaApp/Shared/DesignSystem/GlassMaterial.swift`

```swift
enum GlassSurface {
    case sidebar    // ultraThinMaterial, amber 3%, 0.85
    case chatPanel  // ultraThinMaterial, amber 2%, 0.90
    case toolbar    // thinMaterial, no tint, 0.80
    case card       // simulated: bg.elevated + luminous border
    case input      // ultraThinMaterial, amber 5%, 0.92
}
```

macOS 15: simulated (solid bg + border). macOS 26+: `#available` with native `.glassEffect()`.

### Phase 2 Verification
- [ ] All 6 components build on both platforms
- [ ] Each has SwiftUI Preview
- [ ] Hover states work on macOS
- [ ] Press states animate
- [ ] Old components still compile
- [ ] hestia-build-validator passes both targets

---

## Phase 3: Existing Component Updates (4-5h)

**Goal:** Fix 9 existing macOS components to match spec. Also fix navigation tabs.

### WS3.1: HestiaPanelModifier — 0.5h
- Border: 1pt → 0.5pt
- Add hover glow

### WS3.2: HestiaDetailPane — 1h
- Sticky header
- Loading spinner: system blue → amber
- Error: add retry pill

### WS3.3: HestiaSidebarSection — 0.5h
- Disclosure tint: 50% → 35%
- Add hover bg (bg.elevated @ 30%)
- Animation: normalSpring

### WS3.4: HestiaContentRow — 1h
- Selection: accent @ 12% → bg.elevated @ 50% + border.subtle
- Trailing label: add 0.5pt border
- Add hover highlight

### WS3.5: HestiaButtonStyle — 0.5h
- Spring: use MacAnimation.fastSpring (response 0.2, damping 0.85)
- Icon style opacity: 0.7 → 0.85

### WS3.6: IconSidebar + Navigation Tabs — 1h

**Fix sidebar spec alignment:**
- Active indicator gradient: #FFB900 → #FF8904
- Active: icon amber, glass pill highlight, border.accent + bg.elevated
- Hover: icon → text.primary, bg → bg.elevated @ 50%
- matchedGeometryEffect, fastSpring

**Fix navigation tabs** (`WorkspaceState.swift`):
```swift
enum WorkspaceView: String, CaseIterable {
    case command    // Tab 1: house.fill, ⌘1
    case orders     // Tab 2: bolt.fill, ⌘2 (was "workflow")
    case memory     // Tab 3: brain.head.profile, ⌘3 (was "research")
    case explorer   // Tab 4: magnifyingglass, ⌘4
    case settings   // Tab 5: avatar, ⌘5
}
```

Remove `health` case. Add UserDefaults migration for old "health"/"research"/"workflow" values.

Update: `IconSidebar.swift`, `WorkspaceRootView.swift`, `Accessibility.swift` switch statements.

### Phase 3 Verification
- [ ] Panel borders 0.5pt
- [ ] Detail pane spinner is amber
- [ ] Sidebar sections have hover
- [ ] Content rows have correct selection
- [ ] 5 tabs: Command, Orders, Memory, Explorer, Settings
- [ ] ⌘1-5 shortcuts work
- [ ] Persisted state migrates (no crash)
- [ ] HestiaCrossLinkBadge: all modules amber

---

## Phase 4: Screen-by-Screen Migration (28-38h)

**Goal:** Migrate every view file to design tokens + Glass components. Per-screen, also remove agent colors and migrate from old `Spacing` to `GlassSpacing`. Each screen = one commit.

**Per-screen checklist:**
1. Replace hardcoded `Color(hex:)` / `Color.white` / etc. → design tokens
2. Replace hardcoded `.system(size:)` → MacTypography / iOS typography tokens
3. Replace old `Spacing.*` → `GlassSpacing.*`
4. Replace old components → Glass components where they appear
5. Remove agent color references (agentTeal/Purple, HestiaMode colors)
6. Add missing interaction states (hover/press)
7. Build-verify

### Screen 1: Command Center — macOS (3-4h)
**9 files:** CommandView, HeroSection, StatCardsRow, ActivityFeed, ActivityFeedView, InternalActivityView, ExternalActivityView, NewsFeedListView, LearningMetricsPanel
- HeroSection: remove `currentMode: HestiaMode`, use amber only
- StatCardsRow: padding(17) → MacSpacing tokens
- All: tokenize hardcoded fonts/colors

### Screen 2: Chat Panel — macOS (2-3h)
**9 files:** MacChatPanelView (236 lines), MacMessageBubble, MacMessageInputBar, FloatingAvatarView, BackgroundSessionButton, CLITextView, MarkdownMessageView, MacReactionsRow, OutcomeFeedbackRow
- FloatingAvatarView: remove mode picker, single Hestia avatar, delete `accentColor(for:)` usage
- Message bubbles: AI → bg.elevated + border.subtle, user → amber @ 15%
- Input bar: apply glass.input material
- Apply glass.chatPanel to panel background

### Screen 3: Chat — iOS (2-3h)
**8 files:** ChatView, ChatInputBar, VoiceJournalView, ThinkingIndicator, WaveformView, MessageBubble, VoiceRecordingOverlay, TranscriptReviewView
- ChatView: remove HestiaMode.allCases picker
- ChatInputBar: replace Color.black.opacity(0.3), remove mode.color
- VoiceJournalView: replace Font.custom("Georgia") → SF Pro, replace agentTeal
- MessageBubble: Color.orange → amber

### Screen 4: Settings — Both (3-4h)
**iOS (4):** MobileSettingsView, ResourcesDetailView, SystemDetailView, AgentCustomizationView
**macOS (7):** MacSettingsView, MacProfileView, MacAgentsView, AgentDetailSheet, ProfilePhotoEditor, MacResourcesView, MacCloudSettingsView
- Replace all agent color tints with .accent / amberAccent
- iOS: HestiaCard → HestiaGlassCard, HestiaSettingsBlock → HestiaGlassSettingsBlock

### Screen 5: Research / Memory — macOS (4-5h)
**8 files — HIGHEST hardcoding density:**
ResearchView (1000+ lines, 50+ font calls, 12+ colors), NodeDetailPopover, ResearchCanvasDetailPane, ResearchCanvasSidebar, MacSceneKitGraphView, ResearchCanvasWebView, MemoryBrowserView, MemoryReviewView
- ResearchView: aggressive tokenization, consider splitting if >800 lines post-migration
- Node colors: diagram.apple/cloud/default tokens
- HestiaCrossLinkBadge: all modules → amber

### Screen 6: Explorer — macOS (2-3h)
**10 files:** ExplorerView (900+ lines), ExplorerFilesView, ExplorerInboxView, FileTreeView, FileSearchBar, FilePreviewArea, FileContentSheet, InboxItemRow, MacExplorerResourcesView, InboxDetailSheet

### Screen 7: Wiki / Field Guide — Both (2-3h)
**21 files:** 6 Shared + 15 macOS (including DiagramKit)
- DiagramKit nodes: hardcoded colors → MacColors tokens

### Screen 8: Orders / Workflows — macOS (1-2h)
**7 files:** MacWorkflowView, MacWorkflowSidebarView, MacWorkflowDetailPane, MacWorkflowRow, MacNewWorkflowSheet, MacNodeInspectorView, WorkflowCanvasWebView
- MacNodeInspectorView: padding(4) × 4 → MacSpacing.xs

### Screen 9: Health — macOS (1h)
**5 files:** HealthView, HealthTopBar, HealthMetricsRow, EpigeneticMarkersCard, BiologicalAgeCard

### Screen 10: Auth / Onboarding — Both (1-2h)
**6 files:** AuthView, OnboardingView, LockScreenView, PermissionsOnboardingView, QRScannerView, MacOnboardingView
- OnboardingBackground: fix gradient to spec bg tiers
- HestiaOrbView: fix colors (#E0A050 → #FF9F0A)

### Screen 11: Common / Chrome (1-2h)
**16 files:** ModeIndicator, GradientBackground, ErrorView, LoadingView, HestiaOrbView, OnboardingBackground, CommandPaletteView, GlobalErrorBanner, SkeletonLoader, TrendBadge, MarkdownEditorView, OfflineBanner, ChatToggleButton, ChatPanelToggleOverlay + IconSidebar (already done)
- ModeIndicator: all modes use amber (keep functional mode switching)
- GradientBackground: single amber gradient
- ErrorView/LoadingView: amber spinners

### Screen 12: iOS Command Center (1-2h)
**2 files:** MobileCommandView, SystemDetailView
- HestiaCard → HestiaGlassCard
- HestiaPillButton → HestiaGlassPill
- HestiaStatusBadge → HestiaGlassBadge
- Replace agentTeal/agentPurple with .accent

### Screen 13: WorkflowCanvas CSS (Condition 5) (1h)
**Files:** `HestiaApp/WorkflowCanvas/src/` (React Flow theme)
- Update CSS variables to match Liquid Glass color spec
- Background: bg.surface
- Node colors: amber spectrum
- Edge colors: text.secondary

### Phase 4 Verification (per screen)
- [ ] Zero hardcoded Color(hex:) in migrated files
- [ ] Zero hardcoded .system(size:) in migrated files
- [ ] All padding uses GlassSpacing or MacSpacing tokens
- [ ] No agentTeal/agentPurple/accentColor(for:) references remain
- [ ] Old components replaced with Glass equivalents
- [ ] Build clean on both targets

---

## Phase 5: Cleanup & Polish (3-5h)

### WS5.1: Delete Old Components — 1h

After all views migrated (verify via grep):
- Split HestiaSettingsBlock out of HestiaPillButton.swift into own file
- Mark deprecated: HestiaCard, HestiaPillButton, HestiaStatusBadge, HestiaSettingsBlock
- Delete `accentColor(for:)` from MacColors if not already removed
- Delete agentTeal/agentPurple definitions from Colors+iOS
- Delete old Spacing tokens from HestiaShared (replace with GlassSpacing)

### WS5.2: iOS Typography Token System — 1h

Create `HestiaApp/Shared/DesignSystem/Typography+iOS.swift`:
```swift
extension Font {
    static let glassHero: Font = .system(size: 32, weight: .semibold)
    static let glassTitle: Font = .system(size: 22, weight: .semibold)
    static let glassHeading: Font = .system(size: 18, weight: .medium)
    static let glassSubheading: Font = .system(size: 15, weight: .medium)
    static let glassBody: Font = .system(size: 14)
    static let glassBodyMedium: Font = .system(size: 14, weight: .medium)
    static let glassCaption: Font = .system(size: 12)
    static let glassCaptionMedium: Font = .system(size: 12, weight: .medium)
    static let glassMicro: Font = .system(size: 10, weight: .medium)
    static let glassCode: Font = .system(size: 13, design: .monospaced)
    static let glassSectionLabel: Font = .system(size: 11, weight: .semibold)
    static let glassInput: Font = .system(size: 15)
    static let glassChat: Font = .system(size: 15)
    static let glassChatSender: Font = .system(size: 13, weight: .medium)
}
```

### WS5.3: Accessibility Audit — 0.5h
- All text on glass meets WCAG 2.1 AA (4.5:1 body, 3:1 large)
- Increase Contrast mode: glass → opaque bg.elevated
- Focus rings: border.accent, 2pt width

### WS5.4: Documentation Update — 0.5h
- Update CLAUDE.md project structure
- ADR in decision log
- Update component names in sub-agent definitions

### WS5.5: Final Visual Validation — 1h
Screenshot every screen on both platforms. Compare against spec.

---

## Execution Schedule

| Phase | Hours | Dependencies | Parallelizable |
|-------|-------|-------------|----------------|
| Phase 1: Token Foundation | 5-7h | None | Start immediately |
| Phase 2: Glass Components | 7-9h | Phase 1 | Yes (with Phase 3) |
| Phase 3: Component Updates + Nav | 4-5h | Phase 1 | Yes (with Phase 2) |
| Phase 4: Screen Migration | 28-38h | Phase 2 + 3 | Screens are independent |
| Phase 5: Cleanup | 3-5h | Phase 4 | Last |

**Total: 47-64h.** At Andrew's pace + Claude Code, ~3-4 weeks (Sprints 31-33).

---

## Commit Strategy

~40 commits, each individually buildable and revertable:
- Phase 1: 1 per WS (6 commits)
- Phase 2: 1 per component (7 commits)
- Phase 3: 1 per component + 1 for nav (7 commits)
- Phase 4: 1 per screen (13 commits)
- Phase 5: 1 per WS (5 commits)

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| iOS CornerRadius change (25→16/12) breaks layouts | MEDIUM | These are clearly wrong at 25pt. Change is safe. |
| ResearchView (1000+ lines) migration introduces bugs | HIGH | Tokenize in small batches within the commit. Build after each file. |
| Navigation rename breaks persisted state | MEDIUM | Migration code in WorkspaceState init() |
| Simulated glass looks flat on macOS 15 | LOW | Luminous borders + hover glow compensate. Native glass in macOS 26+. |
| Phase 4 takes longer than estimated | MEDIUM | Budget for high end (38h). Screens are independent — can pause/resume. |
