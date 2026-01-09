import Foundation

/// Hestia environment configuration
/// Manages API endpoints and environment-specific settings
///
/// Security: All environments use HTTPS to protect device tokens in transit.
/// Self-signed certificates are supported with certificate pinning.
enum HestiaEnvironment: String, CaseIterable {
    case local
    case tailscale

    /// Display name for settings UI
    var displayName: String {
        switch self {
        case .local: return "Local (Development)"
        case .tailscale: return "Tailscale (Remote)"
        }
    }

    /// API base URL for this environment
    /// Security: Always uses HTTPS to protect tokens in transit
    var apiBaseURL: String {
        switch self {
        case .local:
            // HTTPS even for local to protect device tokens
            // Self-signed cert is validated via certificate pinning
            return "https://localhost:8443/v1"
        case .tailscale:
            // Mac Mini hostname (via Tailscale or local network)
            return "https://hestia-3.local:8443/v1"
        }
    }

    /// Whether this environment uses HTTPS (always true for security)
    var usesHTTPS: Bool {
        // All environments use HTTPS for security
        return true
    }

    /// Description for settings UI
    var description: String {
        switch self {
        case .local:
            return "Connect to Hestia running on this device (HTTPS with self-signed cert)"
        case .tailscale:
            return "Connect to Hestia on Mac Mini via Tailscale VPN"
        }
    }
}

/// Global configuration manager
final class Configuration: ObservableObject {
    // MARK: - Singleton

    static let shared = Configuration()

    // MARK: - Storage Keys

    private enum Keys {
        static let environment = "hestia_environment"
        static let customTailscaleHost = "hestia_tailscale_host"
    }

    // MARK: - Published State

    @Published private(set) var environment: HestiaEnvironment {
        didSet {
            UserDefaults.standard.set(environment.rawValue, forKey: Keys.environment)
            NotificationCenter.default.post(name: .hestiaConfigurationChanged, object: nil)
        }
    }

    @Published var customTailscaleHost: String? {
        didSet {
            UserDefaults.standard.set(customTailscaleHost, forKey: Keys.customTailscaleHost)
        }
    }

    // MARK: - Computed Properties

    /// Current API base URL based on environment and custom settings
    var apiBaseURL: String {
        if environment == .tailscale, let customHost = customTailscaleHost, !customHost.isEmpty {
            // Use custom hostname if provided
            return "https://\(customHost):8443/v1"
        }
        return environment.apiBaseURL
    }

    /// Request timeout in seconds
    var requestTimeout: TimeInterval {
        switch environment {
        case .local:
            // Local connection is faster, but Ollama can still be slow
            return 120
        case .tailscale:
            // Remote connection needs more buffer
            return 150
        }
    }

    /// Resource timeout for long operations
    var resourceTimeout: TimeInterval {
        switch environment {
        case .local: return 180
        case .tailscale: return 240
        }
    }

    /// Retry configuration
    var maxRetries: Int { 3 }
    var retryBaseDelay: TimeInterval { 1.0 }
    var retryMaxDelay: TimeInterval { 10.0 }

    // MARK: - Initialization

    private init() {
        // Load saved environment
        if let savedEnv = UserDefaults.standard.string(forKey: Keys.environment),
           let env = HestiaEnvironment(rawValue: savedEnv) {
            self.environment = env
        } else {
            // Default to Tailscale for physical devices, local for simulator
            #if targetEnvironment(simulator)
            self.environment = .local
            #else
            self.environment = .tailscale
            #endif
        }

        // Load custom tailscale host
        self.customTailscaleHost = UserDefaults.standard.string(forKey: Keys.customTailscaleHost)
    }

    // MARK: - Methods

    /// Switch to a different environment
    func setEnvironment(_ env: HestiaEnvironment) {
        environment = env
    }

    /// Update custom Tailscale hostname
    func setTailscaleHost(_ host: String?) {
        customTailscaleHost = host?.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Reset to default configuration
    func reset() {
        environment = .local
        customTailscaleHost = nil
    }
}

// MARK: - Notification Names

extension Notification.Name {
    static let hestiaConfigurationChanged = Notification.Name("hestiaConfigurationChanged")
}
