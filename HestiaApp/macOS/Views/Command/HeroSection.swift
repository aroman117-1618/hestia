import SwiftUI
import HestiaShared

struct HeroSection: View {
    @ObservedObject var viewModel: MacCommandCenterViewModel
    @EnvironmentObject var appState: AppState

    var body: some View {
        HStack(alignment: .center) {
            leftSide
            Spacer()
            rightStats
        }
        .padding(.horizontal, MacSpacing.xxl)
        .padding(.vertical, MacSpacing.xl)
    }

    // MARK: - Left Side

    private var leftSide: some View {
        HStack(spacing: MacSpacing.lg) {
            avatar

            // Text + wavelength behind it
            ZStack(alignment: .leading) {
                // Wavelength fills this box, scaled down to fit
                HestiaWavelengthView(mode: .idle, waveScale: 0.25)
                    .allowsHitTesting(false)

                // Text on top
                VStack(alignment: .leading, spacing: MacSpacing.sm) {
                    Text(greetingText)
                        .font(.system(size: 20, weight: .semibold))
                        .foregroundStyle(MacColors.textPrimaryAlt)

                    Text(dateByline)
                        .font(.system(size: 11))
                        .foregroundStyle(MacColors.textSecondary)
                }
            }
            .frame(height: 80)
        }
    }

    private var avatar: some View {
        ZStack {
            Circle()
                .fill(MacColors.aiAvatarBackground)
                .frame(width: 64, height: 64)

            if let image = appState.currentMode.avatarImage {
                image
                    .resizable()
                    .scaledToFill()
                    .frame(width: 58, height: 58)
                    .clipShape(Circle())
            } else {
                Text(appState.currentMode.displayName.prefix(1))
                    .font(.system(size: 26, weight: .bold))
                    .foregroundStyle(MacColors.amberAccent)
            }
        }
        .overlay {
            Circle()
                .strokeBorder(
                    LinearGradient(
                        colors: [MacColors.amberAccent, Color(red: 191/255, green: 90/255, blue: 242/255)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: 2
                )
        }
        .shadow(color: MacColors.amberAccent.opacity(0.3), radius: 8, x: 0, y: 0)
    }

    // MARK: - Right Stats

    private var rightStats: some View {
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

    private var greetingText: String {
        let hour = Calendar.current.component(.hour, from: Date())
        if hour < 12 { return "Good morning, Andrew" }
        else if hour < 17 { return "Good afternoon, Andrew" }
        else { return "Good evening, Andrew" }
    }

    private var dateByline: String {
        let formatter = DateFormatter()
        formatter.dateFormat = "EEEE, MMMM d"
        return formatter.string(from: Date())
    }
}
