import SwiftUI

struct SystemAlertsTabView: View {
    @StateObject private var viewModel = SystemAlertsTabViewModel()

    private let cardBackground = Color(red: 17/255, green: 11/255, blue: 3/255)
    private let cardBorder = Color(red: 26/255, green: 20/255, blue: 8/255)

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: MacSpacing.xl) {
                successSection
                errorsSection
                atlasSection
            }
            .padding(MacSpacing.md)
        }
        .task {
            await viewModel.loadData()
        }
    }

    // MARK: - Success Section

    private var successSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            // Header
            HStack(spacing: MacSpacing.sm) {
                Circle()
                    .fill(Color.green)
                    .frame(width: 8, height: 8)
                Text("SUCCESS")
                    .font(.system(size: 11))
                    .tracking(0.8)
                    .foregroundStyle(Color.green)
            }

            // Card
            VStack(alignment: .leading, spacing: 0) {
                if viewModel.successAlerts.isEmpty {
                    centeredMessage("No recent activity", color: MacColors.textSecondary)
                } else {
                    ForEach(viewModel.successAlerts) { alert in
                        alertRow(alert)
                        if alert.id != viewModel.successAlerts.last?.id {
                            Divider()
                                .background(MacColors.divider)
                        }
                    }
                }
            }
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(cardBorder, lineWidth: 1)
            )
        }
    }

    // MARK: - Errors Section

    private var errorsSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            // Header
            HStack(spacing: MacSpacing.sm) {
                Circle()
                    .fill(Color.red)
                    .frame(width: 8, height: 8)
                Text("ERRORS")
                    .font(.system(size: 11))
                    .tracking(0.8)
                    .foregroundStyle(Color.red)
            }

            // Card with red-tinted border
            VStack(alignment: .leading, spacing: 0) {
                if viewModel.errorAlerts.isEmpty {
                    centeredMessage("All systems nominal", color: Color.green)
                } else {
                    ForEach(viewModel.errorAlerts) { alert in
                        alertRow(alert)
                        if alert.id != viewModel.errorAlerts.last?.id {
                            Divider()
                                .background(MacColors.divider)
                        }
                    }
                }
            }
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(Color(red: 255/255, green: 69/255, blue: 58/255).opacity(0.2), lineWidth: 1)
            )
        }
    }

    // MARK: - Atlas Alerts Section

    private var atlasSection: some View {
        VStack(alignment: .leading, spacing: MacSpacing.sm) {
            // Header
            HStack(spacing: MacSpacing.sm) {
                Circle()
                    .fill(MacColors.amberAccent)
                    .frame(width: 8, height: 8)
                Text("ATLAS ALERTS")
                    .font(.system(size: 11))
                    .tracking(0.8)
                    .foregroundStyle(MacColors.amberAccent)
            }

            // Card with amber-tinted border
            VStack(alignment: .leading, spacing: 0) {
                if viewModel.atlasAlerts.isEmpty {
                    centeredMessage("No security alerts", color: Color.green)
                } else {
                    ForEach(viewModel.atlasAlerts) { alert in
                        alertRow(alert)
                        if alert.id != viewModel.atlasAlerts.last?.id {
                            Divider()
                                .background(MacColors.divider)
                        }
                    }
                }
            }
            .padding(14)
            .background(
                RoundedRectangle(cornerRadius: 12)
                    .fill(cardBackground)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12)
                    .stroke(MacColors.amberAccent.opacity(0.2), lineWidth: 1)
            )
        }
    }

    // MARK: - Alert Row

    private func alertRow(_ alert: SystemAlertsTabViewModel.SystemAlert) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            HStack(spacing: MacSpacing.sm) {
                Image(systemName: alert.icon)
                    .font(.system(size: 11))
                    .foregroundStyle(alert.iconColor)

                Text(alert.title)
                    .font(.system(size: 11, weight: .medium))
                    .foregroundStyle(MacColors.textPrimary)
                    .lineLimit(1)

                Spacer()

                Text(formatTimestamp(alert.timestamp))
                    .font(.system(size: 10))
                    .foregroundStyle(MacColors.textSecondary)
            }

            Text(alert.detail)
                .font(.system(size: 10))
                .foregroundStyle(MacColors.textSecondary)
                .lineLimit(1)
                .padding(.leading, 22)
        }
        .padding(.vertical, MacSpacing.xs)
    }

    // MARK: - Helpers

    private func centeredMessage(_ text: String, color: Color) -> some View {
        Text(text)
            .font(.system(size: 11))
            .foregroundStyle(color)
            .frame(maxWidth: .infinity, minHeight: 60)
    }

    private func formatTimestamp(_ date: Date) -> String {
        let formatter = RelativeDateTimeFormatter()
        formatter.unitsStyle = .abbreviated
        return formatter.localizedString(for: date, relativeTo: Date())
    }
}
