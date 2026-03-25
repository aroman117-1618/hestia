#if os(iOS)
import SwiftUI
import HestiaShared
import AuthenticationServices

/// Redesigned onboarding: dark atmospheric background, animated orb,
/// Apple Sign In, smart server URL pre-fill, QR fallback.
struct OnboardingView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @StateObject private var viewModel = OnboardingViewModel()
    @State private var isConfigured = false
    @State private var showQRScanner = false
    @State private var successOffset: CGFloat = 0
    @State private var successOpacity: Double = 1.0

    var body: some View {
        GeometryReader { geo in
            ZStack {
                OnboardingBackground()

                switch viewModel.step {
                case .welcome:
                    welcomeStep(geo: geo)
                        .transition(.opacity)

                case .appleSignIn:
                    appleSignInStep(geo: geo)
                        .transition(.opacity)

                case .serverURL:
                    serverURLStep(geo: geo)
                        .transition(.opacity)

                case .connecting:
                    connectingStep(geo: geo)
                        .transition(.opacity)

                case .success:
                    successStep(geo: geo)
                        .transition(.opacity)

                case .error(let message):
                    errorStep(message: message, geo: geo)
                        .transition(.opacity)
                }
            }
            .animation(.easeInOut(duration: 0.4), value: viewModel.step)
        }
        .onAppear {
            if !isConfigured {
                viewModel.configure(authService: authService, apiClientProvider: apiClientProvider)
                isConfigured = true
            }
        }
        .sheet(isPresented: $showQRScanner) {
            QRScannerView { code in
                showQRScanner = false
                viewModel.handleScannedCode(code)
            }
        }
    }

    // MARK: - Welcome Step

    private func welcomeStep(geo: GeometryProxy) -> some View {
        VStack(spacing: 0) {
            Spacer()
                .frame(height: geo.size.height * 0.15)

            // Orb — centered in upper portion
            HestiaOrbView(state: viewModel.orbState, size: 150)
                .frame(height: geo.size.height * 0.35)

            // Title area
            VStack(spacing: Spacing.sm) {
                Text("Hestia")
                    .font(.system(size: 38, weight: .bold))
                    .foregroundColor(.white)

                Text("Your personal AI assistant")
                    .font(.system(size: 16))
                    .foregroundColor(.white.opacity(0.4))
            }

            Spacer()

            // Get Started button — Liquid Glass pill
            liquidGlassButton(title: "Get Started") {
                viewModel.getStartedTapped()
            }
            .padding(.bottom, geo.safeAreaInsets.bottom + 60)
        }
        .padding(.horizontal, Spacing.xl)
    }

    // MARK: - Apple Sign In Step

    private func appleSignInStep(geo: GeometryProxy) -> some View {
        ZStack {
            // Same layout as welcome, dimmed slightly
            VStack(spacing: 0) {
                Spacer()
                    .frame(height: geo.size.height * 0.15)

                HestiaOrbView(state: viewModel.orbState, size: 150)
                    .frame(height: geo.size.height * 0.35)

                VStack(spacing: Spacing.sm) {
                    Text("Hestia")
                        .font(.system(size: 38, weight: .bold))
                        .foregroundColor(.white)

                    Text("Your personal AI assistant")
                        .font(.system(size: 16))
                        .foregroundColor(.white.opacity(0.4))
                }

                Spacer()
            }
            .padding(.horizontal, Spacing.xl)

            // Apple Sign In overlay at bottom
            VStack {
                Spacer()

                VStack(spacing: Spacing.md) {
                    Text("Sign in to get started")
                        .font(.system(size: 15))
                        .foregroundColor(.white.opacity(0.5))

                    SignInWithAppleButton(.signIn) { request in
                        request.requestedScopes = [.email, .fullName]
                    } onCompletion: { result in
                        viewModel.handleAppleSignIn(result: result)
                    }
                    .signInWithAppleButtonStyle(.white)
                    .frame(height: 50)
                    .cornerRadius(25)
                    .padding(.horizontal, 40)

                    Button {
                        viewModel.goBack()
                    } label: {
                        Text("Cancel")
                            .font(.system(size: 15))
                            .foregroundColor(.white.opacity(0.4))
                    }
                    .padding(.top, Spacing.sm)
                }
                .padding(.bottom, geo.safeAreaInsets.bottom + 60)
            }
        }
    }

    // MARK: - Server URL Step

    private func serverURLStep(geo: GeometryProxy) -> some View {
        VStack(spacing: 0) {
            Spacer()
                .frame(height: geo.size.height * 0.15)

            HestiaOrbView(state: .idle, size: 120)
                .frame(height: geo.size.height * 0.28)

            VStack(spacing: Spacing.sm) {
                Text("Connect to Server")
                    .font(.system(size: 28, weight: .bold))
                    .foregroundColor(.white)

                Text("Enter your Hestia server address")
                    .font(.system(size: 15))
                    .foregroundColor(.white.opacity(0.4))
            }

            Spacer()
                .frame(height: Spacing.xl)

            // Frosted glass text field
            HStack {
                Image(systemName: "link")
                    .foregroundColor(.white.opacity(0.4))
                    .font(.system(size: 15))

                TextField("https://hestia-3.local:8443", text: $viewModel.serverURL)
                    .foregroundColor(.white)
                    .font(.system(size: 16, design: .monospaced))
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .keyboardType(.URL)
                    .textContentType(.URL)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 14)
                    .fill(Color.white.opacity(0.07))
                    .overlay(
                        RoundedRectangle(cornerRadius: 14)
                            .stroke(Color.white.opacity(0.12), lineWidth: 1)
                    )
            )
            .padding(.horizontal, Spacing.xl)

            Spacer()

            VStack(spacing: Spacing.md) {
                // Connect button
                liquidGlassButton(title: "Connect") {
                    viewModel.connectToServer()
                }

                // QR fallback
                Button {
                    showQRScanner = true
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "qrcode.viewfinder")
                            .font(.system(size: 14))
                        Text("Scan QR code instead")
                            .font(.system(size: 14))
                    }
                    .foregroundColor(.white.opacity(0.35))
                }
            }
            .padding(.bottom, geo.safeAreaInsets.bottom + 60)
        }
        .padding(.horizontal, Spacing.xl)
    }

    // MARK: - Connecting Step

    private func connectingStep(geo: GeometryProxy) -> some View {
        VStack(spacing: 0) {
            Spacer()
                .frame(height: geo.size.height * 0.2)

            HestiaOrbView(state: .thinking, size: 150)
                .frame(height: geo.size.height * 0.35)

            SnarkyBylineView(isRegistration: true)
                .padding(.bottom, Spacing.md)

            if !viewModel.serverURL.isEmpty {
                Text(viewModel.serverURL)
                    .font(.system(size: 13, design: .monospaced))
                    .foregroundColor(.white.opacity(0.3))
            }

            Spacer()
        }
    }

    // MARK: - Success Step

    private func successStep(geo: GeometryProxy) -> some View {
        VStack(spacing: 0) {
            Spacer()
                .frame(height: geo.size.height * 0.2)

            HestiaOrbView(state: .success, size: 150)
                .frame(height: geo.size.height * 0.35)
                .offset(y: successOffset)
                .opacity(successOpacity)

            Text("Connected")
                .font(.system(size: 28, weight: .bold))
                .foregroundColor(.white)
                .opacity(successOpacity)

            Spacer()
        }
        .onAppear {
            // After a brief pause, animate the orb upward and fade
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
                withAnimation(.easeIn(duration: 0.8)) {
                    successOffset = -geo.size.height
                    successOpacity = 0
                }
            }
        }
    }

    // MARK: - Error Step

    private func errorStep(message: String, geo: GeometryProxy) -> some View {
        VStack(spacing: 0) {
            Spacer()
                .frame(height: geo.size.height * 0.15)

            HestiaOrbView(state: .idle, size: 120)
                .frame(height: geo.size.height * 0.28)

            VStack(spacing: Spacing.sm) {
                Text("Connection Failed")
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(.white)

                Text(message)
                    .font(.system(size: 15))
                    .foregroundColor(.white.opacity(0.5))
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, Spacing.lg)
            }

            Spacer()

            VStack(spacing: Spacing.md) {
                liquidGlassButton(title: "Try Again") {
                    viewModel.retry()
                }

                Button {
                    viewModel.goBack()
                } label: {
                    Text("Back")
                        .font(.system(size: 15))
                        .foregroundColor(.white.opacity(0.4))
                }
            }
            .padding(.bottom, geo.safeAreaInsets.bottom + 60)
        }
        .padding(.horizontal, Spacing.xl)
    }

    // MARK: - Liquid Glass Button

    private func liquidGlassButton(title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 17, weight: .semibold))
                .foregroundColor(.white.opacity(0.95))
                .padding(.horizontal, 48)
                .padding(.vertical, 16)
                .background(
                    Capsule()
                        .fill(.ultraThinMaterial)
                        .overlay(
                            Capsule()
                                .fill(Color.white.opacity(0.08))
                        )
                        .overlay(
                            Capsule()
                                .stroke(
                                    LinearGradient(
                                        colors: [
                                            Color.white.opacity(0.18),
                                            Color.white.opacity(0.12),
                                            Color.white.opacity(0.06),
                                        ],
                                        startPoint: .top,
                                        endPoint: .bottom
                                    ),
                                    lineWidth: 1
                                )
                        )
                )
                .shadow(color: .black.opacity(0.3), radius: 12, x: 0, y: 4)
        }
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
