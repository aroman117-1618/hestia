# HestiaApp

Native iOS/iPad SwiftUI app for Hestia - Your personal AI assistant.

## Requirements

- iOS 16.0+
- Xcode 15.0+
- Swift 5.9+

## Setup

### 1. Create Xcode Project

1. Open Xcode
2. File → New → Project
3. Select "App" under iOS
4. Configure:
   - Product Name: `HestiaApp`
   - Team: Your development team
   - Organization Identifier: `com.hestia`
   - Interface: SwiftUI
   - Language: Swift
5. Save to `/Users/andrewlonati/hestia/HestiaApp/`
6. Delete the default `ContentView.swift` and `HestiaAppApp.swift` files

### 2. Add Source Files

Drag the `Shared/` folder into your Xcode project, ensuring "Create folder references" is selected.

### 3. Add Volkhov Fonts

1. Download from [Google Fonts](https://fonts.google.com/specimen/Volkhov)
2. Add `Volkhov-Regular.ttf` and `Volkhov-Bold.ttf` to the project
3. Ensure they're added to the target
4. Fonts are already registered in `Info.plist`

### 4. Configure Signing

1. Select the project in the navigator
2. Select the target
3. Signing & Capabilities → Select your team
4. Update the Bundle Identifier if needed

### 5. Build & Run

Select your device or simulator and press ⌘R.

## Project Structure

```
HestiaApp/
├── Shared/
│   ├── App/
│   │   ├── HestiaApp.swift           # @main entry point
│   │   └── ContentView.swift         # Root navigation
│   ├── DesignSystem/
│   │   ├── Colors.swift              # Mode gradients, semantic colors
│   │   ├── Typography.swift          # Volkhov + SF Pro fonts
│   │   ├── Spacing.swift             # Layout constants
│   │   └── Animations.swift          # Custom animations
│   ├── Models/
│   │   ├── HestiaMode.swift          # Tia/Mira/Olly modes
│   │   ├── Message.swift             # Conversation messages
│   │   ├── Response.swift            # API responses
│   │   ├── MemoryChunk.swift         # Memory models (ADR-002)
│   │   ├── SystemHealth.swift        # Health status
│   │   └── HestiaError.swift         # Error types
│   ├── Services/
│   │   ├── Protocols/
│   │   │   └── HestiaClientProtocol.swift
│   │   ├── MockHestiaClient.swift    # Mock for development
│   │   ├── APIClient.swift           # Real API (Week 2+)
│   │   ├── AuthService.swift         # Face ID + tokens
│   │   └── NetworkMonitor.swift      # Connectivity
│   ├── ViewModels/
│   │   ├── ChatViewModel.swift
│   │   ├── CommandCenterViewModel.swift
│   │   ├── MemoryReviewViewModel.swift
│   │   ├── SettingsViewModel.swift
│   │   └── AuthViewModel.swift
│   ├── Views/
│   │   ├── Chat/
│   │   │   ├── ChatView.swift
│   │   │   └── Components/
│   │   ├── CommandCenter/
│   │   │   ├── CommandCenterView.swift
│   │   │   └── Widgets/
│   │   ├── Memory/
│   │   │   └── MemoryReviewView.swift
│   │   ├── Settings/
│   │   │   ├── SettingsView.swift
│   │   │   └── AgentCustomizationView.swift
│   │   ├── Auth/
│   │   │   ├── AuthView.swift
│   │   │   └── LockScreenView.swift
│   │   └── Common/
│   │       ├── ModeIndicator.swift
│   │       ├── GradientBackground.swift
│   │       ├── LoadingView.swift
│   │       └── ErrorView.swift
│   └── Utilities/
│       ├── Extensions/
│       └── Constants.swift
├── iOS/
│   ├── Info.plist
│   └── Assets.xcassets/
└── Tests/
```

## Features

### Chat Interface
- Mode-specific gradient backgrounds (Tia=Orange, Mira=Blue, Olly=Green)
- Typewriter text effect for responses
- Message bubbles with timestamps
- Loading indicators

### Command Center (iPad)
- Automation toggles
- Activity log
- System health status
- Next meeting widget

### Memory Review (ADR-002)
- Pending memory updates
- Approve/Reject actions
- Confidence scores
- Reviewer notes

### Settings
- Default mode selection
- Auto-lock timeout
- System health status
- Agent customization

### Security
- Face ID / Touch ID authentication
- Auto-lock on timeout
- Device registration

## Development

### Mock Data

The app uses `MockHestiaClient` by default, which returns canned responses. This allows UI development while the FastAPI backend is built.

### Connecting to Real API

1. Start the Hestia backend: `python -m hestia.api.server`
2. Replace `MockHestiaClient()` with `APIClient()` in ViewModels
3. Ensure device is on the same network as the Mac Mini

### Testing

```bash
# Run unit tests
⌘U in Xcode

# Run UI tests
Select UI Tests scheme and run
```

## Design Decisions

- **iOS 16+**: Uses `ObservableObject` + `@Published` instead of iOS 17's `@Observable`
- **Protocol-based services**: Easy to swap mock/real implementations
- **MVVM architecture**: ViewModels handle business logic, Views handle presentation
- **Figma colors**: Tia=Orange/Brown, Mira=Blue, Olly=Green gradients

## Dependencies

None required! The app uses only system frameworks:
- SwiftUI
- Combine
- LocalAuthentication
- Network
- PhotosUI

Optional (for enhanced features):
- swift-markdown-ui (markdown rendering)
- keychain-swift (secure token storage)

## Next Steps

1. [ ] Create actual Xcode project file
2. [ ] Add Volkhov fonts
3. [ ] Add app icon
4. [ ] Add Hestia avatar image
5. [ ] Test on physical device (Face ID)
6. [ ] Connect to real API (Week 2)
