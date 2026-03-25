# Second Opinion: Onboarding Redesign — Implementation Approach

**Date:** 2026-03-25
**Models:** Claude Opus 4.6 (internal) + Gemini 2.5 Pro (external) + hestia-critic (adversarial)
**Verdict:** APPROVE WITH CONDITIONS

## Plan Summary

Replace the broken iOS onboarding (unreadable Lottie animation, dead-end QR-only flow) with a premium dark atmospheric visual design, reusable fluid orb component, Sign in with Apple authentication, and layered server discovery (Bonjour → manual URL → QR fallback). Spec: `docs/superpowers/specs/2026-03-25-onboarding-redesign-design.md`.

---

## Front-Line Engineering Review

### Metal Shader: High Risk, Questionable ROI

**Finding:** Zero Metal infrastructure exists in the codebase — no `.metal` files, no shader build phase, no SwiftUI shader APIs used anywhere. The spec proposes "2-3 layers of simplex noise, circular UV mapping, Fresnel edge glow, internal caustic highlights." This is a non-trivial fragment shader that requires specialized graphics programming knowledge.

**Risk assessment:**
- Estimated effort: 40-80 hours for production quality (fluid plasma simulation is hard)
- Testing: "Visual verification only" — no automated tests, requires physical device
- Debugging: GPU Frame Capture required for shader issues — unfamiliar tooling
- Maintenance: Future orb states require reopening shader code with no tests and no established patterns

**Gemini's alternative (STRONG AGREEMENT):** "Metal is the wrong tool for the job. This is an extreme architectural escalation."

**Three viable alternatives ranked by quality/effort:**

| Approach | Quality | Effort | Risk | Recommendation |
|----------|---------|--------|------|----------------|
| SwiftUI `Canvas` + `TimelineView` with noise functions | 85% | 8-15h | Low | **Primary choice** — stays in SwiftUI, GPU-accelerated, supports state transitions |
| Professional Lottie animation (commission/create) | 80% | 3-5h (create) + asset cost | Very low | **Fallback** — proven infrastructure already exists (`LottieView` wrapper) |
| Custom Metal shader | 95% | 40-80h | High | **Defer** — build v1 with Canvas, upgrade to Metal in a dedicated sprint if warranted |
| SceneKit sphere with animated material | 75% | 15-25h | Medium | Not recommended — different complexity for marginal gain over Canvas |

**Condition #1:** Start with a **2-day time-boxed spike** on SwiftUI `Canvas` + `TimelineView`. Use layered noise functions (`sin`/`cos` combinations at different frequencies) with circular UV mapping for the sphere illusion. If the result doesn't meet the quality bar after 2 days, fall back to a professionally designed Lottie animation. **Do not invest in Metal for v1.**

### Bonjour/mDNS: Fundamentally Incompatible with Primary Use Case

**Finding:** Bonjour/mDNS does NOT work over Tailscale. The Tailscale overlay network is Layer 3; mDNS packets are link-local (TTL=1) and don't cross the Tailscale interface. This means:

- **iPhone on Tailscale → Mac Mini on Tailscale**: Bonjour FAILS
- **iPhone on same Wi-Fi → Mac Mini on same LAN**: Bonjour works
- **iPhone on cellular**: Bonjour FAILS

The primary connection method (Tailscale) gets zero benefit from Bonjour. The `hestia-3.local` hostname resolves via Tailscale MagicDNS, not mDNS.

**Critic's insight:** "Bonjour adds complexity for the narrow case (same LAN, no Tailscale) while the working case (Tailscale everywhere) requires none of it."

**Additional cost:** The `NWBrowser` scan triggers iOS's local network permission dialog ("Hestia wants to find and connect to devices on your local network") — a jarring system prompt immediately after Apple Sign In, before the user has seen the app do anything useful. If denied, no in-app recovery path.

**Condition #2:** **Drop Bonjour from v1 entirely.** Replace with Tailscale-aware URL pre-fill: attempt to resolve `hestia-3.local` via DNS (works on Tailscale), pre-fill the URL field if it resolves. This achieves the "smart discovery" UX without mDNS, without a new Python dependency, without permission prompts, and without a feature that silently fails in the primary use case.

### Registration Paths: Simplify to Two

**Current spec:** Four paths (Apple + Bonjour + Manual URL + QR)
**Recommended:** Two paths (Apple + Manual URL, with QR as hidden fallback)

Simplified flow:
```
Welcome → Get Started → Sign in with Apple →
  Attempt DNS resolution of hestia-3.local →
    Resolves? → pre-fill URL, auto-connect → register → success
    Doesn't resolve? → show URL field (empty) → user enters URL → register → success
  Footer: "Connect with QR code" (tertiary, existing code)
```

This eliminates: `zeroconf` dependency, `NWBrowser` code, Bonjour Info.plist entries, local network permission prompt, 3-second discovery timeout UX, Python mDNS advertisement in server.py.

**Condition #3:** Implement the simplified two-path flow. Keep QR as a footer link (existing code, zero new engineering).

### Cross-View Orb Animation

**Finding:** `matchedGeometryEffect` requires source and destination views in the same hierarchy with a shared `Namespace`. The onboarding orb and chat view are in separate view hierarchy roots (`RootView` switches between `OnboardingView` and `MainTabView`). The effect will silently no-op.

