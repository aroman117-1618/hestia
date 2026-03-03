# Hestia UX Optimization Research
### Enterprise-Grade Experience Audit & Proposals

**Date:** 2026-03-03
**Scope:** Full macOS app UX audit — 81 Swift files, 10,986 lines, 8 major views
**Standard:** Apple HIG (WWDC25 Liquid Glass era) + Enterprise SaaS production quality

---

## Part 1: Current State Assessment

### Architecture Summary

Hestia macOS is a three-panel native SwiftUI application:

```
┌──────┬──────────────────────┬──────────────┐
│ Icon │                      │              │
│ Side │    Content Area      │  Chat Panel  │
│ bar  │    (flex width)      │   (520px)    │
│ 68px │                      │  collapsible │
└──────┴──────────────────────┴──────────────┘
```

Built on `NSSplitViewController` (AppKit) hosting SwiftUI views via `NSHostingController`. Design system uses 60+ color tokens, 8 spacing scales, Volkhov serif branding font, and spring-based animation primitives. Seven primary views switchable via ⌘1-7 keyboard shortcuts.

### What's Working Well

The app already has a strong foundation: precision color tokens from Figma, consistent amber/dark theme identity, spring-based animation primitives, a well-structured ViewModels-per-view pattern, and functional keyboard shortcuts (⌘1-7, ⌘\). The `NSSplitViewController` approach gives real divider drag behavior. The design system files (MacColors, MacSpacing, MacTypography) are clean and well-tokenized.

### Critical Gaps Identified

| Gap | Severity | Impact |
|-----|----------|--------|
| No haptic feedback anywhere | High | Interactions feel "dead" — no tactile confirmation |
| Button hit targets below 44pt minimum | High | Sidebar nav icons are 40x40pt with no expanded hit area |
| Single responsive breakpoint (700px) | Medium | Harsh layout jump, no intermediate states |
| No accessibility identifiers | High | Screen reader support is absent |
| Chat panel toggle is keyboard-only (⌘\) | High | No visible GUI control to collapse/expand chat |
| No `sensoryFeedback()` modifiers | Medium | Missing modern SwiftUI haptic integration |
| No debounce on search inputs | Medium | Rapid typing causes unnecessary recomputation |
| Graphics don't gracefully degrade at small sizes | Medium | Progress rings, cards clip/overlap below 700px |
| No loading skeletons | Medium | Views show blank or spinner during API calls |
| No `@SceneStorage` for panel state | Low | Chat panel visibility resets on app relaunch |
| No cursor shape hints on dividers/buttons | Low | Users don't know the divider is draggable |
| Typewriter effect blocks UI thread pattern | Low | 0.03s per-character loop in ViewModel |

---

## Part 2: Deep Dive — Your Three Priority Areas

### 2.1 Panel Toggling via GUI

**Current implementation:** The chat panel toggle lives exclusively behind ⌘\ (keyboard shortcut) and the View menu. There is no visible button, icon, or affordance in the GUI to collapse or expand the chat panel. The `MainSplitViewController.toggleChatPanel()` method uses `NSAnimationContext` with a 0.25s ease-in-out animation, which is solid. But discoverability is zero for a new user.

**What enterprise apps do:** Slack, Linear, Notion, Arc Browser, and Apple Mail all provide a visible toolbar button (often a sidebar/panel icon) that toggles the secondary panel. Apple's HIG explicitly recommends pairing `SidebarCommands()` with a toolbar toggle button for discoverability. The WWDC25 Liquid Glass guidelines emphasize that panel controls should be visually present and respond to both click and keyboard.

**Proposed Options:**

**Option A: Toolbar Toggle Button (Recommended)**
Add a small panel-toggle icon (e.g., `sidebar.right`) to the top-right corner of the content area or inside the icon sidebar. On click, call `toggleChatPanel()`. Show a tooltip with the shortcut hint "⌘\".

