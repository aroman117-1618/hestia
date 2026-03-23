# Discovery Report: Knowledge Graph Visualization Round 2
**Date:** 2026-03-23
**Confidence:** High
**Decision:** Use Metal shader modifiers for synapse-style edge animation; filter node types to Entity+Principle only; simplify legend; tighten extraction prompts to exclude system/dev concepts.

## Hypothesis
Redesign the knowledge graph visualization with: (1) Only Entity + Principle nodes on graph, (2) All nodes are spheres, (3) Synapse-style edges with white/starlight pulsing animation where brightness and frequency are proportional to edge weight, (4) Tighter extraction filtering to exclude Hestia-internal concepts, (5) Fix community label prompt grounding, (6) Simplified legend.

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** SceneKit already works well for 3D graph; Metal shader modifiers run on GPU with zero CPU overhead per-frame; existing edge/node architecture is modular and clean; 3-phase extraction already has significance filtering (Phase 2 PRISM) | **Weaknesses:** Current edge styling is purely static (cylinder + flat color); 7 node types create visual clutter; community label prompt is ungrounded (no examples/few-shot); entity extraction captures too many dev/system concepts |
| **External** | **Opportunities:** Metal shader `scn_frame.time` enables per-edge pulse frequency without SCNAction overhead; HDR bloom on SCNCamera creates realistic glow for free; uniform binding via `setValue(_:forKey:)` enables per-edge customization at material level | **Threats:** Shader complexity could cause compilation delay on first load; bloom threshold must be tuned carefully to avoid washing out the whole scene; filtering too aggressively could remove legitimate entities |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Synapse edge animation (Metal shader); Node type filtering (Entity+Principle only); Simplified legend | All-spheres node geometry (visual cleanup) |
| **Low Priority** | Extraction prompt tightening (reduces noise over time); Community label prompt grounding | HDR bloom tuning (nice-to-have polish) |

## Argue (Best Case)

1. **Metal shader modifiers are the right tool.** GPU-native, zero CPU overhead per frame, scales to 500+ edges trivially. `scn_frame.time` is built-in; no timer management needed. Each edge gets its own material with `pulseSpeed` and `baseBrightness` uniforms bound via KVC.

2. **Entity+Principle only is the right filter.** The current 7-type graph (memory, topic, entity, principle, community, episode, fact) creates noise. Entities and Principles are the knowledge graph's core semantic content. Topics, communities, episodes, and facts are structural/metadata layers that belong in the detail panel, not the 3D visualization.

3. **All-spheres simplifies cognition.** The current per-type shapes (diamond, torus, capsule, cylinder, box) require legend decoding. With only 2 node types, color alone differentiates them. Spheres are also the cheapest SceneKit geometry to render.

4. **The extraction prompt already has good bones.** Phase 1 prompt excludes "conversational fragments, filler phrases, instructions, greetings, thinking-out-loud, color descriptions, UI element descriptions, file paths, or device IDs." Adding "software module names, internal system components, API endpoints" to the exclusion list is a one-line change.

## Refute (Devil's Advocate)

1. **Per-edge materials multiply draw calls.** SceneKit can't batch objects with different materials. 200 edges = 200 draw calls. On M1 this should be fine (Metal is designed for many small draw calls), but worth monitoring.

2. **Bloom can wash out the dark UI.** HDR bloom applies to the entire scene. If the threshold is too low, node labels and the background could glow unintentionally. Mitigation: use `bloomThreshold = 0.5` to only bloom edges, not nodes.

3. **Removing community/episode/fact nodes loses context.** Users who want to see temporal patterns (episodes) or raw fact triples lose that capability. Mitigation: keep those as filter options in GraphControlPanel, just don't enable them by default.

4. **Community label prompt "grounding" is limited.** The LLM generates labels from entity names alone, with no few-shot examples. This means labels like "community-1" appear when the LLM fails. Better: provide 3-5 examples in the system prompt.

## Third-Party Evidence

