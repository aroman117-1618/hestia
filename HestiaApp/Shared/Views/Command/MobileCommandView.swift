import SwiftUI
import HestiaShared

/// Card-based mobile command dashboard.
/// Trading condensed to one card (bot rows only show when unhealthy).
/// Orders removed. Feed shows scheduled orders, completed output, investigations.
/// Quick Actions moved to Force Touch menu.
struct MobileCommandView: View {
    @EnvironmentObject var appState: AppState
    @EnvironmentObject var apiClientProvider: APIClientProvider
    @EnvironmentObject var authService: AuthService
    @StateObject private var viewModel = MobileCommandViewModel()

    @State private var selectedPeriod = 0  // 0=7D, 1=30D, 2=3M

    var body: some View {
        ZStack {
            Color.black
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: Spacing.md) {
                    // Title
                    Text("Command")
                        .font(.system(size: 34, weight: .bold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.top, Spacing.lg)

                    // Condensed Trading Card
                    tradingCard

                    // Feed Card (replaces Orders + Newsfeed)
                    feedCard
                }
                .padding(.horizontal, Spacing.md)
                .padding(.top, Spacing.sm)
                .padding(.bottom, Spacing.xl)
            }
            .refreshable {
                await viewModel.loadAll()
            }
        }
        .onAppear {
            if apiClientProvider.isReady {
                viewModel.configure(client: apiClientProvider.client)
                Task { await viewModel.loadAll() }
            }
        }
        .onChange(of: apiClientProvider.isReady) { isReady in
            if isReady {
                viewModel.configure(client: apiClientProvider.client)
                Task { await viewModel.loadAll() }
            }
        }
    }

    // MARK: - Trading Card (Condensed)

    private var tradingCard: some View {
        HestiaCard(label: "TRADING") {
            VStack(spacing: Spacing.sm) {
                // Summary metrics + health badge
                HStack(spacing: Spacing.lg) {
                    statusMetric(
                        value: "\(viewModel.summary?.activeBots ?? 0)",
                        label: "Bots"
                    )
                    statusMetric(
                        value: formatPnl(viewModel.summary?.totalPnl ?? 0),
                        label: "P&L"
                    )
                    statusMetric(
                        value: "\(viewModel.summary?.totalTrades ?? 0)",
                        label: "Fills"
                    )
                    Spacer()
                    if let summary = viewModel.summary {
                        HestiaStatusBadge(
                            text: summary.killSwitchActive ? "Kill Active" : "Healthy",
                            status: summary.killSwitchActive ? .error : .healthy
                        )
                    }
                }

                // Period toggle (7D / 30D / 3M)
                Picker("Period", selection: $selectedPeriod) {
                    Text("7D").tag(0)
                    Text("30D").tag(1)
                    Text("3M").tag(2)
                }
                .pickerStyle(.segmented)
                .colorMultiply(Color(red: 1, green: 159/255, blue: 10/255))

                // Unhealthy bots only — if all healthy, show summary message
                let unhealthyBots = viewModel.bots.filter { $0.status != "running" }
                if unhealthyBots.isEmpty {
                    Text("All \(viewModel.bots.count) bots running normally")
                        .font(.caption)
                        .foregroundColor(.textSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, Spacing.xs)
                } else {
                    ForEach(unhealthyBots) { bot in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(bot.pair)
                                    .font(.body.weight(.medium))
                                    .foregroundColor(.textPrimary)
                                Text(bot.name)
                                    .font(.caption)
                                    .foregroundColor(.textSecondary)
                            }
                            Spacer()
                            HestiaStatusBadge(
                                text: bot.status.capitalized,
                                status: statusFor(bot.status)
                            )
                        }
                        .padding(.vertical, Spacing.xs)
                    }
                }

                Divider().background(Color.iosCardBorder)

                // Kill Switch
                Button {
                    viewModel.killSwitchConfirmation = true
                } label: {
                    HStack {
                        Image(systemName: viewModel.riskStatus?.killSwitch.active == true
                              ? "play.circle.fill" : "xmark.octagon.fill")
                        Text(viewModel.riskStatus?.killSwitch.active == true
                             ? "Reactivate Trading" : "Kill Switch")
                            .font(.body.weight(.semibold))
                    }
                    .foregroundColor(viewModel.riskStatus?.killSwitch.active == true ? .healthyGreen : .errorRed)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.sm)
                }
                .alert("Confirm", isPresented: $viewModel.killSwitchConfirmation) {
                    Button("Cancel", role: .cancel) {}
                    Button(
                        viewModel.riskStatus?.killSwitch.active == true ? "Reactivate" : "Kill All Trading",
                        role: viewModel.riskStatus?.killSwitch.active == true ? nil : .destructive
                    ) {
                        Task { await viewModel.toggleKillSwitch() }
                    }
                } message: {
                    Text(viewModel.riskStatus?.killSwitch.active == true
                         ? "Reactivate all trading bots?"
                         : "This will immediately stop all trading activity.")
                }
            }
        }
    }

    // MARK: - Feed Card (Scheduled Orders + Completed Output + Investigations)

    private var feedCard: some View {
        HestiaCard(label: "FEED") {
            if viewModel.newsfeedItems.isEmpty && viewModel.workflows.isEmpty
                && !viewModel.failedSections.contains("newsfeed")
                && !viewModel.failedSections.contains("workflows") {
                Text("No recent activity")
                    .font(.caption)
                    .foregroundColor(.textTertiary)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, Spacing.md)
            } else {
                VStack(spacing: 0) {
                    // Upcoming scheduled orders
                    ForEach(viewModel.workflows.filter { $0.status == "active" }.prefix(3)) { workflow in
                        feedRow(
                            icon: "clock.fill",
                            iconColor: Color(red: 1, green: 159/255, blue: 10/255),
                            title: workflow.name,
                            subtitle: "Scheduled",
                            showDivider: true
                        )
                    }

                    // Newsfeed items (completed output + investigations)
                    ForEach(Array(viewModel.newsfeedItems.prefix(5).enumerated()), id: \.element.id) { index, item in
                        feedRow(
                            icon: feedIcon(for: item),
                            iconColor: feedColor(for: item),
                            title: item.title,
                            subtitle: item.summary,
                            showDivider: index < min(viewModel.newsfeedItems.count - 1, 4)
                        )
                    }
                }
            }
        }
    }

    // MARK: - Feed Row

    private func feedRow(icon: String, iconColor: Color, title: String, subtitle: String?, showDivider: Bool) -> some View {
        VStack(spacing: 0) {
            HStack(alignment: .top, spacing: Spacing.sm) {
                Image(systemName: icon)
                    .font(.system(size: 13))
                    .foregroundColor(iconColor)
                    .frame(width: 28, height: 28)
                    .background(iconColor.opacity(0.15))
                    .cornerRadius(8)

                VStack(alignment: .leading, spacing: 2) {
                    Text(title)
                        .font(.body.weight(.medium))
                        .foregroundColor(.textPrimary)
                        .lineLimit(1)
                    if let subtitle, !subtitle.isEmpty {
                        Text(subtitle)
                            .font(.caption)
                            .foregroundColor(.textSecondary)
                            .lineLimit(2)
                    }
                }

                Spacer()
            }
            .padding(.vertical, Spacing.sm)

            if showDivider {
                Divider()
                    .background(Color.white.opacity(0.05))
            }
        }
    }

    // MARK: - Helpers

    private func statusMetric(value: String, label: String) -> some View {
        VStack(spacing: 2) {
            Text(value)
                .font(.title3.weight(.bold).monospacedDigit())
                .foregroundColor(.textPrimary)
            Text(label)
                .font(.caption2)
                .foregroundColor(.textSecondary)
        }
    }

    private func formatPnl(_ value: Double) -> String {
        let prefix = value >= 0 ? "+" : ""
        return "\(prefix)$\(String(format: "%.2f", value))"
    }

    private func statusFor(_ status: String) -> HestiaStatusBadge.Status {
        switch status.lowercased() {
        case "active", "running": return .healthy
        case "paused", "pending": return .warning
        case "failed", "error": return .error
        default: return .neutral
        }
    }

    private func feedIcon(for item: MobileNewsfeedItem) -> String {
        if item.title.lowercased().contains("investigat") { return "magnifyingglass" }
        if item.title.lowercased().contains("complete") || item.title.lowercased().contains("finished") { return "checkmark.circle.fill" }
        return "doc.text.fill"
    }

    private func feedColor(for item: MobileNewsfeedItem) -> Color {
        if item.title.lowercased().contains("investigat") { return Color(red: 90/255, green: 200/255, blue: 250/255) }
        if item.title.lowercased().contains("complete") || item.title.lowercased().contains("finished") { return .healthyGreen }
        return Color(red: 1, green: 159/255, blue: 10/255)
    }
}
