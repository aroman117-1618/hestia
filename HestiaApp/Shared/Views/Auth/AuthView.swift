import SwiftUI

/// Initial authentication / device registration view
struct AuthView: View {
    @EnvironmentObject var authService: AuthService
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @StateObject private var viewModel = AuthViewModel()
    @State private var showingSetup = false
    @State private var isConfigured = false

    var body: some View {
        ZStack {
            // Background
            StaticGradientBackground(mode: .tia)

            VStack(spacing: Spacing.xl) {
                Spacer()

                // Logo / Avatar — Lottie AI Blob
                avatarSection

                // Title
                titleSection

                Spacer()

                // Action button
                if viewModel.isDeviceRegistered {
                    authenticateButton
                } else {
                    setupButton
                }

                Spacer()
                    .frame(height: Spacing.xxl)
            }
            .padding(.horizontal, Spacing.xl)

            // Loading overlay — Lottie animation + snarky rotating bylines
            if viewModel.isLoading {
                snarkyLoadingOverlay
            }
        }
        .alert("Authentication Error", isPresented: $viewModel.showError) {
            Button("OK") {
                viewModel.dismissError()
            }
        } message: {
            Text(viewModel.error?.userMessage ?? "An error occurred")
        }
        .onAppear {
            // Configure viewModel with environment services (once)
            if !isConfigured {
                viewModel.configure(authService: authService, apiClientProvider: apiClientProvider)
                isConfigured = true
            }
            viewModel.checkAuthState()
        }
    }

    // MARK: - Sections

    private var avatarSection: some View {
        VStack(spacing: Spacing.md) {
            // Lottie AI Blob — morphing, organic, alive
            LottieView(
                animationName: "ai_blob",
                fallbackSymbol: "brain.head.profile",
                fallbackColor: .white.opacity(0.6)
            )
            .frame(width: Size.Avatar.xlarge, height: Size.Avatar.xlarge)
            .shadow(color: .black.opacity(0.3), radius: 10, x: 0, y: 5)
        }
    }

    private var titleSection: some View {
        VStack(spacing: Spacing.sm) {
            Text("Hestia")
                .font(.greeting)
                .foregroundColor(.white)

            // Only show byline for returning users
            if viewModel.isDeviceRegistered {
                Text("Welcome back, Boss.")
                    .font(.subheading)
                    .foregroundColor(.white.opacity(0.8))
            }
        }
    }

    // MARK: - Snarky Loading Overlay

    /// Rotating snarky bylines during authentication/registration
    private var snarkyLoadingOverlay: some View {
        ZStack {
            // Dim background
            Color.black.opacity(0.7)
                .ignoresSafeArea()

            VStack(spacing: Spacing.lg) {
                // Lottie animation
                LottieView(
                    animationName: "ai_blob",
                    speed: 1.5,
                    fallbackSymbol: "brain.head.profile"
                )
                .frame(width: 120, height: 120)

                // Rotating snarky bylines using TimelineView for auto-cleanup
                SnarkyBylineView(
                    isRegistration: !viewModel.isDeviceRegistered
                )
            }
        }
        .transition(.opacity)
    }

    // MARK: - Buttons

    private var authenticateButton: some View {
        Button {
            Task {
                await viewModel.authenticate()
            }
        } label: {
            HStack(spacing: Spacing.sm) {
                Image(systemName: viewModel.biometricType.iconName)
                    .font(.system(size: 24))

                Text("Unlock with \(viewModel.biometricType.displayName)")
                    .font(.buttonText)
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(Spacing.md)
            .background(Color.white.opacity(0.2))
            .cornerRadius(CornerRadius.button)
        }
        .disabled(viewModel.isLoading)
        .accessibilityLabel("Unlock with \(viewModel.biometricType.displayName)")
    }

    private var setupButton: some View {
        Button {
            Task {
                await viewModel.registerDevice()
            }
        } label: {
            HStack(spacing: Spacing.sm) {
                Image(systemName: "arrow.right.circle.fill")
                    .font(.system(size: 24))

                Text("Get Started")
                    .font(.buttonText)
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(Spacing.md)
            .background(Color.white.opacity(0.2))
            .cornerRadius(CornerRadius.button)
        }
        .disabled(viewModel.isLoading)
        .accessibilityLabel("Get started with Hestia")
    }
}

// MARK: - Snarky Byline View (TimelineView for auto-cleanup)

/// Rotates through snarky loading messages using TimelineView
struct SnarkyBylineView: View {
    let isRegistration: Bool

    private let authBylines = [
        "Authenticating...",
        "Debating...",
        "Grabbing groceries...",
        "Scrolling Instagram...",
        "Consulting the council...",
        "Warming up neurons...",
        "Checking your vibe...",
        "Reticulating splines...",
    ]

    private let setupBylines = [
        "Setting up...",
        "Unpacking boxes...",
        "Reading the manual...",
        "Calibrating sass levels...",
        "Brewing coffee...",
        "Almost there...",
    ]

    private var bylines: [String] {
        isRegistration ? setupBylines : authBylines
    }

    @State private var currentIndex = 0

    var body: some View {
        TimelineView(.periodic(from: .now, by: 2.5)) { timeline in
            Text(bylines[currentIndex % bylines.count])
                .font(.subheadline)
                .foregroundColor(.white.opacity(0.8))
                .animation(.easeInOut(duration: 0.3), value: currentIndex)
                .onChange(of: timeline.date) { _ in
                    currentIndex += 1
                }
        }
    }
}

// MARK: - Preview

struct AuthView_Previews: PreviewProvider {
    static var previews: some View {
        AuthView()
            .environmentObject(AuthService())
            .environmentObject(APIClientProvider())
    }
}
