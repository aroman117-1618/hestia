import SwiftUI
import HestiaShared

/// Colored status badge — green/amber/red dot + text label.
struct HestiaStatusBadge: View {
    let text: String
    let status: Status

    enum Status {
        case healthy, warning, error, neutral

        var color: Color {
            switch self {
            case .healthy: return .healthyGreen
            case .warning: return .warningYellow
            case .error: return .errorRed
            case .neutral: return .white.opacity(0.4)
            }
        }
    }

    var body: some View {
        HStack(spacing: Spacing.xs) {
            Circle()
                .fill(status.color)
                .frame(width: 8, height: 8)
            Text(text)
                .font(.caption.weight(.medium))
                .foregroundColor(status.color)
        }
        .padding(.horizontal, Spacing.sm)
        .padding(.vertical, Spacing.xs)
        .background(status.color.opacity(0.1))
        .cornerRadius(CornerRadius.small)
    }
}
