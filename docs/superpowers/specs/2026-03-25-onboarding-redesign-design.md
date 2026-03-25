# Onboarding Redesign — Design Spec

**Date:** 2026-03-25
**Status:** Approved with conditions (see second opinion: `docs/plans/onboarding-redesign-second-opinion-2026-03-25.md`)
**Author:** Claude (brainstormed with Andrew)

### Prerequisites (Before Implementation)

- **Apple Developer Portal**: Enable "Sign in with Apple" capability for bundle ID `com.andrewlonati.hestia` in the Apple Developer account. Add `com.apple.developer.applesignin` entitlement to `HestiaApp/iOS/HestiaApp.entitlements`. The `aud` claim in Apple's identity token will be the bundle ID.
- **`python-jose[cryptography]`** is already in `requirements.in` — no new Python dependency for JWT validation. Only `zeroconf` is new.

---

## Problem Statement

The current iOS onboarding screen has three critical issues:

1. **Unreadable** — The `ai_blob` Lottie animation overflows its frame and dominates the screen with chaotic animated color shapes, making text illegible.
2. **Dead-end flow** — The only option is "Scan QR Code" but there's no obvious way for a first-time user to generate one. A user downloading from TestFlight hits an immediate wall.
3. **Not enterprise-grade** — The QR-only approach doesn't match the Apple ecosystem integration Hestia already has. A personal AI assistant deeply integrated with Apple services should authenticate like one.

## Design Decisions (Validated via Mockups)

### Visual Direction: "Dark + Warm Accent with Atmospheric Teal"

- **Background**: Single continuous 12-stop linear gradient — near-black at top, transitioning through warm dark tones to deep teal (`#245044`) at bottom. No separate shapes or hard edges. A buried radial glow at the bottom creates atmospheric light without a visible boundary.
- **Orb**: Centered in the upper ~55% of the screen. In production: a Metal shader rendering a fluid, luminous sphere with internal light wisps, refractive edge highlights, and organic distortion. Amber/warm color palette matching Hestia brand (`#E0A050` → `#A54B17`).
- **Typography**: "Hestia" in 38pt bold white, "Your personal AI assistant" in 16pt at 40% white opacity. Generous spacing.
- **Button**: Compact pill shape (not full-width), Liquid Glass treatment — frosted blur, multi-layer borders with brighter top edge, subtle teal-tinted underglow. Floats in the lower 25% of the screen.
- **Composition**: Vast negative space between title and button. The empty space IS the design — it signals premium quality.

### Auth Flow: Layered Discovery (Option C)

```
Welcome Screen
    ↓ tap "Get Started"
Sign in with Apple (ASAuthorizationAppleIDProvider)
    ↓ identity token received
Bonjour Discovery (2-3 second silent scan)
    ├─ Found → auto-connect → register device → success
    └─ Not found → show server URL field (pre-filled from Tailscale/last-known)
         ├─ Connect → register device → success
         └─ Footer: "Scan QR code instead" (tertiary escape hatch)
```

### Connecting/Success States

- **Connecting**: Orb becomes the focal point. Background fades to darker. Orb shader transitions to `.thinking` state — faster internal fluid rotation, brighter core, subtle scale pulse. Snarky rotating bylines below ("Consulting the council...", "Warming up neurons...").
- **Success**: Orb flashes bright (`.success` state) → bounces/flows upward off the top of the screen → view transitions to the Chat tab. The orb's exit motion creates a satisfying "launch" feeling.

---

## Architecture

### Component 1: HestiaOrb (Reusable Metal Shader)

**Purpose**: Fluid animated orb used across the app — onboarding, chat idle, thinking indicator, voice mode.

**Files**: `HestiaApp/Shared/Views/Common/HestiaOrb.swift` + `HestiaApp/Shared/Views/Common/HestiaOrb.metal`

**Cross-platform**: The Metal shader compiles for both iOS and macOS (Metal is available on both). The SwiftUI wrapper uses standard `TimelineView` + `.colorEffect()` — no platform-specific APIs. No `#if os()` guards needed. macOS will use it when the macOS onboarding is redesigned later.

