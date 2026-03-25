import SwiftUI

// MARK: - Global Error Banner

/// Slide-down error banner displayed at the top of the content area.
/// Auto-dismisses after 4 seconds or on manual dismiss.
struct GlobalErrorBanner: View {
    @Environment(ErrorState.self) private var errorState

    var body: some View {
        if let error = errorState.currentError {
            HStack(spacing: MacSpacing.md) {
                Image(systemName: error.icon)
                    .font(MacTypography.sectionTitle)
                    .foregroundStyle(error.accentColor)

                Text(error.message)
                    .font(MacTypography.body)
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(2)

                Spacer()

                Button {
                    errorState.dismiss()
                } label: {
                    Image(systemName: "xmark")
                        .font(MacTypography.smallMedium)
                        .foregroundStyle(MacColors.textSecondary)
                        .frame(width: 24, height: 24)
                        .background(MacColors.searchInputBackground)
                        .clipShape(Circle())
                }
                .buttonStyle(.hestiaIcon)
                .accessibilityLabel("Dismiss error")
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.vertical, MacSpacing.md)
            .background {
                RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                    .fill(MacColors.panelBackground)
                    .overlay {
                        RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                            .strokeBorder(error.accentColor.opacity(0.4), lineWidth: 1)
                    }
                    .shadow(color: error.accentColor.opacity(0.15), radius: 8, y: 4)
            }
            .padding(.horizontal, MacSpacing.xxl)
            .padding(.top, MacSpacing.md)
            .transition(.move(edge: .top).combined(with: .opacity))
        }
    }
}
