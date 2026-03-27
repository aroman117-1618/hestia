# Second Opinion: Wavelength Metal Migration
**Date:** 2026-03-26
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Flash (external)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
Migrate Hestia's iOS wavelength particle renderer from CGContext (CPU-bound, 15-24fps, blurry at 2x scale) to Metal (GPU-accelerated, 60fps target, native 3x retina). 2000 amber/gold particles with radial gradient textures, additive blending, 3-ribbon wave physics. Estimated 6-8 hours.

## Scale Assessment
| Scale | Works? | Breaking Points | Cost to Fix Later |
|-------|--------|----------------|-------------------|
| Single user | Yes | None | N/A |
| Family | Yes | None — rendering is device-local | N/A |
| Community | Yes | None — no shared state | N/A |

## Front-Line Engineering
- **Feasibility:** High. Metal particle systems are well-documented. Architecture maps cleanly.
- **Hidden prerequisites:** Metal.framework explicit linkage in project.yml; xcodegen regeneration for .metal file; async pipeline compilation to avoid stutter.
- **Testing gaps:** Metal rendering can't be unit tested in CI (no GPU). Particle state/wave computation testable independently. Visual validation via device screenshots.
- **Estimate risk:** 6-8h realistic for experienced Metal dev. Budget 8-10h for first Metal integration in this codebase.

## Architecture Review
- **Fit:** Excellent. Follows existing model/renderer/view separation. UIViewRepresentable pattern already established (LottieAnimationView).
- **Data model:** Particle struct, WavelengthParams, WaveTable all reusable as-is. Only rendering backend changes.
- **Integration risk:** Low. Touches 4 files in Shared/Views/Common/ + 2 new files. No backend changes.

## Product Review
- **Completeness:** Covers all modes (idle/listening/speaking/thinking), frame rate per mode, reduce-motion fallback, simulator fallback.
- **Missing item:** Conversation layout overlap — wavelength needs ~30pt downward offset so it doesn't overlap with Hestia header. Simple padding fix in ChatView, independent of Metal.
- **Scope calibration:** Right-sized. Metal rendering + layout adjustment is one cohesive sprint.

## UX/Design Review
- **Point sprite size:** Hero particles at 3x: baseSize(9) * z(1.0) * 6 * 3 = 162px. Within range for A15+ (511px max), but must query `MTLDevice.maxPointSize` and clamp.
- **Visual parity:** Radial gradient textures load as MTLTexture. Additive blending maps directly. Visual output should be identical or better.
- **Accessibility:** Reduce-motion fallback already implemented (static gradient).

## Infrastructure Review
- **Deployment impact:** iOS-only TestFlight build. No server changes.
- **New dependencies:** Metal.framework (system, always available on device).
- **Rollback:** CGContext code preserved as simulator fallback. Can revert by toggling.
- **Resource impact:** Lower CPU, lower battery. Net positive.

## Executive Verdicts
- **CISO:** Acceptable — No security implications. Local rendering only.
- **CTO:** Approve with conditions — Use instanced quads (not point sprites), triple-buffer ring, async pipeline compilation.
- **CPO:** Acceptable — Directly fixes #1 user complaint (choppy/blurry animation).
- **CFO:** Acceptable — 8-10h investment with no ongoing costs.
- **Legal:** Acceptable — Apple first-party framework, no license concerns.

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No security implications |
| Empathy | 5 | Directly addresses user-reported quality issues |
| Simplicity | 3 | Metal adds complexity but eliminates threading/frame-skip hacks |
| Joy | 5 | 60fps at native retina — transformative visual upgrade |

## Critic Findings (Adversarial Review)

The @hestia-critic agent raised three high-severity issues not adequately addressed in the original plan:

### 1. @MainActor / MTKViewDelegate Threading Conflict (HIGH)
`WavelengthViewModel` is `@MainActor`. `MTKViewDelegate.draw(in:)` runs on Metal's display link thread. Calling particle updates from `draw()` requires either restructuring the ViewModel to be non-actor-isolated, or dispatching to main actor (which at 60fps creates latency that defeats the purpose of Metal).

**Resolution:** Create a non-actor-isolated `MetalParticleRenderer` class that owns particle state and wave tables. The MTKViewDelegate calls it directly from `draw()`. The SwiftUI view reads only the rendered output. This is a clean separation — particle physics on the render thread, display on the main thread.

