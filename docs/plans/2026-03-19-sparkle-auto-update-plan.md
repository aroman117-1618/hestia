# macOS Auto-Update (Sparkle 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a version tag is pushed to GitHub, CI/CD builds, signs, notarizes, and publishes the macOS app — the running app on Andrew's MacBook auto-updates.

**Architecture:** Sparkle 2 via SPM checks an appcast.xml hosted on GitHub Pages. Tagged commits trigger a GitHub Actions workflow that archives, code-signs (Developer ID), notarizes (Apple), signs with EdDSA (Sparkle), and publishes to GitHub Releases + appcast. Non-sandboxed app simplifies integration.

**Tech Stack:** Sparkle 2 (SPM), GitHub Actions, GitHub Pages, Apple notarytool, xcodegen

**References:**
- Discovery: `docs/discoveries/macos-auto-update-sparkle-2026-03-19.md`
- project.yml: `HestiaApp/project.yml`
- AppDelegate: `HestiaApp/macOS/AppDelegate.swift`
- Current CI/CD: `.github/workflows/deploy.yml`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `.github/workflows/release-macos.yml` | Build/sign/notarize/appcast workflow triggered by version tags |
| `HestiaApp/ExportOptions.plist` | Xcode archive export settings for Developer ID distribution |

### Modified Files
| File | Changes |
|------|---------|
| `HestiaApp/project.yml` | Add Sparkle SPM dependency to HestiaWorkspace target |
| `HestiaApp/macOS/Info.plist` | Add `SUPublicEDKey` and `SUFeedURL` keys |
| `HestiaApp/macOS/AppDelegate.swift` | Import Sparkle, init `SPUStandardUpdaterController`, add "Check for Updates" menu item |

---

## Task 1: Generate EdDSA Keypair + Store Secrets (~15 min)

**Requires Andrew's involvement** — GitHub Secrets access needed.

- [ ] **Step 1: Generate Sparkle EdDSA keypair on Mac Mini**

```bash
ssh andrewroman117@hestia-3.local 'cd /tmp && curl -sL https://github.com/sparkle-project/Sparkle/releases/download/2.6.0/Sparkle-2.6.0.tar.bz2 | tar xj && ./Sparkle-2.6.0/bin/generate_keys'
```

Save both keys — public key goes in Info.plist, private key goes in GitHub Secrets.

- [ ] **Step 2: Store private key in GitHub Secrets**

```bash
# Andrew: Go to github.com/aroman117-1618/hestia → Settings → Secrets → Actions
# Create: SPARKLE_PRIVATE_KEY = <private key from step 1>
```

- [ ] **Step 3: Store Apple notarization credentials in GitHub Secrets**

```bash
# Create: AC_USERNAME = <Apple ID email>
# Create: AC_PASSWORD = <app-specific password from appleid.apple.com>
# Create: AC_TEAM_ID = 563968AM8L
```

---

## Task 2: Add Sparkle to project.yml (~10 min)

**Files:**
- Modify: `HestiaApp/project.yml`

- [ ] **Step 1: Add Sparkle package**

In `packages:` section (after HestiaShared), add:
```yaml
  Sparkle:
    url: https://github.com/sparkle-project/Sparkle
    from: "2.6.0"
```

- [ ] **Step 2: Add dependency to HestiaWorkspace target**

In `targets: HestiaWorkspace: dependencies:`, add:
```yaml
      - package: Sparkle
```

- [ ] **Step 3: Regenerate and build**

```bash
cd HestiaApp && xcodegen generate && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | grep -E "error:|BUILD"
```

- [ ] **Step 4: Commit** — `git commit -am "chore: add Sparkle 2 SPM dependency"`

---

## Task 3: Add Sparkle keys to Info.plist (~5 min)

**Files:**
- Modify: `HestiaApp/macOS/Info.plist`

- [ ] **Step 1: Add SUPublicEDKey and SUFeedURL**

After the existing plist entries, add:
```xml
<key>SUPublicEDKey</key>
<string>PUBLIC_KEY_FROM_TASK_1</string>
<key>SUFeedURL</key>
<string>https://aroman117-1618.github.io/hestia/appcast.xml</string>
```

- [ ] **Step 2: Commit** — `git commit -am "feat: add Sparkle public key + feed URL to Info.plist"`

---

## Task 4: Wire Sparkle into AppDelegate (~20 min)

**Files:**
- Modify: `HestiaApp/macOS/AppDelegate.swift`

- [ ] **Step 1: Add Sparkle import and updater controller**

