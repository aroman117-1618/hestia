import SwiftUI
import HestiaShared

/// macOS onboarding flow — paste QR payload or manually enter server URL
struct MacOnboardingView: View {
    @ObservedObject var authService: AuthService
    @StateObject private var viewModel = OnboardingViewModel()
    @State private var pastedText = ""
    @State private var isConfigured = false

    var body: some View {
        ZStack {
            MacColors.windowBackground.ignoresSafeArea()

            switch viewModel.step {
            case .welcome:
                welcomeStep
            case .scanQR:
                pasteStep
            case .connecting:
                connectingStep
            case .success:
                successStep
            case .error(let message):
                errorStep(message: message)
            }
        }
        .onAppear {
            if !isConfigured {
                viewModel.configure(authService: authService, apiClientProvider: APIClientProvider())
                isConfigured = true
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
                viewModel.startScanning()
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
            .buttonStyle(.plain)

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
                    viewModel.goBack()
                } label: {
                    Text("Back")
                        .foregroundColor(MacColors.textSecondary)
                }
                .buttonStyle(.plain)

                Button {
                    viewModel.handleManualPayload(pastedText.trimmingCharacters(in: .whitespacesAndNewlines))
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
                .buttonStyle(.plain)
                .disabled(pastedText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
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

            if !viewModel.serverURL.isEmpty {
                Text(viewModel.serverURL)
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
                    viewModel.goBack()
                } label: {
                    Text("Back")
                        .foregroundColor(MacColors.textSecondary)
                }
                .buttonStyle(.plain)

                Button {
                    viewModel.retry()
                } label: {
                    Text("Try Again")
                        .font(.headline)
                        .foregroundColor(.white)
                        .frame(width: 120, height: 36)
                        .background(MacColors.amberAccent.opacity(0.3))
                        .cornerRadius(8)
                }
                .buttonStyle(.plain)
            }

            Spacer()
        }
    }
}
