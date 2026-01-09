import Foundation
import LocalAuthentication
import Security
import UIKit

/// Service for handling authentication (Face ID / Touch ID) and device registration
class AuthService: ObservableObject {
    // MARK: - Published State

    @Published private(set) var isAuthenticated: Bool = false
    @Published private(set) var isDeviceRegistered: Bool = false
    @Published private(set) var biometricType: BiometricType = .none
    @Published private(set) var lastAuthenticationTime: Date?

    // MARK: - Configuration

    /// Auto-lock timeout in seconds (default: 30 minutes)
    var autoLockTimeout: TimeInterval = 30 * 60

    /// Configuration reference for API settings
    private let config = Configuration.shared

    /// Skip biometric auth in simulator (for development)
    private var isSimulator: Bool {
        #if targetEnvironment(simulator)
        return true
        #else
        return false
        #endif
    }

    // MARK: - Private

    private let context = LAContext()

    // Keychain configuration
    private let keychainService = "com.hestia.app"
    private let keychainAccount = "device_token"

    // Cached API client for registration (uses Configuration.shared automatically)
    private lazy var registrationClient: APIClient = {
        APIClient()
    }()

    // MARK: - Initialization

    init() {
        checkBiometricType()
        checkDeviceRegistration()

        // Auto-authenticate in simulator for easier development
        #if targetEnvironment(simulator)
        if isDeviceRegistered {
            isAuthenticated = true
            lastAuthenticationTime = Date()
        }
        #endif
    }

    // MARK: - Biometric Authentication

    enum BiometricType {
        case none
        case touchID
        case faceID

        var displayName: String {
            switch self {
            case .none: return "None"
            case .touchID: return "Touch ID"
            case .faceID: return "Face ID"
            }
        }

        var iconName: String {
            switch self {
            case .none: return "lock"
            case .touchID: return "touchid"
            case .faceID: return "faceid"
            }
        }
    }

    /// Check what biometric type is available
    private func checkBiometricType() {
        var error: NSError?
        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            switch context.biometryType {
            case .faceID:
                biometricType = .faceID
            case .touchID:
                biometricType = .touchID
            default:
                biometricType = .none
            }
        } else {
            biometricType = .none
        }
    }

    /// Authenticate with Face ID / Touch ID
    func authenticate() async throws {
        // Skip biometric auth in simulator
        #if targetEnvironment(simulator)
        await MainActor.run {
            isAuthenticated = true
            lastAuthenticationTime = Date()
        }
        return
        #else
        let context = LAContext()
        context.localizedCancelTitle = "Cancel"

        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            if let error = error {
                throw mapLAError(error)
            }
            throw HestiaError.biometricNotAvailable
        }

        do {
            let success = try await context.evaluatePolicy(
                .deviceOwnerAuthenticationWithBiometrics,
                localizedReason: "Authenticate to access Hestia"
            )

            if success {
                await MainActor.run {
                    isAuthenticated = true
                    lastAuthenticationTime = Date()
                }
            }
        } catch let error as NSError {
            throw mapLAError(error)
        }
        #endif
    }

    /// Check if authentication has timed out
    func checkAuthenticationTimeout() -> Bool {
        guard let lastAuth = lastAuthenticationTime else {
            return true // Never authenticated
        }

        let elapsed = Date().timeIntervalSince(lastAuth)
        if elapsed > autoLockTimeout {
            isAuthenticated = false
            return true
        }
        return false
    }

    /// Lock the app (require re-authentication)
    func lock() {
        isAuthenticated = false
        lastAuthenticationTime = nil
    }

    // MARK: - Device Registration

    /// Check if device is registered by looking for token in Keychain
    private func checkDeviceRegistration() {
        isDeviceRegistered = loadTokenFromKeychain() != nil
    }

    /// Register this device with the Hestia backend
    /// Returns the device token for use with APIClient
    func registerDevice() async throws -> String {
        // Get device info
        let deviceName = await MainActor.run { UIDevice.current.name }
        let deviceType = "iOS"

        // Call the registration API
        let response = try await registrationClient.registerDevice(
            deviceName: deviceName,
            deviceType: deviceType
        )

        // Store the JWT token in Keychain
        try saveTokenToKeychain(response.token)

        await MainActor.run {
            isDeviceRegistered = true
        }

        return response.token
    }

    /// Get the stored device token from Keychain
    func getDeviceToken() -> String? {
        return loadTokenFromKeychain()
    }

    /// Remove device registration
    func unregisterDevice() {
        deleteTokenFromKeychain()
        isDeviceRegistered = false
        isAuthenticated = false
    }

    // MARK: - Keychain Helpers

    private func saveTokenToKeychain(_ token: String) throws {
        guard let data = token.data(using: .utf8) else {
            throw HestiaError.unknown("Failed to encode token")
        }

        // Build the query
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        ]

        // Delete any existing token first
        SecItemDelete(query as CFDictionary)

        // Add the new token
        let status = SecItemAdd(query as CFDictionary, nil)
        guard status == errSecSuccess else {
            throw HestiaError.unknown("Failed to save token to Keychain (status: \(status))")
        }
    }

    private func loadTokenFromKeychain() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let token = String(data: data, encoding: .utf8) else {
            return nil
        }

        return token
    }

    private func deleteTokenFromKeychain() {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: keychainService,
            kSecAttrAccount as String: keychainAccount
        ]

        SecItemDelete(query as CFDictionary)
    }

    // MARK: - Private Helpers

    private func mapLAError(_ error: NSError) -> HestiaError {
        switch error.code {
        case LAError.userCancel.rawValue,
             LAError.appCancel.rawValue,
             LAError.systemCancel.rawValue:
            return .biometricFailed
        case LAError.biometryNotAvailable.rawValue:
            return .biometricNotAvailable
        case LAError.biometryNotEnrolled.rawValue:
            return .biometricNotAvailable
        case LAError.biometryLockout.rawValue:
            return .biometricFailed
        case LAError.authenticationFailed.rawValue:
            return .biometricFailed
        default:
            return .biometricFailed
        }
    }
}