At top of file, add:
```swift
import Sparkle
```

In the `AppDelegate` class, add property:
```swift
private var updaterController: SPUStandardUpdaterController!
```

- [ ] **Step 2: Initialize in applicationDidFinishLaunching**

After `APIClient.configure(...)` (or near the end of the method), add:
```swift
updaterController = SPUStandardUpdaterController(
    startingUpdater: true,
    updaterDelegate: nil,
    userDriverDelegate: nil
)
```

- [ ] **Step 3: Add "Check for Updates..." menu item**

In `buildMainMenu()`, in the app menu section (after "About Hestia"), add:
```swift
appMenu.addItem(NSMenuItem.separator())
let checkForUpdatesItem = NSMenuItem(
    title: "Check for Updates...",
    action: #selector(checkForUpdates(_:)),
    keyEquivalent: ""
)
checkForUpdatesItem.target = self
appMenu.addItem(checkForUpdatesItem)
```

- [ ] **Step 4: Add action method**

```swift
@objc private func checkForUpdates(_ sender: Any?) {
    updaterController.checkForUpdates(sender)
}
```

- [ ] **Step 5: Build and verify**

```bash
cd HestiaApp && xcodebuild -scheme HestiaWorkspace -destination 'platform=macOS' build CODE_SIGNING_ALLOWED=NO 2>&1 | grep -E "error:|BUILD"
```

- [ ] **Step 6: Commit** — `git commit -am "feat: wire Sparkle updater into AppDelegate + Check for Updates menu"`

---

## Task 5: Create ExportOptions.plist (~5 min)

**Files:**
- Create: `HestiaApp/ExportOptions.plist`

- [ ] **Step 1: Create export options**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>method</key>
    <string>developer-id</string>
    <key>signingStyle</key>
    <string>automatic</string>
    <key>stripSwiftSymbols</key>
    <true/>
    <key>teamID</key>
    <string>563968AM8L</string>
</dict>
</plist>
```

- [ ] **Step 2: Commit** — `git commit -am "chore: add ExportOptions.plist for Developer ID distribution"`

---

## Task 6: Create GitHub Actions Release Workflow (~60 min)

**Files:**
- Create: `.github/workflows/release-macos.yml`

- [ ] **Step 1: Create workflow file**

```yaml
name: macOS Release

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:
    inputs:
      version:
        description: 'Version (e.g., 1.0.1)'
        required: true

concurrency:
  group: release-macos
  cancel-in-progress: false

