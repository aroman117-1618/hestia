# Session Handoff — 2026-03-27 (iOS Refresh Sprint)

## Mission
Major iOS app refresh: Metal GPU particle renderer, redesigned chat layout, new lock screen, condensed Command Center, markdown chat rendering, keyboard behavior, and voice crash fixes. Shipped builds 41-60 to TestFlight across ~20 iterations.

## Completed

### Metal GPU Renderer (replaces CGContext)
- `HestiaApp/Shared/Views/Common/Particles.metal` — vertex + fragment shaders for instanced quads
- `HestiaApp/Shared/Views/Common/MetalParticleView.swift` — MTKViewDelegate with triple-buffer ring, non-@MainActor renderer
- `HestiaApp/Shared/Views/Common/HestiaWavelengthView.swift` — Metal on device, CGContext fallback for simulator
- `HestiaApp/Shared/Views/Common/WavelengthRenderer.swift` — wave table pre-computation (128 buckets)
- `HestiaApp/Shared/Views/Common/WavelengthState.swift` — particle sizes increased (2000 particles, larger base sizes)
- `.github/workflows/release-ios.yml` — Metal Toolchain download step added for CI

### Chat Layout (approved mockup: `docs/superpowers/specs/wavelength-metal-preview.html`)
- Wavelength in top 50% frame, wave center at 54% of frame (~27% of screen)
- Chat area starts at 39% with 120px soft fade gradient (black opacity, not hardcoded color)
- Messages dissolve behind wavelength as they scroll up
- Pure black background across all tabs (eliminates Metal compositing seam)

### Hestia Header (`HestiaApp/Shared/Views/Common/HestiaHeaderView.swift`)
- Gradient amber "Hestia" title with constellation stars + shimmer underline
- Wired into conversation layout in ChatView.swift

### Lock Screen (`HestiaApp/Shared/Views/Auth/LockScreenView.swift`)
- Amber gradient title with firefly glow behind
- Face ID ember circle (breathing animation)
- "Authenticate" button (amber outline)
- Auth only on button tap — no auto-trigger
- Approved mockup: `docs/superpowers/specs/login-and-command-mockups.html`

### Command Center (`HestiaApp/Shared/Views/Command/MobileCommandView.swift`)
- Trading condensed to 1 card: Bots/P&L/Fills + 7D/30D/3M segmented toggle
- Bot rows only show when unhealthy; "All N bots running normally" when healthy
- Orders section removed
- Feed card: scheduled orders + completed output + investigations
- Quick Actions removed (moved to Force Touch — not yet implemented)

### Chat Features
- Markdown rendering in message bubbles (`MessageBubble.swift`) — bold, italic, lists via AttributedString
- Keyboard-aware input bar — rides above keyboard, dismisses on tap/tab switch
- Swipe navigation between Chat/Command/Settings (TabView .page style)

