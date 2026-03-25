# Hestia Liquid Glass Design System

**Version:** 1.0 — March 25, 2026
**Status:** Draft — Pending Andrew's Review
**Scope:** Unified design language for macOS (primary) and iOS (companion), inspired by Apple's Liquid Glass (iOS 26 / macOS Tahoe), adapted to Hestia's dark-mode amber/green identity.

---

## 1. Design Philosophy

### Core Principle: "Notion for Architecture, Apple for Aesthetics"

The information architecture borrows from Notion — block-based, cross-linked, navigable workspaces. The visual execution follows Apple's Liquid Glass: clean, minimal, generous space, translucent materials, luminous accents on deep dark backgrounds.

### Three Pillars

**1. Content Elevation.** Glass and translucency exist to push content forward, not to decorate. Every surface, border, and glow should serve hierarchy — making the important things unmissable and the chrome invisible.

**2. Warmth Through Restraint.** Hestia's amber/orange palette gives the app personality. But it's used surgically — accent color on active states, tinted glass on navigation, subtle glow on interactive elements. The dominant visual is deep black/dark-brown with luminous punctuation, not an amber wash.

**3. Breathing Room.** Generous negative space between elements. Cards float, don't stack. Text has room to read. The app should feel like it has less on screen than it actually does.

### What This Is NOT

- Not a light mode design (dark-first, dark-only for v1)
- Not emoji chrome or playful illustration
- Not skeuomorphic — glass is a metaphor for depth and layering, not realism
- Not a 1:1 copy of Apple's blue language — Hestia has its own color identity

---

## 2. Color System

### 2.1 Background Tiers

All backgrounds are near-black with warm brown undertones. The tier system creates subtle depth without competing with content.

| Token | Hex | Usage |
|-------|-----|-------|
| `bg.base` | `#080503` | Window chrome, deepest layer |
| `bg.surface` | `#0D0802` | Primary content area |
| `bg.elevated` | `#110B03` | Cards, panels, popovers |
| `bg.overlay` | `#1A1005` | Modal overlays, command palette |
| `bg.input` | `#1E1308` | Text fields, search bars |

**Rule:** Each tier is approximately 3-5% lighter than the one below. The warmth comes from the brown channel, not from adding orange.

### 2.2 Glass Materials

Glass surfaces blend translucency with Hestia's warm palette. On macOS, these map to `NSVisualEffectView` materials with tinted overlays.

| Token | Base Material | Tint | Opacity | Usage |
|-------|---------------|------|---------|-------|
| `glass.sidebar` | `.ultraThinMaterial` | Amber 3% | 0.85 | Icon sidebar background |
| `glass.chatPanel` | `.ultraThinMaterial` | Amber 2% | 0.90 | Chat panel background |
| `glass.toolbar` | `.thinMaterial` | None | 0.80 | Floating toolbars |
| `glass.card` | None (simulated) | Amber 4% | 0.95 | Content cards — opaque dark with luminous border |
| `glass.input` | `.ultraThinMaterial` | Amber 5% | 0.92 | Input bars (chat, search, command palette) |

**Implementation note:** True translucency (`NSVisualEffectView` / SwiftUI `.background(.ultraThinMaterial)`) is used on the sidebar and chat panel — surfaces at the edges where the desktop can bleed through. Content areas (cards, detail panes, text-heavy zones) use simulated glass — solid dark backgrounds with luminous borders and subtle gradient overlays. This hybrid approach maximizes the depth effect while guaranteeing text readability.

### 2.3 Brand Colors — Amber Spectrum

The primary accent is amber/orange. A single hue with multiple intensities, not separate colors.

| Token | Hex | Usage |
|-------|-----|-------|
| `amber.50` | `#FFF5E6` | Tint on light surfaces (rare) |
| `amber.100` | `#FFE0B2` | Highlight backgrounds |
| `amber.200` | `#FFCA80` | Hover states |
| `amber.300` | `#FFB347` | Secondary accent |
| `amber.400` | `#FF9F0A` | **Primary accent** — active nav, buttons, links |
| `amber.500` | `#E08A00` | Pressed states |
| `amber.600` | `#C07400` | Dark accent (borders on bright surfaces) |
| `amber.700` | `#8B5500` | Muted accent |

**`amber.400` (`#FF9F0A`)** is the canonical Hestia amber. It matches the iOS spec and Apple's system orange. The macOS codebase currently uses `#E0A050` — this spec updates it to align cross-platform.

### 2.4 Secondary Accent — Green

Green is the secondary accent for positive states, health, and success. It also maps to the Apollo agent color (execution/completion).

| Token | Hex | Usage |
|-------|-----|-------|
| `green.300` | `#72F69E` | Status: healthy, success badges |
| `green.400` | `#34C759` | **Primary green** — Apple system green |
| `green.500` | `#2CC295` | Apollo agent accent |
| `green.600` | `#00A86B` | Muted green for backgrounds |

### 2.5 Single-Agent Color Identity