*SWOT:*
- **Strengths:** Maximum discoverability. Matches Apple Mail / Xcode / Arc patterns. Minimal code change (~20 lines). Tooltip teaches the keyboard shortcut over time.
- **Weaknesses:** Consumes a small amount of visual real estate. Needs careful placement to avoid clutter.
- **Opportunities:** Can double as a drag handle for panel resize. Can show chat notification badge (unread count dot).
- **Threats:** If placed poorly, users might accidentally toggle. Need to match existing amber theme carefully.

**Option B: Edge-Hover Reveal Strip**
Add a thin (4-6px) invisible strip along the right edge of the content area. On hover, it expands to show a small panel icon with a slide-in animation. Clicking opens/closes the chat panel.

*SWOT:*
- **Strengths:** Zero visual footprint when not in use. Feels premium/magical. Common in pro tools (Final Cut, DaVinci Resolve).
- **Weaknesses:** Poor discoverability — users won't find it without being told. Accessibility concern for motor-impaired users. More complex to implement.
- **Opportunities:** Can combine with a resize-cursor hint to suggest draggability.
- **Threats:** Conflicts with the existing NSSplitView divider hit area (currently 9px). Could cause accidental triggers during normal resize.

**Option C: Bottom Tab Bar Chat Toggle**
Add a persistent mini-bar below the icon sidebar with a chat bubble icon that glows amber when the panel is open. Tapping toggles the panel.

*SWOT:*
- **Strengths:** Always visible. Naturally extends the sidebar's navigation metaphor. Can show unread message count.
- **Weaknesses:** Adds vertical complexity to the sidebar. May conflict with the profile button's bottom position.
- **Opportunities:** Could host additional quick-actions (e.g., notification center, quick command).
- **Threats:** Sidebar is already 68px wide — adding more controls risks making it feel cramped.

**Recommendation:** Option A. It's the Apple-canonical pattern with the best discoverability-to-effort ratio. Specifically, add a `sidebar.right` SF Symbol button in the top bar of the content area (or in the icon sidebar, above the profile button). Pair it with `.help("Toggle Chat (⌘\\)")` for tooltip on hover.

---

### 2.2 Graphics Handling When Size Shrinks

**Current implementation:** The app uses a single `isCompact` boolean at the 700px breakpoint in `CommandView`. Below 700px, layouts switch from `HStack` to `VStack`, progress rings shrink by 0.7x, stat card grids go from 3 columns to 2, and some text labels are hidden. However, the transition is binary — there's no intermediate state, and several components clip or overflow at widths between 600-700px (the minimum content width is set to 600px in the split view).

**What enterprise apps do:** Linear, Figma, and Apple's own apps use multi-tier responsive breakpoints with smooth interpolation. The WWDC25 design system emphasizes "content-first" layouts where elements reflow gracefully rather than jump between two states. Best practice is 3-4 breakpoints: compact (<600), regular (600-900), wide (900-1200), and ultrawide (1200+).

**Proposed Options:**

**Option A: Multi-Tier Adaptive Layout System (Recommended)**
Replace the binary `isCompact` flag with a `LayoutMode` enum: `.compact`, `.regular`, `.wide`. Use `GeometryReader` to derive the mode, then let each component adapt per-tier. Progress rings get three sizes (small/medium/large). Stat card grids get three column counts (1/2/3). Text truncation happens progressively.

*SWOT:*
- **Strengths:** Smooth visual experience at any window size. Matches Apple's adaptive layout philosophy. Future-proofs for iPad support. Each view can independently define its breakpoints.
- **Weaknesses:** Requires touching most view files. More state to reason about. Needs thorough testing at many widths.
- **Opportunities:** Enables a truly responsive experience that works on external displays, split-screen, and Stage Manager. Can use `ViewThatFits` (SwiftUI 4+) for automatic fallback selection.
- **Threats:** Complexity creep — three tiers means three states to test per component. Risk of inconsistent breakpoint thresholds across views.