**States** (drive shader uniforms):

| State | Behavior | Where Used |
|-------|----------|------------|
| `.idle` | Gentle fluid rotation, slow wisp movement, soft glow | Welcome screen, chat idle |
| `.thinking` | Faster rotation, brighter core, scale pulse | Connecting state, chat thinking |
| `.success` | Bright flash → upward bounce animation | Post-registration |
| `.listening` | Rhythmic pulse synced to audio input level | Voice conversation mode |

**Audio reactivity API**: The `HestiaOrbView` accepts an optional `audioLevel: Binding<Float>` (0.0-1.0) that maps to the shader's `intensity` uniform. When in `.listening` state, the orb pulses proportionally. The voice conversation view provides this binding from `AVAudioEngine` input level metering.

**Implementation approach**:
- Metal fragment shader (`HestiaOrb.metal`) — renders fluid plasma/noise simulation inside a circular mask
- Uniforms: `time` (float, auto-incremented), `state` (float, 0-3 for blending between states), `intensity` (float, 0-1 for audio reactivity), `color_primary` (float3, brand amber), `color_secondary` (float3, brand teal)
- SwiftUI wrapper: `HestiaOrbView` — `TimelineView(.animation)` driving the shader via `.colorEffect()` or `.layerEffect()` modifier
- Reduce Motion: falls back to static radial gradient with brand colors (no shader, no animation)
- The shader simulates: 2-3 layers of simplex noise at different scales/speeds, circular UV mapping for sphere illusion, Fresnel edge glow, internal caustic highlights

**Dependencies**: None external. Metal is built into iOS/macOS.

### Component 2: OnboardingView (Redesigned)

**File**: `HestiaApp/Shared/Views/Auth/OnboardingView.swift` (replace existing)

**State machine**:

```swift
enum OnboardingStep: Equatable {
    case welcome           // Orb + title + "Get Started"
    case appleSignIn       // Sign in with Apple sheet (system-managed)
    case discovering       // Bonjour scan (orb in .thinking state)
    case serverURL         // Manual URL entry (Bonjour failed)
    case connecting        // Registering with server (orb in .thinking state)
    case success           // Orb flash + bounce off → transition to main app
    case error(String)     // Error with retry
}
```

**Step details**:

**welcome**: Dark atmospheric background, HestiaOrb in `.idle`, "Hestia" title, subtitle, "Get Started" pill button. No animation on background — all motion concentrated in the orb.

**appleSignIn**: System `SignInWithAppleButton` presented. The `onCompletion` handler receives `ASAuthorizationAppleIDCredential` containing `identityToken`, `user` (stable ID), `email` (first sign-in only), and `fullName`. **If the user cancels** (`.cancelled` error domain), return to `.welcome` — no error message, just silently go back.

**discovering**: Background dims slightly. Orb transitions to `.thinking`. Text: "Looking for your Hestia server..." with subtle animated ellipsis. `NWBrowser` scans for `_hestia._tcp` service type for up to 3 seconds. If found, extract server URL from Bonjour TXT record → jump to `connecting`. If timeout → jump to `serverURL`.

**serverURL**: Orb stays in gentle `.idle`. A frosted-glass text field appears below the title area, pre-filled with the best guess:
  1. Last known server URL (from UserDefaults)
  2. Tailscale detection: if `hestia-3.local` resolves, pre-fill `https://hestia-3.local:8443`
  3. Empty with placeholder "https://your-server:8443"

Below the field: "Connect" pill button. Footer link: "Scan QR code instead" (opens existing QR scanner).

**connecting**: Orb in `.thinking`. Text: rotating snarky bylines (reuse existing `SnarkyBylineView`). Calls new backend endpoint `POST /v1/auth/register-with-apple` with the Apple identity token + server URL. Server validates token, matches email, issues device JWT.

**success**: Orb transitions to `.success` — bright flash, then animates upward off screen using `matchedGeometryEffect` or explicit offset animation. After orb exits, view transitions to `MainTabView` (chat tab).

