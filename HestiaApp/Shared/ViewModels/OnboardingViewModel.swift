import SwiftUI
import HestiaShared
import AuthenticationServices

// MARK: - Onboarding Step

enum OnboardingStep: Equatable {
    case welcome
    case appleSignIn
    case serverURL
    case connecting
    case success
    case error(String)
}

// MARK: - OnboardingViewModel

/// State machine for the redesigned onboarding flow:
/// welcome -> appleSignIn -> serverURL -> connecting -> success/error
@MainActor
class OnboardingViewModel: ObservableObject {
    // MARK: - Published State

    @Published var step: OnboardingStep = .welcome
    @Published var orbState: HestiaOrbState = .idle
    @Published var serverURL: String = ""
    @Published var isProcessing = false
    @Published var scannedPayload: QRInvitePayload?
    @Published var successTransitionStarted = false

    // MARK: - Internal State

    /// Apple identity token stored after Sign In with Apple succeeds
    private var appleIdentityToken: String?

    // MARK: - Dependencies

    private var authService: AuthService?
    private var apiClientProvider: APIClientProvider?

    // MARK: - Constants

    private static let tailscaleHost = "hestia-3.local"
    private static let defaultPort = "8443"
    private static let serverURLKey = "hestia_last_server_url"
    private static let successDismissDelay: TimeInterval = 1.2

    // MARK: - Configuration

    func configure(authService: AuthService, apiClientProvider: APIClientProvider) {
        self.authService = authService
        self.apiClientProvider = apiClientProvider
    }

    // MARK: - Actions

    /// User taps "Get Started" on the welcome screen
    func getStartedTapped() {
        step = .appleSignIn
    }

