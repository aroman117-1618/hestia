import SwiftUI
import HestiaShared

/// macOS onboarding state
private enum MacOnboardingStep: Equatable {
    case welcome
    case paste
    case connecting
    case success
    case error(String)
}

/// macOS onboarding flow — paste QR payload to register with Hestia server
struct MacOnboardingView: View {
    @ObservedObject var authService: AuthService
    @State private var step: MacOnboardingStep = .welcome
    @State private var pastedText = ""
    @State private var serverURL = ""
    @State private var isProcessing = false

    var body: some View {
        ZStack {
            MacColors.windowBackground.ignoresSafeArea()

            switch step {
            case .welcome:
                welcomeStep
            case .paste:
                pasteStep
            case .connecting:
                connectingStep
            case .success:
                successStep
            case .error(let message):
                errorStep(message: message)
            }
        }
    }

    // MARK: - Welcome

    private var welcomeStep: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "brain.head.profile")
                .font(.system(size: 64))
                .foregroundColor(MacColors.amberAccent)

            Text("Hestia")
                .font(.system(size: 36, weight: .bold))
                .foregroundColor(.white)

            Text("Paste the invite code from your Hestia server to connect this Mac.")
                .font(.body)
                .foregroundColor(MacColors.textSecondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)

            Spacer()

            Button {
                step = .paste
            } label: {
                Text("Connect to Server")
                    .font(.headline)
                    .foregroundColor(.white)
                    .frame(width: 220, height: 40)
                    .background(MacColors.amberAccent.opacity(0.3))
                    .cornerRadius(8)
                    .overlay(
                        RoundedRectangle(cornerRadius: 8)
                            .stroke(MacColors.amberAccent.opacity(0.5), lineWidth: 1)
                    )
            }
            .buttonStyle(.hestia)

            Spacer()
                .frame(height: 40)
        }
        .frame(maxWidth: 500)
        .frame(maxWidth: .infinity)
    }

    // MARK: - Paste Step

    private var pasteStep: some View {
        VStack(spacing: 20) {
            Spacer()

            Image(systemName: "qrcode")
                .font(.system(size: 48))
                .foregroundColor(MacColors.amberAccent)

            Text("Paste Invite Code")
                .font(.title2.bold())
                .foregroundColor(.white)

            Text("Copy the JSON invite code from your Hestia server and paste it below.")
                .font(.body)
                .foregroundColor(MacColors.textSecondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)

            TextEditor(text: $pastedText)
                .font(.system(.body, design: .monospaced))
                .frame(width: 420, height: 120)
                .scrollContentBackground(.hidden)
                .background(MacColors.panelBackground)
                .cornerRadius(8)
                .overlay(
                    RoundedRectangle(cornerRadius: 8)
                        .stroke(MacColors.subtleBorder, lineWidth: 1)
                )

            HStack(spacing: 16) {
                Button {
                    step = .welcome
                    pastedText = ""
                } label: {
                    Text("Back")
                        .foregroundColor(MacColors.textSecondary)
                }
                .buttonStyle(.hestia)

                Button {
                    handlePaste()
                } label: {
                    Text("Connect")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(width: 120, height: 36)
                        .background(pastedText.isEmpty ? MacColors.amberAccent.opacity(0.15) : MacColors.amberAccent.opacity(0.3))
                        .cornerRadius(8)
                        .overlay(
                            RoundedRectangle(cornerRadius: 8)
                                .stroke(MacColors.amberAccent.opacity(0.5), lineWidth: 1)
                        )
                }
                .buttonStyle(.hestia)
                .disabled(pastedText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isProcessing)
            }

            Spacer()
                .frame(height: 40)
        }
        .frame(maxWidth: 500)
        .frame(maxWidth: .infinity)
    }

    // MARK: - Connecting

    private var connectingStep: some View {
        VStack(spacing: 20) {
            Spacer()

            ProgressView()
                .scaleEffect(1.5)
                .tint(MacColors.amberAccent)

            Text("Connecting...")
                .font(.headline)
                .foregroundColor(.white)

            if !serverURL.isEmpty {
                Text(serverURL)
                    .font(.caption)
                    .foregroundColor(MacColors.textSecondary)
            }

            Spacer()
        }
    }

    // MARK: - Success

    private var successStep: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 64))
                .foregroundColor(.green)

            Text("Connected")
                .font(.title.bold())
                .foregroundColor(.white)

            Text("This Mac is now registered with your Hestia server.")
                .font(.body)
                .foregroundColor(MacColors.textSecondary)

            Spacer()
        }
    }

    // MARK: - Error

    private func errorStep(message: String) -> some View {
        VStack(spacing: 20) {
            Spacer()

            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundColor(.yellow)

            Text("Connection Failed")
                .font(.title2.bold())
                .foregroundColor(.white)

            Text(message)
                .font(.body)
                .foregroundColor(MacColors.textSecondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)

            HStack(spacing: 16) {
                Button {
                    step = .welcome
                } label: {
                    Text("Back")
                        .foregroundColor(MacColors.textSecondary)
                }
                .buttonStyle(.hestia)

                Button {
                    step = .paste
                    pastedText = ""
                } label: {
                    Text("Try Again")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(width: 120, height: 36)
                        .background(MacColors.amberAccent.opacity(0.3))
                        .cornerRadius(8)
                }
                .buttonStyle(.hestia)
            }

            Spacer()
        }
    }

    // MARK: - Actions

    private func handlePaste() {
        let text = pastedText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }

        guard let data = text.data(using: .utf8),
              let payload = try? JSONDecoder().decode(QRInvitePayload.self, from: data) else {
            step = .error("Invalid invite code. Expected JSON with keys: t, u, f.")
            return
        }

        serverURL = payload.u
        isProcessing = true
        step = .connecting

        // Configure API to point at server from QR code
        Configuration.shared.configureFromQR(
            serverURL: payload.u,
            certFingerprint: payload.f
        )

        Task {
            do {
                let token = try await authService.registerWithInvite(inviteToken: payload.t)

                // Configure the shared APIClient with the new token
                APIClient.shared.setDeviceToken(token)

                #if DEBUG
                print("[MacOnboarding] Registration successful")
                #endif

                step = .success

                // Notify MainSplitViewController to transition to workspace
                DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                    NotificationCenter.default.post(name: .hestiaConfigurationChanged, object: nil)
                }
            } catch {
                #if DEBUG
                print("[MacOnboarding] Registration failed: \(error)")
                #endif

                let message: String
                if let hestiaError = error as? HestiaError {
                    message = hestiaError.userMessage
                } else {
                    message = "Could not connect to server. Check the invite code and try again."
                }
                step = .error(message)
            }
            isProcessing = false
        }
    }
}
