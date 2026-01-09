import SwiftUI
import Combine

/// ViewModel for authentication flow
@MainActor
class AuthViewModel: ObservableObject {
    // MARK: - Published State

    @Published var isAuthenticated: Bool = false
    @Published var isDeviceRegistered: Bool = false
    @Published var isLoading: Bool = false
    @Published var error: HestiaError?
    @Published var showError: Bool = false

    // MARK: - Dependencies

    private var authService: AuthService
    private var apiClientProvider: APIClientProvider?

    // MARK: - Computed Properties

    var biometricType: AuthService.BiometricType {
        authService.biometricType
    }

    var biometricAvailable: Bool {
        authService.biometricType != .none
    }

    // MARK: - Initialization

    init(authService: AuthService = AuthService(), apiClientProvider: APIClientProvider? = nil) {
        self.authService = authService
        self.apiClientProvider = apiClientProvider
        updateState()
    }

    /// Configure with services from environment
    func configure(authService: AuthService, apiClientProvider: APIClientProvider) {
        self.authService = authService
        self.apiClientProvider = apiClientProvider
        updateState()
    }

    // MARK: - Public Methods

    /// Check current authentication state
    func checkAuthState() {
        updateState()

        // Check if we need to re-authenticate due to timeout
        if authService.checkAuthenticationTimeout() {
            isAuthenticated = false
        }
    }

    /// Authenticate with Face ID / Touch ID
    func authenticate() async {
        isLoading = true
        error = nil

        do {
            try await authService.authenticate()
            updateState()
        } catch let hestiaError as HestiaError {
            self.error = hestiaError
            self.showError = true
        } catch {
            self.error = .unknown(error.localizedDescription)
            self.showError = true
        }

        isLoading = false
    }

    /// Register this device
    func registerDevice() async {
        isLoading = true
        error = nil

        do {
            let token = try await authService.registerDevice()
            updateState()

            // Configure API client with the new token
            apiClientProvider?.configure(withToken: token)
            print("[AuthViewModel] API client configured with new token")

            // After registration, authenticate
            await authenticate()
        } catch let hestiaError as HestiaError {
            self.error = hestiaError
            self.showError = true
        } catch {
            self.error = .unknown(error.localizedDescription)
            self.showError = true
        }

        isLoading = false
    }

    /// Lock the app
    func lock() {
        authService.lock()
        updateState()
    }

    /// Dismiss error
    func dismissError() {
        showError = false
        error = nil
    }

    // MARK: - Private Methods

    private func updateState() {
        isAuthenticated = authService.isAuthenticated
        isDeviceRegistered = authService.isDeviceRegistered
    }
}
