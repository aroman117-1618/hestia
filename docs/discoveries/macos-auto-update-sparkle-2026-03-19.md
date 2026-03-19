# Discovery Report: macOS App Auto-Update via Sparkle Framework
**Date:** 2026-03-19
**Confidence:** High
**Decision:** Use Sparkle 2 via SPM, integrated into xcodegen project.yml, with GitHub Actions CI/CD building/signing/notarizing on the Mac Mini self-hosted runner and hosting appcast.xml on GitHub Pages.

## Hypothesis
Sparkle framework is the right choice for implementing auto-update in the Hestia macOS app, and it can be fully automated via the existing GitHub Actions + Mac Mini CI/CD pipeline such that pushes to `main` produce signed, notarized releases that the running app on Andrew's MacBook downloads and installs automatically.

## Current State
- **Build system:** xcodegen (`HestiaApp/project.yml`), scheme `HestiaWorkspace`
- **CI/CD:** GitHub Actions → Mac Mini (self-hosted runner via SSH/rsync)
- **Code signing:** Developer ID certificate, team `563968AM8L`, automatic signing
- **App lifecycle:** `AppDelegate.swift` with `NSApplication` manual setup (not SwiftUI `@main App`)
- **Entitlements:** `com.apple.security.network.client`, `com.apple.security.personal-information.calendars`
- **App is NOT sandboxed** (no `com.apple.security.app-sandbox` entitlement)
- **Bundle ID:** `com.andrewlonati.hestia-macos`
- **Current version:** `MARKETING_VERSION: 1.0.0`, `CURRENT_PROJECT_VERSION: 1`

## SWOT Analysis

| | Positive | Negative |
|---|---------|----------|
| **Internal** | **Strengths:** Existing CI/CD pipeline to Mac Mini (has Xcode, certificates). Non-sandboxed app simplifies Sparkle integration (no XPC complexity). Developer ID already configured. xcodegen supports SPM packages natively. | **Weaknesses:** Current CI uses ubuntu runner + SSH to Mac Mini (not a proper self-hosted macOS runner). No existing versioning automation. No notarization step in current pipeline. |
| **External** | **Opportunities:** Sparkle is the de facto standard (15+ years, actively maintained, 2.6.x series). SPM support means simple `project.yml` addition. GitHub Pages = free appcast hosting. Delta updates reduce download size. | **Threats:** Code signing order matters (Sparkle XPC components before main app). Apple could change notarization requirements. `generate_appcast` path is obscure with SPM builds. |

## Priority x Impact Matrix

