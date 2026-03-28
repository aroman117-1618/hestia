import SwiftUI
import HestiaShared

struct HeroSection: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel

    var body: some View {
        HStack(alignment: .center) {
            wavelengthHero
            Spacer(minLength: MacSpacing.lg)
            rightStats
        }
        .padding(.horizontal, MacSpacing.xxl)
        .padding(.vertical, MacSpacing.xl)
    }

    // MARK: - Wavelength Hero

    private var wavelengthHero: some View {
        HestiaWavelengthView(mode: .idle, waveScale: 0.25)
            .frame(height: 40)
            .frame(maxWidth: .infinity)
            .allowsHitTesting(false)
    }

    // MARK: - Right Stats

    private var rightStats: some View {
        VStack(alignment: .trailing, spacing: MacSpacing.sm) {
        HStack(spacing: MacSpacing.lg) {
            statColumn(
                value: viewModel.tradingPnLDisplay,
                label: "P&L",
                valueColor: viewModel.tradingPnL >= 0 ? MacColors.healthGreen : MacColors.healthRed
            )

            statDivider

            statColumn(
                value: "\(viewModel.activeBotCount)",
                label: "Bots",
                valueColor: MacColors.textPrimaryAlt
            )

            statDivider

            statColumn(
                value: "\(viewModel.totalFills)",
                label: "Fills",
                valueColor: MacColors.textPrimaryAlt
            )

            statDivider

            statColumn(
                value: "\(viewModel.alertCount)",
                label: "Alerts",
                valueColor: viewModel.alertCount > 0 ? MacColors.amberAccent : MacColors.textPrimaryAlt
            )
        }

            Text(dateByline)
                .font(.system(size: 11))
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    private func statColumn(value: String, label: String, valueColor: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(valueColor)
            Text(label)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
        }
    }

    private var statDivider: some View {
        Rectangle()
            .fill(MacColors.textSecondary.opacity(0.3))
            .frame(width: 0.5, height: 28)
    }

    // MARK: - Computed Text

    private var dateByline: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d"
        return formatter.string(from: Date())
    }
}
