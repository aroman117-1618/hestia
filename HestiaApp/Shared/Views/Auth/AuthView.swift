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

                // Logo / Avatar
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

            // Loading overlay
            if viewModel.isLoading {
                LoadingOverlay(message: viewModel.isDeviceRegistered ? "Authenticating..." : "Setting up...")
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
            // Hestia avatar
            Circle()
                .fill(Color.white.opacity(0.2))
                .frame(width: Size.Avatar.xlarge, height: Size.Avatar.xlarge)
                .overlay(
                    Text("H")
                        .font(.system(size: 48, weight: .bold))
                        .foregroundColor(.white)
                )
                .shadow(color: .black.opacity(0.3), radius: 10, x: 0, y: 5)
        }
    }

    private var titleSection: some View {
        VStack(spacing: Spacing.sm) {
            Text("Hestia")
                .font(.greeting)
                .foregroundColor(.white)

            Text(viewModel.isDeviceRegistered ?
                 "Welcome back, Boss." :
                 "Your personal AI assistant")
                .font(.subheading)
                .foregroundColor(.white.opacity(0.8))
        }
    }

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

// MARK: - Preview

struct AuthView_Previews: PreviewProvider {
    static var previews: some View {
        AuthView()
            .environmentObject(AuthService())
            .environmentObject(APIClientProvider())
    }
}
