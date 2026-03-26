---
name: ship-it
description: Use when the user wants to release a new version of the macOS app, iOS app, or both. Supports platform-specific releases via tag prefixes (ios-v*, mac-v*, v* for both).
---

# /ship-it — Release an App Update

Bumps the version in `HestiaApp/project.yml`, commits, tags, and pushes. Tag prefix determines which platform(s) to release:

| Tag | Triggers |
|-----|----------|
| `ios-vX.Y.Z` | iOS only (TestFlight via `release-ios.yml`) |
| `mac-vX.Y.Z` | macOS only (Sparkle via `release-macos.yml`) |
| `vX.Y.Z` | Both platforms |

## Usage

```
/ship-it ios              # iOS-only, auto-increment patch
/ship-it ios 1.10.0       # iOS-only, explicit version
/ship-it mac              # macOS-only, auto-increment patch
/ship-it mac minor        # macOS-only, minor bump
/ship-it                  # Both platforms, auto-increment patch
/ship-it 2.0.0            # Both platforms, explicit version
```

First argument (optional): platform — `ios`, `mac`, or omit for both.
Second argument (optional): version — `major`, `minor`, explicit version, or omit for patch increment.

## Steps

1. **Read current version** from `HestiaApp/project.yml` (`MARKETING_VERSION` and `CURRENT_PROJECT_VERSION`)

2. **Compute new version:**
   - No version arg: increment patch (1.0.1 → 1.0.2)
   - `major`: increment major, reset minor+patch (1.2.3 → 2.0.0)
   - `minor`: increment minor, reset patch (1.2.3 → 1.3.0)
   - Explicit version (e.g., `1.1.0`): use as-is

3. **Always increment `CURRENT_PROJECT_VERSION`** (build number) by 1

4. **Update `HestiaApp/project.yml`:**
   - `MARKETING_VERSION: "X.Y.Z"`
   - `CURRENT_PROJECT_VERSION: "N"`

5. **Regenerate Xcode project:** `cd HestiaApp && xcodegen generate`

6. **Build verify:**
   - iOS: `xcodebuild -scheme HestiaApp -destination 'platform=iOS Simulator,name=iPhone 17 Pro' build`
   - macOS: `xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO`
   - Both: verify both builds
   - Abort if any build fails

7. **Commit:** `git commit -am "bump: version X.Y.Z (build N)"`

8. **Tag based on platform:**
   - iOS only: `git tag ios-vX.Y.Z`
   - macOS only: `git tag mac-vX.Y.Z`
   - Both: `git tag vX.Y.Z`

9. **Push:** `git push && git push --tags`

9.5. **Sync Notion:** `source .venv/bin/activate && python scripts/sync-notion.py sync-all --incremental 2>&1`

10. **Report:** "Shipped [platform] v{X.Y.Z}. Monitor at: https://github.com/aroman117-1618/hestia/actions"

## Do NOT

- Push without verifying the build compiles
- Skip the xcodegen regeneration (Info.plist version comes from project.yml)
- Create a tag that already exists (check first with `git tag -l`)
- Amend a previous commit — always create a new one
- Use `v*` tag for a single-platform change — use `ios-v*` or `mac-v*`