**error**: Orb returns to `.idle`. Error message displayed with "Try Again" button (→ back to `discovering` or `serverURL` depending on where it failed).

### Component 3: Backend — Apple Identity Endpoint

**File**: `hestia/api/routes/auth.py` (add endpoint)

**New endpoint**: `POST /v1/auth/register-with-apple`

```python
class AppleRegisterRequest(BaseModel):
    identity_token: str      # JWT from Apple
    device_name: str = ""
    device_type: str = "ios"
    # Note: server URL is NOT included — the client already knows the server URL
    # because it's connecting to it. The server knows its own URL from config.

class AppleRegisterResponse(BaseModel):
    device_token: str        # Hestia JWT
    device_id: str
    server_url: str          # Echo back for client confirmation
    expires_at: str
```

**Server-side validation flow**:
1. Fetch Apple's public keys from `https://appleid.apple.com/auth/keys` (cache-then-refresh-on-miss strategy: cache indefinitely, refetch when a `kid` is not found in cache. Also refresh daily as Apple recommends.)
2. Decode and verify the JWT using `python-jose` with RS256
3. Validate claims: `iss` == `https://appleid.apple.com`, `aud` == `com.andrewlonati.hestia` (bundle ID), `exp` not expired
4. Extract `sub` (stable Apple user identifier) and `email` (may be nil on subsequent sign-ins)
5. **Identity matching** (two-tier):
   - **Primary**: Look up `sub` in `registered_devices` table (new `apple_user_id` column). If found, this is a returning device re-registration.
   - **Secondary** (first-time only): If `email` is present, match against configured owner email in user profile. Store `sub` in device registry for future lookups.
   - **Fallback**: If neither matches and this is a single-user server, auto-approve the first Apple Sign In and store the `sub` as the owner identity.
6. If matched/approved: create device token, register in device store (with `apple_user_id`), return JWT
7. If not matched: return 403 with clear error ("No Hestia account found for this Apple ID")
8. **Rate limiting**: 10 attempts per hour per IP (matches invite endpoint pattern)
9. **Error sanitization**: Use `sanitize_for_log(e)` for all error logging, never expose raw errors in response

**Apple key rotation note**: Apple rotates public keys periodically. The cache-then-refresh-on-miss strategy handles this gracefully — if a token's `kid` isn't in the cached keyset, refetch from Apple before failing.

**Dependencies**: `python-jose[cryptography]` (add to requirements.in)

### Component 4: Bonjour Service Advertisement

**File**: `hestia/api/server.py` (add on startup)

The Hestia server advertises itself on the local network so iOS/macOS apps can auto-discover it.

**Python side** (using `zeroconf` library):
- Service type: `_hestia._tcp`
- Port: 8443
- TXT record: `{"url": "https://hestia-3.local:8443", "fp": "<cert_fingerprint>", "v": "1"}`
- Register on server startup, unregister on shutdown

**iOS side** (`NWBrowser` in Network.framework):
- Browse for `_hestia._tcp` service type
- Extract URL and cert fingerprint from TXT record
- Requires `NSLocalNetworkUsageDescription` in Info.plist
- Requires `_hestia._tcp` in `NSBonjourServices` array in Info.plist

**Lifecycle**: Register on server startup, unregister on clean shutdown. Stale records (crash/force-kill) expire via mDNS TTL (default 75 minutes). Bind to all interfaces (Mac Mini may have both Ethernet and Wi-Fi). The cert fingerprint for the TXT record is read from the `HESTIA_CERT_FINGERPRINT` env var (already used by the invite system).

**Dependencies**: `zeroconf` Python package (add to requirements.in)

**Info.plist entries** (via `project.yml` info properties):
```yaml
NSLocalNetworkUsageDescription: "Hestia uses your local network to discover your Hestia server."
NSBonjourServices:
  - "_hestia._tcp"
```

### Component 5: Background Gradient View (Replacement)

**File**: `HestiaApp/Shared/Views/Common/OnboardingBackground.swift` (new)

