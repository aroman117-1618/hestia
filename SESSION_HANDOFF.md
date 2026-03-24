# Session Handoff — 2026-03-23

## Mission
Fix the broken fact extraction pipeline, then redesign the knowledge graph visualization with synapse-style pulsing edges, simplified node filtering, and improved data quality.

## Completed

### Fact Extraction Pipeline Fix
- **Root cause #1**: `fact_extractor.py` called `client.generate()` — method doesn't exist on `InferenceClient` (only `complete()`). All 5 call sites silently caught `AttributeError`. Pipeline never executed a single LLM call. (`dceea66`)
- **Root cause #2**: `_get_inference_client()` was `async` but `get_inference_client()` is sync — `await` on non-awaitable raised `TypeError`. (`1caef7b`)
- **Added `force_tier` + `format` params** to `complete()` → `_call_with_routing()` → `_call_ollama()` for explicit model routing control (`dceea66`)
- **Tests fixed**: all mocks updated from `generate` → `complete`, `AsyncMock` → regular patch (`1caef7b`)
- **Extraction working**: 26 entities, 20 facts, 8 named communities on Mac Mini

### Knowledge Graph Visualization (v1.1.9 → v1.2.3)
- **Synapse pulsing edges**: Metal shader modifier on `.surface` entry point. Root cause of magenta error: missing `#pragma arguments` declaration for custom uniforms. Fixed with proper Metal syntax. (`14bbbd0`)
- **All nodes are spheres**: removed per-nodeType shape switch (`f09d4d3`)
- **Entity + Principle only**: client-side node type filtering in `applyGraphResponse()` (`045c1de`)
- **Community nodes hidden**: removed from `defaultNodeTypes` (`f09d4d3`)
- **Text labels removed**: `addBillboardLabel()` calls removed (`f09d4d3`)
- **Simplified legend**: Entity + Principle + edge brightness note (`f09d4d3`)
- **Entity-type colors in legend**: Person/Tool/Concept/Project/Org/Place breakdown (removed in later simplification)

### Data Quality
- **Entity fuzzy dedup**: Jaro-Winkler matching (threshold 0.93) + name normalization (underscores, parentheticals) in `entity_registry.py` (`f09d4d3`)
- **LLM community labels**: few-shot prompted descriptive names instead of "community-N" (`f09d4d3`)
- **Tighter extraction prompts**: positive examples + exclusions for dev/system concepts (`e57fbe2`)
- **Entity rejection API**: `POST /v1/research/entities/{id}/reject` + `/unreject` for feedback loop (`e57fbe2`)
- **Graph builder filters rejected entities** (`e57fbe2`)

### CI/CD Fixes
- **Plist version injection**: `Info.plist` used hardcoded "1.0" instead of `$(MARKETING_VERSION)`. Fixed via `project.yml` info properties. (`9dcf6f7`)
- **Release workflow clean build**: Added `xcodebuild clean` + `-derivedDataPath` to prevent stale DerivedData (`9dcf6f7`)

### Releases
- v1.1.10 (build 14) — fact extraction fix
- v1.1.11 (build 15) — graph refinements round 1
- v1.2.0 (build 16) — synapse edges + simplified graph (broken shader)
- v1.2.1 (build 17) — CI/CD plist fix
- v1.2.2 (build 18) — white edges (shader removed), client-side filter
- v1.2.3 (build 19) — synapse shader working with `#pragma arguments`

## In Progress
- **Extraction quality tuning** — 26 entities include some junk ("Hi Boss, ready for some good trouble?", "Mobile-CommandCenter.png"). The reject/unreject API exists but hasn't been wired into the macOS app UI yet. Extraction prompts need continued iteration based on rejection feedback.