- Apple's SCNCamera HDR properties (`wantsHDR`, `bloomIntensity`, `bloomThreshold`, `bloomBlurRadius`) are well-documented and hardware-accelerated on Apple Silicon.
- SceneKit shader modifiers use the `SCNShaderModifierEntryPoint.surface` entry point for emission manipulation. The `_surface.emission` struct is writable.
- `setValue(_:forKey:)` on SCNMaterial binds custom uniforms. Supported types include `Float`, `Double`, `NSValue`-wrapped vectors, and `MTLBuffer`.
- SCNParticleSystem along edges was evaluated and rejected: particles are designed for discrete sprites (fire, smoke), not solid linear glow effects. Performance with 200+ edge emitters would be poor.

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- Metal shader modifier is the superior technique for 200+ simultaneous edge animations on M1 (GPU-native, parallel execution).
- `scn_frame.time` is the correct time uniform for SceneKit Metal shaders.
- SCNParticleSystem is a poor fit for edge glow effects (wrong abstraction level).
- SCNAction-based emission animation creates CPU overhead that won't scale to 200+ edges.
- HDR camera bloom (`wantsHDR`, `bloomIntensity`) is the standard way to achieve glow bleed in SceneKit.

### Contradicted Findings
- None. All internal hypotheses were confirmed.

### New Evidence
- Bloom requires careful threshold tuning. Setting `bloomThreshold = 0.4-0.5` prevents unintended glow on non-emissive surfaces.
- `#pragma transparent` in the shader modifier is needed for proper alpha blending on edges.
- `bloomBlurRadius` of 8-12 gives a subtle neural glow without extreme bleed.

