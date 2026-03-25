---
name: ship-it
description: Use when the user wants to release a new version. Bumps version, commits, tags, and pushes — triggering GitHub Actions workflows for both macOS (Sparkle auto-update) and iOS (TestFlight).
---

# /ship-it — Release an App Update (macOS + iOS)

Bumps the version in `HestiaApp/project.yml`, commits, tags, and pushes. A tag push triggers **both** release workflows:
- **`release-macos.yml`** — archive, sign, notarize, Sparkle sign, GitHub Release, appcast update
- **`release-ios.yml`** — archive, export for App Store, upload to TestFlight via App Store Connect API

## Usage

```
/ship-it              # Auto-increment patch: 1.0.1 → 1.0.2
/ship-it 1.1.0        # Set explicit version
/ship-it major        # 1.0.2 → 2.0.0
/ship-it minor        # 1.0.2 → 1.1.0
```

## Steps

1. **Read current version** from `HestiaApp/project.yml` (`MARKETING_VERSION` and `CURRENT_PROJECT_VERSION`)

2. **Compute new version:**
   - No argument: increment patch (1.0.1 → 1.0.2)
   - `major`: increment major, reset minor+patch (1.2.3 → 2.0.0)
   - `minor`: increment minor, reset patch (1.2.3 → 1.3.0)
   - Explicit version (e.g., `1.1.0`): use as-is

3. **Always increment `CURRENT_PROJECT_VERSION`** (build number) by 1, regardless of marketing version

4. **Update `HestiaApp/project.yml`:**
   - `MARKETING_VERSION: "X.Y.Z"`
   - `CURRENT_PROJECT_VERSION: "N"`

5. **Regenerate Xcode project:** `cd HestiaApp && xcodegen generate`

6. **Build verify:** `xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO` — abort if build fails

7. **Commit:** `git commit -am "bump: version X.Y.Z (build N)"`

8. **Tag:** `git tag vX.Y.Z`

9. **Push:** `git push && git push --tags`

10. **Report:** "Shipped v{X.Y.Z}. Both workflows triggered — macOS (Sparkle) + iOS (TestFlight). Monitor at: https://github.com/aroman117-1618/hestia/actions"

## Do NOT

- Push without verifying the build compiles
- Skip the xcodegen regeneration (Info.plist version comes from project.yml)
- Create a tag that already exists (check first with `git tag -l "vX.Y.Z"`)
- Amend a previous commit — always create a new one