### 2. Particle State Sync / Position Ownership (HIGH)
Current code mutates `particles[i].x` and `yOffset` during rendering (position update + wraparound). In the Metal path, who owns this mutation? If it stays in the render method (now on Metal's thread), it conflicts with @MainActor ownership.

**Resolution:** Particle position updates move into `MetalParticleRenderer` alongside buffer preparation. The renderer owns the particle array entirely — no copy-for-thread-safety needed. SwiftUI only passes mode/audioLevel as inputs.

### 3. Dual Renderer Maintenance Burden (MEDIUM)
The CGContext fallback for simulator is not a "one-line check" — it's a forking state machine. The two paths will diverge over time.

**Resolution:** Accept this as a known trade-off. The CGContext path is debug/simulator-only and doesn't need visual parity. Mark it clearly as `#if targetEnvironment(simulator)` and don't invest in keeping it visually identical.

### 4. Revised Estimate
Critic assessed 12-18h for someone experienced with Metal, 20+ for first Metal project. Original 6-8h was optimistic. **Revised: 12-16h** accounting for threading model, shader debugging, and visual validation.

## Final Critiques
1. **Most likely failure:** @MainActor threading conflict when calling particle updates from MTKViewDelegate.draw(). **Mitigation:** Non-actor-isolated MetalParticleRenderer class owns all particle state.
2. **Critical assumption:** Metal additive blending produces visually identical results to CGBlendMode.plusLighter. **Validation:** Build mockup first (DONE — wavelength-metal-preview.html), then compare device screenshots side-by-side after implementation.
3. **Half-time cut list:** If only 8 hours — skip triple-buffering (use double), skip compute shader, skip macOS Metal. Core: MTKView + instanced quads + SwiftUI wrapper.

## Cross-Model Validation (Gemini 2.5 Flash)

### Gemini's Independent Assessment
**Verdict: NEEDS REWORK** — Gemini pushed back on point sprites and single-buffer strategy.

Key recommendations:
1. **Instanced quads over point sprites** — better control over size/shape/rotation, avoids hardware max size limits, more future-proof for complex particle effects.
2. **Triple-buffer ring mandatory** — single buffer will cause CPU/GPU stalls and prevent consistent 60fps.
3. **Lifecycle management critical** — MTKView inside UIViewRepresentable in SwiftUI TabView can be recreated frequently. Must use `isPaused` in `onAppear`/`onDisappear`.
4. **Query `MTLDevice.maxPointSize` at runtime** if using point sprites — 162px is borderline.

### Where Both Models Agree
- Metal migration is the correct approach (no disagreement on the fundamental decision)
- Triple-buffering is important for consistent 60fps
- Point sprite max size is a real concern that needs runtime checking
- MTKView lifecycle management in SwiftUI requires careful attention
- CGContext fallback for simulator is necessary and correct
- Wave table computation on CPU is fine (<1ms, not worth compute shader complexity)

### Where Models Diverge
| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| Point sprites vs instanced quads | Point sprites with size clamping | Instanced quads strongly preferred | **Use instanced quads.** Gemini is right — instanced quads eliminate the size limit concern entirely, add ~20 lines of code, and future-proof for particle rotation/non-square shapes. |
| Overall verdict | APPROVE WITH CONDITIONS | NEEDS REWORK | **APPROVE WITH CONDITIONS.** Gemini's "needs rework" was based on the point sprite decision, not fundamental architecture. Adopting instanced quads satisfies the concern. |

### Novel Insights from Gemini
1. **MTKView.isPaused control** — pause rendering when the view is off-screen (on tab switch). Not in the original plan. Important for battery.
2. **drawableSize change handling** — MTKView auto-updates drawableSize on frame changes. Projection matrices must respond. Relevant for the idle↔conversation layout transition.

### Reconciliation
Both models agree Metal is correct and the architecture is sound. The key delta is instanced quads vs point sprites — Gemini makes a compelling case that instanced quads are worth the marginal extra complexity for the elimination of size limits and future flexibility. The triple-buffer recommendation is unanimous. Adding `isPaused` lifecycle control is a valuable Gemini-originated insight.

## Conditions for Approval

1. **Use instanced quads instead of point sprites** — eliminates max size concern, adds ~20 lines
2. **Implement triple-buffer ring** — prevents CPU/GPU contention stalls
3. **Async pipeline compilation** — compile Metal pipeline on background thread, show fallback until ready
4. **MTKView lifecycle management** — pause rendering on tab switch via `isPaused`
5. **Address conversation layout overlap** — push wavelength down ~30pt in conversation mode
6. **Query `MTLDevice.maxPointSize`** as safety check even with instanced quads (for future reference)

## Implementation Plan (Revised)

### Files to Create
1. `HestiaApp/Shared/Views/Common/Particles.metal` — vertex + fragment shaders for instanced quads (~60 lines)
2. `HestiaApp/Shared/Views/Common/MetalParticleView.swift` — UIViewRepresentable + MTKViewDelegate + triple-buffer ring (~180 lines)

### Files to Modify
3. `HestiaApp/Shared/Views/Common/WavelengthRenderer.swift` — replace `renderToImage()` with `prepareBuffer()` that writes particle data to MTLBuffer (~30 lines changed)
4. `HestiaApp/Shared/Views/Common/HestiaWavelengthView.swift` — swap Image(cgImage:) for MetalParticleView, remove isRendering/dispatch logic (~30 lines changed)
5. `HestiaApp/Shared/Views/Chat/ChatView.swift` — add ~30pt top offset to wavelength in conversation layout (~2 lines)
6. `HestiaApp/project.yml` — add Metal.framework linkage (1 line)

### Files Unchanged
- `WavelengthState.swift` — particle model, palette, params, wave tables all reusable

### Estimated Effort: 12-16 hours (revised from 6-8h after critic review)
