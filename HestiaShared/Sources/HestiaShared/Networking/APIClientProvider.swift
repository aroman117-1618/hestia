import Foundation
import Combine

/// Provides a configured APIClient for use throughout the app
/// Handles the connection between AuthService and APIClient
@MainActor
public class APIClientProvider: ObservableObject {
    // MARK: - Published State

    @Published public private(set) var isReady: Bool = false

    // MARK: - Properties

    public private(set) var client: APIClient

    // MARK: - Initialization

    public init() {
        self.client = APIClient()
    }

    // MARK: - Public Methods

    /// Configure the client with a device token
    public func configure(withToken token: String) {
        client.setDeviceToken(token)
        isReady = true
    }

    /// Configure from an existing AuthService
    public func configureFromAuthService(_ authService: AuthService) -> Bool {
        if let token = authService.getDeviceToken() {
            configure(withToken: token)
            return true
        }
        return false
    }

    /// Reset the client (e.g., after logout)
    public func reset() {
        client = APIClient()
        isReady = false
    }
}
