#if os(iOS)
import SwiftUI
import HestiaShared

/// Multi-step onboarding flow for new device registration via QR code (iOS)
struct OnboardingView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @StateObject private var viewModel = OnboardingViewModel()
    @State private var isConfigured = false

    var body: some View {
        ZStack {
            StaticGradientBackground(mode: .tia)

            switch viewModel.step {
            case .welcome:
                welcomeStep

            case .scanQR:
                scanStep

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
                viewModel.configure(authService: authService, apiClientProvider: apiClientProvider)
                isConfigured = true
            }
        }
    }

    // MARK: - Welcome Step

    private var welcomeStep: some View {
        VStack(spacing: Spacing.xl) {
            Spacer()

            LottieView(
                animationName: "ai_blob",
                fallbackSymbol: "brain.head.profile",
                fallbackColor: .white.opacity(0.6)
            )
            .frame(width: Size.Avatar.xlarge, height: Size.Avatar.xlarge)
            .shadow(color: .black.opacity(0.3), radius: 10, x: 0, y: 5)

            VStack(spacing: Spacing.sm) {
                Text("Hestia")
                    .font(.greeting)
                    .foregroundColor(.white)

                Text("Your personal AI assistant")
                    .font(.subheading)
                    .foregroundColor(.white.opacity(0.8))
            }

            Spacer()

            VStack(spacing: Spacing.md) {
                Text("Scan the QR code from your Hestia server to get started.")
                    .font(.body)
                    .foregroundColor(.white.opacity(0.7))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.lg)

                Button {
                    viewModel.startScanning()
                } label: {
                    HStack(spacing: Spacing.sm) {
                        Image(systemName: "qrcode.viewfinder")
                            .font(.system(size: 24))
                        Text("Scan QR Code")
                            .font(.buttonText)
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(Spacing.md)
                    .background(Color.white.opacity(0.2))
                    .cornerRadius(CornerRadius.button)
                }
                .accessibilityLabel("Scan QR code to connect to Hestia server")
            }

            Spacer()
                .frame(height: Spacing.xxl)
        }
        .padding(.horizontal, Spacing.xl)
    }

    // MARK: - Scan Step

    private var scanStep: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Button {
                    viewModel.goBack()
                } label: {
                    Image(systemName: "chevron.left")
                        .font(.system(size: 18, weight: .medium))
                        .foregroundColor(.white)
                }
                .accessibilityLabel("Go back")

                Spacer()

                Text("Scan QR Code")
                    .font(.headline)
                    .foregroundColor(.white)

                Spacer()

                // Balance the back button
                Color.clear.frame(width: 18, height: 18)
            }
            .padding(.horizontal, Spacing.lg)
            .padding(.vertical, Spacing.md)

            // Camera viewfinder
            ZStack {
                QRScannerView { code in
                    viewModel.handleScannedCode(code)
                }
                .cornerRadius(CornerRadius.large)

                // Viewfinder overlay
                RoundedRectangle(cornerRadius: CornerRadius.large)
                    .stroke(Color.white.opacity(0.3), lineWidth: 2)
            }
            .padding(.horizontal, Spacing.lg)

            // Instructions
            Text("Point your camera at the QR code displayed on your Hestia server")
                .font(.footnote)
                .foregroundColor(.white.opacity(0.6))
                .multilineTextAlignment(.center)
                .padding(.horizontal, Spacing.xl)
                .padding(.vertical, Spacing.lg)

            Spacer()
        }
    }

    // MARK: - Connecting Step

    private var connectingStep: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            LottieView(
                animationName: "ai_blob",
                speed: 1.5,
                fallbackSymbol: "brain.head.profile"
            )
            .frame(width: 120, height: 120)

            SnarkyBylineView(isRegistration: true)

            if !viewModel.serverURL.isEmpty {
                Text("Connecting to \(viewModel.serverURL)")
                    .font(.caption)
                    .foregroundColor(.white.opacity(0.5))
            }

            Spacer()
        }
    }

    // MARK: - Success Step

    private var successStep: some View {
        VStack(spacing: Spacing.xl) {
            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundColor(.healthyGreen)
                .shadow(color: Color.healthyGreen.opacity(0.4), radius: 20)

            VStack(spacing: Spacing.sm) {
                Text("Connected")
                    .font(.greeting)
                    .foregroundColor(.white)

                Text("Your device is registered with Hestia")
                    .font(.subheading)
                    .foregroundColor(.white.opacity(0.8))
            }

            Spacer()

            Button {
                Task {
                    try? await authService.authenticate()
                }
            } label: {
                HStack(spacing: Spacing.sm) {
                    Image(systemName: authService.biometricType.iconName)
                        .font(.system(size: 24))
                    Text("Continue")
                        .font(.buttonText)
                }
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(Spacing.md)
                .background(Color.white.opacity(0.2))
                .cornerRadius(CornerRadius.button)
            }
            .accessibilityLabel("Continue to Hestia")

            Spacer()
                .frame(height: Spacing.xxl)
        }
        .padding(.horizontal, Spacing.xl)
    }

    // MARK: - Error Step

    private func errorStep(message: String) -> some View {
        VStack(spacing: Spacing.xl) {
            Spacer()

            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 60))
                .foregroundColor(.warningYellow)

            VStack(spacing: Spacing.sm) {
                Text("Connection Failed")
                    .font(.title2.bold())
                    .foregroundColor(.white)

                Text(message)
                    .font(.body)
                    .foregroundColor(.white.opacity(0.7))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.lg)
            }

            Spacer()

            VStack(spacing: Spacing.md) {
                Button {
                    viewModel.retry()
                } label: {
                    HStack(spacing: Spacing.sm) {
                        Image(systemName: "arrow.counterclockwise")
                            .font(.system(size: 20))
                        Text("Try Again")
                            .font(.buttonText)
                    }
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(Spacing.md)
                    .background(Color.white.opacity(0.2))
                    .cornerRadius(CornerRadius.button)
                }

                Button {
                    viewModel.goBack()
                } label: {
                    Text("Back")
                        .font(.body)
                        .foregroundColor(.white.opacity(0.6))
                }
            }

            Spacer()
                .frame(height: Spacing.xxl)
        }
        .padding(.horizontal, Spacing.xl)
    }
}

// MARK: - Preview

struct OnboardingView_Previews: PreviewProvider {
    static var previews: some View {
        OnboardingView()
            .environmentObject(AuthService())
            .environmentObject(APIClientProvider())
    }
}
#endif