Replaces `StaticGradientBackground` for onboarding screens. A static (non-animated) view with:
- 12-stop linear gradient from near-black to deep teal
- Buried radial glow at bottom center
- No animation (all motion concentrated in the orb)
- Respects Reduce Motion (identical — it's already static)

---

## Files Changed

| File | Action | Description |
|------|--------|-------------|
| `HestiaApp/Shared/Views/Common/HestiaOrb.swift` | **New** | SwiftUI wrapper for the Metal orb shader |
| `HestiaApp/Shared/Views/Common/HestiaOrb.metal` | **New** | Metal fragment shader — fluid plasma sphere |
| `HestiaApp/Shared/Views/Common/OnboardingBackground.swift` | **New** | Dark-to-teal atmospheric gradient |
| `HestiaApp/Shared/Views/Auth/OnboardingView.swift` | **Replace** | Full rewrite with new flow |
| `HestiaApp/Shared/ViewModels/OnboardingViewModel.swift` | **Replace** | New state machine with Apple auth + discovery |
| `HestiaApp/Shared/Views/Auth/AuthView.swift` | **Modify** | Update to use HestiaOrb instead of LottieView |
| `HestiaApp/iOS/Info.plist` | **Modify** | Add Bonjour service types, local network description |
| `HestiaApp/Shared/App/ContentView.swift` | **Modify** | Update RootView routing for new onboarding states |
| `hestia/api/routes/auth.py` | **Modify** | Add `/v1/auth/register-with-apple` endpoint |
| `hestia/api/schemas/auth.py` | **Modify** | Add Apple auth request/response schemas |
| `hestia/api/server.py` | **Modify** | Add Bonjour/zeroconf service advertisement |
| `requirements.in` | **Modify** | Add `zeroconf` (python-jose already present) |
| `hestia/api/schemas/__init__.py` | **Modify** | Export `AppleRegisterRequest`, `AppleRegisterResponse` |
| `HestiaShared/Sources/HestiaShared/Auth/AuthService.swift` | **Modify** | Add `signInWithApple()` and `registerWithAppleIdentity()` |
| `HestiaShared/Sources/HestiaShared/Networking/ServerDiscovery.swift` | **New** | NWBrowser wrapper for Bonjour discovery |
| `HestiaApp/iOS/HestiaApp.entitlements` | **Modify** | Add `com.apple.developer.applesignin` entitlement |
| `HestiaApp/project.yml` | **Modify** | Add Bonjour services to Info.plist generation |

## Testing Strategy

- **Metal shader**: Visual verification only — no automated test. Verify on device (simulator may not render Metal identically). Test Reduce Motion fallback.
- **Onboarding flow**: Manual test all paths: Bonjour found, Bonjour timeout → manual URL, QR fallback, error recovery
- **Apple auth**: Mock `ASAuthorizationAppleIDCredential` in tests. Backend: unit test JWT validation with a test token.
- **Bonjour discovery**: Integration test on local network. Verify Info.plist entitlements. Test timeout behavior.
- **Backend endpoint**: pytest for `/v1/auth/register-with-apple` — valid token, expired token, unknown email, missing fields

## Security Notes

- The existing `/v1/auth/register` (open registration) and `/v1/auth/register-with-invite` (QR) endpoints remain unchanged. The `HESTIA_REQUIRE_INVITE` env var continues to gate open registration. Apple Sign In is an additional registration path, not a replacement.
- The existing QR scanner flow is preserved as a fallback option — no code removed, just deprioritized in the UI.
- Lottie dependency remains — `AuthView.swift` and `LoadingView.swift` still use `LottieView`. The `ai_blob.json` asset can be removed once `HestiaOrb` replaces it in all locations (tracked as future cleanup, not this sprint).

## Not In Scope

- macOS onboarding redesign (keep current paste-based flow, update visual later)
- Multi-server selection UI (future — QR fallback covers this for now)
- Apple Sign In account linking/unlinking in settings
- Orb usage on chat screen (reusable component is built, integration is a separate task)
