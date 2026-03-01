import SwiftUI
import HestiaShared

/// State machine for QR code onboarding flow
enum OnboardingStep: Equatable {
    case welcome
    case scanQR
    case connecting
    case success
    case error(String)
}

/// ViewModel managing the QR code onboarding flow
@MainActor
class OnboardingViewModel: ObservableObject {
    // MARK: - Published State

    @Published var step: OnboardingStep = .welcome
    @Published var isProcessing = false
    @Published var scannedPayload: QRInvitePayload?
    @Published var serverURL: String = ""

    // MARK: - Dependencies

    private var authService: AuthService?
    private var apiClientProvider: APIClientProvider?

    // MARK: - Configuration

    func configure(authService: AuthService, apiClientProvider: APIClientProvider) {
        self.authService = authService
        self.apiClientProvider = apiClientProvider
    }

    // MARK: - Actions

    /// Start the QR scanning step
    func startScanning() {
        step = .scanQR
    }

    /// Handle a scanned QR code string
    func handleScannedCode(_ code: String) {
        guard !isProcessing else { return }

        guard let payload = parseQRPayload(code) else {
            step = .error("Invalid QR code. Please scan the Hestia invite QR code.")
            return
        }

        scannedPayload = payload
        serverURL = payload.u

        Task {
            await registerWithInvite(payload: payload)
        }
    }

    /// Handle manual paste of QR payload (macOS fallback)
    func handleManualPayload(_ text: String) {
        handleScannedCode(text)
    }

    /// Retry after an error
    func retry() {
        step = .scanQR
        scannedPayload = nil
    }

    /// Go back to welcome
    func goBack() {
        step = .welcome
        scannedPayload = nil
    }

    // MARK: - Private

    private func parseQRPayload(_ code: String) -> QRInvitePayload? {
        guard let data = code.data(using: .utf8) else { return nil }

        let decoder = JSONDecoder()
        return try? decoder.decode(QRInvitePayload.self, from: data)
    }

    private func registerWithInvite(payload: QRInvitePayload) async {
        guard let authService = authService else {
            step = .error("Auth service not available.")
            return
        }

        isProcessing = true
        step = .connecting

        // Configure the API to point at the server from the QR code
        Configuration.shared.configureFromQR(
            serverURL: payload.u,
            certFingerprint: payload.f
        )

        do {
            let token = try await authService.registerWithInvite(inviteToken: payload.t)

            // Configure the API client with the new token
            apiClientProvider?.configure(withToken: token)

            #if DEBUG
            print("[OnboardingVM] Registration successful, token stored")
            #endif

            step = .success
        } catch {
            #if DEBUG
            print("[OnboardingVM] Registration failed: \(error)")
            #endif

            let message: String
            if let hestiaError = error as? HestiaError {
                message = hestiaError.userMessage
            } else {
                message = "Could not connect to server. Check the QR code and try again."
            }
            step = .error(message)
        }

        isProcessing = false
    }
}