## Decisions Made
- **`force_tier` over truncation**: Expose `force_tier="primary"` on `complete()` instead of truncating prompt text. Preserves full entity extraction context. Both Claude + Gemini agreed.
- **Single-phase extraction deferred**: 3-phase pipeline kept for now. Quality baseline needed before deciding if significance filter (Phase 2) adds value.
- **Fuzzy dedup threshold 0.93**: Conservative — 0.88 was merging too aggressively for short entity names.
- **Metal shader `#pragma arguments`**: Required for custom uniform declarations in SceneKit Metal shader modifiers. Without it, uniforms are undeclared identifiers → magenta error.
- **HDR bloom disabled**: Was bleeding node colors onto edges. Can re-enable with higher threshold once shader is stable.

## Test Status
- 2644 backend tests passing (3 skipped — integration markers)
- macOS build clean
- CLI tests have pre-existing import path issue (not from this session)

## Uncommitted Changes
None — all committed and pushed. Untracked files pre-date this session:
- `HestiaApp/iOS/steward-icon-knot-v3-teal-dark.png`
- `docs/mockups/`
- `docs/plans/consumer-product-strategy.md`

## Known Issues / Landmines
- **Extraction still produces junk entities**: "Hi Boss, ready for some good trouble?", file paths like "Mobile-CommandCenter.png", device IDs. The reject API exists but no UI to call it yet. Manual curl or next-session improvement.
- **HDR bloom commented out**: Re-enabling could enhance the synapse effect but needs careful threshold tuning to avoid node color bleed.
- **Synapse shader uses hardcoded pulse range**: `mix(0.02, 2.0, pulse)` — `u_baseBrightness` uniform is bound but the shader doesn't use it for the glow range. Could be parameterized per-edge for weight-based brightness variation.
- **Sparkle auto-update**: v1.2.3 CI/CD release will have correct version in plist. Previous releases (v1.1.10–v1.2.0) had "1.0" in plist so Sparkle couldn't compare versions properly. May need manual install for users on very old versions.
- **Mac Mini server needs restart** after code deploy — launchd service not updated this session.
- **Bot service on Mac Mini** — trading bots may need restart after deploy: `launchctl unload/load com.hestia.trading-bots.plist`

## Process Learnings
- **Misdiagnosis cost 30+ minutes**: SESSION_HANDOFF from previous session blamed "model routing" for extraction failure. Actual bug was `generate()` → `complete()` method name mismatch. Lesson: always verify hypotheses against actual error logs, not inferred from similar patterns.
- **Metal shader debugging is blind in CLI**: SceneKit shader modifiers fail silently (magenta) with no error message accessible from CLI builds. Need Xcode GPU debugger or file-based diagnostic logging. The `/tmp/hestia-edge-debug.txt` file approach worked for confirming code execution.
- **`#pragma arguments` was the key insight**: Metal shader modifiers differ from GLSL — custom uniforms MUST be declared in a `#pragma arguments` block. This is documented in Apple's `SCNShadable.h` header but not prominently in online tutorials.
- **First-pass success**: ~60% (extraction fix, node filtering, legend worked first try; shader took 4 attempts, plist took 2 attempts)
- **Top blocker**: No way to see Metal shader compilation errors from CLI. Proposed mitigation: add a `#if DEBUG` runtime check that logs shader compilation status.

## Next Session: Polish & Wire Rejection UI

### Exact steps:
1. **Wire entity rejection into macOS app** — add a "Reject" button to the node detail panel (NodeDetailPopover) that calls `POST /v1/research/entities/{id}/reject`
2. **Re-enable HDR bloom with tuned threshold** — try `bloomThreshold = 0.8` (higher than before) to only bloom the brightest edge pulses without bleeding node colors
3. **Parameterize pulse brightness per edge** — use `u_baseBrightness` in the shader's `mix()` range so stronger connections pulse brighter
4. **Review and reject junk entities** — use the rejection API to flag bad entities, then tune extraction prompts based on rejection patterns
5. **Consider traveling pulse** — the current shader does overall brightness throbbing. Add a spatial component using `_surface.position.y` for a "light packet traveling along the edge" effect (needs `u_edgeLength` uniform)