Hestia is the only user-facing agent. Artemis and Apollo operate in the backend only — they have no user-visible color identity. The entire UI uses **amber as the single, consistent accent color**. There is no agent color switching, no mode-based tint changes, and no teal/purple in the interface.

| Element | Color | Hex | Usage |
|---------|-------|-----|-------|
| Primary accent | Amber | `#FF9F0A` | Active nav, buttons, links, orb, interactive highlights |
| Secondary accent | Green | `#34C759` | Status: healthy/success only (not an "agent" color) |

**Migration:** Remove `accentColor(for mode:)` from `MacColors.swift`. Remove the `HestiaMode` color switch. All accent references resolve to `amber.400` (`#FF9F0A`). The iOS `agentTeal` and `agentPurple` tokens in `Colors+iOS.swift` can be deprecated — they are no longer needed in user-facing UI.

### 2.6 Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `status.healthy` | `#34C759` | System healthy, bot running |
| `status.warning` | `#FF9F0A` | Degraded, needs attention |
| `status.error` | `#FF453A` | Error, critical, kill switch |
| `status.info` | `#0A84FF` | Informational, links (Apple system blue) |
| `status.neutral` | `#8E8E93` | Inactive, disabled (Apple system gray) |

### 2.7 Health & Vitals Colors

Used in health metrics, coaching cards, and any biometric data display. Even with Health on the backburner, these appear in Command Center status cards.

| Token | Hex / Value | Usage |
|-------|-------------|-------|
| `health.green` | `#00D492` | Positive health metric (steps, activity) |
| `health.green.bg` | `#00D492` @ 15% | Background tint for positive metrics |
| `health.red` | `#FF6467` | Critical metric (heart rate alert, low score) |
| `health.red.bg` | `#FF6467` @ 8% | Background tint for critical metrics |
| `health.red.border` | `#FF6467` @ 15% | Border for critical state containers |
| `health.gold` | `#FEE685` | Caution/warning metric |
| `health.gold.text` | `#FEE685` @ 50% | Text color for gold/warning labels |
| `health.amber.bg` | `#FFB900` @ 10% | Background tint for warning state |
| `health.amber.border` | `#FFB900` @ 20% | Border for warning state containers |
| `health.amber.text` | `#FFB900` @ 40% | Text color for amber/caution state |
| `health.amber.dim` | `#FFB900` @ 35% | Dimmed secondary health info |
| `health.label` | `#FEE685` @ 55% | Text for health metric labels |
| `health.heart` | `#FF6467` | Heart rate specific (alias of health.red) |
| `health.sleep` | `#8B5CF6` | Sleep metric accent (purple) |

### 2.8 Trading & Activity Colors

Used in the trading module for bot status, P&L indicators, and order state.

| Token | Hex | Usage |
|-------|-----|-------|
| `trading.cyan` | `#00D7FF` | Bot status, order state indicators |
| `trading.positive` | `#00FFB2` | Profit, positive trade outcome |
| `trading.negative` | `#FF6467` | Loss, negative trade outcome (alias of health.red) |

### 2.9 Chat Colors

Specific to message bubbles, input bar, and conversation UI.

| Token | Hex / Value | Usage |
|-------|-------------|-------|
| `chat.aiBubble` | `#E8E2D9` @ 12% | AI message bubble background |
| `chat.userBubble` | `#FF9F0A` @ 15% | User message bubble background |
| `chat.userText` | `#1A1005` @ 80% | User bubble text (dark on amber tint) |
| `chat.userTextShort` | `#442B11` | Short user message text (single-line) |
| `chat.input` | `#1E1308` | Chat input bar background (alias of bg.input) |

### 2.10 Editor & Code Colors

Used in terminal/code display contexts.

| Token | Hex | Usage |
|-------|-----|-------|
| `editor.bg` | `#1E1E1E` | Code editor / terminal background |
| `editor.bg.alt` | `#1A1A1A` | Alternate editor background (contrast areas) |

### 2.11 Diagram & Visualization Colors

Used in the Research knowledge graph and canvas visualizations.

| Token | Hex | Usage |
|-------|-----|-------|
| `diagram.apple` | `#007AFF` | Apple ecosystem entity nodes |
| `diagram.cloud` | `#5AC8FA` | Cloud provider / service nodes |
| `diagram.default` | `#FF9F0A` | Default entity node color (amber) |

### 2.12 Text Colors (renumbered from 2.7)

Text uses warm beige tones on dark backgrounds, never pure white.

| Token | Hex/Opacity | Usage |
|-------|-------------|-------|
| `text.primary` | `#E8E2D9` | Body text, headings |
| `text.secondary` | `#E8E2D9` @ 55% | Subtitles, metadata, timestamps |
| `text.tertiary` | `#E8E2D9` @ 35% | Placeholders, disabled labels |
| `text.inverse` | `#1A1005` | Text on amber/bright backgrounds |
| `text.link` | `#FF9F0A` | Tappable text, in-line links |
| `text.code` | `#FFCA80` | Inline code, monospace highlights |

### 2.8 Border & Glow

Borders are the primary mechanism for defining glass edges. They glow subtly on interactive surfaces.

