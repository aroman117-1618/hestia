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

    /// In DEBUG simulator builds, skip auth so we can test UI without a server
    private var shouldBypassAuth: Bool {
        #if DEBUG && targetEnvironment(simulator)
        return true
        #else
        return false
        #endif
    }

    var body: some View {
        ZStack {
            if shouldBypassAuth {
                // Debug-only: skip auth for previews / simulator testing
                MainTabView()
            } else if !authService.isDeviceRegistered {
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

            // Network offline banner — outside the auth transition
            if !networkMonitor.isConnected {
                VStack {
                    OfflineBanner()
                    Spacer()
                }
            }
        }
        .animation(.easeInOut(duration: 0.5), value: authService.isDeviceRegistered)
    }
}

/// Main tab navigation with swipe-to-switch between Chat, Command, and Settings.
/// No visible tab bar — swipe left/right to navigate.
struct MainTabView: View {
    @State private var selectedTab = 0
    @EnvironmentObject var networkMonitor: NetworkMonitor
    @EnvironmentObject var apiClientProvider: APIClientProvider

    var body: some View {
        TabView(selection: $selectedTab) {
            ChatView()
                .tag(0)

            MobileCommandView()
                .tag(1)
                .onAppear { dismissKeyboard() }

            MobileSettingsView()
                .tag(2)
                .onAppear { dismissKeyboard() }
        }
        .tabViewStyle(.page(indexDisplayMode: .never))
        .ignoresSafeArea()
        .onChange(of: selectedTab) { _ in
            dismissKeyboard()
        }
    }

    private func dismissKeyboard() {
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
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
