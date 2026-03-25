import SwiftUI
import HestiaShared
import Combine

/// ViewModel for Settings
@MainActor
class SettingsViewModel: ObservableObject {
    // MARK: - Published State

    @Published var defaultMode: HestiaMode = .tia
    @Published var autoLockTimeout: AutoLockTimeout = .thirtyMinutes
    @Published var systemHealth: SystemHealth?
    @Published var isLoading: Bool = false
    @Published var pendingReviewCount: Int = 0
    @Published var cloudState: String?
    @Published var deviceCount: Int = 1

    // MARK: - Dependencies

    private let client: HestiaClientProtocol
    private let authService: AuthService

    // MARK: - Types

    enum AutoLockTimeout: Int, CaseIterable, Identifiable {
        case fifteenMinutes = 15
        case thirtyMinutes = 30
        case oneHour = 60
        case never = 0

        var id: Int { rawValue }

        var displayName: String {
            switch self {
            case .fifteenMinutes: return "15 minutes"
            case .thirtyMinutes: return "30 minutes"
            case .oneHour: return "1 hour"
            case .never: return "Never"
            }
        }
    }

    // MARK: - Computed Properties

    var biometricType: AuthService.BiometricType {
        authService.biometricType
    }

    var biometricEnabled: Bool {
        authService.biometricType != .none
    }

    var serverOnline: Bool {
        systemHealth != nil
    }

    var autoLockMinutes: Int {
        autoLockTimeout.rawValue
    }

    var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0"
    }

    var buildNumber: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "1"
    }

    // MARK: - Initialization

    init(client: HestiaClientProtocol = APIClient.shared, authService: AuthService = AuthService()) {
        self.client = client
        self.authService = authService
        loadSavedSettings()
    }

    // MARK: - Configuration

    /// Configure with a specific API client (used by MobileSettingsView).
    func configure(apiClient: APIClient) {
        // SettingsViewModel already uses APIClient.shared via init.
        // This method exists so the view can trigger configuration timing.
    }

    /// Load settings and server state.
    func loadSettings() async {
        await refresh()
        // Load cloud state
        do {
            let state: CloudStateResponse = try await (client as! APIClient).getCloudState()
            cloudState = state.state
        } catch {
            #if DEBUG
            print("[Settings] Failed to load cloud state: \(error)")
            #endif
        }
    }

    // MARK: - Public Methods

    /// Refresh data from server
    func refresh() async {
        isLoading = true

        do {
            systemHealth = try await client.getSystemHealth()
            let pending = try await client.getPendingMemoryReviews()
            pendingReviewCount = pending.count
        } catch {
            // Silent failure for settings refresh
        }

        isLoading = false
    }

    /// Save settings
    func saveSettings() {
        UserDefaults.standard.set(defaultMode.rawValue, forKey: "defaultMode")
        UserDefaults.standard.set(autoLockTimeout.rawValue, forKey: "autoLockTimeout")

        // Update auth service timeout
        authService.autoLockTimeout = TimeInterval(autoLockTimeout.rawValue * 60)
    }

    /// Lock the app
    func lockApp() {
        authService.lock()
    }

    /// Unregister device
    func unregisterDevice() {
        authService.unregisterDevice()
    }

    // MARK: - Private Methods

    private func loadSavedSettings() {
        if let modeString = UserDefaults.standard.string(forKey: "defaultMode"),
           let mode = HestiaMode(rawValue: modeString) {
            defaultMode = mode
        }

        let timeout = UserDefaults.standard.integer(forKey: "autoLockTimeout")
        autoLockTimeout = AutoLockTimeout(rawValue: timeout) ?? .thirtyMinutes
    }
}