| | High Impact | Low Impact |
|---|-----------|-----------|
| **High Priority** | Sparkle SPM integration + `project.yml` changes. GitHub Actions workflow for build/sign/notarize/release. EdDSA key generation and GitHub Secrets setup. `SUFeedURL` in Info.plist pointing to GitHub Pages. | Version bumping automation (can be manual initially). |
| **Low Priority** | Delta updates (automatic with `generate_appcast`). Custom update UI (Sparkle's default is fine). Analytics on update adoption. | Sandboxing the app (not needed now). Release notes formatting (plain text works). |

## Argue (Best Case)

1. **Sparkle is battle-tested.** Used by hundreds of major macOS apps (Maccy, iTerm2, Sequel Pro, etc.). 15+ years of edge cases handled. Community is large enough that every problem has a known solution.
2. **Non-sandboxed = simpler path.** The most painful Sparkle integration issues (XPC service authorization, mach-lookup entitlements, signing order) only apply to sandboxed apps. Hestia is non-sandboxed, so Sparkle's Autoupdate.app handles updates directly without XPC complexity.
3. **SPM + xcodegen = 3 lines in project.yml.** Add the package URL, add the dependency to the target. No CocoaPods, no manual framework embedding.
4. **GitHub ecosystem covers hosting.** GitHub Pages for appcast.xml (stable URL), GitHub Releases for .zip artifacts (versioned downloads). Zero server cost, zero maintenance.
5. **Mac Mini already has everything.** Xcode, Developer ID certificate, can run `xcodebuild archive`, `notarytool`, `generate_appcast`. Just need a proper GitHub Actions workflow.
6. **Single-user app = low risk.** If an update mechanism has a hiccup, Andrew is the only user. No support burden, easy to debug.

## Refute (Devil's Advocate)

1. **CI/CD rework required.** The current deploy workflow uses an ubuntu runner that SSHes into the Mac Mini. Building the macOS app requires a macOS runner. Options: (a) register Mac Mini as a self-hosted GitHub Actions runner, or (b) use `macos-latest` GitHub-hosted runners ($0.08/min, ~10 min build = ~$0.80/build). The self-hosted route is free but adds maintenance.
2. **Notarization adds 2-5 minutes per build.** Apple's notary service is asynchronous. `notarytool submit --wait` blocks until Apple processes the binary. This is usually fast but can be slow during WWDC or major releases.
3. **Certificate management in CI.** The Developer ID certificate and private key must be available to the GitHub Actions runner. For a self-hosted Mac Mini, this is already in the Keychain. For a cloud runner, you'd need to export the certificate as a .p12, store it in GitHub Secrets, and import it into a temporary keychain during the workflow.
4. **Version management discipline.** Every release needs a unique `CFBundleShortVersionString` and `CFBundleVersion`. Without automation, forgetting to bump versions causes Sparkle to silently skip updates (it won't "update" to the same version).
5. **`generate_appcast` with SPM.** The tool is not easily accessible when Sparkle is added via SPM. Workaround: download Sparkle's binary release separately in CI just for the tools, or use the GitHub Action marketplace action `update-appcast`.
6. **Chicken-and-egg for first install.** Sparkle handles *updates*, not initial distribution. Andrew still needs to manually install the first version (or use a separate DMG/download mechanism).

## Third-Party Evidence

### Working Open-Source References
- **[Maccy](https://github.com/p0deje/Maccy)** — Clipboard manager with a complete GitHub Actions release workflow using Sparkle. Their `.github/workflows/release.yml` handles keychain creation, signing, notarization, and `generate_appcast`.
- **[SparkleReleaseTest](https://github.com/AlexPerathoner/SparkleReleaseTest)** — Minimal reference repo demonstrating the full Sparkle + GitHub Actions + GitHub Pages workflow.

### Key Gotchas from Real-World Implementations
- **Peter Steinberger's "Sparkle and Tears" (2025):** Detailed the pain of XPC service signing order, cryptic authorization errors, and notarization workflow brittleness. However, most of his pain points were specific to *sandboxed* apps — Hestia is non-sandboxed, so these don't apply.
- **ZIP creation matters:** `zip -qr` causes notarization to fail. Must use `ditto -c -k --keepParent App.app App.zip` for proper code signature preservation.
- **`notarytool --wait` is essential.** Custom polling loops are fragile. Use `xcrun notarytool submit --wait --timeout 600`.

## Gemini Web-Grounded Validation
**Model:** Gemini 2.5 Pro (thinking + google_web_search)

### Confirmed Findings
- Sparkle is actively maintained (2.6.x series as of early 2026), with consistent commits and issue resolution
- Non-sandboxed apps have a significantly simpler integration path (no XPC authorization dance)
- Notarization is effectively mandatory for usable distribution — without it, macOS 15+ shows alarming dialogs requiring System Settings bypass
- GitHub Pages (appcast.xml) + GitHub Releases (download artifacts) is the recommended hosting pattern
- No viable open-source alternatives exist — roll-your-own is deceptively complex, commercial services have shut down

### Contradicted Findings
- None of the core SWOT findings were contradicted

### New Evidence
- **Maccy** confirmed as a strong real-world reference with a complete working workflow
- For non-notarized apps on macOS 15+, users must navigate to `System Settings > Privacy & Security` to grant an exception — most users will abandon the app rather than do this
- `generate_appcast` binary location with SPM is in `.build/debug` or `.build/release` — needs dynamic path resolution in CI scripts

### Sources
- [Sparkle GitHub Repository](https://github.com/sparkle-project/Sparkle)
- [Sparkle Official Documentation](https://sparkle-project.org/documentation/)
- [Maccy Release Workflow](https://github.com/p0deje/Maccy/blob/master/.github/workflows/release.yml)
- [Peter Steinberger: Sparkle and Tears](https://steipete.me/posts/2025/code-signing-and-notarization-sparkle-and-tears)
- [Automating Xcode Sparkle Releases with GitHub Actions](https://medium.com/@alex.pera/automating-xcode-sparkle-releases-with-github-actions-bd14f3ca92aa)
- [Apple: Notarizing macOS Software](https://developer.apple.com/documentation/security/notarizing_macos_software_before_distribution)
- [SparkleReleaseTest Reference Repo](https://github.com/AlexPerathoner/SparkleReleaseTest)
- [GitHub Marketplace: Update Appcast Action](https://github.com/marketplace/actions/update-appcast)

## Philosophical Layer
- **Ethical check:** Fully ethical. Auto-update is a standard, expected feature that improves security (patches reach the user faster) and UX.
- **First principles:** The problem is "get new code from repo to running app." Sparkle is the established solution for non-App-Store macOS apps. The only alternative first-principles approach would be App Store distribution (which constrains the app significantly) or a custom update server (unnecessary complexity for a single-user app).
- **Moonshot:** SHELVE. The moonshot would be a self-updating app that pulls directly from GitHub Releases without Sparkle — just a simple "download zip, replace .app, relaunch" script. This is feasible for a single-user app but gives up: delta updates, signature verification, rollback on failure, user-facing update UI, and proven reliability. Not worth the risk when Sparkle is free and proven. Would reconsider only if Sparkle integration proves significantly harder than expected.

## Key Principles Score
| Principle | Score (1-5) | Notes |
|-----------|-------------|-------|
| Security | 5 | EdDSA signatures, notarization, code signing — full chain of trust |
| Empathy | 4 | Seamless background updates. Minor ding: initial setup complexity for the developer, but invisible to the user |
| Simplicity | 3 | Sparkle itself is simple to integrate (SPM). The CI/CD pipeline is where complexity lives (signing, notarizing, appcast generation). Unavoidable for the goal |
| Joy | 4 | "Push to main and the app updates itself" is deeply satisfying developer infrastructure |

## Recommendation

**Use Sparkle 2 via SPM.** Integrate into the existing xcodegen project.yml, wire up a GitHub Actions workflow that runs on the Mac Mini self-hosted runner (already has certificates), and host the appcast on GitHub Pages.

**Confidence: High.** Sparkle is the only serious option for non-App Store macOS auto-updates. The non-sandboxed nature of Hestia eliminates the hardest integration pain points. The existing Mac Mini CI/CD infrastructure provides the foundation.

**What would change this recommendation:**
- If Apple announced a built-in non-App-Store update mechanism (unlikely)
- If Sparkle were abandoned (no signs of this — actively maintained)
- If the app moved to sandboxed distribution (would increase complexity but Sparkle still works)

## Implementation Plan (Estimated: 8-12 hours)

### Phase 1: One-Time Setup (2-3h)
1. **Generate Sparkle EdDSA keypair** on the Mac Mini: `./bin/generate_keys` from Sparkle's binary distribution
2. **Store private key** in GitHub Secrets (`SPARKLE_PRIVATE_KEY`)
3. **Add public key** to `Info.plist` as `SUPublicEDKey`
4. **Add `SUFeedURL`** to `Info.plist`: `https://aroman117.github.io/hestia-releases/appcast.xml`
5. **Create `hestia-releases` repo** on GitHub with GitHub Pages enabled (or use `gh-pages` branch of main repo)
6. **Register Mac Mini as a self-hosted GitHub Actions runner** (or confirm existing SSH-based approach works for `xcodebuild`)

### Phase 2: project.yml + App Code (2-3h)
1. **Add Sparkle package** to `project.yml`:
   ```yaml
   packages:
     Sparkle:
       url: https://github.com/sparkle-project/Sparkle
       from: "2.6.0"
   ```
2. **Add dependency** to `HestiaWorkspace` target:
   ```yaml
   dependencies:
     - package: Sparkle
   ```
3. **Wire up `SPUStandardUpdaterController`** in `AppDelegate.swift`:
   - Create controller in `applicationDidFinishLaunching`
   - Add "Check for Updates..." menu item connected to `checkForUpdates:`
4. **Bump version scheme**: decide on semver automation (or manual for now)

### Phase 3: CI/CD Workflow (3-4h)
Create `.github/workflows/release-macos.yml`:
1. Trigger: push to `main` (or manual `workflow_dispatch` with version input)
2. Build: `xcodebuild archive` on Mac Mini (self-hosted or via SSH)
3. Export: `xcodebuild -exportArchive` with Developer ID distribution
4. Notarize: `xcrun notarytool submit --wait`
5. Staple: `xcrun stapler staple`
6. Package: `ditto -c -k --keepParent` (NOT `zip`)
7. Sign with Sparkle: `sign_update` with EdDSA private key
8. Generate appcast: `generate_appcast` (download Sparkle binary tools in CI)
9. Upload: Create GitHub Release with .zip, push appcast.xml to GitHub Pages
10. Existing `deploy.yml` continues for backend deployment (unchanged)

### Phase 4: Verification (1-2h)
1. Build and release a test version (1.0.1)
2. Install 1.0.0 on MacBook manually
3. Push a 1.0.2 change to main
4. Verify the app prompts for / automatically installs the update
5. Verify `spctl --assess` passes on the distributed app

## Final Critiques
- **Skeptic:** "The CI/CD pipeline is the hard part — code signing in CI is notoriously fragile." **Response:** True, but the Mac Mini self-hosted runner already has the Developer ID certificate in its Keychain. This eliminates the hardest CI signing problem (exporting .p12, importing to temporary keychain). If we use SSH to the Mac Mini (current pattern), signing "just works" because the certificate is already there.
- **Pragmatist:** "Is 8-12 hours worth it for a single-user app?" **Response:** Yes. Andrew deploys frequently (daily pushes to main). Currently the macOS app requires manual rebuilding on the MacBook. Auto-update eliminates this friction permanently. It also establishes infrastructure that scales if the app ever has more users.
- **Long-Term Thinker:** "What happens in 6 months?" **Response:** Sparkle is low-maintenance once set up. The appcast updates automatically with each release. The only ongoing cost is bumping version numbers, which can be automated. If the app moves to the App Store later, Sparkle can be cleanly removed (it's a single package dependency + a few lines of code).

## Open Questions
1. **Self-hosted runner vs SSH:** Should the Mac Mini be registered as a proper GitHub Actions self-hosted runner (cleaner workflow YAML, native step support) or continue using the current SSH-based approach (proven, working)? Self-hosted runner is recommended for the macOS build workflow.
2. **Version bumping:** Manual (edit `project.yml` before push) or automated (CI reads git tag, injects version)? Git-tag-based automation is cleaner long-term.
3. **Update frequency:** Should every push to `main` trigger a release, or only tagged commits? Recommend tagged commits (e.g., `v1.0.1`) to avoid update fatigue.
4. **Appcast hosting:** Separate `hestia-releases` repo with GitHub Pages, or `gh-pages` branch on the main `hestia` repo? Separate repo is cleaner (no noise in main repo history).
