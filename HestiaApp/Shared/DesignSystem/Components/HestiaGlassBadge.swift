import SwiftUI

/// Status indicator badge with glowing dot and tinted background.
struct HestiaGlassBadge: View {
    let status: Status
    let label: String

    enum Status {
        case healthy, warning, error, neutral, info

        var color: Color {
            #if os(macOS)
            switch self {
            case .healthy: return MacColors.statusGreen
            case .warning: return MacColors.statusWarning
            case .error: return MacColors.statusCritical
            case .neutral: return MacColors.textPlaceholder
            case .info: return MacColors.statusInfo
            }
            #else
            switch self {
            case .healthy: return Color.healthyGreen
            case .warning: return Color.warningYellow
            case .error: return Color.errorRed
            case .neutral: return Color.white.opacity(0.4)
            case .info: return Color.agentAmber
            }
            #endif
        }
    }

    var body: some View {
        HStack(spacing: GlassSpacing.xs) {
            Circle()
                .fill(status.color)
                .frame(width: 8, height: 8)
                .shadow(color: status.color.opacity(0.6), radius: 2)

            Text(label)
                .font(.system(size: 12))
                .foregroundStyle(status.color)
        }
        .padding(.vertical, 4)
        .padding(.horizontal, 8)
        .background(status.color.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: GlassRadius.sm))
    }
}

// MARK: - Preview

#Preview {
    VStack(spacing: 12) {
        HestiaGlassBadge(status: .healthy, label: "Online")
        HestiaGlassBadge(status: .warning, label: "Degraded")
        HestiaGlassBadge(status: .error, label: "Offline")
        HestiaGlassBadge(status: .neutral, label: "Unknown")
        HestiaGlassBadge(status: .info, label: "Syncing")
    }
    .padding()
    .background(Color.black)
}