**Condition #4:** Use explicit `withAnimation` + `.offset` + `.opacity` for the orb exit. The orb animates upward and fades out, then `RootView` transitions to `MainTabView` with a crossfade. Build the functional flow first, add animation last.

### Apple Sign In Security: Close the Auto-Approve Hole

**Critic's finding:** The "auto-approve first Apple Sign In" fallback (spec line 151) creates a race condition — anyone with the TestFlight build who onboards before the owner claims the owner slot and locks out the real owner with a 403.

**Condition #5:** Remove the auto-approve fallback. Instead:
- First-time setup still requires the existing setup secret (server-side) to configure the owner's Apple ID (`sub`)
- Or: the first QR-based registration stores the Apple `sub` from that session
- Subsequent Apple Sign Ins match against the stored `sub`
- This preserves the security guarantee that the server owner controls who registers

---

## Executive Verdicts

- **CISO:** APPROVE WITH CONDITIONS — Apple identity token validation is sound. Remove auto-approve fallback (race condition). Drop Bonjour (eliminates unnecessary permission prompt and attack surface).
- **CTO:** APPROVE WITH CONDITIONS — SwiftUI Canvas over Metal (proven patterns > novel infrastructure). Simplify to two registration paths. Build functional flow first, polish last.
- **CPO:** APPROVE — Visual direction is validated and premium. The simplified flow (Apple Sign In → smart URL) delivers the same first-run UX without the complexity.
- **CFO:** APPROVE WITH CONDITIONS — Metal spike is the biggest cost risk. Canvas approach reduces effort from 40-80h to 8-15h. Dropping Bonjour saves ~10-15h of implementation + testing.
- **Legal:** APPROVE — Sign in with Apple complies with App Store guidelines. Apple identity token handling follows Apple's recommended practices.

## Key Principles Score

| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 4 | Apple auth is strong. Condition: remove auto-approve. |
| Empathy | 5 | Solves a real, immediate problem (can't get past onboarding) |
| Simplicity | 3 → 5 with conditions | Original spec: 3 (four paths, Metal, Bonjour). With conditions: 5 |
| Joy | 5 | The visual direction is genuinely beautiful |

## Cross-Model Validation (Gemini 2.5 Pro)

### Gemini's Independent Assessment

Gemini gave **APPROVE WITH CONDITIONS** with these key points:
- "Metal is the wrong tool for the job — an extreme architectural escalation"
- "Bonjour is fundamentally incompatible with your architecture"
- "Four registration paths are three too many"
- Recommended: SwiftUI Canvas + `TimelineView` for orb, or Lottie as fallback
- Recommended: Single QR flow + Sign in with Apple (more conservative than our simplified approach)
- Build functional flow first, add `matchedGeometryEffect` animation last

### Where Both Models Agree (High Confidence)

- **Do NOT use Metal for v1** — Canvas or Lottie instead
- **Drop Bonjour** — fundamentally incompatible with Tailscale
- **Simplify registration paths** — fewer is better
- **Build functional flow first, animation last** — de-risk the hard parts
- **matchedGeometryEffect is fragile** — use explicit animation

### Where Models Diverge

| Topic | Claude | Gemini | Resolution |
|-------|--------|--------|------------|
| Registration flow | Apple Sign In → smart URL pre-fill → QR fallback | Server-initiated QR + Sign in with Apple (no manual URL) | **Claude's approach** — manual URL with smart pre-fill is simpler and doesn't require QR generation infrastructure changes. The existing QR flow remains as escape hatch. |
| Orb technology | Canvas primary, Lottie fallback | Canvas primary, Lottie fallback | **Agreement** |
| Bonjour | Drop from v1 | Drop entirely | **Agreement** |

### Novel Insights from Gemini

1. "A `TimelineView(.animation)` drives at display refresh rate — up to 120fps on ProMotion devices. This burns GPU cycles continuously on a screen the user sees exactly once per device lifetime." — Good point: implement frame-rate throttling or use `.animation(minimumInterval: 1/30)` for the orb.
2. "Store `baseUrl` in Keychain" rather than UserDefaults — better security posture for server URL.

---

## Conditions for Approval (Summary)

1. **Orb: Canvas + TimelineView, not Metal.** 2-day spike. Lottie fallback if quality insufficient.
2. **Drop Bonjour entirely.** Use Tailscale-aware DNS resolution for smart URL pre-fill.
3. **Two registration paths** — Apple Sign In + manual URL (with smart pre-fill). QR as hidden footer link.
4. **Explicit animation** for orb exit (offset + opacity), not matchedGeometryEffect. Add animation last.
5. **Remove auto-approve fallback.** First-time owner identity set via existing setup-secret flow or first QR registration.

## Recommended Implementation Order

1. **Backend first** — `POST /v1/auth/register-with-apple` endpoint + Apple JWT validation + tests
2. **iOS auth flow** — Sign in with Apple → server URL field (pre-filled via DNS) → register → functional (no polish)
3. **Visual foundation** — `OnboardingBackground` gradient + pill button + Liquid Glass styling
4. **Orb spike** — 2-day time-box on Canvas + TimelineView fluid orb with state transitions
5. **Integration** — Wire orb into onboarding, wire states to network activity
6. **Animation polish** — Orb exit animation, view transitions, connecting/success states
7. **Cleanup** — Remove old Lottie from onboarding, update tests
