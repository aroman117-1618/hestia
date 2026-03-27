# Discovery Report: iOS Particle Animation — Metal vs CGContext
**Date:** 2026-03-26
**Confidence:** High
**Decision:** Migrate from CGContext to Metal for the wavelength particle renderer. The current CPU-bound approach has a hard ceiling around 24fps; Metal unlocks 60fps with 2000+ particles while reducing CPU load and battery drain.

## Hypothesis
For Hestia's iOS wavelength particle animation (2000 particles, pre-rendered radial gradient textures, additive blending, retina resolution), Metal GPU rendering will achieve 60fps with lower CPU/battery impact than the current CGContext (UIGraphicsImageRenderer) approach, and the implementation complexity is manageable.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Current CGContext renderer works, is debuggable, thread-safe. Pre-computed wave tables + texture caching already optimize the hot path. Architecture (ViewModel + Renderer separation) maps cleanly to Metal. | **Weaknesses:** CPU-bound — 1300+ sequential `ctx.draw()` calls per frame. Capped at 15-24fps depending on mode. Saturates one CPU core on background thread. Each frame must complete in <16.67ms for 60fps — impossible with sequential CPU draw calls at 2x retina scale. |
| **External** | **Opportunities:** Metal can render 100K-2M particles at 60fps (ParticleLab demo: 2M at 60fps on iPad Air 2). GPU parallelism eliminates the sequential bottleneck. Compute shaders can also handle particle position updates, freeing the CPU entirely. Lower battery drain (GPU is more power-efficient than CPU for parallel workloads). | **Threats:** Metal adds ~200-300 lines of shader + pipeline code. Harder to debug than CGContext (no Xcode breakpoints in shaders, need GPU debugger). Metal shader compilation errors are cryptic. Requires understanding of render/compute pipelines. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Metal renderer migration (solves 60fps goal directly) | Reduce particle count as interim band-aid (diminishing returns, already optimized from 3500 to 2000) |
| **Low Priority** | GPU-side particle simulation via compute shader (future optimization, not needed for MVP) | CAEmitterLayer exploration (dead-end — lacks custom wave physics) |

## Argue (Best Case)

**Metal is the clearly correct technical choice for this workload:**

1. **100-1000x headroom.** FlexMonkey's ParticleLab renders 2,000,000 particles at 60fps on an iPad Air 2 (A8X, 2014 hardware). The current target of 2000 particles is trivial for Metal on any modern iPhone (A15+). This means zero performance anxiety about adding visual complexity later.

2. **Eliminates the fundamental bottleneck.** The current CGContext approach processes each `ctx.draw()` sequentially on a single CPU core. At ~1300 visible particles x retina resolution, that's the wall. Metal processes all particles in parallel on thousands of GPU cores — the workload is embarrassingly parallel.

3. **Lower battery drain.** Apple's Energy Efficiency Guide explicitly states that GPU-accelerated rendering via Core Animation/Metal is more power-efficient than CPU-based drawing. The GPU is purpose-built for this; running it on the CPU is like sorting data with bubble sort when quicksort exists.

4. **Clean architecture mapping.** The current code already separates concerns well:
   - `WavelengthState.swift` — particle model + parameters (reusable as-is)
   - `WavelengthRenderer.swift` — rendering logic (replace with Metal pipeline)
   - `HestiaWavelengthView.swift` — SwiftUI wrapper (swap CGImage for MTKView)

   The particle struct, wave tables, and state management stay identical. Only the rendering backend changes.

5. **Implementation is bounded.** A minimal 2D textured particle Metal renderer requires:
   - `Particles.metal` — vertex + fragment shader (~50 lines)
   - `ParticleMetalView.swift` — MTKView wrapper + pipeline setup (~150 lines)
   - Particle buffer upload logic (~30 lines)

   Total: ~230 lines of new code replacing ~130 lines of CGContext rendering.

6. **Additive blending is a one-line pipeline config.** The current `ctx.setBlendMode(.plusLighter)` maps directly to Metal's `MTLRenderPipelineColorAttachmentDescriptor.destinationRGBBlendFactor = .one`. No custom blending math needed.

7. **Pre-rendered textures map directly.** The 32x32 and 64x64 radial gradient CGImages can be loaded as `MTLTexture` objects. The fragment shader samples from them — identical visual result, GPU-accelerated.

## Refute (Devil's Advocate)

**Arguments against migrating to Metal:**

1. **"If it works, don't fix it."** The current renderer caps at 15-24fps but looks acceptable. The wavelength is not the primary interaction surface — chat is. Users may not perceive 24fps vs 60fps on a background animation. Is the visual improvement worth the migration risk?

2. **Debugging is harder.** CGContext code is standard Swift — breakpoints, print statements, Instruments Time Profiler all work natively. Metal shaders require the GPU debugger (Metal System Trace), shader validation layers, and capture frames. When something goes wrong in a shader, the error messages are opaque.

3. **Platform complexity.** The current code is iOS-only with a macOS stub. Metal requires:
   - `MTLDevice` creation (can fail on simulator without GPU)
   - Pipeline state compilation (can fail with shader errors)
   - Buffer management (manual memory, unlike ARC)
   - Fallback path for when Metal is unavailable

