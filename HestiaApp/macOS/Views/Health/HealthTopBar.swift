import SwiftUI
import HestiaShared

struct HealthTopBar: View {
    @ObservedObject var viewModel: MacHealthViewModel

    var body: some View {
        HStack {
            // Title
            Text("Health")
                .font(MacTypography.pageTitle)
                .foregroundStyle(.white)
                .tracking(0.45)

            Spacer()

            // Summary pills
            if viewModel.hasData {
                HStack(spacing: MacSpacing.md) {
                    metricPill(
                        icon: "figure.walk",
                        label: "Steps",
                        value: formatNumber(viewModel.steps)
                    )

                    Rectangle()
                        .fill(MacColors.healthGreen.opacity(0.2))
                        .frame(width: 1, height: 20)

                    metricPill(
                        icon: "flame.fill",
                        label: "Calories",
                        value: "\(viewModel.calories)"
                    )

                    Rectangle()
                        .fill(MacColors.healthGreen.opacity(0.2))
                        .frame(width: 1, height: 20)

                    metricPill(
                        icon: "heart.fill",
                        label: "HR",
                        value: viewModel.restingHR > 0 ? "\(viewModel.restingHR) bpm" : "--"
                    )
                }
                .padding(.horizontal, MacSpacing.lg)
                .padding(.vertical, MacSpacing.sm)
                .background(
                    LinearGradient(
                        colors: [
                            MacColors.healthGreen.opacity(0.1),
                            Color(red: 0/255, green: 212/255, blue: 146/255).opacity(0.04)
                        ],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .clipShape(Capsule())
                .overlay {
                    Capsule().strokeBorder(MacColors.healthGreen.opacity(0.15), lineWidth: 1)
                }
            }

            Spacer()

            // Sync info
            if let syncDate = viewModel.lastSyncDate {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "arrow.triangle.2.circlepath")
                        .font(.system(size: 11))
                        .foregroundStyle(MacColors.textSecondary)
                    Text("Synced \(syncDate)")
                        .font(MacTypography.smallBody)
                        .foregroundStyle(MacColors.textSecondary)
                }
            } else if !viewModel.hasData {
                HStack(spacing: MacSpacing.xs) {
                    Image(systemName: "iphone.and.arrow.forward")
                        .font(.system(size: 11))
                        .foregroundStyle(MacColors.textFaint)
                    Text("Sync from iPhone")
                        .font(MacTypography.smallBody)
                        .foregroundStyle(MacColors.textFaint)
                }
            }
        }
        .padding(.horizontal, MacSpacing.xxl)
        .frame(height: 52)
        .background(
            LinearGradient(
                colors: [
                    Color(red: 0/255, green: 50/255, blue: 35/255).opacity(0.4),
                    Color(red: 0/255, green: 212/255, blue: 146/255).opacity(0.05),
                    Color(red: 0/255, green: 50/255, blue: 35/255).opacity(0.4)
                ],
                startPoint: .leading,
                endPoint: .trailing
            )
        )
        .overlay(alignment: .bottom) {
            MacColors.cardBorderStrong.frame(height: 1)
        }
    }

    private func metricPill(icon: String, label: String, value: String) -> some View {
        HStack(spacing: MacSpacing.sm) {
            Image(systemName: icon)
                .font(.system(size: 14))
                .foregroundStyle(MacColors.healthGreen)
            Text(label + " ")
                .font(MacTypography.label)
                .foregroundStyle(.white)
            +
            Text(value)
                .font(.system(size: 18, weight: .medium))
                .foregroundStyle(MacColors.healthGold)
        }
    }

    private func formatNumber(_ n: Int) -> String {
        if n >= 1000 {
            let k = Double(n) / 1000.0
            return String(format: "%.1fk", k)
        }
        return "\(n)"
    }
}