    /// Handle the result from SignInWithAppleButton
    func handleAppleSignIn(result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let tokenData = credential.identityToken,
                  let token = String(data: tokenData, encoding: .utf8) else {
                step = .error("Could not read Apple identity token. Please try again.")
                orbState = .idle
                return
            }

            appleIdentityToken = token

            #if DEBUG
            print("[OnboardingVM] Apple Sign In succeeded, identity token stored")
            #endif

            // Pre-fill the server URL, then advance
            prefillServerURL()
            step = .serverURL

        case .failure(let error):
            // ASAuthorizationError.canceled means user dismissed the sheet
            if let authError = error as? ASAuthorizationError,
               authError.code == .canceled {
                #if DEBUG
                print("[OnboardingVM] Apple Sign In canceled by user")
                #endif
                step = .welcome
                return
            }

            #if DEBUG
            print("[OnboardingVM] Apple Sign In failed: \(error)")
            #endif
            step = .error("Apple Sign In failed. Please try again.")
            orbState = .idle
        }
    }

    /// Attempt to connect to the server using the entered URL
    func connectToServer() {
        guard !isProcessing else { return }
        guard let token = appleIdentityToken else {
            step = .error("No Apple identity token. Please sign in again.")
            return
        }

        let trimmedURL = serverURL.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedURL.isEmpty else {
            step = .error("Please enter a server URL.")
            return
        }

        // Normalize: ensure https:// prefix
        let normalizedURL: String
        if trimmedURL.hasPrefix("https://") || trimmedURL.hasPrefix("http://") {
            normalizedURL = trimmedURL
        } else {
            normalizedURL = "https://\(trimmedURL)"
        }

        isProcessing = true
        step = .connecting
        orbState = .thinking

        // Save for future pre-fill
        UserDefaults.standard.set(normalizedURL, forKey: Self.serverURLKey)

        // Configure API to point at the server
        Configuration.shared.configureFromQR(
            serverURL: normalizedURL,
            certFingerprint: "" // Established on first successful connection
        )

        Task {
            await registerWithApple(identityToken: token)
        }
    }

    /// Handle a scanned QR code (fallback path)
    func handleScannedCode(_ code: String) {
        guard !isProcessing else { return }

        guard let payload = parseQRPayload(code) else {
            step = .error("Invalid QR code. Please scan the Hestia invite QR code.")
            orbState = .idle
            return
        }

        scannedPayload = payload
        serverURL = payload.u

        Task {
            await registerWithInvite(payload: payload)
        }
    }

    /// Retry after an error
    func retry() {
        orbState = .idle
        if appleIdentityToken != nil {
            // Already signed in with Apple — go back to URL entry
            step = .serverURL
        } else {
            step = .welcome
        }
    }

    /// Go back to welcome
    func goBack() {
        step = .welcome
        orbState = .idle
        scannedPayload = nil
        appleIdentityToken = nil
    }

    /// Go back one step from server URL
    func goBackFromURL() {
        step = .welcome
        orbState = .idle
        appleIdentityToken = nil
    }

    // MARK: - Server URL Pre-fill

    /// Try Tailscale DNS resolution, fall back to last known URL
    func prefillServerURL() {
        // First check UserDefaults for last known URL
        if let lastURL = UserDefaults.standard.string(forKey: Self.serverURLKey), !lastURL.isEmpty {
            serverURL = lastURL
        }

        // Try Tailscale DNS resolution in background
        Task {
            if let resolved = await resolveTailscaleHost() {
                serverURL = resolved
            }
        }
    }

    private func resolveTailscaleHost() async -> String? {
        return await withCheckedContinuation { continuation in
            let host = CFHostCreateWithName(nil, Self.tailscaleHost as CFString).takeRetainedValue()
            var resolved = DarwinBoolean(false)
            CFHostStartInfoResolution(host, .addresses, nil)
            guard let addresses = CFHostGetAddressing(host, &resolved)?.takeUnretainedValue() as? [Data],
                  !addresses.isEmpty else {
                continuation.resume(returning: nil)
                return
            }
            continuation.resume(returning: "https://\(Self.tailscaleHost):\(Self.defaultPort)")
        }
    }

    // MARK: - Registration

    private func registerWithApple(identityToken: String) async {
        guard let authService = authService else {
            step = .error("Auth service not available.")
            orbState = .idle
            isProcessing = false
            return
        }

        do {
            let token = try await authService.registerWithApple(identityToken: identityToken)

            // Configure the API client with the new token
            apiClientProvider?.configure(withToken: token)

            #if DEBUG
            print("[OnboardingVM] Apple registration successful, token stored")
            #endif

            orbState = .success
            step = .success

            // After a delay, signal the transition
            try? await Task.sleep(nanoseconds: UInt64(Self.successDismissDelay * 1_000_000_000))
            successTransitionStarted = true
        } catch {
            #if DEBUG
            print("[OnboardingVM] Apple registration failed: \(error)")
            #endif

            let message: String
            if let hestiaError = error as? HestiaError {
                message = hestiaError.userMessage
            } else {
                message = "Could not connect to server. Check the URL and try again."
            }
            step = .error(message)
            orbState = .idle
        }

        isProcessing = false
    }

    private func registerWithInvite(payload: QRInvitePayload) async {
        guard let authService = authService else {
            step = .error("Auth service not available.")
            orbState = .idle
            return
        }

        isProcessing = true
        step = .connecting
        orbState = .thinking

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
            print("[OnboardingVM] QR registration successful, token stored")
            #endif

            orbState = .success
            step = .success

            try? await Task.sleep(nanoseconds: UInt64(Self.successDismissDelay * 1_000_000_000))
            successTransitionStarted = true
        } catch {
            #if DEBUG
            print("[OnboardingVM] QR registration failed: \(error)")
            #endif

            let message: String
            if let hestiaError = error as? HestiaError {
                message = hestiaError.userMessage
            } else {
                message = "Could not connect to server. Check the QR code and try again."
            }
            step = .error(message)
            orbState = .idle
        }

        isProcessing = false
    }

    // MARK: - Helpers

    private func parseQRPayload(_ code: String) -> QRInvitePayload? {
        guard let data = code.data(using: .utf8) else { return nil }
        return try? JSONDecoder().decode(QRInvitePayload.self, from: data)
    }
}
