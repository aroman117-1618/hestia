# Figma Make Prompt — Hestia AI Particle Wave

## What to Build

An animated, interactive particle wave visualization for "Hestia," a personal AI assistant. The visual is a **flowing field of thousands of luminous amber particles** forming undulating wave shapes — like dust caught in light, or a murmuration of glowing embers. It floats on a pure black background and responds to two states: Listening (calm, gentle drift) and Speaking (alive, pulsing with confident energy). The attached reference images show the exact visual language — flowing particle waves with ethereal glow — but converted from blue/purple to Hestia's warm amber/orange palette.

## Core Visual — Luminous Particle Wave Field

This is NOT a solid object. It's a **cloud of thousands of individual glowing particles** that collectively form flowing, wave-like shapes. Think of it as a horizontal ribbon of luminous dust — wider in the center, tapering at the edges — undulating gently like a slow-motion ocean wave or silk scarf caught in a breeze.

### Particle Properties

Each particle is a tiny point of light, individually rendered:

- **Size:** Varies. Most particles are tiny (1-2px). Some are larger "hero" particles (3-6px) that act as bright focal points scattered throughout the wave.
- **Brightness:** Varies per particle. Some are bright and crisp, others are dim and soft. The distribution creates a sense of density and depth — denser bright clusters in the wave's core, sparse dim particles at the fringes.
- **Color:** Warm amber spectrum. Individual particles range from near-white (`#FFF0D0`) through bright amber (`#FF9F0A`) to deep orange (`#C06800`). A subtle secondary accent of warm gold (`#FFD700`) adds shimmer. No blue, no purple — entirely warm-toned.
- **Glow/Bloom:** Each bright particle has a soft radial glow halo around it, like a tiny out-of-focus light source. This bloom is what gives the wave its ethereal, luminous quality.
- **Opacity:** Particles fade in and out as they move through the wave, creating a sense of particles flowing through a visible zone rather than a fixed shape.

### Wave Shape & Flow

The particles collectively form **2-3 flowing wave ribbons** that undulate horizontally across the viewport:

- **Primary wave:** The dominant, densest ribbon of particles. Occupies the center of the composition. Has the most pronounced vertical undulation — like a sine wave with organic irregularity.
- **Secondary wave:** A fainter, offset wave that weaves above/below the primary. Creates depth and visual complexity. Slightly out of phase with the primary.
- **Scattered particles:** Individual particles that drift beyond the main wave bodies — like sparks or embers detaching from the flow. These extend the visual envelope and make the edges feel organic rather than hard-cut.

The waves flow **continuously from left to right** (or right to left), with particles streaming along the wave path. The vertical undulation is slow and organic — not mechanical. Multiple overlapping sine waves at different frequencies create the irregular, natural-feeling motion (like real ocean swells).

### Depth & Dimension

The wave field has implied depth:

- **Foreground particles:** Larger, brighter, sharper. They move slightly faster (parallax).
- **Background particles:** Smaller, dimmer, softer/blurred. They move slightly slower.
- **This parallax layering creates a 3D volume** even though each particle is 2D. The wave feels like it occupies space, not a flat plane.

### Reflective Surface (Optional)

Below the wave, a subtle reflective "floor" — a faint mirror-image of the wave reflected downward, fading quickly to black. Like the wave is hovering above a dark glass surface. This is visible in the reference and adds grounding.

## Color Palette

Dark-mode only. Pure black background, warm amber particles.

### Particle Colors (Amber Spectrum)
- **Brightest highlights:** `#FFF0D0` — near-white with warm tint (hero particles, brightest points)
- **Bright amber:** `#FFB347` — warm bright amber (upper quartile particles)
- **Primary amber:** `#FF9F0A` — canonical Hestia accent (majority of visible particles)
- **Mid amber:** `#E08A00` — the body color of the wave density
- **Deep orange:** `#C06800` — dimmer particles, edges of the wave
- **Ember:** `#8B4500` — the faintest, most distant particles
- **Gold shimmer:** `#FFD700` at 40% — occasional bright accent particles for sparkle

### Particle Glow
Each particle's glow halo uses the same color as the particle but at ~20-30% opacity with a gaussian blur radius of 2-8px (proportional to particle brightness).

### Environment
- **Background:** `#000000` to `#050302` — pure black to very faint warm black
- **Ambient light cast:** Very subtle radial gradient of amber on the background behind the densest part of the wave, as if the particles illuminate their surroundings
- **Floor reflection:** If included, a faint (~15% opacity) vertical mirror of the wave, fading to transparent within ~30% of the wave height
- **Text (primary):** `#FFF5E6` — warm off-white
- **Text (secondary):** `#B89060` — muted amber
- **UI chrome:** Glass-style panels with `rgba(255, 159, 10, 0.04)` background and `rgba(255, 159, 10, 0.15)` borders

## Two Interactive States

### Listening (Default)
The wave is **calm, gently flowing, meditative.** It drifts with patient presence.