| Token | Value | Usage |
|-------|-------|-------|
| `border.subtle` | `#FF9F0A` @ 6% | Card resting state |
| `border.default` | `#FF9F0A` @ 12% | Card hover, panel edges |
| `border.strong` | `#FF9F0A` @ 20% | Active panels, focused inputs |
| `border.accent` | `#FF9F0A` @ 40% | Active nav indicator, selected card |
| `border.glow` | `#FF9F0A` @ 8%, 4px blur | Luminous halo on hover (box-shadow equivalent) |
| `border.divider` | `#E8E2D9` @ 8% | Section separators |

---

## 3. Typography

### 3.1 Type Scale

SF Pro throughout. Volkhov-Bold reserved for the brand wordmark only (not headings).

| Token | Size | Weight | Usage |
|-------|------|--------|-------|
| `type.hero` | 32pt | Semibold | Dashboard hero numbers, large stats |
| `type.title` | 22pt | Semibold | Page titles ("Command Center") |
| `type.heading` | 18pt | Medium | Section headings within a page |
| `type.subheading` | 15pt | Medium | Card titles, list group headers |
| `type.body` | 14pt | Regular | Default body text |
| `type.bodyMedium` | 14pt | Medium | Emphasized body (bold without bold) |
| `type.caption` | 12pt | Regular | Timestamps, metadata, secondary info |
| `type.captionMedium` | 12pt | Medium | Badge labels, tab labels |
| `type.micro` | 10pt | Medium | Axis labels, fine print |
| `type.code` | 13pt | Regular (mono) | Code blocks, technical values |

### 3.2 Special Uses

| Token | Spec | Usage |
|-------|------|-------|
| `type.brand` | Volkhov-Bold, 28pt | "Hestia" wordmark only |
| `type.sectionLabel` | 11pt, Semibold, UPPERCASE, 0.8pt tracking | Card section headers (iOS pattern) |
| `type.input` | 15pt, Regular | Text fields, chat input |
| `type.chat` | 15pt, Regular | Chat message body |
| `type.chatSender` | 13pt, Medium | Message sender labels |

### 3.3 Line Heights

Body text: 1.5× font size. Headings: 1.25× font size. Captions: 1.4× font size.

---

## 4. Spacing & Layout

### 4.1 Spacing Scale

8pt base rhythm, unchanged from current system.

| Token | Value | Usage |
|-------|-------|-------|
| `space.xs` | 4pt | Tight gaps (icon-to-label within a button) |
| `space.sm` | 8pt | Default inner padding, list item gaps |
| `space.md` | 12pt | Card inner padding, section gaps |
| `space.lg` | 16pt | Between cards, panel padding |
| `space.xl` | 20pt | Section separators |
| `space.2xl` | 24pt | Major section gaps |
| `space.3xl` | 32pt | Page-level padding, hero spacing |

### 4.2 Corner Radii

Rounded, generous, Apple-aligned.

| Token | Value | Usage |
|-------|-------|-------|
| `radius.sm` | 8pt | Badges, small pills, input fields |
| `radius.md` | 12pt | Buttons, list items |
| `radius.lg` | 16pt | Cards, panels, popovers |
| `radius.xl` | 20pt | Modal dialogs, large containers |
| `radius.pill` | 9999pt (capsule) | Chat input bar, nav pills, search |
| `radius.circle` | 50% | Avatars, status dots |

### 4.3 Layout Zones (macOS)

| Zone | Width | Notes |
|------|-------|-------|
| Icon sidebar | 64pt | Reduced from 68pt — tighter, more Apple-native |
| Content area | Flexible (min 560pt) | Main workspace |
| Chat panel | 480pt (max 540pt) | Slightly narrower, more focused |
| File sidebar | 260pt | When present (Explorer, Orders) |
| Command palette | 520pt × 400pt | Centered modal |
| Top bar | 44pt height | When present |

### 4.4 Responsive Breakpoints

| Mode | Window Width | Behavior |
|------|-------------|----------|
| Compact | < 700pt | Sidebar collapses to icons, chat panel hidden |
| Standard | 700–1200pt | Full sidebar, chat toggleable |
| Wide | > 1200pt | Full sidebar + chat panel simultaneously |

---

## 5. Navigation Structure

### 5.1 Tab Model — 5 Tabs

| Tab | Icon (SF Symbol) | Label | Shortcut | Purpose |
|-----|-------------------|-------|----------|---------|
| Command | `house.fill` | Command | ⌘1 | Dashboard hub — status, activity, quick actions |
| Orders | `bolt.fill` | Orders | ⌘2 | Workflow/order management + execution |
| Memory | `brain.head.profile` | Memory | ⌘3 | Knowledge graph, canvas, research, principles |
| Explorer | `magnifyingglass` | Explorer | ⌘4 | File browser, inbox, resources |
| Settings | (Avatar) | Settings | ⌘5 | Profile, agents, integrations, wiki |

**Removed from primary nav:** Health (backburner — accessible via Command Center card or ⌘K if needed later).

### 5.2 Sidebar Design

The sidebar is a vertical strip of glass with icon buttons. It uses true translucency (`glass.sidebar`).