**Option B: Proportional Scaling with `GeometryReader`**
Instead of discrete breakpoints, use continuous proportional scaling. Progress ring size = `min(100, availableWidth * 0.12)`. Card grid columns = `max(1, Int(availableWidth / 200))`. Text font sizes scale between min/max based on width.

*SWOT:*
- **Strengths:** Perfectly smooth — no layout jumps at any size. Elegant mathematical model. Easy to reason about in isolation.
- **Weaknesses:** Can produce awkward intermediate sizes (e.g., 2.5 columns worth of cards). Text scaling can create readability issues. Harder to design for specific sizes in Figma.
- **Opportunities:** Combined with `matchedGeometryEffect`, can create fluid card reflow animations.
- **Threats:** Performance risk from excessive `GeometryReader` re-evaluation. Proportional scaling can make the app feel "stretchy" rather than designed.

**Option C: `ViewThatFits` + Priority-Based Degradation**
For each section, define a hierarchy of views from richest to simplest. SwiftUI's `ViewThatFits` automatically selects the largest one that fits. Progress rings → compact rings → numeric badges. Stat cards → horizontal list → count-only strip.

*SWOT:*
- **Strengths:** SwiftUI-native. Declarative — each component defines its own degradation path. No manual breakpoint math. Apple recommends this approach.
- **Weaknesses:** Only available macOS 13+ (your target is 15.0, so this works). Doesn't handle partial fitting well. Can cause unexpected view selection if content varies.
- **Opportunities:** Cleanest long-term architecture. Each component becomes self-contained and testable.
- **Threats:** Less predictable — the "fit" algorithm may not always choose what you'd expect visually. Harder to debug layout issues.

**Recommendation:** Option A with selective use of Option C's `ViewThatFits` for individual components. Define `LayoutMode` as an `@Environment` value computed from a top-level `GeometryReader`, then let each view respond to the mode. This gives you deterministic breakpoints (designable in Figma) with graceful per-component degradation.

---

### 2.3 Button Response Snappiness, Haptic Feedback, and Hit Targets

**Current implementation:** Buttons use `.buttonStyle(.plain)` with manual hover tracking via `onHover`. Nav icon buttons are 40x40pt (below the 44pt minimum). No haptic feedback exists anywhere — the app has zero calls to `NSHapticFeedbackManager` or `.sensoryFeedback()`. Button press feedback is limited to color changes (amber accent on active, opacity changes on hover). There are no pressed-state animations (scale-down, bounce, etc.).

**What enterprise apps do:** Every major macOS app (Slack, Discord, Notion, Linear, Arc) uses trackpad haptics for meaningful interactions. Apple's HIG provides `NSHapticFeedbackManager.defaultPerformer` with `.alignment` and `.levelChange` patterns. The modern SwiftUI approach is `.sensoryFeedback(.impact, trigger: someValue)`. Button press feedback typically includes a subtle scale animation (0.96x for 100ms), haptic tick, and immediate visual state change. Hit targets should be at minimum 44x44pt per Apple accessibility guidelines, even if the visual element is smaller.

**Proposed Options:**

**Option A: Comprehensive Interaction Layer (Recommended)**
Build a `HestiaButtonStyle` that wraps all buttons with: (1) expanded 44pt minimum hit area via `.contentShape()`, (2) pressed-state scale animation (0.96x spring), (3) haptic feedback via `.sensoryFeedback(.impact(weight: .light), trigger:)`, and (4) hover state with smooth color transition. Apply this as the default button style across the app.

