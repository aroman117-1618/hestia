import Foundation
import Combine

/// Provides a configured APIClient for use throughout the app
/// Handles the connection between AuthService and APIClient
@MainActor
class APIClientProvider: ObservableObject {
    // MARK: - Published State

    @Published private(set) var isReady: Bool = false

    // MARK: - Properties

    private(set) var client: APIClient

    // MARK: - Initialization

    init() {
        // APIClient uses Configuration.shared automatically
        self.client = APIClient()
    }

    // MARK: - Public Methods

    /// Configure the client with a device token
    /// Call this after successful device registration
    func configure(withToken token: String) {
        client.setDeviceToken(token)
        isReady = true
    }

    /// Configure from an existing AuthService
    /// Returns true if a valid token was found and configured
    func configureFromAuthService(_ authService: AuthService) -> Bool {
        if let token = authService.getDeviceToken() {
            configure(withToken: token)
            return true
        }
        return false
    }

    /// Reset the client (e.g., after logout)
    func reset() {
        client = APIClient()
        isReady = false
    }
}
