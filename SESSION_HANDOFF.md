# Session Handoff — 2026-03-26 (Wavelength UI)

## Mission
Replace the iOS chat view with a particle wave "wavelength" UI — from Figma design to TestFlight deployment. The wavelength is Hestia's new visual identity, replacing the old sphere orb.

## Completed
- **Discovery report**: `docs/discoveries/ios-orb-chat-redesign-2026-03-26.md`
- **HTML prototype**: `docs/superpowers/specs/wavelength-prototype.html` — Andrew-approved visual matching Figma ParticleWave.tsx
- **Implementation plan + second opinion**: `docs/superpowers/plans/2026-03-26-ios-wavelength-chat-ui.md`
- **Particle wave renderer**: `WavelengthState.swift`, `WavelengthRenderer.swift`, `HestiaWavelengthView.swift` — CGContext, 3500 particles, off-main-thread, 1x scale
- **ChatView redesign**: idle (wavelength + greeting) / conversation (wave top, messages bottom)
- **ChatInputBar**: liquid glass, lock icon removed, voice icon right, wider padding
- **Hidden tab bar**: swipe-up from bottom 60px
- **Conversation crash fix**: async audio session handoff
- **Release pipeline split**: `ios-v*` iOS, `mac-v*` macOS, `v*` both (`4fc0b62`)
- **Shipped ios-v1.10.4 (build 41)** to TestFlight

## In Progress
- **Andrew reviewing v1.10.4 on device** — has feedback ready for next session
- **Visual tuning** (Task 9) — not yet started

## Decisions Made
- Wavelength = horizontal particle wave, NOT sphere (Figma 369:647 + 369:710)
- CGContext primary renderer (SwiftUI Canvas lacks setShadow, plusLighter, transparency layers)
- Render at 1x scale off main thread (3x caused 99% CPU watchdog kill)
- Tab bar hidden by default (intentional HIG violation per Andrew)
- Tap mic = transcription, hold 2s = conversation (replaces 3-mode cycle)
- Speaking state during streaming responses
- Release tags: `ios-v*`, `mac-v*`, `v*`

## Test Status
- Backend: ~2915 passing, no regressions (iOS-only changes)
- iOS: BUILD SUCCEEDED

## Known Issues / Landmines
1. **Wavelength rendering on device unconfirmed** — CPU crash fixed but visual output needs verification
2. **No idle↔conversation animation** — matchedGeometryEffect removed (caused zero-frame). Needs explicit frame animation.
3. **HestiaOrbView.swift still exists** — kept for macOS. Remove after confirming macOS doesn't use it.
4. **forceLocal toggle removed from UI** — functionality exists but no visible control
5. **Greeting says "Boss"** — Figma says "Hello Andrew". May need user profile name.

## Process Learnings
- **50% first-pass success** (6/12 tasks). Top blocker: building renderer without visual prototype sign-off → full rewrite
- **Hallucinated 3 SwiftUI Canvas APIs** — caught by second opinion audit. Add Canvas API limitations to memory.
- **Proposal**: Always build HTML prototype for visual features before native code

## Next Step
1. Read this handoff, ask Andrew for his v1.10.4 device feedback
2. Apply visual tuning (particle brightness, wave positioning, animation timing)
3. Verify wavelength renders on device — if blank, debug CGContext output
4. Add message fade-to-background near wavelength zone
5. Re-add idle↔conversation animation without matchedGeometryEffect