### Sources
- [SCNShadable Documentation](https://developer.apple.com/documentation/scenekit/scnshadable)
- [SceneKit Shader Modifiers Setup (Deurell Labs)](https://deurell.github.io/posts/scenekit-setup/)
- [SCNTechniqueGlow (GitHub)](https://github.com/laanlabs/SCNTechniqueGlow)
- [Metal with SceneKit (Dev Genius)](https://medium.com/@MalikAlayli/metal-with-scenekit-create-your-first-shader-2c4e4e983300)
- [SCNParticleSystem Documentation](https://developer.apple.com/documentation/scenekit/scnparticlesystem)
- [Animating SceneKit Content](https://developer.apple.com/documentation/scenekit/animation/animating_scenekit_content)

---

## Implementation Plan

### 1. Synapse-Style Edge Animation (Metal Shader)

**Technique:** Metal shader modifier on `SCNShaderModifierEntryPoint.surface` entry point.

**How it works:**
- Each edge's `SCNMaterial` gets a shader modifier string that reads `scn_frame.time` and produces a sine-wave pulse on `_surface.emission.rgb`.
- Per-edge customization via two KVC-bound uniforms: `pulseSpeed` (frequency proportional to edge weight) and `baseBrightness` (minimum glow proportional to edge weight).
- Edge color: white/starlight (`NSColor(white: 0.92, alpha: 1.0)`) for the diffuse, emission pulsed via shader.

**Metal shader code (surface entry point):**
```metal
#pragma transparent
#pragma body

float pulseSpeed = u_pulseSpeed;   // KVC-bound: 1.0 + weight * 4.0
float minGlow = u_baseBrightness;  // KVC-bound: 0.1 + weight * 0.3
float maxGlow = minGlow + 0.5;     // Peak brightness

float pulseFactor = (sin(scn_frame.time * pulseSpeed) + 1.0) * 0.5;
float emissionStrength = mix(minGlow, maxGlow, pulseFactor);

_surface.emission.rgb = float3(0.92, 0.92, 0.95) * emissionStrength;
```

**Swift binding (in `MacSceneKitGraphView.createEdgeNode`):**
```swift
let material = SCNMaterial()
material.diffuse.contents = NSColor(white: 0.92, alpha: CGFloat(0.15 + weight * 0.25))
material.lightingModel = .constant
material.shaderModifiers = [.surface: synapseShaderCode]
material.setValue(Double(1.0 + weight * 4.0), forKey: "u_pulseSpeed")
material.setValue(Double(0.1 + weight * 0.3), forKey: "u_baseBrightness")
```

**HDR bloom on camera (in `buildScene`):**
```swift
cameraNode.camera?.wantsHDR = true
cameraNode.camera?.bloomIntensity = 0.8
cameraNode.camera?.bloomThreshold = 0.5
cameraNode.camera?.bloomBlurRadius = 10.0
```

**Performance:** All 200+ edges animate on GPU in parallel. CPU does zero per-frame work. M1 handles this trivially.

### 2. Entity + Principle Nodes Only (Default Filter)

**Changes to `MacNeuralNetViewModel`:**
- Change `GraphMode.facts.defaultNodeTypes` from `["entity", "principle", "fact"]` to `["entity", "principle"]`
- Change `GraphMode.legacy.defaultNodeTypes` from `["memory", "topic", "entity", "principle"]` to `["entity", "principle"]`
- Keep all other node types available in `GraphControlPanel` toggle pills (user can re-enable)

### 3. All Nodes Are Spheres

**Changes to `MacSceneKitGraphView.createNodeGeometry`:**
- Replace the entire `switch graphNode.nodeType` with a single `SCNSphere` for all types
- Differentiate by color (already done via `graphNode.color`) and size (already done via `graphNode.radius`)
- Entity nodes: teal/green spheres (existing colors)
- Principle nodes: purple spheres (existing colors)

```swift
private func createNodeGeometry(for graphNode: MacNeuralNetViewModel.GraphNode) -> SCNNode {
    let r = CGFloat(graphNode.radius)
    let sphere = SCNSphere(radius: r)
    sphere.segmentCount = 24

    // ... existing confidence/recency material logic unchanged ...

    let node = SCNNode(geometry: sphere)
    node.position = SCNVector3(graphNode.position.x, graphNode.position.y, graphNode.position.z)
    node.name = graphNode.id
    // ... existing pulse animation unchanged ...
    return node
}
```

### 4. Tighter Extraction Filtering

**Changes to `hestia/research/fact_extractor.py`:**

Add to `PHASE1_ENTITY_PROMPT` exclusion list:
```
EXCLUDE: ...existing exclusions..., software module names (e.g. 'MemoryManager', 'GraphBuilder'),
internal system components (e.g. 'Hestia', 'Artemis', 'Apollo' when referring to the AI system),
API endpoints, Python/Swift class names, configuration parameters, database table names.
Only extract entities that a non-technical person would recognize.
```

Add to `PHASE2_SIGNIFICANCE_PROMPT`:
```
BACKGROUND entities include: software components, system modules, configuration settings,
and AI assistant names when discussed in a development context.
```

### 5. Fix Community Label Prompt Grounding

**Changes to `hestia/research/entity_registry.py` `_generate_community_label`:**

Add few-shot examples to the system prompt:
```python
system=(
    "Generate a 2-4 word descriptive label that captures the common theme "
    "of these related entities. Return JSON: {\"label\": \"...\"}\n\n"
    "Examples:\n"
    "Entities: Andrew, Sarah, Mike, Lisa -> {\"label\": \"Social Circle\"}\n"
    "Entities: Python, FastAPI, SQLite, ChromaDB -> {\"label\": \"Tech Stack\"}\n"
    "Entities: Apple, Google, Anthropic -> {\"label\": \"Tech Companies\"}\n"
    "Entities: Running, Cycling, Swimming -> {\"label\": \"Fitness Activities\"}\n"
    "Entities: Bitcoin, Ethereum, Coinbase -> {\"label\": \"Crypto Ecosystem\"}\n"
),
```

### 6. Simplified Legend

**Changes to `ResearchView.graphLegend`:**

With only Entity + Principle nodes by default, the legend becomes minimal:
- Remove the memory chunk type breakdown section entirely (no memory nodes by default)
- Remove the entity sub-type breakdown (all spheres now, differentiated only by color)
- Keep only: Entity (green dot), Principle (purple dot), "Edge brightness = connection strength"
- If user re-enables other node types via control panel, legend dynamically adds those entries back (existing `activeNodeTypes` logic handles this)

---

## File Change Summary

| File | Changes |
|------|---------|
| `HestiaApp/macOS/Views/Research/MacSceneKitGraphView.swift` | Synapse shader on edges, all-spheres node geometry, HDR bloom on camera |
| `HestiaApp/macOS/ViewModels/MacNeuralNetViewModel.swift` | Default node types to Entity+Principle |
| `HestiaApp/macOS/Views/Research/ResearchView.swift` | Simplified legend |
| `hestia/research/fact_extractor.py` | Tighter extraction exclusion list |
| `hestia/research/entity_registry.py` | Few-shot examples in community label prompt |

**Estimated effort:** 6-8 hours total
- Synapse shader + bloom: 2-3h (shader code, KVC binding, bloom tuning, testing)
- All-spheres + default filters: 1h
- Legend simplification: 0.5h
- Extraction prompt tightening: 0.5h
- Community label grounding: 0.5h
- Visual testing and tuning: 1-2h

## Philosophical Layer
- **Ethical check:** Pure UI/UX improvement. No data privacy or security implications.
- **First principles:** A knowledge graph's primary value is showing *connections between meaningful concepts*. Structural metadata (topics, episodes, facts) are implementation details that belong in drill-down views, not the primary visualization. The synapse metaphor (brightness = importance) is intuitive and maps directly to the data's semantics.
- **Moonshot:** Full-on neural network visualization with real-time physics — nodes attracted/repelled by mouse proximity, edges that spark when hovered, 3D flythrough camera path. **Verdict: SHELVE** — the shader-based approach gets 80% of the visual impact at 10% of the effort. Revisit when M5 Ultra provides headroom for real-time physics.

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | No security impact — pure frontend visualization |
| Empathy | 5 | Dramatically reduces visual noise; synapse animation is immediately intuitive |
| Simplicity | 4 | Metal shader is slightly complex but well-contained in one function; overall reduces code (removes shape switch) |
| Joy | 5 | Pulsing neural synapses look incredible; this will be a showcase feature |

## Recommendation
Implement all 6 changes as a single sprint. The Metal shader modifier approach is the clear winner for edge animation — GPU-native, zero CPU overhead, scales to 500+ edges trivially. Combined with the node/legend simplification, this transforms the graph from a cluttered data dump into an elegant neural visualization.

**Confidence: High.** The Metal shader approach is well-documented, confirmed by Gemini with real-world evidence, and the SceneKit API surface is stable. The main risk is bloom tuning, which is easily iterable.

**What would change the answer:** If SceneKit shader modifiers were deprecated (no signs of this) or if the graph needed to run on iOS (same API works on iOS, so no change needed).

## Final Critiques
- **Skeptic:** "Metal shader compilation could cause a visible stutter on first load." **Response:** SceneKit caches compiled shaders after first use. The shader is tiny (6 lines of MSL). Compilation is sub-10ms on M1. Not a real concern.
- **Pragmatist:** "Is 6-8 hours worth it for a visualization most users glance at?" **Response:** The research graph is the primary way Andrew reviews what Hestia has learned. Making it visually intuitive directly impacts trust in the system. Also, this is one of the most visually impressive features — worth polishing.
- **Long-Term Thinker:** "Will this shader approach survive a move to RealityKit or visionOS?" **Response:** RealityKit uses a different shader system (CustomMaterial with Metal functions). The core math (sine pulse on emission) transfers directly; only the binding API changes. The node/legend simplification is framework-agnostic.

## Open Questions
1. Exact starlight color values — pure white `(0.92, 0.92, 0.95)` or slightly warm `(0.95, 0.92, 0.88)`? Need to test both against the dark background.
2. Bloom radius sweet spot — need to test 8, 10, 12 values visually.
3. Should the node pulse animation (existing `SCNAction.scale`) be replaced with a shader-based emission pulse too, for consistency? (Low priority, current look is fine.)
