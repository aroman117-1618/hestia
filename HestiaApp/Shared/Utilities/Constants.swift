import Foundation

/// App-wide constants
enum Constants {
    // MARK: - API

    enum API {
        static let baseURL = "http://localhost:8443/v1"
        static let timeout: TimeInterval = 60
        static let maxMessageLength = 32000
    }

    // MARK: - Storage Keys

    enum StorageKeys {
        static let deviceToken = "com.hestia.deviceToken"
        static let defaultMode = "defaultMode"
        static let autoLockTimeout = "autoLockTimeout"
        static let lastSessionId = "lastSessionId"
        static let hasCompletedOnboarding = "hasCompletedOnboarding"
    }

    // MARK: - Animation

    enum Animation {
        static let typewriterSpeed: Double = 0.03  // seconds per character
        static let standardDuration: Double = 0.3
        static let quickDuration: Double = 0.2
        static let slowDuration: Double = 0.5
    }

    // MARK: - Limits

    enum Limits {
        static let maxConversationHistory = 100
        static let maxPendingReviews = 50
        static let sessionTimeoutSeconds: TimeInterval = 30 * 60  // 30 minutes
    }

    // MARK: - Keychain

    enum Keychain {
        static let service = "com.hestia.app"
        static let accessGroup: String? = nil  // Set for app group sharing
    }
}