jobs:
  build-and-release:
    runs-on: macos-15
    timeout-minutes: 45

    steps:
      - uses: actions/checkout@v4

      - name: Extract version
        id: version
        run: |
          if [ -n "${{ inputs.version }}" ]; then
            echo "version=${{ inputs.version }}" >> $GITHUB_OUTPUT
          else
            echo "version=${GITHUB_REF#refs/tags/v}" >> $GITHUB_OUTPUT
          fi

      - name: Install xcodegen
        run: brew install xcodegen

      - name: Generate Xcode project
        run: cd HestiaApp && xcodegen generate

      - name: Build and archive
        run: |
          cd HestiaApp
          xcodebuild archive \
            -scheme HestiaWorkspace \
            -archivePath build/Hestia.xcarchive \
            -configuration Release \
            CODE_SIGN_IDENTITY="Developer ID Application" \
            DEVELOPMENT_TEAM=563968AM8L

      - name: Export archive
        run: |
          xcodebuild -exportArchive \
            -archivePath HestiaApp/build/Hestia.xcarchive \
            -exportPath HestiaApp/build/export \
            -exportOptionsPlist HestiaApp/ExportOptions.plist

      - name: Notarize
        env:
          AC_USERNAME: ${{ secrets.AC_USERNAME }}
          AC_PASSWORD: ${{ secrets.AC_PASSWORD }}
          AC_TEAM_ID: ${{ secrets.AC_TEAM_ID }}
        run: |
          cd HestiaApp/build/export
          ditto -c -k --keepParent "HestiaWorkspace.app" Hestia.zip
          xcrun notarytool submit Hestia.zip \
            --apple-id "$AC_USERNAME" \
            --password "$AC_PASSWORD" \
            --team-id "$AC_TEAM_ID" \
            --wait --timeout 600
          xcrun stapler staple "HestiaWorkspace.app"

      - name: Package with ditto (preserves signatures)
        run: |
          cd HestiaApp/build/export
          ditto -c -k --keepParent "HestiaWorkspace.app" \
            "../../../Hestia-${{ steps.version.outputs.version }}.zip"

      - name: Download Sparkle tools
        run: |
          curl -sL https://github.com/sparkle-project/Sparkle/releases/download/2.6.0/Sparkle-2.6.0.tar.bz2 | tar xj

      - name: Sign with EdDSA
        env:
          SPARKLE_KEY: ${{ secrets.SPARKLE_PRIVATE_KEY }}
        run: |
          SIGNATURE=$(echo "$SPARKLE_KEY" | ./Sparkle-2.6.0/bin/sign_update \
            "Hestia-${{ steps.version.outputs.version }}.zip" \
            --ed-key-file /dev/stdin 2>&1 | grep 'edSignature=' | cut -d'"' -f2)
          echo "SIGNATURE=$SIGNATURE" >> $GITHUB_ENV
          SIZE=$(stat -f%z "Hestia-${{ steps.version.outputs.version }}.zip")
          echo "SIZE=$SIZE" >> $GITHUB_ENV

      - name: Create GitHub Release
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh release create "v${{ steps.version.outputs.version }}" \
            "Hestia-${{ steps.version.outputs.version }}.zip" \
            --title "Hestia v${{ steps.version.outputs.version }}" \
            --generate-notes

      - name: Update appcast.xml
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          VERSION="${{ steps.version.outputs.version }}"
          DOWNLOAD_URL="https://github.com/${{ github.repository }}/releases/download/v${VERSION}/Hestia-${VERSION}.zip"

          cat > /tmp/appcast.xml << APPCAST_EOF
          <?xml version="1.0" encoding="utf-8"?>
          <rss version="2.0" xmlns:sparkle="http://www.andymatuschak.org/xml-namespaces/sparkle">
            <channel>
              <title>Hestia Updates</title>
              <item>
                <title>Version ${VERSION}</title>
                <sparkle:version>${VERSION}</sparkle:version>
                <sparkle:shortVersionString>${VERSION}</sparkle:shortVersionString>
                <pubDate>$(date -R)</pubDate>
                <enclosure
                  url="${DOWNLOAD_URL}"
                  sparkle:edSignature="${SIGNATURE}"
                  length="${SIZE}"
                  type="application/octet-stream" />
              </item>
            </channel>
          </rss>
          APPCAST_EOF

      - name: Deploy appcast to gh-pages
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git fetch origin gh-pages || git checkout --orphan gh-pages
          git checkout gh-pages || git checkout --orphan gh-pages
          cp /tmp/appcast.xml appcast.xml
          git add appcast.xml
          git commit -m "Update appcast for v${{ steps.version.outputs.version }}" || true
          git push origin gh-pages
```

- [ ] **Step 2: Create gh-pages branch**

```bash
git checkout --orphan gh-pages
echo "# Hestia Releases" > README.md
echo '<rss version="2.0"><channel><title>Hestia Updates</title></channel></rss>' > appcast.xml
git add README.md appcast.xml
git commit -m "init: gh-pages for Sparkle appcast"
git push origin gh-pages
git checkout main
```

- [ ] **Step 3: Enable GitHub Pages** — Settings → Pages → Source: gh-pages branch, / (root)

- [ ] **Step 4: Commit workflow** — `git commit -am "feat: GitHub Actions release workflow for macOS auto-update"`

---

## Task 7: First Release Test (~30 min)

- [ ] **Step 1: Bump version**

Edit `HestiaApp/project.yml`:
```yaml
MARKETING_VERSION: "1.0.1"
CURRENT_PROJECT_VERSION: "2"
```

- [ ] **Step 2: Commit, tag, push**

```bash
git commit -am "bump: version 1.0.1"
git tag v1.0.1
git push && git push --tags
```

- [ ] **Step 3: Monitor workflow** — GitHub Actions → release-macos → watch for green

- [ ] **Step 4: Verify appcast** — `curl https://aroman117-1618.github.io/hestia/appcast.xml`

- [ ] **Step 5: Test update in app** — Launch Hestia → Menu → "Check for Updates..." → should find v1.0.1

- [ ] **Step 6: Verify signature** — `spctl --assess -vvv /Applications/HestiaWorkspace.app`

---

## What's NOT in Scope
- Delta updates (Sparkle supports them but adds complexity — full ZIP is fine for <50MB app)
- Release notes in appcast (can add later with `<description>` in appcast XML)
- Automatic version bumping from git tags (manual for now, automate later if tedious)
- iOS auto-update (App Store handles this)
