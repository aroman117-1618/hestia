import SwiftUI
import HestiaShared

/// Persistent banner shown at the top of the content area when the server is unreachable.
/// Unlike `GlobalErrorBanner` (transient errors with auto-dismiss), this stays visible
/// for the entire duration of the disconnection.
///
/// Two states:
/// - **Offline + has cached data** → amber "Showing cached data from X ago"
/// - **Offline + no cache** → red "Server unreachable — check your connection"
struct OfflineBanner: View {
    @EnvironmentObject var networkMonitor: NetworkMonitor

    /// Whether any cached data exists (set by parent view based on ViewModel state).
    var hasCachedData: Bool = false

    /// When the cache was last updated (for "X ago" display).
    var lastCacheDate: Date?

    var body: some View {
        if !networkMonitor.isConnected {
            HStack(spacing: MacSpacing.md) {
                Image(systemName: hasCachedData ? "clock.arrow.circlepath" : "wifi.slash")
                    .font(MacTypography.body)
                    .foregroundStyle(bannerColor)
                Text(bannerText)
                    .font(MacTypography.label)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
            }
            .padding(.horizontal, MacSpacing.xl)
            .padding(.vertical, MacSpacing.sm)
            .background(bannerColor.opacity(0.15))
            .transition(.move(edge: .top).combined(with: .opacity))
        }
    }

    private var bannerColor: Color {
        hasCachedData ? MacColors.amberAccent : MacColors.calorieRed
    }

    private var bannerText: String {
        if hasCachedData {
            if let lastCacheDate {
                let formatter = RelativeDateTimeFormatter()
                formatter.unitsStyle = .short
                let ago = formatter.localizedString(for: lastCacheDate, relativeTo: Date())
                return "Offline — showing cached data from \(ago)"
            }
            return "Offline — showing cached data"
        }
        return "Server unreachable — check your connection"
    }
}
