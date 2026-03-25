import SwiftUI
import HestiaShared

/// Inline error message
struct ErrorBanner: View {
    let error: HestiaError
    let onDismiss: () -> Void
    let onRetry: (() -> Void)?

    var body: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundColor(.errorRed)

            Text(error.userMessage)
                .font(.subheadline)
                .foregroundColor(.textPrimary)
                .lineLimit(2)

            Spacer()

            if error.isRetryable, let retry = onRetry {
                Button("Retry") {
                    retry()
                }
                .font(.subheadline.weight(.semibold))
                .foregroundColor(.textPrimary)
            }

            Button {
                onDismiss()
            } label: {
                Image(systemName: "xmark")
                    .foregroundColor(.textSecondary)
            }
        }
        .padding(Spacing.md)
        .background(Color.errorRed.opacity(0.3))
        .cornerRadius(CornerRadius.small)
        .padding(.horizontal, Spacing.md)
    }
}

/// Full-screen error view
struct ErrorScreen: View {
    let error: HestiaError
    let onRetry: (() -> Void)?
    let onDismiss: () -> Void

    var body: some View {
        VStack(spacing: Spacing.lg) {
            Spacer()

            // Error icon
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 60))
                .foregroundColor(.errorRed)

            // Error message
            Text(error.userMessage)
                .font(.headline)
                .foregroundColor(.textPrimary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, Spacing.xl)

            // Action buttons
            VStack(spacing: Spacing.md) {
                if error.isRetryable, let retry = onRetry {
                    Button {
                        retry()
                    } label: {
                        Text("Try Again")
                            .font(.buttonText)
                            .foregroundColor(.textPrimary)
                            .frame(maxWidth: .infinity)
                            .padding(Spacing.md)
                            .background(Color.bgOverlay)
                            .cornerRadius(CornerRadius.button)
                    }
                }

                Button {
                    onDismiss()
                } label: {
                    Text("Dismiss")
                        .font(.buttonText)
                        .foregroundColor(.textSecondary)
                }
            }
            .padding(.horizontal, Spacing.xl)

            Spacer()
        }
    }
}

/// Network offline indicator
struct OfflineBanner: View {
    var body: some View {
        HStack(spacing: Spacing.sm) {
            Image(systemName: "wifi.slash")
                .foregroundColor(.warningYellow)

            Text("No connection")
                .font(.subheadline)
                .foregroundColor(.textPrimary)

            Spacer()
        }
        .padding(Spacing.sm)
        .background(Color.bgBase.opacity(0.6))
    }
}

// MARK: - Preview

struct ErrorView_Previews: PreviewProvider {
    static var previews: some View {
        ZStack {
            Color.black.ignoresSafeArea()

            VStack(spacing: 40) {
                ErrorBanner(
                    error: .networkUnavailable,
                    onDismiss: {},
                    onRetry: {}
                )

                ErrorBanner(
                    error: .modelUnavailable,
                    onDismiss: {},
                    onRetry: nil
                )

                OfflineBanner()
            }
        }
    }
}
