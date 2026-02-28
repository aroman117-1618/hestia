# Hestia Enhancement Development Prompt

Copy this entire prompt into Claude Code to continue development independently.

---

## Project Context

You are working on **Hestia**, a locally-hosted personal AI assistant running on a Mac Mini M1. The project is at **Phase 6b complete** with a fully functional Python backend (47 REST API endpoints), native SwiftUI iOS app, and local Qwen 2.5 7B inference via Ollama.

**Key Files to Read First:**
- `CLAUDE.md` - Full project context, architecture, session log
- `docs/phase-6-gaps.md` - Enhancement roadmap and current status
- `docs/ui-requirements.md` - UI specifications including enhancement phases
- `docs/api-contract.md` - All 47 API endpoints

---

## Current Enhancement Roadmap

Work through these phases in order. Each phase should be **fully tested** before moving to the next.

### Phase 1: Critical Bug Fixes ✅ COMPLETE

All Phase 1 bugs have been fixed:
- Face ID lock state (`LockScreenView.swift`)
- Apple Notes -1728 error (`hestia-notes-cli/main.swift`)
- Tool call JSON display (`handler.py`, `MessageBubble.swift`)

**Verification needed:** Rebuild iOS app in Xcode and test on physical device.

---

### Phase 2: UI Quick Wins (START HERE)

**Goal:** Clean up the UI per user feedback.

| Task | File | What to Do |
|------|------|------------|
| Remove byline | `HestiaApp/Shared/Views/Chat/ChatView.swift` | Remove any byline/tagline text from the chat view |
| Remove Default Mode | `HestiaApp/Shared/Views/Settings/SettingsView.swift` | Remove the "Default Mode" picker from Settings |
| Move Memory to Command Center | Multiple files | Move Memory review from Settings to Command Center as new tab |

**Implementation Steps:**

1. **Remove byline from ChatView:**
   ```bash
   # Find any byline text in ChatView
   grep -r "byline\|tagline\|subtitle" HestiaApp/Shared/Views/Chat/
   ```
   Remove any subtitle/byline text elements.

2. **Remove Default Mode from Settings:**
   - Open `SettingsView.swift`
   - Find and remove the "Default Mode" Picker component
   - Remove any associated `@AppStorage` or state variables

3. **Move Memory to Command Center:**
   - Add new "Memory" tab to `CommandCenterView.swift` TabView
   - Move `MemoryReviewView` to CommandCenter
   - Remove Memory section from SettingsView
   - Update navigation flow

**Verify:** Build and run in Xcode, confirm all changes work.

---

### Phase 3: Lottie Animations + Loading Bylines

**Goal:** Replace the standard spinner with a Lottie animation and rotating snarky bylines.

**Dependencies:**
```swift
// Add to Package.swift or via Xcode SPM
.package(url: "https://github.com/airbnb/lottie-ios.git", from: "4.0.0")
```

**Implementation:**

1. **Add Lottie Package:**
   - In Xcode: File → Add Package Dependencies
   - URL: `https://github.com/airbnb/lottie-ios`
   - Add to HestiaApp target

2. **Create Loading Animation View:**
   ```swift
   // HestiaApp/Shared/Views/Common/LoadingAnimationView.swift
   import SwiftUI
   import Lottie

   struct LoadingAnimationView: View {
       @State private var currentByline = 0

       let bylines = [
           "Consulting the oracle...",
           "Summoning the wisdom of the ancients...",
           "Brewing some digital coffee...",
           "Teaching hamsters to run faster...",
           "Convincing the AI it's not a Monday...",
           "Searching through the void...",
           "Asking the magic 8-ball...",
           "Channeling the spirit of Clippy...",
           "Performing arcane calculations...",
           "Negotiating with the cloud spirits..."
       ]

       let timer = Timer.publish(every: 2.5, on: .main, in: .common).autoconnect()

       var body: some View {
           VStack(spacing: Spacing.md) {
               LottieView(animation: .named("loading"))
                   .looping()
                   .frame(width: 80, height: 80)

               Text(bylines[currentByline])
                   .font(.messageBody)
                   .foregroundColor(.white.opacity(0.7))
                   .animation(.easeInOut, value: currentByline)
           }
           .onReceive(timer) { _ in
               withAnimation {
                   currentByline = Int.random(in: 0..<bylines.count)
               }
           }
       }
   }
   ```

3. **Create/Find Lottie Animation:**
   - Download a suitable loading animation from LottieFiles.com
   - Save as `HestiaApp/Shared/Resources/loading.json`
   - Common search terms: "loading", "AI thinking", "processing"

4. **Replace Spinner in MessageBubble:**
   - Update `MessageBubble.swift` to use `LoadingAnimationView` instead of `ProgressView`
   - Also update any other loading states in ChatView

5. **Replace Spinner in ChatView:**
   - Find where `ProgressView` is used for loading states
   - Replace with `LoadingAnimationView()`

**Verify:** Build and test - should see Lottie animation with rotating bylines during inference.

---

### Phase 4: Settings Integrations Section

**Goal:** Add a new "Integrations" section to Settings showing all available data sources.

**Implementation:**

