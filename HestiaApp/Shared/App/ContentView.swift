import SwiftUI
import HestiaShared

/// Root view that handles authentication state and main navigation
struct RootView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var networkMonitor: NetworkMonitor
    @State private var isLocked = false
    @State private var showingLockScreen = false

    private var needsPermissionsOnboarding: Bool {
        !UserDefaults.standard.bool(forKey: "hestia_permissions_onboarding_complete")
    }

    var body: some View {
        ZStack {
            if !authService.isDeviceRegistered {
                // First time setup — QR code onboarding
                OnboardingView()
            } else if authService.isAuthenticated && needsPermissionsOnboarding {
                // Permissions onboarding (one-time, after first auth)
                PermissionsOnboardingView()
            } else if !authService.isAuthenticated || showingLockScreen {
                // Need to authenticate
                LockScreenView(onUnlock: {
                    showingLockScreen = false
                })
            } else {
                // Main app content
                MainTabView()
                    .onReceive(NotificationCenter.default.publisher(for: UIApplication.willResignActiveNotification)) { _ in
                        // App going to background - note the time
                    }
                    .onReceive(NotificationCenter.default.publisher(for: UIApplication.didBecomeActiveNotification)) { _ in
                        // App returning to foreground - check if we need to lock
                        if authService.checkAuthenticationTimeout() {
                            showingLockScreen = true
                        }
                    }
            }

            // Network offline banner
            if !networkMonitor.isConnected {
                VStack {
                    OfflineBanner()
                    Spacer()
                }
            }
        }
    }
}

/// Main tab navigation
struct MainTabView: View {
    @State private var selectedTab = 0
    @EnvironmentObject var networkMonitor: NetworkMonitor
    @EnvironmentObject var apiClientProvider: APIClientProvider

    var body: some View {
        TabView(selection: $selectedTab) {
            // Chat tab - client configured via environment in ChatView.onAppear
            ChatView()
                .tabItem {
                    Label("Chat", systemImage: "message.fill")
                }
                .tag(0)

            // Command Center tab
            CommandCenterView()
                .tabItem {
                    Label("Command", systemImage: "square.grid.2x2.fill")
                }
                .tag(1)

            // Explorer tab
            ExplorerView()
                .tabItem {
                    Label("Explorer", systemImage: "rectangle.stack.fill")
                }
                .tag(2)

            // Settings tab
            SettingsView()
                .tabItem {
                    Label("Settings", systemImage: "gearshape.fill")
                }
                .tag(3)
        }
        .accentColor(.white)
    }
}

// MARK: - Preview

struct RootView_Previews: PreviewProvider {
    static var previews: some View {
        RootView()
            .environmentObject(AppState())
            .environmentObject(AuthService())
            .environmentObject(NetworkMonitor())
            .environmentObject(APIClientProvider())
    }
}

struct MainTabView_Previews: PreviewProvider {
    static var previews: some View {
        MainTabView()
            .environmentObject(AppState())
            .environmentObject(NetworkMonitor())
            .environmentObject(APIClientProvider())
    }
}
