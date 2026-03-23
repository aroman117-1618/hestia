# Second Opinion: Knowledge Graph Round 2
**Date:** 2026-03-23
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external)
**Mode:** Operate (compressed — focused on HOW)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary
6 refinements to the knowledge graph visualization: synapse-style pulsing edges (Metal shader), Entity+Principle-only nodes, all-sphere geometry, tighter extraction prompts, grounded community labels, simplified legend.

## Rapid Risk Assessment

**Feasibility:** All 6 items are well-scoped. The Metal shader is the only non-trivial item — validated by both Claude and Gemini as the correct approach.

**Hidden prerequisite:** The `createEdgeNode()` method (line 297) builds edges as `SCNCylinder` oriented along the Y-axis. The traveling pulse shader uses `_surface.position.y` for spatial offset — this requires knowing the cylinder height (`distance`). Must pass `distance` as a uniform.

**Performance:** 500 edges with per-edge materials = 500 draw calls. M1 handles this fine (Metal is optimized for many small draws). Shader code is identical across edges, so the compiled program is reused — only uniform data changes per-edge.

## Cross-Model Reconciliation

### Where Both Models Agree (High Confidence)
- Metal shader modifier on `.surface` is the correct technique
- `scn_frame.time` for animation, KVC `setValue(_:forKey:)` for per-edge uniforms
- HDR bloom (`wantsHDR`, `bloomIntensity`, `bloomThreshold`) for glow effect
- SCNAction and SCNParticleSystem are wrong tools for this
- 500 edges is well within M1 capability

### Where Models Diverge

| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| `#pragma transparent` | Included in shader | **Remove it** — forces transparent queue unnecessarily. Use `.blendMode = .add` instead | **Gemini is right.** Additive blending is better for emission-only glow. Black diffuse + additive = pure emission visible. |
| Traveling pulse | Simple sine on `_surface.position` | **`pow(sin(ramp * pi), 30.0)`** — localized packet with configurable sharpness | **Gemini's version is much better.** Creates a visible "light packet" traveling along the edge instead of a continuous wave. More synapse-like. |
| Color warmth | `float3(0.92, 0.92, 0.95)` (cool white) | No opinion | Test both cool white and warm `(0.95, 0.92, 0.88)` against dark background. |

### Novel Insights from Gemini
1. **Additive blend mode** (`material.blendMode = .add`) + black diffuse = pure emission glow. Much better than transparent blending for the synapse effect.
2. **Traveling packet shader** with `pow(sin(...), 30.0)` creates a sharp localized pulse rather than a continuous wave. The exponent controls packet width.
3. **Two new uniforms needed:** `u_travelSpeed` (packet travel speed) and `u_edgeLength` (cylinder height, needed for position normalization).
4. **Shader program reuse:** SceneKit caches the compiled shader. All 500 edges share the same program — only uniform values differ. This is efficient.

## Final Shader (Merged Best of Both)

```metal
#pragma body

float timePulseFactor = (sin(scn_frame.time * u_pulseSpeed) * 0.5 + 0.5);
float maxGlow = u_baseBrightness + 0.4;
float overallEmission = mix(u_baseBrightness, maxGlow, timePulseFactor);

float normalizedPos = (_surface.position.y / u_edgeLength) + 0.5;
float ramp = fract(normalizedPos - scn_frame.time * u_travelSpeed);
float packet = pow(sin(ramp * 3.14159), 30.0);

float finalEmission = (packet * 0.9) + (overallEmission * 0.1);
_surface.emission.rgb = float3(0.92, 0.92, 0.95) * finalEmission;
```

**Swift binding:**
```swift
material.blendMode = .add
material.diffuse.contents = NSColor.black
material.lightingModel = .constant
material.shaderModifiers = [.surface: synapseShaderCode]
material.setValue(Float(1.0 + weight * 4.0), forKey: "u_pulseSpeed")
material.setValue(Float(0.1 + weight * 0.3), forKey: "u_baseBrightness")
material.setValue(Float(1.0 + weight * 2.0), forKey: "u_travelSpeed")
material.setValue(Float(distance), forKey: "u_edgeLength")
```

## Conditions for Approval

1. **Use Gemini's additive blend approach** — `.blendMode = .add` + black diffuse, no `#pragma transparent`
2. **Use traveling packet shader** — `pow(sin(ramp * pi), 30.0)` for localized synapse pulses, not continuous sine wave
3. **Pass `distance` as `u_edgeLength` uniform** — already computed in `createEdgeNode()`
4. **Use `Float` not `Double`** for `setValue` — Metal shader uniforms are `float`, not `double`
5. **Test bloom threshold** — start at 0.5, adjust visually. Too low washes out nodes.
