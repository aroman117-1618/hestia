import SwiftUI
import CoreData

@main
struct HestiaApp: App {
    @StateObject private var appState = AppState()
    @StateObject private var authService = AuthService()
    @StateObject private var networkMonitor = NetworkMonitor()
    @StateObject private var apiClientProvider = APIClientProvider()

    let persistenceController = PersistenceController.shared

    init() {
        // Load custom fonts
        FontLoader.loadFonts()

        // Configure appearance
        configureAppearance()

        // Schedule cleanup of old agent profile snapshots
        let controller = persistenceController
        Task {
            await controller.cleanupOldSnapshots()
        }
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(appState)
                .environmentObject(authService)
                .environmentObject(networkMonitor)
                .environmentObject(apiClientProvider)
                .environment(\.managedObjectContext, persistenceController.viewContext)
                .task {
                    // Configure API client with stored token if available
                    if apiClientProvider.configureFromAuthService(authService) {
                        #if DEBUG
                        print("[HestiaApp] API client configured with stored token")
                        #endif
                    } else {
                        #if DEBUG
                        print("[HestiaApp] No stored token, device registration required")
                        #endif
                    }
                }
        }
    }

    private func configureAppearance() {
        // Tab bar appearance
        let tabBarAppearance = UITabBarAppearance()
        tabBarAppearance.configureWithOpaqueBackground()
        tabBarAppearance.backgroundColor = UIColor.black.withAlphaComponent(0.9)
        UITabBar.appearance().standardAppearance = tabBarAppearance
        UITabBar.appearance().scrollEdgeAppearance = tabBarAppearance

        // Navigation bar appearance
        let navBarAppearance = UINavigationBarAppearance()
        navBarAppearance.configureWithTransparentBackground()
        navBarAppearance.titleTextAttributes = [.foregroundColor: UIColor.white]
        navBarAppearance.largeTitleTextAttributes = [.foregroundColor: UIColor.white]
        UINavigationBar.appearance().standardAppearance = navBarAppearance
        UINavigationBar.appearance().scrollEdgeAppearance = navBarAppearance
        UINavigationBar.appearance().tintColor = .white
    }
}