### Voice / Speech (`HestiaApp/Shared/Services/SpeechService.swift`)
- Replaced iOS 26 SpeechAnalyzer (crashes in Apple's framework) with stable SFSpeechRecognizer
- AudioTapHandler class isolates audio thread from @MainActor (Swift 6 concurrency fix)
- On-device recognition enabled
- fullScreenCover computed binding crash fixed with @State

### Settings
- `NavigationView` → `NavigationStack` for TabView .page compatibility
- Pure black background

### Discovery / Plans
- `docs/discoveries/ios-particle-animation-metal-vs-cgcontext-2026-03-26.md`
- `docs/plans/wavelength-metal-migration-second-opinion-2026-03-26.md`
- Multiple HTML mockups in `docs/superpowers/specs/`

## In Progress
- **Voice recording**: SFSpeechRecognizer rewrite shipped (build 60) — needs device testing to confirm crash is fixed
- **Wavelength choppiness**: Metal renderer should fix this but hasn't been tested on device yet (the CGContext fallback was still choppy)
- **Force Touch quick actions**: Moved from Command view but not yet implemented as UIApplicationShortcutItem

## Decisions Made
- Metal over CGContext for particle rendering — GPU eliminates CPU saturation / watchdog kills
- Instanced quads over point sprites — no size limits, future-proof
- SFSpeechRecognizer over SpeechAnalyzer — Apple's iOS 26 API crashes internally
- Pure black backgrounds — eliminates Metal/gradient compositing seam
- Gradient reserved for cards (Command/Settings) not backgrounds
- Wave center at 230pt from top (27% of screen) — approved via HTML mockup iteration
- Chat area starts at 39% of screen with 120px soft fade

## Test Status
- Backend: ~2915 passing (iOS-only changes, no backend regressions)
- iOS: BUILD SUCCEEDED (build 60)
- Some test errors in parallel session's Sentinel work (unrelated)

## Uncommitted Changes
- None (hestia/data/ is gitignored)

## Known Issues / Landmines
1. **Voice crash (build 60)**: SFSpeechRecognizer rewrite needs device verification. Previous 4 attempts (builds 55-59) all crashed on Swift 6 @MainActor isolation + Apple SpeechAnalyzer framework bug
2. **Wavelength still choppy on older builds**: Metal renderer hasn't been confirmed smooth on device yet — Andrew was testing CGContext builds (45-59). Build 60 has Metal.
3. **Parallel Sentinel session**: Another Claude session committed Sentinel work to main (7d099ec..4d17102). Our iOS commits are interleaved. No conflicts.
4. **Cloud mode**: Andrew enabled "Full Cloud" in iOS settings — confirmed working (Anthropic claude-opus-4-6, 3-5s responses). Local inference was 2+ minutes due to model swapping on M1 16GB.
5. **Notion whiteboard**: Andrew left extensive Phase 1 notes (iOS Command UX, macOS Settings, Memory, Onboarding, Explorer, etc.) — only iOS items addressed this session
6. **CI Metal Toolchain**: Added download step to release-ios.yml — first run on Mac Mini may take extra time for the 704MB download
7. **`ios-v1.11.0` tag retagged many times**: Tag was force-updated across builds 46-60. CI ran for each retag.

## Process Learnings

### First-Pass Success: ~60% (12/20 tasks)
- **Top blocker**: Swift 6 strict concurrency — the @MainActor isolation on audio threads required 5 iterations to fix
- **Second blocker**: Metal compositing seam — took 4 iterations to eliminate gradient/Metal transparency conflict (solved by going pure black)
- **Third blocker**: HTML mockup → native layout translation — wave Y positioning math was wrong when frame size changed between idle/conversation

### Config Gaps
1. **HOOK proposal**: Auto-test Swift builds after .swift edits (like auto-test.sh for Python). Would have caught the `NewsfeedItem` type mismatch before shipping.
2. **CLAUDE.MD gap**: No mention of Swift 6 strict concurrency gotchas — add section about @MainActor isolation on audio/Metal threads
3. **SKILL proposal**: `/ship-it ios` skill doesn't exist — the macOS ship-it skill was adapted manually each time. Should have a dedicated iOS variant.

### Agent Orchestration
- @hestia-explorer used well for initial research (wavelength files, Metal feasibility)
- @hestia-build-validator used but unreliable (Metal toolchain missing caused false positives)
- @hestia-critic provided excellent adversarial review of Metal migration
- Missed opportunity: should have used @hestia-tester for backend test verification instead of manual pytest runs

## Next Step
1. **Verify voice on device**: Install build 60 from TestFlight, tap the mic icon. If it still crashes, check `/Users/andrewlonati/Downloads/` for new .ips files.
2. **Verify Metal wavelength**: Check if the particle animation is smooth (60fps) on build 60. If still choppy, the Metal renderer may need debugging (check if `MTLCreateSystemDefaultDevice()` is returning nil — would fall back to CGContext).
3. **Implement Force Touch quick actions**: UIApplicationShortcutItem for Cloud Mode, Investigate, Journal, Lock — moved from Command view but not yet built.
4. **Notion whiteboard Phase 1 items**: macOS Settings, Memory Canvas, Command Audit, Onboarding refresh, Explorer file system, Orders Canvas default.