- **Flow speed:** Slow, steady horizontal streaming. Particles take ~8-10 seconds to traverse the visible area.
- **Wave amplitude:** Gentle vertical undulation. The wave barely rises and falls — serene, not dramatic.
- **Particle density:** Moderate. The wave is visible and defined but not overwhelming.
- **Brightness:** Moderate overall. Soft, even glow. Hero particles are present but not dominant.
- **Scale pulse:** None. Perfectly still in scale.
- **Mood:** Patient, attentive, waiting. Like Jarvis in standby — the arc reactor glowing steadily, ready but not urgent. "Sir, whenever you're ready."

### Speaking
The wave **comes alive with measured, confident energy.** Not frantic — think Jarvis or Friday mid-briefing.

- **Flow speed:** ~2x faster than listening. Particles stream with visible momentum.
- **Wave amplitude:** More pronounced vertical motion. The wave crests higher and dips lower — like the surface of water responding to a voice.
- **Particle density:** Higher. More particles become visible, the wave becomes denser and more defined. Additional scattered particles appear in the periphery like sparks.
- **Brightness:** Noticeably brighter. More hero particles appear. The overall glow intensifies.
- **Scale pulse:** The entire wave field gently pulses in scale and brightness:
  - Scale: `1.0 → 1.04 → 1.0` on a ~1.8 second sine-wave cycle
  - Brightness: glow intensity increases ~15% at peak scale, decreases at trough
  - This creates a "breathing with speech" rhythm — calm, confident, measured
  - The pulse should feel like the wave is swelling with each thought or phrase, not vibrating
- **Scattered sparks:** More individual bright particles break free from the main wave, drifting upward or outward before fading. Like embers rising from a fire.
- **Mood:** Confident, engaged, deliberate. Like Friday explaining a tactical analysis — calm authority with visible energy. "The data suggests three options, boss."

### State Transition
Smooth interpolation over ~0.8 seconds. When entering Speaking, the wave density gradually increases, the flow accelerates, and the scale pulse fades in (first pulse starts at 50% amplitude, reaching full within 2 cycles). When returning to Listening, the last pulse completes naturally, then the wave settles gracefully — density thins, speed eases, brightness softens.

## Layout

Full-screen dark background. The wave is centered vertically, spanning most of the screen width.

1. **The particle wave** — horizontally centered, occupying ~70-80% of viewport width. Vertically centered or slightly above center. The wave height (including scattered particles) is ~200-250px.
2. **Greeting line:** "Hello Andrew" — 16px, `#B89060`, centered above the wave with ~48px spacing.
3. **Main prompt:** "How can I help you today?" — 32px, weight 700, `#FFF5E6`, centered below the wave with ~48px spacing.
4. **Input bar:** Capsule-shaped, glass material, at bottom of screen. "Ask anything..." placeholder with microphone icon. Border: `rgba(255, 159, 10, 0.15)`. Background: `rgba(255, 159, 10, 0.04)` with backdrop blur.

### Controls (for prototype interaction)
A small bottom panel with:
- Two toggle buttons: **Listening** / **Speaking** (to switch states interactively)
- Buttons: dark glass style, 12px rounded corners, amber border. Active state gets brighter fill and glow.

## Typography

- **Font:** SF Pro Display (Inter fallback)
- **Greeting:** 16px, regular weight, `#B89060`
- **Main prompt:** 32px, bold (700), `#FFF5E6`
- **Input placeholder:** 16px, regular, `#B89060` at 60% opacity
- **Button labels:** 13px, semibold (600), `#FFF5E6`

## Key Reference

The attached images show 4 variations of the exact visual language to target. They show:
- **Flowing particle waves** — thousands of tiny luminous points forming undulating wave ribbons
- **Ethereal glow** — soft bloom around bright particles creating a dreamlike, atmospheric quality
- **Depth via particle size/brightness** — foreground particles are larger and brighter, background ones are smaller and dimmer
- **Organic flow** — the waves have natural, irregular undulation (not mechanical sine waves)
- **Scattered peripheral particles** — individual bright points drifting beyond the main wave, like sparks or dust motes
- **Reflective floor** — faint mirror image below the wave suggesting a dark glass surface
- **Multiple interleaving ribbons** — 2-3 wave bodies at different phases creating visual complexity

The reference uses blue/purple/cyan colors. Convert this entirely to Hestia's warm amber/orange/gold palette. The visual structure, particle behavior, glow quality, and wave dynamics should match the reference — only the color changes.

## Technical Notes

- Canvas 2D or WebGL particle system
- Each particle: position (x, y), velocity, size, brightness, color, lifetime
- Wave shape defined by layered sine functions with noise for organic irregularity
- Particles follow the wave field with slight individual variation (not locked to exact positions)
- Glow via `shadowBlur` (Canvas 2D) or additive blending with gaussian sprites (WebGL)
- Depth layers: 2-3 particle layers with parallax speed differences
- Target: 2000-5000 visible particles for density, culled when off-screen
- 60fps target, responsive sizing (wave scales with viewport width)
- State transitions via tweened global parameters (wave amplitude, flow speed, density, brightness, scale)