*SWOT:*
- **Strengths:** Single source of truth for all button behavior. Guarantees accessibility compliance. Haptic feedback makes interactions feel "real." Pressed-state animation provides instant visual acknowledgment. Consistent across the entire app.
- **Weaknesses:** Overriding button styles globally requires touching many views. Some buttons (e.g., tab bar, nav icons) need variant styles. Risk of haptic fatigue if applied too broadly.
- **Opportunities:** Can define haptic intensity per interaction tier: navigation = `.impact(.light)`, destructive = `.impact(.heavy)`, toggle = `.levelChange`. Can add `.sensoryFeedback` to non-button interactions (panel toggle, mode switch). The style system becomes a competitive differentiator.
- **Threats:** macOS haptics only work on Force Touch trackpads (MacBook, Magic Trackpad 2+). External mice won't feel them. Over-engineering the style system could delay shipping.

**Option B: Selective Haptics + Hit Target Fix**
Don't build a global style. Instead, add `.contentShape(Rectangle())` and `.frame(minWidth: 44, minHeight: 44)` to existing buttons individually. Add `.sensoryFeedback` only to high-value interactions: nav switches, chat panel toggle, mode switch, send message.

*SWOT:*
- **Strengths:** Targeted — only changes what matters most. Lower risk of regression. Faster to implement and ship. Can be done incrementally.
- **Weaknesses:** Inconsistent — some buttons will feel polished, others won't. Doesn't establish a reusable pattern. Hit target fixes are tedious to apply one-by-one.
- **Opportunities:** Good as a first pass before committing to Option A. Lets you A/B test which haptics users notice.
- **Threats:** Technical debt — scattered button modifications are harder to maintain than a centralized style.

**Option C: Custom Gesture Recognizer with Haptic Engine**
Build a `HestiaInteractionModifier` ViewModifier that wraps any view with: long-press detection, haptic on press-down and release, scale animation, and expanded hit area. Use `NSHapticFeedbackManager.defaultPerformer.perform(.levelChange, performanceTime: .now)` for precise timing control.

*SWOT:*
- **Strengths:** Maximum control over haptic timing. Can differentiate press-down vs. release feedback. Supports long-press patterns for future features (context menus, drag-to-reorder).
- **Weaknesses:** More complex than necessary for basic buttons. Custom gesture recognizers can conflict with SwiftUI's built-in button handling. Harder to maintain.
- **Opportunities:** Foundation for advanced interactions: haptic drag-and-drop, force-touch shortcuts, pressure-sensitive drawing.
- **Threats:** Over-engineering risk. Custom gestures can break VoiceOver and keyboard navigation if not carefully implemented.

**Recommendation:** Option A, implemented incrementally. First, create `HestiaButtonStyle` and `HestiaNavButtonStyle` as reusable ButtonStyles. Then apply them across the app in a single pass. The style should enforce the 44pt minimum hit area, include a pressed-state scale spring, and fire `.sensoryFeedback(.impact(weight: .light))` on tap. For the icon sidebar, the nav icons should get `.contentShape(Rectangle().inset(by: -2))` to expand their 40pt frame to 44pt without changing visual layout.

---

## Part 3: Full UX Surface Audit — Additional Opportunities

Beyond the three priority areas, the audit revealed several additional areas where Hestia can reach enterprise production quality:

### 3.1 Accessibility (Critical — Blocks Enterprise Deployment)

**Finding:** Zero accessibility identifiers across 81 files. No `.accessibilityLabel`, `.accessibilityHint`, or `.accessibilityValue` modifiers. No VoiceOver testing evidence.

**Recommendation:** Add accessibility labels to all interactive elements. This is not optional for enterprise grade — it's a legal and ethical requirement. Start with navigation (sidebar icons, tab bars), then chat (messages, input, reactions), then content views.

### 3.2 Loading States & Skeletons

**Finding:** Views use `ProgressView` spinners or blank screens during data loading. No skeleton/shimmer patterns.

**Recommendation:** Implement a `SkeletonModifier` that renders placeholder shapes matching the final layout. Apply to Command Center stat cards, Health metrics, Wiki article list, and Explorer file tree. This eliminates the "flash of empty content" and makes the app feel faster even when the API is slow.

