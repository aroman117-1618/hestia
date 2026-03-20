import SwiftUI
import HestiaShared

/// Persistent banner shown at the top of the content area when the server is unreachable.
/// Unlike `GlobalErrorBanner` (transient errors with auto-dismiss), this stays visible
/// for the entire duration of the disconnection.
struct OfflineBanner: View {
    @EnvironmentObject var networkMonitor: NetworkMonitor

    var body: some View {
        if !networkMonitor.isConnected {
            HStack(spacing: MacSpacing.md) {
                Image(systemName: "wifi.slash")
                    .font(.system(size: 14))
                    .foregroundStyle(MacColors.calorieRed)
                Text("Server unreachable — check your connection")
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.vertical, MacSpacing.sm)
            .background(MacColors.calorieRed.opacity(0.15))
            .transition(.move(edge: .top).combined(with: .opacity))
        }
    }
}
