import SwiftUI
import HestiaShared

/// Lock screen shown when app times out
struct LockScreenView: View {
    // Use the shared AuthService from environment (source of truth)
    @EnvironmentObject var authService: AuthService
    @State private var isLoading = false
    @State private var error: HestiaError?
    @State private var showError = false

    let onUnlock: () -> Void

    var body: some View {
        ZStack {
            // Blurred background
            Color.bgBase.opacity(0.9)
                .ignoresSafeArea()

            VStack(spacing: Spacing.xl) {
                Spacer()

                // Lock icon
                Image(systemName: "lock.fill")
                    .font(.system(size: 60))
                    .foregroundColor(.textSecondary)

                // Message
                VStack(spacing: Spacing.sm) {
                    Text("Hestia is Locked")
                        .font(.title2.weight(.semibold))
                        .foregroundColor(.textPrimary)

                    Text("Authenticate to continue")
                        .font(.subheadline)
                        .foregroundColor(.textSecondary)
                }

                Spacer()

                // Unlock button
                Button {
                    Task {
                        await authenticate()
                    }
                } label: {
                    HStack(spacing: Spacing.sm) {
                        Image(systemName: authService.biometricType != .none ? authService.biometricType.iconName : "lock.open.fill")
                            .font(.system(size: 24))

                        Text("Authenticate")
                            .font(.buttonText)
                    }
                    .foregroundColor(.textPrimary)
                    .frame(maxWidth: .infinity)
                    .padding(Spacing.md)
                    .background(Color.bgOverlay)
                    .cornerRadius(CornerRadius.button)
                }
                .disabled(isLoading)
                .padding(.horizontal, Spacing.xl)

                Spacer()
                    .frame(height: Spacing.xxl)
            }

            // Loading state
            if isLoading {
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .accent))
                    .scaleEffect(1.5)
            }
        }
        .alert("Authentication Failed", isPresented: $showError) {
            Button("Try Again") {
                showError = false
                error = nil
            }
        } message: {
            Text(error?.userMessage ?? "Please try again")
        }
        .onAppear {
            // Auto-trigger authentication on appear
            Task {
                await authenticate()
            }
        }
        // Watch for changes in authService.isAuthenticated (the source of truth)
        .onChange(of: authService.isAuthenticated) { newValue in
            if newValue {
                onUnlock()
            }
        }
    }

    // MARK: - Private Methods

    private func authenticate() async {
        isLoading = true
        error = nil

        do {
            try await authService.authenticate()
            // After successful auth, authService.isAuthenticated will be true
            // The onChange modifier will trigger onUnlock()
        } catch let hestiaError as HestiaError {
            self.error = hestiaError
            self.showError = true
        } catch {
            self.error = .unknown(error.localizedDescription)
            self.showError = true
        }

        isLoading = false
    }
}

// MARK: - Preview

struct LockScreenView_Previews: PreviewProvider {
    static var previews: some View {
        LockScreenView(onUnlock: {})
            .environmentObject(AuthService())
    }
}