### 3.3 State Persistence

**Finding:** Panel visibility, selected view, scroll positions, and sidebar state reset on app relaunch. No `@SceneStorage` usage.

**Recommendation:** Add `@SceneStorage("chatPanelVisible")` for chat panel state, `@SceneStorage("currentView")` for active view, and `@SceneStorage("wikiSelectedTab")` for Wiki tab selection. This makes the app feel like it "remembers" where you left off — a hallmark of polished desktop software.

### 3.4 Cursor Feedback

**Finding:** No custom cursor shapes on interactive regions. The NSSplitView divider shows a standard resize cursor, but custom draggable areas (e.g., Wiki sidebar width, Explorer file tree) don't signal interactivity.

**Recommendation:** Add `.onHover { NSCursor.resizeLeftRight.set() }` on draggable dividers and `.onHover { NSCursor.pointingHand.set() }` on non-standard clickable areas. This provides immediate affordance for interactive elements.

### 3.5 Search Debouncing

**Finding:** Search fields in Explorer (`FileSearchBar`) and Wiki (`MacWikiSidebarView`) trigger filtering on every keystroke with no debounce.

**Recommendation:** Add a 250ms debounce using `Combine`'s `.debounce(for: .milliseconds(250), scheduler: RunLoop.main)` on the search text publisher. This prevents unnecessary recomputation during rapid typing and is standard practice in every enterprise search implementation.

### 3.6 Error Boundaries

**Finding:** Error handling exists per-view but there's no global error boundary. If an API call fails in a nested view, the error message may not surface to the user.

**Recommendation:** Create a `HestiaErrorBanner` environment-injected component that any view can push errors to. Display it as an overlay at the top of the content area with auto-dismiss after 5 seconds. This matches Slack's error toast pattern.

### 3.7 Animation Polish

**Finding:** View transitions use `.easeInOut(duration: 0.2)` — functional but generic. No matched geometry transitions between views. No scroll-linked animations.

**Recommendation:** For view switches (⌘1-7), use `.matchedGeometryEffect` on the active sidebar indicator to create a pill that smoothly slides between positions. For the chat panel toggle, consider a 0.3s spring animation (response: 0.35, dampingFraction: 0.85) instead of the current linear ease-in-out. These small polish items separate "works" from "delightful."

### 3.8 Keyboard Navigation Completeness

**Finding:** ⌘1-7 and ⌘\ are implemented. No Tab/arrow-key navigation within views. No Escape-to-dismiss patterns. No ⌘K command palette.

**Recommendation:** (Phase 2) Add a command palette (⌘K) that searches across views, actions, and recent items — this is the single highest-impact keyboard feature for power users. Linear, Notion, Slack, and Arc all have this. It transforms the app from "navigable" to "instantly accessible."

### 3.9 Chat Input Micro-Interactions

**Finding:** The send button transitions between disabled (0.5 opacity) and enabled (full opacity) with no animation. The input bar has no focus ring or expansion on focus.

**Recommendation:** Add a subtle glow/border animation when the input field receives focus (amber accent border fades in over 0.2s). The send button should spring-scale from 0.8 → 1.0 when transitioning from disabled to enabled. On send, the button should briefly pulse (scale to 1.1 then back) with a `.sensoryFeedback(.success)` haptic.

---

## Part 4: Implementation Priority Matrix

