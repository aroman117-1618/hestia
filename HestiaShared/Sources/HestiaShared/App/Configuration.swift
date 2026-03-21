import Foundation

/// Hestia environment configuration
/// Manages API endpoints and environment-specific settings
///
/// Security: All environments use HTTPS to protect device tokens in transit.
/// Self-signed certificates are supported with certificate pinning.
public enum HestiaEnvironment: String, CaseIterable, Sendable {
    case local
    case tailscale

    /// Display name for settings UI
    public var displayName: String {
        switch self {
        case .local: return "Local (Development)"
        case .tailscale: return "Tailscale (Remote)"
        }
    }

    /// API base URL for this environment
    /// Security: Always uses HTTPS to protect tokens in transit
    public var apiBaseURL: String {
        switch self {
        case .local:
            return "https://localhost:8443/v1"
        case .tailscale:
            return "https://hestia-3.local:8443/v1"
        }
    }

    /// Whether this environment uses HTTPS (always true for security)
    public var usesHTTPS: Bool {
        return true
    }

    /// Description for settings UI
    public var description: String {
        switch self {
        case .local:
            return "Connect to Hestia running on this device (HTTPS with self-signed cert)"
        case .tailscale:
            return "Connect to Hestia on Mac Mini via Tailscale VPN"
        }
    }
}

/// Global configuration manager
@MainActor
public final class Configuration: ObservableObject {
    // MARK: - Singleton

    public static let shared = Configuration()

    // MARK: - Storage Keys

    private enum Keys {
        static let environment = "hestia_environment"
        static let customTailscaleHost = "hestia_tailscale_host"
    }

    // MARK: - Published State

    @Published public private(set) var environment: HestiaEnvironment {
        didSet {
            UserDefaults.standard.set(environment.rawValue, forKey: Keys.environment)
            NotificationCenter.default.post(name: .hestiaConfigurationChanged, object: nil)
        }
    }

    @Published public var customTailscaleHost: String? {
        didSet {
            UserDefaults.standard.set(customTailscaleHost, forKey: Keys.customTailscaleHost)
        }
    }

    // MARK: - Computed Properties

    /// Current API base URL based on environment and custom settings
    public var apiBaseURL: String {
        if environment == .tailscale, let customHost = customTailscaleHost, !customHost.isEmpty {
            return "https://\(customHost):8443/v1"
        }
        return environment.apiBaseURL
    }

    /// Request timeout in seconds
    public var requestTimeout: TimeInterval {
        switch environment {
        case .local:
            return 120
        case .tailscale:
            return 150
        }
    }

    /// Resource timeout for long operations
    public var resourceTimeout: TimeInterval {
        switch environment {
        case .local: return 180
        case .tailscale: return 240
        }
    }

    /// Retry configuration
    public var maxRetries: Int { 3 }
    public var retryBaseDelay: TimeInterval { 1.0 }
    public var retryMaxDelay: TimeInterval { 10.0 }

    // MARK: - Initialization

    private init() {
        // Load saved environment
        let savedEnv = UserDefaults.standard.string(forKey: Keys.environment)
        #if DEBUG
        print("[Configuration] UserDefaults hestia_environment = \(savedEnv ?? "nil")")
        print("[Configuration] Bundle ID = \(Bundle.main.bundleIdentifier ?? "nil")")
        #endif
        if let savedEnv, let env = HestiaEnvironment(rawValue: savedEnv) {
            self.environment = env
        } else {
            // Default to local for macOS development, Tailscale for iOS devices
            #if os(macOS) || targetEnvironment(simulator)
            self.environment = .local
            #else
            self.environment = .tailscale
            #endif
        }
        #if DEBUG
        print("[Configuration] Resolved environment = \(environment.rawValue) → \(environment.apiBaseURL)")
        #endif

        // Load custom tailscale host
        self.customTailscaleHost = UserDefaults.standard.string(forKey: Keys.customTailscaleHost)
    }

    // MARK: - Methods

    /// Switch to a different environment
    public func setEnvironment(_ env: HestiaEnvironment) {
        environment = env
    }

    /// Update custom Tailscale hostname
    public func setTailscaleHost(_ host: String?) {
        customTailscaleHost = host?.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// Reset to default configuration
    public func reset() {
        environment = .local
        customTailscaleHost = nil
    }

    /// Configure from QR code onboarding payload
    /// Extracts the host from the server URL and stores the cert fingerprint in Keychain
    public func configureFromQR(serverURL: String, certFingerprint: String) {
        // Extract host from URL (e.g. "https://hestia-3.local:8443" → "hestia-3.local")
        if let url = URL(string: serverURL), let host = url.host {
            setTailscaleHost(host)
            setEnvironment(.tailscale)
        }

        // Store certificate fingerprint in Keychain for pinning
        let stored = CertificatePinningDelegate.storeFingerprint(certFingerprint)
        #if DEBUG
        print("[Configuration] QR config: host from \(serverURL), cert stored: \(stored)")
        #endif
    }
}

// MARK: - Notification Names

extension Notification.Name {
    public static let hestiaConfigurationChanged = Notification.Name("hestiaConfigurationChanged")
}
