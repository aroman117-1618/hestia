import SwiftUI
import HestiaShared

struct LearningMetricsPanel: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    var body: some View {
        VStack(alignment: .leading, spacing: MacSpacing.md) {
            // Section header
            HStack {
                Image(systemName: "chart.line.uptrend.xyaxis")
                    .foregroundStyle(MacColors.amberAccent)
                Text("Learning Metrics")
                    .font(MacTypography.cardSubtitle)
                    .foregroundStyle(MacColors.textPrimary)
                Spacer()
                if viewModel.unacknowledgedAlertCount > 0 {
                    alertBadge
                }
            }

            // Metrics grid: 2x2
            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: MacSpacing.md) {
                metricCard(
                    icon: "face.smiling",
                    label: "Positive Ratio",
                    value: "\(viewModel.positiveRatioPercent)%",
                    color: viewModel.positiveRatioPercent > 70 ? MacColors.healthGreen : MacColors.healthAmber
                )
                metricCard(
                    icon: "brain",
                    label: "Memory Chunks",
                    value: "\(viewModel.memoryChunkCount)",
                    color: MacColors.textSecondary
                )
                metricCard(
                    icon: "doc.on.doc",
                    label: "Redundancy",
                    value: String(format: "%.1f%%", viewModel.memoryRedundancyPct),
                    color: viewModel.memoryRedundancyPct > 20 ? MacColors.healthRed : MacColors.healthGreen
                )
                metricCard(
                    icon: "bolt.trianglebadge.exclamationmark",
                    label: "Alerts",
                    value: "\(viewModel.unacknowledgedAlertCount)",
                    color: viewModel.unacknowledgedAlertCount > 0 ? MacColors.healthRed : MacColors.healthGreen
                )
            }
        }
        .padding(MacSpacing.lg)
        .background(MacColors.cardGradient)
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.panel)
                .strokeBorder(MacColors.cardBorder, lineWidth: 1)
        }
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.panel))
    }

    // MARK: - Metric Card

    private func metricCard(icon: String, label: String, value: String, color: Color) -> some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: icon)
                    .font(.system(size: 12))
                    .foregroundStyle(color)
                Text(label)
                    .font(MacTypography.caption)
                    .foregroundStyle(MacColors.textSecondary)
            }
            Text(value)
                .font(.system(size: 18, weight: .bold))
                .foregroundStyle(MacColors.textPrimary)

            // Colored accent bar
            RoundedRectangle(cornerRadius: 1)
                .fill(color.opacity(0.4))
                .frame(height: 2)
        }
        .padding(MacSpacing.md)
        .background(MacColors.searchInputBackground)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
    }

    // MARK: - Alert Badge

    private var alertBadge: some View {
        HStack(spacing: MacSpacing.xs) {
            Circle()
                .fill(MacColors.healthRed)
                .frame(width: 8, height: 8)
            Text("\(viewModel.unacknowledgedAlertCount) alert\(viewModel.unacknowledgedAlertCount == 1 ? "" : "s")")
                .font(MacTypography.captionMedium)
                .foregroundStyle(MacColors.healthRed)
        }
        .padding(.horizontal, MacSpacing.sm)
        .padding(.vertical, MacSpacing.xs)
        .background(MacColors.healthRedBg)
        .clipShape(RoundedRectangle(cornerRadius: MacCornerRadius.search))
        .overlay {
            RoundedRectangle(cornerRadius: MacCornerRadius.search)
                .strokeBorder(MacColors.healthRedBorder, lineWidth: 1)
        }
    }
}
