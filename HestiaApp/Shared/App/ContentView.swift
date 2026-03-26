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

/// Main tab navigation with hidden tab bar.
/// Tab bar appears on swipe-up from bottom edge, dismisses on tap outside or swipe down.
struct MainTabView: View {
    @State private var selectedTab = 0
    @State private var showTabBar = false
    @EnvironmentObject var networkMonitor: NetworkMonitor
    @EnvironmentObject var apiClientProvider: APIClientProvider

    private let tabs: [(name: String, icon: String)] = [
        ("Chat", "message.fill"),
        ("Command", "square.grid.2x2.fill"),
        ("Settings", "gearshape.fill")
    ]

    var body: some View {
        ZStack(alignment: .bottom) {
            // Content
            Group {
                switch selectedTab {
                case 0: ChatView()
                case 1: MobileCommandView()
                case 2: MobileSettingsView()
                default: ChatView()
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Swipe-up detection zone at bottom edge
            if !showTabBar {
                Color.clear
                    .frame(height: 60)
                    .contentShape(Rectangle())
                    .gesture(
                        DragGesture(minimumDistance: 20)
                            .onEnded { value in
                                // Swipe up (negative y translation)
                                if value.translation.height < -20 {
                                    withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
                                        showTabBar = true
                                    }
                                }
                            }
                    )
                    .frame(maxHeight: .infinity, alignment: .bottom)
            }

            // Custom tab bar overlay
            if showTabBar {
                // Dismiss backdrop
                Color.black.opacity(0.3)
                    .ignoresSafeArea()
                    .onTapGesture {
                        withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                            showTabBar = false
                        }
                    }
                    .gesture(
                        DragGesture(minimumDistance: 10)
                            .onEnded { value in
                                if value.translation.height > 20 {
                                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                                        showTabBar = false
                                    }
                                }
                            }
                    )

                // Tab bar
                customTabBar
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
    }

    private var customTabBar: some View {
        HStack(spacing: 0) {
            ForEach(0..<tabs.count, id: \.self) { index in
                Button {
                    selectedTab = index
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                        showTabBar = false
                    }
                } label: {
                    VStack(spacing: 4) {
                        Image(systemName: tabs[index].icon)
                            .font(.system(size: 22))
                        Text(tabs[index].name)
                            .font(.system(size: 11, weight: .medium))
                    }
                    .foregroundColor(selectedTab == index ? Color(hex: "FF9F0A") : .white.opacity(0.5))
                    .frame(maxWidth: .infinity)
                }
            }
        }
        .padding(.top, 12)
        .padding(.bottom, 28)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(Color.white.opacity(0.1), lineWidth: 0.5)
                )
                .shadow(color: .black.opacity(0.3), radius: 20, y: -5)
        )
        .padding(.horizontal, 8)
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
