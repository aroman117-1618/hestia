# UI Phase 3: Lottie Animations + Settings Restructure

**Status**: PLANNED (reviewed, revised per audit feedback)
**Estimated effort**: ~3.5 hours across 2-3 sessions
**Date**: 2026-02-15

---

## Pre-Session Checklist (Andrew)

Before the implementation session, Andrew needs to:

1. **Select Lottie animation files** from [LottieFiles.com](https://lottiefiles.com):
   - Search "brain", "AI", "neural network", "thinking"
   - Download 1-2 `.json` files (target < 100KB each)
   - Verify license allows commercial use (check "Free for commercial use" tag)
   - Place files in `HestiaApp/Shared/Resources/Animations/` (create directory)
2. **Decide calendar preferences**:
   - Include all-day events? (currently excluded)
   - Keep "aLonati" calendar exclusion?
   - Extend look-ahead beyond 7 days?

---

## Phase 3A: Foundation (~1.5 hours)

### Task 1: Add Lottie-iOS Package (15 min)

**File**: `HestiaApp/project.yml`

Add SPM dependency via `project.yml` (NOT Xcode dialog — xcodegen wipes Xcode-added SPM refs on regeneration):

```yaml
packages:
  Lottie:
    url: https://github.com/airbnb/lottie-ios
    majorVersion: 4.0.0

targets:
  HestiaApp:
    # ... existing config ...
    dependencies:
      - package: Lottie
```

Then run `xcodegen generate` to update `.xcodeproj`.

**Why not Xcode SPM dialog**: `xcodegen generate` regenerates the project file from `project.yml`. Any SPM packages added via Xcode's GUI live only in `.xcodeproj` and get wiped on regeneration. The `packages:` key is the only durable way.

### Task 2: Settings Restructure (60 min)

**File**: `HestiaApp/Shared/Views/Settings/SettingsView.swift`

Current 7 sections → new 4 sections:

```
Settings (NavigationView)
├── .toolbar: Profile icon (top-right) → UserProfileView
├── Section: System Status (expanded)
│   ├── Overall health + refresh button
│   ├── Inference / Memory / Tools status dots
│   └── Version + Build number (moved from About)
├── Section: Security (kept separate — reviewer recommendation)
│   ├── Biometric type + status (FIXED — see below)
│   ├── Auto-Lock picker
│   └── Lock Now button
├── Section: Agent Profiles
│   ├── Tia (Primary)
│   ├── Mira
│   └── Olly
├── Section: Resources (renamed from Cloud Providers)
│   └── NavigationLink → ResourcesView
└── Section: Advanced
    └── Unregister Device
```

**Changes from current**:
- **Remove**: User Profile section (move to toolbar icon)
- **Remove**: About section (version moves into System Status)
- **Keep**: Security as its own section (reviewer: merging creates 7-row megasection)
- **Rename**: "Cloud Providers" → "Resources"
- **Add**: Toolbar profile icon

**Toolbar implementation**:
```swift
.toolbar {
    ToolbarItem(placement: .navigationBarTrailing) {
        NavigationLink(destination: UserProfileView()) {
            // User avatar or placeholder
            Circle()
                .fill(Color.white.opacity(0.2))
                .frame(width: 32, height: 32)
                .overlay(
                    Text("A")
                        .font(.system(size: 14, weight: .bold))
                        .foregroundColor(.white)
                )
        }
    }
}
```

### Task 3: Fix Biometric Display (10 min)

**File**: `HestiaApp/Shared/Views/Settings/SettingsView.swift` (Security section, lines 320-335)

**Bug**: When `biometricType == .none` (simulator, no hardware, or not enrolled), displays "None - Enabled" — contradictory.

**Fix**:
```swift
HStack {
    Image(systemName: viewModel.biometricType.iconName)
        .foregroundColor(viewModel.biometricType == .none ? .warningYellow : .white)

    Text(viewModel.biometricType == .none ?
         "No Biometrics Available" :
         viewModel.biometricType.displayName)
        .foregroundColor(.white)

    Spacer()

    if viewModel.biometricType != .none {
        Text("Enabled")
            .foregroundColor(.healthyGreen)
            .font(.caption)
    } else {
        Text("Unavailable")
            .foregroundColor(.warningYellow)
            .font(.caption)
    }
}
```

**Root cause**: `LAContext.biometryType` returns `.none` when:
- Device has no biometric hardware
- App lacks Face ID entitlement
- User hasn't enrolled biometrics
- Running in simulator

All cases should show warning state, not "Enabled".

### Task 4: Create ResourcesView Skeleton (45 min)

**New file**: `HestiaApp/Shared/Views/Settings/ResourcesView.swift`
**New file**: `HestiaApp/Shared/ViewModels/ResourcesViewModel.swift`

Tab-based view following MVVM pattern:

```swift
// ResourcesViewModel.swift
@MainActor
class ResourcesViewModel: ObservableObject {
    @Published var selectedTab: Tab = .llms

    enum Tab: String, CaseIterable {
        case llms = "LLMs"
        case integrations = "Integrations"
        case mcps = "MCPs"
    }
}

// ResourcesView.swift
struct ResourcesView: View {
    @StateObject private var viewModel = ResourcesViewModel()

    var body: some View {
        VStack(spacing: 0) {
            // Tab selector (same style as CommandCenter tabs)
            tabSelector

            // Content
            switch viewModel.selectedTab {
            case .llms:
                CloudSettingsView()  // Existing view, embedded here
            case .integrations:
                placeholderTab("Calendar, Reminders, Notes, Mail", "Coming in Phase 4")
            case .mcps:
                placeholderTab("Model Context Protocol", "Coming Soon")
            }
        }
        .navigationTitle("Resources")
    }
}
```

CloudSettingsView requires no changes — it's embedded directly in the LLMs tab.

---

## Phase 3B: Animations (~1.5 hours)

### Task 5: Create LottieWrapper Component (20 min)

**New file**: `HestiaApp/Shared/Views/Common/LottieAnimationView.swift`

UIViewRepresentable wrapper with accessibility support:

```swift
import Lottie
import SwiftUI

struct LottieAnimationView: UIViewRepresentable {
    let animationName: String
    var loopMode: LottieLoopMode = .loop
    var speed: CGFloat = 1.0

    @Environment(\.accessibilityReduceMotion) var reduceMotion

    func makeUIView(context: Context) -> LottieAnimationViewBase {
        let view = Lottie.LottieAnimationView(name: animationName)
        view.loopMode = loopMode
        view.animationSpeed = speed
        view.contentMode = .scaleAspectFit
        if !reduceMotion {
            view.play()
        }
        return view
    }

    func updateUIView(_ uiView: LottieAnimationViewBase, context: Context) {
        // Stop animation if reduce motion is enabled
        if reduceMotion {
            uiView.stop()
        }
    }
}
```

**Static fallback** for reduce-motion users: wrap in a conditional that shows `Image(systemName: "brain")` instead.

### Task 6: AuthView Lottie Integration (30 min)

**File**: `HestiaApp/Shared/Views/Auth/AuthView.swift`

Changes:

| Element | Current (line) | Change |
|---------|----------------|--------|
| Avatar | Static "H" circle (66-74) | Replace with `LottieAnimationView(animationName: "brain")` |
| First-time byline | "Your personal AI assistant" (86) | Remove entirely |
| Returning byline | "Welcome back, Boss." (85) | Keep as-is |
| CTA button | "Get Started" (125) | **Keep as "Get Started"** (reviewer: this is for unregistered devices, "Authenticate" is wrong) |
| Loading overlay | Static text (41) | Lottie animation + rotating snarky bylines |

**Snarky byline rotation** during loading:

```swift
// In AuthView or a new LoadingAnimationView
@State private var bylineIndex = 0
private let bylines = [
    "Authenticating...",
    "Debating...",
    "Grabbing groceries...",
    "Scrolling Instagram...",
    "Consulting the council...",
    "Warming up neurons...",
]

// Use TimelineView for automatic cleanup (no manual timer invalidation needed)
TimelineView(.periodic(from: .now, by: 2.5)) { timeline in
    VStack(spacing: Spacing.md) {
        LottieAnimationView(animationName: "brain")
            .frame(width: 120, height: 120)

        Text(bylines[bylineIndex % bylines.count])
            .font(.subheading)
            .foregroundColor(.white.opacity(0.8))
            .animation(.easeInOut, value: bylineIndex)
            .onChange(of: timeline.date) { _ in
                bylineIndex += 1
            }
    }
}
```

**Why TimelineView over Timer**: SwiftUI manages the lifecycle automatically — no need for manual `Timer.invalidate()` on view disappear. Available iOS 15+, well within our target.

**Note**: Keep existing `LoadingBubble` (bouncing dots) for chat messages. Lottie is overkill there — reviewer recommended limiting Lottie to high-value, once-per-session views like AuthView.

---

## Phase 3C: Polish (~30 min)

### Task 7: Calendar Adjustments (10 min)

**File**: `HestiaApp/Shared/Services/CalendarService.swift`

Apply Andrew's decisions from pre-session checklist:
- `excludeAllDay` parameter default (line 82)
- `excludedCalendars` array (line 32)
- Look-ahead window: `byAdding: .day, value: N` (line 94)

**Context**: The "snarky phrases" in Command Center are the intended empty state (`CalendarEmptyStateView`). They appear when calendar access is granted but no events exist in the next 7 days (excluding all-day events). This is working correctly — not a bug.

### Task 8: Testing Pass (20 min)

- Build in Xcode, verify no compilation errors
- Run on simulator: Settings navigation, profile icon, Resources tabs
- Run on device: biometric display (should show "Face ID - Enabled", not "None")
- Verify Lottie animations play on AuthView loading
- Verify reduce-motion accessibility fallback
- Test CloudSettingsView still works inside ResourcesView's LLMs tab

---

## Files Summary

| File | Action | Task |
|------|--------|------|
| `project.yml` | Modify (add `packages:` key) | 1 |
| `SettingsView.swift` | Modify (restructure, toolbar, biometric fix) | 2, 3 |
| `ResourcesView.swift` | **New** | 4 |
| `ResourcesViewModel.swift` | **New** | 4 |
| `LottieAnimationView.swift` | **New** | 5 |
| `AuthView.swift` | Modify (avatar, byline, loading) | 6 |
| `CalendarService.swift` | Modify (parameters) | 7 |
| `CloudSettingsView.swift` | No changes (embedded in ResourcesView) | — |

---

## Deferred

| Item | Target Phase | Notes |
|------|-------------|-------|
| Neural Net graph (Grape library) | Phase 5 | Limited adoption, defer until memory graph API exists. Use Lottie "neural net" animation as placeholder |
| Integrations tab content | Phase 4 | Calendar, Reminders, Notes, Mail settings |
| MCPs tab content | Future | Model Context Protocol server management |
| Chat loading Lottie | Future | Current bouncing dots are lightweight and fine |

---

## Reviewer Feedback Incorporated

| Reviewer Finding | Resolution |
|-----------------|------------|
| CRITICAL: SPM + xcodegen conflict | Use `project.yml` `packages:` key, not Xcode dialog |
| CRITICAL: CTA "Authenticate" wrong | Keep "Get Started" for unregistered devices |
| CRITICAL: Biometric fix incomplete | Handle all `.none` cases with warning state |
| CRITICAL: Lottie files not sourced | Added pre-session checklist for Andrew |
| WARNING: Timer cleanup | Use `TimelineView` instead of manual `Timer` |
| WARNING: Missing ResourcesViewModel | Added as separate file |
| WARNING: iOS 26.0 target | Kept as-is (intentional per SpeechAnalyzer bump) |
| SUGGESTION: Keep Security separate | Kept as own section, not merged into System Status |
| SUGGESTION: Accessibility | Added `@Environment(\.accessibilityReduceMotion)` support |
| SUGGESTION: Task ordering | Reordered: Settings restructure before AuthView Lottie |