4. **Testing gaps.** The current CGContext renderer can be tested by comparing output CGImages. Metal renderers are harder to unit test — you need a real GPU device, which limits CI testing.

5. **24fps might be fine.** Many acclaimed animations (Studio Ghibli films, classic Disney) run at 12-24fps. The human eye perceives particle clouds differently than UI scrolling — 24fps particles may look "dreamy" rather than "janky."

6. **Intermediate options exist.** CAEmitterLayer is GPU-accelerated, requires zero shader code, and can handle 10K+ particles. While it lacks custom wave physics, you could approximate the wavelength shape with emitter geometry. SpriteKit's SKEmitterNode offers more control with similar ease.

**Counter-refutation:** The 24fps argument has merit for idle mode, but during speaking/thinking modes the animation is the primary visual focus, and the CPU saturation (99% reported in the commit history — `ade2c23`) causes watchdog kills. This is not just an aesthetic issue; it's a stability issue. Metal resolves both.

## Third-Party Evidence

### External Validation

1. **ParticleLab (FlexMonkey/Simon Gladman):** Open-source Metal particle system. 2,000,000 particles at 60fps on iPad Air 2. Both compute (simulation) and render (drawing) on GPU. Demonstrates that 2000 particles is trivial for Metal. [GitHub](https://github.com/FlexMonkey/ParticleLab)

2. **GPU-Computed Particle System (julianlork):** SwiftUI + Metal implementation demonstrating 100,000 particles at 60fps. Clean, minimal codebase showing the Swift/Metal interop pattern. [GitHub](https://github.com/julianlork/gpu-computed-particle-system-with-swift)

3. **Besher Al Maleh — "High Performance Drawing on iOS":** Two-part series documenting CGContext performance cliffs. Key finding: UIGraphicsImageRenderer performance varies dramatically across devices — smooth on iPhone 6S, drops to teens on iPad Pro (higher resolution). This directly explains the retina scaling problem. [Part 1](https://medium.com/@almalehdev/high-performance-drawing-on-ios-part-1-f3a24a0dcb31) | [Part 2](https://medium.com/@almalehdev/high-performance-drawing-on-ios-part-2-2cb2bc957f6)

4. **Inferno (twostraws/Paul Hudson):** Library of Metal shaders for SwiftUI. Demonstrates the integration pattern — Metal shaders composed with SwiftUI views. [GitHub](https://github.com/twostraws/Inferno)

5. **Apple WWDC25 — Metal 4:** Unified command encoder, neural rendering, MetalFX Frame Interpolation. Apple is doubling down on Metal as the rendering API. No investment in CPU-based rendering APIs.

6. **Apple Energy Efficiency Guide:** Explicitly recommends GPU-based rendering over CPU drawing for animations. States that extraneous CPU drawing prevents system low-power states. [Apple Docs](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/AvoidExtraneousGraphicsAndAnimations.html)

### Alternative Approaches Considered

| Approach | 60fps at 2000 particles? | Custom wave physics? | Implementation effort | Verdict |
|----------|-------------------------|---------------------|----------------------|---------|
| CGContext (current) | No (15-24fps ceiling) | Yes | Already done | Insufficient |
| CAEmitterLayer | Yes (GPU-accelerated) | No (predefined physics) | Low (~50 lines) | Cannot replicate wave shape |
| SpriteKit SKEmitterNode | Yes | Limited | Medium (~200 lines) | Overkill framework for non-game app |
| SwiftUI Canvas + drawingGroup() | Unlikely (still CPU-computed) | Yes | Low (refactor) | CPU bottleneck persists |
| Metal (MTKView + shaders) | Yes (trivial) | Yes (full control) | Medium (~250 lines) | Best fit |

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- No production iOS apps found using UIGraphicsImageRenderer for real-time particle rendering at 60fps with 1000+ particles. The consensus is that CGContext is not viable for this workload.
- Minimal Metal particle system boilerplate is ~100-150 lines of shader/pipeline code (less than the ~500 lines initially feared).
- CAEmitterLayer and SpriteKit are GPU-accelerated but run simulation logic on CPU, creating a different bottleneck at scale.

### Contradicted Findings
- Initial estimate of ~500 lines for Metal implementation is too high. Gemini's research suggests ~100-150 lines of core Metal code (shaders + pipeline), plus ~80 lines of MTKView wrapper. Total closer to 230-250 lines.

### New Evidence
- SwiftUI Canvas with `.drawingGroup()` offloads rendering to Metal internally, but particle state computation remains CPU-bound. This is an optimization for complex static scenes, not dynamic particle systems.
- SpriteKit may start dropping frames at ~5000 particles due to CPU-side simulation overhead, even on A15+ hardware.
- Metal compute kernels can handle both simulation AND rendering on GPU, eliminating CPU from the hot path entirely.

### Sources
- [FlexMonkey ParticleLab](https://github.com/FlexMonkey/ParticleLab)
- [GPU Particle System (julianlork)](https://github.com/julianlork/gpu-computed-particle-system-with-swift)
- [Inferno Metal Shaders for SwiftUI](https://github.com/twostraws/Inferno)
- [Metal in SwiftUI — Jacob Bartlett](https://blog.jacobstechtavern.com/p/metal-in-swiftui-how-to-write-shaders)
- [Apple Energy Efficiency Guide](https://developer.apple.com/library/archive/documentation/Performance/Conceptual/EnergyGuide-iOS/AvoidExtraneousGraphicsAndAnimations.html)

## Philosophical Layer
- **Ethical check:** No concerns. This is a performance optimization for a local-first personal AI app. No data collection, no privacy implications.
- **First principles:** The fundamental issue is running an embarrassingly parallel workload (independent particle rendering) sequentially on a CPU. This is architecturally wrong regardless of the optimization level. The GPU exists precisely for this class of problem.
- **Moonshot:** Render the entire wavelength as a single Metal fragment shader — no particle objects at all. The wave shape, particle positions, sizes, and colors could all be computed per-pixel in a shader. This would eliminate buffer uploads, particle structs, and CPU-side state entirely. A full-screen shader at retina resolution on A15+ would trivially hit 120fps. **Verdict: SHELVE** — the visual quality of discrete particles with varying sizes/brightness is superior to shader-only approaches for this aesthetic. Revisit if the wavelength design evolves toward a more fluid/continuous look.

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No security implications — rendering is local, no data flows |
| Empathy | 4 | 60fps feels noticeably smoother; fixes watchdog kills that crash the app |
| Simplicity | 3 | Metal adds pipeline complexity but eliminates the background-thread/frame-skipping/CPU-saturation hacks. Net simplicity gain once migrated. |
| Joy | 5 | Buttery smooth particle animation at 60fps with zero CPU stress. Satisfying to build. |

## Recommendation
**Migrate the wavelength renderer from CGContext to Metal.** Confidence: **High.**

### Implementation Plan (estimated ~6-8 hours)

1. **Create `Particles.metal`** (~50 lines)
   - Vertex shader: read particle position/size/alpha from buffer, output point sprite
   - Fragment shader: sample from radial gradient texture, apply alpha + additive blend

2. **Create `MetalParticleView.swift`** (~150 lines)
   - `UIViewRepresentable` wrapping `MTKView`
   - One-time pipeline setup: device, command queue, render pipeline with additive blending
   - Per-frame: upload particle buffer, dispatch draw call
   - Preferred FPS configurable (15/24/60 per mode, matching current frameInterval logic)

3. **Adapt `WavelengthRenderer.swift`** (~30 lines changed)
   - Replace `renderToImage()` with buffer preparation (write particle positions/sizes/alphas to `MTLBuffer`)
   - Wave table computation stays on CPU (lightweight, <1ms) or moves to compute shader later

4. **Adapt `HestiaWavelengthView.swift`** (~20 lines changed)
   - Replace `Image(cgImage:)` with `MetalParticleView`
   - Remove `isRendering` flag, background dispatch, frame-skip logic (Metal handles its own frame pacing)

5. **Keep `WavelengthState.swift` unchanged** — particle model, palette, params, wave tables all reusable

6. **Fallback:** If `MTLCreateSystemDefaultDevice()` returns nil (simulator without GPU), fall back to the existing CGContext renderer. This is a one-line check.

### What would change this recommendation:
- If the design pivots away from discrete particles to a continuous fluid effect, a fragment-shader-only approach (the moonshot) becomes better
- If 24fps is explicitly accepted as "good enough" AND the watchdog kill issue is resolved another way, the migration becomes optional
- If the app drops iOS support and goes macOS-only, AppKit has different rendering paths worth evaluating

## Final Critiques
- **Skeptic:** "Metal is overkill for 2000 particles. You're bringing a cannon to a knife fight." **Response:** The cannon is the same weight as the knife here — ~250 lines of code. And it eliminates the CPU saturation that causes watchdog kills (commit `ade2c23`). The "overkill" framing assumes high implementation cost, which the research disproves.
- **Pragmatist:** "Is 6-8 hours worth it when the animation already works at 24fps?" **Response:** It's not just about fps. The current approach saturates a CPU core, which impacts battery life and can trigger iOS watchdog termination. Metal moves the entire workload to dedicated hardware, freeing the CPU for inference, networking, and UI. The 6-8 hour investment pays for itself in stability.
- **Long-Term Thinker:** "What happens in 6 months when you want richer animations?" **Response:** Metal is future-proof. Adding glow effects, color transitions, interaction ripples, or scaling to 10K particles requires zero architectural changes — just shader modifications. The CGContext approach would need a rewrite at that point anyway.

## Open Questions
1. Should particle position updates also move to a Metal compute shader (Phase 2), or stay on CPU for now?
2. What is the minimum iOS version that supports the Metal features needed? (Likely iOS 13+, well below the 26.0 target)
3. Should the macOS wavelength (currently stubbed out) also use Metal, or is it lower priority?
4. Profile the exact per-frame timing on a physical device before and after migration to quantify the improvement