| Priority | Item | Effort | Impact | Dependency |
|----------|------|--------|--------|------------|
| P0 | Chat panel GUI toggle button | S (2h) | High | None |
| P0 | Button hit target expansion (44pt min) | S (3h) | High | None |
| P0 | HestiaButtonStyle with pressed state | M (4h) | High | None |
| P0 | Haptic feedback on navigation + send | S (2h) | High | HestiaButtonStyle |
| P1 | Multi-tier responsive breakpoints | L (8h) | High | None |
| P1 | Accessibility labels (interactive elements) | M (6h) | Critical | None |
| P1 | `@SceneStorage` state persistence | S (2h) | Medium | None |
| P1 | Search debouncing | S (1h) | Medium | None |
| P2 | Loading skeletons | M (6h) | Medium | None |
| P2 | Sidebar indicator matchedGeometry | S (3h) | Medium | None |
| P2 | Cursor feedback on interactive regions | S (2h) | Low | None |
| P2 | Global error banner | M (4h) | Medium | None |
| P3 | ⌘K command palette | L (12h) | Very High | None |
| P3 | Chat input micro-interactions | S (2h) | Low | HestiaButtonStyle |
| P3 | Spring animation polish pass | M (4h) | Medium | None |

**Size key:** S = half-day, M = full day, L = multi-day

---

## Part 5: SWOT Analysis — Overall UX Transformation

### Strengths
- Native SwiftUI on macOS — no Electron overhead, instant startup, system-level integration
- Well-tokenized design system already in place — changes propagate cleanly
- Keyboard shortcut infrastructure already works — just needs extension
- NSSplitViewController gives real native panel behavior (resize, collapse, persist)
- Dark theme with amber accents is distinctive and professional — strong brand identity
- Clean ViewModel architecture — state changes are predictable and testable

### Weaknesses
- Zero accessibility support — blocks any enterprise or regulated deployment
- No haptic feedback — interactions feel flat compared to Apple first-party apps
- Binary responsive layout — the 700px cliff creates visual jarring
- Chat panel has no GUI discoverability — a core feature hidden behind a keyboard shortcut
- No command palette — power users can't quick-navigate without memorizing shortcuts
- AppKit/SwiftUI bridge adds complexity — some patterns (haptics, cursor) require AppKit calls

### Opportunities
- WWDC25 Liquid Glass design language — adopting it would make Hestia feel cutting-edge
- `sensoryFeedback()` modifier is new and underused — early adoption differentiates
- `ViewThatFits` for responsive layouts is elegant and future-proof
- `@SceneStorage` makes state persistence trivial with no backend changes
- ⌘K command palette would leapfrog most personal AI assistants in usability
- The three-agent model (Tia/Mira/Olly) is unique — UX polish would make mode-switching feel magical rather than mechanical

### Threats
- Over-polishing before shipping — diminishing returns past the P1 tier
- macOS 15.0 target may not support all WWDC25 features (Liquid Glass requires macOS 26)
- Force Touch haptics only work on certain hardware — need graceful degradation
- Responsive layout rework touches many files — risk of regressions without comprehensive tests
- Custom button styles can conflict with system behaviors if not careful (keyboard focus rings, VoiceOver)

---

## Part 6: Recommended Execution Plan

**Sprint A (1 week): Interaction Foundation**
- Build `HestiaButtonStyle` and `HestiaNavButtonStyle`
- Add haptic feedback to navigation, send, mode switch, panel toggle
- Expand all hit targets to 44pt minimum
- Add visible chat panel toggle button
- Add `@SceneStorage` for panel + view state

**Sprint B (1 week): Responsive & Visual Polish**
- Implement `LayoutMode` enum with three tiers
- Refactor CommandView, HeroSection, StatCards for multi-tier
- Add search debouncing
- Add sidebar indicator `matchedGeometryEffect`
- Spring animation polish pass

**Sprint C (1 week): Accessibility & Resilience**
- Full accessibility label pass on all interactive elements
- Loading skeleton modifiers for data-dependent views
- Global error banner system
- Cursor feedback on interactive regions

**Sprint D (1 week): Power User Features**
- ⌘K command palette
- Chat input micro-interactions
- Keyboard Tab navigation within views
- Final QA pass across window sizes

---

*Research conducted via: full codebase exploration (81 files), Apple HIG documentation, WWDC25 design system session, enterprise SaaS UX pattern analysis, SwiftUI haptic feedback documentation, and responsive layout best practices.*
