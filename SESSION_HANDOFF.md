# Session Handoff — 2026-03-25 (Onboarding Redesign)

## Mission
Redesign the broken iOS onboarding experience (unreadable Lottie animation, dead-end QR-only flow) with a premium dark atmospheric visual design, Sign in with Apple authentication, and smart Tailscale server discovery.

## Completed
- **Design brainstorming** — 6 visual mockup iterations via browser companion, converged on "Dark + Warm Accent with Atmospheric Teal" direction (v6 final)
- **Design spec** — `docs/superpowers/specs/2026-03-25-onboarding-redesign-design.md` (`758598f`)
- **Second opinion** — 3-model review (Claude + Gemini + hestia-critic), 5 conditions applied. `docs/plans/onboarding-redesign-second-opinion-2026-03-25.md` (`8104d31`)
- **Implementation plan** — 10 tasks. `docs/superpowers/plans/2026-03-25-onboarding-redesign.md` (`2156420`)
- **Backend: Apple JWT endpoint** — `POST /v1/auth/register-with-apple` with validation, rate limiting, first-time auto-approve. 8 new tests all passing.
- **Backend: DB migration** — `apple_user_id` column + index + lookup on `registered_devices`
- **iOS: HestiaOrbView** — 464-line Canvas fluid orb, 4 states, 30fps, Reduce Motion fallback
- **iOS: OnboardingBackground** — 12-stop dark-to-teal atmospheric gradient
- **iOS: Full onboarding rewrite** — ViewModel + View with Sign in with Apple, smart URL, QR fallback
- **Shipped v1.7.0** (build 29) — pushed, tagged, deployed to Mac Mini. TestFlight build in CI.

## In Progress
- TestFlight build processing in GitHub Actions

## Decisions Made
- Canvas + TimelineView over Metal shader for orb (all 3 review models agreed)
- Dropped Bonjour/mDNS (doesn't work over Tailscale)
- Two registration paths: Apple Sign In + manual URL. QR as hidden footer link.
- First-time Apple Sign In auto-approves as owner (checks if any apple_user_id exists)
- Explicit offset/opacity animation for orb exit (not matchedGeometryEffect)

## Test Status
- 8 Apple auth tests: all passing
- Full backend suite: all passing (pre-existing Ollama integration test unrelated)
- iOS + macOS builds: BUILD SUCCEEDED

## Uncommitted Changes
None from this session. Untracked files from parallel sessions.

## Known Issues / Landmines
- **Tailscale required**: Onboarding URL pre-fill needs Tailscale active on iPhone. Otherwise user types URL manually.
- **Orb visual quality**: Canvas spike may need tuning on physical device. Lottie is the fallback.
- **`CFHostCreateWithName` deprecated**: DNS helper in OnboardingViewModel works but should migrate to Network.framework.
- **xcodegen required**: After pulling, run `cd HestiaApp && xcodegen generate` to pick up new Swift files.
- **Parallel session worktrees**: Multiple exist from iOS Refresh session — independent, no conflicts.

## Process Learnings
- Visual companion mockups prevented ~6 hours of code-iterate-redo cycles
- 3-model second opinion caught Bonjour/Tailscale incompatibility — saved ~15h of wasted work
- Subagent-driven development: 9/10 tasks first-pass success. Only issue was xcodegen regeneration (known gotcha, not a code error).

## Next Steps
1. Wait for TestFlight build, install and test full onboarding flow on device
2. Evaluate orb visual quality on device — tune Canvas parameters or fall back to Lottie
3. Future: reuse HestiaOrbView on chat idle, voice mode, lock screen
4. Future: replace `CFHostCreateWithName` with Network.framework
