# Orb v3 Implementation Plan — Ribbons in Empty Space

**Date:** 2026-03-25
**Context:** Third iteration of the Hestia orb for the Liquid Glass design system mockup
**Reference:** Apple Intelligence Siri orb (video: `1d6956a9c499dbe7f69ce142751a6c3b.mp4`)

---

## Root Cause of Previous Failures

**v1** (thin wireframe rings): Too thin, mechanical rotation, no bloom.
**v2** (thick ribbons + solid core): Correct ribbon thickness and bloom, BUT a solid dark circle (`.orb-core` at 90-98% opacity, z-index: 1) blocked all bands behind it. The screenshot shows a big black disc with bands peeking around the edges.

**The fundamental misunderstanding:** We treated the orb as "solid dark sphere with rings orbiting around it." The Apple orb has **no solid sphere at all.**

---

## Analysis from Video Frames (18 frames studied)

### What the Apple orb actually is:

1. **No solid sphere.** The "sphere" is purely implied by the curvature of luminous bands. The center is empty dark space — background shows through.

2. **2-3 luminous ribbon arcs** curving through 3D space. Each is a thick, glowing path (roughly 8-15px equivalent) with heavy bloom.

3. **Depth illusion via brightness variation:** Bands are bright when "in front" of the implied sphere center, and dimmer when "behind" it. This sells the 3D without any occluding geometry.

4. **Bands are always fully visible** — they are never clipped or hidden by a solid element. Even the "behind" portions are visible, just dimmer.

5. **Heavy bloom/glow halo** around each band — soft, wide blur that bleeds into surrounding space.

6. **Faint ambient glow** at center — a very subtle (5-10% opacity) radial gradient suggesting volumetric light, but never opaque enough to hide anything.

7. **Organic motion** — slight tilt wobble over time, not rigid mechanical rotation.

8. **Additive blending** — where bands cross, the intersection brightens.

---

## Implementation Plan

### Architecture: Wobble Wrapper → Ribbon Spinner (keep from v2)

```
.orb                          ← Container, perspective, breathing animation
├── .orb-glow                 ← Center volumetric glow (replaces solid core)
├── .orb-wobble.orb-wobble-1  ← Tilt oscillation wrapper
│   └── .orb-ribbon.orb-ribbon-1  ← Z-spin + visible stroke + bloom
├── .orb-wobble.orb-wobble-2
│   └── .orb-ribbon.orb-ribbon-2
└── .orb-wobble.orb-wobble-3
    └── .orb-ribbon.orb-ribbon-3
```

### Change 1: Replace solid core with volumetric glow

**Delete:** `.orb-core` (the opaque black circle), `.orb-inner`, all `.orb-wisp` elements.

**Add:** `.orb-glow` — a single div with:
```css
.orb-glow {
  position: absolute;
  inset: 15%;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255, 159, 10, 0.07) 0%, transparent 70%);
  pointer-events: none;
}
```

This provides a faint warm hint at the center without blocking anything. 7% opacity max. No `z-index`, no `overflow: hidden`.

### Change 2: Ribbons are the visual (keep v2 ribbon CSS, mostly)

Keep the thick border approach (9-12px) with directional opacity:
- `border-top-color`: Bright (0.85-0.95 opacity) — the "near" arc
- `border-right-color` / `border-left-color`: Medium (0.2-0.5) — transition zones
- `border-bottom-color`: Near-transparent (0.03-0.08) — the "far" arc

This creates the depth illusion as the border rotates with the Z-spin animation.

### Change 3: Bloom halos (keep from v2)

Each ribbon's `::after` pseudo-element with:
- Thicker border (18-26px)
- Heavy blur (16-24px)
- Same directional opacity pattern as the ribbon stroke
- `mix-blend-mode: screen` for additive crossing

### Change 4: Wobble wrappers (keep from v2)

Outer `.orb-wobble` handles tilt oscillation (±3-5° over 9-14s).
Inner `.orb-ribbon` handles Z-axis spin (360° over 6-12s).
Separate DOM elements = no transform conflict.

### Change 5: Remove all inner content

No wisps, no specular highlight, no inner clipping. Just the glow + 3 ribbons.

### Change 6: Wider ambient background wash

The `.orb-demo` container gets a stronger radial gradient:
```css
radial-gradient(ellipse at 50% 30%, rgba(255, 159, 10, 0.10) 0%, transparent 45%)
```
This simulates the ambient light the orb casts onto its surroundings.

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Without solid core, orb looks like floating rings not a sphere | Medium | Depth-dimming (border opacity gradient) + center glow sell the volume |
| `mix-blend-mode: screen` may not work on all backgrounds | Low | Fallback: remove blend mode, rely on opacity alone |
| Wobble animation causing jank on slower machines | Low | Keep wobble subtle (±3-5°), use `will-change: transform` |
| Bloom `filter: blur()` performance on large elements | Low | Only 3 blurred pseudo-elements, reasonable for modern browsers |

---

## Success Criteria

Comparing side-by-side with the reference video:
1. ✅ No visible solid sphere — dark background shows through center
2. ✅ 2-3 thick luminous bands visible at all angles of rotation
3. ✅ Bands appear to curve around an implied spherical volume
4. ✅ Depth illusion — "near" arcs brighter than "far" arcs
5. ✅ Heavy bloom/glow halo around each band
6. ✅ Organic wobble motion (not rigid)
7. ✅ Additive brightness at band crossings
8. ✅ Subtle ambient glow at center and on background