```
┌──────┐
│      │  ← 12pt top padding
│  ◉   │  ← Hestia logo (28×28, amber glow on idle)
│      │
│ ─────│  ← Subtle divider (border.divider)
│      │
│  ⌂   │  ← Command (36×36 hit target, 20pt icon)
│  ⚡  │  ← Orders
│  🧠  │  ← Memory
│  🔍  │  ← Explorer
│      │
│      │  ← Spacer
│      │
│  AV  │  ← Settings (avatar circle, 32×32)
│      │  ← 12pt bottom padding
└──────┘
  64pt
```

**Active state:** Icon tinted `amber.400`, glass pill highlight behind icon (`border.accent` + `bg.elevated`), 3pt × 14pt amber indicator pill on left edge (gradient `#FFB900` → `#FF8904`).

**Hover state:** Icon brightens to `text.primary`, background fills to `bg.elevated` @ 50%.

**Transition:** `matchedGeometryEffect` for the active pill. Spring animation (0.2s, damping 0.8).

### 5.3 Command Palette (⌘K)

Floating glass modal, centered. Uses `glass.input` material for the search bar.

- Capsule-shaped search input at top
- Fuzzy-filtered command list below
- Arrow key navigation, Enter to execute
- Dismiss on Escape or click outside
- Results grouped by category with `type.sectionLabel` headers

---

## 6. Glass Components

### 6.1 HestiaGlassCard

The primary content container. Replaces current `HestiaCard` and `HestiaPanelModifier`.

```
┌─────────────────────────────────┐  ← border.subtle (resting)
│                                 │     border.default (hover)
│  SECTION LABEL                  │  ← type.sectionLabel, text.tertiary
│                                 │
│  Card Title                     │  ← type.subheading, text.primary
│  Supporting text or content     │  ← type.body, text.secondary
│                                 │
│  [Action Pill]  [Action Pill]   │  ← HestiaGlassPill buttons
│                                 │
└─────────────────────────────────┘

Background: bg.elevated
Border: 0.5pt, border.subtle → border.default on hover
Corner radius: radius.lg (16pt)
Padding: space.md (12pt) inner
Hover: border glow (border.glow), slight scale (1.005×)
```

**Variants:**
- **Default**: As above
- **Accent**: Left edge 2pt amber border (for active/highlighted cards)
- **Interactive**: Cursor changes to pointer, press scale 0.98×

### 6.2 HestiaGlassInput

Capsule-shaped input field with glass material. Used for chat input, search, command palette.

```
┌─────────────────────────────────────────┐
│  🔍  Placeholder text...          [mic] │
└─────────────────────────────────────────┘

Background: glass.input (translucent on supported surfaces, bg.input fallback)
Border: 0.5pt, border.default → border.strong on focus
Corner radius: radius.pill (capsule)
Height: 44pt
Padding: space.md horizontal
Focus: border.accent + subtle amber glow
```

### 6.3 HestiaGlassPill

Small tinted action button. Replaces `HestiaPillButton`.

```
┌──────────────────┐
│  ⚡  Action Name  │
└──────────────────┘

Background: tint color @ 12% opacity
Border: tint color @ 20%, 0.5pt
Corner radius: radius.sm (8pt)
Padding: space.xs vertical, space.md horizontal
Text: type.captionMedium, tint color
Icon: 14pt, medium weight, tint color
Press: scale 0.96×, opacity 0.8
```

### 6.4 HestiaGlassBadge

Status indicator with dot and label. Replaces `HestiaStatusBadge`.

```
● Healthy

Dot: 8pt circle, status color, subtle glow (2px blur)
Text: type.caption, status color
Background: status color @ 8%
Corner radius: radius.sm
Padding: space.xs vertical, space.sm horizontal
```

### 6.5 HestiaGlassSettingsBlock

Notion-style navigation row. Replaces `HestiaSettingsBlock`.

```
┌─────────────────────────────────────────┐
│  [icon]  Title                      ▸   │
│          Subtitle description           │
└─────────────────────────────────────────┘

Icon: 20pt SF Symbol in 36pt frame, tinted, radius.sm background @ 12%
Title: type.body, Medium weight, text.primary
Subtitle: type.caption, text.secondary
Chevron: text.tertiary
Background: bg.elevated
Border: 0.5pt, border.subtle
Corner radius: radius.lg (16pt)
Padding: space.md
Hover: border.default + cursor pointer
```

### 6.6 HestiaGlassDetailPane

Generic 3-state detail pane (loading / error / empty / content). Retains the pattern from `HestiaDetailPane` with updated styling.

- Header region: sticky, `bg.surface` with bottom `border.divider`
- Content region: scrollable, `bg.surface`
- Footer region: optional, sticky bottom
- Loading: centered amber spinner (not system blue)
- Error: centered, `status.error` text with retry pill
- Empty: centered illustration + `text.tertiary` message

---

## 7. Animation & Interaction

### 7.1 Motion Tokens