1. **Create IntegrationsView:**
   ```swift
   // HestiaApp/Shared/Views/Settings/IntegrationsView.swift
   struct IntegrationsView: View {
       var body: some View {
           List {
               Section("Native Integrations") {
                   IntegrationRow(name: "Calendar", icon: "calendar", status: .connected)
                   IntegrationRow(name: "Reminders", icon: "checklist", status: .connected)
                   IntegrationRow(name: "Notes", icon: "note.text", status: .connected)
                   IntegrationRow(name: "Mail", icon: "envelope", status: .connected)
               }

               Section("API Integrations") {
                   IntegrationRow(name: "Weather", icon: "cloud.sun", status: .connected)
                   IntegrationRow(name: "Stocks", icon: "chart.line.uptrend.xyaxis", status: .planned)
               }

               Section("Future MCP Resources") {
                   IntegrationRow(name: "More coming soon...", icon: "plus.circle", status: .planned)
               }
           }
           .navigationTitle("Integrations")
       }
   }

   struct IntegrationRow: View {
       let name: String
       let icon: String
       let status: IntegrationStatus

       enum IntegrationStatus {
           case connected, disconnected, planned

           var color: Color {
               switch self {
               case .connected: return .green
               case .disconnected: return .red
               case .planned: return .gray
               }
           }

           var label: String {
               switch self {
               case .connected: return "Connected"
               case .disconnected: return "Disconnected"
               case .planned: return "Coming Soon"
               }
           }
       }

       var body: some View {
           HStack {
               Image(systemName: icon)
                   .foregroundColor(.accentColor)
                   .frame(width: 24)
               Text(name)
               Spacer()
               Text(status.label)
                   .font(.caption)
                   .foregroundColor(status.color)
               Circle()
                   .fill(status.color)
                   .frame(width: 8, height: 8)
           }
       }
   }
   ```

2. **Add to SettingsView:**
   - Add NavigationLink to IntegrationsView in the Settings sections

**Verify:** Build and navigate to Settings → Integrations.

---

### Phase 5: Neural Net Graph Visualization

**Goal:** Add a force-directed graph showing memory tags and conversation clusters to Command Center.

**Dependencies:**
- Research Swift graph libraries: Grape, SwiftGraph, or custom SwiftUI implementation

**Implementation Approach:**

1. **Research Graph Libraries:**
   ```bash
   # Check available Swift graph visualization libraries
   # Options:
   # - Grape: https://github.com/nicklockwood/Grape (simple force-directed)
   # - Custom SwiftUI with drag gestures
   ```

2. **Data Model:**
   ```swift
   struct MemoryNode: Identifiable {
       let id: String
       let label: String  // Memory tag name
       let size: CGFloat  // Based on frequency
       let color: Color   // Based on category
   }

   struct MemoryEdge: Identifiable {
       let id: String
       let from: String
       let to: String
       let weight: CGFloat  // Connection strength
   }
   ```

3. **Create Neural Net View:**
   - New tab in CommandCenterView
   - Fetch memory tags from `/v1/memory/search` or new endpoint
   - Render as interactive force-directed graph
   - Tap nodes to see related memories

4. **Backend Support (if needed):**
   - May need new endpoint: `GET /v1/memory/graph`
   - Returns nodes (tags) and edges (co-occurrence)

**Note:** This is the most complex phase. Consider breaking into sub-tasks.

---

## Development Commands

```bash
# Start the API server
cd ~/hestia
source .venv/bin/activate
python -m hestia.api.server

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_orchestration.py -v

# Rebuild Swift CLI tools (on Mac Mini)
cd ~/hestia/hestia-cli-tools/hestia-notes-cli
swift build -c release
cp .build/release/hestia-notes-cli ~/.hestia/bin/

# iOS app - use Xcode
# 1. Open HestiaApp.xcodeproj
# 2. Select iPhone target
# 3. Cmd+R to build and run
```

---

## Key Patterns to Follow

### SwiftUI State Management
- Use `@EnvironmentObject` for shared services (AuthService, HestiaClient)
- Use `@StateObject` for view-owned state
- Use `@State` for local UI state

### Error Handling
- Always show user-friendly error messages
- Log errors with context for debugging
- Use `HestiaError` enum for typed errors

### API Calls
- Use `async/await` with `HestiaClient`
- Handle loading and error states in UI
- Cache where appropriate

### Testing
- Write tests for new functionality
- Run existing tests before committing
- Test on physical device when possible

---

## Files Summary

| Category | Key Files |
|----------|-----------|
| Backend Entry | `hestia/api/server.py` |
| Orchestration | `hestia/orchestration/handler.py` |
| iOS Entry | `HestiaApp/Shared/App/HestiaApp.swift` |
| Chat UI | `HestiaApp/Shared/Views/Chat/ChatView.swift` |
| Settings | `HestiaApp/Shared/Views/Settings/SettingsView.swift` |
| Command Center | `HestiaApp/Shared/Views/CommandCenter/CommandCenterView.swift` |
| Auth | `HestiaApp/Shared/Services/AuthService.swift` |
| Design System | `HestiaApp/Shared/DesignSystem/` |

---

## Success Criteria

Each phase is complete when:
1. All code changes implemented
2. No build errors or warnings
3. Tests pass (if applicable)
4. Tested on physical device (iOS)
5. Documentation updated

---

## Questions to Ask Yourself

Before starting each task:
1. What files need to be modified?
2. Are there existing patterns to follow?
3. What could break?
4. How will I test this?

---

**Start with Phase 2: UI Quick Wins.** It's the quickest win and sets up for the more complex phases.