| Token | Duration | Curve | Usage |
|-------|----------|-------|-------|
| `motion.fast` | 0.15s | `spring(response: 0.2, damping: 0.85)` | Button press, icon swap |
| `motion.normal` | 0.25s | `spring(response: 0.3, damping: 0.8)` | Tab switch, panel resize |
| `motion.slow` | 0.40s | `spring(response: 0.45, damping: 0.75)` | Modal open/close, page transition |
| `motion.gentle` | 0.60s | `easeInOut` | Ambient glow, subtle state transitions |
| `motion.orb` | 4.00s | `easeInOut` | Orb breathing pulse, glow shift (also uses `linear` for spin) |

### 7.2 Interaction States

| State | Visual Change |
|-------|---------------|
| Hover | Border brightens (subtle → default), cursor changes, optional glow |
| Press | Scale 0.96–0.98×, opacity 0.85 |
| Focus | Border accent + amber glow ring |
| Active (nav) | Amber tint, indicator pill, icon color change |
| Disabled | Opacity 0.4, no hover/press response |
| Loading | Shimmer animation (existing SkeletonModifier pattern) |

### 7.3 Sensory Feedback

- Tab switch: `.impact(weight: .light)` haptic (existing)
- Button press: no haptic (too frequent)
- Modal open: `.impact(weight: .medium)` haptic
- Error: `.notificationOccurred(.error)` haptic

---

## 8. The Orb — Login & Loading

The luminous orb is Hestia's visual identity mark, used on the login/onboarding screen and during app loading states. It is NOT used in the main app chrome for v1.

### 8.1 Visual Spec — Morphing Luminous Ribbons

Inspired by the Apple Intelligence Siri orb (in Hestia's amber palette). **There is no solid sphere.** The orb is composed entirely of 3 luminous ribbon arcs curving through dark empty space. The "sphere" is implied by the curvature of the bands and depth-dimming (bright when "near," dim when "far"). A faint volumetric glow at the center hints at the spherical volume without occluding the bands.

**Design principles (from video reference analysis):**
- Bands are the entire visual — no opaque geometry blocks them
- Each band has a unique shape (different eccentricity, size, thickness)
- Brightness morphs organically along each band over time, not fixed
- Depth illusion via near/far brightness variation
- Heavy bloom/glow halo around each band
- Additive blending where bands cross (intersections brighten)
- Organic wobble breaks rigid mechanical rotation

**Size:** ~200pt diameter on macOS, ~160pt on iOS

#### Center Glow (volumetric hint)

A faint radial gradient at the center — enough to suggest volume, never enough to block:
- `radial-gradient(circle, amber.400 @ 12% center, amber.500 @ 5% at 40%, transparent at 70%)`
- Subtle box-shadow: `0 0 80pt 20pt amber.400 @ 8%`
- No solid background, no overflow clipping

#### Ribbon Specifications

Each ribbon is a **conic-gradient masked into a ring shape**, not a CSS border. This enables the brightness "hot spot" to animate independently of the ring's rotation, creating the morphing effect where the band appears to thicken, brighten, dim, and thin as it orbits.

**Rendering technique:** `background: conic-gradient(from var(--glow-angle), ...)` masked with `radial-gradient(transparent inner%, black ring%, transparent outer%)`. The `--glow-angle` custom property animates via `@property` at a different speed than the Z-spin, so the bright zone crawls around the ring independently.

| Ribbon | Shape | Eccentricity | Tilt (rotateX/Y) | Spin Speed | Glow Shift Speed | Peak Color | Ring Width |
|--------|-------|-------------|-------------------|------------|------------------|------------|------------|
| **1 (Primary)** | Wide horizontal oval | High | 65° X, 10° Y | 6.5s | 8s | `amber.200` @ 95% | ~9pt (varies) |
| **2 (Secondary)** | Taller, rounder arc | Medium | 48° X, -32° Y | 8s (reverse) | 11s | `amber.400` @ 92% | ~7pt (varies) |
| **3 (Accent)** | Narrow steep ellipse | High | 76° X, 22° Y | 11s | 15s | `amber.600` @ 40% | ~5pt (varies) |

Each ribbon's conic-gradient transitions from peak brightness (~95% near arc) through medium (~40% transition zones) to near-transparent (~3% far arc) and back, creating the depth illusion. As the gradient angle animates independently of the spin, the bright zone shifts continuously — no two moments look the same.

#### Bloom Halos

Each ribbon has a companion bloom layer (its `::after` pseudo-element): same conic-gradient technique but with a wider ring mask (18-26pt) and 14-22pt gaussian blur. This creates the soft light bleed visible in the reference.

#### Animation Layers (per ribbon)

Three independent animation layers combine to create organic motion:

| Layer | Property | Duration | Easing | Purpose |
|-------|----------|----------|--------|---------|
| Z-Spin | `transform: rotateZ()` | 6-12s | linear | Orbital rotation on the tilted plane |
| Wobble | `transform: rotateX/Y()` (on wrapper) | 9-14s | ease-in-out | Organic tilt oscillation (±3-5°) |
| Glow Shift | `--glow-angle` (CSS @property) | 8-15s | linear | Brightness zone crawl — the morphing effect |

The wobble and spin are separated onto parent/child DOM elements to avoid CSS transform conflicts.

#### Overall Breathing

The entire orb container pulses with a gentle breathing animation: `scale(1.0 → 1.02)` + `brightness(1.0 → 1.1)` over a 4s ease-in-out cycle.

#### Background Ambient Wash

The login screen background behind the orb gets layered radial gradients to simulate ambient light cast by the orb:
- `radial-gradient(ellipse at 50% 30%, amber.400 @ 10%, transparent 40%)`
- `radial-gradient(ellipse at 50% 35%, amber.700 @ 8%, transparent 55%)`

### 8.2 States

| State | Behavior |
|-------|----------|
| Idle | Ribbons rotate at base speeds, breathing glow (scale 1.0 → 1.02, 4s cycle), glow shift active |
| Loading | Spin speeds increase 2×, glow shift speeds increase 1.5×, center glow intensifies to 20%, breathing accelerates to 2s |
| Connecting | Ribbons briefly align tilt planes (wobble converges), then desync — visual "handshake" |
| Error | Spin slows to near-stop, glow shift pauses, color shifts toward `status.error` @ 40%, center glow dims to 5% |

### 8.2.1 SwiftUI Implementation Notes

**Recommended approach:** `Canvas` with `GraphicsContext` for maximum control over the gradient ring rendering and bloom effects. Each ribbon is drawn as a stroked elliptical arc with a `ConicGradient` fill whose start angle animates independently.

**Alternative for macOS 26+:** `MeshGradient` could provide the fluid brightness morphing natively. Would need benchmarking against Canvas for performance.

**Architecture:**
- Standalone `HestiaOrb` view accepting a `state: Binding<OrbState>`
- `TimelineView(.animation)` drives all animation state (spin angles, wobble offsets, glow angles)
- Each ribbon rendered via `rotation3DEffect()` for the tilt plane, `rotationEffect()` for Z-spin
- Bloom layer = same path drawn twice: sharp stroke + blurred duplicate behind
- Use `blendMode(.screen)` for additive crossing behavior
- `drawingGroup()` to flatten GPU layers for performance

### 8.3 Surrounding UI (Login Screen)

```
┌──────────────────────────────┐
│                              │
│                              │
│           ◉ (orb)            │  ← Centered, upper third
│                              │
│        Hello Andrew          │  ← type.body, text.secondary
│     How can I help           │  ← type.title, text.primary
│       you today?             │
│                              │
│                              │
│  ┌────────────────────────┐  │
│  │ Ask anything...   [mic]│  │  ← HestiaGlassInput (capsule)
│  └────────────────────────┘  │
│                              │
└──────────────────────────────┘

Background: Radial gradient
  Center: amber.700 @ 12%
  Mid: bg.surface
  Edge: bg.base
Bottom: Subtle amber-to-transparent gradient wash
```

### 8.4 Future Consideration

The orb may later appear in the chat panel header as a presence indicator (idle/thinking/responding). This is scoped out of v1 but the component should be built as a standalone `HestiaOrb` view for reuse.

---

## 9. Screen-Level Guidelines

These are directional notes for when each screen is redesigned. Implementation details will be specced per-screen.

### 9.1 Command Center

The daily-use hub. Should surface the most important information at a glance without requiring clicks.

- Hero area: system status badge + greeting + Hestia orb (small, 48pt, subtle glow — NOT the full login orb)
- Live cards: Trading bot status (green/amber/red per bot), recent orders, calendar next-up
- Activity feed: Single scrollable timeline (not 3 separate tabs — merge system/internal/external with filter pills)
- Quick actions: Glass pill buttons for common operations ("New Order", "Open Chat", "Search Memory")
- All data must be live — no hardcoded values

### 9.2 Orders (Workflows)

- Left sidebar: order list with status badges and search
- Right detail: order inspector with node visualization
- Active orders should pulse with subtle amber glow
- Completed orders use `text.secondary` / muted treatment

### 9.3 Memory (Research)

- Default view: 2D knowledge graph (React Flow canvas)
- Secondary views accessible via segmented control: Graph | Canvas | Principles | Browser
- Graph should use amber nodes (entities), green edges (relationships), dark background
- Detail pane slides in from right for selected entity

### 9.4 Explorer

- File browser: tree view + preview (keep current pattern, update styling)
- Inbox: separate section (not a toggle — use segmented control or sub-tabs)
- Glass treatment on the file tree sidebar

### 9.5 Settings

- Two-column layout: left nav list + right detail pane (not accordion)
- Sections: Profile, Agents, Integrations, Wiki, About
- Each section rendered as a scrollable detail view with HestiaGlassSettingsBlock rows
- Wiki gets its own section (promoted from buried inside Settings)

### 9.6 Chat Panel

- Glass background (`glass.chatPanel`)
- Message bubbles: AI uses `bg.elevated` with `border.subtle`, user uses `amber.400` @ 15% background
- Input bar: `HestiaGlassInput` (capsule) pinned to bottom
- Thinking state: animated dots with amber tint
- Session controls in a minimal header bar

---

## 10. Migration Guide

### 10.1 Token Renames (MacColors.swift)

| Current Token | New Token | Change |
|---------------|-----------|--------|
| `windowBackground` (#0D0802) | `bg.surface` | Rename only |
| `sidebarBackground` (#0A0603) | `bg.base` | Rename, add glass material |
| `panelBackground` (#110B03) | `bg.elevated` | Rename only |
| `chatInputBackground` (#261302) | `bg.input` | Value update to `#1E1308` |
| `amberAccent` (#E0A050) | `amber.400` | **Value change to `#FF9F0A`** |
| `amberBright` (#FFB900) | `amber.300` | Map to scale |
| `amberDark` (#FF8904) | `amber.500` | Map to scale |
| `textPrimary` (#E4DFD7) | `text.primary` | Slight warmth adjustment to `#E8E2D9` |
| `textSecondary` (50%) | `text.secondary` | Update to 55% |
| `textPlaceholder` (40%) | `text.tertiary` | Update to 35% |
| `healthGreen` (#00D492) | `green.300` → `#72F69E` | Align with status system |
| `statusGreen` (#72F69E) | `status.healthy` → `#34C759` | Align with Apple system green |

### 10.2 Agent Color Removal

The multi-agent color system is removed from the UI. Hestia is the only user-facing agent.

| What | Action |
|------|--------|
| `MacColors.accentColor(for mode:)` | **Delete.** Replace all call sites with `amber.400` |
| `MacColors` mode-specific colors (`.tia`, `.mira`, `.olly`) | **Delete.** No longer referenced |
| `Colors+iOS.agentTeal` (`#30D5C8`) | **Deprecate.** Not used in user-facing UI |
| `Colors+iOS.agentPurple` (`#BF5AF2`) | **Deprecate.** Not used in user-facing UI |
| `Colors+iOS.agentAmber` (`#FF9F0A`) | **Rename** to `accent` or `amber.400` — it's just the primary accent now |
| All `amberAccent` references (82 files) | **Rename** to `amber.400`, **value change** from `#E0A050` → `#FF9F0A` |

### 10.3 Component Migration

| Current | New | Notes |
|---------|-----|-------|
| `HestiaCard` | `HestiaGlassCard` | Shared component, both platforms |
| `HestiaPillButton` | `HestiaGlassPill` | Shared component |
| `HestiaStatusBadge` | `HestiaGlassBadge` | Shared component |
| `HestiaSettingsBlock` | `HestiaGlassSettingsBlock` | Shared component |
| `HestiaDetailPane` | `HestiaGlassDetailPane` | macOS, updated styling |
| `HestiaPanelModifier` | Absorbed into glass tokens | Remove dedicated modifier |
| `HestiaButtonStyle` | Retained, updated values | Press scale + glow |
| `HestiaSidebarSection` | `HestiaGlassSidebarSection` | macOS — collapsible sidebar section wrapper (DisclosureGroup). Used in Research, Wiki, Workflow, Explorer sidebars. Update: disclosure tint → `text.tertiary`, hover bg → `bg.elevated` @ 30%, animation → `motion.normal` |
| `HestiaContentRow` | `HestiaGlassContentRow` | macOS — standardized list row (dot/icon + title/subtitle + trailing label). Used everywhere. Update: selection bg → `bg.elevated` @ 50% + `border.subtle`, trailing label gets `border.subtle` 0.5pt, hover → `border.default`, corner radius → `radius.sm` |
| `HestiaCrossLinkBadge` | `HestiaGlassCrossLinkBadge` | macOS — cross-module link pill in Research detail pane. **Redesign:** Unify all module indicators to `amber.400` (single accent). Drop per-module colors (cyan, blue, purple). Keep SF Symbol icons for context. Use `border.subtle` + `bg.elevated` glass styling. |

### 10.4 Unmapped Token Migration

Tokens that exist in current `MacColors.swift` but were not in the original migration guide. Now mapped:

| Current Token | New Token | Notes |
|---------------|-----------|-------|
| `healthGold` (#FEE685) | `health.gold` | Direct map |
| `healthGreenBg` | `health.green.bg` | Opacity preserved |
| `healthRedBg` | `health.red.bg` | Opacity preserved |
| `healthRedBorder` | `health.red.border` | Opacity preserved |
| `healthAmberBg` | `health.amber.bg` | Opacity preserved |
| `healthAmberBorder` | `health.amber.border` | Opacity preserved |
| `healthGoldText` | `health.gold.text` | Opacity preserved |
| `healthAmberText` | `health.amber.text` | Opacity preserved |
| `healthDimText` | `health.amber.dim` | Renamed for clarity |
| `healthLabelText` | `health.label` | Simplified name |
| `heartRed` (#FF6467) | `health.heart` | Alias of `health.red` |
| `sleepPurple` (#8B5CF6) | `health.sleep` | Direct map |
| `calorieRed` (#FF6467) | **Remove** — redundant | Identical to `heartRed` / `health.red` |
| `cyanAccent` (#00D7FF) | `trading.cyan` | Trading module specific |
| `healthLime` (#00FFB2) | `trading.positive` | Repurposed for trading P&L |
| `aiBubbleBackground` | `chat.aiBubble` | Direct map |
| `userBubbleText` | `chat.userText` | Direct map |
| `userBubbleTextShort` (#442B11) | `chat.userTextShort` | Direct map |
| `editorBackground` (#1E1E1E) | `editor.bg` | Direct map |
| `editorBackgroundAlt` (#1A1A1A) | `editor.bg.alt` | Direct map |
| `blueAccent` / `diagramApple` (#007AFF) | `diagram.apple` | Consolidated |
| `diagramCloud` (#5AC8FA) | `diagram.cloud` | Direct map |
| `systemBlue` (#0A84FF, iOS) | `status.info` | Already defined in spec §2.6 |

### 10.5 SwiftUI API Usage

For macOS Tahoe (macOS 26+), use native Liquid Glass APIs where available:

```swift
// Native glass effect (macOS 26+ / iOS 26+)
.glassEffect(.regular, in: .capsule)

// Tinted glass
.glassEffect(.regular, in: .rect(cornerRadius: 16))
.tint(.orange)

// Glass container for grouped elements
GlassEffectContainer {
    // Child glass views morph into each other
}

// Fallback for macOS 15 (current minimum target)
.background(.ultraThinMaterial)
.background(Color("bg.elevated").opacity(0.95))
```

**Deployment strategy:** Build the design system with the simulated glass approach (solid backgrounds + luminous borders) for macOS 15.0 compatibility. Add `#available(macOS 26, *)` branches for native `.glassEffect()` when targeting Tahoe. This ensures the app looks great on both OS versions.

---

## 11. Implementation Phases

### Phase 0: Design Token Foundation (This Document)
- Finalize this spec with Andrew's feedback
- No code changes yet

### Phase 1: Token Migration (~4-6h)
- Create `HestiaDesignTokens.swift` (shared, cross-platform)
- Migrate `MacColors.swift` → new token system
- Migrate `MacTypography.swift` → new type scale
- Migrate `MacSpacing.swift` → new spacing tokens
- Ensure zero visual regression (values map 1:1 where possible)

### Phase 2: Glass Components (~6-8h)
- Build `HestiaGlassCard`, `HestiaGlassPill`, `HestiaGlassBadge`, `HestiaGlassInput`
- Build `HestiaGlassSettingsBlock`, `HestiaGlassDetailPane`
- Build `HestiaOrb` (login/loading) — Canvas-based morphing conic-gradient ribbons per Section 8
- Deprecate old components (keep as aliases initially)

### Phase 3: Core Screen Refresh (~10-15h per screen)
- Command Center first (highest daily use)
- Chat Panel second (always visible)
- Settings third (validates the block/settings pattern)
- Remaining screens in priority order

### Phase 4: Polish & Platform Convergence (~4-6h)
- Align iOS components to same token system
- Add macOS 26 native glass branches
- Accessibility audit (contrast ratios on glass surfaces)
- Animation polish pass

---

## Appendix A: Accessibility on Glass

Translucent surfaces can compromise contrast. Rules:

1. **All text on glass must meet WCAG 2.1 AA** (4.5:1 for body, 3:1 for large text)
2. Glass surfaces that contain text must have a minimum tint opacity that guarantees contrast even on bright backgrounds
3. **Increased Contrast mode:** When the user has "Increase Contrast" enabled in System Preferences, all glass surfaces fall back to opaque `bg.elevated` backgrounds
4. **Reduce Transparency mode:** When enabled, all glass surfaces fall back to opaque equivalents automatically (SwiftUI handles this for `.material` backgrounds)
5. Focus rings use `border.accent` (high contrast amber) with 2pt width

## Appendix B: Dark Mode Only (v1)

This design system is dark-mode only. A light mode is not planned for v1. If light mode is added later:

- All `bg.*` tokens would need light equivalents
- `text.*` tokens would invert (dark text on light backgrounds)
- Glass materials would shift to lighter tints
- The amber accent works well in both modes — no change needed
- Semantic colors (status.*) may need slight adjustments for contrast

The token naming system is designed to support this extension — just add a `ColorScheme` switch at the token level without changing any call sites.

## Appendix C: References

- [Apple Liquid Glass Overview](https://developer.apple.com/documentation/TechnologyOverviews/liquid-glass)
- [Applying Liquid Glass to Custom Views](https://developer.apple.com/documentation/SwiftUI/Applying-Liquid-Glass-to-custom-views)
- [SwiftUI .glassEffect() API](https://developer.apple.com/documentation/swiftui/view/glasseffect(_:in:))
- [GlassEffectContainer](https://developer.apple.com/documentation/swiftui/glasseffectcontainer)
- [WWDC25: Build a SwiftUI App with the New Design](https://developer.apple.com/videos/play/wwdc2025/323/)
- [WWDC25: Get to Know the New Design System](https://developer.apple.com/videos/play/wwdc2025/356/)
- [WWDC25: Meet Liquid Glass](https://developer.apple.com/videos/play/wwdc2025/219/)
